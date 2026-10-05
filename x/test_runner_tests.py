"""Failure-path tests for the gate; run with python3 x/test_runner_tests.py."""
import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

import test_runner as runner


class ProtocolTests(unittest.TestCase):
    def test_compact_sources_round_trip_exact_inputs_and_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            root = cache / 'run-finished'
            source = root / 'src'
            (source / 'empty').mkdir(parents=True)
            code = source / 'fixture.foil'
            code.write_bytes(b'actual native source\n' * 100)
            code.chmod(0o755)
            os.utime(code, ns=(1700000000123456789, 1700000000123456789))
            (root / 'results.json').write_text('[{"passed": true}]')
            (root / 'out.log').write_text('kept execution evidence')
            (root / 'snap').mkdir()
            (root / 'snap/pins.pack').write_bytes(b'never a cleanup target')
            before = runner.source_inventory(source)
            runner.compact_test_sources(root, cache)
            self.assertFalse(source.exists())
            self.assertTrue((root / 'source.tar.gz').exists())
            self.assertEqual((root / 'out.log').read_text(), 'kept execution evidence')
            self.assertEqual((root / 'snap/pins.pack').read_bytes(), b'never a cleanup target')
            with patch.object(runner, 'require_disk_space'):
                runner.restore_test_sources(root, cache)
            self.assertEqual(runner.source_inventory(source), before)
            runner.compact_test_sources(root, cache)
            self.assertFalse(source.exists())

    def test_compaction_refuses_incomplete_linked_and_durable_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            root = cache / 'run-pending'
            (root / 'src').mkdir(parents=True)
            (root / 'src/file').write_text('preserve')
            with self.assertRaisesRegex(ValueError, 'completed'):
                runner.compact_test_sources(root, cache)
            (root / 'results.json').write_text('[{"passed": true}]')
            (root / 'world.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'completed'):
                runner.compact_test_sources(root, cache)
            (root / 'world.json').unlink()
            (root / 'src/link').symlink_to(root / 'src/file')
            with self.assertRaisesRegex(ValueError, 'Linked'):
                runner.compact_test_sources(root, cache)
            self.assertEqual((root / 'src/file').read_text(), 'preserve')

    def test_failed_archive_verification_never_removes_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            root = cache / 'run-finished'
            (root / 'src').mkdir(parents=True)
            (root / 'src/file').write_text('preserve')
            (root / 'results.json').write_text('[{"passed": false}]')
            with patch.object(runner, 'verify_source_archive', side_effect=ValueError('corrupt')):
                with self.assertRaisesRegex(ValueError, 'corrupt'):
                    runner.compact_test_sources(root, cache)
            self.assertEqual((root / 'src/file').read_text(), 'preserve')
            self.assertFalse((root / 'source.tar.gz.tmp').exists())

    def test_restore_rejects_tampered_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            root = cache / 'run-finished'
            (root / 'src').mkdir(parents=True)
            (root / 'src/file').write_text('preserve')
            (root / 'results.json').write_text('[{"passed": true}]')
            runner.compact_test_sources(root, cache)
            with (root / 'source.tar.gz').open('ab') as output:
                output.write(b'tampered')
            with self.assertRaisesRegex(ValueError, 'digest'):
                runner.restore_test_sources(root, cache)
            self.assertFalse((root / 'src').exists())

    def failed_run(self, cache, name, timestamp, *, keep=False):
        root = cache / name
        group = root / 'native'
        (group / 'snap').mkdir(parents=True)
        (group / 'snap/pins.pack').write_bytes(b'disposable frozen test store')
        (root / 'src').mkdir()
        (root / 'src/fixture.foil').write_text('exact reproduction input')
        (root / 'results.json').write_text('[{"passed": false}]')
        (group / 'result.json').write_text(json.dumps(dict(passed=False, keep_snapshot=keep)))
        os.utime(group / 'result.json', ns=(timestamp, timestamp))
        (group / 'out.log').write_text('actual failed execution evidence')
        (group / 'input').write_text('actual native command')
        return group

    def test_retention_rotates_without_prompt_or_false_diagnosis(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            oldest = self.failed_run(cache, 'run-z-old', 1000000000)
            newest = self.failed_run(cache, 'run-a-new', 2000000000)
            runner.compact_test_sources(oldest.parent, cache)
            root = cache / 'run-next'
            root.mkdir()
            with patch.object(runner, 'run_group_owned') as execute:
                runner.run_group([], 'engine', cache, root, 1)
                execute.assert_called_once()
            self.assertEqual(len(runner.unresolved_stores(cache)), 1)
            self.assertFalse((oldest / 'snap').exists())
            self.assertTrue((newest / 'snap').exists())
            self.assertEqual((oldest / 'out.log').read_text(), 'actual failed execution evidence')
            self.assertEqual((oldest / 'input').read_text(), 'actual native command')
            self.assertTrue((oldest.parent / 'source.tar.gz').is_file())
            receipt = json.loads((oldest / 'retention.json').read_text())
            self.assertFalse(receipt['diagnosed'])
            self.assertEqual(receipt['discarded'], 'snap')

    def test_retention_does_not_remove_unfinished_held_or_durable_stores(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            held = self.failed_run(cache, 'run-held', 1, keep=True)
            incomplete = self.failed_run(cache, 'run-incomplete', 2)
            (incomplete / 'result.json').unlink()
            durable = self.failed_run(cache, 'run-durable', 3)
            (durable.parent / 'world.json').write_text('{}')
            reproducible = self.failed_run(cache, 'run-disposable', 4)
            self.assertEqual(runner.rotate_failure_stores(cache, limit=0), [reproducible.resolve()])
            for group in (held, incomplete, durable):
                self.assertTrue((group / 'snap').is_dir())

    def test_retention_requires_verified_source_reproduction(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            group = self.failed_run(cache, 'run-failed', 1)
            runner.compact_test_sources(group.parent, cache)
            with (group.parent / 'source.tar.gz').open('ab') as archive:
                archive.write(b'tampered')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                runner.rotate_failure_stores(cache, limit=0)
            self.assertTrue((group / 'snap').exists())
            self.assertFalse((group / 'retention.json').exists())

    def test_diagnosis_cannot_delete_durable_or_linked_stores(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            group = cache / 'run-one/native'
            (group / 'snap').mkdir(parents=True)
            (group / 'result.json').write_text('{"passed": false}')
            (group / 'world.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'durable world'):
                runner.diagnose_store(group, 'diagnosed', cache)
            (group / 'world.json').unlink()
            link = cache / 'run-one/linked'
            link.symlink_to(group, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'unlinked'):
                runner.diagnose_store(link, 'diagnosed', cache)
            self.assertTrue((group / 'snap').is_dir())

    def test_check_root_is_local_or_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn('/.local/share/shrine/checks/', str(runner.check_root()))
        with patch.dict(os.environ, {'SHRINE_CHECK_ROOT': '/tmp/explicit-shrine-tests'}):
            self.assertEqual(runner.check_root(), Path('/tmp/explicit-shrine-tests').resolve())

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

    def test_external_template_uses_its_own_publication_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / 'template-external'
            template.mkdir()
            (root / 'stage.lock').touch()
            for name in ('data.mdb', 'pins.pack'):
                (template / name).write_bytes(b'compiler-only-fixture')
            runner.copy_template(template, root / 'copy')
            self.assertEqual((root / 'copy/data.mdb').read_bytes(), b'compiler-only-fixture')

    def test_private_engine_copies_share_cache_but_content_edits_do_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / 'engine', root / 'private-engine'
            first.write_bytes(b'engine version 1')
            shutil.copyfile(first, second)
            self.assertEqual(runner.compiler_key(first), runner.compiler_key(second))
            stamp = second.stat()
            second.write_bytes(b'engine version 2')
            os.utime(second, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertNotEqual(runner.compiler_key(first), runner.compiler_key(second))

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

    def test_low_space_stops_child_and_cannot_pass(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            with patch.object(runner, 'check_world_storage', side_effect=RuntimeError('disk reserve reached')):
                code, complete, seconds = runner.run_process(
                    [sys.executable, '-c', 'import time; time.sleep(10)'], path, '', 5)
            self.assertFalse(complete)
            self.assertNotEqual(code, 0)
            self.assertLess(seconds, 2)
            self.assertIn('disk reserve reached', (path / 'out.log').read_text())

    def test_memory_growth_stops_child_and_preserves_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'snap').mkdir()
            pins = path / 'snap/pins.pack'
            pins.write_bytes(b'committed native state')
            code, complete, seconds = runner.run_process(
                [sys.executable, '-c',
                 'import time; data=bytearray(48*1024**2); time.sleep(10)'],
                path, '', 5, memory_bytes=32 * 1024**2)
            self.assertFalse(complete)
            self.assertNotEqual(code, 0)
            self.assertLess(seconds, 3)
            self.assertIn('Owned process memory exceeds', (path / 'out.log').read_text())
            report = json.loads((path / 'memory.json').read_text())
            self.assertGreater(report['sampled_peak_bytes'], report['limit_bytes'])
            self.assertEqual(pins.read_bytes(), b'committed native state')

    def test_retention_only_removes_disposable_store(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'snap').mkdir()
            (path / 'snap/pins.pack').write_bytes(b'copied test pins')
            (path / 'out.log').write_text('test evidence')
            (path / 'world.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'durable world'):
                runner.discard_test_snapshot(path)
            self.assertTrue((path / 'snap/pins.pack').exists())
            (path / 'world.json').unlink()
            runner.discard_test_snapshot(path)
            self.assertFalse((path / 'snap').exists())
            self.assertEqual((path / 'out.log').read_text(), 'test evidence')

    def test_inventory_is_complete(self):
        suites = runner.inventory()
        names = [s['name'] for s in suites]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('foil:tests/json', names)
        self.assertNotIn('foil:apps/chat/tests', names)
        self.assertNotIn('foil:apps/loom/tests', names)
        self.assertNotIn('foil:apps/nenex/tests', names)
        self.assertIn('doc:sept', names)
        self.assertIn('foil:tests/supervisor', names)
        self.assertIn('foil:tests/http_foot', names)
        self.assertFalse(any(name.startswith('helm-') for name in names))

    def test_generated_helpers_are_covered_without_running_as_suites(self):
        suites = {s['name']: s for s in runner.inventory()}
        for helper in ('grove_backend', 'grove_install', 'grove_publication'):
            self.assertNotIn('foil:tests/' + helper, suites)
            self.assertIn('"tests/' + helper + '"',
                          '\n'.join((runner.ROOT / 'src/reaver' / (name + '.rvr')).read_text()
                                    for name in runner.reaver_closure(['foil-grove-tree-tests'])
                                    if (runner.ROOT / 'src/reaver' / (name + '.rvr')).exists()))
        self.assertTrue(suites['foil-grove-tree-tests']['enabled'])
        for name in ('backend', 'action', 'norm', 'role', 'sewn', 'tree'):
            suite = suites['foil-grove-' + name + '-tests']
            self.assertEqual(suite['entrypoint'], 'run' if name == 'backend' else 'check')
            self.assertEqual(suite['fixture'], ['foil-grove-fixture', 'create'])

    def test_migrated_pure_suites_are_native(self):
        suites = {s['name']: s for s in runner.inventory()}
        for name in ('pact', 'sept', 'semidoc', 'weft'):
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
            self.assertNotIn('foil:' + target, suites)
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
