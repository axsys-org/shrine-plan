#!/usr/bin/env python3
"""Own one disposable, real Grove runtime; never use a live namespace snapshot.

`launch` freezes current backend and asset sources before starting Eden.
`assets` seals the five final frontend assets before the separately run UI test.
`stop` checks the recorded PID/cwd/port ownership before stopping this controller.
All artifacts are retained. No HTTP requests are made by this controller.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from debug_runtime_helpers import startup_failed, verify_asset_build
from namespace_identity import parse_node_identity


ROOT = Path(__file__).resolve().parent.parent
PROTECTED_PORT = 8138
ASSETS = {
    '/style.css': 'foil/style.css',
    '/debug.js': 'foil/debug.js',
    '/debug.css': 'foil/debug.css',
    '/debug-mash.js': 'foil/.debug-assets/mash.js',
    '/debug-components.css': 'foil/.debug-assets/components.css',
}


def startup_source(entry, port, node_number):
    """Select one trusted system and publisher before invoking the real entry."""
    if entry not in ('start-srs', 'start-debug', 'start-debug-srs'):
        raise ValueError('Unknown Grove runtime entry')
    if not isinstance(port, int) or not 1 <= port <= 65535 or port == PROTECTED_PORT:
        raise ValueError('Unsafe Grove runtime port')
    if not isinstance(node_number, int) or node_number <= 0:
        raise ValueError('A nonzero node identity is required')
    return f'''(#bind eden (#module eden))
(#bind bootstrap (#module foil-bootstrap))
(#bind std (#module std))
(#import std)
(define (launch ignored)
  (define (resolve name) [["x" {node_number}] ["ts" "lib"] ["ts" name]])
  (define slot [("x" {node_number}) ("ts" "compiler") ("ts" "artifact")])
  (define system (bootstrap:build-system (Pin eden:{entry}) resolve slot))
  (eden:{entry} ("x" {node_number}) system resolve slot {port}))
(print ("GROVE-LAUNCH-RETURNED" (Try launch 0)))
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def lsof(pid, *options):
    executable = shutil.which('lsof') or ('/usr/sbin/lsof' if Path('/usr/sbin/lsof').is_file() else None)
    if not executable:
        raise RuntimeError('Install lsof to prove runtime ownership; refusing an unchecked process operation.')
    answer = subprocess.run([executable, '-a', '-p', str(pid), *options, '-Fn'],
                            capture_output=True, text=True, timeout=5)
    if answer.returncode:
        raise RuntimeError(f'Cannot prove owned PID {pid}: {answer.stderr.strip()}')
    return answer.stdout.splitlines()


def owned(path, require_ready=True):
    path = path.resolve()
    value = json.loads(path.read_text())
    work = Path(value['work']).resolve()
    if path != work / 'runtime.json' or not work.name.startswith('shrine-grove-runtime-'):
        raise RuntimeError('Not a disposable Grove controller manifest')
    for name in ('pid', 'controllerPid'):
        pid = value[name]
        if not isinstance(pid, int) or pid <= 0:
            raise RuntimeError('Unsafe or protected process identity')
        cwd = [line[1:] for line in lsof(pid, '-d', 'cwd') if line.startswith('n')]
        if cwd != [str(work)]:
            raise RuntimeError(f'PID {pid} is no longer owned by {work}: {cwd}')
    port = value['port']
    if not isinstance(port, int) or port == PROTECTED_PORT or not 1 <= port <= 65535:
        raise RuntimeError('Unsafe or protected port')
    if require_ready:
        if value['state'] != 'ready':
            raise RuntimeError('Disposable runtime is not ready')
        listener = lsof(value['pid'], '-iTCP:' + str(port), '-sTCP:LISTEN')
        if not any(line.startswith('n') and re.search(r':' + str(port) + r'$', line) for line in listener):
            raise RuntimeError('Recorded child does not own the recorded listener')
    return value


def launch(args):
    node_number, node = parse_node_identity(args.node)
    if args.template:
        template = args.template.resolve()
    else:
        import test_runner
        if not args.wisp:
            raise RuntimeError('Set WISP or put wisp on PATH.')
        template = test_runner.stage(args.wisp, False, args.startup_timeout)
    if not args.wisp:
        raise RuntimeError('Set WISP or put wisp on PATH.')
    executable = Path(args.wisp).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError('A working Wisp executable is required')
    for name in ('data.mdb', 'pins.pack'):
        if not (template / name).is_file():
            raise RuntimeError('Missing compiler-only bootstrap: ' + str(template / name))
    work = Path(tempfile.mkdtemp(prefix='shrine-grove-runtime-')).resolve()
    source = work / 'src'
    shutil.copytree(ROOT / 'src', source)
    asset_source = args.assets.resolve()
    if args.entry.startswith('start-debug'):
        verify_asset_build(asset_source / 'foil')
    for relative in ASSETS.values():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset_source / relative, target)
    snapshot = work / 'snap'
    snapshot.mkdir()
    for name in ('data.mdb', 'pins.pack'):
        shutil.copyfile(template / name, snapshot / name)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    if port == PROTECTED_PORT:
        raise RuntimeError('Protected port selected; refusing to launch')
    source_files = {str(path.relative_to(source)): sha(path)
                    for path in sorted(source.rglob('*')) if path.is_file()
                    and path.suffix in ('.rvr', '.foil', '.grove', '.plan')}
    manifest = dict(version=1, id=str(uuid.uuid4()), state='starting', work=str(work),
                    sourceSnapshot=str(source), sourceRepository=str(ROOT),
                    backendSourceFiles=source_files, template=str(template),
                    templateFiles={name: sha(template / name) for name in ('data.mdb', 'pins.pack')},
                    wisp=str(executable), wispSha256=sha(executable), controllerPid=os.getpid(),
                    port=port, origin=f'http://127.0.0.1:{port}', node=node, pid=None,
                    assets=None, startedAt=time.time(), entry='eden:' + args.entry)
    manifest_path = work / 'runtime.json'
    save(manifest_path, manifest)
    os.chdir(work)
    process = None

    def shutdown(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, shutdown)
    started = time.monotonic()
    try:
        with (work / 'out.log').open('w') as output:
            process = subprocess.Popen([str(executable), '--file-root', str(source), 'snap', 'root', '_'],
                cwd=work, stdin=subprocess.PIPE, stdout=output, stderr=output, text=True,
                restore_signals=False)
            manifest['pid'] = process.pid
            save(manifest_path, manifest)
            print(json.dumps(dict(event='compiling', manifest=str(manifest_path),
                                  pid=process.pid, controllerPid=os.getpid(), port=port)), flush=True)
            process.stdin.write(startup_source(args.entry, port, node_number))
            process.stdin.flush()
            deadline = started + args.startup_timeout
            while True:
                log = (work / 'out.log').read_text(errors='replace')
                if process.poll() is not None:
                    raise RuntimeError(f'Owned Wisp exited {process.returncode}: {log[-6000:]}')
                # Module self-tests intentionally print caught lowercase
                # errors. Reject uncaught errors or a failed entry result;
                # a successful entry returns the spawned supervisor actor ID.
                if startup_failed(log, 'GROVE-LAUNCH-RETURNED'):
                    raise RuntimeError(log[-6000:])
                if re.search(r'^"?HTTP foot listening"?$', log, re.MULTILINE):
                    manifest.update(state='ready', startupMs=round((time.monotonic() - started) * 1000, 3))
                    save(manifest_path, manifest)
                    owned(manifest_path)
                    print(json.dumps(dict(event='ready', manifest=str(manifest_path),
                                          origin=manifest['origin'], startupMs=manifest['startupMs'],
                                          assets='pending final seal')), flush=True)
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'Grove startup exceeded its {args.startup_timeout} second deadline')
                time.sleep(.25)
            returncode = process.wait()
            raise RuntimeError(f'Owned runtime stopped unexpectedly with status {returncode}')
    except KeyboardInterrupt:
        manifest['state'] = 'stopping'
    except BaseException as error:
        manifest.update(state='failed', failure=str(error))
        raise
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if manifest['state'] != 'failed':
            manifest['state'] = 'closed'
        # The asset seal is deliberately a separate immutable artifact: it is
        # written after backend startup, including while this process waits.
        seal = work / 'assets.json'
        if seal.is_file():
            manifest.update(json.loads(seal.read_text()))
        manifest.update(closedAt=time.time(), returncode=process.returncode if process else None)
        save(manifest_path, manifest)
        print(json.dumps(dict(event=manifest['state'], manifest=str(manifest_path))), flush=True)


def seal_assets(path, asset_source):
    manifest = owned(path)
    if manifest.get('assets') is not None:
        raise RuntimeError('Assets already sealed; do not alter an active test provenance')
    source = Path(manifest['sourceSnapshot'])
    build = verify_asset_build(asset_source / 'foil') if manifest.get('entry', '').startswith('eden:start-debug') else None
    copied = {}
    for url, relative in ASSETS.items():
        original, target = asset_source / relative, source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        copied[url] = dict(path=relative, sha256=sha(target), bytes=target.stat().st_size)
    sealed = dict(assets=copied, assetBuild=build, assetsSealedAt=time.time())
    seal = Path(manifest['work']) / 'assets.json'
    if seal.exists():
        raise RuntimeError('Immutable asset provenance already exists')
    save(seal, sealed)
    manifest.update(sealed)
    save(path.resolve(), manifest)
    print(json.dumps(dict(event='assets-sealed', manifest=str(path.resolve()), assets=copied)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('launch')
    start.add_argument('--template', type=Path,
                       help='Compiler-only bootstrap; omitted stages the content-keyed compiler, never a live snapshot')
    start.add_argument('--assets', type=Path, default=ROOT / '.check/debug-assets',
                       help='Directory containing foil/ assets from build-debug.mjs')
    start.add_argument('--wisp', default=os.environ.get('WISP') or shutil.which('wisp'),
                       help='Wisp executable (defaults to WISP or PATH)')
    start.add_argument('--entry', choices=('start-srs', 'start-debug', 'start-debug-srs'), default='start-debug')
    start.add_argument('--node', default='0x11',
                       help='Explicit node identity; disposable previews default to fixture identity 0x11')
    start.add_argument('--startup-timeout', type=int, default=900)
    assets = commands.add_parser('assets')
    assets.add_argument('manifest', type=Path)
    assets.add_argument('--source', type=Path, default=ROOT / 'src',
                        help='Prepared asset root containing foil/; leaves live preview assets unchanged')
    for command in ('stop', 'verify'):
        commands.add_parser(command).add_argument('manifest', type=Path)
    args = parser.parse_args()
    if args.command == 'launch':
        launch(args)
    elif args.command == 'assets':
        seal_assets(args.manifest, args.source.resolve())
    elif args.command == 'stop':
        manifest = owned(args.manifest)
        os.kill(manifest['controllerPid'], signal.SIGTERM)
        print('Requested shutdown of this manifest-owned controller only.', flush=True)
    else:
        print(json.dumps(owned(args.manifest)), flush=True)


if __name__ == '__main__':
    main()
