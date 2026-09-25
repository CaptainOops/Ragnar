"""Hardware-free target smoke check; only a temporary library and loopback sockets."""
import argparse
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--module-dir', type=Path, default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
sys.path.insert(0, str(args.module_dir))
from toolkit import Toolkit
from toolkit_honeypot import listen

with tempfile.TemporaryDirectory(prefix='ragnar-toolkit-check-') as temp:
    root = Path(temp)
    kit = Toolkit(lambda: root, lambda: '')
    kit.payloads.save('hello', 'import os\nprint("payload-ok", os.environ["RAGNAR_JOB_DIR"])')
    job = kit.start('payload', {'target': 'hello', 'duration': 5})
    deadline = time.monotonic() + 8
    while kit.running and time.monotonic() < deadline:
        time.sleep(.05)
    assert not kit.running
    assert kit.jobs()[0]['status'] == 'completed', kit.jobs()[0]
    assert 'payload-ok' in kit.artifact(job['id'], 'output.txt').read_text()

    probe = socket.socket()
    probe.bind(('127.0.0.1', 0))
    probe.listen()
    port = probe.getsockname()[1]
    try:
        listen('127.0.0.1', port, 'http', 5, root, threading.Event())
        raise AssertionError('Busy port unexpectedly accepted')
    except ValueError:
        pass
    probe.close()
    stop = threading.Event()
    results = []
    worker = threading.Thread(target=lambda: results.append(listen('127.0.0.1', port, 'http', 5, root, stop)))
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                client = socket.create_connection(('127.0.0.1', port), timeout=.5)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        with client:
            client.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            assert b'503 Service Unavailable' in client.recv(4096)
    finally:
        stop.set()
        worker.join(3)
    assert not worker.is_alive()
    assert results[0]['connections'] == 1
    assert kit.interface_address('lo') == '127.0.0.1'
    for profile, prefix in [('ssh-banner', b'SSH-2.0-'), ('ftp-banner', b'220 ')]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            banner_port = probe.getsockname()[1]
        stop = threading.Event()
        worker = threading.Thread(target=listen, args=('127.0.0.1', banner_port, profile, 5, root, stop))
        worker.start()
        try:
            deadline = time.monotonic() + 2
            while True:
                try:
                    client = socket.create_connection(('127.0.0.1', banner_port), timeout=.5)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.05)
            with client:
                assert client.recv(4096).startswith(prefix), profile
        finally:
            stop.set()
            worker.join(3)
        assert not worker.is_alive()
print(json.dumps({'payload_execution': 'passed', 'honeypot_loopback': 'passed',
                  'ssh_ftp_banners': 'passed', 'port_conflict': 'passed', 'listener_shutdown': 'passed'}))
