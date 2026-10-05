#!/usr/bin/env python3
"""Real native source-as-material acceptance; no browser/domain evaluator.

The retained fixture is useful software: two uses of a definition, a dependent
computation, a Grove source editor, and a source editor inspecting that editor.
"""
import argparse,json,uuid
from check_medium_live import Client,ROOT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',required=True);parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args();c=Client(args.world,args.port)
    suffix=uuid.uuid4().hex[:6]
    identities={name:name+suffix for name in ('number','source','successor')}
    native_node=c.node
    c.node=lambda ident:native_node(identities.get(ident,ident))
    draft_slot='/0x11/gov/medium/'+identities['source']+'/draft'
    def author(ident,label,source,inputs=()):
        return c.call('author',{'edits':[dict(target='/0x11/app/medium/'+identities.get(ident,ident),label=label,source=source,
            intent='Native construction acceptance; ordinary reusable Grove.',reuse='',scope='occurrence',inputs=list(inputs))]})
    def selected(ident,slots=()):return dict(subject='/0x11/app/medium/'+identities.get(ident,ident),slots=list(slots),occurrence='')
    def amount(ident):
        n=c.node(ident);return next(f['value'] for f in n['fields'] if f['slot']==n['code_root']+'/amount')
    def act(ident,inputs=None):
        n=c.node(ident);controls=[o for o in n['view']['occurrences'] if o['kind']=='action' and o['invoke']]
        return c.call('act',dict(target=n['id'],control=controls[0]['control'],inputs=inputs or {},
            expected=n['expected'],displayed=n['displayed'],publication=c.frame['publication']))
    def require(name,status,result):c.require(name,status==200,result if status!=200 else None)
    try:
        status,result=c.call('read');require('native owner ready',status,result)
        c.require('owner exposes construction capabilities','native-definition-actions' in c.frame['features'])
        counter=(ROOT/'extras/mounts/medium/fixtures/counter.grove').read_text().replace('COUNTER',identities['number'])
        status,result=author('number','Number',counter);require('native number definition compiled',status,result)
        status,result=c.call('instantiate',{'pattern':c.node('number')['id'],'inputs':[]});require('second use shares definition',status,result)
        second=c.frame['nodes'][-1]['id'].rsplit('/',1)[-1]
        status,result=act('number');require('native number action executes',status,result)
        c.require('separate uses retain separate state',amount('number')=='1' and amount(second)=='0')
        derived=(ROOT/'extras/mounts/medium/fixtures/derived.grove').read_text().replace('INPUT',identities['number']).replace('DERIVED',identities['successor'])
        status,result=author('successor','Successor',derived,[selected('number')]);require('computation uses the original subject',status,result)
        editor=(ROOT/'extras/mounts/medium/library/source_editor.grove').read_text().replace('EDITOR',identities['source'])
        status,result=author('source','Source editor',editor,[selected('number',['/sys/grove/definition'])]);require('editor is compiled Grove with an exact source binding',status,result)
        c.require('multiline editing is a native Goo presentation','<textarea' in c.node('source')['view']['html'])
        old=c.frame
        status,result=act('source',{draft_slot:'not valid native code = ! foil % nope'})
        c.require('broken code is rejected through the native action',status==422,result if status!=422 else None)
        c.call('read');c.require('failed compiler leaves source, values and identities unchanged',c.frame==old)
        updated=counter.replace('card.amount.inc','(add card.amount 5)').replace('Add one','Add five')
        status,result=act('source',{draft_slot:updated});require('native editor recompiles the shared definition',status,result)
        c.require('source update preserved both values',amount('number')=='1' and amount(second)=='0')
        c.require('both uses receive new native controls',all('Add five' in c.node(i)['view']['html'] for i in ('number',second)))
        status,result=act('number');require('first use executes changed code',status,result)
        status,result=act(second);require('second use executes the same changed code',status,result)
        c.require('source change propagates through shared-reference computation',amount('number')=='6' and amount(second)=='5' and amount('successor')=='7')
        status,result=c.call('instantiate',{'pattern':c.node('source')['id'],
            'inputs':[selected('source',['/sys/grove/definition'])]});require('editor can be applied to an editor',status,result)
        outer=c.frame['nodes'][-1]['id'].rsplit('/',1)[-1]
        changed_editor=editor.replace('Run this definition','Run source')
        status,result=act(outer,{draft_slot:changed_editor});require('an editor edits its own shared implementation through another use',status,result)
        c.require('editor evolution retains both exact bindings',c.node('source')['inputs'][0]['subject']==c.node('number')['id'] and c.node(outer)['inputs'][0]['subject']==c.node('source')['id'])
        c.require('new editor code reaches both live presentations',all('Run source' in c.node(i)['view']['html'] for i in ('source',outer)))
        # Reference correspondence is not authority: a normal value edge cannot
        # drive definition publication, even if its data includes source facts.
        status,result=c.call('instantiate',{'pattern':c.node('source')['id'],'inputs':[selected('number')]});require('ordinary data projection can inspect a definition',status,result)
        powerless=c.frame['nodes'][-1]['id'].rsplit('/',1)[-1]
        old=c.frame
        status,result=act(powerless,{draft_slot:counter});c.require('data reference does not grant source-edit authority',status==422)
        c.call('read');c.require('rejected authority does not change the world',old==c.frame)
        status,result=c.call('retire',{'target':c.node(powerless)['id']});require('unused instance retires without removing the shared definition',status,result)
        # The repeated use can keep its definition relation open without data loss.
        status,result=c.call('detach',{'target':c.node(outer)['id'],'index':'0'});require('editor input detaches natively',status,result)
        c.require('detached editor is unavailable while other software keeps running',not c.node(outer)['ready'] and c.node('source')['ready'] and amount('successor')=='7')
        status,result=c.call('rebind',{'target':c.node(outer)['id'],'index':'0','selection':selected('source',['/sys/grove/definition'])});require('exact source connection recovers',status,result)
        c.call('read');before=c.frame
        pins=(c.world/'snap'/'pins.pack').stat().st_size
        for _ in range(20):c.call('read')
        c.require('unchanged frames do not mutate native history',before==c.frame)
        c.require('unchanged frames do not grow pins',(c.world/'snap'/'pins.pack').stat().st_size==pins)
        print('CONSTRUCTION ACCEPTANCE PASSED',flush=True)
    finally:
        (c.world/'construction-acceptance.json').write_text(json.dumps({'checks':c.results,'timings':c.timings},indent=2)+'\n')
        if c.frame:(c.world/'construction-frame.json').write_text(json.dumps(c.frame,indent=2)+'\n')
if __name__=='__main__':main()
