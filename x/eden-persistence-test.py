"""Crash/restart regression against the real native world, not a JSON export.

Set WISP and run this file. EDEN_TEST_WORLD may reuse a disposable test world
to avoid recompiling the initial mount publication. Never select a personal world.
"""
import fcntl
import json
import os
import re
from pathlib import Path
import runpy
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
api = runpy.run_path(str(ROOT / 'extras/mounts/flows/client.py'))


@unittest.skipUnless(os.environ.get('WISP'), 'Set WISP for the native crash test')
class NativeWorldTest(unittest.TestCase):
    def test_startup_preflight_failure_preserves_saved_root(self):
        """Real mounted restart: failed route preparation must not checkpoint.

        A valid retry must still run the captured service/artifact even when
        the host source has changed. Only a publication request selects it.
        """
        with tempfile.TemporaryDirectory(prefix='startup-order-', dir=ROOT / '.check') as temporary:
            work = Path(temporary)
            bag = work / 'extras/mounts/contract'
            bag.mkdir(parents=True)
            (bag / 'mount.json').write_text(json.dumps(dict(
                version=1, name='contract', dependencies=[],
                modules={'startup_contract': 'main.foil'},
                roots=[['lib', 'startup_contract']], routes=['/contract'],
                http=dict(module='startup_contract', entry=['startup_contract', 'http']))))
            module = bag / 'main.foil'
            module.write_text('''- http_foot
+ startup_contract
  + http
    \\ files=row[[str nat]] state=namespace
    ^ http_foot/config
    = port (sovereign_peek [state.self 'io 'http] state).fil.fall(myth/new).nat_at(['port] 0)
    ? (eq port 65534) (Seq[http_foot/config] (error (pails/t "startup-contract-route-failure")) http_foot/empty)
    = request
        \\ request=http_foot/request now=nat
        ^ http_foot/action
        | ./reply (http_driver/response 200 (str/cat_all ["captured:" (nat/show port)]))
    | http_foot/add_routes [(http_foot/route "/contract" request)] http_foot/empty
''')
            world = work / 'world'
            runtime = os.environ['WISP']
            inspector = Path(runtime).resolve().parent / 'scry'
            process = None

            def free_port():
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    return sock.getsockname()[1]

            def stop():
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)

            def launch(port, fail=False):
                nonlocal process
                log = world / 'out.log'
                offset = log.stat().st_size if log.exists() else 0
                output = work / ('launcher-' + str(port) + '.log')
                with output.open('w') as stream:
                    process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                        '--world', str(world), '--extras-root', str(work / 'extras'),
                        '--mount', 'contract', '--compiler', 'P1', '--port', str(port),
                        '--startup-timeout', '900'],
                        env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT)),
                        stdout=stream, stderr=stream)
                deadline = time.monotonic() + 900
                while time.monotonic() < deadline:
                    text = log.read_text(errors='replace')[offset:] if log.exists() else ''
                    if fail and process.poll() is not None:
                        self.assertNotEqual(process.returncode, 0, text[-4000:])
                        self.assertIn('startup-contract-route-failure', text)
                        return
                    if not fail and 'Eden: http://' in output.read_text(errors='replace'):
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/contract', timeout=10) as response:
                            self.assertEqual(response.read().decode(), 'captured:' + str(port))
                        return
                    self.assertIsNone(process.poll(), text[-4000:] + output.read_text()[-1000:])
                    time.sleep(.1)
                self.fail('Startup timed out: ' + str(log))

            def root_hash():
                return subprocess.check_output([str(inspector), str(world / 'snap'), 'root'], text=True)

            try:
                launch(free_port())
                stop()
                retained = root_hash()
                # Neither changed host bytes nor a failed reconnect may rewrite
                # the saved program or any namespace/history reachable from it.
                module.write_text('+ deliberately_invalid_host_replacement unknown_name\n')
                launch(65534, fail=True)
                self.assertEqual(root_hash(), retained)
                launch(free_port())
                stop()
                print('Startup preflight failure retained the exact native root; captured-service retry passed.')
            finally:
                stop()

    def test_publication_identity_and_history_survive_native_restart(self):
        sys.path.insert(0, str(ROOT / 'x'))
        import test_runner as runner
        runtime = os.environ['WISP']
        template = runner.stage(runtime, False, 180)
        source = Path(os.environ.get('TEST_SOURCE_ROOT', ROOT / 'src'))
        with tempfile.TemporaryDirectory(prefix='eden-publication-restart-') as temporary:
            work = Path(temporary)
            runner.copy_snapshot(template, work / 'snap')
            for phase, marker in [('initial', 'PUBLICATION-CHECKPOINT-READY'),
                                  ('restored', 'PUBLICATION-RESTART-PASS')]:
                log_path = work / (phase + '.log')
                with log_path.open('w') as log, log_path.open(errors='replace') as observed:
                    process = subprocess.Popen([runtime, '--file-root', str(source),
                        'snap', 'root', '_', 'none', 'verify'], cwd=work,
                        stdin=subprocess.PIPE, stdout=log, stderr=log, text=True)
                    try:
                        if phase == 'initial':
                            process.stdin.write('(#bind fixture (#module foil-publication-tests))\n'
                                                '(fixture:checkpoint-test "initial")\n')
                        process.stdin.close()
                        deadline = time.monotonic() + 300
                        output = ''
                        while True:
                            output = output[-12000:] + observed.read()
                            self.assertIsNone(runner.ERROR.search(output), output[-6000:])
                            if re.search(r'^"' + re.escape(marker) + r':[0-9]+"$', output, re.M):
                                break
                            if process.poll() is not None or time.monotonic() > deadline:
                                import shutil
                                failure = Path(tempfile.mkdtemp(prefix='publication-restart-failure-', dir=ROOT / '.check'))
                                shutil.copytree(work, failure, dirs_exist_ok=True)
                                self.fail(f'{phase}: runtime exit {process.poll()}; retained {failure}\n' + output[-6000:])
                            time.sleep(.1)
                    finally:
                        # Deliberately terminate without a graceful shutdown;
                        # the next phase resumes only the native saved root.
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=10)

    def test_checkpoints_reuse_service_closure(self):
        sys.path.insert(0, str(ROOT / 'x'))
        import test_runner as runner
        runtime = os.environ['WISP']
        template = runner.stage(runtime, False, 180)
        source_root = Path(os.environ.get('TEST_SOURCE_ROOT', ROOT / 'src'))
        with tempfile.TemporaryDirectory(prefix='eden-sharing-') as temporary:
            work = Path(temporary)
            runner.copy_snapshot(template, work / 'snap')
            with (work / 'out.log').open('w') as log:
                process = subprocess.Popen([runtime, '--file-root', str(source_root),
                    'snap', 'root', '_'], cwd=work, stdin=subprocess.PIPE,
                    stdout=log, stderr=log, text=True)
                try:
                    process.stdin.write('''(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(#bind world (#module eden-world))
(define (exercise count)
  (define payload (gen 256 (lambda (i) (Add (Bex (Mul count 1638)) i))))
  (define (serve commit state args) (Ix (Mod (_0 state) 256) payload))
  (define saved [0 (Pin payload)])
  (world:save serve saved)
  (define (step state serial)
    (define next [serial (_1 state)])
    (Seq (world:save serve next) next))
  (lambda (ignored)
    (define result (foldl step saved (gen count (lambda (i) i))))
    (If (Eq (_0 result) (Dec count)) (print "SHARING-COMPLETE")
      (error "Checkpoint lost the updated state"))))
(define continue-sharing (exercise 20))
(Seq continue-sharing (print "SHARING-BASELINE"))
''')
                    process.stdin.flush()
                    deadline = time.monotonic() + 180
                    while 'SHARING-BASELINE' not in (work / 'out.log').read_text(errors='replace'):
                        output = (work / 'out.log').read_text(errors='replace')
                        if process.poll() is not None or '("ERROR"' in output or time.monotonic() > deadline:
                            self.fail(output[-6000:])
                        time.sleep(.02)
                    baseline = (work / 'snap/arena.dat').stat().st_size
                    process.stdin.write('(continue-sharing 0)\n')
                    process.stdin.flush()
                    process.stdin.close()
                    self.assertEqual(0, process.wait(timeout=180))
                    output = (work / 'out.log').read_text(errors='replace')
                    self.assertIn('SHARING-COMPLETE', output)
                    growth = (work / 'snap/arena.dat').stat().st_size - baseline
                    # Twenty scalar changes must not duplicate the unchanged
                    # one-megabyte service closure on every checkpoint.
                    print(f'Native checkpoint growth for 20 updates: {growth} bytes')
                    self.assertLess(growth, 4 * 1024 * 1024, f'Checkpoint growth: {growth} bytes')
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=10)

    def test_unresolved_flow_and_completed_history_survive_crash(self):
        with tempfile.TemporaryDirectory(prefix='eden-restart-') as temporary:
            world = Path(os.environ.get('EDEN_TEST_WORLD', temporary + '/world'))
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            client = api['FlowClient']('http://127.0.0.1:' + str(port), timeout=120)
            process = None
            log = open(temporary + '/launcher.log', 'w+')

            def start():
                nonlocal process
                offset = log.seek(0, os.SEEK_END)
                env = dict(os.environ, _EDEN_NIX_ROOT=str(ROOT))
                selection = [] if (world / 'world.json').exists() else ['--mount', 'flows']
                process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                    '--world', str(world), *selection, '--compiler', 'P1', '--port', str(port)], env=env, stdout=log, stderr=log,
                    start_new_session=True)
                deadline = time.monotonic() + 900
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail(log.read()[-6000:])
                    log.flush()
                    ready = Path(temporary + '/launcher.log').read_text(errors='replace')[offset:]
                    if 'Eden: http://' not in ready:
                        time.sleep(.2)
                        continue
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            return
                    except OSError:
                        time.sleep(.2)
                self.fail('World did not become ready: ' + str(world / 'out.log'))

            def crash():
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
                # Waiting for the launcher does not reap its killed runtime.
                # That process intentionally inherits world.lock; wait for its
                # kernel cleanup before asking a new launcher to take the lock.
                deadline = time.monotonic() + 10
                with (world / 'world.lock').open('a') as lock:
                    while True:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            if time.monotonic() > deadline:
                                self.fail('Crashed runtime did not release world.lock')
                            time.sleep(.02)

            name = 'restart_contract_' + uuid.uuid4().hex[:8]
            page = '/0x11/app/nenex/w/' + name
            controller = page + '/work/maintenance'
            output = page + '_output'
            request = controller + '/work/revision_1'
            hole = output + '/holes/' + name + '/concepts'
            recipe = (ROOT / 'extras/mounts/flows/examples/evidence_resume.semidoc').read_text()
            def values(value):
                # Historical read projections intentionally omit the transport
                # handle for opaque code. Execution below checks its behavior.
                if isinstance(value, dict):
                    return {k: values(v) for k, v in value.items()
                            if not (value.get('type') == 'code' and k == 'reference')}
                if isinstance(value, list):
                    return list(map(values, value))
                return value
            try:
                start()
                source = Path(temporary) / 'readiness.txt'
                source.write_text('Captured evidence before the crash. GATE_OPEN\n')
                manifest = Path(temporary) / 'sources.json'
                manifest.write_text(json.dumps({'readiness': {'path': source.name}}))
                sources = client.import_sources(api['prepare'](temporary, manifest))
                client.author(page, recipe)
                self.assertEqual(recipe, client.source(page))
                definition = client.publish(page, 'evidence_resume')
                client.follow(controller, definition, output, {'sources': sources})
                # The acknowledgement is the durability boundary. No graceful
                # shutdown, export, delay or separate checkpoint command follows.
                saved = {p: client.read(p, care='x') for p in
                         [page, definition, controller + '/cells/work', request, hole]}
                evidence = client.read('/x' + request + '/evidence', care='z')
                # Page requests create and retire native HTTP records. Their
                # ancestor care histories must share old branches, including
                # when EDEN_TEST_WORLD contains large existing care histories.
                arena = world / 'snap/arena.dat'
                growth = []
                for _ in range(10):
                    before = arena.stat().st_size
                    self.assertEqual(recipe, client.source(page))
                    growth.append(arena.stat().st_size - before)
                print(f'Native page-request growth: {growth}')
                self.assertLess(max(growth), 2 * 1024 * 1024,
                                f'Care histories were recopied: {growth}')
                marker = uuid.uuid4().hex
                client.tool('write', records=[{'path': page + '/notes', 'slots': {'text': marker}}])
                crash()
                start()
                self.assertEqual(recipe, client.source(page))
                self.assertEqual(marker, client.read(page + '/notes', care='x')['properties']['/text'])
                locked = subprocess.run([sys.executable, str(ROOT / 'x/eden'), '--world', str(world)],
                    env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT)), capture_output=True, text=True, timeout=20)
                self.assertNotEqual(0, locked.returncode)
                self.assertIn('already running', locked.stderr)
                for p, before in saved.items():
                    self.assertTrue(before['exists'], p)
                    after = client.read(p, care='x')
                    self.assertEqual(before['reference'], after['reference'], p)
                    self.assertEqual(before['properties'], after['properties'], p)
                    historical = client.read(before['reference'], care='x')
                    self.assertTrue(historical['exists'], p)
                    self.assertEqual(values(before['properties']), values(historical['properties']), p)
                self.assertEqual(evidence['children'], client.read('/x' + request + '/evidence', care='z')['children'])
                # Executing the retained operation after a cold restore also
                # proves the saved state retained its actual compiled behavior.
                client.submit_revision(request, ';= Restart contract\n\n  Captured evidence survived.\n',
                                       'Completed against the original frozen evidence after restart.')
                published = client.read(output, care='x')
                self.assertTrue(published['exists'])
                completed = client.read(request, care='x')
                crash()
                start()
                self.assertIn('Captured evidence survived.', client.source(output))
                self.assertEqual(published['reference'], client.read(output, care='x')['reference'])
                self.assertEqual(completed['properties'], client.read(request, care='x')['properties'])
                self.assertEqual('resolved', client.read(hole, care='x')['properties']['/work/status'])
            finally:
                if process is not None and process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=20)
                log.flush()
                (world / 'restart-test-launcher.log').write_text(Path(temporary + '/launcher.log').read_text(errors='replace'))
                log.close()


if __name__ == '__main__':
    unittest.main()
