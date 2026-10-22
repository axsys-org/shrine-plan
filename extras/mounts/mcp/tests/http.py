"""MCP acceptance for the lean mount: four tools over the native cards, and a cell."""
import json
import statistics
import time
import urllib.request


def check(base, node, timeout):
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
    root = '/' + node + '/app/leanproof'
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
    data = '/' + node + '/user/cells/data'
    for key, amount in [('a', 5), ('b', 7)]:
        tool('write', path=data + '/' + key, properties={'amount': amount})
    cell = '/' + node + '/user/cells/proof'
    tool('write', path=cell, properties={
        'sys/weft': {'type': 'reference', 'value': counter},
        'sys/tack': {'type': 'reference', 'value': '/h/y/0/' + str(len(data.strip('/').split('/'))) + data},
        'into': '/items'})
    derived = tool('read', path='/x' + cell, care='x')
    assert derived['properties']['/items'] == '2', derived
    tool('write', path=data + '/c', properties={'amount': 1})
    assert tool('read', path='/x' + cell, care='x')['properties']['/items'] == '3'
    total = '/' + node + '/user/cells/total'
    summer = tool('read', path=stdlib + '/sum', care='x')['reference']
    tool('write', path=total, properties={
        'sys/weft': {'type': 'reference', 'value': summer},
        'sys/tack': {'type': 'reference', 'value': '/h/y/0/' + str(len(data.strip('/').split('/'))) + data},
        'slot': '/amount'})
    assert tool('read', path='/x' + total, care='x')['properties']['/total'] == '13'
    tool('write', path=cell, action='cull')
    tool('write', path=root, action='cull')
    assert not tool('read', path=root, care='x')['exists']
    start = len(durations)
    for _ in range(5):
        tool('read', path='/x' + total, care='x')
    print(json.dumps({'mcp_http_round_trips': sequence,
        'warm_cell_read_median_ms': round(statistics.median(durations[start:]) * 1000, 2)}), flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
