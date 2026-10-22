#!/usr/bin/env python3
"""Check the vendored profile, native preparation, and optional browser geometry.

Requires the pinned Reaver WISP. --mash-root also runs the Chromium and SVG
consumer checks using Mash's installed Playwright; production needs neither.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]


def paint_probe():
    """Compare compiled Foil output with the CSS resolver for every recipe."""
    spec = importlib.util.spec_from_file_location('goo_profile_sync', PACKAGE / 'scripts/sync-mash-profile.py')
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    profile = sync.verify_bundle(sync.VENDOR)
    rules = sync.paint_rules((sync.VENDOR / 'profile.css').read_text())
    cases = [('button', '', primary, destructive)
             for primary in (False, True) for destructive in (False, True)]
    cases += [('text', role, False, False) for role in profile['textStyles']['roles']]
    cases += [(kind, '', False, False) for kind in ('input', 'code', 'avatar', 'presence', 'media', 'bar', 'group')]
    cases += [('text', 'unknown', True, True), ('unknown', 'title', True, True)]
    expressions, expected = [], []
    for kind, role, primary, destructive in cases:
        recipe = sync.paint_recipe(profile, rules, kind, role, primary, destructive)
        recipe['states'] = {}
        for state in ('highlight', 'focus'):
            appearance = sync.paint_recipe(profile, rules, kind, role, primary, destructive, state)
            if 'outline' in appearance:
                recipe['states'][state] = appearance['outline']
        expected.append(recipe)
        expressions.append(f'(goo_profile/paint_style {sync.quote(kind)} {sync.quote(role)} '
                           f'.{str(primary).lower()} .{str(destructive).lower()})')
    source = '\n+ goo_paint_probe\n  \\ ignored=unit\n  ^ str\n  | show (json/arr [' + ' '.join(expressions) + '])\n'
    return source, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mash-root', type=Path)
    parser.add_argument('--output', type=Path, help='Keep native logs, fixtures and SVG consumer output here')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--compiler', choices=('P6', 'none'), default='P6',
                        help='Production optimizer by default; none is for boot-compiler diagnosis')
    args = parser.parse_args()
    sys.set_int_max_str_digits(0)
    sys.path[:0] = [str(ROOT / 'x'), str(ROOT / 'extras/x')]
    import test_runner as runner
    from fixture_sources import materialize
    wisp = os.environ.get('WISP') or shutil.which('wisp')
    if not wisp:
        parser.error('Set WISP or enter the core Nix shell')
    sync = [sys.executable, str(PACKAGE / 'scripts/sync-mash-profile.py'), '--check']
    if args.mash_root:
        sync += ['--mash-root', str(args.mash_root.resolve())]
    subprocess.run(sync, check=True)
    output = (args.output or Path(tempfile.mkdtemp(prefix='goo-profile-check-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    materialize(ROOT, ROOT / 'extras', output / 'src', ['goo'])
    probe, expected_paint = paint_probe()
    with (output / 'src/foil/goo_app/prepared_tests.foil').open('a') as source:
        source.write(probe)
    # Use real file modules, matching extras/x/check.
    (output / 'src/reaver/foil-test-deps.rvr').write_text(
        '(#bind std (#module std))\n(#import std)\n'
        '(#bind fixture (#module foil-test-context))\n'
        '(#bind source (#module foil-source))\n'
        '(define (prepare cache mods) (fixture:prepare source:read-module cache mods))\n'
        '(define (generated? name) 0)\n(define module-file-stamps [])\n'
        '(#export prepare generated? module-file-stamps)\n')
    native = output / 'native' 
    runner.copy_template(runner.stage(wisp, False, args.timeout), native / 'snap')
    source = '''(#bind std (#module std))
(#import std)
(#bind source (#module foil-source))
(#bind fixture (#module foil-test-context))
(#bind driver (#module foil-new-env))
(#bind abi (#module foil-abi))
(#bind test (#module foil-test-runner))
(define (check ignored)
  (define built (source:compile (fixture:files 0 ["goo_app/prepared_tests"]) 0 "goo_app/prepared_tests"))
  (define entry (_1 built))
  (define sut (driver:perc-subject entry))
  (define fixtures (driver:source-entry-val ["goo_prepared_tests" "fixtures_text"] sut))
  (define paints (driver:source-entry-val ["goo_paint_probe"] sut))
  (Seq (test:native entry)
    (Seq (print ("GOO-PAINT-FIXTURES" (paints (abi:constructor entry ["unit"]))))
      (print ("GOO-PROFILE-FIXTURES" (fixtures (abi:constructor entry ["unit"])))))))
(check 0)
(print "TEST-RUN-DONE")
'''
    # Exercise the production tier: boot-only execution can hide expensive
    # descriptor construction inside a function body.
    if args.compiler != 'none':
        source = '(#bind opt (#module plangrm))\n(Install opt:compileP6)\n' + source
    code, completed, _ = runner.run_process(
        [wisp, '--file-root', str(output / 'src'), 'snap', 'root', '_'],
        native, source, args.timeout)
    log = (native / 'out.log').read_text(errors='replace')
    good, records = runner.verdict(log, code, completed)
    marker = re.search(r'^\("GOO-PROFILE-FIXTURES"\s+' + runner.ATOM + r'\s*\)', log, re.M)
    if not good or not marker:
        raise RuntimeError(f'Native profile checks failed: {native / "out.log"}')
    fixtures = json.loads(runner.decode_atom(marker[1]))
    paints = re.search(r'^\("GOO-PAINT-FIXTURES"\s+' + runner.ATOM + r'\s*\)', log, re.M)
    if not paints or json.loads(runner.decode_atom(paints[1])) != expected_paint:
        raise RuntimeError(f'Compiled paint recipes differ from the CSS resolver: {native / "out.log"}')
    (output / 'paint-fixtures.json').write_text(json.dumps(expected_paint, indent=2) + '\n')
    print(f'Compiled paint parity: {len(expected_paint)} recipes match the CSS resolver', flush=True)
    if not fixtures or any('error' in fixture or not fixture.get('display') for fixture in fixtures):
        raise RuntimeError('Native preparation rejected a conformance fixture')
    path = output / 'fixtures.json'
    path.write_text(json.dumps(fixtures, indent=2) + '\n')
    print(f'Native prepared contract: {sum(row[0] == "pass" for row in records)} assertions; {len(fixtures)} renderer fixtures', flush=True)
    if args.mash_root:
        subprocess.run(['node', '--test', str(PACKAGE / 'scripts/test-preview.cjs')], check=True)
        subprocess.run(['node', str(PACKAGE / 'scripts/check-profile-browser.mjs'),
                        str(path), str(PACKAGE / 'profile'), str(args.mash_root.resolve())], check=True)
    print(f'Profile conformance passed. Artifacts: {output}')


if __name__ == '__main__':
    main()
