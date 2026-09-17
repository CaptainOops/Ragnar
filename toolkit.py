"""Headless dashboard utilities inspired by RaspyJack; no LCD/GPIO dependency.

Jobs freeze their network loot directory at submission. Commands are fixed argv
templates, never shell strings. HTTP/API work and child processes are bounded.
"""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests


TOOLS = [
    dict(id='shodan_host', name='Shodan host lookup', field='public_ip', binary=None,
         description='Indexed services, banners, and last-observed dates for one public IP.'),
    dict(id='shodan_search', name='Shodan search', field='query', binary=None,
         description='One page of indexed results. Searches may consume Shodan query credits.'),
    dict(id='shodan_account', name='Shodan account', field=None, binary=None,
         description='Check API plan and remaining query/scan credits.'),
    dict(id='dns', name='DNS records', field='host', binary='dig',
         description='A, AAAA, MX, NS, TXT and CAA records for a hostname.'),
    dict(id='whois', name='WHOIS', field='host', binary='whois',
         description='Registration and allocation information for a domain or IP.'),
    dict(id='ping', name='Reachability', field='host', binary='ping',
         description='Five ICMP probes with timing and loss statistics.'),
    dict(id='trace', name='Route trace', field='host', binary='traceroute',
         description='Bounded numeric route trace, up to 16 hops.'),
    dict(id='neighbors', name='ARP / IPv6 neighbors', field=None, binary='ip',
         description='Read the selected interface’s neighbor table.', interface=True),
    dict(id='interfaces', name='Interface inventory', field=None, binary='ip',
         description='Addresses, link state and routes for the host.'),
    dict(id='services', name='Service inventory', field='host', binary='nmap',
         description='Top 100 TCP ports on one host, with light service detection.'),
    dict(id='capture', name='Packet capture', field=None, binary='tcpdump', interface=True,
         description='Bounded PCAP capture: all traffic, DNS, DHCP, LLDP/CDP or mDNS/SSDP.'),
    dict(id='capture_summary', name='Capture summary', field='capture_job', binary='tcpdump',
         description='Read the first 200 packets from a Toolkit capture without network traffic.'),
]
BY_ID = {tool['id']: tool for tool in TOOLS}
FILTERS = {
    'all': [], 'dns': ['port', '53'],
    'dhcp': ['udp', 'and', '(', 'port', '67', 'or', 'port', '68', 'or', 'port', '546', 'or', 'port', '547', ')'],
    'lldp': ['ether', 'proto', '0x88cc', 'or', 'ether', 'dst', '01:00:0c:cc:cc:cc'],
    'discovery': ['udp', 'and', '(', 'port', '5353', 'or', 'port', '1900', ')'],
}
SHODAN_BASE = 'https://api.shodan.io'
MAX_OUTPUT = 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def host(value):
    value = str(value or '').strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if len(value) > 253 or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value):
        raise ValueError('Enter one hostname or IP address (no URL, subnet or command options).')
    if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in value.split('.')):
        raise ValueError('Invalid hostname.')
    return value


class Stopped(Exception):
    pass


class Toolkit:
    def __init__(self, loot_root, get_key, max_jobs=2):
        self.loot_root = loot_root
        self.get_key = get_key
        self.max_jobs = max_jobs
        self.lock = threading.RLock()
        self.running = {}

    def root(self):
        root = Path(self.loot_root()).resolve() / 'toolkit'
        root.mkdir(parents=True, exist_ok=True)
        return root

    def catalog(self):
        keyed = bool(self.get_key())
        tools = []
        for source in TOOLS:
            tool = dict(source)
            reason = ''
            if tool['binary'] and not shutil.which(tool['binary']):
                reason = 'Install ' + tool['binary']
            if tool['id'].startswith('shodan_') and not keyed:
                reason = 'Configure a Shodan API key'
            tool.update(available=not reason, reason=reason)
            tools.append(tool)
        try:
            interfaces = [name for _, name in socket.if_nameindex()]
        except (OSError, AttributeError):
            interfaces = []
        return dict(tools=tools, interfaces=interfaces, shodan_configured=keyed,
                    capture_profiles=list(FILTERS), max_jobs=self.max_jobs)

    def validate(self, tool_id, params):
        if tool_id not in BY_ID:
            raise ValueError('Unknown tool.')
        tool = BY_ID[tool_id]
        result = {}
        field = tool.get('field')
        if field == 'host':
            result['target'] = host(params.get('target'))
        elif field == 'public_ip':
            try:
                address = ipaddress.ip_address(str(params.get('target', '')).strip())
            except ValueError:
                raise ValueError('Enter a public IP address.')
            if not address.is_global:
                raise ValueError('Shodan host lookup requires a public IP, not a LAN address.')
            result['target'] = str(address)
        elif field == 'query':
            query = str(params.get('target', '')).strip()
            if not query or len(query) > 500 or any(ord(c) < 32 for c in query):
                raise ValueError('Enter a search query of 1–500 characters.')
            result['target'] = query
            result['page'] = self._integer(params.get('page', 1), 1, 20)
        elif field == 'capture_job':
            job_id = str(params.get('target', ''))
            self.artifact(job_id, 'capture.pcap')
            result['target'] = job_id
        if tool.get('interface'):
            interface = str(params.get('interface', ''))
            if interface not in self.catalog()['interfaces'] or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}', interface):
                raise ValueError('Select an existing network interface.')
            result['interface'] = interface
        if tool_id == 'capture':
            profile = params.get('profile', 'all')
            if not isinstance(profile, str) or profile not in FILTERS:
                raise ValueError('Unknown capture profile.')
            result.update(profile=profile, duration=self._integer(params.get('duration', 20), 5, 120))
        available = next(t for t in self.catalog()['tools'] if t['id'] == tool_id)
        if not available['available']:
            raise ValueError(available['reason'])
        return result

    @staticmethod
    def _integer(value, low, high):
        try:
            number = int(value)
        except (ValueError, TypeError):
            raise ValueError('Invalid number.')
        if str(number) != str(value) or not low <= number <= high:
            raise ValueError('Value must be between %s and %s.' % (low, high))
        return number

    @staticmethod
    def _write(folder, report):
        tmp = folder / 'report.tmp'
        tmp.write_text(json.dumps(report, indent=2), encoding='utf-8')
        os.replace(str(tmp), str(folder / 'report.json'))

    def start(self, tool_id, params):
        clean = self.validate(tool_id, params)
        root = self.root()  # freeze network context before creating a worker
        job_id = uuid.uuid4().hex
        folder = root / job_id
        report = dict(id=job_id, tool=tool_id, name=BY_ID[tool_id]['name'], params=clean,
                      created=now(), status='running', artifacts=[], error=None)
        cancel = threading.Event()
        with self.lock:
            if len(self.running) >= self.max_jobs:
                raise ValueError('Two Toolkit jobs are already running; stop or wait for one.')
            folder.mkdir()
            self._write(folder, report)
            self.running[job_id] = (cancel, report, folder)
        submitted = copy.deepcopy(report)
        threading.Thread(target=self._run, args=(report, folder, cancel), daemon=True).start()
        return submitted

    def _run(self, report, folder, cancel):
        try:
            result = self.execute(report['tool'], report['params'], folder, cancel)
            if cancel.is_set():
                raise Stopped()
            (folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            report['status'] = 'completed'
        except Stopped:
            report['status'] = 'cancelled'
        except Exception as exc:
            report['status'] = 'failed'
            # Do not persist exception URLs: Shodan credentials are query parameters.
            report['error'] = str(exc) if isinstance(exc, ValueError) else 'Tool failed; check dependencies and connectivity.'
        finally:
            report['finished'] = now()
            report['artifacts'] = [p.name for p in folder.iterdir() if p.name in ('result.json', 'output.txt', 'capture.pcap')]
            try:
                self._write(folder, report)
            finally:
                with self.lock:
                    self.running.pop(report['id'], None)

    def cancel(self, job_id):
        with self.lock:
            job = self.running.get(job_id)
            if job:
                job[0].set()
                return True
        return False

    def jobs(self):
        reports = []
        with self.lock:
            active = set(self.running)
        for file in self.root().glob('*/report.json'):
            if file.is_symlink() or file.parent.is_symlink():
                continue
            try:
                report = json.loads(file.read_text(encoding='utf-8'))
                if report['status'] == 'running' and report['id'] not in active:
                    report['status'] = 'interrupted'
                reports.append(report)
            except (OSError, ValueError, KeyError):
                continue
        return sorted(reports, key=lambda r: r.get('created', ''), reverse=True)[:100]

    def artifact(self, job_id, name):
        if not re.fullmatch(r'[0-9a-f]{32}', job_id) or name not in ('report.json', 'result.json', 'output.txt', 'capture.pcap'):
            raise ValueError('Invalid artifact.')
        with self.lock:
            active = self.running.get(job_id)
        root = active[2].parent if active else self.root()
        path = root / job_id / name
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink() or path.resolve().parent.parent != root.resolve():
            raise ValueError('Artifact not found in this network.')
        return path

    def command(self, argv, folder, cancel, timeout=45, capture=False):
        path = folder / 'output.txt'
        with path.open('ab') as output:
            process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            started = time.monotonic()
            limit = False
            try:
                while process.poll() is None:
                    if cancel.wait(.1):
                        raise Stopped()
                    if time.monotonic() - started >= timeout:
                        if capture:
                            limit = True
                            break
                        raise ValueError('Tool timed out.')
                    if path.stat().st_size > MAX_OUTPUT:
                        raise ValueError('Output limit reached; narrow the target.')
                if not limit and process.returncode:
                    raise ValueError('Tool exited with an error; see output.txt.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        return dict(output='output.txt', duration_limited=limit)

    def shodan(self, endpoint, params, cancel):
        key = self.get_key()
        if not key:
            raise ValueError('Configure a Shodan API key.')
        if cancel.is_set():
            raise Stopped()
        try:
            with requests.get(SHODAN_BASE + endpoint, params=dict(params, key=key),
                              timeout=(5, 20), stream=True, allow_redirects=False) as response:
                errors = {401: 'Invalid Shodan API key.', 403: 'Shodan plan or credits do not permit this request.',
                          404: 'Shodan has no indexed results for this host.', 429: 'Shodan rate limit reached; retry later.'}
                if response.status_code in errors:
                    raise ValueError(errors[response.status_code])
                if response.status_code != 200:
                    raise ValueError('Shodan is temporarily unavailable.')
                data = bytearray()
                deadline = time.monotonic() + 30
                for chunk in response.iter_content(65536):
                    if cancel.is_set():
                        raise Stopped()
                    data.extend(chunk)
                    if len(data) > 5 * MAX_OUTPUT or time.monotonic() > deadline:
                        raise ValueError('Shodan response limit reached.')
                # Provider data is untrusted; never echo the configured key into loot.
                text = data.decode('utf-8').replace(key, '[REDACTED]')
                return json.loads(text)
        except requests.RequestException:
            raise ValueError('Could not reach Shodan. Check connectivity and retry.') from None

    def execute(self, tool, p, folder, cancel):
        target = p.get('target', '')
        if tool.startswith('shodan_'):
            endpoint, query = {
                'shodan_host': ('/shodan/host/' + target, {}),
                'shodan_search': ('/shodan/host/search', {'query': target, 'page': p.get('page', 1), 'minify': 'true'}),
                'shodan_account': ('/api-info', {}),
            }[tool]
            return self.shodan(endpoint, query, cancel)
        if tool == 'dns':
            for kind in ('A', 'AAAA', 'MX', 'NS', 'TXT', 'CAA'):
                if cancel.is_set():
                    raise Stopped()
                self.command(['dig', '+time=3', '+tries=1', target, kind], folder, cancel, timeout=8)
            return dict(output='output.txt')
        if tool == 'interfaces':
            for args in (['ip', '-j', 'address', 'show'], ['ip', '-j', 'route', 'show']):
                self.command(args, folder, cancel)
            return dict(output='output.txt')
        if tool == 'capture':
            # At most 10,000 x 512-byte packet snapshots (~5 MB) and 120 seconds.
            argv = ['tcpdump', '-i', p['interface'], '-nn', '-U', '-s', '512', '-c', '10000',
                    '-w', str(folder / 'capture.pcap')] + FILTERS[p['profile']]
            return self.command(argv, folder, cancel, timeout=p['duration'], capture=True)
        if tool == 'capture_summary':
            # Resolve inside the frozen network, even if active network changes.
            capture = folder.parent / target / 'capture.pcap'
            if capture.is_symlink() or capture.parent.is_symlink() or not capture.is_file():
                raise ValueError('Capture not found.')
            return self.command(['tcpdump', '-nn', '-r', str(capture), '-c', '200'], folder, cancel)
        commands = {
            'whois': ['whois', target], 'ping': ['ping', '-n', '-c', '5', '-W', '2', target],
            'trace': ['traceroute', '-n', '-m', '16', '-w', '1', '-q', '1', target],
            'neighbors': ['ip', '-j', 'neigh', 'show', 'dev', p.get('interface', '')],
            'services': ['nmap', '-sT', '-sV', '--version-light', '--top-ports', '100',
                         '--host-timeout', '60s', target],
        }
        argv = commands[tool]
        if tool == 'services' and ':' in target:
            argv.insert(1, '-6')
        return self.command(argv, folder, cancel, timeout=75 if tool == 'services' else 45)
