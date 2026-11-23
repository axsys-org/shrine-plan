#!/usr/bin/env python3
"""Reproducible HTTP search baseline/acceptance measurements in a DISPOSABLE world."""
import argparse, json, platform, statistics, time, urllib.request, urllib.parse, urllib.error, subprocess, hashlib, os, shutil
from pathlib import Path

HOME='/0x11/app/agents'; VIEW='/0x11/gov/shuin_agents/agents'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,help='Executable used by the server, for benchmark provenance')
    p.add_argument('--server',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sizes',default='100,1000,10000,100000');p.add_argument('--samples',type=int,default=100)
    p.add_argument('--version',type=int,default=1);p.add_argument('--label',default='baseline')
    p.add_argument('--matching',choices=['prefix','full'],help='Defaults to prefix for protocol 2, full for the old scan')
    p.add_argument('--classes',help='Comma-separated query classes; omit for the full acceptance workload')
    p.add_argument('--skip-commits',action='store_true',help='Query-only diagnostic run, not full acceptance')
    p.add_argument('--bulk-rebuild-seed',action='store_true',help='Seed a larger corpus without the search index, then rebuild once; record preparation separately from indexed commit costs')
    p.add_argument('--seed-only',action='store_true',help='Prepare the requested corpora; collect query/commit samples in a later --resume run')
    p.add_argument('--startup-log',type=Path,help='Eden log containing index construction timestamps')
    p.add_argument('--disabled-server',help='Matched disposable integrated world started with --without-search-index; avoids rebuilding the primary index between corpora')
    p.add_argument('--baseline-class-seconds',type=float,default=0,
        help='Optional cumulative time cap per OLD-scan query class; never permitted for indexed acceptance')
    p.add_argument('--resume',action='store_true');p.add_argument('--source-root',type=Path);p.add_argument('--timeout',type=float,default=120);p.add_argument('--wait',type=float,default=600)
    a=p.parse_args()
    a.matching=a.matching or ("prefix" if a.version==2 else "full")
    if a.bulk_rebuild_seed and a.version!=2: p.error('--bulk-rebuild-seed requires protocol 2')
    if a.baseline_class_seconds and (a.version!=1 or a.baseline_class_seconds<0):
        p.error('--baseline-class-seconds requires protocol 1 and a positive budget')
    out={'label':a.label,'machine':platform.platform(),'seed':20261119,'samples':a.samples,'version':a.version,'sizes':[], 'cpu': subprocess.getoutput('sysctl -n machdep.cpu.brand_string'), 'fixture_sha256': hashlib.sha256((Path(__file__).resolve().parent.parent/'mounts/shuin-chat-test/paths.foil').read_bytes()).hexdigest()}
    if a.resume and a.output.exists():
        out=json.loads(a.output.read_text())
        if out['version'] != a.version or out['samples'] != a.samples: raise RuntimeError('Resume parameters differ')
    if a.resume and out.get('matching','full') != a.matching: raise RuntimeError('Resume matching semantics differ')
    out['matching']=a.matching
    out['load_average']=os.getloadavg()
    runtime_path = a.runtime or os.environ.get('WISP') or shutil.which('wisp')
    if not runtime_path: p.error('Pass --runtime with the executable used by the measured server')
    runtime=Path(runtime_path).resolve()
    out['runtime']={'path':str(runtime),'sha256':hashlib.sha256(runtime.read_bytes()).hexdigest()}
    out['query_only']=a.skip_commits
    out['seed_only']=a.seed_only
    out['selected_classes']=a.classes
    out['baseline_class_seconds']=a.baseline_class_seconds
    class_deadline=None
    active_class=None
    def summary(values):
        ordered=sorted(values)
        return dict(p50_ms=statistics.median(ordered),p95_ms=ordered[max(0,int(.95*len(ordered)+.999)-1)],max_ms=max(ordered))
    def save():
        if active_class is not None:
            active_class['class_elapsed_ms']=used_ms+(time.perf_counter()-class_started)*1000
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    def request(path,fields,fixture=False,server=None):
        body=(json.dumps(fields).encode() if fixture else urllib.parse.urlencode(fields).encode())
        start=time.perf_counter();wall_started=time.time()
        timeout=a.timeout
        if class_deadline is not None:
            remaining=class_deadline-start
            if remaining<=0:raise TimeoutError('Baseline class time budget exhausted')
            timeout=min(timeout,remaining)
        try:
            with urllib.request.urlopen((server or a.server)+path,body,timeout=timeout) as r:data=r.read()
        except urllib.error.HTTPError as e:raise RuntimeError(f'{e.code}: {e.read().decode()}') from e
        elapsed=(time.perf_counter()-start)*1000
        wall_elapsed=(time.time()-wall_started)*1000
        if abs(wall_elapsed-elapsed)>1000:
            out.setdefault('interrupted_requests',[]).append({'path':path,'monotonic_ms':elapsed,'wall_ms':wall_elapsed})
            save()
            raise RuntimeError('Measurement interrupted by sleep or a clock adjustment; this request is not a timing sample.')
        try:value=json.loads(data)
        except ValueError:value=data.decode()
        return value,elapsed,len(data)
    def fixture(**fields):return request('/shuin-test',fields,True)
    def disabled_fixture(**fields):return request('/shuin-test',fields,True,a.disabled_server)
    wait_started=time.monotonic();wait_wall=time.time();until=wait_started+a.wait
    while True:
        try:fixture(operation='path_form');break
        except Exception:
            if time.monotonic()>until:raise
            time.sleep(1)
    readiness={'wait_ms':(time.monotonic()-wait_started)*1000,
               'wall_ms':(time.time()-wait_wall)*1000}
    out.setdefault('readiness_checks',[]).append(readiness)
    if 'readiness_wait_ms' not in out:
        out['readiness_wait_ms']=readiness['wait_ms']
        out['readiness_wall_ms']=readiness['wall_ms']
        out['startup_timing_valid']=abs(readiness['wall_ms']-readiness['wait_ms'])<=1000
    if a.startup_log and 'startup' not in out:
        import re
        trace_log=a.startup_log
        log=trace_log.read_text()
        nested=re.search(r'Compiling Eden\. Log:\s*(.+)',log)
        if nested:
            trace_log=Path(nested.group(1).strip())
            log=trace_log.read_text()
        if a.source_root is None and (trace_log.parent/'src/foil').is_dir():
            a.source_root=trace_log.parent
        stamps={kind:int(value) for kind,value in re.findall(r'"SEARCH-INDEX-([A-Z-]+)"\s+(\d+)',log)}
        out['startup']={'log':str(trace_log.resolve()),'requested_log':str(a.startup_log.resolve()),'timestamps_ns':stamps}
        if stamps and wait_wall*1e9>min(stamps.values()):
            out['startup_timing_valid']=False
            out['startup']['caveat']='Monitoring began after index construction started; an earlier sleep/clock gap cannot be excluded.'
        for scope in ('LOCAL','SYSTEM'):
            if scope+'-START' in stamps and scope+'-END' in stamps:
                out['startup'][scope.lower()+'_ms']=(stamps[scope+'-END']-stamps[scope+'-START'])/1e6
    if a.source_root:
        out['source_root']=str(a.source_root.resolve())
        out['source_hashes']={str(f.relative_to(a.source_root)):hashlib.sha256(f.read_bytes()).hexdigest()
            for folder in ['src/foil','src/mounts/shuin-chat','extras/mounts/shuin-chat']
            for f in (a.source_root/folder).rglob('*.foil')}
    view,_,_=request('/shuin/render',dict(target=HOME,view=VIEW))
    if a.disabled_server:
        state,_,_=disabled_fixture(operation='path_index_state')
        if state.get('posting_entries') != 0: raise RuntimeError('Commit control world has a search index')
        out['disabled_server']=a.disabled_server
    binding=dict(version=a.version,target=HOME,view=VIEW,slot='/0x11/gov/shuin_agents/read_dependencies',publication=view['snapshot']['publication'])
    previous=max((r.get('seeded_records',r['records'] if r.get('seed_batches_ms') else 0) for r in out['sizes']),default=0) if a.resume else 0
    for size in map(int,a.sizes.split(',')):
        row=next((r for r in out['sizes'] if r['records']==size),None)
        if row is None:
            row={'records':size,'structural_folders':(size+9)//10,'seed_batches_ms':[],'queries':{}};out['sizes'].append(row)
        if size < previous:
            if row.get('commit_samples_complete') and all(v.get('complete') or (a.version==1 and v.get('capped')) for v in row['queries'].values()): continue
            raise RuntimeError(f'Cannot resume incomplete {size}-record measurements in a {previous}-record world; use a fresh disposable world.')
        row.setdefault('seed_method','bulk rebuild' if a.bulk_rebuild_seed else 'incremental')
        if a.bulk_rebuild_seed and size>previous and not row.get('bulk_seed_started'):
            out['phase']={'operation':'retire index for bulk preparation','records':size};save()
            existing_index,_,_=fixture(operation='path_index_state')
            if existing_index.get('records',0):
                _,row['bulk_index_retire_ms'],_=fixture(operation='path_index_disable')
            else:
                row['bulk_index_retire_ms']=0
            row['bulk_seed_started']=True;save()
        out['phase']={'operation':'seed','records':size};save()
        for first in range(previous,size,500):
            _,ms,_=fixture(operation='path_bench',start=str(first),count=str(min(500,size-first)),mode='seed')
            field='unindexed_seed_batches_ms' if row.get('bulk_seed_started') else 'seed_batches_ms'
            row.setdefault(field,[]).append(ms);row['seeded_records']=first+min(500,size-first);save()
        if row.get('bulk_seed_started') and not row.get('bulk_index_ready'):
            out['phase']={'operation':'rebuild prepared corpus','records':size};save()
            attempts=row.setdefault('bulk_rebuild_attempts',[])
            attempt={'started_unix_seconds':time.time()};attempts.append(attempt);save()
            try:
                _,ms,_=fixture(operation='path_index_enable')
                attempt.update(completed=True,elapsed_ms=ms)
                row['bulk_index_ready']=True
                # A retry may observe an already-finished build. Do not label
                # that cheap readiness check as construction performance.
                row['bulk_index_rebuild_ms']=ms if len(attempts)==1 else None
                row['index_size'],_,_=fixture(operation='path_index_state')
                save()
            except Exception as error:
                attempt['error']=str(error);save();raise
        previous=max(previous,size)
        if a.disabled_server:
            for first in range(out.get('disabled_seeded_records',0),size,500):
                _,ms,_=disabled_fixture(operation='path_bench',start=str(first),count=str(min(500,size-first)),mode='seed')
                row.setdefault('disabled_seed_batches_ms',[]).append(ms)
                out['disabled_seeded_records']=first+min(500,size-first);save()
        if a.seed_only:continue
        n=size//2;title=f'Study {n} festival astronomy '+('שלום 東京' if n%7==0 else 'notes')
        queries={'exact_title':title,'exact_path':f'/0x11/app/search_bench/group{n//10}/item{n}',
                 'short_prefix':'St','long_prefix':f'Study {n} festival','substring':'ival astr',
                 'path_prefix':'/0x11/app/search_bench','fuzzy':'sdyftvastr','miss':'qxz987nonexistent','empty':'','common':'festival','unicode':'שלום','eligibility':'/sys'}
        if a.matching=='prefix':
            queries['common']='Study '
            queries['unicode']='Study 7 festival astronomy ש'
            queries['substring_miss']=queries.pop('substring')
            queries['fuzzy_miss']=queries.pop('fuzzy')
        for kind,q in queries.items():
            if a.classes and kind not in a.classes.split(','): continue
            existing=row['queries'].get(kind,{})
            continuation_incomplete=(kind=='common' and existing.get('continuation_ms')
                and len(existing.get('continuation_bytes',[]))!=len(existing['continuation_ms']))
            if existing.get('complete') and not continuation_incomplete: continue
            out['phase']={'operation':'query','records':size,'class':kind};save()
            used_ms=existing.get('class_elapsed_ms',sum(existing.get('samples_ms',[]))
                +existing.get('first_ms',0)+sum(existing.get('continuation_ms',[])))
            stats=row['queries'].setdefault(kind,{'samples_ms':[],'bytes':[]})
            stats.setdefault('samples_ms',[]);stats.setdefault('bytes',[])
            class_started=time.perf_counter()
            active_class=stats
            class_deadline=(class_started+max(0,a.baseline_class_seconds-used_ms/1000)
                if a.baseline_class_seconds else None)
            fields=dict(binding,query=q,after='',revision='')
            if kind=='eligibility': fields['slot']='/0x11/gov/shuin_agents/write_dependencies'
            try:
                first,ms,_=request('/shuin/paths',fields)
                if kind not in ('miss','substring_miss','fuzzy_miss','eligibility') and not first['items'] and not first.get('limited'): raise RuntimeError('Invalid benchmark: expected hits')
                if kind == 'exact_title' and first['items'][0]['title'] != title: raise RuntimeError('Exact title fixture mismatch')
                if kind == 'exact_path' and first['items'][0]['path'] != q: raise RuntimeError('Exact path fixture mismatch')
                if kind in ('miss','substring_miss','fuzzy_miss') and first['items']: raise RuntimeError('Miss unexpectedly matched')
                stats['query']=q
                stats.setdefault('first_ms',ms)
                stats.pop('capped',None)
                stats['index_revision']=first['revision'];stats.pop('error',None)
                for _ in range(3):request('/shuin/paths',fields)
                for _ in range(len(stats["samples_ms"]),a.samples):
                    page,elapsed,bytes_=request('/shuin/paths',fields)
                    stats['samples_ms'].append(elapsed);stats['bytes'].append(bytes_)
                    if 'stats' in page:stats.setdefault('work_samples',[]).append(page['stats'])
                    stats.setdefault('counts',[]).append(len(page['items']))
                    stats.setdefault('limited',[]).append(page.get('limited',False))
                    save()
                stats.update(summary(stats['samples_ms']));save()
                if kind == 'common' and first.get('next'):
                    if continuation_incomplete:
                        stats['earlier_continuation_ms']=stats.pop('continuation_ms')
                    pages=stats.setdefault('continuation_ms',[])
                    for _ in range(len(pages),a.samples):
                        page,elapsed,bytes_=request('/shuin/paths',dict(fields,after=first['next'],revision=first['revision']))
                        pages.append(elapsed)
                        stats.setdefault('continuation_bytes',[]).append(bytes_)
                        stats.setdefault('continuation_counts',[]).append(len(page['items']))
                        stats.setdefault('continuation_limited',[]).append(page.get('limited',False))
                        if 'stats' in page:stats.setdefault('continuation_work',[]).append(page['stats'])
                        save()
                    stats['continuation_ms']=pages
                    stats['continuation_summary']=summary(pages)
                stats['complete']=True
                stats['gate_100ms']=stats['p95_ms']<=100
                print(a.label,size,kind,round(stats['p95_ms'],2),flush=True)
            except Exception as e:
                capped=class_deadline is not None and time.perf_counter()>=class_deadline
                if capped:
                    stats['capped']=True;stats['complete']=False
                    if stats['samples_ms']:stats.update(summary(stats['samples_ms']))
                    stats['error']=f'Baseline capped at {a.baseline_class_seconds:g}s; {len(stats["samples_ms"])} / {a.samples} measured first pages'
                else:stats['error']=str(e)
                print(a.label,size,kind,stats['error'],flush=True)
            finally:
                stats['class_elapsed_ms']=used_ms+(time.perf_counter()-class_started)*1000
                class_deadline=None
                active_class=None
                save()
            save()
        def commits(label,run=fixture):
            out['phase']={'operation':label,'records':size};save()
            times={mode:[] for mode in ('rename','restore','create','delete','bulk_create','bulk_delete')}
            result={'samples_ms':times,'summary':{}}
            row[label]=result
            def measured(operation_name,**fields):
                try:
                    _,ms,_=run(**fields)
                except Exception as error:
                    result['error']=str(error);save();raise
                times[operation_name].append(ms)
                result['summary'][operation_name]=summary(times[operation_name]);save()
            for i in range(20):
                for mode,verb in [('rename','rename'),('restore','seed')]:
                    measured(mode,operation='path_bench',start=str(n),count='1',mode=verb)
                for mode,verb in [('create','seed'),('delete','delete')]:
                    measured(mode,operation='path_bench',start='200000',count='1',mode=verb)
            for i in range(5):
                for mode,verb in [('bulk_create','seed'),('bulk_delete','delete')]:
                    measured(mode,operation='path_bench',start='300000',count='100',mode=verb)
            return result
        if not a.skip_commits and not row.get('commit_samples_complete'):
            row['commits_enabled']=commits('commits_enabled')
            if a.version == 2:
                row['index_size'],_,_=fixture(operation='path_index_state')
                if a.disabled_server:
                    row['commits_disabled']=commits('commits_disabled',disabled_fixture)
                else:
                    _,row['index_retire_ms'],_=fixture(operation='path_index_disable')
                    row['commits_disabled']=commits('commits_disabled')
                    _,row['index_rebuild_ms'],_=fixture(operation='path_index_enable')
                    _,row['first_query_after_rebuild_ms'],_=request('/shuin/paths',dict(binding,query=title,after='',revision=''))
            row['commit_samples_complete']=True;save()
    gate=next((r for r in out['sizes'] if r['records']==10000),None)
    out['http_acceptance']={'evaluated':bool(gate and len(gate['queries'])==12 and not a.classes and a.samples>=100),
        'passed':bool(gate and not a.classes and a.samples>=100 and len(gate['queries'])==12 and all(v.get('complete') and v.get('gate_100ms') for v in gate['queries'].values()))}
    out['phase']={'operation':'prepared' if a.seed_only else 'finished'}
    save()
if __name__=='__main__':main()
