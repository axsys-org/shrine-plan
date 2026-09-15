"""Shared startup verdicts; compiler self-tests may print caught errors."""
import re
import hashlib
import json

ASSET_PATHS = frozenset(('debug.js', 'debug.css', 'style.css', '.debug-assets/mash.js', '.debug-assets/components.css'))


def verify_asset_build(root):
    manifest = root / 'build.json'
    if not manifest.is_file():
        raise RuntimeError('Build native assets first: MASH_ROOT=/path/to/mash node x/build-debug.mjs')
    build = json.loads(manifest.read_text())
    if build.get('mode') != 'grove' or set(build.get('assets', {})) != ASSET_PATHS:
        raise RuntimeError('Expected a complete Grove asset build, not a legacy or partial bundle.')
    for relative, digest in build['assets'].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Asset differs from its build provenance: ' + relative)
    return build


def startup_failed(output, returned_marker):
    # Try returns (0 value) on success and (1 reason) on failure. Eden's entry
    # returns its spawned supervisor actor ID before the HTTP foot listens.
    # Success is not readiness: the caller must still prove the live listener.
    return bool(re.search(r'^\("ERROR"(?:\s|\))', output, re.M)
                or re.search(r'^\("' + re.escape(returned_marker) + r'"\s+\(1(?:\s|\))', output, re.M)
                or 'pump: listen failed' in output or 'bind/listen failed' in output)
