"""Deterministic transport tests; no Codex install or account needed."""
import socket
import sys
import tempfile
import threading
import time
import unittest
from codex_bridge import Bridge


class BridgeTests(unittest.TestCase):
    def bridge(self, source, stderr=None):
        bridge = Bridge([sys.executable, '-u', '-c', source], stderr=stderr,
                        auth_timeout=.2).start()
        self.addCleanup(bridge.close)
        return bridge

    def connect(self, bridge):
        client = socket.create_connection(('127.0.0.1', bridge.port), timeout=3)
        self.addCleanup(client.close)
        client.sendall(bridge.token.encode() + b'\n')
        return client

    def test_authentication_precedes_process_start(self):
        bridge = self.bridge('import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())')
        with socket.create_connection(('127.0.0.1', bridge.port), timeout=2) as bad:
            bad.sendall(b'wrong\n')
            self.assertEqual(b'', bad.recv(1))
        self.assertIsNone(bridge.process)
        client = self.connect(bridge)
        client.sendall(b'hello')
        deadline = time.monotonic() + 2
        while bridge.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertIsNotNone(bridge.process)

    def test_fragmentation_coalescing_and_stderr(self):
        with tempfile.TemporaryFile() as err:
            bridge = self.bridge('import sys\nprint("diagnostic", file=sys.stderr)\n'
                                 'for line in sys.stdin.buffer:\n'
                                 ' sys.stdout.buffer.write(line[:2]); sys.stdout.buffer.flush()\n'
                                 ' sys.stdout.buffer.write(line[2:]); sys.stdout.buffer.flush()\n', err)
            client = self.connect(bridge)
            parts = [b'{"id":', b'1}\n{"id":2}\n']
            for part in parts:
                client.sendall(part)
            expected = b''.join(parts)
            result = bytearray()
            while len(result) < len(expected):
                result.extend(client.recv(1024))
            self.assertEqual(expected, result)
            bridge.close()
            err.seek(0)
            self.assertEqual(b'diagnostic\n', err.read())
            self.assertIsNotNone(bridge.process.returncode)

    def test_exit_drains_final_output(self):
        bridge = self.bridge('import sys; print("final"); sys.exit(3)')
        client = self.connect(bridge)
        data = bytearray()
        while chunk := client.recv(1024):
            data.extend(chunk)
        self.assertEqual(b'final\n', data)
        bridge.thread.join(3)
        self.assertFalse(bridge.thread.is_alive())
        self.assertEqual(3, bridge.process.returncode)

    def test_disconnect_reaps_child(self):
        bridge = self.bridge('import time; time.sleep(60)')
        client = self.connect(bridge)
        deadline = time.monotonic() + 2
        while bridge.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        client.close()
        bridge.thread.join(3)
        self.assertFalse(bridge.thread.is_alive())
        self.assertIsNotNone(bridge.process.returncode)

    def test_backpressure_preserves_large_stream(self):
        bridge = self.bridge('import os\nwhile True:\n data=os.read(0,65536)\n if not data: break\n os.write(1,data)\n')
        client = self.connect(bridge)
        payload = bytes(range(256)) * 12288
        errors = []
        def write():
            try:
                client.sendall(payload)
            except Exception as exc:
                errors.append(exc)
        writer = threading.Thread(target=write)
        writer.start()
        result = bytearray()
        while len(result) < len(payload):
            chunk = client.recv(65536)
            self.assertTrue(chunk)
            result.extend(chunk)
        writer.join(3)
        self.assertFalse(writer.is_alive())
        self.assertFalse(errors)
        self.assertEqual(payload, result)

    def test_missing_executable_propagates_eof(self):
        bridge = Bridge(['/does/not/exist'], auth_timeout=.2).start()
        self.addCleanup(bridge.close)
        client = self.connect(bridge)
        self.assertEqual(b'', client.recv(1))
        bridge.thread.join(3)
        self.assertIsInstance(bridge.error, FileNotFoundError)


if __name__ == '__main__':
    unittest.main()
