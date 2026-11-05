import urllib.request
from pathlib import Path


def check(url, node, timeout):
    with urllib.request.urlopen(url + '/live', timeout=timeout) as response:
        assert response.headers.get_content_type() == 'text/html'
        live_html = response.read().decode()
        assert 'id="live"' in live_html
    # the page names each asset with a hash of the file it was stamped from; the served file must hash the same,
    # or a browser that cached the old viewer keeps it (run version-assets.py after a change)
    import hashlib, re
    for name in ('goo-live.css', 'goo-live.js'):
        stamped = re.search(r'/static/%s\?v=([0-9a-f]+)' % re.escape(name), live_html)
        assert stamped, name + ' is not versioned in /live'
        # fetch exactly what the page asks for, query and all: a static route that ignores the query serves a 404 here
        with urllib.request.urlopen(url + stamped.group(0), timeout=timeout) as response:
            assert hashlib.sha256(response.read()).hexdigest()[:10] == stamped.group(1), name + ' served does not match its stamp'
    for path, mime in [('/static/goo-live.html', 'text/html'),
                       ('/static/goo-live.css', 'text/css'),
                       ('/static/goo-live.js', 'text/javascript')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            actual = response.headers.get_content_type()
            assert actual == mime or (mime == "text/javascript" and actual == "application/javascript")
            assert response.read() == (Path(__file__).parent / path.rsplit('/', 1)[1]).read_bytes()
