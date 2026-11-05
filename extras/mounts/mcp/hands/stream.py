"""Follow a world's commits: GET /mcp/stream as server-sent events, pushed by the world as it commits, one per commit
from any writer (MCP, a page, a mount, the filesystem, a reaction): {epoch, who, touched, touched_count, woke,
woke_count}, with the epoch as the event id; and {shown} (no epoch) for a presented read. `woke` is the cells the
commit woke through the reverse index: the cells it wrote and the cells reading what it changed, transitively.

A stream opened without `after` starts at the top and says where, as the comment ": at <epoch>". A stream opened with
?after=<epoch> first replays every commit after that epoch from the world's journal, then goes live, with no gap and
no repeat. follow() keeps the last epoch it yielded and reconnects with it, so a dropped connection or a restarted
world loses nothing. Nothing here polls: between commits the socket is silent.

    for line in follow(base, seen=epoch):     # seen None: from now
        ...
"""
import json
import socket
import time
import urllib.parse


class Stream:
    """A raw socket on GET /mcp/stream[?after=<epoch>]; at is the epoch a live open started from."""

    def __init__(self, base, after=None, timeout=None):
        u = urllib.parse.urlparse(base)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=30)
        self.sock.settimeout(timeout)
        target = '/mcp/stream' + ('' if after is None else '?after=' + str(int(after)))
        self.sock.sendall(('GET ' + target + ' HTTP/1.0\r\nHost: localhost\r\n\r\n').encode())
        self.buf = b''
        self.at = after
        head = self._until(b'\r\n\r\n')
        if b'200' not in head.split(b'\r\n')[0] or b'text/event-stream' not in head:
            raise OSError('no stream at /mcp/stream')

    def _until(self, marker):
        while marker not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError('stream closed')
            self.buf += chunk
        head, self.buf = self.buf.split(marker, 1)
        return head

    def event(self):
        """The next event's data, parsed; a ": at <epoch>" comment sets self.at on the way."""
        while True:
            lines = self._until(b'\r\n\r\n').decode().split('\r\n')
            for l in lines:
                if l.startswith(': at '):
                    self.at = int(l[5:])
            data = [l[6:] for l in lines if l.startswith('data: ')]
            if data:
                return json.loads(''.join(data))

    def opened_at(self):
        """The epoch a live open started from: the ": at" comment, sent before any event."""
        while self.at is None:
            for l in self._until(b'\r\n\r\n').decode().split('\r\n'):
                if l.startswith(': at '):
                    self.at = int(l[5:])
        return self.at

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def follow(base, seen=None, log=print, retry=1.0):
    """Yield lines forever, in epoch order, each commit once. seen is the last epoch already handled (None: from now);
    after a drop the stream is reopened with after=<last epoch yielded>, retrying the connection every `retry` seconds
    while the world is down (a retry on failure, not a wait for change)."""
    while True:
        stream = None
        try:
            stream = Stream(base, seen)
            while True:
                line = stream.event()
                if seen is None:
                    seen = stream.at
                if 'epoch' in line:
                    if seen is not None and line['epoch'] <= seen:
                        continue
                    seen = line['epoch']
                yield line
        except (OSError, EOFError, ValueError) as e:
            if seen is None and stream is not None:
                seen = stream.at
            log(f'stream dropped ({e}); reconnecting after {seen}')
        finally:
            if stream:
                stream.close()
        time.sleep(retry)
