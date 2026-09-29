"""Real signals exercise CLI cancellation and process-group cleanup."""
import fcntl, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
import adapter
from runtime import PACKAGE, Cancelled, run

BLOCKER = '''import fcntl, pathlib, subprocess, sys, time
root=pathlib.Path(sys.argv[1])
held=(root/'parent.lock').open('w');fcntl.flock(held,fcntl.LOCK_EX)
child=subprocess.Popen([sys.executable,'-c',"import fcntl,pathlib,sys,time; p=pathlib.Path(sys.argv[1]); f=(p/'child.lock').open('w'); fcntl.flock(f,fcntl.LOCK_EX); (p/'child.ready').touch(); time.sleep(60)",str(root)])
while not (root/'child.ready').exists():time.sleep(.01)
(root/'ready').touch()
child.wait()
'''
HARNESS = '''import pathlib,runpy,sys
sys.path.insert(0,sys.argv[1])
import adapter,runtime
root=pathlib.Path(sys.argv[2]);stage=sys.argv[3];launcher=sys.argv[4]
def block(*args,**kwargs):
    runtime.run([sys.executable,str(root/'blocker.py'),str(root)],root,timeout=30)
setattr(adapter,stage,block)
sys.argv=[launcher,'adapter']
runpy.run_path(launcher,run_name='__main__')
'''

def require(condition,message):
    if not condition:raise AssertionError(message)
def check_cancellation():
    report=[]
    request=dict(version=1,action='source',source='x')
    # The adapter must propagate cancellation, while still framing ordinary errors.
    for stage in ('retained','invoke'):
        for exception in (KeyboardInterrupt(),Cancelled(signal.SIGTERM)):
            with patch.object(adapter,stage,side_effect=exception):
                try:adapter.batch([request])
                except type(exception):pass
                else:raise AssertionError('adapter swallowed cancellation at '+stage)
            report.append(stage+': '+type(exception).__name__+' propagated')
        with patch.object(adapter,stage,side_effect=RuntimeError('synchronous failure')):
            response=adapter.batch([request])[0]
            require(response['ok'] is False and response['error']=='synchronous failure','synchronous failure framing')
        report.append(stage+': synchronous failure framed')
    for stage in ('retained','invoke'):
        for signum in (signal.SIGINT,signal.SIGTERM):
            with tempfile.TemporaryDirectory(prefix='goo-cancel-') as temp:
                root=Path(temp);(root/'blocker.py').write_text(BLOCKER)
                proc=subprocess.Popen([sys.executable,'-c',HARNESS,str(PACKAGE/'host'),temp,stage,str(PACKAGE/'bin/goo-foil')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    proc.stdin.write(json.dumps(request));proc.stdin.close();proc.stdin=None
                    deadline=time.monotonic()+10
                    while not (root/'ready').exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                    require((root/'ready').exists(),'cancellation fixture did not become ready')
                    for name in ('parent','child'):
                        with (root/(name+'.lock')).open('a') as held:
                            try:fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
                            except BlockingIOError:pass
                            else:raise AssertionError('fixture process was not holding its lock')
                    proc.send_signal(signum);stdout,stderr=proc.communicate(timeout=10)
                    require(proc.returncode==128+signum,'wrong cancellation exit status: '+str(proc.returncode)+stderr)
                    require(not stdout,'cancellation emitted ordinary JSON: '+stdout)
                    for name in ('parent','child'):
                        with (root/(name+'.lock')).open('a') as held:
                            deadline=time.monotonic()+3
                            while True:
                                try:fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                                except BlockingIOError:
                                    if time.monotonic()>deadline:raise AssertionError('cancelled descendant still running')
                                    time.sleep(.01)
                    report.append(stage+': '+signal.Signals(signum).name+' stops process group without JSON')
                finally:
                    if proc.poll() is None:
                        proc.send_signal(signal.SIGTERM)
                        try:proc.communicate(timeout=3)
                        except subprocess.TimeoutExpired:proc.kill();proc.communicate()
    for signum in (signal.SIGINT,signal.SIGTERM):
        try:run([sys.executable,'-c',f'import os,signal; signal.signal({int(signum)},signal.SIG_DFL); os.kill(os.getpid(),{int(signum)})'],PACKAGE)
        except Cancelled as cancelled:require(cancelled.signum==signum,'child signal lost')
        else:raise AssertionError('child cancellation converted to ordinary failure')
        report.append('child '+signal.Signals(signum).name+' propagates')
    return report
if __name__=='__main__':print(json.dumps(check_cancellation(),indent=2))
