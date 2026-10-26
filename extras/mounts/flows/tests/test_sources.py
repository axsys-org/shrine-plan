import hashlib
from html import escape
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

host = runpy.run_path(str(Path(__file__).parents[1] / 'host.py'))
capture, validate_bundle = host['capture_sources'], host['validate_bundle']


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.md'
        self.source.write_bytes('Café\r\nSource evidence\n'.encode('utf-8'))
        self.manifest = self.root / 'sources.json'
        self.manifest.write_text(json.dumps({'source': {'path': 'source.md'}}))

    def test_exact_bytes_and_repeatable_snapshot(self):
        first = capture(self.root, self.manifest)
        self.assertEqual(first, capture(self.root, self.manifest))
        source = first['sources']['source']
        self.assertEqual(source['content'].encode(), self.source.read_bytes())
        self.assertEqual(source['digest'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.source.write_text('Changed source')
        self.assertNotEqual(first['digest'], capture(self.root, self.manifest)['digest'])

    def test_incomplete_inventory_refuses(self):
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            capture(self.root, self.manifest)

    def test_replay_checks_captured_bytes_and_manifest(self):
        bundle = capture(self.root, self.manifest)
        self.source.unlink()
        self.assertEqual(bundle, validate_bundle(json.loads(json.dumps(bundle))))
        bundle['sources']['source']['content'] = 'Changed after capture'
        with self.assertRaisesRegex(ValueError, 'source digest mismatch'):
            validate_bundle(bundle)
        bundle['sources']['source']['digest'] = hashlib.sha256(b'Changed after capture').hexdigest()
        with self.assertRaisesRegex(ValueError, 'bundle digest mismatch'):
            validate_bundle(bundle)

    def test_escaped_source_and_oversize_refuse(self):
        self.manifest.write_text(json.dumps({'source': {'path': '../outside.md'}}))
        with self.assertRaisesRegex(ValueError, 'escapes repository'):
            capture(self.root, self.manifest)
        self.manifest.write_text(json.dumps({'source': {'path': 'source.md'}}))
        self.source.write_bytes(b'x' * 131073)
        with self.assertRaisesRegex(ValueError, '131072'):
            capture(self.root, self.manifest)

    def test_mount_capture_is_repeatable(self):
        bag = self.root / 'bag'
        bag.mkdir()
        with patch.dict('os.environ', {'SHRINE_FLOW_SOURCE_ROOT': str(self.root)}):
            host['scan'](self.root, bag)
            first = (bag / 'repository-evidence.json').read_bytes()
            host['scan'](self.root, bag)
        self.assertEqual(first, (bag / 'repository-evidence.json').read_bytes())
        self.assertEqual(json.loads(first)['source']['content'].encode(), self.source.read_bytes())

    def test_failed_evidence_does_not_block_shared_module_scan(self):
        bag = self.root / 'bag'
        bag.mkdir()
        with patch.dict('os.environ', {'SHRINE_FLOW_SOURCE_ROOT': str(self.root)}):
            host['scan'](self.root, bag)
            self.source.unlink()
            (self.root / 'main.foil').write_text('+ changed\n  ^ nat\n  2\n')
            host['scan'](self.root, bag)
        fault = json.loads((bag / 'repository-evidence.json').read_text())
        self.assertIn('capture_error', fault)
        self.assertNotIn('source', fault)
        self.assertEqual((bag / 'main.foil').read_text(), '+ changed\n  ^ nat\n  2\n')


class SourceFormTests(unittest.TestCase):
    def test_source_export_preserves_entities_and_line_endings(self):
        text = ';.\r\n  Café & <tags> </textarea>\n' + ('  Long source\n' * 1000)
        client = runpy.run_path(str(Path(__file__).parents[1] / 'client.py'))
        form = client['SourceForm']()
        form.feed('<textarea id="other">ignore</textarea><textarea id="page-source">'
                  + escape(text) + '</textarea><p>ignore</p>')
        self.assertTrue(form.found)
        self.assertFalse(form.active)
        self.assertEqual(text, ''.join(form.parts))


if __name__ == '__main__':
    unittest.main()
