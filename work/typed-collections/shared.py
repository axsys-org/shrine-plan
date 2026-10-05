import sys,json
from pathlib import Path
sys.path[:0]=['x','extras/mounts/medium']
from check_medium_live import Client
from typed_collections import codec,DATE_CHECK
c=Client('/Users/ianchanner/.local/share/shrine/development/grove-drop-fit-v3',8198);c.call('read')
for kind in ['Boolean','Date']:
 root='/0x11/gov/user/field_codecs_v1/'+kind.lower()
 code=(DATE_CHECK+'\n\n' if kind=='Date' else '')+codec({'key':'value','type':kind,'choices':[]})
 status,result=c.call('native/author',{'subject':root,'source':code,'expected':''},expected=0)
 print(kind,status,result.get('error','installed')[:600],flush=True)
 Path('work/typed-collections/codec-'+kind+'.json').write_text(json.dumps(result,indent=2))
