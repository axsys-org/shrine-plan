#!/usr/bin/env python3
"""Exercise native construction, original references and source-directed execution.

Uses the built workshop, keeps current input values, and restores the authored
formula after testing a shared-definition edit. No browser or full-OS claim.
"""
import argparse, json
from pathlib import Path
from check_medium_live import Client
p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--port',type=int,required=True);args=p.parse_args()
out=args.world/'native-workshop';ids=json.loads((out/'subjects.json').read_text());c=Client(args.world,args.port);assert c.call('read')[0]==200

def node(k):return next(n for n in c.frame['nodes'] if n['id']==ids[k])
def value(k,slot):return next(f['value'] for f in node(k)['fields'] if f['slot']==node(k)['code_root']+'/'+slot)
def source(k):
 n=node(k);return n['source'] or next(v['source'] for v in c.frame['nodes'] if v['code_root']==n['code_root'] and v['source'])
def act(k,label,inputs):
 n=node(k);lines=source(k).splitlines();controls=[o for o in n['view']['occurrences'] if o['kind']=='action' and label in lines[int(o['line'])-1]]
 assert len(controls)==1,(k,label,controls)
 return c.call('act',dict(target=n['id'],control=controls[0]['control'],expected=n['expected'],displayed=n['displayed'],publication=c.frame['publication'],inputs=inputs))

before=c.frame;original=source('sheet');a=int(value('cell','amount'));b=int(value('cell2','amount'))
try:
 c.require('native values feed first sheet',int(value('sheet','amount'))==a+b)
 c.require('a sheet is material for another sheet',node('sheet2')['pattern']==node('sheet')['pattern'] and int(value('sheet2','amount'))==a+b+b)
 c.require('bindings retain original cell refs',node('sheet')['inputs'][0]['subject']==ids['cell'] and node('sheet')['inputs'][1]['subject']==ids['cell2'])
 c.require('image consumes sheet result directly',node('image')['inputs'][1]['subject']==ids['sheet'] and int(value('image','beta'))==a+b)
 c.require('editor is an ordinary source-bound instance',node('editor')['inputs'][0]['subject']==ids['sheet'] and node('editor')['inputs'][0]['slots']==['/sys/grove/definition'])
 before_image=value('image','picture');editor_slot=node('editor')['code_root']+'/draft'
 assert '  | add a b\n' in original
 changed=original.replace('  | add a b\n','  | mul a b\n',1)
 code,result=act('editor','Run this definition',{editor_slot:changed})
 c.require('native editor compiles and installs a real shared program',code==200,result if code!=200 else None)
 c.require('first sheet runs changed Foil',int(value('sheet','amount'))==a*b)
 c.require('second sheet runs same changed definition over first result',int(value('sheet2','amount'))==a*b*b)
 c.require('original cell values and refs survive code replacement',int(value('cell','amount'))==a and int(value('cell2','amount'))==b and node('sheet')['inputs']==next(n for n in before['nodes'] if n['id']==ids['sheet'])['inputs'])
 c.require('visual computation updates downstream',int(value('image','beta'))==a*b and value('image','picture')!=before_image)
 established=c.frame
 code,result=act('editor','Run this definition',{editor_slot:'invalid Grove on purpose'})
 c.require('bad compilation is rejected',code==422)
 c.call('read');c.require('failed compile preserves entire established frame',c.frame==established)
 code,result=act('editor','Run this definition',{editor_slot:original});c.require('source can be changed back without rolling back data',code==200 and int(value('sheet','amount'))==a+b)
 if 'filter' in ids and node('filter')['authored']:
  c.require('image filter consumes original image ref',node('filter')['inputs'][0]['subject']==ids['image'])
  image=value('image','picture');mode=int(value('filter','mode'));prior=value('filter','picture')
  code,_=act('filter','Next treatment',{})
  c.require('filter action changes its native representation and leaves input intact',code==200 and value('filter','picture')!=prior and value('image','picture')==image)
  for _ in range(3):assert act('filter','Next treatment',{})[0]==200
  c.require('four modes return to original native treatment',int(value('filter','mode'))==mode and value('filter','picture')==prior)
 if 'dictionary' in ids and node('dictionary')['authored']:
  root=node('dictionary')['code_root'];old=value('dictionary','query');term=value('entry','term');meaning=value('entry','meaning')
  code,_=act('dictionary','Find exact term',{root+'/query':term})
  c.require('dictionary searches real native entries',code==200 and meaning in value('dictionary','result'))
  code,_=act('dictionary','Find exact term',{root+'/query':'no-such-native-entry-qa'})
  c.require('dictionary does not invent missing information',code==200 and value('dictionary','result').startswith('No exact entry'))
  assert act('dictionary','Find exact term',{root+'/query':old})[0]==200
 size=(args.world/'snap/pins.pack').stat().st_size;events=c.frame['events']
 for _ in range(5):assert c.call('read')[0]==200
 c.require('unchanged inspection adds no journal or pins',(args.world/'snap/pins.pack').stat().st_size==size and c.frame['events']==events)
finally:
 report={'results':c.results,'timings':c.timings,'subject_ids':ids,'coverage':'Actual native compilation, actions and maintained bindings. No rendered browser QA, spreadsheet feature-completeness, raster editing or complete OS acceptance.'}
 (out/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Report:',out/'acceptance.json',flush=True)
