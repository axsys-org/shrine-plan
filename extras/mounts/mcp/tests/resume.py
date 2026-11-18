"""Boot, write, stop, boot, read: a world kept with `x/eden --world DIR` resumes with its records.

Unlike the other tests here this one boots its own worlds (two of them, one after the other, never two at
once), so it needs the checkout and a runtime, not a running world:

    WISP=<runtime> _EDEN_NIX_ROOT=$PWD python3 -I extras/mounts/mcp/tests/resume.py --port 8450

It prints the save cost it measured: single-record write latency, pack growth per event, and the resume time.
"""
import sys
from pathlib import Path
# This folder holds http.py; keep it off the path so the stdlib's http loads.
sys.path[:] = [entry for entry in sys.path
               if Path(entry or '.').resolve() != Path(__file__).resolve().parent]
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[4]


class World:
    def __init__(self, directory, port, log, timeout, extras=None):
        self.directory, self.port, self.timeout = directory, port, timeout
        self.extras = Path(extras) if extras else ROOT / 'extras'
        self.base = f'http://127.0.0.1:{port}'
        self.log = log
        self.process = None
        self.seq = 0
        self.lines = []

    def boot(self):
        command = [sys.executable, str(ROOT / 'x/eden'), '--mount', 'mcp', '--mount', 'probe',
                   '--extras-root', str(self.extras), '--port', str(self.port), '--world', str(self.directory)]
        env = dict(os.environ, _EDEN_NIX_ROOT=str(ROOT))
        t0 = time.perf_counter()
        self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, env=env, text=True)
        deadline = time.monotonic() + self.timeout
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f'x/eden exited with {self.process.returncode}; see {self.log.name}')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=.2):
                    break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f'the world did not listen within {self.timeout}s; see {self.log.name}')
            time.sleep(.25)
        # The MCP mount answers once its routes are up; the first call warms it.
        for _ in range(200):
            try:
                self.read('/')
                break
            except Exception:
                time.sleep(.25)
        return time.perf_counter() - t0

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process = None

    def tool(self, name, **arguments):
        self.seq += 1
        body = json.dumps(dict(jsonrpc='2.0', id=self.seq, method='tools/call',
                               params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(self.base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            reply = json.load(response)
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=self.timeout) as response:
            return response.read().decode()

    def read(self, path, care='y'):
        # A cell's answer is read at care x with the node in its path, as the product test does.
        return self.tool('read', path=path, care=care)

    def write(self, records):
        return self.tool('write', records=records, who='resume-test')

    def pack(self):
        # The snapshot the runtime keeps: one arena.dat since the 2026-10 enki, data.mdb and pins.pack before it.
        return sum(f.stat().st_size for f in (self.directory / 'snap').iterdir() if f.is_file())


def check(port, directory, timeout, count=20, node='0x11'):
    checks = []

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    log = (directory.parent / (directory.name + '.log')).open('w')
    world = World(directory, port, log, timeout)
    try:
        boot = world.boot()
        print(f'fresh boot into {directory}: {boot:.1f} s', flush=True)
        world.write([{'path': '/user/keep/warm', 'slots': {'n': 0}}])
        before = world.pack()
        times = []
        for i in range(count):
            t0 = time.perf_counter()
            last = world.write([{'path': f'/user/keep/r{i}', 'slots': {'n': i, 'tag': 'first'}}])
            times.append(time.perf_counter() - t0)
        times.sort()
        growth = (world.pack() - before) / count / 1024
        print(f'{count} single-record writes: median {1000 * times[count // 2]:.1f} ms, '
              f'max {1000 * times[-1]:.1f} ms; snapshot growth {growth:.0f} KiB per event', flush=True)
        world.write([{'path': f'/user/keep/b{i}', 'slots': {'n': i}} for i in range(100)])
        # A reference's path carries the node, as a read's reference does.
        weft = {'type': 'reference', 'path': f'/{node}/weft/stdlib/count', 'care': 'x',
                'case': int(world.read('/weft/stdlib/count')['reference'].split('/')[3])}
        tack = {'type': 'reference', 'path': f'/{node}/user/keep', 'care': 'y', 'case': 0}
        cell = world.write([{'path': '/user/views/kept', 'slots': {'sys/weft': weft, 'sys/tack': tack}}])
        epoch_before = cell['epoch']
        expect('writes before the stop land', world.read('/user/keep/r3')['properties'].get('/n'), '3')
        expect('the launcher says this world is kept', world.read('/agent/launcher/world')['properties'].get('/kept'), 'true')
        expect('a cell counts the folder before the stop', world.read(f'/x/{node}/user/views/kept', 'x')['properties'].get('/count'), '121')
        scanned = int(world.read('/io/fs/mcp')['properties'].get('/sys/epoch') or 0)
        world.stop()
        print('stopped', flush=True)
        resume = world.boot()
        print(f'resume: {resume:.1f} s', flush=True)
        expect('the records are back after the reboot', world.read('/user/keep/r3')['properties'].get('/n'), '3')
        expect('the resume scanned the mounts again', int(world.read('/io/fs/mcp')['properties'].get('/sys/epoch') or 0), scanned + 1)
        expect('the batch is back', world.read('/user/keep/b99')['properties'].get('/n'), '99')
        expect('the cell still counts every record', world.read(f'/x/{node}/user/views/kept', 'x')['properties'].get('/count'), '121')
        expect('the world record is written again on resume', world.read('/agent/launcher/world')['properties'].get('/kept'), 'true')
        history = world.tool('history', after=epoch_before - 1)
        expect('history continues from the saved epoch', history['events'][0]['epoch'], epoch_before)
        # the remount is a few events of its own (a scan, a batch and a status per mount), all under /io/fs
        resumed_at = json.loads(world.get(f'/probe/read?path=/{node}'))['epoch']
        expect('the remount spent its events on the mounts, nothing else', (resumed_at > epoch_before, all(t.startswith(f'/{node}/io/fs') or t == f'/{node}' or t == f'/{node}/io' for e in world.tool('history', after=epoch_before)['events'] for t in e['touched'])), (True, True))
        after = world.write([{'path': '/user/keep/again', 'slots': {'n': 1}}])
        expect('the next epoch continues the count', after['epoch'], resumed_at + 1)
        expect('the cell is live after the resume', world.read(f'/x/{node}/user/views/kept', 'x')['properties'].get('/count'), '122')
        t0 = time.perf_counter()
        for i in range(count):
            world.write([{'path': f'/user/keep/s{i}', 'slots': {'n': i, 'tag': 'second'}}])
        print(f'{count} writes after the resume: {1000 * (time.perf_counter() - t0) / count:.1f} ms each', flush=True)
        world.stop()
        world.boot()
        expect('the second generation survives too', world.read('/user/keep/s7')['properties'].get('/n'), '7')
        expect('and so does the first', world.read('/user/keep/again')['properties'].get('/n'), '1')
    finally:
        world.stop()
        log.close()
    # A kept directory that saw nothing but its boot still resumes: the launcher's own world record is the
    # first event of every kept world, so the saved root is never the boot repl. (The launcher keeps its probe
    # for a directory whose boot was cut before that write.)
    empty = directory.parent / (directory.name + '-empty')
    log2 = (directory.parent / (empty.name + '.log')).open('w')
    world = World(empty, port, log2, timeout)
    try:
        world.boot()
        world.stop()
        world.boot()
        expect('a kept world that saw only its boot resumes', world.read('/weft/stdlib/count')['exists'], True)
        expect('and the launcher said so', 'Resuming the world kept in' in Path(log2.name).read_text(), True)
    finally:
        world.stop()
        log2.close()
    # A resumed world runs the mounts as the checkout has them now: a change to a mount's code between the stop
    # and the resume is published on the resume, and its routes serve it. The mounts are copied so the change
    # touches nothing in the checkout.
    extras = directory.parent / (directory.name + '-extras')
    for name in ('mcp', 'probe'):
        shutil.copytree(ROOT / 'extras/mounts' / name, extras / 'mounts' / name)
    changed = directory.parent / (directory.name + '-changed')
    log3 = (directory.parent / (changed.name + '.log')).open('w')
    world = World(changed, port, log3, timeout, extras=extras)
    try:
        world.boot()
        world.write([{'path': '/user/keep/one', 'slots': {'n': 1}}])
        expect('the probe answers as written', world.get(f'/probe/ok?path=/{node}'), 'ok')
        world.stop()
        source = extras / 'mounts/probe/probe.foil'
        source.write_text(source.read_text().replace('(http_driver/response 200 "ok")', '(http_driver/response 200 "ok again")'))
        world.boot()
        expect('a mount changed between the stop and the resume serves its new code', world.get(f'/probe/ok?path=/{node}'), 'ok again')
        expect('over the records as they were saved', world.read('/user/keep/one')['properties'].get('/n'), '1')
    finally:
        world.stop()
        log3.close()
    print(f'resume: {len(checks)} checks passed', flush=True)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--port', type=int, default=8450)
    parser.add_argument('--world', type=Path, help='the directory to keep the world in (default: a fresh temporary one)')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    directory = args.world.resolve() if args.world else Path(tempfile.mkdtemp(prefix='shrine-resume-'))
    if directory.exists() and any(directory.iterdir()):
        raise SystemExit(f'{directory} is not empty; the test wants a fresh directory')
    check(args.port, directory, args.timeout)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
