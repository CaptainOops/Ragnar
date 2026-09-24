"""Toolkit routes. Ragnar's application-wide authentication protects this blueprint."""
import os
import re
import threading
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request, send_file
from payload_workspace import check_source

KEY = 'RAGNAR_SHODAN_API_KEY'


def create_blueprint(engine, settings):
    bp = Blueprint('toolkit', __name__, url_prefix='/api/toolkit')

    @bp.before_request
    def check_mutation():
        if request.method in ('POST', 'DELETE'):
            origin = request.headers.get('Origin')
            if origin and (urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme):
                return jsonify(error='Cross-origin changes are not allowed.'), 403
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Cross-site changes are not allowed.'), 403
            if not request.is_json:
                return jsonify(error='Send application/json.'), 415
            limit = 400000 if request.path.startswith('/api/toolkit/payloads') else 4096
            if request.content_length and request.content_length > limit:
                return jsonify(error='Request too large.'), 413

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object.')
        return value

    @bp.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @bp.get('/catalog')
    def catalog():
        return jsonify(engine.catalog())

    @bp.get('/payloads')
    def payloads():
        with engine.lock:
            return jsonify(payloads=engine.payloads.list())

    @bp.post('/payloads/check')
    def payload_check():
        check_source(body().get('source'))
        return jsonify(valid=True)

    @bp.post('/payloads')
    def payload_save():
        data = body()
        with engine.lock:
            return jsonify(engine.payloads.save(data.get('name'), data.get('source'), data.get('revision')))

    @bp.delete('/payloads/<name>')
    def payload_delete(name):
        with engine.lock:
            engine.payloads.delete(name, body().get('revision'))
        return jsonify(deleted=True)

    @bp.post('/shodan-key')
    def save_key():
        key = body().get('key', '')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
            raise ValueError('Enter a valid Shodan API key.')
        # Verify with the no-query-credit account endpoint before replacing a working key.
        account = engine.shodan('/api-info', {}, threading.Event(), key=key)
        settings.set_env_key(KEY, key)
        os.chmod(settings.env_file_path, 0o600)
        return jsonify(configured=True, plan=account.get('plan'), query_credits=account.get('query_credits'))

    @bp.delete('/shodan-key')
    def remove_key():
        settings.delete_env_key(KEY)
        return jsonify(configured=False)

    @bp.get('/jobs')
    def jobs():
        return jsonify(jobs=engine.jobs())

    @bp.post('/jobs')
    def start():
        data = body()
        params = data.get('params', {})
        if not isinstance(params, dict) or not isinstance(data.get('tool'), str):
            raise ValueError('Choose a tool and its parameters.')
        return jsonify(engine.start(data['tool'], params)), 202

    @bp.post('/jobs/<job_id>/cancel')
    def cancel(job_id):
        return jsonify(cancelled=engine.cancel(job_id))

    @bp.get('/jobs/<job_id>/files/<name>')
    def artifact(job_id, name):
        path = engine.artifact(job_id, name)
        response = send_file(str(path), as_attachment=True, download_name=name)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    return bp
