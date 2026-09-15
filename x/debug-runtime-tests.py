#!/usr/bin/env python3
import unittest
import tempfile
import json
import hashlib
from pathlib import Path
from debug_runtime_helpers import startup_failed, verify_asset_build, ASSET_PATHS
from debug_transport_fixture import MODES, RETURNED, startup_source, require_declaration, SlotDocument


class TransportFixtureTests(unittest.TestCase):
    def test_each_fixture_uses_production_declarations_and_explicit_try(self):
        for mode in MODES:
            source = startup_source(49152, mode)
            self.assertIn('(#module debug-transport-fixture)', source)
            self.assertIn(f'(fixture:start 49152 "{mode}" 10000)', source)
            self.assertIn(f'("{RETURNED}" (Try (lambda', source)
            self.assertNotIn('eden:start ', source)

    def test_protected_ports_and_unknown_modes_are_rejected(self):
        for port in (0, -1, 8138, 51571, 65536):
            with self.assertRaises(ValueError):
                startup_source(port, 'journal')
        with self.assertRaises(ValueError):
            startup_source(49152, 'unknown')

    def test_legacy_documents_cannot_pass_the_transport_ui_contract(self):
        require_declaration('<main data-grove-contract="debugger/v1"></main>')
        with self.assertRaises(AssertionError):
            require_declaration('<main id="debug-workspace"></main>')

    def test_slot_metadata_excludes_manifest_previews(self):
        document = SlotDocument('''<main id="debug-workspace" data-path="/" data-grove-contract="debugger/v1">
          <sh-limb data-key="/text" data-value-epoch="22"><sh-slot title="Display label"></sh-slot></sh-limb>
          <sh-limb><sh-slot title="/text"></sh-slot></sh-limb>
        </main>''')
        self.assertEqual(document.workspace['data-path'], '/')
        self.assertEqual(list(document.fields), ['/text'])
        self.assertEqual(document.fields['/text']['data-value-epoch'], '22')


class StartupTests(unittest.TestCase):
    def test_caught_compiler_error_is_not_a_failed_launch(self):
        self.assertFalse(startup_failed('(\"error\" (0 \"newtype\" \"unknown row face\"))\n', 'RETURNED'))

    def test_uncaught_repl_error_fails(self):
        self.assertTrue(startup_failed('prefix\n(\"ERROR\"\n \"failed\")', 'RETURNED'))

    def test_entry_failure_is_terminal_but_actor_start_is_not(self):
        self.assertTrue(startup_failed('(\"RETURNED\" (1 \"compile failed\"))', 'RETURNED'))
        self.assertFalse(startup_failed('(\"RETURNED\" (0 1))', 'RETURNED'))
        self.assertFalse(startup_failed('(\"RETURNED\" (0 22))\n\"HTTP foot listening\"', 'RETURNED'))

    def test_quoted_source_is_not_a_returned_entry(self):
        self.assertFalse(startup_failed('(0 \"print\" (0 \"RETURNED\" 0))', 'RETURNED'))

    def test_listen_failure_is_terminal(self):
        self.assertTrue(startup_failed('pump: listen failed', 'RETURNED'))
        self.assertFalse(startup_failed('\"HTTP foot listening\"', 'RETURNED'))

    def test_asset_build_is_complete_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = {}
            for name in ASSET_PATHS:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(name)
                assets[name] = hashlib.sha256(name.encode()).hexdigest()
            manifest = root / 'build.json'
            for mode, values in [('legacy-compatibility', assets), ('grove', {})]:
                manifest.write_text(json.dumps(dict(mode=mode, assets=values)))
                with self.assertRaisesRegex(RuntimeError, 'complete Grove'):
                    verify_asset_build(root)
            manifest.write_text(json.dumps(dict(mode='grove', assets=assets)))
            self.assertEqual(verify_asset_build(root)['assets'], assets)
            (root / 'debug.js').write_text('changed')
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                verify_asset_build(root)


if __name__ == '__main__':
    unittest.main()
