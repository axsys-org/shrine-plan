#!/usr/bin/env python3
"""Native compilation, publication, action and reuse acceptance. No UI mocks.

Run only against a disposable medium world. Requests use its local supervisor
credential internally; reports contain source, outcomes and cases, not authority.
"""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import uuid
import time

ROOT = Path(__file__).resolve().parents[1]

class Client:
    def __init__(self, world, port):
        self.world, self.port = Path(world), port
        self.authority = (self.world/'src/medium-authority').read_text()
        self.frame = None
        self.results = []
        self.timings = []

    def call(self, operation, body=None, expected=None):
        data = urllib.parse.urlencode(dict(credential=self.authority,
            principal='administrator', operation=operation,
            expected=str(expected if expected is not None else self.frame['expected'] if self.frame else 0),
            event=uuid.uuid4().hex, body=json.dumps(body or {}))).encode()
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}/medium-native', data,
            {'Content-Type':'application/x-www-form-urlencoded'})
        started = time.monotonic()
        pins=self.world/'snap/pins.pack'
        before_bytes=pins.stat().st_size
        try:
            with urllib.request.urlopen(request, timeout=150) as response:
                code, value = response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            code, value = error.code, json.loads(error.read())
        self.timings.append({'operation':operation,'status':code,'seconds':round(time.monotonic()-started,3),
                            'pin_bytes_before':before_bytes,'pin_bytes_after':pins.stat().st_size,
                            'pin_bytes_added':pins.stat().st_size-before_bytes})
        if code == 200: self.frame = value
        return code, value

    def require(self, name, condition, detail=None):
        self.results.append({'name':name,'passed':bool(condition),'detail':detail})
        print(('PASS ' if condition else 'FAIL ')+name, flush=True)
        if not condition: raise AssertionError(detail or name)

    def author(self, identity, source, inputs=()):
        return self.call('author', {'edits':[dict(target='/0x11/app/medium/'+identity,
            source=source,label=identity,intent='Synthetic native acceptance fixture',
            reuse='',inputs=list(inputs))]})

    def node(self, identity):
        return next(n for n in self.frame['nodes'] if n['id'].endswith('/'+identity))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--world',required=True,type=Path)
    parser.add_argument('--port',required=True,type=int)
    parser.add_argument('--disposable',required=True,action='store_true')
    args=parser.parse_args()
    client=Client(args.world,args.port)
    fixtures=ROOT/'extras/mounts/medium/fixtures'
    prefix='qa'+uuid.uuid4().hex[:8]
    a,b,c,d=(prefix+suffix for suffix in ('a','b','c','d'))
    try:
        code,_=client.call('read');client.require('native owner ready',code==200)
        original=client.frame
        source=(fixtures/'counter.grove').read_text().replace('COUNTER',a)
        code,result=client.author(a,source)
        client.require('Grove compiles and publishes an executable native subject',code==200,result if code!=200 else None)
        prior=a
        for name in (b,c,d):
            source=(fixtures/'derived.grove').read_text().replace('DERIVED',name).replace('INPUT',prior)
            selection={'subject':client.node(prior)['id'],'slots':[f'/0x11/gov/medium/{prior}/amount'],'occurrence':''}
            code,result=client.author(name,source,[selection])
            client.require('composition retains higher-order input '+name,code==200,result if code!=200 else None)
            prior=name
        def amount(name):
            return next(f['value'] for f in client.node(name)['fields'] if f['slot'].endswith('/amount'))
        client.require('four-level chain establishes native result',str(amount(d))=='3',amount(d))
        counter=client.node(a)
        action=next(o for o in counter['view']['occurrences'] if o['kind']=='action' and o['invoke'])
        code,result=client.call('act',dict(target=counter['id'],expected=counter['expected'],
            displayed=counter['displayed'],publication=client.frame['publication'],control=action['control'],inputs={}))
        client.require('Goo invokes compiled Foil action',code==200,result if code!=200 else None)
        client.require('native action propagates across four levels',str(amount(d))=='4',amount(d))
        original_ids=[n['id'] for n in client.frame['nodes']]
        original_sources={n['id']:n['source'] for n in client.frame['nodes']}
        selected=client.node(b)['inputs'][0]
        code,result=client.call('detach',{'target':client.node(b)['id'],'index':'0'})
        client.require('decomposition detaches only the contextual edge',code==200,result if code!=200 else None)
        client.require('detachment suspends only dependent realizations',client.node(a)['ready'] and not any(client.node(n)['ready'] for n in (b,c,d)))
        client.require('decomposition preserves definitions and data identities',original_ids==[n['id'] for n in client.frame['nodes']] and original_sources=={n['id']:n['source'] for n in client.frame['nodes']})
        code,result=client.call('rebind',{'target':client.node(b)['id'],'index':'0','selection':selected})
        client.require('reinsertion restores the same native chain',code==200 and all(client.node(n)['ready'] for n in (a,b,c,d)) and str(amount(d))=='4',result if code!=200 else None)
        installed=client.frame
        code,result=client.author(b,'this is deliberately not valid Grove')
        client.require('invalid source rejected',code==422)
        client.call('read')
        client.require('failed compilation leaves native world intact',client.frame==installed)
        code,result=client.call('instantiate',{'pattern':client.node(b)['id']})
        client.require('reuse creates open positions without new source',code==200,result if code!=200 else None)
        new=client.frame['nodes'][-1]
        client.require('new instance has explicit unresolved binding',new['open']==['0'] and not new['ready'])
        code,result=client.call('rebind',{'target':new['id'],'index':'0','selection':dict(subject=client.node(a)['id'],slots=[f'/0x11/gov/medium/{a}/amount'],occurrence='')})
        client.require('existing boundary binds without compiler or model',code==200,result if code!=200 else None)
        instance=client.frame['nodes'][-1]
        client.require('reuse keeps exact source identity',instance['pattern']==client.node(b)['pattern'] and instance['ready'])
        installed=client.frame
        code,result=client.call('rebind',{'target':instance['id'],'index':'0','selection':dict(subject=client.node(c)['id'],slots=['/sys/lede'],occurrence='')})
        client.require('incompatible binding rejected by native contract',code==422)
        client.call('read');client.require('rejected binding preserves established world',client.frame==installed)
        code,result=client.call('define',{'label':'Stale'},expected=original['expected'])
        client.require('stale candidate rejected',code==409)
        # Undo resolves historical native records rather than copying closures.
        code,result=client.call('undo')
        client.require('undo reopens the prior instance binding',code==200 and client.frame['nodes'][-1]['open']==['0'],result if code!=200 else None)
        client.require('undo preserves independent source and behavior',client.node(a)['source']==original_sources[client.node(a)['id']] and amount(d)=='4')
        pins=args.world/'snap/pins.pack'
        size=pins.stat().st_size
        for _ in range(20): client.call('read')
        client.require('unchanged reads do not grow canonical storage',pins.stat().st_size==size)
        client.require('each acceptance operation retains less than 8 MiB',max(t['pin_bytes_added'] for t in client.timings)<8*1024*1024,client.timings)
    finally:
        report=args.world/'medium-acceptance.json'
        report.write_text(json.dumps({'results':client.results,'timings':client.timings},indent=2)+'\n')
        print('Report: '+str(report),flush=True)

if __name__=='__main__':main()
