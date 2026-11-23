#!/usr/bin/env python3
"""Stage a disposable, instrumented Reaver; never edit the integrated kernel.

Run run-chat-server.py with the printed checkout and --without-search-index,
then POST path_bench / path_index_enable to /shuin-test. PROFILE events are
nanosecond timestamps. Filing events include elapsed ns and emitted-key count.
Deep forcing at phase boundaries makes lazy work attributable; this is a
diagnostic build, not an acceptance benchmark.
"""
import argparse
import hashlib
import json
import platform
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path


def replace(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Instrumentation anchor is not unique: {old[:100]!r}')
    return text.replace(old, new)


def stage(source, destination):
    destination.mkdir()
    for entry in source.iterdir():
        if entry.name in ('.git', '.check'):
            continue
        if entry.name in ('src', 'x'):
            shutil.copytree(entry, destination / entry.name, symlinks=True)
        elif entry.is_file():
            shutil.copy2(entry, destination / entry.name)
        else:
            (destination / entry.name).symlink_to(entry)
    path = destination / 'src/foil/idx.foil'
    original = path.read_text()
    text = replace(original,
        '    = existing\n        | (idx/live r.at after).tap.fold',
        '    ; (Trace ["PROFILE-REBUILD-START" r.at (Now 0)] 0)\n'
        '    = existing\n        | (idx/live r.at after).tap.fold')
    text = replace(text,
        '    ? (and r.fresh (gt existing.wyt 0))',
        '    ; (DeepSeq[nat] existing 0)\n'
        '    ; (Trace ["PROFILE-EXISTING-END" existing.wyt (Now 0)] 0)\n'
        '    ? (and r.fresh (gt existing.wyt 0))')
    text = replace(text,
        '        = empty=mop[path myth lt_pith] (mop/empty)',
        '        ; (DeepSeq[nat] sources 0)\n'
        '        ; (Trace ["PROFILE-SOURCES-END" sources.wyt (Now 0)] 0)\n'
        '        = empty=mop[path myth lt_pith] (mop/empty)')
    text = replace(text,
        '          | (idx/file wanted.wing name record).tap.fold acc',
        '          = ;started (Now 0)\n'
        '            filed (idx/file wanted.wing name record)\n'
        '          ; (DeepSeq[nat] filed 0)\n'
        '          = ;ended (Now 0)\n'
        '          ; (Trace ["PROFILE-FILE" (sub ended started) filed.size name.len (Now 0)] 0)\n'
        '          | filed.tap.fold acc')
    text = replace(text,
        '    = made\n        | desired.tap.fold out',
        '    ; (DeepSeq[nat] desired 0)\n'
        '    ; (Trace ["PROFILE-TRANSPOSE-END" desired.size (Now 0)] 0)\n'
        '    = made\n        | desired.tap.fold out')
    text = replace(text,
        '    | ./ok\n    | existing.tap.fold made',
        '    ; (DeepSeq[nat] made 0)\n'
        '    ; (Trace ["PROFILE-NOTES-END" made.wyt (Now 0)] 0)\n'
        '    | ./ok\n    | existing.tap.fold made')
    path.write_text(text)
    path = destination / 'src/foil/namespace.foil'
    namespace_original = path.read_text()
    text = replace(namespace_original,
        '    ? !(diffs.tap.all((\\ [name change] state.permitted(name))))',
        '    = profiling (diffs.has([state.self \'idx \'path_search]))\n'
        '    ; (? profiling (Trace ["PROFILE-STEP-START" (Now 0)] 0) 0)\n'
        '    ? !(diffs.tap.all((\\ [name change] state.permitted(name))))')
    text = replace(text,
        '       = [raw next changes] staged',
        '       = [raw next changes] staged\n'
        '       ; (? profiling (DeepSeq[nat] staged 0) 0)\n'
        '       ; (? profiling (Trace ["PROFILE-TRIAL-END" (Now 0)] 0) 0)')
    text = replace(text,
        '          = address=path [state.self \'log ($u next.top)]',
        '          ; (? profiling (DeepSeq[nat] derived 0) 0)\n'
        '          ; (? profiling (Trace ["PROFILE-SETTLE-END" derived.wyt (Now 0)] 0) 0)\n'
        '          = address=path [state.self \'log ($u next.top)]')
    text = replace(text,
        '          ? (sov/step complete now block state.local)',
        '          ; (? profiling (DeepSeq[nat] complete 0) 0)\n'
        '          ; (? profiling (Trace ["PROFILE-MERGE-END" complete.wyt (Now 0)] 0) 0)\n'
        '          ? (sov/step complete now block state.local)')
    text = replace(text,
        '             = [committed signs] result',
        '             = [committed signs] result\n'
        '             ; (? profiling (DeepSeq[nat] result 0) 0)\n'
        '             ; (? profiling (Trace ["PROFILE-COMMIT-END" (Now 0)] 0) 0)')
    path.write_text(text)
    manifest = {
        'source': str(source), 'staged': str(destination),
        'source_hashes': {
            'idx.foil': hashlib.sha256(original.encode()).hexdigest(),
            'namespace.foil': hashlib.sha256(namespace_original.encode()).hexdigest(),
        },
        'caveat': 'Phase forcing and per-source traces add overhead; diagnostic only.',
    }
    (destination / 'construction-profile.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return destination


def measure(server, output, records):
    result = {'server': server, 'seeded_records': records,
              'purpose': 'instrumented construction profile, not acceptance',
              'machine': platform.platform(),
              'source_sha256': hashlib.sha256((Path(__file__).resolve().parent.parent/'mounts/shuin-chat/namespace_search.foil').read_bytes()).hexdigest()}

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2)+'\n')

    def request(fields, timeout=900):
        start, wall = time.monotonic(), time.time()
        with urllib.request.urlopen(server+'/shuin-test', json.dumps(fields).encode(), timeout=timeout) as response:
            body = response.read().decode()
        return {'elapsed_ms': (time.monotonic()-start)*1000,
                'wall_ms': (time.time()-wall)*1000, 'response': body}

    try:
        deadline = time.monotonic()+300
        while True:
            try:
                request({'operation': 'path_form'}, timeout=3)
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        result['initial_index'] = request({'operation': 'path_index_state'})
        if json.loads(result['initial_index']['response'])['records']:
            raise RuntimeError('Use a fresh disposable world started with --without-search-index; refusing to time an already-built index.')
        result['seed'] = request({'operation': 'path_bench', 'start': '0', 'count': str(records), 'mode': 'seed'})
        result['build_started_unix'] = time.time()
        result['phase'] = 'construction'
        save()
        result['build'] = request({'operation': 'path_index_enable'})
        save()
        result['counts'] = request({'operation': 'path_index_state'})
        result['phase'] = 'complete'
        save()
    except BaseException as error:
        result['error'] = repr(error)
        result['phase'] = 'incomplete'
        save()
        raise
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reaver', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--server', help='Measure an already running disposable instrumented world instead of staging')
    parser.add_argument('--records', type=int, default=100)
    args = parser.parse_args()
    if args.server:
        measure(args.server, args.output or Path('artifacts/path-search-construction-profile.json'), args.records)
    else:
        if args.reaver is None:
            parser.error('--reaver is required when staging')
        parent = Path(tempfile.mkdtemp(prefix='shuin-construction-profile-')) if args.output is None else args.output.parent
        print(stage(args.reaver.resolve(), args.output or parent / 'reaver'))
