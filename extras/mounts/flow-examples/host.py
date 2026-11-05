"""Stage declared source bytes for Eden's existing filesystem capture foot.

No evidence envelopes, hashing, polling or flow execution live in the host.
"""
import json
import os
from pathlib import Path
import shutil


capture_workspace = None


def scan(root, bag):
    repo = Path(os.environ.get('SHRINE_FLOW_SOURCE_ROOT') or capture_workspace or root.parents[2]).resolve()
    staged = {path.name: path for path in root.iterdir() if path.is_file()}
    staged.update({path.name: path for path in (root / 'examples').glob('*.semidoc')})
    catalogue = root / 'examples.json'
    examples = json.loads(catalogue.read_text()) if catalogue.is_file() else {}
    source_files = set()
    for example in examples.values():
        for spec in example.get('sources', {}).values():
            leaf = spec['file']
            if not leaf or Path(leaf).name != leaf or leaf in ('.', '..'):
                raise ValueError('Source files must have flat names: ' + leaf)
            source = (repo / spec['path']).resolve()
            if not source.is_relative_to(repo):
                raise ValueError('Source escapes workspace: ' + spec['path'])
            if leaf in staged and (leaf not in source_files or staged[leaf] != source):
                raise ValueError('Different source files must have distinct names: ' + leaf)
            source_files.add(leaf)
            staged[leaf] = source
    present = set()
    for leaf, source in staged.items():
        try:
            shutil.copyfile(source, bag / leaf)
            present.add(leaf)
        except OSError:
            # Missing/unreadable bytes must disappear from the current scan.
            # Native capture history and attempts remain owned by the world.
            if leaf not in source_files:
                raise
    for path in bag.iterdir():
        if path.is_file() and path.name not in present:
            path.unlink()


def prepare(root, work, check, cleanup, context):
    global capture_workspace
    capture_workspace = context.get('workspace')
    bag = work / 'flow-examples' / 'bag'
    bag.mkdir(parents=True)
    scan(root, bag)
    return bag, []
