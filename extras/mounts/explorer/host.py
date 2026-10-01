import urllib.request
from pathlib import Path

def check(url, node, timeout):
    for path, expected in [('/views', 'Namespace'), ('/views/' + node + '/hello', '/sys/slot/synthetic'), ('/ns', 'sh-triptych'), ('/ns/' + node + '/hello', 'Hello from Eden.')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert expected in response.read().decode()
    with urllib.request.urlopen(url + '/style.css', timeout=timeout) as response:
        assert response.read()
    for path, mime in [('/static/goo-reference.css', 'text/css'),
                       ('/static/goo-fonts.css', 'text/css'),
                       ('/static/goo-Sans400.ttf', 'font/ttf')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert response.headers.get_content_type() == mime
            body = response.read()
            assert body
            if mime == 'font/ttf':
                assert body == (Path(__file__).parent / "goo-Sans400.ttf").read_bytes()
