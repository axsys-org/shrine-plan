"""Rebuildable navigation over explicit references. Never a dependency engine."""
from __future__ import annotations
from collections import defaultdict, deque
import base64
import json
from records import encoded, fields_of, digest

SOFT = {"related", "tags"}
LINKS = SOFT | {"anchors", "about", "evidence", "established_by", "origin_work", "parent", "triggered_by",
    "used", "produced", "revised", "predecessors", "successors", "supersedes", "derived_from",
    "generalizes", "specializes", "implemented_by", "relies_on", "must_preserve", "subjects"}


def references(value):
    if isinstance(value, dict):
        world = value.get("external_world", value.get("world"))
        if isinstance(value.get("path"), str) and value["path"].startswith("/"):
            yield value["path"], value.get("case"), world
        elif isinstance(value.get("path"), list) and all(isinstance(p, str) for p in value["path"]):
            yield "/" + "/".join(value["path"]), value.get("case"), world
        else:
            for v in value.values():
                yield from references(v)
    elif isinstance(value, list):
        for v in value:
            yield from references(v)


class Connections:
    def __init__(self, world_id=None):
        self.world_id = world_id
        self.records = {}
        self.edges = defaultdict(list)
        self.reverse = defaultdict(list)
        self.tags = defaultdict(set)
        self.version = 0

    def update(self, record, path=None):
        path = path or record["path"]
        if self.records.get(path) == record:
            return
        self.version += 1
        for edge in self.edges.pop(path, []):
            if not edge.get("external"):
                self.reverse[edge["to"]] = [e for e in self.reverse[edge["to"]] if e["from"] != path]
        for paths in self.tags.values():
            paths.discard(path)
        if record is None:
            self.records.pop(path, None)
            return
        self.records[path] = record
        fields = fields_of(record)
        for key, value in fields.items():
            if key in LINKS:
                for target, case, world in references(value):
                    self._edge(path, target, key, case, key in SOFT, world)
        for slot in record.get("slots", []):
            if isinstance(slot.get("value"), dict) and "$native" in slot["value"]:
                for target, case, world in references(slot["value"]):
                    if target != path:
                        self._edge(path, target, "native_value", case, False, world)
        if path != "/":
            self._edge(path, path.rsplit("/", 1)[0] or "/", "child_of", None, False)
        for dep in record.get("crew", []):
            self._edge(path, dep["path"], "crew", None, False)
        for target in record.get("behaviors", []):
            self._edge(path, target, "behavior", None, False)
        for tag in fields.get("tags", []) if isinstance(fields.get("tags"), list) else []:
            if isinstance(tag, str):
                self.tags[tag].add(path)

    def _edge(self, source, target, relation, case, soft, world=None):
        edge = {"from": source, "to": target, "relation": relation, "case": case, "tentative": soft}
        if world is not None:
            edge.update(world=world, external=world != self.world_id)
        self.edges[source].append(edge)
        if not edge.get("external"):
            self.reverse[target].append(edge)

    def ingest(self, event):
        for change in event.get("result", {}).get("changes", []):
            self.update(change.get("record"), change["path"])

    def context(self, subjects, cursor=0, limits=None, include_tags=False):
        limits = limits or {}
        count = min(100, max(1, limits.get("items", 12)))
        byte_limit = min(65536, max(512, limits.get("bytes", 12288)))
        query = digest([subjects, include_tags])
        offset = 0
        if cursor:
            try:
                page = json.loads(base64.urlsafe_b64decode(cursor))
                if page["version"] != self.version or page["query"] != query:
                    return {"items": [], "cursor": 0, "more": True, "error": "context_changed", "restart_cursor": 0}
                offset = page["offset"]
            except (ValueError, TypeError, KeyError):
                raise ValueError("Invalid context cursor; restart with cursor=0")
        queue = deque((p, []) for p in subjects)
        seen = {(p, None, None) for p in subjects}
        found = []
        reference_only = []
        while queue and len(seen) < 1000:
            here, route = queue.popleft()
            # Transparent namespace spines are navigation addresses, not
            # evidence that every sibling observation is semantically related.
            if route and here not in self.records:
                continue
            neighbors = [(e["to"], e) for e in self.edges.get(here, [])]
            neighbors += [(e["from"], {**e, "direction": "reverse"}) for e in self.reverse.get(here, [])]
            if include_tags:
                for tag in fields_of(self.records.get(here)).get("tags", []):
                    neighbors += [(p, {"from": here, "to": p, "relation": "shared_tag", "tag": tag,
                        "tentative": True}) for p in sorted(self.tags.get(tag, set()))]
            for target, edge in neighbors:
                foreign = edge.get("external", False)
                # An edge's case describes its destination, even when walking
                # in reverse. Never borrow current prose for historical support.
                case = edge.get("case") if edge.get("direction") != "reverse" else None
                identity = (target, edge.get("world") if foreign else None, case)
                if identity in seen:
                    continue
                seen.add(identity)
                next_route = route + [edge]
                record = None if foreign else self.records.get(target)
                if not record and edge["relation"] == "child_of":
                    continue
                historical = bool(record and case is not None and case != record.get("case"))
                if foreign or not record or historical:
                    reference_only.append({"path": target, "case": case,
                        "world": edge.get("world", self.world_id),
                        "category": "reference_only", "route": next_route, "summary": {},
                        "availability": "external_world" if foreign else "historical_reference" if historical else "unavailable"})
                    continue
                fields = fields_of(record)
                unresolved = bool(fields.get("question")) or fields.get("applicability") in {"UNESTABLISHED", "NEEDS_REVIEW"}
                tentative = unresolved or any(e["tentative"] for e in next_route)
                found.append({"path": target, "case": record.get("case") if record else None,
                    "category": "potentially_relevant_unfinished" if tentative else "established_connection",
                    "route": next_route, "summary": {k: fields[k] for k in
                        ("statement", "question", "applicability", "result", "summary") if k in fields}})
                if len(next_route) < 4:
                    queue.append((target, next_route))
        # Missing references remain inspectable, but do not displace available
        # knowledge or let transparent namespace spines connect unrelated work.
        found.extend(reference_only)
        selected = []
        for item in found[offset:]:
            if len(selected) == count or len(encoded(selected + [item]).encode()) > byte_limit:
                break
            selected.append(item)
        next_offset = offset + len(selected)
        token = base64.urlsafe_b64encode(encoded({"version": self.version, "query": query, "offset": next_offset}).encode()).decode()
        return {"items": selected, "cursor": token, "more": next_offset < len(found)}
