"""Gate S: exact phase parity, UUID lifecycle, and backend interoperability."""
import copy,gzip,json,subprocess,sys,uuid
from pathlib import Path
from unittest.mock import patch
from runtime import GOO,BUILD,invoke,verify
from adapter import batch,codec_json
from codec_checks import comparable,wire
sys.path.insert(0,str(GOO/'scripts/porting'))
from oracle_compare import canonical,first,Identities
from check_oracle import source_cases,UI,walk,output,stage

def require(condition,message):
    if not condition:raise AssertionError(message)
def semantic_compare(want,got):
    if not want.get('ok') or not got.get('ok'):
        return None if want.get('ok')==got.get('ok') else dict(path='$',expected=want,actual=got)
    a=canonical(want)['stages'][:6];b=canonical(got)['stages'][:6]
    return first(comparable(a),comparable(b))
def oracle(requests):
    path=BUILD/'semantic-oracle/run'
    if not path.exists():raise RuntimeError('Build test oracle: goo/scripts/porting/build-semantic-oracle.sh')
    return json.loads(subprocess.run([str(path)],input=codec_json(requests),text=True,capture_output=True,check=True).stdout)

def extra_cases():
    cases=[]
    def add(name,source,**options):cases.append(dict(name=name,request=dict(version=1,action='source',source=source,**options)))
    for path in ['/sys/slots/scar','/sys/slots/label','/sys/slots/summary','/sys/slots/inspect','/sys/slots/detail','/sys/slots/full','/unknown','/summary','/']:
        add('view/'+path,UI,viewPath=path)
    for paths in [[],[[]],[[0]],[[1]],[[2]],[[99]],[[0,0]],[[1,0]],[[0],[0]],[[1],[2]]]:add('hidden/'+str(paths),UI,hiddenPaths=paths)
    for source in [
        'opt(2) { row(%x) { text("a") opt(1) { text("b") } } }',
        'opt(1) { opt(2) { text("a") } }', 'opt(1) {}', 'group {}',
        'row { group {} text("survivor") }','row { opt(2) { text("a") } }',
        'group({[optional]:2}) { text({[optional]:0}, "a") }',
        'row { text("left",%title) opt(2) { text("middle",%subtitle) } text("right",%body) }']:
        for budget in range(3):add('sugar/'+str(len(cases)),source,budget=budget)
    for text in ['01','00','0x10','0Xff','0o10','1.','1.0','+1','-1','1e2','1E+2','.5','1e309','-1e-400','NaN','Infinity','0x','0o9','-0x10','0x1.2','1e-324','9007199254740993']:
        add('number/'+text,'text({[maxIdeal]: '+text+'}, "x")')
    for source in ['wat','text(1)','text(true)','text("a","b","c")','row("a","b") {}','row', 'opt(0) {}','opt(3) {}','opt(true) {}','opt(1,2) {}','text({[grow]:2},"x")','text({[grow]:true},"x")','text({[primary]:1},"x")','text({[x]:1},"x")','text({[grow]:1,[grow]:0},"x")','text({x:1},"x")','text({[x y]:1},"x")','text({[grow]},"x")','text({[slot]:2},"x")','bar({[value]:1},"x")','bar({[value]:2,[max]:1},"x")','text("x",/a//b)','text("x",/a/../b)','text(escaped("bad\\q"))','text(escaped("line\\nnext\\t\\\\"))','row { text("a")\r\n\ttext("b") }']:
        add('read-negative/'+str(len(cases)),source)
    for path in ['/sys/slots/icon','/sys/slots/lede','/sys/slots/caption','/sys/slots/code','/sys/slots/label','/sys/slots/summary','/sys/containers/row','/sys/containers/col','/sys/containers/card','/unknown/slot']:
        add('alias/'+path,'text("x",'+path+')')
    rules=json.loads((GOO/'goo-reimplementation/rules.json').read_text())
    for rule in rules+[dict(number=0,left='unknown-left',right='unknown-right')]:
        for uniform in [False,True]:add('rule/'+str(rule['number'])+'/'+str(uniform),'row(%owner) { text("l",%'+rule['left']+') text("r",%'+rule['right']+') }',uniform=uniform)
    for options in [dict(budget=1.0),dict(hiddenPaths=[[1.0]]),dict(width=-0.0),dict(textScale=1e-320),dict(budget=3),dict(hiddenPaths=[[-1]]),dict(hiddenPaths=['bad']),dict(hiddenIds=['']),dict(viewPath='/a//b'),dict(viewPath='/a/../b'),dict(viewPath='relative'),dict(uniform=1)]:add('protocol/'+str(len(cases)),UI,**options)
    return cases

def check_gate(frozen_verified=0):
    reference=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'))
    frozen=frozen_verified
    for start in ([] if frozen_verified==len(reference) else range(0,len(reference),30)):
        chunk=reference[start:start+30];actual=batch([r['case']['request'] for r in chunk])
        for record,got in zip(chunk,actual):
            mismatch=semantic_compare(record['response'],got)
            require(not mismatch,(record['case']['name'],mismatch))
        frozen+=len(chunk)
    print('Frozen semantic prefixes:',frozen,flush=True)
    cases=[dict(name=c['name']+'/budget-'+str(b),request=dict(c['request'],budget=b)) for c in source_cases() if c['name'].endswith('.goo') for b in range(3)]+extra_cases()
    seen=set();node_count=0;counts={}
    for start in range(0,len(cases),30):
        chunk=cases[start:start+30];requests=[r['request'] for r in chunk]
        want=oracle(requests);got=batch(requests)
        for case,expected,actual in zip(chunk,want,got):
            mismatch=semantic_compare(expected,actual)
            if mismatch:
                (BUILD/'gate-mismatch.json').write_text(json.dumps(dict(case=case,expected=expected,actual=actual,mismatch=mismatch),indent=2))
                raise AssertionError((case['name'],mismatch))
            if not actual['ok']:continue
            if stage(actual,'normalized')['status']=='ok':
                ids=[n['attrs']['id'] for n in walk(output(actual,'normalized'))]
                require(len(ids)==len(set(ids)) and not seen.intersection(ids),'UUID collision')
                require(all(str(uuid.UUID(i))==i and uuid.UUID(i).version==4 and uuid.UUID(i).variant==uuid.RFC_4122 for i in ids),'not RFC UUIDv4')
                seen.update(ids);node_count+=len(ids)
                counts.setdefault(case['request']['source'],set()).add(len(ids))
        print('Gate S requests:',min(start+30,len(cases)),'/',len(cases),flush=True)
    require(all(len(v)==1 for v in counts.values()),'allocation count changed with visibility/options')
    lifecycle=uuid_lifecycle()
    report=dict(frozen_prefixes=frozen,cases=len(cases),corpus_budget_cases=1107,extra_cases=len(extra_cases()),distinct_uuid_nodes=node_count,uuid_lifecycle=lifecycle)
    (BUILD/'last-gate-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def uuid_lifecycle():
    requests=[dict(version=1,action='source',source=UI,budget=b) for b in range(3)]
    allocated=[]
    def provider(count):
        ids=[str(uuid.uuid4()) for _ in range(count)];allocated.append(ids);return ids
    with patch('adapter.allocate_ids',provider):results=batch(requests)
    require([len(v) for v in allocated]==[4,4,4],'must allocate once for all four normalized nodes before pruning')
    for ids,result in zip(allocated,results):require(ids==[n['attrs']['id'] for n in walk(output(result,'normalized'))],'UUID provider order/count changed')
    # A known ID is hidden only after allocation; parent and sibling IDs persist.
    fixed=allocated[2]
    with patch('adapter.allocate_ids',return_value=fixed):
        hidden=batch([dict(requests[2],hiddenIds=[fixed[2]])])[0]
    children=output(hidden,'semantic')['children'];require([n['attrs']['id'] for n in children]==[fixed[1],fixed[3]],'hidden ID resolution')
    require(children[0]['attrs']['after']['rightId']==fixed[3],'hidden middle adjacency was not rebuilt')
    require(children[-1]['attrs']['after'] is None and output(hidden,'semantic')['attrs']['after'] is None,'root/final edge')
    empty=batch([dict(requests[2],hiddenPaths=[[]])])[0]
    require(stage(empty,'semantic')['status']=='ok' and output(empty,'semantic') is None,'empty success lost')
    # Retain this compiled semantic tree while changing backend-only dimensions.
    semantic=wire(output(results[2],'semantic')); ids=[n['id'] for n in walk(semantic)]
    roundtrip=batch([dict(version=1,action='codec',phase='semantic',tree=semantic)])[0]
    require(roundtrip['ok'] and roundtrip['tree']==semantic,'semantic transport changed IDs')
    backend=oracle([dict(version=1,action='fixture',tree=semantic,width=w,textScale=scale) for w,scale in [(80,1),(248,1),(752,1),(752,.75),(752,1.5)]])
    for rendered in backend:
        require(rendered['outcome']=='complete','Haskell renderer rejected Foil semantic tree')
        require([n['attrs']['id'] for n in walk(output(rendered,'semantic'))]==ids,'resize/render reallocated IDs')
        require([n['id'] for n in walk(output(rendered,'prepared')['measurement']['tree'])]==ids,'prepared output changed IDs')
        require(all('data-node="'+id+'"' in output(rendered,'html') for id in ids),'rendered HTML lost identities')
    with patch('adapter.allocate_ids',side_effect=lambda n: (_ for _ in ()).throw(AssertionError('allocated on failed input')) if n else []):
        failed=batch([dict(version=1,action='source',source=s) for s in [')','wat','opt(1) {}']])
    require(all(r['outcome']=='rejected' for r in failed),'failure control changed')
    with patch('adapter.allocate_ids',side_effect=OSError('entropy unavailable')):
        crashed=batch([requests[2]])[0]
    require(stage(crashed,'core')['status']=='ok' and stage(crashed,'normalized')['status']=='crashed','entropy failure attribution')
    from runtime import Cancelled
    with patch('adapter.allocate_ids',side_effect=Cancelled(15)):
        try:batch([requests[2]])
        except Cancelled:pass
        else:raise AssertionError('entropy cancellation swallowed')
    return dict(pre_pruning_allocation=True,hidden_ids=True,hidden_adjacency=True,empty_success=True,resize_render_cases=len(backend),failure_allocation=True)
if __name__=='__main__':print(json.dumps(check_gate(),indent=2))
