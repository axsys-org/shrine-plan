#!/usr/bin/env python3
"""Exercise real Goo actions in an explicitly disposable Branchmap world."""
import argparse,json,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
p=argparse.ArgumentParser();p.add_argument('--server',default='http://127.0.0.1:8190');p.add_argument('--disposable',action='store_true');p.add_argument('--output',type=Path,default=Path(__file__).parent/'run/live-check.json');args=p.parse_args()
if not args.disposable: p.error('Use --disposable only with a fresh world; this check trades and resolves markets')
TARGET='/0x11/app/branchmap/exchange';SLOT='/0x11/gov/branchmap/'
receipts=[]
def request(route,values=None,body=None):
    data=body if body is not None else (urlencode(values).encode() if values is not None else None)
    req=Request(args.server+route,data=data,headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urlopen(req,timeout=240) as response: status=response.status;raw=response.read()
    except HTTPError as e:status=e.code;raw=e.read()
    try:result=json.loads(raw)
    except ValueError:result={'text':raw.decode()}
    return status,result

def render():
    status,r=request('/goo/render',dict(target=TARGET,slot='/sys/slot/content',width=900,textScale=1,direction='ltr'))
    assert status==200 and r['ok'],(status,r)
    return r

def text(r):
    return '\n'.join(n.get('payload','') for n in r['display']['nodes'])

def invocation(r,operation='buy',participant='alice',market='0',outcome='0',quantity='10',conditions=''):
    snap=r['snapshot'];control=next(c for c in r['controls'] if c['binding']['kind']=='invoke')
    fields=dict(target=snap['subject'],subject=snap['target'],view=r['view'],control=control['binding']['route'],expected=snap['expected'],displayed=snap['displayed'],publication=snap['publication'],invocation=str(uuid.uuid4()))
    fields.update({'input:'+SLOT+k:v for k,v in dict(operation=operation,participant=participant,market=market,outcome=outcome,quantity=quantity,conditions=conditions).items()})
    return urlencode(fields).encode()

def submit(body,accepted=True):
    status,r=request('/goo/act',body=body)
    receipts.append({'status':status,'response':r})
    if accepted:assert status==200 and r.get('expected'),(status,r)
    else:assert 400<=status<500,(status,r)
    return r

def act(**kw):
    r=render();submit(invocation(r,**kw));return render()

initial=render()
assert 'alice: 100.000000' in text(initial),text(initial)
first=invocation(initial)
stale=invocation(initial,participant='bob')
submit(first); bought=render()
assert 'alice: 98.600000' in text(bought) and 'alice holds 10 shares of 0:0' in text(bought),text(bought)
submit(first);retried=render()
assert retried['snapshot']['expected']==bought['snapshot']['expected'],'Exact retry changed the ledger'
submit(stale,False);after=render()
assert after['snapshot']['expected']==bought['snapshot']['expected'],'Stale request changed the ledger'
submit(invocation(after,operation='sell',participant='bob'),False)
assert render()['snapshot']['expected']==after['snapshot']['expected'],'Rejected sale changed state'
sold=act(operation='sell')
assert 'alice: 100.000000' in text(sold),text(sold)
act(operation='split')
nested=act(operation='split',market='2',conditions='0:0')
assert '0:0,2:0' in text(nested) and '0:0,2:1' in text(nested),text(nested)
partial=act(operation='resolve',participant='operator',quantity='0')
assert 'alice holds 10 shares of 2:0' in text(partial),text(partial)
finished=act(operation='resolve',participant='operator',market='2',outcome='1',quantity='0')
assert 'alice: 100.000000' in text(finished),text(finished)
submit(invocation(finished),False)
created=act(operation='open-account',participant='carol',quantity='0')
assert 'carol: 100.000000' in text(created),text(created)
# Read the derived namespace collections through the same source contract egui uses.
projections={}
for name in ['accounts','positions','markets','receipts','verses']:
    status,r=request('/goo/source?'+urlencode(dict(target='/x/0x11/app/branchmap/'+name,axis='z')))
    assert status==200,(name,status,r)
    assert r.get("bounded") and isinstance(r.get("members"),list),(name,r)
    projections[name]=r
assert len(projections["accounts"]["members"])==4,projections["accounts"]
assert len(projections["markets"]["members"])==7,projections["markets"]
assert len(projections["receipts"]["members"])==7,projections["receipts"]
assert len(projections["verses"]["members"])==13,projections["verses"]
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'passed':True,'checks':['buy','sell','exact retry','stale version','unowned sale refusal','nested split','partial settlement','full settlement','closed market refusal','account grant','native projections'],'actions':receipts,'projections':projections,'final':created},indent=2)+'\n')
print('PASS: real Goo actions, retry/stale/refusal checks, settlement and native projections')
print(args.output)
