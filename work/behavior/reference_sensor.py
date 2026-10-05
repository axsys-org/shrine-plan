"""Local test provider for the supplied sensor walkthrough. No real hardware."""
import json,math,time
from http.server import HTTPServer,BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  body=json.dumps({'name':'Freezer','provider':'Local test sensor (simulated)',
    'fields':[{'name':'label','type':'Text','role':'title','writable':False},{'name':'value','type':'Number','role':'quantity','writable':False},{'name':'max','type':'Number','role':'max','writable':False},{'name':'limit','type':'Number','role':'limit','writable':False},{'name':'target','type':'Number','role':'target','writable':True}],
    'values':{'label':'Local test sensor','value':str(round(6.2+math.sin(time.monotonic()/15)*.4,1)),'max':'12','limit':'8','target':'8'}}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
HTTPServer(('127.0.0.1',8231),Handler).serve_forever()
