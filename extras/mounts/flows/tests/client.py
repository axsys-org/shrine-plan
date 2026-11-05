"""Transport assertions for disposable tests; not a production flow runner."""
from pathlib import Path
import re
import json
import hashlib
import runpy
import uuid
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parents[1]
_transport = runpy.run_path(str(HERE.parent / 'cooperate' / 'client.py'))
Client = _transport['Client']
reference = _transport['reference']


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
        """Read the complete authored value through its ordinary Goo input."""
        if not author.startswith('/' + self.node + '/'):
            raise ValueError('source export must address this local publisher')
        body = urlencode(dict(target=author, view=f'/{self.node}/gov/nenex_tools/source_view',
                              width=720, textScale=1, direction='ltr')).encode()
        request = Request(self.base + '/goo/render', data=body,
                          headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlopen(request, timeout=self.timeout) as response:
            encoded = response.read(2097153)
        if len(encoded) > 2097152:
            raise ValueError('source view exceeds the export limit')
        rendered = json.loads(encoded)
        controls = [control for control in rendered.get('controls', [])
                    if control.get('kind') == 'input' and control.get('slot') == '/source']
        if len(controls) != 1:
            raise ValueError('the selected page has no unique source input')
        nodes = [node for node in rendered.get('display', {}).get('nodes', [])
                 if node.get('id') == controls[0]['id']]
        if len(nodes) != 1 or nodes[0].get('editing', {}).get('encoding') != 'goo-text-v1':
            raise ValueError('the source input has no native text value')
        runs = nodes[0].get('textRuns')
        if not isinstance(runs, list) or any(
                run.get('myth') != {} or not isinstance(run.get('lang', {}).get('en', {}).get('txt'), str)
                for run in runs):
            raise ValueError('the source input must contain plain text')
        return ''.join(run['lang']['en']['txt'] for run in runs)
