#!/usr/bin/env python3
"""Rehearse live publication against a disposable local demo; restore source afterward."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8144')
    parser.add_argument('--node', default='0x11')
    args = parser.parse_args()
    source = f'/{args.node}/gov/demo'
    root = f'/{args.node}/app/demo'
    other = root + '_other'
    selected = root + '/notes/welcome'
    path = Path(__file__).with_name('demo.grove')
    original = path.read_text()
    def request(op, target=root, selected_path=selected, **fields):
        payload = urllib.parse.urlencode(dict(source=source, root=target, selected=selected_path, **fields))
        read = op == 'status'
        req = urllib.request.Request(args.url + '/grove/dev/' + op + ('?' + payload if read else ''), data=None if read else payload.encode())
        try:
            with urllib.request.urlopen(req, timeout=240) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    def status(target=root):
        code, state = request('status', target=target)
        assert code == 200, state
        return state
    def unit(state):
        return next(u for u in state['units'] if u['source'] == source)
    def page(route, target=selected):
        with urllib.request.urlopen(args.url + route + target, timeout=120) as response:
            return response.read().decode()
    def mutate(op, state=None, target=root, **overrides):
        state = state or status(target)
        u = unit(state)
        fields = dict(version=u['version'] or '0', scan=u['completed'], expected=state['expected'] or '')
        fields.update(overrides)
        return request(op, target=target, **fields)
    def publish(success=True):
        before = status()
        u = unit(before)
        started = time.perf_counter()
        code, pending = request('rescan', scan=u['requested'])
        assert code == 200, pending
        epoch = unit(pending)['requested']
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            current = status()
            if int(unit(current)['completed']) >= int(epoch):
                assert unit(current)['ready'] is success, current
                print(f'Publication ready={success}: {time.perf_counter()-started:.3f}s', flush=True)
                return before, current
            time.sleep(.1)
        raise AssertionError('Publication did not complete')
    def rebuild():
        started = time.perf_counter()
        before, current = publish()
        code, after = mutate('replace', current, expected=before['expected'] or '')
        assert code == 200, after
        print(f'Rebuild including replacement: {time.perf_counter()-started:.3f}s', flush=True)
        return after
    try:
        assert 'Hello from Grove' in page('/views')
        assert status()['installed'] is not None
        code, other_state = mutate('install', target=other)
        assert code == 200, other_state
        # Existing edit endpoint changes a local slot; replacement must discard it.
        data = urllib.parse.urlencode({'runtime_note':'Temporary runtime edit'}).encode()
        with urllib.request.urlopen(args.url + '/edit' + selected, data=data, timeout=60) as response:
            assert response.status == 200
        assert 'Temporary runtime edit' in page('/ns')
        changed = original.split('"/notes/second"')[0].replace('Hello from Grove', 'Updated live from Grove').replace('Edit demo.grove, then rebuild.', 'View updated without restarting.')
        changed += '"/notes/third" =\n  @tree\n  lede: "New child"\n  %/title: "Added live"\n'
        path.write_text(changed)
        updated = rebuild()
        assert 'Updated live from Grove' in page('/views')
        assert 'View updated without restarting.' in page('/views')
        assert 'Temporary runtime edit' not in page('/ns')
        assert 'Added live' in page('/views', root + '/notes/third')
        assert 'Inspect my slots' not in page('/views', root + '/notes/second')
        code, missing = request('status', selected_path=root + '/notes/second')
        assert code == 200 and missing['selected'] == root, missing
        assert 'Hello from Grove' in page('/views', other + '/notes/welcome')
        code, error = mutate('replace', updated, version='1')
        assert code == 409 and error['error'] == 'stale_template', error
        bad = changed + '\nthis = (\n'
        path.write_text(bad)
        before, failed = publish(False)
        assert failed['installed'] == before['installed'] and failed['expected'] == before['expected']
        assert unit(failed)['diagnostic'], failed
        assert 'Updated live from Grove' in page('/views')
        code, error = mutate('replace', failed)
        assert code == 409, error
        path.write_text(changed)
        rebuild()
        code, deleted = mutate('delete')
        assert code == 200 and not deleted['occupied'] and deleted['installed'] is None, deleted
        assert unit(deleted)['version'] is not None
        code, installed = mutate('install', deleted)
        assert code == 200 and installed['installed'] is not None, installed
        assert 'Updated live from Grove' in page('/views')
        # Read source/declaration and instance pages through the actual debugger.
        for target in [source, source + '/note', source + '/note_view', selected]:
            assert 'debugger/v1' in page('/debug', target)
        print('PASS: edit, rescan, atomic replace, child removal/addition, failure recovery, reset, delete/reinstall, independent instance, and debugger', flush=True)
    finally:
        path.write_text(original)
        rebuild()
        old = status(other)
        if old['installed']:
            code, result = mutate('delete', old, target=other)
            assert code == 200, result
        print('Restored demo source and live seed data.', flush=True)


if __name__ == '__main__':
    main()
