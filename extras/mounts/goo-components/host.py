"""Exercise the published components through the ordinary Goo render boundary."""
import json
import hashlib
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


CASES = {
    "heading": ("copy", "heading"), "paragraph": ("prose", "paragraph"),
    "caption": ("copy", "caption_text"), "code": ("code", "code"),
    "rich-text": ("rich", "rich_text"), "badge": ("badge", "badge"),
    "status": ("status", "status"), "metadata": ("metadata", "metadata"),
    "identity": ("person", "identity"), "card": ("article", "card"),
    "compact-card": ("article", "compact_card"), "empty-state": ("empty", "empty_state"),
    "text-field": ("field", "text_field"), "rich-editor": ("rich", "rich_editor"),
    "image": ("photo", "image"), "figure": ("photo", "figure"),
}


def check(url, node, timeout):
    node = str(node).strip('/')
    def get(path):
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            return response.read().decode()

    for key, (subject, view) in CASES.items():
        assert 'data-goo-surface' in get('/goo-components?component=' + key), key
        for width, scale, direction in [(320, 1, 'ltr'), (720, 1, 'ltr'), (640, 2, 'rtl')]:
            selector = ({'slot': '/sys/slot/components/' + key.replace('-', '_')}
                        if width == 720 else {'view': f'/{node}/gov/goo_components/{view}'})
            query = urllib.parse.urlencode(dict(target=f'/{node}/app/goo_components/{subject}',
                **selector, width=width, textScale=scale, direction=direction))
            with urllib.request.urlopen(url + '/goo/render', data=query.encode(), timeout=timeout) as response:
                rendered = json.load(response)
            display = rendered['display']
            assert display['nodes'], (key, rendered)
            assert display['context']['textScale'] == scale
            assert display['context']['direction'] == direction
            controls = rendered['controls']
            if key in ('text-field', 'rich-editor'):
                assert any(c['kind'] == 'input' for c in controls), key
                assert any(c['kind'] == 'action' and c['invoke'] for c in controls), key
            else:
                assert not controls, (key, controls)
            if key == 'rich-editor':
                assert display['version'] == 3
                editor = next(n for n in display['nodes'] if 'editing' in n)
                assert editor['editing']['encoding'] == 'goo-text-v1'
            if key == 'rich-text':
                assert any('/sys/link' in r['myth'] for n in display['nodes'] for r in n['textRuns'])
            if key in ('image', 'figure'):
                images = [n for n in display['nodes'] if 'src' in n]
                assert len(images) == 1
                assert images[0]['src'] == '/goo-components/sculpture.jpg'
                assert images[0]['semantics']['label'] == 'Clay sculpture with multiple human faces, held in a workshop.'
                assert images[0]['config']['aspectRatio'] == 1
                box = images[0]['box']
                assert box['width'] > 0 and abs(box['width'] - box['height']) < 0.01, (key, box)
                assert 'alt="Clay sculpture' in rendered['html']
    original = Path(__file__).with_name('sculpture.jpg').read_bytes()
    with urllib.request.urlopen(url + '/goo-components/sculpture.jpg', timeout=timeout) as response:
        assert response.headers.get_content_type() == 'image/jpeg'
        assert hashlib.sha256(response.read()).digest() == hashlib.sha256(original).digest()
    for query in ['component=missing', 'component=card&component=heading', 'view=card']:
        try:
            get('/goo-components?' + query)
        except urllib.error.HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError('Invalid catalog selection accepted: ' + query)
    print(f'PASS: {len(CASES)} components, {len(CASES)*3} prepared contexts, original image bytes, alt text, typed controls, rich metadata, and invalid selections.')


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
