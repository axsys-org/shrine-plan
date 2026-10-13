"""Item 07 checks against the production Haskell result validator."""
import copy,gzip,json,sys
from runtime import GOO,BUILD
from adapter import batch
from gate_checks import oracle
sys.path.insert(0,str(GOO/'scripts/porting'))
from oracle_compare import first

def cases():
    records=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'));out=[]
    for record in records:
        stage=next(s for s in record['response']['stages'] if s['name']=='prepared')
        if stage['status']=='ok':out.append((record['case']['name'],stage['output']['measurement']))
    # Use an existing measured flow with an in-row edge as the mutation witness.
    witness=next(copy.deepcopy(r) for _,r in out if r['tree'] and r['tree']['kind']=='group' and r['tree']['layout']=='flow' and len(r['tree']['children'])>=2 and r['plan']['rows'][0].get('rowGaps') and r['trace'])
    def add(name,mutate):
        r=copy.deepcopy(witness);mutate(r);out.append((name,r))
    for key in ['version','tree','width','sizes','plan','trace']:add('missing-'+key,lambda r,k=key:r.pop(k))
    for val in [None,0,2,True,'1']:add('version-'+str(val),lambda r,v=val:r.update(version=v))
    for val in [-1,0,.5,None,'752',True]:add('width-'+str(val),lambda r,v=val:r.update(width=v))
    add('missing-metric',lambda r:r['sizes'].pop(next(iter(r['sizes']))))
    add('extra-metric',lambda r:r['sizes'].update(extra=dict(min=0,pref=1,grow=0)))
    for key,val in [('min',-1),('pref',-1),('grow',2),('grow',True),('min',None),('pref','2')]:add('metric-'+key+'-'+str(val),lambda r,k=key,v=val:next(iter(r['sizes'].values())).__setitem__(k,v))
    add('metric-inverted',lambda r:next(iter(r['sizes'].values())).update(min=10,pref=1))
    for key,val in [('id','unknown'),('w',0),('w',1),('h',-1),('cost',-1),('rows',None),('rows',[])]:add('plan-'+key+'-'+str(val),lambda r,k=key,v=val:r['plan'].__setitem__(k,v))
    add('null-plan',lambda r:r.update(plan=None))
    add('plan-child-id',lambda r:r['plan']['rows'][0]['children'][0].update(id='unknown'))
    add('leaf-rows',lambda r:r['plan']['rows'][0]['children'][0].update(rows=[]))
    for key,val in [('start',1),('start',-1),('end',0),('end',999),('children',[]),('gap',-1),('h',-1),('rowGaps',None),('rowGaps',[]),('rowGaps',[-1])]:add('row-'+key+'-'+str(val),lambda r,k=key,v=val:r['plan']['rows'][0].__setitem__(k,v))
    add('overlap-row',lambda r:r['plan']['rows'].append(copy.deepcopy(r['plan']['rows'][0])))
    add('reorder-plan',lambda r:r['plan']['rows'][0]['children'].reverse())
    add('missing-trace',lambda r:r['trace'].pop())
    add('extra-trace',lambda r:r['trace'].append(copy.deepcopy(r['trace'][0])))
    for key,val in [('parent','unknown'),('leftId','unknown'),('rightId','unknown'),('parentSlot','wrong'),('axis','z'),('axis','y'),('cut',True),('gap',-1),('x',-1),('y',-1),('stretch',-1),('breakPenalty',-1),('preferredGap',999),('rule',0)]:add('trace-'+key+'-'+str(val),lambda r,k=key,v=val:r['trace'][0].__setitem__(k,v))
    for delta in [.0109,.011,.0111,-.0109,-.011,-.0111]:add('gap-tolerance-'+str(delta),lambda r,d=delta:r['trace'][0].update(gap=r['trace'][0]['gap']+d))
    add('tree-null-with-plan',lambda r:r.update(tree=None))
    out.append(('empty-result',dict(version=1,tree=None,width=1,sizes={},plan=None,trace=[])))
    out.append(('empty-extra-metrics',dict(version=1,tree=None,width=1,sizes={'x':dict(min=0,pref=0,grow=0)},plan=None,trace=[])))
    return out

def check_measurements():
    probes=cases();accepted=0
    for start in range(0,len(probes),15):
        chunk=probes[start:start+15];requests=[dict(version=1,action='validate-measurement',result=r) for _,r in chunk]
        expected=oracle(requests);actual=batch(requests)
        for (name,request),want,got in zip(chunk,expected,actual):
            mismatch=first(want,got) if want['ok'] and got['ok'] else None
            if want['ok']!=got['ok'] or mismatch or (not got['ok'] and got.get('stage')!='protocol'):
                (BUILD/'measurement-mismatch.json').write_text(json.dumps(dict(name=name,request=request,expected=want,actual=got,mismatch=mismatch),indent=2))
                raise AssertionError((name,mismatch,want['ok'],got['ok']))
            accepted+=want['ok']
        if start%75==0:print('Measurement validation:',min(start+15,len(probes)),'/',len(probes),flush=True)
    report=dict(cases=len(probes),accepted=accepted,rejected=len(probes)-accepted,names=[n for n,_ in probes])
    (BUILD/'last-measurement-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':print(json.dumps(check_measurements(),indent=2))
