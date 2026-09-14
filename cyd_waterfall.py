#!/usr/bin/env python3
"""cyd_waterfall.py — stream a downsampled SDR spectrum row to a CYD console.

The CYD has no SDR. When its Waterfall screen is open it asks Ragnar to sweep a
band; this module drives Ragnar's real SDR and hands back a compact, quantised
row (WF_BINS bins, 0..255) the ESP32 scrolls into a low-res waterfall.

Ragnar has two SDR stacks and either may be attached:
  * HackRF  → sdr_spectrum.py (hackrf_sweep), bands 1 MHz-6 GHz incl. 2.4/5/6.
  * RTL-SDR → rtl_sdr.py (rtl_power / IQ FFT), sub-GHz + fm/air (no 2.4/5/6).
This module auto-selects whichever is present (HackRF preferred), so a plain
RTL-SDR on the Pi now feeds the waterfall (the earlier HackRF-only path reported
'no SDR' with an RTL dongle attached). Coarse by design; auto-stops the sweep
when the CYD stops asking, freeing the shared radio.
"""

import time
import threading

try:
    import sdr_spectrum          # HackRF
except Exception:  # pragma: no cover
    sdr_spectrum = None
try:
    import rtl_sdr               # RTL-SDR
except Exception:  # pragma: no cover
    rtl_sdr = None

WF_BINS = 120
_BASE_DBM = -110        # 0 in the quantised row
_SPAN_DB = 80           # -110..-30 dBm -> 0..255
_STALE_SEC = 15         # stop the sweep if the CYD stops asking

_LOCK = threading.RLock()
_band = None
_backend = None         # 'hackrf' | 'rtl' | None
_active = False
_we_started = False     # did WE start the sweep? (else we piggyback; never stop it)
_since = 0
_last_req = 0.0
_avail_cache = (0.0, None)   # (checked_at, backend) — probing opens the USB bus


def _rtl_sweeping():
    """True if an RTL power sweep is already running (e.g. the web RF-waterfall)."""
    try:
        return bool((rtl_sdr.status().get('power') or {}).get('running'))
    except Exception:
        return False


def _detect_backend():
    """Return 'hackrf', 'rtl', or None — memoised 5 s. Uses streaming-aware status
    so a device already sweeping (busy) still counts as available; a raw detect()
    probe would fail on a busy dongle (that's why the CYD said 'no SDR'/'waiting'
    while the web waterfall held the RTL-SDR)."""
    global _avail_cache
    now = time.time()
    if now - _avail_cache[0] < 5.0:
        return _avail_cache[1]
    backend = None
    if sdr_spectrum is not None:
        try:
            if bool((sdr_spectrum.status().get('detect') or {}).get('available')):
                backend = 'hackrf'
        except Exception:
            pass
    if backend is None and rtl_sdr is not None:
        try:
            if _rtl_sweeping() or bool(rtl_sdr.detect().get('available')):
                backend = 'rtl'
        except Exception:
            pass
    _avail_cache = (now, backend)
    return backend


# RTL-SDR can't reach 2.4/5/6 GHz; remap those requests to a sub-GHz ISM band so
# the screen shows something useful instead of an error on an RTL-only box.
_RTL_BAND_FALLBACK = {'2.4': '433', '5': '433', '6': '433'}


def _start(backend, band):
    """Start a sweep and return True if WE started it (False = piggybacking an
    already-running sweep, which we must not stop or retune)."""
    if backend == 'hackrf':
        sdr_spectrum.start(band=band)
        return True
    # RTL: if a sweep is already running (web RF-waterfall etc.), just read it.
    if _rtl_sweeping():
        return False
    rtl_sdr.power_start(band=_RTL_BAND_FALLBACK.get(band, band))
    return True


def _stop_backend(backend):
    try:
        if backend == 'hackrf':
            sdr_spectrum.stop()
        elif backend == 'rtl':
            rtl_sdr.power_stop()
    except Exception:
        pass


def _frames(backend, since):
    if backend == 'hackrf':
        return sdr_spectrum.get_frames(since=since) or {}
    return rtl_sdr.power_frames(since=since) or {}


def _stop():
    global _active, _we_started
    if _active and _backend and _we_started:
        _stop_backend(_backend)      # only stop a sweep we started ourselves
    _active = False
    _we_started = False


def request(band, on):
    """The CYD opened (`on`) or closed the waterfall on `band`. Start/stop the
    sweep on whichever SDR is present. Safe to call repeatedly (keep-alive)."""
    global _band, _backend, _active, _we_started, _since, _last_req
    band = (str(band or '').strip() or '433')
    with _LOCK:
        _last_req = time.time()
        if not on:
            _stop()
            return
        backend = _detect_backend()
        if not backend:
            _active = False
            return
        # Self-healing: called ~every 1.5s while the screen is open, so re-verify
        # each time instead of starting once. For RTL, trust the actual sweep
        # state (a sweep that never came up, or died, gets (re)started; an
        # already-running one — ours or the web page's — is piggybacked).
        if backend == 'rtl':
            sweeping = _rtl_sweeping()
            if sweeping:
                if not _active or _backend != 'rtl':
                    _band, _backend, _active, _we_started, _since = band, 'rtl', True, False, 0
            elif (not _active) or _we_started:      # our sweep isn't up — (re)start it
                try:
                    rtl_sdr.power_start(band=_RTL_BAND_FALLBACK.get(band, band))
                    _band, _backend, _active, _we_started, _since = band, 'rtl', True, True, 0
                except Exception:
                    _active = False
        else:  # hackrf
            if not _active or _backend != 'hackrf' or (band != _band and _we_started):
                try:
                    sdr_spectrum.start(band=band)
                    _band, _backend, _active, _we_started, _since = band, 'hackrf', True, True, 0
                except Exception:
                    _active = False


def wants_stream():
    with _LOCK:
        return (time.time() - _last_req) < _STALE_SEC


def _downsample_quant(power, floor=None):
    """Downsample to WF_BINS and quantise 0..255 across [floor .. -20 dBm] so the
    contrast tracks the live noise floor (a fixed -110..-30 range made everything
    saturate on a high auto-gain floor — the 'all red' look). Robust floor: the
    10th-percentile of the frame when floor_dbm isn't given."""
    n = len(power)
    if not n:
        return [0] * WF_BINS
    if floor is None:
        s = sorted(power)
        floor = s[len(s) // 10]
    base = float(floor)
    top = -20.0
    span = top - base
    if span < 12:
        span = 12.0
    out = []
    for i in range(WF_BINS):
        a = i * n // WF_BINS
        b = (i + 1) * n // WF_BINS
        if b <= a:
            b = a + 1
        seg = power[a:b]
        db = max(seg) if seg else base
        v = int((db - base) / span * 255)
        out.append(0 if v < 0 else (255 if v > 255 else v))
    return out


def latest_row():
    """The current waterfall row for the CYD: a data row, `{'waiting':1}`, or
    `{'err': 'no SDR'}`. Enforces the idle auto-stop."""
    global _since
    with _LOCK:
        if _active and (time.time() - _last_req) > _STALE_SEC:
            _stop()
        if not _detect_backend() or not _active:
            return {'err': 'no SDR'}
        try:
            res = _frames(_backend, _since)
        except Exception:
            return {'band': _band, 'waiting': 1}
        frames = res.get('frames') or []
        if not frames:
            return {'band': _band, 'waiting': 1}
        _since = res.get('seq', _since)
        latest = frames[-1]
        # HackRF reports band_mhz; RTL reports band_hz.
        bm = res.get('band_mhz')
        if not bm:
            bh = res.get('band_hz') or [0, 0]
            bm = [(bh[0] or 0) / 1e6, (bh[1] or 0) / 1e6]
        return {
            'seq': int(latest.get('seq', 0)),
            'band': _band,
            'lo': int(bm[0] or 0),
            'hi': int(bm[1] or 0),
            'bins': _downsample_quant(latest.get('power') or [], res.get('floor_dbm')),
        }
