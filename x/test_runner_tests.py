"""Failure-path tests for the gate; run with python3 x/test_runner_tests.py."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

import test_runner as runner


class ProtocolTests(unittest.TestCase):
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

    def test_native_helpers_are_not_mistaken_for_suites(self):
        suites = {s['name']: s for s in runner.inventory()}
        for name in ('eden_srs', 'grove_backend', 'grove_debugger', 'grove_install', 'value_http'):
            self.assertFalse(suites['foil:tests/' + name]['enabled'])
            self.assertTrue(suites['foil:tests/' + name]['reason'])

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
                    '(#bind driver (#module foil-new-env))',
                    '(define (check z)',
                    '  (define result (source:compile 0 "cache_probe_dep"))',
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
  (define (compile version cache mod) (driver:compile-with (read version) cache mod))
  (define first (compile 1 0 "alias"))
  (define all-cache (_0 (compile 1 (_0 first) "generated")))
  (define (entry cache name) (_0 (driver:get-foil-cache name cache)))
  (define other (entry all-cache "other"))
  assert(Equal ["alias" "app" "dep"] (cc:closure all-cache "alias"))
  assert(Equal ["generated" "other"] (cc:closure all-cache "generated"))
  (define kept (cc:refresh all-cache ["dep"]))
  assert(Eq 2 (Sz (driver:cache-results kept)))
  assert(Equal other (entry kept "other"))
  assert(Equal 0 (driver:get-foil-cache "alias" kept))
  (define rebuilt (compile 2 kept "alias"))
  assert(Eq 2 (driver:get-perc ["observed"] (_1 rebuilt)))
  assert(Equal other (entry (_0 rebuilt) "other"))
  (define importer-edit (cc:refresh (_0 rebuilt) ["app"]))
  assert(Equal (entry (_0 rebuilt) "dep") (entry importer-edit "dep"))
  assert(Equal 0 (driver:get-foil-cache "alias" importer-edit))
  (define generated-edit (cc:refresh all-cache ["other"]))
  assert(Eq 3 (Sz (driver:cache-results generated-edit)))
  assert(Equal 0 (driver:get-foil-cache "generated" generated-edit))
  ;; A failed recompile cannot mutate the retained unrelated modules.
  (define failure (Try (lambda (z)
    (force (driver:compile-with (lambda (name) (error name)) kept "app"))) 0))
  assert(Eq 1 (Hd failure))
  assert(Equal other (entry kept "other"))
  ;; App paths are generated word leaves; their nominal identity survives aliases.
  (define app-result (driver:compile-with
    (lambda (name) (If (Equal name "app_alias")
      (source:import-tree "apps/probe/main")
      (rex:ParseRexNormFile "+ token\n  : value=nat\n+ value | token 7"))) 0 "app_alias"))
  assert(Equal ["apps/probe/main"] (driver:perc-dependencies (_1 app-result)))
  assert(Equal "/boot/apps/probe/main/token"
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


if __name__ == '__main__':
    unittest.main()
