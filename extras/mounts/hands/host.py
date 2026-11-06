"""The hands mount's host hook: each world keeps its own hands, in <world>/hands/hands.foil.

The kit and the mount module come from this folder; the world's hands.foil is its own (started from the empty one
here the first time). A rescan copies this folder and then the world's, so the world's hands.foil is what compiles.
"""
import shutil
from pathlib import Path


def prepare(root, work, check, cleanup, context):
    root = Path(root)
    # work is <world>/session-…/hands; the world's own folder outlives the session
    own = Path(work).parent.parent / 'hands'
    own.mkdir(exist_ok=True)
    for name in ('mount.json', 'hands_kit.foil', 'hands_mount.foil'):
        shutil.copyfile(root / name, own / name)
    if not (own / 'hands.foil').is_file():
        shutil.copyfile(root / 'hands.foil', own / 'hands.foil')
    return own, ['/' + context['node'] + '/app/hands']


def scan(root, prepared):
    root, prepared = Path(root), Path(prepared)
    for name in ('mount.json', 'hands_kit.foil', 'hands_mount.foil'):
        shutil.copyfile(root / name, prepared / name)
