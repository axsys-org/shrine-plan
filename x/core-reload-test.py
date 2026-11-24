"""Live core replacement, retained history, and atomic failure regressions.

Runs an isolated checkout and world; never edits the developer's source files.
Requires WISP and permission to bind loopback listeners.
"""
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
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'x'))
from mount_tools import wire_request


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    work = Path(tempfile.mkdtemp(prefix='core-reload-live-', dir=ROOT / '.check'))
    checkout = work / 'checkout'
    checkout.mkdir()
    for name in ('src', 'x', 'slots'):
        shutil.copytree(ROOT / name, checkout / name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'test-inventory.json', checkout / 'test-inventory.json')
    (checkout / '.check').symlink_to(ROOT / '.check', target_is_directory=True)
    mount = checkout / 'extras/mounts/probe'
    mount.mkdir(parents=True)
    (mount / 'mount.json').write_text(json.dumps(dict(
        version=1, name='probe', dependencies=[], modules={'apps/probe/main': 'main.foil'},
        grove=[], assets={}, files={}, roots=[['lib', 'apps/probe/main']], tests={},
        http={'module': 'apps/probe/main', 'entry': ['probe', 'http']}, routes=['/probe'])))
    (mount / 'main.foil').write_text(r'''- stdlib/runtime
+ probe
  + read
    \ target=path version=nat state=namespace
    ^ [nat str]
    > (./known tree) (sovereign_value .x version target state) [404 "missing"]
    [200 (tree.fil.fall(myth/new).nat_at(['value] 0)).show]
  + typed
    \ target=path version=nat state=namespace
    ^ [nat str]
    > (./known tree) (sovereign_value .x version target state) [404 "missing"]
    > (./some record) tree.fil [500 "missing record"]
    > (./some text) record.get('/json) [500 "missing json"]
    > value=json/str text [500 "json identity changed"]
    > (./some finding) record.get('/lint) [500 "missing lint"]
    > diag=lint/diag finding [500 "lint identity changed"]
    [200 value.s.cat(diag.message)]
  + http
    \ files=row[[str nat]] state=namespace
    ^ http_foot/config
    = target=path [state.self 'user 'kept]
      route
        \ request=http_foot/request now=nat
        ^ http_foot/action
        ? (equal request.method "POST")
          | ./commit target
            (writ/make (myth/sing '/value (pd (nat/parse request.body).fall(0))).put('/json (json/str "json")).put('/lint (lint/diag rex/zero_span "rule" "warning" "lint")))
            (\ err (http_driver/response (? err.is_some 409 200) "written"))
        ? (equal request.target "/probe/typed")
          | ./snapshot (probe/typed target 0)
        ? (equal request.target "/probe/typed-history")
          | ./snapshot (probe/typed target 1)
        ? (equal request.target "/probe/fuel")
          | ./reply (http_driver/response 200 read_fuel.show)
        | ./snapshot (probe/read target (? (equal request.target "/probe/history") 1 0))
    | http_foot/add_routes [(http_foot/route "/probe" route)] http_foot/empty
''')
    types = checkout / 'src/foil/types.foil'
    types.write_text(types.read_text() + '\n+ reload_fixture\n  : value=nat\n')
    split = '--split-stdlib' in sys.argv
    split_sources = {}
    if split:
        foil = checkout / 'src/foil'
        for name in ('stdlib/base.foil', 'stdlib/json.foil', 'stdlib/rex.foil',
                     'stdlib/lint.foil', 'stdlib/runtime.foil', 'modules.tsv'):
            split_sources[name] = (foil / name).read_text()
        base = split_sources['stdlib/base.foil']
        for name in ('json', 'rex', 'lint'):
            base = base.replace(f'- stdlib/{name}\n', '')
        section = lambda name: split_sources[f'stdlib/{name}.foil'].split(
            f"' --- {name} ---", 1)[1]
        base = base.replace("' --- shrine_types ---",
            "' --- json ---" + section('json') + "' --- shrine_types ---", 1)
        base = base.replace("' --- path_segments ---",
            "' --- rex ---" + section('rex') + "' --- lint ---" + section('lint')
            + "' --- path_segments ---", 1)
        (foil / 'stdlib/base.foil').write_text(base)
        (foil / 'stdlib/runtime.foil').write_text(split_sources['stdlib/runtime.foil'].replace(
            '- stdlib/json [at=json_source]', '- stdlib/base [at=json_source]'))
        (foil / 'modules.tsv').write_text('\n'.join(line for line in
            split_sources['modules.tsv'].splitlines()
            if not line.startswith(('stdlib/json\t', 'stdlib/rex\t', 'stdlib/lint\t'))) + '\n')
        for name in ('json', 'rex', 'lint'):
            (foil / f'stdlib/{name}.foil').unlink()
    http_port, wire_port = port(), port()
    while http_port == wire_port:
        wire_port = port()
    env = dict(os.environ, _EDEN_NIX_ROOT=str(checkout))
    log_path = work / 'launcher.log'
    print(f'Live reload validation: {work}', flush=True)
    with log_path.open('w') as log:
        child = subprocess.Popen([sys.executable, str(checkout / 'x/eden'), '--mount', 'probe',
            '--port', str(http_port), '--wire-port', str(wire_port), '--compiler', 'none',
            '--startup-timeout', '1800', '--request-timeout', '1800'],
            env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 1800
            while 'Foil editor wire:' not in log_path.read_text():
                assert child.poll() is None, log_path.read_text()[-10000:]
                assert time.monotonic() < deadline, log_path.read_text()[-10000:]
                time.sleep(.25)
            def http(path, value=None, status=200):
                request = urllib.request.Request(f'http://127.0.0.1:{http_port}/probe/{path}',
                    None if value is None else str(value).encode())
                try:
                    response = urllib.request.urlopen(request, timeout=60)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    assert response.status == status, response.read().decode()
                    return response.read().decode()
            def reload(ok):
                started = time.monotonic()
                result = wire_request({'op': 'core/reload'}, wire_port, 1800)
                print('reload', round(time.monotonic() - started, 1), result, flush=True)
                assert bool(result.get('ok')) == ok, result
                assert child.poll() is None
            def retained():
                assert http('latest') == '84'
                assert http('history') == '42'
                assert http('typed') == 'jsonlint'
                assert http('typed-history') == 'jsonlint'
            assert http('fuel') == '32768'
            print('HTTP route ready', flush=True)
            http('latest', 42)
            print('First write committed', flush=True)
            http('latest', 84)
            retained()
            assert http('fuel') == '32768'
            if split:
                for name, text in split_sources.items():
                    (checkout / 'src/foil' / name).write_text(text)
                print('Restored split sources and module inventory', flush=True)
            core = checkout / 'src/foil/namespace.foil'
            original = core.read_text()
            core.write_text(original.replace('\n  32768\n', '\n  32769\n'))
            runtime = checkout / 'src/foil/stdlib/runtime.foil'
            runtime_before = runtime.read_text()
            marker = '      | helm/supervisor/run_task (task/vine target command) now block state'
            assert runtime_before.count(marker) == 1
            runtime.write_text(runtime_before.replace(marker,
                "      ? (equal[path] target [state.self 'user 'kept])\n"
                "        [state (helm/supervisor/denied 'reload_probe)]\n" + marker))
            reload(True)
            retained()
            assert http('fuel') == '32769'
            http('latest', 999, status=409)
            retained()
            print('Changed supervisor behavior and retained history: PASS', flush=True)
            # Compilation failure cannot partially publish or change active routes.
            core.write_text(original + '\n+ broken unknown_function(1)\n')
            reload(False)
            retained()
            assert http('fuel') == '32769'
            # A shape change is rejected despite being valid Foil.
            core.write_text(original)
            types = checkout / 'src/foil/types.foil'
            before = types.read_text()
            types.write_text(before.replace('+ reload_fixture\n  : value=nat',
                '+ reload_fixture\n  : value=nat extra=nat'))
            reload(False)
            retained()
            types.write_text(before)
            # A dependent mount failure rolls back the prepared core too.
            source = mount / 'main.foil'
            good = source.read_text()
            source.write_text(good + '\n+ bad unknown_function(1)\n')
            reload(False)
            retained()
            assert http('fuel') == '32769'
            source.write_text(good)
            runtime.write_text(runtime_before)
            reload(True)
            retained()
            assert http('fuel') == '32768'
            http('latest', 126)
            assert http('latest') == '126'
            assert http('history') == '42'
            print('CORE-RELOAD-LIVE-PASS', flush=True)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    main()
