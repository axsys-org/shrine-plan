"""Mount selection and launcher contracts, without Nix or a runtime."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from eden_mounts import catalog, select, runtime_specs, ScanBridge, prepare, runtime_literal
from eden_runtime import startup_ready, startup_failed


class MountTests(unittest.TestCase):
    def test_ready_waits_for_activation_and_reports_failure(self):
        listening = '"HTTP foot listening"\n'
        self.assertFalse(startup_ready(listening, 'DONE'))
        success = '("DONE" (0 17))\n'
        self.assertFalse(startup_ready(success, 'DONE'))
        self.assertTrue(startup_ready(listening + success, 'DONE'))
        failure = listening + '("DONE" (1 "activation failed"))\n'
        self.assertFalse(startup_ready(failure, 'DONE'))
        self.assertTrue(startup_failed(failure, 'DONE'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bag(self, name, **options):
        folder = self.root / 'mounts' / name
        folder.mkdir(parents=True)
        data = dict(version=1, name=name, modules={}, dependencies=[])
        data.update(options)
        (folder / 'mount.json').write_text(json.dumps(data))
        return folder

    def test_dependency_order_and_deduplication(self):
        self.bag('shared')
        self.bag('left', dependencies=['shared'])
        self.bag('right', dependencies=['shared'])
        self.assertEqual([m.name for m in select(self.root, ['right', 'left', 'right'])],
                         ['shared', 'right', 'left'])
        self.assertEqual(select(self.root, []), [])

    @unittest.skipUnless(os.environ.get('WISP'), 'Native descriptor check requires WISP')
    def test_descriptor_bytes_and_entrypoint_positions(self):
        import test_runner as runner
        bag = self.bag('example', modules={'example': 'main.foil'},
                       http={'module': 'example', 'entry': ['example', 'http']},
                       description='quotes " and slash \\ and café' * 400)
        source = self.root / 'src'
        shutil.copytree(runner.ROOT / 'src', source)
        specs = runtime_specs([(select(self.root, ['example'])[0], bag, [], None)], source)
        (source / 'expected.json').write_text(specs[0][2])
        work = self.root / 'worker'
        template = Path(os.environ['TEST_TEMPLATE']) if os.environ.get('TEST_TEMPLATE') else runner.stage(os.environ['WISP'], False, 60)
        runner.copy_template(template, work / 'snap')
        script = '\n'.join([
            '(#bind std (#module std))', '(#import std)',
            '(#bind reef (#module reef))',
            '(define spec (_0 ' + runtime_literal(specs) + '))',
            '(define good (And (Eq (Sz spec) 13) (And (Eq (_2 spec) (reef:read-text-file "expected.json")) (Equal (_6 spec) ["example" ["example" "http"]]))))',
            '(print (If good "MOUNT-ENCODING-PASS" "MOUNT-ENCODING-FAIL"))',
            '(print "TEST-RUN-DONE")', ''])
        code, complete, _ = runner.run_process([os.environ['WISP'], '--file-root', str(source), 'snap', 'root', '_'], work, script, 60)
        log = (work / 'out.log').read_text()
        self.assertEqual(code, 0, log)
        self.assertTrue(complete, log)
        self.assertIn('"MOUNT-ENCODING-PASS"', log)
        self.assertNotIn('"MOUNT-ENCODING-FAIL"', log)

    def test_unknown_and_cycles(self):
        self.bag('a', dependencies=['b'])
        self.bag('b', dependencies=['a'])
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            select(self.root, ['missing'])
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            select(self.root, ['a'])

    def test_conflicting_ownership_and_routes(self):
        self.bag('a', modules={'common': 'a.foil'})
        self.bag('b', modules={'common': 'b.foil'})
        with self.assertRaisesRegex(ValueError, 'owned by both'):
            select(self.root, ['a', 'b'])
        self.bag('c', grove=[dict(root=['gov','example'], files=['one.grove'])])
        self.bag('d', grove=[dict(root=['gov','example','child'], files=['two.grove'])])
        with self.assertRaisesRegex(ValueError, 'Conflicting publication'):
            select(self.root, ['c','d'])
        self.bag('e', routes=['/ns'])
        self.bag('f', routes=['/ns'])
        with self.assertRaisesRegex(ValueError, 'Duplicate HTTP'):
            select(self.root, ['e','f'])

    def test_flat_file_validation(self):
        self.bag('bad', modules={'main': '../main.foil'})
        with self.assertRaisesRegex(ValueError, 'must be flat'):
            catalog(self.root)

    def test_live_scan_and_logical_module_names(self):
        bag = self.bag('app', modules={'apps/app/main': 'main.foil'})
        source = bag / 'main.foil'
        source.write_text('+ value 1\n')
        mount = select(self.root, ['app'])[0]
        root = self.root / 'runtime'
        root.mkdir()
        specs = runtime_specs([(mount, bag, [], None)], root)
        self.assertEqual(specs[0][3], [('apps/app/main', 'main.foil')])
        self.assertFalse((root/'foil').exists())
        scanner = ScanBridge.__new__(ScanBridge)
        scanner.roots = {'mounts/app': bag}
        scanner.destination = root
        scanner.refresh('mounts/app')
        source.write_text('+ value 2\n')
        scanner.refresh('mounts/app')
        self.assertEqual((root/'mounts/app/main.foil').read_text(), '+ value 2\n')
        source.unlink()
        scanner.refresh('mounts/app')
        self.assertFalse((root/'mounts/app/main.foil').exists())
        (bag/'mount.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing mount descriptor'):
            scanner.refresh('mounts/app')
        self.assertTrue((root/'mounts/app/mount.json').exists())

    def test_host_cleanup_after_startup_preparation_failure(self):
        first = self.bag('first', host='host.py')
        (first / 'host.py').write_text("def prepare(root, work, check, cleanup, context):\n"
            "    marker = root / 'companion-alive'\n"
            "    marker.write_text('started')\n"
            "    cleanup.callback(marker.unlink)\n"
            "    return root, []\n")
        self.bag('broken', dependencies=['first'], modules={'absent': 'missing.foil'})
        with self.assertRaisesRegex(ValueError, 'missing module source'):
            with ExitStack() as cleanup:
                prepare(select(self.root, ['broken']), self.root / 'work', True, cleanup, {})
        self.assertFalse((first / 'companion-alive').exists())

    def test_core_modules_cannot_be_overridden(self):
        self.bag('shadow', modules={'eden': 'eden.foil'})
        with self.assertRaisesRegex(ValueError, 'belongs to core'):
            select(self.root, ['shadow'])

    def test_help_lists_generic_flags_only(self):
        launcher = Path(__file__).with_name('eden')
        result = subprocess.run([sys.executable, str(launcher), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        for flag in ('--mount', '--extras-root', '--list-mounts'):
            self.assertIn(flag, result.stdout)
        for flag in ('--debug', '--srs', '--codex', '--mash-root'):
            self.assertNotIn(flag, result.stdout)
        result = subprocess.run([sys.executable, str(launcher), '--srs'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
