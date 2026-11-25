#!/usr/bin/env python3
"""Rebuild the calculator page and refresh this mount's assets.

  python3 extras/mounts/gematria/build-web.py

Builds web/frontend with Vite (npm install on first run), copies the output
into this flat bag as web-* files, and rewrites mount.json's "assets" to
match. Then rescan the mount (or restart Eden) and reload the page.
"""
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTEND = HERE / 'web' / 'frontend'


def main():
    if not (FRONTEND / 'node_modules').is_dir():
        subprocess.run(['npm', 'install', '--no-audit', '--no-fund'], cwd=FRONTEND, check=True)
    subprocess.run(['npx', 'vite', 'build'], cwd=FRONTEND, check=True)
    dist = FRONTEND / 'dist'
    for old in HERE.glob('web-*'):
        old.unlink()
    assets = {}
    for path in sorted(p for p in dist.rglob('*') if p.is_file()):
        relative = path.relative_to(dist).as_posix()
        leaf = 'web-' + relative.replace('/', '-')
        shutil.copyfile(path, HERE / leaf)
        if relative == 'index.html':
            assets['/gematria'] = leaf
            assets['/gematria/'] = leaf
        else:
            assets['/gematria/' + relative] = leaf
    manifest_path = HERE / 'mount.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['assets'] = assets
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('assets:', ', '.join(sorted(assets)))


if __name__ == '__main__':
    main()
