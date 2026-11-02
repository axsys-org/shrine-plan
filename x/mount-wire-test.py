"""Exercise authoring CLIs and wire publication against a real Eden supervisor."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

from mount_tools import ROOT, wire_request


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix='mount-wire-check-') as tmp:
        root = Path(tmp)
        extras = root / 'extras'
        def cli(command, *args, ok=True):
            result = subprocess.run([sys.executable, str(ROOT / 'x' / command), *args],
                                    capture_output=True, text=True, timeout=900)
            assert (result.returncode == 0) == ok, result.stdout + result.stderr
            return result.stdout
        cli('create-mount', 'wire-check', '--extras-root', str(extras))
        cli('add-file', 'wire-check', 'extra.grove', '--extras-root', str(extras))
        cli('add-file', 'wire-check', 'tests.foil', '--kind', 'test', '--extras-root', str(extras))
        cli('create-mount', 'wire-child', '--kind', 'foil', '--dependency', 'wire-check',
            '--extras-root', str(extras))
        (extras / 'mounts/wire-child/main.foil').write_text(
            '- apps/wire_check/main\n+ inherited wire_check/greeting\n')
        http_port, port = free_port(), free_port()
        while port == http_port:
            port = free_port()
        env = dict(os.environ, _EDEN_NIX_ROOT=str(ROOT))
        log_path = root / 'launcher.log'
        with log_path.open('w') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                '--extras-root', str(extras), '--mount', 'wire-child',
                '--port', str(http_port), '--wire-port', str(port),
                '--startup-timeout', '900', '--request-timeout', '120'],
                env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                deadline = time.monotonic() + 900
                while 'Foil editor wire:' not in log_path.read_text():
                    assert process.poll() is None, log_path.read_text()
                    assert time.monotonic() < deadline, log_path.read_text()
                    time.sleep(.25)
                print(log_path.read_text(), flush=True)
                def request(op, **args):
                    result = wire_request(dict(op=op, mount='wire-check', **args), port, 900)
                    print(op, json.dumps(result), flush=True)
                    return result
                def success(result):
                    assert result['ok'], result
                    return result
                initial = success(request('mount/status'))
                assert initial['live'] and initial['status']['ready'], initial
                child = success(wire_request(dict(op='mount/status', mount='wire-child'), port, 900))
                folder = extras / 'mounts/wire-check'
                grove = folder / 'main.grove'
                original = grove.read_text()
                updated = original.replace('A new world', 'An updated world')
                upload = root / 'upload.grove'
                upload.write_text(updated)
                saved = json.loads(cli('save-mount', 'wire-check', 'main.grove',
                    '--from', str(upload), '--port', str(port)))
                success(saved)
                assert saved['saved'] == 'main.grove' and grove.read_text() == updated
                published = saved['reloaded'][0]
                assert published['publication'] != initial['status']['publication'], saved
                assert [m['mount'] for m in saved['reloaded']] == ['wire-check', 'wire-child'], saved
                assert saved['reloaded'][1]['publication'] != child['status']['publication'], saved
                # Rebuild the unchanged consumer against changed Foil definitions too.
                foil = folder / 'main.foil'
                code = success(request('mount/save', file='main.foil',
                    text=foil.read_text().replace('Hello from wire_check.', 'Hello again.'),
                    expected=initial['files']['main.foil']))
                assert code['reloaded'][1]['ready'], code
                published = code['reloaded'][0]
                # A bad source is saved on disk, but cannot replace a good publication.
                bad = request('mount/save', file='main.grove', text='broken =\n  @unknown\n',
                              expected=saved['sha256'])
                assert not bad['ok'] and bad['saved'] == 'main.grove', bad
                assert bad['reloaded'][0]['publication'] == published['publication'], bad
                assert bad['reloaded'][0]['diagnostic'], bad
                repaired = success(request('mount/save', file='main.grove', text=original,
                                           expected=bad['sha256']))
                assert repaired['reloaded'][0]['ready'], repaired
                # Direct disk edits and the separate reload command follow the same path.
                grove.write_text(updated)
                success(json.loads(cli('reload-mount', 'wire-check', '--port', str(port))))
                success(json.loads(cli('show-mount', 'wire-check', '--live', '--port', str(port))))
                # Compiler operations still work on the same endpoint, including generated tests.
                success(request('compile', module='apps/wire_check/main'))
                success(request('compile', module='apps/wire_check/tests'))
                cli('add-file', 'wire-check', 'new.grove', '--extras-root', str(extras))
                changed = request('mount/reload')
                assert not changed['ok'] and changed['restart_required'], changed
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                print(log_path.read_text(), flush=True)
    print('MOUNT-WIRE-CHECK-PASS', flush=True)


if __name__ == '__main__':
    main()
