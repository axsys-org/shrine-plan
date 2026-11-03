#!/usr/bin/env python3
"""Terminal device for native Foil Doom. No gameplay or rendering runs here."""
import argparse
import hashlib
import json
import os
import re
import statistics
from pathlib import Path
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KEYS = 'wsadqefur'


def positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return n


def recv_exact(connection, size):
    out = bytearray()
    while len(out) < size:
        chunk = connection.recv(size - len(out))
        if not chunk:
            raise RuntimeError('The Foil engine closed its connection')
        out.extend(chunk)
    return bytes(out)


def mask(keys):
    unknown = set(keys) - set(KEYS)
    if unknown:
        raise ValueError('unknown keys: ' + ''.join(sorted(unknown)))
    return sum(1 << KEYS.index(k) for k in set(keys))


def ppm(path, frame, palette, width, height):
    pixels = b''.join(palette[frame[x * height + y] * 3:frame[x * height + y] * 3 + 3]
                      for y in range(height) for x in range(width))
    Path(path).write_bytes(f'P6\n{width} {height}\n255\n'.encode() + pixels)


def paint(frame, palette, width, height, status):
    columns, rows = shutil.get_terminal_size((96, 40))
    dw = max(1, min(width, columns))
    dh = max(2, min(height, (rows - 2) * 2))
    dh -= dh % 2
    colors = [';'.join(map(str, palette[i:i + 3])) for i in range(0, 768, 3)]
    output = ['\x1b[H']
    for y in range(0, dh, 2):
        fg = bg = -1
        for x in range(dw):
            sx = x * width // dw
            top = frame[sx * height + y * height // dh]
            bottom = frame[sx * height + (y + 1) * height // dh]
            if top != fg:
                output.append(f'\x1b[38;2;{colors[top]}m')
                fg = top
            if bottom != bg:
                output.append(f'\x1b[48;2;{colors[bottom]}m')
                bg = bottom
            output.append('▀')
        output.append('\x1b[0m\x1b[K\r\n')
    output.append(status[:columns] + '\x1b[K\r\n')
    output.append('WASD/arrows move/turn · Q/E strafe · F fire · Space use · R run · N restart · Esc quit'[:columns] + '\x1b[K')
    sys.stdout.write(''.join(output))
    sys.stdout.flush()


class Keyboard:
    def __init__(self):
        self.held = {}
        self.running = False
        self.pending = b''
        self.escape_at = None
        self.quit = False
        self.reset = False

    def read(self):
        now = time.monotonic()
        if select.select([sys.stdin], [], [], 0)[0]:
            data = os.read(sys.stdin.fileno(), 4096)
            if not data:
                self.quit = True
                return 0
            self.pending += data
        while self.pending:
            c = self.pending[0]
            if c == 27:
                if len(self.pending) < 3 and self.pending in (b'\x1b', b'\x1b[', b'\x1bO'):
                    if self.escape_at is None:
                        self.escape_at = now
                    if now - self.escape_at > .08:
                        self.quit = True
                        self.pending = b''
                    break
                if self.pending[:2] in (b'\x1b[', b'\x1bO') and self.pending[2:3] in (b'A', b'B', b'C', b'D'):
                    key = dict(A='w', B='s', C='d', D='a')[chr(self.pending[2])]
                    self.pending = self.pending[3:]
                    self.escape_at = None
                else:
                    self.quit = True
                    self.pending = b''
                    break
            else:
                self.pending = self.pending[1:]
                self.escape_at = None
                if c in (3, 4):
                    self.quit = True
                    break
                key = chr(c).lower()
                if key == 'n':
                    self.reset = True
                    continue
                if key == 'r':
                    self.running = not self.running
                    continue
                if key == ' ' or key == '\r':
                    key = 'u'
                if key not in KEYS:
                    continue
                if 65 <= c <= 90:
                    self.held['r'] = now + .2
            self.held[key] = now + (.16 if self.held.get(key, 0) > now else .35)
        keys = ''.join(k for k, until in self.held.items() if until > now)
        if self.running and 'r' not in keys:
            keys += 'r'
        if self.reset:
            self.reset = False
            return 512
        return mask(keys)


def launch(args):
    startup = time.monotonic()
    runtime = os.environ.get('WISP') or shutil.which('wisp')
    if not runtime:
        raise RuntimeError('Wisp is required. Run inside `nix develop .#eden`, or set WISP=/path/to/wisp.')
    sys.path.insert(0, str(ROOT / 'x'))
    import test_runner
    template = test_runner.stage(runtime, False, args.timeout)
    work = Path(tempfile.mkdtemp(prefix='shrine-doom-'))
    source = work / 'src'
    shutil.copytree(ROOT / 'src', source)
    target = source / 'foil/apps/doom'
    target.mkdir(parents=True, exist_ok=True)
    for file in HERE.glob('*.foil'):
        shutil.copy2(file, target / file.name)
    shutil.copy2(HERE / 'boot.rvr', source / 'reaver/doom-boot.rvr')
    shutil.copy2(args.wad, source / 'doom.wad')
    test_runner.copy_template(template, work / 'snap')
    listener = socket.socket()
    try:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
    except OSError:
        listener.close()
        shutil.rmtree(work)
        raise
    listener.settimeout(.25)
    port = listener.getsockname()[1]
    commands = ('(#bind opt (#module plangrm))\n(Install opt:compileP6)\n' if args.compiler == 'P6' else '') + f'(#bind doom (#module doom-boot))\n(doom:run {port} {args.width} {args.height} {int(args.profile is not None or args.trace is not None)} {int(args.renderer == "reference")})\n'
    log = (work / 'engine.log').open('wb')
    runtime_args = [runtime, '--file-root', str(source)]
    if args.trace:
        runtime_args += ['--profile-json', str(args.trace.resolve())]
    process = subprocess.Popen(runtime_args + ['snap', 'root', '_'],
                               cwd=work, stdin=subprocess.PIPE, stdout=log, stderr=log,
                               start_new_session=True)
    process.stdin.write(commands.encode())
    process.stdin.close()
    connection = None
    try:
        deadline = time.monotonic() + args.timeout
        print('shrine-doom: compiling Foil and loading E1M1…', file=sys.stderr)
        while connection is None:
            with (work / 'engine.log').open('rb') as reader:
                reader.seek(max(0, reader.seek(0, 2) - 8192))
                tail = reader.read().decode('utf-8', 'replace')
            if '\n("ERROR"' in tail:
                raise RuntimeError('Native engine error:\n' + tail[-2000:])
            if process.poll() is not None:
                raise RuntimeError(f'Engine exited during startup ({process.returncode})')
            if time.monotonic() > deadline:
                raise TimeoutError('Engine startup timed out')
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                pass
        connection.settimeout(args.timeout)
        palette = recv_exact(connection, 768)
        print(f'shrine-doom: ready after {time.monotonic() - startup:.2f}s', file=sys.stderr)
        return work, process, connection, palette, log
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait()
        log.close()
        if connection:
            connection.close()
        print(f'Engine log: {work / "engine.log"}', file=sys.stderr)
        raise
    finally:
        listener.close()


PHASES = ('step', 'visibility', 'raster', 'pack', 'write')


def parse_profile(log):
    samples = []
    for match in re.finditer(r'DOOM_PROFILE (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)', log):
        values = list(map(int, match.groups()))
        samples.append(dict(tic=values[0], **dict(zip(PHASES, (n / 1e6 for n in values[1:])))))
    return samples


def distribution(values):
    if not values:
        return None
    ordered = sorted(values)
    return dict(mean_ms=statistics.mean(values), median_ms=statistics.median(values),
                p95_ms=ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)],
                min_ms=ordered[0], max_ms=ordered[-1])


def summarize_profile(samples, roundtrip):
    return dict(count=len(samples), phases={name: distribution([s[name] for s in samples]) for name in PHASES},
                roundtrip=distribution(roundtrip))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=positive, default=96)
    parser.add_argument('--height', type=positive, default=60)
    parser.add_argument('--frames', type=positive, help='Stop after N game tics')
    parser.add_argument('--keys', default='', help='Keys held during a headless run: wsadqefur')
    parser.add_argument('--script', type=Path, help='JSON array of {keys, tics} replay segments')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--ppm', type=Path, help='Save the final native frame as a PPM image')
    parser.add_argument('--state', type=Path, help='Save the final HUD state and frame hash as JSON')
    parser.add_argument('--wad', type=Path, default=HERE / 'e1m1.wad')
    parser.add_argument('--timeout', type=positive, default=300)
    parser.add_argument('--compiler', choices=('P6', 'none'), default='P6')
    parser.add_argument('--profile', type=Path, help='Write per-tic native phase timings and warm summaries as JSON')
    parser.add_argument('--warmup', type=int, default=10, help='Initial frames excluded from benchmark summaries (default 10)')
    parser.add_argument('--renderer', choices=('spans', 'reference'), default='spans')
    parser.add_argument('--trace', type=Path, help='Optional Wisp Chrome trace (requires a profiling-capable runtime)')
    parser.add_argument('--keep-work', action='store_true', help='Keep staged sources and engine log')
    args = parser.parse_args(argv)
    if args.warmup < 0:
        parser.error('--warmup must be nonnegative')
    if not (16 <= args.width <= 320 and 16 <= args.height <= 200):
        parser.error('resolution must be 16..320 by 16..200')
    if not args.wad.is_file():
        parser.error(f'WAD not found: {args.wad}')
    try:
        default_mask = mask(args.keys)
        replay = []
        if args.script:
            for part in json.loads(args.script.read_text()):
                count = part['tics']
                if not isinstance(count, int) or not 1 <= count <= 100000:
                    raise ValueError('script tics must be 1..100000')
                replay.extend([mask(part['keys'])] * count)
            if not replay:
                raise ValueError('script must contain at least one segment')
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    interactive = not args.headless and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive and args.frames is None and not replay:
        args.frames = 1
    limit = args.frames or (len(replay) if replay else float('inf'))
    work, process, connection, palette, log = launch(args)
    saved_terminal = None
    failed = True
    keyboard = Keyboard()
    frames = 0
    timings = []
    frame_hashes = []
    states = []
    started = time.monotonic()
    try:
        if interactive:
            import termios
            import tty
            saved_terminal = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
            sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[2J')
            sys.stdout.flush()
        while frames < limit:
            tic_start = time.monotonic()
            command = replay[frames] if frames < len(replay) else (keyboard.read() if interactive else default_mask)
            if keyboard.quit:
                break
            connection.sendall(struct.pack('<H', command))
            header = struct.unpack('<10I', recv_exact(connection, 40))
            frame = recv_exact(connection, args.width * args.height)
            frames += 1
            tic, health, armor, ammo, kills, items, flags = header[:7]
            elapsed = time.monotonic() - tic_start
            timings.append(elapsed * 1000)
            if args.profile:
                frame_hashes.append(hashlib.sha256(frame).hexdigest())
                states.append(header)
            if interactive:
                status = (f'SHRINE DOOM  HP {health}  ARM {armor}  AMMO {ammo}  KILLS {kills}  '
                          f'TIC {tic}  {elapsed * 1000:.0f}ms')
                if flags & 1:
                    status = 'YOU DIED — Space to respawn | ' + status
                if flags & 2:
                    status = 'LEVEL COMPLETE — N to restart | ' + status
                paint(frame, palette, args.width, args.height, status)
                time.sleep(max(0, 1 / 35 - (time.monotonic() - tic_start)))
        if frames:
            if args.ppm:
                ppm(args.ppm, frame, palette, args.width, args.height)
            if args.state:
                state = dict(zip(('tic', 'health', 'armor', 'ammo', 'kills', 'items', 'flags', 'x', 'y', 'angle'), header))
                for coordinate in ('x', 'y'):
                    value = state[coordinate]
                    state[coordinate] = value // 2 if value % 2 == 0 else -(value + 1) // 2
                state.update(width=args.width, height=args.height, frames=frames,
                             sha256=hashlib.sha256(frame).hexdigest(),
                             mean_ms=sum(timings) / len(timings), min_ms=min(timings), max_ms=max(timings))
                args.state.write_text(json.dumps(state, indent=2) + '\n')
        connection.sendall(struct.pack('<H', 1024))
        process.wait(timeout=10)
        if process.returncode:
            raise RuntimeError(f'Engine exited with status {process.returncode}')
        if args.profile:
            phases = parse_profile((work / 'engine.log').read_text(errors='replace'))
            if len(phases) != frames:
                raise RuntimeError(f'Expected {frames} timing records, got {len(phases)}')
            result = dict(renderer=args.renderer, width=args.width, height=args.height,
                          warmup=args.warmup, frames=frames, samples=phases, roundtrip_ms=timings,
                          frame_hashes=frame_hashes, states=states,
                          summary=summarize_profile(phases[args.warmup:], timings[args.warmup:]))
            args.profile.write_text(json.dumps(result, indent=2) + '\n')
        failed = False
    finally:
        if saved_terminal is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved_terminal)
            sys.stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l')
            sys.stdout.flush()
        connection.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        log.close()
        if failed or args.keep_work:
            print(f'Engine log: {work / "engine.log"}', file=sys.stderr)
        else:
            shutil.rmtree(work)
    print(f'shrine-doom: {frames} tics in {time.monotonic() - started:.2f}s', file=sys.stderr)


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print(f'shrine-doom: {error}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
