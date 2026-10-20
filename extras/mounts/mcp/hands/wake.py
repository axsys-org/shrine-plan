"""wake: the watch an agent runs for itself on the paths it owns and the paths it depends on.

    python3 wake.py <base> --name <you> [--own /user/team ...] [--run "<command>"] [--node 0x11] [--interval 2]

An agent is a name that owns paths (/agent/<name>, and any --own) and depends on paths (what the cells under its
folders point at: their tack and their reference slots). A wake is a stream line, not signed by the agent, that
touches one of those paths or anything beneath. The paths are the address; there is no field to fill. The command
is the agent's own plumbing (the setup page has the commands for the apps we know): it runs in a shell with
WAKE_NAME, WAKE_FROM, WAKE_EPOCH and WAKE_PATHS set and the line as JSON on stdin, one run at a time; lines that
land while a run is going wait and run once together after it. Without --run the wakes are printed. Never writes.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, stream_follow = _hand.World, _hand.stream_follow


def start(command, payload):
    """The plug: the command, started and left running; its output goes nowhere (a run that backgrounds itself holds
    no pipe to the watch). Returns the process."""
    env = dict(os.environ, WAKE_NAME=payload['name'], WAKE_FROM=str(payload.get('from') or ''),
               WAKE_EPOCH=str(payload.get('epoch') or ''), WAKE_PATHS=' '.join(payload['paths']))
    process = subprocess.Popen(command, shell=True, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    try:
        process.stdin.write(json.dumps(payload)); process.stdin.close()
    except OSError:
        pass
    return process


def under(path, folder):
    return path == folder or path.startswith(folder + '/')


def target_of(reference):
    """The world path a reference names: /h/<care>/<case>/<len>/<path>, a cell's /x stripped."""
    parts = str(reference).split('/')
    if len(parts) < 6 or parts[1] != 'h':
        return None
    path = '/' + '/'.join(parts[5:])
    return path[2:] if path.startswith('/x/') else path


class Wake:
    def __init__(self, world, name, own=(), run=None, plug=start, log=print):
        self.w, self.name, self.run, self.plug, self.log = world, name, run, plug, log
        node = '/' + world.node
        self.owned = [node + '/agent/' + name] + [p if p.startswith(node + '/') else node + p for p in own]
        self.process = None
        self.waiting = []           # paths that landed while a run was going

    def depends(self):
        """The paths the cells under the owned folders point at, read now."""
        out = set()
        for folder in self.owned:
            for ch in self.w.read_all(folder, 'y').get('children', []):
                for key, value in (ch.get('properties') or {}).items():
                    if key in ('/sys/weft',):
                        continue
                    ref = value.get('value') if isinstance(value, dict) else value
                    if isinstance(ref, str) and ref.startswith('/h/'):
                        t = target_of(ref)
                        if t:
                            out.add(t)
        return sorted(out)

    def matches(self, line):
        """The touched paths that fall under something owned or depended on."""
        folders = self.owned + self.depends()
        return sorted({t for t in line.get('touched') or [] if any(under(t, f) for f in folders)})

    def line(self, line):
        """True when the line woke the agent (or joined a run already going)."""
        if (line.get('who') or '') == self.name:
            return False
        paths = self.matches(line)
        if not paths:
            return False
        self.log(f'wake {self.name}: {line.get("who")} touched {", ".join(paths)} at {line.get("epoch")}')
        if not self.run:
            return True
        if self.process is not None and self.process.poll() is None:
            self.waiting = sorted(set(self.waiting) | set(paths))
            return True
        self.process = self.plug(self.run, {'name': self.name, 'from': line.get('who'), 'epoch': line.get('epoch'), 'paths': paths})
        return True

    def settle(self):
        """After a run ends, one more run for what landed meanwhile."""
        if self.waiting and self.run and (self.process is None or self.process.poll() is not None):
            paths, self.waiting = self.waiting, []
            self.process = self.plug(self.run, {'name': self.name, 'from': None, 'epoch': None, 'paths': paths})

    def follow(self, lines):
        for item in lines:
            if 'epoch' in item:
                self.line(item)
            self.settle()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('base'); p.add_argument('--name', required=True); p.add_argument('--own', action='append', default=[])
    p.add_argument('--run', default=None); p.add_argument('--node', default='0x11'); p.add_argument('--interval', type=float, default=2.0)
    a = p.parse_args(argv)
    world = World(a.base, a.node)
    seen = json.load(__import__('urllib.request').request.urlopen(a.base + '/probe/read?path=/' + a.node, timeout=30)).get('epoch', 0) if a.base else 0
    watch = Wake(world, a.name, own=a.own, run=a.run)
    print(f'wake {a.name}: owns {", ".join(watch.owned)}; depends on {", ".join(watch.depends()) or "nothing yet"}; from epoch {seen}', flush=True)
    watch.follow(stream_follow(a.base, a.node, seen=seen, interval=a.interval, log=print))


if __name__ == '__main__':
    sys.exit(main())
