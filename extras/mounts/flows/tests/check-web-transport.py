"""Disposable loopback proof of the native HTTP transport, not a work runner.

Called by the native test gate with TEST_SOURCE_ROOT and TEST_TEMPLATE. The
host only serves fixed HTTP bytes; Fetch and all assertions run in Foil.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import sys
import threading

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO / 'x'), str(REPO / 'extras/x')]
import test_runner
from eden_mounts import select
from fixture_sources import materialize


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
    # Use the same mount catalogue and fixture projection as the native gate;
    # aliases, shared test helpers and authored recipe bytes have one owner.
    mounts = select(REPO / 'extras', ['flows', 'flow-examples'])
    source_root = Path(os.environ['TEST_SOURCE_ROOT'])
    materialize(source_root.parent, REPO / 'extras', root / 'src',
                {mount.name for mount in mounts}, native_tests=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = 'http://127.0.0.1:' + str(server.server_port)
        module = root / 'src/foil/web_transport_test.foil'
        module.write_text('- flow_web_tests\n'
                          '+ authored\n  \\ ignored=unit\n  ^ row[testing/check]\n'
                          '  = ;bytes (ReadFile "examples/web-source-guide.semidoc")\n'
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
