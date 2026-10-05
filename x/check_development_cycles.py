#!/usr/bin/env python3
"""Real serial Foil compile/evaluate/discard cycles through the native runner."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from test_runner import (ROOT, check_root, stage, copy_template, run_process,
                         verdict, discard_test_snapshot, compact_test_sources,
                         unresolved_stores)
from eden_runtime import atomic_json, require_disk_space
import fcntl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=50)
    parser.add_argument('--timeout', type=float, default=90)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 50:
        parser.error('cycles must be between 1 and 50')
    runtime = args.runtime.resolve()
    cache = check_root()
    cache.mkdir(parents=True, exist_ok=True)
    template = stage(str(runtime), False, 900)
    root = Path(tempfile.mkdtemp(prefix='run-', dir=cache))
    shutil.copytree(ROOT / 'src', root / 'src')
    shutil.copyfile(ROOT / 'x/fixtures/development-cycle.rvr',
                    root / 'src/reaver/development-cycle.rvr')
    atomic_json(root / 'engine.json', dict(path=str(runtime),
        sha256=hashlib.sha256(runtime.read_bytes()).hexdigest()))
    results = []
    print('Results:', root, flush=True)
    # The same lock used by the ordinary native runner: never fifty concurrent
    # worlds. Retain one failed worker for diagnosis and stop on its first error.
    with (cache / 'retention.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if len(unresolved_stores(cache)) >= 2:
            raise RuntimeError('Two unresolved test stores already exist; diagnose them before this run')
        for index in range(1, args.cycles + 1):
            require_disk_space(root)
            directory = root / f'cycle-{index:02d}'
            copy_template(template, directory / 'snap')
            # Distinct native implementations, all evaluated against a real
            # argument. Python emits source and verifies receipts, not behavior.
            source = f'+ evaluate\n  \\ value=nat\n  ^ nat\n  {index}\n'
            (directory / 'candidate.foil').write_text(source)
            # Reaver cords do not use Python's backslash escapes. Pass exact
            # UTF-8 bytes as a native text atom; retain readable source beside it.
            text_atom = str(int.from_bytes(source.encode(), 'little'))
            program = ('(#bind cycle (#module development-cycle))\n'
                f'(cycle:run {text_atom} {index})\n'
                '(print "TEST-RUN-DONE")\n')
            started = time.time()
            code, complete, seconds = run_process(
                [str(runtime), '--file-root', str(root / 'src'), 'snap', 'root', '_'],
                directory, program, args.timeout)
            log = (directory / 'out.log').read_text()
            passed, _ = verdict(log, code, complete)
            result = dict(cycle=index, passed=bool(passed), seconds=seconds,
                started=started, completed=time.time(), returncode=code,
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                pin_bytes=(directory / 'snap/pins.pack').stat().st_size)
            atomic_json(directory / 'result.json', result)
            results.append(result)
            atomic_json(root / 'results.json', results)
            if passed:
                discard_test_snapshot(directory)
            print(('PASS' if passed else 'FAIL'), f'cycle {index}/{args.cycles}',
                  f'({seconds:.2f}s)', flush=True)
            if not passed:
                print('Inspect:', directory / 'out.log', flush=True)
                return 1
    assert not list(root.glob('*/snap')), 'Successful disposable stores accumulated'
    compact_test_sources(root)
    atomic_json(root / 'acceptance.json', dict(passed=True, cycles=len(results),
        successful_stores_retained=0, fixture='Distinct minimal Foil functions; not a bound on arbitrary application compilation',
        results='results.json', engine='engine.json', source='source-manifest.json'))
    print('Accepted:', root / 'acceptance.json', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
