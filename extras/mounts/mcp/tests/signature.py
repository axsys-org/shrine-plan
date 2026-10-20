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


def keyname(value):
    """A child name made from a value, as the world spells it: letters, digits and underscores kept, any other byte an
    underscore; digits alone a number, a text starting with a letter a symbol, the rest a text atom shown with $."""
    clean = re.sub(r'[^A-Za-z0-9_]', '_', value)
    if clean == '':
        return 'empty'
    if clean.isdigit() or re.match(r'[A-Za-z]', clean):
        return clean
    return '$' + clean


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


class Text(str):
    """A text that looks like a number: written as {type: str}, read back as the same text, never a number."""


def is_num(text):
    return text is not None and not isinstance(text, Text) and INT.match(text) is not None


def as_text(s):
    """What a text entry writes is a text, even when it looks like a number."""
    return Text(s) if INT.match(s) or DEC.match(s) else s


def slot_text(n, rel, slot):
    """Convention two: a child's name is the slot called name; a record's own /name wins."""
    if slot == '/name' and '/name' not in n['props']:
        return rel[-1] if rel else None
    return n['props'].get(slot)


def disp(n, rel, slot):
    """The text of a row's slot as a read shows it: a number with its own scale as the decimal; the text entries read this."""
    if slot in n['props']:
        return shown(n['props']).get(slot)
    return slot_text(n, rel, slot)


def scale_of(n, slot):
    s = n['props'].get(slot + '/scale', n['props'].get('/scale', '0'))
    return int(s) if is_num(s) else 0


def num_of(n, slot):
    """A slot's number: a natural at the record's or the slot's scale, or the decimal the world shows for a slot with its own
    scale (already the value), signed either way."""
    v = n['props'].get(slot)
    if v is not None and not isinstance(v, Text) and DEC.match(v):
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


def put_fig(r, into, v, scale):
    """A derived number on a row carries the slot's own scale, so the row's other numbers keep theirs; a whole number on
    a row that has /scale says so with <slot>/scale 0 (the world renders a slot with its own scale as the decimal)."""
    r['props'][into] = fig(v, scale)
    own = r['props'].get('/scale', '0')
    if scale == 0 and (not is_num(own) or int(own) == 0):
        r['props'].pop(into + '/scale', None)
    else:
        r['props'][into + '/scale'] = str(scale)


def row_scale(R, slot):
    return max([scale_of(r, slot) for rel, r in R if num_of(r, slot) is not None], default=0)


def row_num(r, rel, slot):
    """A row's number at a slot, the name convention included (a numeric name counts, at scale 0)."""
    if slot in r['props']:
        return num_of(r, slot)
    t = slot_text(r, rel, slot)
    return Fraction(int(t)) if is_num(t) else None


def day_of(r, rel, slot):
    """A row's day as (y, m, d): a day number YYYYMMDD with a year of at least one, or a text date."""
    import datetime
    t = slot_text(r, rel, slot)
    if t is None:
        return None
    if is_num(t):
        n = int(t)
        if n < 0:
            return None
        y, m, d = n // 10000, (n // 100) % 100, n % 100
    else:
        m_ = re.match(r'(\d{4})-(\d{2})-(\d{2})', t)
        if not m_:
            return None
        y, m, d = int(m_.group(1)), int(m_.group(2)), int(m_.group(3))
    try:
        datetime.date(y, m, d)
    except ValueError:
        return None
    return y, m, d


def ascii_case(t, upper):
    return ''.join((c.upper() if upper else c.lower()) if 'a' <= c.lower() <= 'z' else c for c in t)


def ref_path(text):
    """The absolute path a rendered reference /h/<care>/<case>/<len>/<path> points at."""
    if not text or not text.startswith('/h/'):
        return None
    parts = text.split('/')
    return '/' + '/'.join(parts[5:]) if len(parts) > 5 else None


def record_at(tree, rel):
    """The record at a relative path of a cut view tree, if there is one."""
    cur = tree
    for seg in rel:
        cur = cur['kids'].get(seg)
        if cur is None:
            return None
    return cur if cur.get('rec', True) and cur is not None else None


# ============================================================================ expressions, from the spec
# Slot names, scaled signed numbers, quoted text, + - * /, = != < <= > >=, and or not, in, parens, min max abs round len
# lower upper trim contains starts ends; usual precedence (or < and < not < comparison < + - < * / < unary minus < atoms).
# A slot the row lacks is a hole on that row; a bad expression is one fault with its position; division by zero and a
# number against a text in arithmetic fault; expr beside the old settings faults.  Written from the spec, not from the Foil.
class ExprError(Exception):
    pass


class Hole(Exception):
    pass


TOKEN = re.compile(r'\s*(?:(\d+(?:\.\d+)?)|("[^"]*"|\'[^\']*\')|([A-Za-z_][A-Za-z0-9_]*)|(!=|<=|>=|[-+*/=<>(),])|(.))')


def expr_tokens(src):
    out, i = [], 0
    while i < len(src):
        m = TOKEN.match(src, i)
        if m.end() == i:
            break
        num, txt, ident, op, bad = m.groups()
        pos = m.start(m.lastindex) if m.lastindex else i
        if num:
            out.append(('num', num, pos))
        elif txt:
            out.append(('txt', txt[1:-1], pos))
        elif ident:
            out.append(('id', ident, pos))
        elif op:
            out.append(('op', op, pos))
        elif bad:
            raise ExprError('expr: a value, not %s at %d' % (bad, pos))
        i = m.end()
    out.append(('end', '', len(src)))
    return out


def expr_parse(src):
    """The expression as a tree: ('num', Fraction, scale) | ('txt', s) | ('bit', b) | ('slot', name) | ('un', op, a) |
    ('bin', op, a, b) | ('call', f, [args]).  A bad expression raises ExprError with its position."""
    toks = expr_tokens(src)
    at = [0]

    def peek():
        return toks[at[0]]

    def take():
        t = toks[at[0]]
        at[0] += 1
        return t

    def is_op(t, *ops):
        return t[0] == 'op' and t[1] in ops

    def is_word(t, w):
        return t[0] == 'id' and t[1] == w

    def p_or():
        a = p_and()
        while is_word(peek(), 'or'):
            take()
            a = ('bin', 'or', a, p_and())
        return a

    def p_and():
        a = p_not()
        while is_word(peek(), 'and'):
            take()
            a = ('bin', 'and', a, p_not())
        return a

    def p_not():
        if is_word(peek(), 'not'):
            take()
            return ('un', 'not', p_not())
        return p_cmp()

    def p_cmp():
        a = p_add()
        t = peek()
        if is_op(t, '=', '!=', '<', '<=', '>', '>=') or is_word(t, 'in'):
            take()
            return ('bin', t[1], a, p_add())
        return a

    def p_add():
        a = p_mul()
        while is_op(peek(), '+', '-'):
            a = ('bin', take()[1], a, p_mul())
        return a

    def p_mul():
        a = p_unary()
        while is_op(peek(), '*', '/'):
            a = ('bin', take()[1], a, p_unary())
        return a

    def p_unary():
        if is_op(peek(), '-'):
            take()
            return ('un', '-', p_unary())
        return p_primary()

    def p_primary():
        t = take()
        kind, text, pos = t
        if kind == 'num':
            lit = literal(text)
            return ('num', lit[0], lit[1])
        if kind == 'txt':
            return ('txt', text)
        if kind == 'id':
            if text in ('true', 'false'):
                return ('bit', text == 'true')
            if is_op(peek(), '('):
                take()
                args = []
                if is_op(peek(), ')'):
                    take()
                    return ('call', text, args)
                while True:
                    args.append(p_or())
                    nxt = take()
                    if is_op(nxt, ')'):
                        return ('call', text, args)
                    if not is_op(nxt, ','):
                        raise ExprError('expr: a comma or a closing paren at %d' % nxt[2])
            return ('slot', text)
        if is_op(t, '('):
            a = p_or()
            nxt = take()
            if not is_op(nxt, ')'):
                raise ExprError('expr: a closing paren at %d' % nxt[2])
            return a
        if kind == 'end':
            raise ExprError('expr: a value, not the end at %d' % pos)
        raise ExprError('expr: a value, not %s at %d' % (text, pos))
    tree = p_or()
    if peek()[0] != 'end':
        raise ExprError('expr: unexpected %s at %d' % (peek()[1], peek()[2]))
    return tree


def expr_slots(tree):
    """The slot names an expression reads."""
    kind = tree[0]
    if kind == 'slot':
        return {tree[1]}
    if kind == 'un':
        return expr_slots(tree[2])
    if kind == 'bin':
        return expr_slots(tree[2]) | expr_slots(tree[3])
    if kind == 'call':
        return set().union(*(expr_slots(a) for a in tree[2])) if tree[2] else set()
    return set()


def expr_size(tree):
    """(terms, and-links) of an expression: its leaves, and how many and operators it chains."""
    kind = tree[0]
    if kind in ('num', 'txt', 'bit', 'slot'):
        return 1, 0
    if kind == 'un':
        return expr_size(tree[2])
    if kind == 'bin':
        a, b = expr_size(tree[2]), expr_size(tree[3])
        return a[0] + b[0], a[1] + b[1] + (1 if tree[1] == 'and' else 0)
    sizes = [expr_size(x) for x in tree[2]]
    return sum(t for t, _ in sizes) or 1, sum(c for _, c in sizes)


def paren_depth(src):
    depth = best = 0
    for ch in src:
        if ch == '(':
            depth += 1
            best = max(best, depth)
        elif ch == ')':
            depth -= 1
    return best


def expr_ops(tree):
    """The operators and functions an expression uses (the matrix's columns)."""
    kind = tree[0]
    if kind == 'un':
        return {tree[1] if tree[1] == 'not' else 'neg'} | expr_ops(tree[2])
    if kind == 'bin':
        return {tree[1]} | expr_ops(tree[2]) | expr_ops(tree[3])
    if kind == 'call':
        return {tree[1]}.union(*(expr_ops(a) for a in tree[2])) if tree[2] else {tree[1]}
    return set()


def shown_number(v, scale):
    """A number as a read shows it: the magnitude at the scale, with a point when the scale is above zero, signed."""
    m = fig(v, scale)
    neg = m.startswith('-')
    digits = m.lstrip('-').rjust(scale + 1, '0')
    return ('-' if neg else '') + (digits[:-scale] + '.' + digits[-scale:] if scale else digits)


def value_text(v):
    if v[0] == 'num':
        return shown_number(v[1], v[2])
    if v[0] == 'txt':
        return v[1]
    return 'true' if v[1] else 'false'


def expr_eval(tree, r, rel):
    """A value at a row: ('num', Fraction, scale) | ('txt', text) | ('bit', bool).  A slot the row lacks raises Hole(name);
    a type fault raises ExprError."""
    kind = tree[0]
    if kind == 'num':
        return ('num', tree[1], tree[2])
    if kind == 'txt':
        return ('txt', tree[1])
    if kind == 'bit':
        return ('bit', tree[1])
    if kind == 'slot':
        slot = '/' + tree[1]
        t = slot_text(r, rel, slot)
        if t is None:
            raise Hole(tree[1])
        v = row_num(r, rel, slot)
        if v is not None:
            return ('num', v, scale_of(r, slot) if slot in r['props'] else 0)
        if t in ('true', 'false'):
            return ('bit', t == 'true')
        return ('txt', t)
    if kind == 'un':
        a = expr_eval(tree[2], r, rel)
        if tree[1] == '-':
            if a[0] != 'num':
                raise ExprError('a text or a boolean cannot be negated')
            return ('num', -a[1], a[2])
        if a[0] != 'bit':
            raise ExprError('not needs a boolean')
        return ('bit', not a[1])
    if kind == 'bin':
        op, a, b = tree[1], expr_eval(tree[2], r, rel), expr_eval(tree[3], r, rel)
        nums = a[0] == 'num' and b[0] == 'num'
        if op in '+-*/':
            if not nums:
                raise ExprError('arithmetic needs two numbers')
            scale = max(a[2], b[2])
            if op == '+':
                return ('num', a[1] + b[1], scale)
            if op == '-':
                return ('num', a[1] - b[1], scale)
            if op == '*':
                return ('num', Fraction(fig(a[1] * b[1], scale)) / 10 ** scale, scale)
            if b[1] == 0:
                raise ExprError('division by zero')
            return ('num', Fraction(fig(a[1] / b[1], scale)) / 10 ** scale, scale)
        if op in ('<', '<=', '>', '>='):
            if not nums:
                raise ExprError('only numbers can be ordered')
            return ('bit', {'<': a[1] < b[1], '<=': a[1] <= b[1], '>': a[1] > b[1], '>=': a[1] >= b[1]}[op])
        if op in ('=', '!='):
            same = (a[1] == b[1]) if nums or a[0] == b[0] else False
            return ('bit', same if op == '=' else not same)
        if op in ('and', 'or'):
            if a[0] != 'bit' or b[0] != 'bit':
                raise ExprError(op + ' needs two booleans')
            return ('bit', (a[1] and b[1]) if op == 'and' else (a[1] or b[1]))
        if op == 'in':
            return ('bit', value_text(a) in value_text(b))
        raise ExprError('unknown operator ' + op)
    f, args = tree[1], [expr_eval(x, r, rel) for x in tree[2]]
    two = f in ('min', 'max', 'contains', 'starts', 'ends', 'round')
    if f not in ('min', 'max', 'abs', 'round', 'len', 'lower', 'upper', 'trim', 'contains', 'starts', 'ends'):
        raise ExprError('unknown function ' + f)
    if len(args) != (2 if two else 1):
        raise ExprError(f + ' takes ' + ('two arguments' if two else 'one argument'))
    if f in ('min', 'max'):
        if args[0][0] != 'num' or args[1][0] != 'num':
            raise ExprError(f + ' needs two numbers')
        a, b = args
        pick_ = a if ((a[1] <= b[1]) if f == 'min' else (a[1] >= b[1])) else b
        return pick_
    if f == 'round':
        if args[0][0] != 'num' or args[1][0] != 'num':
            raise ExprError('round needs a number and the places')
        places = args[1][1]
        if places.denominator != 1 or places < 0 or args[1][2] != 0:
            raise ExprError('round takes a whole number of places')
        places = int(places)
        return ('num', Fraction(fig(args[0][1], places)) / 10 ** places, places)
    if f == 'abs':
        if args[0][0] != 'num':
            raise ExprError('abs needs a number')
        return ('num', abs(args[0][1]), args[0][2])
    a = value_text(args[0])
    if f == 'len':
        return ('num', Fraction(len(a.encode())), 0)
    if f == 'lower':
        return ('txt', ascii_case(a, False))
    if f == 'upper':
        return ('txt', ascii_case(a, True))
    if f == 'trim':
        return ('txt', a.strip(''.join(chr(c) for c in range(33))))
    b = value_text(args[1])
    return ('bit', {'contains': b in a, 'starts': a.startswith(b), 'ends': a.endswith(b)}[f])


# ============================================================================ the oracle: the standard cells
DEFAULT_INTO = {'count': '/count', 'sum': '/total', 'min': '/min', 'max': '/max', 'avg': '/avg', 'any': '/any', 'all': '/all'}


def evaluate(formula, params, inp, care, views, stamp=None, view_paths=None):
    """formula x params x input (at a care; None when the tack resolves to nothing) x views {name: (tree|None, care)}
    -> (output tree, or None for unknown) and the context': missing, fault, empty views, notes."""
    ctx = {'missing': False, 'fault': False, 'empty': set(), 'notes': set(), 'holes': set()}
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
    def rule(rel, r, key, value, op):
        # where's comparison: a number slot by value at its scale, anything else as text
        t = slot_text(r, rel, key)
        lit = literal(value)
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

    def fault(why):
        ctx['fault'] = True
        return None, ctx

    if formula in ('each', 'where', 'when', 'validate') and P('expr') is not None:
        old = ('left', 'op', 'right') if formula == 'each' else ('key', 'value', 'op')
        if any(P(k) is not None for k in old):
            return fault('expr: not beside the old settings')
        if formula in ('each', 'when') and P('into') is None:
            return missing()
        if formula == 'when' and P('then') is None:
            return missing()
        try:
            tree = expr_parse(P('expr'))
        except ExprError as e:
            return fault(str(e))
        into = P('into')
        out = node(inp['props'], rec=inp['rec'])
        for rel, r in R:
            row = node(r['props'])
            try:
                v = expr_eval(tree, r, rel)
            except Hole as h:
                ctx['holes'].add(keyname('_'.join(rel)))        # a row's name in the context: its path joined by underscores
                if formula == 'where':
                    continue
                if formula == 'validate':
                    row['props']['/reason'] = str(h) + ' is absent'
                place(out, rel, row)
                continue
            except ExprError as e:
                return fault('expr: %s in row %s' % (e, key_of(rel)))
            if formula == 'each':
                if v[0] == 'num':
                    put_fig(row, into, v[1], v[2])
                elif v[0] == 'txt':
                    row['props'][into] = as_text(v[1])
                else:
                    row['props'][into] = 'true' if v[1] else 'false'
            elif v[0] != 'bit':
                return fault('expr: %s needs a boolean in row %s' % (formula, key_of(rel)))
            elif formula == 'where':
                if not v[1]:
                    continue
            elif formula == 'validate':
                if v[1]:
                    continue
                row['props']['/reason'] = as_text(P('reason') if P('reason') is not None else P('expr'))
            elif v[1]:
                row['props'][into] = P('then')
            elif P('else') is not None:
                row['props'][into] = P('else')
            place(out, rel, row)
        return out, ctx
    if formula == 'where':
        key, value, op = P('key'), P('value'), P('op') or 'equals'
        if key is None or value is None:
            return missing()
        return filter_rows(inp, care, lambda rel, r: rule(rel, r, key, value, op)), ctx
    if formula == 'sort':
        slots = (P('slot') or '').split()
        if not slots:
            return missing()
        desc = (P('order') or 'asc') == 'desc'
        order = ranked(slots[0], desc)
        if len(slots) > 1:
            # a second slot breaks ties; a row without a number there counts as zero
            second = lambda item: row_num(item[1], item[0], slots[1]) or Fraction(0)
            order = sorted(order, key=lambda item: (row_num(item[1], item[0], slots[0]), second(item)), reverse=desc)
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
            texts = [t for t in (disp(r, rel, w) for w in wanted) if t is not None]
            if texts:
                r['props'][into] = as_text(sep.join(texts))
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
            t = disp(r, rel, slot)
            if t is not None:
                for i, part in enumerate(t.split(sep) if sep else [t], 1):
                    r['props'][into + '/' + str(i)] = as_text(part)
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
        # the root gains /count: how many distinct values (a record from then on)
        return node(dict(inp['props'], **{'/count': str(len(counts))}), {str(i + 1): node({'/value': v, '/count': str(c)}) for i, (v, c) in enumerate(counts.items())}), ctx
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
        keys = key.split() if key != 'depth' else [key]
        if not keys:
            return missing()
        into = P('into') or '/' + op
        groups = {}
        for rel, r in R:
            # two keys: both values joined by an underscore, both needed
            vs = [slot_text(r, rel, k) for k in keys] if key != 'depth' else [str(len(rel))]
            if all(v is not None for v in vs):
                groups.setdefault('_'.join(vs), []).append(r)
        out = node(inp['props'], rec=inp['rec'])
        for v, members in groups.items():
            figure, scale = (str(len(members)), 0) if op == 'count' else (lambda f, s: (fig(f, s), s))(*reduce_(op, members, slot))
            out['kids'][keyname(v)] = node({'/value': v, into: figure, '/scale': str(scale)})
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
            out['kids'][keyname(rv)] = node({'/' + keyname(cv): (str(len(m)) if op == 'count' else fig(*reduce_(op, m, slot))) for cv, m in cols.items()})
        return out, ctx
    if formula == 'flatten':
        return node(inp['props'], {keyname('_'.join(rel)): node(r['props']) for rel, r in R}, inp['rec']), ctx
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
    if formula == 'when':
        key, value, op, then, other, into = P('key'), P('value'), P('op') or 'equals', P('then'), P('else'), P('into')
        if None in (key, value, then, into):
            return missing()
        out = clone(inp)
        for rel, r in rows(out, care):
            if rule(rel, r, key, value, op):
                r['props'][into] = then
            elif other is not None:
                r['props'][into] = other
        return out, ctx
    if formula == 'coalesce':
        slot, value = P('slot'), P('value')
        if slot is None or value is None:
            return missing()
        into = P('into') or slot
        out = clone(inp)
        for rel, r in rows(out, care):
            t = slot_text(r, rel, slot)
            if t is None:
                r['props'][into] = value
            elif into != slot:
                r['props'][into] = t
        return out, ctx
    if formula == 'part':
        import datetime
        slot, unit = P('slot'), P('unit')
        if slot is None or unit not in ('year', 'quarter', 'month', 'week', 'weekday'):
            return missing()
        into = P('into') or '/' + unit
        out = clone(inp)
        for rel, r in rows(out, care):
            ymd = day_of(r, rel, slot)
            if ymd:
                y, m, d = ymd
                dt = datetime.date(y, m, d)
                r['props'][into] = str({'year': y, 'quarter': (m - 1) // 3 + 1, 'month': m, 'week': (dt.timetuple().tm_yday - 1) // 7 + 1,
                                        'weekday': dt.isoweekday()}[unit])
        return out, ctx
    if formula == 'shift':
        import datetime, calendar
        slot, by, unit = P('slot'), literal(P('by')) if P('by') else None, P('unit') or 'day'
        if slot is None or by is None or by[1] != 0 or unit not in ('day', 'week', 'month', 'year'):
            return missing()
        into = P('into') or slot
        n = int(by[0])
        out = clone(inp)
        for rel, r in rows(out, care):
            ymd = day_of(r, rel, slot)
            if not ymd:
                continue
            y, m, d = ymd
            try:
                if unit in ('day', 'week'):
                    moved = datetime.date(y, m, d) + datetime.timedelta(days=n * (7 if unit == 'week' else 1))
                    y2, m2, d2 = moved.year, moved.month, moved.day
                else:
                    total = y * 12 + (m - 1) + n * (12 if unit == 'year' else 1)
                    if total < 0:
                        continue
                    y2, m2 = total // 12, total % 12 + 1
                    d2 = min(d, calendar.monthrange(y2, m2)[1]) if y2 >= 1 else d
                if y2 < 1:
                    continue
            except (OverflowError, ValueError):
                continue
            r['props'][into] = str(y2 * 10000 + m2 * 100 + d2)
        return out, ctx
    if formula in ('running', 'change', 'moving', 'percent'):
        slot = P('slot')
        if slot is None:
            return missing()
        into = P('into') or '/' + formula
        window = int(P('window')) if formula == 'moving' and is_num(P('window')) else 3
        if formula == 'moving' and window == 0:
            return missing()
        out = clone(inp)
        out_rows = rows(out, care)
        s = row_scale(out_rows, slot)
        total, prev, recent = Fraction(0), None, []
        all_total = sum((row_num(r, rel, slot) for rel, r in out_rows if row_num(r, rel, slot) is not None), Fraction(0))
        for rel, r in out_rows:
            v = row_num(r, rel, slot)
            if v is None:
                continue
            if formula == 'running':
                total += v
                put_fig(r, into, total, s)
            elif formula == 'change':
                if prev is not None:
                    put_fig(r, into, v - prev, s)
                prev = v
            elif formula == 'moving':
                recent = (recent + [v])[-window:]
                put_fig(r, into, sum(recent) / len(recent), s)
            elif all_total != 0:
                put_fig(r, into, v / all_total * 100, 2)
        return out, ctx
    if formula == 'rank':
        into = P('into') or '/rank'
        out = clone(inp)
        for i, (rel, r) in enumerate(rows(out, care)):
            r['props'][into] = str(i + 1)
        return out, ctx
    if formula in ('trim', 'case', 'replace', 'length', 'starts', 'ends'):
        slot = P('slot')
        if slot is None:
            return missing()
        if formula == 'case' and P('to') not in ('lower', 'upper'):
            return missing()
        if formula == 'replace' and P('find') is None:
            return missing()
        if formula in ('starts', 'ends') and P('value') is None:
            return missing()
        into = P('into') or {'length': '/length', 'starts': '/starts', 'ends': '/ends'}.get(formula, slot)
        out = clone(inp)
        for rel, r in rows(out, care):
            t = disp(r, rel, slot)
            if t is None:
                continue
            if formula == 'trim':
                r['props'][into] = as_text(t.strip(''.join(chr(c) for c in range(33))))
            elif formula == 'case':
                r['props'][into] = as_text(ascii_case(t, P('to') == 'upper'))
            elif formula == 'replace':
                r['props'][into] = as_text(t.replace(P('find'), P('with') or '') if P('find') else t)
            elif formula == 'length':
                r['props'][into] = str(len(t.encode()))
            else:
                r['props'][into] = 'true' if (t.startswith(P('value')) if formula == 'starts' else t.endswith(P('value'))) else 'false'
        return out, ctx
    if formula == 'follow':
        slot = P('slot')
        if slot is None:
            return missing()
        into = P('into') or slot
        names = [P('from')] if P('from') else sorted(views)
        names = [n for n in names if n in views]
        if not names:
            return missing()
        out = clone(inp)
        for rel, r in rows(out, care):
            target = ref_path(slot_text(r, rel, slot))
            if target is None:
                continue
            for name in names:
                tree, vcare = views[name]
                root = (view_paths or {}).get(name)
                if tree is None or root is None or not (target == root or target.startswith(root + '/')):
                    continue
                found = record_at(cut(tree, vcare), tuple(seg for seg in target[len(root):].split('/') if seg))
                if found is not None and found['rec']:
                    for k, v in found['props'].items():
                        r['props'][into + k] = v
                break
        return out, ctx
    if formula == 'reference':
        key, into, frm = P('key'), P('into'), P('from') or 'table'
        match = P('match') or key
        if key is None or into is None or frm not in views or (view_paths or {}).get(frm) is None:
            return missing()
        table = view_rows(frm)
        out = clone(inp)
        for rel, r in rows(out, care):
            kv = slot_text(r, rel, key)
            for trel, tr in table:
                if kv is not None and slot_text(tr, trel, match) == kv:
                    path = view_paths[frm] + '/' + '/'.join(trel)
                    r['props'][into] = '/h/x/0/' + str(len(path.strip('/').split('/'))) + path
                    break
        return out, ctx
    if formula in ('median', 'percentile', 'variance', 'stddev'):
        slot = P('slot')
        at = int(P('at')) if is_num(P('at')) else 50
        if slot is None or (formula == 'percentile' and (at > 100 or at < 0)):
            return missing()
        into = P('into') or '/' + formula
        s = max([scale_of(r, slot) for rel, r in R], default=0)
        xs = sorted(v for v in (row_num(r, rel, slot) for rel, r in R) if v is not None)
        n = len(xs)
        if n == 0:
            return node({into: '0', '/scale': str(s)}), ctx
        if formula == 'median':
            v = (xs[(n - 1) // 2] + xs[n // 2]) / 2
            return node({into: fig(v, s), '/scale': str(s)}), ctx
        if formula == 'percentile':
            k = min(max((at * n + 99) // 100, 1), n)
            return node({into: fig(xs[k - 1], s), '/scale': str(s)}), ctx
        X = [int(v * 10 ** s) for v in xs]
        S = sum(X)
        num = sum((n * x - S) ** 2 for x in X)
        if formula == 'variance':
            den = n ** 3 * 10 ** s
            return node({into: str((num + den // 2) // den), '/scale': str(s)}), ctx
        # the standard deviation at the scale, rounded half up: floor(sqrt(4 num / n^3) + 1) / 2
        return node({into: str((math.isqrt(4 * num // n ** 3) + 1) // 2), '/scale': str(s)}), ctx
    if formula == 'mode':
        slot = P('slot')
        if slot is None:
            return missing()
        into = P('into') or '/mode'
        counts = {}
        for rel, r in R:
            v = slot_text(r, rel, slot)
            if v is not None:
                counts[v] = counts.get(v, 0) + 1
        if not counts:
            return node({}), ctx
        best = max(counts.items(), key=lambda kv: kv[1])[1]
        return node({into: next(v for v, c in counts.items() if c == best)}), ctx
    if formula == 'group':
        key = P('key')
        if key is None:
            return missing()
        out = node(inp['props'], rec=inp['rec'])
        for rel, r in R:
            v = slot_text(r, rel, key)
            if v is not None:
                place(out, (keyname(v),) + rel, node(r['props']))
        return out, ctx
    if formula in ('rename', 'drop'):
        if formula == 'rename' and (P('from') is None or P('to') is None):
            return missing()
        if formula == 'drop' and not (P('slots') or '').split():
            return missing()
        out = clone(inp)

        def reshape(n):
            if formula == 'rename':
                frm, to = P('from'), P('to')
                if frm in n['props']:
                    n['props'][to] = n['props'].pop(frm)
                    if frm + '/scale' in n['props']:
                        n['props'][to + '/scale'] = n['props'].pop(frm + '/scale')
            else:
                for slot in P('slots').split():
                    n['props'].pop(slot, None)
                    n['props'].pop(slot + '/scale', None)
        reshape(out)
        for rel, r in rows(out, care):
            reshape(r)
        return out, ctx
    if formula == 'unflatten':
        out = node(inp['props'], rec=inp['rec'])
        for rel, r in R:
            if len(rel) == 1 and '_' in rel[0]:
                place(out, tuple(keyname(seg) for seg in rel[0].split('_')), node(r['props']))
            else:
                place(out, rel, node(r['props']))
        return out, ctx
    if formula == 'explode':
        slot = P('slot')
        if slot is None:
            return missing()
        sep = ' ' if P('with') is None else P('with')
        out = node(inp['props'], rec=inp['rec'])
        for rel, r in R:
            t = disp(r, rel, slot)
            if t is None:
                place(out, rel, node(r['props']))
                continue
            # the pieces as rows 1, 2, 3 under the row's name; the row itself becomes the folder holding them
            for i, piece in enumerate(t.split(sep) if sep else [t], 1):
                place(out, rel + (str(i),), node(dict(r['props'], **{slot: as_text(piece)})))
        return out, ctx
    if formula == 'validate':
        key, op, value, reason = P('key'), P('op') or 'equals', P('value'), P('reason')
        if key is None or (op != 'present' and value is None):
            return missing()
        given = value or ''

        def failing(rel, r):
            has = slot_text(r, rel, key) is not None
            return not (has if op == 'present' else has and rule(rel, r, key, given, op))
        out = filter_rows(inp, care, failing)
        for rel, r in rows(out, care):
            r['props']['/reason'] = reason if reason is not None else (key + ' is absent' if slot_text(r, rel, key) is None else key + ' is not ' + op + ' ' + given)
        return out, ctx
    if formula == 'unique':
        key = P('key')
        if key is None:
            return missing()
        counts = {}
        for rel, r in R:
            v = slot_text(r, rel, key)
            if v is not None:
                counts[v] = counts.get(v, 0) + 1
        out = filter_rows(inp, care, lambda rel, r: counts.get(slot_text(r, rel, key), 0) >= 2)
        for rel, r in rows(out, care):
            r['props']['/count'] = str(counts[slot_text(r, rel, key)])
        return out, ctx
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


# ============================================================================ coverage
# What each entry consumes, by value kind of the slot it reads: natural, scaled, signed, text, boolean, reference, missing (a row
# without the slot), date text; and by shape: empty (no rows), one (one row), cap (fifty rows or more).
KINDS = ['natural', 'scaled', 'signed', 'text', 'boolean', 'reference', 'missing', 'date', 'numtext', 'utf8', 'empty', 'one', 'cap']
UTF8 = ['Zoë', ' Ångström ', 'naïve-café', 'Łódź', 'Ærø', 'façade']
NUMERIC = ['natural', 'scaled', 'signed', 'missing']
TEXTUAL = ['text', 'reference', 'date', 'natural', 'missing']
ROWS = ['empty', 'one', 'cap']
CONSUMES = {}
for _f in ('sum', 'min', 'max', 'avg', 'sort', 'top', 'latest', 'earliest', 'between', 'running', 'change', 'moving', 'percent',
           'median', 'percentile', 'variance', 'stddev', 'each'):
    CONSUMES[_f] = NUMERIC + ROWS
for _f in ('where', 'match', 'split', 'join', 'date', 'distinct', 'select', 'by', 'grid', 'lookup', 'when', 'coalesce', 'trim', 'case',
           'replace', 'length', 'starts', 'ends', 'reference', 'mode', 'group', 'explode', 'validate', 'unique', 'except', 'intersect', 'diff'):
    CONSUMES[_f] = TEXTUAL + ROWS
for _f in ('any', 'all'):
    CONSUMES[_f] = ['boolean', 'natural', 'missing'] + ROWS
for _f in ('part', 'shift'):
    CONSUMES[_f] = ['date', 'natural', 'missing'] + ROWS
CONSUMES['follow'] = ['reference', 'missing'] + ROWS
for _f in ('count', 'rank', 'flatten', 'unflatten', 'merge', 'gather', 'rename', 'drop'):
    CONSUMES[_f] = ROWS
for _f in ('add', 'subtract', 'multiply', 'divide', 'round', 'since'):
    CONSUMES[_f] = ['natural', 'scaled', 'signed', 'missing']
CONSUMES['pick'] = ['natural', 'text', 'missing']
CONSUMES['put'] = []
EXPR_ENTRIES = ('each:x', 'where:x', 'when:x', 'validate:x')
for _f in EXPR_ENTRIES:
    CONSUMES[_f] = ['natural', 'scaled', 'signed', 'text', 'boolean', 'reference', 'missing', 'date', 'numtext', 'utf8'] + ROWS
for _f in ('lower', 'upper', 'trim', 'length', 'split', 'match'):
    CONSUMES[_f if _f not in ('lower', 'upper') else 'case'] = CONSUMES[_f if _f not in ('lower', 'upper') else 'case'] + ['utf8']
OPS = ['+', '-', '*', '/', 'neg', '=', '!=', '<', '<=', '>', '>=', 'and', 'or', 'not', 'in',
       'min', 'max', 'abs', 'round', 'len', 'lower', 'upper', 'trim', 'contains', 'starts', 'ends']
SLOT_PARAMS = {'where': 'key', 'match': 'key', 'when': 'key', 'validate': 'key', 'unique': 'key', 'group': 'key', 'by': 'key', 'lookup': 'key',
               'except': 'key', 'intersect': 'key', 'diff': 'key',
               'reference': 'key', 'grid': 'row', 'each': 'left', 'add': 'left', 'subtract': 'left', 'multiply': 'left', 'divide': 'left',
               'select': 'slots', 'join': 'slots', 'drop': 'slots', 'pick': 'from', 'rename': 'from'}


def value_kind(text):
    if text is None:
        return 'missing'
    if isinstance(text, Text):
        return 'numtext'
    if any(ord(c) > 127 for c in text):
        return 'utf8'
    if text.startswith('/h/'):
        return 'reference'
    if text in ('true', 'false'):
        return 'boolean'
    if re.match(r'\d{4}-\d{2}-\d{2}', text):
        return 'date'
    if is_num(text):
        return 'signed' if text.startswith('-') else 'natural'
    if DEC.match(text):
        return 'signed' if text.startswith('-') else 'scaled'
    return 'text'


def kinds_of(formula, params, inp, care):
    """The value kinds the entry meets on this input: on the slot its first parameter names (every slot when it names none),
    across the rows (the root for root entries), plus the shape kinds."""
    if inp is None:
        return set()
    R = rows(cut(inp, care), care)
    root_only = formula in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'pick', 'put')
    members = [((), inp)] if root_only else R
    key = params.get(SLOT_PARAMS.get(formula, 'slot'))
    slots = str(key).split() if key is not None else None
    if formula.endswith(':x'):
        try:
            slots = ['/' + n for n in sorted(expr_slots(expr_parse(params.get('expr', ''))))] or None
        except ExprError:
            slots = None
    found = set()
    for rel, r in members:
        for slot in (slots or [k for k in r['props'] if not k.endswith('/scale')]):
            if not str(slot).startswith('/'):
                continue
            t = slot_text(r, rel, slot)
            k = value_kind(t)
            if k == 'natural' and slot in r['props'] and scale_of(r, slot) > 0:
                k = 'scaled'
            found.add(k)
    if not root_only:
        found.add('empty' if not R else 'one' if len(R) == 1 else 'cap' if len(R) >= 50 else 'some')
    return found


class Coverage:
    def __init__(self):
        self.cells = {}
        self.chains = {}
        self.ops = {}
        self.long = {'eight terms or more': 0, 'three paren levels': 0, 'and chains of three or more': 0, 'expressions': 0}

    def note_expr(self, src):
        try:
            tree = expr_parse(src)
        except ExprError:
            return
        terms, ands = expr_size(tree)
        self.long['expressions'] += 1
        self.long['eight terms or more'] += terms >= 8
        self.long['three paren levels'] += paren_depth(src) >= 3
        self.long['and chains of three or more'] += ands >= 3

    def filled(self):
        total = sum(len(CONSUMES[f]) * 12 for f in CONSUMES)
        fine = sum(1 for f in CONSUMES for k in CONSUMES[f] for c in 'xyz' for p in ('pinned', 'live') for v in ('view', 'none')
                   if self.cells.get((f, k, c, p, v), 0) == 0)
        return total - fine, total

    def add(self, formula, kinds, care, pinned, viewed, depth, ops=()):
        for k in kinds:
            key = (formula, k, care, 'pinned' if pinned else 'live', 'view' if viewed else 'none')
            self.cells[key] = self.cells.get(key, 0) + 1
        for op in ops:
            self.ops[(formula, op)] = self.ops.get((formula, op), 0) + 1
        self.chains[(depth, care, 'view' if viewed else 'none')] = self.chains.get((depth, care, 'view' if viewed else 'none'), 0) + 1

    def wants(self, formula):
        """The kinds and margins this entry has not met yet: what the next case should go for."""
        have = {key[1] for key in self.cells if key[0] == formula}
        margins = {d for key in self.cells if key[0] == formula for d in key[2:]}
        root_only = formula in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'pick', 'put')
        needs_view = formula in ('lookup', 'except', 'intersect', 'diff', 'reference', 'follow')
        want = {k for k in CONSUMES.get(formula, []) if k not in have}
        for d in ('x', 'y', 'z', 'pinned', 'live', 'view', 'none'):
            if d not in margins and not (root_only and d in ('y', 'z')) and not (needs_view and d == 'none'):
                want.add(d)
        if formula in EXPR_ENTRIES:
            want |= {'op:' + op for op in OPS if (formula, op) not in self.ops}
        return want

    def report(self, strict):
        print('| entry | ' + ' | '.join(KINDS) + ' | x | y | z | pinned | live | view | none |')
        print('|---|' + '---|' * (len(KINDS) + 7))
        zero = []
        for f in sorted(CONSUMES):
            by_kind = {k: sum(n for key, n in self.cells.items() if key[0] == f and key[1] == k) for k in KINDS}
            margins = {d: sum(n for key, n in self.cells.items() if key[0] == f and d in key[2:]) for d in ('x', 'y', 'z', 'pinned', 'live', 'view', 'none')}
            print('| %s | %s | %s |' % (f, ' | '.join(str(by_kind[k]) for k in KINDS), ' | '.join(str(margins[d]) for d in ('x', 'y', 'z', 'pinned', 'live', 'view', 'none'))))
            zero += [(f, k) for k in CONSUMES[f] if by_kind[k] == 0]
            zero += [(f, d) for d in margins if margins[d] == 0 and not (f in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'pick', 'put') and d in ('y', 'z'))
                     and not (f in ('lookup', 'except', 'intersect', 'diff', 'reference', 'follow') and d == 'none')]
        print('| expr entry | ' + ' | '.join(OPS) + ' |')
        print('|---|' + '---|' * len(OPS))
        for f in EXPR_ENTRIES:
            print('| %s | %s |' % (f, ' | '.join(str(self.ops.get((f, op), 0)) for op in OPS)))
            zero += [(f, op) for op in OPS if self.ops.get((f, op), 0) == 0]
        reached, total = self.filled()
        print('chains (depth, care, view): ' + ', '.join('%s=%d' % (k, n) for k, n in sorted(self.chains.items())))
        print('long expressions: ' + ', '.join('%s=%d' % (k, n) for k, n in self.long.items()))
        print('coverage: %d entry-kind cells, %d zero; %d of %d fine cells (entry x kind x care x pinned x view) filled' % (
            sum(len(CONSUMES[f]) for f in CONSUMES), len(zero), reached, total))
        if zero:
            print('ZERO COVERAGE', zero)
        if strict and zero:
            raise AssertionError('the generator never drew these entry-kind cells: %s' % zero)
        return zero


# ============================================================================ generators
FORMULAS = ['count', 'sum', 'min', 'max', 'avg', 'any', 'all', 'where', 'sort', 'top', 'latest', 'earliest', 'each', 'lookup',
            'distinct', 'select', 'by', 'grid', 'flatten', 'merge', 'gather', 'except', 'intersect', 'diff', 'add', 'subtract', 'multiply',
            'divide', 'pick', 'put', 'round', 'since', 'between', 'join', 'match', 'split', 'date',
            'when', 'coalesce', 'part', 'shift', 'running', 'rank', 'change', 'moving', 'percent', 'trim', 'case', 'replace', 'length',
            'starts', 'ends', 'follow', 'reference', 'median', 'percentile', 'variance', 'stddev', 'mode', 'group', 'rename', 'drop',
            'unflatten', 'explode', 'validate', 'unique']          # amend has its own stage (notes need the world's stamps)
SHAPES = ['rec1', 'recN', 'recM', 'list', 'map', 'set', 'table', 'bag', 'attach', 'tree', 'grouped', 'matrix', 'hier', 'uneven', 'empty', 'one', 'list', 'map', 'table']
WIDE_EVERY = 25          # one cap-sized shape (fifty rows or more) in every batch of cases
REQUIRED = {'where': ['key', 'value'], 'each': ['left', 'right', 'op'], 'lookup': ['key', 'take'], 'select': ['slots'], 'by': ['key'],
            'grid': ['row', 'col'], 'pick': ['from', 'into'], 'put': ['into', 'value'], 'round': ['slot', 'places'],
            'since': ['slot', 'from'], 'between': ['slot', 'from', 'to'], 'join': ['slots'], 'match': ['key', 'value'],
            'split': ['slot'], 'date': ['slot']}
for _f in ('add', 'subtract', 'multiply', 'divide'):
    REQUIRED[_f] = ['left', 'right']
REQUIRED.update({'when': ['key', 'value', 'then', 'into'], 'coalesce': ['slot', 'value'], 'part': ['slot', 'unit'], 'shift': ['slot', 'by'],
                 'case': ['slot', 'to'], 'replace': ['slot', 'find'], 'starts': ['slot', 'value'], 'ends': ['slot', 'value'], 'follow': ['slot'],
                 'reference': ['key', 'into'], 'group': ['key'], 'rename': ['from', 'to'], 'drop': ['slots'], 'explode': ['slot'],
                 'validate': ['key'], 'unique': ['key']})
for _f in ('running', 'change', 'moving', 'percent', 'trim', 'length', 'median', 'percentile', 'variance', 'stddev', 'mode'):
    REQUIRED[_f] = ['slot']
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
        if isinstance(v, Text):
            out[k] = {'type': 'str', 'value': str(v)}
        elif is_num(v):
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
    def __init__(self, rng, node_, coverage=None):
        self.rng, self.node, self.coverage = rng, node_, coverage

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
            if not self.coin(0.6):
                return node(rec=False)
            p = props(**kw)
            if self.coin(0.4):
                p['/n'] = text(num())
                if self.coin(0.4):
                    p['/scale'] = str(rng.randint(1, 2))
            return node(p)
        k = rng.randint(2, 5)

        def extras(p):
            # what imported data looks like: some rows carry a reference, a date, a boolean; some lack a slot
            if self.coin(0.25):
                p['/rf'] = '/h/x/0/2/' + self.node + '/user'
            if self.coin(0.2):
                p['/d'] = '%d-%02d-%02d' % (rng.randint(1990, 2026), rng.randint(1, 12), rng.randint(1, 28))
            if self.coin(0.2):
                p['/ok'] = text(self.coin())
            if self.coin(0.15):
                p['/code'] = Text(str(rng.randint(10, 99)))
            if self.coin(0.1):
                p['/name'] = rng.choice(UTF8)
            if self.coin(0.15):
                for slot in list(p):
                    if slot in ('/n', '/t', '/amount', '/region') and self.coin():
                        p.pop(slot, None)
                        p.pop(slot + '/scale', None)
            return p
        if kind == 'empty':
            return root()
        if kind == 'one':
            r = root()
            r['kids'][rng.choice(NAMES)] = row(n=num(), t=self.word())
            return r
        if kind == 'wide':
            r = root(title='wide')
            for i in range(rng.randint(50, 60)):
                p = row(n=rng.randint(1, 400), t=self.word())
                r['kids']['w' + str(i + 1)] = p
            return r
        if kind == 'rec1':
            p = props(n=num())
            if self.coin(0.4):
                p['/scale'] = str(rng.randint(1, 2))
            return node(p)
        if kind == 'recN':
            return row('amount', n=num(), t=self.word(), ok=self.coin(), when=rng.randint(1, 99), amount=num(), d='%d-%02d-%02d' % (rng.randint(1990, 2026), rng.randint(1, 12), rng.randint(1, 28)))
        if kind == 'recM':
            return node(props(n=num(), t=self.word(), ok=self.coin(), p='/' + self.node + '/user', rf='/h/x/0/2/' + self.node + '/user'))
        if kind == 'list':
            r = root(title='list')
            for i in range(k):
                r['kids'][str(i + 1)] = row(n=num(), t=self.word())
                extras(r['kids'][str(i + 1)]['props'])
        elif kind == 'map':
            r = root()
            for nm in rng.sample(NAMES, k):
                r['kids'][nm] = row(n=num(), region=self.word())
                extras(r['kids'][nm]['props'])
        elif kind == 'set':
            r = root()
            for nm in rng.sample(NAMES, k):
                r['kids'][nm] = node()
        elif kind == 'table':
            r = root(title='table')
            for i in range(k):
                r['kids']['r' + str(i + 1)] = row('amount', region=self.word(), status=rng.choice(['open', 'closed']), amount=num(), when=rng.randint(1, 99))
                extras(r['kids']['r' + str(i + 1)]['props'])
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

    def params(self, f, inp, care, views, wants=frozenset()):
        """Settings that are valid for this input most of the time; a slot that carries a kind the entry has not met
        yet is preferred (wants), so the coverage matrix fills."""
        rng = self.rng
        R = rows(inp, care)
        members = [((), inp)] if f in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'pick', 'put') else (R or [((), inp)])

        def slot_kinds(slot):
            found = set()
            for rel, r in members:
                t = slot_text(r, rel, slot)
                k = value_kind(t)
                if k == 'natural' and slot in r['props'] and scale_of(r, slot) > 0:
                    k = 'scaled'
                found.add(k)
            return found

        def pick(cands):
            cands = list(cands)
            steered = [sl for sl in cands if isinstance(sl, str) and sl.startswith('/') and slot_kinds(sl) & wants]
            return rng.choice(steered) if steered else rng.choice(cands)

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
            p['slot'] = pick(rown + (rowt if wants & {'text', 'missing'} else []))
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f in ('any', 'all'):
            p['slot'] = pick(rowb + rown)
        elif f == 'where':
            op = pick(['equals', 'equals', 'equals', 'over', 'under', 'before', 'after', 'contains'])
            if wants & {'reference', 'date', 'text', 'boolean', 'missing'}:
                op = pick(['equals', 'contains'])
            if 'natural' in wants:
                rowt = rowt + rown
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
            if 'natural' in wants:
                rowt = rowt + rown
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
            p['slots'] = ' '.join(dict.fromkeys([pick(rowt + rown)] + rng.sample(sorted(set(rowt + rown)), rng.randint(0, 1))))
            if self.coin():
                p['with'] = pick([', ', '-', ''])
            if self.coin(0.3):
                p['into'] = '/full'
        elif f == 'match':
            p['key'], p['value'] = pick(rowt + (rown if 'natural' in wants else [])), pick(['e', 'o', 'st', 'th', 'a', 'west', 'z', '1', 'ë', 'Ło', 'é'])
            if self.coin():
                p['op'] = pick(['contains', 'starts', 'ends'])
        elif f == 'split':
            p['slot'] = pick(rowt + (rown if 'natural' in wants else []))
            if self.coin():
                p['with'] = pick(['-', 'e', 'o', ' ', 'ë', 'ç'])
            if self.coin(0.3):
                p['into'] = '/part'
        elif f == 'date':
            p['slot'] = pick(rowt + (rown if 'natural' in wants else []))
            if self.coin(0.3):
                p['into'] = '/on'
        elif f == 'by':
            p['key'] = pick(rowt + rowb + (rown if 'natural' in wants else []))
            op = pick(['count', 'count', 'sum', 'min', 'max', 'avg'])
            if op != 'count' or self.coin():
                p['op'] = op
            if op != 'count':
                p['slot'] = pick(rown)
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f == 'grid':
            p['row'], p['col'] = pick(rowt + (rown if 'natural' in wants else [])), pick(rowt + rowb)
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
        elif f == 'when':
            p['key'] = pick(rowt + rowb + rown)
            p['value'] = pick(vals(p['key']) or [self.word()])
            if self.coin():
                p['op'] = pick(['equals', 'over', 'under', 'contains'])
            p['then'], p['into'] = pick([self.word(), str(rng.randint(1, 9))]), '/flag'
            if self.coin(0.7):
                p['else'] = pick([self.word(), '0'])
        elif f == 'coalesce':
            p['slot'], p['value'] = pick(rown + rowt + ['/missing']), pick([self.word(), '0'])
            if self.coin(0.3):
                p['into'] = '/filled'
        elif f in ('part', 'shift'):
            dates = [sl for sl in rowt if any(value_kind(v) == 'date' for v in vals(sl))]
            p['slot'] = pick(dates) if dates and self.coin(0.8) else pick(rowt + rown)
            if f == 'part':
                p['unit'] = pick(['year', 'quarter', 'month', 'week', 'weekday'])
            else:
                p['by'], p['unit'] = pick(['3', '-10', '1', '-1', '14', '2']), pick(['day', 'day', 'week', 'month', 'year'])
            if self.coin(0.3):
                p['into'] = '/when2'
        elif f in ('running', 'change', 'moving', 'percent', 'median', 'percentile', 'variance', 'stddev'):
            p['slot'] = pick(rown)
            if f == 'moving' and self.coin():
                p['window'] = rng.randint(1, 3)
            if f == 'percentile':
                p['at'] = pick([0, 25, 50, 75, 90, 100])
            if self.coin(0.3):
                p['into'] = '/fig'
        elif f == 'rank':
            if self.coin(0.3):
                p['into'] = '/pos'
        elif f in ('trim', 'length', 'case', 'replace', 'starts', 'ends', 'explode'):
            p['slot'] = pick(rowt + (rown if 'natural' in wants else []))
            if f == 'case':
                p['to'] = pick(['lower', 'upper'])
            if f == 'replace':
                p['find'] = pick(['e', 'o', 'st', 'th'])
                if self.coin():
                    p['with'] = pick(['', 'X', 'ee'])
            if f in ('starts', 'ends'):
                p['value'] = pick(['e', 'w', 'st', 'th', 'west', 'z'])
            if f == 'explode' and self.coin():
                p['with'] = pick(['-', 'e', ' '])
            if f in ('trim', 'case', 'replace', 'length', 'starts', 'ends') and self.coin(0.3):
                p['into'] = '/txt'
        elif f == 'follow':
            p['slot'] = '/ref' if self.coin(0.8) else pick(rowt)
            if views and self.coin(0.4):
                p['from'] = pick(sorted(views))
            if self.coin(0.3):
                p['into'] = '/pointed'
        elif f == 'reference':
            if 'natural' in wants:
                rowt = rowt + rown
            name = next((n for n in views if n not in ('v1', 'v2')), 'table')
            if name != 'table':
                p['from'] = name
            table = view_rows_of(views, name)
            tt = set()
            for _, r in table:
                tt |= set(kinds(r['props'])[2])
            tt = sorted(tt) + ['/name']
            pairs = [(k, m) for k in rowt for m in tt if set(vals(k)) & {slot_text(r, rel, m) for rel, r in table}]
            p['key'], match = pick(pairs) if pairs and self.coin(0.7) else (pick(rowt), pick(tt))
            if match != p['key'] or self.coin():
                p['match'] = match
            p['into'] = '/ref_to'
        elif f == 'mode':
            p['slot'] = pick(rowt + rown)
        if f in ('except', 'intersect', 'diff') and 'key' not in p and wants & {'reference', 'date', 'missing', 'natural'}:
            p['key'] = pick(rowt + rown)
            if self.coin(0.3):
                p['into'] = '/common'
        elif f in ('group', 'unique'):
            p['key'] = pick(rowt + rowb + (rown if 'natural' in wants else []))
        elif f == 'rename':
            p['from'], p['to'] = pick(rown + rowt), '/renamed'
        elif f == 'drop':
            p['slots'] = ' '.join(rng.sample(sorted(set(rown + rowt + rowb)), rng.randint(1, 2)))
        elif f == 'validate':
            op = pick(['equals', 'over', 'under', 'contains', 'present'])
            if wants & {'reference', 'date', 'text', 'boolean', 'missing'}:
                op = pick(['equals', 'contains', 'present'])
            p['key'] = pick(rown) if op in ('over', 'under') else pick(rowt + rowb + rown)
            if op != 'equals' or self.coin():
                p['op'] = op
            if op != 'present':
                p['value'] = pick(vals(p['key']) or [self.word()]) if op != 'over' and op != 'under' else lit()
            if self.coin(0.3):
                p['reason'] = 'bad row'
        if f == 'by' and self.coin(0.25):
            p['key'] = p['key'] + ' ' + pick(rowt + rowb)
        if f == 'sort' and self.coin(0.3):
            p['slot'] = p['slot'] + ' ' + pick(rown)
        return p


def gen_expr(g, f, inp, care, wants):
    """A random expression for one of the four entries: a boolean for where, when and validate, anything for each; the
    operators and functions the entry has not met yet (wants, as op:<name>) come first."""
    rng, pick = g.rng, g.rng.choice
    R = rows(inp, care) or [((), inp)]

    def slots(test):
        return sorted({k[1:] for _, r in R for k, v in r['props'].items() if '/' not in k[1:] and not k.endswith('/scale') and test(k, v)})
    nums = slots(lambda k, v: is_num(v) or (not isinstance(v, Text) and DEC.match(v) is not None)) or ['n']
    texts = slots(lambda k, v: not is_num(v) and v not in ('true', 'false') and not DEC.match(v)) or ['t']
    bools = slots(lambda k, v: v in ('true', 'false'))
    wanted = [w[3:] for w in wants if w.startswith('op:')]

    def want(*ops):
        """A wanted operator of these, taken once."""
        hits = [op for op in wanted if op in ops]
        if not hits:
            return None
        op = pick(hits)
        wanted.remove(op)
        return op

    def lit():
        return pick([str(rng.randint(0, 9)), str(rng.randint(1, 60)), str(rng.randint(1, 9)) + '.5', str(rng.randint(10, 99)) + '.25'])

    def num(depth=0):
        op = want('+', '-', '*', '/', 'neg', 'min', 'max', 'abs', 'round', 'len') if depth < 2 else None
        if op in ('+', '-', '*', '/'):
            return '%s %s %s' % (num(depth + 1), op, num(depth + 1))
        if op == 'neg':
            return '-' + num(depth + 1)
        if op in ('min', 'max'):
            return '%s(%s, %s)' % (op, num(depth + 1), num(depth + 1))
        if op == 'abs':
            return 'abs(%s)' % num(depth + 1)
        if op == 'round':
            return 'round(%s, %d)' % (num(depth + 1), rng.randint(0, 2))
        if op == 'len':
            return 'len(%s)' % txt(depth + 1)
        r = rng.random()
        if depth > 1 or r < 0.4:
            return pick([pick(nums), pick(nums), lit(), '-' + pick(nums)])
        if r < 0.75:
            return '%s %s %s' % (num(depth + 1), pick(['+', '-', '*', '/']), num(depth + 1))
        return pick(['min(%s, %s)' % (num(depth + 1), num(depth + 1)), 'max(%s, %s)' % (num(depth + 1), lit()), 'abs(%s)' % num(depth + 1),
                     'round(%s, %d)' % (num(depth + 1), rng.randint(0, 2)), 'len(%s)' % txt(depth + 1), '(%s)' % num(depth + 1)])

    def txt(depth=0):
        op = want('lower', 'upper', 'trim') if depth < 2 else None
        if op:
            return '%s(%s)' % (op, txt(depth + 1))
        r = rng.random()
        if depth > 1 or r < 0.6:
            return pick([pick(texts), pick(texts), "'" + pick(TEXT) + "'", "'e'"])
        return '%s(%s)' % (pick(['lower', 'upper', 'trim']), txt(depth + 1))

    def bit(depth=0):
        op = want('=', '!=', '<', '<=', '>', '>=', 'and', 'or', 'not', 'in', 'contains', 'starts', 'ends') if depth < 2 else None
        if op in ('=', '!=', '<', '<=', '>', '>='):
            return '%s %s %s' % (num(depth + 1), op, num(depth + 1)) if op not in ('=', '!=') or g.coin() else '%s %s %s' % (txt(depth + 1), op, txt(depth + 1))
        if op in ('and', 'or'):
            return '%s %s %s' % (bit(depth + 1), op, bit(depth + 1))
        if op == 'not':
            return 'not %s' % bit(depth + 1)
        if op == 'in':
            return '%s in %s' % (txt(depth + 1), txt(depth + 1))
        if op in ('contains', 'starts', 'ends'):
            return '%s(%s, %s)' % (op, txt(depth + 1), txt(depth + 1))
        if depth < 2 and any(w in wanted for w in ('+', '-', '*', '/', 'neg', 'min', 'max', 'abs', 'round', 'len')):
            return '%s %s %s' % (num(depth + 1), pick(['<', '<=', '>', '>=', '=', '!=']), num(depth + 1))
        if depth < 2 and any(w in wanted for w in ('lower', 'upper', 'trim')):
            return '%s = %s' % (txt(depth + 1), txt(depth + 1))
        r = rng.random()
        if depth > 1 or r < 0.5:
            return pick(['%s %s %s' % (num(2), pick(['<', '<=', '>', '>=', '=', '!=']), num(2)), '%s = %s' % (txt(2), txt(2)),
                         '%s in %s' % (txt(2), txt(2)), '%s(%s, %s)' % (pick(['contains', 'starts', 'ends']), txt(2), txt(2))] + (bools + ['true']) * (1 if bools else 0))
        if r < 0.8:
            return '%s %s %s' % (bit(depth + 1), pick(['and', 'or']), bit(depth + 1))
        return 'not %s' % bit(depth + 1)
    def long_num(level=0):
        """Four to eight terms with parens up to three levels deep."""
        parts = []
        for _ in range(rng.randint(4, 8) if level == 0 else rng.randint(2, 3)):
            if level < 3 and g.coin(0.35):
                parts.append('(' + long_num(level + 1) + ')')
            else:
                parts.append(pick([pick(nums), pick(nums), lit()]))
        if level == 0 and g.coin(0.5):
            parts[0] = '(%s + (%s * (%s - %s)))' % (pick(nums), pick(nums), lit(), pick(nums))     # three levels, on purpose
        out = parts[0]
        for part in parts[1:]:
            out += ' ' + pick(['+', '-', '*', '/', '+']) + ' ' + part
        return out

    def long_bit():
        """A chain of three to five comparisons joined by and (one or, sometimes)."""
        parts = [bit(2) for _ in range(rng.randint(3, 5))]
        out = parts[0]
        for part in parts[1:]:
            out += (' or ' if g.coin(0.15) else ' and ') + part
        return out
    if not wanted and g.coin(0.2):
        return long_num() if f == 'each' and g.coin(0.6) else long_bit()
    if f == 'each':
        if any(op in wanted for op in ('=', '!=', '<', '<=', '>', '>=', 'and', 'or', 'not', 'in', 'contains', 'starts', 'ends')):
            return bit()
        if any(op in wanted for op in ('lower', 'upper', 'trim')):
            return txt()
        choice = rng.random()
        return num() if choice < 0.5 else txt() if choice < 0.75 else bit()
    return bit()


def view_rows_of(views, name):
    v = views.get(name)
    return [] if v is None or v[0] is None else rows(v[0], v[1])


def inject(g, shape, wants):
    """Put a wanted value kind on the shape where the generator would rarely draw it: a row without its slot, a row with a
    reference, a date, a boolean, a negative or a scaled number; a negative or scaled number on the root for the root entries.
    Only rows history leaves alone change, so what the world holds is what the oracle sees."""
    rng = g.rng
    pairs = [(r0, record_at(shape['state'], rel)) for rel, r0 in rows(shape['state0'], 'z')]
    pairs = [(a, b) for a, b in pairs if b is not None and a['props'] == b['props']]
    if not pairs:
        pairs = []
    root_pair = (shape['state0'], shape['state']) if shape['state0']['rec'] else None

    def both(pair, f):
        for n in pair:
            f(n['props'])
    for kind in sorted(wants):
        # one value, set on both copies of the row: the world holds the first, the oracle reads the second
        if kind == 'missing' and pairs:
            def drop(p):
                for slot in ('/n', '/t', '/amount', '/region'):
                    if slot in p:
                        p.pop(slot); p.pop(slot + '/scale', None); return
            both(rng.choice(pairs), drop)
        elif kind == 'reference' and pairs:
            both(rng.choice(pairs), lambda p: p.__setitem__('/rf', '/h/x/0/2/' + g.node + '/user'))
        elif kind == 'date' and pairs:
            day = '%d-%02d-%02d' % (rng.randint(1990, 2026), rng.randint(1, 12), rng.randint(1, 28))
            both(rng.choice(pairs), lambda p: p.__setitem__('/d', day))
        elif kind == 'boolean' and pairs:
            flag = text(g.coin())
            both(rng.choice(pairs), lambda p: p.__setitem__('/ok', flag))
        elif kind == 'numtext' and pairs:
            code = Text(str(rng.randint(10, 99)))
            both(rng.choice(pairs), lambda p: p.__setitem__('/code', code))
        elif kind == 'utf8' and pairs:
            # one row with multi-byte names in its slots: the text entries are byte-level, and this is where it shows
            name = rng.choice(UTF8)
            both(rng.choice(pairs), lambda p: p.__setitem__('/name', name))
        elif kind == 'signed':
            for pair in ([rng.choice(pairs)] if pairs else []) + ([root_pair] if root_pair else []):
                v = str(-rng.randint(1, 99))
                both(pair, lambda p: p.__setitem__('/n', v))
        elif kind == 'scaled':
            for pair in ([rng.choice(pairs)] if pairs else []) + ([root_pair] if root_pair else []):
                v, sc = str(rng.randint(1, 999)), str(rng.randint(1, 2))
                both(pair, lambda p: (p.__setitem__('/n', v), p.__setitem__('/n/scale', sc)))


def gen_case(g, i, home):
    """One case: a primary shape, 0-2 secondary shapes, a chain of 1-4 cells, each with its oracle expectation."""
    rng = g.rng
    base = home + '/d/' + str(i)
    # the first entry is drawn first; what it still lacks in the coverage matrix steers the shape, care, pinning and views
    def wanting(f):
        return len(g.coverage.wants(f)) + (len(g.coverage.wants(f + ':x')) if f in ('each', 'where', 'when', 'validate') else 0)
    first = rng.choice(FORMULAS)
    if g.coverage is not None:
        first = max((rng.choice(FORMULAS) for _ in range(6)), key=wanting)
    expr_first = first in ('each', 'where', 'when', 'validate') and g.coin(0.5)
    wants = set()
    if g.coverage is not None:
        if first in ('each', 'where', 'when', 'validate'):
            old, new = g.coverage.wants(first), g.coverage.wants(first + ':x')
            expr_first = g.coin(0.5) if (old and new) or not (old or new) else bool(new)
        wants = g.coverage.wants(first + ':x' if expr_first else first)
    kind = ('wide' if 'cap' in wants else 'one' if 'one' in wants else 'empty' if 'empty' in wants else
            rng.choice(['table', 'list', 'map']) if wants & {'date', 'reference', 'boolean', 'missing', 'scaled', 'signed', 'numtext', 'utf8'} else
            rng.choice(SHAPES))
    if i % WIDE_EVERY == 0:
        kind = 'wide'
    prim = g.shape(kind, base + '/p', history=g.coin(0.35))
    inject(g, prim, wants)
    shapes = [prim]
    for j in range(rng.choice([0, 1, 1, 2])):
        shapes.append(g.shape(rng.choice(SHAPES), base + '/v' + str(j + 1)))
    depth = 1 if g.coin(0.5) else rng.randint(2, 4)
    if (depth > 1 or 'view' in wants) and len(shapes) == 1:
        shapes.append(g.shape(rng.choice(SHAPES), base + '/v1'))        # a chain gets a secondary input somewhere
    view_step = 0 if 'view' in wants else (rng.randint(1, depth - 1) if 'none' in wants and depth > 1 else rng.randint(0, depth - 1))
    care = next((c for c in 'xyz' if c in wants), rng.choice('xyz'))
    pinned = prim['has_root'] and ('pinned' in wants or (g.coin(0.2) and 'live' not in wants))
    tack = {'kind': 'shape', 'shape': 0, 'care': care, 'pinned': pinned}

    def at(shape, care, pinned):
        """A shape as an input at a care: at x a folder with no record of its own is nothing, and so is a folder with no
        record anywhere beneath it at any care."""
        tree = shape['state0'] if pinned else shape['state']
        if not tree['rec'] and (care == 'x' or not rows(tree, 'z')):
            return None
        return cut(tree, care)
    inp = at(prim, care, pinned)
    cells = []
    for step in range(depth):
        f = first if step == 0 else (max((rng.choice(FORMULAS) for _ in range(3)), key=wanting) if g.coverage is not None else rng.choice(FORMULAS))
        needs = {'lookup': 'table', 'except': 'other', 'intersect': 'other', 'diff': 'other', 'reference': 'table', 'follow': 'table'}.get(f)
        if needs and len(shapes) == 1 and g.coin(0.8):
            shapes.append(g.shape(rng.choice(SHAPES), base + '/v1'))
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
        for idx in (available if (step == view_step or needs) and not (step == 0 and 'none' in wants and not needs) else []):
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
        shape_views = sorted(n for n in views if views[n]['kind'] == 'shape')
        if f == 'follow' and step == 0 and shape_views:
            # references on the primary's rows (the ones history leaves alone) into a view's rows, as an import would leave them
            target_shape = shapes[views[rng.choice(shape_views)]['shape']]
            targets = rows(target_shape['state0'], 'z')
            if targets:
                for rel, r0 in rows(prim['state0'], 'z'):
                    r1 = record_at(prim['state'], rel)
                    if r1 is not None and r1['props'] == r0['props'] and g.coin(0.7):
                        trel, _ = rng.choice(targets)
                        path = target_shape['path'] + '/' + '/'.join(trel)
                        r0['props']['/ref'] = r1['props']['/ref'] = '/h/x/0/' + str(len(path.strip('/').split('/'))) + path
                inp = at(prim, care, tack.get('pinned', False)) if tack['kind'] == 'shape' else inp
                # the views were cut before the references landed: cut them again, so a view of the same shape carries them
                for name, v in views.items():
                    if v['kind'] != 'bad':
                        view_trees[name] = (at(shapes[v['shape']], v['care'], v['pinned']), v['care'])
        expr_mode = f in ('each', 'where', 'when', 'validate') and (expr_first if step == 0 else
                                                                   (len(g.coverage.wants(f + ':x')) > len(g.coverage.wants(f)) if g.coverage is not None else g.coin(0.5)))
        if expr_mode:
            step_wants = wants if step == 0 else (g.coverage.wants(f + ':x') if g.coverage is not None else frozenset())
            params = {'expr': gen_expr(g, f, inp if inp is not None else node(), care, step_wants)}
            if f in ('each', 'when'):
                params['into'] = '/v'
            if f == 'when':
                params['then'] = rng.choice([g.word(), str(rng.randint(1, 9))])
                if g.coin(0.7):
                    params['else'] = g.word()
            if f == 'validate' and g.coin(0.3):
                params['reason'] = 'bad row'
            if bad == 'badslot':
                params['expr'] = params['expr'] + ' +'          # a bad expression: one fault with its position
            elif bad == 'wrongkind':
                params['key'] = '/n'                            # expr beside the old settings: a fault
            elif bad == 'omit' and f in ('each', 'when'):
                params.pop('into')
        else:
            params = g.params(f, inp if inp is not None else node(), care, view_trees, wants if step == 0 else frozenset())
        if bad == 'omit' and REQUIRED.get(f) and not expr_mode:
            params.pop(rng.choice(REQUIRED[f]), None)
        elif bad == 'badslot' and not expr_mode:
            slotty = [k for k in params if k in ('slot', 'key', 'left', 'right', 'from', 'take', 'match', 'row', 'col') and str(params[k]).startswith('/')]
            if slotty:
                params[rng.choice(slotty)] = '/nope'
        elif bad == 'wrongkind' and not expr_mode:
            if f in ('add', 'subtract', 'multiply', 'divide', 'round', 'since', 'sum', 'min', 'max', 'avg', 'sort', 'top') and 'slot' in params or 'left' in params:
                texts = [s for s, v in (inp or node())['props'].items() if not is_num(v)] or ['/t']
                params['slot' if 'slot' in params else 'left'] = rng.choice(texts)
        view_paths = {name: shapes[v['shape']]['path'] for name, v in views.items() if v['kind'] == 'shape'}
        expect = evaluate(f, params, inp, care, view_trees, view_paths=view_paths)
        if g.coverage is not None:
            entry = f + ':x' if expr_mode else f
            ops = set()
            if expr_mode:
                g.coverage.note_expr(params['expr'])
                try:
                    ops = expr_ops(expr_parse(params['expr']))
                except ExprError:
                    pass
            g.coverage.add(entry, kinds_of(entry, params, inp, care), care, tack.get('pinned', False), bool(views), step + 1, ops)
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
    g = Gen(rng, node_, Coverage())
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
        """The whole answer: a cap-sized shape pages, so the pages are followed and merged by path."""
        page = tool('read', path=path, care=care, limit=500)
        first = page
        while page.get('next'):
            page = tool('read', path=path, care=care, limit=500, next=page['next'])
            merge_page(first, page)
        return first

    def merge_page(into, page):
        index = {}

        def walk(n):
            index[n['path']] = n
            for ch in n.get('children', []):
                walk(ch)
        walk(into)

        def absorb(n):
            for ch in n.get('children', []):
                if ch['path'] in index:
                    absorb(ch)
                else:
                    parent = index.get(n['path'])
                    if parent is not None:
                        parent.setdefault('children', []).append(ch)
                        walk(ch)
        absorb(page)

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
    assert len(stdlib) == 68, sorted(stdlib)      # sixty-seven formulas and ask
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
                'notes': {k[len('/sys/view/note/'):] for k in props if k.startswith('/sys/view/note/')},
                'holes': {k[len('/sys/view/hole/'):] for k in props if k.startswith('/sys/view/hole/')}}

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
        if (start + group) % 500 == 0:
            print('matrix at %d cases: %d of %d fine cells reached' % (start + group, *g.coverage.filled()), flush=True)

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
    # the coverage matrix: what the generator actually drew; at a full run a zero cell for a kind an entry consumes fails
    g.coverage.report(strict=cases >= 500)
    assert not mismatches, [m[:3] for m in mismatches]


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120, int(sys.argv[3]) if len(sys.argv) > 3 else None, int(sys.argv[4]) if len(sys.argv) > 4 else 1000)
