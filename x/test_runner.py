"""Inventory-driven Reaver, Foil and doctest gate (stdlib Python only)."""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
# Print uses doubled quotes and doubled backslashes inside cords.
ATOM = r'("(?:[^"\\]|\\.|"")*"|[0-9]+)'
EVENT = re.compile(r'^\("TEST"\s+' + r'\s+'.join([ATOM] * 5) + r'\s*\)', re.M)
ERROR = re.compile(r'^\("ERROR"|Assertion .* failed|arena exhausted|deadlock', re.M)
DONE = '"TEST-RUN-DONE"'


def decode_atom(token):
    if token.startswith('"'):
        return token[1:-1].replace('""', '"').replace('\\\\', '\\')
    # PLAN cords are packed little-endian naturals. The printer chooses
    # decimal for some text (notably text containing quotes or newlines).
    value = int(token)
    return value.to_bytes((value.bit_length() + 7) // 8, 'little').decode('utf-8', 'replace')


def events(log):
    rows = [tuple(decode_atom(x) for x in m.groups()) for m in EVENT.finditer(log)]
    return [r[:2] + tuple(x[2:] if x.startswith('~:') else x for x in r[2:]) for r in rows]


def verdict(log, returncode, completed=True):
    records = events(log)
    faults = [r for r in records if r[0] not in ('start', 'pass')]
    well_formed = len(records) == len(re.findall(r'^\("TEST"', log, re.M))
    finished = [r for r in records if r[0] != 'start']
    all_finished = all(any(end[1] == start[1] and
                           (end[2] == start[2] or end[2].startswith(start[2] + '/'))
                           for end in finished) for start in records if start[0] == 'start')
    done = re.search(r'^' + re.escape(DONE) + r'$', log, re.M)
    good = bool(all_finished and well_formed and completed and returncode == 0
                and done and not ERROR.search(log) and not faults)
    return good, records


def report_log(path):
    """Keep protocol records and failure context, skipping rendered state.

    The runtime indents continuation lines of top-level records. Preserve
    every TEST header, including malformed ones, so verdict stays closed
    on missing or invalid results. Full output remains in out.log.
    """
    output = []
    record = False
    context = 0
    with path.open(errors='replace') as source:
        for line in source:
            if line.startswith('("TEST"'):
                record = True
            elif record and line and not line[0].isspace():
                record = False
            if ERROR.search(line):
                context = 1200
            if record or line.rstrip('\n') == DONE or line.startswith('"FETCH-ORDER-'):
                output.append(line)
            elif context:
                output.append(line[:context])
            context = max(0, context - len(line))
    return ''.join(output)


def reaver_closure(mods):
    seen = set()
    pending = list(mods)
    while pending:
        mod = pending.pop()
        if mod in seen:
            continue
        seen.add(mod)
        path = ROOT / 'src/reaver' / (mod + '.rvr')
        if path.exists():
            pending.extend(re.findall(r'\(#module ([\w-]+)\)', path.read_text()))
    return seen


def needs_corpus(mod):
    return 'foil-stage' in reaver_closure([mod])


def compiler_files():
    # Test sources are loaded in disposable workers, never into this key.
    mods = reaver_closure(['foil-new-env', 'std', 'quip'])
    return [ROOT / 'src/reaver' / (m + '.rvr') for m in mods
            if (ROOT / 'src/reaver' / (m + '.rvr')).exists()]


def inventory():
    data = json.loads((ROOT / 'test-inventory.json').read_text())
    native_excluded = data.get('native_excluded', {})
    for mod in native_excluded:
        if not (ROOT / 'src/foil' / (mod + '.foil')).is_file():
            raise ValueError('missing native fixture: ' + mod)
    suites = []
    registered = set()
    for group in data['groups']:
        for mod in group['modules']:
            if mod in registered:
                raise ValueError('duplicate suite: ' + mod)
            registered.add(mod)
            suites.append(dict(name=mod, kind='reaver', target=mod,
                               group=group['name'], fast=group['fast'],
                               timeout=group['timeout'], category=group['category'],
                               enabled=group.get('enabled', True),
                               reason=group.get('reason', 'Explicit selection only.')))
    for mod, reason in data['excluded'].items():
        if mod in registered:
            raise ValueError('registered and excluded: ' + mod)
        suites.append(dict(name=mod, kind='reaver', target=mod, group=mod,
                           fast=False, timeout=900, category='manual', enabled=False, reason=reason))
    known = registered | data['excluded'].keys()
    found = {p.stem for p in (ROOT / 'src/reaver').glob('*.rvr')
             if p.stem.endswith('-tests') or p.stem.startswith('test-')}
    if found != known:
        raise ValueError(f'inventory drift: unclassified={sorted(found-known)}, missing={sorted(known-found)}')
    for path in sorted((ROOT / 'src/foil').rglob('*.foil')):
        mod = path.relative_to(ROOT / 'src/foil').with_suffix('').as_posix()
        if mod.startswith('tests/') or (mod.startswith('apps/') and path.stem == 'tests'):
            suites.append(dict(name='foil:' + mod, kind='native', target=mod,
                               group='native', fast=mod not in native_excluded, timeout=900, category='foil',
                               enabled=mod not in native_excluded, reason=native_excluded.get(mod, '')))
        if re.search(r"^\s*'\s*\?=", path.read_text(), re.M):
            suites.append(dict(name='doc:' + mod, kind='docs', target=mod,
                               group='doctests', fast=True, timeout=900, category='docs', enabled=True))
    for command in data['commands']:
        suites.append(dict(command, kind='command', group=command['name'], enabled=True))
    return suites


def run_process(command, directory, source, timeout, env=None, cwd=None):
    """Own the whole process group so timeouts also stop actor/child processes."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'input').write_text(source)
    started = time.monotonic()
    with (directory / 'out.log').open('w') as out:
        with subprocess.Popen(command, cwd=cwd or directory, stdin=subprocess.PIPE,
                              stdout=out, stderr=out, text=True, start_new_session=True,
                              env=env) as proc:
            completed = True
            try:
                proc.communicate(source, timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                completed = False
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
            code = proc.returncode
    return code, completed, time.monotonic() - started


def digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def copy_snapshot(source, dest):
    dest.mkdir(parents=True)
    for name in ('data.mdb', 'pins.pack'):
        shutil.copy2(source / name, dest / name)


def compiler_key(wisp):
    inputs = [*compiler_files(), *(ROOT / 'src/plan').glob('*.plan'),
              Path(wisp), ROOT / 'x/stage-lib']
    return 'compiler-new-env-v1-' + digest(inputs)


def stage(wisp, fresh, timeout):
    cache = ROOT / '.check'
    cache.mkdir(exist_ok=True)
    # A runtime change invalidates boot just like PLAN changes do.
    planhash = digest([* (ROOT / 'src/plan').glob('*.plan'), Path(wisp), ROOT / 'x/stage-lib'])
    key = compiler_key(wisp)
    template = cache / ('template-' + key)
    with (cache / 'stage.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (template / 'ready').exists() and not fresh:
            return template
        directory = Path(tempfile.mkdtemp(prefix='stage-', dir=cache))
        print(f'Staging {key}: {directory}', flush=True)
        boot_files = [ROOT / 'src/reaver' / (m + '.rvr')
                      for m in reaver_closure(['std', 'quip', 'rex'])
                      if (ROOT / 'src/reaver' / (m + '.rvr')).exists()]
        boot = cache / ('boot-' + planhash + '-' + digest(boot_files))
        if boot.exists() and not fresh:
            copy_snapshot(boot, directory / 'snap')
        else:
            env = dict(os.environ, WISP=wisp, TEST_ROOT=str(ROOT))
            code, complete, _ = run_process(
                ['sh', '-ec', '. "$TEST_ROOT/x/stage-lib"; stage_repl "$WISP" "$TEST_ROOT"'],
                directory, '', timeout, env)
            log = (directory / 'out.log').read_text(errors='replace')
            if code or not complete or ERROR.search(log):
                raise RuntimeError(f'boot failed (exit={code}, completed={complete}): {directory}/out.log')
            (directory / 'out.log').rename(directory / 'boot.log')
            if boot.exists():
                shutil.rmtree(boot)
            copy_snapshot(directory / 'snap', boot)
        module = 'foil-new-env'
        source = f'(#bind stage (#module {module}))\n(print "TEST-RUN-DONE")\n'
        code, complete, _ = run_process([wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
                                        directory, source, timeout)
        log = (directory / 'out.log').read_text(errors='replace')
        if not verdict(log, code, complete)[0]:
            raise RuntimeError(f'staging failed: {directory}/out.log')
        if key != compiler_key(wisp):
            raise RuntimeError('Compiler inputs changed during staging; rerun tests')
        # Never expose a half-built template to a reader.
        prepared = directory / 'snap'
        (prepared / 'planhash').write_text(planhash)
        (prepared / 'ready').write_text(key)
        if template.exists():
            shutil.rmtree(template)
        prepared.rename(template)
    return template


def rvr_string(value):
    # CLI selections are resolved through the inventory, never raw code.
    return '"' + value.replace('\\', '\\\\').replace('"', '""') + '"'


def copy_template(source, dest):
    # Workers copy the immutable compiler template under its publication lock.
    if source.name.startswith('template-'):
        with (ROOT / '.check/stage.lock').open('r') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            copy_snapshot(source, dest)
    else:
        copy_snapshot(source, dest)


def run_group(suites, wisp, template, root, timeout):
    directory = root / suites[0]['group']
    copy_template(template, directory / 'snap')
    command_suite = suites[0]['kind'] == 'command'
    if command_suite:
        env = dict(os.environ, WISP=wisp, TEST_TEMPLATE=str(template),
                   TEST_RUN_DIR=str(directory), PATH=str(Path(wisp).parent) + os.pathsep + os.environ.get('PATH', ''))
        code, complete, seconds = run_process([sys.executable, str(ROOT / suites[0]['target'])],
                                               directory, '', timeout, env)
        log = (directory / 'out.log').read_text(errors='replace')
        good = bool(code == 0 and complete and not ERROR.search(log)
                    and re.search(suites[0]['completion'], log, re.M))
        records = []
    else:
        lines = []
        if any(s['kind'] != 'reaver' for s in suites):
            lines.append('(#bind runner (#module foil-test-runner))')
            mods = '[' + ' '.join(rvr_string(s['target']) for s in suites) + ']'
            lines.append(f'(runner:run 0 {rvr_string(suites[0]["kind"])} {mods})')
        for suite in suites:
            mod = rvr_string(suite['target'])
            if suite['kind'] == 'reaver':
                lines += [f'(print ("TEST" "start" {mod} "~:module" "~:" "~:"))',
                          f'(#bind {suite["target"]} (#module {suite["target"]}))',
                          f'(print ("TEST" "pass" {mod} "~:module" "~:" "~:"))']
        lines.append('(print "TEST-RUN-DONE")')
        code, complete, seconds = run_process([wisp, '--file-root', str(ROOT / 'src'), 'snap', 'root', '_'],
                                               directory, '\n'.join(lines) + '\n', timeout)
        log = report_log(directory / 'out.log')
        good, records = verdict(log, code, complete)
        # A legacy module may return control after a failed top-level form.
        # Attribute the uncaught error to that module, not a false PASS.
        matches = list(EVENT.finditer(log))
        for suite in suites:
            if suite['kind'] != 'reaver':
                continue
            start = None
            for i, record in enumerate(records):
                if record[1] != suite['target']:
                    continue
                if record[0] == 'start' and start is None:
                    start = matches[i].end()
                elif record[0] == 'pass' and start is not None:
                    error = ERROR.search(log, start, matches[i].start())
                    if error:
                        records[i] = ('error', record[1], record[2], 'passing module',
                                      log[error.start():error.start()+800])
        # A completely missing adapter output must never look green.
        good &= all(any(r[1] == s['target'] and r[0] != 'start' for r in records) for s in suites)
    # The REPL echoes a top-level print's result; nested prints do not.
    records = [r for i, r in enumerate(records) if i == 0 or r != records[i-1]]
    for suite in suites:
        if suite['kind'] == 'docs':
            path = ROOT / 'src/foil' / (suite['target'] + '.foil')
            expected = len(re.findall(r"^\s*'\s*\?=", path.read_text(), re.M))
            actual = sum(r[1] == suite['target'] and r[0] != 'start' for r in records)
            if expected != actual:
                good = False
                print(f'  {suite["name"]}: expected {expected} example results, got {actual}', flush=True)
    if not good and not any(r[0] not in ('start', 'pass') for r in records):
        error = ERROR.search(log)
        detail = log[error.start():error.start()+1200] if error else ('timeout' if not complete else 'missing results/completion or process failure')
        print('  ' + detail, flush=True)
    locations = {}
    for suite in suites:
        path = ROOT / 'src/foil' / (suite['target'] + '.foil')
        if suite['kind'] != 'docs':
            continue
        by_text = {}
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.match(r"^\s*'\s*\?=", line):
                by_text.setdefault(line.lstrip().removeprefix("'").strip(), []).append(number)
        for _, mod, name, _, _ in records:
            key = mod + ':' + name
            text = name.partition(': ')[2]
            if mod == suite['target'] and key not in locations and by_text.get(text):
                locations[key] = str(path) + ':' + str(by_text[text].pop(0))
    result = dict(group=suites[0]['group'], passed=bool(good), seconds=round(seconds, 3),
                  completed=complete, returncode=code, suites=[s['name'] for s in suites],
                  records=records, locations=locations, log=str(directory / 'out.log'))
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'{"PASS" if good else "FAIL"} {result["group"]} ({seconds:.1f}s) — {result["log"]}', flush=True)
    for status, mod, name, want, got in records:
        if status not in ('start', 'pass'):
            location = locations.get(mod + ':' + name, mod)
            print(f'  {status}: {location} {name}\n    expected: {want}\n    actual:   {got}', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suites', nargs='*', help='suite names, group names, foil, or doctests')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--fast', action='store_true')
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--timeout', type=float, help='override group/staging timeout in seconds')
    args = parser.parse_args()
    if args.jobs < 1 or args.timeout is not None and args.timeout <= 0:
        parser.error('jobs and timeout must be positive')
    suites = inventory()
    if args.list:
        for s in suites:
            print(f'{s["name"]:40} {s["group"]:14} {s["category"]:13} '
                  + ('default' if s['enabled'] else 'excluded: ' + s['reason']))
        return 0
    selected = []
    if args.suites:
        for choice in args.suites:
            matches = [s for s in suites if choice in (s['name'], s['group'])
                       or choice == 'foil' and s['kind'] == 'native']
            if not matches:
                parser.error('unknown suite/group: ' + choice)
            selected.extend(s for s in matches if s not in selected)
    else:
        selected = [s for s in suites if s['enabled'] and (s['fast'] or not args.fast)]
    wisp = os.environ.get('WISP') or shutil.which('wisp') or str(ROOT / 'wisp')
    wisp = str(Path(wisp).resolve())
    if not os.access(wisp, os.X_OK):
        parser.error('wisp unavailable; enter the dev shell or set WISP=/path/to/wisp')
    (ROOT / '.check').mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='run-', dir=ROOT / '.check'))
    started = time.monotonic()
    compiler = stage(wisp, args.fresh, args.timeout or 900)
    phases = {'compiler_seconds': round(time.monotonic() - started, 3)}
    (root / 'phases.json').write_text(json.dumps(phases, indent=2) + '\n')
    print('Setup: ' + json.dumps(phases), flush=True)
    print('Results: ' + str(root), flush=True)
    groups = {}
    for s in selected:
        groups.setdefault(s['group'], []).append(s)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_group, ss, wisp,
                               compiler, root,
                               args.timeout or max(s['timeout'] for s in ss)) for ss in groups.values()]
        results = [f.result() for f in futures]
    (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return int(not all(r['passed'] for r in results))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as e:
        sys.exit(str(e))
