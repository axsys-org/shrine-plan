#!/usr/bin/env python3
"""Negative admission and whole-composition binding against progression fixtures."""
import argparse
import json
import uuid
from check_medium_live import Client, ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--world',required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--disposable',action='store_true',required=True)
    args=parser.parse_args(); c=Client(args.world,args.port)
    try:
        c.call('read')
        group=next(n for n in reversed(c.frame['nodes']) if n['label']=='People' and n['ready'])
        person=next(n for n in c.frame['nodes'] if n['id']==group['inputs'][0]['subject'])
        key=group['typing']['positions'][0]['identity']['key']
        # Custom accepts only checks name. Native role additionally requires lede.
        limited={**group['inputs'][0],'slots':[person['code_root']+'/full_name']}
        before=c.frame
        code,res=c.call('rebind',{'target':group['id'],'requirement':key,'selection':limited})
        c.require('native role rejects projection accepted by the custom name check',code==422 and 'does not satisfy requirement' in res.get('error',''),res)
        c.call('read');c.require('role rejection is atomic',c.frame==before)
        code,res=c.call('detach',{'target':group['id'],'requirement':key+'/unknown','index':'0'})
        c.require('unknown stable key never falls back to a valid index',code==400 and 'exact requirement' in res.get('error',''),res)
        c.call('read');c.require('invalid requirement leaves bindings unchanged',c.frame==before)
        identity='use'+uuid.uuid4().hex[:8]
        source=(ROOT/'extras/mounts/medium/fixtures/group_use.grove').read_text().replace('USE',identity).replace('PEOPLE',group['code_root'].rsplit('/',1)[-1])
        def author(inputs,src=source):
            return c.call('author',{'edits':[{'target':'/0x11/app/medium/'+identity,
                'label':'Group use','intent':'Synthetic native requirement fixture',
                'source':src,'scope':'occurrence','reuse':'','inputs':inputs}]})
        empty={'subject':'/','slots':[],'occurrence':''}
        code,res=author([empty]);c.require('higher-order requirement can exist without a filler',code==200,res if code!=200 else None)
        n=c.node(identity);requirement=n['typing']['positions'][0]['identity']['key']
        code,res=c.call('rebind',{'target':n['id'],'requirement':requirement,'selection':group['inputs'][0]})
        c.require('a constituent does not satisfy the whole composition contract',code==422 and 'does not satisfy requirement' in res.get('error',''),res)
        code,res=c.call('rebind',{'target':n['id'],'requirement':requirement,'selection':{'subject':group['id'],'slots':[],'occurrence':''}})
        c.require('established composition fills the same requirement',code==200 and c.node(identity)['ready'],res if code!=200 else None)
        use=c.node(identity)
        c.require('one reference retains the composition interior',len(use['inputs'])==1 and use['inputs'][0]['subject']==group['id'] and next(n for n in c.frame['nodes'] if n['id']==group['id'])['inputs']==group['inputs'])
        before=c.frame
        code,res=author(group['inputs'])
        c.require('one requirement cannot silently become two scalar inputs',code==422 and 'exactly one realization position' in res.get('error',''),res)
        c.call('read');c.require('arity failure preserves the current realization',c.frame==before)
    finally:
        (c.world/'requirements-acceptance.json').write_text(json.dumps({'checks':c.results,'timings':c.timings},indent=2)+'\n')


if __name__=='__main__':main()
