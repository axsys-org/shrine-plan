#!/usr/bin/env python3
"""Exercise bounded journal HTTP reads in disposable compiler state.

Stages compiler-only state by default; --template accepts an explicit compiler
bootstrap, never a live namespace snapshot. The harness copies it, compiles and
publishes the production Grove debugger, chooses an ephemeral port, and stops its own
runtime. Artifacts remain in the printed temporary directory for inspection.
Use --eden for a second smoke test with a real booted namespace and legacy
permalink requests. Without it, the physical-index fixture has 10,000 keys.
Run `node x/debug-journal-contract-test.mjs <printed-artifact-directory>`
after the default fixture to validate the production document parser too.
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
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from debug_runtime_helpers import startup_failed
from debug_transport_fixture import compiler_template, startup_source, require_declaration, RETURNED

ROOT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--template', type=pathlib.Path,
                    help='Compiler bootstrap snapshot containing data.mdb and pins.pack')
parser.add_argument('--wisp', default=os.environ.get('WISP') or shutil.which('wisp'),
                    help='Wisp executable (or set WISP)')
parser.add_argument('--eden', action='store_true',
                    help='Use real disposable Eden state to check legacy permalink coexistence')
args = parser.parse_args()
if not args.wisp or not os.access(args.wisp, os.X_OK):
    parser.error('A working --wisp executable is required.')
args.template = compiler_template(args.template, args.wisp)
WORK = pathlib.Path(tempfile.mkdtemp(prefix='shrine-journal-http-'))
SNAP = args.template
RUNTIME = args.wisp

class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.workspace = {}
        self.children = []
        self.events = []
        self.links = []
        require_declaration(html)
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if data.get('id') == 'debug-workspace':
            self.workspace = data
        if tag == 'ui-tree-item' and 'data-path' in data:
            self.children.append(data['data-path'])
        if tag == 'a' and data.get('class') == 'debug-event':
            self.events.append(data)
        if tag == 'a':
            self.links.append(data)

with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
assert port != 8138
(WORK / 'snap').mkdir(exist_ok=True)
for name in ('data.mdb', 'pins.pack'):
    shutil.copyfile(SNAP / name, WORK / 'snap' / name)
log_path = WORK / 'out.log'
results = []
print(f'Disposable journal runtime port: {port}; log: {log_path}', flush=True)
with log_path.open('w') as log:
    process = subprocess.Popen([RUNTIME, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
        cwd=WORK, stdin=subprocess.PIPE, stdout=log, stderr=log, text=True, restore_signals=False)
    try:
        process.stdin.write(startup_source(port, 'journal-eden' if args.eden else 'journal'))
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
        origin = f'http://127.0.0.1:{port}'
        def get(path='/debug/log', expected=200, save=None, method='GET'):
            start = time.monotonic()
            request = urllib.request.Request(origin + path, method=method)
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    status, body = response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                status, body = error.code, error.read().decode()
            elapsed = round((time.monotonic() - start) * 1000, 3)
            assert status == expected, (path, status, body[:1000])
            result = {'path': path, 'status': status, 'ms': elapsed, 'bytes': len(body.encode())}
            results.append(result)
            print(json.dumps(result), flush=True)
            if save:
                (WORK / (save + '.html')).write_text(body)
            return Document(body) if status == 200 else None
        def check(document, before, limit, expected_keys, next_before, total='10000', epoch='10000'):
            data = document.workspace
            assert data['data-paging'] == 'journal', data
            assert data['data-page-before'] == before, data
            assert data['data-page-limit'] == str(limit), data
            assert data['data-page-next-before'] == next_before, data
            assert data['data-child-count'] == total, data
            assert data['data-page-epoch'] == epoch, data
            paths = ['/log/' + str(key) for key in expected_keys]
            assert document.children == paths, (document.children, paths)
            assert [event['data-reference'] for event in document.events] == paths
            assert [event['href'] for event in document.events] == ['/debug' + path for path in paths]
        if args.eden:
            initial = get(save='eden-initial')
            assert initial.workspace['data-paging'] == 'journal'
            # Boot uses journal-free seeding; the first collection can be empty.
            repeated = get()
            assert initial.workspace == repeated.workspace
            assert initial.children == repeated.children
            assert get('/debug/hello').workspace['data-path'] == '/hello'
            populated = get(save='eden-populated')
            assert populated.events, 'An ordinary HTTP namespace read must be journaled.'
            permalink = populated.events[0]['href']
            detail = get(permalink, save='eden-permalink')
            assert detail.workspace['data-path'] == permalink.removeprefix('/debug')
            assert not detail.workspace.get('data-paging')
            assert get('/debug/hello').workspace['data-path'] == '/hello'
            paths = ['/debug/hello', '/debug/log?limit=2'] * 4
            with ThreadPoolExecutor(max_workers=4) as clients:
                mixed = list(clients.map(get, paths))
            for path, document in zip(paths, mixed):
                assert document.workspace['data-path'] == ('/hello' if path.endswith('hello') else '/log')
                if document.workspace['data-path'] == '/log':
                    assert document.workspace['data-page-limit'] == '2'
                    assert len(document.children) == 2
            latest = get(save='eden-latest')
            assert int(latest.workspace['data-page-epoch']) > int(initial.workspace['data-page-epoch'])
            assert latest.workspace == get().workspace, 'Journal reads must not create a new epoch.'
            assert latest.children == get().children, 'Journal reads must not append entries.'
            (WORK / 'results.json').write_text(json.dumps({'port': port, 'mode': 'eden', 'requests': results, 'passed': True}, indent=2))
            print(f'PASS: {len(results)} real Eden requests; permalinks and mixed legacy/read-only connections coexist.', flush=True)
            raise SystemExit(0)
        latest = get(save='latest')
        check(latest, '', 40, range(10000, 9960, -1), '9961')
        assert next(event for event in latest.events if event['data-reference'] == '/log/9996')['data-event-valid'] == 'false'
        older = get('/debug/log?before=9961&limit=40', save='older')
        check(older, '9961', 40, range(9960, 9920, -1), '9921')
        assert not set(latest.children) & set(older.children)
        check(get('/debug/log?before=1', save='empty'), '1', 40, [], '')
        check(get('/debug/log?before=0'), '0', 40, [], '')
        check(get('/debug/log?before=2&limit=1', save='last'), '2', 1, [1], '')
        check(get('/debug/log?limit=1'), '', 1, [10000], '10000')
        check(get('/debug/log?before=123456789012345678901234567890&limit=2', save='huge'),
            '123456789012345678901234567890', 2, [10000, 9999], '9999')
        check(get('/debug/log?view=rendered'), '', 40, range(10000, 9960, -1), '9961')
        for query in ['before=', 'before=-1', 'before=1.0', 'before=1e3', 'before=+1',
                      'before=%201', 'before=01', 'before=00', 'limit=01', 'before=1&before=2',
                      'before=1&%62efore=2', 'limit=0', 'limit=41', 'limit=-1', 'limit=1.0',
                      'limit=', 'limit=3&limit=3', 'view=other', 'view=rendered&view=rendered',
                      'offset=40', 'care=z', 'before=%zz', 'before=3?limit=2', 'limit=3&', '=1']:
            get('/debug/log?' + query, 400)
        get('/debug/log', 405, method='POST')
        with ThreadPoolExecutor(max_workers=4) as clients:
            concurrent = list(clients.map(lambda _: get('/debug/log?limit=3'), range(8)))
        for document in concurrent:
            check(document, '', 3, [10000, 9999, 9998], '9998')
        check(get(save='repeated'), '', 40, range(10000, 9960, -1), '9961')
        (WORK / 'results.json').write_text(json.dumps({'port': port, 'requests': results, 'passed': True}, indent=2))
        print(f'PASS: {len(results)} HTTP requests; output bounded; repeated and concurrent reads preserved total and epoch.', flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
