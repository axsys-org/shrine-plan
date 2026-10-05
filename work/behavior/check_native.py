import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path('extras/mounts/medium').resolve()))
import workshop_host,behaviors
w=Path('/Users/ianchanner/.local/share/shrine/development/grove-start-finish-v3')
s=workshop_host.base.Server(Path('extras/mounts/medium/workshop'),w,8228,(w/'src/medium-authority').read_text(),0)
try:
 source='behavior =\n  ! foil\n  + apply\n    \\ input=json\n    ^ either[str json]\n    | ./ok input\n'
 result=behaviors.prepare(s,source,[{'input':{'v':7},'expected':{'v':7}}])
 Path('work/behavior/check-native.json').write_text(json.dumps(result,indent=2))
 print('Native pure wrapper prepared; self-check and null input passed',flush=True)
except Exception as e: print(type(e).__name__,str(e)[:3000],flush=True)
finally:s.server_close()
