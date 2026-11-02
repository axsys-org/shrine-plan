"""Real terminal stdin, live supervisor calls, and wire reload while Input blocks."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import subprocess
import sys
import tempfile
import termios
import time

from mount_tools import ROOT, create, wire_request


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


PROGRAM = r'''- stdlib/runtime
+ terminal
  + say
    \ text=str
    ^ nat
    | Output (add (str/to_atom text) (bex (mul 8 text.len)))
  + main
    \ server=nat arguments=row[str]
    ^ nat
    ; (terminal/say arguments.at(0))
    ; (SendCaps server (helm/card/snapshot 71 (\ state=namespace [200 "live> "])) [0])
    = ;[reply caps] (Recv[feet/task[unit]] 0)
    ; (helm/supervisor/close_caps caps)
    > (feet/task/develop request status body) reply (error (pails/t "Bad supervisor reply"))
    ; (terminal/say body)
    % ignored=nat 0
    ^ nat
    = ;bytes (Input 1)
    ? (le bytes 1) 7
    ; (Output bytes)
    | _ 0
'''


def main():
    with tempfile.TemporaryDirectory(prefix='eden-terminal-check-') as tmp:
        root = Path(tmp)
        extras = root / 'extras'
        folder = create(extras, 'terminal-check', terminal=True)
        (folder / 'cli.foil').write_text(PROGRAM)
        port, http_port = free_port(), free_port()
        while port == http_port:
            http_port = free_port()
        master, slave = pty.openpty()
        # A real canonical terminal: newline delivers a line and ^D delivers
        # EOF. Disable local echo; only the Foil program should echo bytes.
        mode = termios.tcgetattr(slave)
        mode[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, mode)
        log_path = root / 'launcher.log'
        with log_path.open('w') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'),
                '--extras-root', str(extras), '--terminal', 'terminal-check',
                '--port', str(http_port), '--wire-port', str(port),
                '--startup-timeout', '900', '--request-timeout', '120', '--', 'ARG '],
                stdin=slave, stdout=subprocess.PIPE, stderr=log,
                env=dict(os.environ, _EDEN_NIX_ROOT=str(ROOT)), start_new_session=True)
            os.close(slave)
            output = bytearray()
            def receive(expected, timeout=900):
                deadline = time.monotonic() + timeout
                while bytes(output) != expected:
                    assert process.poll() is None, (process.returncode, output, log_path.read_text())
                    assert time.monotonic() < deadline, (output, log_path.read_text())
                    if select.select([process.stdout], [], [], .1)[0]:
                        chunk = os.read(process.stdout.fileno(), 4096)
                        assert chunk, log_path.read_text()
                        output.extend(chunk)
                        assert expected.startswith(output), output
            try:
                receive(b'ARG live> ')
                print('Terminal prompt and supervisor reply received.', flush=True)
                deadline = time.monotonic() + 900
                while 'Foil editor wire:' not in log_path.read_text():
                    assert process.poll() is None, log_path.read_text()
                    assert time.monotonic() < deadline, log_path.read_text()
                    time.sleep(.1)
                before = wire_request({'op': 'mount/status', 'mount': 'terminal-check'}, port)
                assert before['ok'] and before['status']['ready'], before
                source = (folder / 'main.grove').read_text().replace('A new world', 'Reloaded at the prompt')
                saved = wire_request(dict(op='mount/save', mount='terminal-check', file='main.grove',
                    text=source, expected=before['files']['main.grove']), port)
                assert saved['ok'] and saved['reloaded'][0]['ready'], saved
                assert saved['reloaded'][0]['publication'] != before['status']['publication'], saved
                print('Wire save/reload passed while Input was blocked.', flush=True)
                # Code-looking text must reach Input, never the Reaver reader.
                message = b'(#bind should_not_run 42)\nhello terminal\n'
                os.write(master, message)
                receive(b'ARG live> ' + message, 30)
                os.write(master, b'\x04')
                assert process.wait(timeout=30) == 7, log_path.read_text()
                assert not process.stdout.read(), 'Compiler output leaked onto stdout'
                print('Terminal bytes, EOF and exit status passed.', flush=True)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                process.stdout.close()
                os.close(master)
                print(log_path.read_text(), flush=True)
    print('EDEN-TERMINAL-CHECK-PASS', flush=True)


if __name__ == '__main__':
    main()
