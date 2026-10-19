"""Local Shrine MCP client; every call is journaled as a request/response receipt."""
import json, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'run'
URL = 'http://127.0.0.1:8148/mcp'

def rpc(method, params=None):
    request = {'jsonrpc':'2.0','id':time.time_ns(),'method':method,'params':params or {}}
    start=time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(URL,json.dumps(request).encode(),{'Content-Type':'application/json'}),timeout=180) as response:
        result=json.load(response)
    RUN.mkdir(exist_ok=True)
    with (RUN/'mcp-receipts.jsonl').open('a') as log:
        log.write(json.dumps({'request':request,'response':result,'elapsed_seconds':time.monotonic()-start})+'\n')
    if 'error' in result: raise RuntimeError(result)
    return result['result']

def tool(name, **arguments):
    result=rpc('tools/call',{'name':'mcp/'+name,'arguments':arguments})
    if result.get('isError'): raise RuntimeError(result)
    return result['structuredContent']

if __name__=='__main__':
    print(json.dumps(rpc('initialize'),indent=2))
    print(json.dumps(rpc('tools/list'),indent=2))
    target='/0x11/agent/astra_branchmap/scratch/connection'
    print(json.dumps(tool('write',records=[{'path':target,'slots':{'status':'connected','sequence':1}}],who='astra_branchmap')))
    print(json.dumps(tool('read',path=target)))
