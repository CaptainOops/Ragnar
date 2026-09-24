import json
import socket
import threading
import time

import pytest
from flask import Flask

from env_manager import EnvManager
from toolkit import Toolkit, Stopped
from toolkit_api import create_blueprint
from toolkit_honeypot import listen
from watchtower import Watchtower


def test_library_revision_syntax_and_network_isolation(tmp_path):
    kit = Toolkit(lambda: tmp_path / 'first', lambda: '')
    first = kit.payloads.save('hello', 'print("hello")')
    with pytest.raises(ValueError, match='Reload'):
        kit.payloads.save('hello', 'print("changed")')
    with pytest.raises(ValueError, match='syntax'):
        kit.payloads.save('broken', 'def')
    with pytest.raises(ValueError, match='syntax'):
        kit.payloads.save('top-level-return', 'return 1')
    with pytest.raises(ValueError, match='name'):
        kit.payloads.read('../../secret')
    updated = kit.payloads.save('hello', 'print("changed")', first['revision'])
    assert updated['revision'] != first['revision']
    kit.loot_root = lambda: tmp_path / 'second'
    assert kit.payloads.list() == []


def test_payload_run_snapshots_source_and_context(tmp_path):
    kit = Toolkit(lambda: tmp_path / 'first', lambda: '')
    saved = kit.payloads.save('hello', 'import os\nprint(os.environ["RAGNAR_LOOT_DIR"])')
    root = kit.root()
    job = kit.start('payload', {'target': 'hello', 'duration': 5})
    kit.payloads.save('hello', 'raise Exception("new version")', saved['revision'])
    kit.loot_root = lambda: tmp_path / 'second'
    deadline = time.monotonic() + 8
    while kit.running and time.monotonic() < deadline:
        time.sleep(.02)
    folder = root / job['id']
    assert json.loads((folder / 'report.json').read_text())['status'] == 'completed'
    assert 'new version' not in (folder / 'payload.py').read_text()
    assert str(root.parent) in (folder / 'output.txt').read_text()
    assert json.loads((folder / 'context.json').read_text())['network_loot'] == str(root.parent)


def test_payload_api_and_cross_origin(tmp_path):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(kit, EnvManager(str(tmp_path / '.env'))))
    client = app.test_client()
    assert client.post('/api/toolkit/payloads', json={'name': 'x', 'source': 'print(1)'},
                       headers={'Origin': 'https://other.example'}).status_code == 403
    # >4 KiB scripts are accepted, source still has its own 64 KiB bound.
    source = '# comment\n' * 800 + 'print(1)'
    response = client.post('/api/toolkit/payloads', json={'name': 'x', 'source': source})
    assert response.status_code == 200
    assert client.post('/api/toolkit/payloads/check', json={'source': 'def'}).status_code == 400
    revision = response.json['revision']
    assert client.delete('/api/toolkit/payloads/x', json={'revision': revision}).status_code == 200


def test_honeypot_conflict_cancel_and_metadata_only(tmp_path):
    occupied = socket.socket()
    occupied.bind(('127.0.0.1', 0))
    occupied.listen()
    port = occupied.getsockname()[1]
    with pytest.raises(ValueError, match='port already in use'):
        listen('127.0.0.1', port, 'http', 5, tmp_path, threading.Event())
    occupied.close()
    cancel = threading.Event()
    results = []
    thread = threading.Thread(target=lambda: results.append(listen('127.0.0.1', port, 'http', 5, tmp_path, cancel)))
    thread.start()
    deadline = time.monotonic() + 2
    while True:
        try:
            client = socket.create_connection(('127.0.0.1', port), timeout=.3)
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(.02)
    with client:
        client.sendall(b'GET / HTTP/1.1\r\nAuthorization: secret-password\r\n\r\n')
        assert b'503 Service Unavailable' in client.recv(4096)
    cancel.set()
    thread.join(2)
    assert not thread.is_alive()
    events = (tmp_path / 'events.jsonl').read_text()
    assert 'secret-password' not in events
    assert results[0]['connections'] == 1
    assert results[0]['events'] == 2


def test_payload_cancellation(tmp_path):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    kit.payloads.save('wait', 'import time\nprint("started", flush=True)\ntime.sleep(60)')
    job = kit.start('payload', {'target': 'wait', 'duration': 120})
    kit.cancel(job['id'])
    deadline = time.monotonic() + 5
    while kit.running and time.monotonic() < deadline:
        time.sleep(.02)
    assert not kit.running
    assert kit.jobs()[0]['status'] == 'cancelled'


def test_honeypot_uses_existing_watchtower_normalizer(tmp_path):
    logs = tmp_path / 'logs'
    kit = Toolkit(lambda: tmp_path, lambda: '', event_dir=logs)
    try:
        tower = Watchtower(dirs=[str(logs)], tail_only=False)
        kit.emit_honeypot_event(dict(source='192.0.2.4', address='192.0.2.5', port=8088,
                                    service='http'), tmp_path / 'toolkit' / ('a' * 32))
        alerts = tower.poll()
        assert len(alerts) == 1
        assert alerts[0]['src'] == '192.0.2.4'
        assert alerts[0]['codes'] == ['HONEYPOT_CONNECTION']
    finally:
        kit.event_handler.close()


def test_fast_payload_output_is_capped(tmp_path):
    kit = Toolkit(lambda: tmp_path, lambda: '')
    kit.payloads.save('large-output', 'print("x" * 1200000)')
    job = kit.start('payload', {'target': 'large-output', 'duration': 5})
    deadline = time.monotonic() + 8
    while kit.running and time.monotonic() < deadline:
        time.sleep(.02)
    assert not kit.running
    assert kit.jobs()[0]['status'] == 'failed'
    assert kit.artifact(job['id'], 'output.txt').stat().st_size == 1024 * 1024
