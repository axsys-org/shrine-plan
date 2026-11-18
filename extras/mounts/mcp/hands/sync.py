"""The sync hand: a site or a collection of pages brought into a world, and brought again later, keeping only what changed.

A sync is a record the owner of a world writes; everything it does is records beside it, so any hand can resume it and
anyone can inspect it:

    <world>/user/syncs/<name>                   {urls: "<one per line>"} or {site, search?, limit?}; resync: <n> asks again;
                                                fresh: true reads past Firecrawl's cache
    <world>/user/syncs/<name>/runs/r<n>         {state: running|done, cursor, of, urls, new, changed, unchanged, failed}
    <world>/user/syncs/<name>/runs/r<n>/pages/p<k>  {url, page, outcome: new|changed|unchanged|failed, added, removed}
    <world>/user/web/pages/<host>/<slug>        {url, title, fetched, digest, via}: the page, a source, once
    <world>/user/web/pages/<host>/<slug>/h<sha> {heading, level, text, n}: its regions, named by their content

Regions are named by what they say, so a page fetched again writes only the regions that are new and culls the ones
that are gone; an unchanged region keeps its record and its digested mark, and only new text waits for the digest hand.
Arrival is kept apart from interpretation: this hand stores what the page says; the digest hand decides what it means.
A run writes its cursor after every page, so a run stopped halfway resumes at the next page and writes nothing twice.
Pages come through Firecrawl when a key is set (FIRECRAWL_API_KEY), else a plain fetch.

    python3 sync.py <base> [--node 0x11]
"""
import hashlib
import importlib.util
import urllib.error
import urllib.request
import os
import re
import threading
import time
import urllib.parse

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('web_hand', os.path.join(_here, 'web.py'))
_web = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_web)
_hand = _web._hand
Hand, segment_of, reference = _hand.Hand, _hand.segment_of, _web.reference

EXTRACTOR = 'sync-1'


def props_of(record):
    return {k.lstrip('/'): v for k, v in (record.get('properties') or {}).items() if not k.startswith('/sys')}


class SyncHand(Hand):
    name = 'sync'
    every = 10.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.node = '/' + world.node
        self.busy = threading.Lock()

    def quiet(self, item):
        return True                 # it works from the sync records on its tick, not from the stream

    def mark_seen(self):
        pass

    def roots(self):
        """This world's /user. Peer worlds kept under it were listed by the links index; none is listed now."""
        return [self.node + '/user']

    def due(self):
        """Every sync with a run to do: a run left running (resumed where it stopped), or none yet, or a resync asked."""
        work = []
        for root in self.roots():
            for s in self.w.read(root + '/syncs', 'y', limit=200).get('children') or []:
                if not s.get('exists', True):
                    continue
                sp = props_of(self.w.read(s['path'], 'x'))
                if not (sp.get('urls') or sp.get('site')):
                    continue
                runs = [r for r in (self.w.read(s['path'] + '/runs', 'y', limit=500).get('children') or []) if re.search(r'/r\d+$', r['path'])]
                last = max(runs, key=lambda r: int(r['path'].rsplit('/r', 1)[1]), default=None)
                n = int(last['path'].rsplit('/r', 1)[1]) if last else 0
                lp = props_of(self.w.read(last['path'], 'x')) if last else {}
                if last and lp.get('state') == 'running':
                    work.append((root, s['path'], sp, last['path'], True))
                elif not last or int(float(sp.get('resync') or 1)) > n:
                    work.append((root, s['path'], sp, f"{s['path']}/runs/r{n + 1}", False))
        return work

    def tick(self, now):
        if self.busy.locked():
            return 0
        work = self.due()
        if work:
            threading.Thread(target=self.run_all, args=(work,), daemon=True).start()
        return 0

    def run_all(self, work):
        with self.busy:
            for item in work:
                try:
                    self.run_sync(*item)
                except Exception as e:
                    self.log(f'sync {item[1]}: {str(e)[:160]}')

    def urls(self, sp):
        if sp.get('urls'):
            return [u.strip() for u in str(sp['urls']).split() if u.strip().startswith('http')]
        site = str(sp['site']); site = site if '://' in site else 'https://' + site
        body = {'url': site, 'limit': int(float(sp.get('limit') or 20))}
        if sp.get('search'):
            body['search'] = str(sp['search'])[:100]
        links = _web.firecrawl('/map', body).get('links') or []
        links = [l.get('url') if isinstance(l, dict) else l for l in links]
        return [l for l in links if str(l).startswith('http')][:body['limit']]

    def run_sync(self, root, sync, sp, run, resume):
        if resume:
            rp = props_of(self.w.read(run, 'x'))
            urls = [u for u in str(rp.get('urls') or '').split() if u]
            cursor = int(float(rp.get('cursor') or 0))
            counts = {k: int(float(rp.get(k) or 0)) for k in ('new', 'changed', 'unchanged', 'failed')}
            self.log(f'sync {sync}: resuming {run} at page {cursor + 1} of {len(urls)}')
        else:
            urls = self.urls(sp)
            cursor, counts = 0, {'new': 0, 'changed': 0, 'unchanged': 0, 'failed': 0}
            self.write([{'path': run, 'slots': {'state': 'running', 'started': int(time.time()), 'cursor': 0, 'of': len(urls), 'urls': '\n'.join(urls), **counts}}])
            self.log(f'sync {sync}: {run} over {len(urls)} pages')
        for k in range(cursor, len(urls)):
            url = urls[k]
            try:
                outcome, page, added, removed = self.sync_page(root, url, fresh=str(sp.get('fresh') or '').lower() in ('true', '1', 'yes'))
                rec = {'url': url, 'page': reference(page), 'outcome': outcome, 'added': added, 'removed': removed}
            except Exception as e:
                outcome, rec = 'failed', {'url': url, 'outcome': 'failed', 'error': str(e)[:200]}
            counts[outcome] += 1
            # the page's outcome and the run's cursor in one event: a run stopped here resumes at the next page
            self.write([{'path': f'{run}/pages/p{k + 1}', 'slots': rec},
                        {'path': run, 'action': 'poke', 'slots': {'cursor': k + 1, **counts}}])
        self.write([{'path': run, 'action': 'poke', 'slots': {'state': 'done', 'finished': int(time.time()), **counts}}])
        self.log(f'sync {sync}: {run} done: ' + ', '.join(f'{v} {k}' for k, v in counts.items()))

    def fetch(self, url, fresh=False):
        if _web.firecrawl_key():
            for wait in (0, 20, 45, 90):                # Firecrawl's rate limit answers 429: wait and ask again
                time.sleep(wait)
                try:
                    body = {'url': url, 'formats': ['rawHtml'], 'onlyMainContent': False, **({'maxAge': 0} if fresh else {})}   # fresh: past Firecrawl's cache
                    d = _web.firecrawl('/scrape', body, timeout=90)
                    break
                except urllib.error.HTTPError as e:
                    if e.code != 429 or wait == 90:
                        raise
            markup = (d.get('data') or {}).get('rawHtml') or ''
            if markup:
                return markup, 'firecrawl'
        markup, _ = _web.fetch_page(url)
        return markup, 'fetch'

    def sync_page(self, root, url, fresh=False):
        """One page into the world: its regions named by content; only new regions written, gone ones culled."""
        markup, via = self.fetch(url, fresh)
        title, regions = _web.page_regions(markup, url)
        if not regions:
            raise RuntimeError('no readable content')
        u = urllib.parse.urlparse(url)
        page = f"{root}/web/pages/{segment_of(u.netloc.replace('www.', ''))}/{segment_of((u.path.strip('/') or 'index')[-60:]) or 'index'}"
        had = self.w.read(page, 'x').get('exists')
        have = {}
        for c in self.w.read(page, 'y', limit=500).get('children') or []:
            seg = c['path'].rsplit('/', 1)[1]
            if c.get('exists', True) and re.fullmatch(r'h[0-9a-f]{10}', seg):
                have[seg] = c['path']
        now_named, recs = {}, []
        for i, r in enumerate(regions[:80], 1):
            seg = 'h' + hashlib.sha1((r['heading'] + '\n' + r['text']).encode()).hexdigest()[:10]
            now_named.setdefault(seg, (i, r))
        added = [s for s in now_named if s not in have]
        removed = [s for s in have if s not in now_named]
        digest = hashlib.sha256(''.join(sorted(now_named)).encode()).hexdigest()[:16]
        if not had or added or removed:
            recs.append({'path': page, 'slots': {'url': url, 'title': title[:200], 'fetched': int(time.strftime('%Y%m%d')), 'digest': digest,
                                                 'regions': len(now_named), 'extractor': EXTRACTOR, 'via': via}})
            recs += [{'path': have[s], 'action': 'cull'} for s in removed]
            recs += [{'path': f'{page}/{s}', 'slots': {'heading': now_named[s][1]['heading'], 'level': now_named[s][1]['level'],
                                                       'text': now_named[s][1]['text'], 'n': now_named[s][0]}} for s in added]
            self.write(recs)
        outcome = 'new' if not had else ('changed' if added or removed else 'unchanged')
        return outcome, page, len(added), len(removed)


if __name__ == '__main__':
    _hand.run(SyncHand, settings=())
