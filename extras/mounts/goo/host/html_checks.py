"""Gate H compares DOM structure with narrowly scoped numeric style tolerance."""
import copy,gzip,json,math,re,subprocess
from html.parser import HTMLParser
from runtime import GOO,BUILD,verify
from adapter import batch,codec_json
from codec_checks import wire,comparable
from oracle_compare import canonical,first
from layout_checks import leaf,group,require
NUMBER=re.compile(r'(?<![\w#])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
VOID={'input','img','meta','link','br','hr'}
def numeric_style(text):
    result=[];last=0
    for m in NUMBER.finditer(text):
        result.extend([text[last:m.start()],float(m.group())]);last=m.end()
    return result+[text[last:]]
def dom(text):
    class Parser(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=True);self.root=[];self.stack=[self.root]
        def handle_decl(self,data):self.stack[-1].append(dict(doctype=data.lower()))
        def handle_starttag(self,tag,attrs):
            require(len(attrs)==len(dict(attrs)),'duplicate attribute')
            attrs=dict(attrs)
            if 'style' in attrs:
                parts=[p.split(':',1) for p in attrs['style'].split(';') if p]
                require(all(len(p)==2 for p in parts) and len(parts)==len(dict(parts)),'invalid or duplicate CSS property')
                attrs['style']={k.strip():numeric_style(v.strip()) for k,v in parts}
            for key in ['aria-valuemin','aria-valuemax','aria-valuenow']:
                if key in attrs:attrs[key]=float(attrs[key])
            node=dict(tag=tag,attrs=attrs,children=[]);self.stack[-1].append(node)
            if tag not in VOID:self.stack.append(node['children'])
        def handle_startendtag(self,tag,attrs):
            self.handle_starttag(tag,attrs)
            if tag not in VOID:self.handle_endtag(tag)
        def handle_endtag(self,tag):
            require(len(self.stack)>1,'unexpected close tag '+tag)
            require(self.stack[-2][-1]['tag']==tag,'mismatched close tag '+tag);self.stack.pop()
        def handle_data(self,data):
            if self.stack[-1] and isinstance(self.stack[-1][-1],str):self.stack[-1][-1]+=data
            elif data:self.stack[-1].append(data)
        def handle_comment(self,data):self.stack[-1].append(dict(comment=data))
    p=Parser();p.feed(text);p.close();require(len(p.stack)==1,'unclosed tag');return p.root

def html_difference(a,b,path='$'):
    if type(a) in (int,float) and type(b) in (int,float):
        if a==b or (math.isfinite(a) and math.isfinite(b) and abs(a-b)<=max(1e-6,1e-10*max(abs(a),abs(b)))):return None
    elif isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return dict(path=path+'.keys',expected=sorted(a),actual=sorted(b))
        for k in sorted(a):
            d=html_difference(a[k],b[k],path+'.'+k)
            if d:return d
        return None
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return dict(path=path+'.length',expected=len(a),actual=len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            d=html_difference(x,y,path+'['+str(i)+']')
            if d:return d
        return None
    elif type(a)==type(b) and a==b:return None
    return dict(path=path,expected=a,actual=b)
def fail(name,d,a,b):
    (BUILD/'html-mismatch.json').write_text(json.dumps(dict(name=name,mismatch=d,expected=a,actual=b),indent=2))
    raise AssertionError((name,d))
def match_html(a,b,name):
    d=html_difference(dom(a),dom(b))
    if d:fail(name,d,a,b)
def match_envelope(a,b,name):
    a=canonical(a);b=canonical(b)
    for x,y in zip(a['stages'],b['stages']):
        if x['name']=='html' and x['status']==y['status']=='ok':
            match_html(x['output'],y['output'],name+'/html');x=dict(x,output=None);y=dict(y,output=None)
        d=first(comparable(x),comparable(y),numeric=x['name'] in {'metrics','layout','trace','prepared'})
        if d:fail(name+'/'+x['name'],d,x,y)
    require(a['outcome']==b['outcome'],(name,a['outcome'],b['outcome']))
def oracle(requests):
    path=BUILD/'html-oracle/run';require(path.exists(),'Build goo/scripts/porting/build-html-oracle.sh')
    return json.loads(subprocess.run([str(path)],input=codec_json(requests),text=True,capture_output=True,check=True).stdout)
def request(tree,width=752,scale=1,direction='ltr',path='/full'):return dict(version=1,action='render',tree=tree,width=width,textScale=scale,direction=direction,viewPath=path)
def compare_render(a,b,name):
    require(a.get('ok')==b.get('ok'),(name,a,b))
    if not a.get('ok'):return
    d=first(comparable(a['prepared']),comparable(b['prepared']),numeric=True)
    if d:fail(name+'/prepared',d,a['prepared'],b['prepared'])
    for key in ['html','document']:match_html(a[key],b[key],name+'/'+key)
    require('<script' not in b['document'].lower(),'canonical document has script')

def extra_cases():
    cases=[]
    def add(name,tree,**kw):cases.append((name,request(tree,**kw)))
    texts=['','<script>alert("x")</script>&\'"','  leading\tword\r\n\nnext\n','x'*180]
    for kind in ['text','button','input','code','avatar','presence','media','bar']:
        for role in ['status','error','action/destructive','title/sub']:
            for text in texts:
                n=leaf('a',role,kind=kind);n['text']=text;n.update(label='Label <&"\'',primary=True)
                if kind=='bar':n.update(value=37.5,max=75)
                add(kind+'/'+role+'/'+repr(text),n,width=99.955,scale=1.5,direction='rtl')
    for slot in ['icon','avatar','media','icon/sub','unknown']:
        for label in ['', 'alt <&"\'']:
            add('image/'+slot+'/'+label,dict(id='a',kind='avatar' if slot in ('icon','avatar') else 'media',slot=slot,src='https://example.test/a?x="&y=<b>',label=label,after=None))
    for value,maximum in [(0,100),(1,3),(1e308,1e308),(1e-320,1e-320)]:add('bar/'+str(value),dict(leaf('a','progress',kind='bar'),value=value,max=maximum))
    nested=group('root',[leaf('a','status'),group('nested',[leaf('b','title'),leaf('c','body')],layout='stack'),leaf('d','action/destructive',kind='button')],binds=['loose','separate'])
    for width in [0,1,20.125,100.005,300,100000]:
        for scale in [.5,1,1.5,2]:
            for direction in ['ltr','rtl']:add('nested/'+str((width,scale,direction)),nested,width=width,scale=scale,direction=direction)
    for path in ['/sys/slots/scar','/sys/slots/label','/sys/slots/summary','/sys/slots/inspect','/sys/slots/detail','/sys/slots/full','/full','/','/custom']:
        add('document/'+path,leaf('a'),path=path);add('empty/'+path,None,path=path)
    for key,values in [('width',[-1,100001,True,'10']),('textScale',[0,-1,11,True]),('direction',['auto',False]),('viewPath',['relative','/a/../b']),('version',[0,True])]:
        for value in values:r=request(leaf('a'));r[key]=value;cases.append(('invalid/'+key+'/'+repr(value),r))
    for tree in [None,leaf('a')]:
        cases.append(('omitted defaults',dict(version=1,action='render',tree=tree)))
        cases.append(('null defaults',dict(version=1,action='render',tree=tree,width=None,textScale=None,direction=None,viewPath=None)))
    return cases

def mutation_checks():
    base='<div class="goo-surface" dir="rtl" style="width:100px;--goo-text-scale:1"><span data-node="a" class="goo-ascii-line">safe &lt;b&gt;</span></div>'
    matches=[base.replace('width:100px','width:100.0px'),base.replace('&lt;b&gt;','&#60;b&#62;')]
    for x in matches:match_html(base,x,'equivalent encoding')
    mutations=[base.replace('rtl','ltr'),base.replace('100px','110px'),base.replace('data-node="a"','data-node="b"'),base.replace('safe','unsafe'),base.replace('goo-ascii-line','other'),base.replace('safe &lt;b&gt;','<b>safe</b>')]
    paths=[]
    for text in mutations:
        d=html_difference(dom(base),dom(text));require(d,'DOM mutation escaped comparator');paths.append(d['path'])
    return paths

def check_html(frozen_verified=0):
    records=json.load(gzip.open(GOO/'porting/oracle-reference.json.gz','rt'))
    if not frozen_verified:
        for start in range(0,len(records),12):
            rs=records[start:start+12]
            for r,a in zip(rs,batch([r['case']['request'] for r in rs])):match_envelope(r['response'],a,r['case']['name'])
            if start%60==0:print('Gate H full source',min(start+12,len(records)),'/',len(records),flush=True)
    cases=[]
    for r in records:
        stage=next(s for s in r['response']['stages'] if s['name']=='semantic')
        if stage['status']=='ok':
            rq=r['case']['request'];cases.append((r['case']['name'],request(wire(stage['output']),rq.get('width',752),rq.get('textScale',1),rq.get('direction','ltr'),rq.get('viewPath','/full'))))
    cases+=extra_cases();accepted=rejected=0
    for start in range(0,len(cases),12):
        chunk=cases[start:start+12];rs=[r for _,r in chunk]
        for (name,_),a,b in zip(chunk,oracle(rs),batch(rs)):
            compare_render(a,b,name);accepted+=bool(b.get('ok'));rejected+=not b.get('ok')
        if start%60==0:print('Gate H render',min(start+12,len(cases)),'/',len(cases),flush=True)
    for field in ['prepared','plan','lines']:
        r=request(leaf('a'));r[field]=[]
        require(batch([r])[0].get('stage')=='protocol','external '+field+' accepted')
    report=dict(status='pass',external_prepared_rejections=3,frozen_full_source_responses=len(records),render_requests=len(cases),accepted=accepted,rejected=rejected,extra_requests=len(extra_cases()),mutation_paths=mutation_checks(),html_comparison='parsed structure, text, exact nonnumeric attributes; numeric CSS/ARIA tolerance only')
    (BUILD/'last-html-checks.json').write_text(json.dumps(report,indent=2)+'\n');verify();print(json.dumps(report),flush=True);return report
if __name__=='__main__':check_html()
