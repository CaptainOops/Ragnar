"""Headless dashboard utilities inspired by RaspyJack; no LCD/GPIO dependency.

Jobs freeze their network loot directory at submission. Commands are fixed argv
templates, never shell strings. HTTP/API work and child processes are bounded.
"""
from __future__ import annotations

import copy
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.parse import urlsplit

import requests
from payload_workspace import PayloadWorkspace, check_source
from toolkit_honeypot import PROFILES, listen as run_honeypot


TOOLS = [
    dict(id='honeypot', name='Honeypot listener', field=None, binary=None, interface=True, port=8088,
         description='A timed HTTP decoy or SSH/FTP banner listener. Connection metadata is saved to this network’s loot.'),
    dict(id='payload', name='Saved Python payload', field='payload', binary=None,
         description='Run a saved Python payload with Ragnar’s service permissions. Edit and validate it in Payload IDE.'),
    dict(id='internetdb', name='Shodan InternetDB (free)', field='public_ip', binary=None,
         description='No API key: indexed ports, hostnames, CPEs, tags and reported CVEs for one public IPv4 address.'),
    dict(id='shodan_host', name='Shodan host lookup', field='public_ip', binary=None,
         description='Indexed services, banners, and last-observed dates for one public IP.'),
    dict(id='shodan_search', name='Shodan search', field='query', binary=None,
         description='One page of indexed results. Searches may consume Shodan query credits.'),
    dict(id='shodan_account', name='Shodan account', field=None, binary=None,
         description='Check API plan and remaining query/scan credits.'),
    dict(id='shodan_count', name='Shodan result count', field='query', binary=None,
         description='Count indexed matches without consuming Shodan query credits.'),
    dict(id='http_headers', name='HTTP headers', field='url', binary='curl',
         description='Inspect one HTTP(S) response’s headers without downloading its body.'),
    dict(id='tls_certificate', name='TLS certificate', field='host', binary='openssl', port=443,
         description='Inspect the certificate chain and TLS handshake on one host and port.'),
    dict(id='mdns', name='mDNS service discovery', field=None, binary='avahi-browse', interface=True,
         description='Resolve advertised local services on the selected interface.'),
    dict(id='smb_shares', name='SMB share listing', field='host', binary='smbclient',
         description='List shares offered to an anonymous session; no passwords or file retrieval.'),
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
         description='Top 100 TCP ports on one host, with light service detection. Quiet pacing is available.'),
    dict(id='port_watch', name='New-port check', field='host', binary='nmap',
         description='Compare one host’s top 100 TCP ports with the last check on this network.'),
    dict(id='ms17_check', name='MS17-010 check', field='host', binary='nmap',
         description='Run Nmap’s detection script against SMB port 445 on one host; no exploitation.'),
    dict(id='ldap_rootdse', name='LDAP root discovery', field='host', binary='ldapsearch', port=389,
         description='Read an LDAP server’s public RootDSE naming contexts without credentials.'),
    dict(id='smb_crawl', name='Anonymous SMB share crawl', field='host', binary='smbclient',
         description='List accessible share names and bounded file listings; no files downloaded.'),
    dict(id='tcp_jitter', name='TCP latency / jitter', field='host', binary=None, port=443,
         description='Eight TCP connection samples to one host and port, with latency and jitter.'),
    dict(id='mac_presence', name='MAC presence in neighbor table', field='mac', binary='ip', interface=True,
         description='Look for one MAC on the selected interface without probing the network.'),
    dict(id='usb_watch', name='USB insertion watch', field=None, binary=None,
         description='Watch for newly attached USB HID and storage devices; saves device IDs, not serials or keystrokes.'),
    dict(id='capture', name='Packet capture', field=None, binary='tcpdump', interface=True,
         description='Bounded PCAP capture: all traffic, DNS, DHCP, LLDP/CDP or mDNS/SSDP.'),
    dict(id='capture_summary', name='Capture summary', field='capture_job', binary='tcpdump',
         description='Read the first 200 packets from a Toolkit capture without network traffic.'),
    dict(id='packet_replay', name='Bounded packet replay', field='capture_job', binary='tcpreplay', interface=True,
         description='Replay up to 200 packets from a Toolkit capture on one selected interface at 10 packets/second.'),
    dict(id='responder', name='Responder (Ethernet)', field=None, binary=None, interface=True,
         description='Bounded Responder session on a connected wired interface. Analyze mode listens; active mode answers name queries.'),
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
# Keep established endpoints for compatibility and payload use; their dashboard
# controls already live in Ragnar, so do not expose a second launcher.
NATIVE_TOOLS = {'ping': 'network', 'trace': 'network', 'whois': 'network',
                'dns': 'network', 'interfaces': 'network', 'neighbors': 'network',
                'services': 'discovered', 'capture': 'traffic', 'capture_summary': 'traffic',
                'tls_certificate': 'network', 'ms17_check': 'adv-vuln'}
ARTIFACTS = ('result.json', 'output.txt', 'capture.pcap', 'events.jsonl', 'payload.py', 'context.json')


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
    def __init__(self, loot_root, get_key, max_jobs=2, event_dir=None):
        self.loot_root = loot_root
        self.get_key = get_key
        self.max_jobs = max_jobs
        self.lock = threading.RLock()
        self.running = {}
        self.payloads = PayloadWorkspace(self.root)
        self.event_handler = None
        if event_dir:
            try:
                Path(event_dir).mkdir(parents=True, exist_ok=True)
                self.event_handler = RotatingFileHandler(str(Path(event_dir) / 'toolkit_honeypot.jsonl'),
                                                        maxBytes=1024 * 1024, backupCount=2, encoding='utf-8')
                self.event_handler.setFormatter(logging.Formatter('%(message)s'))
            except OSError:
                logging.getLogger(__name__).warning('Honeypot Watchtower log unavailable; per-job events still saved.')

    def emit_honeypot_event(self, event, folder):
        if self.event_handler:
            record = dict(event, severity='low', code='HONEYPOT_CONNECTION',
                          src=event['source'], target=event['address'] + ':' + str(event['port']),
                          module='toolkit_honeypot', job_id=folder.name,
                          network_loot=str(folder.parent.parent),
                          summary='Connection to %s decoy on %s:%s' %
                                  (event['service'], event['address'], event['port']))
            self.event_handler.handle(logging.LogRecord(__name__, logging.INFO, __file__, 0,
                                                        json.dumps(record), (), None))

    def root(self):
        root = Path(self.loot_root()).resolve() / 'toolkit'
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def wired_carrier(interface):
        """Require a physical Ethernet link at the moment a replay starts."""
        path = Path('/sys/class/net') / interface
        try:
            if not (path / 'device').exists() or (path / 'wireless').exists():
                return False
            return (path / 'carrier').read_text(encoding='ascii').strip() == '1'
        except OSError:
            return False

    def catalog(self):
        keyed = bool(self.get_key())
        tools = []
        for source in TOOLS:
            tool = dict(source)
            tool['native_tab'] = NATIVE_TOOLS.get(tool['id'])
            reason = ''
            if tool['binary'] and not shutil.which(tool['binary']):
                reason = 'Install ' + tool['binary']
            if tool['id'].startswith('shodan_') and not keyed:
                reason = 'Configure a Shodan API key'
            if tool['id'] == 'responder':
                source = Path(os.environ.get('RAGNAR_RESPONDER_DIR', '/opt/ragnar-responder'))
                if not all((source / name).is_file() for name in ('Responder.py', 'Responder.conf', 'settings.py')):
                    reason = 'Install Responder in /opt/ragnar-responder'
            tool.update(available=not reason, reason=reason)
            tools.append(tool)
        try:
            interfaces = [name for _, name in socket.if_nameindex()]
        except (OSError, AttributeError):
            interfaces = []
        return dict(tools=tools, interfaces=interfaces, shodan_configured=keyed,
                    capture_profiles=list(FILTERS), max_jobs=self.max_jobs,
                    honeypot_profiles=PROFILES)

    @staticmethod
    def interface_address(interface):
        try:
            result = subprocess.run(['ip', '-j', '-4', 'address', 'show', 'dev', interface],
                                    capture_output=True, text=True, timeout=5, check=True)
            addresses = [a['local'] for item in json.loads(result.stdout)
                         for a in item.get('addr_info', []) if a.get('family') == 'inet']
            if addresses:
                return str(ipaddress.IPv4Address(addresses[0]))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            pass
        raise ValueError('Selected interface has no usable IPv4 address.')

    def validate(self, tool_id, params):
        if tool_id not in BY_ID:
            raise ValueError('Unknown tool.')
        tool = BY_ID[tool_id]
        result = {}
        field = tool.get('field')
        if field == 'payload':
            payload = self.payloads.read(params.get('target'))
            check_source(payload['source'])
            result.update(target=payload['name'], revision=payload['revision'])
            result['duration'] = self._integer(params.get('duration', 30), 5, 120)
        if field == 'host':
            result['target'] = host(params.get('target'))
        elif field == 'url':
            value = str(params.get('target', '')).strip()
            parsed = urlsplit(value)
            if (len(value) > 2048 or parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or any(ord(c) < 33 for c in value)):
                raise ValueError('Enter an HTTP(S) URL without embedded credentials or whitespace.')
            host(parsed.hostname)
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError('Invalid URL port.')
            result['target'] = value
        elif field == 'public_ip':
            try:
                address = ipaddress.ip_address(str(params.get('target', '')).strip())
            except ValueError:
                raise ValueError('Enter a public IP address.')
            if not address.is_global:
                raise ValueError('Shodan host lookup requires a public IP, not a LAN address.')
            if tool_id == 'internetdb' and address.version != 4:
                raise ValueError('InternetDB requires a public IPv4 address.')
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
        elif field == 'mac':
            value = str(params.get('target', '')).strip().lower()
            if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', value):
                raise ValueError('Enter one MAC address as six colon-separated hex bytes.')
            result['target'] = value
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
        if tool_id == 'usb_watch':
            result['duration'] = self._integer(params.get('duration', 20), 5, 120)
        if tool_id == 'honeypot':
            profile = params.get('profile', 'http')
            if not isinstance(profile, str) or profile not in PROFILES:
                raise ValueError('Choose HTTP, SSH banner or FTP banner.')
            result.update(profile=profile, duration=self._integer(params.get('duration', 60), 5, 3600))
            result['address'] = self.interface_address(result['interface'])
        if tool_id == 'responder':
            result['duration'] = self._integer(params.get('duration', 30), 5, 120)
            mode = params.get('mode', 'analyze')
            if mode not in ('analyze', 'active'):
                raise ValueError('Unknown Responder mode.')
            result['mode'] = mode
        if tool_id == 'services':
            pace = params.get('pace', 'normal')
            if pace not in ('normal', 'quiet'):
                raise ValueError('Unknown scan pace.')
            result['pace'] = pace
        if tool.get('port'):
            result['port'] = self._integer(params.get('port', tool['port']), 1, 65535)
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
            if tool_id == 'responder' and any(job[1]['tool'] == 'responder' for job in self.running.values()):
                raise ValueError('A Responder session is already running.')
            folder.mkdir()
            if tool_id == 'payload':
                payload = PayloadWorkspace(lambda: root).read(clean['target'])
                if payload['revision'] != clean['revision']:
                    folder.rmdir()
                    raise ValueError('Payload changed during submission. Run again.')
                (folder / 'payload.py').write_text(payload['source'], encoding='utf-8')
                (folder / 'context.json').write_text(json.dumps(dict(
                    job_id=job_id, network_loot=str(root.parent), job_dir=str(folder)), indent=2), encoding='utf-8')
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
            report['artifacts'] = [p.name for p in folder.iterdir() if p.name in ARTIFACTS]
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
        if not re.fullmatch(r'[0-9a-f]{32}', job_id) or name not in ('report.json',) + ARTIFACTS:
            raise ValueError('Invalid artifact.')
        with self.lock:
            active = self.running.get(job_id)
        root = active[2].parent if active else self.root()
        path = root / job_id / name
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink() or path.resolve().parent.parent != root.resolve():
            raise ValueError('Artifact not found in this network.')
        return path

    def command(self, argv, folder, cancel, timeout=45, capture=False, cwd=None, env=None):
        path = folder / 'output.txt'
        with path.open('ab') as output:
            process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, cwd=cwd, env=env,
                                       start_new_session=os.name == 'posix')
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
                if path.stat().st_size > MAX_OUTPUT:
                    raise ValueError('Output limit reached; narrow the target.')
            finally:
                if os.name == 'posix':
                    # Also clean descendants if the parent exited before cancellation.
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                elif process.poll() is None:
                    process.terminate()
                if process.poll() is None:
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if os.name == 'posix':
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if path.stat().st_size > MAX_OUTPUT:
                    output.truncate(MAX_OUTPUT)
        return dict(output='output.txt', duration_limited=limit)

    def shodan(self, endpoint, params, cancel, key=None):
        key = key or self.get_key()
        if not key:
            raise ValueError('Configure a Shodan API key.')
        if cancel.is_set():
            raise Stopped()
        return self._shodan_request(SHODAN_BASE + endpoint, dict(params, key=key), cancel, key)

    def _shodan_request(self, url, params, cancel, key=''):
        try:
            with requests.get(url, params=params,
                              timeout=(5, 20), stream=True, allow_redirects=False) as response:
                errors = {400: 'Shodan rejected the query. Check its syntax and your plan.',
                          401: 'Invalid Shodan API key.', 403: 'Shodan plan or credits do not permit this request.',
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
                text = data.decode('utf-8')
                if key:
                    text = text.replace(key, '[REDACTED]')
                result = json.loads(text)
                if not isinstance(result, dict) or result.get('error'):
                    raise ValueError('Shodan returned an invalid or unsuccessful response.')
                return result
        except requests.RequestException:
            raise ValueError('Could not reach Shodan. Check connectivity and retry.') from None

    def execute(self, tool, p, folder, cancel):
        target = p.get('target', '')
        if cancel.is_set():
            raise Stopped()
        if tool == 'payload':
            # Snapshot created at submission: editing a saved script cannot alter a running job.
            env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'HOME', 'SYSTEMROOT')}
            env.update(RAGNAR_JOB_DIR=str(folder), RAGNAR_LOOT_DIR=str(folder.parent.parent),
                       RAGNAR_CONTEXT=str(folder / 'context.json'), PYTHONUNBUFFERED='1')
            return self.command([sys.executable, '-u', str(folder / 'payload.py')], folder, cancel,
                                timeout=p['duration'], cwd=str(folder), env=env)
        if tool == 'honeypot':
            if self.interface_address(p['interface']) != p['address']:
                raise ValueError('Interface address changed. Start a new listener.')
            return run_honeypot(p['address'], p['port'], p['profile'], p['duration'], folder, cancel,
                               on_connection=lambda event: self.emit_honeypot_event(event, folder))
        if tool == 'internetdb':
            return self._shodan_request('https://internetdb.shodan.io/' + target, {}, cancel)
        if tool.startswith('shodan_'):
            endpoint, query = {
                'shodan_host': ('/shodan/host/' + target, {}),
                'shodan_search': ('/shodan/host/search', {'query': target, 'page': p.get('page', 1), 'minify': 'true'}),
                'shodan_account': ('/api-info', {}),
                'shodan_count': ('/shodan/host/count', {'query': target}),
            }[tool]
            return self.shodan(endpoint, query, cancel)
        if tool == 'http_headers':
            return self.command(['curl', '--disable', '--head', '--silent', '--show-error', '--globoff',
                                 '--connect-timeout', '5', '--max-time', '20', '--proto', '=http,https',
                                 '--', target], folder, cancel, timeout=25)
        if tool == 'tls_certificate':
            address = ('[' + target + ']') if ':' in target else target
            return self.command(['openssl', 's_client', '-connect', address + ':' + str(p['port']),
                                 '-servername', target, '-showcerts'], folder, cancel, timeout=25)
        if tool == 'mdns':
            return self.command(['avahi-browse', '--all', '--resolve', '--terminate', '--parsable',
                                 '--interface=' + p['interface']], folder, cancel, timeout=30)
        if tool == 'smb_shares':
            return self.command(['smbclient', '-L', target, '-N', '-U', '%', '-g', '-t', '10'], folder, cancel, timeout=25)
        if tool == 'ms17_check':
            return self.command(['nmap', '-sT', '-Pn', '-p', '445', '--script', 'smb-vuln-ms17-010',
                                 '--host-timeout', '60s', target], folder, cancel, timeout=75)
        if tool == 'ldap_rootdse':
            address = '[' + target + ']' if ':' in target else target
            scheme = 'ldaps' if p['port'] == 636 else 'ldap'
            return self.command(['ldapsearch', '-x', '-H', f'{scheme}://{address}:{p["port"]}',
                                 '-s', 'base', '-b', '', '-l', '10', '-z', '50',
                                 'namingContexts', 'defaultNamingContext', 'supportedLDAPVersion'],
                                folder, cancel, timeout=25)
        if tool == 'smb_crawl':
            self.command(['smbclient', '-L', target, '-N', '-U', '%', '-g', '-t', '10'], folder, cancel, timeout=25)
            listing = (folder / 'output.txt').read_text(encoding='utf-8', errors='replace')
            shares = []
            for line in listing.splitlines():
                parts = line.split('|')
                if len(parts) >= 2 and parts[0] == 'Disk' and re.fullmatch(r'[A-Za-z0-9_$-]{1,64}', parts[1]):
                    if parts[1].upper() not in ('ADMIN$', 'IPC$', 'PRINT$'):
                        shares.append(parts[1])
            shares = list(dict.fromkeys(shares))[:3]
            for share in shares:
                if cancel.is_set():
                    raise Stopped()
                self.command(['smbclient', f'//{target}/{share}', '-N', '-U', '%', '-c', 'recurse;ls',
                              '-t', '10'], folder, cancel, timeout=25)
            return dict(output='output.txt', shares=shares)
        if tool == 'port_watch':
            args = ['nmap'] + (['-6'] if ':' in target else []) + ['-sT', '-Pn', '--top-ports', '100',
                    '--host-timeout', '60s', '-oX', '-', target]
            self.command(args, folder, cancel, timeout=75)
            try:
                root = ET.fromstring((folder / 'output.txt').read_bytes())
                open_ports = sorted({int(node.attrib['portid']) for node in root.findall('.//port')
                                     if node.attrib.get('protocol') == 'tcp' and
                                     node.find('state') is not None and
                                     node.find('state').attrib.get('state') == 'open'})
            except (ET.ParseError, KeyError, ValueError) as exc:
                raise ValueError('Could not parse Nmap port results.') from exc
            baseline = folder.parent / 'port_watch_baselines.json'
            with self.lock:
                try:
                    previous = json.loads(baseline.read_text(encoding='utf-8')) if baseline.exists() else {}
                    if not isinstance(previous, dict):
                        previous = {}
                except (OSError, ValueError):
                    previous = {}
                prior = previous.get(target)
                prior_ports = set(prior) if isinstance(prior, list) else set()
                previous[target] = open_ports
                temp = baseline.with_suffix('.tmp')
                temp.write_text(json.dumps(previous, indent=2), encoding='utf-8')
                os.replace(temp, baseline)
            return dict(output='output.txt', baseline_created=prior is None, open_ports=open_ports,
                        new_ports=sorted(set(open_ports) - prior_ports) if prior is not None else [],
                        closed_ports=sorted(prior_ports - set(open_ports)) if prior is not None else [])
        if tool == 'tcp_jitter':
            samples, errors = [], []
            for _ in range(8):
                if cancel.is_set():
                    raise Stopped()
                started = time.monotonic()
                try:
                    with socket.create_connection((target, p['port']), timeout=1.5):
                        samples.append(round((time.monotonic() - started) * 1000, 2))
                except OSError as exc:
                    errors.append(type(exc).__name__)
                cancel.wait(.1)
            jitter = [abs(b - a) for a, b in zip(samples, samples[1:])]
            return dict(samples_ms=samples, median_ms=median(samples) if samples else None,
                        mean_jitter_ms=round(sum(jitter) / len(jitter), 2) if jitter else None,
                        failed_samples=len(errors), errors=errors)
        if tool == 'mac_presence':
            self.command(['ip', '-j', 'neigh', 'show', 'dev', p['interface']], folder, cancel)
            try:
                entries = json.loads((folder / 'output.txt').read_text(encoding='utf-8'))
                matches = [dict(ip=item.get('dst'), state=item.get('state')) for item in entries
                           if isinstance(item, dict) and str(item.get('lladdr', '')).lower() == target]
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError('Could not parse the neighbor table.') from exc
            return dict(output='output.txt', found=bool(matches), matches=matches)
        if tool == 'usb_watch':
            root = Path('/sys/bus/usb/devices')
            if not root.is_dir():
                raise ValueError('USB sysfs is not available on this host.')

            def devices():
                found = {}
                for path in root.iterdir():
                    if not re.fullmatch(r'[0-9]+-[0-9.]+', path.name) or not path.is_dir():
                        continue
                    def read(name):
                        try:
                            return (path / name).read_text(encoding='utf-8').strip()[:128]
                        except OSError:
                            return ''
                    vid, pid = read('idVendor'), read('idProduct')
                    if not re.fullmatch(r'[0-9a-fA-F]{4}', vid) or not re.fullmatch(r'[0-9a-fA-F]{4}', pid):
                        continue
                    classes = []
                    for interface in root.glob(path.name + ':*'):
                        try:
                            classes.append((interface / 'bInterfaceClass').read_text().strip().lower())
                        except OSError:
                            continue
                    found[path.name] = dict(usb_id=f'{vid.lower()}:{pid.lower()}',
                                            product=read('product'), manufacturer=read('manufacturer'),
                                            classes=sorted(set(classes)),
                                            hid='03' in classes, storage='08' in classes)
                return found

            initial = devices()
            seen, events = set(initial), []
            deadline = time.monotonic() + p['duration']
            while time.monotonic() < deadline:
                if cancel.wait(min(.5, max(0, deadline - time.monotonic()))):
                    raise Stopped()
                current = devices()
                for key in sorted(set(current) - seen):
                    events.append(dict(timestamp=now(), port=key, **current[key]))
                seen = set(current)
            return dict(duration=p['duration'], initial_count=len(initial), inserted=events,
                        hid_count=sum(event['hid'] for event in events),
                        storage_count=sum(event['storage'] for event in events))
        if tool == 'responder':
            if not self.wired_carrier(p['interface']):
                raise ValueError('Responder requires a connected wired interface.')
            source = Path(os.environ.get('RAGNAR_RESPONDER_DIR', '/opt/ragnar-responder'))
            if not all((source / name).is_file() for name in ('Responder.py', 'Responder.conf', 'settings.py')):
                raise ValueError('Install Responder in /opt/ragnar-responder.')
            with tempfile.TemporaryDirectory(prefix='ragnar-responder-') as temp:
                runtime = Path(temp) / 'Responder'
                shutil.copytree(source, runtime, ignore=shutil.ignore_patterns('.git', '.venv', 'logs', '__pycache__'))
                responder_python = Path(os.environ.get('RAGNAR_RESPONDER_PYTHON', '/opt/ragnar-responder-venv/bin/python'))
                args = [str(responder_python) if responder_python.is_file() else sys.executable,
                        str(runtime / 'Responder.py'), '-I', p['interface']]
                if p['mode'] == 'analyze':
                    args.append('-A')
                try:
                    command_result = self.command(args, folder, cancel, timeout=p['duration'],
                                                  capture=True, cwd=runtime)
                finally:
                    logs = runtime / 'logs'
                    if logs.is_dir():
                        destination = folder / 'responder_logs'
                        destination.mkdir(exist_ok=True)
                        for item in sorted(logs.iterdir())[:20]:
                            if item.is_file() and not item.is_symlink() and item.stat().st_size <= MAX_OUTPUT:
                                shutil.copy2(item, destination / item.name)
            return dict(output='output.txt', mode=p['mode'], interface=p['interface'],
                        duration_limited=command_result['duration_limited'],
                        logs=[item.name for item in (folder / 'responder_logs').iterdir()]
                        if (folder / 'responder_logs').is_dir() else [])
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
            import pwd
            capture_user = pwd.getpwuid(os.geteuid()).pw_name
            # Keep the invoking identity: tcpdump's distro default drop-user may
            # otherwise be unable to create files in Ragnar's per-network loot.
            argv = ['tcpdump', '-i', p['interface'], '-nn', '-U', '-s', '512', '-c', '10000',
                    '-Z', capture_user, '-w', str(folder / 'capture.pcap')] + FILTERS[p['profile']]
            return self.command(argv, folder, cancel, timeout=p['duration'], capture=True)
        if tool in ('capture_summary', 'packet_replay'):
            # Resolve inside the frozen network, even if active network changes.
            capture = folder.parent / target / 'capture.pcap'
            if capture.is_symlink() or capture.parent.is_symlink() or not capture.is_file():
                raise ValueError('Capture not found.')
            if tool == 'capture_summary':
                return self.command(['tcpdump', '-nn', '-r', str(capture), '-c', '200'], folder, cancel)
            if not self.wired_carrier(p['interface']):
                raise ValueError('Packet replay requires a connected wired interface.')
            return self.command(['tcpreplay', '--intf1', p['interface'], '--limit', '200',
                                 '--pps', '10', '--duration', '30', str(capture)],
                                folder, cancel, timeout=35)
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
        if tool == 'services' and p.get('pace') == 'quiet':
            argv[-1:-1] = ['-T2', '--scan-delay', '250ms', '--max-rate', '10', '--max-retries', '1']
        return self.command(argv, folder, cancel, timeout=180 if tool == 'services' and p.get('pace') == 'quiet'
                            else 75 if tool == 'services' else 45)
