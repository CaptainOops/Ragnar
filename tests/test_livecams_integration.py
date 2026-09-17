"""Exercise real camera route functions without starting Ragnar's hardware stack."""
import ast
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify, request


@pytest.fixture
def camera_app(tmp_path):
    app = Flask(__name__)
    shared = SimpleNamespace(config={'livecams': []}, save_config=lambda: None)
    namespace = dict(app=app, shared_data=shared, jsonify=jsonify, request=request,
                     os=os, time=time, datetime=datetime, logger=logging.getLogger('test'),
                     _camera_recon_loot_dir=lambda: str(tmp_path))
    names = {'_livecams_list', '_livecam_embed_url', '_resolve_youtube_channel',
             'livecams_get', 'livecams_add', 'livecams_reorder', 'livecams_save_snapshot'}
    source = Path(__file__).resolve().parents[1] / 'webapp_modern.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace['_LIVECAM_TYPES'] = {'snapshot', 'mjpeg', 'embed'}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    return app.test_client(), shared, namespace


def test_reorder_preserves_cameras_without_duplicates(camera_app):
    client, shared, _ = camera_app
    shared.config['livecams'] = [{'id': x, 'url': 'https://example.com/' + x} for x in 'abc']
    response = client.post('/api/livecams/reorder', json={'order': ['c', 'c', 'unknown', 'a']})
    assert [c['id'] for c in response.json['cams']] == ['c', 'a', 'b']
    assert client.post('/api/livecams/reorder', json={'order': [{}]}).status_code == 400


def test_channel_and_video_resolution(camera_app):
    client, shared, namespace = camera_app
    namespace['_resolve_youtube_channel'] = lambda url: ('UC' + 'a' * 22, 'abcdefghijk')
    for url in ('https://www.youtube.com/@surfcheck', 'https://youtu.be/abcdefghijk'):
        response = client.post('/api/livecams', json={'url': url, 'type': 'embed', 'category': "Fisherman's Wharf"})
        assert response.json['cam']['url'].startswith('https://www.youtube.com/embed/abcdefghijk?')
    assert len(shared.config['livecams']) == 2


def test_snapshot_format_unique_and_frozen_network(camera_app, tmp_path, monkeypatch):
    client, shared, namespace = camera_app
    shared.config['livecams'] = [{'id': 'one', 'type': 'snapshot', 'url': 'https://example.com/snap', 'label': '../Surf'}]
    class Response:
        headers = {'Content-Type': 'image/png'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size):
            namespace['_camera_recon_loot_dir'] = lambda: str(tmp_path / 'other-network')
            yield b'png-bytes'
    monkeypatch.setattr('requests.get', lambda *a, **kw: Response())
    first = client.post('/api/livecams/save-snapshot', json={'id': 'one'})
    assert first.status_code == 200
    path = Path(first.json['path'])
    assert path.parent == tmp_path / 'snapshots' and path.suffix == '.png'
    namespace['_camera_recon_loot_dir'] = lambda: str(tmp_path)
    second = client.post('/api/livecams/save-snapshot', json={'id': 'one'})
    assert second.json['path'] != first.json['path']
    assert path.read_bytes() == b'png-bytes'


def test_snapshot_rejects_non_images(camera_app, monkeypatch):
    client, shared, _ = camera_app
    shared.config['livecams'] = [{'id': 'one', 'type': 'snapshot', 'url': 'https://example.com'}]
    class Response:
        headers = {'Content-Type': 'text/html'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
    monkeypatch.setattr('requests.get', lambda *a, **kw: Response())
    assert client.post('/api/livecams/save-snapshot', json={'id': 'one'}).status_code == 415
