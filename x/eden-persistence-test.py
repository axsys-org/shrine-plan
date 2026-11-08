"""Crash/restart regressions in disposable native snapshots. Set WISP to run."""
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
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
api = runpy.run_path(str(ROOT / 'extras/mounts/flows/tests/client.py'))


@unittest.skipUnless(os.environ.get('WISP'), 'Set WISP for the native crash test')
class NativeSnapshotTest(unittest.TestCase):
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
                host='host.py', start=dict(module='startup_contract', entry=['startup_contract', 'start']),
                http=dict(module='startup_contract', entry=['startup_contract', 'http']))))
            (bag / 'host.py').write_text('''import os
def prepare(root, work, check, cleanup, context):
    return root, [os.environ['EDEN_TEST_SESSION']]
''')
            module = bag / 'main.foil'
            module.write_text('''- http_foot
+ startup_contract
  + start
    \\ server=nat arguments=row[str]
    ^ nat
    ; (Print (str/cat_all ["SESSION-HOOK " arguments.at(0) (str/from_atom 10)]))
    server
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
            snapshot = work / 'snap'
            runtime = os.environ['WISP']
            inspector = Path(runtime).resolve().parent / 'scry'
            process = None
            hook_sessions = []

            def free_port():
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    return sock.getsockname()[1]

            def stop():
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)

            def launch(port, fail=False, selection=None):
                nonlocal process
                output = work / ('launcher-' + str(port) + '.log')
                hook_session = uuid.uuid4().hex
                with output.open('w') as stream:
                    process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                        '--snapshot', str(snapshot), '--extras-root', str(work / 'extras'),
                        *(['--mount', 'contract'] if selection is None else selection), '--compiler', 'P1', '--port', str(port),
                        '--startup-timeout', '900'],
                        env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT), EDEN_TEST_SESSION=hook_session),
                        stdout=stream, stderr=stream)
                deadline = time.monotonic() + 900
                last_probe_error = None
                while time.monotonic() < deadline:
                    text = output.read_text(errors='replace')
                    if fail and process.poll() is not None:
                        self.assertNotEqual(process.returncode, 0, text[-4000:])
                        self.assertIn('startup-contract-route-failure' if selection is None else 'Snapshot mount descriptor', text)
                        return
                    self.assertIsNone(process.poll(), text[-4000:] + output.read_text()[-1000:])
                    if not fail and 'Eden: http://' in output.read_text(errors='replace'):
                        # TCP readiness can precede cold compilation of the
                        # listener/routes. HTTP readiness shares the startup
                        # budget; each probe still has a bounded timeout.
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        try:
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/contract',
                                                        timeout=min(10, remaining)) as response:
                                body = response.read().decode()
                        except urllib.error.HTTPError:
                            raise
                        except (TimeoutError, urllib.error.URLError) as error:
                            last_probe_error = error
                        else:
                            self.assertEqual(body, 'captured:' + str(port))
                            native_log = Path(re.search(r'\. Log: (.+)', text).group(1)).read_text(errors='replace')
                            self.assertIn('SESSION-HOOK ' + hook_session, native_log)
                            for old in hook_sessions:
                                self.assertNotIn('SESSION-HOOK ' + old, native_log)
                            hook_sessions.append(hook_session)
                            return
                    time.sleep(.1)
                self.fail(f'Startup timed out: {output}; last HTTP probe: {last_probe_error}')

            def root_hash():
                return subprocess.check_output([str(inspector), str(snapshot), 'root'], text=True)

            try:
                launch(free_port())
                stop()
                retained = root_hash()
                self.assertFalse((snapshot / 'world.json').exists())
                self.assertFalse((snapshot / 'src').exists())
                self.assertFalse((snapshot / 'world.lock').exists())
                launch(free_port(), fail=True, selection=[])
                self.assertEqual(root_hash(), retained)
                # Neither changed host bytes nor a failed reconnect may rewrite
                # the saved program or any namespace/history reachable from it.
                module.write_text('+ deliberately_invalid_host_replacement unknown_name\n')
                launch(65534, fail=True)
                self.assertEqual(root_hash(), retained)
                launch(free_port())
                stop()
                print('Native snapshot alone resumed; selection and startup failures retained its exact root.')
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


    def test_unresolved_flow_and_completed_history_survive_crash(self):
        with tempfile.TemporaryDirectory(prefix='eden-restart-') as temporary:
            snapshot = Path(temporary) / 'snap'
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            client = api['FlowClient']('http://127.0.0.1:' + str(port), timeout=120)
            process = None
            log = open(temporary + '/launcher.log', 'w+')
            # One startup deadline for the test and launcher. Use the normal
            # compiler tier; HTTP and shutdown keep their shorter deadlines.
            startup_timeout = 900

            def start():
                nonlocal process
                offset = log.seek(0, os.SEEK_END)
                env = dict(os.environ, _EDEN_NIX_ROOT=str(ROOT))
                process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                    '--snapshot', str(snapshot), '--mount', 'flow-authoring', '--port', str(port),
                    '--startup-timeout', str(startup_timeout)], env=env, stdout=log, stderr=log,
                    start_new_session=True)
                deadline = time.monotonic() + startup_timeout
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
                self.fail('Snapshot did not become ready:\n' + Path(temporary + '/launcher.log').read_text(errors='replace')[-6000:])

            def crash():
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
                # Waiting for the launcher does not reap its killed runtime.
                # The native store owns writer exclusion. Wait for the killed
                # runtime to release it; there is no second launcher lock.
                deadline = time.monotonic() + 10
                with (snapshot / 'arena.writer.lock').open('a') as lock:
                    while True:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            if time.monotonic() > deadline:
                                self.fail('Crashed runtime did not release its native writer lock')
                            time.sleep(.02)

            name = 'restart_contract_' + uuid.uuid4().hex[:8]
            page = '/0x11/app/nenex/w/' + name
            controller = page + '/work/maintenance'
            output = page + '_output'
            request = controller + '/work/revision_1'
            hole = output + '/holes/' + name + '/concepts'
            recipe = (ROOT / 'extras/mounts/flow-examples/examples/evidence_resume.semidoc').read_text()
            def source_record(path):
                # Persistence concerns the native authored record. A rendered
                # Goo input is a separate projection with its own UI checks.
                record = client.read(path, care='x')
                self.assertTrue(record['exists'], path)
                source = record['properties']['/src']
                self.assertIsInstance(source, str)
                return source
            def values(value):
                # Historical read projections intentionally omit the transport
                # handle for opaque code. Execution below checks its behavior.
                if isinstance(value, dict):
                    return {k: values(v) for k, v in value.items()
                            if not (value.get('type') == 'code' and k == 'reference')}
                if isinstance(value, list):
                    return list(map(values, value))
                return value
            def evidence_values(node):
                # Live computed-view references capture the current world epoch.
                # Compare contents separately; exact pinned views are checked below.
                return dict(path=node['path'], exists=node.get('exists'),
                            properties=values(node.get('properties', {})),
                            children=[evidence_values(c) for c in node.get('children', [])])
            try:
                start()
                sources = client.import_texts({'readiness': 'Captured evidence before the crash. GATE_OPEN\n'})
                client.author(page, recipe)
                self.assertEqual(recipe, source_record(page))
                definition = client.publish(page, 'evidence_resume')
                client.follow(controller, definition, output, {'sources': sources})
                # The acknowledgement is the durability boundary. No graceful
                # shutdown, export, delay or separate checkpoint command follows.
                saved = {p: client.read(p, care='x') for p in
                         [page, definition, controller + '/cells/work', request, hole]}
                evidence = client.read('/x' + request + '/evidence', care='z')
                evidence_pin = evidence['reference_z']
                pinned_evidence = client.read(evidence_pin, care='z')
                marker = uuid.uuid4().hex
                client.tool('write', records=[{'path': page + '/notes', 'slots': {'text': marker}}])
                crash()
                start()
                self.assertEqual(recipe, source_record(page))
                self.assertEqual(marker, client.read(page + '/notes', care='x')['properties']['/text'])
                locked = subprocess.run([sys.executable, str(ROOT / 'x/eden'), '--snapshot', str(snapshot), '--mount', 'flow-authoring'],
                    env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT)), capture_output=True, text=True, timeout=20)
                self.assertNotEqual(0, locked.returncode)
                self.assertIn('already has a writer', locked.stderr)
                for p, before in saved.items():
                    self.assertTrue(before['exists'], p)
                    after = client.read(p, care='x')
                    self.assertEqual(before['reference'], after['reference'], p)
                    self.assertEqual(before['properties'], after['properties'], p)
                    historical = client.read(before['reference'], care='x')
                    self.assertTrue(historical['exists'], p)
                    self.assertEqual(values(before['properties']), values(historical['properties']), p)
                self.assertEqual(pinned_evidence, client.read(evidence_pin, care='z'))
                self.assertEqual(evidence_values(evidence),
                                 evidence_values(client.read('/x' + request + '/evidence', care='z')))
                # Executing the retained operation after a cold restore also
                # proves the saved state retained its actual compiled behavior.
                client.submit_revision(request, ';= Restart contract\n\n  Captured evidence survived.\n',
                                       'Completed against the original frozen evidence after restart.')
                published = client.read(output, care='x')
                self.assertTrue(published['exists'])
                completed = client.read(request, care='x')
                crash()
                start()
                self.assertIn('Captured evidence survived.', source_record(output))
                self.assertEqual(published['reference'], client.read(output, care='x')['reference'])
                self.assertEqual(completed['properties'], client.read(request, care='x')['properties'])
                self.assertEqual('resolved', client.read(hole, care='x')['properties']['/work/status'])
            except BaseException:
                # Keep the failed native arena and launch receipt, not an export.
                # Stop its writer before retaining the disposable fixture.
                import shutil
                if process is not None and process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=20)
                failure = Path(tempfile.mkdtemp(prefix='snapshot-restart-failure-', dir=ROOT / '.check'))
                shutil.copytree(temporary, failure, dirs_exist_ok=True)
                print('Failed native restart fixture retained at ' + str(failure), flush=True)
                raise
            finally:
                if process is not None and process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=20)
                log.flush()
                log.close()


if __name__ == '__main__':
    unittest.main()
