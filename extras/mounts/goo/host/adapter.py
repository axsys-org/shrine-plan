"""Process I/O and framing only; all Goo pass code belongs in Foil."""
import json, math, subprocess, uuid
from decimal import Decimal
from runtime import invoke, verify, run
from wire import strict_tree

def failure(stage,message):return dict(version=1,ok=False,stage=stage,error=str(message))
def integer(value):
    return type(value) in (int,float,Decimal) and math.isfinite(value) and value==int(value) and -2**63<=value<2**63

def validate(req):
    if not isinstance(req,dict):raise ValueError('expected request object')
    if req.get('action')!='codec' and (not integer(req.get('version')) or req['version']!=1):raise ValueError('unsupported version')
    action=req.get('action')
    if action in {'capabilities','tests','fonts'}:
        if set(req)!={'version','action'}:raise ValueError('unexpected request field')
    elif action in {'source','parse'}:
        fields={'version','action','source'}
        if action=='source':fields|={'viewPath','budget','hiddenIds','hiddenPaths','uniform','width','textScale','direction'}
        if not set(req)<=fields:raise ValueError('unexpected request field')
        if not isinstance(req.get('source'),str) or '\0' in req['source']:raise ValueError('expected NUL-free source string')
        req={k:v for k,v in req.items() if v is not None}
        for key in ('width','textScale'):
            if key in req:
                value=req[key]
                if type(value) not in (int,float,Decimal) or not math.isfinite(value) or float(value)<0:raise ValueError('invalid '+key)
        if not 0<float(req.get('textScale',1))<=10 or float(req.get('width',752))>100000:raise ValueError('dimensions out of range')
        if 'viewPath' in req:
            path=req['viewPath']
            if not isinstance(path,str) or not path.startswith('/') or (path!='/' and any(not part or part in {'.','..'} or any(not (c.isalnum() or c in '_-.') for c in part) for part in path[1:].split('/'))):raise ValueError('invalid viewPath')
        if 'hiddenIds' in req and (not isinstance(req['hiddenIds'],list) or any(not isinstance(v,str) or not v for v in req['hiddenIds'])):raise ValueError('invalid hiddenIds')
        if 'hiddenPaths' in req:
            paths=req['hiddenPaths']
            if not isinstance(paths,list) or any(not isinstance(path,list) or any(not integer(v) or v<0 for v in path) for path in paths):raise ValueError('invalid hiddenPaths')
        if 'uniform' in req and type(req['uniform']) is not bool:raise ValueError('invalid uniform')
        if 'budget' in req and (not integer(req['budget']) or req['budget'] not in (0,1,2)):raise ValueError('invalid budget')
        if req.get('direction') is not None and req['direction'] not in ('ltr','rtl'):raise ValueError('invalid direction')
    elif action in {'echo','print','goo-print'}:
        if set(req)!={'version','action','trees'} or not isinstance(req['trees'],list):raise ValueError('expected trees array')
        for tree in req['trees']:strict_tree(tree)
    elif action=='codec':
        if set(req)!={'version','action','phase','tree'}:raise ValueError('expected phase and tree')
    elif action=='render':
        if not set(req)<={'version','action','tree','width','textScale','viewPath','direction'}:raise ValueError('unexpected render field')
    elif action in {'layout','plan'}:
        fields={'version','action','tree','width','textScale','measurements'}
        if not set(req)<=fields:raise ValueError('unexpected layout field')
    elif action=='ascii':
        if set(req)!={'version','action','tree','textScale','widths'}:raise ValueError('expected tree, textScale and widths')
    elif action=='validate-measurement':
        if set(req)!={'version','action','result'}:raise ValueError('expected measurement result')
    elif action=='fixture':
        fields={'version','action','tree','measurements','viewPath','budget','hiddenIds','hiddenPaths','uniform','width','textScale','direction'}
        if not set(req)<=fields:raise ValueError('unexpected fixture field')
        if req.get('direction') is not None and req['direction'] not in ('ltr','rtl'):raise ValueError('invalid direction')
    else:raise ValueError('unknown action')
    return True

def retained(directory,requests):
    out,err=run([str(directory/'retained-rex')],directory,json.dumps(requests),120)
    values=json.loads(out)
    if not isinstance(values,list) or len(values)!=len(requests):raise ValueError('invalid Rex response count')
    for value in values:
        if value.get('version')!=1 or value.get('ok') is not True:raise ValueError(value.get('error','Rex failed'))
        for tree in value.get('trees',[]):strict_tree(tree)
    return values

def allocate_ids(count):
    # Count is produced by Foil normalization; this boundary supplies entropy only.
    return [str(uuid.uuid4()) for _ in range(count)]

def batch(requests):
    answers=[None]*len(requests);valid=[]
    for i,req in enumerate(requests):
        try:
            validate(req);valid.append(i)
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as e:answers[i]=failure('protocol',e)
    if not valid:return answers
    stage='build'
    try:
        directory,_=verify()
        stage='rex/parse'
        parsing=[i for i in valid if requests[i]['action'] in {'source','parse'}]
        parsed=retained(directory,[dict(version=1,action='parse',source=requests[i]['source']) for i in parsing]) if parsing else []
        trees={i:r['trees'] for i,r in zip(parsing,parsed)}
        compiling=[i for i in valid if requests[i]['action']=='source']
        stage='foil'
        counts=invoke([('prepare',trees[i]) for i in compiling],directory,False) if compiling else []
        identities={}
        for i,r in zip(compiling,counts):
            try:identities[i]=allocate_ids(r['count']) if r['count'] else []
            except (OSError,RuntimeError):
                # Native allocation records a normalized-stage crash and keeps prior outputs.
                identities[i]=[]
        calls=[]
        for i in valid:
            action=requests[i]['action']
            if action=='source':calls.append(('compile',(trees[i],codec_json(requests[i]),json.dumps(identities[i]))))
            elif action=='render':calls.append(('render',codec_json(requests[i])))
            elif action=='fixture':calls.append(('fixture',codec_json(requests[i])))
            elif action in {'layout','plan'}:calls.append(('layout',codec_json(requests[i])))
            elif action=='ascii':calls.append(('ascii',codec_json(requests[i])))
            elif action=='validate-measurement':calls.append(('measurement',codec_json(requests[i])))
            elif action=='codec':calls.append(('codec',codec_json(requests[i])))
            elif action in {'capabilities','tests','fonts'}:calls.append((action,None))
            else:calls.append(('source' if action=='source' else 'accept',trees.get(i,requests[i].get('trees'))))
        stage='foil'
        results=invoke(calls,directory,False)
        printing=[]
        for i,result in zip(valid,results):
            action=requests[i]['action']
            if action in {'print','goo-print'}:printing.append((i,dict(version=1,action=action,trees=result['trees'])))
            elif action=='echo':answers[i]={k:v for k,v in result.items() if k!='diagnostics'}
            else:answers[i]=result
        stage='rex/print'
        if printing:
            for (i,_),r in zip(printing,retained(directory,[r for _,r in printing])):answers[i]=r
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError,RecursionError) as e:
        for i in valid:
            if answers[i] is None:answers[i]=failure(stage,e)
    return answers

def codec_json(value):
    # Preserve decimal lexemes until the Foil binary64 decoder sees them.
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,list):return '['+','.join(codec_json(v) for v in value)+']'
    if isinstance(value,dict):return '{'+','.join(json.dumps(k)+':'+codec_json(v) for k,v in value.items())+'}'
    return json.dumps(value,ensure_ascii=True,allow_nan=False)

def ordinary_numbers(value):
    if isinstance(value,Decimal):return float(value)
    if isinstance(value,list):return [ordinary_numbers(v) for v in value]
    if isinstance(value,dict):return {k:ordinary_numbers(v) for k,v in value.items()}
    return value

def main():
    try:
        req=json.load(__import__('sys').stdin,parse_float=Decimal,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON number')))
        many=isinstance(req,list)
        requests=req if many else [req]
        requests=[r if isinstance(r,dict) and r.get('action') in {'source','codec','validate-measurement','ascii','layout','plan','fixture','render'} else ordinary_numbers(r) for r in requests]
        answer=batch(requests);result=answer if many else answer[0]
    except (ValueError,ArithmeticError,UnicodeError,RecursionError) as e:result=failure('protocol',e)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
