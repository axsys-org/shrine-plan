"""Application I/O boundary: files, HTTP, UUID entropy and retained Rex printing.

All Goo compilation, display projection and HTML page assembly run in Foil.
The host never accepts caller-supplied pass snapshots on an HTTP route.
"""
import contextlib,json, os, pathlib, re, sys, time, urllib.parse, threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from adapter import retained, allocate_ids, codec_json
from runtime import PACKAGE, invoke, verify

_execution=threading.local()

def execute(requests,directory):
    worker=getattr(_execution,"worker",None)
    if worker is not None:
        if worker.directory!=directory:raise RuntimeError("Server build changed; restart the server")
        return worker.invoke(requests)
    return invoke(requests,directory,False)

DEFAULT_VIEW='/sys/slots/summary'
USAGE='''Usage: goo [command]

Commands:
  serve [--port N]   Run the dev server on port N (default 8000); the default command
  passes [FILE]      Print the output of every lowering pass
  html [--width N] [--text-scale N] [--rtl] [FILE]   Print static HTML (width 752)

FILE defaults to stdin.'''

def decoded(text):
    return json.loads(text,parse_float=Decimal,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite JSON number')))

def native(action,value,directory):
    return execute([(action,codec_json(value))],directory)[0]

def print_snapshots(result,directory):
    snapshots=result['snapshots']
    requests=[dict(version=1,action='goo-print',trees=s[key]) for s in snapshots for key in ('trees','diffTrees')]
    printed=retained(directory,requests) if requests else []
    for i,s in enumerate(snapshots):
        s['output']=printed[2*i]['text'];s['diffOutput']=printed[2*i+1]['text']
        del s['trees'];del s['diffTrees']
    return result

def compile_source(source,options=None,directory=None):
    directory=directory or verify()[0]
    options=dict(viewPath=DEFAULT_VIEW,**(options or {})) if not options or 'viewPath' not in options else dict(options)
    trees=retained(directory,[dict(version=1,action='parse',source=source)])[0]['trees']
    count=execute([('prepare',trees)],directory)[0]['count']
    try:ids=allocate_ids(count)
    except (OSError,RuntimeError):ids=[]
    result=execute([('application',(trees,codec_json(options),codec_json(ids)))],directory)[0]
    if not result.get('ok'):raise ValueError(result.get('error','invalid compilation request'))
    return print_snapshots(result,directory)

@contextlib.contextmanager
def production_worker(directory):
    worker=getattr(_execution,"worker",None)
    owned=worker is None
    if worker is not None and worker.directory!=directory:raise RuntimeError("Server build changed; restart the server")
    if owned:
        from workers import Worker
        worker=Worker(directory,verify(directory,False)[1])
    try:
        yield worker
    except BaseException:
        # A failed printer exchange must not leave a pending request for reuse.
        worker.close()
        raise
    finally:
        if owned:worker.close()

def finish_printing(worker,request,directory):
    if request.get('ok') is not True:raise ValueError('invalid compile request')
    batches=request['batches']
    texts=retained(directory,[dict(version=1,action='goo-print-compact',batches=batches)])[0]['texts'] if batches else []
    if len(texts)!=len(batches) or not all(isinstance(t,str) for t in texts):raise RuntimeError('invalid printer response')
    return worker.invoke([('finish',codec_json(texts))])[0]

def production_source(source,mode='lower',options=None,directory=None,identities=None):
    directory=directory or verify()[0]
    options={'viewPath':DEFAULT_VIEW,**(options or {}),'mode':mode}
    trees=retained(directory,[dict(version=1,action='parse',source=source)])[0]['trees']
    with production_worker(directory) as worker:
        count=worker.invoke([('prepare',trees)])[0]['count']
        try:ids=allocate_ids(count) if identities is None else identities
        except (OSError,RuntimeError):ids=[]
        arguments=(trees,codec_json(options),codec_json(ids))
        if mode in {'html','preview'}:return worker.invoke([('ssr' if mode=='html' else 'preview',arguments)])[0]
        request=worker.invoke([('begin',arguments)])[0]
        return finish_printing(worker,request,directory)

def lower(source,options=None,output_only=False):return production_source(source,'preview' if output_only else 'lower',options)

def layout(request):
    if not isinstance(request,dict) or 'width' not in request or 'tree' not in request:raise ValueError('Invalid layout JSON.')
    result=native('production-layout',{**request,'direction':'ltr','viewPath':DEFAULT_VIEW},verify()[0])
    if not result.pop('ok',False):raise ValueError(result.get('error','Invalid layout JSON.'))
    return result

def rendered(request):
    directory=verify()[0]
    with production_worker(directory) as worker:
        pending=worker.invoke([('begin-measured',codec_json(request))])[0]
        if not pending.get('ok'):raise ValueError('Invalid measurement JSON.')
        return finish_printing(worker,pending,directory)

def page(action,**values):
    return native('view',dict(action=action,**values),verify()[0])['html']

def valid_name(name):return bool(name) and len(name)<=64 and all(c.isalnum() or c in '-_' for c in name)
def valid_file(name):return valid_name(name.split('.')[0]) and all(c.isalnum() or c in '-_.' for c in name)
def root_path():
    if 'GOO_ROOT' in os.environ:return pathlib.Path(os.environ['GOO_ROOT']).resolve()
    if pathlib.Path('static/inspector/app.js').is_file():return pathlib.Path.cwd()
    return PACKAGE

def stamp(path):
    from datetime import datetime,timezone
    stat=path.stat();secs,nanos=divmod(stat.st_mtime_ns,10**9)
    return datetime.fromtimestamp(secs,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')+('.'+f'{nanos:09d}'.rstrip('0') if nanos else '')+' UTC'

def query_options(query):
    # Keep absent values distinct from empty UTF-8 values, as WAI does.
    pairs=[]
    for part in query.split('&') if query else []:
        key,sep,value=part.partition('=')
        pairs.append((urllib.parse.unquote_to_bytes(key.replace('+',' ')),urllib.parse.unquote_to_bytes(value.replace('+',' ')) if sep else None))
    def get(key):return next((v for k,v in pairs if k==key.encode()),None)
    options={}
    if any(k==b'view' for k,_ in pairs):
        value=get('view')
        if value is None:raise ValueError('Missing view path.')
        try:options['viewPath']=value.decode('utf-8')
        except UnicodeDecodeError:raise ValueError('View path must be UTF-8.')
        path=options['viewPath']
        if not path.startswith('/') or (path!='/' and any(not p or p in {'.','..'} or any(not(c.isalnum() or c in '_-.') for c in p) for p in path[1:].split('/'))):raise ValueError('View path must be absolute, with nonempty segments and no . or .. segments.')
    message='Budget must be 0–2; hiddenPaths must be arrays of nonnegative integer indices.'
    budget=get('budget')
    if budget is not None:
        try:
            text=budget.decode('utf-8');assert re.fullmatch(r'\s*[+]?\d+\s*',text)
            options['budget']=int(text);assert options['budget'] in (0,1,2)
        except (ValueError,AssertionError):raise ValueError(message)
    hidden=get('hiddenPaths')
    if hidden is not None:
        try:
            paths=decoded(hidden)
            assert isinstance(paths,list) and all(isinstance(p,list) and all(type(n) in (int,Decimal) and n==int(n) and 0<=n<=2**63-1 for n in p) for p in paths)
            options['hiddenPaths']=paths
        except (ValueError,AssertionError,UnicodeError,TypeError):raise ValueError(message)
    options['uniform']=get('uniform')==b'1'
    return options,get('outputOnly')==b'1'

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,root):
        self.root=pathlib.Path(root);self.boot=str(round(time.time()*1000))
        from workers import Pool
        directory,manifest=verify();self.workers=Pool(directory,manifest)
        try:super().__init__(address,Handler)
        except BaseException:self.workers.close();raise
    def server_close(self):
        self.workers.close();super().server_close()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def send(self,status,body='',content_type='text/plain; charset=utf-8',headers=()):
        data=body.encode('utf-8') if isinstance(body,str) else body
        try:
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            for key,value in headers:self.send_header(key,value)
            self.end_headers()
            if status!=304:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def json(self,value):self.send(200,codec_json(value),'application/json',[('Cache-Control','no-cache')])
    def html(self,value):self.send(200,value,'text/html; charset=utf-8',[('Cache-Control','no-cache')])
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size<0:raise ValueError('Invalid Content-Length.')
        return self.rfile.read(size)
    def names(self):return sorted(p.stem for p in (self.server.root/'examples').glob('*.goo') if p.is_file())
    def source(self,name):return (self.server.root/'examples'/(name+'.goo')).read_text(encoding='utf-8',errors='replace')
    def do_GET(self):self.dispatch('GET')
    def do_POST(self):self.dispatch('POST')
    def do_PUT(self):self.dispatch('PUT')
    def dispatch(self,method):
        url=urllib.parse.urlsplit(self.path)
        parts=[urllib.parse.unquote(p) for p in url.path.split('/') if p]
        try:
            dynamic=(method=='POST' and parts in (['lower'],['layout'],['rendered'])) or (method=='GET' and parts in ([],['gallery']))
            if dynamic:
                with self.server.workers.lease() as worker:
                    _execution.worker=worker
                    try:self.route(method,parts,url.query)
                    finally:_execution.worker=None
            else:self.route(method,parts,url.query)
        except (ValueError,UnicodeError,TypeError,KeyError) as e:self.send(400,'Invalid measurement JSON.' if parts==['rendered'] else str(e))
        except FileNotFoundError:self.send(404,'not found')
        except (OSError,RuntimeError) as e:self.send(500,str(e))
    def route(self,method,parts,query):
        root=self.server.root
        if method=='POST' and parts==['lower']:
            options,output_only=query_options(query)
            result=lower(self.body().decode('utf-8','replace'),options,output_only)
            if output_only:result.pop('passes',None)
            return self.json(result)
        if method=='POST' and parts==['layout']:return self.json(layout(decoded(self.body())))
        if method=='POST' and parts==['rendered']:return self.json(rendered(decoded(self.body())))
        if method=='GET' and not parts:
            names=self.names();requested=urllib.parse.parse_qs(query).get('example',[None])[0]
            current=requested if requested in names else 'profile' if 'profile' in names else next(iter(names),None)
            return self.html(page('page',names=names,current=current,source=self.source(current) if current else ''))
        if method=='GET' and parts==['gallery']:
            metadata=[]
            for name in ('adversarial.json','domain.json'):
                try:values=decoded((root/'examples'/name).read_bytes())
                except (OSError,ValueError):values=[]
                if isinstance(values,list):metadata.extend(values)
            examples=[]
            for name in self.names():
                meta=next((dict(v) for v in metadata if isinstance(v,dict) and v.get('name')==name),None)
                if meta is not None:meta.pop('tree',None)
                examples.append([name,self.source(name),meta])
            return self.html(page('gallery',examples=examples))
        if len(parts)==2 and parts[0]=='examples' and valid_name(parts[1]):
            if method=='GET':return self.send(200,self.source(parts[1]))
            if method=='PUT':
                (root/'examples'/(parts[1]+'.goo')).write_text(self.body().decode('utf-8','replace'),encoding='utf-8')
                return self.send(204)
        if method=='GET' and parts==['version']:
            files=[*(root/'static').glob('*'),*(root/'static/inspector').glob('*'),root/'src/goo.generated.css']
            return self.json(dict(boot=self.server.boot,assets=max((stamp(p) for p in files if p.is_file()),default='')))
        if method=='GET' and ((len(parts)==2 and parts[0]=='static') or (len(parts)==3 and parts[:2]==['static','inspector'])) and valid_file(parts[-1]):
            path=root.joinpath(*parts)
            headers=[('Cache-Control','no-cache')]
            if parts==['static','goo.generated.css']:
                path=root/'src/goo.generated.css';tag='"'+stamp(path)+':'+str(path.stat().st_size)+'"';headers.append(('ETag',tag))
                if self.headers.get('If-None-Match')==tag:return self.send(304,b'','text/css; charset=utf-8',headers)
            mime={'.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.ttf':'font/ttf','.html':'text/html; charset=utf-8','.svg':'image/svg+xml','.png':'image/png'}.get(path.suffix,'application/octet-stream')
            return self.send(200,path.read_bytes(),mime,headers)
        self.send(404,'not found')

def serve(port=8000):
    verify();root=root_path()
    with Server(('127.0.0.1',port),root) as server:
        print(f'goo dev server on http://localhost:{server.server_port}  (root: {root})',flush=True)
        server.serve_forever()

def diagnostics(result,prefix=''):
    return [prefix+('-' if d['location'] is None else str(d['location']['line'])+':'+str(d['location']['column']))+': '+d['message'] for s in result['snapshots'] for d in s['diagnostics']]

def main(arguments):
    if not arguments or arguments==['serve']:return serve()
    if len(arguments)==3 and arguments[:2]==['serve','--port']:
        try:port=int(arguments[2]);assert 0<=port<=65535
        except (ValueError,AssertionError):raise SystemExit(USAGE)
        return serve(port)
    if arguments[0]=='passes' and len(arguments)<=2:
        path=arguments[1] if len(arguments)==2 else None;mode='passes';options={}
    elif arguments[0]=='html':
        mode='html';path=None;options={};args=iter(arguments[1:])
        try:
            for arg in args:
                if arg in ('--width','--text-scale'):
                    text=next(args);number=Decimal(text)
                    options['width' if arg=='--width' else 'textScale']=number
                elif arg=='--rtl':options['direction']='rtl'
                elif not arg.startswith('--') and path is None:path=arg
                else:raise ValueError()
        except (ValueError,ArithmeticError,StopIteration):raise SystemExit('Invalid html arguments.\n'+USAGE)
    else:raise SystemExit(USAGE)
    try:
        source=pathlib.Path(path).read_text() if path is not None else sys.stdin.read()
        result=production_source(source,mode,options)
        if mode=='passes':sys.stdout.write(result.get('text',''))
        else:
            for line in result.get('diagnostics',[]):print(line,file=sys.stderr)
        if result.get('crash'):
            print('pass '+result['crash']['name']+' threw: '+result['crash']['message'],file=sys.stderr)
        if not result.get('success'):
            if result.get('error'):raise SystemExit('render: '+result['error'])
            raise SystemExit(1)
        if mode=='html':print(result['document'])
    except (OSError,RuntimeError,ValueError) as e:raise SystemExit(str(e))
