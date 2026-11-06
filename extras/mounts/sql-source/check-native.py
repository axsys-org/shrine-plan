"""Opt-in WWI proof in a disposable native world, through the existing test runner."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / 'x'), str(REPO / 'extras/x')]
import test_runner
from eden_mounts import select
from fixture_sources import materialize


def main():
    runtime = os.environ.get('WISP') or shutil.which('wisp')
    if not runtime:
        raise RuntimeError('Run in the Eden Nix shell or set WISP')
    original = Path(os.environ['SHRINE_SQL_CONFIG']).resolve()
    config = json.loads(original.read_text())
    config['port'] = 0
    for query in config['queries'].values():
        query['file'] = str((original.parent / query['file']).resolve())
    root = Path(tempfile.mkdtemp(prefix='sql-native-', dir=REPO / '.check'))
    config_file = root / 'source.json'
    config_file.write_text(json.dumps(config))
    config_file.chmod(0o600)
    os.environ['SHRINE_SQL_CONFIG'] = str(config_file)
    spec = importlib.util.spec_from_file_location('sql_host', HERE / 'host.py')
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    try:
        with ExitStack() as cleanup:
            bag, _ = host.prepare(HERE, root / 'transport', True, cleanup, {'timeout': 30})
            endpoints = json.loads((bag / 'endpoint.json').read_text())
            url = endpoints['orders']['url'] + '?after=0&limit=3'
            assert urlparse(url).hostname == '127.0.0.1'
            mounts = select(REPO / 'extras', ['flow-examples'])
            materialize(REPO, REPO / 'extras', root / 'src', {m.name for m in mounts}, native_tests=True)
            # Token validation in the companion ensures this replacement cannot
            # inject Foil source. The fixture and logs remain in a private folder.
            source = (HERE / 'tests/wwi.foil').read_text().replace('SQL_SOURCE_URL', url)
            (root / 'src/foil/live_sql_test.foil').write_text(source)
            (root / 'src/examples/wwi-endpoints.json').write_text(json.dumps(endpoints))
            (root / 'src/foil/live_workspace_test.foil').write_text(
                '- flow_workspace_tests\n'
                '+ checks\n  \\ ignored=unit\n  ^ row[testing/check]\n'
                '  = ;bytes (ReadFile "examples/wwi-endpoints.json")\n'
                '  | workspace_tests/checks (flow_web_foot/unbar bytes) .true ignored\n'
                '+ tests\n  ^ row[testing/case]\n'
                '  [(testing/case "single invocation assembles live WWI" checks)]\n')
            template = test_runner.stage(runtime, False, 1200)
            suites = [dict(name='foil:' + name, kind='native', target=name, group='sql-native')
                      for name in ['flow_web_tests', 'flow_workspace_tests', 'live_sql_test', 'live_workspace_test']]
            result = test_runner.run_group(suites, runtime, template, root, 1200)
            (root / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
            print('Validation:', root)
            return 0 if result['passed'] else 1
    finally:
        config_file.unlink(missing_ok=True)
        os.environ['SHRINE_SQL_CONFIG'] = str(original)


if __name__ == '__main__':
    raise SystemExit(main())
