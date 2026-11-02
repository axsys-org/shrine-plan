"""Headless model and fresh Eden integration gate, registered in x/check."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

BAG = Path(__file__).resolve().parent
CORE = BAG.parents[2]
node = os.environ.get('NODE') or shutil.which('node')
if not node:
    raise SystemExit('Set NODE or put node on PATH for the Pathways model checks.')
subprocess.run([node, str(BAG / 'check-model.mjs')], check=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
subprocess.run([sys.executable, str(CORE / 'x/eden'), '--extras-root', str(BAG.parents[1]),
                '--mount', 'pathways', '--node', '0x2a', '--port', str(port),
                '--startup-timeout', '900', '--check'],
               env=dict(os.environ, _EDEN_NIX_ROOT=str(CORE)), check=True, timeout=1200)
print('PATHWAYS-CHECK-PASS', flush=True)
