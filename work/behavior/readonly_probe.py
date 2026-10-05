exec(open('work/behavior/check_native.py').read().split('try:')[0])
try:
 c,frame=s.call('read');frame=workshop_host.typed_collections.project(frame)
 record=next(n for n in frame['nodes'] if n['id']=='/0x11/app/medium/$dcf36f6d-51e2-5414-90f0-fc5c77c51a33')
 fields=record['properties'];print('Native values:',{p['label']:p['value'] for p in fields},flush=True)
 args={p['argument']:('999' if p['label']=='value' else p['value']) for p in fields}
 action=next(o for o in record['view']['occurrences'] if o['kind']=='action' and o['invoke'])
 c,r=s.call('act',frame['expected'],str(__import__('uuid').uuid4()),{'target':record['id'],'expected':record['expected'],'displayed':record['displayed'],'publication':frame['publication'],'control':action['control'],'inputs':args})
 print('Native read-only result:',c,r.get('error','accepted'),flush=True)
 assert c!=200,'Read-only native handler allowed a change'
except Exception as e: print(type(e).__name__,str(e)[:500],flush=True)
finally:s.server_close()
