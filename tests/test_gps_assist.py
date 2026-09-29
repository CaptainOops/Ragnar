"""Tests for gps_assist — the self-aided start that pre-loads a battery-less
u-blox receiver with position, time and its own saved almanac/ephemeris.

The frames go to real hardware with no feedback beyond ACK/NAK, so the byte
layouts are pinned here against the u-blox protocol spec, and the policy
(never inject an untrusted time, never replay stale orbit data, never wipe a
good saved almanac with an empty poll) is locked down.
"""

import struct
import time
from calendar import timegm
from unittest.mock import MagicMock, patch

import gps_assist as ga
from gps_manager import GPSManager


def _payload(frame):
    assert frame[:2] == ga.UBX_SYNC
    (length,) = struct.unpack_from('<H', frame, 4)
    assert len(frame) == 8 + length
    return frame[2], frame[3], frame[6:-2]


def test_gps_week_tow_known_epoch():
    # GPS week 1930 began 2017-01-01 00:00:00 GPS = 23:59:42 UTC the day
    # before (18 leap seconds), so UTC midnight is 18 s into the week.
    assert ga.gps_week_tow(timegm((2017, 1, 1, 0, 0, 0))) == (1930, 18000)


def test_aid_ini_layout_position_and_time():
    t = timegm((2017, 1, 1, 0, 0, 0))
    cls, mid, p = _payload(ga.aid_ini_frame(59.3066, 18.0256, 21.5, t))
    assert (cls, mid, len(p)) == (0x0B, 0x01, 48)
    (lat, lon, alt, pacc, tmcfg, wno, tow, _tow_ns, tacc_ms, _tacc_ns,
     _clkd, _clkdacc, flags) = struct.unpack('<iiiIhHIiIIiII', p)
    assert (lat, lon, alt) == (593066000, 180256000, 2150)
    assert pacc == ga.POS_ACC_M * 100
    assert (wno, tow, tacc_ms, tmcfg) == (1930, 18000, ga.TIME_ACC_MS, 0)
    assert flags == 0x01 | 0x02 | 0x20          # pos, time, LLA


def test_aid_ini_position_only_without_altitude():
    p = _payload(ga.aid_ini_frame(59.0, 18.0, None, None))[2]
    flags = struct.unpack_from('<I', p, 44)[0]
    assert flags == 0x01 | 0x20 | 0x40          # pos, LLA, altInv — no time


def test_mga_frames_layout():
    cls, mid, p = _payload(ga.mga_ini_pos_frame(59.3066, 18.0256, 21.5))
    assert (cls, mid, len(p), p[0]) == (0x13, 0x40, 20, 0x01)
    cls, mid, p = _payload(ga.mga_ini_time_frame(timegm((2026, 9, 29, 7, 8, 9))))
    assert (cls, mid, len(p), p[0]) == (0x13, 0x40, 24, 0x10)
    assert struct.unpack_from('<HBBBBB', p, 4) == (2026, 9, 29, 7, 8, 9)


def test_parse_roundtrip_skips_noise_and_bad_checksum():
    good = ga.ubx_frame(0x0B, 0x30, bytes(40))
    bad = bytearray(ga.ubx_frame(0x0B, 0x31, bytes(8)))
    bad[-1] ^= 0xFF
    stream = b'{"class":"VERSION"}\n' + bytes(bad) + good + b'$GPGGA,,\r\n' + good[:5]
    assert ga.parse_ubx_frames(stream) == [(0x0B, 0x30, bytes(40))]


def _alm(sv):
    return (0x0B, 0x30, struct.pack('<II', sv, 2400) + bytes(32))


def _eph(sv):
    return (0x0B, 0x31, struct.pack('<II', sv, 1) + bytes(96))


def test_update_store_keeps_only_real_data_and_never_wipes():
    store = {}
    frames = [_alm(1), _alm(2), (0x0B, 0x30, struct.pack('<II', 3, 0)),
              _eph(5), (0x0B, 0x31, struct.pack('<II', 6, 0))]
    assert ga.update_store(store, frames, 1000.0) == (2, 1, False)
    assert set(store['alm']) == {'1', '2'} and set(store['eph']) == {'5'}
    # A later poll with no ephemeris (receiver lost track) keeps the old set.
    assert ga.update_store(store, [_alm(7)], 2000.0) == (1, 0, False)
    assert set(store['alm']) == {'7'} and store['eph_saved_at'] == 1000.0


def test_build_frames_policy():
    now = 1_790_000_000.0
    last = {'lat': 59.3, 'lon': 18.0, 'alt': 20.0}
    store = {'alm': {'1': (struct.pack('<II', 1, 2400) + bytes(32)).hex()},
             'alm_saved_at': now - 86400,
             'eph': {'5': (struct.pack('<II', 5, 1) + bytes(96)).hex()},
             'eph_saved_at': now - 5 * 3600}          # stale: > 4 h

    frames, summary = ga.build_assist_frames(last, now, True, store)
    kinds = [_payload(f)[:2] for f in frames]
    assert kinds[0] == (0x0B, 0x01)                   # AID-INI first
    assert (0x0B, 0x30) in kinds and (0x0B, 0x31) not in kinds
    assert any('time' in s for s in summary)

    # Untrusted clock: position only, no time, no orbit data.
    frames, summary = ga.build_assist_frames(last, now, False, store)
    assert [_payload(f)[:2] for f in frames] == [(0x0B, 0x01), (0x13, 0x40)]
    flags = struct.unpack_from('<I', _payload(frames[0])[2], 44)[0]
    assert not flags & 0x02

    # Nothing known at all: send nothing.
    assert ga.build_assist_frames(None, now, False, store) == ([], [])


def _mgr(tmp_path, **kw):
    m = GPSManager(port='/dev/ttyACM0', state_file=str(tmp_path / 'last_gps.json'), **kw)
    m._serial = MagicMock()
    m.last_known = {'lat': 59.3, 'lon': 18.0, 'alt': None, 't': 1}
    m.start_time = time.time() - 10
    m.last_sentence = time.time()
    return m


def test_manager_preloads_once_when_no_fix(tmp_path):
    m = _mgr(tmp_path)
    with patch.object(GPSManager, '_run_bg', staticmethod(lambda fn: fn())), \
            patch('gps_assist.clock_is_synced', return_value=True), \
            patch('gps_manager.time.sleep'):
        m._assist_tick()
        m._assist_tick()
    written = [c.args[0] for c in m._serial.write.call_args_list]
    assert written and _payload(written[0])[:2] == (0x0B, 0x01)
    assert sum(_payload(f)[:2] == (0x0B, 0x01) for f in written) == 1
    assert m.get_status()['assist']['via'] == 'serial'


def test_manager_skips_preload_when_disabled_or_already_fixed(tmp_path):
    m = _mgr(tmp_path, assist=False)
    m._assist_tick()
    assert not m._serial.write.called

    m = _mgr(tmp_path)
    m.fix_quality, m.latitude, m.longitude = 1, 59.3, 18.0
    m.last_update = time.time()
    with patch.object(GPSManager, '_run_bg', staticmethod(lambda fn: fn())):
        m._assist_tick()
    assert not m._serial.write.called


def test_manager_serial_capture_saves_store(tmp_path):
    m = _mgr(tmp_path)
    m._assist_done = True
    m._ubx_capture = bytearray(ga.ubx_frame(*_alm(3)) + ga.ubx_frame(*_eph(9)))
    m._ubx_capture_until = 0
    m._assist_tick()
    store = ga.load_store(m._aid_file)
    assert set(store['alm']) == {'3'} and set(store['eph']) == {'9'}
    assert m.get_status()['aid_saved']['eph'] == 1


def test_manager_saves_soon_after_fix_then_followup(tmp_path):
    m = _mgr(tmp_path)
    m._assist_done = True
    m.fix_quality, m.latitude, m.longitude = 1, 59.3, 18.0
    calls = []
    with patch.object(GPSManager, '_run_bg', staticmethod(calls.append)):
        m.last_update = time.time()
        m._assist_tick()                       # fix just appeared: too early
        assert not calls
        m._fix_since = time.time() - GPSManager._AID_SAVE_AFTER_FIX_S
        m._assist_tick()
        assert len(calls) == 1                 # early save fires
        m._aid_busy = False
        assert m._aid_next_save - time.time() <= GPSManager._AID_SAVE_FOLLOWUP_S
