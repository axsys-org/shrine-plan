"""Assemble disposable test sources; runtime Eden uses source mounts instead."""
from pathlib import Path
import json
import shutil


def materialize(core, extras, destination, names=None, *, native_tests=False):
    shutil.copytree(Path(core) / 'src', destination)
    for bag in sorted((Path(extras) / 'mounts').iterdir()):
        if names is not None and bag.name not in names:
            continue
        descriptor = json.loads((bag / 'mount.json').read_text())
        for old, leaf in descriptor.get('files', {}).items():
            if old.startswith('src/'):
                target = destination / old[4:]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(bag / leaf, target)
        for name, leaf in {**descriptor.get('modules', {}), **descriptor.get('tests', {})}.items():
            target = destination / 'foil' / (name + '.foil')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bag / leaf, target)
        for path in bag.glob('*.rvr'):
            shutil.copyfile(path, destination / 'reaver' / path.name)
    if native_tests:
        # Mounted checks read the same declared modules as production, rather
        # than the core schema compiler's generated dependency specimens.
        (destination / 'reaver/foil-test-deps.rvr').write_text(
            '(#bind std (#module std))\n(#import std)\n'
            '(#bind fixture (#module foil-test-context))\n(#bind source (#module foil-source))\n'
            '(define (prepare cache mods) (fixture:prepare source:read-module cache mods))\n'
            '(define (generated? name) 0)\n(define module-file-stamps [])\n'
            '(#export prepare generated? module-file-stamps)\n')
