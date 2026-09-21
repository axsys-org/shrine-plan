"""A subprocess transport, not a namespace implementation."""
from __future__ import annotations

import json
import copy
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
PROTECTED = {"agent", "log", "boot", "h", "io"}


def path_parts(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Use an absolute namespace path")
    parts = [] if path == "/" else path[1:].split("/")
    if len(parts) > 32 or any(not p or p in {".", ".."} or len(p) > 128 for p in parts):
        raise ValueError("Use nonempty path segments, at most 32 levels")
    return parts


def validate(operation, *, internal=False):
    if not isinstance(operation, dict):
        raise ValueError("Operation must be an object")
    op = operation.get("op")
    if op not in {"read", "make", "poke", "cull"}:
        raise ValueError("Choose read, make, poke, or cull")
    path = operation.get("path")
    parts = path_parts(path)
    if op != "read" and (not parts or (parts[0] in PROTECTED and not internal)):
        raise ValueError("The root and runtime/observation paths are read-only to the model")
    fields = copy.deepcopy(operation.get("fields", {}))
    if not isinstance(fields, dict):
        raise ValueError("fields must be an object of record slots")
    if op in {"make", "poke"} and "fields" not in operation:
        raise ValueError("make/poke require fields, including {} for an empty record")
    if op in {"read", "cull"} and fields:
        raise ValueError("read/cull do not take fields")
    if any(not k or ("/" in k and k not in {"/sys/crew", "/app/goal"}) or len(k) > 128 for k in fields):
        raise ValueError("Use simple field names, /sys/crew, or /app/goal")
    if "/app/goal" in fields:
        goal = fields["/app/goal"]
        if "/sys/crew" in fields:
            raise ValueError("Goals derive /sys/crew from their conditions; do not supply both")
        if not isinstance(goal, dict) or set(goal) != {"conditions"}:
            raise ValueError("/app/goal takes {conditions}; fulfilled is calculated by Foil, not writable")
        conditions = goal["conditions"]
        if not isinstance(conditions, dict) or not (0 if internal else 1) <= len(conditions) <= 64:
            raise ValueError("A goal needs 1–64 named conditions")
        for name, condition in conditions.items():
            if not name or "/" in name or len(name) > 128 or not isinstance(condition, dict):
                raise ValueError("Each condition needs a simple name and {path, care, note, met}")
            if set(condition) != {"path", "care", "note", "met"}:
                raise ValueError("Each condition requires exactly path, care, note, met")
            if (condition["care"] not in {"x", "y", "z"} or not isinstance(condition["note"], str)
                    or not condition["note"].strip() or type(condition["met"]) is not bool):
                raise ValueError("Condition care must be x/y/z, note nonempty text, and met a boolean")
            target = path_parts(condition["path"])
            if not target or target[0] in PROTECTED:
                raise ValueError("Goal conditions must watch application paths")
            if target == parts or (condition["care"] != "x" and parts[:len(target)] == target):
                raise ValueError("A goal cannot watch itself or a subtree containing itself")
            condition["path"] = target
    if "/sys/crew" in fields:
        crew = fields["/sys/crew"]
        if not isinstance(crew, dict) or len(crew) > 64:
            raise ValueError("/sys/crew must map up to 64 names to {path, care}; {} unwires it")
        for name, dep in crew.items():
            if not name or "/" in name or len(name) > 128 or not isinstance(dep, dict):
                raise ValueError("Each dependency needs a simple name and {path, care}")
            if set(dep) != {"path", "care"} or dep["care"] not in {"x", "y", "z"}:
                raise ValueError("Each dependency requires path and care: x, y, or z")
            target = path_parts(dep["path"])
            if not target or target[0] in PROTECTED:
                raise ValueError("Watch application paths, not root or runtime bookkeeping")
            dep["path"] = target
    # Only /sys/crew and /app/goal gain native types; other JSON remains data.
    payload = json.dumps({"op": op, "path": parts, "fields": fields},
                         ensure_ascii=False, allow_nan=False)
    if "\u0000" in payload or "\\u0000" in payload:
        raise ValueError("Foil cords cannot contain NUL")
    if len(payload.encode()) > 256_000:
        raise ValueError("Operation exceeds the 256 KB transport limit")
    return json.loads(payload)


class Native:
    def __init__(self, wisp: str, directory: Path, seed: Path | None = None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.responses = queue.Queue()
        snapshot = self.directory / "snap"
        if not (snapshot / "data.mdb").exists():
            if seed:
                shutil.copytree(seed, snapshot)
            else:
                self._boot(wisp)
        self.log = (self.directory / "native.log").open("a")
        self.proc = subprocess.Popen(
            [wisp, "--file-root", str(ROOT / "src"), "snap", "root", "_"],
            cwd=self.directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.reader = threading.Thread(target=self._reader, daemon=True)
        self.reader.start()
        self.proc.stdin.write("(#bind agent (#module agent-crud))\n(agent:serve 0)\n")
        self.proc.stdin.flush()
        try:
            ready = self.responses.get(timeout=300)
            if not ready or not ready.get("ready"):
                raise RuntimeError("Shrine bridge did not start; see native.log")
        except Exception:
            self.close()
            raise
        self.journal = (self.directory / "operations.jsonl").open("a")
        self.current_operations = []

    def _boot(self, wisp):
        with (self.directory / "boot.log").open("w") as log:
            stages = [([str(ROOT / "src/plan"), "reaver", "main"], ""),
                      (["snap", "root", "_"], "(#bind std (#module std))\n(#import std)\n::*rex\n"),
                      (["snap", "root", "_"], "(#bind quip (#module quip))\n")]
            for args, source in stages:
                subprocess.run([wisp, "--file-root", str(ROOT / "src"), *args],
                               cwd=self.directory, input=source, text=True,
                               stdout=log, stderr=log, check=True, timeout=300)

    def _reader(self):
        for line in self.proc.stdout:
            if line.startswith("NS_AGENT "):
                try:
                    self.responses.put(json.loads(line[9:]))
                except ValueError:
                    self.responses.put({"transport_error": "Malformed native response"})
            else:
                self.log.write(line)
                self.log.flush()
        self.responses.put(None)

    def _send(self, payload):
        with self.lock:
            if self.proc.poll() is not None:
                raise RuntimeError("Shrine stopped; inspect native.log")
            self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            try:
                response = self.responses.get(timeout=90)
            except queue.Empty:
                self.proc.terminate()  # never continue after an ambiguous transaction
                raise RuntimeError("Shrine timed out; stopped to avoid ambiguous retries")
            if response is None or "transport_error" in response:
                raise RuntimeError("Shrine transport failed; inspect native.log")
            return response

    def op(self, operation, *, internal=False):
        payload = validate(operation, internal=internal)
        with self.lock:
            self._require_watch_roots(payload)
            return self._execute(operation, payload)

    def _require_watch_roots(self, payload):
        """Check watch prerequisites using Shrine's records before committing a write."""
        if payload["op"] not in {"make", "poke"}:
            return
        fields = payload["fields"]
        watches = fields.get("/sys/crew", fields.get("/app/goal", {}).get("conditions", {}))
        checked = set()
        for name, dependency in watches.items():
            if dependency["care"] == "x":
                continue  # Exact watches may observe the creation of an absent record.
            target = dependency["path"]
            if payload["op"] == "make" and target == payload["path"]:
                continue  # This same native Make asserts the watched record.
            path = "/" + "/".join(target)
            if path in checked:
                continue
            result = self._send({"op": "read", "path": target, "fields": {}})
            if not result.get("ok"):
                raise RuntimeError(f"Shrine could not inspect watch target {path}")
            if not any(record["path"] == path for record in result["records"]):
                state = "only an implicit parent" if result["records"] else "not an existing record"
                raise ValueError(
                    f"Cannot install {dependency['care']}-care watch {name!r}: {path} is {state}. "
                    f"Create its record with Make {path} {{}} (preserves children), then retry. "
                    "This operation made no changes.")
            checked.add(path)

    def _execute(self, operation, payload):
        """Send and journal a native command; callers own live preflight or historical replay."""
        with self.lock:
            start = time.monotonic()
            result = self._send(payload)
            if payload["op"] != "read":
                entry = {"request": copy.deepcopy(operation), "result": copy.deepcopy(result)}
                self.current_operations.append(entry)
                self.journal.write(json.dumps(entry) + "\n")
                self.journal.flush()
            return {**result, "runtime_ms": round((time.monotonic() - start) * 1000, 2)}

    def page(self):
        return self._send({"op": "page"})["html"]

    def reset(self):
        result = self._send({"op": "reset"})
        self.journal.write(json.dumps({"reset": True}) + "\n")
        self.journal.flush()
        self.current_operations = []
        return result

    def replay(self):
        """Restore native state by re-executing the recorded operations, without model calls."""
        entries = [json.loads(line) for line in (self.directory / "operations.jsonl").read_text().splitlines()]
        last = max((i for i, e in enumerate(entries) if e.get("reset")), default=-1)
        pending = entries[last + 1:]
        self.restore(pending)

    def restore(self, operations):
        """Replay actual commands through Shrine; never install a Python state snapshot."""
        operations = copy.deepcopy(operations)
        with self.lock:
            self.reset()
            for entry in operations:
                # Old accepted watches must reproduce their original state. Live
                # preflight is intentionally excluded only from historical replay.
                payload = validate(entry["request"], internal=True)
                result = self._execute(entry["request"], payload)
                if result.get("ok") != entry["result"].get("ok"):
                    raise RuntimeError("Operation replay changed acceptance; original journal retained")

    def save_replay(self, path):
        path = Path(path)
        temp = path.with_suffix(".tmp")
        temp.write_text("".join(json.dumps(e) + "\n" for e in self.current_operations))
        temp.replace(path)

    def recover_legacy(self, saved):
        """Find an archived chat's exact observation boundary in the original journal."""
        if not saved["events"]:
            if saved["records"]:
                raise RuntimeError("No verified operation history for this archived namespace")
            return []
        last_event = saved["events"][-1]
        entries = [json.loads(line) for line in (self.directory / "operations.jsonl").read_text().splitlines()]
        for end in range(len(entries) - 1, -1, -1):
            request = entries[end].get("request", {})
            fields = request.get("fields", {})
            if (request.get("path") == last_event["ref"] and fields.get("kind") == last_event["kind"]
                    and fields.get("data") == last_event["data"]):
                start = max((i for i in range(end) if entries[i].get("reset")), default=-1)
                return entries[start + 1:end + 1]
        raise RuntimeError("The original operation journal for this chat is unavailable")

    def close(self):
        if hasattr(self, "proc") and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if hasattr(self, "journal"):
            self.journal.close()
        if hasattr(self, "reader"):
            self.reader.join(timeout=5)
        if hasattr(self, "proc"):
            self.proc.stdin.close()
            self.proc.stdout.close()
        if hasattr(self, "log"):
            self.log.close()
