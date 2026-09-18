"""Installed only by x/check-rescan in its private editable checkout."""
import importlib.util
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent


def check(url, node, timeout):
    spec = importlib.util.spec_from_file_location('srs_integration', ROOT / 'host.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.check(url, node, timeout)
    def get(path):
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            return response.read().decode()
    def post(path, fields):
        request = urllib.request.Request(url + path, data=urllib.parse.urlencode(fields).encode())
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode()
    def version():
        return re.search(r'name="version" value="(\d+)"', get('/ns/' + node + '/gov/srs')).group(1)
    key = 'v1/x:' + node[2:] + ''.join('/ts:' + part.encode().hex() for part in ('io', 'fs', 'srs'))
    def status():
        response = json.loads(get('/debug-read/physical?' + urllib.parse.urlencode(
            {'pathKey': key, 'collection': 'slots', 'limit': '40'})))
        values = {}
        for entry in response['entries']:
            path = entry.get('displayKey') or ''
            for name in ('epoch', 'ready', 'publication'):
                if path.endswith('/fs/source/' + name):
                    values[name] = int.from_bytes(bytes.fromhex(entry['value']['hex']), 'little')
        assert len(values) == 3, response
        return values
    def rescan(ready):
        before = status()
        post('/op/' + node + '/io/fs/srs', {'op': '/' + node + '/io/fs/srs/op/rescan'})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            after = status()
            if after['epoch'] > before['epoch']:
                assert after['ready'] == ready, after
                return before, after
            time.sleep(.1)
        raise AssertionError('Source scan did not complete')
    original_version = version()
    before, after = rescan(1)
    assert before['publication'] == after['publication']
    source = ROOT / 'srs.grove'
    original = source.read_text()
    source.rename(ROOT / 'withheld.grove')
    try:
        rescan(0)
        assert version() == original_version
    finally:
        (ROOT / 'withheld.grove').rename(source)
    try:
        source.write_text('this is deliberately invalid Grove source\n')
        rescan(0)
        assert version() == original_version
        source.write_text(original.replace('What does a Shrine name identify?', 'Revised source snapshot?'))
        rescan(1)
        new_version = version()
        assert new_version != original_version
        assert 'What does a Shrine name identify?' in get('/ns/' + node + '/app/srs/cards/demo')
        post('/grove/install', {'source': '/' + node + '/gov/srs', 'version': new_version,
                               'root': '/' + node + '/app/third'})
        assert 'Revised source snapshot?' in get('/ns/' + node + '/app/third/cards/demo')
        before, after = rescan(1)
        assert before['publication'] == after['publication']
    finally:
        source.write_text(original)
    print('RESCAN-PASS: unchanged, missing, invalid, new publication, pinned and fresh instances', flush=True)
