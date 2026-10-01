import subprocess
import urllib.request
from pathlib import Path


def prepare(root, work, check, cleanup, context):
    bag = work / 'bag'
    bag.mkdir(parents=True)
    for source in root.iterdir():
        if source.is_file():
            (bag / source.name).symlink_to(source)
    subprocess.run(['nix', '--extra-experimental-features', 'nix-command flakes',
                    'develop', '--no-update-lock-file', f'path:{root.parent.parent}#debugger',
                    '--command', 'node', str(root / 'build-topoi.mjs'), str(bag)], check=True)
    return bag, []


def check(url, node, timeout):
    for path, expected in [('/views', 'Namespace'), ('/views/' + node + '/hello', '/sys/slot/synthetic'), ('/ns', 'sh-triptych'), ('/ns/' + node + '/hello', 'Hello from Eden.')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            assert expected in response.read().decode()
    with urllib.request.urlopen(url + '/style.css', timeout=timeout) as response:
        assert response.read()
    for path, mime in [('/static/goo-reference.css', 'text/css'),
                       ('/static/goo-fonts.css', 'text/css'),
                       ('/static/goo-topoi-components.js', 'text/javascript'),
                       ('/static/goo-topoi-components.css', 'text/css'),
                       ('/static/goo-topoi.js', 'text/javascript'),
                       ('/static/goo-Sans400.ttf', 'font/ttf')]:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            actual = response.headers.get_content_type()
            assert actual == mime or (mime == "text/javascript" and actual == "application/javascript")
            body = response.read()
            assert body
            if mime == 'font/ttf':
                assert body == (Path(__file__).parent / "goo-Sans400.ttf").read_bytes()
