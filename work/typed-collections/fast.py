import sys,json
from pathlib import Path
sys.path[:0]=['x','extras/mounts/medium'];from check_medium_live import Client
s=Path('work/typed-collections/twomin.grove').read_text().replace('twominproof','fastproof')
a=s.index('save_all =');b=s.index('surface =');s=s[:a]+'''save_all =
  @slot
  #meta ;
    "/sys/grove/action_handler": (grove_action_handler save_all/apply)
  ! foil
  + apply
    \\ arguments=myth current=myth
    ^ maybe[myth]
    < f0 arguments.get(['/0x11/gov/medium/fastproof/arg_f0])
    < f0 (text/read f0)
    < f1 arguments.get(['/0x11/gov/medium/fastproof/arg_f1])
    < f1 (natural/input_value/read f1)
    = current (? (eq f0 "") current.del(['/0x11/gov/medium/fastproof/f0]) current.put(['/0x11/gov/medium/fastproof/f0] (pails/t f0)))
    = current
        ? (eq f1 "") current.del(['/0x11/gov/medium/fastproof/f1])
        | current.put(['/0x11/gov/medium/fastproof/f1] (pails/n (nat/parse f1).fall(0)))
    | ./some current

'''+s[b:]
# path literals must be actual paths, not a single quoted full-path segment
for name in ['arg_f0','arg_f1','f0','f1']:
 s=s.replace("['/0x11/gov/medium/fastproof/"+name+"]", "[($x 17) 'gov 'medium 'fastproof '"+name+"]")
Path('work/typed-collections/fast.grove').write_text(s)
c=Client('/Users/ianchanner/.local/share/shrine/development/grove-drop-fit-v3',8198);c.call('read');status,r=c.author('fastproof',s);Path('work/typed-collections/fast.json').write_text(json.dumps(r));print(status,r.get('error','compiled'))
