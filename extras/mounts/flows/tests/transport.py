"""Native flow lifecycle through real transport in a disposable namespace."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import uuid
from urllib.request import urlopen
from urllib.parse import quote
from urllib.error import HTTPError

api = runpy.run_path(str(Path(__file__).parents[1] / 'client.py'))
FlowClient, prepare = api['FlowClient'], api['prepare']


def check(base):
    c = FlowClient(base)
    suffix = uuid.uuid4().hex[:10]
    author = '/0x11/app/nenex/w/flow_check_' + suffix
    destination = '/0x11/app/nenex/w/book_check_' + suffix
    inputs = '/0x11/user/flow_check_' + suffix

    source = """;.
  ;@ /flow/definition import_guide
  ;= Deterministic import fixture
    ;@ /flow/input sources
    ;= Sources
    ;@ /flow/step checked ;/0x11/gov/flows/operations/inventory
    ;@ /flow/bind sources sources
    ;= Check
    ;@ /flow/step decomposed ;/0x11/gov/flows/operations/decompose
    ;@ /flow/bind sources checked
    ;= Import Markdown
    ;@ /flow/step pages ;/0x11/gov/flows/operations/documents
    ;@ /flow/bind pages document
    ;@ /flow/bind sources decomposed
    ;= Compose fixed templates
    ;@ /flow/result pages
    ;= Result
    ;@ /flow/page /
    ;@ /flow/uses manual
    ;= Import guide
      A deterministic fixture for external format loading.
    ;@ /flow/page child
    ;= Cohesive typed data
      Keep related fields in a cohesive value.
""" + '\n  ' + ('Source export must preserve complete authored prose. ' * 180) + '\n'
    # Pure import is an independent operation; the shipped handbook uses judgment.
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / 'manual.md').write_text('# Manual\n\n## Authoring\n\nKeep related fields together.\n\n| Field | Meaning |\n| --- | --- |\n| name | Display name |\n')
        manifest = root / 'sources.json'
        manifest.write_text(json.dumps({'manual': {'path': 'manual.md'}}))
        bundle = prepare(root, manifest)
    try:
        c.author(author, source)
        assert len(source.encode()) > 8192 and c.source(author) == source
        for name, record in bundle['sources'].items():
            c.apply('import_source', inputs + '/' + name, record)
        definition = c.publish(author, 'import_guide')
        run = c.preview(definition, destination, {'sources': inputs}, ident='first')
        assert not c.read(destination)['exists']
        assert c.read('/x' + run + '/result')['exists']
        c.commit(run)
        guide = c.source(destination + '/reference/manual/section_authoring')
        assert 'Keep related fields together.' in guide and ';$ md' not in guide
        child = destination + '/child'
        assert 'cohesive value' in c.read(child)['properties']['/src']
        with urlopen(base + '/nenex?path=' + quote(child, safe=''), timeout=60) as response:
            html = response.read().decode()
            assert response.status == 200 and 'Cohesive typed data' in html
        for invalid in [destination + '/0', '/0x11/user/private']:
            try:
                urlopen(base + '/nenex?path=' + quote(invalid, safe=''), timeout=60)
            except HTTPError as error:
                assert error.code == 400
            else:
                raise AssertionError('Non-page route accepted: ' + invalid)

        print(json.dumps({'passed': True, 'checks': ['large source export', 'typed native invocation', 'imported section', 'nested reader', 'page route boundaries']}))
    finally:
        c.tool('write', records=[{'path': p, 'action': 'cull'} for p in [author, destination, inputs]])


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8138')
