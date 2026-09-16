#!/usr/bin/env python3
"""Build current Grove + Mash sources and verify the native declaration in an inert browser.

Requires WISP (or wisp on PATH), Node, pnpm, and an explicit MASH_ROOT checkout
with dependencies installed from its lockfile. Never reads a live namespace.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import test_runner as runner


def source_digest():
    digest = hashlib.sha256()
    for path in sorted((runner.ROOT / 'src').rglob('*')):
        if path.suffix in ('.rvr', '.foil', '.grove') and path.is_file():
            digest.update(str(path.relative_to(runner.ROOT)).encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


def check(args):
    wisp = os.environ.get('WISP') or shutil.which('wisp')
    node = os.environ.get('NODE') or shutil.which('node')
    if not wisp or not node:
        raise RuntimeError('Set WISP and NODE or put wisp and node on PATH.')
    if not args.backend_only and not os.environ.get('MASH_ROOT'):
        raise RuntimeError('Set MASH_ROOT to the explicit paired Mash checkout.')
    work = Path(tempfile.mkdtemp(prefix='shrine-debugger-check-')).resolve()
    print('Debugger check artifacts: ' + str(work), flush=True)
    code, complete, _ = runner.run_process([sys.executable,str(runner.ROOT / 'x/debug-runtime-tests.py')],
                                          work / 'launcher', '', 30, cwd=runner.ROOT)
    if code or not complete:
        raise RuntimeError('Launcher regression failed: ' + str(work / 'launcher/out.log'))
    template = Path(os.environ['TEST_TEMPLATE']) if os.environ.get('TEST_TEMPLATE') else runner.stage(wisp, False, 900)
    runner.copy_template(template, work / 'native/snap')
    before = source_digest()
    source = '\n'.join([
        '(#bind suite (#module foil-grove-debugger-tests))',
        '(#bind backend-tests (#module foil-grove-backend-tests))',
        '(#bind backend-fixture (#module foil-grove-fixture))',
        '(print ("DEBUGGER-COMPILER-PASS" (backend-tests:run (backend-fixture:create 0))))',
        '(print "TEST-RUN-DONE")', '',
    ])
    code, complete, seconds = runner.run_process(
        [wisp, '--file-root', str(runner.ROOT / 'src'), 'snap', 'root', '_'],
        work / 'native', source, 900)
    log_path = work / 'native/out.log'
    log = log_path.read_text(errors='replace')
    if (not runner.verdict(log, code, complete)[0]
            or '"DEBUGGER-APPLICATION-PASS"' not in log
            or '"DEBUGGER-PINNED-BOUNDARY-PASS"' not in log
            or '("DEBUGGER-HOST-COMPILED" 1)' not in log
            or '("DEBUGGER-COMPILER-PASS" 1)' not in log):
        raise RuntimeError('Native declaration check failed: ' + str(log_path))
    if source_digest() != before:
        raise RuntimeError('Backend sources changed during compilation; rerun the gate.')
    report = dict(sourceSha256=before, nativeSeconds=seconds, nativeLog=str(log_path), browser=False)
    if not args.backend_only:
        env = dict(os.environ, GROVE_CHECK_LOG=str(log_path), TEST_RUN_DIR=str(work),
                   DEBUG_OUTPUT_ROOT=str(work / 'assets/foil'))
        for name, command in [('build-boundary',[node,str(runner.ROOT / 'x/debug-build-test.mjs')]),
                              ('read-queue',[node,str(runner.ROOT / 'x/debug-preview-queue-test.mjs')]),
                              ('values',[node,str(runner.ROOT / 'x/debug-values-test.mjs')]),
                              ('physical-parser',[node,str(runner.ROOT / 'x/debug-physical-contract-test.mjs')]),
                              ('assets',[node,str(runner.ROOT / 'x/build-debug.mjs'), *(['--release'] if args.release else [])]),
                              ('browser',[node,str(runner.ROOT / 'x/debug-declaration-test.mjs')])]:
            code, complete, _ = runner.run_process(command, work / name, '', 900, env, runner.ROOT)
            if code or not complete:
                raise RuntimeError(name + ' check failed: ' + str(work / name / 'out.log'))
            print((work / name / 'out.log').read_text(errors='replace')[-3500:], flush=True)
        report['browser'] = True
        report['build'] = json.loads((work / 'assets/foil/build.json').read_text())
    (work / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('GROVE-DEBUGGER-CHECK-PASS' if report['browser'] else 'GROVE-DEBUGGER-BACKEND-PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-only', action='store_true')
    parser.add_argument('--release', action='store_true', help='Require the pinned, clean paired Mash commit')
    try:
        check(parser.parse_args())
    except (RuntimeError, OSError) as error:
        sys.exit(str(error))
