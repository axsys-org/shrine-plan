#!/usr/bin/env python3
"""Bounded physical reads over a disposable registered HTTP foot.

Stages compiler-only state and publishes the production Grove debugger.
An optional --template must be compiler-only, never live state. The
harness owns its ephemeral port/process, persists untouched JSON responses for
the production parser bridge, and performs no writes outside its temp worker.
The large scenario is read-only and intentionally includes malformed index
fixtures. Epoch transitions use a separate clean Eden runtime, never that index.
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
from html.parser import HTMLParser
from debug_runtime_helpers import startup_failed
from debug_transport_fixture import compiler_template, startup_source, require_declaration, RETURNED

ROOT = pathlib.Path(__file__).resolve().parent.parent


def key(*segments):
    def segment(value):
        if isinstance(value, str):
            tag, payload = 'ts', value.encode()
        else:
            tag, payload = value
            if isinstance(payload, int):
                payload = payload.to_bytes((payload.bit_length() + 7) // 8, 'little')
            elif isinstance(payload, str):
                payload = payload.encode()
        return '/' + tag + ':' + payload.hex()
    return 'v1' + ''.join(map(segment, segments))


def local_key(*segments):
    return key(('x', 17), *segments)


class Workspace(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.attrs = {}
        require_declaration(html)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'debug-workspace':
            self.attrs = attrs


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=pathlib.Path)
    parser.add_argument('--wisp', default=os.environ.get('WISP') or shutil.which('wisp'))
    parser.add_argument('--scenario', choices=('large', 'epoch'), default='large')
    args = parser.parse_args()
    if not args.wisp or not os.access(args.wisp, os.X_OK):
        parser.error('A working --wisp executable is required.')
    args.template = compiler_template(args.template, args.wisp)
    work = pathlib.Path(tempfile.mkdtemp(prefix=f'shrine-physical-http-{args.scenario}-'))
    (work / 'snap').mkdir()
    for name in ('data.mdb', 'pins.pack'):
        shutil.copyfile(args.template / name, work / 'snap' / name)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    assert port != 8138
    origin = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(NoRedirect())
    results = []
    log_path = work / 'out.log'
    print(f'Disposable physical runtime port: {port}; artifacts: {work}', flush=True)

    with log_path.open('w') as log:
        process = subprocess.Popen(
            [args.wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
            cwd=work, stdin=subprocess.PIPE, stdout=log, stderr=log,
            text=True, restore_signals=False)
        try:
            process.stdin.write(startup_source(port, 'physical-' + args.scenario))
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
                time.sleep(.25)

            def request(path, expected=200, save=None, method='GET', data=None):
                assert path.startswith('/') and not path.startswith('//')
                started = time.monotonic()
                req = urllib.request.Request(origin + path, method=method,
                    data=None if data is None else urllib.parse.urlencode(data).encode(),
                    headers={} if data is None else {'Content-Type': 'application/x-www-form-urlencoded'})
                try:
                    response = opener.open(req, timeout=20)
                except urllib.error.HTTPError as error:
                    response = error
                except Exception as error:
                    results.append(dict(path=path, method=method, status=None,
                        ms=round((time.monotonic()-started)*1000, 3), bytes=0,
                        file=None, failure=type(error).__name__))
                    raise
                with response:
                    status, body = response.status, response.read()
                    ctype = response.headers.get_content_type()
                    declared = int(response.headers['Content-Length'])
                assert status == expected, (path[:300], status, body[:1000])
                assert declared == len(body), (path, declared, len(body))
                if path.startswith('/debug-read/physical'):
                    assert ctype == 'application/json', (path, ctype)
                    assert len(body) <= 131072
                result = dict(path=path, method=method, status=status,
                    ms=round((time.monotonic() - started) * 1000, 3), bytes=len(body), file=save)
                results.append(result)
                if save:
                    (work / save).write_bytes(body)
                return json.loads(body) if ctype == 'application/json' else body.decode()

            def url(path_key=local_key('demo'), collection='children', **options):
                return '/debug-read/physical?' + urllib.parse.urlencode(dict(pathKey=path_key, collection=collection, **options), safe='/:')

            def page(path_key=local_key('demo'), collection='children', save=None, **options):
                out = request(url(path_key, collection, **options), save=save)
                assert out['version'] == 1 and out['resolution'] == 'physical'
                assert out['pathKey'] == path_key and out['collection'] == collection
                assert out['limit'] == int(options.get('limit', 40))
                assert out['after'] == options.get('after')
                if 'epoch' in options:
                    assert out['epoch'] == str(options['epoch'])
                assert out['epoch'].isdecimal() and out['total'].isdecimal()
                assert len(out['entries']) <= out['limit']
                assert out['complete'] is (out['next'] is None)
                if out['next'] is not None:
                    assert out['entries'] and out['next'] == out['entries'][-1]['key']
                return out

            if args.scenario == 'epoch':
                before_log = Workspace(request('/debug/0x11/log', save='epoch-journal-before.html')).attrs
                before = page(collection='slots', save='epoch-before.json')
                epoch = before['epoch']
                assert before['total'] == '11' and before['own']['fields'] == '11'
                first = page(collection='slots', epoch=epoch, limit=2, save='epoch-first.json')
                assert first['next'] is not None
                next_page = page(collection='slots', epoch=epoch, after=first['next'],
                    limit=2, save='epoch-next.json')
                assert first['entries'] + next_page['entries'] == before['entries'][:4]
                assert before_log == Workspace(request('/debug/0x11/log',
                    save='epoch-journal-after-reads.html')).attrs
                assert 'committed' in request('/edit/0x11/demo', method='POST', data={'text': 'changed'})
                fresh = page(collection='slots', save='epoch-after.json')
                assert int(fresh['epoch']) > int(epoch)
                assert fresh['own']['recordEpoch'] == fresh['epoch']
                fields = {entry['key']: entry['value'] for entry in fresh['entries']}
                assert fields[key('text')]['hex'] == b'changed'.hex()
                assert request(url(collection='slots', epoch=epoch, after=first['next'], limit=2),
                    409, save='epoch-stale.json') == dict(version=1, error='epoch_conflict')
                (work/'results.json').write_text(json.dumps(dict(port=port,
                    scenario='epoch', passed=True, requests=results), indent=2))
                print(f'PASS clean epoch transition: {len(results)} HTTP requests; artifacts: {work}', flush=True)
                return

            baseline = Workspace(request('/debug/0x11/log', save='journal-before.html')).attrs
            assert baseline['data-page-epoch'] == '3' and baseline['data-child-count'] == '1'
            demo = page(collection='slots', save='demo-slots.json')
            epoch = demo['epoch']
            maximum = local_key() + '/f:' * 2727 + '/rd:'
            assert len(maximum) == 8192
            assert request(url(maximum, 'slots', epoch=epoch, after=maximum), 404,
                save='maximum-identities.json') == dict(version=1, error='path_missing')
            maximum_ms = results[-1]['ms']
            fully_escaped = '/debug-read/physical?' + urllib.parse.urlencode(dict(pathKey=maximum,
                collection='slots', epoch=epoch, after=maximum))
            assert request(fully_escaped, 400) == dict(version=1, error='invalid_query')
            print(f'PASS paired maximum identities: {maximum_ms}ms; over-budget escaped form rejects', flush=True)
            own = demo['own']
            assert own['recordEpoch'] == '1' and own['state'] == 'live' and own['fields'] == '11'
            assert own['labelSource'] == 'lede' and bytes.fromhex(own['label']['hex']) == b'Authored fixture'
            assert own['helpSource'] == 'lore-body' and own['helpLine'] == 1
            assert bytes.fromhex(own['help']['hex']) == b'Authored help'
            fields = {entry['key']: entry['value'] for entry in demo['entries']}
            assert fields['v1']['hex'] == b'empty key'.hex()
            assert fields[key('nul')]['hex'] == '410042'
            assert fields[key('long')]['complete'] is False and len(fields[key('long')]['hex']) == 512
            assert fields[key('zero')]['total'] == '0' and fields[key('zero')]['hex'] == ''
            assert fields[key('huge')]['total'] == '513' and fields[key('huge')]['complete'] is False
            assert fields[key('reference')]['pathKey'] == key('elsewhere')
            assert fields[key('opaque')] == dict(type='opaque', reason='unsupported_type')
            assert fields[key('a', 'b')]['hex'] == b'one opaque slot key'.hex()
            assert page(collection='slots', limit=1, save='demo-first.json')['own'] == own
            continued = page(collection='slots', epoch=epoch, after='v1', limit=1, save='demo-after-empty.json')
            assert continued['own'] == own and continued['entries'][0]['key'] != 'v1'
            assert page(local_key('empty'), 'slots', save='empty.json')['complete']
            spine = page(local_key('spine'), save='spine.json')
            assert spine['own']['state'] == 'unknown' and spine['total'] == '1'
            assert spine['entries'][0]['node']['state'] == 'live'
            assert page(local_key('dead'), save='dead-children.json')['own']['state'] == 'tombstone'
            page(local_key(), 'slots', save='root-slots.json')
            ordered = page(local_key('order'), save='order.json')
            assert ordered['total'] == '35'
            walk = page(local_key('order'), epoch=epoch, limit=1, save='order-first.json')
            seen_order = []
            for _ in range(40):
                seen_order.extend(entry['key'] for entry in walk['entries'])
                assert len(set(seen_order)) == len(seen_order), 'Opaque aura cursor re-admitted an earlier key'
                if walk['complete']:
                    break
                walk = page(local_key('order'), epoch=epoch, after=walk['next'], limit=1)
            assert walk['complete'] and seen_order == [entry['key'] for entry in ordered['entries']]
            print('PASS metadata, exact scalar previews, opaque keys and native aura ordering', flush=True)

            for name, collection in [('big', 'children'), ('slots', 'slots')]:
                out = page(local_key(name), collection, save=f'{name}-first.json')
                assert out['total'] == '10000'
                seen = []
                index = 0
                while True:
                    seen.extend(entry['key'] for entry in out['entries'])
                    if out['complete']:
                        break
                    index += 1
                    out = page(local_key(name), collection, epoch=epoch, after=out['next'],
                        save=f'{name}-second.json' if index == 1 else None)
                assert seen == [key(('u', n)) for n in range(10000)]
                page(local_key(name), collection, epoch=epoch, after=key(('u', 9999)), save=f'{name}-terminal.json')
                absent = page(local_key(name), collection, epoch=epoch, after=key(('u', 20000)), save=f'{name}-absent.json')
                assert absent['complete'] and not absent['entries']
                print(f'PASS all 10000 {collection} exactly once across {index+1} HTTP pages', flush=True)

            wide = page(local_key('wide'), 'slots', save='wide-first.json')
            assert 0 < len(wide['entries']) < 20 and not wide['complete']
            second = page(local_key('wide'), 'slots', epoch=epoch, after=wide['next'], save='wide-second.json')
            assert second['complete'] and len(wide['entries']) + len(second['entries']) == 20
            assert not ({entry['key'] for entry in wide['entries']} & {entry['key'] for entry in second['entries']})
            assert request(url(maximum, 'slots', epoch=epoch, after=maximum), 404,
                save='maximum-identities-after-walks.json') == dict(version=1, error='path_missing')
            print(f'PASS paired maximum identities after large walks: {results[-1]["ms"]}ms', flush=True)

            for target, status, error in [
                (url(local_key('missing')), 404, 'path_missing'),
                (url(local_key('spine'), 'slots'), 404, 'record_missing'),
                (url(local_key('dead'), 'slots'), 410, 'record_deleted'),
                (url(key('x', 'demo')), 422, 'derived_path'),
                (url(key('o', 'demo')), 422, 'derived_path'),
                (url(key('h', 'demo')), 422, 'derived_path'),
                (url(epoch='2'), 409, 'epoch_conflict'),
                (url(epoch='4'), 409, 'epoch_conflict'),
                (url(epoch='9'*128), 409, 'epoch_conflict'),
                (url(local_key('oversized')), 422, 'key_too_large'),
                (url(local_key('zzzbroken')), 500, 'read_failed')]:
                assert request(target, status, save=f'error-{error}.json') == dict(version=1, error=error)
                assert page(collection='slots') == demo, 'Error must not strand pending read or mutate state'
            base = url()
            invalid = [base+'&pathKey=v1', base+'&%70athKey=v1', base+'&collection=slots',
                base+'&epoch=3&epoch=3', base+'&limit=1&limit=1', base+'&unknown=1', base+'&',
                base+'&&limit=1', base+'?limit=1', base+'&epoch=', base+'&epoch=01', base+'&epoch=-1',
                base+'&epoch=+1', base+'&epoch=1.0', base+'&epoch=%203', base+'&epoch='+'1'*129,
                base+'&limit=0', base+'&limit=41', base+'&limit=01', base+'&after=v1/u:',
                base+'&epoch=3&after=v1', base+'&epoch=3&after=v1/u:/u:',
                base+'&epoch=3&after=v1/u:&after=v1/u:',
                '/debug-read/physical', '/debug-read/physical?',
                '/debug-read/physical?pathKey=v1&collection=other']
            for malformed in ['v1/u:%00', 'v1/u:%09', 'v1/u:%0a', 'v1/u:%7f', 'v1/u:%zz',
                              'v1/u:00', 'v1/u:AA', 'v1/u:1', 'v2', 'v1/', 'v1/z:', 'v1/u:%2500']:
                invalid.append('/debug-read/physical?pathKey='+malformed+'&collection=children')
            invalid += [url('v1'+('/u:'*2731)), base+'&unknown='+'a'*32768]
            for target in invalid:
                assert request(target, 400) == dict(version=1, error='invalid_query')
            assert request(base, 405, method='POST') == dict(version=1, error='method_not_allowed')
            assert request('/debug-read/physical/extra', 404) == dict(version=1, error='route_missing')

            for control in [b'\x00', b'\t', b'\x1f', b'\x7f']:
                raw = b'GET /debug-read/physical?collection=children&pathKey=v1/u:'+control+b' HTTP/1.1\r\nHost: localhost\r\n\r\n'
                with socket.create_connection(('127.0.0.1', port), timeout=20) as conn:
                    conn.sendall(raw)
                    response = b''
                    while True:
                        part = conn.recv(65536)
                        if not part:
                            break
                        response += part
                assert response.startswith(b'HTTP/1.0 400 '), (control, response[:200])
                results.append(dict(path='raw-control-'+control.hex(), method='GET', status=400, bytes=len(response), file=None))
            prefix = ('GET '+base+' HTTP/1.1\r\nHost: localhost\r\nX-Padding: ').encode()
            fragment = prefix + b'a'*(16383-len(prefix)) + b'\x00'
            assert len(fragment) == 16384
            with socket.create_connection(('127.0.0.1', port), timeout=20) as conn:
                conn.sendall(fragment)
                response = b''
                while True:
                    part = conn.recv(65536)
                    if not part:
                        break
                    response += part
            assert response.startswith(b'HTTP/1.0 400 '), response[:200]
            results.append(dict(path='raw-chunk-terminal-nul-16384', method='GET', status=400, bytes=len(response), file=None))
            print('PASS strict queries, raw control bytes, stable errors and recovery', flush=True)

            def concurrent(n):
                return page(local_key('big'), epoch=epoch, after=key(('u', n*100)), limit=3)
            with ThreadPoolExecutor(max_workers=4) as clients:
                replies = list(clients.map(concurrent, range(8)))
            for n, out in enumerate(replies):
                assert [entry['key'] for entry in out['entries']] == [key(('u', i)) for i in range(n*100+1, n*100+4)]
            after = Workspace(request('/debug/0x11/log', save='journal-after.html')).attrs
            assert baseline == after, 'Physical success/error/concurrent reads must not mint or journal'
            report = dict(port=port, scenario='large', passed=True, requests=results)
            (work/'results.json').write_text(json.dumps(report, indent=2))
            print(f'PASS: {len(results)} HTTP requests; artifacts: {work}', flush=True)
        except Exception as error:
            (work/'results.json').write_text(json.dumps(dict(port=port, scenario=args.scenario, passed=False,
                requests=results, failure=type(error).__name__, message=str(error)), indent=2))
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            print(f'Owned runtime exited: {process.returncode}', flush=True)


if __name__ == '__main__':
    main()
