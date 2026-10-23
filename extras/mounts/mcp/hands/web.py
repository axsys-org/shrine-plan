"""The web hand: a digger that fills asks from the web, our own scraper, beside the world.

An ask is a hole with a declared shape: /agent/<name>/asks/<id> {asked, scope, shape}. The main agent (or a person)
writes it when the world cannot answer; it keeps working. This hand wakes on the write, searches within the scope,
fetches pages, indexes each page as a source in the world (reused by every later ask), leaves its research trail as
records, extracts only the ask's shape from what it read, and writes found rows under the ask. The write is the
alert: the agent's lens, which counts the found rows, moves on its next reading. The hand never composes a view and
never writes a fact into /user; the agent decides what the rows mean.

    /agent/<a>/asks/<id>                 {asked, scope, shape}           written by the agent; the hole
    /agent/<a>/asks/<id>/found/<n>       {<shape slots>, source, page}   written by web; typed; a reference to the region
    /user/web/pages/<host>/<slug>        {url, title, fetched, digest}   the index: a page is a source, once
    /user/web/pages/<host>/<slug>/<n>    {heading, text, level}          its regions, by heading
    /agent/web/research/<id>/queries/<n> {q, engine, when, hits}         the trail: what was asked of the web
    /agent/web/research/<id>/visited/<n> {page: ref, why}                and which pages were read for it

    python3 web.py <base> [--node 0x11] [--once] [--model anthropic/claude-sonnet-5.5]
"""
import hashlib
import html
import importlib.util
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, segment_of = _hand.World, _hand.Hand, _hand.segment_of

DEFAULT_MODEL = 'anthropic/claude-sonnet-5.5'
ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'   # the search page answers a browser, not a bot name
MAX_PAGES = 5            # pages read per ask
MAX_REGION = 6000        # chars of a region kept
MAX_PAGE_CHARS = 14000   # chars of a page shown to the extractor


def reference(path, care='x', case=0):
    return {'type': 'reference', 'path': path, 'care': care, 'case': case}


# ---- the web, raw
def get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace'), r.headers.get_content_type()


def search(q, limit=8):
    """DuckDuckGo's html endpoint, no key: [(url, title, snippet)]."""
    body, _ = get('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q))
    out = []
    for m in re.finditer(r'<a([^>]*class="result__a"[^>]*)>(.*?)</a>(?:.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>)?', body, re.S):
        hm = re.search(r'href="([^"]+)"', m.group(1))
        if not hm:
            continue
        href = html.unescape(hm.group(1))
        if href.startswith('//'):
            href = 'https:' + href
        u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('uddg', [href])[0] if 'uddg=' in href else href
        title = re.sub(r'<[^>]+>', '', html.unescape(m.group(2))).strip()
        snippet = re.sub(r'<[^>]+>', '', html.unescape(m.group(3) or '')).strip()
        if u.startswith('http') and 'duckduckgo.com' not in u:
            out.append((u, title, snippet))
        if len(out) >= limit:
            break
    return out


class Text(HTMLParser):
    """HTML to regions: a heading starts a region; everything else is its text."""
    def __init__(self):
        super().__init__(); self.regions = [('', 0, [])]; self.skip = 0; self.title = ''; self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'footer', 'noscript', 'svg'): self.skip += 1
        if tag == 'title': self.in_title = True
        if re.fullmatch(r'h[1-6]', tag) and not self.skip: self.regions.append(('', int(tag[1]), [])); self._heading = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'noscript', 'svg'): self.skip = max(0, self.skip - 1)
        if tag == 'title': self.in_title = False
        if re.fullmatch(r'h[1-6]', tag): self._heading = False
    def handle_data(self, data):
        if self.skip: return
        if self.in_title: self.title += data
        s = data.strip()
        if not s: return
        h, lvl, parts = self.regions[-1]
        if getattr(self, '_heading', False) and not h:
            self.regions[-1] = (s, lvl, parts)
        else:
            parts.append(s)


def page_regions(markup):
    t = Text(); t.feed(markup)
    out = []
    for heading, level, parts in t.regions:
        text = re.sub(r'\s+', ' ', ' '.join(parts)).strip()
        if len(text) > 40:
            out.append({'heading': heading[:160], 'level': level, 'text': text[:MAX_REGION]})
    return t.title.strip()[:200], out


def page_path(node, url):
    u = urllib.parse.urlparse(url)
    host = segment_of(u.netloc.replace('www.', ''))
    slug = segment_of((u.path.strip('/') or 'index')[-60:]) or 'index'
    return f'/{node}/user/web/pages/{host}/{slug}'


# ---- the extractor
def call_model(model, system, user):
    key = os.environ.get('OPENROUTER_API_KEY')
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key} if key else {'Content-Type': 'application/json'}
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': 0, 'max_tokens': 4000, 'response_format': {'type': 'json_object'}}).encode()
    reply = json.load(urllib.request.urlopen(urllib.request.Request(ENDPOINT, body, headers), timeout=180))
    text = reply['choices'][0]['message']['content'] or '{}'
    start, end = text.find('{'), text.rfind('}')
    return json.loads(text[start:end + 1]) if start >= 0 else {}


EXTRACT = """You extract facts from web pages into typed rows. You are given a question, the exact shape of a row (slot names and
types), and the regions of one page, each with an index. Reply with one JSON object: {"rows": [ {<the shape's slots>,
"region": <index of the region the row comes from>, "quote": "<the few words that state it>"} ]}. Rules: only rows the
page actually states; every slot typed as the shape says (numbers as numbers, days as YYYYMMDD, flags true/false, text
only where the shape says text); no row for a guess; an empty list when the page does not answer. Also reply
"queries": [<up to two better search queries if this page suggests where the answer is>] when the page did not answer."""


class WebHand(Hand):
    name = 'web'
    every = 120.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.model = self.setting('model') or DEFAULT_MODEL
        self.done = set()

    # ---- the asks that are open
    def asks(self):
        out = []
        agents = self.w.read('/' + self.w.node + '/agent', 'y', limit=200)
        for a in agents.get('children', []):
            if not a.get('exists') or not re.search(r'/agent/[a-z]\d*$', a['path']):
                continue
            asks = self.w.read(a['path'] + '/asks', 'y', limit=200)
            for q in asks.get('children', []):
                if not q.get('exists'):
                    continue
                props = {k.lstrip('/'): v for k, v in (q.get('properties') or {}).items() if not k.startswith('/sys')}
                found = self.w.read(q['path'] + '/found', 'y', limit=10)
                taken = self.w.read(q['path'] + '/taken', 'x')
                if props.get('asked') and not found.get('children') and not taken.get('exists') and q['path'] not in self.done:
                    out.append((q['path'], props))
        return out

    # ---- one ask, end to end
    def dig(self, ask, props):
        node = self.w.node
        aid = ask.rsplit('/', 1)[1]
        trail = f'/{node}/agent/web/research/{aid}'
        # the trail's root first, in the same event as the claim: a culled trail would otherwise refuse its children
        self.w.tool('write', records=[{'path': ask + '/taken', 'slots': {'by': 'web', 'when': int(time.time())}},
                                      {'path': trail, 'slots': {'ask': reference(ask), 'started': int(time.time())}}], who=self.name)
        asked, scope, shape = props.get('asked', ''), props.get('scope', ''), props.get('shape', '')
        many = str(props.get('many') or '').lower() == 'true'          # a collection: keep reading pages for more items
        queries, seen, rows, nq, nv = [asked + (' ' + scope if scope else '')], set(), [], 0, 0
        pages_read = 0
        while queries and pages_read < MAX_PAGES:
            q = queries.pop(0)
            try:
                hits = search(q)
            except Exception as e:
                self.log(f'web {aid}: search failed: {e}'); hits = []
            nq += 1
            self.w.tool('write', records=[{'path': f'{trail}/queries/q{nq}', 'slots': {'q': q, 'engine': 'duckduckgo', 'when': int(time.time()), 'hits': len(hits)}}], who=self.name)
            for url, title, snippet in hits:
                if pages_read >= MAX_PAGES or url in seen:
                    continue
                seen.add(url)
                try:
                    markup, ctype = get(url)
                except Exception as e:
                    continue
                if 'html' not in (ctype or ''):
                    continue
                pages_read += 1
                ptitle, regions = page_regions(markup)
                digest = hashlib.sha256(markup.encode()).hexdigest()[:16]
                ppath = page_path(node, url)
                have = self.w.read(ppath, 'x').get('properties') or {}
                if have.get('/digest') != digest:                       # the index: a page once, its regions beneath
                    recs = [{'path': ppath, 'slots': {'url': url, 'title': ptitle or title, 'fetched': int(time.strftime('%Y%m%d')), 'digest': digest, 'regions': len(regions)}}]
                    recs += [{'path': f'{ppath}/r{i}', 'slots': {'heading': r['heading'], 'level': r['level'], 'text': r['text']}} for i, r in enumerate(regions[:60], 1)]
                    self.w.tool('write', records=recs, who=self.name)
                nv += 1
                self.w.tool('write', records=[{'path': f'{trail}/visited/v{nv}', 'slots': {'page': reference(ppath), 'why': q[:120]}}], who=self.name)
                # extraction, to the ask's shape only
                shown = '\n'.join(f'[{i}] {r["heading"]}: {r["text"]}' for i, r in enumerate(regions[:60], 1))[:MAX_PAGE_CHARS]
                try:
                    got = call_model(self.model, EXTRACT, f'QUESTION: {asked}\nSHAPE: {shape}\nPAGE: {url}\nREGIONS:\n{shown}')
                except Exception as e:
                    self.log(f'web {aid}: extractor failed: {str(e)[:120]}'); got = {}
                for r in got.get('rows') or []:
                    idx = r.pop('region', None); quote = r.pop('quote', '')
                    row = {}
                    for k, v in r.items():                      # a slot is text, a number or a flag; nothing else is admitted
                        if not k or k.startswith('/') or v is None or v == '':
                            continue
                        row[segment_of(k)] = v if isinstance(v, (int, float, bool)) else (json.dumps(v) if isinstance(v, (list, dict)) else str(v)[:300])
                    if not row:
                        continue
                    row['page'] = reference(ppath)
                    if isinstance(idx, int) and 1 <= idx <= len(regions):
                        row['source'] = reference(f'{ppath}/r{idx}')
                    if quote:
                        row['quote'] = str(quote)[:160]
                    rows.append(row)
                for extra in (got.get('queries') or [])[:2]:
                    if extra not in queries and len(queries) < 4:
                        queries.append(extra)
                if rows and not many:
                    break
            if rows and not many:
                break
        if rows:
            cap = 80 if many else 12
            recs = [{'path': f'{ask}/found/f{i}', 'slots': row} for i, row in enumerate(rows[:cap], 1)]
            for start in range(0, len(recs), 40):
                self.w.tool('write', records=recs[start:start + 40], who=self.name)
        self.log(f'web {aid}: {nq} queries, {pages_read} pages, {len(rows)} rows')
        self.done.add(ask)
        return len(rows)

    def dig_all(self):
        """Every open ask, three at a time; a slow one does not hold up the others."""
        open_asks = self.asks()
        if not open_asks:
            return 0
        with ThreadPoolExecutor(max_workers=3) as pool:
            return sum(pool.map(lambda ap: self._safe_dig(*ap), open_asks))

    def _safe_dig(self, ask, props):
        try:
            return self.dig(ask, props)
        except Exception as e:
            self.log(f'web {ask}: {str(e)[:160]}')
            return 0

    def line(self, line):
        touched = line.get('touched') or []
        if not any('/asks/' in t for t in touched):
            return 0
        return self.dig_all()

    def tick(self, now):
        return self.dig_all()


if __name__ == '__main__':
    _hand.run(WebHand, settings=('model',))
