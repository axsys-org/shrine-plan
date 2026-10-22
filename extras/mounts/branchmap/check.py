#!/usr/bin/env python3
"""Run the Foil domain tests using Shrine's real compiler/runtime."""
from pathlib import Path
import hashlib,json,os,shutil,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'x'))
import test_runner as runner
runtime=os.environ.get('WISP') or shutil.which('wisp')
if not runtime: raise SystemExit('Enter the pinned eden Nix shell first')
template=runner.stage(runtime,False,1200)
work=Path(tempfile.mkdtemp(prefix='branchmap-tests-'))
shutil.copytree(ROOT/'src',work/'src')
mount=Path(__file__).resolve().parent
manifest=json.loads((mount/'mount.json').read_text())
for name,leaf in {**manifest['modules'],**manifest['tests']}.items():
    target=work/'src/foil'/f'{name}.foil';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(mount/leaf,target)
suite=dict(name='foil:tests/branchmap',target='tests/branchmap',kind='native',group='branchmap',timeout=1200)
result=runner.run_group([suite],runtime,template,work,1200)
result['source_sha256']={leaf:hashlib.sha256((work/'src/foil'/f'{name}.foil').read_bytes()).hexdigest() for name,leaf in {**manifest['modules'],**manifest['tests']}.items()}
output=mount/'run/native-checks.json';output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result,indent=2)+'\n')
print(f"{sum(row[0]=='pass' for row in result['records'])} native checks passed; report: {output}")
raise SystemExit(0 if result['passed'] else 1)
