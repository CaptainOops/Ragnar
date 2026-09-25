import threading

import pytest
from PIL import Image, ImageFont
from toolkit_activity import Activity, draw_activity
from toolkit import Toolkit


def test_concurrent_activity_and_expiry(monkeypatch):
    clock = [0]
    state = Activity(lambda: clock[0])
    first = dict(id='one', name='Headers', status='running', target='private')
    second = dict(id='two', name='Honeypot', status='running')
    state.update(first)
    state.update(second)
    state.update(dict(first, status='failed'))
    assert state.snapshot() == dict(second, active=1)
    state.update(dict(second, status='cancelled'))
    assert state.snapshot()['status'] == 'cancelled'
    assert 'target' not in state.snapshot()
    monkeypatch.setattr('toolkit_activity.activity', state)
    image = Image.new('1', (320, 480), 255)
    draw_activity(image, ImageFont.load_default())
    assert image.getextrema() == (0, 255)
    clock[0] = 21
    assert state.snapshot() is None
    image = Image.new('1', (320, 480), 255)
    draw_activity(image, ImageFont.load_default())
    assert image.getextrema() == (255, 255)


def test_mdns_filters_actual_avahi_format_and_preserves_failures(tmp_path, monkeypatch):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    def command(argv, folder, cancel, **kwargs):
        assert not any(arg.startswith('--interface') for arg in argv)
        (folder / 'output.txt').write_text('+;eth0;IPv4;Other;_http._tcp;local\n=;wlan0;IPv4;Printer;_ipp._tcp;local;printer.local;192.0.2.1;631;\n')
    monkeypatch.setattr(kit, 'command', command)
    result = kit.execute('mdns', {'interface': 'wlan0'}, tmp_path, threading.Event())
    assert result['resolved'] == 1
    assert 'Other' not in (tmp_path / 'output.txt').read_text()
    def fail(*args, **kwargs):
        (tmp_path / 'output.txt').write_text('Daemon not running')
        raise ValueError('Tool exited with an error; see output.txt.')
    monkeypatch.setattr(kit, 'command', fail)
    with pytest.raises(ValueError):
        kit.execute('mdns', {'interface': 'wlan0'}, tmp_path, threading.Event())
    assert (tmp_path / 'output.txt').read_text() == 'Daemon not running'
