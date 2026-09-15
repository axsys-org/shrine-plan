// Saved/Recent/Roots integration over a saved real shell. An ephemeral loopback
// server serves only frozen fixtures/assets; browser routing rejects all other
// origins and methods. Native tabs receive actual HTTP documents, avoiding
// intercepted cold-popup parser stalls. No live namespace or user browser state.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; this suite has no live fallback');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
let base, fixtureServer;
const root = fileURLToPath(new URL('..', import.meta.url));
const html = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const encodedPath = '/alpha/price?#%λ';
const initialVisits = ['/alpha', '/beta', '/alpha', '/gamma', '/alpha', '/log'];
const journalCursor = '900719925474099312345';
const journalHref = '/debug/log?before=' + journalCursor + '&limit=2';
const savedPaths = ['/alpha', '/beta', '/unavailable', encodedPath];
const places = ['/', '/app', '/gov', '/weft', '/log', '/sys'];
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const reads = [], writes = [], unexpected = [], errors = [], screenshots = [], network = [], revealSettles = [], auxiliaryResults = [];
const owners = new WeakMap(); let nextOwner = 0, activePage;
const browser = await chromium.launch();
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage(); activePage = page;
  const fixtures = await page.evaluate(({html, encodedPath, places, journalCursor}) => {
    const original = new DOMParser().parseFromString(html, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell lacks current document anatomy');
    const children = {'/': ['/alpha', '/beta', '/gamma', '/app', '/weft', '/sys'], '/alpha': [encodedPath, '/alpha/child'], '/beta': ['/beta/child']};
    const paths = [...new Set([...places, '/alpha', '/beta', '/gamma', '/alpha/child', '/beta/child', encodedPath])];
    const documents = Object.fromEntries(paths.map(path => {
      const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
      Object.assign(workspace.dataset, {path, kind: 'record', writable: 'false', label: path.split('/').at(-1) || 'Namespace',
        fixture: 'sidebar-navigation', renderUrl: '/ns' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('')});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
      if (path === '/log') Object.assign(workspace.dataset, {kind: 'journal', paging: 'journal', pageBefore: '', pageNextBefore: '', pageLimit: '40', childCount: '0', pageEpoch: journalCursor});
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, value] of [['/sys/lede', 'Browser-only sidebar fixture'], ['/value', 'Authored fixture at ' + path]]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
        const pail = doc.createElement('sh-pail'); pail.textContent = value; limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations'])
        doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of children[path] || []) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.dataset.kind = 'record';
        item.dataset.label = child.split('/').at(-1); item.setAttribute('title', item.dataset.label); tree.append(item);
      }
      doc.querySelector('#debug-go ui-input')?.setAttribute('value', path);
      return [path, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
    const journal = new DOMParser().parseFromString(documents['/log'], 'text/html');
    Object.assign(journal.querySelector('#debug-workspace').dataset, {pageBefore: journalCursor, pageLimit: '2'});
    documents['/log?before=' + journalCursor + '&limit=2'] = '<!doctype html>' + journal.documentElement.outerHTML;
    return documents;
  }, {html, encodedPath, places, journalCursor});
  function fixtureResponse(url) {
    if (url.origin !== base) return null;
    if (assets.has(url.pathname) && !url.search) return {status: 200, ...assets.get(url.pathname)};
    if (/^\/debug(?:\/|$)/.test(url.pathname)) {
      let path;
      try { path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/'; } catch { return null; }
      if (path === '/unavailable' || path === '/gov') return {status: 503, contentType: 'text/plain', body: 'Browser-only navigation read failure'};
      const body = fixtures[path + url.search] || (!url.search && fixtures[path]);
      if (body) return {status: 200, contentType: 'text/html', body};
    }
    if (url.pathname === '/favicon.ico' && !url.search) return {status: 204, body: ''};
    return null;
  }
  fixtureServer = createServer((request, response) => {
    if (!base || request.headers.host !== new URL(base).host) {
      unexpected.push('Fixture server rejected Host ' + request.headers.host);
      response.writeHead(404); response.end(); return;
    }
    if (request.method !== 'GET') {
      writes.push('Fixture server rejected ' + request.method + ' ' + request.url);
      response.writeHead(405); response.end(); return;
    }
    let fixture;
    try { fixture = fixtureResponse(new URL(request.url, base)); } catch { /* Reject malformed request targets. */ }
    if (!fixture) {
      unexpected.push('Fixture server rejected ' + request.url);
      response.writeHead(404); response.end(); return;
    }
    const body = Buffer.isBuffer(fixture.body) ? fixture.body : Buffer.from(fixture.body || '');
    response.writeHead(fixture.status, {'Content-Type': fixture.contentType || 'text/plain', 'Content-Length': body.byteLength, 'Cache-Control': 'no-store'});
    response.end(body);
  });
  await new Promise((resolve, reject) => {
    fixtureServer.once('error', reject); fixtureServer.listen(0, '127.0.0.1', resolve);
  });
  base = 'http://127.0.0.1:' + fixtureServer.address().port;
  async function routeFixture(route) {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET') { writes.push(request.method() + ' ' + request.url()); return route.abort(); }
    if (!fixtureResponse(url)) { unexpected.push(request.url()); return route.abort(); }
    if (/^\/debug(?:\/|$)/.test(url.pathname)) {
      const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/';
      // Chromium can emit a new document request before its frame/page exists.
      // Subsequent SPA reads always have a frame; do not confuse the initial
      // document of a native new tab with a same-tab application read.
      let target;
      try { target = request.frame().page(); }
      catch (error) { if (!request.isNavigationRequest()) throw error; }
      if (target && !owners.has(target)) owners.set(target, ++nextOwner);
      reads.push({path, owner: target ? owners.get(target) : null});
    }
    return route.continue();
  }
  async function seed(targetContext, {preferences = {saved: true, recent: true, tree: true, root: '/', expanded: ['/']}, navigation = null} = {}) {
    targetContext.setDefaultTimeout(5000); targetContext.setDefaultNavigationTimeout(5000);
    targetContext.on('request', request => network.push({event: 'request', url: request.url(), type: request.resourceType(), navigation: request.isNavigationRequest()}));
    targetContext.on('response', response => network.push({event: 'response', url: response.url(), status: response.status(), headers: response.headers()}));
    targetContext.on('requestfinished', request => network.push({event: 'finished', url: request.url()}));
    targetContext.on('requestfailed', request => network.push({event: 'failed', url: request.url(), error: request.failure()?.errorText}));
    await targetContext.route('**/*', route => routeFixture(route).catch(async error => {
      errors.push('Fixture route: ' + error.message);
      await route.abort().catch(() => {});
    }));
    targetContext.on('page', target => {
      network.push({event: 'page', url: target.url()});
      target.on('pageerror', error => errors.push(error.message));
      target.on('download', download => network.push({event: 'download', url: download.url()}));
    });
    await targetContext.addInitScript(({base, savedPaths, initialVisits, journalCursor, preferences, navigation}) => {
      window.__sidebarFixtureRevealEnds = [];
      document.addEventListener('mash-reveal-end', event => {
        window.__sidebarFixtureRevealEnds.push({state: event.detail?.state, open: event.detail?.open, interrupted: event.detail?.interrupted});
      });
      if (location.origin !== base || sessionStorage.getItem('sidebar-navigation-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', JSON.stringify(savedPaths));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify(navigation || {visits: initialVisits, pages: initialVisits.map(path => path === '/log' ? {before: journalCursor, limit: 2} : null), cursor: 4}));
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify(preferences));
      sessionStorage.setItem('sidebar-navigation-fixture', 'seeded');
    }, {base, savedPaths, initialVisits, journalCursor, preferences, navigation});
  }
  await seed(context); page.on('pageerror', error => errors.push(error.message));
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function settled(check, message) {
    for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); }
    assert.fail(message);
  }
  async function ready(target, path) {
    await target.waitForFunction(path => {
      const ws = document.querySelector('#debug-workspace');
      return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
    }, path, {timeout: 5000});
  }
  const saved = (target, path) => target.locator('#debug-saved .debug-page-row[data-path="' + path + '"] > ui-link');
  const recent = (target, path) => target.locator('#debug-history .debug-page-row[data-path="' + path + '"] > ui-link');
  const anchor = link => link.locator('a[part=control]');
  const nativeButton = host => host.locator('button[part=control]');
  const rootMenu = target => target.locator('#debug-root-menu');
  const rootItem = (target, path) => rootMenu(target).locator('ui-menu-item[value="' + path + '"]');
  const rootAnchor = (target, path) => rootItem(target, path).locator('a[part=control]');
  const filter = target => target.locator('#debug-filter input');
  const scope = target => target.locator('#debug-tree-root').getAttribute('path');
  const history = target => target.evaluate(() => JSON.parse(sessionStorage.getItem('shrine-debug.v1.navigation')));
  const section = (target, value) => target.locator('#debug-section-' + value);
  const sectionTrigger = (target, value) => section(target, value).locator('button[part=trigger]');
  const sectionStates = target => target.locator('#debug-sidebar-sections').evaluate(el => Object.fromEntries([...el.children].map(item => [item.value, item.open])));
  async function revealGeometry(target) {
    return target.locator('#debug-sidebar-sections').evaluate(container => {
      const reveals = [];
      function visit(node) {
        if (node.localName === 'ui-reveal' && node.open) {
          const content = node.shadowRoot?.querySelector('[part=content]'), measure = node.shadowRoot?.querySelector('[part=measure]');
          reveals.push({active: node.matches(':state(active)'), entering: node.matches(':state(entering)'),
            content: content?.getBoundingClientRect().height ?? 0, measure: measure?.getBoundingClientRect().height ?? 0,
            natural: measure?.scrollHeight ?? 0, dimension: content?.style.blockSize,
            animations: content?.getAnimations().map(animation => animation.playState) || []});
        }
        for (const child of node.children || []) visit(child);
        if (node.shadowRoot) visit(node.shadowRoot);
      }
      const sections = [...container.querySelectorAll(':scope > .debug-sidebar-section')].map(item => {
        if (item.open) visit(item);
        const body = item.querySelector(':scope > .debug-section-body');
        return {id: body?.id, open: item.open, height: body?.getBoundingClientRect().height ?? 0};
      });
      return {reveals, events: window.__sidebarFixtureRevealEnds || [], sections};
    });
  }
  function projected(geometry, requireContent) {
    const opened = geometry.sections.filter(item => item.open);
    return geometry.reveals.length >= opened.length && geometry.reveals.every(item => item.active && !item.entering && item.content >= item.measure - .6) &&
      geometry.sections.length === 3 && (!requireContent || opened.length === 3 && opened.every(item => item.height > 0));
  }
  async function sectionsVisible(target, requireContent = false) {
    const started = Date.now(), initial = await revealGeometry(target);
    await settled(async () => projected(await revealGeometry(target), requireContent), 'expanded sidebar sections and nested hierarchy complete actual reveal presence: ' + JSON.stringify(initial));
    const final = await revealGeometry(target);
    revealSettles.push({width: target.viewportSize().width, elapsedMs: Date.now() - started,
      ...(projected(initial, requireContent) ? {} : {initial, final})});
  }
  async function showSidebar(target) {
    if (!await filter(target).isVisible()) await target.locator('#debug-sidebar-toggle').click();
    await filter(target).waitFor({state: 'visible'});
    await settled(() => target.locator('#debug-sidebar-sections').evaluate(el => el.getBoundingClientRect().height > 0), 'sidebar navigation is fully projected');
    await sectionsVisible(target);
  }
  async function clickRoute(target, control, path, key = null) {
    const before = reads.length;
    if (key) { await control.focus(); await control.press(key); } else await control.click();
    await ready(target, path);
    await settled(() => Promise.resolve(reads.slice(before).some(read => read.path === path && read.owner === owners.get(target))), 'primary activation reads the intended fixture');
  }
  async function snapshot(target) {
    return {url: target.url(), scope: await scope(target), filter: await filter(target).inputValue(), history: await history(target)};
  }
  async function untouched(target, before, label) {
    assert.deepEqual(await snapshot(target), before, label + ' preserves the current page, scope, filter and exact visit cursor');
  }
  async function alternateDefaults(target, native) {
    const before = await snapshot(target), count = reads.filter(read => read.owner === owners.get(target)).length;
    const outcomes = await native.evaluate(control => [
      ...['metaKey', 'ctrlKey', 'shiftKey', 'altKey'].map(modifier => ({type: 'click', button: 0, [modifier]: true, description: modifier})),
      {type: 'auxclick', button: 1, description: 'middle'},
    ].map(({type, description, ...options}) => {
      const event = new MouseEvent(type, {bubbles: true, composed: true, cancelable: true, ...options});
      let prevented = null;
      const observe = received => {
        if (received !== event) return;
        prevented = received.defaultPrevented;
        // Observe after production document routing, then prevent only the
        // platform window/download default of this synthetic diagnostic.
        received.preventDefault();
      };
      window.addEventListener(type, observe); control.dispatchEvent(event); window.removeEventListener(type, observe);
      return {description, prevented};
    }));
    assert.ok(outcomes.every(outcome => outcome.prevented === false), 'alternate clicks reach native defaults: ' + JSON.stringify(outcomes));
    await untouched(target, before, 'Modified and middle activation');
    assert.equal(reads.filter(read => read.owner === owners.get(target)).length, count, 'alternate clicks start no same-tab namespace read');
  }
  async function actualMiddle(target, native, path, expectedHref = href(path)) {
    const before = await snapshot(target), count = reads.filter(read => read.owner === owners.get(target)).length;
    const nativeMarkup = await native.evaluate(el => el.outerHTML);
    let other;
    try {
      [other] = await Promise.all([target.context().waitForEvent('page', {timeout: 5000}), native.click({button: 'middle'})]);
      await other.bringToFront();
      await other.waitForURL(base + expectedHref, {waitUntil: 'domcontentloaded'});
      await ready(other, path);
      assert.equal(new URL(other.url()).pathname + new URL(other.url()).search, expectedHref, 'real middle-click opens its canonical native destination in another tab');
      auxiliaryResults.push({path, href: expectedHref, passed: true});
    } catch (error) {
      console.error('NATIVE ANCHOR:', nativeMarkup);
      console.error('AUXILIARY NETWORK:', JSON.stringify(network));
      for (const candidate of target.context().pages()) console.error('AUXILIARY PAGE:', JSON.stringify(await candidate.evaluate(() => ({url: location.href, title: document.title, ready: document.readyState,
        workspace: document.querySelector('#debug-workspace')?.dataset, text: document.body?.textContent.slice(0, 1500),
        scripts: [...document.scripts].map(script => script.src)})).catch(() => ({url: candidate.url()}))));
      await other?.screenshot({path: '/private/tmp/shrine-sidebar-navigation-auxiliary-failure.png', animations: 'disabled'}).catch(() => {});
      // Native new-tab loading is a separately reported integration
      // group. Its failure must not suppress the remaining layout evidence,
      // and still makes the complete suite fail at the end.
      auxiliaryResults.push({path, href: expectedHref, passed: false, error: error.message});
    } finally { await other?.close(); await target.bringToFront(); }
    await untouched(target, before, 'Real middle-click');
    assert.equal(reads.filter(read => read.owner === owners.get(target)).length, count, 'the original tab does not fetch on real middle-click');
  }
  async function focusGeometry(control) {
    return control.evaluate(el => {
      const box = el.getBoundingClientRect(), style = getComputedStyle(el);
      const reach = style.outlineStyle === 'none' ? 0 : Math.max(0, parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset));
      const ring = {left: box.left - reach, right: box.right + reach, top: box.top - reach, bottom: box.bottom + reach};
      const clips = []; let ancestor = el;
      while (ancestor) {
        ancestor = ancestor.assignedSlot || ancestor.parentNode;
        if (ancestor instanceof ShadowRoot) ancestor = ancestor.host;
        if (!(ancestor instanceof Element)) continue;
        const css = getComputedStyle(ancestor), bound = ancestor.getBoundingClientRect();
        const clipX = /^(hidden|clip|auto|scroll)$/.test(css.overflowX), clipY = /^(hidden|clip|auto|scroll)$/.test(css.overflowY);
        if (clipX || clipY) clips.push({name: ancestor.id || ancestor.getAttribute('part') || ancestor.localName,
          clipX, clipY, left: bound.left + ancestor.clientLeft, right: bound.left + ancestor.clientLeft + ancestor.clientWidth,
          top: bound.top + ancestor.clientTop, bottom: bound.top + ancestor.clientTop + ancestor.clientHeight});
      }
      return {outline: style.outlineStyle, outlineWidth: parseFloat(style.outlineWidth), outlineColor: style.outlineColor, reach, ring, clips};
    });
  }
  async function focusContained(control) {
    await control.focus();
    // The sidebar may have just opened from a pointer click. Enter and return
    // through the actual Tab sequence before checking its keyboard ring.
    await control.press('Tab'); await control.page().keyboard.press('Shift+Tab');
    assert.equal(await control.evaluate(el => el.getRootNode().activeElement === el), true, 'Tab navigation returns to the native destination');
    await settled(async () => {
      const {outline, outlineWidth, outlineColor, ring, clips} = await focusGeometry(control);
      return outline !== 'none' && outlineWidth > 0 && !['transparent', 'rgba(0, 0, 0, 0)'].includes(outlineColor) && clips.every(clip => (!clip.clipX || ring.left >= clip.left - .6 && ring.right <= clip.right + .6) &&
        (!clip.clipY || ring.top >= clip.top - .6 && ring.bottom <= clip.bottom + .6));
    }, 'complete native focus ring fits every composed clipping ancestor: ' + JSON.stringify(await focusGeometry(control)));
  }
  async function menuFocusContained(target, path) {
    const control = rootAnchor(target, path); await control.focus();
    // Exercise real keyboard modality: programmatic focus immediately after
    // a pointer-open menu intentionally does not imply :focus-visible.
    await target.keyboard.press('Home');
    for (let index = 0; index < places.indexOf(path); index++) await target.keyboard.press('ArrowDown');
    await settled(() => control.evaluate(el => el.getRootNode().activeElement === el), 'native Roots destination owns keyboard focus');
    const other = rootAnchor(target, path === '/' ? '/app' : '/');
    const background = link => link.evaluate(el => getComputedStyle(el).backgroundColor);
    await settled(async () => await background(control) !== await background(other), 'Mash menu selection visibly distinguishes its focused destination');
    // Menu items use the shared selection fill, not the separate ui-link
    // outline. Assert the actual control rectangle remains fully visible.
    const geometry = await focusGeometry(control);
    assert.ok(geometry.clips.every(clip => (!clip.clipX || geometry.ring.left >= clip.left - .6 && geometry.ring.right <= clip.right + .6) &&
      (!clip.clipY || geometry.ring.top >= clip.top - .6 && geometry.ring.bottom <= clip.bottom + .6)),
    'focused Roots selection fits its clipping surfaces: ' + JSON.stringify(geometry));
  }
  async function rowGeometry(target, coarse) {
    const rows = target.locator('#debug-saved .debug-page-row, #debug-history .debug-page-row');
    for (const row of await rows.all()) {
      if (!await row.isVisible()) continue;
      const link = row.locator(':scope > ui-link'), control = anchor(link), box = await control.boundingBox(), parent = await row.boundingBox();
      assert.equal(await link.getAttribute('variant'), 'quiet'); assert.equal(await link.getAttribute('size'), 'small');
      assert.equal(await link.locator(':scope > ui-icon[slot=prefix]').count(), 1);
      assert.equal(await control.getAttribute('aria-label'), await row.getAttribute('data-path'), 'native saved/recent links name the complete namespace path');
      assert.ok(box.x >= parent.x - .6 && box.x + box.width <= parent.x + parent.width + .6, 'native link remains inside its row');
      if (coarse) assert.ok(box.width >= 43.9 && box.height >= 43.9, 'native saved/recent target is44px in both axes: ' + JSON.stringify(box));
      const remove = row.locator(':scope > ui-button');
      if (await remove.count()) {
        const button = await nativeButton(remove).boundingBox();
        if (coarse) assert.ok(button.width >= 43.9 && button.height >= 43.9, 'unsave has its own44px native target');
        assert.ok(box.x + box.width <= button.x + .6, 'saved navigation and unsave targets are separated');
      }
    }
    assert.ok(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'sidebar page stays within the viewport');
  }
  async function openPlaces(target, keyboard = false) {
    await showSidebar(target);
    if (keyboard) { await target.locator('#debug-root-toggle').focus(); await target.locator('#debug-root-toggle').press('ArrowDown'); }
    else await target.locator('#debug-root-toggle').click();
    await rootAnchor(target, '/').waitFor({state: 'visible'});
  }
  async function rootsFocusReturned(target) {
    await settled(() => nativeButton(target.locator('#debug-root-toggle')).evaluate(el => el.getRootNode().activeElement === el),
      'completed Roots keyboard navigation returns focus to its native trigger, not body: ' + JSON.stringify(await target.evaluate(() => ({tag: document.activeElement?.localName, id: document.activeElement?.id}))));
  }
  async function rootGeometry(target, coarse) {
    const bounds = [];
    for (const path of places) {
      const control = rootAnchor(target, path);
      assert.equal(await control.getAttribute('href'), href(path), 'Roots retain canonical native destinations');
      assert.equal(await control.getAttribute('role'), 'menuitem');
      const box = await control.boundingBox(); bounds.push(box);
      if (coarse) assert.ok(box.width >= 43.9 && box.height >= 43.9, 'native Roots menu target is44px: ' + JSON.stringify(box));
    }
    for (let index = 1; index < bounds.length; index++) assert.ok(bounds[index - 1].y + bounds[index - 1].height <= bounds[index].y + .6, 'Roots menu hit rows do not overlap');
  }
  async function screenshot(target, name) {
    await sectionsVisible(target, true);
    const path = '/private/tmp/shrine-sidebar-navigation-' + name + '.png'; await target.screenshot({path, animations: 'disabled'}); screenshots.push(path);
    assert.ok(projected(await revealGeometry(target), true), 'screenshot animation handling must not collapse populated expanded sections: ' + JSON.stringify(await revealGeometry(target)));
  }
  async function accordionContract(target, coarse = false) {
    const group = target.locator('#debug-sidebar-sections');
    assert.equal(await group.evaluate(el => el.localName), 'ui-accordion');
    for (const [attribute, value] of [['mode', 'multiple'], ['size', 'compact'], ['variant', 'quiet']]) assert.equal(await group.getAttribute(attribute), value);
    for (const value of ['saved', 'recent', 'tree']) {
      const item = section(target, value), trigger = sectionTrigger(target, value), region = item.locator('ui-reveal[part=content]');
      assert.equal(await item.evaluate(el => el.localName), 'ui-accordion-item');
      assert.equal(await item.getAttribute('value'), value); assert.equal(await item.getAttribute('heading-level'), '2');
      assert.equal(await item.getByRole('heading', {level: 2}).count(), 1);
      assert.equal(await trigger.getAttribute('type'), 'button');
      assert.equal(await trigger.getAttribute('aria-controls'), await region.getAttribute('id'));
      assert.equal(await region.getAttribute('aria-labelledby'), await trigger.getAttribute('id'));
      assert.equal(await region.getAttribute('role'), 'region');
      assert.equal(await item.locator(':scope > ui-icon[slot=prefix]').count(), 1);
      assert.equal(await item.locator(':scope > ui-icon[slot=disclosure]').count(), 1);
      assert.equal(await item.locator(':scope > [slot=title]').count(), 1);
      assert.equal(await item.locator(':scope > .debug-section-count[slot=suffix]').count(), 1);
      const box = await trigger.boundingBox(), parent = await item.boundingBox();
      assert.ok(box.x >= parent.x - .6 && box.x + box.width <= parent.x + parent.width + .6, 'native section header fits its column');
      if (coarse) assert.ok(box.width >= 43.9 && box.height >= 43.9, 'native accordion header has its own44px touch target: ' + JSON.stringify(box));
    }
  }
  async function sectionCount(target, value, expected) {
    const count = section(target, value).locator(':scope > .debug-section-count');
    await settled(async () => (await count.textContent()).trim() === expected, value + ' has meaningful count text ' + expected);
    assert.ok(await count.getAttribute('title'), 'counts explain their namespace meaning');
    assert.match(await count.getAttribute('data-count-value'), /^\d+$/, 'count base remains an exact decimal');
    assert.equal(await count.getAttribute('data-count-value'), expected.split(' ')[0], 'count metadata agrees with its actually displayed base');
    const title = value[0].toUpperCase() + value.slice(1);
    const name = await sectionTrigger(target, value).ariaSnapshot();
    assert.ok(name.includes(title) && name.includes(expected), 'native trigger accessible name contains the section and meaningful count: ' + name);
  }
  async function toggleSection(target, value, open, gesture = 'pointer') {
    const before = await sectionStates(target), trigger = sectionTrigger(target, value);
    assert.notEqual(before[value], open, 'fixture toggles a genuinely different section state');
    if (gesture === 'pointer') await trigger.click();
    else if (gesture === 'tap') await trigger.tap();
    else await trigger.press(gesture);
    await settled(async () => await trigger.getAttribute('aria-expanded') === String(open), 'native section trigger reflects activation');
    assert.deepEqual(await sectionStates(target), {...before, [value]: open}, 'multiple accordion sections toggle independently');
    const reveal = section(target, value).locator('ui-reveal[part=content]');
    if (open) await sectionsVisible(target);
    else {
      assert.equal(await reveal.getAttribute('aria-hidden'), 'true');
      await settled(() => reveal.evaluate(el => !el.matches(':state(present)') && el.getBoundingClientRect().height === 0), 'closed section completes exit presence without removing authored content');
    }
    const preferences = await target.evaluate(() => JSON.parse(localStorage.getItem('shrine-debug.sidebar.v2')));
    assert.equal(preferences[value], open, 'section preference persists its independent open state');
  }

  // Section lifecycles run in their own storage/viewport so the navigation
  // and14 visual baselines below retain the same authored fixture state.
  const sectionsContext = await browser.newContext({viewport: {width: 1440, height: 440}}); await seed(sectionsContext);
  const sectionPage = await sectionsContext.newPage(); activePage = sectionPage;
  await sectionPage.goto(base + href('/alpha')); await ready(sectionPage, '/alpha'); await showSidebar(sectionPage);
  await accordionContract(sectionPage);
  await sectionCount(sectionPage, 'saved', '4 pages'); await sectionCount(sectionPage, 'recent', '4 paths'); await sectionCount(sectionPage, 'tree', '6 names');
  const retained = await Promise.all([
    sectionPage.locator('#debug-saved'), sectionPage.locator('#debug-history'), sectionPage.locator('#debug-children'),
    sectionPage.locator('#debug-path-tree'), sectionPage.locator('#debug-path-tree ui-tree > ui-tree-item').first(), anchor(saved(sectionPage, '/alpha')),
  ].map(async locator => ({locator, handle: await locator.elementHandle()})));
  async function retainedSectionDOM() {
    for (const {locator, handle} of retained) assert.equal(await handle.evaluate((node, current) => node.isConnected && node === current, await locator.elementHandle()), true,
      'section toggles preserve body, tree, root item and native page anchor identity');
  }
  const scrollArea = await sectionPage.locator('#debug-sidebar').evaluateHandle(el => el.shadowRoot.querySelector('ui-scroll-area'));
  await scrollArea.evaluate(area => area.scrollViewportTo({top: 8, behavior: 'instant'}));
  const initialScroll = await scrollArea.evaluate(area => area.viewportElement.scrollTop);
  assert.ok(initialScroll > 0, 'short viewport provides genuine scroll state to preserve');
  // Recent's header is fully visible at this positive offset. Clicking the
  // first partly clipped Saved header would correctly scroll it into view,
  // testing browser focus scrolling instead of accordion DOM preservation.
  await toggleSection(sectionPage, 'recent', false);
  assert.ok(Math.abs(await scrollArea.evaluate(area => area.viewportElement.scrollTop) - initialScroll) < .6, 'collapsing Recent does not reset an otherwise valid sidebar scroll offset');
  await toggleSection(sectionPage, 'recent', true, 'Enter'); await retainedSectionDOM();
  assert.ok(Math.abs(await scrollArea.evaluate(area => area.viewportElement.scrollTop) - initialScroll) < .6, 'reopening Recent preserves sidebar scroll');
  await scrollArea.evaluate(area => area.scrollViewportTo({top: 0, behavior: 'instant'}));
  await toggleSection(sectionPage, 'saved', false); await toggleSection(sectionPage, 'saved', true, 'Enter');
  await filter(sectionPage).fill('alpha');
  await toggleSection(sectionPage, 'recent', false, 'Space'); await toggleSection(sectionPage, 'tree', false);
  await toggleSection(sectionPage, 'recent', true, 'Enter'); await retainedSectionDOM();
  assert.equal(await filter(sectionPage).inputValue(), 'alpha', 'section composition preserves the filter value');
  await sectionCount(sectionPage, 'saved', '4 pages');
  await sectionPage.locator('#debug-filter-clear').click();
  const originalRootDocument = fixtures['/']; fixtures['/'] = originalRootDocument.replace('Browser-only sidebar fixture', 'Refreshed tree fixture');
  const beforeClosedRefresh = reads.length;
  await sectionPage.locator('#wb-refresh').click(); await ready(sectionPage, '/alpha'); await sectionsVisible(sectionPage);
  assert.deepEqual(reads.slice(beforeClosedRefresh).filter(read => read.owner === owners.get(sectionPage)).map(read => read.path), ['/alpha'],
    'explicit document refresh does not read a hidden tree root');
  await retainedSectionDOM();
  const beforeReopen = reads.length; await toggleSection(sectionPage, 'tree', true, 'Space');
  await settled(() => sectionPage.locator('#debug-path-tree ui-tree > ui-tree-item').first().locator(':scope > .debug-node-lede').textContent().then(value => value === 'Refreshed tree fixture'), 'reopening lazily refreshes the retained tree snapshot');
  assert.equal(reads.slice(beforeReopen).filter(read => read.path === '/' && read.owner === owners.get(sectionPage)).length, 1, 'tree reopening performs exactly one missing-root read');
  await retainedSectionDOM(); fixtures['/'] = originalRootDocument;
  await clickRoute(sectionPage, anchor(saved(sectionPage, '/beta')), '/beta'); await settled(async () => await scope(sectionPage) === '/beta', 'Saved root established before persistence test');
  await sectionCount(sectionPage, 'tree', '1 name');
  await toggleSection(sectionPage, 'recent', false); await toggleSection(sectionPage, 'tree', false, 'Enter');
  await sectionPage.reload(); await ready(sectionPage, '/beta'); await showSidebar(sectionPage);
  assert.deepEqual(await sectionStates(sectionPage), {saved: true, recent: false, tree: false}, 'disposable reload preserves independent disclosure preferences');
  assert.equal(await scope(sectionPage), '/beta', 'saved tree root survives reload even while its section is closed');
  await toggleSection(sectionPage, 'recent', true, 'Space'); await toggleSection(sectionPage, 'tree', true, 'Enter');
  await sectionCount(sectionPage, 'tree', '1 name'); await sectionsContext.close();

  const cappedVisits = [...Array.from({length: 33}, (_, index) => '/remembered/' + index), '/alpha'];
  const lazyContext = await browser.newContext({viewport: {width: 1440, height: 1000}});
  await seed(lazyContext, {preferences: {saved: true, recent: true, tree: false, root: '/', expanded: ['/']}, navigation: {visits: cappedVisits, pages: cappedVisits.map(() => null), cursor: cappedVisits.length - 1}});
  const lazyPage = await lazyContext.newPage(); activePage = lazyPage;
  const beforeHiddenStartup = reads.length;
  await lazyPage.goto(base + href('/alpha')); await ready(lazyPage, '/alpha'); await showSidebar(lazyPage);
  await sectionCount(lazyPage, 'recent', '30 of 34 paths');
  assert.equal(await lazyPage.locator('#debug-history .debug-page-row').count(), 30);
  assert.deepEqual(reads.slice(beforeHiddenStartup).filter(read => read.owner === owners.get(lazyPage)).map(read => read.path), ['/alpha'], 'persisted closed Tree starts with no implicit root read');
  await toggleSection(lazyPage, 'recent', false, 'Space');
  const beforeInitialOpen = reads.length; await toggleSection(lazyPage, 'tree', true, 'Enter');
  await sectionCount(lazyPage, 'tree', '6 names');
  assert.equal(reads.slice(beforeInitialOpen).filter(read => read.path === '/' && read.owner === owners.get(lazyPage)).length, 1, 'first Tree opening lazily loads its root once');
  await toggleSection(lazyPage, 'tree', false);
  await lazyPage.locator('#wb-refresh').click(); await ready(lazyPage, '/alpha');
  const beforePlacesOpen = reads.length;
  await openPlaces(lazyPage); await clickRoute(lazyPage, rootAnchor(lazyPage, '/app'), '/app');
  await settled(async () => (await sectionStates(lazyPage)).tree, 'successful Places selection opens the actual Tree section');
  await sectionCount(lazyPage, 'tree', '6 names');
  assert.equal(reads.slice(beforePlacesOpen).filter(read => read.path === '/' && read.owner === owners.get(lazyPage)).length, 1,
    'programmatic Places opening schedules the same deferred root read without a synthetic accordion event');
  await openPlaces(lazyPage); await clickRoute(lazyPage, rootAnchor(lazyPage, '/log'), '/log');
  await lazyPage.locator('#debug-save').click();
  await clickRoute(lazyPage, anchor(saved(lazyPage, '/log')), '/log');
  await sectionCount(lazyPage, 'tree', '0 loaded entries');
  await lazyContext.close(); activePage = page;
  console.log('PASS: independent Mash accordion semantics, counts, DOM/filter/scroll persistence and hidden-tree lazy reads.');

  await page.goto(base + href('/alpha')); await ready(page, '/alpha'); await showSidebar(page);
  assert.deepEqual((await history(page)).visits, initialVisits); assert.equal((await history(page)).cursor, 4);
  await rowGeometry(page, false);
  assert.equal(await anchor(saved(page, encodedPath)).getAttribute('href'), href(encodedPath));
  await focusContained(anchor(saved(page, '/alpha')));
  assert.equal(await anchor(recent(page, '/log')).getAttribute('href'), journalHref, 'Recent journal href retains exact high-precision cursor and page limit');
  await alternateDefaults(page, anchor(recent(page, '/log'))); await actualMiddle(page, anchor(recent(page, '/log')), '/log', journalHref);
  await clickRoute(page, anchor(recent(page, '/log')), '/log');
  assert.equal(page.url(), base + journalHref); assert.equal((await history(page)).cursor, 5);
  assert.deepEqual((await history(page)).pages[5], {before: journalCursor, limit: 2});
  await clickRoute(page, page.locator('#debug-back'), '/alpha'); assert.equal((await history(page)).cursor, 4);
  const recentBeta = await anchor(recent(page, '/beta')).elementHandle();
  await clickRoute(page, anchor(recent(page, '/beta')), '/beta');
  assert.equal(await recentBeta.evaluate(el => el.isConnected && el.getRootNode().activeElement === el), true, 'Recent selection retains the same focused native anchor');
  assert.equal((await history(page)).cursor, 1, 'Recent uses the stored last visit index');
  assert.deepEqual((await history(page)).visits, initialVisits, 'Recent does not append another visit');
  await clickRoute(page, page.locator('#debug-back'), '/alpha'); assert.equal((await history(page)).cursor, 0);
  await clickRoute(page, page.locator('#debug-forward'), '/beta'); assert.equal((await history(page)).cursor, 1);
  await clickRoute(page, anchor(recent(page, '/alpha')), '/alpha'); assert.equal((await history(page)).cursor, 4, 'repeated path chooses its last visit, not the first match');
  await clickRoute(page, anchor(recent(page, '/alpha')), '/alpha', 'Enter'); assert.equal((await history(page)).cursor, 4, 'selecting the same Recent path by keyboard preserves its exact cursor');
  await clickRoute(page, anchor(saved(page, '/alpha')), '/alpha', 'Enter');
  await settled(async () => await scope(page) === '/alpha', 'Saved scopes the hierarchy only after successful navigation');
  assert.deepEqual((await history(page)).visits, initialVisits, 'same-path Saved selection does not append history');
  assert.equal(await page.locator('#debug-path-tree ui-tree > ui-tree-item').first().getAttribute('data-path'), '/alpha');
  assert.equal(await anchor(saved(page, '/alpha')).getAttribute('aria-current'), 'page');
  assert.equal(await anchor(recent(page, '/alpha')).getAttribute('aria-current'), 'page');
  await filter(page).fill('unavailable');
  const failedBefore = await snapshot(page);
  await anchor(saved(page, '/unavailable')).click();
  await page.waitForFunction(() => document.querySelector('#debug-status').textContent.includes('Navigation failed.') && document.querySelector('#debug-workspace').getAttribute('aria-busy') === 'false');
  await untouched(page, failedBefore, 'Failed Saved navigation');
  await page.locator('#debug-filter-clear').click();
  const savedBeta = await anchor(saved(page, '/beta')).elementHandle();
  await clickRoute(page, anchor(saved(page, '/beta')), '/beta');
  await settled(async () => await scope(page) === '/beta', 'successful Saved navigation scopes the chosen page');
  assert.equal(await savedBeta.evaluate(el => el.isConnected && el.getRootNode().activeElement === el), true, 'Saved selection retains the same focused native anchor');
  assert.equal(await recentBeta.evaluate(el => el.isConnected && el.getRootNode().host.closest('.debug-page-row') === document.querySelector('#debug-history .debug-page-row')), true,
    'moving Recent to the top reuses its original native anchor');
  await alternateDefaults(page, anchor(saved(page, encodedPath))); await actualMiddle(page, anchor(saved(page, encodedPath)), encodedPath);
  await alternateDefaults(page, anchor(recent(page, '/alpha')));
  await clickRoute(page, anchor(saved(page, encodedPath)), encodedPath);
  assert.equal(await scope(page), encodedPath); assert.equal(new URL(page.url()).pathname, href(encodedPath));
  assert.equal(new URL(page.url()).search, ''); assert.equal(new URL(page.url()).hash, '');
  const distinctRecent = new Set((await history(page)).visits).size;
  await sectionCount(page, 'recent', distinctRecent + ' paths');

  await filter(page).fill('keep this filter'); await openPlaces(page);
  await rootGeometry(page, false); await alternateDefaults(page, rootAnchor(page, '/app'));
  await actualMiddle(page, rootAnchor(page, '/app'), '/app');
  // Alternate activation may transfer OS focus; reopening is an explicit
  // interaction only if the actual menu closed. It never clears the filter.
  if (!await rootAnchor(page, '/').isVisible()) await openPlaces(page);
  await rootAnchor(page, '/').press('Escape');
  assert.equal(await filter(page).inputValue(), 'keep this filter', 'menu dismissal does not clear filtering');
  await settled(() => nativeButton(page.locator('#debug-root-toggle')).evaluate(el => el.getRootNode().activeElement === el), 'keyboard Escape returns to the invoker even after pointer-open');
  // Verify the same restoration from a wholly keyboard-driven opening.
  await openPlaces(page, true); await rootAnchor(page, '/').press('Escape');
  await settled(() => nativeButton(page.locator('#debug-root-toggle')).evaluate(el => el.getRootNode().activeElement === el), 'Escape returns to the Roots trigger');
  await openPlaces(page, true);
  await settled(() => rootAnchor(page, '/').evaluate(el => el.getRootNode().activeElement === el), 'keyboard menu opening focuses the first native destination');
  await rootAnchor(page, '/').press('End'); await settled(() => rootAnchor(page, '/sys').evaluate(el => el.getRootNode().activeElement === el), 'End selects the last Root');
  await rootAnchor(page, '/sys').press('Home'); await rootAnchor(page, '/').press('ArrowDown');
  await settled(() => rootAnchor(page, '/app').evaluate(el => el.getRootNode().activeElement === el), 'ArrowDown selects Applications');
  await menuFocusContained(page, '/app');
  await rootAnchor(page, '/app').press('Enter'); await ready(page, '/app');
  await rootsFocusReturned(page);
  assert.equal(await filter(page).inputValue(), '', 'primary keyboard Roots activation clears filtering');
  assert.equal(await scope(page), '/', 'Roots navigation leaves an incompatible saved scope');
  await filter(page).fill('app'); await openPlaces(page, true); await clickRoute(page, rootAnchor(page, '/app'), '/app', 'Space');
  await rootsFocusReturned(page);
  assert.equal(await filter(page).inputValue(), '', 'same-path primary Root selection also clears filtering');
  await filter(page).fill('keep on failure');
  const rootBefore = await snapshot(page);
  await openPlaces(page); await rootAnchor(page, '/gov').click();
  await page.waitForFunction(() => document.querySelector('#debug-status').textContent.includes('Navigation failed.') && document.querySelector('#debug-workspace').getAttribute('aria-busy') === 'false');
  await untouched(page, rootBefore, 'Failed Root navigation');
  await page.locator('#debug-filter-clear').click();
  const treeSelection = await page.locator('#debug-path-tree ui-tree-item[current]').getAttribute('data-path');
  const beforeFilterReads = reads.length;
  await filter(page).fill('alpha'); await filter(page).press('Escape');
  assert.equal(reads.length, beforeFilterReads, 'sidebar filtering searches only loaded paths without implicit reads');
  assert.equal(await page.locator('#debug-path-tree ui-tree-item[current]').getAttribute('data-path'), treeSelection, 'filtering preserves the selected namespace path');
  while (await page.locator('#debug-saved .debug-page-row').count()) {
    const row = page.locator('#debug-saved .debug-page-row').first();
    await row.locator(':scope > ui-button').click();
    const remaining = await page.locator('#debug-saved .debug-page-row').count();
    await sectionCount(page, 'saved', remaining + (remaining === 1 ? ' page' : ' pages'));
    const destination = page.locator('#debug-saved .debug-page-row > ui-link').first();
    if (await destination.count()) await settled(() => anchor(destination).evaluate(el => el.getRootNode().activeElement === el), 'Unsave focuses the next destination, not another remove action');
    else await settled(() => nativeButton(page.locator('#debug-saved > ui-button')).evaluate(el => el.getRootNode().activeElement === el), 'last Unsave focuses the mounted Save current page action');
  }
  const filteredContext = await browser.newContext({viewport: {width: 1440, height: 1000}}); await seed(filteredContext);
  const filtered = await filteredContext.newPage(); activePage = filtered;
  await filtered.goto(base + href('/alpha')); await ready(filtered, '/alpha'); await showSidebar(filtered);
  await filter(filtered).fill('beta');
  assert.equal(await filtered.locator('#debug-saved .debug-page-row:visible').count(), 1, 'filtered Unsave fixture has one visible saved destination');
  await filtered.locator('#debug-saved .debug-page-row[data-path="/beta"] > ui-button').click();
  await settled(() => filter(filtered).evaluate(el => el.getRootNode().activeElement === el), 'removing the only filtered destination returns focus to the filter, never a hidden link');
  assert.equal(await filter(filtered).inputValue(), 'beta');
  assert.equal(await filtered.locator('#debug-saved .debug-page-row:visible').count(), 0);
  assert.equal(await filtered.locator('#debug-saved .debug-page-row').count(), 3, 'other saved pages remain present but filtered');
  await filteredContext.close(); activePage = page;
  console.log('PASS: exact Recent cursor/history, same-path Saved scope, failed navigation rollback, native alternate links, encoded paths and keyboard Roots/filter semantics.');

  for (const width of [1440, 768, 390]) {
    const responsive = await browser.newContext({viewport: {width, height: width === 390 ? 844 : 1000}}); await seed(responsive);
    const target = await responsive.newPage(); activePage = target;
    await target.goto(base + href('/alpha')); await ready(target, '/alpha'); await showSidebar(target);
    await accordionContract(target); await focusContained(sectionTrigger(target, 'saved'));
    await rowGeometry(target, false); await focusContained(anchor(saved(target, '/alpha'))); await screenshot(target, 'light-' + width);
    await openPlaces(target); await rootGeometry(target, false); await menuFocusContained(target, '/app');
    await screenshot(target, 'roots-light-' + width); await rootAnchor(target, '/app').press('Escape');
    await target.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
    await focusContained(sectionTrigger(target, 'saved'));
    await rowGeometry(target, false); await focusContained(anchor(recent(target, '/alpha'))); await screenshot(target, 'dark-' + width);
    await openPlaces(target); await rootGeometry(target, false); await menuFocusContained(target, '/app');
    await screenshot(target, 'roots-dark-' + width); await rootAnchor(target, '/app').press('Escape');
    await responsive.close();
  }
  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce'}); await seed(touchContext);
  const touch = await touchContext.newPage(); activePage = touch;
  await touch.goto(base + href('/alpha')); await ready(touch, '/alpha'); await showSidebar(touch);
  assert.equal(await touch.evaluate(() => matchMedia('(pointer: coarse)').matches), true);
  await accordionContract(touch, true); await focusContained(sectionTrigger(touch, 'saved'));
  await toggleSection(touch, 'saved', false, 'tap'); await toggleSection(touch, 'saved', true, 'tap');
  await rowGeometry(touch, true); await focusContained(anchor(saved(touch, '/alpha'))); await screenshot(touch, 'touch-390');
  await openPlaces(touch); await rootGeometry(touch, true); await menuFocusContained(touch, '/app'); await screenshot(touch, 'roots-touch-390');
  await rootAnchor(touch, '/app').press('Escape');
  await clickRoute(touch, anchor(saved(touch, '/beta')), '/beta'); await settled(async () => await scope(touch) === '/beta', 'touch Saved scopes the intended page');
  assert.equal(await filter(touch).isVisible(), false, 'successful touch sidebar navigation reveals the main document');
  await settled(() => touch.locator('.wb-document-title').evaluate(el => document.activeElement === el), 'closing the sidebar after touch Saved navigation moves focus to the document title');
  await settled(async () => {
    const geometry = await focusGeometry(touch.locator('.wb-document-title'));
    return geometry.ring.bottom > geometry.ring.top && geometry.ring.right > geometry.ring.left && geometry.clips.every(clip =>
      (!clip.clipX || geometry.ring.right > clip.left && geometry.ring.left < clip.right) && (!clip.clipY || geometry.ring.bottom > clip.top && geometry.ring.top < clip.bottom));
  }, 'focused document title is visibly projected after the sidebar closes');
  assert.equal(await nativeButton(touch.locator('#debug-sidebar-toggle')).getAttribute('aria-expanded'), 'false');
  await showSidebar(touch); await clickRoute(touch, anchor(recent(touch, '/alpha')), '/alpha');
  await settled(() => touch.locator('.wb-document-title').evaluate(el => document.activeElement === el), 'closing the sidebar after touch Recent navigation moves focus to the document title');
  assert.equal(await nativeButton(touch.locator('#debug-sidebar-toggle')).getAttribute('aria-expanded'), 'false');
  await touchContext.close();
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  const auxiliaryPassed = auxiliaryResults.every(result => result.passed);
  console.log(JSON.stringify({passed: auxiliaryPassed, interfacePassed: true, auxiliaryPassed, auxiliaryResults,
    fixtureOrigin: base, liveReads: 0, protectedRuntimeReads: 0, fixtureReads: reads.length, revealSettles, screenshots}, null, 2));
  if (!auxiliaryPassed) process.exitCode = 1;
} catch (error) {
  await activePage?.screenshot({path: '/private/tmp/shrine-sidebar-navigation-failure.png', animations: 'disabled'}).catch(() => {});
  console.error(JSON.stringify({reads, writes, unexpected, errors}, null, 2)); throw error;
} finally {
  try { await browser.close(); }
  finally {
    if (fixtureServer?.listening) {
      fixtureServer.closeAllConnections();
      await new Promise((resolve, reject) => fixtureServer.close(error => error ? reject(error) : resolve()));
    }
  }
}
