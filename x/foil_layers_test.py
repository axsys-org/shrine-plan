"""Regression tests for the production dependency boundary gate."""
from pathlib import Path
import tempfile
import unittest

from foil_layers import check


class LayerTests(unittest.TestCase):
    def errors(self, sources):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in sources.items():
                path = root / (name + '.foil')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            return check(root)

    def test_same_and_earlier_layers(self):
        self.assertEqual([], self.errors({
            'sys/types': '', 'sys/shrine': '- sys/types\n',
            'types': '- sys/shrine\n', 'stdlib/base': '- types\n',
            'namespace': '- stdlib/base\n', 'vanes': '- namespace\n',
            'stdlib/runtime': '- vanes\n', 'tests/example': '- stdlib/runtime\n',
        }))

    def test_nested_and_multiple_imports_cannot_bypass_boundary(self):
        errors = self.errors({
            'types': "+ nested\n  - sys/types vanes [at=http] ' comment\n",
            'sys/types': '', 'vanes': '',
        })
        self.assertEqual(['types:2: upward import vanes'], errors)

    def test_production_cannot_import_fixtures(self):
        for prefix in ('tests', 'test_fixtures', 'fixtures'):
            with self.subTest(prefix=prefix):
                errors = self.errors({'namespace': f'- {prefix}/example\n',
                                      prefix + '/example': ''})
                self.assertIn('production imports fixture', errors[0])

    def test_missing_and_unclassified_modules(self):
        errors = self.errors({'flat': '', 'types': '- missing flat\n',
                              'stdlib/runtime/obsolete': ''})
        self.assertTrue(any('unclassified production' in e for e in errors))
        self.assertTrue(any('missing import missing' in e for e in errors))
        self.assertTrue(any('unclassified import flat' in e for e in errors))
        self.assertIn('stdlib/runtime/obsolete: unclassified production module', errors)

    def test_cycles(self):
        errors = self.errors({'sys/a': '- sys/b\n', 'sys/b': '- sys/a\n'})
        self.assertEqual(['import cycle: sys/a -> sys/b -> sys/a'], errors)
        self.assertEqual(['import cycle: namespace -> namespace'],
                         self.errors({'namespace': '- namespace\n'}))

    def test_fixture_cycles_do_not_constrain_production(self):
        self.assertEqual([], self.errors({'test_fixtures/a': '- test_fixtures/a\n'}))


if __name__ == '__main__':
    unittest.main()
