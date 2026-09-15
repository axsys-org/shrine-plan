// Browser checks against real GETs. No operation or other write reaches runtime.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const base = process.env.DEBUG_URL || 'http://127.0.0.1:8134';
const errors = [];
const writes = [];
const reads = [];
let failNext = null;
const fixtures = new Map();
page.on('pageerror', error => errors.push(error.message));
await page.route('**/*', async route => {
  const request = route.request();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
    writes.push(request.url()); return route.fulfill({ status: 405, body: 'Writes blocked by test' });
  }
  if (request.resourceType() === 'fetch') reads.push(request.url());
  const fixture = fixtures.get(new URL(request.url()).pathname);
  if (fixture) return route.fulfill({ status: 200, contentType: 'text/html', body: fixture });
  if (failNext && new URL(request.url()).pathname === failNext) {
    failNext = null; return route.fulfill({ status: 503, body: 'Intentional browser test failure' });
  }
  await route.continue();
});
function row(path) { return page.locator('#debug-path-tree ui-tree-item[data-path=' + JSON.stringify(path) + ']'); }
async function loaded(path) {
  await page.waitForFunction(path => [...document.querySelectorAll('#debug-path-tree ui-tree-item')]
    .some(item => item.dataset.path === path && item.dataset.readState === 'ready'), path, { timeout: 60000 });
}
async function expand(path) {
  const target = row(path);
  await target.waitFor();
  if (await target.getAttribute('expanded') === null) await target.locator(':scope > [slot=disclosure]').click();
  await loaded(path);
}
async function navigate(path) {
  if (!await page.locator('#debug-go').isVisible())
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  await page.locator('#debug-go ui-input input').fill(path);
  await page.locator('#debug-go ui-input input').press('Enter');
  await page.waitForFunction(path => document.querySelector('#debug-workspace')?.dataset.path === path &&
    document.querySelector('#debug-workspace')?.getAttribute('aria-busy') === 'false', path);
}
try {
  await page.goto(base + '/debug/boot?care=x&case=1');
  await loaded('/'); await loaded('/boot');
  assert.equal(await page.locator('#debug-path-tree .debug-node-preview').count(), 0,
    'revealing current path does not open metadata previews on all ancestors');
  assert.equal(await row('/boot').getAttribute('expanded'), null, 'navigation reveals the row without expanding its contents');
  await row('/boot').getByRole('button', { name: 'Preview record /boot', exact: true }).click();
  assert.equal(await row('/boot').locator(':scope > [slot=preview]').isVisible(), true);
  assert.equal(await row('/boot').getAttribute('expanded'), null, 'preview opens independently of hierarchy');
  assert.doesNotMatch(await row('/boot').locator(':scope > [slot=preview]').textContent(), /Own record slots and namespace relationships\./);
  assert.equal(await row('/boot').locator(':scope > [slot=preview] sh-slot[title="/sys/help"], :scope > [slot=preview] sh-slot[title="/sys/lede"]').count(), 0,
    'inline previews omit documentation slots already represented by the heading');
  await page.keyboard.press('Escape');
  assert.equal(await row('/boot').locator(':scope > [slot=preview]').count(), 0, 'Escape dismisses the deliberate preview');
  assert.equal(await row('/boot').evaluate(item => item.shadowRoot.activeElement?.getAttribute('part')), 'control',
    'closing preview returns keyboard focus to its tree row');
  assert.equal(await page.locator('#debug-saved p').count(), 0, 'empty Saved has no explanatory filler');
  assert.equal(new URL(page.url()).search, '', 'retired care/case parameters are not app modes');
  assert.equal(await page.locator('#wb-version, #wb-history, #wb-pin, #wb-case-input, #debug-views, [data-filter-view]').count(), 0);
  assert.equal(await page.locator('#debug-path-tree').getAttribute('variant'), 'namespace');
  await page.locator('#debug-root-toggle').click();
  assert.equal(await page.getByRole('menu', { name: 'Namespace places', exact: true }).isVisible(), true);
  assert.deepEqual(await page.locator('#debug-root-menu > ui-menu-item').evaluateAll(items => items.map(item => item.value)),
    ['/', '/app', '/gov', '/weft', '/log', '/sys']);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#debug-root-menu').getAttribute('open'), null, 'shared Mash menu handles Escape');
  await page.locator('#debug-root-toggle').click();
  await page.locator('#debug-root-menu > ui-menu-item[value="/gov"]').click();
  await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.path === '/gov');
  assert.equal(await page.locator('#debug-root-menu').getAttribute('open'), null, 'choosing a place dismisses the menu');
  await navigate('/boot');
  assert.equal(await page.locator('#debug-path-tree').evaluate(tree => {
    const graph = tree.shadowRoot.querySelector('[part=graph]');
    return !graph || getComputedStyle(graph).display === 'none';
  }), true, 'no revision graph painted over namespace');
  assert.equal(await row('/').count(), 1, 'ordinary browsing starts at the whole namespace');
  const branchBefore = await row('/').evaluate(node => { node.dataset.testIdentity = 'preserved'; return true; });
  assert.equal(branchBefore, true);
  await expand('/weft');
  await expand('/weft/kook');
  await expand('/weft/kook/face');
  assert.equal(await row('/weft/kook').locator(':scope > [slot=preview]').count(), 0, 'hierarchy disclosure does not dump record metadata');
  const previewReads = reads.length;
  await row('/weft/kook/face').getByRole('button', { name: 'Preview record /weft/kook/face', exact: true }).click();
  assert.equal(await row('/weft/kook/face').locator(':scope > [slot=preview] sh-myth').count(), 1, 'slots preview through real deep path');
  assert.equal(reads.length, previewReads, 'a loaded record preview opens immediately without another read');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/boot', 'expanding does not navigate');
  await navigate('/weft/kook/face');
  assert.equal(await row('/').getAttribute('data-test-identity'), 'preserved', 'navigation preserves tree DOM and expansion');
  assert.equal(await row('/weft').getAttribute('expanded') !== null, true);
  assert.equal(await row('/weft/kook/face').getAttribute('current') !== null, true);

  const saved = page.locator('#debug-section-saved');
  const recent = page.locator('#debug-section-recent');
  const treeSection = page.locator('#debug-section-tree');
  await recent.locator('button[part=trigger]').click();
  assert.equal(await recent.getAttribute('open') !== null, true);
  assert.equal(await treeSection.getAttribute('open') !== null, true, 'Recent opens without replacing Tree');
  await saved.locator('button[part=trigger]').click();
  assert.equal(await saved.getAttribute('open'), null);
  assert.equal(await recent.getAttribute('open') !== null, true, 'Saved is independently collapsible');
  await saved.locator('button[part=trigger]').click();
  await navigate('/weft');
  await page.locator('#debug-save').click();
  await page.locator('#debug-saved .debug-page-row[data-path="/weft"] a').click();
  await page.waitForFunction(() => document.querySelector('#debug-path-tree ui-tree > ui-tree-item')?.dataset.path === '/weft');
  await loaded('/weft');
  assert.equal(await page.locator('#debug-path-tree ui-tree > ui-tree-item').getAttribute('data-path'), '/weft', 'saved page scopes the child hierarchy beneath it');
  assert.equal(await page.locator('#debug-tree-root').getAttribute('path'), '/weft');
  await expand('/weft/kook');
  assert.equal(await row('/weft/kook/face').count(), 1);
  await page.locator('#debug-tree-namespace').click();
  await loaded('/');
  assert.equal(await page.locator('#debug-path-tree ui-tree > ui-tree-item').getAttribute('data-path'), '/');

  const filter = page.locator('#debug-filter input');
  await filter.fill('/weft/kook/face');
  assert.equal(await row('/weft/kook/face').isVisible(), true);
  assert.equal(await row('/app').isVisible(), false);
  await filter.press('Escape');
  assert.equal(await filter.inputValue(), '');
  assert.equal(await row('/app').isVisible(), true);
  await page.locator('#debug-tree-collapse').click();
  assert.equal(await row('/weft').getAttribute('expanded'), null);
  await row('/weft').evaluate(item => item.focusControl());
  await page.keyboard.press('ArrowRight');
  await loaded('/weft');
  assert.equal(await row('/weft').getAttribute('expanded') !== null, true, 'keyboard expands without changing current record');
  await page.keyboard.press('ArrowLeft');
  assert.equal(await row('/weft').getAttribute('expanded'), null);
  await row('/weft').getByRole('button', { name: 'Preview record /weft', exact: true }).click();
  assert.equal(await row('/weft').locator(':scope > [slot=preview]').isVisible(), true);
  assert.equal(await row('/weft/kook').isVisible(), false, 'previewing a collapsed branch keeps its children closed');
  await page.keyboard.press('Escape');

  failNext = '/debug';
  await page.locator('#debug-tree-refresh').click();
  await page.waitForFunction(() => document.querySelector('#debug-path-tree ui-tree-item').dataset.readState === 'error');
  await row('/').getByRole('button', { name: 'Retry /', exact: true }).click();
  await loaded('/');
  assert.equal(reads.some(url => /\/debug\/h\//.test(url)), false, 'sidebar only reads live paths, not case projections');
  assert.equal(await page.locator('ui-icon.wb-icon').evaluateAll(icons => icons.every(icon => icon.dataset.iconSource === 'Mash' && !icon.getAttribute('name').startsWith('shrine.'))), true);
  await navigate('/app');
  await loaded('/');
  await page.locator('#debug-tree-collapse').click();
  await page.locator('#debug-sidebar').evaluate(sidebar => {
    const scroller = sidebar.shadowRoot.querySelector('ui-scroll-area')?.shadowRoot.querySelector('[part="viewport"]');
    if (scroller) scroller.scrollTop = 0;
  });
  await page.screenshot({ path: '/private/tmp/mash-namespace-sidebar-app.png' });

  // Each test page has isolated browser storage. Previously expanded sibling
  // branches must not return after Collapse all, deep navigation, and reload.
  // Exercise genuine namespace reads, never an install or other runtime write.
  async function hasLiveRecord(path) {
    const response = await page.request.get(base + '/debug' + path, { timeout: 60000 });
    if (response.status() === 404) return false;
    assert.equal(response.ok(), true, 'deep-path probe returned HTTP ' + response.status() + ' for ' + path);
    return page.evaluate(({ raw, path }) => {
      const doc = new DOMParser().parseFromString(raw, 'text/html');
      return doc.querySelector('#debug-workspace')?.dataset.path === path &&
        Boolean(doc.querySelector('#debug-main > section[aria-label="Record"] > sh-myth'));
    }, { raw: await response.text(), path });
  }
  const deepPath = await hasLiveRecord('/app/srs/cards/demo')
    ? '/app/srs/cards/demo' : '/gov/srs/card';
  assert.equal(await hasLiveRecord(deepPath), true,
    'collapse/reload regression requires the installed demo or the published SRS card definition');
  const segments = deepPath.split('/').filter(Boolean);
  const ancestors = ['/', ...segments.slice(0, -1).map((_, index) => '/' + segments.slice(0, index + 1).join('/'))];
  console.log('Collapse/reload regression uses live record ' + deepPath);
  await expand('/weft');
  await expand('/sys');
  await page.locator('#debug-tree-collapse').click();
  const expandedPaths = () => page.locator('#debug-path-tree ui-tree-item[expanded]')
    .evaluateAll(items => items.map(item => item.dataset.path).sort());
  const storedExpansion = () => page.evaluate(() =>
    JSON.parse(localStorage.getItem('shrine-debug.sidebar.v2') || '{}').expanded || []);
  assert.deepEqual(await expandedPaths(), ['/'], 'Collapse all closes every non-root branch');
  assert.deepEqual(await storedExpansion(), ['/'], 'Collapse all removes old expansion preferences');
  const afterCollapseReads = reads.length;
  await navigate(deepPath);
  await loaded(deepPath);
  assert.deepEqual(await expandedPaths(), ancestors, 'deep navigation reveals only the selected path ancestors');
  await page.reload();
  await loaded('/');
  await loaded(deepPath);
  assert.deepEqual(await expandedPaths(), ancestors, 'reload does not resurrect unrelated collapsed branches');
  for (const path of ['/app', '/gov', '/io', '/kook', '/log', '/sys', '/weft'].filter(path => !ancestors.includes(path))) {
    assert.equal(await row(path).getAttribute('expanded'), null, path + ' remains collapsed after reload');
    assert.equal(reads.slice(afterCollapseReads).some(url => new URL(url).pathname === '/debug' + path), false,
      'collapsed sibling ' + path + ' makes no background read');
  }
  assert.equal((await storedExpansion()).every(path => ancestors.includes(path)), true,
    'reload does not persist unrelated expansion state');

  // Deterministic large-journal fixture: only read SSR; no fabricated events
  // or writes are submitted to the runtime. Exercise paging independent of
  // how many HTTP entries the running development namespace already has.
  const original = await (await page.request.get(base + '/debug/log')).text();
  const fixturePages = await page.evaluate(raw => {
    function documentFor(path, kind, label, description, children = []) {
      const doc = new DOMParser().parseFromString(raw, 'text/html');
      const workspace = doc.querySelector('#debug-workspace');
      workspace.dataset.path = path; workspace.dataset.kind = kind;
      workspace.dataset.label = label; workspace.dataset.description = description;
      workspace.dataset.descriptionSource = '/sys/help';
      doc.querySelector('#debug-main section[aria-label="Record"]')?.remove();
      doc.querySelector('#debug-main section[aria-label="Semantics"]')?.remove();
      doc.querySelector('#debug-children').replaceChildren(...children.map(number => {
        const item = doc.createElement('ui-tree-item');
        item.dataset.path = '/log/' + number; item.dataset.kind = 'event';
        item.dataset.label = 'Event ' + number; item.dataset.description = 'Disposed request /io/http/r' + number;
        item.dataset.descriptionSource = '/sys/help';
        return item;
      }));
      return '<!doctype html>' + doc.documentElement.outerHTML;
    }
    const children = Array.from({ length: 125 }, (_, index) => index + 1).sort((a, b) => String(a).localeCompare(String(b)));
    return [
      ['/debug/log', documentFor('/log', 'journal', 'Activity', 'Runtime event journal.', children)],
      ['/debug/log/120', documentFor('/log/120', 'event', 'Event 120', 'Disposed request /io/http/r120')],
    ];
  }, original);
  fixturePages.forEach(([path, body]) => fixtures.set(path, body));
  await page.goto(base + '/debug/log');
  await loaded('/log');
  await expand('/log');
  const logChildren = row('/log').locator(':scope > ui-tree-item');
  assert.equal(await logChildren.count(), 60, 'large journal starts with a bounded page');
  assert.equal(await logChildren.first().getAttribute('data-path'), '/log/125', 'newest numeric journal entry comes first');
  assert.equal(await logChildren.last().getAttribute('data-path'), '/log/66');
  await row('/log').getByRole('button', { name: 'Show more children of /log', exact: true }).click();
  assert.equal(await logChildren.count(), 120, 'show more adds one bounded page');
  await expand('/log/120');
  await row('/log/120').getByRole('button', { name: 'Preview record /log/120', exact: true }).click();
  const eventPreview = row('/log/120').locator(':scope > [slot=preview]');
  assert.match(await eventPreview.textContent(), /Event 120.*event.*Disposed request \/io\/http\/r120/s);
  assert.doesNotMatch(await eventPreview.textContent(), /Empty record|No own record/, 'semantic nodes are not described as empty');
  await row('/log').evaluate(item => { item.dataset.testIdentity = 'refresh-preserved'; });
  fixtures.set('/debug/log/120', fixtures.get('/debug/log/120').replaceAll('Disposed request /io/http/r120', 'Disposed request /io/http/r120 — refreshed snapshot'));
  await page.locator('#wb-refresh').click();
  await page.waitForFunction(() => [...document.querySelectorAll('#debug-path-tree ui-tree-item')]
    .find(item => item.dataset.path === '/log/120')?.querySelector(':scope > [slot=preview]')?.textContent.includes('refreshed snapshot'));
  assert.equal(await row('/log').getAttribute('data-test-identity'), 'refresh-preserved', 'refresh invalidation retains tree DOM');
  assert.equal(await row('/log/120').getAttribute('preview-open'), '', 'refresh retains explicitly opened semantic previews');
  assert.equal(await logChildren.count(), 120, 'refresh retains journal page size');
  await page.locator('#debug-filter input').fill('disposed');
  assert.equal(await row('/log/125').isVisible(), true, 'semantic child summaries are searchable without reading every child');
  assert.equal(reads.some(url => new URL(url).pathname === '/debug/log/125'), false, 'summaries do not trigger background journal reads');
  await page.locator('#debug-filter input').press('Escape');
  await loaded('/');
  await page.screenshot({ path: '/private/tmp/mash-namespace-sidebar-desktop.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#debug-sidebar-toggle').click();
  await page.screenshot({ path: '/private/tmp/mash-namespace-sidebar-mobile.png' });
  assert.deepEqual(writes, []);
  assert.deepEqual(errors, []);
  console.log('PASS: independent hierarchy and inline previews, no automatic metadata dumps, cached previews, Escape focus return, recursive tree, Places menu, newest-first paged journal, collapse/deep-navigation/reload persistence, independent sections, saved-page hierarchy, filtering, keyboard, retry, Mash icons, no case requests or writes.');
} catch (error) {
  console.error('Sidebar failure context:', await page.evaluate(() => ({
    path: document.querySelector('#debug-workspace')?.dataset.path,
    busy: document.querySelector('#debug-workspace')?.getAttribute('aria-busy'),
    status: document.querySelector('#debug-status')?.textContent,
  })).catch(() => null), errors);
  await page.screenshot({ path: '/private/tmp/mash-namespace-sidebar-failure.png' }).catch(() => {});
  throw error;
} finally { await browser.close(); }
