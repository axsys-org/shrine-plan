"""MCP acceptance for the lean mount: four tools over the native cards, and a cell."""
import json
import http.client
import socket
import statistics
import time
import uuid
import urllib.parse
import urllib.request
from contextlib import ExitStack


def check_connections(base, timeout):
    """Idle, partial and malformed clients must not block a complete MCP request."""
    address = urllib.parse.urlsplit(base)
    timeout = min(timeout, 5)
    body = json.dumps(dict(jsonrpc='2.0', id=99, method='tools/list', params={})).encode()
    head = (b'POST /mcp HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\n'
            + b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n')

    def response(sock, status=200):
        reply = http.client.HTTPResponse(sock)
        reply.begin()
        assert reply.status == status, reply.status
        data = reply.read()
        reply.close()
        if status == 200:
            assert json.loads(data)['result']['tools'], data

    with ExitStack() as stack:
        def connect():
            return stack.enter_context(socket.create_connection(
                (address.hostname, address.port or 80), timeout=timeout))

        # More idle sockets than a small reader pool, like browser preconnects.
        idle = [connect() for _ in range(8)]
        header = connect()
        header.sendall(head[:12])
        partial_body = connect()
        partial_body.sendall(head + body[:7])

        complete = connect()
        complete.sendall(head + body)
        response(complete)

        # Stalled clients still finish correctly, even in reverse arrival order.
        partial_body.sendall(body[7:])
        response(partial_body)
        header.sendall(head[12:] + body)
        response(header)
        idle[0].sendall(head + body)
        response(idle[0])

        malformed = connect()
        malformed.sendall(b'GET /bad\x01 HTTP/1.0\r\n\r\n')
        response(malformed, 400)
        for sock in idle[1:]:
            sock.close()
        healthy = connect()
        healthy.sendall(head + body)
        response(healthy)
    print('HTTP concurrency passed: idle sockets, partial headers/body, malformed input and recovery', flush=True)


def check(base, node, timeout):
    check_connections(base, timeout)
    durations = []
    sequence = 0

    def rpc(method, params=None, ident=None):
        nonlocal sequence
        sequence += 1
        body = json.dumps(dict(jsonrpc='2.0', id=sequence if ident is None else ident,
                               method=method, params=params or {})).encode()
        start = time.perf_counter()
        request = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.load(response)
        durations.append(time.perf_counter() - start)
        return answer

    def tool(name, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments})
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    assert rpc('initialize')['result']['protocolVersion']
    names = {x['name'] for x in rpc('tools/list')['result']['tools']}
    assert names == {'mcp/' + n for n in ['read', 'write', 'history', 'apply']}, names
    denied = rpc('tools/call', {'name': 'mcp/test-build', 'arguments': {'path': '/'}})
    assert denied['result'].get('isError'), denied
    home = '/' + node + '/user/mcp_check_' + uuid.uuid4().hex[:10]
    root = home + '/record'
    try:
        tool('write', path=root, properties={'label': 'retained', 'count': {'type': 'nat', 'value': '9007199254740993'}})
        original = tool('read', path=root, care='x')
        assert original['properties']['/count'] == '9007199254740993', original
        assert original['reference'].startswith('/h/x/'), original
        tool('write', path=root, action='poke', properties={'count': 7})
        after = tool('read', path=root, care='x')['properties']
        assert after['/count'] == '7' and after['/label'] == 'retained', after
        historical = tool('read', path=original['reference'], care='x')
        assert historical['properties']['/count'] == '9007199254740993', historical
        history = tool('history', path=root)
        assert history['cases'] >= 2 and history['versions'][0]['properties']['/count'] == '7', history
        # A cell: weft references a standard cell, tack references its input live, parameters are slots.
        stdlib = '/' + node + '/weft/stdlib'
        counter = tool('read', path=stdlib + '/count', care='x')['reference']
        assert counter.startswith('/h/x/'), counter
        data = home + '/data'
        for key, amount in [('a', 5), ('b', 7)]:
            tool('write', path=data + '/' + key, properties={'amount': amount})
        cell = home + '/cell'
        tool('write', path=cell, properties={
            'sys/weft': {'type': 'reference', 'value': counter},
            'sys/tack': {'type': 'reference', 'value': '/h/y/0/' + str(len(data.strip('/').split('/'))) + data},
            'into': '/items'})
        derived = tool('read', path='/x' + cell, care='x')
        assert derived['properties']['/items'] == '2', derived
        tool('write', path=data + '/c', properties={'amount': 1})
        assert tool('read', path='/x' + cell, care='x')['properties']['/items'] == '3'
        tool('write', path=root, action='cull')
        assert not tool('read', path=root, care='x')['exists']
        start = len(durations)
        for _ in range(5):
            tool('read', path='/x' + cell, care='x')
        print(json.dumps({'mcp_http_round_trips': sequence,
            'warm_cell_read_median_ms': round(statistics.median(durations[start:]) * 1000, 2)}), flush=True)
    finally:
        tool('write', path=home, action='cull')


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
