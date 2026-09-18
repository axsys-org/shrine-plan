"""Private, single-client byte transport for the native Foil Codex driver."""
import hmac
import os
import secrets
import selectors
import socket
import subprocess
import threading


class Bridge:
    """Start Codex only after authentication; never interpret its protocol."""

    def __init__(self, command, *, stderr=None, auth_timeout=10):
        self.command = list(command)
        self.stderr = stderr
        self.auth_timeout = auth_timeout
        self.token = secrets.token_hex(32)
        self.listener = socket.socket()
        try:
            self.listener.bind(('127.0.0.1', 0))
        except OSError:
            self.listener.close()
            raise
        self.listener.listen(1)
        self.listener.settimeout(.2)
        self.port = self.listener.getsockname()[1]
        self.stop = threading.Event()
        self.client = None
        self.process = None
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def _authenticate(self, client):
        client.settimeout(self.auth_timeout)
        token = bytearray()
        while len(token) <= 64:
            byte = client.recv(1)
            if byte == b'\n':
                return hmac.compare_digest(bytes(token), self.token.encode('ascii'))
            if not byte:
                return False
            token.extend(byte)
        return False

    def _run(self):
        try:
            while not self.stop.is_set():
                try:
                    client, _ = self.listener.accept()
                except socket.timeout:
                    continue
                try:
                    accepted = self._authenticate(client)
                except (OSError, TimeoutError):
                    accepted = False
                if not accepted:
                    client.close()
                    continue
                self.client = client
                break
            if self.client is None or self.stop.is_set():
                return
            self.listener.close()
            self.process = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self.stderr, bufsize=0, start_new_session=True)
            self._proxy()
        except Exception as exc:
            if not self.stop.is_set():
                self.error = exc
        finally:
            self._cleanup()

    def _proxy(self):
        """Bounded nonblocking buffers preserve bytes and propagate backpressure."""
        client, proc = self.client, self.process
        client.setblocking(False)
        os.set_blocking(proc.stdout.fileno(), False)
        os.set_blocking(proc.stdin.fileno(), False)
        to_child, to_client = bytearray(), bytearray()
        limit = 1024 * 1024
        server_eof = False
        with selectors.DefaultSelector() as selector:
            while not self.stop.is_set():
                if server_eof and not to_client:
                    return
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                flags = (selectors.EVENT_READ if not server_eof and len(to_child) < limit else 0)
                if to_client:
                    flags |= selectors.EVENT_WRITE
                if flags:
                    selector.register(client, flags, 'client')
                if not server_eof and len(to_client) < limit:
                    selector.register(proc.stdout, selectors.EVENT_READ, 'stdout')
                if to_child and not server_eof:
                    selector.register(proc.stdin, selectors.EVENT_WRITE, 'stdin')
                for key, mask in selector.select(.2):
                    if key.data == 'client':
                        if mask & selectors.EVENT_READ:
                            data = client.recv(min(65536, limit - len(to_child)))
                            if not data:
                                return
                            to_child.extend(data)
                        if mask & selectors.EVENT_WRITE:
                            count = client.send(to_client)
                            del to_client[:count]
                    elif key.data == 'stdin':
                        if server_eof:
                            continue
                        count = os.write(proc.stdin.fileno(), to_child)
                        del to_child[:count]
                    else:
                        data = os.read(proc.stdout.fileno(), min(65536, limit - len(to_client)))
                        if not data:
                            # Keep draining under normal backpressure before EOF.
                            server_eof = True
                            to_child.clear()
                            continue
                        to_client.extend(data)

    def _cleanup(self):
        if self.client:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.client.close()
        self.listener.close()
        if self.process:
            import signal
            # Reap an exited child before signaling its process group.
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
            for stream in (self.process.stdin, self.process.stdout):
                stream.close()

    def close(self):
        self.stop.set()
        if self.client:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.listener.close()
        self.thread.join(timeout=self.auth_timeout + 3)
        if self.thread.is_alive():
            raise RuntimeError('Codex bridge did not shut down')
