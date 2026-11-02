"""Small filesystem and wire tools for version-1 flat extras mounts."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import socket
import sys
import tempfile

from eden_mounts import catalog, select

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r'[a-z][a-z0-9_-]*\Z')
MODULE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*\Z')


def leaf_name(value):
    if not value or Path(value).name != value or value.startswith('.') or value == 'mount.json' or '\\' in value or '\0' in value:
        raise ValueError('file must be a visible flat filename other than mount.json')
    return value


def atomic_write(path, data):
    path = Path(path)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def roots(data):
    return [['lib', mod] for mod in data.get('modules', {})] + [u['root'] for u in data.get('grove', [])]


def validate_candidate(extras, name, data):
    """Apply Eden's descriptor checks before exposing a new registration."""
    manifests = {m.name: m.manifest for m in catalog(extras).values()}
    for group in ('modules', 'tests'):
        for mod in data.get(group, {}):
            if (ROOT / 'src/foil' / (mod + '.foil')).exists():
                raise ValueError(f'module belongs to core: {mod}')
            for other, manifest in manifests.items():
                if other != name and any(mod in manifest.get(key, {}) for key in ('modules', 'tests')):
                    raise ValueError(f'module already registered: {mod}')
    manifests[name] = data
    with tempfile.TemporaryDirectory(prefix='mount-contract-') as temp:
        candidate = Path(temp)
        for key, manifest in manifests.items():
            target = candidate / 'mounts' / key
            target.mkdir(parents=True)
            (target / 'mount.json').write_text(json.dumps(manifest))
        select(candidate, [name])


def foil_template(mod):
    name = mod.split('/')[1].replace('-', '_') if mod.startswith('apps/') else mod.split('/')[-1].replace('-', '_')
    return f'- stdlib/runtime\n\n+ {name}\n  + greeting\n    ^ str\n    "Hello from {name}."\n'


def grove_template():
    return '''#import lede=sys/lede

"/" =
  @tree
  lede: "A new world"
'''


def terminal_template():
    return '''- stdlib/runtime

+ terminal
  + main
    ' stdin/stdout belong to this loop. Return a process exit status.
    \\ server=nat arguments=row[str]
    ^ nat
    % ignored=nat 0
    ^ nat
    = ;bytes (Input 4096)
    ? (le bytes 1) 0
    ; (Output bytes)
    | _ 0
'''


def create(extras, name, kind='grove', dependencies=(), terminal=False):
    if not NAME.fullmatch(name):
        raise ValueError('mount names must start with a lowercase letter and contain only letters, digits, _ or -')
    folder = extras / 'mounts' / name
    folder.parent.mkdir(parents=True, exist_ok=True)
    if folder.exists():
        raise ValueError(f'mount already exists: {folder}')
    available = catalog(extras)
    for dep in dependencies:
        if dep not in available:
            raise ValueError(f'unknown dependency: {dep}')
    mod = f'apps/{name.replace("-", "_")}/main'
    data = dict(version=1, name=name, dependencies=list(dict.fromkeys(dependencies)),
                modules={mod: 'main.foil'}, grove=[], assets={}, files={}, tests={})
    if kind == 'grove':
        data['grove'] = [{'root': ['gov', name.replace('-', '_')], 'files': ['main.grove']}]
    if terminal:
        cli = f'apps/{name.replace("-", "_")}/cli'
        data['modules'][cli] = 'cli.foil'
        data['terminal'] = {'module': cli, 'entry': ['terminal', 'main']}
    data['roots'] = roots(data)
    validate_candidate(extras, name, data)
    # Construct the whole bag off to the side, exposing it only when complete.
    with tempfile.TemporaryDirectory(prefix='.' + name + '-', dir=folder.parent) as temp:
        staged = Path(temp) / name
        staged.mkdir()
        (staged / 'main.foil').write_text(foil_template(mod))
        if kind == 'grove':
            (staged / 'main.grove').write_text(grove_template())
        if terminal:
            (staged / 'cli.foil').write_text(terminal_template())
        (staged / 'mount.json').write_text(json.dumps(data, indent=2) + '\n')
        (staged / 'README.md').write_text(f'# {name}\n\nStart from the core checkout:\n\n'
            f'```sh\nx/eden --extras-root {shlex.quote(str(extras))} --{"terminal" if terminal else "mount"} {name} --wire-port 8679\n```\n\n'
            f'After editing registered source files: `x/reload-mount {name}`.\n'
            'Manifest registration changes require an Eden restart.\n')
        staged.rename(folder)
    return folder


def add_file(extras, name, leaf, kind=None, module=None, root=None, url=None, content=None):
    leaf_name(leaf)
    mount = catalog(extras).get(name)
    if mount is None:
        raise ValueError(f'unknown mount: {name}')
    data = json.loads(json.dumps(mount.manifest))
    path = mount.root / leaf
    if path.is_symlink():
        raise ValueError('refusing to register a symlink')
    if path.exists() and not path.is_file():
        raise ValueError('file is not a regular file')
    kind = kind or {'.foil': 'foil', '.grove': 'grove'}.get(path.suffix, 'support')
    if kind in ('foil', 'test'):
        if path.suffix != '.foil':
            raise ValueError('Foil modules and tests must use .foil')
        mod = module or f'apps/{name.replace("-", "_")}/{path.stem.replace("-", "_")}'
        if not MODULE.fullmatch(mod):
            raise ValueError('logical module segments must be identifiers (use underscores, not hyphens)')
        key = 'tests' if kind == 'test' else 'modules'
        for other in catalog(extras).values():
            for group in ('modules', 'tests'):
                if mod in other.manifest.get(group, {}) and not (
                        other.name == name and group == key and other.manifest[group][mod] == leaf):
                    raise ValueError(f'module already registered: {mod}')
        if (ROOT / 'src/foil' / (mod + '.foil')).exists():
            raise ValueError(f'module belongs to core: {mod}')
        data.setdefault(key, {})[mod] = leaf
        default = foil_template(mod) if kind == 'foil' else '- stdlib/runtime\n\n+ tests\n  ^ row[testing/case]\n  []\n'
    elif kind == 'grove':
        if path.suffix != '.grove':
            raise ValueError('Grove files must use .grove')
        units = data.setdefault('grove', [])
        if root:
            parts = root.strip('/').split('/')
            if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', p) for p in parts):
                raise ValueError('invalid Grove root')
        elif len(units) == 1:
            parts = units[0]['root']
        elif not units:
            parts = ['gov', name.replace('-', '_')]
        else:
            raise ValueError('multiple Grove roots; specify --root')
        unit = next((u for u in units if u['root'] == parts), None)
        if unit is None:
            unit = {'root': parts, 'files': []}
            units.append(unit)
        if leaf not in unit['files']:
            if any(leaf in u['files'] for u in units):
                raise ValueError('file already belongs to a different Grove unit')
            unit['files'].append(leaf)
        default = "' Add Grove declarations here.\n"
    elif kind == 'asset':
        if not url or not url.startswith('/') or '?' in url or '#' in url:
            raise ValueError('assets require a canonical --url /path')
        if url in data.get('assets', {}) and data['assets'][url] != leaf:
            raise ValueError(f'asset URL already registered: {url}')
        data.setdefault('assets', {})[url] = leaf
        default = ''
    elif kind == 'support':
        default = ''
    else:
        raise ValueError('unknown file kind')
    data['roots'] = roots(data)
    if path.exists() and content is not None:
        raise ValueError('file already exists; use save-mount to update it')
    # Validate candidate contracts using the same catalog/selector as Eden,
    # before touching either the source or its descriptor.
    validate_candidate(extras, name, data)
    created = False
    try:
        if not path.exists():
            with path.open('xb') as out:
                created = True
                out.write(content if content is not None else default.encode())
        atomic_write(mount.root / 'mount.json', (json.dumps(data, indent=2) + '\n').encode())
    except BaseException:
        if created and path.exists():
            path.unlink()
        raise
    return path


def wire_request(request, port=8679, timeout=600):
    encoded = json.dumps(request, ensure_ascii=False).encode() + b'\n'
    if len(encoded) > 1024 * 1024:
        raise ValueError('wire requests must fit within 1 MiB')
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as sock:
        sock.sendall(encoded)
        with sock.makefile('rb') as incoming:
            return json.load(incoming)


def main(command=None, argv=None):
    command = command or Path(sys.argv[0]).name
    parser = argparse.ArgumentParser(description=f'{command}: manage a Shrine extras mount')
    if command not in ('list-mounts',):
        parser.add_argument('mount')
    if command in ('add-file', 'save-mount'):
        parser.add_argument('file')
        parser.add_argument('--from', dest='source', help='read content from a file, or - for stdin')
    parser.add_argument('--extras-root', type=Path, default=ROOT / 'extras')
    if command == 'create-mount':
        parser.add_argument('--kind', choices=('foil', 'grove'), default='grove')
        parser.add_argument('--dependency', action='append', default=[])
        parser.add_argument('--terminal', action='store_true', help='include an Input/Output terminal entrypoint')
    if command == 'add-file':
        parser.add_argument('--kind', choices=('foil', 'grove', 'test', 'asset', 'support'))
        parser.add_argument('--module')
        parser.add_argument('--root', help='Grove root, e.g. gov/clockwork')
        parser.add_argument('--url', help='asset URL')
    if command in ('save-mount', 'reload-mount', 'show-mount'):
        parser.add_argument('--port', type=int, default=8679)
        parser.add_argument('--timeout', type=float, default=600)
    if command == 'save-mount':
        parser.add_argument('--no-reload', action='store_true')
    if command == 'show-mount':
        parser.add_argument('--live', action='store_true')
    args = parser.parse_args(argv)
    try:
        if hasattr(args, 'mount') and not NAME.fullmatch(args.mount):
            raise ValueError('invalid mount name')
        if hasattr(args, 'port') and not 1 <= args.port <= 65535:
            raise ValueError('--port must be between 1 and 65535')
        if hasattr(args, 'timeout') and args.timeout <= 0:
            raise ValueError('--timeout must be positive')
        extras = args.extras_root.resolve()
        if command == 'create-mount':
            print(create(extras, args.mount, args.kind, args.dependency, args.terminal))
        elif command == 'add-file':
            content = None if args.source is None else (sys.stdin.buffer.read() if args.source == '-' else Path(args.source).read_bytes())
            print(add_file(extras, args.mount, args.file, args.kind, args.module, args.root, args.url, content))
            print('Restart Eden after registration changes; use reload-mount for source edits.')
        elif command == 'list-mounts':
            for name in catalog(extras):
                print(name)
        elif command == 'show-mount' and not args.live:
            selected = select(extras, [args.mount])
            print(json.dumps({'manifest': selected[-1].manifest, 'load_order': [m.name for m in selected]}, indent=2))
        else:
            request = {'op': 'mount/status' if command == 'show-mount' else 'mount/reload', 'mount': args.mount}
            if command == 'save-mount':
                leaf_name(args.file)
                if args.source == '-':
                    text = sys.stdin.read()
                else:
                    path = Path(args.source) if args.source else extras / 'mounts' / args.mount / args.file
                    text = path.read_text()
                status = wire_request({'op': 'mount/status', 'mount': args.mount}, args.port, args.timeout)
                if not status.get('ok'):
                    print(json.dumps(status, indent=2))
                    return 1
                if args.file not in status['files']:
                    raise ValueError('file is not present in the selected server mount; add/register it before starting Eden')
                request = dict(op='mount/save', mount=args.mount, file=args.file, text=text,
                               expected=status['files'][args.file], reload=not args.no_reload)
            result = wire_request(request, args.port, args.timeout)
            print(json.dumps(result, indent=2))
            return 0 if result.get('ok') else 1
        return 0
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
