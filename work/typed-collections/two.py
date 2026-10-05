import sys,json
from pathlib import Path
sys.path[:0]=['x','extras/mounts/medium']
from check_medium_live import Client
from typed_collections import schema_input,source
c=Client('/Users/ianchanner/.local/share/shrine/development/grove-drop-fit-v3',8198);c.call('read')
s=schema_input('Two fields',[{'name':'title','type':'Text'},{'name':'duration','type':'Natural'}]);code=source(s,'/0x11/gov/medium/twofieldsproof');Path('work/typed-collections/two.grove').write_text(code)
status,result=c.author('twofieldsproof',code);Path('work/typed-collections/two.json').write_text(json.dumps(result,indent=2));print(status,result.get('error','compiled')[:1400])
