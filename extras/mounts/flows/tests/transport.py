"""Native flow lifecycle through real transport in a disposable namespace."""
import json
from pathlib import Path
import runpy
import sys
import uuid
from urllib.request import urlopen
from urllib.parse import quote
from urllib.error import HTTPError

api = runpy.run_path(str(Path(__file__).parents[1] / 'client.py'))
FlowClient, prepare = api['FlowClient'], api['prepare']
Refused = api['_transport']['Refused']


def check(base):
    c = FlowClient(base)
    suffix = uuid.uuid4().hex[:10]
    author = '/0x11/app/nenex/w/flow_check_' + suffix
    destination = '/0x11/app/nenex/w/book_check_' + suffix
    inputs = '/0x11/user/flow_check_' + suffix

    def refused(call, reason):
        try:
            call()
        except Refused as error:
            assert reason in str(error), (reason, error.reply)
        else:
            raise AssertionError('Expected refusal: ' + reason)

    source = """;.
  ;@ /flow/definition handbook
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
    ;@ /flow/uses flow_harness
    ;= Shrine handbook
      A deterministic fixture for external format loading.
    ;@ /flow/page child
    ;= Cohesive typed data
      Keep related fields in a cohesive value.
""" + '\n  ' + ('Source export must preserve complete authored prose. ' * 180) + '\n'
    # Pure import is an independent operation; the shipped handbook uses judgment.
    bundle = prepare()
    try:
        c.author(author, source)
        assert len(source.encode()) > 8192 and c.source(author) == source
        for name, record in bundle['sources'].items():
            c.apply('import_source', inputs + '/' + name, record)
        definition = c.publish(author, 'handbook')
        run = c.preview(definition, destination, {'sources': inputs}, ident='first')
        before = c.read(run)['reference']
        assert not c.read(destination)['exists']
        assert c.read('/x' + run + '/result')['exists']
        assert c.preview(definition, destination, {'sources': inputs}, ident='first') == run
        assert c.read(run)['reference'] == before
        refused(lambda: c.preview(definition, destination + '_other', {'sources': inputs}, ident='first'), 'flow_run_id_conflict')
        c.commit(run)
        guide = c.source(destination + '/reference/flow_harness')
        assert ';$ md' not in guide and '# Semidoc flow harness' not in guide
        contract = c.source(destination + '/reference/flow_harness/section_authoring_contract')
        assert ';- /flow/input NAME' in contract and ';- Meaning:' in contract
        saved = c.read(destination)['reference']
        c.commit(run)
        assert c.read(destination)['reference'] == saved
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

        # Reauthor the same flow in Semidoc, preserve named annotations on refresh.
        c.tool('write', records=[{'path': destination + '/notes', 'slots': {'text': 'Keep my annotation'}}])
        text = source.replace('    ;= Shrine handbook\n', '    ;= Updated handbook\n', 1)
        version = int(c.read(author)['reference'].split('/')[3])
        c.author(author, text, expected=version)
        c.publish(author, 'handbook')
        fresh = c.preview(definition, destination, {'sources': inputs}, ident='refresh')
        c.commit(fresh)
        assert 'Updated handbook' in c.read(destination)['properties']['/src']
        assert c.read(destination + '/notes')['properties']['/text'] == 'Keep my annotation'

        # Revision conflict must leave the destination and run unchanged.
        stale = c.preview(definition, destination, {'sources': inputs}, ident='stale')
        c.tool('write', records=[{'path': inputs + '/grove', 'action': 'poke', 'slots': {'changed': True}}])
        before = c.read(destination)['reference']
        refused(lambda: c.commit(stale), 'flow_stale_input')
        assert c.read(destination)['reference'] == before

        # An unrelated second authored flow reuses the exact same operations.
        second_source = source.replace('/flow/definition handbook', '/flow/definition domain_guide', 1)
        second_source = second_source.replace('    ;= Shrine handbook\n', '    ;= Domain guide\n', 1)
        version = int(c.read(author)['reference'].split('/')[3])
        c.author(author, second_source, expected=version)
        second = c.publish(author, 'domain_guide')
        second_run = c.preview(second, destination, {'sources': inputs}, ident='second_flow')
        c.commit(second_run)
        assert 'Domain guide' in c.read(destination)['properties']['/src']
        print(json.dumps({'passed': True, 'source_count': len(bundle['sources']),
                          'checks': ['authored deterministic Semidoc', 'native source sections and table items', 'preview cells', 'retry', 'nested reader',
                                     'reauthoring', 'notes preserved', 'atomic stale refusal',
                                     'second authored flow']}))
    finally:
        c.tool('write', records=[{'path': p, 'action': 'cull'} for p in [author, destination, inputs]])


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8138')
