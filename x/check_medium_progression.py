#!/usr/bin/env python3
"""Native definition/occurrence evolution, absent fields and stable requirements.

Fixture source is authored for coverage. It is not evidence of model inference.
"""
import argparse
import json
import uuid
from check_medium_live import Client, ROOT


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',required=True);ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--disposable',action='store_true',required=True);args=ap.parse_args()
    c=Client(args.world,args.port);prefix='p'+uuid.uuid4().hex[:8];person=prefix+'person';people=prefix+'people'
    fixtures=ROOT/'extras/mounts/medium/fixtures'
    source=(fixtures/'person.grove').read_text().replace('PERSON',person)
    root='/0x11/gov/medium/'+person
    def author(identity,source,inputs=()):
        label='Person' if identity==person else 'People' if identity==people else 'Another group'
        return c.call('author',{'edits':[dict(target='/0x11/app/medium/'+identity,source=source,
            label=label,intent='Synthetic native progression fixture',reuse='',scope='occurrence',inputs=list(inputs))]})
    def field(n,slot):return next((f['value'] for f in n['fields'] if f['slot']==slot),None)
    def action(n,text,values):
        # Native control order is read from the actual compiled Goo frame.
        controls=[o for o in n['view']['occurrences'] if o['kind']=='action' and o['invoke']]
        o=controls[0 if text=='name' else 1]
        return c.call('act',dict(target=n['id'],expected=n['expected'],displayed=n['displayed'],publication=c.frame['publication'],control=o['control'],inputs=values))
    def edit(n,source,scope='occurrence',inputs=None):
        return c.call('author',{'edits':[dict(target=n['id'],source=source,label=n['label'],intent='Native progression acceptance',reuse='',scope=scope,inputs=n['inputs'] if inputs is None else inputs)]})
    try:
        status,_=c.call('read');c.require('native owner ready',status==200)
        status,res=author(person,source);c.require('Person compiles with genuinely absent optional name',status==200,res if status!=200 else None)
        emma=c.node(person)
        c.require('no personal value invented',field(emma,root+'/full_name') is None)
        status,res=action(emma,'name',{root+'/full_name':'Emma'});c.require('ordinary Goo action fills Emma name',status==200,res if status!=200 else None)
        status,_=c.call('instantiate',{'pattern':emma['id']});c.require('fresh Person occurrence created',status==200)
        lucas_id=c.frame['nodes'][-1]['id'];lucas_name=lucas_id.rsplit('/',1)[-1]
        c.require('new occurrence did not clone Emma name',field(c.node(lucas_name),root+'/full_name') is None)
        status,res=action(c.node(lucas_name),'name',{root+'/full_name':'Lucas'});c.require('Lucas is separately editable',status==200,res if status!=200 else None)
        selections=[dict(subject=c.node(n)['id'],slots=[],occurrence='') for n in (person,lucas_name)]
        people_source=(fixtures/'people.grove').read_text().replace('PERSON',person).replace('PEOPLE',people)
        status,res=author(people,people_source,selections);c.require('People references existing identities',status==200,res if status!=200 else None)
        positions=c.node(people)['typing']['positions'];keys=[p['identity']['key'] for p in positions]
        c.require('two equal role types have distinct stable positions',keys[0]!=keys[1] and positions[0]['role']==positions[1]['role'])
        v2=source.replace('person_role =','birthday =\n  @slot\n\nperson_role =').replace('    %/full_name: text','    %/full_name: text\n    %/birthday: text')
        birthday='''    group(on = card, action = .poke, myth = {
      'ROOT/birthday = .input(card.birthday)
    }) {
      text("Birthday", '/sys/slot/caption)
      input('ROOT/birthday)
      action("Keep birthday")
    }
'''.replace('ROOT',root)
        v2=v2.rsplit('  }',1)[0]+birthday+'  }\n'
        status,_=edit(c.node(person),v2);c.require('occurrence scope cannot silently replace shared source',status==422)
        status,res=edit(c.node(lucas_name),v2,'definition');c.require('definition edit through an occurrence updates shared native code',status==200,res if status!=200 else None)
        for name,value in ((person,'Emma'),(lucas_name,'Lucas')):
            n=c.node(name)
            c.require(value+' retains name and identity',field(n,root+'/full_name')==value)
            states=n['typing']['role']['values']
            c.require(value+' has an absent typed birthday position',any(f['declaration']['slot']==root+'/birthday' and f['status']=='absent' for f in states))
        c.require('definition owner records new source; occurrence stays shared',c.node(person)['source']==v2 and c.node(lucas_name)['source']=='' and c.node(person)['pattern']==c.node(lucas_name)['pattern'])
        for name,date in ((person,'Oct 14'),(lucas_name,'Nov 2')):
            status,res=action(c.node(name),'birthday',{root+'/birthday':date});c.require('occurrence birthday entry '+date,status==200,res if status!=200 else None)
        c.require('existing People composition recomputes from both occurrences',field(c.node(people),c.node(people)['code_root']+'/summary')=='Emma - Oct 14 / Lucas - Nov 2')
        status,_=c.call('instantiate',{'pattern':emma['id']});fresh=c.frame['nodes'][-1]
        c.require('pattern copy has fresh identity and fresh personal positions',status==200 and fresh['id']!=emma['id'] and field(fresh,root+'/full_name') is None and field(fresh,root+'/birthday') is None)
        status,_=c.call('duplicate',{'pattern':emma['id']});copied=c.frame['nodes'][-1]
        c.require('explicit value copy keeps data but gets new identity',status==200 and copied['id']!=emma['id'] and field(copied,root+'/full_name')=='Emma' and field(copied,root+'/birthday')=='Oct 14')
        status,_=c.call('detach',{'target':c.node(people)['id'],'requirement':keys[0]})
        c.require('detach addresses requirement identity',status==200 and c.node(people)['open']==['0'])
        status,res=edit(c.node(people),people_source)
        c.require('source edit cannot reactivate detached former filler',status==200 and not c.node(people)['ready'] and c.node(people)['open']==['0'],res if status!=200 else None)
        bad=[selections[1],selections[1]];before=c.frame
        status,_=edit(c.node(people),people_source,inputs=bad);c.require('source edit cannot replace unbound provenance',status==422)
        c.call('read');c.require('rejected edit leaves installed state identical',c.frame==before)
        status,res=c.call('rebind',{'target':c.node(people)['id'],'requirement':keys[0],'selection':selections[0]})
        c.require('reinsertion restores same positions and realization',status==200 and c.node(people)['ready'] and [p['identity']['key'] for p in c.node(people)['typing']['positions']]==keys,res if status!=200 else None)
        renamed=people_source.replace("'first]","'other]")
        status,_=edit(c.node(people),renamed);c.require('source edit cannot rename an established requirement',status==422)
        new=prefix+'unanchored'
        status,res=author(new,people_source.replace(people,new),[dict(subject='/',slots=[],occurrence='')]*2)
        c.require('new composition can hold unanchored typed requirements',status==200 and c.node(new)['open']==['0','1'] and not c.node(new)['ready'],res if status!=200 else None)
        n=c.node(new);key=n['typing']['positions'][0]['identity']['key']
        status,_=c.call('rebind',{'target':n['id'],'requirement':key,'selection':selections[0]})
        c.require('partial establishment keeps the other requirement open',status==200 and c.node(new)['open']==['1'] and not c.node(new)['ready'])
    finally:
        (c.world/'progression-acceptance.json').write_text(json.dumps({'checks':c.results,'timings':c.timings},indent=2)+'\n')
        if c.frame:(c.world/'progression-frame.json').write_text(json.dumps(c.frame,indent=2)+'\n')

if __name__=='__main__':main()
