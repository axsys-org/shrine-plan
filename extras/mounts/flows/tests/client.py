"""Transport assertions for disposable tests; not a production flow runner."""
from html.parser import HTMLParser
from pathlib import Path
import re
import hashlib
import runpy
import uuid
from urllib.parse import quote
from urllib.request import urlopen

HERE = Path(__file__).resolve().parents[1]
_transport = runpy.run_path(str(HERE.parent / 'cooperate' / 'client.py'))
Client = _transport['Client']
reference = _transport['reference']


class SourceForm(HTMLParser):
    """The existing Nenex source form carries the complete escaped source."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.found = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'textarea' and dict(attrs).get('id') == 'page-source':
            self.active = self.found = True

    def handle_endtag(self, tag):
        if tag == 'textarea':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


class FlowClient(Client):
    def __init__(self, base, node='0x11', timeout=180):
        if not re.fullmatch(r'0x[0-9a-f]+', node):
            raise ValueError('node must be a hexadecimal publisher identity')
        super().__init__(base, node, timeout)
        self.publisher = '/' + node + '/gov/flows'

    def import_texts(self, texts):
        """Submit explicit test fixtures through the native import operation."""
        root = '/' + self.node + '/user/flow_sources/test_' + uuid.uuid4().hex
        for name, text in texts.items():
            self.apply('import_source', root + '/' + name,
                       dict(location=name + '.md', title=name, format='md',
                            digest=hashlib.sha256(text.encode()).hexdigest(), content=text))
        return root

    def author(self, target, source, *, expected=0):
        return self.apply('author', target, {'source': source, 'expected': expected})

    def publish(self, author, name):
        current = self.read(author)
        if not current.get('exists'):
            raise ValueError('authoring document does not exist: ' + author)
        version = int(current['reference'].split('/')[3])
        self.apply('publish', author, {'id': name, 'expected': version})
        return author + '/flows/' + name

    def preview(self, definition, destination, bindings, *, ident=None, writer=None):
        ident = ident or 'run_' + uuid.uuid4().hex
        inputs = {'id': ident, 'destination': {'type': 'path', 'value': destination},
                  'writer': reference(writer or self.publisher + '/nenex')}
        inputs.update({'input/' + name: value if isinstance(value, dict) else reference(value, 'z')
                       for name, value in bindings.items()})
        self.apply('preview', definition, inputs)
        return definition + '/work/' + ident

    def commit(self, run):
        return self.apply('commit', run, {})

    def observe(self, feed, source):
        return self.apply('observe', feed, {'source': reference(source, 'z')})

    def follow(self, controller, definition, destination, bindings, *, writer=None, provider=None):
        inputs = {'definition': reference(definition),
                  'destination': {'type': 'path', 'value': destination},
                  'writer': reference(writer or self.publisher + '/nenex')}
        if provider:
            inputs['provider'] = reference(provider)
        inputs.update({'input/' + name: value if isinstance(value, dict) else reference(value, 'z')
                       for name, value in bindings.items()})
        self.apply('follow', controller, inputs)
        return controller

    def set_enabled(self, controller, enabled):
        return self.apply('set_enabled', controller, {'enabled': enabled})

    def source_failed(self, feed, reason):
        return self.apply('source_failed', feed, {'reason': reason[:1500]})

    def submit_revision(self, request, source, note, expected=None):
        if expected is None:
            draft = self.read(request + '/draft')
            expected = int(draft['reference'].split('/')[3])
        return self.apply('submit_revision', request,
                          {'source': source, 'note': note, 'expected': expected})

    def source(self, author):
        # MCP renders text above 8 KiB as a reference. The normal source editor
        # supplies the whole source in one response, without a debugger mount.
        if not author.startswith('/' + self.node + '/'):
            raise ValueError('source export must address this local publisher')
        with urlopen(self.base + '/nenex?path=' + quote(author, safe=''), timeout=self.timeout) as response:
            html = response.read(2097153)
        if len(html) > 2097152:
            raise ValueError('source form exceeds the export limit')
        form = SourceForm()
        form.feed(html.decode('utf-8'))
        if not form.found or form.active:
            raise ValueError('the selected page has no complete source form')
        return ''.join(form.parts)
