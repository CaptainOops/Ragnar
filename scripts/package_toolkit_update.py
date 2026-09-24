"""Build a hash-checked feature bundle against an explicit installed Git revision."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

FILES = ['toolkit.py', 'toolkit_api.py', 'payload_workspace.py', 'toolkit_honeypot.py',
         'camera_recon.py', 'webapp_modern.py', 'network_diagnostics.py',
         'web/index_modern.html', 'web/scripts/ragnar_modern.js', 'web/scripts/toolkit.js',
         'docs/TOOLKIT.md', 'docs/RASPYJACK_PORT_AUDIT.md', 'docs/nettools.md']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous-bundle', type=Path,
                        help='Use a previously deployed bundle as the baseline for an incremental update.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = {}
    previous = {}
    if args.previous_bundle:
        with zipfile.ZipFile(args.previous_bundle) as old:
            previous = json.loads(old.read('manifest.json'))
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            before = subprocess.run(['git', 'show', args.base + ':' + name], cwd=root, capture_output=True)
            data = (root / name).read_bytes().replace(b'\r\n', b'\n')
            manifest[name] = dict(before=hashlib.sha256(before.stdout).hexdigest() if before.returncode == 0 else None,
                                  after=hashlib.sha256(data).hexdigest())
            if name in previous:
                manifest[name]['before'] = previous[name]['after']
            bundle.writestr('files/' + name, data)
        bundle.writestr('manifest.json', json.dumps(manifest, indent=2))
        bundle.write(root / 'scripts/deploy_toolkit_bundle.py', 'deploy_toolkit_bundle.py')
    print('Bundle:', args.output, '| files:', len(manifest))


if __name__ == '__main__':
    main()
