"""power_tools: Pi 5 USB current-limit config editing + USB dropout parsing."""
import power_tools as pt


def _pi5(monkeypatch, tmp_path, text, live=0, psu=3000):
    cfg = tmp_path / 'config.txt'
    cfg.write_text(text)
    monkeypatch.setattr(pt, '_boot_cfg', lambda: str(cfg))
    monkeypatch.setattr(pt, '_model', lambda: 'Raspberry Pi 5 Model B Rev 1.1')
    monkeypatch.setattr(pt, '_dt_u32', lambda n: {
        'usb_max_current_enable': live, 'max_current': psu}[n])
    return cfg


def test_not_pi5(monkeypatch):
    monkeypatch.setattr(pt, '_model', lambda: 'Raspberry Pi 4 Model B Rev 1.4')
    monkeypatch.setattr(pt.os.path, 'exists', lambda p: False)
    st = pt.usb_current_status()
    assert st['applies'] is False
    assert pt.set_usb_max_current(True)['success'] is False


def test_section_filters_respected():
    assert pt._configured_value('usb_max_current_enable=1\n') is True
    assert pt._configured_value('[pi4]\nusb_max_current_enable=1\n') is None
    assert pt._configured_value('[cm5]\nx=1\n[all]\nusb_max_current_enable=1') is True
    assert pt._configured_value('usb_max_current_enable=1\n[pi5]\n'
                                'usb_max_current_enable=0\n') is False


def test_enable_lands_under_all_even_after_filter(monkeypatch, tmp_path):
    cfg = _pi5(monkeypatch, tmp_path, 'dtparam=audio=on\n[cm4]\notg_mode=1\n')
    st = pt.set_usb_max_current(True)
    assert st['success'] and st['configured'] is True
    assert st['pending_reboot'] is True          # live flag still 0
    assert st['usb_limit_ma'] == 600             # not active until reboot
    assert pt._configured_value(cfg.read_text()) is True
    assert list(tmp_path.glob('config.txt.ragnar-*'))   # backup taken


def test_toggle_is_idempotent_and_disable_is_explicit(monkeypatch, tmp_path):
    cfg = _pi5(monkeypatch, tmp_path, 'usb_max_current_enable=1\n')
    for _ in range(3):
        pt.set_usb_max_current(True)
    pt.set_usb_max_current(False)
    text = cfg.read_text()
    assert text.count('usb_max_current_enable') == 1
    assert text.count('[all]') == 1
    assert 'usb_max_current_enable=0' in text    # installer must not re-enable


def test_live_and_5a_supply(monkeypatch, tmp_path):
    _pi5(monkeypatch, tmp_path, '', live=0, psu=5000)
    st = pt.usb_current_status()
    assert st['pd_5a_supply'] and st['usb_limit_ma'] == 1600
    _pi5(monkeypatch, tmp_path, 'usb_max_current_enable=1\n', live=1)
    st = pt.usb_current_status()
    assert st['usb_limit_ma'] == 1600 and st['pending_reboot'] is False


def test_dropout_loop_detection():
    log = '\n'.join([
        '[221736.614780] usb 5-1: USB disconnect, device number 60',
        '[221744.011906] usb 5-1: USB disconnect, device number 61',
        '[221751.402000] usb 5-1: USB disconnect, device number 62',
        '[300000.000000] usb 1-1.2: USB disconnect, device number 5',
        '[300001.000000] usb 1-1.2: new high-speed USB device number 6',
    ])
    d = pt.usb_dropouts(log)
    ports = {p['port']: p for p in d['ports']}
    assert d['total'] == 4 and d['looping'] is True
    assert ports['5-1']['loop'] is True and ports['5-1']['count'] == 3
    assert ports['1-1.2']['loop'] is False       # a single unplug is not a loop


def test_verdict_recommends_usb_limit_on_pi5():
    idle = pt._summarise([], 0)
    load = pt._summarise([], 5)
    v = pt._verdict(idle, load, {}, {'applies': True, 'usb_limit_ma': 600})
    assert v['ok'] is False
    assert any('1.6 A' in a for a in v['advice'])
    v = pt._verdict(idle, pt._summarise([], 0), {}, {'applies': False})
    assert v['ok'] is True


def test_rtl_sdr_not_counted_as_wifi():
    import power_budget
    role, _typ, peak = power_budget._classify({
        'vendor_id': '0bda', 'product_id': '2838', 'product': 'RTL2838UHIDIR',
        'manufacturer': 'Realtek', 'class': '00'})
    assert role == 'RTL-SDR receiver' and peak == 300
