#!/usr/bin/env python3
"""Actual compiled surface/owner checks, with no browser or usability claim.

Run only against a disposable/new native-material world. The script edits its
two seed values, verifies correspondence, batches and subscriptions, then
restores the values through the very same native actions.
"""
import argparse
import json
import math
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from eden_runtime import process_tree_usage

parser = argparse.ArgumentParser()
parser.add_argument('--world', type=Path, required=True)
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--reads', type=int, default=100)
parser.add_argument('--edits', type=int, default=40)
parser.add_argument('--owner-pid', type=int)
parser.add_argument('--memory-limit-mib', type=int, default=1536)
args = parser.parse_args()
world = args.world.resolve()
if not world.name.startswith('grove-native-material-'):
    raise SystemExit('This mutating check is only for a native-material development world.')
authority = (world / 'src/medium-authority').read_text()
results, timings, memory = [], [], []
if args.owner_pid:
    command = subprocess.check_output(['/bin/ps', '-p', str(args.owner_pid), '-o', 'command='], text=True)
    if str(world) not in command or 'x/eden' not in command:
        raise SystemExit('Memory measurement must target this world\'s Eden launcher.')

def sample_memory(read):
    if args.owner_pid:
        processes = process_tree_usage(args.owner_pid)
        if not processes:
            raise AssertionError('Owned process tree disappeared during measurement.')
        memory.append(dict(read=read, charged=sum(p['charged'] for p in processes), processes=processes))

def call(operation, body, event='', principal='administrator'):
    encoded = urllib.parse.urlencode(dict(credential=authority, principal=principal,
        operation=operation, expected='0', event=event, body=json.dumps(body))).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{args.port}/medium-native', data=encoded)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            code, value = response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        code, value = error.code, json.loads(error.read())
    timings.append({'operation': operation, 'status': code, 'ms': (time.perf_counter()-started)*1000})
    return code, value

def check(name, valid, evidence=None, *, fatal=True):
    results.append(dict(name=name, passed=bool(valid), evidence=evidence))
    print(('PASS ' if valid else 'FAIL ')+name, flush=True)
    if not valid and fatal:
        raise AssertionError((name, evidence))

first = '/0x11/app/material/working'
second = '/0x11/app/material/another'
a, b = '/0x11/app/material/values/a', '/0x11/app/material/values/b'

def frame(subject=first):
    status, data = call('native/frame', dict(subject=subject, viewport=[]))
    if status != 200:raise AssertionError((status, data))
    return data

def row(f, target):
    return next(o for o in f['occurrences'] if o['focus']['subject'] == target and o['slot'] == '/value' and o['key'] != '/increment')

def edit(f, target, value, subject=first, event=None):
    return call('native/act', dict(subject=subject, viewport=[], basis=f['basis'],
        key=row(f, target)['key'], parameters=[], arguments=[dict(slot='/value', kind='natural', value=str(value))]),event or uuid.uuid4().hex)

def discover(target):
    status, page = call('native/discover', dict(subject=target))
    if status != 200:raise AssertionError((status, page))
    return page

def number(target):
    return int(next(s['value'] for s in discover(target)['slots'] if s['slot'] == '/value'))

def pins():
    return {str(p.relative_to(world)):p.stat().st_size for p in (world/'snap').rglob('*') if p.name=='pins.pack'}

original = None
try:
    start, reordered = frame(), frame(second)
    original = (number(a), number(b))
    check('compiled Foil produced an editable repeated surface', '<input' in start['html'] and len(start['occurrences'])>=4)
    check('two views retain the original subject and opaque slot after reordering',row(start,b)['focus']==row(reordered,b)['focus'])
    code, detail = call('native/inspect', dict(subject=first,viewport=[],basis=start['basis'],key=row(start,b)['key'],parameters=[]))
    check('exact element inspection resolves native subject and basis',code==200 and detail['occurrence']['focus']['subject']==b,detail)
    event=uuid.uuid4().hex
    code, result = edit(start,b,41,event=event)
    check('native element edit commits',code==200,result)
    check('the original record changes without a projection copy',number(b)==41)
    changed=frame(); other=frame(second)
    check('both native presentations observe the same changed original',row(changed,b)['focus']==row(other,b)['focus'] and row(changed,b)['focus']!=row(start,b)['focus'])
    code, result=edit(start,b,41,event=event)
    check('event replay returns its receipt and does not reapply',code==200 and result.get('duplicate') is True,result)
    code, result=edit(start,b,41,event=event+'different')
    check('a stale original basis is rejected',code==409,result)
    code, result=edit(start,b,42,event=event)
    check('a reused event identity cannot change meaning',code==409,result)
    before=(number(a),number(b)); current=frame()
    code, result=call('native/act',dict(subject=first,viewport=[],basis=current['basis'],key='/increment',parameters=[],arguments=[]),uuid.uuid4().hex)
    check('one native action changes multiple original subjects',code==200 and number(a)==before[0]+1 and number(b)==before[1]+1,result)
    current=frame()
    derived=next(o for o in current['occurrences'] if o['focus']['subject'].startswith('/o/') and o['slot']=='/value')
    check('computed result exposes its actual native overlay',derived['action'] is None,derived)
    code, result=call('native/act',dict(subject=first,viewport=[],basis=current['basis'],key=derived['key'],parameters=[],arguments=[dict(slot='/value',kind='natural',value='999')]),uuid.uuid4().hex)
    check('derived value has no invented inverse',code==422,result)
    check('native overlay recomputes the combined input result',number(derived['focus']['subject'])==before[0]+before[1]+2)
    code, result=call('native/frame',dict(subject=first,viewport=[]),principal='agent')
    check('ungranted principal cannot inherit administrator scope',code==403,result)
    # Measure ordinary acknowledged edits, excluding initial compilation and
    # deliberately failing calls. Each edit targets its just-captured basis.
    for i in range(5 + args.edits):
        code, result = edit(frame(),a,original[0] + i % 2)
        if code != 200:raise AssertionError(('repeated edit',code,result))
        timings[-1]['warm_edit'] = i >= 5
    warm = sorted(t['ms'] for t in timings if t.get('warm_edit'))
    if warm:
        check('warm native edit acknowledgement p95 below 150 ms',warm[math.ceil(.95*len(warm))-1]<150,
              {'count':len(warm),'p50_ms':warm[math.ceil(.5*len(warm))-1],'p95_ms':warm[math.ceil(.95*len(warm))-1],'max_ms':warm[-1]},fatal=False)
    for target,value in zip((a,b),original):check('restore original through native action: '+target,edit(frame(),target,value)[0]==200)
    for _ in range(20):frame()
    before_pins=pins()
    check('canonical pin file is measured',bool(before_pins),before_pins)
    sample_memory(0)
    interval=max(1,args.reads//100)
    for i in range(args.reads):
        frame()
        if (i+1)%interval==0 or i+1==args.reads:sample_memory(i+1)
    check('unchanged native reads do not grow pins.pack',pins()==before_pins,{'before':before_pins,'after':pins()})
    if memory:
        final_half=[m['charged'] for m in memory if m['read']>=args.reads//2]
        check('charged memory final-half range within 16 MiB',max(final_half)-min(final_half)<=16*2**20,
              {'reads':args.reads,'range_bytes':max(final_half)-min(final_half)},fatal=False)
        check('owned process tree remains below the aggregate guard',max(m['charged'] for m in memory)<args.memory_limit_mib*2**20,
              {'peak_bytes':max(m['charged'] for m in memory),'limit_bytes':args.memory_limit_mib*2**20},fatal=False)
finally:
    report=dict(results=results,timings=timings,memory=memory,
                coverage='Actual native compiler/owner and HTTP actions. Memory gate only at the recorded read count and owner tree. Browser interaction, compilation cycles, self-hosting and human usability are separate gates.')
    (world/'native-surface-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    actions=[t['ms'] for t in timings if t['operation']=='native/act' and t['status']==200]
    if actions:print('Native action milliseconds:',actions,flush=True)
if not all(item['passed'] for item in results):
    raise SystemExit(1)
