// Stylesheet handoff against frozen production assets and a saved real shell.
// Every request is intercepted at exact inert fixture origins. No live fallback,
// namespace operations, user storage, runtime lifecycle changes, or retries.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; no live namespace reads');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://stylesheet-fixture.invalid', foreign = 'https://foreign-stylesheet-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
  ['/stylesheets.js', 'src/foil/debug/stylesheets.js', 'application/javascript'],
].map(async ([url, file, contentType]) => [url, {body: await readFile(resolve(root, file), 'utf8'), contentType}])));
const marker = kind => '--shrine-debug-' + kind + '-ready';
const version = (path, kind) => {
  const matches = [...assets.get(path).body.matchAll(new RegExp(marker(kind) + '\\s*:\\s*(asset-[0-9a-f]{16})\\b', 'g'))];
  assert.equal(matches.length, 1, path + ' has one generated readiness footer'); return matches[0][1];
};
const versions = {appVersion: version('/debug.css', 'app'), componentsVersion: version('/debug-components.css', 'components')};
const probeCSS = '\n:root { --stylesheet-fixture-legacy-only: legacy-active; }\n';
assets.get('/style.css').body += probeCSS;
const reads = [], writes = [], unexpected = [], errors = [], expectedErrors = [], screenshots = [], cases = [];
let activePage;
const browser = await chromium.launch();
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, label) { for (let i = 0; i < 120; i++) { if (await check()) return; await wait(25); } assert.fail(label); }
try {
  const author = await browser.newPage();
  const fixtures = await author.evaluate(({shell, foreign}) => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell has incompatible record anatomy');
    return Object.fromEntries(['/', '/demo', '/child'].map(path => {
      const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
      Object.assign(ws.dataset, {path, kind: 'record', writable: 'true', label: 'Stylesheet fixture', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete ws.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, text] of [['/sys/lede', 'Authored stylesheet boundary'], ['/notes', '  Exact fixture text\n' + 'Readable record value '.repeat(30) + '\nTAIL  '], ['/a-long-authored-field-name', 'Complete authored slot value'], ['/reference', '/child']]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.title = key; const pail = doc.createElement('sh-pail');
        if (key === '/reference') { const link = doc.createElement('a'); link.href = '/debug/child'; link.textContent = text; pail.append(link); }
        else pail.textContent = text;
        limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]').replaceChildren();
      const semantics = doc.querySelector('#debug-main section[aria-label=Semantics]');
      const table = doc.createElement('ui-table'); table.id = 'fixture-table'; table.setAttribute('label', 'Authored values');
      for (const pair of [['Slot', 'Value'], ['A descriptive slot', 'A complete authored value'], ['State', 'ready']]) {
        const row = doc.createElement('ui-table-row');
        for (const value of pair) { const cell = doc.createElement('ui-table-cell'); cell.textContent = value; row.append(cell); }
        table.append(row);
      }
      semantics.append(table);
      const docs = doc.createElement('ui-card'), line = doc.createElement('p'); line.className = 'lore-line'; line.textContent = 'Authored documentation remains readable after the old catalogue stylesheet is disabled.'; docs.append(line);
      const example = doc.createElement('div'); example.className = 'row';
      const code = doc.createElement('pre'); code.className = 'dtsrc'; code.textContent = 'example fixture\n  preserving source spacing'; example.append(code); docs.append(example);
      doc.querySelector('#debug-main section[aria-label=Documentation]').append(docs);
      const form = doc.createElement('form'); form.action = '/fixture-write'; form.method = 'post';
      const input = doc.createElement('ui-input'); input.name = 'message'; input.setAttribute('label', 'Fixture message'); input.setAttribute('value', 'Preserved authored input');
      const button = doc.createElement('ui-button'); button.id = 'fixture-operation'; button.setAttribute('type', 'submit'); button.setAttribute('variant', 'secondary'); button.textContent = 'Apply fixture value';
      const disabled = doc.createElement('ui-button'); disabled.id = 'fixture-disabled'; disabled.setAttribute('type', 'submit'); disabled.setAttribute('disabled', ''); disabled.textContent = 'Unavailable action';
      form.append(input, button, disabled); doc.querySelector('#debug-main section[aria-label=Operations]').append(form);
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of path === '/' ? ['/demo', '/child'] : path === '/demo' ? ['/demo/child'] : []) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.title = child.split('/').at(-1); item.dataset.label = item.title; tree.append(item);
      }
      const originalLink = [...doc.querySelectorAll('link[rel=stylesheet]')].find(link => link.getAttribute('href') === '/style.css'); originalLink.id = 'legacy-primary';
      const duplicate = originalLink.cloneNode(); duplicate.id = 'legacy-predisabled'; duplicate.setAttribute('disabled', ''); doc.head.append(duplicate);
      for (const [id, href, media] of [['foreign-style', foreign + '/style.css', 'all'], ['query-style', '/style.css?other=1', 'all'], ['hash-style', '/style.css#other', 'not all'], ['other-style', '/other.css', 'all']]) {
        const link = doc.createElement('link'); link.rel = 'stylesheet'; link.href = href; link.id = id; link.media = media; doc.head.append(link);
      }
      const frame = doc.createElement('iframe'); frame.id = 'fixture-frame'; frame.src = '/frame'; frame.hidden = true; doc.body.append(frame);
      return [path, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, {shell, foreign});
  fixtures['/demo/child'] = fixtures['/child'].replaceAll('data-path="/child"', 'data-path="/demo/child"');
  await author.close();

  async function create(options = {}) {
    const {fault = null, direct = false, initFailure = false, ...browserOptions} = options;
    const context = await browser.newContext({viewport: {width: 1440, height: 960}, ...browserOptions});
    context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    const pending = [], requests = [], expectedFailures = [];
    await context.addInitScript(({base}) => {
      if (location.origin !== base) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: true, root: '/', expanded: ['/']}));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: ['/demo'], pages: [null], cursor: 0}));
    }, {base});
    context.on('page', page => page.on('pageerror', error => (initFailure ? expectedErrors : errors).push(error.message)));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url()); requests.push(url.href);
      if (request.method() !== 'GET') { writes.push(request.method() + ' ' + url); return route.abort(); }
      if (url.origin === foreign && url.pathname === '/style.css' && !url.search) return route.fulfill({contentType: 'text/css', body: ':root {--foreign-sheet: intact}'});
      if (url.origin !== base) { unexpected.push(url.href); return route.abort(); }
      if (url.pathname === '/style.css' && url.search === '?other=1') return route.fulfill({contentType: 'text/css', body: ':root {--query-sheet: intact}'});
      if (url.search) { unexpected.push(url.href); return route.abort(); }
      if (url.pathname === '/other.css') return route.fulfill({contentType: 'text/css', body: ':root {--other-sheet: intact}'});
      if (url.pathname === '/detached.css') return route.fulfill({contentType: 'text/css', body: '/* Intentional temporary nonmatching stylesheet. */'});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (url.pathname === '/frame') return route.fulfill({contentType: 'text/html', body: '<!doctype html><link id="frame-legacy" rel="stylesheet" href="/style.css"><p>Iframe legacy scope</p>'});
      if (url.pathname === '/controller') return route.fulfill({contentType: 'text/html', body: '<!doctype html><html><head><link id="legacy-primary" rel="stylesheet" href="/style.css"><link id="legacy-predisabled" rel="stylesheet" href="/style.css" disabled><script defer src="/debug-mash.js"></script><link rel="stylesheet" href="/debug-components.css"><link rel="stylesheet" href="/debug.css"></head><body><p>Direct lifecycle fixture</p></body></html>'});
      if (assets.has(url.pathname)) {
        const asset = {...assets.get(url.pathname)};
        if (fault?.path === url.pathname) {
          if (fault.kind === 'delay') return new Promise(resolve => pending.push(async () => { await route.fulfill(asset); resolve(); }));
          if (fault.kind === 'missing' || fault.kind === '503') { expectedFailures.push(url.pathname); return fault.kind === 'missing' ? route.abort('failed') : route.fulfill({status: 503, body: 'Expected stylesheet fixture failure'}); }
          if (fault.kind === 'stale') asset.body = asset.body.replace(new RegExp('(' + marker(fault.path === '/debug.css' ? 'app' : 'components') + '\\s*:)\\s*asset-[0-9a-f]+', 'g'), '$1 asset-deadbeef');
        }
        return route.fulfill(asset);
      }
      const path = url.pathname.startsWith('/debug') ? decodeURIComponent(url.pathname.slice(6)) || '/' : null;
      if (path && Object.hasOwn(fixtures, path)) {
        reads.push(path);
        // Remove the real caller's required header, provoking its actual
        // synchronous initialization failure before the commit boundary.
        const body = initFailure ? fixtures[path].replace(/<header\b[^>]*class="debug-header"[^>]*>[\s\S]*?<\/header>/, '') : fixtures[path];
        return route.fulfill({contentType: 'text/html', body});
      }
      unexpected.push(url.href); return route.abort();
    });
    const page = await context.newPage(); activePage = page;
    const target = base + (direct ? '/controller' : '/debug/demo');
    return {context, page, pending, requests, expectedFailures, target};
  }
  const state = page => page.evaluate(() => ({
    disabled: document.querySelector('#legacy-primary').disabled,
    retained: document.querySelector('#legacy-primary').isConnected,
    predisabled: document.querySelector('#legacy-predisabled').disabled,
    probe: getComputedStyle(document.documentElement).getPropertyValue('--stylesheet-fixture-legacy-only').trim(),
    tokens: Boolean(document.querySelector('style[data-mash-tokens]')?.sheet),
    untouched: ['foreign-style', 'query-style', 'hash-style', 'other-style'].filter(id => document.getElementById(id)).map(id => ({id, disabled: document.getElementById(id).disabled})),
  }));
  async function active(page, expected = true) {
    await settled(async () => { const value = await state(page); return value.disabled === expected && value.probe === (expected ? '' : 'legacy-active'); }, expected ? 'matching ready styles take over' : 'legacy stylesheet becomes enabled and effective');
    const value = await state(page); assert.equal(value.retained, true); assert.equal(value.predisabled, true, 'pre-disabled legacy state stays disabled');
    assert.equal(value.probe, expected ? '' : 'legacy-active', 'legacy-only fixture rule follows actual cascade ownership');
    assert.ok(value.untouched.every(link => !link.disabled), 'foreign, query/hash variants, and unrelated links remain untouched');
    return value;
  }
  async function ready(page, path = '/demo') {
    await page.waitForFunction(path => document.querySelector('#debug-workspace')?.dataset.path === path && document.querySelector('#debug-workspace')?.dataset.readState === 'ready' && document.querySelector('#debug-workspace')?.getAttribute('aria-busy') !== 'true', path, {timeout: 5000});
  }
  async function go(page, path) {
    await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
    const input = page.locator('#debug-go ui-input input'); await input.fill(path); await input.press('Enter'); await ready(page, path);
  }
  async function geometry(page) {
    const metrics = await page.evaluate(() => {
      const rect = el => { const r = el.getBoundingClientRect(); return {width: r.width, height: r.height, left: r.left, right: r.right}; };
      return {page: {width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth},
        header: rect(document.querySelector('.debug-header.wb-commandbar')),
        table: rect(document.querySelector('#fixture-table').shadowRoot.querySelector('[part~=table]')),
        cells: [...document.querySelectorAll('#fixture-table ui-table-cell')].map(cell => rect(cell.shadowRoot.querySelector('[part~=cell]'))),
        tokens: ['--color-surface', '--color-text', '--space-2', '--font-family-body'].map(key => [key, getComputedStyle(document.documentElement).getPropertyValue(key).trim()])};
    });
    assert.ok(metrics.page.scroll <= metrics.page.width + 1, 'document has no horizontal overflow: ' + JSON.stringify(metrics));
    assert.ok(metrics.header.right <= metrics.page.width + 1 && metrics.header.left >= -1, 'command bar stays in viewport');
    assert.ok(metrics.table.width > 80 && metrics.cells.every(cell => cell.width > 20 && cell.height > 10), 'authored table cells retain readable layout');
    assert.ok(metrics.cells.every(cell => cell.left >= metrics.table.left - 1 && cell.right <= metrics.table.right + 1), 'table cells remain inside their table');
    assert.ok(metrics.tokens[0][1] && metrics.tokens[1][1], 'Mash semantic palette remains active');
    assert.equal(await page.locator('.wb-lore-prose').textContent(), 'Authored documentation remains readable after the old catalogue stylesheet is disabled.');
    assert.match(await page.locator('.wb-properties sh-limb[data-key="/notes"] sh-pail pre').textContent(), /^  Exact fixture text\n[\s\S]*\nTAIL  $/);
    assert.equal(await page.locator('#fixture-disabled button').isDisabled(), true);
  }
  async function capture(page, name) {
    await page.locator('#debug-workspace').evaluate(el => el.shadowRoot.querySelector('ui-scroll-area[part=main-body]').scrollViewportTo({top: 0, behavior: 'instant'}));
    await geometry(page); const path = '/private/tmp/shrine-stylesheet-' + name + '.png';
    await page.screenshot({path, animations: 'disabled'}); screenshots.push(path);
  }

  const normal = await create(); await normal.page.goto(normal.target); await ready(normal.page); await active(normal.page);
  assert.equal((await state(normal.page)).tokens, true);
  const links = await normal.page.evaluateHandle(() => [...document.querySelectorAll('link[rel=stylesheet]')]);
  await normal.page.frameLocator('#fixture-frame').locator('#frame-legacy').waitFor({state: 'attached'});
  assert.equal(await normal.page.frameLocator('#fixture-frame').locator('#frame-legacy').evaluate(el => el.disabled), false, 'parent handoff never disables iframe styles');
  await geometry(normal.page); await go(normal.page, '/child'); await active(normal.page);
  assert.equal(await links.evaluate(links => links.every(link => link.isConnected)), true, 'navigation retains every stylesheet node');
  assert.equal(await normal.page.locator('link[href="/debug.css"]').count(), 1, 'navigation does not duplicate new styles');
  await go(normal.page, '/demo');
  for (const change of ['disabled', 'removed', 'media', 'tokens']) {
    const target = change === 'tokens' ? 'style[data-mash-tokens]' : 'link[href="/debug.css"]';
    const node = await normal.page.locator(target).elementHandle();
    await node.evaluate((el, change) => { if (change === 'disabled') el.disabled = true; else if (change === 'media') el.media = 'not all'; else el.remove(); }, change);
    await active(normal.page, false);
    await node.evaluate((el, change) => { if (change === 'disabled') el.disabled = false; else if (change === 'media') el.media = 'all'; else document.head.append(el); }, change);
    await active(normal.page); cases.push('automatic restoration: ' + change);
  }
  const appLink = normal.page.locator('link[href="/debug.css"]');
  await appLink.evaluate(el => el.media = '(min-width: 900px)'); await normal.page.setViewportSize({width: 768, height: 960}); await active(normal.page, false);
  await normal.page.setViewportSize({width: 1440, height: 960}); await active(normal.page); await appLink.evaluate(el => el.media = 'all');
  cases.push('media query change and recovery'); await normal.context.close();

  const bodyLinks = await create(); await bodyLinks.page.goto(bodyLinks.target); await ready(bodyLinks.page); await active(bodyLinks.page);
  for (const attribute of ['href', 'rel']) {
    const link = await bodyLinks.page.locator('link[href="/debug-components.css"]').elementHandle();
    assert.equal(await link.evaluate(el => el.parentElement === document.body), true, 'fixture preserves actual server body-link placement');
    await link.evaluate((el, attribute) => el.setAttribute(attribute, attribute === 'href' ? '/detached.css' : 'alternate'), attribute); await active(bodyLinks.page, false);
    await link.evaluate((el, attribute) => el.setAttribute(attribute, attribute === 'href' ? '/debug-components.css' : 'stylesheet'), attribute); await active(bodyLinks.page);
    cases.push('body fresh-link ' + attribute + ' away/back');
  }
  const tokenNode = await bodyLinks.page.locator('style[data-mash-tokens]').elementHandle();
  const tokenText = await tokenNode.textContent(); await tokenNode.evaluate(el => el.textContent = ''); await active(bodyLinks.page, false);
  await tokenNode.evaluate((el, text) => el.textContent = text, tokenText); await active(bodyLinks.page); cases.push('empty token content and recovery');
  const tokenMarker = await tokenNode.getAttribute('data-mash-tokens');
  await tokenNode.evaluate(el => el.removeAttribute('data-mash-tokens')); await active(bodyLinks.page, false);
  await tokenNode.evaluate((el, value) => el.setAttribute('data-mash-tokens', value), tokenMarker); await active(bodyLinks.page); cases.push('token marker removal and recovery');
  await bodyLinks.context.close();

  for (const path of ['/debug.css', '/debug-components.css']) {
    for (const kind of ['delay', 'missing', '503', 'stale']) {
      const test = await create({fault: {path, kind}});
      if (kind === 'delay') {
        await test.page.goto(test.target, {waitUntil: 'commit'});
        await settled(() => test.pending.length > 0, 'expected fresh stylesheet is held');
        await test.page.waitForFunction(() => document.querySelector('#legacy-primary')?.sheet, null, {timeout: 5000});
        await active(test.page, false); await Promise.all(test.pending.splice(0).map(release => release())); await ready(test.page); await active(test.page);
      } else {
        await test.page.goto(test.target); await ready(test.page); await active(test.page, false);
        assert.equal(await test.page.locator('#legacy-primary').evaluate(el => el.sheet.disabled), false);
      }
      cases.push(kind + ' ' + path); await test.context.close();
    }
  }

  const broken = await create({initFailure: true}); await broken.page.goto(broken.target);
  await settled(() => expectedErrors.length > 0, 'actual malformed caller throws before stylesheet commit');
  assert.match(expectedErrors[0], /classList|null/); await active(broken.page, false);
  assert.equal(await broken.page.locator('.debug-header').count(), 0, 'failure fixture only removes the required original header');
  cases.push('actual synchronous workbench failure preserves fallback'); await broken.context.close();

  const direct = await create({direct: true}); await direct.page.goto(direct.target);
  await direct.page.waitForFunction(() => document.querySelector('style[data-mash-tokens]')?.sheet, null, {timeout: 5000});
  await direct.page.evaluate(async versions => {
    const {beginStylesheetHandoff} = await import('/stylesheets.js');
    window.fixtureBegin = beginStylesheetHandoff; window.fixtureVersions = versions; window.fixtureController = beginStylesheetHandoff(versions);
  }, versions);
  await direct.page.evaluate(async () => {
    const extra = document.createElement('link'); extra.id = 'legacy-cssom-disabled'; extra.rel = 'stylesheet'; extra.href = '/style.css';
    await new Promise((resolve, reject) => { extra.onload = resolve; extra.onerror = reject; document.head.append(extra); }); extra.sheet.disabled = true;
  });
  const check = () => direct.page.evaluate(() => window.fixtureController.check());
  let status = await check(); assert.equal(status.ready, true); assert.equal(status.committed, false); await active(direct.page, false);
  await direct.page.evaluate(() => { try { throw new Error('Simulated synchronous caller initialization failure'); } catch {} });
  await active(direct.page, false); // Merely beginning the lifecycle cannot retire fallback.
  status = await direct.page.evaluate(() => window.fixtureController.commit()); assert.equal(status.active, true); assert.equal(status.disabledCount, 1); assert.equal(status.legacyCount, 3);
  await active(direct.page);
  assert.equal(await direct.page.evaluate(() => Object.isFrozen(window.fixtureController.check())), true);
  assert.equal(await direct.page.evaluate(() => window.fixtureBegin(window.fixtureVersions) === window.fixtureController), true, 'same document/version controller is idempotent');
  await direct.page.locator('link[href="/debug-components.css"]').evaluate(el => el.sheet.disabled = true); status = await check(); assert.equal(status.active, false); await active(direct.page, false);
  await direct.page.locator('link[href="/debug-components.css"]').evaluate(el => el.sheet.disabled = false); status = await check(); assert.equal(status.active, true); await active(direct.page);
  await direct.page.evaluate(() => { window.fixtureToken = document.querySelector('style[data-mash-tokens]'); window.fixtureToken.sheet.disabled = true; });
  assert.equal((await check()).active, false); await active(direct.page, false);
  await direct.page.evaluate(() => window.fixtureToken.sheet.disabled = false); assert.equal((await check()).active, true); await active(direct.page);
  await direct.page.evaluate(() => { const sheet = document.querySelector('link[href="/debug.css"]').sheet; window.fixtureRule = sheet.insertRule(':root {--shrine-debug-app-ready: asset-bad}', sheet.cssRules.length); });
  assert.equal((await check()).active, false); await active(direct.page, false);
  await direct.page.evaluate(() => document.querySelector('link[href="/debug.css"]').sheet.deleteRule(window.fixtureRule)); assert.equal((await check()).active, true); await active(direct.page);
  status = await direct.page.evaluate(() => window.fixtureController.restore()); assert.equal(status.committed, false); await active(direct.page, false); await direct.page.evaluate(() => window.fixtureController.commit()); await active(direct.page);
  await direct.page.evaluate(() => { window.fixtureOld = window.fixtureController; window.fixtureController = window.fixtureBegin({...window.fixtureVersions, appVersion: 'asset-deadbeef'}); });
  await active(direct.page, false); assert.equal((await check()).committed, false); assert.equal((await check()).ready, false);
  await direct.page.evaluate(() => { window.fixtureController = window.fixtureBegin(window.fixtureVersions); window.fixtureController.commit(); }); await active(direct.page);
  status = await direct.page.evaluate(() => window.fixtureController.dispose()); assert.equal(status.active, false); await active(direct.page, false);
  assert.equal(await direct.page.locator('#legacy-cssom-disabled').evaluate(el => el.sheet.disabled), true, 'initial CSSOM-disabled legacy remains disabled after restore/dispose');
  assert.equal((await direct.page.evaluate(() => window.fixtureController.commit())).active, false, 'disposed controllers cannot reacquire legacy ownership');
  status = await direct.page.evaluate(() => window.fixtureBegin({}).commit()); assert.equal(status.active, false); assert.equal(status.reason, 'invalid-versions'); await active(direct.page, false);
  cases.push('direct no-commit, CSSOM check, restore, supersession, disposal, and pre-disabled ownership'); await direct.context.close();

  for (const width of [1440, 768, 390]) for (const coarse of [false, true]) {
    const test = await create({viewport: {width, height: width === 390 ? 844 : 960}, hasTouch: coarse});
    await test.page.goto(test.target); await ready(test.page); await active(test.page);
    for (const scheme of ['light', 'dark']) {
      await test.page.emulateMedia({colorScheme: scheme, reducedMotion: 'reduce'});
      const toggle = test.page.locator('#debug-sidebar-toggle');
      if (width < 900 && await toggle.getAttribute('aria-expanded') === 'true') await toggle.click();
      await test.page.locator('.wb-doctests').evaluate(el => el.open = true);
      assert.equal(await test.page.locator('.wb-doctests pre').textContent(), 'example fixture\n  preserving source spacing', 'authored example text survives enhancement');
      await capture(test.page, scheme + '-' + width + (coarse ? '-touch' : ''));
      await test.page.getByRole('button', {name: 'Open operations', exact: true}).click();
      await test.page.locator('#fixture-operation button').waitFor({state: 'visible'});
      const action = await test.page.locator('#fixture-operation button').boundingBox();
      assert.ok(action.width >= (coarse ? 43.9 : 20) && action.height >= (coarse ? 43.9 : 20), 'operation uses native Mash target geometry');
      await test.page.locator('#fixture-operation button').focus(); await test.page.locator('#fixture-operation button').press('ArrowLeft');
      assert.equal(await test.page.locator('#fixture-operation button').evaluate(el => el.getRootNode().activeElement === el), true);
      const focus = await test.page.locator('#fixture-operation button').evaluate(el => {
        const style = getComputedStyle(el), rect = el.getBoundingClientRect(), outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
        return {visible: el.matches(':focus-visible'), outline: style.outlineStyle, width: parseFloat(style.outlineWidth), left: rect.left - outset, right: rect.right + outset, viewport: innerWidth};
      });
      assert.ok(focus.visible && focus.outline !== 'none' && focus.width > 0 && focus.left >= 0 && focus.right <= focus.viewport,
        'fresh shared action focus ring remains visible and horizontally contained: ' + JSON.stringify(focus));
      if (width === 390 && coarse) {
        const path = '/private/tmp/shrine-stylesheet-operations-' + scheme + '-390-touch.png';
        await test.page.screenshot({path, animations: 'disabled'}); screenshots.push(path);
      }
      await test.page.getByRole('button', {name: 'Open operations', exact: true}).click();
    }
    // Sidebar actions now bookmark paths. The main path-row preview remains
    // explicitly operable on both pointer and touch devices.
    const toggle = test.page.locator('#debug-sidebar-toggle');
    if (width < 900 && await toggle.getAttribute('aria-expanded') === 'true') await toggle.click();
    const item = test.page.locator('sh-path-row.wb-child-row[data-path="/demo/child"]');
    await item.locator('ui-button[part~="toggle"] button').click();
    const preview = item.locator('.wb-child-preview sh-myth.wb-preview-record'); await preview.waitFor({state: 'visible'});
    await settled(() => preview.evaluate(el => el.getBoundingClientRect().height > 30 && [...el.querySelectorAll('sh-limb')].every(limb => limb.getBoundingClientRect().height > 10)), 'preview body is actually projected, not zero-height clipped');
    const narrow = await preview.evaluate(el => el.getBoundingClientRect().width <= 28 * parseFloat(getComputedStyle(document.documentElement).fontSize));
    for (const limb of await preview.locator('sh-limb').all()) {
      const key = await limb.locator(':scope > sh-slot').boundingBox(), value = await limb.locator(':scope > sh-pail').boundingBox();
      assert.ok(key.width > 20 && value.width > 20, 'preview key and value retain useful width');
      if (narrow) assert.ok(value.y >= key.y + key.height + 3.4, 'narrow record container keeps complete key above its value: ' + JSON.stringify({key, value}));
      else if ((await limb.locator(':scope > sh-slot').textContent()).length <= 20) assert.ok(value.x >= key.x + key.width - .6, 'ordinary short keys retain columns in a wide record container');
    }
    const shot = '/private/tmp/shrine-stylesheet-preview-' + width + (coarse ? '-touch' : '') + '.png'; await test.page.screenshot({path: shot, animations: 'disabled'}); screenshots.push(shot);
    await test.context.close();
  }
  assert.deepEqual(writes, [], 'no write attempts'); assert.deepEqual(unexpected, [], 'every request matched an inert fixture'); assert.deepEqual(errors, [], 'no browser script errors');
  console.log(JSON.stringify({passed: true, cases, fixtureReads: reads.length, liveReads: 0, writes: 0, unexpected: 0, errors: 0, expectedInitializationErrors: expectedErrors, versions, screenshots}, null, 2));
} catch (error) {
  if (activePage && !activePage.isClosed()) { await activePage.screenshot({path: '/private/tmp/shrine-stylesheet-failure.png', animations: 'disabled'}).catch(() => {}); console.error(JSON.stringify({url: activePage.url(), errors, unexpected, writes}, null, 2)); }
  throw error;
} finally { await browser.close(); }
