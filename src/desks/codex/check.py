"""Stage the flat desk against this checkout and run its Foil checks."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

desk = Path(__file__).resolve().parent
repo = desk.parents[2]
sys.path.insert(0, str(repo / 'x'))
import test_runner as runner

runtime = os.environ.get('WISP') or shutil.which('wisp')
if not runtime:
    raise SystemExit('Set WISP to the native runtime executable.')
template = runner.stage(runtime, False, 300)
work = Path(tempfile.mkdtemp(prefix='codex-desk-', dir=repo / '.check'))
shutil.copytree(repo / 'src', work / 'src')
for source in desk.glob('*.foil'):
    shutil.copy2(source, work / 'src' / 'foil' / source.name)
env = dict(os.environ, WISP=runtime, FOIL_SRC=str(work / 'src'))
compiled = subprocess.run(
    [str(repo / 'x' / 'foil-check'), '--node', '0x15', 'codex_driver'],
    env=env, cwd=repo)
if compiled.returncode:
    raise SystemExit(compiled.returncode)
suites = [dict(name='foil:' + name, kind='native', target=name,
               group='codex', timeout=300)
          for name in ['codex_tests', 'codex_foot_tests', 'codex_ui_tests']]
result = runner.run_group(suites, runtime, template, work, 300)
print('Results:', work)
raise SystemExit(0 if result['passed'] else 1)
