#!/usr/bin/env python3
"""Summarize recorded search measurements without treating missing gates as passes."""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--artifacts', type=Path, default=Path('artifacts'))
p.add_argument('--output', type=Path, default=Path('artifacts/path-search-results.md'))
a = p.parse_args()


def read(name):
    path = a.artifacts / name
    return json.loads(path.read_text()) if path.exists() else None


baseline = read('path-search-baseline.json')
indexed_raw = next((name for name in (
    'path-search-prefix-only.json', 'path-search-indexed-ice.json', 'path-search-indexed-final.json', 'path-search-indexed-delete.json', 'path-search-indexed-prefix.json',
    'path-search-indexed.json') if (a.artifacts / name).exists()),
    'path-search-indexed.json')
indexed = read(indexed_raw)
native = read('path-search-native.json')
lines = ['# Namespace search measurements', '']
http_gate = (indexed or {}).get('http_acceptance', {})
http_status = ('PASS' if http_gate.get('passed') else 'FAIL') if http_gate.get('evaluated') else 'NOT EVALUATED'
native_status = ('PASS' if native['p95_ms'] <= 300 else 'FAIL') if native and len(native.get('samples_ms', [])) >= 100 and native.get('http_measurement') == indexed_raw else 'NOT EVALUATED'
lines += [f'- 10,000-record HTTP gate (each class p95 ≤100 ms): **{http_status}**.',
          f'- Native gate (100 samples, p95 ≤300 ms including debounce): **{native_status}**.',
          '- Functional checks and diagnostic microbenchmarks do not satisfy either performance gate.', '']
for name, label in [('idx-ice-regressions.json', 'Kernel/index, namespace, publication, supervisor and source-mount regressions'),
                    ('idx-posting-map.json', 'Posting deletion order, values and balance'),
                    ('idx-reference-after.json', 'Reference comparison oracle'),
                    ('idx-header-counts.json', 'Index header/count oracle'),
                    ('idx-ice-profile.json', 'Stored-pin state identity, search and subsequent updates'),
                    ('path-search-prefix-only-oracle.json', 'Prefix-only search oracle and pagination')]:
    result = read(name)
    if result:
        count = sum(record[0] == 'pass' for record in result.get('records', []))
        lines.append(f'- {label}: {"PASS" if result["passed"] else "FAIL"}, {count} checks ([raw]({name})).')
native_log = next((name for name in ('idx-prefix-only-native.log', 'idx-ice-native.log', 'idx-final-native.log', 'idx-delete-native.log', 'idx-prefix-native.log')
                   if (a.artifacts / name).exists()), None)
if native_log:
    contents = (a.artifacts / native_log).read_text()
    status = 'FAIL' if 'FAILED' in contents else ('PASS' if contents.count('test result: ok') >= 2 else 'INCOMPLETE')
    caveat = ' (preceding host/query implementation)' if native_log != 'idx-prefix-only-native.log' else ''
    lines.append(f'- Native agent/reflection regressions: **{status}**{caveat} ([log]({native_log})).')
for name, label, marker in [
    ('idx-final-agent-loop.log', 'Agent loop, pending grants and failure boundaries', 'PASS codec, secret exclusion'),
    ('idx-final-paths.log', 'Live chooser protocol, care and draft retention', 'test result: ok. 3 passed'),
]:
    path = a.artifacts / name
    if path.exists():
        contents = path.read_text()
        status = 'PASS' if marker in contents else 'INCOMPLETE / FAILED'
        lines.append(f'- {label}: **{status}** (preceding implementation; not a final prefix-only acceptance run) ([log]({name})).')
prefix_paths = a.artifacts / 'idx-prefix-only-paths.log'
if prefix_paths.exists():
    status = 'PASS' if 'test result: ok. 3 passed' in prefix_paths.read_text() else 'INCOMPLETE / FAILED'
    lines.append(f'- Live prefix chooser protocol, care and draft retention: **{status}** (short-prefix prototype, before parent-scoped postings) ([log]({prefix_paths.name})).')
if indexed and indexed.get('stop_reason'):
    lines += ['', indexed['stop_reason']]
if indexed and indexed.get('source_caveat'):
    lines += ['', indexed['source_caveat']]
previous = read('path-search-indexed-final.json')
previous_native = read('path-search-native-before-ice.json')
if indexed_raw != 'path-search-indexed-final.json' and previous and previous_native:
    old = next((row for row in previous['sizes'] if row['records'] == 10000), None)
    if old and old.get('queries'):
        worst = max(value.get('p95_ms', 0) for value in old['queries'].values())
        lines += ['', f'The preceding implementation failed both 10,000-record gates: worst HTTP class p95 {worst:.2f} ms; native p95 {previous_native["p95_ms"]:.2f} ms. Those measurements remain in [HTTP raw data](path-search-indexed-final.json) and [native raw data](path-search-native-before-ice.json). A new run does not erase those failures.']
lines += ['', 'The current workload uses title/path prefixes only. Interior substring and fuzzy queries are verified misses; the common and Unicode queries are prefixes. Older full-matching measurements are historical evidence, not an identical semantic workload.']
lines += ['', 'Corpus sizes below count seeded records. Structural folders and the fixed application/system namespace are additional; the 10,000-record gate therefore exercises more than 10,000 searchable paths.', '']
for report, label, raw in [(baseline, 'Former scan', 'path-search-baseline.json'),
                           (indexed, 'Indexed', indexed_raw)]:
    lines += [f'## {label}', '']
    if not report:
        lines += ['No full measurement artifact yet.', '']
        continue
    lines += [f'Machine: {report.get("cpu", "unrecorded")}; {report.get("machine", "unrecorded")}. Corpus seed: {report["seed"]}. [Raw samples]({raw}).', '',
              '| Seeded records | Query | Samples | p50 ms | p95 ms | Maximum ms | Status |',
              '| ---: | --- | ---: | ---: | ---: | ---: | --- |']
    for size in report['sizes']:
        for kind, data in size['queries'].items():
            def number(key):
                return f'{data[key]:.2f}' if key in data else '—'
            status = data.get('error') or ('complete' if data.get('complete') else 'incomplete')
            lines.append(f'| {size["records"]:,} | {kind} | {len(data.get("samples_ms", []))} | {number("p50_ms")} | {number("p95_ms")} | {number("max_ms")} | {status.replace(chr(10), " ").replace("|", "/")} |')
    lines.append('')
    if report.get('baseline_class_seconds'):
        lines.append(f'The user-authorized old-scan budget is {report["baseline_class_seconds"]:g} seconds per query class. Capped classes are incomplete observations, not 100-sample results. Indexed budgets and acceptance gates are unchanged.')
    if 'startup' in report:
        startup = report['startup']
        if report.get('startup_timing_valid'):
            lines.append('Initial index construction: ' + ', '.join(
                f'{scope} {startup[scope + "_ms"] / 1000:.2f} s'
                for scope in ('local', 'system') if scope + '_ms' in startup) + '.')
        else:
            lines.append('Startup timing **excluded**: sleep/clock continuity was not verified. Raw timestamps remain in the JSON.')
    lines += ['', '| Seeded records | Preparation | Seed ms | Rebuild ms | Index counts |',
              '| ---: | --- | ---: | ---: | --- |']
    for size in report['sizes']:
        seed_ms=sum(size.get('unindexed_seed_batches_ms',size.get('seed_batches_ms',[])))
        rebuild=size.get('bulk_index_rebuild_ms')
        rebuild_text=f'{rebuild:.2f}' if rebuild is not None else '—'
        lines.append(f'| {size["records"]:,} | {size.get("seed_method","incremental")} | {seed_ms:.2f} | {rebuild_text} | `{json.dumps(size.get("index_size", "not measured"))}` |')
    lines += ['', '| Seeded records | Operation | Enabled p50 / p95 ms | Disabled p50 / p95 ms |',
              '| ---: | --- | ---: | ---: |']
    for size in report['sizes']:
        enabled = size.get('commits_enabled', {}).get('summary', {})
        disabled = size.get('commits_disabled', {}).get('summary', {})
        for operation, timing in enabled.items():
            control = disabled.get(operation)
            cell = f'{control["p50_ms"]:.2f} / {control["p95_ms"]:.2f}' if control else '—'
            lines.append(f'| {size["records"]:,} | {operation} | {timing["p50_ms"]:.2f} / {timing["p95_ms"]:.2f} | {cell} |')
    lines += ['', 'Raw JSON also retains first-query latency, maximum latency, response sizes, work counters, continuation samples and individual commit measurements. Seed costs cover only records added at that step. Bulk-rebuild preparation seeds with the search index disabled and then builds it once; it is not an indexed commit-cost measurement.', '']
if native:
    lines += ['## Native', '', f'Recorded run: `{native.get("run", "unlabeled")}`. p95: **{native["p95_ms"]:.2f} ms**; maximum: {native["max_ms"]:.2f} ms. [Raw samples](path-search-native.json).', '']
lines += ['## Limits and provenance', '',
          '- Baseline samples collected during earlier index-build experiments experienced background load. They establish observed latency, not an isolated causal speedup ratio.',
          '- The user confirmed that the computer slept during earlier builds. Their wall-clock startup durations are excluded from startup performance conclusions; [interrupted-run record](path-search-build-failure.json).',
          '- Filing-only microbenchmarks exclude HTTP, eligibility and native rendering. They are diagnostic measurements.',
          '- The final 1,000-record diagnostic separates request stages: [raw stage timings](path-search-request-profile.json). A two-second CPU sample during corpus seeding includes substantial copying-collector work; it does not establish the cause of query pauses: [runtime sample](path-search-seed-process-sample.txt).',
          '- Live Japanese IME testing remains the separately agreed manual check.',
          '- The legacy `foil-lain-tests` harness also fails on the frozen pre-port checkout; [pre-port result](idx-preport-lain.json).',
          '- [Source/patch fingerprints](path-search-revisions.json) identify the implementation. Each full HTTP run can additionally record the actual disposable source snapshot with `--source-root`.', '']
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text('\n'.join(lines))
print(a.output)
