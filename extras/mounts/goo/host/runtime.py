"""Build and run an immutable local Foil publication, without test fixtures."""
import hashlib, json, os, pathlib, re, shutil, signal, subprocess, sys, tempfile
from wire import DECODE, node, string
sys.set_int_max_str_digits(0)
PACKAGE=pathlib.Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[2]
GOO=ROOT/'goo'  # Historical oracle/test inputs; never used by production build or serving.
BUILD=PACKAGE/'.build'
ATOM=r'("(?:[^"\\]|\\.|"")*"|[0-9]+)'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inputs():
    files=[*PACKAGE.glob('*.foil'),*PACKAGE.glob('host/*.py'),PACKAGE/'package.json',PACKAGE/'mount.json',PACKAGE/'bin/goo-foil',PACKAGE/'flake.lock',PACKAGE/'flake.nix',ROOT/'flake.lock',ROOT/'flake.nix',PACKAGE/'rex/Main.hs',PACKAGE/'rex/Goo/Rex/Layout.hs',ROOT/'x/stage-lib',PACKAGE/'scripts/generate-rules.py',PACKAGE/'scripts/generate-fonts.py']
    for folder in ['fonts','rules']:
        files.extend(p for p in (PACKAGE/folder).rglob('*') if p.is_file())
    files.extend([*sorted((PACKAGE/'static').glob('goo-*.ttf')),PACKAGE/'static/reference.css',PACKAGE/'static/ascii-fonts.css'])
    for directory,suffix in [('foil','*.foil'),('reaver','*.rvr'),('plan','*.plan')]:files.extend((ROOT/'src'/directory).rglob(suffix))
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}
class Cancelled(BaseException):
    """Process cancellation must never become an ordinary adapter failure."""
    def __init__(self,signum):self.signum=signum

def cancel_signal(signum,frame):raise Cancelled(signum)

def run(command,cwd,source='',timeout=900):
    with subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True) as proc:
        try:out,err=proc.communicate(source,timeout=timeout)
        except BaseException:
            # Kill descendants as well as the direct child, then reap it.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.communicate();raise
        if proc.returncode in (-signal.SIGINT,-signal.SIGTERM):
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            raise Cancelled(-proc.returncode)
        if proc.returncode:raise RuntimeError(f'{command[0]} exited {proc.returncode}: {(err+out)[-4000:]}')
        return out,err

def decode_atom(token):
    if token.startswith('"'):return token[1:-1].replace('""','"').replace('\\\\','\\')
    n=int(token);return n.to_bytes((n.bit_length()+7)//8,'little').decode('utf-8')
def responses(log,marker,count):
    if marker=='GOO-APP' and 'GOO-JSON ' in log:
        values={}
        # Split only on LF: Unicode line separators are legal JSON string data.
        for line in log.split('\n'):
            if not line.startswith('GOO-JSON '):continue
            index,separator,payload=line[len('GOO-JSON '):].partition(' ')
            if not separator or not index.isascii() or not index.isdigit():raise RuntimeError('invalid runtime frame')
            index=int(index)
            if index in values:raise RuntimeError('duplicate runtime response')
            values[index]=json.loads(payload)
        if set(values)!=set(range(count)):raise RuntimeError('missing runtime response')
        return [values[i] for i in range(count)]
    values={}
    for m in re.finditer(r'^\("'+marker+r'"\s+'+ATOM+r'\s+'+ATOM+r'\s*\)',log,re.M):
        index=int(m[1]) if not m[1].startswith('"') else int.from_bytes(decode_atom(m[1]).encode(),'little')
        if index in values:raise RuntimeError('duplicate runtime response')
        values[index]=json.loads(decode_atom(m[2]))
    if set(values)!=set(range(count)):raise RuntimeError('Foil execution failed: '+log[-4000:])
    return [values[i] for i in range(count)]

def compile_source():
    # A deterministic, unpublished development authority. It is not a signing
    # key or a claim on any user's node. Deployment authority belongs to item 34.
    authority=int.from_bytes(hashlib.sha256(b'goo-foil-local-development-v1').digest(),'big')
    return f'''(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(#bind rex (#module rex))
(#bind source (#module foil-source))
(#bind driver (#module foil-new-env))
(#bind publication (#module foil-publication))
(#bind context (#module foil-context))
(#bind bootstrap (#module foil-bootstrap))
(#bind subject (#module foil-subject))
(define compiler (Pin driver:compile))
(Seq (define system-plan (publication:prepare-system compiler source:read-module bootstrap:system-roots)) (DeepSeq system-plan 0))
(Seq (define system-code (publication:compile system-plan driver:empty-foil-cache)) (DeepSeq system-code 0))
(define (local-root name)
  (define found (find (lambda (pair) (Equal name (_0 pair))) bootstrap:system-roots))
  (If found (_1 (_0 found)) [["x" {authority}] ["ts" "goo-development"] ["ts" name]]))
(Seq (define app-plan (source:prepare-publication (context:publication-key (publication:compilation-context system-plan)) compiler local-root (_2 system-code) (lambda (path) 0) ["goo_app/types" "goo_app/results" "goo_app/adapter" "goo_app/tests"])) (DeepSeq app-plan 0))
(Seq (define app-code (publication:compile app-plan (_1 system-code))) (DeepSeq app-code 0))
(define (app-subject name)
  (driver:perc-subject (Unpin (_1 (need (find (lambda (pair) (Equal name (_0 pair))) (_2 app-code)))))))
(define adapter (app-subject "goo_app/adapter"))
(define tests (app-subject "goo_app/tests"))
(define goo-source (driver:source-entry-val ["goo_adapter" "source"] adapter))
(define goo-accept (driver:source-entry-val ["goo_adapter" "accept"] adapter))
(define goo-capabilities (driver:source-entry-val ["goo_adapter" "capabilities"] adapter))
(define goo-syntax (driver:source-entry-val ["goo_adapter" "syntax"] adapter))
(define goo-prepare (driver:source-entry-val ["goo_adapter" "prepare"] adapter))
(define goo-start (driver:source-entry-val ["goo_adapter" "production_start"] adapter))
(define goo-start-measured (driver:source-entry-val ["goo_adapter" "production_measured"] adapter))
(define goo-printer-request (driver:source-entry-val ["goo_adapter" "production_request"] adapter))
(define goo-finish (driver:source-entry-val ["goo_adapter" "production_finish"] adapter))
(define goo-preview (driver:source-entry-val ["goo_adapter" "production_preview"] adapter))
(define goo-ssr (driver:source-entry-val ["goo_adapter" "production_ssr"] adapter))
(define goo-production-layout (driver:source-entry-val ["goo_adapter" "production_layout"] adapter))
(define goo-pending 0)
(define goo-input 0)
(define goo-application (driver:source-entry-val ["goo_adapter" "application"] adapter))
(define goo-compile (driver:source-entry-val ["goo_adapter" "compile"] adapter))
(define goo-measurement (driver:source-entry-val ["goo_adapter" "measurement"] adapter))
(define goo-measured-display (driver:source-entry-val ["goo_adapter" "measured_display"] adapter))
(define goo-view (driver:source-entry-val ["goo_adapter" "view"] adapter))
(define goo-html-cli (driver:source-entry-val ["goo_adapter" "html_cli"] adapter))
(define goo-render (driver:source-entry-val ["goo_adapter" "render"] adapter))
(define goo-fixture (driver:source-entry-val ["goo_adapter" "fixture"] adapter))
(define goo-layout (driver:source-entry-val ["goo_adapter" "layout"] adapter))
(define goo-ascii (driver:source-entry-val ["goo_adapter" "ascii"] adapter))
(define goo-fonts (driver:source-entry-val ["goo_adapter" "fonts"] adapter))
(define goo-codec (driver:source-entry-val ["goo_adapter" "codec"] adapter))
(define goo-tests (driver:source-entry-val ["goo_tests" "run"] tests))
{DECODE}
(define (goo-call name arg)
  (cond ((Equal name "source") (goo-source arg))
    ((Equal name "accept") (goo-accept arg))
    ((Equal name "capabilities") (goo-capabilities 0))
    ((Equal name "prepare") (goo-prepare arg))
    ((Equal name "application") (goo-application (_0 arg) (_1 arg) (_2 arg)))
    ((Equal name "preview") (goo-preview (_0 arg) (_1 arg) (_2 arg)))
    ((Equal name "production-layout") (goo-production-layout arg))
    ((Equal name "compile") (goo-compile (_0 arg) (_1 arg) (_2 arg)))
    ((Equal name "measurement") (goo-measurement arg))
    ((Equal name "measured-display") (goo-measured-display arg))
    ((Equal name "view") (goo-view arg))
    ((Equal name "html-cli") (goo-html-cli arg))
    ((Equal name "render") (goo-render arg))
    ((Equal name "fixture") (goo-fixture arg))
    ((Equal name "layout") (goo-layout arg))
    ((Equal name "ascii") (goo-ascii arg))
    ((Equal name "fonts") (goo-fonts 0))
    ((Equal name "codec") (goo-codec arg))
    ((Equal name "syntax") (goo-syntax arg))
    ((Equal name "tests") (goo-tests 0))
    (else (error "unknown Goo entry"))))
; Write UTF-8 JSON directly; never send a large response through the REPL's
; decimal atom pretty-printer. Write uses the runtime's length-marked byte bar.
(define (goo-run-ssr arg) (goo-ssr (_0 arg) (_1 arg) (_2 arg)))
(define (goo-emit-html index value)
  (define meta (_0 value))
  (define html (_1 value))
  (define payload (strcat ["GOO-HTML " (showNat index) " " (showNat (Bytes meta)) " " (showNat (Bytes html)) 10 meta html 10]))
  (Write 1 (Add payload (Bex (Mul 8 (Bytes payload))))))
(define (goo-emit index value)
  (define payload (strcat ["GOO-JSON " (showNat index) " " value 10]))
  (Write 1 (Add payload (Bex (Mul 8 (Bytes payload))))))
(Seq (goo-emit 0 (goo-capabilities 0)) 0)
(Seq (print ("GOO-BUILD" 0 (goo-capabilities 0))) 0)
(Seq (print ("GOO-BUILD" 1 (goo-tests 0))) 0)
'''

def build(wisp=None):
    BUILD.mkdir(exist_ok=True)
    # Serialize builds, and publish only a complete verified generation.
    import fcntl
    with (BUILD/'build.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not wisp:
            wisp=os.environ.get('WISP')
        if not wisp:
            out,err=run(['nix','develop','.#eden','--command','sh','-c','command -v wisp'],ROOT)
            if err:print(err,file=sys.stderr,end='')
            wisp=out.strip()
        wisp=str(pathlib.Path(wisp).resolve())
        run([sys.executable,str(PACKAGE/'scripts/generate-rules.py'),'--check'],ROOT)
        run([sys.executable,str(PACKAGE/'scripts/generate-fonts.py'),'--check'],ROOT)
        source_hashes=inputs();runtime_hash=sha(pathlib.Path(wisp))
        key=hashlib.sha256(json.dumps([source_hashes,runtime_hash],sort_keys=True).encode()).hexdigest()[:20]
        destination=BUILD/key
        if destination.exists():
            verify(destination,False)
            select(key);return destination
        with tempfile.TemporaryDirectory(prefix='build-',dir=BUILD) as temp:
            work=pathlib.Path(temp);overlay=work/'sources';overlay.mkdir()
            for name in ('reaver','plan'):shutil.copytree(ROOT/'src'/name,overlay/name)
            shutil.copytree(ROOT/'src/foil',overlay/'foil')
            (overlay/'foil/goo_app').mkdir()
            for source in PACKAGE.glob('*.foil'):shutil.copy2(source,overlay/'foil/goo_app'/source.name)
            toolchain=work/'toolchain';toolchain.mkdir()
            for name in ('flake.nix','flake.lock'):shutil.copy2(PACKAGE/name,toolchain/name)
            logs=[]
            print('Building the retained Rex component',file=sys.stderr)
            out,err=run(['nix','develop','path:'+str(toolchain),'--command','ghc','-v0','-hide-all-packages','-package','base','-package','rex','-package','aeson','-package','bytestring','-package','vector','-package','text','-irex','-outputdir',str(work/'ghc'),'-o',str(work/'retained-rex'),'rex/Main.hs'],PACKAGE)
            logs.extend([out,err])
            print('Staging and compiling the Foil package',file=sys.stderr)
            out,err=run(['sh','-eu','-c','. "$1/x/stage-lib"; stage_repl "$2" "$1"','sh',str(ROOT),wisp],work)
            logs.extend([out,err])
            out,err=run([wisp,'--file-root',str(overlay),'snap','root','_'],work,compile_source())
            logs.extend([out,err]);(BUILD/'last-build.log').write_text('\n'.join(logs))
            answers=responses(out+err,'GOO-BUILD',2)
            if responses(out+err,'GOO-APP',1)!=[answers[0]]:raise RuntimeError('Runtime framing smoke check failed')
            if not all(a['ok'] for a in answers):raise RuntimeError('Foil unit tests failed: '+json.dumps(answers))
            if inputs()!=source_hashes:raise RuntimeError('Build inputs changed during compilation; run build again')
            artifact=work/'artifact';artifact.mkdir();shutil.move(str(work/'snap'),artifact/'snapshot');shutil.move(str(work/'retained-rex'),artifact/'retained-rex')
            (artifact/'empty').mkdir()
            manifest=dict(version=1,key=key,wisp=wisp,runtime_sha256=runtime_hash,inputs=source_hashes,artifacts={str(p.relative_to(artifact)):sha(p) for p in [artifact/'retained-rex',artifact/'snapshot/data.mdb',artifact/'snapshot/pins.pack']},unit_tests=answers[1])
            (artifact/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            artifact.rename(destination)
        select(key)
        return destination

def select(key):
    pointer=BUILD/'current.new';pointer.write_text(key+'\n');pointer.replace(BUILD/'current')

def verify(directory=None,check_sources=True):
    if directory is None:
        try:key=(BUILD/'current').read_text().strip()
        except FileNotFoundError:raise RuntimeError('No build available; run extras/mounts/goo/bin/goo build')
        if not re.fullmatch('[0-9a-f]{20}',key):raise RuntimeError('Invalid build pointer')
        directory=BUILD/key
    manifest=json.loads((directory/'manifest.json').read_text())
    if sha(pathlib.Path(manifest['wisp']))!=manifest['runtime_sha256']:raise RuntimeError('Runtime changed; rebuild')
    for name,digest in manifest['artifacts'].items():
        if sha(directory/name)!=digest:raise RuntimeError('Build artifact changed; rebuild: '+name)
    if check_sources and inputs()!=manifest['inputs']:raise RuntimeError('Build is stale; run extras/mounts/goo/bin/goo build')
    return directory,manifest

def string_argument(value):
    # Keep decimal atoms bounded: the runtime reader otherwise retains a huge
    # intermediate addition chain while decoding large JSON requests.
    if not isinstance(value,str) or '\0' in value:raise ValueError('expected NUL-free string')
    raw=value.encode('utf-8')
    if len(raw)<=512:return string(value)
    chunks=[str(int.from_bytes(raw[i:i+512],'little')) for i in range(0,len(raw),512)]
    def join(parts):
        if len(parts)==1:return parts[0]
        mid=len(parts)//2
        return '(strWeld '+join(parts[:mid])+' '+join(parts[mid:])+')'
    return join(chunks)

# Large values are data files, never code or decimal literals in the REPL.
# The runtime can read only this private data root; no source tree is mounted.
import contextlib
@contextlib.contextmanager
def request_files(root):
    root.mkdir(exist_ok=True)
    files=[]
    def encode(value):
        if not isinstance(value,str) or '\0' in value:raise ValueError('expected NUL-free string')
        if len(value.encode('utf-8'))<=8192:return string_argument(value)
        name='request-'+str(len(files))+'.json'
        path=root/name;files.append(path);path.write_bytes(value.encode('utf-8'))
        return '(read-text-file "'+name+'")'
    try:yield encode
    finally:
        for path in files:path.unlink(missing_ok=True)

def request_source(requests,encode_string=None):
    encode_string=encode_string or string_argument
    lines=[]
    for i,(action,value) in enumerate(requests):
        if action in {'source','accept','prepare'}:
            arg='(map decode (datum (quote ('+' '.join(node(t) for t in value)+'))))' if value else '0'
        elif action in {'compile','application','begin','ssr','preview'}:
            trees,options,ids=value
            ts='(map decode (datum (quote ('+' '.join(node(t) for t in trees)+'))))' if trees else '0'
            arg='['+ts+' '+encode_string(options)+' '+encode_string(ids)+']'
        elif action in {'syntax','codec','measurement','ascii','layout','fixture','render','measured-display','view','html-cli','finish','begin-measured','production-layout'}:arg=encode_string(value)
        else:arg='0'
        if action=='ssr':
            lines.append(f'(Seq (goo-emit-html {i} (goo-run-ssr {arg})) 0)')
            continue
        if action=='begin':
            lines.append(f'(Seq (define goo-input {arg}) (Seq (define goo-pending (goo-start (_0 goo-input) (_1 goo-input) (_2 goo-input))) (Seq (goo-emit {i} (goo-printer-request goo-pending)) 0)))')
            continue
        if action=='begin-measured':
            lines.append(f'(Seq (define goo-pending (goo-start-measured {arg})) (Seq (goo-emit {i} (goo-printer-request goo-pending)) 0))')
            continue
        if action=='finish':
            lines.append(f'(Seq (goo-emit {i} (goo-finish goo-pending {arg})) (Seq (define goo-pending 0) (define goo-input 0)))')
            continue
        lines.append(f'(Seq (goo-emit {i} (goo-call {string(action)} {arg})) 0)')
    return '\n'.join(lines)+'\n'

def invoke(requests,directory=None,check_sources=True):
    directory,manifest=verify(directory,check_sources)
    if any(action=='ssr' for action,_ in requests):
        from workers import Worker
        worker=Worker(directory,manifest)
        try:return worker.invoke(requests)
        finally:worker.close()
    with tempfile.TemporaryDirectory(prefix='goo-foil-run-') as temp:
        work=pathlib.Path(temp);(work/'snap').mkdir()
        for name in ['data.mdb','pins.pack']:shutil.copy2(directory/'snapshot'/name,work/'snap'/name)
        with request_files(work/'inputs') as encode_string:
            source=request_source(requests,encode_string)
            out,err=run([manifest['wisp'],'--file-root',str(work/'inputs'),'snap','root','_'],work,source)
        return responses(out+err,'GOO-APP',len(requests))

def read_html_frame(stream,header):
    """Length-delimited UTF-8 HTML, with a small JSON status/diagnostic header."""
    match=re.fullmatch(rb'GOO-HTML ([0-9]+) ([0-9]+) ([0-9]+)\n',header)
    if not match:raise RuntimeError('invalid HTML frame header')
    index,meta_size,html_size=map(int,match.groups())
    meta=stream.read(meta_size);body=stream.read(html_size)
    if len(meta)!=meta_size or len(body)!=html_size or stream.read(1)!=b'\n':raise RuntimeError('truncated HTML frame')
    value=json.loads(meta)
    if not isinstance(value,dict) or 'document' in value:raise RuntimeError('invalid HTML metadata')
    return index,dict(value,document=body.decode('utf-8'))
