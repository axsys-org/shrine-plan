#!/usr/bin/env python3
"""Exact typed slot reads through a disposable Eden HTTP foot.

Stages compiler-only state and publishes the production Grove debugger.
An optional --template must be a compiler bootstrap, never live namespace state.
The harness owns an ephemeral port, seeds only its disposable namespace,
tests real documents/chunks and isolated edits/deletion, and stops its process.
The printed artifact directory contains document.html and chunk JSON for
production DOM/parser integration; no existing live runtime is used.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from debug_runtime_helpers import startup_failed
from debug_transport_fixture import compiler_template, startup_source, SlotDocument as Document, RETURNED

ROOT = pathlib.Path(__file__).resolve().parent.parent

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=pathlib.Path)
    parser.add_argument('--wisp', default=os.environ.get('WISP') or shutil.which('wisp'))
    args = parser.parse_args()
    if not args.wisp or not os.access(args.wisp, os.X_OK):
        parser.error('A working --wisp executable is required.')
    args.template = compiler_template(args.template, args.wisp)
    work = pathlib.Path(tempfile.mkdtemp(prefix='shrine-value-http-'))
    (work / 'snap').mkdir()
    for name in ('data.mdb', 'pins.pack'):
        shutil.copyfile(args.template / name, work / 'snap' / name)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    assert port != 8138
    origin = f'http://127.0.0.1:{port}'
    log_path = work / 'out.log'
    results = []
    opener = urllib.request.build_opener(NoRedirect())
    print(f'Disposable value runtime port: {port}; artifacts: {work}', flush=True)
    with log_path.open('w') as log:
        process = subprocess.Popen([args.wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
            cwd=work, stdin=subprocess.PIPE, stdout=log, stderr=log, text=True, restore_signals=False)
        try:
            process.stdin.write(startup_source(port, 'value'))
            process.stdin.flush()
            deadline = time.monotonic() + 900
            while True:
                output = log_path.read_text(errors='replace')
                if process.poll() is not None or startup_failed(output, RETURNED):
                    raise RuntimeError(output[-6000:])
                if re.search(r'^"?HTTP foot listening"?$', output, re.MULTILINE):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError(f'Startup deadline exceeded: {output[-6000:]}')
                time.sleep(0.25)

            def request(path, expected=200, save=None, method='GET', data=None):
                assert path.startswith('/') and not path.startswith('//')
                start = time.monotonic()
                req = urllib.request.Request(origin + path, method=method,
                    data=None if data is None else urllib.parse.urlencode(data).encode(),
                    headers={} if data is None else {'Content-Type': 'application/x-www-form-urlencoded'})
                try:
                    response = opener.open(req, timeout=20)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    status, body, ctype = response.status, response.read(), response.headers.get_content_type()
                assert status == expected, (path, status, body[:1000])
                result = dict(path=path, status=status, ms=round((time.monotonic() - start) * 1000, 3), bytes=len(body))
                results.append(result)
                print(json.dumps(result), flush=True)
                if save:
                    (work / save).write_bytes(body)
                if ctype == 'application/json':
                    return json.loads(body)
                return body.decode()

            doc = Document(request('/debug/demo', save='document.html'))
            fields = doc.fields
            assert fields['/text']['data-value-state'] == 'complete'
            assert fields['/threshold']['data-value-state'] == 'complete'
            assert fields['/long']['data-value-state'] == 'preview'
            assert fields['/long']['data-value-preview-bytes'] == '2047'
            assert fields['/long']['data-value-bytes'] == '2054'
            assert fields['/body']['data-value-preview-bytes'] == '1024'
            assert fields['/huge']['data-preview-reason'] == 'numeric-summary'
            assert fields['/opaque']['data-value-state'] == 'opaque'
            assert not fields['/opaque']['data-value-url']
            assert fields['/nul']['data-preview-reason'] == 'non-text-bytes'
            assert fields['/invalid']['data-preview-reason'] == 'non-text-bytes'
            epoch = fields['/text']['data-value-epoch']
            assert epoch.isdecimal()
            root = Document(request('/debug', save='root.html'))
            assert root.fields and all(f['data-value-epoch'].isdecimal() for f in root.fields.values())

            def url(slot='/text', at=epoch, offset=0, limit=4096, path='/demo'):
                return '/debug-read/value?' + urllib.parse.urlencode(dict(path=path, slot=slot, epoch=at, offset=offset, limit=limit))
            def chunk(slot='/text', at=epoch, offset=0, limit=4096, expected_hex=None, save=None):
                out = request(url(slot, at, offset, limit), save=save)
                assert out['version'] == 1 and out['encoding'] == 'hex'
                assert out['path'] == '/demo' and out['slot'] == slot and out['epoch'] == str(at)
                assert 0 < int(out['recordEpoch']) <= int(at)
                assert out['offset'] == str(offset) and out['total'].isdecimal()
                assert re.fullmatch(r'(?:[0-9a-f]{2})*', out['hex'])
                size = len(out['hex']) // 2
                assert size <= limit and offset + size <= int(out['total'])
                assert out['complete'] == (out['next'] is None)
                assert out['next'] == (str(offset + size) if offset + size < int(out['total']) else None)
                if expected_hex is not None:
                    assert out['hex'] == expected_hex, out
                return out

            before = Document(request('/debug/log')).workspace
            original = chunk(expected_hex='68656c6c6f', save='text.json')
            chunk(offset=2, limit=2, expected_hex='6c6c', save='middle.json')
            chunk(offset=5, limit=1, expected_hex='', save='eof.json')
            chunk('/long', offset=2048, limit=1, expected_hex='82', save='utf8-split.json')
            chunk('/nul', expected_hex='410042', save='nul.json')
            chunk('/nul', offset=1, limit=1, expected_hex='00')
            chunk('/invalid', expected_hex='ff', save='invalid-utf8.json')
            zero = chunk('/zero', expected_hex='', save='zero.json')
            assert zero['total'] == '0' and zero['representation'] == 'natural-le-bytes'
            chunk('/huge', offset=255, limit=2, expected_hex='0001', save='natural.json')
            chunk('/a/b', expected_hex=b'opaque slot key'.hex(), save='opaque-key.json')
            for size in [4096, 8192, 16384, 32768]:
                chunk('/large', limit=size, expected_hex=(b'a' * size).hex())
            first = chunk('/large', limit=65536, save='large-first.json')
            last = chunk('/large', offset=65536, limit=65536, save='large-last.json')
            assert bytes.fromhex(first['hex'] + last['hex']) == b'a' * 70000 + b'END'
            assert first['recordEpoch'] == last['recordEpoch']
            quoted_path = '/$quote"slash\\'
            quoted = request(url(path=quoted_path, slot=quoted_path))
            assert quoted['path'] == quoted_path and quoted['slot'] == quoted_path
            assert quoted['hex'] == b'quoted identifier'.hex()
            for path, status, error in [
                (url(at='123456789012345678901234567890'), 409, 'future_epoch'),
                (url(at='0'), 404, 'record_missing'),
                (url(path='/missing'), 404, 'record_missing'),
                (url(slot='/missing'), 404, 'slot_missing'),
                (url(slot='/opaque'), 422, 'unsupported_type'),
                (url(path='/x/demo'), 422, 'derived_path'),
                (url(path='/h/x/1/1/demo'), 422, 'derived_path'),
                (url(path='/o/demo'), 422, 'derived_path'),
                (url(offset=6), 416, 'offset_out_of_range')]:
                assert request(path, status) == {'version': 1, 'error': error}
            base = url()
            invalid = [base + '&epoch=2', base + '&%65poch=2', base + '&unknown=1', base + '&',
                base.replace('epoch=' + epoch, 'epoch=01'), base.replace('offset=0', 'offset=-1'),
                base.replace('limit=4096', 'limit=65537'), base.replace('limit=4096', 'limit=0'),
                base.replace('path=%2Fdemo', 'path=demo'), base.replace('path=%2Fdemo', 'path=%2Fdemo%2F'),
                base.replace('path=%2Fdemo', 'path=%2F.%2Fdemo'), base.replace('path=%2Fdemo', 'path=%00'),
                base.replace('path=%2Fdemo', 'path=%2F%09'), base.replace('path=%2Fdemo', 'path=%2F%0A'),
                base.replace('slot=%2Ftext', 'slot=%2F%7F'),
                base.replace('path=%2Fdemo', 'path=%zz'), '/debug-read/value']
            for target in invalid:
                assert request(target, 400) == {'version': 1, 'error': 'invalid_query'}
            assert request(base, 405, method='POST') == {'version': 1, 'error': 'method_not_allowed'}
            with ThreadPoolExecutor(max_workers=4) as clients:
                values = list(clients.map(lambda _: chunk(expected_hex='68656c6c6f'), range(8)))
            assert all(v == original for v in values)
            after = Document(request('/debug/log')).workspace
            assert before == after, 'Success, errors and concurrent value reads must not mint or journal.'

            assert 'committed' in request('/edit/demo', 200, method='POST', data={'text': 'changed'})
            changed = Document(request('/debug/demo', save='changed.html'))
            new_epoch = changed.fields['/text']['data-value-epoch']
            new = chunk(at=new_epoch, expected_hex=b'changed'.hex(), save='changed.json')
            assert int(new['recordEpoch']) > int(original['recordEpoch'])
            assert chunk(expected_hex='68656c6c6f', save='old-after-change.json') == original
            assert 'committed' in request('/vine/demo', 200, method='POST', data={'verb': 'cull'})
            latest = Document(request('/debug/log')).workspace['data-page-epoch']
            assert request(url(at=latest), 410) == {'version': 1, 'error': 'record_deleted'}
            assert chunk(expected_hex='68656c6c6f', save='old-after-delete.json') == original
            (work / 'results.json').write_text(json.dumps(dict(port=port, passed=True, requests=results), indent=2))
            print(f'PASS: {len(results)} real HTTP requests; artifact directory: {work}', flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

if __name__ == '__main__':
    main()
