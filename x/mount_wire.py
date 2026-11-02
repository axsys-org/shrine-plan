"""Mount wire operations and the trusted Eden supervisor bridge."""
import hashlib
import json
import hmac
import secrets
import socket
import threading
import time

from mount_tools import atomic_write, leaf_name


class MountWire:
    def __init__(self, compiler, mounts, live=None, timeout=600):
        self.compiler = compiler
        self.mounts = {m.name: m for m in mounts}
        self.live = live
        self.timeout = timeout
        self.lock = threading.Lock()

    def checked(self, name):
        if not isinstance(name, str) or name not in self.mounts:
            raise ValueError('mount is not selected in this server')
        mount = self.mounts[name]
        current = json.loads((mount.root / 'mount.json').read_text())
        if current != mount.manifest:
            return mount, {'ok': False, 'mount': name, 'restart_required': True,
                           'error': 'Mount descriptor changed; restart Eden/the wire server to change registrations.'}
        return mount, None

    def status(self, mount):
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(mount.root.iterdir())
                 if p.is_file() and not p.is_symlink() and p.name != 'mount.json' and not p.name.startswith('.')}
        result = {'ok': True, 'mount': mount.name, 'live': self.live is not None, 'files': files}
        if self.live:
            result['status'] = self.live(mount.name, False)
        return result

    def reload(self, name):
        if not self.live:
            return {'ok': False, 'mount': name, 'error': 'Live reload requires x/eden --wire-port. Use --no-reload to save with x/repl.'}
        # Selected mounts are in dependency order. Refresh consumers after their
        # dependencies so they compile against the new published definitions.
        touched, results = {name}, []
        for mount in self.mounts.values():
            if mount.name != name and not touched.intersection(mount.manifest.get('dependencies', [])):
                continue
            touched.add(mount.name)
            _, error = self.checked(mount.name)
            if error:
                return dict(error, reloaded=results)
            before = self.live(mount.name, False)
            self.live(mount.name, True)
            deadline = time.monotonic() + self.timeout
            while True:
                status = self.live(mount.name, False)
                if status['epoch'] > before['epoch']:
                    results.append(dict(mount=mount.name, **status))
                    if not status['ready']:
                        return {'ok': False, 'mount': name, 'reloaded': results,
                                'error': 'Publication failed; the previous successful publication is retained.'}
                    break
                if time.monotonic() >= deadline:
                    return {'ok': False, 'mount': name, 'reloaded': results,
                            'error': 'Timed out waiting for mount publication; inspect mount status before retrying.'}
                time.sleep(.05)
        return {'ok': True, 'mount': name, 'reloaded': results}

    def request(self, request):
        if not isinstance(request, dict) or request.get('op') not in ('mount/status', 'mount/save', 'mount/reload'):
            return self.compiler.request(request)
        with self.lock:
            mount, error = self.checked(request.get('mount'))
            if error:
                return error
            op = request['op']
            if op == 'mount/status':
                return self.status(mount)
            if op == 'mount/reload':
                return self.reload(mount.name)
            leaf = request.get('file')
            if not isinstance(leaf, str):
                raise ValueError('file must be a filename')
            leaf_name(leaf)
            path = mount.root / leaf
            if not path.is_file() or path.is_symlink() or leaf.startswith('.'):
                raise ValueError('save only accepts existing, non-symlink mount files')
            text = request.get('text')
            if not isinstance(text, str) or '\0' in text:
                raise ValueError('text must be UTF-8 text without NUL')
            reload = request.get('reload', True)
            if not isinstance(reload, bool):
                raise ValueError('reload must be a boolean')
            if reload and not self.live:
                return self.reload(mount.name)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if request.get('expected') != digest:
                return {'ok': False, 'mount': mount.name, 'conflict': True,
                        'error': 'File changed since it was read; fetch mount/status before saving again.'}
            atomic_write(path, text.encode())
            result = {'ok': True, 'mount': mount.name}
            if reload:
                try:
                    result = self.reload(mount.name)
                except (ValueError, RuntimeError, OSError) as error:
                    result = {'ok': False, 'mount': mount.name, 'error': str(error)}
            return dict(result, saved=leaf, sha256=hashlib.sha256(text.encode()).hexdigest())


class EdenMountBridge:
    """Private actor control connection, independent of the runtime's stdin."""
    def __init__(self, timeout):
        self.timeout = timeout
        self.token = secrets.token_hex(32)
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(4)
        self.port = self.listener.getsockname()[1]
        self.connection = None
        self.incoming = None
        self.lock = threading.Lock()
        self.failed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.failed = True
        if self.connection:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
        if self.incoming:
            self.incoming.close()
        self.listener.close()

    def connect(self):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            self.listener.settimeout(max(.01, deadline - time.monotonic()))
            connection, _ = self.listener.accept()
            connection.settimeout(min(2, max(.01, deadline - time.monotonic())))
            incoming = connection.makefile('rb')
            try:
                token = incoming.readline(66).rstrip(b'\n')
                if hmac.compare_digest(token, self.token.encode()):
                    connection.settimeout(self.timeout)
                    self.connection, self.incoming = connection, incoming
                    return
            except OSError:
                pass
            incoming.close()
            connection.close()
        raise RuntimeError('Eden control actor did not connect')

    def __call__(self, name, rescan):
        with self.lock:
            if self.failed:
                raise RuntimeError('Eden control connection stopped; restart Eden')
            if not isinstance(name, str) or not name or '\n' in name or len(name) > 256:
                raise ValueError('invalid control mount name')
            try:
                if self.connection is None:
                    self.connect()
                self.connection.sendall(f'{name}\n{int(bool(rescan))}\n'.encode())
                reply = self.incoming.readline(1024 * 1024 + 1)
                if not reply.endswith(b'\n') or len(reply) > 1024 * 1024:
                    raise RuntimeError('Incomplete Eden control response')
                result = json.loads(reply)
            except (OSError, ValueError, RuntimeError) as error:
                self.close()
                raise RuntimeError(f'Eden control failed: {error}; inspect Eden log') from error
            if not result.get('ok'):
                raise RuntimeError(result.get('error', 'Eden mount request failed'))
            return result
