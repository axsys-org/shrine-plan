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
import queue
import threading
import urllib.error
import urllib.request
from html.parser import HTMLParser

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, segment_of = _hand.World, _hand.Hand, _hand.segment_of

DEFAULT_MODEL = 'anthropic/claude-sonnet-5.5'
ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'   # the search page answers a browser, not a bot name
MAX_PAGES = 5            # pages read per ask
MAX_PAGES_MANY = 30      # pages read for a collection whose site was mapped
MAX_REGION = 6000        # chars of a region kept
MAX_PAGE_CHARS = 14000   # chars of a page shown to the extractor


def reference(path, care='x', case=0):
    return {'type': 'reference', 'path': path, 'care': care, 'case': case}


# ---- the web, raw
def get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace'), r.headers.get_content_type()


STOP = set('''a an the and or but of for on in at to from by with as into than then also about over under is are was were be
been being has have had do does did done can could would should will may might must not no nor so if any all some there their they
them it its this that these those what which who whom whose when where why how exactly please cite original reports report
launched called named known announced according latest recent current new news details detail''' .split())


def keywords(asked, limit=7):
    """A search query from a question: names, numbers and amounts kept, question words dropped. Bing reads a sentence as
    its words; "Has a company called Warhound…" found pages about has and have."""
    names, rest, seen = [], [], set()
    for w in re.findall(r'\$?[\w][\w.\-]*', asked):
        key = w.lower().strip('.')
        if not key or key in STOP or key in seen or (len(key) < 3 and not key[0].isdigit() and not w.startswith('$')):
            continue
        seen.add(key)
        (names if (w[0].isupper() or w[0] == '$' or any(ch.isdigit() for ch in w)) else rest).append(w.strip('.'))
    return ' '.join((names + rest)[:limit]) or asked[:120]      # the names and amounts lead: an engine weighs the first words most


# ---- search: several engines, each with its own pace, each rested when it starts refusing; the first that answers wins
class Refused(Exception):
    """An engine answered with a challenge or a rate limit: rest it, try the next."""


class NoEngine(Exception):
    """No engine answered at all: the search failed; it is not that the web had nothing."""


class Engine:
    def __init__(self, name, fn, gap):
        self.name, self.fn, self.gap, self.last, self.rest_until = name, fn, gap, 0.0, 0.0


def _clean(t):
    t = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t or '', flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html.unescape(t))).strip()


def _bing(q, limit):
    body, _ = get('https://www.bing.com/search?format=rss&count=10&q=' + urllib.parse.quote(q))
    out = []
    for item in re.findall(r'<item>(.*?)</item>', body, re.S):
        l = re.search(r'<link>(.*?)</link>', item, re.S)
        u = _clean(l.group(1)) if l else ''
        if u.startswith('http') and 'bing.com' not in u:
            t = re.search(r'<title>(.*?)</title>', item, re.S); d = re.search(r'<description>(.*?)</description>', item, re.S)
            out.append((u, _clean(t.group(1) if t else ''), _clean(d.group(1) if d else '')[:300]))
    return out[:limit]


def _brave(q, limit):
    body, _ = get('https://search.brave.com/search?source=web&q=' + urllib.parse.quote(q))
    if len(body) < 20000 and ('captcha' in body.lower() or 'challenge' in body.lower()):
        raise Refused('brave challenge')
    out = []
    for seg in re.split(r'<div class="snippet[^"]*"', body)[1:]:
        if 'data-type="web"' not in seg[:400]:
            continue
        hm = re.search(r'href="(https?://[^"]+)"', seg)
        if not hm or 'brave.com' in hm.group(1):
            continue
        u = html.unescape(hm.group(1)).split('#', 1)[0]
        tm = re.search(r'class="title[^"]*"[^>]*>(.*?)</', seg, re.S)
        text = _clean(seg[seg.find('>', hm.end()):])
        out.append((u, _clean(tm.group(1)) if tm else text[:120], text[:300]))
    return out[:limit]


def _ddg(q, limit):
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
        if u.startswith('http') and 'duckduckgo.com' not in u:
            out.append((u, _clean(m.group(2)), _clean(m.group(3) or '')))
        if len(out) >= limit:
            break
    if not out and ('anomaly' in body or 'challenge' in body):
        raise Refused('duckduckgo challenge')
    return out


def _wikipedia(q, limit):
    """The encyclopedia's own search: an entity's article first, with no bot wall in the way."""
    body, _ = get('https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=' + str(min(limit, 5)) + '&srsearch=' + urllib.parse.quote(q))
    hits = json.loads(body).get('query', {}).get('search', [])
    return [('https://en.wikipedia.org/wiki/' + urllib.parse.quote(h['title'].replace(' ', '_')), h['title'], _clean(h.get('snippet', ''))) for h in hits]


FIRECRAWL = 'https://api.firecrawl.dev/v1'


def firecrawl_key():
    return os.environ.get('FIRECRAWL_API_KEY') or ''


def firecrawl(path, body, timeout=60):
    req = urllib.request.Request(FIRECRAWL + path, json.dumps(body).encode(),
                                 {'Authorization': 'Bearer ' + firecrawl_key(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _firecrawl(q, limit):
    """Firecrawl's search: an index with no bot wall, results with a description; the pages are fetched by us."""
    if not firecrawl_key():
        raise Refused('no key')
    d = firecrawl('/search', {'query': q, 'limit': min(limit, 8)})
    if not d.get('success'):
        raise Refused(str(d.get('error'))[:80])
    return [(r.get('url', ''), _clean(r.get('title') or ''), _clean(r.get('description') or '')[:300]) for r in d.get('data') or [] if str(r.get('url', '')).startswith('http')]


def fetch_page(url):
    """A page's html: our own fetch first; when a site refuses us or hands back a shell for scripts to fill, Firecrawl
    renders it and hands back the raw html, which our extractor then reads the same way."""
    try:
        markup, ctype = get(url)
        if 'html' in (ctype or '') and len(re.sub(r'<[^>]+>', ' ', markup)) > 2000:
            return markup, ctype
        shell = markup if 'html' in (ctype or '') else ''
    except Exception:
        shell = ''
    if not firecrawl_key():
        if shell:
            return shell, 'text/html'
        raise RuntimeError('fetch failed and no firecrawl key')
    d = firecrawl('/scrape', {'url': url, 'formats': ['rawHtml'], 'onlyMainContent': False})
    html_ = (d.get('data') or {}).get('rawHtml') or ''
    if not html_:
        raise RuntimeError('firecrawl scrape gave nothing: ' + str(d.get('error'))[:80])
    return html_, 'text/html'


def rank_links(links, q, cap=40):
    """The content pages of a mapped site first: deeper paths, and paths that carry a word of the question."""
    words = {w.lower() for w in re.findall(r'[A-Za-z]{4,}', q)} - STOP
    seen, out = set(), []
    for u in links:
        u = str(u).split('#', 1)[0]
        if not u.startswith('http') or u in seen or re.search(r'\.(xml|json|css|js|png|jpe?g|gif|svg|ico|woff2?)(\?|$)', u, re.I):
            continue
        seen.add(u)
        path = urllib.parse.urlparse(u).path.strip('/')
        depth = len([p for p in path.split('/') if p])
        out.append((depth + (2 if any(w in u.lower() for w in words) else 0), u))
    return [u for sc, u in sorted(out, key=lambda x: -x[0])[:cap] if sc > 0]


ENGINES = [Engine('firecrawl', _firecrawl, 1.0), Engine('bing', _bing, 2.0), Engine('brave', _brave, 3.0), Engine('duckduckgo', _ddg, 6.0)]
WIKIPEDIA = Engine('wikipedia', _wikipedia, 0.5)
REST = 900.0
THROTTLE = threading.Lock()
engine_log = print


def run_engine(e, q, limit):
    """One engine, at its pace: None when it is resting or failed to answer, else its hits (possibly none)."""
    with THROTTLE:
        now = time.time()
        if now < e.rest_until:
            return None
        wait = e.last + e.gap - now
        if wait > 0:
            time.sleep(wait)
        e.last = time.time()
    try:
        return e.fn(q, limit)
    except Refused as r:
        e.rest_until = time.time() + REST
        engine_log(f'search: {e.name} refused ({r}); resting it {int(REST // 60)} min')
    except urllib.error.HTTPError as r:
        e.rest_until = time.time() + (REST if r.code in (202, 403, 429, 503) else 120)
        engine_log(f'search: {e.name} http {r.code}; resting it')
    except Exception as r:
        e.rest_until = time.time() + 120
        engine_log(f'search: {e.name} failed ({str(r)[:80]}); resting it 2 min')
    return None


def distinctive(q):
    """The terms a result must mention to be about the question: names (capitalised), numbers and amounts."""
    out = []
    for w in re.findall(r'\$?[\w][\w.\-]*', q):
        key = w.strip('.').lower()
        if key in STOP or len(key) < 3:
            continue
        if w[0].isupper() or w[0] == '$' or any(ch.isdigit() for ch in w):
            out.append(key.lstrip('$'))
    return out


def mentions(hit, terms):
    blob = ' '.join(hit).lower()
    return not terms or any(t in blob for t in terms)


def search(q, limit=8, entity=None, skip=()):
    """[(url, title, snippet)] and the engine that answered. An entity's own article comes first when one exists;
    then the first general engine that answers, in order. No engine answering at all raises NoEngine."""
    out, seen, used = [], set(), []
    def add(hits):
        for u, t, sn in hits:
            if u not in seen:
                seen.add(u); out.append((u, t, sn))
    if entity:
        hits = run_engine(WIKIPEDIA, entity, 3)
        if hits:
            add(hits); used.append('wikipedia')
    for e in ENGINES:
        if e.name in skip or (e.name == 'firecrawl' and not firecrawl_key()):
            continue
        hits = run_engine(e, q, limit)
        if hits is None:
            continue
        add(hits); used.append(e.name)
        break
    if not used:
        raise NoEngine('no search engine answered')
    return out[:limit], '+'.join(used)


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


try:
    import trafilatura                      # main-content extraction, the same job Firecrawl's onlyMainContent does
except Exception:
    trafilatura = None


def page_regions(markup, url=''):
    """A page as its main content only (navigation, footers, cookie banners and sidebars gone), split into regions at
    its headings. trafilatura when available, else the plain parser."""
    if trafilatura is not None:
        try:
            md = trafilatura.extract(markup, url=url or None, output_format='markdown', include_tables=True, include_links=False,
                                     include_images=False, include_comments=False, include_formatting=True) or ''
            meta = trafilatura.extract_metadata(markup)
            title = (meta.title if meta and meta.title else '')[:200]
            # regions: chunks of the main content of about a paragraph or two, each under the last heading seen, so the
            # ranking can hand the extractor only the few that matter and a locator names a small piece of the page
            regions, heading, level, buf, size = [], '', 0, [], 0
            def flush():
                text = re.sub(r'\s+', ' ', ' '.join(buf)).strip()
                if len(text) > 40:
                    regions.append({'heading': heading[:160], 'level': level, 'text': text[:MAX_REGION]})
            for line in md.splitlines():
                m = re.match(r'^(#{1,6})\s+(.*)$', line)
                if m:
                    flush(); heading, level, buf, size = m.group(2).strip(), len(m.group(1)), [], 0
                    continue
                if not line.strip() and size > 900:
                    flush(); buf, size = [], 0
                    continue
                buf.append(line); size += len(line)
                if size > 1600:
                    flush(); buf, size = [], 0
            flush()
            if sum(len(r['text']) for r in regions) >= 400:      # a listing or index page keeps little main content: use all of it
                return title, regions
        except Exception:
            pass
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


def relevant(regions, wanted, budget=3000):
    """Only the regions worth the extractor's tokens: ranked by how many of the ask's words (and the shape's slot names)
    they contain, kept in page order, within a character budget. The index keeps every region; the model sees few."""
    terms = {w for w in re.findall(r'[a-z0-9]{3,}', wanted.lower()) if w not in {'the', 'and', 'what', 'who', 'where', 'when', 'which', 'text', 'number', 'yyyy', 'yyyymmdd', 'true', 'false'}}
    scored = []
    for i, r in enumerate(regions[:60], 1):
        blob = (r['heading'] + ' ' + r['text']).lower()
        scored.append((sum(blob.count(t) for t in terms) + (2 if i <= 2 else 0), i, r))
    keep, used = [], 0
    for sc, i, r in sorted(scored, key=lambda x: -x[0]):
        line = f'[{i}] {r["heading"]}: {r["text"]}'
        if used + len(line) > budget and keep:
            continue
        keep.append((i, line)); used += len(line)
        if used > budget:
            break
    return '\n'.join(line for i, line in sorted(keep))


# ---- the extractor
def call_model(model, system, user):
    key = os.environ.get('OPENROUTER_API_KEY')
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key} if key else {'Content-Type': 'application/json'}
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': 0, 'max_tokens': 4000, 'response_format': {'type': 'json_object'}}).encode()
    reply = json.load(urllib.request.urlopen(urllib.request.Request(ENDPOINT, body, headers), timeout=180))
    text = reply['choices'][0]['message']['content'] or '{}'
    start = text.find('{')
    if start < 0:
        return {}
    obj, _ = json.JSONDecoder().raw_decode(text[start:])     # the first whole object; anything after it is ignored
    return obj if isinstance(obj, dict) else {}


EXTRACT = """You extract facts from web pages into typed rows. You are given a question, the exact shape of a row (slot names and
types), and the regions of one page, each with an index. Reply with one JSON object: {"rows": [ {<the shape's slots>,
"region": <index of the region the row comes from>, "quote": "<the few words that state it>"} ]}. Rules: only rows the
page actually states; every slot typed as the shape says (numbers as numbers, days as YYYYMMDD, flags true/false, text
only where the shape says text); no row for a guess; an empty list when the page does not answer. Also reply
"queries": [<up to two better search queries if this page suggests where the answer is>] when the page did not answer."""


WORKERS = 3


class WebHand(Hand):
    """One queue for every ask in the world, highest priority first: a chat's ask (someone is waiting) before the
    crawler's (curiosity). Three workers pull from it; the loop that follows the stream only enqueues, so a new chat
    ask never waits behind a batch."""
    name = 'web'
    every = 60.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        global engine_log
        engine_log = log
        self.model = self.setting('model') or DEFAULT_MODEL
        self.done = set()
        self.queued = set()
        self.pq = queue.PriorityQueue()
        self.lock = threading.Lock()
        for _ in range(WORKERS):
            threading.Thread(target=self.worker, daemon=True).start()

    def quiet(self, item):
        """An ask written by a hand (the crawler) still wakes me; my own status writes and fills never do."""
        touched = item.get('touched') or []
        if (item.get('who') or '') != self.name and any('/asks/' in t and '/found/' not in t and not t.endswith('/status') and not t.endswith('/taken') for t in touched):
            return False
        return super().quiet(item)

    # ---- the asks that are open, with their priority
    def asks(self):
        out = []
        agents = self.w.read('/' + self.w.node + '/agent', 'y', limit=200)
        for a in agents.get('children', []):
            name = a['path'].rsplit('/', 1)[1]
            if not a.get('exists') or not (re.fullmatch(r'[a-z]\d*', name) or name == 'crawl'):
                continue
            asks = self.w.read(a['path'] + '/asks', 'y', limit=500)
            for q in asks.get('children', []):
                if not q.get('exists'):
                    continue
                props = {k.lstrip('/'): v for k, v in (q.get('properties') or {}).items() if not k.startswith('/sys')}
                if not props.get('asked') or q['path'] in self.done or q['path'] in self.queued:
                    continue
                kids = {c['path'].rsplit('/', 1)[1] for c in (self.w.read(q['path'], 'y', limit=20).get('children') or []) if c.get('exists') or c.get('children')}
                if 'found' in kids or 'taken' in kids:
                    continue
                prio = 0 if name != 'crawl' else 1 + int(float(props.get('priority') or 1))
                out.append((prio, q['path'], props))
        return out

    def enqueue(self):
        n = 0
        for prio, path, props in self.asks():
            with self.lock:
                if path in self.queued:
                    continue
                self.queued.add(path)
            self.pq.put((prio, time.time(), path, props))
            self.status(path, 'queued', priority=prio)
            n += 1
        return n

    def worker(self):
        while True:
            prio, _, path, props = self.pq.get()
            try:
                self.dig(path, props)
            except Exception as e:
                self.log(f'web {path}: {str(e)[:160]}')
                self.status(path, 'failed', reason=str(e)[:160])
            finally:
                self.pq.task_done()

    def status(self, ask, state, **more):
        """The ask's live status, a child record the queue page and the chat read: state, and what it is doing."""
        try:
            self.w.tool('write', records=[{'path': ask + '/status', 'slots': dict({'state': state, 'updated': int(time.time())}, **{k: v for k, v in more.items() if v is not None})}], who=self.name)
        except Exception:
            pass

    # ---- one ask, end to end
    def dig(self, ask, props):
        node = self.w.node
        aid = ask.rsplit('/', 1)[1]
        owner = ask.split('/agent/', 1)[1].split('/', 1)[0]
        trail = f'/{node}/agent/web/research/{owner}_{aid}'
        # the trail's root first, in the same event as the claim: a culled trail would otherwise refuse its children
        self.w.tool('write', records=[{'path': ask + '/taken', 'slots': {'by': 'web', 'when': int(time.time())}},
                                      {'path': trail, 'slots': {'ask': reference(ask), 'started': int(time.time())}}], who=self.name)
        asked, scope, shape = props.get('asked', ''), props.get('scope', ''), props.get('shape', '')
        many = str(props.get('many') or '').lower() == 'true'          # a collection: keep reading pages for more items
        if props.get('query'):
            first = str(props['query'])[:160]                                          # the asker chose the words
        elif props.get('entity'):
            first = (str(props['entity']) + ' ' + str(props.get('kind') or '')).strip()
        else:
            first = keywords(asked + ' ' + scope)
        queries, seen, rows, nq, nv = [first], set(), [], 0, 0     # an entity is searched by its name, not by the question
        pages_read, failed = 0, ''
        cap, site, queued = (MAX_PAGES_MANY if many else MAX_PAGES), str(props.get('site') or ''), []
        if many and not site and props.get('about'):
            ap = self.w.read(re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props['about'])), 'x').get('properties') or {}
            site = str(ap.get('/website') or ap.get('/url') or ap.get('/site') or '')
        if many and site and firecrawl_key():
            # a collection with a known site: every url of the site in one call, its content pages read in turn
            self.status(ask, 'mapping', step=site[:160], pages=0, queries=0, rows=0)
            try:
                links = firecrawl('/map', {'url': site if '://' in site else 'https://' + site, 'limit': 500}).get('links') or []
            except Exception as e:
                self.log(f'web {owner}/{aid}: map of {site} failed: {str(e)[:80]}'); links = []
            queued = [(u, '', '') for u in rank_links(links, first + ' ' + shape)]
            if queued:
                self.log(f'web {owner}/{aid}: mapped {site}: {len(links)} urls, {len(queued)} to read')
        while (queries or queued) and pages_read < cap:
            if queued:
                q, hits, engine, terms, attempts, queued = 'map ' + site, queued, 'firecrawl-map', [], 0, []
            else:
                q = queries.pop(0)
                self.status(ask, 'searching', step=q[:160], pages=pages_read, queries=nq + 1, rows=len(rows))
                terms, tried, hits, engine, attempts = distinctive(q), set(), [], 'none', 2
            for attempt in range(attempts):          # an engine whose hits mention none of the names is answering a different question
                try:
                    got, engine = search(q, entity=props.get('entity') if nq == 0 else None, skip=tried)
                except NoEngine as e:
                    failed = str(e) if not tried else ''; break
                except Exception as e:
                    self.log(f'web {owner}/{aid}: search failed: {str(e)[:120]}'); break
                hits = [h for h in got if mentions(h, terms)]
                if hits or not got:
                    break
                self.log(f'web {owner}/{aid}: {engine} had {len(got)} hits, none mentioning {", ".join(terms[:4])}; trying another engine')
                tried.update(engine.split('+'))
            if failed:
                self.log(f'web {owner}/{aid}: {failed}'); break
            nq += 1
            self.w.tool('write', records=[{'path': f'{trail}/queries/q{nq}', 'slots': {'q': q, 'engine': engine, 'when': int(time.time()), 'hits': len(hits), 'terms': ' '.join(terms[:6])}}], who=self.name)
            for url, title, snippet in hits:
                if pages_read >= cap or url in seen:
                    continue
                seen.add(url)
                try:
                    markup, ctype = fetch_page(url)
                except Exception as e:
                    self.log(f'web {owner}/{aid}: could not read {url[:60]}: {str(e)[:60]}'); continue
                if 'html' not in (ctype or ''):
                    continue
                pages_read += 1
                self.status(ask, 'reading', step=url[:200], pages=pages_read, queries=nq, rows=len(rows))
                ptitle, regions = page_regions(markup, url)
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
                shown = relevant(regions, asked + ' ' + shape)
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
        why = failed or (None if rows or pages_read else 'no result mentions ' + ', '.join(distinctive(first)[:4]))
        if not rows and props.get('about') and owner != 'crawl':
            # the question stays attached to its thing: a hole the crawl hand looks at again on its schedule
            about = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props['about']))
            slot = segment_of(str(props.get('slot') or aid))
            kind = props.get('kind') if props.get('kind') in ('watch', 'until', 'unknown') else 'unknown'
            every = int(float(props.get('every') or 86400))
            hole = {'slot': slot, 'asked': asked, 'shape': shape, 'kind': kind, 'every': every, 'made': int(time.time()), 'ask': reference(ask),
                    'next': int(time.time() + (1800 if failed else every if kind != 'unknown' else 2 * 86400)), 'tries': 0 if failed else 1,
                    'reason': failed or why or 'nothing found'}
            if props.get('query'):
                hole['query'] = str(props['query'])
            if props.get('due'):
                hole['due'] = int(float(props['due']))
            try:
                self.w.tool('write', records=[{'path': about + '/holes', 'slots': {}}, {'path': f'{about}/holes/{slot}', 'slots': hole}], who=self.name)
                self.log(f'web {owner}/{aid}: now a hole at {about.split("/user/")[-1]}/holes/{slot} ({kind})')
            except Exception as e:
                self.log(f'web {owner}/{aid}: could not write the hole: {str(e)[:80]}')
        self.status(ask, 'done' if rows else ('failed' if failed else 'empty'), pages=pages_read, queries=nq, rows=len(rows), reason=why)
        self.log(f'web {owner}/{aid}: {nq} queries, {pages_read} pages, {len(rows)} rows')
        self.done.add(ask)
        return len(rows)

    def line(self, line):
        touched = line.get('touched') or []
        if not any('/asks/' in t for t in touched):
            return 0
        return self.enqueue()

    def tick(self, now):
        return self.enqueue()

    def once(self, now=None):
        done = super().once(now)
        self.pq.join()                  # --once: the queue drains before the process leaves
        return done


if __name__ == '__main__':
    _hand.run(WebHand, settings=('model',))
