"""Local UI and physical calendar ingestion; authoritative app state is in Shrine."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import argparse, json, re, threading, time
from bridge import *
import canvas

PORT=8784
LOCK=threading.RLock()
SYNC_LOCK=threading.Lock()
LAST_ERROR=''
SEED=browser_seed()
PRECISE={str(i):d for i,d in SEED['deadlines']}
BROWSER_EPOCH=int(datetime.fromisoformat(SEED['observed_at'].replace('Z','+00:00')).timestamp()) if SEED.get('observed_at') else 0

def apply_snapshot(data, observed_epoch=None):
    items=canvas.parse(data) # Validate the entire input before applying any item.
    now=observed_epoch or int(time.time())
    artifact=canvas.archive(data)
    receipt=observe('calendar-feed',{'item_count':len(items),'artifact':artifact,'source_host':'sit.instructure.com'},revision=artifact['sha256'])
    schema=one('/campus/schema')
    existing={r['uid']:r for root in ('/campus/assignments','/campus/events') for r in read(root,True) if r.get('uid')}
    known_courses={r.get('id') for r in read('/campus/courses',True)}
    for item in items:
        cid=item['course_id']
        if cid and cid not in known_courses:
            upsert('/campus/courses/'+str(cid),{'id':cid,'name':item['course_name'],
                'code':'Course '+str(cid),'url':f'https://sit.instructure.com/courses/{cid}',
                'evidence':{'path':receipt['path']}})
            known_courses.add(cid)
    for raw in items:
        item=dict(raw); old=existing.get(item['uid'],{})
        p=('/campus/assignments/' if item['kind']=='assignment' else '/campus/events/')+item['uid']
        precise=PRECISE.get(str(item.get('canvas_id','')))
        if item['due_precision']=='date' and precise and precise[:10]==item['due_date']:
            item.update(due_epoch=int(datetime.fromisoformat(precise).timestamp()),due_precision='browser',
                        exact_time_observed_epoch=BROWSER_EPOCH)
        item.update(observed_epoch=now,evidence={'path':receipt['path']},last_seen_revision=artifact['sha256'],present_in_latest=1)
        if not old:
            item.update(submission_state='unknown',local_done=0,note='',origin_work={'path':WORK})
            if item['kind']=='assignment':
                item.update({'/sys/limb':schema['assignment_behavior'],'/sys/crew':schema['crew']})
        write(p,item,old.get('_case',0),not old)
        if not old and item['kind']=='assignment':write(p,{})
    # Feed coverage is partial. Disappearance means unobserved, never deletion/completion.
    seen={r['uid'] for r in items}
    for uid,old in existing.items():
        if uid not in seen and old.get('present_in_latest',1):
            write(old['_path'],{'present_in_latest':0,'coverage_note':'Not present in the latest limited feed; verify in Canvas.'},old['_case'])
    upsert('/campus/source',{'observed_epoch':now,'last_attempt_epoch':now,'availability':'available','last_error':'',
        'item_count':len(items),'assignment_count':sum(r['kind']=='assignment' for r in items),'event_count':sum(r['kind']=='event' for r in items),
        'snapshot_sha256':artifact['sha256'],'evidence':{'path':receipt['path']},'window_start':min(r['due_date'] for r in items) if items else '',
        'window_end':max(r['due_date'] for r in items) if items else ''})
    return {'ok':True,'items':len(items),'evidence':receipt['path']}

def sync():
    global LAST_ERROR
    if not SYNC_LOCK.acquire(blocking=False):return {'ok':False,'busy':True}
    try:
        data=canvas.fetch()
        with LOCK: result=apply_snapshot(data)
        LAST_ERROR=''
        return result
    except Exception as error:
        # Do not leak a secret feed URL in an exception or native receipt.
        LAST_ERROR=f'Calendar refresh failed ({type(error).__name__}); last successful data retained.'
        with LOCK:
            upsert('/campus/source',{'last_attempt_epoch':int(time.time()),'availability':'unavailable','last_error':LAST_ERROR})
            observe('calendar-feed-failure',{'error':LAST_ERROR},availability='unavailable',coverage='unknown')
        return {'ok':False,'error':LAST_ERROR}
    finally:SYNC_LOCK.release()

def snapshot():
    with LOCK:
        return {'courses':read('/campus/courses',True),'assignments':read('/campus/assignments',True),
            'events':read('/campus/events',True),'source':one('/campus/source'),'settings':one('/campus/settings'),
            'clock':one('/campus/clock'),'notices':read('/campus/notices',True),
            'syncing':SYNC_LOCK.locked(),'server_epoch':int(time.time())}

def monitor():
    while True:
        try:
            with LOCK:
                upsert('/campus/clock',{'epoch':int(time.time())})
                source=one('/campus/source');settings=one('/campus/settings')
            interval=max(300,int(settings.get('refresh_seconds',900)))
            if int(time.time())-source.get('last_attempt_epoch',0)>=interval:sync()
        except Exception as error:
            print('Monitor error:',type(error).__name__,flush=True)
        time.sleep(60)

class Handler(BaseHTTPRequestHandler):
    def valid_host(self):return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}')
    def send(self,data,kind='application/json',status=200):
        data=json.dumps(data).encode() if not isinstance(data,(str,bytes)) else data.encode() if isinstance(data,str) else data
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if not self.valid_host():return self.send({'error':'Invalid host'},status=403)
        try:
            if self.path=='/api/state':return self.send(snapshot())
            assets={'/':('index.html','text/html'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
            if self.path not in assets:return self.send({'error':'Not found'},status=404)
            name,kind=assets[self.path];self.send((ROOT/name).read_bytes(),kind)
        except Exception:self.send({'error':'Shrine is unavailable. Previous native state is preserved.'},status=503)
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
            return self.send({'error':'Same-origin requests only'},status=403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>8192:raise ValueError('Request too large')
            body=json.loads(self.rfile.read(size) or b'{}')
            if self.path=='/api/sync':
                if not SYNC_LOCK.locked():threading.Thread(target=sync,daemon=True).start()
                return self.send({'ok':True,'queued':True})
            if self.path=='/api/plan':
                uid=body.get('uid','')
                if not re.fullmatch(r'event-assignment-[a-zA-Z0-9-]+',uid):raise ValueError('Invalid item')
                updates={k:body[k] for k in ('local_done','note') if k in body}
                if not updates:raise ValueError('No planning change')
                if 'local_done' in updates and (type(updates['local_done']) is not int or updates['local_done'] not in (0,1)):raise ValueError('Invalid completion')
                if 'note' in updates and (not isinstance(updates['note'],str) or len(updates['note'])>4000):raise ValueError('Note too long')
                if type(body.get('case')) is not int:raise ValueError('Missing revision')
                with LOCK:
                    if not one('/campus/assignments/'+uid):raise ValueError('Unknown assignment')
                    write('/campus/assignments/'+uid,updates,body['case'])
                return self.send({'ok':True})
            return self.send({'error':'Unknown action'},status=404)
        except Exception as error:self.send({'error':'Could not save this revision. Refresh and try again.','detail':type(error).__name__},status=409)
    def log_message(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['serve','sync','import']);p.add_argument('file',nargs='?');args=p.parse_args()
    if args.command=='sync':print(json.dumps(sync()));raise SystemExit(0 if not LAST_ERROR else 1)
    if args.command=='import':print(json.dumps(apply_snapshot(Path(args.file).read_bytes())));raise SystemExit()
    if not one('/campus/schema'):raise SystemExit('Run install.py first.')
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    threading.Thread(target=monitor,daemon=True).start()
    print(f'Coursebook at http://127.0.0.1:{PORT}',flush=True);server.serve_forever()
