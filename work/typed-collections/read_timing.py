import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path('extras/mounts/medium').resolve()))
import workshop_host
w=Path('/Users/ianchanner/.local/share/shrine/development/grove-start-finish-v3')
s=workshop_host.base.Server(Path('extras/mounts/medium/workshop'),w,8228,(w/'src/medium-authority').read_text(),0)
workshop_host.configure(s)
for op in ['read','fit/read']:
 t=time.perf_counter();code,frame=s.call(op)
 print(op,code,round((time.perf_counter()-t)*1000),len(json.dumps(frame)),flush=True)
 if op=='read':
  for n in frame.get('nodes',[]):
   vals={p['label']:p['value'] for p in n.get('properties',[])}
   if vals.get('title')=='Electrical':print({'Electrical status':vals.get('status'),'record':n['id']},flush=True)
s.server_close()
