#!/usr/bin/env python3
"""Compile and exercise the local Hyp supervisor and its Grove schema."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

EXTRAS = Path(__file__).resolve().parents[2]
CORE = Path(os.environ.get("SHRINE_CORE_ROOT", EXTRAS.parent)).resolve()
sys.path.insert(0, str(CORE / "x"))
sys.path.insert(0, str(EXTRAS / "x"))
from fixture_sources import materialize

from namespace_identity import parse_node_identity
from test_runner import stage


def main():
    root = CORE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default='0x11',
                        help='Host identity (default: fixture 0x11)')
    parser.add_argument('--runtime', default=os.environ.get('WISP'))
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--check', action='store_true',
                        help='Run the publication and actor integration check')
    args = parser.parse_args()
    try:
        node, _ = parse_node_identity(args.node)
    except ValueError as error:
        parser.error(str(error))
    runtime = args.runtime or shutil.which('wisp') or str(root / 'wisp')
    if not os.access(runtime, os.X_OK):
        parser.error('Set WISP or --runtime to a working runtime executable')
    runtime = str(Path(runtime).resolve())
    template = stage(runtime, False, args.timeout)
    work = Path(tempfile.mkdtemp(prefix='hyp-', dir=root / '.check'))
    materialize(root, EXTRAS, work / 'src', ['hyp'])
    (work / 'snap').mkdir()
    for name in ('data.mdb', 'pins.pack'):
        shutil.copy2(template / name, work / 'snap' / name)
    source = f'''(#bind hyp (#module hyp))
(#bind bootstrap (#module foil-bootstrap))
(#bind driver (#module foil-new-env))
(#bind std (#module std))
(#import std)
(define (launch ignored)
  (define (resolve name) [["x" {node}] ["ts" "lib"] ["ts" name]])
  (define slot [("x" {node}) ("ts" "compiler") ("ts" "artifact")])
  (define system (bootstrap:build-system (Pin driver:compile) resolve slot))
  (hyp:check ("x" {node}) system resolve slot))
(launch 0)
(print "HYP-CHECK-DONE")
'''
    log = work / 'out.log'
    print(f'Compiling and running Hyp. Log: {log}', flush=True)
    with log.open('w') as output:
        try:
            result = subprocess.run(
                [runtime, '--file-root', str(work / 'src'),
                 'snap', 'root', '_'],
                cwd=work, input=source, text=True, stdout=output,
                stderr=subprocess.STDOUT, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f'Hyp timed out; inspect {log}')
            return 1
    text = log.read_text(errors='replace')
    if (result.returncode or 'Hyp integration passed' not in text
            or 'HYP-CHECK-DONE' not in text or '("ERROR"' in text):
        print(f'Hyp failed (exit {result.returncode}); inspect {log}')
        print(text[-4000:])
        return 1
    print('Hyp passed: Grove publication and installation, two isolated '
          'guests, namespace request/receipt, and mounted read via actor.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
