#!/usr/bin/env python3
"""Compile and execute the search scan-oracle suite in an isolated source snapshot."""
import argparse, importlib.util, json, os, shutil, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--reaver',type=Path,default=Path(__file__).resolve().parents[2])
p.add_argument('--wisp',default=os.environ.get('WISP') or shutil.which('wisp'))
p.add_argument('--suite',type=Path,help='Alternative Foil test module for isolated profiling')
p.add_argument('--output',type=Path,default=Path('artifacts/path-search-oracle.json'))
a=p.parse_args();core=a.reaver.resolve();here=Path(__file__).resolve().parent.parent/'mounts'
if not a.wisp: p.error('Set WISP or pass --wisp with the current Reaver runtime')
spec=importlib.util.spec_from_file_location('test_runner',core/'x/test_runner.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
template=runner.stage(a.wisp,False,900)
with tempfile.TemporaryDirectory(prefix='shuin-search-check-') as directory:
 root=Path(directory);shutil.copytree(core/'src',root/'src',symlinks=True)
 shutil.copyfile(here/'shuin-chat/namespace_search.foil',root/'src/foil/namespace_search.foil')
 shutil.copyfile(here/'shuin-chat-test/search_index.foil',root/'src/foil/tests/search_index_support.foil')
 shutil.copyfile(a.suite or here/'shuin-chat-test/search_index.foil',root/'src/foil/tests/search_index.foil')
 result=runner.run_group([dict(name='foil:tests/search_index',kind='native',target='tests/search_index',group='native')],a.wisp,template,root,900)
 a.output.parent.mkdir(parents=True,exist_ok=True);log=a.output.with_suffix('.log');shutil.copyfile(result['log'],log)
 result['log']=str(log.resolve());a.output.write_text(json.dumps(result,indent=2)+'\n')
 raise SystemExit(not result['passed'])
