"""Assemble disposable test sources; runtime Eden uses source mounts instead."""
from pathlib import Path
import json
import shutil


def materialize(core, extras, destination, names=None):
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
