"""Rows: a csv with a header, or a json array of objects (or an object of id -> object). Eager: every row is a region
on first contact. The locator is the key column (`key` on the artifact record; the first column without it), the
row's path its value as a name; `row` is the position (the line in the file, the header being 1). Every column is a
slot in the header's words, numbers as numbers, a digit string with a leading zero as text."""
import csv
import hashlib
import json
import os
import re
import urllib.request


eager = True


def segment_of(text):
    key = re.sub(r'[^A-Za-z0-9_]', '_', str(text).strip()) or 'empty'
    return key if re.match(r'[A-Za-z]', key) else 'c_' + key


def typed(value, key=False):
    """A source value as a slot: the key field is always text, and so is a digit string with a leading zero (a zip
    code, an account number); a whole number is a number, a decimal a decimal, the rest text."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)) and not key:
        return value
    text = str(value)
    if key or re.fullmatch(r'-?0\d+(\.\d+)?', text):
        return {'type': 'str', 'value': text} if re.fullmatch(r'-?\d+(\.\d+)?', text) else text
    if re.fullmatch(r'-?\d+', text):
        return int(text)
    if re.fullmatch(r'-?\d+\.\d+', text):
        return float(text)
    return text


def fetch(where):
    if where.startswith('http://') or where.startswith('https://'):
        with urllib.request.urlopen(where, timeout=60) as r:
            return r.read()
    with open(where, 'rb') as f:
        return f.read()


def marker(source):
    where = source['where']
    if os.path.isfile(where):
        st = os.stat(where)
        return 'mtime %d size %d' % (int(st.st_mtime), st.st_size)
    return 'sha256 ' + hashlib.sha256(fetch(where)).hexdigest()[:16]


def rows(source):
    """(key, line, row dict) for every row."""
    where = source['where']
    raw = fetch(where)
    if where.endswith('.json'):
        data = json.loads(raw.decode())
        items = list(data.items()) if isinstance(data, dict) else list(enumerate(data))
        key = source.get('key')
        out = []
        for i, (k, item) in enumerate(items):
            if not isinstance(item, dict):
                continue
            ident = item.get(key) if key else (k if isinstance(data, dict) else item.get('id', i))
            if ident is None:
                continue
            out.append((ident, i + 1, item))
        return out
    lines = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    key = source.get('key') or (next(iter(lines[0])) if lines else None)
    return [(r[key], i + 2, r) for i, r in enumerate(lines) if key in r and r[key] not in (None, '')]


def skeleton(source):
    return [segment_of(k) for k, _, _ in rows(source)]


def regions(source, paths):
    wanted = set(paths)
    key = source.get('key')
    out = {}
    for ident, line, row in rows(source):
        name = segment_of(ident)
        if name not in wanted:
            continue
        slots = {segment_of(field): typed(value, key=(field == key)) for field, value in row.items() if field is not None}
        slots['row'] = line
        out[name] = slots
    return out


def write(source, path, slots):
    """Put a region's slots back into its row, and nothing else: the file is rewritten with that one row changed,
    its columns in their order; a slot that is not a column (the position, a slot added in the world) is ignored."""
    where = source['where']
    if where.startswith('http://') or where.startswith('https://'):
        raise RuntimeError('a fetched source is not written back')
    raw = fetch(where)
    if where.endswith('.json'):
        data = json.loads(raw.decode())
        key = source.get('key')
        items = data.items() if isinstance(data, dict) else enumerate(data)
        for k, item in items:
            if not isinstance(item, dict):
                continue
            ident = item.get(key) if key else (k if isinstance(data, dict) else item.get('id'))
            if ident is not None and segment_of(ident) == path:
                fields = {segment_of(f): f for f in item}
                for name, value in slots.items():
                    if name in fields and name != 'row':
                        item[fields[name]] = value
                break
        with open(where, 'w') as f:
            json.dump(data, f, indent=1)
        return
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    reader = list(csv.reader(lines))
    header = reader[0]
    key = source.get('key') or header[0]
    ki = header.index(key)
    fields = {segment_of(f): i for i, f in enumerate(header)}
    for row in reader[1:]:
        if len(row) > ki and segment_of(row[ki]) == path:
            for name, value in slots.items():
                if name in fields and name != 'row':
                    row[fields[name]] = shown(value)
            break
    with open(where, 'w', newline='') as f:
        csv.writer(f, lineterminator='\n').writerows(reader)


def shown(v):
    return v.get('value') if isinstance(v, dict) else str(v)
