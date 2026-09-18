"""Own the Codex companion lifetime; mounting source alone never runs it."""
import importlib.util
import os
import shutil
import sys
import urllib.request
import urllib.parse
import re
import time


def prepare(root, work, check, cleanup, context):
    work.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location('shrine_codex_bridge', root / 'codex_bridge.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    executable = os.environ.get('CODEX_BIN', 'codex')
    if not check and not shutil.which(executable):
        raise RuntimeError('Codex executable missing; set CODEX_BIN')
    command = ([sys.executable, str(root / 'codex_fake_server.py'), 'normal'] if check else
               [executable, 'app-server', '--listen', 'stdio://'])
    stderr = cleanup.enter_context((work / 'companion.log').open('w'))
    bridge = module.Bridge(command, stderr=stderr, auth_timeout=context['timeout']).start()
    cleanup.callback(bridge.close)
    return root, [str(bridge.port), bridge.token, '/' + context['node'] + '/io/codex']


def check(url, node, timeout):
    def get(path):
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            return response.read().decode()
    console = f'/ns/{node}/io/codex'
    assert 'What should Codex do?' in get(console)
    def codex_post(**fields):
        request = urllib.request.Request(
            url + f'/post/{node}/io/codex',
            data=urllib.parse.urlencode(fields).encode())
        with urllib.request.urlopen(request, timeout=timeout) as response:
            assert 'committed' in response.read().decode()
    def codex_wait(fragment):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            page = get(console)
            if fragment in page:
                return page
            time.sleep(0.2)
        raise AssertionError(f'Codex console missing {fragment}: {page}')
    codex_post(action='start', prompt='Hello from Shrine')
    codex_wait('hello')
    codex_post(action='steer', thread='t1', turn='u1', prompt='Question please')
    page = codex_wait('data-effect=')
    effect = re.search(r'data-effect="([^"]+)"', page).group(1)
    codex_post(action='reply', effect=effect,
               reply_kind='result', reply='{"answers":{}}')
    codex_wait('serverRequest/resolved')
    codex_post(action='interrupt', thread='t1', turn='u1')
    codex_wait('interrupted')
