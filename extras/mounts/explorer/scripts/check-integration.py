#!/usr/bin/env python3
"""Run real Eden/Grove/Goo/Mash against the immutable production Nix pin.

The pane regression specimen is a test-only mount. Production asset preparation
hooks are used unchanged; no local Mash checkout or build override is accepted.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

MOUNT = Path(__file__).resolve().parents[1]
ROOT = MOUNT.parents[2]


def fixture_extras(destination):
    mounts = destination / 'mounts'
    mounts.mkdir(parents=True)
    for source in (ROOT / 'extras/mounts').iterdir():
        if source.is_dir():
            (mounts / source.name).symlink_to(source, target_is_directory=True)
    (mounts / 'panes').symlink_to(ROOT / 'extras/tests/fixtures/panes', target_is_directory=True)
    return destination


def production_mash():
    command = ['nix', '--extra-experimental-features', 'nix-command flakes',
               'build', '--no-update-lock-file', '--no-link', '--print-out-paths',
               f'path:{ROOT / "extras"}#mash-workspace']
    mash = Path(subprocess.check_output(command, text=True).strip()).resolve()
    lock = json.loads((ROOT / 'extras/flake.lock').read_text())
    pinned = lock['nodes'][lock['nodes'][lock['root']]['inputs']['mash']]['locked']
    provenance = json.loads((mash / 'mash-nix.json').read_text())
    if (mash.parent != Path('/nix/store') or provenance['revision'] != pinned['rev']
            or provenance['repository'] != pinned['url'] or provenance['dirty']):
        raise RuntimeError('Expected the clean, immutable production Mash revision')
    return mash, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Keep logs, browser results and screenshots here')
    parser.add_argument('--startup-timeout', type=int, default=900)
    parser.add_argument('--panes-only', action='store_true', help='Diagnostic subset: skip goo-inspector (not the full gate)')
    parser.add_argument('--url', help='Use an existing disposable Eden server with the test-only panes fixture and goo-inspector (the gate replaces its panes instance)')
    args = parser.parse_args()
    mash, provenance = production_mash()
    wisp = os.environ.get('WISP') or shutil.which('wisp')
    if not args.url and not wisp:
        parser.error('Set WISP to the locked Reaver runtime')
    output = (args.output or Path(tempfile.mkdtemp(prefix='goo-integration-'))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'mash-provenance.json').write_text(json.dumps(dict(provenance, storePath=str(mash)), indent=2) + '\n')
    subprocess.run([sys.executable, str(MOUNT.parent / 'goo/scripts/sync-mash-profile.py'),
                    '--check', '--mash-root', str(mash)], check=True)
    process = None
    try:
        url = args.url
        if not url:
            extras = fixture_extras(output / 'extras')
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            url = f'http://127.0.0.1:{port}'
            env = dict(os.environ, WISP=wisp, _EDEN_NIX_ROOT=str(ROOT))
            log = (output / 'eden.log').open('w')
            hosted = [] if args.panes_only else ['--mount', 'goo-inspector']
            process = subprocess.Popen([sys.executable, str(ROOT / 'x/eden'), '--mount', 'panes', *hosted,
                                        '--extras-root', str(extras), '--port', str(port),
                                        '--startup-timeout', str(args.startup_timeout)],
                                       cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            print(f'Starting real Eden server; log: {output / "eden.log"}', flush=True)
            deadline = time.monotonic() + args.startup_timeout
            next_update = time.monotonic() + 30
            while True:
                text = (output / 'eden.log').read_text(errors='replace')
                if process.poll() is not None:
                    raise RuntimeError(f'Eden startup failed:\n{text[-5000:]}')
                if f'Eden: {url};' in text:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'Eden startup timed out; inspect {output / "eden.log"}')
                if time.monotonic() >= next_update:
                    print('Eden is compiling the real mounted Grove and HTTP runtime…', flush=True)
                    next_update += 30
                time.sleep(.25)
        subprocess.run(['nix', '--extra-experimental-features', 'nix-command flakes',
                        'develop', '--no-update-lock-file', f'path:{ROOT / "extras"}#debugger',
                        '--command', 'node', str(MOUNT / 'scripts/check-integration-browser.mjs'),
                        url.rstrip('/'), str(mash), str(output), *(['--panes-only'] if args.panes_only else [])], check=True)
        label = 'Goo panes integration subset' if args.panes_only else 'Real Goo application integration'
        print(f'{label} passed. Artifacts: {output}', flush=True)
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            log.close()


if __name__ == '__main__':
    main()
