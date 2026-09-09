"""Failure-path tests for the gate; run with python3 x/test_runner_tests.py."""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import json
from pathlib import Path
import sys

import test_runner as runner


class ProtocolTests(unittest.TestCase):
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
        step = next(s for s in suites if s['name'] == 'helm-repl-step-tests')
        self.assertTrue(step['enabled'])
        self.assertFalse(runner.needs_corpus('helm-repl-step-tests'))
        self.assertFalse(runner.needs_corpus('helm-repl-tests'))

    def test_migrated_pure_suites_are_native(self):
        suites = {s['name']: s for s in runner.inventory()}
        for name in ('web', 'pact', 'sept', 'semidoc', 'weft'):
            self.assertNotIn('foil-' + name + '-tests', suites)
            self.assertTrue(suites['foil:tests/' + name]['enabled'])
        self.assertTrue(suites['foil-sept-layout-tests']['enabled'])
        for name in ('semidoc', 'weft'):
            self.assertTrue(suites['foil-' + name + '-layout-tests']['enabled'])
        self.assertEqual(suites['foil-shrine-tests']['group'], 'shrine')
        self.assertFalse(runner.input_fixtures(
            [s for s in suites.values() if s['group'] == 'corpus']))

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
        self.assertIn('schemagen', files)
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
    def test_preparation_keeps_completed_inputs_after_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            (root / 'x').mkdir()
            shutil.copy2(runner.ROOT / 'x/stage-lib', root / 'x/stage-lib')
            (root / '.check').mkdir()
            seed = root / 'seed'
            runner.copy_snapshot(Path(os.environ['TEST_TEMPLATE']), seed)
            first = root / 'src/foil/cache_checkpoint_first.foil'
            second = root / 'src/foil/cache_checkpoint_second.foil'
            first.write_text('+ answer 1\n')
            second.write_text('+ answer missing_checkpoint_value\n')
            suites = [dict(kind='native', target=p.stem) for p in (first, second)]
            with patch.object(runner, 'ROOT', root):
                with self.assertRaisesRegex(RuntimeError, 'cache_checkpoint_second'):
                    runner.prepare_inputs(os.environ['WISP'], seed, suites,
                                          root / 'failed', False, 180)
                second.write_text('+ answer 2\n')
                prepared = runner.prepare_inputs(os.environ['WISP'], seed, suites,
                                                 root / 'retry', False, 180)
                self.assertFalse((root / 'retry/prepare/steps/1').exists())
                self.assertTrue((root / 'retry/prepare/steps/2/out.log').exists())
                work = root / 'check'
                runner.copy_snapshot(prepared, work / 'snap')
                source = '''(#bind foil (#module foil))
(#bind reef (#module reef))
(#import reef)
(define (answer name)
  (foil:source-entry-val ["answer"]
    (_1 (_0 (find (lambda (e) (Equal name (_0 e))) test-cache)))))
assert(Eq 1 (answer "cache_checkpoint_first"))
assert(Eq 2 (answer "cache_checkpoint_second"))
(print "TEST-RUN-DONE")
'''
                code, complete, _ = runner.run_process(
                    [os.environ['WISP'], '--file-root', str(root / 'src'),
                     'snap', 'root', '_'], work, source, 180)
                log = (work / 'out.log').read_text(errors='replace')
                self.assertTrue(runner.verdict(log, code, complete)[0], log[-4000:])

    def test_fixture_snapshot_detects_preserved_timestamp_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            (root / 'x').mkdir()
            shutil.copy2(runner.ROOT / 'x/stage-lib', root / 'x/stage-lib')
            (root / '.check').mkdir()
            (root / '.check/stage.lock').touch()
            dep = root / 'src/foil/cache_probe_dep.foil'
            dep.write_text('+ answer 1\n')
            (root / 'src/reaver/foil-test-shrine.rvr').write_text('''(#bind std (#module std))
(#import std)
(#bind foil (#module foil))
(Seq (define compiled (foil:compile-mod-cached 0
  foil:default-subject "cache_probe_dep")) (DeepSeq compiled 0))
(define module-file-stamps ["foil/cache_probe_dep.foil"])
''')
            seed = root / 'seed'
            runner.copy_snapshot(Path(os.environ['TEST_TEMPLATE']), seed)
            suites = [dict(kind='reaver', target='foil-shrine-tests')]
            with patch.object(runner, 'ROOT', root):
                for value in (1, 2):
                    stamp = dep.stat()
                    dep.write_text(f'+ answer {value}\n')
                    os.utime(dep, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                    prepared = runner.prepare_inputs(
                        os.environ['WISP'], seed,
                        suites, root / str(value), False, 180)
                    self.assertEqual(json.loads((prepared / 'fixtures.json').read_text()),
                                     ['cache_probe_dep'])
                    work = root / ('check-' + str(value))
                    runner.copy_snapshot(prepared, work / 'snap')
                    source = ('assert(Eq ' + str(value) +
                              ' (foil:source-entry-val ["answer"] '
                              '(_1 foil-test-shrine:compiled)))\n'
                              '(print "TEST-RUN-DONE")\n')
                    code, complete, _ = runner.run_process(
                        [os.environ['WISP'], '--file-root', str(root / 'src'),
                         'snap', 'root', '_'], work, source, 180)
                    log = (work / 'out.log').read_text(errors='replace')
                    self.assertTrue(runner.verdict(log, code, complete)[0], log[-4000:])

    def test_content_changes_invalidate_only_dependent_cache_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(runner.ROOT / 'src', root / 'src')
            foil = root / 'src/foil'
            dep = foil / 'cache_probe_dep.foil'
            dep.write_text('+ answer 1\n')
            (foil / 'cache_probe_app.foil').write_text(
                '- cache_probe_dep\n+ observed answer\n')
            (foil / 'cache_probe_other.foil').write_text('+ other 9\n')
            runner.copy_snapshot(Path(os.environ['TEST_TEMPLATE']), root / 'snap')

            def run(source):
                code, complete, _ = runner.run_process(
                    [os.environ['WISP'], '--file-root', str(root / 'src'),
                     'snap', 'root', '_'], root,
                    source + '\n(print "TEST-RUN-DONE")\n', 180)
                log = (root / 'out.log').read_text(errors='replace')
                self.assertTrue(runner.verdict(log, code, complete)[0], log[-4000:])

            run('''(#bind reef (#module reef))
(#import reef)
(#bind cc (#module foil-test-cache))
(#bind foil (#module foil))
(Seq (define saved (cc:prepare 0 []
  ["cache_probe_app" "cache_probe_other"])) (DeepSeq saved 0))
(define (entry cache name)
  (_0 (find (lambda (e) (Equal name (_0 e))) cache)))
(define other (entry saved "cache_probe_other"))
assert(Eq 6 (Sz (entry saved "cache_probe_dep")))
assert(Eq 5 (Sz other))
(define (without-unused-pack marker)
  (cc:durable [(Weld other [(error marker)])]))
assert(Equal [other] (without-unused-pack "unused import pack forced"))
assert(Eq 1 (foil:source-entry-val ["observed"]
  (_1 (entry saved "cache_probe_app"))))
''')
            stamp = dep.stat()
            dep.write_text('+ answer 2\n')
            os.utime(dep, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            run('''(Seq (define kept (cc:refresh saved ["cache_probe_dep"]))
  (DeepSeq kept 0))
assert(Equal [other] kept)
(Seq (define saved (cc:prepare kept [] ["cache_probe_app"]))
  (DeepSeq saved 0))
assert(Eq 2 (foil:source-entry-val ["observed"]
  (_1 (entry saved "cache_probe_app"))))
assert(Equal other (entry saved "cache_probe_other"))
''')
            # Editing only the importer preserves its compiled dependency.
            app = foil / 'cache_probe_app.foil'
            app.write_text('- cache_probe_dep\n+ observed (add answer 3)\n')
            run('''(define dependency (entry saved "cache_probe_dep"))
(Seq (define kept (cc:refresh saved ["cache_probe_app"]))
  (DeepSeq kept 0))
assert(Eq 2 (Sz kept))
(Seq (define saved (cc:prepare kept [] ["cache_probe_app"]))
  (DeepSeq saved 0))
assert(Eq 5 (foil:source-entry-val ["observed"]
  (_1 (entry saved "cache_probe_app"))))
assert(Equal dependency (entry saved "cache_probe_dep"))
''')
            # A tree-fed module and an alias still carry their real imports.
            run('''(#bind rex (#module rex))
(define tree (rex:ParseRexNormFile
  "- cache_probe_other\n+ generated_value other\n"))
(Seq (define generated (foil:compile-rex-cached saved
  foil:default-subject "generated_probe" tree)) (DeepSeq generated 0))
(define app-entry (entry saved "cache_probe_app"))
(define alias (foil:cache-entry "alias_probe" (_1 app-entry)
  (Ix 3 app-entry) (Ix 4 app-entry)))
(define all-cache (snoc alias (_0 generated)))
assert(Equal ["alias_probe" "cache_probe_app" "cache_probe_dep"]
  (cc:closure all-cache "alias_probe"))
(define kept (cc:refresh all-cache ["cache_probe_other"]))
assert(Eq 3 (Sz kept))
assert(Equal alias (entry kept "alias_probe"))
assert(Equal [] (filter (lambda (e) (Equal "generated_probe" (_0 e))) kept))
assert(Eq 3 (Sz (cc:refresh all-cache ["cache_probe_app"])))
''')
            dep.unlink()
            run('''(define kept (cc:refresh saved ["cache_probe_dep"]))
assert(Equal [other] kept)
(define failure (Try (lambda (z)
  (DeepSeq (cc:prepare kept [] ["cache_probe_app"]) 0)) 0))
assert(Eq 1 (Hd failure))
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
            source = ('(#bind runner (#module foil-test-runner))\n'
                      '(runner:run 0 "native" ["test_probe"])\n'
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
                             ['fail', 'pass', 'fail', 'pass', 'fail', 'broken'], log[-4000:])
            self.assertEqual(results[0][3:], ('want', 'got'))
            self.assertEqual(results[4][3:], ('2', '1'))


if __name__ == '__main__':
    unittest.main()
