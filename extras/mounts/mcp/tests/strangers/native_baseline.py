"""Read-only graph fixtures and latency samples for a native-view migration.

Unlike proofs.py this never writes to the world. Output is an explicit file.
Run against the same quiescent dataset and runtime for before/after comparisons.
"""
import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from world import W, idx


SUBJECTS = (
    '/0x11/user/orgs/verisk',
    '/0x11/user/orgs/mckenzie_intelligence_services',
    '/0x11/0x12/user',
)


def capture(samples, warmup=0, graph_base=None):
    outputs, timings = {}, {}
    operations = {}
    for subject in SUBJECTS:
        for route in ('links', 'around', 'unfold', 'union'):
            query = '/' + route + '?' + urllib.parse.urlencode(
                {'to' if route == 'links' else 'at': subject, 'depth': 3})
            operations[query] = (lambda q=query: json.load(urllib.request.urlopen(graph_base.rstrip('/') + q, timeout=60))) if graph_base else (lambda q=query: idx(q))
        operations['record:' + subject] = lambda p=subject: W.read(p, 'x')
    for name, read in operations.items():
        first = time.perf_counter_ns()
        outputs[name] = read()
        cold_ms = (time.perf_counter_ns() - first) / 1_000_000
        for _ in range(warmup):
            read()
        values = []
        for _ in range(samples):
            start = time.perf_counter_ns()
            read()
            values.append((time.perf_counter_ns() - start) / 1_000_000)
        ordered = sorted(values)
        timings[name] = {
            'first_read_ms': cold_ms,
            'samples_ms': values,
            'p50_ms': statistics.median(values),
            'p95_ms': ordered[max(0, int(len(ordered) * .95) - 1)],
            'max_ms': max(values),
        }
        print(name, 'p50', round(timings[name]['p50_ms'], 3),
              'p95', round(timings[name]['p95_ms'], 3), flush=True)
    return {'subjects': SUBJECTS, 'samples': samples, 'warmup': warmup,
            'captured_at': datetime.now(timezone.utc).isoformat(), 'graph_base': graph_base,
            'cold_note': 'First request in this capture; only a fresh runtime guarantees a cold cache.',
            'outputs': outputs, 'timings': timings}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--warmup', type=int, default=0)
    parser.add_argument('--graph-base', help='Native graph URL, for example http://127.0.0.1:8330/graph')
    args = parser.parse_args()
    if args.samples < 2:
        parser.error('at least two samples are required')
    result = capture(args.samples, args.warmup, args.graph_base)
    with open(args.output, 'w') as file:
        json.dump(result, file, indent=2)
