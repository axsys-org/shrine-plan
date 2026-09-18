"""Resolve versioned flat mount bags. This module has no application policy."""
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import hmac
import secrets
import shutil
import socketserver
import threading
import tempfile
import os


def runtime_literal(value):
    """Encode descriptor strings as bytes, independent of Reaver's cord lexer."""
    if isinstance(value, str):
        data = value.encode('utf-8')
        if b'\0' in data:
            raise ValueError('Mount arguments cannot contain NUL')
        chunks = [str(int.from_bytes(data[i:i + 256], 'little'))
                  for i in range(0, len(data), 256)]
        return '(strcat [' + ' '.join(chunks) + '])'
    if isinstance(value, (tuple, list)):
        return '[' + ' '.join(runtime_literal(item) for item in value) + ']'
    if isinstance(value, int):
        return str(value)
    raise ValueError(f'Unsupported mount argument: {type(value).__name__}')


@dataclass(frozen=True)
class Mount:
    name: str
    root: Path
    manifest: dict


def catalog(root):
    folder = Path(root).resolve() / 'mounts'
    result = {}
    for path in sorted(folder.glob('*/mount.json')):
        data = json.loads(path.read_text())
        name = data.get('name')
        if data.get('version') != 1 or name != path.parent.name or not re.fullmatch(r'[a-z][a-z0-9_-]*', name or ''):
            raise ValueError(f'Invalid mount descriptor: {path}')
        if not isinstance(data.get('dependencies', []), list) or any(
                not isinstance(dep, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', dep)
                for dep in data.get('dependencies', [])):
            raise ValueError(f'{name}: invalid dependencies')
        for route in data.get('routes', []):
            if not isinstance(route, str) or not route.startswith('/') or '?' in route or '#' in route:
                raise ValueError(f'{name}: invalid route prefix')
        for key in ('modules', 'assets'):
            if not isinstance(data.get(key, {}), dict):
                raise ValueError(f'{name}: {key} must be an object')
        if any(not re.fullmatch(r'[A-Za-z0-9_/-]+', module) or '..' in module
               for module in data.get('modules', {})):
            raise ValueError(f'{name}: invalid logical module name')
        leaves = list(data.get('modules', {}).values()) + list(data.get('assets', {}).values())
        for unit in data.get('grove', []):
            leaves.extend(unit['files'])
        for leaf in leaves:
            if not isinstance(leaf, str) or Path(leaf).name != leaf or leaf in ('.', '..'):
                raise ValueError(f'{name}: mount files must be flat: {leaf!r}')
        for key in ('activate', 'http', 'start'):
            hook = data.get(key)
            if hook and (hook['module'] not in data.get('modules', {}) or not hook.get('entry')):
                raise ValueError(f'{name}: invalid {key} entrypoint')
        result[name] = Mount(name, path.parent, data)
    return result


def select(root, names):
    available = catalog(root)
    active, order = [], []
    def visit(name):
        if name in active:
            raise ValueError('Cyclic mount dependency: ' + ' -> '.join(active + [name]))
        if any(m.name == name for m in order):
            return
        if name not in available:
            raise ValueError(f'Unknown mount: {name}')
        active.append(name)
        for dependency in available[name].manifest.get('dependencies', []):
            visit(dependency)
        active.pop()
        order.append(available[name])
    for name in names:
        visit(name)
    modules, roots, routes = {}, {}, {}
    core = Path(__file__).resolve().parent.parent / 'src/foil'
    reserved = {str(p.relative_to(core).with_suffix('')) for p in core.rglob('*.foil')}
    inspection = None
    for mount in order:
        data = mount.manifest
        for name in data.get('modules', {}):
            if name in reserved:
                raise ValueError(f'{mount.name}: module {name} belongs to core')
            if name in modules:
                raise ValueError(f'Module {name} is owned by both {modules[name]} and {mount.name}')
            modules[name] = mount.name
        locations = [['lib', name] for name in data.get('modules', {})]
        locations += [unit['root'] for unit in data.get('grove', [])]
        if data.get('roots', locations) != locations:
            raise ValueError(f'{mount.name}: publication roots do not match declared outputs')
        for location in locations:
            key = tuple(location)
            for old, owner in roots.items():
                if key[:len(old)] == old or old[:len(key)] == key:
                    raise ValueError(f'Conflicting publication roots: {owner} and {mount.name}: {key}')
            roots[key] = mount.name
        for route in data.get('routes', []):
            if route in routes:
                raise ValueError(f'Duplicate HTTP route {route}: {routes[route]} and {mount.name}')
            routes[route] = mount.name
        if data.get('inspection'):
            if inspection:
                raise ValueError(f'Duplicate inspection renderer: {inspection} and {mount.name}')
            inspection = mount.name
    return order


def hook_module(mount):
    name = mount.manifest.get('host')
    if not name:
        return None
    if Path(name).name != name:
        raise ValueError(f'{mount.name}: host entrypoint must be in the flat bag')
    spec = importlib.util.spec_from_file_location('eden_extra_' + mount.name, mount.root / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(mounts, work, check, cleanup, context):
    """Host hooks own their build/companion lifecycle through an ExitStack."""
    result = []
    for mount in mounts:
        module = hook_module(mount)
        args = []
        folder = mount.root
        if module and hasattr(module, 'prepare'):
            folder, args = module.prepare(mount.root, work / mount.name, check, cleanup, context)
        for leaf in mount.manifest.get('modules', {}).values():
            if not (Path(folder) / leaf).is_file():
                raise ValueError(f'{mount.name}: missing module source {leaf}')
        result.append((mount, Path(folder).resolve(), args, module))
    return result


def runtime_specs(prepared, source_root):
    """Allocate scan bags in the runtime file root; never overlay core modules."""
    directory = source_root / 'mounts'
    directory.mkdir()
    specs = []
    selected = {mount.name: mount for mount, _, _, _ in prepared}
    def dependencies(mount):
        result = []
        def visit(name):
            for parent in selected[name].manifest.get('dependencies', []):
                visit(parent)
            if name != mount.name and name not in result:
                result.append(name)
        visit(mount.name)
        return result
    for mount, folder, args, _ in prepared:
        # A request-scoped scanner refreshes this bag from the live checkout.
        (directory / mount.name).mkdir()
        data = mount.manifest
        def hook(key):
            value = data.get(key)
            return [value['module'], value['entry']] if value else []
        specs.append([mount.name, 'mounts/' + mount.name,
                      json.dumps(data, sort_keys=True),
                      list(data.get('modules', {}).items()),
                      [[u['root'], u['files'], u.get('prelude', 'grove_role_runtime')]
                       for u in data.get('grove', [])],
                      hook('activate'), hook('http'), hook('start'), args,
                      int(bool(data.get('inspection'))),
                      dependencies(mount),
                      list(data.get('assets', {}).values()), data.get('routes', [])])
    return specs


def nix_root(core):
    command = ['nix', '--extra-experimental-features', 'nix-command flakes',
               'eval', '--raw', '--no-update-lock-file', f'{core}#extrasSource']
    return Path(subprocess.check_output(command, text=True).strip())


class ScanBridge:
    """Expose only selected bags; refresh a complete captured scan on demand.

    Enki disallows symlinks escaping its file root. This adapter copies a fresh
    scan into that root for each explicit request, never into core source dirs.
    The runtime imports those bytes into namespace records before compiling.
    """
    def __init__(self, prepared, source_root):
        self.roots = {'mounts/' + m.name: folder for m, folder, _, _ in prepared}
        self.originals = {'mounts/' + m.name: m.root for m, _, _, _ in prepared}
        self.scanners = {'mounts/' + m.name: (m, folder, module) for m, folder, _, module in prepared}
        self.destination = Path(source_root)
        self.manifests = {'mounts/' + m.name: m.manifest for m, _, _, _ in prepared}
        self.token = secrets.token_hex(32)
        owner = self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(30)
                token = self.rfile.readline(66).rstrip(b'\n')
                name = self.rfile.readline(256).rstrip(b'\n').decode('utf-8')
                if not hmac.compare_digest(token, owner.token.encode()):
                    self.wfile.write(b'Unauthorized scan')
                    return
                try:
                    owner.refresh(name)
                    self.wfile.write(b'OK')
                except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
                    self.wfile.write(str(error).encode()[:4096])
        self.server = socketserver.TCPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def refresh(self, name):
        if name not in self.roots:
            raise ValueError('Unknown source mount')
        root = self.roots[name]
        if hasattr(self, 'manifests'):
            current = json.loads((self.originals[name] / 'mount.json').read_text())
            keys = ('version', 'name', 'dependencies', 'modules', 'grove', 'assets', 'roots',
                    'activate', 'http', 'start', 'host', 'routes', 'inspection')
            if any(current.get(key) != self.manifests[name].get(key) for key in keys):
                raise ValueError('Mount descriptor changed; restart Eden to change registrations')
            mount, prepared, module = self.scanners[name]
            if module and hasattr(module, 'scan'):
                module.scan(mount.root, prepared)
        destination = self.destination / name
        stage = Path(tempfile.mkdtemp(prefix='.scan-', dir=destination.parent))
        try:
            sources = [self.originals[name], root] if hasattr(self, 'originals') else [root]
            for folder in dict.fromkeys(sources):
                for entry in sorted(folder.iterdir()):
                    if entry.is_file():
                        shutil.copyfile(entry, stage / entry.name)
            if not (stage / 'mount.json').is_file():
                raise ValueError('Missing mount descriptor')
            old = destination.with_name('.previous-' + destination.name)
            destination.rename(old)
            try:
                stage.rename(destination)
            except BaseException:
                old.rename(destination)
                raise
            shutil.rmtree(old)
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
