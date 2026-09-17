import json
import sys
import threading
import time

import pytest
from flask import Flask

from env_manager import EnvManager
from toolkit import Toolkit, Stopped, host
from toolkit_api import create_blueprint, KEY


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr('toolkit.shutil.which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr('toolkit.socket.if_nameindex', lambda: [(2, 'eth0')])
    return Toolkit(lambda: tmp_path / 'loot', lambda: 'testkey1234567890')


@pytest.mark.parametrize('value', ['-oX', 'host;id', '$(id)', 'http://example.com', '10.0.0.0/24', 'x\ny', 'a..b'])
def test_reject_command_and_multiple_targets(value):
    with pytest.raises(ValueError):
        host(value)


def test_validation(engine):
    assert host('2001:db8::1') == '2001:db8::1'
    assert engine.validate('capture', {'interface': 'eth0', 'duration': 10})['duration'] == 10
    for params in ({'interface': 'eth0', 'duration': 121}, {'interface': 'eth0;id'}, {'interface': 'eth0', 'profile': '-w'}):
        with pytest.raises(ValueError):
            engine.validate('capture', params)
    with pytest.raises(ValueError):
        engine.validate('shodan_host', {'target': '192.168.1.1'})
    with pytest.raises(ValueError):
        engine.artifact('../etc', 'passwd')


def wait_done(engine):
    deadline = time.monotonic() + 4
    while engine.running and time.monotonic() < deadline:
        time.sleep(.01)
    assert not engine.running


def test_jobs_freeze_network_and_cancel(engine, tmp_path, monkeypatch):
    started = threading.Event()
    def work(tool, params, folder, cancel):
        started.set()
        cancel.wait(3)
        raise Stopped()
    monkeypatch.setattr(engine, 'execute', work)
    first_root = engine.root()
    job = engine.start('ping', {'target': 'localhost'})
    assert started.wait(1)
    engine.loot_root = lambda: tmp_path / 'second'
    assert engine.cancel(job['id'])
    wait_done(engine)
    report = json.loads((first_root / job['id'] / 'report.json').read_text())
    assert report['status'] == 'cancelled'
    assert engine.jobs() == []


def test_success_and_limit(engine, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(engine, 'execute', lambda *args: (release.wait(3), {'ok': True})[1])
    jobs = [engine.start('interfaces', {}) for _ in range(2)]
    with pytest.raises(ValueError, match='already running'):
        engine.start('interfaces', {})
    release.set()
    wait_done(engine)
    assert all(j['status'] == 'completed' for j in engine.jobs())
    assert json.loads(engine.artifact(jobs[0]['id'], 'result.json').read_text()) == {'ok': True}


def test_cancel_terminates_process(engine, tmp_path):
    cancel = threading.Event()
    cancel.set()
    start = time.monotonic()
    with pytest.raises(Stopped):
        engine.command([sys.executable, '-c', 'import time; time.sleep(20)'], tmp_path, cancel)
    assert time.monotonic() - start < 4


def test_fixed_nmap_argv(engine, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(engine, 'command', lambda argv, *a, **kw: calls.append(argv))
    engine.execute('services', {'target': 'example.com'}, tmp_path, threading.Event())
    assert calls[0][-1] == 'example.com'
    assert '-oN' not in calls[0]
    assert '--host-timeout' in calls[0]


def test_shodan_redaction_and_errors(engine, monkeypatch):
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield b'{"banner":"testkey1234567890"}'
    response = Response()
    monkeypatch.setattr('toolkit.requests.get', lambda *a, **kw: response)
    assert engine.shodan('/api-info', {}, threading.Event())['banner'] == '[REDACTED]'
    response.status_code = 403
    with pytest.raises(ValueError, match='plan or credits'):
        engine.shodan('/api-info', {}, threading.Event())


def test_routes_keys_and_origin(engine, tmp_path, monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    settings = EnvManager(str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(engine, settings))
    client = app.test_client()
    assert client.post('/api/toolkit/jobs', json={}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/toolkit/jobs', data='{}').status_code == 415
    assert client.post('/api/toolkit/jobs', json=[]).status_code == 400
    secret = 'privatekey123456789'
    result = client.post('/api/toolkit/shodan-key', json={'key': secret})
    assert result.status_code == 200 and secret not in result.get_data(as_text=True)
    assert settings.get_env_key(KEY) == secret
    assert client.get('/api/toolkit/catalog').status_code == 200
    assert client.get('/api/toolkit/jobs/not-a-job/files/report.json').status_code == 400
    assert client.delete('/api/toolkit/shodan-key', json={}).status_code == 200
    assert settings.get_env_key(KEY) is None
