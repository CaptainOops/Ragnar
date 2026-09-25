import json
import threading

import pytest

from toolkit import Toolkit


def test_port_watch_tracks_changes_within_network(tmp_path, monkeypatch):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    ports = [[80, 443], [443, 8080]]

    def command(argv, folder, cancel, **kwargs):
        assert argv[:2] == ['nmap', '-sT']
        assert argv[-1] == '192.0.2.4'
        nodes = ''.join(f'<port protocol="tcp" portid="{p}"><state state="open"/></port>' for p in ports.pop(0))
        (folder / 'output.txt').write_text('<nmaprun><host><ports>' + nodes + '</ports></host></nmaprun>')

    monkeypatch.setattr(kit, 'command', command)
    first = tmp_path / 'a'
    second = tmp_path / 'b'
    first.mkdir()
    second.mkdir()
    result1 = kit.execute('port_watch', {'target': '192.0.2.4'}, first, threading.Event())
    result2 = kit.execute('port_watch', {'target': '192.0.2.4'}, second, threading.Event())
    assert result1['baseline_created'] is True
    assert result2['new_ports'] == [8080]
    assert result2['closed_ports'] == [80]
    assert json.loads((tmp_path / 'port_watch_baselines.json').read_text())['192.0.2.4'] == [443, 8080]


def test_mac_validation_and_neighbor_lookup(tmp_path, monkeypatch):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    monkeypatch.setattr(kit, 'catalog', lambda: {'interfaces': ['eth0'], 'tools': [{'id': 'mac_presence', 'available': True}]})
    with pytest.raises(ValueError):
        kit.validate('mac_presence', {'target': '-bad', 'interface': 'eth0'})
    clean = kit.validate('mac_presence', {'target': 'AA:BB:CC:DD:EE:FF', 'interface': 'eth0'})
    assert clean['target'] == 'aa:bb:cc:dd:ee:ff'

    def command(argv, folder, cancel, **kwargs):
        assert argv == ['ip', '-j', 'neigh', 'show', 'dev', 'eth0']
        (folder / 'output.txt').write_text(json.dumps([{'dst': '192.0.2.2', 'lladdr': clean['target'], 'state': 'REACHABLE'}]))

    monkeypatch.setattr(kit, 'command', command)
    folder = tmp_path / 'job'
    folder.mkdir()
    assert kit.execute('mac_presence', clean, folder, threading.Event())['matches'][0]['ip'] == '192.0.2.2'


def test_quiet_scan_has_bounded_per_job_pacing(tmp_path, monkeypatch):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    monkeypatch.setattr(kit, 'catalog', lambda: {'interfaces': [], 'tools': [{'id': 'services', 'available': True}]})
    clean = kit.validate('services', {'target': '192.0.2.4', 'pace': 'quiet'})
    with pytest.raises(ValueError):
        kit.validate('services', {'target': '192.0.2.4', 'pace': '-sS'})
    seen = {}

    def command(argv, folder, cancel, **kwargs):
        seen['argv'] = argv
        seen['timeout'] = kwargs['timeout']

    monkeypatch.setattr(kit, 'command', command)
    kit.execute('services', clean, tmp_path, threading.Event())
    assert seen['argv'][-1] == '192.0.2.4'
    assert seen['argv'][-8:-1] == ['-T2', '--scan-delay', '250ms', '--max-rate', '10', '--max-retries', '1']
    assert seen['timeout'] == 180


def test_packet_replay_only_uses_saved_capture_with_limits(tmp_path, monkeypatch):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    job_id = 'a' * 32
    loot = tmp_path / 'toolkit'
    loot.mkdir()
    capture_dir = loot / job_id
    capture_dir.mkdir()
    capture = capture_dir / 'capture.pcap'
    capture.write_bytes(b'pcap')
    monkeypatch.setattr(kit, 'catalog', lambda: {'interfaces': ['eth0'], 'tools': [{'id': 'packet_replay', 'available': True}]})
    monkeypatch.setattr(kit, 'wired_carrier', lambda interface: interface == 'eth0')
    clean = kit.validate('packet_replay', {'target': job_id, 'interface': 'eth0'})
    folder = loot / 'newjob'
    folder.mkdir()
    seen = {}

    def command(argv, folder, cancel, **kwargs):
        seen['argv'] = argv
        seen['timeout'] = kwargs['timeout']

    monkeypatch.setattr(kit, 'command', command)
    kit.execute('packet_replay', clean, folder, threading.Event())
    assert seen['argv'] == ['tcpreplay', '--intf1', 'eth0', '--limit', '200',
                            '--pps', '10', '--duration', '30', str(capture)]
    assert seen['timeout'] == 35
    with pytest.raises(ValueError, match='connected wired interface'):
        kit.execute('packet_replay', {**clean, 'interface': 'wlan0'}, folder, threading.Event())


def test_responder_is_wired_bounded_and_analyze_by_default(tmp_path, monkeypatch):
    source = tmp_path / 'responder'
    source.mkdir()
    for name in ('Responder.py', 'Responder.conf', 'settings.py'):
        (source / name).write_text('')
    monkeypatch.setenv('RAGNAR_RESPONDER_DIR', str(source))
    kit = Toolkit(lambda: tmp_path, lambda: '')
    monkeypatch.setattr(kit, 'catalog', lambda: {'interfaces': ['eth0', 'wlan0'], 'tools': [{'id': 'responder', 'available': True}]})
    monkeypatch.setattr(kit, 'wired_carrier', lambda interface: interface == 'eth0')
    clean = kit.validate('responder', {'interface': 'eth0', 'duration': 10})
    assert clean['mode'] == 'analyze'
    with pytest.raises(ValueError, match='connected wired interface'):
        kit.validate('responder', {'interface': 'wlan0', 'duration': 10})
    with pytest.raises(ValueError):
        kit.validate('responder', {'interface': 'eth0', 'mode': 'bogus'})
    seen = {}

    def command(argv, folder, cancel, **kwargs):
        seen['argv'] = argv
        seen['kwargs'] = kwargs
        logs = kwargs['cwd'] / 'logs'
        logs.mkdir()
        (logs / 'Analyzer-Session.log').write_text('one query')
        return {'duration_limited': True}

    monkeypatch.setattr(kit, 'command', command)
    folder = tmp_path / 'job'
    folder.mkdir()
    result = kit.execute('responder', clean, folder, threading.Event())
    assert seen['argv'][-3:] == ['-I', 'eth0', '-A']
    assert seen['kwargs']['timeout'] == 10
    assert seen['kwargs']['capture'] is True
    assert result['logs'] == ['Analyzer-Session.log']
    assert (folder / 'responder_logs' / 'Analyzer-Session.log').read_text() == 'one query'
    kit.execute('responder', {**clean, 'mode': 'active'}, folder, threading.Event())
    assert seen['argv'][-2:] == ['-I', 'eth0']
    with pytest.raises(ValueError, match='connected wired'):
        kit.execute('responder', {**clean, 'interface': 'wlan0'}, folder, threading.Event())
