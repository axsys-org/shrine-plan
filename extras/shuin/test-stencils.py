#!/usr/bin/env python3
"""Creation contract tests against a disposable --test-fixtures Shrine world.
Use test-agents.py --mock-only --mock-port 8343 for the optional actor test.
"""
import argparse
import copy
import json
import time
import urllib.error
import urllib.request
import urllib.parse


def check(server, actor=False):
    def request(expected=200, **body):
        req = urllib.request.Request(server + '/shuin-test', json.dumps(body).encode(), {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status, text = response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            status, text = error.code, error.read().decode()
        assert status == expected, (status, text, body)
        return text

    channel = '/0x11/app/shuin_chat/festival'
    def call(name, args, care='z', grant=channel, expected=200):
        return request(expected, operation='stencil_tool', care=care, grant=grant,
                       call={'function': {'name': name, 'arguments': json.dumps(args)}})

    def listing():
        return json.loads(call('grove_stencils', {'path': channel}))

    def arguments():
        found = listing()
        stencil = next(s for s in found['stencils'] if s['path'].endswith('/post_message'))
        assert stencil['title'] == 'Post message'
        assert len(found['stencils']) == 1 and found['next'] is None, found
        assert json.loads(call('grove_stencils', {'path': channel, 'after': '24', 'epoch': found['epoch']}))['stencils'] == []
        assert {a['slot'] for a in stencil['arguments']} == {'/sys/content', '/sys/author'}
        return {'path': channel, 'stencil': stencil['path'], 'recordVersion': found['recordVersion'],
                **{k: stencil[k] for k in ('publication', 'roleVersion', 'resultRoleVersion')},
                'arguments': {'/sys/content': {'type': 'text', 'value': 'שלום\nA complete message.'},
                              '/sys/author': {'type': 'text', 'value': 'Stencil test'}}}

    before = json.loads(request(operation='stencil_inspect', path=channel))
    original = arguments()
    actions = json.loads(call('grove_actions', {'path': channel}))
    assert not any(a['path'].endswith('/post_message') for a in actions['actions'])
    for version in ('recordVersion', 'publication', 'roleVersion', 'resultRoleVersion'):
        args = copy.deepcopy(original)
        args[version] = '0'
        assert 'changed' in call('grove_create', args, expected=409)
    for mode in ('missing', 'type', 'extra', 'empty'):
        args = copy.deepcopy(original)
        if mode == 'missing': del args['arguments']['/sys/author']
        if mode == 'type': args['arguments']['/sys/content'] = {'type': 'number', 'value': 17}
        if mode == 'extra': args['arguments']['/sys/now'] = {'type': 'number', 'value': 1}
        if mode == 'empty': args['arguments']['/sys/content']['value'] = ''
        call('grove_create', args, expected=409)
    for care, grant in [('none', channel), ('x', channel), ('y', '/0x11/app/shuin_chat')]:
        assert 'write grant' in call('grove_create', original, care, grant, 409)
    call('grove_stencils', {'path': channel}, grant='/0x11/app/agents/stencil_fixture/workspace', expected=409)
    assert json.loads(request(operation='stencil_inspect', path=channel)) == before
    first = json.loads(call('grove_create', original, care='y'))['created']
    second = json.loads(call('grove_create', original, care='z'))['created']
    assert first != second and first.startswith(channel + '/entry_')
    assert listing()['recordVersion'] == original['recordVersion'], 'Stencil mutated its parent'
    for path in (first, second):
        record, = json.loads(request(operation='stencil_inspect', path=path))
        assert record['content'] == original['arguments']['/sys/content']['value']
        assert record['author'] == 'Stencil test' and record['now'] == 1795197600 and record['message'], record
        # The native chat entry view consumes this same message role.
        source = urllib.request.Request(server + '/goo/render', urllib.parse.urlencode({'target': path, 'view': '/0x11/gov/shuin_chat/entry', 'width': '700', 'textScale': '1', 'direction': 'ltr', 'wire': 'protobuf-v2'}).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(source, timeout=30) as response:
            rendered = response.read()
        assert b'Stencil test' in rendered, rendered[:500]
    # Mutating the parent invalidates a previously discovered creation contract.
    call('namespace_write', {'path': channel, 'slot': '/sys/help', 'type': 'text', 'value': 'Changed parent for stale-version test.'})
    assert 'changed' in call('grove_create', original, expected=409)
    assert 'changed' in call('grove_stencils', {'path': channel, 'after': '24', 'epoch': '0'}, expected=409)
    print('PASS stencil discovery, complete visible messages, fresh allocation, atomic rejection, care authority and stale versions', flush=True)

    if actor:
        start = time.time()
        request(operation='queue', agent='stencil_poster', task='Post a message into the Festival channel using its stencil.', writes=channel)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = json.loads(request(operation='state', agent='stencil_poster'))
            assert state['status'] != 'error', state
            if state['status'] == 'idle' and not state['inbox']:
                break
            time.sleep(.15)
        else:
            raise AssertionError(state)
        records = json.loads(request(operation='stencil_inspect', path=channel))
        posts = [r for r in records if r['author'] == 'stencil_poster']
        assert len(posts) == 1 and posts[0]['message'] and int(start) <= posts[0]['now'] <= time.time(), posts
        request(operation='stencil_retry', agent='stencil_poster')
        assert json.loads(request(operation='stencil_inspect', path=channel)) == records
        print('PASS mock-provider discovery → creation → visible chat message, trusted clock, exact-turn retry without duplicate', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--actor', action='store_true')
    args = parser.parse_args()
    check(args.server.rstrip('/'), args.actor)
