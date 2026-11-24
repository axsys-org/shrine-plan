"""Mount authoring and wire save/reload contract tests (no runtime needed)."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from eden_mounts import catalog, select
from mount_tools import create, add_file
from mount_wire import MountWire


class CompilerStub:
    def request(self, request):
        return {'ok': True, 'op': request.get('op')}


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = create(self.root, 'clockwork')

    def test_core_reload_requires_live_server_and_checks_descriptors(self):
        mounts = select(self.root, ['clockwork'])
        self.assertFalse(MountWire(CompilerStub(), mounts).request({'op': 'core/reload'})['ok'])
        events = []
        def live(name, rescan):
            events.append((name, rescan))
            return {'ok': True}
        service = MountWire(CompilerStub(), mounts, live,
                            refresh_core=lambda: events.append('capture'))
        self.assertTrue(service.request({'op': 'core/reload'})['ok'])
        self.assertEqual(events, ['capture', ('@core', True)])
        add_file(self.root, 'clockwork', 'extra.foil')
        events.clear()
        self.assertTrue(service.request({'op': 'core/reload'})['restart_required'])
        self.assertEqual(events, [])

    def test_scaffold_and_registration(self):
        mount = select(self.root, ['clockwork'])[0]
        self.assertEqual(mount.manifest['grove'][0]['root'], ['gov', 'clockwork'])
        self.assertTrue((self.folder / 'main.foil').is_file())
        add_file(self.root, 'clockwork', 'actors.grove')
        add_file(self.root, 'clockwork', 'rules.foil')
        add_file(self.root, 'clockwork', 'tests.foil', 'test')
        add_file(self.root, 'clockwork', 'style.css', 'asset', url='/clockwork/style.css')
        data = select(self.root, ['clockwork'])[0].manifest
        self.assertEqual(data['grove'][0]['files'], ['main.grove', 'actors.grove'])
        self.assertEqual(data['modules']['apps/clockwork/rules'], 'rules.foil')
        self.assertIn(['lib', 'apps/clockwork/rules'], data['roots'])
        self.assertNotIn(['lib', 'apps/clockwork/tests'], data['roots'])
        add_file(self.root, 'clockwork', 'actors.grove')
        self.assertEqual(catalog(self.root)['clockwork'].manifest, data)

    def test_preserve_files_and_reject_collisions(self):
        with self.assertRaises(ValueError):
            create(self.root, 'clockwork')
        before = (self.folder / 'main.foil').read_bytes()
        with self.assertRaises(ValueError):
            add_file(self.root, 'clockwork', 'main.foil', content=b'overwrite')
        self.assertEqual((self.folder / 'main.foil').read_bytes(), before)
        create(self.root, 'other', 'foil')
        with self.assertRaises(ValueError):
            add_file(self.root, 'other', 'bad.foil', module='apps/clockwork/main')
        with self.assertRaises(ValueError):
            add_file(self.root, 'other', 'bad.foil', module='stdlib/runtime')
        for leaf in ('../escape.foil', '/absolute.foil', 'mount.json', 'nested/file.foil'):
            with self.assertRaises(ValueError):
                add_file(self.root, 'clockwork', leaf)
        self.assertFalse((self.folder / 'bad.foil').exists())

    def test_existing_file_registration(self):
        (self.folder / 'story.grove').write_text('existing content')
        add_file(self.root, 'clockwork', 'story.grove')
        self.assertEqual((self.folder / 'story.grove').read_text(), 'existing content')

    def test_importable_names_and_normalization_collisions(self):
        create(self.root, 'my-game')
        add_file(self.root, 'my-game', 'combat-rules.foil')
        modules = catalog(self.root)['my-game'].manifest['modules']
        self.assertIn('apps/my_game/main', modules)
        self.assertIn('apps/my_game/combat_rules', modules)
        with self.assertRaisesRegex(ValueError, 'already registered'):
            create(self.root, 'my_game')
        self.assertFalse((self.root / 'mounts/my_game').exists())
        with self.assertRaises(ValueError):
            add_file(self.root, 'my-game', 'bad.foil', module='apps/my-game/bad')

    def test_save_compare_and_swap(self):
        service = MountWire(CompilerStub(), select(self.root, ['clockwork']))
        status = service.request({'op': 'mount/status', 'mount': 'clockwork'})
        request = dict(op='mount/save', mount='clockwork', file='main.grove',
                       text='new text', expected=status['files']['main.grove'], reload=False)
        self.assertTrue(service.request(request)['ok'])
        self.assertEqual((self.folder / 'main.grove').read_text(), 'new text')
        self.assertTrue(service.request(request)['conflict'])
        self.assertFalse(service.request({'op': 'mount/reload', 'mount': 'clockwork'})['ok'])
        with self.assertRaises(ValueError):
            service.request(dict(request, file='../outside'))
        with self.assertRaises(ValueError):
            service.request(dict(request, file='mount.json'))
        outside = self.root / 'outside'
        outside.write_text('secret')
        (self.folder / 'link.foil').symlink_to(outside)
        with self.assertRaises(ValueError):
            service.request(dict(request, file='link.foil'))

    def test_restart_required(self):
        service = MountWire(CompilerStub(), select(self.root, ['clockwork']))
        add_file(self.root, 'clockwork', 'extra.grove')
        result = service.request({'op': 'mount/reload', 'mount': 'clockwork'})
        self.assertTrue(result['restart_required'])

    def test_reload_orders_dependents_and_preserves_failed_save(self):
        create(self.root, 'child', 'foil', ['clockwork'])
        events = []
        epochs = {'clockwork': 1, 'child': 1}
        def live(name, rescan):
            if rescan:
                events.append(name)
                epochs[name] += 1
            return {'epoch': epochs[name], 'ready': name != 'child', 'publication': 1, 'message': ''}
        service = MountWire(CompilerStub(), select(self.root, ['child']), live)
        result = service.request({'op': 'mount/reload', 'mount': 'clockwork'})
        self.assertEqual(events, ['clockwork', 'child'])
        self.assertFalse(result['ok'])
        expected = hashlib.sha256((self.folder / 'main.grove').read_bytes()).hexdigest()
        result = service.request(dict(op='mount/save', mount='clockwork', file='main.grove',
                                      text='edited source', expected=expected))
        self.assertEqual(result['saved'], 'main.grove')
        self.assertFalse(result['ok'])
        self.assertEqual((self.folder / 'main.grove').read_text(), 'edited source')


if __name__ == '__main__':
    result = unittest.main(exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('MOUNT-TOOLS-CHECK-PASS')
