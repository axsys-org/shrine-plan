"""The stream in the foot, end to end: two clients hold GET /mcp/stream open, one write reaches both as one line within the
write's own latency; a closed socket is dropped and the next write still reaches the other; a presented read arrives as
{shown} and journals nothing.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/stream.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import json
import socket
import time
import urllib.parse
import urllib.request


class StreamClient:
    """A raw socket on GET /mcp/stream, reading server-sent events line by line."""

    def __init__(self, base, timeout):
        u = urllib.parse.urlparse(base)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        self.sock.sendall(b'GET /mcp/stream HTTP/1.0\r\nHost: localhost\r\n\r\n')
        self.buf = b''
        head = self.read_until(b'\r\n\r\n')
        assert b'200' in head.split(b'\r\n')[0] and b'text/event-stream' in head, head

    def read_until(self, marker, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)
        while marker not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError('stream closed')
            self.buf += chunk
        head, self.buf = self.buf.split(marker, 1)
        return head

    def event(self, timeout=5):
        """The next event's data, parsed."""
        while True:
            block = self.read_until(b'\r\n\r\n', timeout).decode()
            lines = [l[6:] for l in block.split('\r\n') if l.startswith('data: ')]
            if lines:
                return json.loads(''.join(lines))

    def close(self):
        self.sock.close()


def check(base, node, timeout):
    seq = [0]
    checks = []

    def rpc(name, **arguments):
        seq[0] += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq[0], method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        reply = json.load(urllib.request.urlopen(req, timeout=timeout))
        return reply['result']['structuredContent'], 1000 * (time.perf_counter() - t0)

    def epoch():
        with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
            return json.load(r)['epoch']

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    home = '/' + node + '/user/streamed'
    a, b = StreamClient(base, timeout), StreamClient(base, timeout)
    time.sleep(0.2)

    # 1. one write, both streams receive one line, within the write's own latency
    written, write_ms = rpc('write', records=[{'path': home + '/r1', 'slots': {'n': 1}}], who='tester')
    t0 = time.perf_counter(); la = a.event(); ta = 1000 * (time.perf_counter() - t0)
    t0 = time.perf_counter(); lb = b.event(); tb = 1000 * (time.perf_counter() - t0)
    expect('1 both streams got the write as one line: epoch, who, touched', (la['epoch'], lb['epoch'], la['who'], home + '/r1' in la['touched'], la == lb), (written['epoch'], written['epoch'], 'tester', True, True))
    expect('1 the line arrived within the write\'s own latency', ta < write_ms + 50 and tb < write_ms + 50, True)
    expect('1 the line carries the written record under with', la['with'][home + '/r1']['properties']['/n'], '1')

    # 2. a closed socket is dropped; the next write still reaches the other stream and the write is not slowed
    b.close()
    time.sleep(0.2)
    written2, write_ms2 = rpc('write', records=[{'path': home + '/r2', 'slots': {'n': 2}}], who='tester')
    la2 = a.event()
    expect('2 after a stream closed, the other still gets the next write as one line', la2['epoch'], written2['epoch'])
    expect('2 a dropped stream does not slow the write', write_ms2 < 500, True)

    # 3. a presented read arrives as {shown} and journals nothing
    e0 = epoch()
    rpc('read', path=home + '/r1', care='x', present=True)
    shown = a.event()
    expect('3 a presented read arrives on the stream as {shown: {path, care, case}} and moves no epoch', (shown.get('shown', {}).get('path'), shown['shown'].get('care'), epoch() - e0), (home + '/r1', 'x', 0))

    # 4. a batch is one line naming every path
    batch, _ = rpc('write', records=[{'path': home + '/b' + str(i), 'slots': {'n': i}} for i in range(20)], who='tester')
    lb20 = a.event()
    expect('4 a batch of twenty is one line naming all twenty paths', (lb20['epoch'], sum(1 for p in lb20['touched'] if '/b' in p)), (batch['epoch'], 20))
    a.close()
    print(json.dumps({'checks': len(checks), 'round_trips': seq[0]}), flush=True)
