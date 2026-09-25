"""Pi audit: loopback fixtures, passive inventory, and public metadata only.

Never replays packets or enables Responder. Server/hardware/key-dependent tools
are explicitly reported as unverified when no suitable fixture is available.
"""
import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toolkit import Toolkit, TOOLS


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('X-Ragnar-Audit', 'loopback')
        self.end_headers()

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
results = {}
with tempfile.TemporaryDirectory(prefix='ragnar-toolkit-audit-') as temp:
    kit = Toolkit(lambda: temp, lambda: '')
    catalog = {t['id']: t for t in kit.catalog()['tools']}
    kit.payloads.save('audit', 'print("ragnar-audit-ok")')
    checks = {
        'payload': {'target': 'audit', 'duration': 5},
        'http_headers': {'target': 'http://127.0.0.1:%s/' % server.server_port},
        'mdns': {'interface': 'wlan0'},
        'internetdb': {'target': '1.1.1.1'},
        'dns': {'target': 'example.com'},
        'whois': {'target': 'example.com'},
        'ping': {'target': '127.0.0.1'},
        'trace': {'target': '127.0.0.1'},
        'interfaces': {},
        'neighbors': {'interface': 'wlan0'},
        'services': {'target': '127.0.0.1'},
        'port_watch': {'target': '127.0.0.1'},
        'ms17_check': {'target': '127.0.0.1'},
        'tcp_jitter': {'target': '127.0.0.1', 'port': server.server_port},
        'mac_presence': {'target': '02:00:00:00:00:01', 'interface': 'lo'},
        'usb_watch': {'duration': 5},
        'capture': {'interface': 'lo', 'duration': 5, 'profile': 'dns'},
    }
    for tool, params in checks.items():
        try:
            job = kit.start(tool, params)
            deadline = time.monotonic() + 100
            while kit.running and time.monotonic() < deadline:
                time.sleep(.1)
            report = next(r for r in kit.jobs() if r['id'] == job['id'])
            result = {'status': report['status'], 'artifacts': report['artifacts']}
            if report['error']:
                result['error'] = report['error']
            if tool == 'http_headers':
                assert 'X-Ragnar-Audit: loopback' in kit.artifact(job['id'], 'output.txt').read_text()
            if tool == 'payload':
                assert 'ragnar-audit-ok' in kit.artifact(job['id'], 'output.txt').read_text()
            if tool == 'capture' and report['status'] == 'completed':
                checks_summary = kit.start('capture_summary', {'target': job['id']})
                while kit.running:
                    time.sleep(.1)
                results['capture_summary'] = {'status': kit.jobs()[0]['status']}
            results[tool] = result
        except Exception as exc:
            results[tool] = {'status': 'failed', 'error': str(exc)}
        print(json.dumps({tool: results[tool]}), flush=True)
    for item in TOOLS:
        tool = item['id']
        if tool not in results:
            reason = catalog[tool]['reason'] or {
                'honeypot': 'Covered separately by native loopback listener smoke test.',
                'tls_certificate': 'Needs a TLS server fixture; not exercised in this audit.',
                'smb_shares': 'Needs a known anonymous SMB server fixture.',
                'smb_crawl': 'Needs a known anonymous SMB server fixture.',
                'ldap_rootdse': 'Needs a known LDAP server fixture.',
                'packet_replay': 'Requires connected Ethernet and an isolated replay destination.',
                'responder': 'Requires connected Ethernet; active mode not exercised.',
            }.get(tool, 'Not exercised')
            results[tool] = {'status': 'unverified', 'reason': reason}
    print('AUDIT_RESULTS=' + json.dumps(results, sort_keys=True), flush=True)
server.shutdown()
