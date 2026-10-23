"""A real filesystem observer publishes inputs; native spun/crew maintain pages."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).parents[1]
api = runpy.run_path(str(HERE / 'client.py'))
FlowClient, prepare = api['FlowClient'], api['prepare']


def check(base):
    client = FlowClient(base)
    suffix = uuid.uuid4().hex[:10]
    author = '/0x11/app/nenex/w/maint_author_' + suffix
    destination = '/0x11/app/nenex/w/maint_book_' + suffix
    controller = '/0x11/user/maint_' + suffix
    feed = '/0x11/user/feed_' + suffix
    source = ''';.
  ;@ /flow/definition example
  ;= An authored guide
    ;@ /flow/input sources
    ;= Sources
    ;@ /flow/step checked ;/0x11/gov/flows/operations/inventory
    ;@ /flow/bind sources sources
    ;= Check
    ;@ /flow/step decomposed ;/0x11/gov/flows/operations/decompose
    ;@ /flow/bind sources checked
    ;= Decompose
    ;@ /flow/step pages ;/0x11/gov/flows/operations/documents
    ;@ /flow/bind pages document
    ;@ /flow/bind sources decomposed
    ;= Compose
    ;@ /flow/result pages
    ;= Result
    ;@ /flow/page /
    ;@ /flow/uses sample
    ;= Maintained guide
      Authored guidance.
'''
    attached = False
    worker = None
    imports = set()
    with tempfile.TemporaryDirectory(prefix='flow-maintenance-') as folder:
        folder = Path(folder)
        sample = folder / 'sample.md'
        def write_sample(body):
            sample.write_text('# Observed sample\n\n## Facts\n\n' + body + ' ' + suffix)
        write_sample('Initial evidence')
        manifest = folder / 'sources.json'
        manifest.write_text(json.dumps({'sample': {'path': 'sample.md', 'title': 'Observed sample'}}))
        log_path = folder / 'observer.log'
        def page():
            return client.read(destination + '/reference/sample/section_facts')['properties']['/src']
        def wait_for(predicate):
            until = time.monotonic() + 90
            while time.monotonic() < until:
                if predicate():
                    return
                if worker.poll() is not None:
                    raise AssertionError(log_path.read_text())
                time.sleep(.3)
            raise AssertionError('Observer did not converge: ' + log_path.read_text())
        try:
            client.author(author, source)
            definition = client.publish(author, 'example')
            bundle = prepare(folder, manifest)
            imported = client.import_sources(bundle)
            imports.add(imported)
            client.observe(feed, imported)
            client.follow(controller, definition, destination, {'sources': '/x' + feed})
            attached = True
            assert 'Initial evidence' in page()
            client.tool('write', records=[{'path': destination + '/notes', 'slots': {'text': 'Keep me'}}])
            with log_path.open('w') as log:
                worker = subprocess.Popen([sys.executable, '-u', str(HERE / 'client.py'), '--base', base,
                                           'watch', '--feed', feed, '--repo', str(folder),
                                           '--manifest', str(manifest), '--interval', '.25'], stdout=log, stderr=log)
                write_sample('Changed evidence')
                changed = prepare(folder, manifest)
                imports.add('/0x11/user/flow_sources/s_' + changed['digest'])
                wait_for(lambda: 'Changed evidence' in page())
                assert client.read(destination + '/notes')['properties']['/text'] == 'Keep me'
                stable = client.read(controller)['reference']
                time.sleep(1)
                assert stable == client.read(controller)['reference']
                sample.unlink()
                wait_for(lambda: 'Blocked:' in client.read(controller)['properties']['/sys/content'])
                assert 'Changed evidence' in page()
                write_sample('Changed evidence')
                wait_for(lambda: 'Watching' in client.read(controller)['properties']['/sys/content'])
                client.set_enabled(controller, False)
                write_sample('Paused evidence')
                paused = prepare(folder, manifest)
                imports.add('/0x11/user/flow_sources/s_' + paused['digest'])
                wait_for(lambda: paused['digest'] in log_path.read_text())
                assert 'Changed evidence' in page()
                client.set_enabled(controller, True)
                assert 'Paused evidence' in page()
                version = int(client.read(author)['reference'].split('/')[3])
                client.author(author, source.replace(';= Maintained guide', ';= Revised guide'), expected=version)
                client.publish(author, 'example')
                assert 'Revised guide' in client.read(destination)['properties']['/src']
            print(json.dumps({'passed': True, 'checks': ['real file observer', 'decomposed section refresh', 'spun dependency wake',
                              'no feedback loop', 'notes preserved', 'missing file blocks',
                              'same-content recovery', 'pause/resume', 'authored revision']}))
        finally:
            if worker is not None:
                worker.terminate()
                worker.wait(timeout=10)
            if attached:
                client.apply('detach', controller, {})
            client.tool('write', records=[{'path': p, 'action': 'cull'}
                                          for p in [author, destination, controller, feed, *sorted(imports)]])


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8138')
