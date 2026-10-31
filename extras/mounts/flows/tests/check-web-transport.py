"""Disposable loopback proof of the native HTTP transport, not a work runner.

Called by the native test gate with TEST_SOURCE_ROOT and TEST_TEMPLATE. The
host only serves fixed HTTP bytes; Fetch and all assertions run in Foil.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import shutil
import sys
import threading

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'x'))
import test_runner


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'# Fixture source' if self.path == '/source.md' else b'Missing'
        self.send_response(200 if self.path == '/source.md' else 404)
        self.send_header('Content-Type', 'text/markdown')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def check():
    root = Path(os.environ['TEST_RUN_DIR']) / 'native-fetch'
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(os.environ['TEST_SOURCE_ROOT'], root / 'src', dirs_exist_ok=True)
    # The shared host gate stages core; mounted module aliases are taken from
    # the materialized source when present. Direct runs may supply that source.
    needed = set()
    def add(name):
        if name in needed:
            return
        needed.add(name)
        mount = REPO / 'extras/mounts' / name
        manifest = json.loads((mount / 'mount.json').read_text())
        for dep in manifest.get('dependencies', []):
            add(dep)
        for alias, filename in manifest.get('modules', {}).items():
            dest = root / 'src/foil' / (alias + '.foil')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copyfile(mount / filename, dest)
    add('flows')
    shutil.copyfile(REPO / 'extras/mounts/flows/tests/web.foil', root / 'src/foil/flow_web_tests.foil')
    shutil.copyfile(REPO / 'extras/mounts/flows/tests/lifecycle.foil', root / 'src/foil/tests/flows.foil')
    shutil.copyfile(REPO / 'extras/mounts/flows/examples/web-source-guide.semidoc', root / 'src/web-source-guide.semidoc')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = 'http://127.0.0.1:' + str(server.server_port)
        module = root / 'src/foil/web_transport_test.foil'
        module.write_text('- flow_web_tests\n'
                          '+ authored\n  \\ ignored=unit\n  ^ row[testing/check]\n'
                          '  = ;bytes (ReadFile "web-source-guide.semidoc")\n'
                          '  | flow_web_tests/authored (flow_web_foot/unbar bytes) ignored\n'
                          '+ tests\n  ^ row[testing/case]\n'
                          '  [(testing/case "native HTTP loopback" '
                          '(flow_web_tests/transport "' + url + '"))\n'
                          '   (testing/case "authored web guide" authored)]\n')
        suites = [dict(name='foil:' + mod, kind='native', target=mod, group='loopback')
                  for mod in ['flow_web_tests', 'web_transport_test']]
        result = test_runner.run_group(suites, os.environ['WISP'],
                                       Path(os.environ['TEST_TEMPLATE']), root, 900)
        (root / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
        assert result['passed'], result['log']
        print('NATIVE-WEB-TRANSPORT-PASS', flush=True)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    check()
