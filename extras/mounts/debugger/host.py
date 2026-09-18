"""Build immutable assets beside links to the editable flat source bag."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request


def prepare(root, work, check, cleanup, context):
    work.mkdir(parents=True)
    bag = work / 'bag'
    bag.mkdir()
    for source in root.iterdir():
        if source.is_file() and source.name not in ('build.json', 'debug.js', 'debug.css', 'mash.js', 'components.css'):
            (bag / source.name).symlink_to(source)
    scan(root, bag)
    return bag, []


_generations = {}
_expected_assets = {}

def scan(root, bag):
    global _expected_assets
    key = str(bag.resolve())
    digest = hashlib.sha256()
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix in ('.js', '.css', '.mjs'):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    generation = digest.hexdigest()
    if _generations.get(key) == generation:
        return
    env = dict(os.environ, DEBUG_OUTPUT_ROOT=str(bag))
    env.pop('MASH_ROOT', None)
    command = ['nix', '--extra-experimental-features', 'nix-command flakes',
               'develop', '--no-update-lock-file', f'path:{root.parent.parent}#debugger',
               '--command', 'node', str(root / 'build-debug.mjs')]
    subprocess.run(command, env=env, check=True)
    manifest = json.loads((bag / 'build.json').read_text())
    expected = {'debug.js', 'debug.css', 'mash.js', 'components.css'}
    if set(manifest['assets']) != expected:
        raise RuntimeError('Incomplete debugger asset bundle')
    for name, digest in manifest['assets'].items():
        if hashlib.sha256((bag / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Invalid debugger asset: ' + name)
    _generations[key] = generation
    _expected_assets = manifest['assets']


def check(url, node, timeout):
    def checkpoint():
        key = 'v1/x:' + node[2:] + '/ts:696f/ts:68747470'
        with urllib.request.urlopen(url + '/debug-read/physical?pathKey=' + key + '&collection=children&limit=1', timeout=timeout) as response:
            value = json.load(response)
            return value['epoch'], value['total']
    before = checkpoint()
    with urllib.request.urlopen(url + '/debug/' + node + '/app/debug', timeout=timeout) as response:
        assert 'data-grove-contract="debugger/v1"' in response.read().decode()
    for asset, source in [('debug.js', 'debug.js'), ('debug.css', 'debug.css'),
                          ('debug-mash.js', 'mash.js'), ('debug-components.css', 'components.css')]:
        with urllib.request.urlopen(url + '/' + asset, timeout=timeout) as response:
            assert response.status == 200
            assert hashlib.sha256(response.read()).hexdigest() == _expected_assets[source]
    for scope in ('workspace', 'outline', 'preview'):
        with urllib.request.urlopen(url + '/debug/' + node + '?scope=' + scope, timeout=timeout) as response:
            assert 'data-grove-contract="debugger/v1"' in response.read().decode()
    assert checkpoint() == before, 'Inspection must not append journal events or HTTP records'
