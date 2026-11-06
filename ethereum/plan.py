"""Run the real Foil/PLAN compiler in a disposable copy of the compiler image."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.set_int_max_str_digits(0)
sys.path.insert(0, str(ROOT / 'x'))
import test_runner


def run(source):
    wisp = os.environ.get('WISP') or shutil.which('wisp')
    if not wisp:
        raise RuntimeError('Run inside nix develop .#eden or set WISP to the pinned runtime')
    template = test_runner.stage(wisp, False, 900)
    directory = Path(tempfile.mkdtemp(prefix='contract-', dir=ROOT / '.check'))
    test_runner.copy_template(template, directory / 'snap')
    code, complete, _ = test_runner.run_process(
        [wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
        directory, source + '\n(print "TEST-RUN-DONE")\n', 180)
    log = (directory / 'out.log').read_text()
    if not test_runner.verdict(log, code, complete)[0]:
        raise RuntimeError(f'PLAN compilation failed: {directory}/out.log')
    # PLAN prints cords as quoted text or decimal naturals, depending on bytes.
    matches = re.findall(r'^\(0 "CONTRACT-OUTPUT"\s+' + test_runner.ATOM + r'\)', log, re.M)
    if not matches:
        raise RuntimeError(f'Missing compiler output: {directory}/out.log')
    return json.loads(test_runner.decode_atom(matches[-1]))


def compile_contract(module='contracts/checked', cases=()):
    if not re.fullmatch(r'[a-zA-Z0-9_/-]+', module) or '..' in module:
        raise ValueError('Invalid module name')
    rows = '[' + ' '.join('[' + ' '.join(str(int(x)) for x in row) + ']' for row in cases) + ']'
    return run(f'''(#bind build (#module contract-build))
(#bind source (#module contract-source))
(#bind std (#module std))
(#import std)
(define artifact (source:compile "{module}"))
(print ["CONTRACT-OUTPUT" (build:report artifact {rows})])''')
