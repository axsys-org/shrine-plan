"""The import hand: where the data actually lives. On a schedule it reads a source and writes batches under a folder,
who: import:<source>, the source id kept as a slot, and references made once with the reference entry, so the data is
native from the first sync. Idempotent: a second run over the same source writes nothing new.

Config is records under /agent/hands/import/<source>:
    /agent/hands/import/<source>            {kind: csv | json, source: <file path or url>, folder: /user/...,
                                             key: <the field whose value names the record>, every: <seconds>}
    /agent/hands/import/<source>/map        {<field>: <slot name>, ...}   the field-to-slot mapping, a record not code
    /agent/hands/import/<source>/refs/<slot> {table: /user/..., match: <slot of the table>}   references to make once
The plugs: read_csv(source) and read_json(source), each returning rows as dicts; a second source kind is a function
with that shape, named in the kind slot.

    python3 import_.py <base> [--node 0x11] [--once]
"""
import csv
import importlib.util
import json
import os
import re
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, live = _hand.World, _hand.Hand, _hand.live


def read_csv(source):
    with open(source, newline='') as f:
        return list(csv.DictReader(f))


def read_json(source):
    if source.startswith('http://') or source.startswith('https://'):
        with urllib.request.urlopen(source, timeout=60) as r:
            return json.load(r)
    with open(source) as f:
        return json.load(f)


PLUGS = {'csv': read_csv, 'json': read_json}


segment = _hand.segment_of


def typed(value, key=False):
    """A source value as a slot: the key field is always text, and so is a digit string with a leading zero (a zip code,
    an account number); a text that looks like a number is sent as {type: str} so the world keeps it text. Otherwise a
    whole number is a number, a decimal a decimal, the rest text."""
    text = str(value)
    if key or re.fullmatch(r'-?0\d+(\.\d+)?', text):
        return {'type': 'str', 'value': text} if re.fullmatch(r'-?\d+(\.\d+)?', text) else text
    if re.fullmatch(r'-?\d+', text):
        return int(text)
    if re.fullmatch(r'-?\d+\.\d+', text):
        return float(text)
    return text


def shown(value):
    """The text a slot value reads back as."""
    return value['value'] if isinstance(value, dict) else str(value)


class Import(Hand):
    name = 'import'
    every = 60.0

    def __init__(self, world, log=print, plugs=None, **overrides):
        super().__init__(world, log=log, **overrides)
        self.plugs = dict(PLUGS, **(plugs or {}))

    def sources(self):
        home = self.w.read(self.home, 'y')
        return [(ch['path'], {k.lstrip('/'): v for k, v in (ch.get('properties') or {}).items()})
                for ch in home.get('children', []) if ch.get('exists') and ch['path'].rsplit('/', 1)[1] != 'seen']

    def sync(self, config_path, config, now):
        name = config_path.rsplit('/', 1)[1]
        kind, source, folder, key = config.get('kind'), config.get('source'), config.get('folder'), config.get('key')
        every = float(config.get('every') or 0)
        ran = float(config.get('ran') or 0)
        if not (kind and source and folder and key) or (ran and now - ran < every):
            return 0
        # the map record's slot names are the fields as names (full name is full_name): a field maps through its name
        mapping = {k.lstrip('/'): v for k, v in (self.w.read(config_path + '/map', 'x').get('properties') or {}).items()}
        rows = self.plugs[kind](source)
        who = 'import:' + name
        existing = {ch['path'].rsplit('/', 1)[1]: ch.get('properties') or {} for ch in self.w.read_all(folder, 'y').get('children', []) if ch.get('exists')}
        records = []
        for row in rows:
            if key not in row:
                continue
            slots = {mapping.get(segment(field), segment(field)): typed(value, key=field == key) for field, value in row.items()}
            slots['source_id'] = typed(row[key], key=True)
            path = folder + '/' + segment(row[key])
            current = existing.get(path.rsplit('/', 1)[1])
            wanted = {'/' + k: shown(v) for k, v in slots.items()}
            if current is not None and all(current.get(k) == v for k, v in wanted.items()):
                continue                                  # the record is already what the source says
            records.append({'path': path, 'slots': slots, 'action': 'poke' if current is not None else 'make'})
        written = 0
        for start in range(0, len(records), 200):
            self.w.tool('write', records=records[start:start + 200], who=who)
            written += len(records[start:start + 200])
        written += self.references(config_path, folder, who)
        self.w.tool('write', records=[{'path': config_path, 'action': 'poke', 'slots': {'ran': int(now), 'rows': len(rows)}}], who=who)
        self.log(f'import {name}: {len(rows)} rows, {written} written')
        return written

    def references(self, config_path, folder, who):
        """References made once with the reference entry: a kept cell over the folder answers the pointer for each
        row, and rows that lack it get it; rows that have it are left alone."""
        refs = self.w.read(config_path + '/refs', 'y')
        made = 0
        stdlib = None
        for ch in refs.get('children', []):
            if not ch.get('exists'):
                continue
            slot = ch['path'].rsplit('/', 1)[1]
            props = ch.get('properties') or {}
            table, match = props.get('/table'), props.get('/match') or slot
            if not table:
                continue
            if stdlib is None:
                stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']}
                          for c in self.w.read('/' + self.w.node + '/weft/stdlib', 'y', limit=100)['children']}
            cell = config_path + '/refs/' + slot + '/cell'
            into = '/' + slot + '_ref'
            self.w.tool('write', records=[{'path': cell, 'slots': {'sys/weft': stdlib['reference'], 'sys/tack': live(folder, 'y'),
                                                                   'key': '/' + slot, 'match': '/' + match, 'into': into, 'table': live(table, 'y')}}], who=who)
            answer = self.w.read_all('/x' + cell, 'y')
            records = []
            for row in answer.get('children', []):
                ref = (row.get('properties') or {}).get(into)
                target = folder + '/' + row['path'].rsplit('/', 1)[1]
                if ref and into not in (self.w.read(target, 'x').get('properties') or {}):
                    records.append({'path': target, 'action': 'poke', 'slots': {slot + '_ref': {'type': 'reference', 'value': ref}}})
            if records:
                self.w.tool('write', records=records, who=who)
                made += len(records)
        return made

    def tick(self, now):
        return sum(self.sync(path, config, now) for path, config in self.sources())


if __name__ == '__main__':
    _hand.run(Import)
