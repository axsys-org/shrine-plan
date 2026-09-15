// Saved shell + test-owned namespace, never a running Shrine kernel or user profile.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; no live namespace fallback');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-bookmark-fixture.invalid';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const target = '/app/name #?%λ';
const targetHref = '/debug/app/' + encodeURIComponent('name #?%λ');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const versions = Object.fromEntries([...assets].map(([url, {body}]) => [url, createHash('sha256').update(body).digest('hex')]));
const reads = [], unexpected = [], errors = [], checks = [], screenshots = [], contexts = [];
let fixtures = {}, passed = false;
const browser = await chromium.launch();
async function settle(page) {
  await page.waitForFunction(() => {
    const roots = [document];
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      if (['ui-reveal', 'ui-tooltip'].includes(element.localName) && element.matches(':state(entering), :state(exiting)')) return false;
      if (element.shadowRoot) roots.push(element.shadowRoot);
    }
    return true;
  }, null, {timeout: 5000});
}
async function ready(page, coarse) {
  await page.waitForFunction(() => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === '/app' && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, null, {timeout: 5000});
  if (coarse) await page.locator('#debug-sidebar-toggle').tap();
  await page.waitForFunction(() => {
    const tree = document.querySelector('#debug-section-tree'), saved = document.querySelector('#debug-section-saved');
    return [tree, saved].every(section => section?.open && section.shadowRoot.querySelector('ui-reveal')?.matches(':state(active)')) &&
      [...document.querySelectorAll('#debug-path-tree ui-tree-item[expanded]')].every(item => item.dataset.readState === 'ready');
  }, null, {timeout: 5000});
}
async function topology(page) {
  return page.evaluate(() => ({path: document.querySelector('#debug-workspace').dataset.path,
    inspector: document.querySelector('#debug-workspace').inspectorOpen,
    rows: [...document.querySelectorAll('#debug-path-tree ui-tree-item')].map(item => ({path: item.dataset.path,
      expanded: item.expanded, current: item.current, selected: item.selected, preview: item.previewOpen})),
    previews: document.querySelectorAll('#debug-path-tree [slot=preview]').length}));
}
try {
  const author = await browser.newPage();
  fixtures = await author.evaluate(({shell, target}) => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw Error('Saved shell lacks debugger anatomy');
    return Object.fromEntries([['/', ['/app']], ['/app', [target, '/app/other']]].map(([path, children]) => {
      const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
      Object.assign(ws.dataset, {path, kind: 'record', writable: 'false', label: path === '/' ? 'Namespace' : 'Applications', fixture: 'bookmark', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch', 'description', 'descriptionSource']) delete ws.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, text] of [['/sys/lede', 'Applications'], ['/value', 'Authored namespace value']]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.title = key;
        const pail = doc.createElement('sh-pail'); pail.textContent = text; limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of children) { const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
        item.dataset.kind = 'record'; item.dataset.label = child.split('/').at(-1); item.title = item.dataset.label; tree.append(item); }
      return ['/debug' + (path === '/' ? '' : path), '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, {shell, target}); await author.close();
  for (const [theme, coarse] of [['light', false], ['dark', false], ['light', true], ['dark', true]]) {
    const context = await browser.newContext({viewport: {width: coarse ? 390 : 1440, height: 960}, colorScheme: theme,
      hasTouch: coarse, isMobile: coarse, reducedMotion: 'reduce'});
    contexts.push(context); context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    await context.addInitScript(base => {
      if (typeof ServiceWorkerContainer !== 'undefined') Object.defineProperty(ServiceWorkerContainer.prototype, 'register', {
        configurable: true, value() { return Promise.reject(Error('Fixture forbids service workers')); },
      });
      if (location.origin !== base || sessionStorage.getItem('bookmark-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: true, recent: false, tree: true, root: '/', expanded: ['/', '/app']}));
      sessionStorage.setItem('bookmark-fixture', 'seeded');
    }, base);
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET' || url.origin !== base || url.search || url.hash) { unexpected.push(request.method() + ' ' + request.url()); return route.abort(); }
      if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (!Object.hasOwn(fixtures, url.pathname)) { unexpected.push(request.url()); return route.abort(); }
      reads.push(url.pathname); return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[url.pathname]});
    });
    const page = await context.newPage(); await page.goto(base + '/debug/app'); await ready(page, coarse);
    const item = page.locator('#debug-path-tree ui-tree-item[data-path=' + JSON.stringify(target) + ']');
    const bookmark = item.locator(':scope > ui-button.debug-bookmark-toggle');
    const button = bookmark.locator('button[part=control]');
    const saved = page.locator('#debug-saved > .debug-page-row[data-path=' + JSON.stringify(target) + ']');
    const label = theme + (coarse ? '-390-touch' : '-1440-keyboard');
    const assertState = async state => {
      await page.waitForFunction(({target, state}) => {
        const item = [...document.querySelectorAll('#debug-path-tree ui-tree-item')].find(item => item.dataset.path === target);
        const button = item?.querySelector(':scope > .debug-bookmark-toggle');
        return button?.getAttribute('aria-pressed') === String(state) && button.shadowRoot.querySelector('button')?.getAttribute('aria-pressed') === String(state);
      }, {target, state}, {timeout: 5000});
      assert.equal(await bookmark.getAttribute('aria-label'), (state ? 'Unsave ' : 'Save ') + target);
      assert.equal(await button.getAttribute('aria-label'), (state ? 'Unsave ' : 'Save ') + target);
      assert.equal(await bookmark.evaluate(element => element.selected), state, 'Mash selected state reflects this exact saved path');
      assert.equal(await bookmark.locator('ui-icon').getAttribute('name'), 'object.bookmark');
      assert.equal(await bookmark.locator('ui-icon').getAttribute('data-icon-source'), 'Mash');
      assert.equal(await saved.count(), state ? 1 : 0);
      if (state) assert.equal(await saved.locator('ui-link a').getAttribute('href'), targetHref);
      assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('shrine-debug.v1.saved'))), state ? [target] : []);
    };
    const noInspect = async () => {
      assert.equal(await page.locator('#debug-path-tree .debug-preview-toggle').count(), 0);
      assert.equal(await page.locator('#debug-path-tree > ui-tree-item ui-button[slot=actions] ui-icon[name="object.code"]').count(), 0);
      assert.equal(await page.locator('#debug-path-tree ui-button[slot=actions]').evaluateAll(buttons => buttons.every(button =>
        button.classList.contains('debug-bookmark-toggle') && button.querySelector('ui-icon')?.getAttribute('name') === 'object.bookmark')), true,
      'every tree action is a bookmark, including the current row');
    };
    await assertState(false); await noInspect();
    if (!coarse) {
      // Stock row actions are initially pointer-inert. Keyboard focus reveals
      // the real action without intentionally entering the path-hover preview.
      await page.keyboard.press('Tab'); await button.focus(); await button.hover(); await noInspect();
    }
    const before = await topology(page), beforeReads = reads.length;
    const original = await item.elementHandle();
    if (coarse) await button.tap(); else { await page.keyboard.press('Tab'); await button.focus(); await button.press('Space'); }
    await assertState(true); await settle(page);
    assert.deepEqual(await topology(page), before, 'bookmark does not navigate, inspect, expand, select or preview');
    assert.equal(reads.length, beforeReads, 'bookmark does not read any namespace path');
    assert.equal(await item.evaluate((item, original) => item === original, original), true, 'saving retains the exact native tree row');
    if (coarse) { const box = await button.boundingBox(); assert.ok(box.width >= 44 && box.height >= 44, 'native bookmark touch target is44px'); }
    else assert.equal(await button.evaluate(element => element.matches(':focus-visible')), true, 'bookmark retains visible native keyboard focus');
    if (!coarse) {
      await page.locator('#debug-filter input').focus(); await page.mouse.move(700, 800);
      assert.equal(await item.evaluate(item => getComputedStyle(item.shadowRoot.querySelector('[part=actions]')).opacity), '1',
        'a saved non-current row keeps its bookmark visible without hover or row focus');
      await noInspect();
    }
    const screenshot = '/private/tmp/shrine-bookmark-' + label + '.png'; await page.screenshot({path: screenshot}); screenshots.push(screenshot);
    await original.dispose();
    // Same isolated profile, new document: startup must read the persisted bookmark.
    await page.reload(); await ready(page, coarse); await assertState(true); await noInspect();
    const reloadBefore = await topology(page), reloadReads = reads.length;
    if (coarse) await button.tap(); else { await button.focus(); await button.press('Enter'); }
    await assertState(false); await settle(page);
    assert.deepEqual(await topology(page), reloadBefore, 'unsave also leaves the namespace topology and main document unchanged');
    assert.equal(reads.length, reloadReads, 'unsave is entirely browser-local');
    await page.reload(); await ready(page, coarse); await assertState(false);
    if (!coarse) {
      const pointerBefore = await topology(page), pointerReads = reads.length;
      await button.focus(); await button.click(); await assertState(true);
      await button.click(); await assertState(false);
      assert.deepEqual(await topology(page), pointerBefore, 'actual native mouse activation is also bookmark-only');
      assert.equal(reads.length, pointerReads, 'native mouse save/unsave performs no namespace reads');
    }
    checks.push(label); await context.close();
  }
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); passed = true;
  console.log(JSON.stringify({passed, checks, fixtureReads: reads.length, liveReads: 0, writes: 0, versions, screenshots}, null, 2));
} finally {
  await Promise.all(contexts.map(context => context.close().catch(() => {}))); await browser.close();
  await writeFile('/private/tmp/shrine-bookmark-evidence.json', JSON.stringify({passed, checks, reads, unexpected, errors, versions, screenshots}, null, 2));
}
