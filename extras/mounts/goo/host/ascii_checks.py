"""Gate M: exact binary64 and line comparisons with the production measurer."""
import copy,hashlib,json,math,subprocess,sys
from runtime import GOO,BUILD
from adapter import batch,codec_json
from codec_checks import comparable
sys.path.insert(0,str(GOO/'scripts/porting'))
from oracle_compare import first

def oracle(requests):
    path=BUILD/'ascii-oracle/run'
    if not path.exists():raise RuntimeError('Build goo/scripts/porting/build-ascii-oracle.sh first')
    return json.loads(subprocess.run([str(path)],input=codec_json(requests),text=True,capture_output=True,check=True).stdout)
def require(test,message):
    if not test:raise AssertionError(message)
def match(want,got,name):
    if isinstance(want,dict) and isinstance(got,dict) and want.get('ok') is False and got.get('ok') is False and want.get('stage')==got.get('stage')=='protocol':return
    if name.startswith('ascii/') and '\\x00' in name:
        require(want.get('ok') is False and got.get('ok') is False and got.get('stage')=='protocol','NUL must be rejected at the existing transport boundary')
        return
    diff=first(comparable(want),comparable(got))
    if diff:
        (BUILD/'ascii-mismatch.json').write_text(json.dumps(dict(name=name,expected=want,actual=got,mismatch=diff),indent=2))
        raise AssertionError((name,diff))
def request(tree,scale=1,widths=None):return dict(version=1,action='ascii',tree=tree,textScale=scale,widths=widths if widths is not None else [0,1,13,26,65,100.005,335,100000])
def node(slot='body',text='Hello',kind='text',**config):return dict(id='probe',kind=kind,slot=slot,text=text,after=None,**config)
def extra_cases():
    out=[]
    def add(name,tree,scale=1,widths=None):out.append((name,request(tree,scale,widths)))
    roles=['title','subtitle','label','body','summary','hint','caption','credit','provenance','value','unit','qualifier','metadata','author','timestamp','status','error','diagnostic','output','quote','attribution','icon','badge','unknown','title/sub','status/sub','/title']
    texts=['','\n','\n\n','abc\n','abc\n\n','\r\nA\rB\nC','\tX\t Y','  a  b  ','a-b/c d','x'*130,''.join(chr(c) for c in range(32,127))]
    for role in roles:
        for text in texts:add('text/'+role+'/'+repr(text),node(role,text))
    for kind in ['button','input','code','avatar','presence','bar','media']:
        for text in texts:add('primitive/'+kind+'/'+repr(text),node(kind,text,kind))
    for kind,role in [('text','title'),('text','value'),('text','status'),('code','code'),('button','button'),('media','media')]:
        for scale in [.000001,.1,.5,.75,1.25,1.5,2,10,5e-324,1e-320]:add('scale/'+kind+'/'+str(scale),node(role,'a b-c/d\nZ',kind),scale)
    for config in [dict(maxIdeal=0),dict(maxIdeal=.1),dict(maxIdeal=64.1),dict(maxIdeal=1e308),dict(grow=0),dict(grow=1),dict(label='café'),dict(optionLabel='☃')]:
        for kind in ['text','button','code','input']:add('config/'+kind+'/'+str(config),node('title','a b c',kind,**config))
    for c in [*range(32),127,128,233,0x2603]:
        for text in [chr(c),'x'+chr(c),chr(c)+'x']:add('ascii/'+repr(text),node(text=text))
    for slot in ['icon','avatar','media','icon/sub','unknown']:
        add('image/'+slot,dict(id='image',kind='media',after=None,slot=slot,src='https://example.test/café/☃'))
    for key,values in [('textScale',[0,-1,10.1,None,True,'1']),('widths',[[-1],[100001],None,[True],['2']]),('version',[0,2,True])]:
        for value in values:
            r=request(node());r[key]=value;out.append(('protocol/'+key+'/'+repr(value),r))
    for tree in [None,dict(id='bad',kind='wat'),dict(id='',kind='text',slot='body',text='x')]:out.append(('invalid-tree/'+repr(tree),request(tree)))
    # A child failure must retain that child's identity; labels and URLs are excluded.
    tree=dict(id='root',after=None,kind='group',layout='stack',slot='owner',children=[node(text='é')])
    add('nested-ascii-error',tree)
    return out

def check_fonts():
    manifest=json.loads((GOO/'fonts/metrics.json').read_text());response=batch([dict(version=1,action='fonts')])[0]
    require(response.get('ok'),response)
    ratios=oracle([dict(version=1,action='fonts')])[0]['ratios']
    expected=[]
    for (name,f),r in zip(manifest.items(),ratios):
        require(name==r['name'],'face ordering')
        expected.append(dict(name=name,**f,italic=name.startswith('Italic'),ratios=r['values']))
        for p,key in [(GOO/'fonts'/f['source'],'sourceSHA256'),(GOO/'static'/('goo-'+name+'.ttf'),'fontSHA256')]:require(hashlib.sha256(p.read_bytes()).hexdigest()==f[key],str(p))
    match(expected,response['faces'],'font metadata and 760 Haskell advances')
    return dict(faces=len(expected),glyphs=95*len(expected))

def check_ascii():
    fonts=check_fonts()
    frozen=json.loads((GOO/'static/inspector/ascii-check-cases.json').read_text())
    grouped={}
    for record in frozen:
        key=(record['node']['id'],record['scale'])
        grouped.setdefault(key,[]).append(record)
    cases=[]
    for key,rows in grouped.items():
        r=rows[0];cases.append((str(key),request(r['node'],r['scale'],[x['width'] for x in rows]+[100000]),rows))
    for name,r in extra_cases():cases.append((name,r,None))
    layout_count=0
    for start in range(0,len(cases),20):
        chunk=cases[start:start+20];requests=[r for _,r,_ in chunk]
        expected=oracle(requests);actual=batch(requests)
        for (name,r,rows),want,got in zip(chunk,expected,actual):
            if rows or not name.startswith(('ascii/','nested-ascii','protocol/','invalid-tree/')):require(want['ok'],(name,'unexpected oracle rejection',want))
            match(want,got,name)
            if got['ok']:layout_count+=sum(len(n['layouts']) for n in got['nodes'])
            if rows:
                n=got['nodes'][0]
                for record,layout in zip(rows,n['layouts']):
                    match(dict(natural=record['natural'],height=record['height'],lines=record['lines']),dict(natural=n['natural'],height=layout['height'],lines=layout['lines']),'frozen/'+name)
                match(rows[0]['unwrapped'],n['layouts'][-1]['lines'],'unwrapped/'+name)
        if start%100==0:print('Gate M requests:',min(start+20,len(cases)),'/',len(cases),flush=True)
    # Probe just below/at/above actual fit tolerances for each typographic style.
    probes=[request(node(role,'ab-c /de'),scale,[100000]) for role in ['title','body','status','error','value','code','badge','unknown'] for scale in [.1,1,1.5,2]]
    base=oracle(probes);boundary=[]
    for r,result in zip(probes,base):
        n=result['nodes'][0];natural=n['natural'];edge=natural-0.00001
        widths=[max(0,w) for w in [math.nextafter(edge,-math.inf),edge,math.nextafter(edge,math.inf),natural,math.nextafter(natural,-math.inf)]]
        boundary.append(dict(r,widths=widths))
    for start in range(0,len(boundary),16):
        chunk=boundary[start:start+16]
        for i,(a,b) in enumerate(zip(oracle(chunk),batch(chunk))):match(a,b,'rounding-boundary/'+str(start+i))
    report=dict(status='pass',**fonts,frozen_browser_cases=len(frozen),requests=len(cases),extra_requests=len(extra_cases()),layout_samples=layout_count,boundary_requests=len(boundary),boundary_widths=len(boundary)*5,nul_transport_rejections=3,numeric_comparison='exact binary64 bits; no tolerance',lines='exact strings')
    (BUILD/'last-ascii-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Gate M passed:',json.dumps(report),flush=True)
    return report
if __name__=='__main__':check_ascii()
