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
_since = 0
_last_req = 0.0
_avail_cache = (0.0, None)   # (checked_at, backend) — probing opens the USB bus


def _detect_backend():
    """Return 'hackrf', 'rtl', or None — memoised 5 s (probes open the USB bus)."""
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
            if bool(rtl_sdr.detect().get('available')):
                backend = 'rtl'
        except Exception:
            pass
    _avail_cache = (now, backend)
    return backend


# RTL-SDR can't reach 2.4/5/6 GHz; remap those requests to a sub-GHz ISM band so
# the screen shows something useful instead of an error on an RTL-only box.
_RTL_BAND_FALLBACK = {'2.4': '433', '5': '433', '6': '433'}


def _start(backend, band):
    if backend == 'hackrf':
        sdr_spectrum.start(band=band)
    else:
        band = _RTL_BAND_FALLBACK.get(band, band)
        rtl_sdr.power_start(band=band)


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
    global _active
    if _active and _backend:
        _stop_backend(_backend)
    _active = False


def request(band, on):
    """The CYD opened (`on`) or closed the waterfall on `band`. Start/stop the
    sweep on whichever SDR is present. Safe to call repeatedly (keep-alive)."""
    global _band, _backend, _active, _since, _last_req
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
        if not _active or band != _band or backend != _backend:
            if _active and _backend and _backend != backend:
                _stop_backend(_backend)
            try:
                _start(backend, band)
                _band, _backend, _active, _since = band, backend, True, 0
            except Exception:
                _active = False


def wants_stream():
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
            'bins': _downsample_quant(latest.get('power') or []),
        }
