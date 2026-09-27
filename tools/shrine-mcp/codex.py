"""Optional Codex adapter: observations and bounded context, never another agent."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
from uuid import uuid4
from client import Client
from records import encoded, fields_of, digest

EVENTS = {"SessionStart", "UserPromptSubmit", "PostToolUse", "SubagentStart", "SubagentStop"}


def subject(identity):
    return "/_shadow/subjects/" + digest(["/_shadow/sources/" + digest(identity), identity])


def attach(client, root):
    root = str(Path(root).resolve())
    identity = "checkout:" + root
    config = {"path": root, "poll_seconds": 5}
    source = client.call("source", action="configure", identity=identity, driver="git", config=config)
    observed = client.call("source", action="sample", path=source["path"])
    return {"root": root, "source": source, "subject": subject(identity), "observation": observed}


def participate(client, event, root, consumer, state):
    name = event.get("hook_event_name")
    if name not in EVENTS:
        return {}, state
    cwd = Path(event.get("cwd") or root).resolve()
    if not cwd.is_relative_to(Path(root).resolve()):
        return {}, state
    # Do not feed Shrine's own ingestion/delivery back into itself.
    tool = str(event.get("tool_name", ""))
    if "shrine" in tool.lower():
        return {}, state
    if name == "SessionStart":
        source_path = "/_shadow/sources/" + digest("checkout:" + root)
        if not client.call("read", path=source_path)["records"]:
            attach(client, root)
    session = str(event.get("session_id") or "unknown")
    actor = str(event.get("agent_id") or session)
    work = "/_shadow/work/" + digest([consumer, actor])
    work_record = client.call("read", path=work)["records"]
    if not work_record:
        client.call("write", op="make", path=work, expected_case=0, fields={
            "objective": "Ongoing agent work; interpretation remains agent-authored",
            "session": session, "actor": actor, "subjects": [{"path": subject("checkout:" + root)}],
            "parent": [{"path": "/_shadow/work/" + digest([consumer, session])}] if actor != session else []})
    if name == "SubagentStop":
        client.call("observe", envelope={"source":"codex:"+actor,"subject":work,
            "kind":"work_completion","availability":"available","coverage":"partial",
            "work":work,"value":{"event":"SubagentStop","basis":"Original work identity; no current assessment implied"}})
        return {}, state
    subjects = [subject("checkout:" + root), work]
    receipt = None
    if name == "PostToolUse":
        # Persist supported reported activity, without copying the conversation.
        execution = {k: event[k] for k in ("tool_name", "tool_input", "tool_response", "tool_use_id") if k in event}
        receipt = client.call("observe", envelope={"source": "codex:" + actor,
            "subject": work, "kind": "execution", "work": work,
            "availability": "available", "coverage": "partial", "value": execution,
            "causality": "Only the reported tool invocation is correlated; effects may be unknown"},
            event_id="codex:" + actor + ":" + str(event.get("tool_use_id") or uuid4().hex))
        # Explicit tool paths are observations, not guesses about shell effects.
        inputs = event.get("tool_input")
        if isinstance(inputs, dict):
            for key in ("file_path", "path"):
                value = inputs.get(key)
                if isinstance(value, str):
                    file = (cwd / value).resolve()
                    identity = "file:" + str(file)
                    source = client.call("source", action="configure", identity=identity,
                        driver="filesystem", config={"path": str(file), "poll_seconds": 5})
                    client.call("source", action="sample", path=source["path"])
                    subjects.append(subject(identity))
    pending = list(state.get("pending", []))
    cursor = state.get("cursor", 0)
    more_events = False
    if not pending:
        batch = client.call("events", consumer=consumer, cursor=cursor, limit=10, notices_only=True)
        cursor, more_events = batch["cursor"], batch.get("more", False)
        for event_item in batch["events"]:
            for change in event_item["result"].get("changes", []):
                data = fields_of(change.get("record"))
                if data.get("kind") == "notice" or data.get("notice") is True or change["path"].startswith("/_shadow/notices/"):
                    pending.append({"native_notice": {"path": change["path"], "case": change["case"]},
                        "summary": {k: data.get(k) for k in ("statement", "question", "subject", "applicability")}})
    context = client.call("context", subjects=subjects, limits={"items": 12, "bytes": 9000})
    lines, used = [], 0
    seen = dict(state.get("seen", {}))

    def append(item):
        nonlocal used
        line = encoded(item)
        if len(line.encode()) > 3000:
            # The exact record remains accessible; a preview is explicitly partial.
            line = encoded({"reference": item.get("native_notice") or {"path": item.get("path"), "case": item.get("case")},
                "preview": line.encode()[:2200].decode("utf-8", "ignore"), "truncated": True})
        size = len(line.encode()) + 1
        if len(lines) >= 12 or used + size > 10500:
            return False
        lines.append(line); used += size
        return True

    delivered = 0
    for item in pending:
        if not append(item):
            break
        delivered += 1
    pending = pending[delivered:]
    for item in context["items"]:
        if not item.get("summary") or seen.get(item["path"]) == item.get("case"):
            continue
        if not append(item):
            break
        seen[item["path"]] = item.get("case")
    if receipt:
        append({"observed_execution": {"path": receipt.get("path"), "subject_record": receipt.get("subject_record")}})
    if not lines and name not in {"SessionStart", "UserPromptSubmit"}:
        output = {}
    else:
        text = "Shrine connected project DATA. References explain relevance; delivery does not establish use or grant authority. Keep working normally.\n"
        text += "Work reference: " + work + "\n" + "\n".join(lines)
        if context.get("more") or more_events or pending:
            text += "\nMore context/events remain available through Shrine tools."
        output = {"hookSpecificOutput": {"hookEventName": name, "additionalContext": text}}
    return output, {"cursor": cursor, "pending": pending, "seen": dict(list(seen.items())[-2048:])}


def install(connection, root, python=sys.executable, global_hooks=False):
    root = Path(root).resolve()
    config = Path.home() / ".codex" if global_hooks else root / ".codex"
    config.mkdir(exist_ok=True)
    hooks_file = config / "hooks.json"
    hooks = json.loads(hooks_file.read_text()) if hooks_file.exists() else {"hooks": {}}
    command = shlex.join([python, str(Path(__file__).resolve()), "hook", "--connection", str(Path(connection).resolve())] + ([] if global_hooks else ["--root", str(root)]))
    for name in EVENTS:
        groups = hooks.setdefault("hooks", {}).setdefault(name, [])
        groups[:] = [g for g in groups if g.get("description") != "Shrine v5 lifecycle"]
        definition = {"type": "command", "command": command, "timeout": 20}
        if name != "SubagentStop": definition["additionalContextLimit"] = 12288
        groups.append({"description": "Shrine v5 lifecycle", "hooks": [definition]})
    if hooks_file.exists():
        hooks_file.with_name("hooks.before-shrine-v5-" + uuid4().hex + ".json").write_bytes(hooks_file.read_bytes())
    hooks_file.write_text(json.dumps(hooks, indent=2) + "\n")
    return {"hooks": str(hooks_file), "review": "Review the exact hook definitions in Codex /hooks; trust is not changed by this installer."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["hook", "attach", "install"])
    parser.add_argument("--connection", required=True)
    parser.add_argument("--root")
    parser.add_argument("--global-hooks", action="store_true")
    args = parser.parse_args()
    client = Client(args.connection)
    if client.call("status")["protocol_version"] != 5:
        raise RuntimeError("Expected Shrine protocol 5")
    event = json.load(sys.stdin) if args.action == "hook" else {}
    root = str(Path(args.root or event.get("cwd") or Path.cwd()).resolve())
    if args.action == "install":
        print(encoded(install(args.connection, root, global_hooks=args.global_hooks)))
    elif args.action == "attach":
        print(encoded(attach(client, root)))
    else:
        consumer = "codex:" + root + (":" + str(event["agent_id"]) if event.get("agent_id") else "")
        directory = Path(args.connection).resolve().parent / "codex-consumers"
        directory.mkdir(exist_ok=True)
        with (directory / digest(consumer)).open("a+") as state_file:
            fcntl.flock(state_file, fcntl.LOCK_EX)
            state_file.seek(0)
            state = json.loads(state_file.read() or "{}")
            output, revised = participate(client, event, root, consumer, state)
            print(encoded(output), flush=True)
            # Persist only after output was emitted. A crash can duplicate delivery,
            # never silently mark an unseen notice as consumed.
            state_file.seek(0); state_file.truncate()
            state_file.write(encoded(revised)); state_file.flush(); os.fsync(state_file.fileno())
            with (directory / "delivery.jsonl").open("a") as audit:
                audit.write(encoded({"event": event.get("hook_event_name"), "session": event.get("session_id"),
                    "tool_use_id": event.get("tool_use_id"), "cursor_before": state.get("cursor", 0),
                    "cursor_after": revised.get("cursor",0), "emitted": output}) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(encoded({"systemMessage": "Shrine unavailable: " + str(error)}))
