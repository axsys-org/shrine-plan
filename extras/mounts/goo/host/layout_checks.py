"""Gate L: recorded browser geometry and native ASCII integration remain separate."""
import copy,gzip,hashlib,json,math,subprocess,sys
from runtime import GOO,BUILD,verify
from adapter import batch,codec_json
from codec_checks import wire
from gate_checks import oracle as semantic_oracle

def require(value,message):
    if not value:raise AssertionError(message)
def difference(a,b,path='$'):
    if type(a) in (int,float) and type(b) in (int,float):
        if math.isfinite(a) and math.isfinite(b) and abs(a-b)<=max(1e-6,1e-10*max(abs(a),abs(b))):return None
    elif isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return dict(path=path+'.keys',expected=sorted(a),actual=sorted(b))
        for key in a:
            d=difference(a[key],b[key],path+'.'+key)
            if d:return d
        return None
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return dict(path=path+'.length',expected=len(a),actual=len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            d=difference(x,y,path+'['+str(i)+']')
            if d:return d
        return None
    elif type(a)==type(b) and a==b:return None
    return dict(path=path,expected=a,actual=b)
def match(a,b,name):
    d=difference(a,b)
    if d:
        (BUILD/'layout-mismatch.json').write_text(json.dumps(dict(name=name,mismatch=d,expected=a,actual=b),indent=2))
        raise AssertionError((name,d))
def oracle(requests):
    path=BUILD/'layout-oracle/run'
    require(path.exists(),'Build goo/scripts/porting/build-layout-oracle.sh first')
    return json.loads(subprocess.run([str(path)],input=codec_json(requests),text=True,capture_output=True,check=True).stdout)
def leaf(id,slot='body',**kw):return dict(id=id,slot=slot,kind=kw.pop('kind','text'),text='word one two three',after=None,**kw)
def group(id,children,layout='flow',binds=None,**kw):
    children=copy.deepcopy(children);node=dict(id=id,slot='owner',kind='group',layout=layout,children=children,after=None,**kw)
    for i,c in enumerate(children[:-1]):
        r=children[i+1];c['after']=dict(left=c['slot'],right=r['slot'],leftId=c['id'],rightId=r['id'],parent=id,parentSlot='owner',bind=(binds or ['normal']*len(children))[i],rule=None,source='fallback')
    return node
def leaves(n):return sum((leaves(c) for c in n.get('children',[])),[]) if 'children' in n else [n]
def request(tree,width=200,sizes=None,scale=1):
    if sizes is None:return dict(version=1,action='layout',tree=tree,width=width,textScale=scale)
    return dict(version=1,action='plan',tree=tree,width=width,measurements=dict(sizes=sizes,heights={n['id']:20 for n in leaves(tree)}))
def size(lo,pref=None,grow=0):return dict(min=lo,pref=lo if pref is None else pref,grow=grow)
def run_cases(cases,label):
    accepted=rejected=0
    for start in range(0,len(cases),12):
        chunk=cases[start:start+12];rs=[r for _,r in chunk];want=oracle(rs);got=batch(rs)
        for (name,r),a,b in zip(chunk,want,got):
            if a.get('ok') is False:
                require(b.get('ok') is False,(name,a,b));rejected+=1
            else:match(a,b,label+'/'+name);accepted+=1
        if start%60==0:print(label,min(start+12,len(cases)),'/',len(cases),flush=True)
    return dict(requests=len(cases),accepted=accepted,rejected=rejected)
def synthetic_cases():
    cases=[]
    def add(name,t,w,s):cases.append((name,request(t,w,s)))
    for w in [0,-0.,.005,.995,1,1.0049,1.005,20.125,math.nextafter(20.125,0),math.nextafter(20.125,math.inf),99999.995,100000]:add('quantize/'+repr(w),leaf('a'),w,dict(a=size(0)))
    cases.append(('empty',request(None,20.125)))
    for bind in ['attached','tight','related','normal','loose','separate']:
        t=group('p',[leaf('a','title'),leaf('b','subtitle'),leaf('c','body')],binds=[bind,bind])
        for w in [1,49.94,49.95,50,100,148,200,400]:add('edge/'+bind+'/'+str(w),t,w,{k:size(50,100,1) for k in 'abc'})
    for delta in [-.000001,0,.000001]:
        # Width is already quantized; move minima through the 0.05 feasibility bound.
        t=group('p',[leaf('a'),leaf('b')],binds=['tight']);add('feasibility/'+str(delta),t,108,dict(a=size(50),b=size(50.05+delta)))
    add('proportional-shrink',group('p',[leaf('a','title'),leaf('b','subtitle')],binds=['tight']),188,dict(a=size(50,100,1),b=size(70,140,1)))
    add('ragged-strong',group('p',[leaf('a'),leaf('b')],binds=['tight']),400,dict(a=size(100),b=size(80)))
    add('emergency-singleton',group('p',[leaf('a')]),80,dict(a=size(300)))
    add('multiple-weak',group('p',[leaf('a'),leaf('b'),leaf('c')],binds=['loose','separate']),400,{k:size(50) for k in 'abc'})
    # Equal-cost partitions [a]/[b,c] and [a,b]/[c] retain the first endpoint.
    add('deterministic-tie',group('p',[leaf('a'),leaf('b'),leaf('c')],binds=['normal','normal']),116,{k:size(50) for k in 'abc'})
    for delta in [.01,.012,(1e-6/32)**.25,.014,.02]:
        add('near-tie/'+str(delta),group('p',[leaf('a'),leaf('b'),leaf('c')],binds=['normal','normal']),116,dict(a=size(50),b=size(50),c=size(50,50+delta)))
    cases.append(('null-default-scale',dict(request(leaf('a'),200),textScale=None)))
    for grow in [0,1]:
        for layout in ['flow','stack']:
            t=group('root',[group('nested',[leaf('a'),leaf('b')],layout=layout,grow=grow),leaf('c',grow=1-grow)],layout='stack')
            for w in [1,100,200,500]:add('nested/'+layout+'/'+str(grow)+'/'+str(w),t,w,dict(a=size(50,100,0),b=size(40,80,1),c=size(35,90,0)))
    # Generated nested geometry using a fixed seed makes candidate enumeration regressions reproducible.
    import random
    rng=random.Random(20260928)
    for i in range(60):
        ns=[leaf(str(k)) for k in range(rng.randint(2,7))]
        binds=[rng.choice(['attached','tight','related','normal','loose','separate']) for _ in ns]
        t=group('p',ns,binds=binds)
        ss={n['id']:size(rng.randint(0,120),None,rng.randrange(2)) for n in ns}
        for s in ss.values():s['pref']+=rng.randint(0,200)
        add('seeded/'+str(i),t,rng.randint(1,600)+.125,ss)
    return cases

def check_authority_and_failures():
    authority=[]
    for uniform in [False,True]:
        for hidden in [[],[[1]]]:
            source=dict(version=1,action='source',source='row(%owner) { text("A", %title) text("B", %hint) text("C", %subtitle) }',uniform=uniform,hiddenPaths=hidden)
            compiled=batch([source])[0]
            tree=wire(next(s['output'] for s in compiled['stages'] if s['name']=='semantic'))
            sizes={n['id']:size(50) for n in leaves(tree)}
            base=request(tree,400,sizes);changed=copy.deepcopy(base)
            edge=changed['tree']['children'][0]['after'];old=edge['bind'];edge['bind']='loose'
            # Uniform provenance requires Normal; an explicit override updates provenance too.
            edge['source']='fallback' if edge['rule'] is None else 'exact'
            require(old!='loose','authority probe must change bind')
            a,b=batch([base,changed])
            require(a.get('ok') and b.get('ok'),(a,b))
            if uniform:require(a['measurement']['trace'][0]['x']==16 and a['measurement']['trace'][0]['source']=='uniform','uniform edge was re-resolved')
            match(oracle([changed])[0],b,'emitted edge authority')
            require(a['measurement']['trace'][0]['x']!=b['measurement']['trace'][0]['x'],'changed emitted bind ignored')
            trace=b['measurement']['trace'][0];require(trace['x']==24 and trace['stretch']==1,'loose metrics ignored')
            require(trace['source']==edge['source'] and trace['rule']==edge['rule'],'provenance rewritten')
            require(trace['rightId']==tree['children'][1]['id'],'hidden endpoint not retained')
            authority.append(dict(uniform=uniform,hidden=bool(hidden),old_bind=old,new_bind=trace['bind']))
    t=group('p',[leaf('a'),leaf('b')],binds=['tight']);base=request(t,200,dict(a=size(50,100,1),b=size(50,100,1)))
    rejected=[]
    def bad(name,change):
        r=copy.deepcopy(base);change(r);rejected.append((name,r))
    bad('missing-size',lambda r:r['measurements']['sizes'].pop('a'))
    bad('invalid-size',lambda r:r['measurements']['sizes']['a'].update(min=101))
    bad('negative-height',lambda r:r['measurements']['heights'].update(a=-1))
    bad('missing-height',lambda r:r['measurements']['heights'].pop('a'))
    # The singleton candidate requires 100; its combined candidate requires 96.
    bad('missing-height-on-discarded-candidate',lambda r:r['measurements']['heights'].update(a={'100.00':20},b={'100.00':20}))
    bad('duplicate-id',lambda r:r['tree']['children'][1].update(id='a'))
    bad('missing-edge',lambda r:r['tree']['children'][0].update(after=None))
    for key,values in [('width',[-1,100001,None,True,'200']),('textScale',[0,-1,10.01,True,'1']),('version',[0,2,True])]:
        for v in values:bad(key+'/'+repr(v),lambda r,k=key,v=v:r.update({k:v}))
    results=batch([r for _,r in rejected]);require(all(not r['ok'] for r in results),[(n,r) for (n,_),r in zip(rejected,results) if r['ok']])
    good=batch([base])[0]['measurement'];mutations=[]
    for name,change,path in [
        ('cost',lambda r:r['plan'].update(cost=r['plan']['cost']+1),'$.plan.cost'),
        ('ordering',lambda r:r['plan']['rows'][0]['children'].reverse(),'$.plan.rows[0].children[0].id'),
        ('owner',lambda r:r['trace'][0].update(parent='wrong'),'$.trace[0].parent')]:
        altered=copy.deepcopy(good);change(altered);d=difference(good,altered);require(d and d['path']==path,(name,d));mutations.append(d['path'])
    return dict(emitted_edge_authority=authority,rejections=len(rejected),precise_mismatch_paths=mutations)

def original_synthetic_checks():
    from check_oracle import fixture_request,atom,group,sampled,output,eq
    call=batch
    def natural(result,scale=1):
        tree=wire(output(result,"semantic"))
        return batch([dict(version=1,action="ascii",tree=tree,textScale=scale,widths=[100000])])[0]["nodes"][0]["natural"]
    fixtures=json.loads((GOO/'goo-reimplementation/fixtures/synthetic.json').read_text());done=[]
    t=group('id',[atom('t','title'),atom('s','subtitle',optional=1),atom('m','metadata',optional=2)],'identity','stack')
    for f in fixtures:
        name=f['name'];i=f['input'];want=f['expected']
        if name.startswith('pair '):
            result=call([fixture_request(group('owner',[atom('a',i['left']),atom('b',i['right'])]))])[0]
            edge=output(result,'semantic')['children'][0]['attrs']['after'];actual={k:edge[k] for k in want}
        elif name.startswith('budget ') or name in {'empty root','singleton boundary'}:
            options={'budget':i['budget']} if name.startswith('budget ') else {'hiddenIds':['t','s','m']} if name=='empty root' else {'budget':0}
            tree=output(call([fixture_request(t,**options)])[0],'semantic')
            actual=[c['attrs']['id'] for c in tree['children']] if name.startswith('budget ') else None if tree is None else tree['attrs']['slot']
        elif name in {'weak boundary cut','weak edge stretch'}:
            result=call([sampled(i['tree'],i['sizes'],i['width'])])[0];plan=output(result,'layout');assert plan,result
            actual=({'rows':[[c['id'] for c in r['children']] for r in plan['rows']],'cost':plan['cost'],'height':plan['h']}
                    if name=='weak boundary cut' else {'widths':[c['w'] for c in plan['rows'][0]['children']],'gaps':plan['rows'][0]['rowGaps'],'cost':plan['cost']})
        elif name=='proportional shrink':
            tree=group('shrink',[atom('s0','title'),atom('s1','subtitle')]);sizes={f's{k}':dict(min=m,pref=i['pref'][k],grow=1) for k,m in enumerate(i['min'])}
            plan=output(call([sampled(tree,sizes,i['space']+8)])[0],'layout')
            widths=[c['w'] for c in plan['rows'][0]['children']]
            actual=dict(widths=widths,compression=plan['cost']-24,spare=max(0,i['space']-sum(i['pref'])))
        elif name=='strong edges stay ragged':
            tree=group('tight',[atom('a','title'),atom('b','subtitle')]);sizes={'a':dict(min=100,pref=100,grow=1),'b':dict(min=80,pref=80,grow=1)}
            plan=output(call([sampled(tree,sizes,i['width'])])[0],'layout')
            actual=dict(widths=[c['w'] for c in plan['rows'][0]['children']],gaps=plan['rows'][0]['rowGaps'])
        elif name=='emergency singleton':
            tree=group('emergency',[atom('a','value')]);plan=output(call([sampled(tree,{'a':dict(min=i['min'],pref=i['min'],grow=0)},i['width'])])[0],'layout')
            actual=dict(width=plan['rows'][0]['children'][0]['w'],cost=plan['cost'])
        elif name.startswith('leaf size '):
            tree=copy.deepcopy(i['node']);scale=1
            # The production ASCII API has no browser-natural-width injection.
            # Exercise equivalent leaf-policy outcomes with measured ASCII text.
            if tree['id']=='v':
                tree['text']='0123456789';base=call([fixture_request(tree)])[0]
                natural_width=natural(base)
                twice=natural(call([fixture_request(tree,textScale=2)])[0],2)
                scale=1+(199.5-natural_width)/(twice-natural_width)
            elif tree['id']=='t':tree['text']='t'*200
            elif tree['id']=='b':
                base=call([fixture_request(tree)])[0];natural_width=natural(base);scale=(73.2-26)/(natural_width-26)
            actual=output(call([fixture_request(tree,textScale=scale)])[0],'metrics')['sizes'][tree['id']]
        else:raise AssertionError('uncovered synthetic '+name)
        eq(want,actual,name,numeric=True);done.append(name)
    return done

def check_layout():
    frozen_path=GOO/'goo-reimplementation/fixtures/browser-replay.json.gz'
    frozen_hash=hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    fixtures=json.load(gzip.open(frozen_path))['fixtures']
    for start in range(0,len(fixtures),12):
        fs=fixtures[start:start+12]
        semantic=semantic_oracle([dict(version=1,action='fixture',tree=f['tree'],uniform=f['uniform'],width=f['outerWidth']-50,measurements=f['measurements']) for f in fs])
        trees=[wire(next(s['output'] for s in o['stages'] if s['name']=='semantic')) for o in semantic]
        requests=[dict(version=1,action='plan',tree=t,width=f['outerWidth']-50,measurements=f['measurements']) for f,t in zip(fs,trees)]
        expected=oracle(requests)
        native=batch([dict(version=1,action='fixture',tree=f['tree'],uniform=f['uniform'],width=f['outerWidth']-50,measurements=f['measurements']) for f in fs])
        actual=[]
        for o,n,t in zip(semantic,native,trees):
            match(o['stages'][:9],n['stages'][:9],'native fixture phases')
            stages={s['name']:s['output'] for s in n['stages']}
            actual.append(dict(version=1,ok=True,measurement=dict(version=1,tree=t,width=stages['metrics']['width'],sizes=stages['metrics']['sizes'],plan=stages['layout'],trace=stages['trace'])))
        for i,(f,a,b) in enumerate(zip(fs,expected,actual)):
            name=str(start+i)+'/'+f['name'];require(a.get('ok'),a);match(a,b,'recorded/'+name)
            match(f['plan'],b['measurement']['plan'],'frozen-plan/'+name);match(f['trace'],b['measurement']['trace'],'frozen-trace/'+name)
        if start%60==0:print('Gate L recorded',min(start+12,len(fixtures)),'/',len(fixtures),flush=True)
    policies=original_synthetic_checks()
    print('Original frozen synthetic policies:',len(policies),flush=True)
    synthetic=run_cases(synthetic_cases(),'Gate L synthetic')
    records=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'))
    ascii=[]
    for r in records:
        s=next(s for s in r['response']['stages'] if s['name']=='semantic')
        if s['status']=='ok':ascii.append((r['case']['name'],request(wire(s['output']),r['case']['request'].get('width',752),scale=r['case']['request'].get('textScale',1))))
    # Scale/width probes are independent of the recorded browser measurements.
    t=group('root',[leaf('a','title'),group('nested',[leaf('b'),leaf('c','code',kind='code')],layout='stack'),leaf('d',kind='button')],binds=['loose','separate'])
    for scale in [.1,.5,1,1.5,2,10]:
        for width in [0,1,80,200.125,500,100000]:ascii.append(('scale/'+str(scale)+'/'+str(width),request(t,width,scale=scale)))
    integrated=run_cases(ascii,'Gate L ASCII')
    controls=check_authority_and_failures()
    require(hashlib.sha256(frozen_path.read_bytes()).hexdigest()==frozen_hash,'frozen replay changed')
    report=dict(status='pass',recorded=dict(fixtures=len(fixtures),sha256=frozen_hash),synthetic=synthetic,original_synthetic_policies=policies,ascii=integrated,controls=controls,numeric_tolerance='max(1e-6,1e-10*max(abs(a),abs(b)))',structure='exact fields, IDs, partitions, order and traces')
    (BUILD/'last-layout-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    verify();return report
if __name__=='__main__':check_layout()
