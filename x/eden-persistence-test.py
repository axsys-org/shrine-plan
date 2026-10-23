"""Crash/restart regression against the real native world, not a JSON export.

Set WISP and run this file. EDEN_TEST_WORLD may reuse a disposable test world
to avoid recompiling the initial mount publication. Never select a personal world.
"""
import json
import os
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

ROOT = Path(__file__).resolve().parent.parent
api = runpy.run_path(str(ROOT / 'extras/mounts/flows/client.py'))


@unittest.skipUnless(os.environ.get('WISP'), 'Set WISP for the native crash test')
class NativeWorldTest(unittest.TestCase):
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
