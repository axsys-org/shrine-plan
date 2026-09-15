"""Failure-path tests for the gate; run with python3 x/test_runner_tests.py."""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

import test_runner as runner


class ProtocolTests(unittest.TestCase):
    def test_shared_fixture_is_built_once_and_passed_to_each_entrypoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suites = [dict(name=name, kind='reaver', target=name, group='exec',
                           entrypoint='check', fixture=['fixture', 'create'])
                      for name in ['first', 'second']]
            captured = []
            def copy(_source, target):
                target.mkdir(parents=True)
            def execute(_command, directory, source, _timeout):
                captured.append(source)
                (directory / 'out.log').write_text(
                    ''.join(f'("TEST" "pass" "{suite["name"]}" "~:module" "~:" "~:")\n'
                            for suite in suites) + runner.DONE + '\n')
                return 0, True, 0.0
            with patch.object(runner, 'copy_template', copy), \
                 patch.object(runner, 'run_process', execute):
                runner.run_group(suites, 'wisp', root, root, 1)
            source = captured[0]
            self.assertEqual(source.count('(test_fixture_0_module:create 0)'), 1)
            self.assertIn('(#module fixture)', source)
            self.assertIn('(first:check test_fixture_0)', source)
            self.assertIn('(second:check test_fixture_0)', source)
            self.assertLess(source.index('(define (test_fixture_run ignored)'),
                            source.index('(define test_fixture_0'))
            self.assertLess(source.index('(#bind first'),
                            source.index('(define test_fixture_0'))

    def test_doctests_count_and_locate_the_frozen_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = root / 'src/foil/example.foil'
            frozen.parent.mkdir(parents=True)
            frozen.write_text("' ?= ((add 1 1) 2)\n")
            live = root / 'checkout/src/foil/example.foil'
            live.parent.mkdir(parents=True)
            live.write_text("+ changed 0\n")
            suite = dict(name='doc:example', kind='docs', target='example',
                         group='doctests')
            def copy(_source, target):
                target.mkdir(parents=True)
            def execute(_command, directory, _input, _timeout):
                (directory / 'out.log').write_text(
                    '("TEST" "pass" "example" "~:1: ?= ((add 1 1) 2)" '
                    '"~:2" "~:2")\n' + runner.DONE + '\n')
                return 0, True, 0.0
            with patch.object(runner, 'ROOT', root / 'checkout'), \
                 patch.object(runner, 'copy_template', copy), \
                 patch.object(runner, 'run_process', execute):
                result = runner.run_group([suite], 'wisp', root, root, 1)
            self.assertTrue(result['passed'])
            self.assertEqual(list(result['locations'].values()),
                             [str(frozen) + ':1'])

    def test_deprecated_compiler_cannot_reenter_module_graph(self):
        retired = {'foil', 'compiler-host', 'helm-host'}
        modules = {p.stem for p in (runner.ROOT / 'src/reaver').glob('*.rvr')}
        self.assertFalse(retired & modules)
        self.assertFalse(retired & runner.reaver_closure(modules))

    def test_retired_type_system_cannot_return(self):
        retired = {'foil-types', 'foil-core-types', 'foil-types-tests'}
        sources = list((runner.ROOT / 'src/reaver').glob('*.rvr'))
        modules = {p.stem for p in sources}
        self.assertFalse(retired & modules)
        self.assertFalse(retired & runner.reaver_closure(modules))
        for name in retired:
            self.assertNotIn(name, (runner.ROOT / 'test-inventory.json').read_text())
        # Old tags are allowed only as deliberately invalid test inputs.
        rejection_tests = {'typed-reaver-tests', 'foil-relocate-tests',
                           'compiler-inspect-tests'}
        for path in sources:
            if path.stem not in rejection_tests:
                self.assertNotIn('/foil/types/', path.read_text(), str(path))

    def test_type_core_has_no_compiler_or_ffi_dependency(self):
        closure = runner.reaver_closure(['foil-type-core'])
        self.assertFalse({'foil-types', 'foil-core-types', 'foil-builtins',
                          'typed-reaver', 'foil-new-elab', 'foil-new-env'} & closure)

    def test_ffi_producers_do_not_depend_on_retired_types(self):
        closure = runner.reaver_closure(['foil-builtins', 'typed-reaver'])
        self.assertFalse({'foil-types', 'foil-core-types',
                          'foil-new-elab', 'foil-new-env'} & closure)

    def test_compiler_consumers_do_not_import_retired_types(self):
        closure = runner.reaver_closure([
            'foil-new-env', 'foil-lower', 'foil-render', 'foil-relocate',
            'foil-entry', 'compiler-inspect', 'compiler-build',
        ])
        self.assertFalse({'foil-types', 'foil-core-types'} & closure)

    def test_wrapped_fields_and_escaping(self):
        log = '("TEST" "fail" "tests/json"\n "quoted ""case"""\n "a\\\\b" "actual")\n'
        self.assertEqual(runner.events(log), [('fail', 'tests/json', 'quoted "case"', 'a\\b', 'actual')])

    def test_decimal_cords_and_malformed_records(self):
        text = '~:quoted "example"'
        packed = int.from_bytes(text.encode(), 'little')
        log = f'("TEST" "fail" "m" {packed} "~:" "~:")'
        self.assertEqual(runner.events(log)[0][2:], ('quoted "example"', '', ''))
        self.assertFalse(runner.verdict('("TEST" garbage)\n' + runner.DONE, 0)[0])

    def test_completion_is_required_even_on_zero_exit(self):
        self.assertFalse(runner.verdict('', 0)[0])
        self.assertFalse(runner.verdict('(0 ' + runner.DONE + ')', 0)[0])
        self.assertFalse(runner.verdict('("TEST" "start" "m" "case" "~:" "~:")\n' + runner.DONE, 0)[0])
        self.assertTrue(runner.verdict(runner.DONE, 0)[0])
        self.assertFalse(runner.verdict(runner.DONE, -6)[0])
        self.assertFalse(runner.verdict(runner.DONE, 0, False)[0])

    def test_caught_error_trace_is_not_uncaught_error(self):
        self.assertTrue(runner.verdict('("Error" "expected")\n' + runner.DONE, 0)[0])
        self.assertFalse(runner.verdict('("ERROR" "uncaught")\n' + runner.DONE, 0)[0])

    def test_all_nonpass_results_fail(self):
        for status in ['fail', 'error', 'broken', 'unknown']:
            log = f'("TEST" "{status}" "m" "case" "1" "2")\n' + runner.DONE
            self.assertFalse(runner.verdict(log, 0)[0], status)

    def test_large_logs_preserve_protocol_and_failures(self):
        record = '("TEST" "pass" "m"\n  "~:module" "~:" "~:")\n'
        noise = '("compiled-state" ' + 'x' * 100000 + ')\n'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'out.log'
            for bad in ['', '("TEST" garbage)\n',
                        '("ERROR"\n  ("nested" "failure"))\n',
                        'runtime: arena exhausted\n']:
                log = noise + record + bad + runner.DONE + '\n'
                path.write_text(log)
                compact = runner.report_log(path)
                self.assertLess(len(compact), 2000)
                self.assertEqual(runner.verdict(compact, 0),
                                 runner.verdict(log, 0))
            path.write_text('"FETCH-ORDER-read"\n"FETCH-ORDER-recv"\n')
            self.assertEqual(runner.report_log(path), path.read_text())

    def test_timeout_and_crash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            code, completed, _ = runner.run_process(
                [sys.executable, '-c', 'import time; time.sleep(10)'], path, '', .05)
            self.assertFalse(completed)
            self.assertNotEqual(code, 0)
            code, completed, _ = runner.run_process(
                [sys.executable, '-c', 'raise SystemExit(9)'], path, '', 5)
            self.assertTrue(completed)
            self.assertEqual(code, 9)

    def test_inventory_is_complete(self):
        suites = runner.inventory()
        names = [s['name'] for s in suites]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('foil:tests/json', names)
        self.assertIn('foil:apps/chat/tests', names)
        self.assertIn('foil:apps/loom/tests', names)
        self.assertIn('foil:apps/nenex/tests', names)
        self.assertIn('doc:sept', names)
        self.assertIn('foil:tests/supervisor', names)
        self.assertIn('foil:tests/http_foot', names)
        self.assertFalse(any(name.startswith('helm-') for name in names))

    def test_generated_helpers_are_covered_without_running_as_suites(self):
        suites = {s['name']: s for s in runner.inventory()}
        for helper in ('grove_backend', 'grove_install', 'eden_srs'):
            self.assertNotIn('foil:tests/' + helper, suites)
            self.assertIn('"tests/' + helper + '"',
                          '\n'.join((runner.ROOT / 'src/reaver' / (name + '.rvr')).read_text()
                                    for name in runner.reaver_closure(['foil-grove-tree-tests'])
                                    if (runner.ROOT / 'src/reaver' / (name + '.rvr')).exists()))
        self.assertTrue(suites['foil-grove-tree-tests']['enabled'])

    def test_migrated_pure_suites_are_native(self):
        suites = {s['name']: s for s in runner.inventory()}
        for name in ('web', 'pact', 'sept', 'semidoc', 'weft'):
            self.assertNotIn('foil-' + name + '-tests', suites)
            self.assertTrue(suites['foil:tests/' + name]['enabled'])
        self.assertTrue(suites['foil-sept-layout-tests']['enabled'])
        for name in ('semidoc', 'weft'):
            self.assertTrue(suites['foil-' + name + '-layout-tests']['enabled'])
        self.assertEqual(suites['foil-shrine-tests']['group'], 'shrine')
        self.assertTrue(all(not runner.needs_corpus(s['target'])
                            for s in suites.values() if s['group'] == 'corpus'))

    def test_app_migrations_and_semidoc_closure(self):
        suites = {s['name']: s for s in runner.inventory()}
        for name, target in [('life', 'apps/life/tests'),
                             ('loom', 'apps/loom/tests'),
                             ('tmpl', 'tests/tmpl')]:
            self.assertNotIn('foil-' + name + '-tests', suites)
            self.assertTrue(suites['foil:' + target]['enabled'])
        self.assertFalse(runner.needs_corpus('foil-semidoc-layout-tests'))

    def test_compiler_inputs_exclude_suites(self):
        files = {p.stem for p in runner.compiler_files()}
        self.assertIn('foil-new-elab', files)
        self.assertIn('foil-new-env', files)
        self.assertNotIn('foil', files)
        self.assertNotIn('schemagen', files)
        self.assertNotIn('foil-test-shrine', files)
        self.assertNotIn('foil-test-cache', files)
        self.assertNotIn('foil-new-elab-tests', files)
        self.assertNotIn('foil-schemagen-tests', files)
        suites = runner.inventory()
        staged = [s['name'] for s in suites if s['enabled']
                  and s['kind'] == 'reaver' and runner.needs_corpus(s['target'])]
        self.assertEqual(staged, [])
        compile_all = next(s for s in suites if s['name'] == 'foil-compile-all-tests')
        self.assertFalse(compile_all['enabled'])

    def test_vendor_census_is_opt_in(self):
        suites = runner.inventory()
        normal = {s['name'] for s in suites if s['enabled']}
        fast = {s['name'] for s in suites if s['enabled'] and s['fast']}
        census = next(s for s in suites if s['name'] == 'foil-schemagen-exhaustive-tests')
        self.assertEqual(census['group'], 'exhaustive')
        self.assertNotIn(census['name'], normal)
        self.assertNotIn(census['name'], fast)
        self.assertIn('foil-schemagen-tests', normal)
        self.assertIn('foil-schemagen-tests', fast)
        self.assertFalse(runner.needs_corpus(census['target']))


@unittest.skipUnless(os.environ.get('WISP') and os.environ.get('TEST_TEMPLATE'),
                     'set WISP and TEST_TEMPLATE for real-runtime probes')
class RuntimeTests(unittest.TestCase):
    def probe(self, root, source):
        code, complete, _ = runner.run_process(
            [os.environ['WISP'], '--file-root', str(root / 'src'),
             'snap', 'root', '_'], root, source + '\n(print "TEST-RUN-DONE")\n', 180)
        log = (root / 'out.log').read_text(errors='replace')
        self.assertTrue(runner.verdict(log, code, complete)[0], log[-6000:])

    def test_shared_fixture_runtime_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            modules = root / 'src/reaver'
            (modules / 'shared_probe.rvr').write_text(
                '(#bind std (#module std))\n(#import std)\n'
                '(define (create ignored) [17 99])\n(#export create)\n')
            suites = []
            for name, index, expected in [('probe_one', 0, 17), ('probe_two', 1, 99)]:
                (modules / (name + '.rvr')).write_text(
                    '(#bind std (#module std))\n(#import std)\n'
                    f'(define (check fixture) (std:Eq {expected} (std:Ix {index} fixture)))\n'
                    '(#export check)\n')
                suites.append(dict(name=name, target=name, kind='reaver', group='exec',
                                   entrypoint='check', fixture=['shared_probe', 'create']))
            result = runner.run_group(suites, os.environ['WISP'],
                                      Path(os.environ['TEST_TEMPLATE']), root, 180)
            self.assertTrue(result['passed'], (root / 'exec/out.log').read_text()[-6000:])
            # A failed entrypoint must not prevent later shared-fixture suites.
            (modules / 'probe_one.rvr').write_text(
                '(#bind std (#module std))\n(#import std)\n'
                '(define (check fixture) (std:error "fixture probe failure"))\n'
                '(#export check)\n')
            failed_root = root / 'failed'
            failed_root.mkdir()
            (failed_root / 'src').symlink_to(root / 'src')
            result = runner.run_group(suites, os.environ['WISP'],
                                      Path(os.environ['TEST_TEMPLATE']), failed_root, 180)
            self.assertFalse(result['passed'])
            self.assertTrue(any(r[:2] == ('error', 'probe_one') for r in result['records']))
            self.assertTrue(any(r[:2] == ('pass', 'probe_two') for r in result['records']))

    def test_workers_read_preserved_timestamp_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            dep = root / 'src/foil/cache_probe_dep.foil'
            dep.write_text('+ answer 1\n')
            seed = Path(os.environ['TEST_TEMPLATE'])
            for value in (1, 2):
                stamp = dep.stat()
                dep.write_text(f'+ answer {value}\n')
                os.utime(dep, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                work = root / str(value)
                work.mkdir()
                (work / 'src').symlink_to(root / 'src')
                runner.copy_template(seed, work / 'snap')
                self.probe(work, '\n'.join([
                    '(#bind source (#module foil-source))',
                    '(#bind fixture (#module foil-test-context))',
                    '(#bind driver (#module foil-new-env))',
                    '(define (check z)',
                    '  (define result (source:compile (fixture:files 0 ["cache_probe_dep"]) 0 "cache_probe_dep"))',
                    f'  assert(Eq {value} (driver:get-perc ["answer"] (_1 result)))',
                    '  1)', 'assert(check 0)']))
                self.assertFalse((work / 'prepare').exists())

    def test_content_changes_invalidate_only_dependent_cache_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            runner.copy_snapshot(Path(os.environ['TEST_TEMPLATE']), root / 'snap')
            self.probe(root, '''(#bind reef (#module reef))
(#import reef)
(#bind cc (#module foil-test-cache))
(#bind fixture (#module foil-test-context))
(#bind brand (#module shrine-brand))
(#bind driver (#module foil-new-env))
(#bind source (#module foil-source))
(#bind rex (#module rex))
(define (check z)
  (define (read version name)
    (rex:ParseRexNormFile
      (cond
        ((Equal name "dep") (strcat ["+ answer " (showNat version)]))
        ((Equal name "app") "- dep
+ observed answer")
        ((Equal name "other") "+ other 9")
        ((Equal name "generated") "- other
+ generated_value other")
        ((Equal name "alias") "- app")
        (else (error ["missing" name])))))
  (define (compile version cache mod)
    (driver:compile-with (fixture:graph (read version) cache [mod]) (read version) cache mod))
  (define first (compile 1 0 "alias"))
  (define all-cache (_0 (compile 1 (_0 first) "generated")))
  (define (find-entry cache name)
    (find (lambda (perc) (Equal name (driver:perc-name perc))) (driver:cache-results cache)))
  (define (entry cache name) (_0 (find-entry cache name)))
  (define other (entry all-cache "other"))
  assert(Equal ["alias" "app" "dep"] (cc:closure all-cache "alias"))
  assert(Equal ["generated" "other"] (cc:closure all-cache "generated"))
  (define kept (cc:refresh all-cache ["dep"]))
  assert(Eq 2 (Sz (driver:cache-results kept)))
  assert(Equal other (entry kept "other"))
  assert(Equal 0 (find-entry kept "alias"))
  (define rebuilt (compile 2 kept "alias"))
  assert(Eq 2 (driver:get-perc ["observed"] (_1 rebuilt)))
  assert(Equal other (entry (_0 rebuilt) "other"))
  (define importer-edit (cc:refresh (_0 rebuilt) ["app"]))
  assert(Equal (entry (_0 rebuilt) "dep") (entry importer-edit "dep"))
  assert(Equal 0 (find-entry importer-edit "alias"))
  (define generated-edit (cc:refresh all-cache ["other"]))
  assert(Eq 3 (Sz (driver:cache-results generated-edit)))
  assert(Equal 0 (find-entry generated-edit "generated"))
  ;; A failed recompile cannot mutate the retained unrelated modules.
  (define failure (Try (lambda (z)
    (force (driver:compile-with (fixture:graph (read 1) kept ["app"])
      (lambda (name) (error name)) kept "app"))) 0))
  assert(Eq 1 (Hd failure))
  assert(Equal other (entry kept "other"))
  ;; App paths are generated word leaves; their nominal identity survives aliases.
  (define (app-read name) (If (Equal name "app_alias")
      (source:import-tree "apps/probe/main")
      (rex:ParseRexNormFile "+ token\n  : value=nat\n+ value | token 7")))
  (define app-result (driver:compile-with (fixture:graph app-read 0 ["app_alias"]) app-read 0 "app_alias"))
  assert(Equal ["apps/probe/main"] (driver:perc-dependencies (_1 app-result)))
  assert(Equal (brand:encode (Weld (fixture:root "apps/probe/main") [["ts" "token"]]) 1)
    (Hd (driver:get-perc ["value"] (_1 app-result))))
  assert(Equal (driver:get-perc ["value"] (entry (_0 app-result) "apps/probe/main"))
    (driver:get-perc ["value"] (_1 app-result)))
  1)
assert(check 0)
''')

    def test_native_and_doctest_failures_reach_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            (root / 'src/foil/test_probe.foil').write_text(r'''-  testing
+  identity
  '  ?=  ((identity 1) 1)
  '  ?=  ((identity 1) 2)
  '  ?=  malformed
  \ arg=nat
  ^ nat
  arg
+  mismatches
  \ _=unit
  ^ row[testing/check]
  [(testing/text "bad" "want" "got")
   (testing/nat "later" 1 1)]
+  empty_case
  \ _=unit
  ^ row[testing/check]
  []
+  tests
  ^ row[testing/case]
  [(testing/case "mixed" mismatches)
   (testing/case "empty" empty_case)]
''')
            runner.copy_snapshot(Path(os.environ['TEST_TEMPLATE']), root / 'snap')
            (root / 'src/foil/test_bad.foil').write_text('+ tests missing_test_value\n')
            source = ('(#bind runner (#module foil-test-runner))\n'
                      '(runner:run 0 "native" ["test_bad" "test_probe"])\n'
                      '(runner:run 0 "docs" ["test_probe"])\n'
                      '(print "TEST-RUN-DONE")\n')
            code, complete, _ = runner.run_process(
                [os.environ['WISP'], '--file-root', str(root / 'src'), 'snap', 'root', '_'],
                root, source, 180)
            log = (root / 'out.log').read_text(errors='replace')
            self.assertEqual(code, 0, log[-2000:])
            self.assertTrue(complete)
            good, records = runner.verdict(log, code, complete)
            self.assertFalse(good)
            results = [r for r in records if r[0] != 'start']
            self.assertEqual([r[0] for r in results],
                             ['error', 'fail', 'pass', 'fail', 'pass', 'fail', 'broken'], log[-4000:])
            self.assertEqual(results[1][3:], ('want', 'got'))
            self.assertEqual(results[5][3:], ('2', '1'))


class NamespaceIdentityTests(unittest.TestCase):
    def test_identity_uses_shrine_byte_order(self):
        from namespace_identity import parse_node_identity
        for spelling, number in [("0x01", 1), ("0x11", 17), ("0x0102", 513), ("0x0001", 256)]:
            self.assertEqual((number, spelling), parse_node_identity(spelling))

    def test_identity_rejects_noncanonical_and_zero_spellings(self):
        from namespace_identity import parse_node_identity
        for spelling in ["0x", "0x1", "11", "0xFF", "0x1100", "0x00", "-0x01"]:
            with self.subTest(spelling=spelling), self.assertRaises(ValueError):
                parse_node_identity(spelling)


if __name__ == '__main__':
    unittest.main()
