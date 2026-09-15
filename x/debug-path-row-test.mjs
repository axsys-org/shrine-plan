// Production path-row composition over a mandatory saved shell. All namespace
// names, summaries and records are test-owned; no live Grove is inspected.
// Every browser request (including popups) is intercepted before navigation.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live namespace access is forbidden');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-path-row-fixture.invalid';
const parentPath = '/paths';
const children = Array.from({length: 83}, (_, index) => parentPath + '/' + (
  index === 0 ? 'alpha-review' : index === 1 ? '日本語 price?#%λ' :
    index === 2 ? 'long-unbroken-name-' + 'x'.repeat(96) : 'row-' + String(index).padStart(2, '0')));
const richLabel = 'Authored review title — literal <script>window.__pathExecuted=true</script>';
const richDescription = 'Distinct authored help remains visible in the row: café, 日本語, λ, & exact punctuation. ' + 'Complete-not-clipped-'.repeat(8);
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const reads = [], writes = [], unexpected = [], errors = [], screenshots = [], deniedProbes = [];
const policyProbeTargets = new Set();
let activePage;
const browser = await chromium.launch();

try {
  const author = await browser.newContext({serviceWorkers: 'block'});
  let fixtures;
  try {
    await author.route('**/*', route => { unexpected.push('fixture author attempted ' + route.request().url()); return route.abort(); });
    const page = await author.newPage();
    fixtures = Object.freeze(await page.evaluate(({shell, parentPath, children, richLabel, richDescription}) => {
      const original = new DOMParser().parseFromString(shell, 'text/html');
      if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth'))
        throw new Error('Saved shell is not the expected server document anatomy');
      const entries = {'/': [parentPath], [parentPath]: children};
      const paths = ['/', parentPath, ...children];
      return Object.fromEntries(paths.map(path => {
        const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
        const label = path === children[0] ? richLabel : path === parentPath ? 'Fixture path collection' : path.split('/').at(-1) || 'Namespace';
        const help = path === children[0] ? richDescription : 'Test-owned exact record for ' + path + '.';
        Object.assign(workspace.dataset, {path, kind: 'record', writable: 'false', label,
          description: help, descriptionSource: '/sys/help', fixture: 'path-row', renderUrl: '/ns' + path});
        for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
        const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
        for (const [key, text] of [['/sys/lede', label], ['/sys/help', help], ['/value', 'Exact fixture value at ' + path]]) {
          const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
          const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
          const pail = doc.createElement('sh-pail'); pail.textContent = text;
          limb.append(slot, pail); myth.append(limb);
        }
        for (const name of ['Semantics', 'Documentation', 'Operations'])
          doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
        const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
        for (const child of entries[path] || []) {
          const item = doc.createElement('ui-tree-item');
          Object.assign(item.dataset, {path: child, kind: 'record', label: child === children[0] ? richLabel : child.split('/').at(-1),
            description: child === children[0] ? richDescription : '', descriptionSource: '/sys/help'});
          item.title = child.split('/').at(-1); tree.append(item);
        }
        doc.querySelector('#debug-workspace [slot=inspector]')?.replaceChildren();
        doc.querySelector('#debug-activity')?.replaceChildren();
        doc.querySelector('#debug-go ui-input')?.setAttribute('value', path);
        doc.title = 'Test-owned path rows · ' + path;
        const url = '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
        return [url, '<!doctype html>' + doc.documentElement.outerHTML];
      }));
    }, {shell, parentPath, children, richLabel, richDescription}));
  } finally { await author.close(); }

  async function createContext(options = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 960}, serviceWorkers: 'block', ...options});
    context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    await context.addInitScript(({base, parentPath}) => {
      if (location.origin !== base || sessionStorage.getItem('path-row-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: false, root: '/', expanded: []}));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: [parentPath], pages: [null], cursor: 0}));
      sessionStorage.setItem('path-row-fixture', 'seeded');
    }, {base, parentPath});
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      // Deliberate inert policy probes prove foreign, query-bearing, unknown
      // and non-GET requests are rejected. None has a live destination.
      if (policyProbeTargets.delete(request.method() + ' ' + request.url())) {
        const permitted = request.method() === 'GET' && url.origin === base && !url.search &&
          (assets.has(url.pathname) || Object.hasOwn(fixtures, url.pathname) || url.pathname === '/favicon.ico');
        assert.equal(permitted, false, 'policy probe must be outside the allowlist');
        deniedProbes.push(request.method() + ' ' + request.url()); return route.abort();
      }
      if (request.method() !== 'GET') { writes.push(request.method() + ' ' + request.url()); return route.abort(); }
      if (url.origin !== base || url.search) { unexpected.push(request.url()); return route.abort(); }
      if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (!Object.hasOwn(fixtures, url.pathname)) { unexpected.push(request.url()); return route.abort(); }
      // A newly opened native tab can request its initial document before
      // Playwright has a Frame. It is still intercepted at the context level;
      // do not misattribute that document request to the originating page.
      let sourcePage = null;
      try { sourcePage = request.frame().page(); }
      catch { if (!request.isNavigationRequest()) unexpected.push('Frameless non-navigation request: ' + request.url()); }
      reads.push({path: url.pathname, page: sourcePage});
      return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[url.pathname]});
    });
    return context;
  }
  async function ready(page, path = parentPath) {
    await page.waitForFunction(path => {
      const workspace = document.querySelector('#debug-workspace');
      return customElements.get('sh-path-row') && workspace?.dataset.path === path &&
        workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true';
    }, path, {timeout: 5000});
  }
  const rows = page => page.locator('#wb-canvas sh-path-row.wb-child-row');
  const indexedRow = (page, index = 0) => page.locator('sh-path-row.wb-child-row[data-path=' + JSON.stringify(children[index]) + ']');
  const link = host => host.locator('a[part~="link"]');
  const toggle = host => host.locator('ui-button[part~="toggle"] button[part~="control"]');
  const preview = host => host.locator(':scope > .wb-child-preview');
  const pageReads = (page, path) => reads.filter(read => read.page === page && read.path === href(path)).length;
  async function settled(page) {
    await page.waitForFunction(() => {
      const roots = [document];
      for (let index = 0; index < roots.length; index++) for (const element of roots[index].querySelectorAll('*')) {
        if (element.localName === 'ui-reveal' && element.matches(':state(entering), :state(leaving)')) return false;
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
      return true;
    }, null, {timeout: 5000});
  }
  async function openPreview(page, index = 0, touch = false) {
    const host = indexedRow(page, index), before = pageReads(page, children[index]);
    if (touch) await toggle(host).tap(); else await toggle(host).click();
    await preview(host).locator('.wb-preview-open').waitFor();
    assert.equal(await host.evaluate(el => el.open), true);
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), parentPath);
    assert.equal(pageReads(page, children[index]), before + 1, 'first independent preview fetches exactly once');
    assert.equal(await preview(host).getAttribute('aria-busy'), null);
    return host;
  }
  async function geometry(page, coarse) {
    await settled(page);
    const dimensions = await rows(page).evaluateAll(elements => elements.slice(0, 6).map(host => {
      const anchor = host.shadowRoot.querySelector('[part~=link]');
      const button = host.shadowRoot.querySelector('[part~=toggle]').shadowRoot.querySelector('button');
      const rect = el => el.getBoundingClientRect().toJSON();
      const meta = host.querySelector('[slot=meta]');
      const label = host.shadowRoot.querySelector('[part~=label]');
      return {path: host.dataset.path, host: rect(host), link: rect(anchor), button: rect(button),
        label: rect(label), labelLineHeight: parseFloat(getComputedStyle(label).lineHeight),
        hostOverflow: host.scrollWidth - host.clientWidth, linkOverflow: anchor.scrollWidth - anchor.clientWidth,
        hasMeta: !!meta, metaText: meta?.textContent, linkStyle: {outline: getComputedStyle(anchor).outlineStyle, fontSize: getComputedStyle(anchor).fontSize}};
    }));
    for (const value of dimensions) {
      const minimum = coarse ? 44 : 28;
      assert.ok(value.link.height >= minimum - .6 && value.button.height >= minimum - .6,
        'actual native path and preview controls meet the shared ' + minimum + 'px minimum: ' + JSON.stringify(value));
      if (coarse) assert.ok(value.link.width >= 43.9 && value.button.width >= 43.9, 'both native touch targets have44px width');
      assert.ok(value.button.right <= value.link.left + .6 || value.link.right <= value.button.left + .6,
        'independent actions never overlap: ' + JSON.stringify(value));
      for (const action of [value.link, value.button]) assert.ok(action.left >= value.host.left - .6 && action.right <= value.host.right + .6,
        'actual actions remain inside the row: ' + JSON.stringify(value));
      assert.ok(value.hostOverflow <= 1 && value.linkOverflow <= 1, 'long labels and authored metadata wrap without horizontal overflow: ' + JSON.stringify(value));
      if (value.path === children[0]) assert.ok(value.label.height <= value.labelLineHeight + 1,
        'long metadata must not squeeze the short alpha-review name into a vertical word: ' + JSON.stringify(value));
      if (!coarse && value.path === children[3]) assert.ok(value.link.height <= 28.6, 'plain fine-pointer rows retain exactly28px rhythm');
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'document fits the viewport');
    assert.equal(await indexedRow(page).locator('.wb-child-lede').textContent(), richLabel);
    assert.equal(await indexedRow(page).locator('.wb-child-description').textContent(), richDescription);
    assert.equal(await page.evaluate(() => window.__pathExecuted), undefined, 'authored markup-like text is never executed');
    return dimensions;
  }

  const primary = await createContext();
  try {
    const page = await primary.newPage(); activePage = page;
    await page.goto(base + href(parentPath)); await ready(page);
    assert.equal(await rows(page).count(), 60, 'only the first60 fixture paths mount initially');
    assert.equal(await indexedRow(page, 82).count(), 0);
    assert.equal(await indexedRow(page, 1).locator('a[part~=link]').getAttribute('href'), href(children[1]), 'native href retains exact encoded identity');
    const first = await openPreview(page);
    const readCount = pageReads(page, children[0]);
    await toggle(first).focus(); await toggle(first).press('Space');
    assert.equal(await first.evaluate(el => el.open), false); assert.equal(await preview(first).isVisible(), false);
    await toggle(first).press('Enter');
    await preview(first).locator('.wb-preview-open').waitFor();
    assert.equal(pageReads(page, children[0]), readCount, 'cached preview reopens without another read');
    const cachedFrames = await first.evaluate(async host => {
      const button = host.shadowRoot.querySelector('[part~=toggle]').shadowRoot.querySelector('button');
      const values = [];
      // Cached close/reopen only: time component settlement plus its next
      // paint opportunity, never a fetch or a fixed artificial sleep.
      for (let index = 0; index < 20; index++) {
        const desired = !host.open, start = performance.now();
        button.click(); await host.updateComplete;
        await new Promise(resolve => requestAnimationFrame(resolve));
        const region = host.shadowRoot.querySelector('[part~=preview]');
        const content = host.querySelector('[slot=preview]');
        values.push({milliseconds: performance.now() - start, desired, open: host.open,
          regionVisible: region.getBoundingClientRect().height > 0, contentHidden: content.hidden});
      }
      return values;
    });
    assert.ok(cachedFrames.every(value => value.open === value.desired && value.regionVisible === value.desired && value.contentHidden !== value.desired),
      'each cached toggle reaches the actual desired visible state by the measured frame');
    assert.equal(pageReads(page, children[0]), readCount, 'ten cached close/reopen cycles perform no reads');
    const samples = cachedFrames.map(value => value.milliseconds).sort((a, b) => a - b);
    console.log(JSON.stringify({cachedPreviewInteraction: {samples: samples.length,
      medianMs: (samples[9] + samples[10]) / 2, p95Ms: samples[18], maxMs: samples.at(-1),
      measurement: 'native click to component update and next animation frame; excludes fetching; descriptive, not a CI speed guarantee'}}));
    const previewLink = preview(first).locator('.wb-preview-open'); await previewLink.focus();
    await page.evaluate(() => {
      const first = document.querySelector('sh-path-row.wb-child-row');
      window.__pathRowRetained = {rows: [...document.querySelectorAll('#wb-canvas sh-path-row.wb-child-row')],
        preview: first.querySelector('[slot=preview]'), content: first.querySelector('.wb-preview-open'), focused: document.activeElement};
      const more = [...document.querySelectorAll('.wb-children-section > ui-button')].find(button => button.textContent.trim() === 'Show more');
      if (!more) throw new Error('Missing production Show more action');
      more.click();
    });
    assert.equal(await rows(page).count(), 83, 'Show more appends exactly23 remaining paths');
    assert.equal(await page.getByRole('button', {name: 'Show more child paths', exact: true}).isVisible(), false);
    assert.equal(await page.evaluate(() => {
      const kept = window.__pathRowRetained, first = document.querySelector('sh-path-row.wb-child-row');
      return kept.rows.every((node, index) => node === document.querySelectorAll('#wb-canvas sh-path-row.wb-child-row')[index]) &&
        first.open && first.querySelector('[slot=preview]') === kept.preview && first.querySelector('.wb-preview-open') === kept.content &&
        document.activeElement === kept.focused && kept.focused.isConnected;
    }), true, 'appending preserves existing row, preview, child node, open state and current keyboard focus');
    assert.equal(pageReads(page, children[0]), readCount, 'pagination never refetches an open preview');
    assert.deepEqual(await rows(page).evaluateAll(elements => elements.map(el => el.dataset.path)), children, 'all83 names remain accessible in exact fixture order');
    await geometry(page, false);

    const destination = indexedRow(page, 1);
    for (const gesture of ['Meta', 'middle']) {
      await link(destination).scrollIntoViewIfNeeded();
      const originalURL = page.url(), ownReads = pageReads(page, children[1]);
      // Native Cmd/middle navigation may open an independent background tab
      // without an opener-page popup event. A real new context page is required.
      const opened = primary.waitForEvent('page', {timeout: 5000});
      if (gesture === 'Meta') await link(destination).click({modifiers: ['Meta']});
      else await link(destination).click({button: 'middle'});
      const popup = await opened;
      try {
        await ready(popup, children[1]);
        assert.equal(popup.url(), base + href(children[1]));
        assert.equal(page.url(), originalURL, gesture + ' preserves current browser location');
        assert.equal(await destination.evaluate(el => el.open), false, gesture + ' does not open preview');
        assert.equal(pageReads(page, children[1]), ownReads, gesture + ' does not route/fetch in current page');
      } finally { await popup.close(); }
    }
    await link(destination).focus(); await link(destination).press('Enter'); await ready(page, children[1]);
    assert.equal(await page.locator('.wb-document-title').evaluate(el => document.activeElement === el), true,
      'plain keyboard navigation focuses the newly opened document');
    assert.equal(await page.locator('.wb-document-title').textContent(), children[1].split('/').at(-1));
    assert.equal(pageReads(page, children[1]), 1, 'plain link activation routes through the production loader exactly once');

    const probes = [
      ['GET', 'http://foreign-path-row-fixture.invalid/blocked'], ['GET', base + '/debug/unknown-fixture'],
      ['GET', base + '/debug/paths?not-allowed=1'], ['POST', base + '/debug/paths'],
    ];
    for (const [method, url] of probes) policyProbeTargets.add(method + ' ' + url);
    const policyResults = await page.evaluate(async probes => Promise.all(probes.map(async ([method, url]) => {
      try { await fetch(url, {method}); return 'allowed'; }
      catch { return 'blocked'; }
    })), probes);
    assert.deepEqual(policyResults, ['blocked', 'blocked', 'blocked', 'blocked']);
    assert.equal(deniedProbes.length, 4);
    assert.equal(policyProbeTargets.size, 0);
    console.log('PASS:83 exact fixture paths;60+23 append preserves DOM/focus/open preview; lazy/cache; Enter/Meta/middle native behavior; inert request policy.');
  } catch (error) {
    await activePage.screenshot({path: '/private/tmp/shrine-path-rows-failure.png'}).catch(() => {});
    throw error;
  } finally { await primary.close(); }

  for (const specimen of [
    {width: 1440, height: 960, theme: 'light'}, {width: 1440, height: 960, theme: 'dark'},
    {width: 1024, height: 900, theme: 'light', inspector: true}, {width: 768, height: 1000, theme: 'light'},
    {width: 390, height: 844, theme: 'light'}, {width: 390, height: 844, theme: 'dark', coarse: true},
  ]) {
    const context = await createContext({viewport: {width: specimen.width, height: specimen.height}, colorScheme: specimen.theme,
      hasTouch: !!specimen.coarse, isMobile: !!specimen.coarse});
    try {
      const page = await context.newPage(); activePage = page;
      await page.goto(base + href(parentPath)); await ready(page);
      assert.equal(await page.evaluate(() => matchMedia('(pointer: coarse)').matches), !!specimen.coarse);
      if (specimen.inspector) {
        await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
        await page.locator('.wb-inspector').waitFor({state: 'visible'});
      }
      await geometry(page, !!specimen.coarse);
      await openPreview(page, 0, !!specimen.coarse);
      await geometry(page, !!specimen.coarse);
      const first = indexedRow(page);
      await preview(first).scrollIntoViewIfNeeded(); await settled(page);
      const bound = await first.evaluate(host => {
        const link = host.shadowRoot.querySelector('[part~=link]').getBoundingClientRect();
        const region = host.shadowRoot.querySelector('[part~=preview]').getBoundingClientRect();
        const content = host.querySelector('[slot=preview]').getBoundingClientRect();
        return {link: link.toJSON(), region: region.toJSON(), content: content.toJSON()};
      });
      assert.ok(bound.region.height > 0 && bound.region.top >= bound.link.bottom - .6 && bound.content.height > 0,
        'settled expanded preview is actually visible below its navigation row: ' + JSON.stringify(bound));
      const path = '/private/tmp/shrine-path-rows-' + specimen.theme + '-' + specimen.width + '-' + (specimen.coarse ? 'coarse' : 'fine') + (specimen.inspector ? '-inspector' : '') + '.png';
      await page.screenshot({path}); screenshots.push(path);
    } catch (error) {
      await activePage.screenshot({path: '/private/tmp/shrine-path-rows-failure.png'}).catch(() => {});
      throw error;
    } finally { await context.close(); }
  }
  assert.deepEqual(writes, [], 'no non-GET production requests');
  assert.deepEqual(unexpected, [], 'every production URL was an exact inert fixture or local asset');
  assert.deepEqual(errors, [], 'no browser page errors');
  console.log('PASS: light/dark1440,1024 inspector,768,390 fine/coarse; real28/44px controls, no overlap/overflow, exact authored metadata.');
  console.log(JSON.stringify({screenshots, fixtureReads: reads.length, liveReads: 0, allowedWrites: 0, rejectedPolicyProbes: deniedProbes.length}, null, 2));
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-path-rows-failure.png'}).catch(() => {});
  console.error(JSON.stringify({writes, unexpected, errors, reads: reads.map(read => read.path), screenshots, deniedProbes}, null, 2));
  throw error;
} finally { await browser.close(); }
