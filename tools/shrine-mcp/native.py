"""Single-owner transport and durability. Application execution is native Foil."""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from uuid import uuid4

from records import PROTOCOL, checked, digest, encoded, path_parts, slots_of, scope_result, check_world, validate_text, prepare_value

ROOT = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store" and p.relative_to(root).parts[:2] != ("foil", "user"):
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


class NativeProcess:
    def __init__(self, directory, wisp, source, seed=None, timeout=90):
        self.directory, self.source = Path(directory), Path(source)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.responses = queue.Queue()
        self.compiling = True
        snapshot = self.directory / "snap"
        started = self.directory / "started"
        if not snapshot.exists():
            if seed:
                subprocess.run(["cp", "-cR", str(seed), str(snapshot)], check=True)
            else:
                with (self.directory / "boot.log").open("w") as log:
                    for args, text in [([str(self.source / "plan"), "reaver", "main"], ""),
                        (["snap", "root", "_"], "(#bind std (#module std))\n(#import std)\n::*rex\n"),
                        (["snap", "root", "_"], "(#bind quip (#module quip))\n")]:
                        subprocess.run([wisp, "--file-root", str(source), *args], cwd=self.directory,
                            input=text, text=True, stdout=log, stderr=log, check=True, timeout=300)
        self.log = (self.directory / "native.log").open("a")
        self.proc = subprocess.Popen([wisp, "--file-root", str(source), "snap", "root", "_"],
            cwd=self.directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        if not started.exists():
            self.proc.stdin.write("(#bind shadow (#module shadow))\n(shadow:serve 0)\n")
            self.proc.stdin.flush()
        try:
            self.ready = self.responses.get(timeout=600)
            if not self.ready or self.ready.get("protocol_version") != PROTOCOL:
                raise RuntimeError("Expected protocol 5 native owner; inspect native.log")
            started.write_text("5\n")
            self.compiling = False
        except BaseException:
            self.close()
            raise

    def _read(self):
        for line in self.proc.stdout:
            if line.startswith("SHRINE_V5 "):
                try:
                    self.responses.put(json.loads(line[10:]))
                except ValueError:
                    self.responses.put({"transport_error": "Malformed native response"})
            else:
                self.log.write(line)
                self.log.flush()
                if ((self.compiling and any(s in line for s in ("foil-new-elab-errors", "quip-parse-error", "not-an-environment", "reaver-error"))) or line.startswith('("ERROR"')):
                    self.responses.put({"transport_error": "Compilation failed; inspect native.log"})
        self.responses.put(None)

    def send(self, request):
        validate_text(request)
        self.proc.stdin.write(encoded(request) + "\n")
        self.proc.stdin.flush()
        try:
            result = self.responses.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise RuntimeError("Native execution deadline exceeded; last durable snapshot retained") from None
        if result is None or "transport_error" in result:
            raise RuntimeError("Native transport stopped; inspect native.log and restart from its snapshot")
        return result

    def close(self):
        if hasattr(self, "proc"):
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            for f in (self.proc.stdin, self.proc.stdout):
                if f:
                    f.close()
        if hasattr(self, "reader"):
            self.reader.join(timeout=5)
        if hasattr(self, "log"):
            self.log.close()


class World:
    def __init__(self, directory, wisp, seed=None, *, timeout=90):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.owner = (self.directory / "owner.lock").open("a")
        fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.native = None
        self.wisp, self.seed, self.timeout = str(wisp), seed, timeout
        self.events_log = self.directory / "events.jsonl"
        self.completed, self.events_list = {}, []
        self.sequence = 0
        self.pending = None
        manifest = self.directory / "engine.json"
        source = self.directory / "engine"
        try:
            if manifest.exists():
                self.engine = json.loads(manifest.read_text())
                if self.engine.get("protocol_version") != PROTOCOL:
                    raise RuntimeError("This is not a v5 world. Use its archived compatible bridge; no migration was performed.")
                if self.engine["source_sha256"] != tree_hash(source):
                    raise RuntimeError("Pinned engine source changed")
            else:
                if self.events_log.exists() or (self.directory / "requests.jsonl").exists():
                    raise RuntimeError("Existing history has no v5 manifest; refusing to reinterpret it")
                shutil.copytree(ROOT / "src", source, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                self.engine = {"protocol_version": PROTOCOL, "world_id": uuid4().hex,
                    "source_sha256": tree_hash(source), "wisp_sha256": hashlib.sha256(Path(wisp).read_bytes()).hexdigest()}
                manifest.write_text(encoded(self.engine))
            for module_file in (self.directory / "modules").glob("*.json"):
                sources = json.loads(module_file.read_text())
                if digest(sources) != module_file.stem:
                    raise RuntimeError("Module artifact metadata changed")
                for name, content in sources.items():
                    pinned = source / "foil" / (("user/" + module_file.stem + "/main") if name == "main" else name)
                    pinned = pinned.with_suffix(".foil")
                    if not pinned.exists() or pinned.read_text() != content:
                        raise RuntimeError("Pinned module source changed: " + name)
            if self.engine["wisp_sha256"] != hashlib.sha256(Path(wisp).read_bytes()).hexdigest():
                raise RuntimeError("Pinned Wisp changed")
            # Immutable user sources are separate from the hashed runtime, but
            # reachable through its file root. They are content-verified on use.
            (self.directory / "modules").mkdir(exist_ok=True)
            self._recover_log()
            self.native = NativeProcess(self.directory / "native", str(wisp), source, seed, timeout)
            ready = self.native.ready
            if ready["sequence"] == self.sequence + 1 and self.pending:
                result = ready["last"]
                self._commit(self.pending, result)
            elif ready["sequence"] != self.sequence:
                raise RuntimeError("Native snapshot and retained journal disagree; preserve both for recovery")
            elif self.pending:
                result = self.native.send({"op": "abort", "sequence": self.pending["sequence"]})
                self._commit(self.pending, result)
            from context import Connections
            self.connections = Connections(self.engine["world_id"])
            for event in self.events_list:
                self.connections.ingest(event)
        except BaseException:
            self.close()
            raise

    def _append(self, item):
        with self.events_log.open("ab", buffering=0) as f:
            f.write((encoded(item) + "\n").encode())
            os.fsync(f.fileno())

    def _recover_log(self):
        if not self.events_log.exists():
            return
        raw = self.events_log.read_bytes()
        if raw and not raw.endswith(b"\n"):
            end = raw.rfind(b"\n") + 1
            (self.directory / ("torn-tail-" + uuid4().hex)).write_bytes(raw[end:])
            with self.events_log.open("r+b") as f:
                f.truncate(end)
                os.fsync(f.fileno())
            raw = raw[:end]
        for line in raw.splitlines():
            item = json.loads(line)
            if item["kind"] == "begin":
                if self.pending or item["sequence"] != self.sequence + 1:
                    raise RuntimeError("Invalid journal sequence")
                self.pending = item
            elif item["kind"] == "commit" and self.pending and item["id"] == self.pending["id"]:
                self._remember(self.pending, item["result"])
                self.pending = None
            else:
                raise RuntimeError("Invalid journal commit")

    def _remember(self, entry, result):
        result = scope_result({**result, "cursor": entry["sequence"], "request_id": entry["id"]}, self.engine["world_id"])
        self.sequence = entry["sequence"]
        self.completed[entry["id"]] = (entry["signature"], result)
        self.events_list.append({"sequence": self.sequence, "id": entry["id"], "at": entry["at"],
            "work": entry.get("work"), "operation": entry["payload"], "result": result})

    def _commit(self, entry, result):
        self._append({"kind": "commit", "id": entry["id"], "result": result})
        self._remember(entry, result)
        self.pending = None

    def transact(self, payload, request_id=None, work=None):
        validate_text(payload)
        with self.lock:
            if self.pending:
                raise RuntimeError("Previous outcome uncertain; restart to reconcile durable native snapshot")
            request_id = request_id or uuid4().hex
            signature = digest(payload)
            if request_id in self.completed:
                old, result = self.completed[request_id]
                if old != signature:
                    raise ValueError("request_id already belongs to different inputs")
                return {**copy.deepcopy(result), "request_id": request_id, "duplicate": True}
            entry = {"kind": "begin", "id": request_id, "sequence": self.sequence + 1,
                "at": now(), "work": work, "signature": signature,
                "payload": {**payload, "sequence": self.sequence + 1, "work": work}}
            self._append(entry)
            self.pending = entry
            result = self.native.send(entry["payload"])
            self._commit(entry, result)
            self.connections.ingest(self.events_list[-1])
            return scope_result({**result, "cursor": self.sequence, "request_id": request_id}, self.engine["world_id"])

    def write(self, op, path, fields=None, *, slots=None, record=None, expected_case=None, request_id=None, work=None):
        if op not in {"make", "poke", "cull"}:
            raise ValueError("Choose make, poke or cull")
        payload = {"op": op, "path": path_parts(path), "slots": slots_of(fields, slots)}
        if record is not None:
            if fields is not None or slots is not None:
                raise ValueError("Supply a native record or fields/slots, not both")
            check_world(record, self.engine["world_id"])
            payload["record"] = prepare_value(record, self.engine["world_id"])
        for slot in payload["slots"]:
            slot['value'] = prepare_value(slot['value'], self.engine['world_id'])
        if expected_case is not None:
            if type(expected_case) is not int or expected_case < 0:
                raise ValueError("expected_case must be a nonnegative integer")
            payload["expected_case"] = expected_case
        return self.transact(payload, request_id, work)

    def read(self, path, *, recursive=False, case=None, limit=30, after=""):
        with self.lock:
            result = scope_result(checked(self.native.send({"op": "read", "path": path_parts(path),
                "recursive": int(recursive), "case": case or 0})), self.engine["world_id"])
            rows = [r for r in result["records"] if r["path"] > after]
            if case is None:
                for row in rows:
                    self.connections.update(row)
            limit = max(1, min(limit, 100))
            return {"records": rows[:limit], "more": len(rows) > limit,
                "next_after": rows[min(limit, len(rows))-1]["path"] if rows else after, "cursor": self.sequence}

    def exact(self, path):
        rows = self.read(path)["records"]
        return rows[0] if rows else None

    def evaluate(self, expression, *, module=None, inputs=None, request_id=None, work=None):
        rid = request_id or uuid4().hex
        return self.transact({"op": "eval", "expression": expression,
            "module": prepare_value(module, self.engine['world_id']),
            "inputs": {k:prepare_value(v,self.engine['world_id']) for k,v in (inputs or {}).items()}, "id": rid}, rid, work)

    def compile(self, source, *, exports=(), modules=None, request_id=None, work=None):
        rid = request_id or uuid4().hex
        sources = {**(modules or {}), "main": source}
        artifact = digest(sources)
        for name, contents in sources.items():
            if not isinstance(contents, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/" for c in name) or (name != "main" and not name.startswith("user/")) or "//" in name:
                raise ValueError("Additional modules require immutable user/... names and Foil source text")
            target = ("user/" + artifact + "/main") if name == "main" else name
            p = (self.directory / "engine" / "foil" / target).with_suffix(".foil")
            if p.exists() and p.read_text() != contents:
                raise RuntimeError("Immutable module source changed; choose a new module name: " + name)
        for name, contents in sources.items():
            target = ("user/" + artifact + "/main") if name == "main" else name
            p = (self.directory / "engine" / "foil" / target).with_suffix(".foil")
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                with p.open("x") as f:
                    f.write(contents); f.flush(); os.fsync(f.fileno())
        metadata = self.directory / "modules" / (artifact + ".json")
        with metadata.open("w") as f:
            f.write(encoded(sources)); f.flush(); os.fsync(f.fileno())
        return self.transact({"op": "compile", "module": "user/" + artifact + "/main",
            "exports": [e.split("/") if isinstance(e, str) else e for e in exports],
            "id": rid, "artifact": artifact}, rid, work)

    def events(self, cursor=0, limit=50):
        rows = [e for e in self.events_list if e["sequence"] > cursor]
        selected = rows[:max(1, min(limit, 100))]
        return {"events": selected, "cursor": selected[-1]["sequence"] if selected else cursor,
            "more": len(rows) > len(selected)}

    def close(self):
        if self.native:
            self.native.close()
        if getattr(self, "owner", None) and not self.owner.closed:
            fcntl.flock(self.owner, fcntl.LOCK_UN)
            self.owner.close()
