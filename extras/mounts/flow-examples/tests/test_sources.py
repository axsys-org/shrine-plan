import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

host = runpy.run_path(str(Path(__file__).parents[1] / 'host.py'))


class SourceStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bag = self.root / 'bag'
        self.bag.mkdir()
        self.source = self.root / 'source.md'
        self.source.write_bytes('Café\r\nSource evidence\n'.encode('utf-8'))
        self.spec = {'source': {'path': 'source.md', 'file': 'evidence-source.md', 'format': 'md'}}
        self.catalogue = self.root / 'examples.json'
        self.catalogue.write_text(json.dumps({'sample': {'sources': self.spec}}))
        self.env = patch.dict('os.environ', {'SHRINE_FLOW_SOURCE_ROOT': str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def scan(self):
        host['scan'](self.root, self.bag)

    def test_exact_bytes_without_an_evidence_bundle(self):
        self.scan()
        self.assertEqual(self.source.read_bytes(), (self.bag / 'evidence-source.md').read_bytes())
        self.assertFalse((self.bag / 'repository-evidence.json').exists())

    def test_deleted_file_is_released_and_restored(self):
        original = self.source.read_bytes()
        self.scan()
        self.source.unlink()
        self.scan()
        self.assertFalse((self.bag / 'evidence-source.md').exists())
        self.source.write_bytes(original)
        self.scan()
        self.assertEqual(original, (self.bag / 'evidence-source.md').read_bytes())

    def test_changed_source_binding_releases_obsolete_file(self):
        self.scan()
        self.spec['source']['file'] = 'replacement.md'
        self.catalogue.write_text(json.dumps({'sample': {'sources': self.spec}}))
        self.scan()
        self.assertFalse((self.bag / 'evidence-source.md').exists())
        self.assertEqual(self.source.read_bytes(), (self.bag / 'replacement.md').read_bytes())

    def test_examples_share_one_staged_source(self):
        examples = {name: {'sources': self.spec} for name in ['first', 'second']}
        self.catalogue.write_text(json.dumps(examples))
        self.scan()
        self.assertEqual(self.source.read_bytes(), (self.bag / 'evidence-source.md').read_bytes())
        del examples['first']
        self.catalogue.write_text(json.dumps(examples))
        self.scan()
        self.assertTrue((self.bag / 'evidence-source.md').exists())
        self.catalogue.write_text('{}')
        self.scan()
        self.assertFalse((self.bag / 'evidence-source.md').exists())

    def test_different_sources_cannot_claim_the_same_staged_name(self):
        other = dict(self.spec['source'], path='other.md')
        self.catalogue.write_text(json.dumps({'first': {'sources': self.spec},
                                             'second': {'sources': {'source': other}}}))
        with self.assertRaisesRegex(ValueError, 'distinct'):
            self.scan()

    def test_escape_and_name_collision_refuse(self):
        for field, value, reason in [('path', '../outside.md', 'escapes'),
                                      ('file', '../outside.md', 'flat'),
                                      ('file', 'examples.json', 'distinct')]:
            spec = dict(self.spec['source'], **{field: value})
            self.catalogue.write_text(json.dumps({'sample': {'sources': {'source': spec}}}))
            with self.assertRaisesRegex(ValueError, reason):
                self.scan()

    def test_shared_mount_without_examples_still_stages_modules(self):
        self.scan()
        self.catalogue.unlink()
        (self.root / 'main.foil').write_text('+ independent\n  ^ nat\n  1\n')
        self.scan()
        self.assertFalse((self.bag / 'evidence-source.md').exists())
        self.assertTrue((self.bag / 'main.foil').is_file())

    def test_authored_examples_are_flat_and_removal_releases_staging(self):
        examples = self.root / 'examples'
        examples.mkdir()
        example = examples / 'sample.semidoc'
        example.write_text(';. /example\n  ;= Example\n')
        self.scan()
        self.assertEqual(example.read_bytes(), (self.bag / example.name).read_bytes())
        self.assertFalse((self.bag / 'examples').exists())
        example.unlink()
        self.scan()
        self.assertFalse((self.bag / example.name).exists())

    def test_prepare_owns_only_example_staging(self):
        folder, arguments = host['prepare'](self.root, self.root / 'work', True, None,
                                           {'node': '0xab', 'workspace': str(self.root)})
        self.assertTrue((folder / 'evidence-source.md').is_file())
        self.assertEqual(arguments, [])


if __name__ == '__main__':
    unittest.main()
