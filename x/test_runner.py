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
import tarfile
import gzip
import stat
from eden_runtime import require_disk_space, check_world_storage, MemoryBudget, atomic_json

ROOT = Path(__file__).resolve().parent.parent


def source_inventory(source):
    """Exact replay inputs; no links, special files or durable runtime stores."""
    records = {}
    for path in sorted(source.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('Linked test source cannot be compacted')
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and not stat.S_ISREG(info.st_mode):
            raise ValueError('Special test source cannot be compacted')
        relative = path.relative_to(source).as_posix()
        records[relative] = dict(kind='directory' if directory else 'file',
                                sha256=None if directory else hashlib.sha256(path.read_bytes()).hexdigest(),
                                bytes=0 if directory else info.st_size, mode=stat.S_IMODE(info.st_mode),
                                mtime_ns=info.st_mtime_ns)
    return records


def completed_run(directory, cache=None):
    cache = (cache or check_root()).resolve()
    directory = Path(directory)
    if directory.is_symlink() or directory.resolve().parent != cache or not directory.name.startswith('run-'):
        raise ValueError('Expected a direct disposable run beneath the check cache')
    if (directory / 'world.json').exists() or not (directory / 'results.json').is_file():
        raise ValueError('Only completed disposable test runs may compact sources')
    results = json.loads((directory / 'results.json').read_text())
    if not isinstance(results, list) or not results:
        raise ValueError('Completed group results required')
    return directory.resolve()


def verify_source_archive(archive, files):
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        if len(members) != len(files) or {m.name for m in members} != set(files):
            raise ValueError('Source archive membership mismatch')
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe source archive member')
            expected = files[member.name]
            if expected['kind'] == 'directory':
                if not member.isdir():
                    raise ValueError('Source directory type mismatch')
                continue
            if not member.isfile():
                raise ValueError('Source file type mismatch')
            with bundle.extractfile(member) as source:
                digest = hashlib.sha256(source.read()).hexdigest()
            if member.size != expected['bytes'] or digest != expected['sha256']:
                raise ValueError('Source archive content mismatch')


def compact_test_sources(directory, cache=None):
    """Verify a compact reproduction before removing only the frozen src copy."""
    directory = completed_run(directory, cache)
    source = directory / 'src'
    archive = directory / 'source.tar.gz'
    receipt = directory / 'source-manifest.json'
    if not source.exists():
        return
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Test source must be a private directory')
    files = source_inventory(source)
    if archive.exists() or receipt.exists():
        prior = json.loads(receipt.read_text())
        if prior['files'] != files or hashlib.sha256(archive.read_bytes()).hexdigest() != prior['archive_sha256']:
            raise ValueError('Restored test inputs changed; preserve both versions')
        verify_source_archive(archive, files)
    else:
        temporary = directory / 'source.tar.gz.tmp'
        try:
            with temporary.open('xb') as raw:
                with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=6) as zipped:
                    with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as bundle:
                        for name in files:
                            bundle.add(source / name, arcname=name, recursive=False)
                raw.flush()
                os.fsync(raw.fileno())
            verify_source_archive(temporary, files)
            if source_inventory(source) != files:
                raise RuntimeError('Test source changed during compaction')
            temporary.rename(archive)
            atomic_json(receipt, dict(version=1, files=files,
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                restore='x/check --restore-sources ' + str(directory)))
        finally:
            temporary.unlink(missing_ok=True)
    # Check again after verification and receipt publication. Never touch snap/,
    # worlds, logs, results, command inputs, or the development checkout.
    if source_inventory(source) != files:
        raise RuntimeError('Test source changed before removal')
    shutil.rmtree(source)


def restore_test_sources(directory, cache=None):
    directory = completed_run(directory, cache)
    receipt = json.loads((directory / 'source-manifest.json').read_text())
    archive = directory / 'source.tar.gz'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != receipt['archive_sha256']:
        raise ValueError('Source archive digest mismatch')
    files = receipt['files']
    verify_source_archive(archive, files)
    if (directory / 'src').exists():
        if source_inventory(directory / 'src') != files:
            raise ValueError('Existing test source differs from archived input')
        return
    require_disk_space(directory, copy_bytes=sum(v['bytes'] for v in files.values()))
    temporary = Path(tempfile.mkdtemp(prefix='source-restore-', dir=directory))
    try:
        with tarfile.open(archive, 'r:gz') as bundle:
            for name, info in files.items():
                target = temporary / name
                if info['kind'] == 'directory':
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(name) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(info['mode'] & 0o777)
                os.utime(target, ns=(info['mtime_ns'], info['mtime_ns']))
        for name, info in sorted(files.items(), reverse=True):
            if info['kind'] == 'directory':
                target = temporary / name
                target.chmod(info['mode'] & 0o777)
                os.utime(target, ns=(info['mtime_ns'], info['mtime_ns']))
        if source_inventory(temporary) != files:
            raise ValueError('Restored source verification failed')
        temporary.rename(directory / 'src')
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def check_root():
    """Disposable native stores live outside the checkout and cloud sync."""
    configured = os.environ.get('SHRINE_CHECK_ROOT')
    identity = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
    return (Path(configured).expanduser() if configured else
            Path.home() / '.local/share/shrine/checks' / identity).resolve()

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
                               entrypoint=data.get('entrypoints', {}).get(mod),
                               fixture=data.get('entrypoint_fixtures', {}).get(mod),
                               group=group['name'], fast=group['fast'],
                               timeout=group['timeout'], category=group['category'],
                               enabled=group.get('enabled', True),
                               mount=group.get('mount'),
                               reason=group.get('reason', 'Explicit selection only.')))
    for mod, reason in data['excluded'].items():
        if mod in registered:
            raise ValueError('registered and excluded: ' + mod)
        suites.append(dict(name=mod, kind='reaver', target=mod, group=mod,
                           fast=False, timeout=900, category='manual', enabled=False, reason=reason))
    known = registered | data['excluded'].keys()
    found = {p.stem for p in (ROOT / 'src/reaver').glob('*.rvr')
             if p.stem.endswith('-tests') or p.stem.startswith('test-')}
    # Optional application suites can live in their mount bags after core
    # extraction. Validate their source without silently treating them as run.
    for group in data['groups']:
        if group.get('mount'):
            for mod in group['modules']:
                source = ROOT / 'extras/mounts' / group['mount'] / (mod + '.rvr')
                if not source.is_file():
                    raise ValueError('missing mount fixture: ' + str(source))
                found.add(mod)
    if found != known:
        raise ValueError(f'inventory drift: unclassified={sorted(found-known)}, missing={sorted(known-found)}')
    helpers = data.get('native_helpers', {})
    found_helpers = set()
    for path in sorted((ROOT / 'src/foil').rglob('*.foil')):
        mod = path.relative_to(ROOT / 'src/foil').with_suffix('').as_posix()
        if mod in helpers:
            found_helpers.add(mod)
        elif mod.startswith('tests/') or (mod.startswith('apps/') and path.stem == 'tests'):
            suites.append(dict(name='foil:' + mod, kind='native', target=mod,
                               group='native', fast=mod not in native_excluded, timeout=900, category='foil',
                               enabled=mod not in native_excluded, reason=native_excluded.get(mod, '')))
        if re.search(r"^\s*'\s*\?=", path.read_text(), re.M):
            suites.append(dict(name='doc:' + mod, kind='docs', target=mod,
                               group='doctests', fast=True, timeout=900, category='docs', enabled=True))
    for descriptor in (ROOT / 'extras/mounts').glob('*/mount.json'):
        mount = json.loads(descriptor.read_text())
        for mod, leaf in mount.get('tests', {}).items():
            if mod in helpers and (descriptor.parent / leaf).is_file():
                found_helpers.add(mod)
    for item in data.get('native_mounts', []):
        name = item['mount']
        descriptor = ROOT / 'extras/mounts' / name / 'mount.json'
        mount = json.loads(descriptor.read_text())
        for module, leaf in mount['tests'].items():
            if not (descriptor.parent / leaf).is_file():
                raise ValueError('missing native mount test: ' + leaf)
            suites.append(dict(name='mount:' + name + ':' + module, kind='native',
                               target=module, group='native-' + name,
                               native_mount=name, fast=True, timeout=1200,
                               category='foil', enabled=True))
    if found_helpers != helpers.keys():
        raise ValueError(f'missing native helpers: {sorted(helpers.keys() - found_helpers)}')
    for command in data['commands']:
        suites.append(dict(command, kind='command', group=command['name'], enabled=True))
    return suites


def run_process(command, directory, source, timeout, env=None, cwd=None, *, memory_bytes=1024**3):
    """Own the whole process group so timeouts also stop actor/child processes."""
    require_disk_space(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'input').write_text(source)
    started = time.monotonic()
    with (directory / 'out.log').open('w') as out:
        with subprocess.Popen(command, cwd=cwd or directory, stdin=subprocess.PIPE,
                              stdout=out, stderr=out, text=True, start_new_session=True,
                              env=env) as proc:
            completed = True
            memory = MemoryBudget(proc.pid, memory_bytes)
            try:
                pending = source
                while True:
                    memory.check()
                    check_world_storage(directory)
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    try:
                        proc.communicate(pending, timeout=min(.1, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        pending = None
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                completed = False
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
            except RuntimeError as error:
                completed = False
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                out.write('\n("ERROR" ' + json.dumps(str(error)) + ')\n')
            code = proc.returncode
            atomic_json(directory / 'memory.json', memory.report())
    return code, completed, time.monotonic() - started


def digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def copy_snapshot(source, dest):
    require_disk_space(dest, copy_bytes=sum((source / name).stat().st_size
                                          for name in ('data.mdb', 'pins.pack')))
    dest.mkdir(parents=True)
    for name in ('data.mdb', 'pins.pack'):
        shutil.copy2(source / name, dest / name)


def compiler_key(wisp):
    inputs = [*compiler_files(), *(ROOT / 'src/plan').glob('*.plan'), ROOT / 'x/stage-lib']
    return 'compiler-sovereign-v4-' + runtime_key(wisp, inputs)


def runtime_key(wisp, inputs):
    # A world's private copy of an identical engine is the same compiler.
    # Its location must not allocate another staged store on every boot.
    with Path(wisp).open('rb') as stream:
        engine = hashlib.file_digest(stream, 'sha256').hexdigest()
    return hashlib.sha256((digest(inputs) + engine).encode()).hexdigest()[:16]


def stage(wisp, fresh, timeout):
    cache = check_root()
    cache.mkdir(parents=True, exist_ok=True)
    # A runtime change invalidates boot just like PLAN changes do.
    planhash = runtime_key(wisp, [*(ROOT / 'src/plan').glob('*.plan'), ROOT / 'x/stage-lib'])
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
        with (source.resolve().parent / 'stage.lock').open('r') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            copy_snapshot(source, dest)
    else:
        copy_snapshot(source, dest)


def discard_test_snapshot(directory):
    """Only this completed test group's private copy is disposable."""
    snapshot = directory / 'snap'
    if snapshot.is_symlink() or (directory / 'world.json').exists():
        raise RuntimeError('Refusing to discard a linked snapshot or durable world')
    shutil.rmtree(snapshot)


def unresolved_stores(cache):
    """Only disposable group stores, never engines or durable worlds."""
    found = []
    for snapshot in cache.glob('run-*/*/snap'):
        if snapshot.is_symlink():
            raise RuntimeError('Linked test store requires inspection: ' + str(snapshot))
        receipt = snapshot.parent / 'result.json'
        try:
            passed = json.loads(receipt.read_text()).get('passed') is True
        except (OSError, ValueError, AttributeError):
            passed = False
        if not passed:
            found.append(snapshot.parent)
    return sorted(found)


def diagnose_store(directory, reason, cache=None):
    """Discard an explicitly diagnosed copy, retaining its reproduction."""
    cache = (cache or check_root()).resolve()
    directory = Path(directory).absolute()
    if directory.is_symlink() or directory.parent.is_symlink():
        raise RuntimeError('Diagnosis requires an unlinked test directory')
    directory = directory.resolve()
    if (directory.parent.parent != cache or
            not directory.parent.name.startswith('run-') or not reason.strip()):
        raise ValueError('Diagnosis requires a run-*/group directory and a reason')
    result = json.loads((directory / 'result.json').read_text())
    if result.get('passed') is not False:
        raise ValueError('Only a completed failed test store can be diagnosed')
    if (directory / 'snap').is_symlink() or (directory / 'world.json').exists():
        raise RuntimeError('Refusing to discard a linked snapshot or durable world')
    atomic_json(directory / 'retention.json', dict(
        diagnosis=reason, discarded='snap',
        preserved=['out.log', 'input', 'result.json', '../src or ../source.tar.gz',
                   '../source-manifest.json', '../results.json']))
    if (directory / 'snap').exists():
        discard_test_snapshot(directory)


def rotate_failure_stores(cache, limit=2):
    """Retain recent failed stores; keep reproduction/evidence for every run.

    Caller owns retention.lock. Only finished, reproducible test groups are
    eligible. An unfinished store or explicit --keep-snapshots is never an
    automatic deletion candidate. Rotation is not a claim of diagnosis.
    """
    cache = Path(cache).resolve()
    eligible = []
    for directory in unresolved_stores(cache):
        if (directory.is_symlink() or directory.parent.is_symlink() or
                directory.resolve().parent.parent != cache or
                (directory / 'world.json').exists() or
                (directory.parent / 'world.json').exists()):
            continue
        try:
            paths = [directory / name for name in ('result.json', 'out.log', 'input')]
            if any(p.is_symlink() or not p.is_file() for p in paths):
                continue
            result = json.loads(paths[0].read_text())
            if result.get('passed') is not False or result.get('keep_snapshot') is True:
                continue
            eligible.append((paths[0].stat().st_mtime_ns, directory))
        except (OSError, ValueError, AttributeError):
            continue
    discarded = []
    for _, directory in sorted(eligible)[:max(0, len(eligible) - limit)]:
        source = directory.parent / 'src'
        if source.is_symlink():
            continue
        if source.is_dir():
            files = source_inventory(source)
        else:
            manifest = directory.parent / 'source-manifest.json'
            archive = directory.parent / 'source.tar.gz'
            if manifest.is_symlink() or archive.is_symlink() or not manifest.is_file() or not archive.is_file():
                continue
            receipt = json.loads(manifest.read_text())
            if hashlib.sha256(archive.read_bytes()).hexdigest() != receipt['archive_sha256']:
                raise ValueError('Refusing retention rotation: source archive digest mismatch')
            files = receipt['files']
            verify_source_archive(archive, files)
        if not files:
            continue
        atomic_json(directory / 'retention.json', dict(
            reason='automatic_completed_failure_retention', diagnosed=False,
            discarded='snap', retained_store_limit=limit,
            source_manifest_sha256=hashlib.sha256(
                json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            preserved=['out.log', 'input', 'result.json', 'memory.json',
                       '../src or ../source.tar.gz', '../source-manifest.json'],
            recovery='Restore archived sources if needed, then rerun the recorded input with the pinned test engine.'))
        discard_test_snapshot(directory)
        discarded.append(directory)
    return discarded


def run_group(suites, wisp, template, root, timeout, keep_snapshots=False):
    # Serialize native store ownership across independent runner processes too.
    # This avoids memory spikes and closes the retention check/create race.
    with (root.parent / 'retention.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rotate_failure_stores(root.parent, limit=1)
        result = run_group_owned(suites, wisp, template, root, timeout, keep_snapshots)
        rotate_failure_stores(root.parent)
        return result


def run_group_owned(suites, wisp, template, root, timeout, keep_snapshots=False):
    directory = root / suites[0]['group']
    copy_template(template, directory / 'snap')
    command_suite = suites[0]['kind'] == 'command'
    if command_suite:
        env = dict(os.environ, WISP=wisp, TEST_TEMPLATE=str(template),
                   TEST_SOURCE_ROOT=str(root / 'src'),
                   TEST_RUN_DIR=str(directory), PATH=str(Path(wisp).parent) + os.pathsep + os.environ.get('PATH', ''))
        code, complete, seconds = run_process([sys.executable, str(ROOT / suites[0]['target'])],
                                               directory, '', timeout, env)
        log = (directory / 'out.log').read_text(errors='replace')
        good = bool(code == 0 and complete and not ERROR.search(log)
                    and re.search(suites[0]['completion'], log, re.M))
        records = []
    else:
        lines = []
        if any(s.get('entrypoint') for s in suites):
            lines.extend(['(#bind test_std (#module std))', '(#import test_std)'])
        if any(s['kind'] != 'reaver' for s in suites):
            lines.append('(#bind runner (#module foil-test-runner))')
            mods = '[' + ' '.join(rvr_string(s['target']) for s in suites) + ']'
            lines.append(f'(runner:run 0 {rvr_string(suites[0]["kind"])} {mods})')
        fixtures = {}
        fixture_calls = []
        for suite in suites:
            mod = rvr_string(suite['target'])
            if suite['kind'] == 'reaver':
                lines += [f'(print ("TEST" "start" {mod} "~:module" "~:" "~:"))',
                          f'(#bind {suite["target"]} (#module {suite["target"]}))']
                if suite.get('entrypoint'):
                    argument = '0'
                    if suite.get('fixture'):
                        fixture = tuple(suite['fixture'])
                        if fixture not in fixtures:
                            binding = f'test_fixture_{len(fixtures)}'
                            module, entry = fixture
                            lines.append(f'(#bind {binding}_module (#module {module}))')
                            fixture_calls.append(f'(define {binding} ({binding}_module:{entry} 0))')
                            fixtures[fixture] = binding
                        argument = fixtures[fixture]
                    call = (f'(test_std:assert-impl "{suite["target"]}" '
                            f'({suite["target"]}:{suite["entrypoint"]} {argument}))')
                    if suite.get('fixture'):
                        fixture_calls.extend([
                            f'(print ("TEST" "start" {mod} "~:module" "~:" "~:"))',
                            f'(define outcome (Try (lambda (ignored) {call}) 0))',
                            f'(If (Eq 1 (Hd outcome)) '
                            f'(Seq (print outcome) (print ("TEST" "error" {mod} "~:module" "~:passing entrypoint" "~:caught failure"))) '
                            f'(print ("TEST" "pass" {mod} "~:module" "~:" "~:")))'])
                        continue
                    lines.append(call)
                lines.append(f'(print ("TEST" "pass" {mod} "~:module" "~:" "~:"))')
        if fixture_calls:
            # Compiler products stay local to this call, outside snapshot state.
            lines.append('(define (test_fixture_run ignored)')
            lines.extend('  ' + call for call in fixture_calls)
            lines.extend(['  1)', '(test_fixture_run 0)'])
        lines.append('(print "TEST-RUN-DONE")')
        code, complete, seconds = run_process([wisp, '--file-root', str(root / 'src'), 'snap', 'root', '_'],
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
            path = root / 'src/foil' / (suite['target'] + '.foil')
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
        path = root / 'src/foil' / (suite['target'] + '.foil')
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
                  keep_snapshot=bool(keep_snapshots),
                  completed=complete, returncode=code, suites=[s['name'] for s in suites],
                  records=records, locations=locations, log=str(directory / 'out.log'))
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if good and not keep_snapshots:
        discard_test_snapshot(directory)
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
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--keep-snapshots', action='store_true',
                        help='Keep this run’s disposable stores explicitly, excluding automatic rotation')
    parser.add_argument('--timeout', type=float, help='override group/staging timeout in seconds')
    parser.add_argument('--diagnose-store', type=Path,
                        help='Discard a diagnosed failed group store; preserve source and logs')
    parser.add_argument('--diagnosis', help='Required explanation for --diagnose-store')
    parser.add_argument('--compact-sources', type=Path, help='Verify and compress completed run inputs')
    parser.add_argument('--restore-sources', type=Path, help='Restore exact source inputs from a completed run')
    args = parser.parse_args()
    if args.compact_sources:
        compact_test_sources(args.compact_sources)
        return 0
    if args.restore_sources:
        restore_test_sources(args.restore_sources)
        return 0
    if args.diagnose_store:
        if not args.diagnosis:
            parser.error('--diagnose-store requires --diagnosis')
        diagnose_store(args.diagnose_store, args.diagnosis)
        return 0
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
            matches = [s for s in suites if choice == s['name']
                       or s['enabled'] and (choice == s['group']
                           or choice == 'foil' and s['kind'] == 'native')]
            if not matches:
                parser.error('unknown suite/group: ' + choice)
            selected.extend(s for s in matches if s not in selected)
    else:
        selected = [s for s in suites if s['enabled'] and (s['fast'] or not args.fast)]
    for suite in selected:
        if suite.get('mount'):
            parser.error(f'{suite["name"]} belongs to an optional mount; run '
                         f'x/eden --mount {suite["mount"]} --check')
    wisp = os.environ.get('WISP') or shutil.which('wisp') or str(ROOT / 'wisp')
    wisp = str(Path(wisp).resolve())
    if not os.access(wisp, os.X_OK):
        parser.error('wisp unavailable; enter the dev shell or set WISP=/path/to/wisp')
    cache = check_root()
    cache.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='run-', dir=cache))
    started = time.monotonic()
    compiler = stage(wisp, args.fresh, args.timeout or 900)
    # Modules load lazily, sometimes minutes into a group. Preserve one source
    # revision for all runtime groups while work continues in the checkout.
    shutil.copytree(ROOT / 'src', root / 'src')
    from eden_mounts import select as select_mounts
    requested_mounts = sorted({s['native_mount'] for s in selected if s.get('native_mount')})
    # A mount's source imports its declared dependency closure. Tests must see
    # that same closure instead of accidentally depending on other selections.
    for descriptor in select_mounts(ROOT / 'extras', requested_mounts):
        bag = ROOT / 'extras/mounts' / descriptor.name
        mount = json.loads((bag / 'mount.json').read_text())
        # Some maintained mounts explicitly replace core fixture names. Honor
        # only their declared file map; an accidental module collision still
        # fails instead of changing which implementation a test imports.
        declared = mount.get('files', {})
        for relative, leaf in declared.items():
            if not relative.startswith('src/'):
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bag / leaf, target)
        for module, leaf in {**mount['modules'], **mount['tests']}.items():
            target = root / 'src/foil' / (module + '.foil')
            if target.exists() and declared.get('src/foil/' + module + '.foil') != leaf:
                raise ValueError('native mount test module collision: ' + module)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bag / leaf, target)
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
                               args.timeout or max(s['timeout'] for s in ss),
                               args.keep_snapshots) for ss in groups.values()]
        results = [f.result() for f in futures]
    (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    if not args.keep_snapshots:
        compact_test_sources(root)
    return int(not all(r['passed'] for r in results))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as e:
        sys.exit(str(e))
