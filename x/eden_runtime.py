import signal
import sys


class TerminationSignals:
    """Unwind owned resources on SIGTERM before releasing the world lock."""
    def __enter__(self):
        self.previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, self.stop)
        return self

    @staticmethod
    def stop(number, frame):
        raise SystemExit(128 + number)

    def __exit__(self, *ignored):
        signal.signal(signal.SIGTERM, self.previous)


def runtime_exit_status(returncode, log_path):
    """Keep a native child failure visible to people and calling tools."""
    if returncode < 0:
        number = -returncode
        try:
            name = signal.Signals(number).name
        except ValueError:
            name = 'unknown signal'
        print(f'Wisp exited due to {name} (signal {number}). Log: {log_path}',
              file=sys.stderr, flush=True)
        return 128 + number
    print(f'Wisp exited with status {returncode}. Log: {log_path}',
          file=sys.stderr, flush=True)
    return returncode

import re
def startup_ready(output, returned_marker):
    return ('HTTP foot listening' in output and bool(re.search(
        r'^\("' + re.escape(returned_marker) + r'"\s+\(0(?:\s|\))', output, re.M)))

def startup_failed(output, returned_marker):
    # Try returns (0 value) on success and (1 reason) on failure. Eden's entry
    # returns its spawned supervisor actor ID before the HTTP foot listens.
    # Success is not readiness: the caller must still prove the live listener.
    return bool(re.search(r'^\("ERROR"(?:\s|\))', output, re.M)
                or re.search(r'^\("' + re.escape(returned_marker) + r'"\s+\(1(?:\s|\))', output, re.M)
                or 'pump: listen failed' in output or 'bind/listen failed' in output)


# Persistent worlds own a runnable native Silo root. Python pins the physical
# engine/source closure and supervises it; it never reconstructs native state.
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import ctypes
import errno
from functools import lru_cache
import subprocess
import threading
import time


GIB = 1024 ** 3
_memory_sample_lock = threading.RLock()


class _DarwinUsage(ctypes.Structure):
    # SDK sys/resource.h, rusage_info_v0. Physical footprint includes charged
    # compressed memory: RSS alone can fall while the process grows into swap.
    _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64) for name in
        ('user', 'system', 'pkg_wakeups', 'interrupt_wakeups', 'pageins',
         'wired', 'resident', 'footprint', 'start', 'exit')]


@lru_cache(maxsize=1)
def _darwin_query():
    library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    query = library.proc_pid_rusage
    query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    query.restype = ctypes.c_int
    return query


def process_usage(pid):
    """Current charged bytes, never virtual address reservations."""
    # The owner, worker headroom check and worker monitor share this process.
    # Serialize their sampling helpers: one ps must not discover a sibling ps
    # and try to charge it while Darwin is tearing it down. The queried native
    # owner and workers remain fully accounted for.
    with _memory_sample_lock:
        return _process_usage(pid)


def _process_usage(pid):
    if sys.platform == 'darwin':
        usage = _DarwinUsage()
        if _darwin_query()(pid, 0, ctypes.byref(usage)):
            code = ctypes.get_errno()
            if code in (errno.ESRCH, errno.ENOENT):
                return None
            if code == errno.EPERM:
                # A helper can exit between the process-tree snapshot and
                # rusage. Darwin may report EPERM, not ESRCH, during teardown.
                state = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'stat='],
                                       capture_output=True, text=True, timeout=1)
                if (state.returncode == 1 and not state.stdout.strip()) or (
                        state.returncode == 0 and state.stdout.strip().startswith('Z')):
                    return None
                # Also allow a completed exec transition. A live process that
                # remains unreadable still fails closed; it is never charged 0.
                if _darwin_query()(pid, 0, ctypes.byref(usage)) == 0:
                    code = 0
                else:
                    code = ctypes.get_errno()
                    if code in (errno.ESRCH, errno.ENOENT):
                        return None
                    # The helper can finish between the first ps and this
                    # second rusage, too. Confirm that exact PID has gone;
                    # never suppress a persistent live accounting failure.
                    state = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'stat='],
                                           capture_output=True, text=True, timeout=1)
                    if (state.returncode == 1 and not state.stdout.strip()) or (
                            state.returncode == 0 and state.stdout.strip().startswith('Z')):
                        return None
            if code:
                raise RuntimeError(f'Cannot measure owned process {pid}: errno {code}')
        return dict(pid=pid, resident=usage.resident, charged=usage.footprint,
                    identity=usage.start, metric='physical_footprint')
    if sys.platform.startswith('linux'):
        try:
            fields = dict(line.split(':', 1) for line in
                          Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
            rss = int(fields.get('VmRSS', '0 kB').split()[0]) * 1024
            swap = int(fields.get('VmSwap', '0 kB').split()[0]) * 1024
            # stat's comm may contain spaces or parentheses.
            start = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        except (FileNotFoundError, ProcessLookupError):
            return None
        return dict(pid=pid, resident=rss, charged=rss + swap,
                    identity=int(start), metric='rss_plus_swap')
    raise RuntimeError('No process-memory accounting for this platform')


def process_tree_usage(root):
    with _memory_sample_lock:
        return _process_tree_usage(root)


def _process_tree_usage(root):
    with subprocess.Popen(['/bin/ps', '-axo', 'pid=,ppid='], stdout=subprocess.PIPE,
                          text=True) as sampler:
        rows = sampler.communicate(timeout=5)[0].splitlines()
        if sampler.returncode:
            raise RuntimeError('Cannot list owned processes')
    parents = {int(pid): int(parent) for pid, parent in (line.split() for line in rows)}
    # ps includes itself in its snapshot. It has already been reaped here,
    # and its PID may be reused while we measure the actual owned processes.
    parents.pop(sampler.pid, None)
    selected = {root}
    while True:
        following = selected | {pid for pid, parent in parents.items() if parent in selected}
        if following == selected:
            break
        selected = following
    return [value for pid in sorted(selected) if (value := process_usage(pid)) is not None]


class MemoryBudget:
    """Sampled process-tree budget; not an OS-enforced allocation quota."""
    def __init__(self, pid, maximum=GIB):
        if maximum <= 0:
            raise ValueError('Memory budget must be positive')
        self.pid, self.maximum = pid, maximum
        self.peak = self.resident_peak = self.samples = 0
        self.processes = []
        self.peak_processes = []
        self.error = None

    def check(self):
        try:
            self.processes = process_tree_usage(self.pid)
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            self.error = f'Cannot enforce owned process memory budget: {error}'
            raise RuntimeError(self.error) from error
        charged = sum(item['charged'] for item in self.processes)
        resident = sum(item['resident'] for item in self.processes)
        if charged > self.peak:
            self.peak_processes = self.processes
        self.peak = max(self.peak, charged)
        self.resident_peak = max(self.resident_peak, resident)
        self.samples += 1
        if charged > self.maximum:
            self.error = (f'Owned process memory exceeds {self.maximum // 2**20} MiB: '
                          f'{charged // 2**20} MiB charged; native state retained')
            raise RuntimeError(self.error)

    def report(self):
        return dict(limit_bytes=self.maximum, sampled_peak_bytes=self.peak,
                    sampled_resident_peak_bytes=self.resident_peak, samples=self.samples,
                    peak_processes=self.peak_processes,
                    metric='physical_footprint' if sys.platform == 'darwin' else 'rss_plus_swap',
                    error=self.error)


class MemoryMonitor:
    """Cover blocking startup/check calls as well as the owner's idle loop."""
    def __init__(self, maximum, report_path):
        self.budget = MemoryBudget(os.getpid(), maximum)
        self.path = Path(report_path)
        self.done = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def worker_capacity(self):
        """Reserve owner headroom before launching an isolated native worker."""
        used = sum(item['charged'] for item in process_tree_usage(self.budget.pid))
        available = self.budget.maximum - used - 128 * 2**20
        if available < 256 * 2**20:
            raise RuntimeError('Insufficient memory headroom for a native worker; '
                               'the live owner is unchanged')
        return min(GIB, available)

    def check_worker(self):
        """Stop the disposable worker before the owner's emergency guard fires."""
        used = sum(item['charged'] for item in process_tree_usage(self.budget.pid))
        if used > self.budget.maximum - 128 * 2**20:
            raise RuntimeError('Native worker exhausted shared memory headroom; '
                               'stop the worker and retain the live owner')

    def run(self):
        while not self.done.wait(.1):
            try:
                self.budget.check()
            except (RuntimeError, OSError, subprocess.SubprocessError) as error:
                self.error = str(error)
                self.stop_children(self.budget.processes)
                return

    def stop_children(self, processes):
        # Only children sampled under this launcher, rechecked against process
        # start identity. Never signal the user's other apps.
        for item in reversed(processes):
            if item['pid'] == self.budget.pid:
                continue
            try:
                current = process_usage(item['pid'])
                if current and current['identity'] == item['identity']:
                    os.kill(item['pid'], signal.SIGKILL)
            except (ProcessLookupError, RuntimeError, OSError):
                pass

    def check(self):
        if self.error:
            raise RuntimeError(self.error)

    def __enter__(self):
        if self.path.exists():
            self.path.rename(self.path.with_name(f'{self.path.stem}-{time.time_ns()}.json'))
        self.thread.start()
        return self

    def __exit__(self, *ignored):
        self.done.set()
        self.thread.join(timeout=6)
        # A worker may be in a daemon request thread when the owner shuts down.
        # Do not leave its OS process running after the supervisor exits.
        try:
            remaining = process_tree_usage(self.budget.pid)
        except (OSError, subprocess.SubprocessError, RuntimeError):
            remaining = self.budget.processes
        # An earlier cleanup callback may already have stopped a parent and
        # reparented its children. Retain the last verified ownership sample.
        self.stop_children(self.budget.processes)
        self.stop_children(remaining)
        report = self.budget.report()
        report['error'] = self.error
        atomic_json(self.path, report)


def require_disk_space(path, reserve_bytes=2 * GIB, copy_bytes=0):
    """Leave headroom before copying a store or starting native work."""
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    free = shutil.disk_usage(path).free
    if free < reserve_bytes + copy_bytes:
        raise RuntimeError(f'Insufficient disk space at {path}: {free // 2**20} MiB free; '
                           f'need {(reserve_bytes + copy_bytes) // 2**20} MiB. '
                           'Preserve live pins; retire disposable runs instead.')


def check_world_storage(path, min_free_bytes=GIB, max_pin_bytes=GIB):
    """Stop supervised growth without truncating or collecting native pins."""
    require_disk_space(path, min_free_bytes)
    pins = Path(path) / 'snap/pins.pack'
    if pins.exists() and pins.stat().st_size > max_pin_bytes:
        raise RuntimeError(f'Pin store exceeds {max_pin_bytes // 2**20} MiB: {pins}. '
                           'World retained intact; inspect before raising the budget.')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_identity(root):
    return {str(p.relative_to(root)): digest(p)
            for p in sorted(Path(root).rglob('*'))
            if p.is_file() and p.suffix in ('.rvr', '.foil')
            and p.relative_to(root).parts[0] != 'mounts'}


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.next')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class World:
    protocol = 'arbiter/2'

    def __init__(self, path, runtime, source, mounts, node, port, *, protocol='arbiter/2'):
        if protocol not in ('arbiter/2', 'arbiter/3', 'canvas/1'):
            raise ValueError('Unsupported world protocol')
        self.protocol = protocol
        self.path = Path(path).resolve()
        self.runtime = Path(runtime).resolve()
        self.source = Path(source).resolve()
        self.config = dict(protocol=self.protocol, node=node, port=port,
                           mounts=list(mounts))
        self.lock = None
        self.resuming = False

    def __enter__(self):
        require_disk_space(self.path)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.path / 'owner.lock').open('a+')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            self.lock = None
            raise RuntimeError('This world already has a live owner') from None
        manifest = self.path / 'world.json'
        try:
            if manifest.exists():
                saved = json.loads(manifest.read_text())
                for key, expected in self.config.items():
                    if saved.get(key) != expected:
                        raise RuntimeError(f'World {key} differs; no automatic migration')
                engine = self.path / 'engine'
                if digest(engine) != saved['engine_sha256']:
                    raise RuntimeError('Pinned world engine changed')
                if source_identity(self.path / 'src') != saved['source']:
                    raise RuntimeError('Pinned world sources changed')
                if not saved.get('native_root_committed'):
                    raise RuntimeError('World initialization was not confirmed; preserve it for recovery and choose a fresh world')
                self.runtime = engine
                self.resuming = True
            else:
                if any((self.path / p).exists() for p in ('snap', 'src', 'engine')):
                    raise RuntimeError('Incomplete world directory; preserve it and choose a fresh world')
                shutil.copytree(self.source, self.path / 'src')
                shutil.copyfile(self.runtime, self.path / 'engine')
                (self.path / 'engine').chmod(0o700)
                self.runtime = self.path / 'engine'
                saved = dict(self.config, engine_sha256=digest(self.runtime),
                             source=source_identity(self.path / 'src'))
                atomic_json(manifest, saved)
            self.manifest = saved
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def session(self, scan_port, scan_token, hooks):
        atomic_json(self.path / 'src/session.json', dict(
            scan_port=scan_port, scan_token=scan_token, hooks=hooks))

    def confirm_native_root(self):
        """Called only after the native post-checkpoint readiness marker."""
        manifest = self.path / 'world.json'
        saved = json.loads(manifest.read_text())
        if not saved.get('native_root_committed'):
            atomic_json(manifest, dict(saved, native_root_committed=True))

    def __exit__(self, *args):
        if self.lock:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
            self.lock.close()
            self.lock = None
