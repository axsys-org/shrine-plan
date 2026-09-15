// Journal pagination integration over a mandatory saved shell. All journals,
// events, failures and renderer responses are exact inert browser fixtures.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live requests are forbidden.');
const base = 'http://debug-pagination-fixture.invalid';
const root = fileURLToPath(new URL('..', import.meta.url));
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
  ...['namespace', 'journal', 'values'].map(name => ['/__pagination_test__/' + name + '.js', 'src/foil/debug/' + name + '.js', 'application/javascript']),
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const initialHTML = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const ids = Array.from({length: 85}, (_, index) => String(9007199254741085n - BigInt(index)));
const epoch = '9007199254741999';
const firstBefore = ids[39], secondBefore = ids[79];
const browser = await chromium.launch();
try {
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const reads = [], writes = [], unexpected = [], errors = [];
let emptyJournal = false, nextFault = null, heldBefore = null, releaseRead = null, readGate = null;
await context.route('**/*', route => {unexpected.push(route.request().url()); return route.abort();});

// Use the real document anatomy, but never imply these synthetic events are
// runtime records. Large IDs specifically detect lossy Number cursor handling.
const fixtures = await page.evaluate(({html, ids, epoch}) => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  const pageHTML = (path, children = [], paging = null) => {
    const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
    ws.dataset.path = path; ws.dataset.renderUrl = '/ns' + (path === '/' ? '' : path);
    ws.dataset.kind = path === '/log' ? 'journal' : path.startsWith('/log/') ? 'record' : 'record';
    ws.dataset.label = 'Browser-only pagination fixture'; ws.dataset.fixture = 'debug-pagination';
    ws.dataset.writable = 'false';
    for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete ws.dataset[key];
    if (paging) Object.assign(ws.dataset, {paging: 'journal', pageBefore: paging.before || '', pageNextBefore: paging.nextBefore || '',
      pageLimit: String(paging.limit), childCount: paging.total, pageEpoch: paging.epoch});
    for (const limb of doc.querySelectorAll('#debug-main > section[aria-label=Record] > sh-myth > sh-limb')) {
      const key = limb.querySelector('sh-slot')?.getAttribute('title');
      if (key === '/sys/lede' || key === '/sys/help') limb.querySelector('sh-pail').textContent = 'Browser-only pagination fixture';
    }
    doc.querySelector('#debug-main section[aria-label=Operations]')?.replaceChildren();
    const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
    for (const child of children) {
      const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
      item.dataset.label = child.split('/').at(-1); item.setAttribute('title', item.dataset.label);
      tree.append(item);
    }
    const semantics = doc.querySelector('#debug-main section[aria-label=Semantics]'); semantics.replaceChildren();
    if (path === '/log') {
      const events = doc.createElement('div'); events.className = 'debug-events';
      for (const child of children) {
        const event = doc.createElement('a'); event.className = 'debug-event'; event.href = '/debug' + child;
        event.dataset.reference = child; event.dataset.eventValid = String(child !== '/log/' + ids[0]);
        const id = doc.createElement('code'); id.className = 'debug-event-id'; id.textContent = child.split('/').at(-1);
        const verb = doc.createElement('strong'); verb.textContent = child === '/log/' + ids[0] ? 'Inspect record' : 'Fixture event';
        const target = doc.createElement('code'); target.textContent = child;
        const status = doc.createElement('span'); status.className = 'muted';
        status.textContent = child === '/log/' + ids[0] ? 'No event payload' : 'Browser-only fixture';
        event.append(id, verb, target, status); events.append(event);
      }
      if (!children.length) {
        const empty = doc.createElement('p'); empty.className = 'muted'; empty.textContent = 'No journal events in this snapshot.'; events.append(empty);
      }
      semantics.append(events);
      const nav = doc.createElement('nav'); nav.className = 'debug-journal-pagination'; nav.setAttribute('aria-label', 'Journal pages');
      for (const [label, cursor] of [['Latest events', null], ['Older events', paging.nextBefore]]) {
        if (label === 'Latest events' ? !paging.before : !cursor) continue;
        const anchor = doc.createElement('a'); anchor.textContent = label;
        const query = new URLSearchParams(); if (cursor) query.set('before', cursor); query.set('limit', String(paging.limit));
        anchor.setAttribute('href', '/debug/log?' + query); nav.append(anchor);
      }
      semantics.append(nav);
    }
    return '<!doctype html>' + doc.documentElement.outerHTML;
  };
  const journal = {};
  for (const limit of [1, 40]) for (const before of [null, ids[39], ids[79], '0']) {
    const available = before === null ? ids : ids.filter(id => BigInt(id) < BigInt(before));
    const selected = available.slice(0, limit), nextBefore = available.length > selected.length ? selected.at(-1) : null;
    journal[(before || '') + ':' + limit] = pageHTML('/log', selected.map(id => '/log/' + id), {before, nextBefore, limit, total: String(ids.length), epoch});
  }
  return {app: html, root: pageHTML('/', ['/app', '/log']), journal,
    empty: pageHTML('/log', [], {before: null, nextBefore: null, limit: 40, total: '0', epoch: '0'}),
    events: Object.fromEntries([...ids.map(id => ['/log/' + id, pageHTML('/log/' + id)]),
      ['/log/named-fixture', pageHTML('/log/named-fixture')]])};
}, {html: initialHTML, ids, epoch});

function faultHTML(html, fault) {
  if (fault === 'missing') return html.replace(/ data-(?:paging|page-before|page-next-before|page-limit|child-count|page-epoch)="[^"]*"/g, '');
  if (fault === 'invalid') return html.replace(/data-page-epoch="[^"]*"/, 'data-page-epoch="NaN"');
  return html;
}
async function routeFixtures(route) {
  const request = route.request(), url = new URL(request.url());
  if (request.method() !== 'GET') { writes.push(request.url()); return route.abort(); }
  if (url.origin !== base) {unexpected.push(request.url()); return route.abort();}
  if (assets.has(url.pathname) && !url.search) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (url.origin === base && /^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/';
    reads.push({path, query: url.search, before: url.searchParams.get('before'), limit: url.searchParams.get('limit')});
    if (path === '/log') {
      if ([...url.searchParams.keys()].some(key => !['before', 'limit', 'view'].includes(key) || url.searchParams.getAll(key).length !== 1) ||
          url.searchParams.has('view') && url.searchParams.get('view') !== 'rendered') {
        unexpected.push(request.url()); return route.abort();
      }
      const before = url.searchParams.get('before'), limit = url.searchParams.get('limit') || '40';
      if (heldBefore === before && readGate) await readGate;
      const fault = nextFault; nextFault = null;
      if (fault === 'http') return route.fulfill({status: 503, contentType: 'text/plain', body: 'Browser-only journal failure'});
      const html = emptyJournal ? fixtures.empty : fixtures.journal[(before || '') + ':' + limit];
      if (html) return route.fulfill({status: 200, contentType: 'text/html', body: faultHTML(html, fault)});
    } else {
      if (url.search) {unexpected.push(request.url()); return route.abort();}
      const html = path === '/app' ? fixtures.app : path === '/' ? fixtures.root : Object.hasOwn(fixtures.events, path) ? fixtures.events[path] : null;
      if (html) return route.fulfill({status: 200, contentType: 'text/html', body: html});
    }
  }
  if (url.pathname === '/ns/log' && !url.search) return route.fulfill({status: 200, contentType: 'text/html',
    body: '<!doctype html><title>Browser-only rendered fixture</title><p>Rendered journal fixture</p>'});
  if (url.pathname === '/favicon.ico' && !url.search) return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
}
await context.route('**/*', routeFixtures);
page.on('pageerror', error => errors.push(error.message));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); }
  assert.fail(message);
}
const native = host => host.locator('button[part=control]');
const pager = page.locator('nav.debug-journal-pagination');
const older = () => pager.getByRole('link', {name: 'Older events', exact: true});
const latest = () => pager.getByRole('link', {name: 'Latest events', exact: true});
const journalItem = () => page.locator('#debug-path-tree ui-tree-item[data-path="/log"]');
const sidebarChildren = () => journalItem().locator(':scope > ui-tree-item');
const sidebarOlder = () => journalItem().locator('.debug-load-older');
async function ready(path) {
  await page.waitForFunction(path => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, path);
}
async function pageIs(before, selected, total = '85') {
  await ready('/log');
  await settled(async () => await page.locator('#debug-workspace').getAttribute('data-page-before') === (before || ''), 'the requested journal cursor is installed');
  assert.equal(new URL(page.url()).pathname, '/debug/log');
  assert.equal(new URL(page.url()).searchParams.get('before'), before);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-child-count'), total);
  assert.deepEqual(await page.locator('.debug-events > ui-link.debug-event').evaluateAll(links => links.map(link => link.dataset.reference)), selected.map(id => '/log/' + id));
  assert.deepEqual(await page.locator('.debug-event-id').allTextContents(), selected, 'every event ID remains exact and unabridged');
  assert.ok(selected.length <= 40, 'a page is bounded at 40 physical entries');
  assert.equal(await page.locator('#wb-canvas .wb-child-row').count(), 0, 'journal entries are not duplicated as a second main child grid');
}
async function failedReadKeepsPage(fault) {
  const previous = page.url(), paths = await page.locator('.debug-event').evaluateAll(links => links.map(link => link.dataset.reference));
  nextFault = fault; await older().click();
  await settled(async () => await page.locator('#debug-status').getAttribute('data-failed') === 'true', fault + ' page is reported explicitly');
  assert.equal(page.url(), previous, 'a rejected page does not alter the address');
  assert.deepEqual(await page.locator('.debug-event').evaluateAll(links => links.map(link => link.dataset.reference)), paths, 'the last good page remains usable');
  assert.match(await page.locator('#debug-status').textContent(), /fail|invalid|missing|pagination|metadata|page/i);
}
async function journalGeometry(target = page) {
  const result = await target.evaluate(() => {
    const defects = [];
    if (document.documentElement.scrollWidth > innerWidth + 1) defects.push('document overflow');
    for (const row of document.querySelectorAll('.debug-events > .debug-event')) {
      const outer = row.getBoundingClientRect(), content = row.querySelector('.debug-event-content');
      const control = row.shadowRoot.querySelector('a'), bounds = control.getBoundingClientRect();
      const cells = [...content.children];
      if (Math.abs(bounds.width - outer.width) > 2) defects.push('event native link does not span its row');
      if (matchMedia('(pointer: coarse)').matches && (bounds.height < 44 || bounds.width < 44)) defects.push('event touch target below 44px');
      if (row.scrollWidth > row.clientWidth + 1) defects.push('row overflow ' + row.dataset.reference);
      for (const cell of cells) {
        const bounds = cell.getBoundingClientRect(), range = document.createRange(); range.selectNodeContents(cell);
        if (bounds.left < outer.left - 1 || bounds.right > outer.right + 1 || cell.scrollWidth > cell.clientWidth + 1)
          defects.push('cell overflow ' + cell.className);
        if ([...range.getClientRects()].some(fragment => fragment.left < bounds.left - 1 || fragment.right > bounds.right + 1))
          defects.push('text paints outside its own column ' + cell.className);
      }
      const id = row.querySelector('.debug-event-id'), range = document.createRange(); range.selectNodeContents(id);
      if (range.getBoundingClientRect().height > parseFloat(getComputedStyle(id).lineHeight) + 1)
        defects.push('ordinary 16-digit event ID unnecessarily splits across lines');
      for (let left = 0; left < cells.length; left++) for (let right = left + 1; right < cells.length; right++) {
        const a = cells[left].getBoundingClientRect(), b = cells[right].getBoundingClientRect();
        if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
          defects.push('overlapping journal columns');
      }
    }
    for (const link of document.querySelectorAll('nav.debug-journal-pagination ui-link')) {
      const control = link.shadowRoot.querySelector('a'), bounds = control.getBoundingClientRect();
      if (bounds.left < 0 || bounds.right > innerWidth || control.scrollWidth > control.clientWidth + 1) defects.push('pager action overflow');
      if (matchMedia('(pointer: coarse)').matches && (bounds.height < 44 || bounds.width < 44)) defects.push('pager touch target below 44px');
    }
    const controls = [...document.querySelectorAll('nav.debug-journal-pagination ui-link')].map(link => link.shadowRoot.querySelector('a').getBoundingClientRect());
    for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
      const a = controls[i], b = controls[j];
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
        defects.push('overlapping native pager targets');
    }
    return defects;
  });
  assert.deepEqual(result, [], 'long decimal IDs, task/path columns and pager controls retain independent horizontal bounds');
}

try {
  await page.goto(base + '/debug/app'); await ready('/app');
  const parsed = await page.evaluate(async ({html, ids, epoch}) => {
    const {parseDebugDocument} = await import('/__pagination_test__/namespace.js');
    const {journalPageFromURL} = await import('/__pagination_test__/journal.js');
    const doc = () => new DOMParser().parseFromString(html, 'text/html');
    const valid = parseDebugDocument(doc(), '/log');
    const invalid = [];
    for (const [name, value] of [
      ['data-page-before', '01'], ['data-page-next-before', '-1'], ['data-page-limit', '0'],
      ['data-page-limit', '41'], ['data-page-limit', '1.5'], ['data-child-count', '1e6'],
      ['data-page-epoch', 'NaN'], ['data-page-epoch', null], ['data-page-next-before', null],
    ]) {
      const input = doc(), ws = input.querySelector('#debug-workspace');
      if (value === null) ws.removeAttribute(name); else ws.setAttribute(name, value);
      try { parseDebugDocument(input, '/log'); invalid.push({name, value, rejected: false}); }
      catch (error) { invalid.push({name, value, rejected: true, message: error.message}); }
    }
    const legacy = doc();
    for (const attr of ['data-paging', 'data-page-before', 'data-page-next-before', 'data-page-limit', 'data-child-count', 'data-page-epoch']) legacy.querySelector('#debug-workspace').removeAttribute(attr);
    const invalidQueries = ['before=', 'before=01', 'before=-1', 'before=1.5', 'limit=0', 'limit=41', 'limit=040',
      'before=1&before=1', 'limit=1&limit=1', 'view=rendered&view=rendered', 'unknown=1', 'view=inspect',
      'limit=3&', '&before=0', '&&'].map(query => {
      try { journalPageFromURL(new URL('/debug/log?' + query, location.href)); return {query, rejected: false}; }
      catch (error) { return {query, rejected: true, message: error.message}; }
    });
    return {pagination: valid.pagination, children: valid.children, invalid, invalidQueries,
      smallestPage: journalPageFromURL(new URL('/debug/log?before=' + ids[39] + '&limit=1&view=rendered', location.href)),
      legacyPagination: parseDebugDocument(legacy, '/log').pagination ?? null};
  }, {html: fixtures.journal[':40'], ids, epoch});
  assert.deepEqual(parsed.pagination, {kind: 'journal', before: null, nextBefore: firstBefore, limit: 40, total: '85', epoch});
  assert.deepEqual(parsed.children, ids.slice(0, 40).map(id => '/log/' + id));
  assert.equal(parsed.legacyPagination, null, 'the old running kernel remains usable at the default journal URL');
  assert.ok(parsed.invalid.every(result => result.rejected && result.message), 'invalid or incomplete present metadata fails explicitly: ' + JSON.stringify(parsed.invalid));
  assert.deepEqual(parsed.smallestPage, {before: firstBefore, limit: 1});
  assert.ok(parsed.invalidQueries.every(result => result.rejected && result.message), 'unknown, duplicate and malformed page query parameters fail explicitly: ' + JSON.stringify(parsed.invalidQueries));
  console.log('PASS: real parser preserves exact decimal cursors/count/epoch and rejects malformed present metadata; legacy default remains explicit.');

  await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill('/log');
  await page.locator('#debug-go input').press('Enter');
  await pageIs(null, ids.slice(0, 40));
  assert.equal(await latest().count(), 0);
  assert.equal(new URL(await older().getAttribute('href'), base).searchParams.get('before'), firstBefore);
  const malformed = page.locator('.debug-event[data-event-valid="false"]');
  assert.equal(await malformed.getAttribute('data-reference'), '/log/' + ids[0]);
  await malformed.click(); await ready('/log/' + ids[0]);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'record', 'a numeric path without an event payload remains inspectable');
  await page.locator('#debug-back').click(); await pageIs(null, ids.slice(0, 40));
  await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill('/log/named-fixture');
  await page.locator('#debug-go input').press('Enter'); await ready('/log/named-fixture');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'record', 'a named record below /log is not coerced to a numeric cursor');
  await page.locator('#debug-back').click(); await pageIs(null, ids.slice(0, 40));
  await older().click(); await pageIs(firstBefore, ids.slice(40, 80));
  await page.locator('#debug-back').click(); await pageIs(null, ids.slice(0, 40));
  await page.locator('#debug-forward').click(); await pageIs(firstBefore, ids.slice(40, 80));
  await page.goBack(); await pageIs(null, ids.slice(0, 40));
  await page.goForward(); await pageIs(firstBefore, ids.slice(40, 80));
  await page.reload(); await pageIs(firstBefore, ids.slice(40, 80));
  await page.locator('#wb-refresh').click(); await settled(async () => !await page.locator('#wb-refresh').evaluate(el => el.loading), 'refresh settles');
  await pageIs(firstBefore, ids.slice(40, 80));
  await older().click(); await pageIs(secondBefore, ids.slice(80));
  assert.equal(await older().count(), 0, 'terminal page has no false Older affordance');
  await latest().click(); await pageIs(null, ids.slice(0, 40));
  console.log('PASS: newest/older/latest, native and browser history, reload and refresh retain exclusive high-precision cursors; malformed event records remain paths.');

  for (const fault of ['http', 'invalid', 'missing']) {
    await failedReadKeepsPage(fault);
    await older().click(); await pageIs(firstBefore, ids.slice(40, 80));
    await latest().click(); await pageIs(null, ids.slice(0, 40));
  }
  const normalOlderURL = await older().getAttribute('href');
  await older().evaluate(link => { link.href = '/debug/log?limit=1'; });
  await failedReadKeepsPage('missing');
  await older().evaluate((link, href) => { link.href = href; }, normalOlderURL);
  console.log('PASS: failed and invalid/missing explicit-page responses retain the last good page and retry the same cursor.');

  // Fresh document/storage resets the tree's loaded batches without touching
  // runtime state. Every older read must load exactly one bounded page.
  await context.clearCookies();
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await page.goto(base + '/debug/log'); await pageIs(null, ids.slice(0, 40));
  await settled(async () => await sidebarChildren().count() === 40, 'sidebar starts with exactly the first physical page');
  await journalItem().locator('button[part=control]').first().press('ArrowRight');
  await settled(() => journalItem().evaluate(item => item.expanded), 'keyboard disclosure opens the journal children');
  const originalFirst = await sidebarChildren().first().getAttribute('data-path');
  const keptRow = sidebarChildren().first();
  const keptRowElement = await keptRow.elementHandle();
  const keptBookmark = keptRow.locator(':scope > .debug-bookmark-toggle');
  const keptBookmarkElement = await keptBookmark.elementHandle();
  const rowExpanded = await keptRow.evaluate(item => item.expanded);
  const beforeBookmarkReads = reads.length;
  await native(keptBookmark).focus(); await native(keptBookmark).press('Enter');
  await settled(async () => await native(keptBookmark).getAttribute('aria-pressed') === 'true', 'the exact noncurrent journal row is saved before paging');
  assert.equal(await page.locator('.debug-page-row[data-path="' + originalFirst + '"] > ui-link a').getAttribute('href'), '/debug' + originalFirst);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/log', 'bookmarking does not open the event');
  assert.equal(await keptRow.evaluate(item => item.expanded), rowExpanded, 'bookmarking leaves hierarchy disclosure unchanged');
  assert.equal(await keptRow.locator(':scope > [slot="preview"]').count(), 0, 'bookmarking creates no inline preview');
  assert.equal(reads.length, beforeBookmarkReads, 'bookmarking issues no namespace read');
  const beforeReads = reads.filter(read => read.path === '/log').length;
  heldBefore = firstBefore; readGate = new Promise(resolve => { releaseRead = resolve; });
  await sidebarOlder().click();
  await settled(async () => await native(sidebarOlder()).isDisabled(), 'older sidebar button is disabled while loading');
  assert.equal(await sidebarChildren().count(), 40, 'existing rows remain while a page is pending');
  releaseRead(); readGate = null; heldBefore = null;
  await settled(async () => await sidebarChildren().count() === 80, 'one older page appends exactly 40 rows');
  assert.equal(reads.filter(read => read.path === '/log').length - beforeReads, 1, 'one click issues one bounded journal read');
  assert.equal(await sidebarChildren().first().getAttribute('data-path'), originalFirst);
  assert.equal(await keptRow.evaluate((item, original) => item === original, keptRowElement), true, 'appending preserves the original row node');
  assert.equal(await keptBookmark.evaluate((button, original) => button === original, keptBookmarkElement), true, 'appending preserves the original bookmark control');
  assert.equal(await native(keptBookmark).getAttribute('aria-pressed'), 'true', 'appending preserves the existing bookmark state');
  assert.equal(await keptRow.evaluate(item => item.expanded), rowExpanded);
  assert.equal(await page.locator('.debug-page-row[data-path="' + originalFirst + '"] > ui-link a').getAttribute('href'), '/debug' + originalFirst);
  assert.deepEqual(await sidebarChildren().evaluateAll(items => items.map(item => item.dataset.path)), ids.slice(0, 80).map(id => '/log/' + id));
  nextFault = 'http'; await sidebarOlder().click();
  await journalItem().locator('.debug-page-error[role=status]').waitFor();
  assert.equal(await sidebarChildren().count(), 80, 'sidebar failure keeps the already loaded rows');
  const failedCursor = reads.filter(read => read.path === '/log').at(-1).before;
  assert.equal(failedCursor, secondBefore);
  await sidebarOlder().click();
  await settled(async () => await sidebarChildren().count() === 85, 'retry appends the terminal five rows');
  assert.equal(reads.filter(read => read.path === '/log').at(-1).before, failedCursor, 'retry uses the exact failed cursor');
  assert.equal(await sidebarOlder().count(), 0, 'no older button remains after the terminal response');
  assert.equal(new Set(await sidebarChildren().evaluateAll(items => items.map(item => item.dataset.path))).size, 85);
  await pageIs(null, ids.slice(0, 40));
  const beforeUnsaveReads = reads.length;
  await native(keptBookmark).focus(); await native(keptBookmark).press('Enter');
  await settled(async () => await native(keptBookmark).getAttribute('aria-pressed') === 'false', 'the retained row can be unsaved after all batches');
  assert.equal(await page.locator('.debug-page-row[data-path="' + originalFirst + '"]').count(), 0);
  assert.equal(reads.length, beforeUnsaveReads, 'unsaving after append issues no namespace read');
  console.log('PASS: sidebar pages append bounded batches, preserve row identity/bookmarks, retain rows on failure and retry without duplicates or main-page navigation.');

  await page.goto(base + '/debug/log?before=' + firstBefore + '&limit=40&view=rendered'); await ready('/log');
  assert.equal(await page.locator('#wb-mode-rendered').getAttribute('aria-pressed'), 'true');
  await page.locator('#wb-refresh').click(); await settled(async () => !await page.locator('#wb-refresh').evaluate(el => el.loading), 'rendered refresh settles');
  assert.equal(new URL(page.url()).searchParams.get('view'), 'rendered');
  assert.equal(new URL(page.url()).searchParams.get('before'), firstBefore);
  await page.reload(); await ready('/log');
  assert.equal(new URL(page.url()).searchParams.get('view'), 'rendered');
  assert.equal(new URL(page.url()).searchParams.get('before'), firstBefore);
  assert.equal(await page.locator('#wb-mode-rendered').getAttribute('aria-pressed'), 'true');
  await page.locator('#wb-mode-inspect').click(); await pageIs(firstBefore, ids.slice(40, 80));
  assert.equal(Number(new URL(page.url()).searchParams.get('limit') || '40'), 40, 'canonical omission of the default limit retains its meaning');
  console.log('PASS: rendered mode is an independent retained query parameter, not an encoded part of the namespace path.');

  for (const [width, height] of [[1440, 1000], [768, 1000], [390, 844]]) {
    await page.setViewportSize({width, height}); await page.goto(base + '/debug/log'); await pageIs(null, ids.slice(0, 40));
    await journalGeometry();
    await page.screenshot({path: '/private/tmp/shrine-pagination-light-' + width + '.png', animations: 'disabled'});
  }
  await older().scrollIntoViewIfNeeded(); await journalGeometry();
  await page.screenshot({path: '/private/tmp/shrine-pagination-controls-390.png', animations: 'disabled'});
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await page.goto(base + '/debug/log'); await pageIs(null, ids.slice(0, 40)); await journalGeometry();
  await page.screenshot({path: '/private/tmp/shrine-pagination-dark-390.png', animations: 'disabled'});
  console.log('PASS: desktop/intermediate/mobile/dark journal rows keep exact IDs on one line, with full-row Mash anchors and independent content bounds.');

  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true});
  try {
    await touchContext.route('**/*', routeFixtures);
    const touchPage = await touchContext.newPage();
    touchPage.on('pageerror', error => errors.push(error.message));
    await touchPage.goto(base + '/debug/log?before=' + firstBefore);
    await touchPage.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
    assert.equal(await touchPage.evaluate(() => matchMedia('(pointer: coarse)').matches), true);
    await journalGeometry(touchPage);
    const touchOlder = touchPage.locator('nav.debug-journal-pagination').getByRole('link', {name: 'Older events', exact: true});
    await touchOlder.scrollIntoViewIfNeeded();
    await touchPage.screenshot({path: '/private/tmp/shrine-pagination-touch-390.png', animations: 'disabled'});
    await touchOlder.tap();
    await touchPage.waitForFunction(before => document.querySelector('#debug-workspace')?.dataset.pageBefore === before, secondBefore);
    assert.deepEqual(await touchPage.locator('.debug-event-id').allTextContents(), ids.slice(80));
    await journalGeometry(touchPage);
    console.log('PASS: coarse-pointer native event/pager targets are at least 44px, do not overlap, and actual touch navigation opens the next page.');
  } finally { await touchContext.close(); }

  emptyJournal = true;
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await page.goto(base + '/debug/log'); await pageIs(null, [], '0');
  assert.equal(await older().count(), 0); assert.equal(await latest().count(), 0);
  assert.match(await page.locator('.debug-events').innerText(), /No journal events/);
  await journalItem().waitFor({state: 'attached'});
  await settled(async () => await sidebarChildren().count() === 0, 'empty journal has no fabricated child rows');
  assert.equal(await sidebarOlder().count(), 0);
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  assert.ok(reads.filter(read => read.path === '/log').every(read => read.limit === null || Number(read.limit) <= 40));
  assert.ok(reads.every(read => !read.path.includes('?')), 'query strings never become namespace path segments');
  console.log('PASS: empty and terminal states; ' + reads.length + ' intercepted fixture GETs, zero live requests or mutations.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-pagination-failure.png'});
  console.error('Pagination context:', {url: page.url(), reads, writes, unexpected, errors});
  throw error;
} finally { releaseRead?.(); await context.close(); }
} finally { await browser.close(); }
