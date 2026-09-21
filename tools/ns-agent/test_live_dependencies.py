"""Opt-in paid check: a real model leaves a note and acts when Shrine wakes it."""
import argparse
import json
from pathlib import Path

from runner import OpenRouter, Session
from runtime import Native


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wisp", required=True)
    p.add_argument("--runtime", required=True, type=Path)
    p.add_argument("--seed-snapshot", type=Path)
    p.add_argument("--key-file", required=True, type=Path)
    args = p.parse_args()
    native = Native(args.wisp, args.runtime, args.seed_snapshot)
    checks = []
    try:
        session = Session(native, OpenRouter(args.key_file.read_text(), .35), args.runtime / "sessions")
        session.turn(external={"op": "make", "path": "/demo/source", "fields": {"value": 10}})
        checks.append({"name": "unwatched external changes do not call model", "pass": session.metrics["calls"] == 0})
        session.turn("Create a future note at /notes/status watching the exact record /demo/source. "
                     "Whenever that record changes, copy its current value field to /demo/mirror. "
                     "Wire this up now, but don't create or update the mirror until a future source change.")
        state = {r["path"]: r["fields"] for r in session.records}
        crew = state.get("/notes/status", {}).get("/sys/crew", {})
        checks.append({"name": "model installed native crew and note", "pass":
                       bool(state.get("/notes/status", {}).get("note")) and
                       any(d == {"path": "/demo/source", "care": "x"} for d in crew.values())})
        checks.append({"name": "mirror not changed early", "pass": "/demo/mirror" not in state})
        session.turn(external={"op": "poke", "path": "/demo/source", "fields": {"value": 11}})
        state = {r["path"]: r["fields"] for r in session.records}
        checks.append({"name": "native notification automatically caused model repair", "pass":
                       state.get("/demo/mirror", {}).get("value") == 11 and
                       any(e["kind"] == "dependency" for e in session.events)})
        calls = session.metrics["calls"]
        session.turn(external={"op": "poke", "path": "/demo/source", "fields": {"value": 11}})
        session.turn(external={"op": "make", "path": "/unrelated", "fields": {}})
        checks.append({"name": "no-op and unrelated change cause no extra model calls", "pass": session.metrics["calls"] == calls})
        session.turn(external={"op": "cull", "path": "/notes/status"})
        session.turn(external={"op": "poke", "path": "/demo/source", "fields": {"value": 12}})
        state = {r["path"]: r["fields"] for r in session.records}
        checks.append({"name": "deleting note stops wakeups", "pass": session.metrics["calls"] == calls and
                       state.get("/demo/mirror", {}).get("value") == 11})
        report = {"pass": all(c["pass"] for c in checks), "checks": checks, "metrics": session.metrics}
        (args.runtime / "live-checks.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        if not report["pass"]:
            raise SystemExit(1)
    finally:
        native.close()


if __name__ == "__main__":
    main()
