"""Verify atomic workspace publication against a disposable mount source bag.

Usage: python3 check-registration.py BASE_URL DISPOSABLE_DOCUMENTATION_BAG
The bag must be the selected server's source; never use a checkout with live edits.
"""
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

base, folder = sys.argv[1:]
folder = Path(folder).resolve()
if 'workspace-registration-extras' not in folder.parts:
    raise SystemExit('Use a disposable workspace-registration-extras source tree')
source_file, css_file = folder/'documentation.grove', folder/'style.css'
source, css = source_file.read_text(), css_file.read_text()
marker = 'workspace-atomic-publication-check'


def request(path, fields=None):
    data = None if fields is None else urllib.parse.urlencode(fields).encode()
    with urllib.request.urlopen(base + path, data=data, timeout=40) as response:
        return response.read().decode()


def status():
    data = json.loads(request('/grove/dev/status'))
    return next(unit for unit in data['units'] if unit['mount'] == 'goo-documentation')


def rescan():
    before = status()
    request('/grove/dev/rescan', dict(source=before['source'], scan=before['requested']))
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        current = status()
        if int(current['requested']) > int(before['requested']) and current['completed'] == current['requested']:
            return current
        time.sleep(.2)
    raise AssertionError('Rescan did not settle')


def page():
    html = request('/goo-documentation')
    assert 'data-workspace=' in html and 'data-description=' in html
    return html


try:
    baseline = status()
    assert baseline['ready']
    baseline_html = page()
    # Valid Grove, invalid *host* contract: an entry requiring external ports.
    source_file.write_text(source.replace('workspace =\n  @pane',
        'workspace =\n  @pane\n  #port ; /unconnected', 1))
    css_file.write_text(css + '\n/* ' + marker + ' */\n')
    failed = rescan()
    assert not failed['ready'], failed
    assert 'Workspace entry pane' in failed['diagnostic'], failed
    assert marker not in request('/goo-documentation/style.css')
    assert page() == baseline_html
    print('PASS: invalid compiled entry preserves the previous workspace and assets')
    source_file.write_text(source)
    accepted = rescan()
    assert accepted['ready'], accepted
    assert marker in request('/goo-documentation/style.css')
    page()
    print('PASS: repaired source publishes and serves its new asset bundle')
finally:
    source_file.write_text(source)
    css_file.write_text(css)
    # Keep the verification server at the checked-in source after the test.
    final = rescan()
    assert final['ready'], final
