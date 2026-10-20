"""The export hand: a folder as a file, for the person who needs a sheet. An agent asks by writing a request record
under /agent/hands/export/: {folder, format (json or csv), path}. The hand reads the folder paged, writes the file,
and pokes the request with done, the path and the row count. The plug is write_file(path, format, rows); a second
format is a function with that shape.

    python3 export.py <base> [--node 0x11] [--once]
"""
import csv
import importlib.util
import json
import os

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand = _hand.World, _hand.Hand


def rows_of(view):
    """Every record below the root, as (path, slots), folders looked through."""
    out = []

    def walk(n):
        for ch in n.get('children', []):
            if ch.get('exists'):
                out.append((ch['path'], {k.lstrip('/'): v for k, v in (ch.get('properties') or {}).items()}))
            walk(ch)
    walk(view)
    return out


def write_file(path, fmt, rows):
    """The plug: rows as JSON (a list of {path, slots}) or CSV (path, then every slot name seen)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    if fmt == 'csv':
        names = sorted({k for _, slots in rows for k in slots})
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['path'] + names)
            for p, slots in rows:
                w.writerow([p] + [slots.get(n, '') for n in names])
    else:
        with open(path, 'w') as f:
            json.dump([{'path': p, 'slots': slots} for p, slots in rows], f, indent=1)
    return len(rows)


class Export(Hand):
    name = 'export'
    every = 30.0

    def __init__(self, world, log=print, plug=write_file, **overrides):
        super().__init__(world, log=log, **overrides)
        self.plug = plug

    def pending(self):
        """Requests with no done slot."""
        home = self.w.read(self.home, 'y')
        return [(ch['path'], ch.get('properties') or {}) for ch in home.get('children', [])
                if ch.get('exists') and ch['path'].rsplit('/', 1)[1] not in ('seen',) and '/done' not in (ch.get('properties') or {})]

    def serve(self, request, props):
        folder, fmt, path = props.get('/folder'), props.get('/format') or 'json', props.get('/path')
        if not folder or not path:
            self.update(request, {'done': True, 'error': 'a request needs /folder and /path'})
            return 1
        rows = rows_of(self.w.read_all(folder, 'z'))
        count = self.plug(path, fmt, rows)                    # the whole file first, then the one write
        self.update(request, {'done': True, 'path': path, 'rows': count})
        self.log(f'export {request}: {count} rows to {path}')
        return 1

    def line(self, line):
        touched = line.get('touched') or []
        if not any(t.startswith(self.home + '/') for t in touched):
            return 0
        return sum(self.serve(r, p) for r, p in self.pending())

    def tick(self, now):
        return sum(self.serve(r, p) for r, p in self.pending())


if __name__ == '__main__':
    _hand.run(Export)
