exec(open('work/behavior/check_native.py').read().split('try:')[0])
try:
 code, frame=s.call('read')
 assert code==200,code
 frame=workshop_host.typed_collections.project(frame)
 roots={n['id']:n for n in frame['nodes'] if not n.get('parent') or n.get('parent')=='/'}
 collections=[]
 for ident,n in roots.items():
  if not n.get('collectionSchema'):continue
  members=[x for x in frame['nodes'] if x.get('parent')==ident]
  collections.append({'id':ident,'name':n['label'],'fields':[{'name':p['label'],'type':p.get('type'),'writable':p.get('writable',True)} for p in n.get('properties',[])],'records':[{'id':r['id'],'values':{p['label']:p.get('value') for p in r['properties']}} for r in members]})
 code, scene=s.call('fit/read');assert code==200,code
 components=[{'id':b['id'],'name':b.get('content',[{}])[0].get('text'),'revision':b['componentDefinition']['revision']} for b in scene['blocks'] if b.get('componentDefinition') and not b.get('archived')]
 job=json.loads((w/'pure-programs/48f22b3be7f6445aaf53eab462694166.json').read_text())['job']
 result={'captured_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'url':'http://127.0.0.1:8229/','world':str(w),'collections':collections,'components':components,'native_function':{k:job[k] for k in ['id','status','name','requires','receipts']},'surface':job['candidate']['surface'],'native_check_count':len(job['candidate']['cases']),'scope':'Native readback. Browser interaction evidence is recorded separately; this is not proof of visual fidelity.'}
 Path('/Users/ianchanner/Documents/Codex/2026-10-04/design-shrine-plan-rl-harness-thread/outputs/grove-native-readback.json').write_text(json.dumps(result,indent=2))
 print({'collections':[(c['name'],len(c['records'])) for c in collections],'components':components,'function':job['status'],'checks':len(job['candidate']['cases'])})
finally:s.server_close()
