"""The refresh hand: keeps volatile slots current by recipe, with no model.

A recipe is a record at /<node>/user/recipes/<id>, tied to the record whose slot it keeps:

    {record: ref, slot: "stars", url: "...", kind: "json" | "css", select: "...", parse: "number" | "day" | "text",
     every: <seconds>, last_run, last_value, broken}

kind json: select is a dotted path into the response (stargazers_count, data.items.0.name).
kind css:  select is a path into the page from the nearest ancestor with an id, "#id>span[2]" or "html>body>div[3]>a[1]",
           with an optional "@attr" to read an attribute instead of the text. When select is absent the hand derives it
           once: it finds the element whose text (or datetime, title, content attribute) is the record's current value,
           and writes the path back into the recipe. That is the one-time selector.

Each pass: every due recipe is fetched, read, parsed; a value that differs from the record's slot is poked onto the
record with if_case, signed refresh; the recipe gets last_run and last_value. A recipe that cannot read its value is
marked broken, with the reason, and nothing is written to the record: the slot is now a hole for an agent or the web
hand to look at again.

    python3 refresh.py <base> [--node 0x11] [--once]
"""
import importlib.util
import json
import os
import re
import time
import urllib.request
from html.parser import HTMLParser

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, case_of = _hand.World, _hand.Hand, _hand.case_of

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


def fetch(url, timeout=30):
    headers = {'User-Agent': UA, 'Accept': 'application/json, text/html;q=0.9'}
    if 'api.github.com' in url and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace')


# ---- a small DOM: enough to find an element by its text and to walk a path back to it
class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'text', 'parent')
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.text, self.parent = tag, dict(attrs), [], [], parent
    def all_text(self):
        return re.sub(r'\s+', ' ', ''.join(self.text + [k.all_text() for k in self.kids])).strip()


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(); self.root = Node('#root', [], None); self.cur = self.root
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur); self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n
    def handle_endtag(self, tag):
        c = self.cur
        while c is not self.root and c.tag != tag:
            c = c.parent
        if c is not self.root:
            self.cur = c.parent
    def handle_data(self, data):
        self.cur.text.append(data)


def parse_html(markup):
    t = Tree(); t.feed(markup); return t.root


def step(n):
    """tag[i]: this node's position among its parent's children with the same tag, from 1."""
    same = [k for k in n.parent.kids if k.tag == n.tag]
    return f'{n.tag}[{same.index(n) + 1}]'


def path_to(n):
    """From the nearest ancestor with an id (or the root) down to n."""
    parts = []
    while n is not None and n.tag != '#root':
        if n.attrs.get('id'):
            parts.append('#' + n.attrs['id']); break
        parts.append(step(n)); n = n.parent
    return '>'.join(reversed(parts))


def by_id(root, ident):
    stack = [root]
    while stack:
        n = stack.pop()
        if n.attrs.get('id') == ident:
            return n
        stack.extend(n.kids)
    return None


def select(root, sel):
    """Apply a path made by path_to; returns (node, attr or None)."""
    attr = None
    if '@' in sel:
        sel, attr = sel.rsplit('@', 1)
    n = root
    for i, part in enumerate(sel.split('>')):
        if part.startswith('#'):
            n = by_id(root, part[1:])
        else:
            m = re.fullmatch(r'([a-z0-9\-]+)\[(\d+)\]', part)
            if not m or n is None:
                return None, attr
            same = [k for k in n.kids if k.tag == m.group(1)]
            k = int(m.group(2))
            n = same[k - 1] if 0 < k <= len(same) else None
        if n is None:
            return None, attr
    return n, attr


def candidates(value, parse):
    """The strings a page might show for a value: 1234 as 1234 and 1,234 and 1.2k; a day as 2026-10-08."""
    v = str(value).strip()
    out = {v}
    if parse == 'number' and re.fullmatch(r'-?\d+', v):
        n = int(v); out |= {f'{n:,}'}
        if n >= 1000:
            out |= {f'{n / 1000:.1f}k', f'{n // 1000}k'}
    if parse == 'day' and re.fullmatch(r'\d{8}', v):
        out |= {f'{v[:4]}-{v[4:6]}-{v[6:]}'}
    return out


def derive(root, value, parse, slot=''):
    """The one-time selector: the element whose text, or a datetime/title/content attribute, shows the value. When the
    value shows in several places, the one whose ancestry mentions the slot (an id, class, href, label or caption
    containing "star" for stars) wins (duplicates of the same widget tie harmlessly); when nothing mentions the slot and
    the value shows more than once, nothing is derived: a wrong selector is worse than a hole."""
    want = candidates(value, parse)
    stem = re.sub(r'[^a-z]', '', str(slot).lower())
    stem = stem[:-1] if stem.endswith('s') and len(stem) > 4 else stem
    stem = stem[:6]
    found = []
    stack = [root]
    while stack:
        n = stack.pop()
        stack.extend(n.kids)
        for a in ('datetime', 'title', 'content', 'aria-label', 'data-value'):
            av = n.attrs.get(a) or ''
            if any(av == w or (parse == 'day' and av.startswith(w)) for w in want):
                found.append((n, a))
        if not n.kids and n.all_text() in want:
            found.append((n, None))
    def score(item):
        # the element's own caption: its attributes and its parent's attributes and text, and attributes two more up;
        # never the text of a wider ancestor, which mentions every neighbouring widget too
        n, sc, depth = item[0], 0, 0
        while n is not None and n.tag != '#root' and depth < 4:
            blob = ' '.join(str(v) for v in n.attrs.values()).lower() + ' ' + (n.all_text().lower() if depth == 1 else '')
            if stem and stem in blob:
                sc += 4 - depth
            n, depth = n.parent, depth + 1
        return sc
    ranked = sorted(found, key=score, reverse=True)
    if not ranked or score(ranked[0]) == 0:
        return None                     # nothing on the page shows this value as this slot: leave it a hole
    n, a = ranked[0]
    return path_to(n) + ('@' + a if a else '')


def parse_value(raw, parse):
    s = str(raw).strip()
    if parse == 'number':
        m = re.search(r'-?[\d,]+(?:\.\d+)?\s*[kKmM]?', s)
        if not m:
            raise ValueError(f'no number in {s[:40]!r}')
        t = m.group(0).replace(',', '').strip()
        mult = 1000 if t[-1:] in 'kK' else 1000000 if t[-1:] in 'mM' else 1
        t = t.rstrip('kKmM ')
        return int(round(float(t) * mult)) if mult > 1 or '.' not in t else float(t)
    if parse == 'day':
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            return int(m.group(1) + m.group(2) + m.group(3))
        if re.fullmatch(r'\d{8}', s):
            return int(s)
        raise ValueError(f'no day in {s[:40]!r}')
    return s[:300]


def json_select(data, path):
    for part in path.split('.'):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


class RefreshHand(Hand):
    name = 'refresh'
    every = 300.0

    def recipes(self):
        page = self.w.read('/' + self.w.node + '/user/recipes', 'y', limit=500)
        return [(c['path'], {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items() if not k.startswith('/sys')})
                for c in page.get('children', []) if c.get('exists')]

    def apply(self, path, r, now, force=False):
        every = float(r.get('every') or 86400)
        if not force and r.get('last_run') and now - float(r['last_run']) < every:
            return 0
        target = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(r.get('record') or ''))
        slot, url, kind, parse = r.get('slot'), r.get('url'), r.get('kind') or 'css', r.get('parse') or 'text'
        if not (target and slot and url):
            return self.mark(path, 'a recipe needs record, slot and url', now)
        rec = self.w.read(target, 'x')
        if not rec.get('exists'):
            return self.mark(path, f'the record {target} is gone', now)
        current = (rec.get('properties') or {}).get('/' + slot)
        try:
            body = fetch(url)
            sel = r.get('select')
            if kind == 'json':
                raw = json_select(json.loads(body), sel)
            else:
                root = parse_html(body)
                if not sel:
                    if current is None:
                        return self.mark(path, 'no select, and the record has no value to derive it from', now)
                    sel = derive(root, current, parse, slot)
                    if not sel:
                        return self.mark(path, f'could not find {current!r} on the page to derive a selector', now)
                    self.w.tool('write', records=[{'path': path, 'action': 'poke', 'slots': {'select': sel}}], who=self.name)
                n, attr = select(root, sel)
                if n is None:
                    return self.mark(path, f'select {sel} found nothing', now)
                raw = n.attrs.get(attr) if attr else n.all_text()
            value = parse_value(raw, parse)
        except Exception as e:
            return self.mark(path, str(e)[:160], now)
        records = [{'path': path, 'action': 'poke', 'slots': {'last_run': int(now), 'last_value': value, 'broken': False}}]
        changed = str(value) != str(current)
        if changed:
            records.append({'path': target, 'action': 'poke', 'slots': {slot: value}, 'if_case': case_of(rec.get('reference'))})
        self.w.tool('write', records=records, who=self.name)
        if changed:
            self.log(f'refresh {target}.{slot}: {current} -> {value}')
        return 1 if changed else 0

    def mark(self, path, why, now):
        self.w.tool('write', records=[{'path': path, 'action': 'poke', 'slots': {'broken': True, 'reason': why, 'last_run': int(now)}}], who=self.name)
        self.log(f'refresh {path}: broken: {why}')
        return 0

    def tick(self, now):
        return sum(self.apply(p, r, now) for p, r in self.recipes())

    def line(self, line):
        """A recipe written or poked by someone else runs at once, whatever its schedule."""
        root = '/' + self.w.node + '/user/recipes/'
        touched = [t for t in (line.get('touched') or []) if t.startswith(root)]
        if not touched or (line.get('who') or '') == self.name:
            return 0
        now = time.time()
        return sum(self.apply(p, r, now, force=True) for p, r in self.recipes() if p in touched)


if __name__ == '__main__':
    _hand.run(RefreshHand)
