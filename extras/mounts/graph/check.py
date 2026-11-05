#!/usr/bin/env python3
"""Native policy and compiled Grove publication checks in disposable fixtures."""
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'x'), str(ROOT / 'extras/x')]
from fixture_sources import materialize
import test_runner as runner


def main():
    runtime = os.environ.get('WISP') or shutil.which('wisp')
    if not runtime:
        raise SystemExit('Set WISP or enter the core Nix shell')
    template = (Path(os.environ['TEST_TEMPLATE']) if 'TEST_TEMPLATE' in os.environ
                else runner.stage(runtime, False, 1200))
    (ROOT / '.check').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='graph-', dir=ROOT / '.check'))
    materialize(ROOT, ROOT / 'extras', work / 'src', native_tests=True)
    suites = [dict(name='foil:' + name, target=name, kind='native', group='policy', timeout=1200)
              for name in ['graph_reference_tests', 'graph_policy_tests', 'graph_reactivity_tests', 'graph_demand_tests', 'graph_flow_tests']]
    results = [runner.run_group(suites, runtime, template, work, 1200)]
    publication = dict(name='graph-publication-tests', target='graph-publication-tests',
                       kind='reaver', group='publication', entrypoint='check', timeout=1200)
    cost = dict(name='graph-cost-tests', target='graph-cost-tests', kind='reaver',
                group='publication', entrypoint='check', timeout=1200)
    results.append(runner.run_group([publication, cost], runtime, template, work, 1200))
    (work / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('Results:', work / 'results.json')
    return int(not all(result['passed'] for result in results))


if __name__ == '__main__':
    raise SystemExit(main())
