"""Loopback editor service backed by a persistent, isolated Reaver compiler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

from eden_mounts import runtime_literal, select
from test_runner import ROOT, copy_template, stage
from foil_lint import text_diagnostics

MAX_REQUEST = 1024 * 1024
MODULE = re.compile(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\Z')
OPS = {'compile', 'lint', 'eval', 'describe', 'complete', 'doctest'}


def validate(request):
    if not isinstance(request, dict):
        raise ValueError('request must be an object')
    op = request.get('op')
    if op == 'ping':
        return
    if not isinstance(op, str) or op not in OPS:
        raise ValueError('unknown operation')
    if not isinstance(request.get('module'), str) or not MODULE.fullmatch(request['module']):
        raise ValueError('module must be a directory-qualified Foil module name')
    for key in ('text', 'name', 'prefix'):
        if key in request and (not isinstance(request[key], str) or '\0' in request[key]):
            raise ValueError(f'{key} must be text without NUL')
    for key in {'eval': ['text'], 'describe': ['name']}.get(op, []):
        if not request.get(key):
            raise ValueError(f'{op} requires {key}')


class Compiler:
    def __init__(self, wisp, source_root=ROOT / 'src', mounts=(), timeout=1800, compiler='P6', overlays=None):
        self.timeout = timeout
        self.lock = threading.Lock()
        self.source_root = Path(source_root).resolve()
        self.mounts = mounts
        self.overlays = overlays or {}
        self.work = Path(tempfile.mkdtemp(prefix='foil-wire-'))
        self.process = None
        self.log = None
        self.temp_sources = self.work / 'src'
        self.temp_sources.mkdir()
        self.files = {}
        self.messages = queue.Queue()
        try:
            template = stage(wisp, False, timeout)
            copy_template(template, self.work / 'snap')
            for folder in ('reaver', 'plan', 'spec'):
                target = self.source_root / folder
                if target.exists():
                    shutil.copytree(target, self.temp_sources / folder)
            self.refresh()
            self.log = (self.work / 'out.log').open('w')
            self.process = subprocess.Popen(
                [wisp, '--file-root', str(self.temp_sources), 'snap', 'root', '_'],
                cwd=self.work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
            self.reader = threading.Thread(target=self.read_output, daemon=True)
            self.reader.start()
            install = '' if compiler == 'none' else f'(#bind opt (#module plangrm))\n(Install opt:compile{compiler})\n'
            self.send(install + '(#bind wire (#module foil-wire))\n'
                      '(#bind std (#module std))\n(#import std)\n'
                      '(#bind reef (#module reef))\n(#import reef)\n'
                      '(define wire-state 0)\n(Seq (print "FOIL-WIRE-READY") 0)\n')
            self.wait('"FOIL-WIRE-READY"')
        except BaseException:
            self.close()
            raise

    def read_output(self):
        for line in self.process.stdout:
            self.log.write(line)
            self.log.flush()
            if line.strip() in ('"FOIL-WIRE-READY"', '"FOIL-WIRE-DONE"'):
                self.messages.put(line.strip())
            elif line.startswith('("ERROR"'):
                self.messages.put('runtime error')
        self.messages.put('runtime exited')

    def send(self, text):
        self.process.stdin.write(text)
        self.process.stdin.flush()

    def wait(self, expected):
        try:
            result = self.messages.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise RuntimeError(f'compiler timed out; restart the service (log: {self.work}/out.log)')
        if result != expected:
            self.close()
            raise RuntimeError(f'{result}; inspect {self.work}/out.log')

    def sources(self):
        files = {p.relative_to(self.source_root / 'foil').as_posix(): p
                 for p in (self.source_root / 'foil').rglob('*.foil')}
        files['modules.tsv'] = self.source_root / 'foil/modules.tsv'
        for mount in self.mounts:
            for key in ('modules', 'tests'):
                for mod, rel in mount.manifest.get(key, {}).items():
                    if not MODULE.fullmatch(mod):
                        raise ValueError(f'invalid mounted module: {mod}')
                    leaf = mod + '.foil'
                    folder = Path(self.overlays.get(mount.name, mount.root)).resolve()
                    if not (folder / rel).is_file():
                        folder = mount.root.resolve()
                    path = (folder / rel).resolve()
                    if not path.is_relative_to(folder):
                        raise ValueError(f'mounted source escapes its root: {rel}')
                    if leaf in files and files[leaf] != path:
                        raise ValueError(f'duplicate mounted module: {mod}')
                    files[leaf] = path
        return files

    def refresh(self):
        self.origins = self.sources()
        contents = {leaf: path.read_bytes() for leaf, path in self.origins.items()}
        stamps = {leaf: hashlib.sha256(data).digest() for leaf, data in contents.items()}
        changed = stamps != self.files
        for leaf, data in contents.items():
            if stamps[leaf] != self.files.get(leaf):
                dest = self.temp_sources / 'foil' / leaf
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        for leaf in self.files.keys() - stamps.keys():
            (self.temp_sources / 'foil' / leaf).unlink()
        self.files = stamps
        return changed

    def request(self, request):
        validate(request)
        if request['op'] == 'ping':
            return {'ok': self.process is not None and self.process.poll() is None,
                    'server': 'foil-wire', 'v': 1}
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError('compiler stopped; restart the service')
            changed = self.refresh()
            if changed:
                self.send('(define wire-state 0)\n')
            if request['module'] + '.foil' not in self.origins:
                return {'ok': False, 'error': 'module source not found: ' + request['module']}
            result = self.execute(request)
            if request['op'] in ('compile', 'lint'):
                lint = (result if request['op'] == 'lint' else
                        self.execute(dict(op='lint', module=request['module'])))
                findings = [dict(d, source='foil-lint') for d in lint.get('diags', [])]
                text = (self.temp_sources / 'foil' / (request['module'] + '.foil')).read_text()
                findings += [dict(d, module=request['module'], source='foil-lint')
                             for d in text_diagnostics(text)]
                if not lint.get('ok') and not lint.get('diags'):
                    findings.append(dict(module=request['module'], source='foil-lint',
                                         line=1, col=1, level='error',
                                         msg=lint.get('error', 'lint failed')))
                result['diags'] = ((result.get('diags', []) if request['op'] == 'compile' else [])
                                   + findings)
                result['lint_ok'] = bool(lint.get('ok'))
            if result.get('ok') and request['op'] == 'describe':
                path = self.origins.get(result.get('module', '') + '.foil')
                if path:
                    result['file'] = str(path)
            return result

    def execute(self, request, state='wire-state'):
        args = ' '.join(runtime_literal(request.get(key, ''))
                        for key in ('op', 'module', 'text', 'name', 'prefix'))
        self.send(f'(Seq (define wire-result (wire:handle {state} {args})) 0)\n'
                  '(Seq (define wire-state (_0 wire-result)) 0)\n'
                  '(Seq (write-text-file ".wire-response.json" (_1 wire-result)) '
                  '(Seq (print "FOIL-WIRE-DONE") 0))\n')
        self.wait('"FOIL-WIRE-DONE"')
        return json.loads((self.temp_sources / '.wire-response.json').read_text())

    def close(self):
        if self.process:
            if self.process.poll() is None:
                # Evaluated Foil may spawn actors; own the entire worker group.
                import signal
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait()
            if hasattr(self, 'reader') and self.reader is not threading.current_thread():
                self.reader.join(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
        if self.log and not self.log.closed:
            self.log.close()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port, compiler):
        self.compiler = compiler
        super().__init__(('127.0.0.1', port), Handler)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            line = self.rfile.readline(MAX_REQUEST + 1)
            if len(line) > MAX_REQUEST or not line.endswith(b'\n'):
                raise ValueError('expected a newline-terminated JSON request of at most 1 MiB')
            request = json.loads(line)
            result = self.server.compiler.request(request)
        except (ValueError, RuntimeError, OSError) as error:
            result = {'ok': False, 'error': str(error)}
        try:
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode() + b'\n')
        except OSError:
            pass  # client disconnected during compilation


def main():
    from mount_wire import MountWire
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8679)
    parser.add_argument('--mount', action='append', default=[])
    parser.add_argument('--extras-root', type=Path, default=ROOT / 'extras')
    parser.add_argument('--source-root', type=Path, default=ROOT / 'src')
    parser.add_argument('--wisp', default=os.environ.get('WISP') or shutil.which('wisp'))
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--compiler', choices=['none', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6'], default='P6')
    parser.add_argument('--module', default='stdlib/runtime')
    parser.add_argument('--no-repl', action='store_true')
    parser.add_argument('--reset', action='store_true', help='accepted for x/foil compatibility; every session starts fresh')
    args = parser.parse_args()
    if not args.wisp:
        parser.error('wisp is not on PATH; run in nix develop or set WISP')
    if not 1 <= args.port <= 65535 or args.timeout <= 0:
        parser.error('port must be 1..65535 and timeout must be positive')
    compiler = None
    try:
        compiler = Compiler(args.wisp, args.source_root, select(args.extras_root, args.mount), args.timeout, args.compiler)
        with Server(args.port, MountWire(compiler, compiler.mounts)) as server:
            print(f'Foil wire: 127.0.0.1:{server.server_address[1]}; log: {compiler.work}/out.log', flush=True)
            if args.no_repl or not sys.stdin.isatty():
                server.serve_forever()
            else:
                threading.Thread(target=server.serve_forever, daemon=True).start()
                print('Expressions evaluate in the selected module. :m MODULE, :c, :t, :q')
                try:
                    while True:
                        text = input(args.module + '> ')
                        if text == ':q':
                            break
                        if text.startswith(':m '):
                            args.module = text[3:].strip()
                            continue
                        op = {':c': 'compile', ':t': 'doctest'}.get(text, 'eval')
                        print(json.dumps(compiler.request({'op': op, 'module': args.module, 'text': text}), indent=2))
                finally:
                    server.shutdown()
    except (KeyboardInterrupt, EOFError):
        pass
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    finally:
        if compiler:
            compiler.close()


if __name__ == '__main__':
    main()
