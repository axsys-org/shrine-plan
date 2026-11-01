"""Kill a kept world, restart it, and check that nothing it acknowledged was lost.

Writes go through the probe mount; the MCP mount only reads old versions by
their references. Set WISP and run this file. It boots its own disposable world
and prints what it measured: write latency, disk per event, restart time and the
runtime's memory before and after a restart.
"""
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
NODE = '0x11'
HOME = f'/{NODE}/user/kill_test'
WRITES = 300
VERSIONS = 40  # past the history's sealing span
BURST_SECONDS = 2.0
RESETS = 30


class World:
    def __init__(self, directory, port):
        self.directory, self.port = directory, port
        self.base = f'http://127.0.0.1:{port}'
        self.launcher = self.wisp = None
        self.boots = 0

    def boot(self):
        self.boots += 1
        log = self.directory.parent / f'launcher-{self.boots}.log'
        started = time.monotonic()
        with log.open('w') as stream:
            self.launcher = subprocess.Popen(
                [sys.executable, str(ROOT / 'x/eden'), '--world', str(self.directory),
                 '--extras-root', str(ROOT / 'extras'), '--mount', 'mcp', '--mount', 'probe',
                 '--port', str(self.port), '--startup-timeout', '1500'],
                env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT)), stdout=stream, stderr=stream)
        deadline = started + 1600
        while time.monotonic() < deadline:
            if self.launcher.poll() is not None:
                raise RuntimeError(f'launcher exited {self.launcher.returncode}: {log.read_text()[-3000:]}')
            if 'Eden: http://' in log.read_text(errors='replace'):
                try:
                    self.read('/' + NODE)
                    break
                except (OSError, ValueError, http.client.HTTPException):
                    pass
            time.sleep(.05)
        else:
            raise RuntimeError(f'Startup timed out: {log}')
        seconds = time.monotonic() - started
        children = subprocess.run(['pgrep', '-P', str(self.launcher.pid), '-x', 'wisp'],
                                  capture_output=True, text=True).stdout.split()
        self.wisp = int(children[0])
        return seconds

    def kill(self):
        os.kill(self.wisp, signal.SIGKILL)
        self.launcher.wait(timeout=60)

    def stop(self):
        if self.launcher and self.launcher.poll() is None:
            self.launcher.terminate()
            try:
                self.launcher.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.launcher.kill()
                self.launcher.wait()

    def request(self, method, target, body=None):
        data = body.encode() if body is not None else None
        request = urllib.request.Request(self.base + target, data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as reply:
                return reply.status, reply.read().decode(errors='replace')
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(errors='replace')

    def read(self, path):
        status, body = self.request('GET', '/probe/read?path=' + urllib.parse.quote(path, safe='/'))
        return status, json.loads(body)

    def put(self, kind, path, n):
        return self.request('POST', '/probe/' + kind, urllib.parse.urlencode({'path': path, 'n': str(n)}))[0]

    def tool(self, name, **arguments):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                           'params': {'name': 'mcp/' + name, 'arguments': arguments}}).encode()
        request = urllib.request.Request(self.base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=60) as reply:
            result = json.load(reply)['result']
        if result.get('isError'):
            raise RuntimeError(str(result)[:400])
        return result['structuredContent']

    def disk(self):
        return (self.directory / 'snap/arena.dat').stat().st_blocks * 512

    def footprint_mb(self):
        # macOS only; a number to read, not a condition of the test.
        if not shutil.which('vmmap'):
            return None
        out = subprocess.run(['vmmap', '-summary', str(self.wisp)], capture_output=True, text=True).stdout
        found = re.search(r'Physical footprint:\s+([\d.]+)([KMG])', out)
        return round(float(found.group(1)) * {'K': 1 / 1024, 'M': 1, 'G': 1024}[found.group(2)]) if found else None


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@unittest.skipUnless(os.environ.get('WISP'), 'Set WISP for the native kill test')
class KillTest(unittest.TestCase):
    def test_a_killed_world_keeps_what_it_acknowledged(self):
        inspector = str(Path(os.environ['WISP']).resolve().parent / 'scry')
        measured = {}
        (ROOT / '.check').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='eden-kill-', dir=ROOT / '.check') as temporary:
            world = World(Path(temporary) / 'world', free_port())
            snap = str(world.directory / 'snap')
            try:
                measured['first_boot_s'] = round(world.boot(), 1)
                measured['footprint_after_first_boot_mb'] = world.footprint_mb()

                durations = []
                for i in range(WRITES):
                    started = time.perf_counter()
                    self.assertEqual(world.put('make', f'{HOME}/r{i}', i), 200)
                    durations.append(time.perf_counter() - started)
                    if i == 49:
                        early = world.disk()
                measured['write_ms_median'] = round(statistics.median(durations) * 1000, 1)
                measured['write_ms_first_50'] = round(statistics.median(durations[:50]) * 1000, 1)
                measured['write_ms_last_50'] = round(statistics.median(durations[-50:]) * 1000, 1)
                measured['disk_kb_per_event'] = round((world.disk() - early) / (WRITES - 50) / 1024, 1)

                self.assertEqual(world.put('make', f'{HOME}/hot', 0), 200)
                versions = {}
                for n in range(1, VERSIONS + 1):
                    self.assertEqual(world.put('write', f'{HOME}/hot', n), 200)
                    if n % 7 == 0 or n == VERSIONS:
                        versions[n] = world.tool('read', path=f'{HOME}/hot', care='x')['reference']
                epoch = world.read('/' + NODE)[1]['epoch']
                root = subprocess.check_output([inspector, snap, 'root'], text=True)

                # Right after an acknowledged write.
                world.kill()
                self.assertEqual(subprocess.check_output([inspector, snap, 'root'], text=True), root)
                subprocess.check_output([inspector, snap, 'verify'], text=True)
                measured['restart_s'] = round(world.boot(), 2)
                measured['footprint_after_restart_mb'] = world.footprint_mb()
                self.assertEqual(world.read('/' + NODE)[1]['epoch'], epoch)
                for i in range(WRITES):
                    status, record = world.read(f'{HOME}/r{i}')
                    self.assertEqual((status, record.get('n')), (200, str(i)))
                self.assertEqual(world.read(f'{HOME}/hot')[1].get('n'), str(VERSIONS))
                for n, reference in versions.items():
                    self.assertEqual(world.tool('read', path=reference, care='x')['properties']['/n'], str(n))
                measured['footprint_after_reading_all_mb'] = world.footprint_mb()
                self.assertEqual(world.put('make', f'{HOME}/after', 1), 200)
                self.assertEqual(world.read('/' + NODE)[1]['epoch'], epoch + 1)

                # Stalled clients wait alone.
                stalled = [socket.create_connection(('127.0.0.1', world.port)) for _ in range(8)]
                partial = socket.create_connection(('127.0.0.1', world.port))
                partial.sendall(b'POST /probe/make HTTP/1.1\r\nContent-Length: 400\r\n\r\npath=')
                stalled.append(partial)
                time.sleep(.3)
                started = time.perf_counter()
                self.assertEqual(world.read('/' + NODE)[0], 200)
                measured['read_ms_beside_stalled_clients'] = round((time.perf_counter() - started) * 1000, 1)
                for sock in stalled:
                    sock.close()

                # In the middle of a burst: whatever was acknowledged stays.
                acknowledged = []
                killer = threading.Timer(BURST_SECONDS, world.kill)
                killer.start()
                while True:
                    try:
                        if world.put('make', f'{HOME}/burst/b{len(acknowledged)}', 1) != 200:
                            break
                    except (OSError, http.client.HTTPException):
                        break
                    acknowledged.append(len(acknowledged))
                killer.join()
                self.assertGreater(len(acknowledged), 0)
                measured['burst_acknowledged'] = len(acknowledged)
                world.boot()
                for i in acknowledged:
                    self.assertEqual(world.read(f'{HOME}/burst/b{i}')[0], 200)

                # A peer that resets its connection does not take the world down.
                for _ in range(RESETS):
                    sock = socket.create_connection(('127.0.0.1', world.port))
                    sock.sendall(f'GET /probe/read?path=/{NODE} HTTP/1.1\r\nHost: x\r\n\r\n'.encode())
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                    sock.close()
                time.sleep(.5)
                self.assertIsNone(world.launcher.poll())
                self.assertEqual(world.read('/' + NODE)[0], 200)
            finally:
                world.stop()
                print(json.dumps(measured), flush=True)


if __name__ == '__main__':
    unittest.main()
