#!/usr/bin/env python3
"""Extract phase timings from the disposable construction instrumentation."""
import argparse
import json
import re
import statistics
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--log', type=Path, required=True)
p.add_argument('--measurement', type=Path, default=Path('artifacts/path-search-construction-profile.json'))
p.add_argument('--output', type=Path, default=Path('artifacts/path-search-construction-stages.json'))
a = p.parse_args()
measurement = json.loads(a.measurement.read_text())
started = int(measurement['build_started_unix'] * 1e9)
events = []
for match in re.finditer(r'\(0 "(PROFILE-[A-Z-]+)"(.*?)\b(\d{19})\)', a.log.read_text(errors='replace'), re.S):
    stamp = int(match[3])
    if stamp >= started:
        events.append({'event': match[1], 'timestamp_ns': stamp,
                       'arguments': match[2].strip()})
filings = [e for e in events if e['event'] == 'PROFILE-FILE']
def atoms(text):
    # PLAN's printer may show a natural as its printable little-endian bytes.
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\d+', text)
    return [int.from_bytes(json.loads(t).encode(), 'little') if t.startswith('"') else int(t) for t in tokens]

timings = [atoms(e['arguments'])[0]/1e6 for e in filings]
keys = [atoms(e['arguments'])[1] for e in filings]
phases = [e for e in events if e['event'] != 'PROFILE-FILE']
for i, event in enumerate(phases):
    event['since_request_ms'] = (event['timestamp_ns'] - started)/1e6
    event['since_previous_phase_ms'] = (event['timestamp_ns'] - (phases[i-1]['timestamp_ns'] if i else started))/1e6
out = {'measurement': str(a.measurement), 'log': str(a.log), 'phases': phases,
       'filing': {'sources': len(filings), 'total_ms': sum(timings),
                  'p50_ms': statistics.median(timings) if timings else None,
                  'max_ms': max(timings, default=None), 'emitted_keys': sum(keys),
                  'max_keys_per_source': max(keys, default=None)},
       'filing_samples': filings,
       'caveat': 'Instrumented phase-forced execution; timings include instrumentation overhead and are not an acceptance benchmark.'}
a.output.write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k != 'filing_samples'}, indent=2))
