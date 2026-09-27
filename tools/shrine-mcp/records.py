"""Wire encoding only. Slots are opaque paths; Foil owns their meaning."""
from __future__ import annotations

import hashlib
import json

PROTOCOL = 5


def validate_text(value):
    """Native text cords cannot contain a zero byte; reject before journaling."""
    if isinstance(value, str) and '\0' in value:
        raise ValueError('Native text cannot contain NUL. Retain binary content in an artifact or a native byte value; observation values do this automatically.')
    if isinstance(value, dict):
        for k, v in value.items():
            validate_text(k); validate_text(v)
    elif isinstance(value, list):
        for v in value: validate_text(v)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def path_parts(path):
    if isinstance(path, list):
        parts = path
    elif isinstance(path, str) and path.startswith("/"):
        parts = [] if path == "/" else path[1:].split("/")
    else:
        raise ValueError("Expected an absolute namespace path or an explicit segment array")
    auras = {"dm", "dr", "ds", "f", "r", "rd", "rs", "s", "ta", "ts", "tu", "u", "w", "x"}
    def valid(p):
        return isinstance(p, str) or (isinstance(p, dict) and set(p) == {"tag", "value"}
            and p["tag"] in auras and type(p["value"]) is int and p["value"] >= 0)
    if len(parts) > 128 or not all(valid(p) for p in parts):
        raise ValueError("Path segments require text or {tag: native aura, value: natural}; maximum depth 128")
    return parts


def slot_parts(key):
    # Explicit arrays preserve a single 'a/b' slot versus the two-part ['a','b'].
    return path_parts(key) if isinstance(key, list) or key.startswith("/") else [key]


def slots_of(fields=None, slots=None):
    if fields is not None and slots is not None:
        raise ValueError("Supply fields or explicit slots, not both")
    result = slots if slots is not None else [
        {"key": slot_parts(k), "value": v} for k, v in (fields or {}).items()]
    for slot in result:
        if set(slot) != {"key", "value"}:
            raise ValueError("Each slot requires key (segment array) and value")
        path_parts(slot["key"])
    encoded(result)
    return result


def fields_of(record):
    if not record:
        return {}
    return {(s["key"][0] if len(s["key"]) == 1 else "/" + "/".join(s["key"])): s["value"]
            for s in record.get("slots", []) if s["key"] and all(isinstance(k, str) for k in s["key"])}


def checked(result):
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Native operation failed"))
    return result


def ref(path, case=None):
    result = {"path": path}
    if case is not None:
        result["case"] = case
    return result


def scope_result(result, world_id):
    """Add transport identity to references, without changing literal slot data."""
    def visit(value):
        if isinstance(value, list):
            return [visit(v) for v in value]
        if not isinstance(value, dict):
            return value
        if '$native' in value:
            return {'$native': {**value['$native'], 'world': value['$native'].get('world', world_id)}}
        if 'slots' in value:
            out = {k: visit(v) for k,v in value.items() if k != 'slots'}
            out['slots'] = [{**s, 'ref': visit(s.get('ref')), 'value':
                s['value'] if s.get('type') == '/boot/shadow/literal' else visit(s['value'])}
                for s in value['slots']]
            return out
        return {k: visit(v) for k,v in value.items()}
    return visit(result)


def check_world(value, world_id):
    if isinstance(value, dict) and '$native' in value:
        origin = value['$native'].get('world')
        if origin is not None and origin != world_id:
            raise ValueError('Native value belongs to another world; target-specific establishment or explicit import is required')


def prepare_value(value, world_id):
    check_world(value, world_id)
    if not isinstance(value, dict): return value
    for kind in ('$native', '$record'):
        if kind not in value: continue
        reference = value[kind]
        if not isinstance(reference, dict) or 'path' not in reference:
            raise ValueError(kind + ' requires a path and immutable case')
        if type(reference.get('case')) is not int or reference['case'] < 1:
            raise ValueError(kind + ' requires a positive historical case')
        if reference.get('world', world_id) != world_id:
            raise ValueError('Historical reference belongs to another world')
        normalized = {**reference, 'path': path_parts(reference['path'])}
        if kind == '$native':
            if 'slot' not in reference: raise ValueError('$native requires its original slot')
            normalized['slot'] = slot_parts(reference['slot'])
        return {kind: normalized}
    return value
