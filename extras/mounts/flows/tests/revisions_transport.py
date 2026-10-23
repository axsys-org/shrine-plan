"""Prove concept revision, source-scoped invalidation and guarded publication.

Use --codex for the actual mounted bridge; otherwise supply explicit human-style
responses through the same native command. Run in a disposable development world.
"""
import argparse
import json
from pathlib import Path
import runpy
import tempfile
import time
import uuid

HERE = Path(__file__).parents[1]
api = runpy.run_path(str(HERE / 'client.py'))


def check(base, codex=False):
    client = api['FlowClient'](base)
    key = uuid.uuid4().hex[:8]
    author = '/0x11/app/nenex/w/revision_spec_' + key
    destination = '/0x11/app/nenex/w/revision_book_' + key
    controller = author + '/work/maintenance'
    feed = '/0x11/user/revision_feed_' + key
    recipe = ''';.
  ;@ /flow/definition handbook
  ;= A small concept handbook
    ;@ /flow/input sources
    ;= Sources
    ;@ /flow/step checked ;/0x11/gov/flows/operations/inventory
    ;@ /flow/bind sources sources
    ;= Check
    ;@ /flow/step concepts ;/0x11/gov/flows/operations/revise
    ;@ /flow/bind pages document
    ;@ /flow/bind sources checked
    ;= Author concepts
    ;@ /flow/step pages ;/0x11/gov/flows/operations/evidence
    ;@ /flow/bind pages concepts
    ;@ /flow/bind sources checked
    ;= Compose
    ;@ /flow/result pages
    ;= Result
    ;@ /flow/page /
    ;@ /flow/uses entries
    ;= Entry identity and labels
      Explain entry identity versus its label in this fictional Beacon catalogue.
      Give a concrete supported example of how a user can change a displayed
      label, or explain the restriction if the source forbids it.
    ;@ /flow/page status
    ;@ /flow/uses status
    ;= Status as a cohesive value
      Explain the status representation and why it does not require many slots.
'''
    imports = set()
    attached = False
    def pending():
        rows = client.read('/x' + controller + '/queue', 'y', limit=100).get('children', [])
        result = []
        for row in rows:
            value = row.get('properties', {}).get('/request')
            if isinstance(value, dict):
                value = value.get('value') or value.get('path')
            if value:
                result.append(value)
        return result

    def wait_finished():
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            status = client.read(controller).get('properties', {}).get('/sys/content', '')
            if status.startswith('Watching'):
                return
            if status.startswith('Blocked'):
                raise AssertionError(status)
            time.sleep(.5)
        raise AssertionError('Native hand did not complete: ' + status)
    with tempfile.TemporaryDirectory(prefix='flow-concepts-') as folder:
        root = Path(folder)
        (root / 'entries.md').write_text('# Beacon entries\nEach entry has a stable ID and a mutable text label.\nUsers can rename the label in place without changing its ID.\n')
        (root / 'status.md').write_text('# Beacon status\nStatus is one typed value in a single status slot.\nIts fields are phase and explanation and are updated together.\n')
        manifest = root / 'sources.json'
        manifest.write_text(json.dumps({name: {'path': name + '.md'} for name in ('entries', 'status')}))

        def capture():
            bundle = api['prepare'](root, manifest)
            imported = client.import_sources(bundle)
            imports.add(imported)
            client.observe(feed, imported)

        def complete(requests, changed=False):
            if codex:
                wait_finished()
                return
            for request in requests:
                label = client.read(request)['properties']['/sys/lede']
                content = ('Create a separate alias record for a new displayed label; entry IDs remain stable.'
                           if changed else 'The entry ID remains stable while its label is renamed.')
                if 'Status' in label:
                    content = 'Keep phase and explanation together in one typed status value.'
                client.submit_revision(request, ';= ' + label + '\n  ' + content,
                                       'Grounded in the declared entries or status source.')

        try:
            client.author(author, recipe)
            definition = client.publish(author, 'handbook')
            capture()
            client.follow(controller, definition, destination, {'sources': '/x' + feed},
                          provider='/0x11/io/codex/work_provider' if codex else None)
            attached = True
            requests = pending()
            assert len(requests) == 2, requests
            assert not client.read(destination).get('exists')
            complete(requests)
            before = client.source(destination)
            status = client.source(destination + '/status')
            assert 'Watching' in client.read(controller)['properties']['/sys/content']
            client.tool('write', records=[{'path': destination + '/notes', 'slots': {'text': 'Personal annotation'}}])
            (root / 'entries.md').write_text('# Beacon entries\nEach entry has a stable ID and a text label.\nLabels are read-only after creation. To change a displayed label, create a separate alias record.\nEntry IDs remain stable.\n')
            capture()
            affected = pending()
            assert len(affected) == 1, affected
            assert client.source(destination) == before
            complete(affected, changed=True)
            after = client.source(destination)
            assert before != after and 'alias' in after.lower(), after
            assert client.source(destination + '/status') == status
            assert client.read(destination + '/notes')['properties']['/text'] == 'Personal annotation'
            assert not pending()
            stable = client.read(controller)['reference']
            capture()
            assert client.read(controller)['reference'] == stable
            overlay = client.read('/x' + affected[0] + '/view', 'y')
            assert any(row['path'].endswith('/document') for row in overlay.get('children', [])), overlay
            result = {'passed': True, 'codex': codex,
                      'checks': ['concept synthesis', 'source-scoped invalidation',
                                 'changed meaning revises prose', 'unchanged concept reused',
                                 'no partial publication', 'notes preserved',
                                 'working overlay', 'unchanged source no-op']}
            print(json.dumps(result), flush=True)
            return result
        finally:
            if attached:
                client.apply('detach', controller, {})
            client.tool('write', records=[{'path': p, 'action': 'cull'}
                                         for p in [author, destination, feed, *imports]])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base')
    parser.add_argument('--codex', action='store_true')
    args = parser.parse_args()
    check(args.base, args.codex)
