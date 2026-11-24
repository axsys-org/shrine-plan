"""Regression tests for the production dependency boundary gate."""
from pathlib import Path
import tempfile
import unittest

from foil_layers import check
from foil_modules import capture_local, inventory, local_modules, ROOT


class LayerTests(unittest.TestCase):
    def errors(self, sources):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in sources.items():
                path = root / (name + '.foil')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            entries = {name: item for name, item in inventory(ROOT).items()
                       if name in sources}
            # Synthetic sys modules exercise the same-layer cycle gate.
            entries.update({name: ('sys', name) for name in sources
                            if name.startswith('sys/')})
            return check(root, entries)

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


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / 'modules.tsv'
        self.write('sys/types', '')
        self.write('types', '- sys/types\n')
        self.write('stdlib/json', '- types\n')
        self.write('stdlib/base', '- stdlib/json\n')
        self.good = ('sys/types\tsys\tsys/types\n'
                     'types\ttypes\ttypes\n'
                     'stdlib/json\tbase\tstdlib/base\n'
                     'stdlib/base\tbase\tstdlib/base\n')
        self.manifest.write_text(self.good)

    def write(self, name, text):
        path = self.root / (name + '.foil')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_shared_owner_and_capture(self):
        self.assertEqual(('base', 'stdlib/base'), inventory(self.root)['stdlib/json'])
        self.assertEqual(['types', 'stdlib/json', 'stdlib/base'], local_modules(self.root))
        captured = dict(capture_local(self.root))
        self.assertEqual(set(captured), {'types.foil', 'stdlib/json.foil',
                                       'stdlib/base.foil', 'modules.tsv'})
        self.assertEqual(self.good.encode(), captured['modules.tsv'])
        self.assertEqual(b'- types\n', captured['stdlib/json.foil'])
        self.assertEqual([], check(self.root))

    def test_invalid_inventory(self):
        cases = [self.good + 'types\ttypes\ttypes\n',
                 self.good.replace('stdlib/json\tbase', '../json\tbase'),
                 self.good.replace('stdlib/json\tbase', 'stdlib/json\tunknown'),
                 self.good.replace('stdlib/json\tbase', 'stdlib/json\tsys'),
                 self.good.replace('stdlib/json\tbase\tstdlib/base',
                                   'stdlib/json\tbase\tabsent'),
                 self.good.replace('stdlib/base\tbase\tstdlib/base',
                                   'stdlib/base\tbase\tstdlib/json'),
                 self.good.replace('stdlib/json\tbase\tstdlib/base',
                                   'stdlib/json\tbase\tsys/types')]
        for text in cases:
            with self.subTest(manifest=text):
                self.manifest.write_text(text)
                with self.assertRaises(ValueError):
                    inventory(self.root)
                with self.assertRaises(ValueError):
                    capture_local(self.root)

    def test_capture_rejects_missing_or_unclassified_sources(self):
        (self.root / 'stdlib/json.foil').unlink()
        with self.assertRaisesRegex(ValueError, 'inventory source is missing'):
            capture_local(self.root)
        self.write('stdlib/json', '- types\n')
        self.write('stdlib/forgotten', '')
        with self.assertRaisesRegex(ValueError, 'unclassified production'):
            capture_local(self.root)

    def test_capture_rejects_upward_import_and_cycle(self):
        self.write('types', '- stdlib/base\n')
        with self.assertRaisesRegex(ValueError, 'upward import'):
            capture_local(self.root)
        self.write('types', '')
        self.write('stdlib/json', '- stdlib/base\n')
        with self.assertRaisesRegex(ValueError, 'import cycle'):
            capture_local(self.root)


if __name__ == '__main__':
    unittest.main()
