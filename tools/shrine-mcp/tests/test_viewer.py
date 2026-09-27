import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from viewer import handler

class ViewerTests(unittest.TestCase):
    def test_live_read_only_inspector_and_artifacts(self):
        calls=[]
        class ReadClient:
            def call(self,method,**args):
                calls.append(method)
                return {'protocol_version':5,'world_id':'fixture'}
        directory=Path(tempfile.mkdtemp());body=b'actual diff artifact\n';key=hashlib.sha256(body).hexdigest()
        (directory/key).write_bytes(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(ReadClient(),directory))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urlopen(base+'/api?method=status') as r:self.assertEqual(json.load(r)['protocol_version'],5)
            for req in [base+'/api?method=write',base+'/api?method=eval',Request(base+'/api',data=b'{}')]:
                with self.assertRaises(HTTPError):urlopen(req)
            self.assertEqual(calls,['status'])
            with urlopen(base+'/artifact/'+key) as r:self.assertEqual(r.read(),body)
            with self.assertRaises(HTTPError):urlopen(base+'/artifact/../../secret')
            with urlopen(base+'/') as r:self.assertIn(b'Native world',r.read())
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
