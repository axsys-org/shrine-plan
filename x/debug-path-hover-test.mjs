// Hover/focus path previews using a mandatory saved real document shell.
// Every namespace answer is an explicit inert fixture, never live Grove data.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live requests are forbidden');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-path-hover-fixture.invalid';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const assetHashes = Object.fromEntries([...assets].map(([path, asset]) => [path, createHash('sha256').update(asset.body).digest('hex')]));
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const paths = {main: '/app', alpha: '/app/alpha', beta: '/app/beta', slow: '/app/slow',
  broken: '/app/broken', reserved: '/app/λ #?%&', slot: '/sys/req', case: '/h/y/2/1/app', log: '/log'};
const children = {'/': ['/app', '/sys'], '/app': [paths.alpha, paths.beta, paths.slow, paths.broken, paths.reserved],
  '/sys': [paths.slot], [paths.alpha]: ['/app/alpha/child']};
const prompt = path => 'Test-owned request at ' + path;
const longHelp = 'Test-owned authored lore. '.repeat(50) + 'LORE_TAIL_λ';
const longValue = 'Test-owned exact answer. '.repeat(60) + 'VALUE_TAIL_λ';
const reads = [], unexpected = [], errors = [], screenshots = [], checks = [], canceled = [];
const held = new Map(), failures = new Set();
const browser = await chromium.launch();
const contexts = [];
let fixtures = Object.freeze({}), activePage, passed = false;
function hold(path) {
  assert.equal(held.has(path), false);
  let release;
  const promise = new Promise(resolve => { release = resolve; });
  const gate = {promise, release, requested: false}; held.set(path, gate);
  return {release() { held.delete(path); release(); }, async started(page) {
    const deadline = Date.now() + 5000;
    while (!gate.requested && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(gate.requested, true, 'the intended held fixture read starts');
  }};
}
async function newContext(options = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, ...options});
  contexts.push(context); context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
  await context.addInitScript(({base, paths}) => {
    if (typeof ServiceWorkerContainer !== 'undefined') Object.defineProperty(ServiceWorkerContainer.prototype, 'register', {
      configurable: true, value() { return Promise.reject(new Error('Hover fixture forbids service workers')); },
    });
    window.fixtureClipboard = [];
    Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
      writeText: async value => { window.fixtureClipboard.push(value); },
    }});
    const execCommand = document.execCommand.bind(document);
    document.execCommand = (command, ...args) => {
      if (/^copy$/i.test(command)) throw new Error('Native clipboard access is forbidden by the isolated fixture');
      return execCommand(command, ...args);
    };
    if (location.origin !== base || sessionStorage.getItem('hover-fixture-seeded')) return;
    localStorage.setItem('shrine-debug.v1.saved', JSON.stringify([paths.alpha, paths.reserved, paths.log]));
    localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: true, recent: true, tree: true, root: '/', expanded: ['/', '/app']}));
    sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: [paths.beta, paths.main], pages: [null, null], cursor: 1}));
    sessionStorage.setItem('hover-fixture-seeded', 'true');
  }, {base, paths});
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET' || url.origin !== base || url.search || url.hash) {
      unexpected.push({url: request.url(), method: request.method()}); return route.abort();
    }
    if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
    if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
    if (!Object.hasOwn(fixtures, url.pathname)) { unexpected.push({url: request.url()}); return route.abort(); }
    let owner = null;
    try { owner = request.frame().page(); } catch { if (!request.isNavigationRequest()) unexpected.push({url: request.url(), reason: 'unowned read'}); }
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/';
    reads.push({path, at: Date.now(), owner});
    if (held.has(path)) { const gate = held.get(path); gate.requested = true; await gate.promise; }
    if (failures.has(path)) return route.fulfill({status: 503, contentType: 'text/plain', body: 'Test-owned unavailable preview'}).catch(() => {});
    return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[url.pathname]}).catch(() => {});
  });
  context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
  context.on('requestfailed', request => canceled.push({url: request.url(), error: request.failure()?.errorText}));
  return context;
}
const popup = page => page.locator('ui-preview-card#wb-path-preview');
const popupSurface = page => popup(page).locator('[part~="popup"]');
const row = (page, path) => page.locator('sh-path-row.wb-child-row[data-path=' + JSON.stringify(path) + ']');
const rowLink = (page, path) => row(page, path).locator('a[part~="link"]');
const treeItem = (page, path) => page.locator('#debug-path-tree ui-tree-item[data-path=' + JSON.stringify(path) + ']');
const treeLabel = (page, path) => treeItem(page, path).locator(':scope > ui-path');
const savedLink = (page, path) => page.locator('#debug-saved .debug-page-row[data-path=' + JSON.stringify(path) + ']').getByRole('link');
const recentLink = (page, path) => page.locator('#debug-history .debug-page-row[data-path=' + JSON.stringify(path) + ']').getByRole('link');
const countReads = (page, path) => reads.filter(read => read.owner === page && read.path === path).length;
async function ready(page, path = paths.main) {
  await page.waitForFunction(path => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true' &&
      customElements.get('ui-preview-card') && document.querySelector('#wb-path-preview');
  }, path, {timeout: 5000});
}
async function settle(page) {
  await page.waitForFunction(() => {
    const roots = [document];
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      if (element.matches('ui-reveal:state(entering), ui-reveal:state(exiting)')) return false;
      if (element.shadowRoot) roots.push(element.shadowRoot);
    }
    return true;
  }, null, {timeout: 5000});
}
async function start(page) {
  activePage = page; await page.goto(base + href(paths.main)); await ready(page); await settle(page);
  await treeLabel(page, paths.alpha).waitFor({state: 'attached'});
  assert.equal(await popup(page).count(), 1, 'the entire application has one actual Mash preview card');
  assert.equal(await popup(page).getAttribute('trigger'), 'manual');
}
async function openPreview(page, target, path, {keyboard = false} = {}) {
  activePage = page;
  if (keyboard) { await page.keyboard.press('Tab'); await target.focus(); }
  else await target.hover();
  await page.waitForFunction(({path, text}) => {
    const card = document.querySelector('#wb-path-preview');
    return card?.open && card.matches(':state(active)') && card.dataset.readState === 'ready' && card.dataset.path === path &&
      card.querySelector('sh-myth[variant=preview]') && card.textContent.includes(text);
  }, {path, text: prompt(path)}, {timeout: 5000});
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), paths.main, 'hover/focus is not navigation');
  assert.equal(await page.evaluate(() => window.hoverFixtureExecuted), undefined, 'authored preview text never executes');
  assert.equal(await popup(page).locator('img,script').count(), 0, 'untrusted value text never becomes executable markup');
  assert.equal(await popup(page).locator('sh-myth > sh-limb').count(), 3, 'record previews show at most the first three nonmetadata slots');
  assert.equal(await popup(page).locator('.wb-hover-value').first().textContent(), prompt(path), 'authored slot text is retained');
  assert.equal(await popup(page).getByRole('link', {name: 'Open ' + path, exact: true}).getAttribute('href'), base + href(path));
}
async function closePreview(page) {
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => {
    const card = document.querySelector('#wb-path-preview');
    return card && !card.open && !card.matches(':state(present)');
  }, null, {timeout: 5000});
  // Escape suppresses the invoker until a genuine pointer exit. The old fixed
  // (900,900) point left narrow browser viewports instead of another document
  // surface, and could race the outgoing popup. Use a real, verified blank point.
  const point = await page.evaluate(() => {
    const x = innerWidth - 8, y = innerHeight - 8;
    let element = document.elementFromPoint(x, y);
    while (element?.shadowRoot?.elementFromPoint(x, y) && element.shadowRoot.elementFromPoint(x, y) !== element)
      element = element.shadowRoot.elementFromPoint(x, y);
    for (let node = element; node; node = node.assignedSlot || node.parentNode || node.host)
      if (node instanceof Element && node.matches('a[href],ui-link[href],ui-path,ui-tree-item,[data-inspect],[data-path-target]'))
        throw new Error('Fixture exit point is a namespace destination');
    if (!element) throw new Error('Fixture exit point is outside the document');
    return {x, y};
  });
  await page.mouse.move(point.x, point.y);
}
// These waits test declared intent/grace periods, not asynchronous readiness.
const beyondIntent = page => page.waitForTimeout(390);
const beyondGrace = page => page.waitForTimeout(230);
async function isClosed(page) { assert.equal(await popup(page).evaluate(element => element.open), false); }
async function showSidebar(page) {
  if (!await page.locator('#debug-workspace').evaluate(element => element.sidebarOpen))
    await page.getByRole('button', {name: 'Toggle sidebar', exact: true}).click();
  await settle(page);
}
async function popupBounds(page) {
  const result = await popupSurface(page).evaluate(element => {
    const box = element.getBoundingClientRect();
    return {left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height,
      clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, viewportWidth: innerWidth, viewportHeight: innerHeight};
  });
  assert.ok(result.width >= 160 && result.height > 40, 'preview has a useful nonempty visible surface');
  assert.ok(result.left >= -.5 && result.right <= result.viewportWidth + .5 && result.top >= -.5 && result.bottom <= result.viewportHeight + .5,
    'collision handling keeps the full popup inside the viewport: ' + JSON.stringify(result));
  assert.ok(result.scrollWidth <= result.clientWidth + 1, 'preview slots do not horizontally overflow');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
  return result;
}
async function capture(page, label) {
  await popupBounds(page); const path = '/private/tmp/shrine-path-hover-' + label + '.png';
  await page.screenshot({path}); screenshots.push(path);
}
try {
  const author = await browser.newPage();
  try {
    fixtures = Object.freeze(await author.evaluate(({shell, children, paths, longHelp, longValue}) => {
      const original = new DOMParser().parseFromString(shell, 'text/html');
      if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell anatomy is unsupported');
      const allPaths = [...new Set([...Object.keys(children), ...Object.values(children).flat(), ...Object.values(paths)])];
      return Object.fromEntries(allPaths.map(path => {
        const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
        const title = 'Fixture ' + (path.split('/').at(-1) || 'root');
        Object.assign(workspace.dataset, {path, kind: 'record', writable: 'false', label: title, fixture: 'path-hover',
          description: 'Test-owned lore for ' + path + '.', descriptionSource: '/sys/help', renderUrl: '/ns' + path});
        for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
        const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
        for (const [key, text] of [['/sys/lede', title], ['/sys/help', path === paths.reserved ? longHelp : 'Test-owned lore for ' + path + '.'],
          ['/sys/req', 'Test-owned request at ' + path], ['/sys/res', path === paths.reserved ? longValue : 'Test-owned answer at ' + path],
          ['/payload', '<img src=x onerror="window.hoverFixtureExecuted=true">']]) {
          const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
          const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
          const pail = doc.createElement('sh-pail'); pail.textContent = text; limb.append(slot, pail); myth.append(limb);
        }
        for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
        const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
        for (const child of children[path] || []) {
          const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.dataset.kind = 'record';
          item.dataset.label = 'Fixture ' + child.split('/').at(-1); item.setAttribute('title', child.split('/').at(-1)); tree.append(item);
        }
        const inspector = workspace.querySelector('[slot=inspector]'); inspector.replaceChildren();
        const version = doc.createElement('ui-table'); version.setAttribute('label', 'version');
        for (const [key, value] of [['x_data', '2'], ['x_shape', '2'], ['y_data', '2'], ['y_shape', '3'], ['z_data', '0'], ['z_shape', '0'], ['top', '9'], ['state', 'live']]) {
          const row = doc.createElement('ui-table-row'), a = doc.createElement('ui-table-cell'), b = doc.createElement('ui-table-cell');
          a.textContent = '/' + key; b.textContent = value; row.append(a, b); version.append(row);
        }
        inspector.append(version); doc.querySelector('#debug-activity')?.replaceChildren();
        const url = '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
        return [url, '<!doctype html>' + doc.documentElement.outerHTML];
      }));
    }, {shell, children, paths, longHelp, longValue}));
  } finally { await author.close(); }

  // The production event/delay contract is intentionally exercised below;
  // no synthetic path annotations or replacement popup are added by tests.
  const context = await newContext(), page = await context.newPage(); await start(page);
  assert.equal(await popup(page).evaluate(element => element.open), false);
  assert.equal(countReads(page, paths.alpha), 0); assert.equal(countReads(page, paths.beta), 0);
  const beforeTransient = reads.length;
  await rowLink(page, paths.slow).hover(); await page.waitForTimeout(70); await page.mouse.move(900, 900);
  await beyondIntent(page); await isClosed(page);
  assert.equal(reads.length, beforeTransient, 'a transient pointer before320ms starts no preview read');
  await row(page, paths.slow).locator('ui-button[part~="toggle"] button').hover();
  await beyondIntent(page); await isClosed(page);
  assert.equal(reads.length, beforeTransient, 'explicit row disclosure is not mistaken for its path');
  await page.mouse.move(900, 900);
  const current = page.locator('ui-link.wb-path-ancestor[href="/debug/app"]').getByRole('link');
  await openPreview(page, current, paths.main, {keyboard: true});
  assert.equal(countReads(page, paths.main), 1, 'initial current record is cached without a duplicate read');
  assert.equal(await current.evaluate(element => element.getRootNode().activeElement === element), true, 'preview does not steal keyboard focus');
  await page.keyboard.press('Escape'); await beyondIntent(page); await isClosed(page);
  assert.equal(await current.evaluate(element => element.getRootNode().activeElement === element), true, 'Escape keeps focus on the path');
  await page.getByRole('button', {name: 'Edit namespace path', exact: true}).focus();
  await page.mouse.move(900, 900);
  checks.push('one manual Mash surface;320ms intent; nonpath controls excluded; current cache; keyboard/Escape focus');

  await page.evaluate(() => {
    window.hoverRetained = {tree: document.querySelector('#debug-path-tree'),
      items: [...document.querySelectorAll('#debug-path-tree ui-tree-item')],
      rows: [...document.querySelectorAll('sh-path-row.wb-child-row')],
      filter: document.querySelector('#debug-filter'), filterValue: document.querySelector('#debug-filter').value,
      expanded: [...document.querySelectorAll('#debug-path-tree ui-tree-item')].map(node => node.expanded),
      previews: [...document.querySelectorAll('#debug-path-tree ui-tree-item')].map(node => node.previewOpen),
      titles: [...document.querySelectorAll('#debug-path-tree ui-tree-item')].map(node => node.getAttribute('title'))};
  });
  const startedAt = Date.now();
  await openPreview(page, savedLink(page, paths.alpha), paths.alpha);
  assert.equal(countReads(page, paths.alpha), 1);
  const firstAlphaRead = reads.find(read => read.owner === page && read.path === paths.alpha);
  assert.ok(firstAlphaRead.at - startedAt >= 290, 'fetch follows deliberate320ms hover intent');
  const bounds = await popupBounds(page);
  const anchor = await popup(page).evaluate(card => card.anchorElement.getBoundingClientRect().toJSON());
  assert.ok(bounds.left >= anchor.right + 7 && Math.abs(bounds.top - anchor.top) < 2, 'sidebar preview opens to the right, aligned at its actual anchor top');
  const destination = await popupSurface(page).boundingBox();
  await page.mouse.move(destination.x + destination.width / 2, destination.y + Math.min(40, destination.height / 2), {steps: 5});
  await beyondGrace(page);
  assert.equal(await popup(page).evaluate(element => element.open), true, 'crossing the gap into the popup keeps it available');
  assert.equal(await popup(page).getAttribute('data-path'), paths.alpha, 'hovering record content never recursively replaces the preview');
  await capture(page, 'sidebar-right-desktop');
  const beforeNestedMenu = reads.length;
  await popup(page).getByRole('link', {name: 'Open ' + paths.alpha, exact: true}).click({button: 'right'});
  const nestedMenu = page.locator('ui-context-menu#wb-path-menu');
  await nestedMenu.getByRole('menuitem', {name: 'Copy link', exact: true}).waitFor();
  assert.equal(await popup(page).evaluate(element => element.open), true, 'right-clicking inside the preview does not destroy the menu invoker');
  await nestedMenu.getByRole('menuitem', {name: 'Copy link', exact: true}).click();
  assert.deepEqual(await page.evaluate(() => window.fixtureClipboard), [base + href(paths.alpha)], 'a context action inside the popup copies its own exact destination');
  assert.equal(reads.length, beforeNestedMenu, 'nested context actions do not start another record read');
  await closePreview(page);
  await openPreview(page, treeLabel(page, paths.alpha), paths.alpha);
  assert.equal(countReads(page, paths.alpha), 1, 'the same record snapshot is reused across Saved and tree paths');
  const treePopup = await popupBounds(page);
  const bookmark = await treeItem(page, paths.alpha).locator(':scope > .debug-bookmark-toggle button[part=control]').boundingBox();
  assert.ok(bookmark && bookmark.width > 0 && bookmark.height > 0, 'the sibling bookmark has a real native hit target');
  assert.ok(treePopup.left >= bookmark.x + bookmark.width + 7,
    'the tree popup clears the entire sibling bookmark lane, not only the row label');
  await page.mouse.move(bookmark.x + bookmark.width / 2, bookmark.y + bookmark.height / 2, {steps: 3});
  await page.mouse.move(treePopup.left + 20, treePopup.top + 20, {steps: 3});
  await beyondGrace(page);
  assert.equal(await popup(page).evaluate(element => element.open), true, 'crossing the bookmark lane and gap into the tree popup retains the preview');
  assert.equal(countReads(page, paths.alpha), 1, 'the bookmark-lane pointer bridge performs no additional read');
  await capture(page, 'tree-bookmark-bridge');
  await closePreview(page);
  const retained = await page.evaluate(() => {
    const kept = window.hoverRetained, items = [...document.querySelectorAll('#debug-path-tree ui-tree-item')];
    return kept.tree === document.querySelector('#debug-path-tree') && kept.filter === document.querySelector('#debug-filter') &&
      kept.filterValue === document.querySelector('#debug-filter').value && kept.items.every((node, index) => node === items[index] &&
      node.expanded === kept.expanded[index] && node.previewOpen === kept.previews[index] && node.getAttribute('title') === kept.titles[index]) &&
      kept.rows.every((node, index) => node === document.querySelectorAll('sh-path-row.wb-child-row')[index]);
  });
  assert.equal(retained, true, 'hover never reparents the tree or mutates its hierarchy/preview/filter state');
  checks.push('right-aligned rich myth; pointer bridge; cross-surface cache; authored text safety and retained tree state');

  // A snapshot loaded by the existing inline preview is reused by hover too.
  await row(page, paths.beta).locator('ui-button[part~="toggle"] button').click();
  await row(page, paths.beta).locator('.wb-child-preview .wb-preview-open').waitFor();
  const loadedBeta = countReads(page, paths.beta);
  await openPreview(page, recentLink(page, paths.beta), paths.beta);
  assert.equal(countReads(page, paths.beta), loadedBeta, 'actual readPreview snapshot events seed the shared hover cache');
  await closePreview(page);
  await openPreview(page, rowLink(page, paths.reserved), paths.reserved);
  assert.equal(countReads(page, paths.reserved), 1, 'Unicode/reserved identity is read as one canonical path');
  assert.equal(await popup(page).locator('.wb-hover-description').textContent(), longHelp, 'authored lore is clamped visually, not destructively truncated');
  assert.equal(await popup(page).locator('.wb-hover-value').nth(1).textContent(), longValue, 'long supplied slot text remains byte-for-byte in the preview DOM');
  for (const content of [popup(page).locator('.wb-hover-description'), popup(page).locator('.wb-hover-value').nth(1)]) {
    const box = await content.evaluate(element => ({height: element.getBoundingClientRect().height, line: parseFloat(getComputedStyle(element).lineHeight)}));
    assert.ok(box.height <= box.line * 3 + 1, 'a long excerpt stays within three visual lines');
  }
  assert.equal(await popup(page).locator('ui-scroll-area.wb-hover-scroll').count(), 1, 'bounded popup content uses Mash scrolling');
  await capture(page, 'reserved-long-slots');
  await closePreview(page);
  const definition = page.locator('#debug-main ui-button[data-inspect="/sys/req"]').first().getByRole('button');
  await openPreview(page, definition, paths.slot, {keyboard: true});
  assert.equal(await definition.evaluate(element => element.getRootNode().activeElement === element), true);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-inspector-path'), paths.main, 'hovering a slot definition does not open its inspector');
  await closePreview(page);
  await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  const historical = page.locator('.wb-cases [data-care=y]').getByRole('link', {name: 'y case 2 of /app', exact: true});
  await openPreview(page, historical, paths.case);
  const caseBounds = await popupBounds(page), caseAnchor = await popup(page).evaluate(card => card.anchorElement.getBoundingClientRect().toJSON());
  assert.ok(caseBounds.right <= caseAnchor.left - 7, 'right-edge inspector path preview collision-flips left');
  await capture(page, 'inspector-left-desktop'); await closePreview(page);
  await page.locator('#debug-inspector-toggle').click();
  await openPreview(page, page.locator('ui-link.wb-path-ancestor[href="/debug"]').getByRole('link'), '/');
  assert.equal(countReads(page, '/'), 1, 'already-loaded namespace-root snapshot is reused');
  await closePreview(page);
  checks.push('loaded inline snapshot cache; native child/Recent/slot/locator/case targets; reserved identity; collision flip');

  failures.add(paths.broken);
  await rowLink(page, paths.broken).hover();
  await page.waitForFunction(() => document.querySelector('#wb-path-preview')?.dataset.readState === 'error', null, {timeout: 5000});
  assert.match(await popup(page).textContent(), /Could not preview this path/);
  failures.delete(paths.broken);
  await popup(page).getByRole('button', {name: 'Retry preview', exact: true}).click();
  await page.waitForFunction(text => document.querySelector('#wb-path-preview')?.dataset.readState === 'ready' &&
    document.querySelector('#wb-path-preview').textContent.includes(text), prompt(paths.broken), {timeout: 5000});
  assert.equal(countReads(page, paths.broken), 2); await closePreview(page);
  const slow = hold(paths.slow);
  await rowLink(page, paths.slow).hover(); await slow.started(page);
  await openPreview(page, rowLink(page, paths.alpha), paths.alpha);
  slow.release(); await beyondGrace(page);
  assert.equal(await popup(page).getAttribute('data-path'), paths.alpha, 'late response cannot overwrite the newly chosen record');
  assert.equal(await popup(page).getAttribute('data-read-state'), 'ready'); await closePreview(page);
  const canceledRead = hold(paths.slow);
  await rowLink(page, paths.slow).hover(); await canceledRead.started(page);
  await page.mouse.move(900, 900); await beyondGrace(page); await isClosed(page);
  canceledRead.release(); await beyondGrace(page); await isClosed(page);
  await savedLink(page, paths.log).hover();
  await page.waitForFunction(() => document.querySelector('#wb-path-preview')?.dataset.readState === 'unavailable', null, {timeout: 5000});
  assert.equal(countReads(page, paths.log), 0, 'uncached legacy log preview never causes an unbounded read');
  await closePreview(page);
  checks.push('error/retry; held response supersession and leave cancellation; legacy log no-read guard');

  const beforeMenu = reads.length;
  await savedLink(page, paths.reserved).click({button: 'right'});
  const menu = page.locator('ui-context-menu#wb-path-menu');
  await menu.getByRole('menuitem', {name: 'Copy path', exact: true}).waitFor();
  await beyondIntent(page); await isClosed(page);
  assert.equal(reads.length, beforeMenu, 'opening a path context menu suppresses hover intent and performs no read');
  await menu.getByRole('menuitem', {name: 'Copy path', exact: true}).click();
  assert.deepEqual(await page.evaluate(() => window.fixtureClipboard), [base + href(paths.alpha), paths.reserved], 'real Copy path action writes the exact canonical identity to the isolated clipboard stub');
  await savedLink(page, paths.reserved).click({button: 'right'});
  await menu.getByRole('menuitem', {name: 'Copy link', exact: true}).click();
  assert.deepEqual(await page.evaluate(() => window.fixtureClipboard), [base + href(paths.alpha), paths.reserved, base + href(paths.reserved)], 'Copy link preserves encoded Unicode/reserved characters');
  await beyondIntent(page); await isClosed(page); assert.equal(reads.length, beforeMenu);
  checks.push('real path context actions copy canonical identity without clipboard mutation or racing hover reads');

  // Navigation is tested on a separate context so earlier cache evidence is
  // unaffected; there is no fixture write or relabelled stale response.
  const navContext = await newContext(), navPage = await navContext.newPage(); await start(navPage);
  const navGate = hold(paths.slow); await rowLink(navPage, paths.slow).hover(); await navGate.started(navPage);
  await rowLink(navPage, paths.alpha).click(); await ready(navPage, paths.alpha);
  navGate.release(); await beyondIntent(navPage); await isClosed(navPage);
  assert.equal(countReads(navPage, '/app/alpha/child'), 0, 'a new row appearing beneath the stationary cursor is not fresh hover intent');
  assert.equal(await navPage.locator('#debug-workspace').getAttribute('data-path'), paths.alpha);
  await navContext.close(); checks.push('foreground navigation cancels pending hover and stale content');

  for (const width of [1440, 768, 390]) {
    const visualContext = await newContext({viewport: {width, height: 1000}}), visual = await visualContext.newPage();
    await start(visual); await showSidebar(visual);
    await openPreview(visual, savedLink(visual, paths.alpha), paths.alpha); await capture(visual, 'light-' + width);
    await visual.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
    await closePreview(visual); await openPreview(visual, savedLink(visual, paths.alpha), paths.alpha); await capture(visual, 'dark-' + width);
    await visualContext.close();
  }
  const touchContext = await newContext({viewport: {width: 390, height: 1000}, isMobile: true, hasTouch: true}), touch = await touchContext.newPage();
  await start(touch);
  assert.equal(await touch.evaluate(() => matchMedia('(pointer:coarse)').matches), true);
  const beforeTouch = reads.length;
  await rowLink(touch, paths.alpha).dispatchEvent('pointerover', {pointerType: 'touch', bubbles: true, composed: true});
  await beyondIntent(touch); await isClosed(touch); assert.equal(reads.length, beforeTouch, 'touch pointer contact starts no hover read');
  await rowLink(touch, paths.alpha).tap(); await ready(touch, paths.alpha); await beyondIntent(touch); await isClosed(touch);
  assert.equal(countReads(touch, paths.alpha), 1, 'touch retains native navigation without a second hover fetch');
  checks.push('1440/768/390 themed collision bounds; coarse touch never triggers hover reads');
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  assert.deepEqual(canceled, Array.from({length: 3}, () => ({url: base + href(paths.slow), error: 'net::ERR_ABORTED'})),
    'supersession, pointer leave and navigation each abort the actual held fetch; no unrelated request fails');
  passed = true;
  console.log(JSON.stringify({passed, checks, screenshots, liveReads: 0, writes: 0}, null, 2));
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-path-hover-failure.png'}).catch(() => {});
  console.error(JSON.stringify({passed: false, error: error.stack, checks, reads: reads.map(({owner, ...read}) => read), errors, unexpected}, null, 2));
  throw error;
} finally {
  for (const gate of held.values()) gate.release();
  for (const context of contexts) await context.close().catch(() => {});
  await browser.close();
  await writeFile('/private/tmp/shrine-path-hover-evidence.json', JSON.stringify({passed, checks, screenshots,
    reads: reads.map(({owner, ...read}) => read), canceled, errors, unexpected, assetHashes, liveReads: 0, writes: 0}, null, 2));
}
