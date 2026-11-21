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
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


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
                last_probe_error = None
                while time.monotonic() < deadline:
                    text = log.read_text(errors='replace')[offset:] if log.exists() else ''
                    if fail and process.poll() is not None:
                        self.assertNotEqual(process.returncode, 0, text[-4000:])
                        self.assertIn('startup-contract-route-failure', text)
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
                            return
                    time.sleep(.1)
                self.fail(f'Startup timed out: {log}; last HTTP probe: {last_probe_error}')

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



if __name__ == '__main__':
    unittest.main()
