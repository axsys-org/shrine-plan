"""Production source inventory; loader names and publication owners differ."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent / 'src/foil'
LAYERS = ('sys', 'types', 'base', 'namespace', 'vanes', 'runtime')
NAME = re.compile(r'[a-z_][a-z0-9_]*(?:/[a-z_][a-z0-9_]*)*\Z')


def inventory(root=ROOT):
    entries = {}
    for number, line in enumerate((root / 'modules.tsv').read_text().splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        fields = line.split('\t')
        if (len(fields) != 3 or not NAME.fullmatch(fields[0])
                or fields[1] not in LAYERS or not NAME.fullmatch(fields[2])):
            raise ValueError(f'modules.tsv:{number}: invalid module entry')
        name, layer, owner = fields
        if name in entries:
            raise ValueError(f'modules.tsv:{number}: duplicate module {name}')
        if name.startswith('sys/') != (layer == 'sys'):
            raise ValueError(f'modules.tsv:{number}: invalid system layer')
        entries[name] = (layer, owner)
    for name, (layer, owner) in entries.items():
        if owner not in entries or entries[owner][1] != owner:
            raise ValueError(f'{name}: owner must name a canonical inventory entry')
        if (layer == 'sys') != (entries[owner][0] == 'sys'):
            raise ValueError(f'{name}: ownership crosses the system boundary')
    return entries


def local_modules(root=ROOT):
    return [name for name, (layer, _) in inventory(root).items() if layer != 'sys']


def capture_local(root=ROOT):
    """Capture the manifest and every local source before copying any bytes."""
    manifest = (root / 'modules.tsv').read_bytes()
    entries = inventory(root)
    from foil_layers import check
    errors = check(root, entries)
    if errors:
        raise ValueError('Invalid module inventory: ' + '; '.join(errors))
    sources = [(name + '.foil', (root / (name + '.foil')).read_bytes())
               for name, (layer, _) in entries.items() if layer != 'sys']
    if (root / 'modules.tsv').read_bytes() != manifest:
        raise ValueError('Module inventory changed while capturing sources; retry')
    return sources + [('modules.tsv', manifest)]
