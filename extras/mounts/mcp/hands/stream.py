"""Follow a world's stream: GET /mcp/stream as server-sent events, one JSON line per admitted write ({epoch, label, who,
touched, with}) and per presented read ({shown}); when the stream cannot be opened or closes, fall back to polling
`history after <seen> with x` and hand the same lines over, so a hand works the same either way.

    for line in follow(base, node, seen=epoch_now):
        ...

follow() yields lines in order and never returns; it reconnects to the stream after a close, polling meanwhile.
"""
import json
import socket
import time
import urllib.parse
import urllib.request


class Stream:
    def __init__(self, base, timeout=30):
        u = urllib.parse.urlparse(base)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        self.sock.sendall(b'GET /mcp/stream HTTP/1.0\r\nHost: localhost\r\n\r\n')
        self.buf = b''
        head = self._until(b'\r\n\r\n')
        if b'200' not in head.split(b'\r\n')[0] or b'text/event-stream' not in head:
            raise OSError('no stream at /mcp/stream')

    def _until(self, marker):
        while marker not in self.buf:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue                    # an idle world sends nothing; the stream is still open
            if not chunk:
                raise EOFError('stream closed')
            self.buf += chunk
        head, self.buf = self.buf.split(marker, 1)
        return head

    def event(self):
        while True:
            block = self._until(b'\r\n\r\n').decode()
            data = [l[6:] for l in block.split('\r\n') if l.startswith('data: ')]
            if data:
                return json.loads(''.join(data))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def poll(base, node, seen, timeout=120, limit=40):
    """One page of events after `seen`, with x, as stream-shaped lines; returns (lines, new seen). A page the world
    refuses as too large (events that wrote many big records) is asked for again with half the limit, down to one."""
    while True:
        body = json.dumps(dict(jsonrpc='2.0', id=1, method='tools/call', params={'name': 'mcp/history', 'arguments': {'after': seen, 'limit': limit, 'with': 'x'}})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        result = json.load(urllib.request.urlopen(req, timeout=timeout))['result']
        if 'structuredContent' in result:
            page = result['structuredContent']
            break
        text = ''.join(c.get('text', '') for c in result.get('content', []))
        if 'too large' in text and limit > 1:
            limit = max(1, limit // 2)
            continue
        raise OSError('history refused: ' + text[:200])
    lines = [{'epoch': e['epoch'], 'label': 'history', 'who': e.get('who'), 'touched': e['touched'], 'with': e.get('with') or {}} for e in page['events']]
    return lines, (page.get('next') or (lines[-1]['epoch'] if lines else seen))


def follow(base, node, seen=0, interval=2.0, log=print):
    """Yield lines forever: from the stream while it is open, from the poll while it is not."""
    while True:
        stream = None
        try:
            stream = Stream(base)
            log('following /mcp/stream')
            # anything that happened between the last line seen and the stream opening comes from one poll
            lines, seen = poll(base, node, seen)
            for line in lines:
                yield line
            while True:
                line = stream.event()
                if 'epoch' in line:
                    seen = max(seen, line['epoch'])
                yield line
        except (OSError, EOFError, ValueError) as e:
            log(f'stream unavailable ({e}); polling')
        finally:
            if stream:
                stream.close()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                lines, seen = poll(base, node, seen)
            except Exception as e:
                log(f'poll failed: {e}')
                lines = []
            for line in lines:
                yield line
            time.sleep(interval)
