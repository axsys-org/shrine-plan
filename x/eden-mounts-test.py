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
import time
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
            '(define good (And (Eq (Sz spec) 14) (And (Eq (_2 spec) (reef:read-text-file "expected.json")) (Equal (_6 spec) ["example" ["example" "http"]]))))',
            '(print (If good "MOUNT-ENCODING-PASS" "MOUNT-ENCODING-FAIL"))',
            '(print "TEST-RUN-DONE")', ''])
        code, complete, _ = runner.run_process([os.environ['WISP'], '--file-root', str(source), 'snap', 'root', '_'], work, script, 60)
        log = (work / 'out.log').read_text()
        self.assertEqual(code, 0, log)
        self.assertTrue(complete, log)
        self.assertIn('"MOUNT-ENCODING-PASS"', log)
        self.assertNotIn('"MOUNT-ENCODING-FAIL"', log)

    def test_hands_named_in_the_descriptor_start_and_stop(self):
        import eden_hands
        from contextlib import ExitStack
        self.assertEqual(eden_hands.parse_hand('clock --timezone UTC'), {'name': 'clock', 'args': ['--timezone', 'UTC']})
        with self.assertRaisesRegex(ValueError, 'hand name'):
            eden_hands.parse_hand('')
        hands_dir = self.root / 'hands'
        hands_dir.mkdir()
        (hands_dir / 'sleepy.py').write_text('import sys, time\nprint("hand", sys.argv[1:], flush=True)\ntime.sleep(60)\n')
        with self.assertRaisesRegex(ValueError, 'no hand called'):
            eden_hands.hand_commands([{'name': 'nope', 'args': []}], 'http://x', '0x11', hands_dir)
        commands = eden_hands.hand_commands([{'name': 'sleepy', 'args': ['--a', '1']}], 'http://127.0.0.1:1', '0x11', hands_dir)
        self.assertEqual(commands[0][1:4], ['-u', str(hands_dir / 'sleepy.py'), 'http://127.0.0.1:1'])
        self.assertEqual(commands[0][4:], ['--node', '0x11', '--a', '1'])
        kept = [{'name': 'clock', 'args': ['--timezone', 'UTC']}]
        self.assertEqual(eden_hands.merge_hands(kept, [{'name': 'inbox', 'args': []}, {'name': 'clock', 'args': ['--timezone', 'UTC']}]),
                         kept + [{'name': 'inbox', 'args': []}])                      # a kept world gains a hand, the same hand again is fine
        with self.assertRaisesRegex(ValueError, 'kept with args'):
            eden_hands.merge_hands(kept, [{'name': 'clock', 'args': ['--timezone', 'Asia/Tokyo']}])
        work = self.root / 'world'
        work.mkdir()
        with ExitStack() as cleanup:
            started = eden_hands.start_hands([{'name': 'sleepy', 'args': ['--a', '1']}], 'http://127.0.0.1:1', '0x11', work, cleanup, hands_dir)
            name, process, log = started[0]
            self.assertEqual((name, process.poll()), ('sleepy', None))        # running
            for _ in range(50):
                if 'hand' in log.read_text():
                    break
                time.sleep(0.1)
            self.assertIn("hand ['http://127.0.0.1:1', '--node', '0x11', '--a', '1']", log.read_text())
        self.assertIsNotNone(process.poll())                                   # stopped at teardown
        self.assertEqual(eden_hands.hand_commands([], 'http://x', '0x11', hands_dir), [])      # a hand not listed does not run

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

    def workspace(self):
        return dict(name='reader', route='/reader', entry=['gov', 'reader', 'workspace'],
                    receiver=dict(slot=['gov', 'reader', 'source'], initial=['lib']),
                    shell=dict(stylesheet='/reader/style.css'))

    def workspace_bag(self, **overrides):
        self.bag('explorer', modules={'goo_workspace_mount': 'host.foil'})
        options = dict(dependencies=['explorer'],
                       grove=[dict(root=['gov', 'reader'], files=['reader.grove'])],
                       assets={'/reader/style.css': 'style.css'}, workspaces=[self.workspace()])
        options.update(overrides)
        return self.bag('reader', **options)

    def test_workspace_routes_and_runtime_registration(self):
        bag = self.workspace_bag()
        selected = select(self.root, ['reader'])
        source = self.root / 'runtime'; source.mkdir()
        specs = runtime_specs([(m, m.root, [], None) for m in selected], source)
        self.assertEqual(specs[-1][12], ['/reader', '/reader/style.css'])
        self.assertEqual(specs[-1][13], 1)
        self.assertEqual(specs[-1][5:7], [[], []])
        self.assertEqual(specs[0][13], 0)

    def test_workspace_schema_rejects_invalid_contracts(self):
        bag = self.workspace_bag()
        original = json.loads((bag / 'mount.json').read_text())
        mutations = [
            lambda w: w.update(unknown=True),
            lambda w: w.update(route='/reader/'),
            lambda w: w.update(entry=['lib', 'foreign']),
            lambda w: w['receiver'].update(slot=['sys', 'foreign']),
            lambda w: w['receiver'].update(admission='anything'),
            lambda w: w['receiver'].update(initial='/sys'),
            lambda w: w['shell'].update(stylesheet='/undeclared.css'),
            lambda w: w['shell'].update(navigation=[['invalid']]),
            lambda w: w['shell'].update(breadcrumbs='yes'),
        ]
        for mutate in mutations:
            data = json.loads(json.dumps(original)); mutate(data['workspaces'][0])
            (bag / 'mount.json').write_text(json.dumps(data))
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'workspace'):
                select(self.root, ['reader'])

    def test_multiple_workspaces_and_optional_shell(self):
        first = self.workspace(); first.pop('shell')
        second = self.workspace()
        second.update(name='secondary', route='/secondary', entry=['gov', 'reader', 'secondary'])
        second['receiver'].update(initial=['sys'], admission='record')
        self.workspace_bag(workspaces=[first, second])
        selected = select(self.root, ['reader'])
        self.assertEqual(len(selected[-1].manifest['workspaces']), 2)

    def test_workspace_requires_dependency_not_merely_selected_provider(self):
        self.workspace_bag(dependencies=[])
        with self.assertRaisesRegex(ValueError, 'explorer dependency'):
            select(self.root, ['explorer', 'reader'])

    def test_workspace_duplicate_receivers_and_route_collisions(self):
        bag = self.workspace_bag()
        original = json.loads((bag / 'mount.json').read_text())
        other = self.workspace(); other.update(name='other', route='/other')
        data = dict(original, workspaces=[self.workspace(), other])
        (bag / 'mount.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'two hosted receivers'):
            select(self.root, ['reader'])
        data = dict(original, routes=['/reader'])
        (bag / 'mount.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'distinct'):
            select(self.root, ['reader'])
        (bag / 'mount.json').write_text(json.dumps(original))
        self.bag('other', routes=['/reader/style.css'])
        with self.assertRaisesRegex(ValueError, 'Duplicate HTTP route'):
            select(self.root, ['reader', 'other'])

    def test_workspace_descriptor_change_requires_restart_and_retains_scan(self):
        bag = self.workspace_bag()
        mount = select(self.root, ['reader'])[-1]
        root = self.root / 'runtime'; (root / 'mounts' / 'reader').mkdir(parents=True)
        scanner = ScanBridge.__new__(ScanBridge)
        scanner.roots = {'mounts/reader': bag}; scanner.originals = scanner.roots
        scanner.manifests = {'mounts/reader': mount.manifest}
        scanner.scanners = {'mounts/reader': (mount, bag, None)}
        scanner.destination = root
        scanner.refresh('mounts/reader')
        data = json.loads((bag / 'mount.json').read_text())
        data['workspaces'][0]['receiver']['slot'][-1] = 'changed'
        (bag / 'mount.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'restart Eden'):
            scanner.refresh('mounts/reader')
        captured = json.loads((root / 'mounts/reader/mount.json').read_text())
        self.assertEqual(captured, mount.manifest)

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
