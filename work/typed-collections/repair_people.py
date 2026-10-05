import sys,json
from pathlib import Path
sys.path[:0]=['x','extras/mounts/medium'];from check_medium_live import Client;from typed_collections import project,schema_from,source
c=Client('/Users/ianchanner/.local/share/shrine/development/grove-start-finish-v3',8228);c.call('read');project(c.frame)
p=next(n for n in c.frame['nodes'] if n['label']=='People' and n['parent']=='/');s=schema_from(p)
code,r=c.call('author',{'edits':[{'target':p['id'],'source':source(s,p['code_root']),'label':'People','intent':'Repair native input argument binding; retain user data','scope':'definition','reuse':'','inputs':[]}]});print('definition',code,r.get('error','ok'),flush=True)
if code!=200:sys.exit(1)
n=next(n for n in c.frame['nodes'] if n['parent']==p['id']);a=next(o for o in n['view']['occurrences'] if o['kind']=='action' and o['invoke'])
code,r=c.call('act',dict(target=n['id'],expected=n['expected'],displayed=n['displayed'],publication=c.frame['publication'],control=a['control'],inputs={p['code_root']+'/arg_f0':'Ana'}));project(r);print('restored',code,[(n['properties']) for n in r.get('nodes',[]) if n.get('parent')==p['id']],r.get('error',''))
