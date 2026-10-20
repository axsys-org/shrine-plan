"""The watch hand: tells a person, not a page. It watches named cells; when a line touches the world it reads each
watched cell, compares the answer to the last value it kept at /agent/hands/watch/<cell>, and posts on change.
Config: /agent/hands/watch {cells: "/user/views/a /user/views/b", url: <webhook>}; --cells and --url override.
The plug is post(url, payload): a JSON POST (Slack is a URL). A second plug is a function with that shape.

    python3 watch.py <base> [--node 0x11] [--cells "/user/views/total"] [--url http://...] [--once]
"""
import importlib.util
import json
import os
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand = _hand.World, _hand.Hand


def post(url, payload, timeout=30):
    """The plug: one JSON POST."""
    req = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


key_of = _hand.segment_of


class Watch(Hand):
    name = 'watch'
    every = 60.0

    def __init__(self, world, log=print, plug=post, **overrides):
        super().__init__(world, log=log, **overrides)
        self.plug = plug

    def cells(self):
        return [c for c in (self.setting('cells') or '').split() if c]

    def check(self, cell):
        """One cell: its answer now against the last value kept; a change is posted, then kept (write-if-unchanged)."""
        answer = self.w.read('/x' + cell, 'x')
        now = json.dumps(answer.get('properties') or {}, sort_keys=True) if answer.get('exists') else ''
        kept = self.home + '/' + key_of(cell)
        last = self.w.read(kept, 'x').get('properties') or {}
        if last.get('/value') == now:
            return 0
        if '/value' in last:
            url = self.setting('url')
            if url:
                self.plug(url, {'cell': cell, 'before': json.loads(last['/value']) if last['/value'] else None,
                                'after': json.loads(now) if now else None, 'epoch': self.seen})
            self.log(f'watch {cell}: changed')
            posted = 1
        else:
            posted = 0                                  # the first look keeps the value; there is nothing to compare yet
        self.update(kept, {'cell': cell, 'value': now}, action='make')
        return posted

    def line(self, line):
        return sum(self.check(cell) for cell in self.cells())

    def tick(self, now):
        return sum(self.check(cell) for cell in self.cells())


if __name__ == '__main__':
    _hand.run(Watch, settings=('cells', 'url'))
