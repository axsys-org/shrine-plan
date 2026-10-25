"""Compile the real Grove component views in a disposable native test fixture."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'x'))
import test_runner as runner

runtime = os.environ.get('WISP') or shutil.which('wisp')
if not runtime:
    raise SystemExit('Set WISP or enter the core Nix shell.')
manifest = json.loads((HERE / 'mount.json').read_text())
source = '\n'.join((HERE / name).read_text() for name in manifest['grove'][0]['files'])
names = re.findall(r'^(\w+) =\n  @view\s*$', source, re.MULTILINE)
if not names:
    raise SystemExit('No component views found.')

def cord(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '""') + '"'

fixture = '''- grove_views
- testing
+ component_source
  ^ str
  | str/join (str/from_atom 10)
    [SOURCE_LINES]
+ message
  (@ v)
  \\ result=either[grove/error v]
  ^ str
  ? result
   > (./ok _) "valid"
   > (./err cause)
    ? cause
     > (grove/error/syntax span text) (str/cat_all [(nat/show span.line) ": " text])
     > (grove/error/parser _) "Rex parse failure"
+ checks
  \\ ignored=unit
  ^ row[testing/check]
  = parsed (grove/parse component_source)
  ?> (./ok doc) parsed [(testing/text "parse components" "valid Grove" (message[grove/document] parsed))]
  = compile (\\ name=str (grove_views/compile ['gov 'components] doc (\\ path .none) .nil (goo/html_types ['lib 'grove 'types]) name))
    names=row[str] [VIEW_NAMES]
  | names.map
    \\ name
    = result (compile name)
    | testing/text name "valid view" (? (either/is_ok result) "valid view" (message[goo/view] result))
+ tests
  ^ row[testing/case]
  [(testing/case "Component declarations" checks)]
'''.replace('SOURCE_LINES', '\n     '.join(map(cord, source.splitlines())))
fixture = fixture.replace('VIEW_NAMES', ' '.join(map(cord, names)))
work = Path(tempfile.mkdtemp(prefix='goo-components-views-'))
shutil.copytree(ROOT / 'src', work / 'src')
(work / 'src/foil/tests/goo_components_views.foil').write_text(fixture)
template = runner.stage(runtime, False, 1200)
result = runner.run_group([dict(name='foil:tests/goo_components_views',
    target='tests/goo_components_views', kind='native', group='views', timeout=300)],
    runtime, template, work, 300)
(work / 'results.json').write_text(json.dumps(result, indent=2))
print(f'View check artifacts: {work}')
raise SystemExit(0 if result['passed'] else 1)
