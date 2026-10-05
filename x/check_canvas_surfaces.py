#!/usr/bin/env python3
"""Live native presentation regression, run only against a development world.

Creates one concept through its published template, exercises its declared Goo
control, and retains compact evidence. Does not imitate a browser or evaluate
application rules in Python.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from check_canvas_live import Client


def journey(world, refine=False):
    client = Client(world / 'canvas-admin.json')
    checks = []

    def call(operation, body, event=None, envelope=None):
        return client.action(operation, envelope or client.read(), body, event)

    def present(target):
        code, frame = call('present', {'target': target})
        assert code == 200, (code, frame)
        return frame

    def passed(name):
        checks.append(name)
        print('PASS', name, flush=True)

    code, created = call('construct', {'label': 'Workspace instruments'})
    assert code == 200, (code, created)
    original = present(created['created'])
    view = next(view for view in original['views'] if view['slot'] == '/sys/slot/edit')
    control = next(control for control in view['occurrences']
                   if control['kind'] == 'action' and control['invoke'])
    inputs = {'/sys/lede': 'Grove field instruments',
              '/sys/content': 'Inspect a result. Try a change. Keep the evidence. Return to using it.'}
    action = {key: original[key] for key in ('target', 'subject', 'expected', 'displayed', 'publication')}
    action.update(view=view['id'], control=control['control'], inputs=inputs)
    code, failure = call('perform', dict(action, inputs={}))
    assert code == 409, (code, failure)
    assert present(original['target'])['expected'] == original['expected']
    passed('missing declared inputs reject without changing the subject')
    event = str(uuid.uuid4())
    envelope = client.read()
    code, saved = call('perform', action, event, envelope)
    assert code == 200, (code, saved)
    changed = present(original['target'])
    actual = {field['slot']: field['value'] for field in changed['views'][0]['fields']}
    assert all(actual[slot] == value for slot, value in inputs.items()), actual
    assert changed['expected'] != original['expected']
    passed('published Goo action changes the installed native subject and its presentation')
    code, repeated = call('perform', action, event, envelope)
    assert code == 200 and repeated['expected'] == saved['expected'], (code, repeated)
    assert present(original['target'])['expected'] == changed['expected']
    passed('identical action replay is idempotent')
    code, rejected = call('perform', action)
    assert code == 409, (code, rejected)
    assert present(original['target'])['expected'] == changed['expected']
    passed('stale subject cannot be overwritten through a fresh workspace envelope')
    source_request = {'target': view['id'], 'revision': view['revision']}
    code, source = call('source', source_request)
    assert code == 200 and source['files'], (code, source)
    passed('inspection resolves the published presentation to its actual Grove source')
    preview = None
    if refine:
        code, narrow = call('present', {'target': changed['target'], 'width': '316'})
        assert code == 200 and narrow['width'] == '316', (code, narrow)
        assert all('width:316.0px' in item['html'] for item in narrow['views'] if item['html']), narrow
        assert narrow['subject'] == changed['subject'] and narrow['expected'] == changed['expected']
        code, invalid = call('present', {'target': changed['target'], 'width': '100000'})
        assert code == 400, (code, invalid)
        passed('native Goo lays out a bounded canvas card without changing subject identity or case')
        assert isinstance(source.get('editable_source'), str), source
        proposed = source['editable_source'].replace('action("Save",', 'action("Keep changes",')
        assert proposed != source['editable_source']
        evaluation = dict(target=changed['target'], view=view['id'], revision=view['revision'],
                          publication=changed['publication'], source=proposed, width='316')
        code, preview = call('evaluate', {'kind': 'presentation', **evaluation})
        assert code == 200 and preview['installed'] is False, (code, preview)
        assert 'Keep changes' in preview['after']['html'] and 'Keep changes' not in preview['before']['html']
        assert present(original['target']) == changed
        passed('native Grove compilation changes the preview without installing source or mutating data')
        code, failure = call('evaluate', {'kind': 'presentation', **evaluation, 'revision': '999999'})
        assert code == 409, (code, failure)
        code, failure = call('evaluate', {'kind': 'presentation', **evaluation,
                                         'source': proposed.replace("input('/sys/content)", "input('/sys/lede)")})
        assert code == 422, (code, failure)
        assert present(original['target']) == changed
        passed('stale presentation basis and retargeted input reject while preserving the installed world')

    messages = [dict(jsonrpc='2.0', id=1, method='initialize', params={}),
                dict(jsonrpc='2.0', method='notifications/initialized'),
                dict(jsonrpc='2.0', id=2, method='tools/call',
                     params=dict(name='read', arguments={'target': original['target']})),
                dict(jsonrpc='2.0', id=3, method='tools/call',
                     params=dict(name='source', arguments=source_request))]
    if refine:
        messages.append(dict(jsonrpc='2.0', id=4, method='tools/call', params=dict(name='eval', arguments=evaluation)))
    process = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent /
                             'extras/mounts/canvas/mcp.py'), '--connection', str(world / 'canvas-agent.json')],
                             input='\n'.join(map(json.dumps, messages)) + '\n', text=True,
                             capture_output=True, timeout=90, check=True)
    replies = {reply['id']: reply for reply in map(json.loads, process.stdout.splitlines())}
    assert replies[2]['result']['structuredContent'] == changed, replies[2]
    assert replies[3]['result']['structuredContent'] == source, replies[3]
    passed('actual MCP stdio reads the same native subject, occurrences, and source')
    if refine:
        assert replies[4]['result']['structuredContent'] == preview, replies[4]
        passed('actual MCP eval produces the identical native comparison used by Canvas')
    return dict(checks=checks, subject=original['subject'], expected=changed['expected'],
                source_sha256=hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refine', action='store_true', help='Require native source refinement and MCP eval')
    args = parser.parse_args()
    result = dict(started=time.time(), status='running')
    try:
        result.update(journey(args.world, args.refine))
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        result['completed'] = time.time()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
