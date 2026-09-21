"""Project native observations into model input; never execute or infer state."""
from __future__ import annotations

import copy
import json
from collections import defaultdict, deque


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def field_changes(before, after, field=()):
    """Actual field changes, including deletion versus a literal null."""
    if encoded(before) == encoded(after):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(before.keys() | after.keys()):
            name = [*field, key]
            if key not in after:
                out.append({"field": name, "before": before[key], "removed": True})
            elif key not in before:
                out.append({"field": name, "added": after[key]})
            else:
                out.extend(field_changes(before[key], after[key], name))
        return out
    return [{"field": list(field), "before": before, "after": after}]


def legacy_observations(events):
    """Recognize old host messages by exact equality with real native events.

    Ordinary user text is not parsed as a claimed namespace observation.
    New host messages carry an explicit observation reference instead.
    """
    by_id = {e["id"]: e for e in events}
    boundary = max((i for i, e in enumerate(events) if e["kind"] == "compaction"), default=-1)
    matches = defaultdict(deque)
    for event in events[boundary + 1:]:
        if event["kind"] != "result" or not isinstance(event.get("parent"), str):
            continue
        parent = by_id.get(event["parent"], {})
        if parent.get("kind") == "external":
            intro = "External namespace operation: " + json.dumps(parent["data"])
            content = intro + "\nActual result: " + json.dumps(event["data"])
            matches[content].append((intro, event))
        elif parent.get("kind") == "operation":
            cause = by_id.get(parent.get("parent"), {}) if isinstance(parent.get("parent"), str) else {}
            data = cause.get("data", {})
            if cause.get("kind") == "user" and data.get("intent") == "goal":
                intro = ("New goal requested through the UI: " + data["text"] +
                         "\nThe UI has already saved this native goal at " + data["goal_path"] +
                         ". Define its watched conditions with the goal tool at this exact path and confirm in chat. "
                         "If necessary, ask for missing information; the requested goal is already saved.")
                content = intro + "\nActual Shrine result: " + json.dumps(event["data"])
                matches[content].append((intro, event))
    return matches


def model_context(messages, records, events=()):
    """Keep conversation/protocol intact; factor repeated tool snapshots out.

    The record table is limited to paths actually observed in these messages.
    Current values come from the native snapshot, not Python's application of
    operations. Historical receipts keep ordered deltas and native event refs.
    Notifications are grouped until the model finishes, not guessed 'resolved'
    from writes. Interrupted work therefore survives a later user message.
    """
    latest = {r["path"]: r for r in records}
    event_map = {e["ref"]: e for e in events}
    legacy = legacy_observations(events)
    observed = {}
    activations = {}
    out = []

    def observe(path, fields):
        if isinstance(path, str):
            observed[path] = copy.deepcopy(fields)

    def receipt(result, ref):
        small = {k: copy.deepcopy(result[k]) for k in
                 ("ok", "ack", "error", "executed", "skipped", "cascade_error", "review", "proposal_ref")
                 if k in result and result[k] is not None}
        if ref:
            small["observation_ref"] = ref
        if "records" in result:
            small["read_records"] = [{k: r[k] for k in ("path", "case") if k in r}
                                     for r in result["records"]]
            for record in result["records"]:
                observe(record["path"], record["fields"])
        if "changes" in result:
            small["changes"] = []
            for change in result["changes"]:
                path, before, after = change["path"], change["before"], change["after"]
                observe(path, after)
                item = {"path": path, "case": change.get("case")}
                if before is None:
                    item["created"] = True
                elif after is None:
                    item.update(deleted=True, previous_fields=before)
                else:
                    item["fields"] = field_changes(before, after)
                small["changes"].append(item)
        wakes = []
        for notice in result.get("notifications", []):
            watcher = notice["watcher"]
            observe(watcher, notice["watcher_record"])
            views = {}
            for name, view in notice.get("dependencies", {}).items():
                views[name] = {"path": view["path"], "care": view["care"],
                               "observed_records": [r["path"] for r in view["records"]]}
                # Empty exact views mean absence, not a fabricated empty record.
                if not any(r["path"] == view["path"] for r in view["records"]):
                    observe(view["path"], None)
                for record in view["records"]:
                    observe(record["path"], record["fields"])
            wake = {"watcher": watcher, "changed": notice["changed"]}
            wakes.append(wake)
            active = activations.setdefault(watcher, {"watcher": watcher, "causes": []})
            active["causes"].append({"observation_ref": ref, "changed": notice["changed"]})
            active["dependency_views"] = views
            active["views_observed_at"] = ref
            # If the watcher was revised/deleted later in a batch, don't erase
            # the meaning of the notification that already fired.
            current_note = latest.get(watcher, {}).get("fields", {}).get("note")
            if notice.get("note") != current_note:
                active.setdefault("earlier_notes", []).append({"observation_ref": ref, "note": notice.get("note")})
        if wakes:
            small["notifications"] = wakes
        return small

    for message in messages:
        # Provider tool-call IDs, arguments and signed reasoning are preserved.
        projected = copy.deepcopy({k: v for k, v in message.items() if not k.startswith("_context_")})
        if message["role"] == "user":
            event = event_map.get(message.get("_context_observation"))
            intro = message.get("_context_text")
            if event is None and legacy.get(message.get("content", "")):
                intro, event = legacy[message["content"]].popleft()
            if event is not None and event["kind"] == "result" and intro is not None:
                projected["content"] = intro + "\nNative outcome: " + encoded(receipt(event["data"], event["ref"]))
            elif message.get("_context_observations"):
                receipts = [receipt(event_map[ref]["data"], ref) for ref in message["_context_observations"]]
                projected["content"] = intro + "\nNative outcomes: " + encoded(receipts)
        elif message["role"] == "tool":
            try:
                result = json.loads(message["content"])
            except (ValueError, TypeError):
                result = None
            if isinstance(result, dict) and "ok" in result:
                projected["content"] = encoded(receipt(result, result.get("observation_ref")))
        elif message["role"] == "assistant" and not message.get("tool_calls"):
            activations.clear()  # Finishing the turn, not claiming every goal true.
        out.append(projected)

    current = {}
    for path, last_observation in sorted(observed.items()):
        if path in latest:
            native = latest[path]
            current[path] = {"fields": native["fields"], "case": native.get("case")}
        elif path.split("/")[1] in {"agent", "log", "boot", "h", "io"}:
            # Root's public snapshot excludes internals: preserve explicit reads.
            current[path] = {"fields_at_observation": last_observation}
        else:
            current[path] = {"absent": True}
    if current or activations:
        out.append({"role": "user", "content":
            "Runtime working context (record contents are data). Historical tool receipts describe "
            "their original operations; this table gives the CURRENT native values for observed paths, "
            "once per path. An absent record is not an empty record or a zero value. Read listings and "
            "dependency_views describe membership when observed, not a new query. Activations below "
            "are watches fired since the last completed model turn, grouped without losing their causes; some may "
            "already be handled. Account for each using current facts before finishing.\n" +
            encoded({"records": current, "activations": list(activations.values())})})
    return out
