#!/usr/bin/env python3
"""End-to-end Agents acceptance against a disposable Shrine + mock OpenRouter.

Start this mock with --mock-only, then boot run-chat-server.py --test-fixtures
with SHUIN_AGENT_TEST=1 SHUIN_OPENROUTER_URL=http://127.0.0.1:8342/api/v1/chat/completions
and OPENROUTER_API_KEY=shuin-test-key. Run this script --server http://127.0.0.1:8341.
"""
import argparse
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = 'shuin-test-key'
MOCK = 'http://127.0.0.1:8342'
requests = []
gate = threading.Event()


def tool(name, args, i):
    return {'id': f'call_{i}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(requests).encode())

    def do_POST(self):
        if self.path == '/hold':
            gate.clear()
            self.send_response(200)
            self.end_headers()
            return
        if self.path == '/release':
            gate.set()
            self.send_response(200)
            self.end_headers()
            return
        raw = self.rfile.read(int(self.headers['Content-Length']))
        body = json.loads(raw)
        assert self.headers['Authorization'] == f'Bearer {KEY}'
        assert KEY not in raw.decode()
        assert body['model'] == 'google/gemini-4-neon'
        requests.append(body)
        bundle = body['messages'][-1]['content']
        agent = bundle.split('Namespace root ', 1)[1].splitlines()[0]
        name = agent.rsplit('/', 1)[-1]
        prior = [m for m in body['messages'] if m['role'] == 'assistant']
        for message in prior:
            assert message['reasoning_details'] == [{'type': 'reasoning.text', 'text': 'Mock provider reasoning.', 'index': 0}]
        index = len(prior)
        note = agent + '/workspace/note'
        calls = []
        status = 200
        finish = 'stop'
        if name == 'pending_failure':
            gate.wait(30)
            status = 429
        elif name == 'failed':
            status = 429
        elif name == 'incomplete':
            finish = 'length'
        elif name == 'arrivals':
            if index == 0:
                gate.wait(30)
            else:
                assert 'Edited while the provider was working.' in bundle
                assert 'An item that arrived during HTTP.' in bundle
        elif name == 'workbench_poster':
            channel = '/0x11/app/shuin_chat/festival'
            last = next((m['content'] for m in reversed(body['messages']) if m['role'] == 'tool'), '')
            if index == 0 or not prior[-1].get('tool_calls') or last.startswith('Error:'):
                calls = [tool('grove_stencils', {'path': channel}, 'discover')]
            else:
                receipt = json.loads(last)
                if 'stencils' in receipt:
                    gate.wait(180)
                    stencil = next(s for s in receipt['stencils'] if s['path'].endswith('/post_message'))
                    calls = [tool('grove_create', {'path': channel, 'stencil': stencil['path'],
                        'recordVersion': receipt['recordVersion'],
                        **{k: stencil[k] for k in ('publication', 'roleVersion', 'resultRoleVersion')},
                        'arguments': {'/sys/content': {'type': 'text', 'value': 'Live workbench message'},
                                      '/sys/author': {'type': 'text', 'value': name}}}, 'post')]
                else:
                    assert receipt['created'].startswith(channel + '/entry_'), receipt
        elif name == 'stencil_poster':
            channel = '/0x11/app/shuin_chat/festival'
            if index == 0:
                assert {'grove_stencils', 'grove_create'} <= {t['function']['name'] for t in body['tools']}
                calls = [tool('grove_stencils', {'path': channel}, 'discover')]
            elif index == 1:
                listing = json.loads([m for m in body['messages'] if m['role'] == 'tool'][-1]['content'])
                stencil = next(s for s in listing['stencils'] if s['path'].endswith('/post_message'))
                calls = [tool('grove_create', {'path': channel, 'stencil': stencil['path'],
                    'recordVersion': listing['recordVersion'],
                    **{k: stencil[k] for k in ('publication', 'roleVersion', 'resultRoleVersion')},
                    'arguments': {'/sys/content': {'type': 'text', 'value': 'Posted through a Shrine stencil.'},
                                  '/sys/author': {'type': 'text', 'value': 'stencil_poster'}}}, 'post')]
            else:
                receipt = json.loads([m for m in body['messages'] if m['role'] == 'tool'][-1]['content'])
                assert receipt['created'].startswith(channel + '/entry_'), receipt
        elif name == 'happy':
            if index == 0:
                calls = [tool('namespace_write', {'path': note, 'slot': '/sys/content', 'type': 'text', 'value': 'hello'}, index)]
            elif index == 1:
                calls = [tool('grove_actions', {'path': note}, index)]
            elif index == 2:
                result = next(m for m in reversed(body['messages']) if m['role'] == 'tool')
                listing = json.loads(result['content'])
                action = next(a for a in listing['actions'] if a['path'].endswith('/shuin_actions_fixture/append'))
                calls = [tool('grove_invoke', {'path': note, 'action': action['path'], 'recordVersion': listing['recordVersion'], 'publication': action['publication'], 'roleVersion': action['roleVersion'], 'arguments': {}}, index)]
            elif index == 3:
                calls = [tool('namespace_read', {'path': note}, index)]
            elif index == 4:
                result = next(m for m in reversed(body['messages']) if m['role'] == 'tool')
                assert 'hello!' in result['content']
                assert '@x' not in result['content']
        elif name == 'guards' and index == 0:
            calls = [tool('namespace_write', {'path': '/0x11/app/agents/happy/workspace/note', 'slot': '/sys/content', 'type': 'text', 'value': 'corrupted'}, 0),
                     tool('namespace_read', {'path': '/0x11/io/http'}, 1),
                     tool('namespace_write', {'path': note, 'slot': '/sys/content', 'type': 'foil', 'value': '(Print "bad")'}, 2)]
        message = {'role': 'assistant', 'content': 'Mock task complete.' if not calls else None,
                   'reasoning': 'Mock provider reasoning.',
                   'reasoning_details': [{'type': 'reasoning.text', 'text': 'Mock provider reasoning.', 'index': 0}]}
        if calls:
            message['tool_calls'] = calls
            finish = 'tool_calls'
        payload = {'choices': [{'message': message, 'finish_reason': finish}]} if status == 200 else {'error': {'message': 'Mock rate limit'}}
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


def post(url, body):
    try:
        with urllib.request.urlopen(url, json.dumps(body).encode(), timeout=120) as r:
            return r.read().decode()
    except urllib.error.HTTPError as error:
        raise AssertionError(f'{url}: HTTP {error.code}: {error.read().decode()}') from error


def check(server):
    # The local mock may serve several disposable worlds in one session.
    # Assertions below concern this run, not retained requests from earlier runs.
    with urllib.request.urlopen(MOCK, timeout=10) as response:
        request_offset = len(json.load(response))

    def request(**fields):
        return post(server + '/shuin-test', fields)

    def state(agent):
        return json.loads(request(operation='state', agent=agent))

    def wait(agent, predicate, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = state(agent)
            if predicate(current):
                return current
            time.sleep(.3)
        raise AssertionError(f'{agent}: timed out: {current}')

    for agent in ('happy', 'guards', 'failed', 'incomplete', 'arrivals'):
        assert not state(agent)['entries'], 'Use a fresh disposable world for the full suite'
    request(operation='http_guard')
    deadline = time.monotonic() + 30
    while not (guard := request(operation='http_state')):
        assert time.monotonic() < deadline
        time.sleep(.2)
    guard = json.loads(guard)
    assert guard['state'] == 'failed' and 'credential' in guard['error'].lower(), guard
    text = request(operation='codec')
    assert text.index('+ .') < text.index('+ a') < text.index('+ z')
    assert "'~/z" in text and "'/sys" in text
    assert '12345678901234567890' in text and '@x' not in text and '($ts ' in text
    assert '/code' in request(operation='unsupported')
    # Parse whole records with the real Rex reader, then evaluate only these
    # trusted generated literals through the fixture's typed action argument.
    # Seed constructors resolve by definition path; the fixture imports pails.
    # Keep its replacement the same width to preserve Rex cord columns.
    def action_request(**fields):
        with urllib.request.urlopen(server + '/shuin/actions', urllib.parse.urlencode(fields).encode(), timeout=60) as r:
            return json.load(r)

    samples = ['', 'Plain text', 'Quotes: " and שלום', 'First\n  second\n\n   \nlast\n',
               '\nleading\n  \n', '\n', 'carriage\r\nreturn', 'a\tb', 'a\0b']
    for sample in samples:
        atom = int.from_bytes(sample.encode(), 'little')
        # Shrine's JSON reader rejects NUL strings; construct that existing
        # namespace value from its packed atom in this test-only fixture.
        fields = {'atom': atom} if '\0' in sample else {'text': sample}
        encoded = json.loads(request(operation='codec_text', **fields))
        assert all(not leaf['error'] for leaf in encoded['leaves']), encoded
        numeric = sample.startswith('\n') or any(ord(c) < 32 and c != '\n' for c in sample)
        if numeric:
            assert str(atom) in encoded['literal']
        else:
            assert any(leaf['kind'] == 'cord' and leaf['text'] == sample for leaf in encoded['leaves']), encoded
        source = encoded['literal'].replace('sys/types/pails/t', 'pails/t' + ' ' * 10)
        listing = action_request(operation='list', target=encoded['path'])
        action = next(a for a in listing['actions'] if a['path'].endswith('/shuin_actions_fixture/rename'))
        result = action_request(operation='invoke', target=encoded['path'], life=listing['life'], recordVersion=listing['recordVersion'],
                                action=action['path'], publication=action['publication'], roleVersion=action['roleVersion'],
                                id=uuid.uuid4().hex, **{'arg:/sys/content': source})
        assert result['accepted'], result
        assert json.loads(request(operation='codec_result')) == atom
    print('PASS Rex record parsing and exact text literal round trips', flush=True)
    for agent in ('happy', 'guards', 'failed', 'incomplete'):
        request(operation='queue', agent=agent, task='Complete this test task.', dependencies='/0x11/app/codec_fixture' if agent == 'happy' else '')
        result = wait(agent, lambda s: s['status'] == 'error' or (s['status'] == 'idle' and not s['inbox']))
        if agent in ('failed', 'incomplete'):
            assert result['status'] == 'error' and result['inbox'], result
        else:
            assert result['status'] == 'idle' and not result['inbox'], result
            if agent == 'happy':
                note = next(e for e in result['entries'] if e['path'].endswith('/workspace/note'))
                assert note['slots']['/sys/content'] == 'hello!'
            else:
                messages = [e['slots'].get('/messages', '') for e in result['entries']]
                assert sum(m.count('Error:') for m in messages) == 3
        print('PASS', agent, flush=True)
    post(MOCK + '/hold', {})
    request(operation='queue', agent='arrivals', task='First task.', dependencies='')
    wait('arrivals', lambda s: s['status'] == 'running')
    # Save through the production receiver continuation while real HTTP is held.
    request(operation='path_pending', agent='arrivals', path='/0x11/app/codec_fixture', care='x')
    old = json.loads(request(operation='path_grants', path='/0x11/app/agents/arrivals'))
    assert old['read']['hunts'] == [], old
    # Another agent is idle: its grant edit must apply immediately even while
    # the single provider driver is awaiting the first agent's response.
    request(operation='path_pending', agent='happy', path='/0x11/app/codec_fixture/a', care='x')
    changed = json.loads(request(operation='path_grants', path='/0x11/app/agents/happy'))
    assert len(changed['read']['hunts']) == 1 and changed['read']['hunts'][0]['care'] == 'x'
    request(operation='arrive', agent='arrivals')
    post(MOCK + '/release', {})
    result = wait('arrivals', lambda s: s['status'] == 'idle' and not s['inbox'])
    turns = [e for e in result['entries'] if '/turns/' in e['path'] and e['slots'].get('/status') == 'complete']
    assert len(turns) == 2, result
    with urllib.request.urlopen(MOCK, timeout=10) as r:
        requests = json.load(r)[request_offset:]
    arrival_requests = [r for r in requests if r['messages'][-1]['content'].startswith('Namespace root /0x11/app/agents/arrivals\n')]
    assert len(arrival_requests) == 2
    assert 'Edited while the provider was working.' in arrival_requests[1]['messages'][-1]['content']
    applied = json.loads(request(operation='path_grants', path='/0x11/app/agents/arrivals'))
    assert applied['read']['hunts'][0]['care'] == 'x', applied
    print('PASS per-agent pending grants during HTTP, idle edits, and arrivals', flush=True)
    request(operation='arrive', agent='arrivals')
    result = wait('arrivals', lambda s: s['status'] == 'idle' and not s['inbox'])
    root = next(e for e in result['entries'] if e['path'] == '/0x11/app/agents/arrivals')
    assert root['slots']['/sequence'] == '3'
    print('PASS direct inbox writes wake an idle agent', flush=True)
    post(MOCK + '/hold', {})
    request(operation='queue', agent='pending_failure', task='Fail this turn.', dependencies='')
    wait('pending_failure', lambda s: s['status'] == 'running')
    request(operation='path_pending', agent='pending_failure', path='/0x11/app/codec_fixture/a', care='x')
    assert json.loads(request(operation='path_grants', path='/0x11/app/agents/pending_failure'))['read']['hunts'] == []
    post(MOCK + '/release', {})
    failed = wait('pending_failure', lambda s: s['status'] == 'error')
    assert failed['inbox']
    assert json.loads(request(operation='path_grants', path='/0x11/app/agents/pending_failure'))['read']['hunts'][0]['care'] == 'x'
    time.sleep(.5)
    assert state('pending_failure')['status'] == 'error', 'Saving grants retried a failed turn'
    print('PASS failure-boundary grant application without retry', flush=True)
    exported = request(operation='export', path='/0x11/app/agents/happy')
    assert KEY not in exported and 'hello!' in exported
    print('PASS codec, secret exclusion, tools, action versions, provider failure, inbox retention', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mock-only', action='store_true')
    p.add_argument('--mock-port', type=int, default=8342)
    p.add_argument('--server')
    args = p.parse_args()
    MOCK = f'http://127.0.0.1:{args.mock_port}'
    if args.mock_only:
        print(f'Mock OpenRouter listening on 127.0.0.1:{args.mock_port}', flush=True)
        ThreadingHTTPServer(('127.0.0.1', args.mock_port), Provider).serve_forever()
    else:
        check(args.server.rstrip('/'))
