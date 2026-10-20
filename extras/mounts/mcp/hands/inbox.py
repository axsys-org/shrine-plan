"""The inbox hand: a note to an agent wakes its reader.

    python3 inbox.py <base> [--node 0x11] [--once]

A chat session does nothing between turns, so nothing reads its inbox on its own. This hand follows the stream and,
when a line writes a record under /agent/<name>/inbox or a record carrying `to: <name>`, nudges that agent through the
plug its config names: /agent/hands/inbox/to/<name> {url} posts {to, from, epoch, paths} as JSON to the URL;
{command} runs the command in a shell with INBOX_TO, INBOX_FROM, INBOX_EPOCH and INBOX_PATHS in its environment and
the same JSON on stdin. A name with no plug is logged and the note waits where it is. The hand never writes.
"""
import importlib.util
import json
import os
import re
import subprocess
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand = _hand.World, _hand.Hand


def post(url, payload, timeout=10):
    """The URL plug: one JSON POST."""
    req = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status


def run(command, payload, timeout=30):
    """The command plug: a shell command with the note in its environment and on stdin."""
    env = dict(os.environ, INBOX_TO=payload['to'], INBOX_FROM=str(payload.get('from') or ''), INBOX_EPOCH=str(payload.get('epoch') or ''),
               INBOX_PATHS=' '.join(payload['paths']))
    # output goes nowhere: a command that backgrounds a long run (nohup ... &) must not hold a pipe to this hand
    return subprocess.run(command, shell=True, env=env, input=json.dumps(payload), text=True, timeout=timeout,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


PLUGS = {'post': post, 'run': run}


class Inbox(Hand):
    name = 'inbox'
    every = 60.0

    def __init__(self, world, log=print, plugs=None, **overrides):
        super().__init__(world, log=log, **overrides)
        self.plugs = dict(PLUGS, **(plugs or {}))
        self.nudged = 0

    def addressed(self, line):
        """Who a line is for: {name: [paths]}, from the inbox paths it touched and the `to` slots it wrote."""
        out = {}
        mailbox = re.compile(re.escape('/' + self.w.node) + r'/agent/([A-Za-z][A-Za-z0-9_]*)/inbox/[^/]+')
        for path in line.get('touched') or []:
            m = mailbox.match(path)
            if m:
                out.setdefault(m.group(1), set()).add(path)
        for path, view in (line.get('with') or {}).items():
            if path.startswith('/x/') or path.startswith('/c/'):
                continue
            to = (view.get('properties') or {}).get('/to')
            if isinstance(to, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', to):
                out.setdefault(to, set()).add(path)
        return {name: sorted(paths) for name, paths in out.items()}

    def plug_for(self, name):
        record = self.w.read(self.home + '/to/' + name, 'x').get('properties') or {}
        return {k.lstrip('/'): v for k, v in record.items() if not k.startswith('/sys')}

    def line(self, line):
        for name, paths in self.addressed(line).items():
            cfg = self.plug_for(name)
            payload = {'to': name, 'from': line.get('who'), 'epoch': line.get('epoch'), 'paths': paths}
            if not (cfg.get('url') or cfg.get('command')):
                self.log(f'inbox: no plug for {name}; the note waits at {paths[0]}')
                continue
            try:
                if cfg.get('url'):
                    self.plugs['post'](cfg['url'], payload)
                if cfg.get('command'):
                    self.plugs['run'](cfg['command'], payload)
                self.nudged += 1
                self.log(f'inbox: nudged {name} about {", ".join(paths)}')
            except Exception as e:                  # the next note nudges again; nothing is retried on its own
                self.log(f'inbox: nudge for {name} failed: {e}')
        return 0                                    # the hand never writes

    def tick(self, now):
        return 0


if __name__ == '__main__':
    _hand.run(Inbox)
