#!/usr/bin/env python3
"""Contract checks for slot documentation input and deterministic generation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import slot_catalog as catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.doc = {'format': 'reaver.slots/v2', 'slots': [
            {'path': '/sys/example', 'title': 'Example', 'summary': 'An example.'}]}

    def load(self, doc):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'example.slots.json'
            path.write_text(json.dumps(doc) if isinstance(doc, dict) else doc)
            return catalog.load(path)

    def test_rejects_duplicate_keys_and_paths(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON member'):
            self.load('{"format": "reaver.slots/v2", "format": "reaver.slots/v2", "slots": []}')
        self.doc['slots'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate slot'):
            self.load(self.doc)

    def test_rejects_malformed_contract(self):
        for field, value in [('path', '/0x11/private'), ('path', '/sys/a/../b'),
                             ('summary', ' '), ('title', ' '), ('title', 'a\nb'),
                             ('payload', 'text'), ('scope', 'record'),
                             ('machinery', False), ('extra', '')]:
            with self.subTest(field=field, value=value):
                doc = copy.deepcopy(self.doc)
                doc['slots'][0][field] = value
                with self.assertRaises(ValueError):
                    self.load(doc)

    def test_rejects_slot_namespace_collision(self):
        child = dict(self.doc['slots'][0], path='/sys/example/child')
        self.doc['slots'].append(child)
        with self.assertRaisesRegex(ValueError, 'namespace prefix'):
            self.load(self.doc)

    def test_order_does_not_change_output(self):
        self.doc['slots'].append(dict(self.doc['slots'][0], path='/sys/another'))
        first = catalog.outputs(self.load(self.doc))
        self.doc['slots'].reverse()
        self.assertEqual(first, catalog.outputs(self.load(self.doc)))

    def test_catalog_is_current(self):
        for path, content in catalog.outputs(catalog.load(catalog.CATALOG)).items():
            self.assertEqual(path.read_text(), content, str(path))


if __name__ == '__main__':
    unittest.main()
