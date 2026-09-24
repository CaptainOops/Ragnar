"""Isolated smoke test; never imports Ragnar's hardware stack or reads its .env.

Use --live to query InternetDB for 1.1.1.1 and run installed read-only utilities
against example.com / loopback. All reports live in an automatically removed
temporary directory, not production loot. No service restart is required.
"""
import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toolkit import Toolkit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--shodan-config', help='Optional existing Ragnar directory: test configured key without printing or changing it')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ragnar-toolkit-smoke-') as directory:
        engine = Toolkit(lambda: directory, lambda: None)
        catalog = engine.catalog()
        print(json.dumps({'interfaces': catalog['interfaces'], 'available': [t['id'] for t in catalog['tools'] if t['available']]}))
        if args.shodan_config:
            from env_manager import EnvManager
            settings = EnvManager(args.shodan_config)
            try:
                key = settings.get_env_key('RAGNAR_SHODAN_API_KEY')
                if key:
                    account = engine.shodan('/api-info', {}, threading.Event(), key=key)
                    print(json.dumps({'shodan_key': 'verified', 'plan': account.get('plan')}))
                else:
                    print(json.dumps({'shodan_key': 'not configured; InternetDB requires no key'}))
            except PermissionError:
                print(json.dumps({'shodan_key': 'configuration not readable by this user'}))
        if not args.live:
            return 0
        failures = []
        for tool, params in [('internetdb', {'target': '1.1.1.1'}), ('dns', {'target': 'example.com'}),
                             ('http_headers', {'target': 'https://example.com'}),
                             ('tls_certificate', {'target': 'example.com'}), ('ping', {'target': '127.0.0.1'}),
                             ('interfaces', {})]:
            if not next(t['available'] for t in catalog['tools'] if t['id'] == tool):
                print(json.dumps({'tool': tool, 'status': 'not installed'}))
                continue
            job = engine.start(tool, params)
            deadline = time.monotonic() + 90
            while job['id'] in engine.running and time.monotonic() < deadline:
                time.sleep(.1)
            if job['id'] in engine.running:
                engine.cancel(job['id'])
                raise RuntimeError('Smoke test deadline exceeded')
            report = json.loads(engine.artifact(job['id'], 'report.json').read_text())
            summary = {'tool': tool, 'status': report['status'], 'artifacts': report['artifacts'], 'error': report['error']}
            if tool == 'internetdb' and report['status'] == 'completed':
                result = json.loads(engine.artifact(job['id'], 'result.json').read_text())
                assert result['ip'] == '1.1.1.1' and isinstance(result['ports'], list)
                summary['ports'] = result['ports']
            print(json.dumps(summary), flush=True)
            if report['status'] != 'completed':
                failures.append(tool)
        return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
