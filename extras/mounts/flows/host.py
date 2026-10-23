"""Capture repository evidence through Eden's existing filesystem mount.

No work polling, model dispatch, document writes or flow lifecycle lives here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


def validate_bundle(bundle):
    """Accept a replay only when the source bytes still match its captured hashes."""
    sources = bundle['sources']
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 64:
        raise ValueError('bundle must contain between 1 and 64 named sources')
    for name, source in sources.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
            raise ValueError('invalid source name: ' + name)
        if set(source) != {'location', 'title', 'digest', 'format', 'content'} or not all(
                isinstance(value, str) for value in source.values()):
            raise ValueError('incomplete source envelope: ' + name)
        raw = source['content'].encode('utf-8')
        if not source['location'] or not 0 < len(raw) <= 131072:
            raise ValueError('invalid source size or location: ' + name)
        if hashlib.sha256(raw).hexdigest() != source['digest']:
            raise ValueError('source digest mismatch: ' + name)
    encoded = json.dumps(sources, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(encoded) > 1500000:
        raise ValueError('source inventory exceeds the client materialization budget')
    if hashlib.sha256(encoded).hexdigest() != bundle['digest']:
        raise ValueError('bundle digest mismatch')
    return bundle


def capture_sources(repo, manifest):
    """Capture the complete declared inventory before publishing scan output."""
    repo = Path(repo).resolve()
    entries = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 64:
        raise ValueError('manifest must contain between 1 and 64 named sources')
    sources = {}
    for name, entry in sorted(entries.items()):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
            raise ValueError('invalid source name: ' + name)
        path = (repo / entry['path']).resolve()
        if not path.is_relative_to(repo):
            raise ValueError('source escapes repository: ' + entry['path'])
        raw = path.read_bytes()
        if not 0 < len(raw) <= 131072:
            raise ValueError('source must contain 1..131072 bytes: ' + entry['path'])
        sources[name] = dict(location=entry['path'], title=entry.get('title', name),
                             digest=hashlib.sha256(raw).hexdigest(),
                             format=path.suffix.lstrip('.') or 'text',
                             content=raw.decode('utf-8'))
    encoded = json.dumps(sources, ensure_ascii=False, sort_keys=True).encode('utf-8')
    if len(encoded) > 1500000:
        raise ValueError('source inventory exceeds the client materialization budget')
    return validate_bundle({'digest': hashlib.sha256(encoded).hexdigest(), 'sources': sources})


capture_workspace = None


def scan(root, bag):
    repo = Path(os.environ.get('SHRINE_FLOW_SOURCE_ROOT') or capture_workspace or root.parents[2])
    bundle = capture_sources(repo, root / 'sources.json')
    for path in root.iterdir():
        if path.is_file():
            shutil.copyfile(path, bag / path.name)
    (bag / 'repository-evidence.json').write_text(
        json.dumps(bundle['sources'], ensure_ascii=False), encoding='utf-8')


def prepare(root, work, check, cleanup, context):
    global capture_workspace
    capture_workspace = context.get('workspace')
    bag = work / 'flows' / 'bag'
    bag.mkdir(parents=True)
    scan(root, bag)
    return bag, []
