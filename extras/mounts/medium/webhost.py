"""Local transport, spatial intent delivery and a real model connection.

The host never evaluates application behavior. Model output is Grove source;
Shrine compiles, assesses and installs an atomic native change set.
"""
from pathlib import Path
import importlib.util
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('medium_canvas_transport', ROOT.parent/'canvas/webhost.py')
transport = importlib.util.module_from_spec(spec); spec.loader.exec_module(transport)
spec = importlib.util.spec_from_file_location('medium_model', ROOT/'model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)

class Server(transport.Server):
    def __init__(self, root, world, native_port, authority, port):
        super().__init__(root, 'http://127.0.0.1:'+str(native_port), authority, port,
                         transport.browser_session(Path(world)/'medium-session.json'))
        self.RequestHandlerClass = Handler
        self.world = Path(world)
        self.proof = Path(root).name == 'proof'
        self.jobs = {}
        self.jobs_lock = threading.Lock()
        self.cancel = threading.Event()
        self.generation = 0
        self.native_author = None
    def frame_identity(self,result):
        if isinstance(result,dict) and 'nodes' in result:
            result['workspace']=self.cookie_name
        return result
    def call(self, operation, expected='0', event='', body=None):
        ready = getattr(self, 'native_ready', None)
        if ready is not None and not ready.is_set():
            return 503, {'error':'Your world is restoring. The current view and drafts are retained.'}
        data = urllib.parse.urlencode(dict(credential=self.authority, principal='administrator',
            operation=operation, expected=str(expected), event=event, body=json.dumps(body or {}))).encode()
        req = urllib.request.Request(self.backend+'/medium-native', data,
            {'Content-Type':'application/x-www-form-urlencoded'})
        with self.lock:
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    return response.status, self.frame_identity(json.loads(response.read(2*1024*1024)))
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read(2*1024*1024))
    def gesture(self, gesture):
        with self.jobs_lock:
            self.cancel.set()
            self.cancel = threading.Event()
            cancel = self.cancel
            self.generation += 1
            generation = self.generation
            key = uuid.uuid4().hex
            job = {'id':key,'status':'reading','message':'','created':time.time()}
            self.jobs[key] = job
            # Only receipts for the last 16 gestures; full established source is native.
            self.jobs = dict(list(self.jobs.items())[-16:])
        def work():
            context = None
            diagnostics = []
            receipts = []
            try:
                status, frame = self.call('read')
                if status != 200: raise RuntimeError(frame.get('error','Native owner unavailable'))
                selected=gesture.get('selected',{})
                if selected.get('occurrence') and selected.get('basis'):
                    subject=next((n for n in frame['nodes'] if n['id']==selected.get('subject')),None)
                    basis=selected['basis']
                    if not subject or any(subject.get(k)!=basis.get(k) for k in ('expected','displayed')):
                        raise RuntimeError('That presentation changed. Point at the current result before continuing.')
                root = '/'.join(frame['nodes'][0]['id'].split('/')[:-1]) if frame['nodes'] else '/0x11/app/medium'
                fresh = root+'/c'+key[:16]
                context = {'frame':model.scoped_frame(frame,gesture),'gesture':gesture,'new_subject':fresh,
                    'new_code_root':root.replace('/app/','/gov/')+'/c'+key[:16], 'proof':True}
                job['status']='selecting'
                known=model.exact_connection(frame,gesture)
                if known:
                    status,result=self.call('author',frame['expected'],key,{'edits':known['edits']})
                    if status==200:
                        job.update(status='done',frame=result,touched=[e['target'] for e in known['edits']],message=known['intent'])
                        return
                    if status==409:raise RuntimeError(result.get('error','The native basis changed'))
                    diagnostics.append({'proposed_reuse':known,'native_error':result})
                context['new_subjects']=[root+'/c'+key[:16]+str(i) for i in range(3)]
                context['new_code_roots']=[ref.replace('/app/','/gov/') for ref in context['new_subjects']]
                for attempt in range(3):
                    if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
                    job['status']='interpreting' if not diagnostics else 'repairing'
                    candidate, receipt = model.run(context, diagnostics, cancel, self.world)
                    receipts.append(receipt)
                    if not candidate['edits']:
                        job.update(status='done',frame=frame,touched=[],message=candidate['intent'])
                        return
                    if cancel.is_set(): raise RuntimeError('Superseded by your next interaction')
                    job['status']='checking'
                    job['message']=candidate['intent']
                    # Race check remains native and covers every dependency in this workspace.
                    status, result = self.call('author', frame['expected'], key,
                                               {'edits':candidate['edits'],'gesture':gesture})
                    if status == 200:
                        job.update(status='done',frame=result,receipt=receipt,
                                   touched=[edit['target'] for edit in candidate['edits']])
                        return
                    if status == 409: raise RuntimeError(result.get('error','The native basis changed'))
                    diagnostics.append({'source':candidate,'native_error':result})
                raise RuntimeError(diagnostics[-1]['native_error'].get('error','Native checks did not pass'))
            except Exception as error:
                if isinstance(error,model.IncompleteGeneration):receipts.append(error.receipt)
                job.update(status='cancelled' if cancel.is_set() else 'error',message=str(error))
            finally:
                # Factual local execution receipt. It is not a native approval,
                # and never includes the supervisor or browser credential.
                work_dir=self.world/'authoring';work_dir.mkdir(exist_ok=True)
                (work_dir/('attempt-'+key+'.json')).write_text(json.dumps({
                    'id':key,'gesture':gesture,'status':job['status'],
                    'message':job.get('message',''),'basis':context['frame']['expected'] if context else None,
                    'diagnostics':diagnostics,'model_runs':receipts},ensure_ascii=False,indent=2)+'\n')
                attempts=sorted(work_dir.glob('attempt-*.json'),key=lambda p:p.stat().st_mtime)
                for old in attempts[:-16]:old.unlink()
        threading.Thread(target=work,daemon=True).start()
        return job.copy()

class Handler(transport.Handler):
    # Native Foil can publish SVG/bitmap data through Goo image. Script and
    # network origins remain restricted; SVG executes only in the image context.
    image_sources = "'self' data:"
    def do_GET(self):
        if not self.valid_host(): return self.reply(403,{'error':'Local origin required'})
        path=urllib.parse.urlsplit(self.path).path
        if path == '/api/agent':
            if not self.principal(): return self.reply(401,{'error':'Local session required'})
            author = self.server.native_author
            return self.reply(200,author.status() if author else
                {'state':'unavailable','running':False,'message':'The native author is not running with this Canvas host.'})
        if path == '/api/read':
            if not self.principal(): return self.reply(401,{'error':'Connect from this local page'})
            try:
                status,result=self.server.call('read')
                if status != 200:return self.reply(status,result)
                body=json.dumps(result).encode()
                etag='"'+hashlib.sha256(body).hexdigest()+'"'
                if self.headers.get('If-None-Match')==etag:
                    return self.reply(304,b'',headers={'ETag':etag})
                return self.reply(200,body,headers={'ETag':etag})
            except Exception: return self.reply(503,{'error':'The native owner is starting. Your world is unchanged.'})
        if path.startswith('/api/jobs/'):
            if not self.principal(): return self.reply(401,{'error':'Local session required'})
            with self.server.jobs_lock: job=self.server.jobs.get(path.rsplit('/',1)[-1])
            return self.reply(200 if job else 404,job or {'error':'No such interaction'})
        assets={'/':'index.html','/medium':'index.html','/app.js':'app.js','/interaction.mjs':'interaction.mjs','/style.css':'style.css'}
        if path in assets:
            target=self.server.root/assets[path]
            if not target.exists(): return self.reply(503,{'error':'Surface is being built'})
            mime='text/html' if target.suffix=='.html' else 'text/javascript' if target.suffix in ('.js','.mjs') else 'text/css'
            return self.reply(200,target.read_bytes(),mime+'; charset=utf-8')
        if path in transport.GOO_ASSETS:
            target=ROOT.parent/'goo'/'static'/transport.GOO_ASSETS[path]
            if target.exists(): return self.reply(200,target.read_bytes(),'text/css' if path.endswith('.css') else 'font/ttf')
        self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != self.server.origin:
            return self.reply(403,{'error':'Same-origin local interaction required'})
        # Opening the local surface is the connection ceremony. Cross-origin
        # pages cannot obtain a session or send mutations; no copied URL token.
        if self.path == '/connect':
            return self.reply(200,{'connected':True},headers={
                'Set-Cookie':f'{self.server.cookie_name}={self.server.admin}; HttpOnly; SameSite=Strict; Path=/; Max-Age={transport.SESSION_AGE}'})
        if not self.principal(): return self.reply(401,{'error':'Local session required'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            limit = 1024 * 1024 if self.path == '/api/native' else transport.MAX_BODY
            if not 0 < size <= limit: return self.reply(413,{'error':'Interaction too large'})
            data=json.loads(self.rfile.read(size))
            if self.path == '/api/native':
                operation = data.get('operation')
                if operation not in ('native/discover', 'native/frame', 'native/inspect', 'native/act', 'native/undo', 'native/source', 'native/author', 'native/instantiate', 'native/prepare', 'native/commit'):
                    return self.reply(400, {'error': 'Unknown native operation'})
                status, result = self.server.call(operation, '0', data.get('event', ''), data.get('body', {}))
                return self.reply(status, result)
            if self.path == '/api/gesture': return self.reply(202,self.server.gesture(data))
            if self.path == '/api/cancel':
                self.server.cancel.set(); return self.reply(200,{'cancelled':True})
            operation=data.get('operation')
            if self.path != '/api' or operation not in ('define','act','undo','instantiate','duplicate','rebind','detach','place','relate','retire','property','description'):
                return self.reply(403,{'error':'Use native surface actions'})
            self.server.cancel.set()
            status,result=self.server.call(operation,data.get('expected','0'),data.get('event',uuid.uuid4().hex),data.get('body',{}))
            self.reply(status,result)
        except (ValueError,KeyError): self.reply(400,{'error':'Invalid interaction'})
        except Exception: self.reply(503,{'error':'Native owner unavailable; installed state was not replaced by the browser'})
