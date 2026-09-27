"""Physical sources and executors. No application matcher or retry policy."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import urllib.error
import socket
from uuid import uuid4

from records import checked, digest, encoded, fields_of
from native import now


class IO:
    def __init__(self, world):
        self.world = world
        self.artifacts = world.directory / "artifacts"
        self.artifacts.mkdir(exist_ok=True)

    def artifact(self, data):
        data = data.encode() if isinstance(data, str) else data
        key = hashlib.sha256(data).hexdigest()
        p = self.artifacts / key
        if not p.exists():
            with p.open("xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        return {"sha256": key, "bytes": len(data), "path": str(p)}

    def source(self, identity, driver, config, *, outbound=False):
        with self.world.lock:
            return self._source(identity, driver, config, outbound=outbound)

    def _source(self, identity, driver, config, *, outbound=False):
        if driver not in {"filesystem", "git", "process", "http", "push"}:
            raise ValueError("driver must be filesystem, git, process, http or push")
        path = "/_shadow/sources/" + digest(identity)
        record = self.world.exact(path)
        checked(self.world.write("make", path, {"identity": identity, "driver": driver,
            "config": config, "outbound": bool(outbound)}, expected_case=record["case"] if record else 0))
        return {"path": path, "case": self.world.exact(path)["case"]}

    def observe(self, envelope, *, event_id=None):
        with self.world.lock:
            return self._observe(envelope, event_id=event_id)

    def _observe(self, envelope, *, event_id=None):
        if not isinstance(envelope, dict) or any(k not in envelope for k in ("source", "subject", "availability", "coverage")):
            raise ValueError("Observation needs source, subject, availability and coverage")
        if envelope["availability"] not in {"available", "unavailable", "deleted"}:
            raise ValueError("availability must distinguish available, unavailable and deleted")
        if envelope["coverage"] not in {"complete", "partial", "unknown"}:
            raise ValueError("coverage must be complete, partial or unknown")
        event_id = event_id or uuid4().hex
        path = "/_shadow/observations/" + digest(event_id)
        observed = {**envelope, "observed_at": envelope.get("observed_at", now()), "event_id": event_id}
        if len(encoded(observed).encode()) > 8192 or '\\u0000' in encoded(envelope.get('value')):
            observed = {k: v for k, v in observed.items() if k != "value"}
            observed["value_artifact"] = self.artifact(encoded(envelope.get("value")))
        existing = self.world.exact(path)
        if existing:
            prior = fields_of(existing)
            if prior.get("envelope_sha256") != digest(envelope):
                raise ValueError("Observation event id reused with different facts")
            return {"path": path, "case": existing["case"], "duplicate": True}
        observed["envelope_sha256"] = digest(envelope)
        if isinstance(envelope.get("work"), str):
            observed["origin_work"] = {"path": envelope["work"]}
        checked(self.world.write("make", path, observed, expected_case=0, request_id="observe-" + digest(event_id),
            work=envelope.get("work")))
        receipt = {"path": path, "case": self.world.exact(path)["case"]}
        # A physical subject head is an observation, not an inferred concept.
        # Receipt/time churn is outside its factual publication.
        head = "/_shadow/subjects/" + digest([envelope["source"], envelope["subject"]])
        facts = {k: observed[k] for k in ("source", "subject", "revision", "value", "value_artifact", "availability", "coverage") if k in observed}
        prior = self.world.exact(head)
        if fields_of(prior) != facts:
            checked(self.world.write("make", head, facts, expected_case=prior["case"] if prior else 0))
        return {**receipt, "subject_record": head}

    def sample(self, source, *, only_changes=False):
        fields = fields_of(self.world.exact(source))
        config, driver = fields["config"], fields["driver"]
        availability, coverage = "available", "complete"
        try:
            if driver == "filesystem":
                p = Path(config["path"])
                data = p.read_bytes()
                artifact = self.artifact(data)
                value = {"sha256": artifact["sha256"], "bytes": len(data)}
                if config.get("text"):
                    value["text"] = data.decode(config.get("encoding", "utf-8"))
            elif driver == "git":
                root = config["path"]
                def git(*args):
                    return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=30, check=True).stdout
                value = {"head": git("rev-parse", "HEAD").decode().strip(),
                    "status_entries": git("status", "--porcelain=v1", "-z").decode().split('\0')[:-1],
                    "diff": self.artifact(git("diff", "--no-ext-diff", "HEAD"))}
                artifact = self.artifact(encoded(value))
            elif driver == "http":
                with urllib.request.urlopen(config["url"], timeout=config.get("timeout", 15)) as r:
                    data = r.read(config.get("max_bytes", 1048576) + 1)
                    if len(data) > config.get("max_bytes", 1048576):
                        data, coverage = data[:config.get("max_bytes", 1048576)], "partial"
                    artifact = self.artifact(data)
                    value = {"status": r.status, "body": data.decode("utf-8", "replace")}
            else:
                raise ValueError("This source accepts pushed observations or explicit execution")
        except FileNotFoundError:
            availability, value, artifact = "deleted", None, None
        except (OSError, subprocess.SubprocessError, UnicodeError) as error:
            availability, coverage, value, artifact = "unavailable", "unknown", {"error": str(error)}, None
        revision = digest([availability, coverage, value])
        head = "/_shadow/subjects/" + digest([source, fields["identity"]])
        prior = self.world.exact(head)
        if only_changes and fields_of(prior).get("revision") == revision:
            return {"unchanged": True, "subject_record": head, "case": prior["case"]}
        return self.observe({"source": source, "subject": fields["identity"],
            "revision": revision, "value": value,
            "availability": availability, "coverage": coverage, "artifacts": [artifact] if artifact else []})

    def execute(self, driver, config, operation, arguments):
        start = now()
        result = {"started_at": start, "driver": driver, "operation": operation, "effects": "unknown"}
        try:
            if driver == "filesystem":
                p = Path(config["path"])
                if operation == "read":
                    data = p.read_bytes()
                    result.update(value=data.decode("utf-8", "replace"), artifact=self.artifact(data))
                elif operation == "write":
                    if "expected_sha256" in arguments:
                        current = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
                        if current != arguments["expected_sha256"]:
                            raise ValueError("external_revision_conflict")
                    p.write_text(arguments["text"])
                    result["effects"] = {"written_path": str(p)}
                else:
                    raise ValueError("Unsupported filesystem operation")
            elif driver == "process" and operation == "run":
                argv = arguments["argv"]
                if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
                    raise ValueError("argv must be a nonempty array of strings")
                process = subprocess.run(argv, cwd=config.get("cwd"), capture_output=True,
                    timeout=config.get("timeout", 30), shell=False)
                result.update(exit_code=process.returncode, stdout=self.artifact(process.stdout),
                    stderr=self.artifact(process.stderr))
                result["reported_outcome"] = "success" if process.returncode == 0 else "failure"
            elif driver == "http" and operation == "request":
                body = arguments.get("body")
                request = urllib.request.Request(config["url"],
                    data=body.encode() if isinstance(body, str) else None,
                    headers=arguments.get("headers", {}), method=arguments.get("method", "GET"))
                with urllib.request.urlopen(request, timeout=config.get("timeout", 15)) as response:
                    data = response.read(1048576)
                    result.update(status=response.status, body=self.artifact(data))
            else:
                raise ValueError("Driver does not implement this operation")
            result.setdefault("reported_outcome", "success")
        except (subprocess.TimeoutExpired, TimeoutError, socket.timeout) as error:
            result.update(reported_outcome="uncertain", error=str(error))
        except urllib.error.URLError as error:
            result.update(reported_outcome="uncertain", error=str(error))
        except Exception as error:
            result.update(reported_outcome="failure", error=str(error))
        return {**result, "finished_at": now()}

    def dispatch(self, request_path):
        # Eligibility and retries belong to the request's native form. Claim by
        # case, then verify that the form actually accepted this attempt.
        with self.world.lock:
            record = self.world.exact(request_path)
            fields = fields_of(record)
            if fields.get("status") != "PENDING":
                return {"dispatched": False, "status": fields.get("status")}
            source_record = self.world.exact(fields["driver"])
            source = fields_of(source_record)
            if not source.get("outbound"):
                return {"dispatched": False, "error": "Source is observation-only"}
            attempt = uuid4().hex
            checked(self.world.write("poke", request_path, {"claim": attempt, "claimed_at": now()}, expected_case=record["case"]))
            claimed = fields_of(self.world.exact(request_path))
            if claimed.get("status") != "IN_FLIGHT" or claimed.get("attempt") != attempt:
                return {"dispatched": False, "error": "Native request did not accept claim"}
        outcome = self.execute(source["driver"], source["config"], fields["operation"], fields["arguments"])
        result = self.observe({"source": fields["driver"], "subject": request_path,
            "availability": "available", "coverage": "complete", "kind": "execution",
            "attempt": attempt, "source_revision": source_record["case"], "request": {"path": request_path, "case": record["case"]},
            "value": outcome, "work": fields.get("origin_work")}, event_id=attempt)
        checked(self.world.write("poke", request_path, {"report_attempt": attempt,
            "reported_outcome": outcome["reported_outcome"], "outcome": result}))
        return {"dispatched": True, "outcome": result}
