"""Native tree/config codec differential checks against actual Haskell decoders."""
import copy, gzip, json, random, struct, subprocess
from runtime import GOO, BUILD, invoke
from adapter import batch, codec_json
from decimal import Decimal
import sys
sys.path.insert(0,str(GOO/"scripts/porting"))
from oracle_compare import first

def wire(tree):
    if tree is None:return None
    value=copy.deepcopy(tree['attrs']);kind=tree['constructor']
    if kind=='flow':value.update(kind='group',layout='flow' if tree['direction']=='Row' else 'stack',children=[wire(t) for t in tree['children']])
    elif kind=='image':value.update(kind='avatar' if value['slot'] in ('icon','avatar') else 'media',src=tree['src'],text='')
    elif kind=='primitive':value.update(kind=tree['kind'],text=tree['text'])
    elif kind=='text':value.update(kind='text',text=tree['text'])
    else:raise AssertionError('unexpected canonical constructor: '+kind)
    return value

def cases():
    out=[]
    def add(name,tree,phase='semantic',**extra):out.append((name,dict(version=1,action='codec',phase=phase,tree=copy.deepcopy(tree),**extra)))
    records=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'))
    for record in records:
        for stage in record['response']['stages']:
            if stage['name'] in ('normalized','semantic') and stage['status']=='ok':add(record['case']['name']+'/'+stage['name'],wire(stage['output']),stage['name'])
    leaf=dict(id='a',slot='custom',kind='text',after=None)
    add('empty',None)
    add('default-leaf',leaf)
    def change(name,**fields):add(name,dict(leaf,**fields))
    for key in ('optional','origin','grow','maxIdeal','primary','toggle','label','optionLabel','value','max','text','src'):
        change('null-'+key,**{key:None})
    for key in ('id','slot','kind','after'):
        v=copy.deepcopy(leaf);del v[key];add('missing-'+key,v)
        change('required-null-'+key,**{key:None})
    for kind in ('button','input','code','avatar','presence','media','bar'):
        change('primitive-'+kind,kind=kind,text='payload')
    for kind in ('text','button','input','code','avatar','presence','media','bar','opt','unknown'):
        change('image-'+kind,kind=kind,src='url',text='discarded')
    for slot in ('icon','avatar','/icon','custom',''):
        change('image-slot-'+slot,kind='media',slot=slot,src='url')
    for key,values in {
        'optional':[-1,0,1,2,3,True,'1',1.0,1.5],
        'grow':[-1,0,1,2,True,'1',1.0,1.5],
        'primary':[0,1,True,False,'true'], 'toggle':[0,False],
        'label':['',0,False], 'optionLabel':['',[]],
        'origin':[{},dict(line=0,column=1),dict(line=1,column=0),dict(line=1,column=1),dict(line=1.0,column=2.0),dict(line=2**63,column=1),dict(line=True,column=2)],
        'children':[None,[],{}], 'text':[0,True,[]], 'src':[0,False],
        'id':['',1,True], 'slot':['',1,True],
    }.items():
        for i,v in enumerate(values):change(f'{key}-{i}',**{key:v})
    for value,maxv in [(None,None),(None,0),(0,0),(0,1),(1,1),(2,1),(1,None),(-1,1),(0,-1),(0,'1')]:change(f'bar-{value}-{maxv}',kind='bar',value=value,max=maxv)
    for field in ('maxIdeal','value','max'):
        for i,value in enumerate([0,-0.0,-1,0.1,1.5,5e-324,2.2250738585072014e-308,1.7976931348623157e308,9007199254740993,True,'1',{},1e-300]):change(f'{field}-numeric-{i}',**{field:value})
    for i,text in enumerate(['1.00000000000000011102230246251565404236316680908203125','1.00000000000000011102230246251565404236316680908203126','1e309','1e-4000','-1e-4000','-0.0','2.4703282292062327e-324','2.4703282292062328e-324']):
        change('decimal-'+str(i),value=Decimal(text))
    for key in ('optional','grow'):
        for text in ('1e-4000','1.0','1e0','1e309','0.99999999999999999999999999999'):
            change('integer-decimal-'+key+'-'+text,**{key:Decimal(text)})
    rng=random.Random(6)
    for i in range(80):
        bits=rng.randrange(0x7ff0000000000000);value=struct.unpack('>d',struct.pack('>Q',bits))[0]
        change('binary64-'+str(i),value=value)
    edge=dict(left='custom',right='custom',leftId='a',rightId='b',bind='normal',rule=None,source='fallback',parent='p',parentSlot='parent')
    group=dict(id='p',slot='parent',kind='group',layout='flow',after=None,children=[dict(leaf,after=edge),dict(leaf,id='b')])
    add('valid-siblings',group)
    def mutation(name,fn):
        v=copy.deepcopy(group);fn(v);add(name,v)
    for key,value in [('left','wrong'),('right','wrong'),('leftId','b'),('rightId','a'),('parent','a'),('parentSlot','wrong'),('bind','unknown'),('source','unknown'),('rule',0),('rule',-1),('rule',True)]:
        mutation('edge-'+key,lambda t,k=key,v=value:t['children'][0]['after'].__setitem__(k,v))
    for key in edge:mutation('edge-missing-'+key,lambda t,k=key:t['children'][0]['after'].__delitem__(k))
    for source in ('exact','fallback','uniform'):
        for rule in (None,1):
            for bind in ('normal','tight'):mutation(f'provenance-{source}-{rule}-{bind}',lambda t,s=source,r=rule,b=bind:t['children'][0]['after'].update(source=s,rule=r,bind=b))
    mutation('reordered',lambda t:t['children'].reverse())
    mutation('duplicate-child',lambda t:t['children'][1].update(id='a'))
    mutation('duplicate-parent',lambda t:t['children'][1].update(id='p'))
    mutation('missing-edge',lambda t:t['children'][0].update(after=None))
    mutation('final-edge',lambda t:t['children'][1].update(after=edge))
    mutation('root-edge',lambda t:t.update(after=edge))
    mutation('empty-semantic-group',lambda t:t.update(children=[]))
    mutation('bad-layout',lambda t:t.update(layout='row'))
    mutation('group-ignores-leaf-fields',lambda t:t.update(text=False,src=[]))
    add('empty-normalized-group',dict(group,children=[]),'normalized')
    add('normalized-ignores-after',dict(leaf,after='invalid'),'normalized')
    add('normalized-duplicates',dict(group,children=[leaf,leaf]),'normalized')
    for version in (None,0,2,True,'1'):
        req=dict(version=version,action='codec',phase='semantic',tree=leaf);out.append(('version-'+str(version),req))
    out.append(('missing-tree',dict(version=1,action='codec',phase='semantic')))
    return out

def comparable(value):
    # These three fields are Double in the contract. Compare exact IEEE bits,
    # not decimal spellings or tolerances; all other fields remain exact.
    if isinstance(value,dict):return {k:('binary64:'+struct.pack('>d',float(v)).hex() if k in ('maxIdeal','value','max') and type(v) in (int,float) else comparable(v)) for k,v in value.items()}
    if isinstance(value,list):return [comparable(v) for v in value]
    return value

def check_codecs():
    probes=cases();oracle=BUILD/'codec-oracle/run'
    if not oracle.exists():raise RuntimeError('Build test oracle first: goo/scripts/porting/build-codec-oracle.sh')
    expected=json.loads(subprocess.run([str(oracle)],input=codec_json([r for _,r in probes]),text=True,capture_output=True,check=True).stdout)
    actual=[]
    for start in range(0,len(probes),30):
        actual.extend(batch([r for _,r in probes[start:start+30]]))
        if start%150==0:print('Compared codec requests:',min(start+30,len(probes)),flush=True)
    accepted=[]
    for (name,request),want,got in zip(probes,expected,actual):
        mismatch=first(comparable(want.get('tree')),comparable(got.get('tree'))) if want['ok'] and got['ok'] else None
        if got['ok']!=want['ok'] or mismatch:raise AssertionError(codec_json(dict(name=name,request=request,expected=want,actual=got,mismatch=mismatch)))
        if want['ok']:accepted.append((name,dict(request,tree=got['tree'])))
    # Decoder/encoder idempotence exercises the internal-IR-to-wire boundary.
    for start in range(0,len(accepted),30):
        chunk=accepted[start:start+30];again=batch([r for _,r in chunk])
        for (name,req),got in zip(chunk,again):
            if not got['ok'] or got['tree']!=req['tree']:raise AssertionError('roundtrip: '+name)
    raw='{"version":1,"action":"codec","phase":"semantic","tree":{"id":"a","slot":"s","kind":"text","after":null,"grow":0.99999999999999999999999999999}}'
    framed=json.loads(subprocess.run([str(GOO/'foil/bin/goo-foil'),'adapter'],input=raw,text=True,capture_output=True,check=True).stdout)
    if framed['ok']:raise AssertionError('CLI prematurely rounded a fractional integer field')
    report=dict(decimal_framing=True,cases=len(probes),accepted=len(accepted),rejected=len(probes)-len(accepted),roundtrips=len(accepted),names=[name for name,_ in probes])
    (BUILD/'last-codec-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Codec differential checks:',len(probes),'roundtrips:',len(accepted),flush=True)
    return report
if __name__=='__main__':check_codecs()
