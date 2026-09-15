// Mash action/toolbar integration. DEBUG_DOCUMENT is a mandatory saved shell.
// Built assets come from disk and every namespace read is a clearly
// browser-only fixture derived from that initial document. No /debug/log GET,
// namespace write, saved user state, or live operation is exercised here.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; this test never reads a live runtime.');
const base = 'http://debug-actions-fixture.invalid';
const root = fileURLToPath(new URL('..', import.meta.url));
const mash = process.env.MASH_ROOT || resolve(root, '../mash');
const registry = await readFile(resolve(mash, 'packages/components/src/icon/carbon-icons.generated.ts'), 'utf8');
const stockIcons = new Set([...registry.matchAll(/^\s+"([^"]+)": \{/gm)].map(match => match[1]));
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));

const initialHTML = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const browser = await chromium.launch();
try {
const context = await browser.newContext({viewport: {width: 1440, height: 1000}, serviceWorkers: 'block'});
const page = await context.newPage();
const errors = [], writes = [], unexpected = [], fixtureReads = [], focusFailures = [];
let heldPath = null, releaseRead = null, readGate = null, failNextRead = null;
await context.route('**/*', route => {unexpected.push(route.request().url()); return route.abort();});

const fixtures = await page.evaluate(html => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  const appChildren = [...original.querySelectorAll('#debug-children ui-tree-item[data-path]')]
    .map(el => el.dataset.path).filter(path => path.startsWith('/app/'));
  const children = {'/': ['/app', '/__actions__'], '/app': appChildren,
    '/__actions__': ['/__actions__/one', '/__actions__/two']};
  const paths = new Set(['/', '/app', '/__actions__', '/__actions__/one', '/__actions__/two', '/boot', '/sys']);
  for (const path of appChildren) {
    const pieces = path.split('/').filter(Boolean);
    for (let index = 1; index <= pieces.length; index++) paths.add('/' + pieces.slice(0, index).join('/'));
  }
  return Object.fromEntries([...paths].map(path => {
    if (path === '/app') return [path, html];
    const doc = original.cloneNode(true);
    const workspace = doc.querySelector('#debug-workspace');
    workspace.dataset.path = path;
    workspace.dataset.renderUrl = '/ns' + (path === '/' ? '' : path);
    workspace.dataset.label = 'Browser-only toolbar fixture';
    workspace.dataset.fixture = 'debug-actions';
    for (const limb of doc.querySelectorAll('#debug-main > section[aria-label=Record] > sh-myth > sh-limb')) {
      const key = limb.querySelector('sh-slot')?.getAttribute('title');
      if (key === '/sys/lede' || key === '/sys/help')
        limb.querySelector('sh-pail').textContent = 'Browser-only toolbar fixture';
    }
    const tree = doc.querySelector('#debug-children');
    tree.replaceChildren();
    for (const child of children[path] || []) {
      const item = doc.createElement('ui-tree-item');
      item.dataset.path = child;
      item.dataset.label = child.split('/').at(-1);
      item.setAttribute('title', item.dataset.label);
      tree.append(item);
    }
    const input = doc.querySelector('#debug-go input, #debug-go ui-input');
    input?.setAttribute('value', path);
    return [path, '<!doctype html>' + doc.documentElement.outerHTML];
  }));
}, initialHTML);

async function routeFixtures(route) {
  const request = route.request(), url = new URL(request.url());
  if (request.method() !== 'GET') {
    writes.push(request.method() + ' ' + request.url());
    return route.abort();
  }
  if (url.origin !== base || url.search) {unexpected.push(request.url()); return route.abort();}
  const asset = assets.get(url.pathname);
  if (asset) return route.fulfill({status: 200, ...asset});
  if (url.origin === base && /^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/';
    fixtureReads.push(path);
    if (heldPath === path && readGate) await readGate;
    if (failNextRead === path) {
      failNextRead = null;
      return route.fulfill({status: 503, contentType: 'text/plain', body: 'Browser-only action test read failure'});
    }
    if (Object.hasOwn(fixtures, path)) return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
  }
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url());
  return route.abort();
}
await context.route('**/*', routeFixtures);
page.on('pageerror', error => errors.push(error.message));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let index = 0; index < 100; index++) {
    if (await check()) return;
    await wait(25);
  }
  assert.fail(message);
}
const native = host => host.locator('button[part="control"]');
const focused = host => host.evaluate(el => document.activeElement === el && el.shadowRoot.activeElement?.matches('button'));
const css = (locator, property) => locator.evaluate((el, property) => getComputedStyle(el)[property], property);
async function ready(path) {
  await page.waitForFunction(path => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, path);
}
async function navigate(path) {
  if (!await page.locator('#debug-go').isVisible()) await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill(path);
  await page.locator('#debug-go input').press('Enter');
  await ready(path);
}
async function square(host, size) {
  const box = await native(host).boundingBox();
  assert.ok(box && Math.abs(box.width - size) < .6 && Math.abs(box.height - size) < .6,
    (await host.getAttribute('aria-label')) + ' has a ' + size + 'px square native target, got ' + JSON.stringify(box));
}
async function oneTabStop(toolbar, expected = 1) {
  await settled(() => toolbar.evaluate((el, expected) => [...el.querySelectorAll(':scope > ui-button')]
    .filter(button => button.tabIndex === 0).length === expected, expected), 'toolbar has exactly ' + expected + ' Tab stop(s)');
}
async function checkFocus(host, message) {
  // Accumulate these so a genuine focus regression does not hide the remaining
  // geometry/pointer checks in this isolated fixture run.
  await wait(100);
  if (await focused(host)) return;
  const active = await page.evaluate(() => ({tag: document.activeElement?.localName, id: document.activeElement?.id}));
  focusFailures.push(message + ': ' + JSON.stringify(active));
  console.error('FOCUS REGRESSION:', focusFailures.at(-1));
}
async function noOverflow(targetPage) {
  assert.ok(await targetPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page fits its viewport');
  for (const toolbar of await targetPage.locator('ui-toolbar').all()) {
    if (!await toolbar.isVisible()) continue;
    const bounds = await toolbar.locator(':scope > ui-button:visible').evaluateAll(buttons => buttons
      .filter(button => !button.hidden).map(button => button.shadowRoot.querySelector('button').getBoundingClientRect().toJSON()));
    for (let index = 1; index < bounds.length; index++)
      assert.ok(bounds[index - 1].right <= bounds[index].left + 1, 'adjacent toolbar hit targets do not overlap');
  }
}

try {
  await page.goto(base + '/debug/app'); await ready('/app');
  await page.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor();
  for (const [id, label] of [['debug-history-nav', 'Navigation history'], ['wb-header-actions', 'Workspace actions'], ['debug-tree-actions', 'Namespace tree actions']]) {
    const toolbar = page.locator('#' + id);
    assert.equal(await toolbar.evaluate(el => el.localName), 'ui-toolbar');
    assert.equal(await toolbar.getByRole('toolbar', {name: label, exact: true}).count(), 1);
  }
  assert.equal(await page.locator('#wb-activity-toggle').count(), 0, 'the removed journal shortcut is not recreated in the header');
  for (const id of ['debug-sidebar-toggle', 'debug-back', 'debug-forward', 'wb-refresh', 'debug-inspector-toggle'])
    await square(page.locator('#' + id), 28);
  for (const id of ['debug-tree-collapse', 'debug-tree-refresh', 'debug-save']) await square(page.locator('#' + id), 24);
  for (const host of await page.locator('sh-path-row [part="toggle"]:visible').all()) await square(host, 28);
  for (const host of await page.locator('.debug-bookmark-toggle:visible').all()) await square(host, 24);
  for (const host of await page.locator('ui-button.wb-icon-button').all()) {
    assert.equal(await host.getAttribute('icon-only'), '', 'icon actions use Mash geometry, not anonymous CSS squares');
    const label = await host.getAttribute('aria-label');
    assert.ok(label?.trim(), 'an icon-only action has an accessible name');
    assert.equal(await native(host).getAttribute('aria-label'), label, 'the real native button carries the name');
  }
  for (const glyph of await page.locator('ui-icon.wb-icon').all()) {
    assert.ok(stockIcons.has(await glyph.getAttribute('name')), 'every debugger glyph uses the stock Mash registry');
    assert.equal(await glyph.getAttribute('aria-hidden'), 'true');
    assert.equal(await glyph.evaluate(el => el.children.length), 0, 'application code does not override Mash glyphs');
    assert.equal(await glyph.locator('svg').count(), 1, 'the stock glyph renders without a missing-icon fallback');
  }
  await oneTabStop(page.locator('#debug-history-nav'), 0);
  await oneTabStop(page.locator('#wb-header-actions'));
  await oneTabStop(page.locator('#debug-tree-actions'));
  await noOverflow(page);
  console.log('PASS: native accessible names, stock Mash glyphs, 28/24px squares, labelled toolbars and initial Tab stops.');

  const actions = page.locator('#wb-header-actions');
  const refresh = page.locator('#wb-refresh'), inspector = page.locator('#debug-inspector-toggle');
  await refresh.focus(); await refresh.press('ArrowRight'); await settled(() => focused(inspector), 'ArrowRight moves to inspector');
  await refresh.press('End'); await settled(() => focused(inspector), 'End moves to the last enabled action');
  await inspector.press('Home'); await settled(() => focused(refresh), 'Home moves to the first enabled action');
  await refresh.press('ArrowLeft'); await settled(() => focused(inspector), 'the default Mash toolbar wraps arrow navigation');
  await inspector.press('Tab');
  assert.equal(await page.evaluate(() => Boolean(document.activeElement?.closest('#wb-header-actions'))), false, 'one Tab exits the composite instead of visiting every icon');
  await page.keyboard.press('Shift+Tab');
  await settled(() => focused(inspector), 'Shift+Tab returns to the retained roving action');
  const modifierResults = await native(inspector).evaluate(button => ['altKey', 'ctrlKey', 'metaKey', 'shiftKey'].map(modifier => {
    // Synthetic here deliberately avoids invoking OS/browser history shortcuts;
    // ordinary arrows above use trusted Playwright keyboard input.
    const event = new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true, composed: true, cancelable: true, [modifier]: true});
    button.dispatchEvent(event);
    return {modifier, prevented: event.defaultPrevented};
  }));
  assert.ok(modifierResults.every(result => !result.prevented), 'modified arrows retain their platform default: ' + JSON.stringify(modifierResults));
  await settled(() => focused(inspector), 'modified arrows do not move roving focus');

  await refresh.evaluate(el => { el.disabled = true; });
  await inspector.focus(); await inspector.press('ArrowRight'); await settled(() => focused(inspector), 'dynamically disabled actions are skipped');
  assert.equal(await native(refresh).isDisabled(), true);
  await refresh.evaluate(el => { el.disabled = false; el.hidden = true; });
  await inspector.focus(); await inspector.press('ArrowRight'); await settled(() => focused(inspector), 'dynamically hidden actions are skipped');
  await refresh.evaluate(el => { el.hidden = false; });
  await oneTabStop(actions);

  heldPath = '/app'; readGate = new Promise(resolve => { releaseRead = resolve; });
  await refresh.click();
  await settled(() => refresh.evaluate(el => el.loading), 'real refresh orchestration enters loading while its fixture response is held');
  assert.equal(await native(refresh).isDisabled(), true);
  assert.equal(await native(refresh).getAttribute('aria-busy'), 'true');
  await square(refresh, 28);
  assert.equal(await refresh.locator('[part="spinner"]').isVisible(), true);
  await inspector.focus(); await inspector.press('ArrowRight'); await settled(() => focused(inspector), 'loading actions leave the toolbar navigation set');
  releaseRead(); heldPath = null; readGate = null;
  await ready('/app');
  await settled(() => refresh.evaluate(el => !el.loading), 'refresh exits loading after its fixture response');
  await checkFocus(inspector, 'refresh completion must not steal deliberately moved focus');
  await oneTabStop(actions);

  for (const [activation, failure] of [['pointer', false], ['keyboard', true]]) {
    heldPath = '/app'; readGate = new Promise(resolve => { releaseRead = resolve; });
    failNextRead = failure ? '/app' : null;
    if (activation === 'pointer') await refresh.click();
    else { await refresh.focus(); await refresh.press('Enter'); }
    await settled(() => refresh.evaluate(el => el.loading), activation + ' refresh enters loading');
    releaseRead(); heldPath = null; readGate = null;
    await settled(() => refresh.evaluate(el => !el.loading), activation + ' refresh settles');
    await checkFocus(refresh, activation + ' refresh preserves focus after ' + (failure ? 'failure' : 'success'));
  }
  // Recover through the same real refresh handler after the deliberate fixture
  // error; every response remains an inert fixture.
  await refresh.click(); await ready('/app');
  await settled(() => refresh.evaluate(el => !el.loading), 'successful refresh recovers from the fixture error');
  console.log('PASS: arrow/Home/End/Tab contract, modifier preservation, and dynamic disabled/hidden/loading states.');

  await page.mouse.move(1, 1);
  const rest = await css(native(inspector), 'backgroundColor');
  const box = await native(inspector).boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  assert.equal(await inspector.evaluate(el => el.matches(':state(pressed)')), true);
  assert.notEqual(await css(native(inspector), 'backgroundColor'), rest, 'Mash provides visible press feedback');
  await page.mouse.up();
  assert.equal(await inspector.evaluate(el => el.matches(':state(pressed)')), false);
  assert.equal(await native(inspector).getAttribute('aria-expanded'), 'true');
  assert.equal(await page.locator('.wb-inspector').isVisible(), true);
  await inspector.click();
  assert.equal(await native(inspector).getAttribute('aria-expanded'), 'false');
  const save = page.locator('#debug-save');
  await save.click(); assert.equal(await native(save).getAttribute('aria-pressed'), 'true');
  await save.click(); assert.equal(await native(save).getAttribute('aria-pressed'), 'false');
  const bookmarkRow = page.locator('#debug-path-tree ui-tree-item[data-path="/__actions__"]');
  const bookmark = bookmarkRow.locator(':scope > .debug-bookmark-toggle');
  const rowExpanded = await bookmarkRow.evaluate(item => item.expanded);
  const beforeBookmarkReads = fixtureReads.length;
  await native(bookmark).focus(); await native(bookmark).press('Enter');
  await settled(async () => await native(bookmark).getAttribute('aria-pressed') === 'true', 'the noncurrent row is bookmarked');
  assert.equal(await bookmark.getAttribute('aria-label'), 'Unsave /__actions__');
  assert.equal(await page.locator('.debug-page-row[data-path="/__actions__"] > ui-link a').getAttribute('href'), '/debug/__actions__');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/app', 'bookmarking does not navigate');
  assert.equal(await bookmarkRow.evaluate(item => item.expanded), rowExpanded, 'bookmarking does not toggle hierarchy disclosure');
  assert.equal(await bookmarkRow.locator(':scope > [slot="preview"]').count(), 0, 'bookmarking does not create an inline preview');
  assert.equal(fixtureReads.length, beforeBookmarkReads, 'bookmarking does not read the namespace');
  await native(bookmark).press('Enter');
  await settled(async () => await native(bookmark).getAttribute('aria-pressed') === 'false', 'the same row can be unsaved');
  assert.equal(await bookmark.getAttribute('aria-label'), 'Save /__actions__');
  assert.equal(await page.locator('.debug-page-row[data-path="/__actions__"]').count(), 0);
  assert.equal(fixtureReads.length, beforeBookmarkReads, 'unsaving remains a local-only action');
  console.log('PASS: native pointer press, inspector disclosure, current-page save and exact noncurrent-row bookmark toggles.');

  await navigate('/__actions__/one'); await navigate('/__actions__/two');
  await page.locator('#debug-back').click(); await ready('/__actions__/one');
  const history = page.locator('#debug-history-nav'), back = page.locator('#debug-back'), forward = page.locator('#debug-forward');
  await checkFocus(back, 'Back retains focus after busy when it remains enabled');
  assert.equal(await native(back).isDisabled(), false); assert.equal(await native(forward).isDisabled(), false);
  await oneTabStop(history);
  await back.focus(); await back.press('ArrowRight'); await settled(() => focused(forward), 'enabled history controls share Mash arrow navigation');
  await forward.press('Home'); await settled(() => focused(back), 'history Home returns to Back');
  await back.press('End'); await settled(() => focused(forward), 'history End selects Forward');
  await back.click(); await ready('/app');
  assert.equal(await native(back).isDisabled(), true);
  await checkFocus(forward, 'Back at the history boundary moves focus to enabled Forward');
  await forward.press('Enter'); await ready('/__actions__/one');
  await checkFocus(forward, 'Forward retains focus after busy when it remains enabled');
  console.log('PASS: history enables dynamically and remains one keyboard composite (fixture navigation only).');

  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844]]) {
    await page.setViewportSize({width, height});
    await page.goto(base + '/debug/app'); await ready('/app');
    await page.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor({state: 'attached'});
    await noOverflow(page);
    await page.screenshot({path: '/private/tmp/shrine-actions-light-' + width + '.png', animations: 'disabled'});
  }
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto(base + '/debug/app'); await ready('/app');
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await refresh.focus();
  assert.equal(await native(refresh).evaluate(el => el.matches(':focus-visible')), true);
  assert.notEqual(await css(native(refresh), 'outlineStyle'), 'none', 'keyboard focus is visibly styled');
  await noOverflow(page);
  await page.screenshot({path: '/private/tmp/shrine-actions-dark-focus.png', animations: 'disabled'});

  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, serviceWorkers: 'block'});
  await touchContext.route('**/*', routeFixtures);
  const touch = await touchContext.newPage(); touch.on('pageerror', error => errors.push(error.message));
  async function mobileTreeGeometry() {
    return touch.locator('#debug-tree-actions').evaluate(actions => {
      const section = actions.closest('ui-accordion-item');
      const reveal = section.shadowRoot.querySelector('ui-reveal');
      const content = reveal.shadowRoot.querySelector('[part=content]');
      const measure = reveal.shadowRoot.querySelector('[part=measure]');
      const item = section.querySelector('ui-tree-item[data-path="/app"]');
      const bounds = content.getBoundingClientRect(), itemBounds = item?.getBoundingClientRect();
      return {
        visible: section.open && bounds.height > 0 && itemBounds?.height > 0 && itemBounds.top >= bounds.top && itemBounds.bottom <= bounds.bottom + 1,
        sectionOpen: section.open,
        presence: ['entering', 'active', 'exiting', 'present'].filter(state => reveal.matches(':state(' + state + ')')),
        section: section.getBoundingClientRect().toJSON(), content: bounds.toJSON(), item: itemBounds?.toJSON(),
        blockSize: content.style.blockSize, measureHeight: measure.scrollHeight,
      };
    });
  }
  async function visibleMobileTree(phase) {
    try {
      await settled(async () => (await mobileTreeGeometry()).visible, 'the mobile Tree body and current row are visibly inside the open disclosure after ' + phase);
    } catch (error) {
      console.error('Mobile disclosure geometry:', await mobileTreeGeometry());
      await touch.screenshot({path: '/private/tmp/shrine-actions-touch-disclosure-failure.png'});
      throw error;
    }
  }
  await touch.goto(base + '/debug/app');
  await touch.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  assert.equal(await touch.evaluate(() => matchMedia('(pointer: coarse)').matches), true);
  for (const host of await touch.locator('.wb-commandbar ui-button[icon-only]:visible').all()) await square(host, 44);
  await touch.getByRole('button', {name: 'Toggle sidebar', exact: true}).tap();
  await touch.locator('#debug-sidebar').waitFor();
  await touch.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor({state: 'attached'});
  await visibleMobileTree('opening an initially hidden sidebar');
  for (const host of await touch.locator('#debug-tree-actions ui-button[icon-only]').all()) await square(host, 44);
  await touch.locator('#debug-filter input').fill('app');
  await visibleMobileTree('filtering the loaded tree');
  const rootButton = await native(touch.locator('#debug-root-toggle')).boundingBox();
  const filter = await touch.locator('#debug-filter input').boundingBox();
  const clear = await native(touch.locator('#debug-filter-clear')).boundingBox();
  assert.ok(rootButton.x + rootButton.width <= filter.x + 1, 'coarse root action does not intercept the input');
  assert.ok(filter.x + filter.width <= clear.x + 1, 'coarse clear action does not intercept the input');
  await square(touch.locator('#debug-root-toggle'), 44); await square(touch.locator('#debug-filter-clear'), 44);
  await noOverflow(touch);
  await touch.screenshot({path: '/private/tmp/shrine-actions-touch-390.png', animations: 'disabled'});
  await touch.locator('#debug-filter-clear').tap();
  await touch.locator('#debug-save').tap();
  await touch.locator('#debug-saved .debug-page-row[data-path="/app"] > ui-link a').tap();
  await touch.setViewportSize({width: 1024, height: 844});
  await touch.locator('#debug-workspace').evaluate(el => { el.sidebarOpen = true; el.sidebarWidth = 192; });
  await touch.locator('#debug-tree-namespace').waitFor({state: 'visible'});
  const sidebarBounds = await touch.locator('#debug-sidebar').boundingBox();
  assert.ok(sidebarBounds.width <= 194, 'coarse root actions are checked at the actual minimum pane width');
  for (const host of await touch.locator('#debug-tree-toolbar ui-button[icon-only]:visible').all()) {
    await square(host, 44);
    const bounds = await native(host).boundingBox();
    assert.ok(bounds.x >= sidebarBounds.x && bounds.x + bounds.width <= sidebarBounds.x + sidebarBounds.width + 1,
      'a narrowed coarse sidebar contains ' + await host.getAttribute('aria-label'));
  }
  await noOverflow(touch);
  await touch.screenshot({path: '/private/tmp/shrine-actions-touch-narrow-root.png', animations: 'disabled'});
  await touchContext.close();
  assert.deepEqual(writes, []);
  assert.deepEqual(unexpected, []);
  assert.deepEqual(errors, []);
  console.log('PASS: 1440/768/390px, light/dark visible focus, coarse 44px targets, and non-overlapping composer controls.');
  assert.deepEqual(focusFailures, [], 'async native disabling must not discard or steal action focus');
  console.log('PASS: ' + fixtureReads.length + ' intercepted fixture GETs; zero live requests or mutations.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-actions-failure.png'});
  console.error('Action test context:', {url: page.url(), fixtureReads, writes, unexpected, errors});
  throw error;
} finally {
  releaseRead?.();
  await context.close();
}
} finally {
  await browser.close();
}
