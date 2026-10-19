"""The whole cell signature, formula x context x (x|y|z) x (x|y|z)* -> context' x (x|y|z), against an oracle.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/signature.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
check(base, node, timeout, seed=None, cases=1000): prints the seed (rerun with it), generates `cases` random cells
(shapes at every care, 0-2 secondary inputs, valid and invalid settings, chains through /x), writes them in batches,
and compares every /x tree and /c/x context with the oracle below. The oracle is written from the skill
(skills/shrine-mcp/SKILL.md) and the worked examples in shapes.py, never from the implementation.
"""
import json
import math
import random
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

# ============================================================================ the tree model
# A tree is {'props': {slot: text}, 'kids': {name: tree}, 'rec': bool}; props are rendered as a read renders them
# ('/n': '12', '/ok': 'true'); rec False is a folder with no record of its own (never a row, renders as {}).


def node(props=None, kids=None, rec=True):
    return {'props': dict(props or {}), 'kids': dict(kids or {}), 'rec': rec}


def clone(t):
    return {'props': dict(t['props']), 'kids': {k: clone(v) for k, v in t['kids'].items()}, 'rec': t['rec']}


def strip(t):
    """What a read shows: the props and the kids, record or folder alike."""
    return {'props': dict(t['props']), 'kids': {k: strip(v) for k, v in t['kids'].items()}}


def cut(t, care):
    """A tree at a care. y is the record and its children: a read descends through folders without a record of
    their own to the nearest records (a folder's children are the records beneath it), and stops there."""
    if care == 'x':
        return node(t['props'], rec=t['rec'])
    if care == 'y':
        return node(t['props'], {k: node(v['props']) if v['rec'] else cut(v, 'y') for k, v in t['kids'].items()}, t['rec'])
    return clone(t)


def cut_read(view, care):
    """A read's own z tree cut to a care, by the same rule, using the exists flag the read carries."""
    if care == 'x':
        return {'props': view.get('properties', {}), 'kids': {}}
    if care == 'y':
        return {'props': view.get('properties', {}), 'kids': {ch['path'].rsplit('/', 1)[1]: ({'props': ch.get('properties', {}), 'kids': {}} if ch['exists'] else cut_read(ch, 'y'))
                                                              for ch in view.get('children', [])}}
    return {'props': view.get('properties', {}), 'kids': {ch['path'].rsplit('/', 1)[1]: cut_read(ch, 'z') for ch in view.get('children', [])}}


def rows(t, care):
    """The rows of an input: every record strictly below the root within the care, in read order (names sorted,
    parents before children); folders without a record are not rows (convention one), and at y they are
    looked through to the records beneath."""
    out = []

    def walk(n, rel):
        # tap order: symbol names sorted as text, then numeric names in numeric order (a bag's rows 1, 2, 3 come
        # after a row called new)
        for name in sorted(n['kids'], key=lambda nm: (1, int(nm)) if nm.isdigit() else (0, nm)):
            k = n['kids'][name]
            if k['rec']:
                out.append((rel + (name,), k))
            if care == 'z' or not k['rec']:
                walk(k, rel + (name,))
    if care != 'x':
        walk(t, ())
    return out


def key_of(rel):
    """A row's key: its name, or the path as text for a deeper row (sort, top, latest)."""
    return rel[0] if len(rel) == 1 else '/' + '/'.join(rel)


def place(t, rel, n):
    cur = t
    for seg in rel[:-1]:
        cur = cur['kids'].setdefault(seg, node(rec=False))
    cur['kids'][rel[-1]] = n


INT = re.compile(r'-?\d+$')
DEC = re.compile(r'-?\d+\.\d+$')


def is_num(text):
    return text is not None and INT.match(text) is not None


def slot_text(n, rel, slot):
    """Convention two: a child's name is the slot called name; a record's own /name wins."""
    if slot == '/name' and '/name' not in n['props']:
        return rel[-1] if rel else None
    return n['props'].get(slot)


def scale_of(n, slot):
    s = n['props'].get(slot + '/scale', n['props'].get('/scale', '0'))
    return int(s) if is_num(s) else 0


def num_of(n, slot):
    """A slot's number: a natural at the record's or the slot's scale, or the decimal the world shows for a slot with its own
    scale (already the value), signed either way."""
    v = n['props'].get(slot)
    if v is not None and DEC.match(v):
        return Fraction(v)
    return Fraction(int(v), 10 ** scale_of(n, slot)) if is_num(v) else None


def fig(v, scale):
    """A figure rendered at a scale: the magnitude rounded half up, then the sign (the world rounds magnitudes)."""
    m = math.floor(abs(v) * 10 ** scale + Fraction(1, 2))
    return str(-m if v < 0 and m else m)


def shown(props):
    """What a read shows for these props: a number slot with its own <slot>/scale is shown as the decimal it was written
    as (45 with /n/scale 1 reads 4.5), everything else as is."""
    out = dict(props)
    for k, v in props.items():
        sc = props.get(k + '/scale')
        if is_num(v) and sc is not None and is_num(sc) and int(sc) > 0:
            m, s = abs(int(v)), int(sc)
            out[k] = ('-' if int(v) < 0 else '') + str(m // 10 ** s) + '.' + str(m % 10 ** s).rjust(s, '0')
    return out


def shown_tree(t):
    return {'props': shown(t['props']), 'kids': {k: shown_tree(v) for k, v in t['kids'].items()}}


def literal(text):
    """A literal number parameter, '12' or '12.5' -> (value, scale)."""
    m = re.match(r'-?\d+(\.(\d+))?$', text or '')
    return (Fraction(text), len(m.group(2) or '')) if m else None


def truth(n, slot):
    v = n['props'].get(slot)
    return v == 'true' or (is_num(v) and int(v) != 0)


def reduce_(op, members, slot):
    """A figure over the rows' slot, aligned to the largest scale among the rows (every row's, with or without the slot)."""
    scale = max([scale_of(r, slot) for r in members], default=0)
    xs = [v for v in (num_of(r, slot) for r in members) if v is not None]
    if not xs:
        return Fraction(0), scale
    return {'sum': sum(xs), 'min': min(xs), 'max': max(xs), 'avg': sum(xs) / len(xs)}[op], scale


def arith(op, left, right):
    """Numbers are naturals: a difference below zero and a division by zero have no figure (None)."""
    (lv, ls), (rv, rs) = left, right
    scale = max(ls, rs)
    if op == 'add':
        return lv + rv, scale
    if op == 'subtract':
        return lv - rv, scale
    if op == 'multiply':
        return lv * rv, scale
    if op == 'divide':
        return (lv / rv, scale) if rv != 0 else None
    return None


def filter_rows(inp, care, pred):
    """Row formulas keep each matching row at its own path (convention one); the folders on the way stay as folders."""
    out = node(inp['props'], rec=inp['rec'])
    for rel, r in rows(inp, care):
        if pred(rel, r):
            place(out, rel, node(r['props']))
    return out


# ============================================================================ the oracle: the 33 standard cells
DEFAULT_INTO = {'count': '/count', 'sum': '/total', 'min': '/min', 'max': '/max', 'avg': '/avg', 'any': '/any', 'all': '/all'}


def evaluate(formula, params, inp, care, views, stamp=None):
    """formula x params x input (at a care; None when the tack resolves to nothing) x views {name: (tree|None, care)}
    -> (output tree, or None for unknown) and the context': missing, fault, empty views, notes."""
    ctx = {'missing': False, 'fault': False, 'empty': set(), 'notes': set()}
    if inp is None:
        ctx['fault'] = True
        return None, ctx
    for name, (tree, _) in views.items():
        if tree is None:
            ctx['empty'].add(name)
    inp = cut(inp, care)
    R = rows(inp, care)
    P = lambda k: None if k not in params else str(params[k])

    def missing():
        ctx['missing'] = True        # a missing parameter passes the input through unchanged
        return clone(inp), ctx

    def view_rows(name):
        v = views.get(name)
        return [] if v is None or v[0] is None else rows(v[0], v[1])

    def number(text):
        """A number parameter: a literal, a slot of the input root, or /views/<name>/<slot>."""
        if text is None:
            return None
        if text.startswith('/views/'):
            parts = text.split('/')
            v = views.get(parts[2])
            if not v or v[0] is None:
                return None
            slot = '/' + '/'.join(parts[3:])
            x = num_of(v[0], slot)
            return None if x is None else (x, scale_of(v[0], slot))
        if text.startswith('/'):
            x = num_of(inp, text)
            return None if x is None else (x, scale_of(inp, text))
        return literal(text)

    def side(r, text):
        if text.startswith('/'):
            x = num_of(r, text)
            return None if x is None else (x, scale_of(r, text))
        return literal(text)

    def ranked(slot, reverse):
        # the skill: ranking is by number; a row whose slot is absent or text is left out, there is no text ordering
        have = [(rel, r) for rel, r in R if slot_text(r, rel, slot) is not None and is_num(slot_text(r, rel, slot))]
        key = lambda item: num_of(item[1], slot) if slot in item[1]['props'] else Fraction(int(slot_text(item[1], item[0], slot)))
        return sorted(have, key=key, reverse=reverse)

    def with_key(rel, r):
        return node(dict(r['props'], **{'/key': key_of(rel)}))

    if formula == 'count':
        return node({P('into') or '/count': str(len(R))}), ctx
    if formula in ('sum', 'min', 'max', 'avg'):
        if P('slot') is None:
            return missing()
        v, scale = reduce_(formula, [r for _, r in R], P('slot'))
        return node({P('into') or DEFAULT_INTO[formula]: fig(v, scale), '/scale': str(scale)}), ctx
    if formula in ('any', 'all'):
        if P('slot') is None:
            return missing()
        hits = [truth(r, P('slot')) for _, r in R]
        return node({P('into') or DEFAULT_INTO[formula]: 'true' if (any(hits) if formula == 'any' else all(hits)) else 'false'}), ctx
    if formula == 'where':
        key, value, op = P('key'), P('value'), P('op') or 'equals'
        if key is None or value is None:
            return missing()
        lit = literal(value)

        def match(rel, r):
            t = slot_text(r, rel, key)
            if t is None:
                return False
            if op == 'equals':
                return (num_of(r, key) if key in r['props'] else Fraction(int(t))) == lit[0] if is_num(t) and lit else t == value
            if op in ('over', 'after', 'under', 'before'):
                if not is_num(t) or lit is None:
                    return False
                v = num_of(r, key) if key in r['props'] else Fraction(int(t))
                return v > lit[0] if op in ('over', 'after') else v < lit[0]
            return op == 'contains' and value in t
        return filter_rows(inp, care, match), ctx
    if formula == 'sort':
        if P('slot') is None:
            return missing()
        order = ranked(P('slot'), (P('order') or 'asc') == 'desc')
        return node(inp['props'], {str(i + 1): with_key(rel, r) for i, (rel, r) in enumerate(order)}, inp['rec']), ctx
    if formula == 'top':
        if P('slot') is None:
            return missing()
        order = ranked(P('slot'), True)[:int(P('count') or 3)]
        return node(inp['props'], {str(i + 1): with_key(rel, r) for i, (rel, r) in enumerate(order)}, inp['rec']), ctx
    if formula in ('latest', 'earliest'):
        if P('slot') is None:
            return missing()
        order = ranked(P('slot'), formula == 'latest')
        return (with_key(*order[0]) if order else None), ctx      # no child: nothing to be the root
    if formula == 'each':
        left, op, right, into = P('left'), P('op'), P('right'), P('into')
        if None in (left, op, right, into):
            return missing()
        out = clone(inp)
        for rel, r in rows(out, care):
            l, rr = side(r, left), side(r, right)
            res = arith(op, l, rr) if l and rr else None
            if res:
                r['props'][into] = fig(*res)
                r['props']['/scale'] = str(res[1])
        return out, ctx
    if formula == 'join':
        wanted = (P('slots') or '').split()
        if not wanted:
            return missing()
        sep = ' ' if P('with') is None else P('with')
        into = P('into') or '/joined'
        out = clone(inp)
        for rel, r in rows(out, care):
            texts = [t for t in (slot_text(r, rel, w) for w in wanted) if t is not None]
            if texts:
                r['props'][into] = sep.join(texts)
        return out, ctx
    if formula == 'match':
        key, value, op = P('key'), P('value'), P('op') or 'contains'
        if key is None or value is None:
            return missing()

        def hit(rel, r):
            t = slot_text(r, rel, key)
            if t is None:
                return False
            return t.startswith(value) if op == 'starts' else t.endswith(value) if op == 'ends' else value in t
        return filter_rows(inp, care, hit), ctx
    if formula == 'split':
        slot = P('slot')
        if slot is None:
            return missing()
        sep = ' ' if P('with') is None else P('with')
        into = P('into') or slot
        out = clone(inp)
        for rel, r in rows(out, care):
            t = slot_text(r, rel, slot)
            if t is not None:
                for i, part in enumerate(t.split(sep) if sep else [t], 1):
                    r['props'][into + '/' + str(i)] = part
        return out, ctx
    if formula == 'date':
        slot = P('slot')
        if slot is None:
            return missing()
        into = P('into') or '/day'
        out = clone(inp)
        for rel, r in rows(out, care):
            t = slot_text(r, rel, slot)
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})', t or '')
            if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
                r['props'][into] = str(int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3)))
        return out, ctx
    if formula == 'lookup':
        key, take = P('key'), P('take')
        match, into, frm = P('match') or key, P('into') or take, P('from') or 'table'
        if key is None or take is None or frm not in views:
            return missing()
        table = view_rows(frm)
        out = clone(inp)
        for rel, r in rows(out, care):
            kv = slot_text(r, rel, key)
            for trel, tr in table:
                if kv is not None and slot_text(tr, trel, match) == kv:
                    tv = slot_text(tr, trel, take)
                    if tv is not None:
                        r['props'][into] = tv
                    break
        return out, ctx
    if formula == 'distinct':
        if P('slot') is None:
            return missing()
        counts = {}
        for rel, r in R:
            v = slot_text(r, rel, P('slot'))
            if v is not None:
                counts[v] = counts.get(v, 0) + 1
        return node(inp['props'], {str(i + 1): node({'/value': v, '/count': str(c)}) for i, (v, c) in enumerate(counts.items())}, inp['rec']), ctx
    if formula == 'select':
        if P('slots') is None:
            return missing()
        wanted = P('slots').split()
        out = clone(inp)

        def narrow(n, rel):
            n['props'] = {s: slot_text(n, rel, s) for s in wanted if slot_text(n, rel, s) is not None}
        narrow(out, ())
        for rel, r in rows(out, care):
            narrow(r, rel)
        return out, ctx
    if formula == 'by':
        key, op, slot = P('key'), P('op') or 'count', P('slot')
        if key is None or (op != 'count' and slot is None):
            return missing()
        into = P('into') or '/' + op
        groups = {}
        for rel, r in R:
            v = slot_text(r, rel, key)
            if v is not None:
                groups.setdefault(v, []).append(r)
        out = node(inp['props'], rec=inp['rec'])
        for v, members in groups.items():
            figure, scale = (str(len(members)), 0) if op == 'count' else (lambda f, s: (fig(f, s), s))(*reduce_(op, members, slot))
            out['kids'][v] = node({'/value': v, into: figure, '/scale': str(scale)})
        return out, ctx
    if formula == 'grid':
        row, col, op, slot = P('row'), P('col'), P('op') or 'count', P('slot')
        if row is None or col is None or (op != 'count' and slot is None):
            return missing()
        cells = {}
        for rel, r in R:
            rv, cv = slot_text(r, rel, row), slot_text(r, rel, col)
            if rv is not None and cv is not None:
                cells.setdefault(rv, {}).setdefault(cv, []).append(r)
        out = node(inp['props'], rec=inp['rec'])
        for rv, cols in cells.items():
            out['kids'][rv] = node({'/' + cv: (str(len(m)) if op == 'count' else fig(*reduce_(op, m, slot))) for cv, m in cols.items()})
        return out, ctx
    if formula == 'flatten':
        return node(inp['props'], {'_'.join(rel): node(r['props']) for rel, r in R}, inp['rec']), ctx
    if formula == 'merge':
        out = clone(inp)
        for name in sorted(views):
            tree, vcare = views[name]
            if tree is not None:
                out['kids'].update(cut(tree, vcare)['kids'])
        return out, ctx
    if formula == 'gather':
        # the skill: each secondary input lands whole under its slot name, root and children; a root without a
        # record, or an empty view, is an empty record there
        out = clone(inp)
        for name in sorted(views):
            tree, vcare = views[name]
            nested = clone(cut(tree, vcare)) if tree is not None else node({})
            nested['rec'] = True
            nested['props'] = nested.get('props') or {}
            out['kids'][name] = nested
        return out, ctx
    if formula in ('except', 'intersect', 'diff'):
        frm, key = P('from') or 'other', P('key')
        if frm not in views:
            return missing()

        def ident(rel, r):
            return slot_text(r, rel, key) if key else key_of(rel)
        # the skill: every row counts (no collapsing of repeated values); a row without an identity is kept by except,
        # dropped by intersect and ignored by diff; changed compares a row with the FIRST other row of the same identity
        theirs = [(ident(rel, r), rel, r) for rel, r in view_rows(frm) if ident(rel, r) is not None]
        others = {}
        for i, rel, r in theirs:
            others.setdefault(i, (rel, r))
        if formula == 'except':
            return filter_rows(inp, care, lambda rel, r: ident(rel, r) not in others), ctx
        if formula == 'intersect':
            return filter_rows(inp, care, lambda rel, r: ident(rel, r) is not None and ident(rel, r) in others), ctx
        mine_rows = [(ident(rel, r), rel, r) for rel, r in R if ident(rel, r) is not None]
        mine = {}
        for i, rel, r in mine_rows:
            mine.setdefault(i, (rel, r))
        added = [(rel, r) for i, rel, r in mine_rows if i not in others]
        removed = [(rel, r) for i, rel, r in theirs if i not in mine]
        changed = [(rel, r, others[i][1]) for i, rel, r in mine_rows if i in others and r['props'] != others[i][1]['props']]
        # the skill: the two roots' slots compare too, as one more changed row named root (from the other view's
        # root, to the input's); a root without a record is an empty one
        vt, _ = views[frm]
        mine_root = inp['props'] if inp.get('rec') else {}
        other_root = vt['props'] if vt is not None and vt.get('rec') else {}
        if mine_root != other_root:
            changed.append((('root',), node(mine_root), node(other_root)))
        out = node({'/added': str(len(added)), '/removed': str(len(removed)), '/changed': str(len(changed))})
        for name, found in (('added', added), ('removed', removed)):
            if found:
                folder = node(rec=False)
                for rel, r in found:
                    place(folder, rel, node(r['props']))
                out['kids'][name] = folder
        if changed:
            folder = node(rec=False)
            for rel, now, before in changed:
                props = {}
                for s in sorted(set(now['props']) | set(before['props'])):
                    if now['props'].get(s) != before['props'].get(s):
                        if s in before['props']:
                            props[s + '/from'] = before['props'][s]
                        if s in now['props']:
                            props[s + '/to'] = now['props'][s]
                place(folder, rel, node(props))
            out['kids']['changed'] = folder
        return out, ctx
    if formula in ('add', 'subtract', 'multiply', 'divide'):
        left, right = number(P('left')), number(P('right'))
        res = arith(formula, left, right) if left and right else None
        if res is None:
            return missing()
        return node({P('into') or '/result': fig(*res), '/scale': str(res[1])}), ctx
    if formula == 'pick':
        frm, into = P('from'), P('into')
        if frm is None or into is None:
            return missing()
        if frm.startswith('/views/'):
            parts = frm.split('/')
            v = views.get(parts[2])
            value = None if not v or v[0] is None else v[0]['props'].get('/' + '/'.join(parts[3:]))
        else:
            value = inp['props'].get(frm)
        if value is None:
            return missing()
        return node(dict(inp['props'], **{into: value})), ctx        # the root, with the slot copied onto it
    if formula == 'put':
        if P('into') is None or P('value') is None:
            return missing()
        return node(dict(inp['props'], **{P('into'): P('value')})), ctx
    if formula == 'round':
        slot, places = P('slot'), P('places')
        v = num_of(inp, slot) if slot else None
        if v is None or not is_num(places):
            return missing()
        return node({P('into') or slot: fig(v, int(places)), '/scale': places}), ctx
    if formula == 'since':
        slot, frm = P('slot'), number(P('from'))
        v = num_of(inp, slot) if slot else None
        if v is None or frm is None:
            return missing()
        scale = max(scale_of(inp, slot), frm[1])
        return node({P('into') or '/since': fig(v - frm[0], scale), '/scale': str(scale)}), ctx
    if formula == 'between':
        slot, lo, hi = P('slot'), number(P('from')), number(P('to'))
        if slot is None or lo is None or hi is None:
            return missing()
        return filter_rows(inp, care, lambda rel, r: num_of(r, slot) is not None and lo[0] <= num_of(r, slot) <= hi[0]), ctx
    if formula == 'amend':
        if 'notes' not in views:
            return missing()
        out = clone(inp)
        for nrel, note in view_rows('notes'):
            slot, value, case = note['props'].get('/slot'), note['props'].get('/value'), note['props'].get('/case')
            if slot is None or value is None:
                continue
            segs = slot.strip('/').split('/')
            target = out
            for seg in segs[:-1]:
                target = target['kids'].get(seg) if target else None
            if target is None or not target['rec'] and target is not out:
                ctx['notes'].add(key_of(nrel))          # dangling: the record must already exist in the answer
                continue
            target['props']['/' + segs[-1]] = value
            target['rec'] = True                        # a note on the root makes it a record
            if stamp is not None and is_num(case) and int(case) < stamp:
                ctx['notes'].add(key_of(nrel))          # behind the input's case: applies, reported
        return out, ctx
    raise ValueError(formula)


# ============================================================================ generators
FORMULAS = ['count', 'sum', 'min', 'max', 'avg', 'any', 'all', 'where', 'sort', 'top', 'latest', 'earliest', 'each', 'lookup',
            'distinct', 'select', 'by', 'grid', 'flatten', 'merge', 'gather', 'except', 'intersect', 'diff', 'add', 'subtract', 'multiply',
            'divide', 'pick', 'put', 'round', 'since', 'between', 'join', 'match', 'split', 'date']          # amend has its own stage (notes need the world's stamps)
KINDS = ['rec1', 'recN', 'recM', 'list', 'map', 'set', 'table', 'bag', 'attach', 'tree', 'grouped', 'matrix', 'hier', 'uneven']
REQUIRED = {'where': ['key', 'value'], 'each': ['left', 'right', 'op'], 'lookup': ['key', 'take'], 'select': ['slots'], 'by': ['key'],
            'grid': ['row', 'col'], 'pick': ['from', 'into'], 'put': ['into', 'value'], 'round': ['slot', 'places'],
            'since': ['slot', 'from'], 'between': ['slot', 'from', 'to'], 'join': ['slots'], 'match': ['key', 'value'],
            'split': ['slot'], 'date': ['slot']}
for _f in ('add', 'subtract', 'multiply', 'divide'):
    REQUIRED[_f] = ['left', 'right']
for _f in ('sum', 'min', 'max', 'avg', 'any', 'all', 'sort', 'top', 'latest', 'earliest', 'distinct'):
    REQUIRED[_f] = ['slot']
TEXT = ['west', 'east', 'north', 'south', 'open', 'closed', 'hot', 'cold']
NAMES = ['acme', 'zed', 'bob', 'ann', 'cat', 'dog', 'eel', 'fox']


def text(v):
    return ('true' if v else 'false') if isinstance(v, bool) else str(v)


def props(**kw):
    return {'/' + k: text(v) for k, v in kw.items()}


def unrender(rendered):
    """Rendered props back to write slots: numbers as numbers, booleans as booleans, references and paths typed."""
    out = {}
    for k, v in rendered.items():
        k = k.lstrip('/')
        if is_num(v):
            out[k] = int(v)
        elif DEC.match(v):
            out[k] = float(v)
        elif v in ('true', 'false'):
            out[k] = v == 'true'
        elif v.startswith('/h/'):
            out[k] = {'type': 'reference', 'value': v}
        elif v.startswith('/0x'):
            out[k] = {'type': 'path', 'value': v}
        else:
            out[k] = v
    return out


def records(tree, path):
    out = [{'path': path, 'slots': unrender(tree['props'])}] if tree['rec'] else []
    for name, kid in tree['kids'].items():
        out += records(kid, path + '/' + name)
    return out


def fmt(v):
    """A Fraction as a literal: '12' or '12.5'."""
    s = str(float(v)) if v.denominator != 1 else str(int(v))
    return s.rstrip('0').rstrip('.') if '.' in s else s


class Gen:
    def __init__(self, rng, node_):
        self.rng, self.node = rng, node_

    def coin(self, p=0.5):
        return self.rng.random() < p

    def word(self):
        return self.rng.choice(TEXT)

    def build(self, kind):
        rng = self.rng
        pool = rng.sample(range(1, 400), 40)
        negative = self.coin(0.3)

        def num():
            v = pool.pop()
            return -v if negative and rng.random() < 0.4 else v
        mode = rng.choice(['none', 'none', 'record', 'slot'])

        def row(slot='n', **kw):
            p = props(**kw)
            if mode != 'none' and self.coin(0.7):
                p['/scale' if mode == 'record' else '/' + slot + '/scale'] = str(rng.randint(1, 2))
            return node(p)

        def root(**kw):
            return node(props(**kw)) if self.coin(0.6) else node(rec=False)
        k = rng.randint(2, 5)
        if kind == 'rec1':
            return node(props(n=num()))
        if kind == 'recN':
            return row('amount', n=num(), t=self.word(), ok=self.coin(), when=rng.randint(1, 99), amount=num(), d='%d-%02d-%02d' % (rng.randint(1990, 2026), rng.randint(1, 12), rng.randint(1, 28)))
        if kind == 'recM':
            return node(props(n=num(), t=self.word(), ok=self.coin(), p='/' + self.node + '/user', rf='/h/x/0/2/' + self.node + '/user'))
        if kind == 'list':
            r = root(title='list')
            for i in range(k):
                r['kids'][str(i + 1)] = row(n=num(), t=self.word())
        elif kind == 'map':
            r = root()
            for nm in rng.sample(NAMES, k):
                r['kids'][nm] = row(n=num(), region=self.word())
        elif kind == 'set':
            r = root()
            for nm in rng.sample(NAMES, k):
                r['kids'][nm] = node()
        elif kind == 'table':
            r = root(title='table')
            for i in range(k):
                r['kids']['r' + str(i + 1)] = row('amount', region=self.word(), status=rng.choice(['open', 'closed']), amount=num(), when=rng.randint(1, 99))
        elif kind == 'bag':
            r = root()
            vals = rng.sample(TEXT, 2)
            for i in range(k):
                r['kids'][str(i + 1)] = row(t=rng.choice(vals), n=num())
        elif kind == 'attach':
            r = node(props(n=num(), t=self.word()))
            for i in range(k):
                r['kids']['a' + str(i + 1)] = row('size', kind=rng.choice(['pdf', 'txt', 'png']), size=num())
        elif kind == 'tree':
            r = node(props(n=num()))
            a = row(n=num())
            a['kids']['x'] = row(n=num())
            a['kids']['x']['kids']['deep'] = row(n=num(), t=self.word())
            b = row(n=num())
            b['kids']['y'] = node(props(t=self.word()))
            r['kids'] = {'a': a, 'b': b, 'empty': node(props(title='empty'))}
            if self.coin():
                r['kids']['c'] = row(n=num(), t=self.word())
        elif kind == 'grouped':
            r = root()
            for grp in rng.sample(TEXT, 2):
                folder = node(rec=False)
                for nm in rng.sample(NAMES, rng.randint(1, 3)):
                    folder['kids'][nm] = row(n=num(), t=self.word())
                r['kids'][grp] = folder
        elif kind == 'matrix':
            r = root()
            cols = ['c' + str(j + 1) for j in range(rng.randint(2, 3))]
            for i in range(rng.randint(2, 3)):
                folder = node(rec=False)
                for c in cols:
                    folder['kids'][c] = row('v', r='r' + str(i + 1), c=c, v=num())
                r['kids']['r' + str(i + 1)] = folder
        elif kind == 'hier':
            r = node(props(n=num(), t=self.word()))
            for nm in rng.sample(NAMES, 2):
                a = row(n=num(), t=self.word())
                for nm2 in rng.sample(NAMES, rng.randint(1, 2)):
                    b = row(n=num(), t=self.word())
                    if self.coin():
                        b['kids']['leaf'] = row(n=num(), t=self.word())
                    a['kids'][nm2] = b
                r['kids'][nm] = a
        elif kind == 'uneven':
            r = root()
            hollow = node(rec=False)
            hollow['kids']['leaf'] = row(n=num())
            top = row(n=num())
            top['kids']['mid'] = node(rec=False)
            top['kids']['mid']['kids']['low'] = row(n=num())
            r['kids'] = {'hollow': hollow, 'top': top, 'empty': node(props(title='empty'))}
        return r

    def shape(self, kind, path, history=False):
        """A shape instance: state0 is what batch one writes; state is after the history mods (batch two)."""
        state0 = self.build(kind)
        mods, state = [], clone(state0)
        if history and state0['rec'] and state0['kids']:
            rng = self.rng
            names = sorted(state['kids'])
            victim = rng.choice(names)
            if state['kids'][victim]['rec'] and self.coin(0.7):
                changed = clone(state['kids'][victim])
                changed['props']['/n'] = str(rng.randint(400, 999))
                state['kids'][victim] = changed
                mods.append({'path': path + '/' + victim, 'slots': unrender(changed['props'])})
            elif state['kids'][victim]['rec'] and len(names) > 1:      # only a record can be culled and written again
                del state['kids'][victim]
                mods.append({'path': path + '/' + victim, 'action': 'cull'})
            fresh = node(props(n=rng.randint(400, 999), t=self.word()))
            state['kids']['new'] = fresh
            mods.append({'path': path + '/new', 'slots': unrender(fresh['props'])})
        return {'kind': kind + ('+h' if mods else ''), 'path': path, 'state0': state0, 'state': state, 'mods': mods, 'has_root': state0['rec']}

    def params(self, f, inp, care, views):
        """Settings that are valid for this input most of the time."""
        rng, pick = self.rng, self.rng.choice
        R = rows(inp, care)

        def kinds(ps):
            keys = [s for s in ps if s != '/scale' and not s.endswith('/scale')]
            return ([s for s in keys if is_num(ps[s])], [s for s in keys if ps[s] in ('true', 'false')],
                    [s for s in keys if not is_num(ps[s]) and ps[s] not in ('true', 'false')])
        rown, rowb, rowt = set(), set(), set()
        for _, r in R:
            n_, b_, t_ = kinds(r['props'])
            rown |= set(n_); rowb |= set(b_); rowt |= set(t_)
        rown, rowb, rowt = sorted(rown) or ['/n'], sorted(rowb) or ['/ok'], sorted(rowt) + ['/name']
        rootn, rootb, roott = kinds(inp['props'])
        rootn = rootn or ['/n']
        roott = roott + rootn

        def vals(slot):
            return [slot_text(r, rel, slot) for rel, r in R if slot_text(r, rel, slot) is not None]

        def view_num():
            for name, (tree, _) in views.items():
                if tree is not None and kinds(tree['props'])[0]:
                    return '/views/' + name + pick(kinds(tree['props'])[0])
            return None

        def lit():
            return pick([str(rng.randint(1, 9)), str(rng.randint(1, 60)), str(rng.randint(1, 9)) + '.5', str(rng.randint(10, 99)) + '.25', '-' + str(rng.randint(1, 30)), '-' + str(rng.randint(1, 9)) + '.5'])

        def number_param():
            v = view_num()
            return pick([lit(), pick(rootn)] + ([v] if v else []))
        p = {}
        if f == 'count':
            if self.coin(0.3):
                p['into'] = '/cnt'
        elif f in ('sum', 'min', 'max', 'avg'):
            p['slot'] = pick(rown)
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f in ('any', 'all'):
            p['slot'] = pick(rowb + rown)
        elif f == 'where':
            op = pick(['equals', 'equals', 'equals', 'over', 'under', 'before', 'after', 'contains'])
            if op == 'equals':
                p['key'] = pick(rowt + rowb)
                p['value'] = pick(vals(p['key']) or [self.word()])
                if self.coin():
                    p['op'] = op
            elif op == 'contains':
                p['key'] = pick(rowt)
                v = vals(p['key'])
                p['value'] = pick(v)[:2] if v and self.coin(0.7) else self.word()
                p['op'] = op
            else:
                p['key'] = pick(rown)
                v = [slot_text(r, rel, p['key']) for rel, r in R if is_num(slot_text(r, rel, p['key']))]
                p['value'] = pick([fmt(num_of(r, p['key'])) for rel, r in R if num_of(r, p['key']) is not None] or [lit()]) if v else lit()
                p['op'] = op
        elif f in ('sort', 'top', 'latest', 'earliest'):
            p['slot'] = pick(rown) if self.coin(0.85) else pick(rowt)
            if f == 'sort' and self.coin():
                p['order'] = pick(['asc', 'desc'])
            if f == 'top' and self.coin():
                p['count'] = rng.randint(1, 4)
        elif f == 'each':
            p['left'], p['op'], p['right'], p['into'] = pick(rown), pick(['add', 'subtract', 'multiply', 'divide']), pick([lit(), lit(), pick(rown)]), '/out'
        elif f == 'lookup':
            name = next((n for n in views if n not in ('v1', 'v2')), 'table')
            if name != 'table':
                p['from'] = name
            table = view_rows_of(views, name)
            tn, tb, tt = set(), set(), set()
            for _, r in table:
                a, b, c = kinds(r['props'])
                tn |= set(a); tt |= set(c)
            tt, tn = sorted(tt) + ['/name'], sorted(tn) or ['/n']
            pairs = [(k, m) for k in rowt for m in tt if set(vals(k)) & {slot_text(r, rel, m) for rel, r in table}]
            p['key'], match = pick(pairs) if pairs and self.coin(0.7) else (pick(rowt), pick(tt))
            if match != p['key'] or self.coin():
                p['match'] = match
            p['take'] = pick(tt + tn)
            if self.coin():
                p['into'] = '/got'
        elif f == 'distinct':
            p['slot'] = pick(rowt + rown)
        elif f == 'select':
            p['slots'] = ' '.join(rng.sample(sorted(set(rown + rowt + rowb)), rng.randint(1, 2)))
        elif f == 'join':
            p['slots'] = ' '.join(rng.sample(sorted(set(rowt + rown)), rng.randint(1, 2)))
            if self.coin():
                p['with'] = pick([', ', '-', ''])
            if self.coin(0.3):
                p['into'] = '/full'
        elif f == 'match':
            p['key'], p['value'] = pick(rowt), pick(['e', 'o', 'st', 'th', 'a', 'west', 'z'])
            if self.coin():
                p['op'] = pick(['contains', 'starts', 'ends'])
        elif f == 'split':
            p['slot'] = pick(rowt)
            if self.coin():
                p['with'] = pick(['-', 'e', 'o', ' '])
            if self.coin(0.3):
                p['into'] = '/part'
        elif f == 'date':
            p['slot'] = pick(rowt)
            if self.coin(0.3):
                p['into'] = '/on'
        elif f == 'by':
            p['key'] = pick(rowt + rowb)
            op = pick(['count', 'count', 'sum', 'min', 'max', 'avg'])
            if op != 'count' or self.coin():
                p['op'] = op
            if op != 'count':
                p['slot'] = pick(rown)
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f == 'grid':
            p['row'], p['col'] = pick(rowt), pick(rowt + rowb)
            op = pick(['count', 'count', 'sum', 'min', 'max', 'avg'])
            if op != 'count':
                p['op'], p['slot'] = op, pick(rown)
        elif f in ('except', 'intersect', 'diff'):
            name = next((n for n in views if n not in ('v1', 'v2')), None)
            if name and name != 'other':
                p['from'] = name
            if self.coin():
                p['key'] = pick(rowt)
        elif f in ('add', 'subtract', 'multiply', 'divide'):
            p['left'], p['right'] = pick(rootn + [lit()]), number_param()
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f == 'pick':
            v = next(('/views/' + n + pick(sorted(t['props']) or ['/n']) for n, (t, _) in views.items() if t is not None and t['props']), None)
            p['from'] = pick(roott + ([v] if v else []))
            p['into'] = '/copy'
        elif f == 'put':
            p['into'], p['value'] = '/flag', pick([self.word(), rng.randint(1, 50)])
        elif f == 'round':
            p['slot'], p['places'] = pick(rootn), rng.randint(0, 3)
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f == 'since':
            p['slot'] = pick(rootn)
            v = num_of(inp, p['slot'])
            p['from'] = pick([str(rng.randint(0, max(0, int(v)))) if v is not None else lit(), number_param()])
            if self.coin(0.3):
                p['into'] = '/age'
        elif f == 'between':
            p['slot'] = pick(rown)
            v = sorted(num_of(r, p['slot']) for rel, r in R if num_of(r, p['slot']) is not None)
            if v and self.coin(0.8):
                lo, hi = sorted(rng.sample(v, 2)) if len(v) > 1 else (v[0], v[0])
                p['from'], p['to'] = fmt(lo), fmt(hi)
            else:
                p['from'], p['to'] = str(rng.randint(1, 50)), str(rng.randint(50, 400))
        return p


def view_rows_of(views, name):
    v = views.get(name)
    return [] if v is None or v[0] is None else rows(v[0], v[1])


def gen_case(g, i, home):
    """One case: a primary shape, 0-2 secondary shapes, a chain of 1-4 cells, each with its oracle expectation."""
    rng = g.rng
    base = home + '/d/' + str(i)
    prim = g.shape(rng.choice(KINDS), base + '/p', history=g.coin(0.35))
    shapes = [prim]
    for j in range(rng.choice([0, 1, 1, 2])):
        shapes.append(g.shape(rng.choice(KINDS), base + '/v' + str(j + 1)))
    care = rng.choice('xyz')
    pinned = prim['has_root'] and g.coin(0.2)
    tack = {'kind': 'shape', 'shape': 0, 'care': care, 'pinned': pinned}

    def at(shape, care, pinned):
        """A shape as an input at a care: at x a folder with no record of its own is nothing."""
        tree = shape['state0'] if pinned else shape['state']
        return None if care == 'x' and not tree['rec'] else cut(tree, care)
    inp = at(prim, care, pinned)
    cells = []
    for step in range(1 if g.coin(0.7) else rng.randint(2, 4)):
        f = rng.choice(FORMULAS)
        needs = {'lookup': 'table', 'except': 'other', 'intersect': 'other', 'diff': 'other'}.get(f)
        if needs and len(shapes) == 1 and g.coin(0.8):
            shapes.append(g.shape(rng.choice(KINDS), base + '/v1'))
        views = {}
        available = list(range(1, len(shapes)))
        if needs and step == 0 and prim['mods'] and g.coin(0.7):
            views[needs] = {'kind': 'shape', 'shape': 0, 'care': care, 'pinned': True}       # the same path, earlier case
            tack['pinned'] = False
            inp = at(prim, care, False)
        elif needs and available:
            name = needs if g.coin(0.7) else 'ref'
            idx = available.pop(0)
            views[name] = {'kind': 'shape', 'shape': idx, 'care': rng.choice('xyz'), 'pinned': shapes[idx]['has_root'] and g.coin(0.3)}
        for idx in available:
            name = ('extra' if 'extra' not in views else 'more') if f in ('merge', 'gather') else ('v1' if 'v1' not in views else 'v2')
            views[name] = {'kind': 'shape', 'shape': idx, 'care': rng.choice('xyz'), 'pinned': shapes[idx]['has_root'] and g.coin(0.3)}
        bad = rng.choice(['omit', 'badslot', 'emptyview', 'badtack', 'wrongkind']) if g.coin(0.15) else None
        if bad == 'emptyview' and views:
            views[rng.choice(sorted(views))] = {'kind': 'bad'}
        if bad == 'badtack':
            tack = {'kind': 'bad'}
            inp = None
        view_trees = {}
        for name, v in views.items():
            if v['kind'] == 'bad':
                view_trees[name] = (None, 'y')
            else:
                view_trees[name] = (at(shapes[v['shape']], v['care'], v['pinned']), v['care'])     # nothing at x of a folder: empty
        params = g.params(f, inp if inp is not None else node(), care, view_trees)
        if bad == 'omit' and REQUIRED.get(f):
            params.pop(rng.choice(REQUIRED[f]), None)
        elif bad == 'badslot':
            slotty = [k for k in params if k in ('slot', 'key', 'left', 'right', 'from', 'take', 'match', 'row', 'col') and str(params[k]).startswith('/')]
            if slotty:
                params[rng.choice(slotty)] = '/nope'
        elif bad == 'wrongkind':
            if f in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'sum', 'min', 'max', 'avg', 'sort', 'top') and 'slot' in params or 'left' in params:
                texts = [s for s, v in (inp or node())['props'].items() if not is_num(v)] or ['/t']
                params['slot' if 'slot' in params else 'left'] = rng.choice(texts)
        expect = evaluate(f, params, inp, care, view_trees)
        cells.append({'path': home + '/c/' + str(i) + '/s' + str(step), 'formula': f, 'params': params, 'tack': tack, 'views': views,
                      'care': care, 'expect': expect, 'bad': bad, 'nviews': len(views)})
        care = rng.choice('xyz')
        tack = {'kind': 'cell', 'cell': step, 'care': care}
        # a faulted cell's /x is a bad reference downstream; an unknown one (no row to be the root) is an empty input
        inp = cut(expect[0], care) if expect[0] is not None else (None if expect[1]['fault'] else node(rec=False))
    return {'i': i, 'base': base, 'shapes': shapes, 'cells': cells, 'kind': prim['kind']}


# ============================================================================ the run
def check(base, node_, timeout, seed=None, cases=1000, group=25, max_mismatch=10):
    seed = seed if seed is not None else random.randrange(10 ** 8)
    print('seed', seed, 'cases', cases, flush=True)
    rng = random.Random(seed)
    g = Gen(rng, node_)
    seq = [0]
    pool = ThreadPoolExecutor(max_workers=8)

    def epoch():
        try:
            with urllib.request.urlopen(base + '/probe/read?path=/' + node_, timeout=timeout) as r:
                return json.load(r).get('epoch')
        except Exception:
            return None

    def rpc(method, params):
        seq[0] += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq[0], method=method, params=params)).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)

    def tool(name, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments})
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def read(path, care='y'):
        return tool('read', path=path, care=care)

    def shape_of(view):
        return {'props': view.get('properties', {}), 'kids': {ch['path'].rsplit('/', 1)[1]: shape_of(ch) for ch in view.get('children', [])}}

    def live(path, care):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    def write_batch(recs, label):
        e0 = epoch()
        out = tool('write', records=recs)
        e1 = epoch()
        assert not out['refused'], (label, out)
        if e0 is not None and e1 is not None:
            assert e1 - e0 == 1, ('a batch costs one event', label, e1 - e0)
        return {r['path']: r['reference'] for r in out['records']}

    def reads(tasks):
        """Many reads at once; they cost no event."""
        e0 = epoch()
        out = list(pool.map(lambda t: read(*t), tasks))
        e1 = epoch()
        if e0 is not None and e1 is not None:
            assert e1 - e0 == 0, ('reads cost no event', e1 - e0)
        return out

    deadline = time.time() + timeout
    while True:
        try:
            stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']} for c in read('/' + node_ + '/weft/stdlib')['children']}
            break
        except Exception as e:      # the world may still be coming up
            if time.time() > deadline:
                raise
            time.sleep(2)
    assert len(stdlib) == 39, sorted(stdlib)      # thirty-eight formulas and ask
    home = '/' + node_ + '/user/sig/' + str(seed)
    earlier = read(home, 'y')
    if earlier['exists'] or earlier['children']:          # a rerun with the same seed gets its own home under the seed's
        home += '/r' + str(len(earlier['children']))
    stats = {}          # (formula, shape kind, nviews) -> [cells, failed]
    mismatches, classes, skipped = [], {}, [0]
    started = time.perf_counter()

    def ctx_of(props):
        return {'missing': '/sys/view/missing' in props, 'fault': '/sys/view/fault' in props,
                'empty': {k[len('/sys/view/empty/'):] for k in props if k.startswith('/sys/view/empty/')},
                'notes': {k[len('/sys/view/note/'):] for k in props if k.startswith('/sys/view/note/')}}

    def mismatch(case, cell, what, got, want):
        mismatches.append((cell['formula'], case['kind'], cell['care'], what))
        classes[(cell['formula'], what)] = classes.get((cell['formula'], what), 0) + 1
        print('MISMATCH', what, '| case', case['i'], '| formula', cell['formula'], '| shape', case['kind'], '| care', cell['care'],
              '| tack', cell['tack'], '| params', json.dumps(cell['params']), '| views', json.dumps(cell['views']), '| bad', cell.get('bad'))
        print('   world ', json.dumps(got, sort_keys=True))
        print('   oracle', json.dumps(want, sort_keys=True))
        for up in case['cells'][:case['cells'].index(cell)] if cell in case['cells'] else case['cells']:
            out = up['expect'][0]
            print('   upstream', up['formula'], json.dumps(up['params']), 'care', up['care'], 'bad', up['bad'], '->',
                  'unknown' if out is None else json.dumps(strip(out), sort_keys=True)[:300], '| ctx', {k: v for k, v in up['expect'][1].items() if v})
        print(flush=True)
        if len(mismatches) >= max_mismatch:
            raise AssertionError('%d mismatches; stopping' % len(mismatches))

    def compare_cell(case, cell, z, x, y, c):
        key = (cell['formula'], case['kind'], cell['nviews'])
        if case.get('tainted'):
            skipped[0] += 1         # downstream of a mismatch: the oracle's input is already not the world's
            return None
        stats.setdefault(key, [0, 0])[0] += 1
        want, wctx = cell['expect']
        ok = True
        got = shape_of(z)
        if want is None:            # unknown: no root, nothing below it
            if z['exists'] or got != {'props': {}, 'kids': {}}:
                mismatch(case, cell, '/x at z (unknown expected)', got, None); ok = False
        elif shown_tree(strip(want)) != got:
            mismatch(case, cell, '/x at z', got, shown_tree(strip(want))); ok = False
        elif z['exists'] != want['rec']:
            mismatch(case, cell, '/x root exists (record or folder)', z['exists'], want['rec']); ok = False
        gctx = ctx_of(c['properties'])
        if gctx != wctx:
            mismatch(case, cell, '/c/x', c['properties'], {k: sorted(v) if isinstance(v, set) else v for k, v in wctx.items()}); ok = False
        if want is not None:
            for care, view in (('x', x), ('y', y)):
                if shape_of(view) != cut_read(z, care):
                    mismatch(case, cell, '/x at ' + care + ' is not the z tree cut', shape_of(view), cut_read(z, care)); ok = False

            def no_sys(t):
                return not any(k.startswith('/sys/view') for k in t['props']) and all(no_sys(k) for k in t['kids'].values())
            if not no_sys(got):
                mismatch(case, cell, 'sys/view slot in /x', got, None); ok = False
        if not ok:
            stats[key][1] += 1
            case['tainted'] = True
        return ok

    def ref_of(spec, refs, case):
        if spec['kind'] == 'bad':
            return live(case['base'] + '/none', 'y')
        if spec['kind'] == 'cell':
            return live('/x' + case['cells'][spec['cell']]['path'], spec['care'])
        s = case['shapes'][spec['shape']]
        return {'type': 'reference', 'value': refs[s['path']].replace('/h/x/', '/h/' + spec['care'] + '/', 1)} if spec['pinned'] else live(s['path'], spec['care'])

    for start in range(0, cases, group):
        batch = [gen_case(g, i, home) for i in range(start, min(cases, start + group))]
        # one: every shape's first state (and the home record, once)
        recs = [{'path': home, 'slots': {'seed': seed}}] if start == 0 else []
        for case in batch:
            for s in case['shapes']:
                recs += records(s['state0'], s['path'])
        refs = write_batch(recs, 'data')
        # two: the history mods and every cell
        recs = []
        for case in batch:
            for s in case['shapes']:
                recs += s['mods']
            for cell in case['cells']:
                slots = {'sys/weft': stdlib[cell['formula']], 'sys/tack': ref_of(cell['tack'], refs, case)}
                slots.update({name: ref_of(v, refs, case) for name, v in cell['views'].items()})
                slots.update(cell['params'])
                recs.append({'path': cell['path'], 'slots': slots})
        write_batch(recs, 'cells')
        tasks = [t for case in batch for cell in case['cells'] for t in (('/x' + cell['path'], 'z'), ('/x' + cell['path'], 'x'), ('/x' + cell['path'], 'y'), ('/c/x' + cell['path'], 'x'))]
        answers = reads(tasks)
        at = 0
        amends = []
        for case in batch:
            for cell in case['cells']:
                z, x, y, c = answers[at:at + 4]
                at += 4
                compare_cell(case, cell, z, x, y, c)
            # three: notes over the last cell with an answer, at a root slot, a row path and a dangling path
            last = next((cell for cell in reversed(case['cells']) if cell['expect'][0] is not None), None)
            if last is None:
                continue
            cx = answers[tasks.index(('/c/x' + last['path'], 'x'))]['properties']
            if not is_num(cx.get('/sys/tack/case')):
                continue          # a folder with no record of its own has no case to stamp against
            stamp = int(cx['/sys/tack/case'])
            out = last['expect'][0]
            notes = node()
            root_slots = [s for s in out['props'] if s != '/scale' and not s.endswith('/scale')]
            notes['kids']['n1'] = node(props(slot=rng.choice(root_slots) if root_slots and g.coin(0.8) else '/note', value=rng.choice([g.word(), rng.randint(1, 99)]), case=stamp))
            rs = rows(out, 'z')
            if rs:
                rel, r = rng.choice(rs)
                slots = [s for s in r['props'] if not s.endswith('/scale')] or ['/note']
                notes['kids']['n2'] = node(props(slot='/' + '/'.join(rel) + rng.choice(slots), value=rng.choice([g.word(), rng.randint(1, 99)]), case=stamp - 1 if stamp > 1 and g.coin(0.6) else stamp))
            notes['kids']['n3'] = node(props(slot='/nowhere/' + rng.choice(['a', 'b']) + '/n', value=1, case=stamp))
            notes_path = home + '/n/' + str(case['i'])
            cell = {'path': home + '/c/' + str(case['i']) + '/amend', 'formula': 'amend', 'params': {}, 'tack': {'kind': 'cell', 'cell': case['cells'].index(last), 'care': 'z'},
                    'views': {'notes': {'kind': 'notes'}}, 'care': 'z', 'bad': None, 'nviews': 1, 'stamp': stamp,
                    'expect': evaluate('amend', {}, out, 'z', {'notes': (notes, 'y')}, stamp=stamp)}
            amends.append((case, cell, notes, notes_path))
        if amends:
            recs = []
            for case, cell, notes, notes_path in amends:
                recs += records(notes, notes_path)
                recs.append({'path': cell['path'], 'slots': {'sys/weft': stdlib['amend'], 'sys/tack': ref_of(cell['tack'], refs, case), 'notes': live(notes_path, 'y')}})
            write_batch(recs, 'notes')
            tasks = [t for _, cell, _, _ in amends for t in (('/x' + cell['path'], 'z'), ('/x' + cell['path'], 'x'), ('/x' + cell['path'], 'y'), ('/c/x' + cell['path'], 'x'))]
            answers = reads(tasks)
            for k, (case, cell, _, _) in enumerate(amends):
                compare_cell(case, cell, *answers[4 * k:4 * k + 4])
        print('cases', min(cases, start + group), 'cells', sum(v[0] for v in stats.values()), 'mismatches', len(mismatches), 'elapsed %.1fs' % (time.perf_counter() - started), flush=True)

    wall = time.perf_counter() - started
    print('| formula | primary shape | 0 views | 1 view | 2 views | cells | failed |')
    print('|---|---|---|---|---|---|---|')
    by_fs = {}
    for (f, kind, nviews), (n, failed) in sorted(stats.items()):
        row = by_fs.setdefault((f, kind), [0, 0, 0, 0, 0])
        row[min(nviews, 2)] += n
        row[3] += n
        row[4] += failed
    for (f, kind), row in sorted(by_fs.items()):
        print('| %s | %s | %d | %d | %d | %d | %d |' % (f, kind, *row))
    total = sum(v[0] for v in stats.values())
    failed = sum(v[1] for v in stats.values())
    for (f, what), n in sorted(classes.items()):
        print('mismatch class', f, '|', what, '|', n)
    print(json.dumps({'seed': seed, 'cases': cases, 'cells': total, 'passed': total - failed, 'failed': failed, 'skipped_downstream': skipped[0],
                      'round_trips': seq[0], 'wall_s': round(wall, 1)}), flush=True)
    assert not mismatches, [m[:3] for m in mismatches]


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120, int(sys.argv[3]) if len(sys.argv) > 3 else None, int(sys.argv[4]) if len(sys.argv) > 4 else 1000)
