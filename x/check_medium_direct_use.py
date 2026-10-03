#!/usr/bin/env python3
"""Regression for the actual model-authored Number edit in the construction world.

Requires editable-number-request.json and editable-number-result.json receipts.
Uses real native actions, restores input values, retains factual history.
No browser rendering or user-experience acceptance is claimed.
"""
import argparse,sys,json,http.cookiejar,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from check_medium_live import Client
parser=argparse.ArgumentParser();parser.add_argument('--world',required=True,type=Path);parser.add_argument('--port',required=True,type=int);parser.add_argument('--browser-port',required=True,type=int);args=parser.parse_args()
world=args.world;client=Client(world,args.port);client.call('read')
start=client.frame
before=json.loads((world/'editable-number-request.json').read_text())['before']
root='/0x11/gov/medium/number9d1b19';slot=root+'/amount';draft=root+'/draft';error=root+'/error'
numbers=[n for n in start['nodes'] if n['pattern']==root];ids=[n['id'] for n in numbers]
node=lambda f,i:next(n for n in f['nodes'] if n['id']==i)
value=lambda n,s:next(f['value'] for f in n['fields'] if f['slot']==s)
client.require('model edit preserved both original numbers',len(numbers)==2 and all(value(n,slot)==value(node(before,n['id']),slot) and n['inputs']==node(before,n['id'])['inputs'] for n in numbers))
client.require('model left every unrelated definition intact',all(n['source']==node(before,n['id'])['source'] for n in start['nodes'] if n['pattern']!=root))
def set_value(ident,text):
 n=node(client.frame,ident);inp=next(o for o in n['view']['occurrences'] if o['kind']=='input' and o['slot']==draft)
 actions=[o for o in n['view']['occurrences'] if o['kind']=='action' and o['control'].rsplit('.',1)[0]==inp['control'].rsplit('.',1)[0]]
 assert len(actions)==1
 return client.call('act',{'target':ident,'expected':n['expected'],'displayed':n['displayed'],'publication':client.frame['publication'],'control':actions[0]['control'],'inputs':{draft:text}})
code,result=set_value(ids[0],'not a number')
client.require('native invalid input preserves amount and reports its own inline error',code==200 and value(node(result,ids[0]),slot)==value(numbers[0],slot) and 'whole number' in value(node(result,ids[0]),error))
original=value(numbers[0],slot);new=str(int(original)+2)
code,result=set_value(ids[0],new)
client.require('native input sets amount and clears error',code==200 and value(node(result,ids[0]),slot)==new and value(node(result,ids[0]),error)=='')
client.require('other instance retains independent value',value(node(result,ids[1]),slot)==value(numbers[1],slot))
successor=next(n for n in result['nodes'] if n['label']=='Successor')
client.require('native computation follows edited value',value(successor,successor['code_root']+'/amount')==str(int(new)+1))
views=[n for n in result['nodes'] if n['label']=='Interference']
client.require('both dependent pictures recalculate through actual bindings',len(views)==2 and all(n['view']['html']!=node(start,n['id'])['view']['html'] for n in views))
client.require('source editor still reflects the same shared definition',any(n['label']=='Source editor' and any(f['value']==node(result,ids[0])['source'] for f in n['fields']) for n in result['nodes']))
origin='http://127.0.0.1:'+str(args.browser_port);opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.open(urllib.request.Request(origin+'/connect',b'{}',{'Origin':origin})).close()
def read(tag=None):
 req=urllib.request.Request(origin+'/api/read',headers={'If-None-Match':tag} if tag else {})
 try:
  with opener.open(req,timeout=30) as r:return r.status,json.load(r),r.headers.get('ETag')
 except urllib.error.HTTPError as e:
  if e.code==304:return 304,None,e.headers.get('ETag')
  raise
code,current,etag=read();assert code==200 and etag
pins=world/'snap/pins.pack';size=pins.stat().st_size
for _ in range(20):
 code,_,tag=read(etag);assert code==304 and tag==etag
client.call('read')
client.require('20 conditional native reads return unchanged and retain no history or pins',pins.stat().st_size==size and client.frame['events']==result['events'])
code,result=set_value(ids[0],original);assert code==200
code,fresh,tag=read(etag)
client.require("conditional HTTP reports another client's native action",code==200 and tag!=etag and fresh['expected']==client.frame['expected'] and value(node(fresh,ids[0]),slot)==original)
client.require('native values restored without replacing customer history',all(value(node(client.frame,n['id']),slot)==value(n,slot) for n in numbers))
report={'results':client.results,'timings':client.timings,'browser_verification':'Not performed; these are real native and HTTP checks, not rendered UI acceptance.','model_receipt':json.loads((world/'editable-number-result.json').read_text()).get('receipt')}
(world/'interaction-continuation-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
print('Report:',world/'interaction-continuation-acceptance.json',flush=True)
