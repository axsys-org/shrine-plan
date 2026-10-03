#!/usr/bin/env python3
"""Exercise the actual native Canvas owner; emits compact, credential-free evidence."""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import statistics
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
from eden_runtime import process_tree_usage

class Client:
    def __init__(self, connection):
        cfg=json.loads(Path(connection).read_text())
        parsed=urllib.parse.urlsplit(cfg['url'])
        self.origin=f'{parsed.scheme}://{parsed.netloc}'
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        token=urllib.parse.parse_qs(parsed.fragment)['session'][0]
        self.send('/session',{'token':token})
    def send(self,path,payload=None):
        request=urllib.request.Request(self.origin+path,None if payload is None else json.dumps(payload).encode(),
            {'Origin':self.origin,'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=60) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
    def read(self):
        code,data=self.send('/api');assert code==200,(code,data);return data
    def action(self,operation,frame,body,event=None):
        return self.send('/api',dict(operation=operation,expected=frame['expected'],event=event or str(uuid.uuid4()),body=body))

def journey(client,agent_connection):
    evidence=[]
    def passed(name):evidence.append(name);print('PASS',name,flush=True)
    frame=client.read();before=frame['revision']
    code,frame=client.action('stage',frame,dict(turnaround='15',same_person='true',intent='Give different people a handover, but let the same person continue.'))
    assert code==200,(code,frame);passed('native candidate staged')
    case=frame['cases'][0];assert case['after']['kind']=='available'
    code,frame=client.action('demonstrate',frame,dict(**case['query'],available='true',label='The same person can continue at 11:00'))
    assert code==200 and frame['candidate']['new_commitments']=='1',(code,frame)
    code,frame=client.action('publish',frame,dict(revision=frame['candidate']['revision']))
    assert code==200 and int(frame['revision'])==int(before)+1 and frame['commitments'][0]['kind']=='holding'
    passed('approved demonstration becomes retained native commitment')
    code,frame=client.action('stage',frame,dict(turnaround='15',same_person='false',intent='A deliberately regressing candidate'))
    assert code==200 and not frame['candidate']['admissible']
    expected=frame['expected']
    code,rejected=client.action('publish',frame,dict(revision=frame['candidate']['revision']))
    assert code==409,(code,rejected)
    assert client.read()['expected']==expected
    passed('later regression rejected without changing installed state')
    cfg=json.loads(Path(agent_connection).read_text())
    request=urllib.request.Request(cfg['url']+'/api',json.dumps(dict(operation='stage',expected=frame['expected'],event=str(uuid.uuid4()),body=dict(turnaround='15',same_person='true',intent='Restore the retained same-person example.'))).encode(),{'Authorization':'Bearer '+cfg['token'],'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:frame=json.loads(response.read())
    assert frame['candidate']['admissible'];assert client.read()['candidate']['revision']==frame['candidate']['revision']
    passed('agent continuation visible to the browser in the same native candidate')
    code,frame=client.action('publish',frame,dict(revision=frame['candidate']['revision']))
    assert code==200
    case=frame['cases'][2]
    event=str(uuid.uuid4());basis=frame;payload=dict(case['query'],equipment=frame['equipment'][1]['id']);count=len(frame['reservations'])
    code,frame=client.action('reserve',basis,payload,event)
    assert code==200 and len(frame['reservations'])==count+1,(code,frame)
    code,repeated=client.action('reserve',basis,payload,event)
    assert code==200 and repeated['expected']==frame['expected']
    code,collision=client.action('reserve',basis,dict(payload,finish='900'),event)
    assert code==409 and client.read()['expected']==frame['expected']
    passed('installed rule creates a real reservation; duplicate and collision are safe')
    return evidence,frame

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--journey',action='store_true')
    parser.add_argument('--reads',type=int,default=0)
    parser.add_argument('--owner-pid',type=int)
    parser.add_argument('--subject',help='Exercise the real native presentation of this exact subject instead of the workspace frame')
    parser.add_argument('--max-p95-ms',type=float)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();client=Client(args.world/'canvas-admin.json')
    result={'started':time.time(),'status':'running','checks':[]}
    try:
        if args.journey:result['checks'],frame=journey(client,args.world/'canvas-agent.json')
        else:frame=client.read()
        result['revision']=frame['revision'];result['reservations']=len(frame['reservations']);result['commitments']=frame['commitments']
        retained={key:frame[key] for key in ('expected','revision','policy','candidate','reservations','commitments','intentions')}
        result['state_sha256']=hashlib.sha256(json.dumps(retained,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if args.reads:
            # A read receipt records the exact native case as well as on-disk store sizes.
            def read_frame():
                if not args.subject:return client.read()
                code,data=client.action('present',frame,{'target':args.subject})
                assert code==200,(code,data)
                return data
            warm=read_frame()
            projection_sha=hashlib.sha256(json.dumps(warm,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            for _ in range(100):read_frame()
            pins=args.world/'snap/pins.pack';size=pins.stat().st_size
            database=args.world/'snap/data.mdb';database_size=database.stat().st_size
            basis=warm['expected'];latencies=[];samples=[]
            result['read_subject']=args.subject
            result['projection_sha256']=projection_sha
            for i in range(args.reads):
                started=time.perf_counter();current=read_frame();latencies.append((time.perf_counter()-started)*1000)
                assert hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()==projection_sha
                assert current['expected']==basis
                if (i+1)%100==0:
                    if args.owner_pid:
                        usage=process_tree_usage(args.owner_pid)
                        samples.append(dict(read=i+1,charged_bytes=sum(p['charged'] for p in usage),processes=usage))
                        result['memory_samples']=samples
                        args.output.parent.mkdir(parents=True,exist_ok=True)
                        args.output.write_text(json.dumps(result,indent=2)+'\n')
                    if (i+1)%1000==0 or args.reads<=100:print('Reads',i+1,flush=True)
            result['reads']=dict(count=args.reads,database_bytes_before=database_size,database_bytes_after=database.stat().st_size,pin_bytes_before=size,pin_bytes_after=pins.stat().st_size,p50_ms=statistics.median(latencies),p95_ms=sorted(latencies)[int(len(latencies)*.95)-1])
            assert pins.stat().st_size==size
            assert database.stat().st_size==database_size
            result['memory_samples']=samples
            if samples and args.reads>=1000:
                half=next(s for s in samples if s['read']>=args.reads//2)['charged_bytes']
                growth=max(s['charged_bytes'] for s in samples if s['read']>=args.reads//2)-half
                result['final_half_growth_bytes']=growth
                assert growth<=16*2**20,('Memory growth exceeds release budget',growth)
            result['reads']=dict(count=args.reads,database_bytes_before=database_size,database_bytes_after=database.stat().st_size,pin_bytes_before=size,pin_bytes_after=pins.stat().st_size,p50_ms=statistics.median(latencies),p95_ms=sorted(latencies)[int(len(latencies)*.95)-1])
            if args.max_p95_ms is not None:
                assert result['reads']['p95_ms']<=args.max_p95_ms,('Read latency exceeds budget',result['reads']['p95_ms'],args.max_p95_ms)
        result['status']='passed'
    except BaseException as error:
        result['status']='failed';result['error']=str(error)
        raise
    finally:
        result['completed']=time.time();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
        print('Evidence:',args.output)

if __name__=='__main__':main()
