from pathlib import Path
p=Path('extras/mounts/medium/behaviors.py');s=p.read_text()
s=s.replace("return {k:candidate[k] for k in ('surface','definition','hash','pure_source','cases')}|{'implementation':result['implementation']}","return {k:candidate[k] for k in ('surface','definition','hash','pure_source','cases','evaluation','verification') if k in candidate}|{'implementation':result['implementation']}")
pos=s.index('\ndef row_values')
s=s[:pos]+'''
# A predicate is independently pure for each row, while every call receives the
# same immutable collection. Partition execution, never remove the native cap.
FOCUS_BOOL_ADAPTER=BOOL_ADAPTER.replace(
    'remaining=row[json] rows results=',
    'remaining=row[json] rows.keep((\\\\ item (equal[json] (view/field "id" item) (view/field "id" input)))) results=')


def prepare_predicate(server,source,cases,key,rows,progress):
    complete=source+FOCUS_BOOL_ADAPTER
    checks=[]
    for case in cases:
        data=case.get('input',{});expected=case.get('expected')
        if not isinstance(data.get('rows'),list) or not isinstance(expected,list):
            raise ValueError('Predicate checks need rows and expected results')
        ids=[r.get('id') for r in data['rows']]
        if len(ids)>16 or len(set(ids))!=len(ids) or {r.get('id') for r in expected}!=set(ids):
            raise ValueError('Checks must cover each distinct input identity exactly once')
        if not ids:checks.append(({'rows':[]},[],False))
        for result in expected:
            if not isinstance(result.get('value'),bool):raise ValueError('Expected a Bool result')
            checks.append(({**data,'id':result['id']},[result],False))
    checks.extend(({'rows':rows,'id':r['id']},None,True) for r in rows)
    cache=server.world/'pure-programs'/'checks';cache.mkdir(exist_ok=True)
    verified=[]
    for index,(value,expected,probe) in enumerate(checks):
        progress(index+1,len(checks))
        digest=hashlib.sha256(json.dumps([complete,value,expected],sort_keys=True).encode()).hexdigest()
        path=cache/(digest+'.json')
        if path.exists():receipt=json.loads(path.read_text())
        else:
            check=[] if probe else [{'input':value,'expected':expected}]
            candidate=prepare(server,complete,check,probe=value if probe else None)
            actual=output(candidate)
            if probe and (not isinstance(actual,list) or len(actual)!=1 or not isinstance(actual[0].get('value'),bool)):
                raise ValueError('Native probe must return exactly one Bool')
            receipt={'hash':digest,'proposal':candidate['proposal'],'source_hash':hashlib.sha256(complete.encode()).hexdigest(),'probe':probe,'result':actual}
            path.write_text(json.dumps(receipt,indent=2))
        verified.append(receipt)
    candidate=prepare(server,complete,[],key,probe=None)
    candidate.update(evaluation='per-record',verification=verified,cases=cases)
    return candidate

''' +s[pos:]
s=s.replace("candidate=prepare(server,raw+BOOL_ADAPTER,cases,'pure_'+ident,{'rows':valid_rows})", "candidate=prepare_predicate(server,raw,cases,'pure_'+ident,valid_rows,lambda done,total:job.update(message=f'Native isolated check {done} of {total}'))")
s=s.replace("('proposal','surface','definition','hash','pure_source','cases')", "('proposal','surface','definition','hash','pure_source','cases','evaluation','verification')")
s=s.replace("result=evaluate(server,job['descriptor'],{'rows':rows})", """if job['descriptor'].get('evaluation')=='per-record':
            values=[];t=time.monotonic()
            for row in rows:
                result=evaluate(server,job['descriptor'],{'rows':rows,'id':row['id']})
                if len(result['value'])!=1 or result['value'][0].get('id')!=row['id']:raise ValueError('Native predicate identity changed')
                values.extend(result['value'])
            result={'value':values,'implementation':job['descriptor']['implementation'],'native_ms':round((time.monotonic()-t)*1000)}
        else:result=evaluate(server,job['descriptor'],{'rows':rows})""")
p.write_text(s)
