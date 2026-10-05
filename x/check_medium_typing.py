#!/usr/bin/env python3
"""Actual native role/hole export and optional live Jev inference; disposable only."""
import argparse
import importlib.util
import json
import threading
import uuid
from pathlib import Path
from check_medium_live import Client, ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--world',required=True,type=Path)
    parser.add_argument('--port',required=True,type=int)
    parser.add_argument('--disposable',required=True,action='store_true')
    parser.add_argument('--jev',action='store_true',help='Send synthetic native fixture context to OpenRouter')
    args=parser.parse_args()
    client=Client(args.world,args.port)
    receipts=[]
    try:
        status,_=client.call('read');client.require('native owner ready',status==200)
        prefix='typing'+uuid.uuid4().hex[:8];a,b=prefix+'a',prefix+'b'
        fixtures=ROOT/'extras/mounts/medium/fixtures'
        status,_=client.author(a,(fixtures/'counter.grove').read_text().replace('COUNTER',a))
        client.require('actual counter source compiled',status==200)
        origin=client.node(a)
        role=origin['typing']['role']
        field=next(f for f in role['fields'] if f['slot'].endswith('/amount'))
        client.require('compiled role exposes the exact opaque slot',field['slot']==origin['code_root']+'/amount')
        client.require('compiled codec has exact reference and revision',field['type']['address']==origin['code_root']+'/number' and field['type']['case'] is not None)
        selection={'subject':origin['id'],'slots':[field['slot']],'occurrence':''}
        status,_=client.author(b,(fixtures/'derived.grove').read_text().replace('DERIVED',b).replace('INPUT',a),[selection])
        client.require('derived behavior established through real contract',status==200)
        before=client.node(b)
        status,_=client.call('detach',{'target':before['id'],'index':'0'})
        opened=client.node(b);position=opened['typing']['positions'][0]
        client.require('detach suspends use while retaining role declarations',status==200 and not opened['ready'] and opened['view'] is None and opened['typing']['role']==before['typing']['role'])
        client.require('hole retains exact prior selection and contract',position['status']=='open' and position['selection']==selection and position['contract']==before['typing']['accepts'])
        client.require('native trace identifies detach event and original basis',client.frame['events'][0]['kind']=='detach' and bool(client.frame['events'][0]['id']) and bool(client.frame['events'][0]['basis']))
        if args.jev:
            spec=importlib.util.spec_from_file_location('typing_model',ROOT/'extras/mounts/medium/model.py')
            model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
            gesture={'kind':'compose','selected':selection,'placement':{'owner':opened['id'],'index':0},'text':'Restore the former binding at this open position, preserving the established definition.'}
            context={'frame':model.scoped_frame(client.frame,gesture),'gesture':gesture}
            questions,domain=model.binding_questions(context['frame'])
            client.require('Jev question derives from native hole and contract',bool(questions) and domain['positions'][0]['owner']==opened['id'])
            _,receipt=model.decision(context,threading.Event());receipts.append(receipt)
            client.require('live Jev returns contextual binding distribution',bool(receipt['answers'].get('binding_0')))
            snapshot=client.frame
            client.call('read')
            client.require('inference does not fill the hole or mutate native state',client.frame==snapshot)
        status,_=client.call('rebind',{'target':opened['id'],'index':'0','selection':selection})
        restored=client.node(b)
        client.require('native recheck restores the exact boundary',status==200 and restored['ready'] and restored['typing']['positions'][0]['status']=='bound')
        client.require('reinsert preserves source and native field identities',restored['source']==before['source'] and restored['fields']==before['fields'])
    finally:
        (args.world/'typing-acceptance.json').write_text(json.dumps({'checks':client.results,'timings':client.timings,'model_runs':receipts},indent=2)+'\n')


if __name__=='__main__':main()
