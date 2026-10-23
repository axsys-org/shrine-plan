"""Capture repository evidence through Eden's existing filesystem mount.

No work polling, model dispatch, document writes or flow lifecycle lives here.
"""
import json
import os
from pathlib import Path
import runpy
import shutil

capture_workspace = None

def scan(root, bag):
    repo = Path(os.environ.get('SHRINE_FLOW_SOURCE_ROOT') or capture_workspace or root.parents[2])
    capture = runpy.run_path(str(root / 'client.py'))['prepare']
    bundle = capture(repo, root / 'sources.json')
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
