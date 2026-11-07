"""Process and pipe transport for a saved native Shrine wallet world."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
from plan import ROOT, test_runner


class World:
    def __init__(self, directory, address, rpc, signer_port, signer_token, timeout=120):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.timeout = timeout
        wisp = os.environ.get('WISP') or shutil.which('wisp')
        if not wisp:
            raise RuntimeError('Set WISP or run inside nix develop .#eden')
        fresh = not (self.directory / 'ready').exists()
        if fresh:
            if (self.directory / 'snap').exists():
                raise RuntimeError('Incomplete world: inspect its log before using a new directory')
            test_runner.copy_template(test_runner.stage(wisp, False, 900), self.directory / 'snap')
        self.log = (self.directory / 'runtime.log').open('a')
        self.process = subprocess.Popen(
            [wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
            cwd=self.directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, bufsize=1)
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            if fresh:
                # The compiler consumes a PLAN cord; the Foil entry converts it.
                literal = int.from_bytes(address.encode(), 'little')
                self.process.stdin.write(f'''(#bind source (#module contract-source))
(#bind foil (#module foil-new-env))
(define fresh (foil:source-entry-val ["ethereum_wallet_world" "fresh"] (source:load "ethereum_wallet_world")))
(fresh {literal})
''')
                self.process.stdin.flush()
            self.expect('wallet-config')
            (self.directory / 'ready').touch(mode=0o600)
            self.send({'rpc': rpc, 'signerPort': hex(signer_port), 'signerToken': signer_token})
            self.expect('wallet-ready')
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.log.write(line)
                self.log.flush()
                try:
                    self.lines.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
        finally:
            self.lines.put(EOFError('Wallet runtime stopped; inspect runtime.log'))

    def receive(self):
        try:
            value = self.lines.get(timeout=self.timeout)
        except queue.Empty:
            raise TimeoutError('Wallet runtime timed out; inspect runtime.log') from None
        if isinstance(value, BaseException):
            raise value
        return value

    def expect(self, expected):
        while self.receive() != expected:
            pass

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def request(self, value):
        self.send(value)
        while True:
            reply = self.receive()
            if isinstance(reply, dict) and 'ok' in reply:
                return reply

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=5)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
