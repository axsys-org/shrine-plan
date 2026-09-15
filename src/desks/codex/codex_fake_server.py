#!/usr/bin/env python3
"""Strict deterministic app-server peer for the Foil/Helm integration test."""
import json
import os
import sys


def send(*messages):
    raw = b''.join((json.dumps(m, separators=(',', ':')) + '\n').encode() for m in messages)
    # Both split a frame and coalesce frames to exercise the native reader.
    sys.stdout.buffer.write(raw[:3])
    sys.stdout.buffer.flush()
    sys.stdout.buffer.write(raw[3:])
    sys.stdout.buffer.flush()


def result(message, value):
    send({'id': message['id'], 'result': value})


def main():
    mode = os.environ.get('CODEX_FAKE_MODE', sys.argv[1] if len(sys.argv) > 1 else 'normal')
    if mode == 'app-server':
        mode = 'console'
    initialized = False
    commands = []
    for line in sys.stdin:
        message = json.loads(line)
        method = message.get('method')
        if method == 'initialize':
            assert not commands
            result(message, {})
        elif method == 'initialized':
            initialized = True
            print('Codex fake initialized', file=sys.stderr, flush=True)
        elif method == 'thread/start':
            assert initialized
            if mode == 'console-error':
                send({'id': message['id'], 'error': {'code': -1, 'message': 'test error'}})
                continue
            if mode == 'malformed':
                sys.stdout.write('{broken\n')
                sys.stdout.flush()
                continue
            if mode == 'oversized':
                sys.stdout.write('x' * (4 * 1024 * 1024 + 1) + '\n')
                sys.stdout.flush()
                continue
            if mode == 'eof':
                return
            result(message, {'thread': {'id': 't1'}})
        elif method == 'thread/resume':
            assert message['params']['threadId'] == 't2'
            result(message, {'thread': {'id': 't2'}})
        elif method == 'turn/start':
            thread = message['params']['threadId']
            turn = 'u1' if thread == 't1' else 'u2'
            send({'method': 'turn/started', 'params': {'threadId': thread, 'turn': {'id': turn}}},
                 {'id': message['id'], 'result': {'turn': {'id': turn, 'status': 'inProgress'}}},
                 {'method': 'item/agentMessage/delta', 'params': {'threadId': thread, 'delta': 'hello'}})
            if mode == 'console':
                send({'method': 'turn/completed', 'params': {'threadId': thread, 'turn': {'id': turn, 'status': 'completed'}}})
        elif method == 'turn/steer':
            assert message['params']['expectedTurnId'] == 'u1'
            send({'id': 'effect-7', 'method': 'item/tool/requestUserInput',
                  'params': {'threadId': 't1', 'turnId': 'u1', 'questions': []}},
                 {'id': message['id'], 'result': {'turnId': 'u1'}})
        elif method == 'turn/interrupt':
            assert 'effect-reply' in commands
            assert message['params']['turnId'] == 'u1'
            send({'id': message['id'], 'result': {}},
                 {'method': 'turn/completed', 'params': {'threadId': 't1', 'turn': {'id': 'u1', 'status': 'interrupted'}}})
        elif method is None:
            assert message['id'] == 'effect-7'
            assert message['result'] == {'answers': {}}
            assert 'effect-reply' not in commands
            commands.append('effect-reply')
            send({'method': 'serverRequest/resolved', 'params': {'threadId': 't1', 'requestId': 'effect-7'}})
        else:
            raise AssertionError(message)
        if method:
            commands.append(method)


if __name__ == '__main__':
    main()
