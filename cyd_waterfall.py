#!/usr/bin/env python3
"""cyd_waterfall.py — stream a downsampled SDR spectrum row to a CYD console.

The CYD has no SDR. When its Waterfall screen is open it asks Ragnar (over the
serial/HTTP link) to sweep a band; this module drives Ragnar's real SDR
(sdr_spectrum.py — hackrf_sweep) on that band and hands back a compact,
quantised row (WF_BINS bins, 0..255) the ESP32 scrolls into a low-res waterfall.

It is deliberately coarse — a 120-bin postage-stamp of a band, a few frames a
second — not the full web waterfall. It only produces data when a HackRF/RTL-SDR
is actually attached (else `{'err': 'no SDR'}`), and it auto-stops the sweep when
the CYD stops asking (`_STALE_SEC`), so the shared radio is freed on screen exit.
"""

import time
import threading

try:
    import sdr_spectrum
except Exception:  # pragma: no cover - SDR stack optional
    sdr_spectrum = None

WF_BINS = 120
_BASE_DBM = -110        # 0 in the quantised row
_SPAN_DB = 80           # -110..-30 dBm -> 0..255
_STALE_SEC = 15         # stop the sweep if the CYD stops asking

_LOCK = threading.RLock()
_band = None
_active = False
_since = 0
_last_req = 0.0
_avail_cache = (0.0, False)   # (checked_at, available) — probing opens the USB bus


def _available():
    global _avail_cache
    if sdr_spectrum is None:
        return False
    now = time.time()
    if now - _avail_cache[0] < 5.0:
        return _avail_cache[1]
    ok = False
    try:
        st = sdr_spectrum.status() or {}
        ok = bool((st.get('detect') or {}).get('available'))
    except Exception:
        ok = False
    _avail_cache = (now, ok)
    return ok


def _stop():
    global _active
    if _active and sdr_spectrum is not None:
        try:
            sdr_spectrum.stop()
        except Exception:
            pass
    _active = False


def request(band, on):
    """The CYD opened (`on`) or closed the waterfall on `band`. Start/stop the
    sweep accordingly. Safe to call repeatedly (it's the keep-alive)."""
    global _band, _active, _since, _last_req
    band = (str(band or '').strip() or '433')
    with _LOCK:
        _last_req = time.time()
        if not on:
            _stop()
            return
        if not _available():
            _active = False          # requested, but nothing to sweep with
            return
        if not _active or band != _band:
            try:
                sdr_spectrum.start(band=band)
                _band, _active, _since = band, True, 0
            except Exception:
                _active = False


def wants_stream():
    """True while the CYD is (recently) asking — the bridge should keep sending
    rows (data, waiting, or the no-SDR error) so the screen reflects reality."""
    with _LOCK:
        return (time.time() - _last_req) < _STALE_SEC


def _downsample_quant(power):
    n = len(power)
    out = []
    for i in range(WF_BINS):
        a = i * n // WF_BINS
        b = (i + 1) * n // WF_BINS
        if b <= a:
            b = a + 1
        seg = power[a:b]
        db = max(seg) if seg else _BASE_DBM
        v = int((db - _BASE_DBM) / _SPAN_DB * 255)
        out.append(0 if v < 0 else (255 if v > 255 else v))
    return out


def latest_row():
    """The current waterfall row for the CYD: a data row, `{'waiting':1}`, or
    `{'err': 'no SDR'}`. Also enforces the idle auto-stop."""
    global _since
    with _LOCK:
        if _active and (time.time() - _last_req) > _STALE_SEC:
            _stop()
        if not _available():
            return {'err': 'no SDR'}
        if not _active:
            return {'err': 'no SDR'}
        try:
            res = sdr_spectrum.get_frames(since=_since) or {}
        except Exception:
            return {'band': _band, 'waiting': 1}
        frames = res.get('frames') or []
        if not frames:
            return {'band': _band, 'waiting': 1}
        _since = res.get('seq', _since)
        latest = frames[-1]
        bm = res.get('band_mhz') or [0, 0]
        return {
            'seq': int(latest.get('seq', 0)),
            'band': _band,
            'lo': int(bm[0] or 0),
            'hi': int(bm[1] or 0),
            'bins': _downsample_quant(latest.get('power') or []),
        }
