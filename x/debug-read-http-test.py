#!/usr/bin/env python3
"""Read-only debugger regression against an explicitly owned disposable runtime.

Never accepts a bare URL or a user snapshot. Start a fresh runtime with
debug-grove-runtime.py, then pass its manifest. Timings are observations, not
cross-machine pass thresholds; namespace mutation and contract drift are errors.
"""
import argparse
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import socket
import statistics
import tempfile
import time
import urllib.error
import urllib.request


def check(manifest):
    runtime_path = Path(__file__).with_name('debug-grove-runtime.py')
    spec = importlib.util.spec_from_file_location('grove_runtime', runtime_path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    owned = runtime.owned(Path(manifest))
    assert owned['port'] not in (8138, 51571), 'Never profile a protected namespace'
    output = Path(tempfile.mkdtemp(prefix='read-regression-', dir=owned['work']))
    requests, checkpoints = [], []
    report = dict(runtime=owned['id'], origin=owned['origin'], requests=requests,
                  checkpoints=checkpoints, passed=False)

    def get(path, expected=200):
        start = time.perf_counter()
        try:
            response = urllib.request.urlopen(owned['origin'] + path, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == expected, (path, response.status, body[:300])
            assert int(response.headers['Content-Length']) == len(body)
        requests.append(dict(path=path, status=response.status, bytes=len(body),
                             ms=round(1000 * (time.perf_counter() - start), 3)))
        return body

    def checkpoint(label):
        data = json.loads(get('/debug-read/physical?pathKey=v1/ts:696f/ts:68747470&collection=children&limit=1'))
        point = dict(label=label, epoch=data['epoch'], retained=data['total'])
        checkpoints.append(point)
        assert not checkpoints[:-1] or (point['epoch'], point['retained']) == (
            checkpoints[0]['epoch'], checkpoints[0]['retained']), checkpoints

    try:
        checkpoint('before')
        for _ in range(21):
            get('/debug/hello')
        checkpoint('after-documents')
        for path in ('/debug/gov/srs', '/debug', '/debug/app', '/debug/weft'):
            for scope in ('', 'workspace', 'outline', 'preview'):
                body = get(path + ('?scope=' + scope if scope else ''))
                assert b'data-grove-contract="debugger/v1"' in body
                if scope:
                    assert b'<script' not in body and b'id="debug-sidebar"' not in body
                if scope != 'preview':
                    assert b'id="debug-path-preview"' not in body
        # A cursor never silently traverses a different snapshot.
        get('/debug?scope=workspace&epoch=0', 409)
        get('/debug?scope=invalid', 400)
        checkpoint('before-disconnect')
        with socket.create_connection(('127.0.0.1', owned['port']), timeout=3) as connection:
            connection.sendall(b'GET /debug/gov/srs?scope=workspace HTTP/1.0\r\nHost: localhost\r\n\r\n')
            time.sleep(.02)
        # The following read is a mailbox barrier, not a claim of preemption.
        checkpoint('after-disconnect')
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: get('/debug/gov/srs?scope=workspace'), range(3)))
        checkpoint('final')
        report['helloMedianMs'] = statistics.median(
            row['ms'] for row in requests if row['path'] == '/debug/hello')
        report['passed'] = True
    finally:
        (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(output=str(output), passed=report['passed'],
                              requests=len(requests), checkpoints=checkpoints,
                              helloMedianMs=report.get('helloMedianMs'))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    check(parser.parse_args().manifest)
