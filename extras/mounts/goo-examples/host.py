"""Check every adapted fixture through the real namespace view route."""
import json
from pathlib import Path
import urllib.request
from html.parser import HTMLParser

class Previews(HTMLParser):
    def __init__(self):
        super().__init__()
        self.previews = 0
        self.errors = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'goo-preview' in attrs.get('class', '').split():
            self.previews += 1
        if 'error' in attrs.get('class', '').split():
            self.errors += 1

def check(url, node, timeout):
    manifest = json.loads((Path(__file__).parent / 'adaptations.json').read_text())
    objects = {}
    for entry in manifest:
        objects[entry['object']] = objects.get(entry['object'], 0) + 1
    for index, (path, expected) in enumerate(objects.items()):
        with urllib.request.urlopen(f'{url}/views/{node}{path}', timeout=timeout) as response:
            html = response.read().decode()
        parsed = Previews()
        parsed.feed(html)
        assert parsed.errors == 0, f'{path}: renderer error in {html}'
        assert parsed.previews == expected, f'{path}: expected {expected} views, got {parsed.previews}'
        if (index + 1) % 20 == 0:
            print(f'Checked {index + 1}/{len(objects)} objects', flush=True)
    print(f'PASS: {len(manifest)} views across {len(objects)} objects', flush=True)
