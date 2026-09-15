// Delegated path actions over a mandatory saved shell. Every request is an
// exact inert fixture; clipboard APIs are mocked before any app script runs.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live access is forbidden');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-path-menu-fixture.invalid';
const child = '/paths/日本語 price?#%λ';
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const journal = '/debug/log?care=x&before=80&limit=20&epoch=90';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const reads = [], unexpected = [], writes = [], errors = [], screenshots = [];
let activePage;
const browser = await chromium.launch();
try {
  let fixtures;
  const author = await browser.newContext({serviceWorkers: 'block'});
  try {
    await author.route('**/*', route => { unexpected.push(route.request().url()); return route.abort(); });
    const page = await author.newPage();
    fixtures = await page.evaluate(({shell, child}) => {
      const original = new DOMParser().parseFromString(shell, 'text/html');
      if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Unexpected saved shell');
      const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
      return Object.fromEntries(['/', '/paths', child, '/definition'].map(path => {
        const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
        Object.assign(workspace.dataset, {path, kind: 'record', writable: 'false', label: 'Fixture ' + path,
          description: '', fixture: 'path-menu', renderUrl: '/ns' + path});
        for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
        const record = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); record.replaceChildren();
        for (const [key, value] of [['/sys/lede', 'Authored fixture ' + path], ['/definition', 'Exact fixture value'], ['/reference', child]]) {
          const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
          const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
          const pail = doc.createElement('sh-pail');
          if (key === '/reference') { const a = doc.createElement('a'); a.href = href(child); a.textContent = child; pail.append(a); }
          else pail.textContent = value;
          limb.append(slot, pail); record.append(limb);
        }
        for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
        const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
        for (const target of path === '/' ? ['/paths'] : path === '/paths' ? [child] : []) {
          const item = doc.createElement('ui-tree-item'); Object.assign(item.dataset, {path: target, kind: 'record', label: 'Fixture ' + target});
          item.title = target.split('/').at(-1); tree.append(item);
        }
        doc.querySelector('#debug-workspace [slot=inspector]')?.replaceChildren();
        doc.querySelector('#debug-activity')?.replaceChildren();
        doc.querySelector('#debug-go ui-input')?.setAttribute('value', path);
        return [href(path), '<!doctype html>' + doc.documentElement.outerHTML];
      }));
    }, {shell, child});
  } finally { await author.close(); }

  async function context(options = {}) {
    const result = await browser.newContext({viewport: {width: 1440, height: 960}, serviceWorkers: 'block', ...options});
    result.setDefaultTimeout(5000); result.setDefaultNavigationTimeout(5000);
    result.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    await result.addInitScript(({base, child}) => {
      if (location.origin !== base) return;
      window.__copies = []; window.__clipboardMode = 'success';
      Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: async value => {
        window.__copies.push(value);
        if (window.__clipboardMode === 'failure') throw new DOMException('Fixture denied clipboard', 'NotAllowedError');
        if (window.__clipboardMode === 'pending') await new Promise(resolve => {window.__finishCopy = resolve;});
      }}});
      document.execCommand = command => {throw new Error('System clipboard fallback is forbidden: ' + command);};
      if (sessionStorage.getItem('path-menu-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', JSON.stringify([child]));
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: true, recent: true, tree: false, root: '/', expanded: []}));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: [child, '/paths'], pages: [null, null], cursor: 1}));
      sessionStorage.setItem('path-menu-fixture', 'seeded');
    }, {base, child});
    await result.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET') {writes.push(request.method() + ' ' + request.url()); return route.abort();}
      if (url.origin !== base || url.search) {unexpected.push(request.url()); return route.abort();}
      if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (!Object.hasOwn(fixtures, url.pathname)) {unexpected.push(request.url()); return route.abort();}
      reads.push(url.pathname); return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[url.pathname]});
    });
    return result;
  }
  async function ready(page, path = '/paths') {
    await page.waitForFunction(path => {
      const workspace = document.querySelector('#debug-workspace');
      return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' &&
        workspace.getAttribute('aria-busy') !== 'true' && typeof document.querySelector('#wb-path-menu')?.showAt === 'function';
    }, path);
  }
  const menu = page => page.locator('#wb-path-menu');
  async function closed(page) {await page.waitForFunction(() => !document.querySelector('#wb-path-menu').open);}
  async function opened(page) {
    await page.waitForFunction(() => {
      const menu = document.querySelector('#wb-path-menu');
      return menu?.open && menu.matches(':state(active)');
    });
    await menu(page).evaluate(element => element.updateComplete);
    assert.equal(await menu(page).getByRole('menuitem').count(), 2);
  }
  async function pointer(page, target) {
    const count = reads.length;
    await target.click({button: 'right'}); await opened(page);
    assert.equal(reads.length, count, 'right-clicking a path performs no namespace read');
  }
  async function copy(page, kind, expected) {
    const before = await page.evaluate(() => window.__copies.length);
    await menu(page).getByRole('menuitem', {name: 'Copy ' + kind, exact: true}).click();
    await closed(page);
    await page.waitForFunction(count => window.__copies.length === count, before + 1);
    assert.equal(await page.evaluate(() => window.__copies.at(-1)), expected);
    await page.waitForFunction(() => /copied\.$/.test(document.querySelector('#wb-feedback')?.textContent || ''));
  }
  async function geometry(page, coarse) {
    const result = await menu(page).evaluate(element => {
      const box = element.shadowRoot.querySelector('[part=popup]').getBoundingClientRect();
      return {box: {left: box.left, top: box.top, right: box.right, bottom: box.bottom},
        heights: [...element.querySelectorAll('ui-menu-item')].map(item => item.shadowRoot.querySelector('[part=control]').getBoundingClientRect().height),
        compact: parseFloat(getComputedStyle(element).getPropertyValue('--layout-menu-row-compact')),
        width: innerWidth, height: innerHeight};
    });
    assert.ok(result.box.left >= -1 && result.box.top >= -1 && result.box.right <= result.width + 1 && result.box.bottom <= result.height + 1, 'shared collision positioning keeps the popup in the viewport');
    assert.ok(result.box.right - result.box.left < 150, 'two short copy commands fit their content instead of reserving a menu-width floor');
    assert.ok(result.compact > 0, 'shared compact menu row token is available');
    assert.ok(result.heights.every(height => height >= (coarse ? 44 : result.compact) - .1), 'native menu targets retain shared density/touch sizing: ' + JSON.stringify(result));
  }
  const primary = await context();
  try {
    const page = await primary.newPage(); activePage = page;
    await page.goto(base + '/debug/paths'); await ready(page);
    const rowLink = page.locator('#wb-canvas sh-path-row a[part=link]').first();
    await pointer(page, rowLink); await copy(page, 'path', child);
    await pointer(page, rowLink); await copy(page, 'link', base + href(child));
    assert.equal(new URL(page.url()).pathname, '/debug/paths', 'copy never activates navigation');
    const surfaces = [
      [page.locator('#wb-path-locator ui-link').last().locator('a'), '/paths'],
      [page.locator('#wb-canvas [data-key="/definition"] .wb-slot-key button'), '/definition'],
      [page.locator('#wb-canvas [data-key="/reference"] sh-pail a'), child],
      [page.locator('#debug-saved .debug-page-link a').first(), child],
      [page.locator('#debug-history .debug-page-link a').first(), '/paths'],
    ];
    for (const [target, path] of surfaces) {await pointer(page, target); await copy(page, 'path', path);}
    const treeSection = page.locator('#debug-section-tree');
    await treeSection.getByRole('button').first().click();
    const treeRow = page.locator('#debug-path-tree ui-tree-item[data-path="/"] [role=treeitem]').first();
    await treeRow.waitFor(); await pointer(page, treeRow); await copy(page, 'path', '/');
    // Authored journal links keep their exact immutable page query, while
    // copying path remains the decoded namespace identity without that query.
    await page.evaluate(({journal, child}) => {
      const canvas = document.querySelector('#wb-canvas');
      for (const [id, url, text] of [['fixture-journal', journal, 'Authored journal page'],
        ['fixture-external', 'https://external-fixture.invalid/page', 'External reference']]) {
        const a = document.createElement('a'); a.id = id; a.href = url; a.textContent = text; canvas.append(a);
      }
      const input = document.createElement('input'); input.id = 'fixture-path-input'; input.value = child; input.dataset.pathTarget = child; canvas.append(input);
    }, {journal, child});
    await pointer(page, page.locator('#fixture-journal')); await copy(page, 'path', '/log');
    await pointer(page, page.locator('#fixture-journal')); await copy(page, 'link', base + journal);
    for (const selector of ['#fixture-path-input', '#fixture-external']) {
      const prevented = await page.locator(selector).evaluate(element => {
        const event = new MouseEvent('contextmenu', {bubbles: true, composed: true, cancelable: true});
        element.dispatchEvent(event); return event.defaultPrevented;
      });
      assert.equal(prevented, false, 'editing/external native context menus remain untouched'); await closed(page);
    }
    for (const key of ['Shift+F10', 'ContextMenu']) {
      await rowLink.focus(); await rowLink.press(key); await opened(page);
      await page.keyboard.press('Escape'); await closed(page);
      assert.equal(await rowLink.evaluate(element => document.activeElement === element.getRootNode().host && element.getRootNode().activeElement === element), true, 'keyboard dismissal returns native path focus');
    }
    await pointer(page, rowLink); await page.keyboard.press('Escape'); await closed(page);
    assert.equal(await rowLink.evaluate(element => element.getRootNode().activeElement === element), true, 'pointer-open Escape returns its native invoker');
    await page.evaluate(() => {window.__clipboardMode = 'failure';});
    await pointer(page, rowLink);
    await menu(page).getByRole('menuitem', {name: 'Copy link', exact: true}).click(); await closed(page);
    await page.waitForFunction(() => document.querySelector('#wb-feedback')?.textContent.includes('Could not copy the link'));
    assert.equal(await page.locator('#wb-feedback').getAttribute('data-failed'), 'true');
    await page.evaluate(() => {window.__clipboardMode = 'pending';});
    await pointer(page, rowLink); await menu(page).getByRole('menuitem', {name: 'Copy path', exact: true}).click(); await closed(page);
    await page.waitForFunction(() => typeof window.__finishCopy === 'function');
    const copies = await page.evaluate(() => window.__copies.length);
    await pointer(page, rowLink);
    assert.equal(await menu(page).getByRole('menuitem', {name: 'Copy path', exact: true}).isDisabled(), true, 'a pending platform write cannot start a second copy');
    assert.equal(await page.evaluate(() => window.__copies.length), copies);
    await page.evaluate(() => {window.__clipboardMode = 'success'; window.__finishCopy();});
    await page.waitForFunction(() => !document.querySelector('#wb-path-menu ui-menu-item').disabled);
    await page.keyboard.press('Escape'); await closed(page);
    await pointer(page, page.locator('#fixture-journal'));
    await page.locator('#fixture-journal').evaluate(element => element.remove()); await closed(page);
    await pointer(page, rowLink);
    await page.evaluate(() => document.dispatchEvent(new CustomEvent('debug:navigation-start'))); await closed(page);
    // A context action inside a hover preview must keep its real invoker alive
    // while command focus leaves the preview. No second path read is needed.
    await page.mouse.move(0, 0); await rowLink.hover();
    await page.waitForFunction(() => {
      const card = document.querySelector('#wb-path-preview');
      return card?.open && card.dataset.readState === 'ready';
    });
    const previewLink = page.locator('#wb-path-preview a.wb-hover-value').first();
    await pointer(page, previewLink);
    assert.equal(await previewLink.isVisible(), true, 'containing preview remains available during its path menu');
    await copy(page, 'path', child);
    await page.mouse.move(0, 0); await rowLink.hover();
    await previewLink.waitFor({state: 'visible'});
    await previewLink.focus(); await previewLink.press('Shift+F10'); await opened(page);
    await page.keyboard.press('Escape'); await closed(page);
    assert.equal(await previewLink.evaluate(element => {
      let active = document.activeElement;
      while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
      return active === element;
    }), true, 'Escape returns focus to the real reference inside the retained preview');
    await page.mouse.move(0, 0);
    // No context handler interferes with ordinary Enter or modified native links.
    const current = page.url(), popupPromise = primary.waitForEvent('page');
    await rowLink.click({modifiers: ['Meta']});
    const popup = await popupPromise; await ready(popup, child); assert.equal(page.url(), current); await popup.close();
    await rowLink.focus(); await rowLink.press('Enter'); await ready(page, child);
    assert.equal(await page.locator('#wb-path-menu').count(), 1, 'navigation keeps one delegated menu');
    assert.equal(await page.locator('.wb-document-title').evaluate(element => document.activeElement === element), true, 'plain native activation retains document focus behavior');
  } catch (error) {
    if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-path-menu-failure.png', animations: 'disabled'}).catch(() => {});
    throw error;
  } finally {await primary.close();}
  for (const specimen of [{name: 'light-1440', width: 1440, scheme: 'light'},
    {name: 'dark-1024', width: 1024, scheme: 'dark'}, {name: 'light-390-coarse', width: 390, scheme: 'light', coarse: true}]) {
    const sample = await context({viewport: {width: specimen.width, height: 850}, colorScheme: specimen.scheme,
      isMobile: Boolean(specimen.coarse), hasTouch: Boolean(specimen.coarse)});
    try {
      const page = await sample.newPage(); activePage = page;
      await page.goto(base + '/debug/paths'); await ready(page);
      const link = page.locator('#wb-canvas sh-path-row a[part=link]').first();
      await pointer(page, link); await geometry(page, specimen.coarse);
      const path = '/private/tmp/shrine-path-menu-' + specimen.name + '.png';
      await page.screenshot({path, animations: 'disabled'}); screenshots.push(path);
    } catch (error) {
      if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-path-menu-failure.png', animations: 'disabled'}).catch(() => {});
      throw error;
    } finally {await sample.close();}
  }
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log('PASS: shared context actions across breadcrumb/tree/Saved/Recent/slot/reference/path rows; exact Unicode and journal link copy; keyboard/pointer focus; failure/concurrency; native navigation.');
  console.log(JSON.stringify({fixtureReads: reads.length, liveReads: 0, systemClipboardWrites: 0, writes: 0, screenshots}, null, 2));
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-path-menu-failure.png', animations: 'disabled'}).catch(() => {});
  console.error(JSON.stringify({reads, writes, unexpected, errors, screenshots}, null, 2)); throw error;
} finally {await browser.close();}
