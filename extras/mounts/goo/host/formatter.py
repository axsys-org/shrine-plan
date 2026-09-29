"""Conservative Foil whitespace formatter, guarded by exact native Rex structure."""
import argparse, pathlib
from runtime import PACKAGE, invoke

def structure(value):
    if isinstance(value,dict):return {k:structure(v) for k,v in value.items() if k!='span'}
    if isinstance(value,list):return [structure(v) for v in value]
    return value

def has_error(value):
    if isinstance(value,dict):return isinstance(value.get('shape'),dict) and 'bad' in value['shape'] or any(has_error(v) for v in value.values())
    if isinstance(value,list):return any(has_error(v) for v in value)
    return False

def candidate(source):
    return '\n'.join(line.rstrip(' \t') for line in source.replace('\r\n','\n').split('\n')).rstrip('\n')+'\n'

def format_sources(sources):
    proposed=[candidate(s) for s in sources]
    parsed=invoke([('syntax',s) for pair in zip(sources,proposed) for s in pair],check_sources=False)
    result=[]
    for old,new,a,b in zip(sources,proposed,parsed[::2],parsed[1::2]):
        if a.get('ok') is not True or b.get('ok') is not True or has_error(a) or has_error(b):
            raise ValueError('formatter requires parseable Foil source')
        if structure(a)!=structure(b):
            raise ValueError('whitespace change would alter syntax or string payload; left unchanged')
        result.append(new)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('files',nargs='*',type=pathlib.Path)
    args=parser.parse_args()
    paths=args.files or sorted(PACKAGE.glob('*.foil'))
    before=[p.read_bytes().decode('utf-8') for p in paths]
    try:after=format_sources(before)
    except ValueError as error:parser.exit(2,str(error)+'\n')
    changed=[(p,text) for p,old,text in zip(paths,before,after) if old!=text]
    for p,text in changed:
        print(p)
        if not args.check:p.write_bytes(text.encode('utf-8'))
    if args.check and changed:raise SystemExit(1)
