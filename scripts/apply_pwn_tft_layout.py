#!/usr/bin/env python3
"""Reapply the opted-in small TFT layout after Pwnagotchi updates."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

MARKER = Path('/etc/ragnar/pwn-tft-layout.enabled')
STYLE = Path('/opt/pwnagotchi/pwnagotchi/ui/web/static/css/style.css')
SOURCE = Path(__file__).with_name('pwn_tft.css')
BLOCK = re.compile(r'/\* RAGNAR-TFT-BEGIN.*?/\* RAGNAR-TFT-END \*/\s*', re.S)


def apply_layout(style=STYLE, source=SOURCE, marker=MARKER):
    if not marker.exists() or not style.is_file():
        return False
    current = style.read_text(encoding='utf-8')
    updated = BLOCK.sub('', current).rstrip() + '\n\n' + source.read_text(encoding='utf-8').strip() + '\n'
    if updated == current:
        return False
    backup = style.with_name(style.name + '.before-ragnar-tft')
    if not backup.exists():
        shutil.copy2(style, backup)
    temporary = style.with_name(style.name + '.ragnar-tft-tmp')
    try:
        shutil.copy2(style, temporary)
        temporary.write_text(updated, encoding='utf-8')
        temporary.replace(style)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable', action='store_true', help='Enable persistence on this Pi and install its service hook')
    args = parser.parse_args()
    if args.enable:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.touch()
        hook = Path('/etc/systemd/system/pwnagotchi.service.d/ragnar-tft-layout.conf')
        hook.parent.mkdir(parents=True, exist_ok=True)
        script = str(Path(__file__).resolve()).replace('%', '%%').replace('"', '\\"')
        hook.write_text('[Service]\n# Restore the opted-in layout before every launch; never block service startup.\n'
                        f'ExecStartPre=-/usr/bin/python3 "{script}"\n', encoding='utf-8')
        subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=15)
    print('TFT layout updated' if apply_layout() else 'TFT layout unchanged or not enabled')


if __name__ == '__main__':
    main()
