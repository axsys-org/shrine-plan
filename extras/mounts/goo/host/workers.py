"""Bounded, preloaded execution workers for the HTTP transport.

Workers retain the immutable executable only. Calls contain complete inputs;
no Goo tree, width, UUID pool, response or per-request cache is shared. A lease
serializes each worker's stdin/stdout protocol and recycles it after 64 calls.
"""
import collections,contextlib,pathlib,queue,shutil,signal,subprocess,tempfile,threading,os
from runtime import request_source,responses,request_files,read_html_frame

class Worker:
    def __init__(self,directory,manifest):
        self.directory=directory;self.calls=0;self.healthy=True
        self.temp=tempfile.TemporaryDirectory(prefix='goo-foil-http-')
        work=pathlib.Path(self.temp.name);self.inputs=work/'inputs';self.inputs.mkdir();shutil.copytree(directory/'snapshot',work/'snap')
        self.process=subprocess.Popen([manifest['wisp'],'--file-root',str(self.inputs),'snap','root','_'],cwd=work,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        self.output=queue.Queue();self.errors=collections.deque(maxlen=20)
        def stdout():
            try:
                while True:
                    line=self.process.stdout.readline()
                    if not line:break
                    self.output.put(read_html_frame(self.process.stdout,line) if line.startswith(b'GOO-HTML ') else line)
            except BaseException as error:self.errors.append(str(error).encode('utf-8'))
            finally:self.output.put(None)
        def stderr():
            for line in self.process.stderr:self.errors.append(line[-4000:])
        self.readers=[threading.Thread(target=stdout,daemon=True),threading.Thread(target=stderr,daemon=True)]
        for reader in self.readers:reader.start()
        try:
            if self.invoke([('capabilities',None)])[0].get('ok') is not True:raise RuntimeError('invalid worker startup')
        except BaseException:self.close();raise
    def invoke(self,requests):
        if not self.healthy:raise RuntimeError('execution worker is unavailable')
        if not requests:return []
        try:
            with request_files(self.inputs) as encode_string:
                self.process.stdin.write(request_source(requests,encode_string).encode('utf-8'));self.process.stdin.flush()
                lines=[];html_values={}
                for _ in requests:
                    line=self.output.get(timeout=900)
                    if line is None:raise RuntimeError('execution worker exited: '+b''.join(self.errors).decode('utf-8','replace')[-4000:])
                    if isinstance(line,tuple):
                        index,value=line
                        if index in html_values:raise RuntimeError('duplicate HTML response')
                        html_values[index]=value
                        line=('GOO-JSON '+str(index)+' null\n').encode()
                    if not line.startswith(b'GOO-JSON '):raise RuntimeError('invalid worker frame')
                    lines.append(line.decode('utf-8'))
                result=responses(''.join(lines),'GOO-APP',len(requests));self.calls+=len(requests)
                for index,value in html_values.items():result[index]=value
                return result
        except BaseException:
            self.healthy=False;self.close();raise
    def close(self):
        self.healthy=False
        if self.process.poll() is None:
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        self.process.wait()
        for reader in self.readers:reader.join(timeout=2)
        for pipe in (self.process.stdin,self.process.stdout,self.process.stderr):pipe.close()
        self.temp.cleanup()

class Pool:
    def __init__(self,directory,manifest,size=4):
        self.directory=directory;self.manifest=manifest;self.closed=False
        self.available=queue.Queue();self.workers=set();self.lock=threading.Lock()
        try:
            for _ in range(size):
                worker=Worker(directory,manifest);self.workers.add(worker);self.available.put(worker)
        except BaseException:self.close();raise
    @contextlib.contextmanager
    def lease(self):
        worker=self.available.get()
        try:
            if self.closed:raise RuntimeError('server is shutting down')
            yield worker
        finally:
            with self.lock:
                if not self.closed:
                    if not worker.healthy or worker.calls>=64:
                        worker.close();self.workers.discard(worker)
                        worker=Worker(self.directory,self.manifest);self.workers.add(worker)
                    self.available.put(worker)
    def close(self):
        with self.lock:
            self.closed=True
            for worker in self.workers:worker.close()
            self.workers.clear()
