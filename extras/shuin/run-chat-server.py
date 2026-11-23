#!/usr/bin/env python3
"""Boot the in-tree Shrine mount; destructive fixtures are explicitly opt-in."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reaver', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--port', type=int, default=8267)
    parser.add_argument('--with-mcp', action='store_true')
    parser.add_argument('--test-fixtures', action='store_true')
    parser.add_argument('--without-search-index', action='store_true',
                        help='Disposable benchmark control; requires --test-fixtures')
    args = parser.parse_args()
    if args.without_search_index and not args.test_fixtures:
        parser.error('--without-search-index requires --test-fixtures')
    repo = args.reaver.resolve()
    extras = Path(__file__).resolve().parent.parent
    mount = 'shuin-chat-test' if args.test_fixtures else 'shuin-chat'

    def command(source):
        return [sys.executable, str(repo / 'x/eden'), '--extras-root', str(source),
                '--mount', mount, *(['--mount', 'mcp'] if args.with_mcp else []),
                '--port', str(args.port)]

    if not args.without_search_index:
        os.execv(sys.executable, command(extras))
    # Overlay only the application mount; preserve the canonical extras Nix
    # environment and dependency mounts. Never modify the production activation.
    with tempfile.TemporaryDirectory(prefix='shuin-control-') as directory:
        overlay = Path(directory)
        for item in extras.iterdir():
            if item.name != 'mounts':
                (overlay / item.name).symlink_to(item, target_is_directory=item.is_dir())
        (overlay / 'mounts').mkdir()
        for item in (extras / 'mounts').iterdir():
            if item.name == 'shuin-chat':
                shutil.copytree(item, overlay / 'mounts' / item.name)
            else:
                (overlay / 'mounts' / item.name).symlink_to(item, target_is_directory=item.is_dir())
        activation = overlay / 'mounts/shuin-chat/activation.foil'
        text = activation.read_text()
        anchor = '| namespace_search/install next'
        if text.count(anchor) != 1:
            raise RuntimeError('Search installation anchor changed; refusing benchmark overlay')
        activation.write_text(text.replace(anchor, '| ./ok next'))
        child = subprocess.Popen(command(overlay))
        import signal
        def stop(*_):
            child.terminate()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            status = child.wait()
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait()
        if status not in (0, 130, 143, -signal.SIGTERM, -signal.SIGINT):
            raise SystemExit(status)


if __name__ == '__main__':
    main()
