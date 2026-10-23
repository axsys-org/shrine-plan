import hashlib
from html import escape
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

api = runpy.run_path(str(Path(__file__).parents[1] / 'client.py'))
prepare, validate_bundle = api['prepare'], api['validate_bundle']


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.md'
        self.source.write_bytes('Café\r\nSource evidence\n'.encode('utf-8'))
        self.manifest = self.root / 'sources.json'
        self.manifest.write_text(json.dumps({'source': {'path': 'source.md'}}))

    def test_exact_bytes_and_repeatable_snapshot(self):
        first = prepare(self.root, self.manifest)
        self.assertEqual(first, prepare(self.root, self.manifest))
        source = first['sources']['source']
        self.assertEqual(source['content'].encode(), self.source.read_bytes())
        self.assertEqual(source['digest'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.source.write_text('Changed source')
        self.assertNotEqual(first['digest'], prepare(self.root, self.manifest)['digest'])

    def test_incomplete_inventory_refuses(self):
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            prepare(self.root, self.manifest)

    def test_replay_checks_captured_bytes_and_manifest(self):
        bundle = prepare(self.root, self.manifest)
        self.source.unlink()
        self.assertEqual(bundle, validate_bundle(json.loads(json.dumps(bundle))))
        bundle['sources']['source']['content'] = 'Changed after capture'
        with self.assertRaisesRegex(ValueError, 'source digest mismatch'):
            validate_bundle(bundle)
        bundle['sources']['source']['digest'] = hashlib.sha256(b'Changed after capture').hexdigest()
        with self.assertRaisesRegex(ValueError, 'bundle digest mismatch'):
            validate_bundle(bundle)

    def test_source_export_preserves_entities_and_line_endings(self):
        text = ';.\r\n  Café & <tags> </textarea>\n' + ('  Long source\n' * 1000)
        form = api['SourceForm']()
        form.feed('<textarea id="other">ignore</textarea><textarea id="page-source">'
                  + escape(text) + '</textarea><p>ignore</p>')
        self.assertTrue(form.found)
        self.assertFalse(form.active)
        self.assertEqual(text, ''.join(form.parts))

    def test_escaped_source_and_oversize_refuse(self):
        self.manifest.write_text(json.dumps({'source': {'path': '../outside.md'}}))
        with self.assertRaisesRegex(ValueError, 'escapes repository'):
            prepare(self.root, self.manifest)
        self.manifest.write_text(json.dumps({'source': {'path': 'source.md'}}))
        self.source.write_bytes(b'x' * 131073)
        with self.assertRaisesRegex(ValueError, '131072'):
            prepare(self.root, self.manifest)

    def test_mount_capture_is_repeatable_and_has_no_transport(self):
        host = runpy.run_path(str(Path(__file__).parents[1] / 'host.py'))
        bag = self.root / 'bag'
        bag.mkdir()
        with patch.dict('os.environ', {'SHRINE_FLOW_SOURCE_ROOT': str(self.root)}), patch.object(
                host['runpy'], 'run_path', return_value={'prepare': prepare}):
            host['scan'](self.root, bag)
            first = (bag / 'repository-evidence.json').read_bytes()
            host['scan'](self.root, bag)
        self.assertEqual(first, (bag / 'repository-evidence.json').read_bytes())
        self.assertEqual(json.loads(first)['source']['content'].encode(), self.source.read_bytes())

    def test_incomplete_capture_preserves_last_good_mount_bag(self):
        host = runpy.run_path(str(Path(__file__).parents[1] / 'host.py'))
        bag = self.root / 'bag'
        bag.mkdir()
        with patch.dict('os.environ', {'SHRINE_FLOW_SOURCE_ROOT': str(self.root)}), patch.object(
                host['runpy'], 'run_path', return_value={'prepare': prepare}):
            host['scan'](self.root, bag)
            first = (bag / 'repository-evidence.json').read_bytes()
            self.source.unlink()
            with self.assertRaises(FileNotFoundError):
                host['scan'](self.root, bag)
        self.assertEqual(first, (bag / 'repository-evidence.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
