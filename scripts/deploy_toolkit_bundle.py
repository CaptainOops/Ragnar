"""Check or deploy an extracted bundle without overwriting unrelated Pi edits.

Default is read-only checking. --apply backs up, installs and restarts Ragnar,
then restores the previous files automatically if the service fails its check.
"""
import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('/home/ragnar/Ragnar'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve()
    stage = Path(__file__).resolve().parent
    manifest = json.loads((stage / 'manifest.json').read_text())
    updates = []
    for name, checks in manifest.items():
        path = repo / name
        staged = stage / 'files' / name
        if not path.resolve().is_relative_to(repo) or path.is_symlink():
            raise SystemExit('Unsafe destination: ' + name)
        if digest(staged) != checks['after']:
            raise SystemExit('Bundle hash mismatch: ' + name)
        current = digest(path)
        if current == checks['after']:
            continue
        if current != checks['before']:
            raise SystemExit('Local changes conflict; no files changed: ' + name)
        if name.endswith('.py'):
            ast.parse(staged.read_text(), filename=name)
        updates.append(name)
    print(json.dumps({'preflight': 'passed', 'files_to_update': len(updates)}), flush=True)
    if not args.apply or not updates:
        return
    backup = repo.parent / 'ragnar-backups' / ('integrated-toolkit-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True, exist_ok=False)
    os.chmod(backup, 0o700)
    existed = {}
    for name in updates:
        path = repo / name
        existed[name] = path.exists()
        if path.exists():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (backup / 'manifest.json').write_text(json.dumps(existed, indent=2))
    print(json.dumps({'backup': str(backup)}), flush=True)
    needs_restart = any(name.endswith('.py') for name in updates)
    try:
        for name in updates:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.toolkit-update')
            shutil.copyfile(stage / 'files' / name, tmp)
            if path.exists():
                shutil.copymode(path, tmp)
            else:
                os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        if needs_restart:
            subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'ragnar.service'], check=True, timeout=60)
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3) as response:
                    html = response.read().decode('utf-8')
                if 'toolkit-tab' in html and 'livecams-tab' in html:
                    print(json.dumps({'deployment': 'healthy', 'backup': str(backup)}), flush=True)
                    return
            except OSError:
                pass
            time.sleep(1)
        raise RuntimeError('Dashboard health check failed.')
    except Exception:
        for name, was_present in existed.items():
            path = repo / name
            if was_present:
                shutil.copy2(backup / name, path)
            elif path.exists():
                path.unlink()
        if needs_restart:
            subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'ragnar.service'], timeout=60)
        print('Update rolled back. Backup: ' + str(backup), flush=True)
        raise


if __name__ == '__main__':
    main()
