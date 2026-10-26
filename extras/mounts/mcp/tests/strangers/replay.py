"""Replay the saved world's records into a fresh world through MCP writes, references live (case 0).
python3 replay.py http://127.0.0.1:8330 before-0x11.json [before-0x12.json ...]"""
import sys, os, json, re, time
sys.path.insert(0, '/Users/ianchanner/shrine-cells/extras/mounts/mcp/tests/strangers')
os.environ['STRANGERS_BASE'] = sys.argv[1]
from world import W
REF = re.compile(r'^/h/([xyz])/\d+/(\d+)(/.*)$')
records = {}
for f in sys.argv[2:]:
    for p, v in json.load(open(f)).items():
        records[p] = v.get('props') or {}
def slot(v):
    m = REF.match(v) if isinstance(v, str) else None
    return {'type': 'reference', 'value': '/h/%s/0/%s%s' % (m.group(1), m.group(2), m.group(3))} if m else v
paths = sorted(records, key=lambda p: (p.count('/'), p))
batch, done, skipped, failed, t0 = [], 0, 0, [], time.time()
def flush():
    global batch, done
    if not batch: return
    try:
        W.tool('write', records=batch, who='replay'); done += len(batch)
    except Exception as e:
        for r in batch:          # one at a time, so one bad record does not lose its batch
            try: W.tool('write', records=[r], who='replay'); done += 1
            except Exception as e2: failed.append((r['path'], str(e2)[:160]))
    batch = []
for p in paths:
    slots = {k.lstrip('/'): slot(v) for k, v in records[p].items() if not k.lstrip('/').startswith('sys')}
    batch.append({'path': p, 'slots': slots})   # a slotless record is still a record: a folder, a thing named and empty
    if len(batch) >= 100:
        flush()
        if done % 1000 < 100: print(done, 'written', round(time.time() - t0), 's', flush=True)
flush()
print('written', done, 'skipped (no slots)', skipped, 'failed', len(failed), 'in', round(time.time() - t0), 's')
for p, e in failed[:20]: print('  FAIL', p, e)
json.dump(failed, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'replay-failed.json'), 'w'))
