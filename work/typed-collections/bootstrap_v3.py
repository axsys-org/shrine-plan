from pathlib import Path
import sys,json
sys.path[:0]=['x','extras/mounts/medium']
from check_medium_live import Client
from typed_collections import codec,DATE_CHECK,schema_input,source
c=Client('/Users/ianchanner/.local/share/shrine/development/grove-start-finish-v3',8228)
for kind in ['Natural','Boolean','Date']:
 code=(DATE_CHECK+'\n\n' if kind=='Date' else '')+codec({'key':'value','type':kind,'choices':[]})
 status,result=c.call('native/author',{'subject':'/0x11/gov/user/field_codecs_v1/'+kind.lower(),'source':code,'expected':''},expected=0)
 print(kind,status,result.get('error','installed'),flush=True)
 if status!=200:sys.exit(1)
status,result=c.call('native/author',{'subject':'/0x11/gov/user/collection_values_v1','source':Path('extras/mounts/medium/collection_values.grove').read_text(),'expected':''},expected=0)
print('values',status,result.get('error','installed'),flush=True)
if status!=200:sys.exit(1)
c.call('read',expected=0)
schema=schema_input('Six fields',[{'name':'field'+str(i),'type':'Text'}for i in range(6)])
s=source(schema,'/0x11/gov/medium/sixproof')
status,r=c.author('sixproof',s);Path('work/typed-collections/new-six.json').write_text(json.dumps(r));print('six',status,r.get('error','compiled'),flush=True)
