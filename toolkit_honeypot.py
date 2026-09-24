"""Bounded, low-interaction decoys. No shell, credential collection or forwarding."""
import json
import selectors
import socket
import time
from collections import Counter
from datetime import datetime, timezone

PROFILES = {'http': 8088, 'ssh-banner': 2222, 'ftp-banner': 2121}


def listen(address, port, profile, duration, folder, cancel, on_connection=None):
    counts = Counter()
    total = 0
    deadline = time.monotonic() + duration
    clients = {}
    with selectors.DefaultSelector() as selector, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        # No SO_REUSEPORT: existing Ragnar/SSH listeners always keep their ports.
        try:
            server.bind((address, port))
            server.listen(32)
        except OSError as exc:
            raise ValueError('Cannot listen on %s:%s; address unavailable or port already in use.' % (address, port)) from exc
        server.setblocking(False)
        selector.register(server, selectors.EVENT_READ)
        with (folder / 'events.jsonl').open('w', encoding='utf-8') as output:
            def record(peer, event, **extra):
                nonlocal total
                total += 1
                record = dict(time=datetime.now(timezone.utc).isoformat(),
                                             source=peer[0], source_port=peer[1],
                                             service=profile, event=event, address=address, port=port, **extra)
                output.write(json.dumps(record) + '\n')
                output.flush()
                if event == 'connection' and counts[peer[0]] == 1 and on_connection:
                    on_connection(record)

            def close(client):
                selector.unregister(client)
                clients.pop(client, None)
                client.close()

            try:
                while time.monotonic() < deadline and not cancel.is_set() and total < 1000:
                    for key, _ in selector.select(.2):
                        if total >= 1000 or cancel.is_set():
                            break
                        if key.fileobj is server:
                            client, peer = server.accept()
                            client.setblocking(False)
                            counts[peer[0]] += 1
                            record(peer, 'connection')
                            if len(clients) >= 32:
                                client.close()
                                continue
                            clients[client] = (peer, time.monotonic())
                            selector.register(client, selectors.EVENT_READ)
                            if profile != 'http':
                                banner = b'SSH-2.0-OpenSSH_9.2\r\n' if profile == 'ssh-banner' else b'220 FTP ready\r\n'
                                try:
                                    client.send(banner)
                                except OSError:
                                    close(client)
                        else:
                            client = key.fileobj
                            peer, _ = clients[client]
                            try:
                                data = client.recv(4096)
                                # Keep metadata, never authorization headers or entered passwords.
                                record(peer, 'request', bytes_received=len(data))
                                if profile == 'http' and data:
                                    body = b'<html><body><h1>Service unavailable</h1></body></html>'
                                    client.send(b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Type: text/html\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                            except OSError:
                                pass
                            close(client)
                    for client, (_, started) in list(clients.items()):
                        if time.monotonic() - started > 2:
                            close(client)
            finally:
                for client in list(clients):
                    close(client)
    return dict(address=address, port=port, profile=profile, connections=sum(counts.values()),
                sources=dict(counts), events=total, event_limit_reached=total >= 1000)
