"""Per-network Python payload library. Payloads are trusted administrator code."""
import hashlib
import os
import re
import tempfile
from pathlib import Path

MAX_SOURCE = 65536


def check_source(source):
    if not isinstance(source, str) or not source.strip() or len(source.encode('utf-8')) > MAX_SOURCE:
        raise ValueError('Enter Python source up to 64 KiB.')
    try:
        compile(source, 'payload.py', 'exec', dont_inherit=True)
    except (SyntaxError, ValueError) as exc:
        raise ValueError('Python syntax error on line %s: %s' %
                         (getattr(exc, 'lineno', '?'), getattr(exc, 'msg', str(exc)))) from None
    return source


class PayloadWorkspace:
    def __init__(self, root):
        self.root = root

    def path(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name):
            raise ValueError('Use a payload name of 1–64 letters, numbers, hyphens or underscores.')
        root = self.root() / 'payloads'
        if root.is_symlink():
            raise ValueError('Payload directory must not be a symbolic link.')
        root.mkdir(exist_ok=True)
        path = root / (name + '.py')
        if path.is_symlink():
            raise ValueError('Payload files must not be symbolic links.')
        return path

    def read(self, name):
        path = self.path(name)
        if not path.is_file() or path.stat().st_size > MAX_SOURCE:
            raise ValueError('Payload not found or exceeds 64 KiB.')
        source = path.read_text(encoding='utf-8')
        return dict(name=name, source=source, revision=hashlib.sha256(source.encode('utf-8')).hexdigest())

    def list(self):
        root = self.path('example').parent
        return [self.read(p.stem) for p in sorted(root.glob('*.py'))[:100]
                if not p.is_symlink() and p.stat().st_size <= MAX_SOURCE]

    def save(self, name, source, revision=None):
        check_source(source)
        path = self.path(name)
        if not path.exists() and len(list(path.parent.glob('*.py'))) >= 100:
            raise ValueError('This network already has 100 payloads. Remove one before adding another.')
        if path.exists() and self.read(name)['revision'] != revision:
            raise ValueError('This payload changed or already exists. Reload it before saving.')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, delete=False) as out:
            out.write(source)
            temp = Path(out.name)
        try:
            os.chmod(temp, 0o600)
            os.replace(str(temp), str(path))
        finally:
            if temp.exists():
                temp.unlink()
        return self.read(name)

    def delete(self, name, revision):
        if self.read(name)['revision'] != revision:
            raise ValueError('This payload changed. Reload it before deleting.')
        self.path(name).unlink()
