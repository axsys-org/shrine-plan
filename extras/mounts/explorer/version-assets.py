#!/usr/bin/env python3
"""Stamp goo-live.html's asset references with a hash of each file (?v=<sha256 prefix>), so a browser that cached the
old viewer fetches the new one after a change. Run after editing goo-live.js or goo-live.css; host.py checks the stamps
match the files served, so a forgotten run fails the check instead of showing a stale page.

    python3 extras/mounts/explorer/version-assets.py
"""
import hashlib, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = ['goo-live.css', 'goo-live.js']


def stamp(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()[:10]


def stamped_html():
    html = (HERE / 'goo-live.html').read_text()
    for name in ASSETS:
        html = re.sub(r'(/static/%s)(\?v=[0-9a-f]+)?' % re.escape(name), r'\1?v=' + stamp(name), html)
    return html


def main(check=False):
    html = stamped_html()
    current = (HERE / 'goo-live.html').read_text()
    if check:
        if html != current:
            print('goo-live.html is stale: run version-assets.py'); return 1
        print('goo-live.html stamps match'); return 0
    (HERE / 'goo-live.html').write_text(html)
    print('stamped', ', '.join('%s?v=%s' % (n, stamp(n)) for n in ASSETS))
    return 0


if __name__ == '__main__':
    sys.exit(main(check='--check' in sys.argv))
