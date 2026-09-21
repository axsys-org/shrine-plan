"""Opt-in paid check: real model assessments, native completion and reopening."""
import argparse
import json
from pathlib import Path

from runner import OpenRouter, Session
from runtime import Native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wisp", required=True)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--seed-snapshot", type=Path)
    parser.add_argument("--key-file", required=True, type=Path)
    args = parser.parse_args()
    native = Native(args.wisp, args.runtime, args.seed_snapshot)
    try:
        session = Session(native, OpenRouter(args.key_file.read_text(), .50), args.runtime / "sessions")
        checks = []

        def goal():
            return next((r["fields"].get("/app/goal") for r in session.records
                         if r["path"] == "/goals/release"), None)

        for name, ready in [("tests", True), ("approval", False)]:
            session.turn(external={"op": "make", "path": f"/release/{name}", "fields": {"ready": ready}})
        session.turn("Create a persistent goal at /goals/release: the release is ready when "
                     "/release/tests has ready true AND /release/approval has ready true. "
                     "Assess what holds now and keep watching so it reopens if either changes. "
                     "Those source records are external facts: only observe them; don't modify them.")
        g = goal()
        checks.append({"name": "model installed and assessed native goal", "pass": bool(g) and
                       not g["fulfilled"] and sorted(c["met"] for c in g["conditions"].values()) == [False, True]})
        session.turn(external={"op": "poke", "path": "/release/approval", "fields": {"ready": True}})
        checks.append({"name": "all conditions met yields native fulfillment", "pass": bool(goal()) and goal()["fulfilled"]})
        before = len(session.events)
        session.turn(external={"op": "poke", "path": "/release/tests", "fields": {"ready": False}})
        notices = [e["data"] for e in session.events[before:] if e["kind"] == "dependency"]
        checks.append({"name": "native notification contains reopened goal before model responds", "pass":
                       bool(notices) and not notices[0]["watcher_record"]["/app/goal"]["fulfilled"]})
        g = goal()
        checks.append({"name": "goal persists and only changed condition invalidates", "pass": bool(g) and
                       not g["fulfilled"] and sorted(c["met"] for c in g["conditions"].values()) == [False, True]})
        session.turn(external={"op": "poke", "path": "/release/tests", "fields": {"ready": True}})
        checks.append({"name": "reassessment fulfills same goal again", "pass": bool(goal()) and goal()["fulfilled"]})
        calls = session.metrics["calls"]
        session.turn(external={"op": "poke", "path": "/release/tests", "fields": {"ready": True}})
        checks.append({"name": "no-op leaves fulfilled goal asleep", "pass": session.metrics["calls"] == calls})
        checks.append({"name": "model never altered source facts", "pass": not any(
            e["kind"] == "operation" and e["data"].get("op") != "read" and
            e["data"].get("path", "").startswith("/release") for e in session.events)})
        report = {"pass": all(c["pass"] for c in checks), "checks": checks, "metrics": session.metrics}
        (args.runtime / "live-checks.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
        if not report["pass"]:
            raise SystemExit(1)
    finally:
        native.close()


if __name__ == "__main__":
    main()
