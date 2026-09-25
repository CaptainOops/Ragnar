import wipe_epd


def test_tft_switch_never_initializes_epaper(monkeypatch):
    monkeypatch.setattr(wipe_epd, 'resolve_epd_type', lambda: 'ili9486')
    def unexpected(_):
        raise AssertionError('TFT must not initialize an e-paper driver')
    monkeypatch.setattr(wipe_epd, 'wipe_display', unexpected)
    assert wipe_epd.main() == 0


def test_epaper_still_cleared(monkeypatch):
    calls = []
    monkeypatch.setattr(wipe_epd, 'resolve_epd_type', lambda: 'epd2in13_V4')
    monkeypatch.setattr(wipe_epd, 'wipe_display', calls.append)
    assert wipe_epd.main() == 0
    assert calls == ['epd2in13_V4']
