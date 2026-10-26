#!/usr/bin/env python3
"""Exercise native dynamic watches against real files in a disposable world.

Only this test driver deletes/restores fixture files. The application lifecycle
runs entirely in Foil through the existing supervisor, filesystem foot, and
published source operations. No live world, port, or persisted arena is opened.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'x'))
import test_runner as runner
from eden_mounts import select


def main():
    runtime = os.environ.get('WISP') or shutil.which('wisp')
    if not runtime:
        raise SystemExit('Set WISP or enter the core Nix shell')
    (ROOT / '.check').mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='watch-lifecycle-', dir=ROOT / '.check'))
    sys.path.insert(0, str(ROOT / 'extras/x'))
    from fixture_sources import materialize
    mounts = select(ROOT / 'extras', ['flows'])
    materialize(ROOT, ROOT / 'extras', root / 'src', {m.name for m in mounts}, native_tests=True)
    shutil.copyfile(Path(__file__).with_name('watch_lifecycle.foil'), root / 'src/foil/tests/watch_lifecycle.foil')
    files = root / 'src/watch'
    for name in ['a', 'b']:
        (files / name).mkdir(parents=True)

    def bundle(name, revision):
        (files / name / 'bundle').write_text(json.dumps({'source': {
            'location': name + '/README.md', 'digest': str(revision) * 64,
            'title': name, 'format': 'md', 'content': f'Source {name} revision {revision}'}}))

    bundle('a', 1)
    bundle('b', 1)
    stopped = threading.Event()
    faults = []

    def mutate_fixtures():
        last = 0
        try:
            while not stopped.wait(.05):
                try:
                    raw = (files / 'action').read_bytes()
                except FileNotFoundError:
                    continue
                if len(raw) != 1 or raw[0] == last:
                    continue
                action = raw[0]
                if action == 1:
                    (files / 'b/bundle').unlink()
                elif action == 2:
                    bundle('b', 1)
                elif action == 3:
                    bundle('b', 2)
                    (files / 'block').write_bytes(b'\x01')
                elif action == 4:
                    (files / 'block').write_bytes(b'\x00')
                else:
                    raise AssertionError(f'Unknown fixture action: {action}')
                (files / 'done').write_bytes(raw)
                last = action
        except Exception as exc:
            faults.append(repr(exc))

    worker = threading.Thread(target=mutate_fixtures, daemon=True)
    worker.start()
    print(f'Disposable watch world: {root}', flush=True)
    try:
        template = runner.stage(runtime, False, 1200)
        suites = [dict(name='foil:' + name, target=name, kind='native',
                       group='native', timeout=1200)
                  for name in ['tests/watch_lifecycle']]
        result = runner.run_group(suites, runtime, template, root, 1200)
    finally:
        stopped.set()
        worker.join()
    print(json.dumps({'passed': result['passed'], 'fixture_errors': faults,
                      'results': str(root / 'native/result.json')}, indent=2))
    return 0 if result['passed'] and not faults else 1


if __name__ == '__main__':
    raise SystemExit(main())
