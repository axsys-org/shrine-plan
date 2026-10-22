#!/usr/bin/env python3
"""Export a harness-only baseline plus frozen Branchmap inputs into a new directory."""
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

HARNESS = 'aae7cfa49ada19d066905d9e9e88347bc4064bde'
INPUT_COMMIT = '91b8257282fee78472e6eab248abd53e16856c49'
PREFIX = 'extras/experiments/branchmap/'


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def prepare(repo, destination, revision):
    commit = git(repo, 'rev-parse', revision + '^{commit}').decode().strip()
    inputs = git(repo, 'rev-parse', INPUT_COMMIT + '^{commit}').decode().strip()
    paths = git(repo, 'ls-tree', '-r', '--name-only', commit).decode().splitlines()
    if any(p.startswith(('extras/experiments/branchmap/', 'extras/experiments/branchmap-hands/', 'extras/mounts/branchmap/')) for p in paths):
        raise SystemExit('Choose a harness-only revision; this revision includes a previous application.')
    destination.mkdir(parents=True, exist_ok=False)
    archive = git(repo, 'archive', commit)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter='data')
    chosen = git(repo, 'ls-tree', '-r', '--name-only', inputs, '--', PREFIX + 'data', PREFIX + 'source/branchmap.pdf').decode().splitlines()
    if not chosen:
        raise SystemExit('Frozen inputs are missing from the repository.')
    hashes = {}
    for source in chosen:
        relative = source.removeprefix(PREFIX)
        relative = relative.replace('source/branchmap.pdf', 'branchmap.pdf')
        target = destination / 'inputs' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = git(repo, 'show', inputs + ':' + source)
        target.write_bytes(data)
        hashes[str(target.relative_to(destination))] = hashlib.sha256(data).hexdigest()
    brief = Path(__file__).resolve().parents[1] / 'references/experiment.md'
    (destination / 'EXPERIMENT.md').write_bytes(brief.read_bytes())
    manifest = dict(harness_commit=commit, input_commit=inputs, input_sha256=hashes,
                    model='record at run start', reasoning='record at run start',
                    goo_egui_commit='record at run start', prior_exposure='record at run start')
    (destination / 'experiment-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    subprocess.run(['git', 'init', '-q', str(destination)], check=True)
    print(json.dumps(dict(directory=str(destination), harness_commit=commit, input_files=len(hashes)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--revision', default=HARNESS)
    args = parser.parse_args()
    prepare(args.repository.resolve(), args.destination.resolve(), args.revision)
