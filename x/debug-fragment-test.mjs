// Capture only the explicitly restarted preview, then test frozen HTML/assets.
// No operation requests, persistent browser profiles or live test fallbacks.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const live = process.env.DEBUG_URL;
const documents = new Map();
if (process.env.DEBUG_DOCUMENT) documents.set('/debug', await readFile(process.env.DEBUG_DOCUMENT, 'utf8'));
else {
assert.equal(live, 'http://127.0.0.1:8138', 'Explicit fresh preview URL required');
for (const path of ['/debug', '/debug/gov/srs', '/debug/pact', '/debug/boot']) {
  const response = await fetch(live + path, {signal: AbortSignal.timeout(30000)});
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /data-debug-fragment="inspect"/);
  assert.doesNotMatch(html, /x-bad-selector/);
  documents.set(path, html);
}
await writeFile('/private/tmp/shrine-manifest-fragment.html', documents.get('/debug'));
}
const assets = new Map(await Promise.all([
  ['/debug-mash.js', '.debug-assets/mash.js', 'text/javascript'],
  ['/debug-components.css', '.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'debug.js', 'text/javascript'], ['/debug.css', 'debug.css', 'text/css'],
  ['/style.css', 'style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {contentType, body: await readFile(root + '/src/foil/' + path)}])));
const browser = await chromium.launch();
const violations = [], errors = [], checks = [];
const base = 'http://fragment-fixture.invalid';
try {
  for (const [name, app, width, touch] of [['mash-only', false, 1440, false], ['desktop', true, 1440, false], ['touch', true, 390, true]]) {
    const context = await browser.newContext({viewport: {width, height: 1000}, hasTouch: touch, isMobile: touch, reducedMotion: 'reduce'});
    context.setDefaultTimeout(5000);
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET' || url.origin !== base || url.search) {violations.push(request.url()); return route.abort();}
      if (url.pathname === '/debug.js') {
        const capture = 'window.__serverNodes=[...document.querySelectorAll("#debug-main,#wb-canvas,.wb-manifest, .wb-manifest sh-path-row, #wb-canvas > section[aria-label=Record] sh-limb")];\n';
        return route.fulfill({contentType: 'text/javascript', body: app ? capture + assets.get('/debug.js').body.toString() : ''});
      }
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (documents.has(url.pathname)) return route.fulfill({contentType: 'text/html', body: documents.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      violations.push(request.url()); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(name + ': ' + error.message));
    await page.goto(base + '/debug');
    await page.waitForFunction(() => customElements.get('sh-path-row') && document.querySelector('.wb-manifest ui-accordion-item').shadowRoot);
    if (app) {
      await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.readState === 'ready');
      assert.equal(await page.evaluate(() => __serverNodes.length > 10 && __serverNodes.every(node => node.isConnected)), true, 'server document node identity survives app initialization');
    }
    const manifest = page.locator('.wb-manifest');
    assert.match(await manifest.innerText(), /eden/);
    assert.match(await manifest.innerText(), /Eden: the live namespace/);
    const kooks = manifest.locator('ui-accordion-item[value=kooks]');
    assert.equal(await kooks.evaluate(node => node.open), true);
    await kooks.locator('button').first().click();
    assert.equal(await kooks.evaluate(node => node.open), false);
    await kooks.locator('button').first().click();
    assert.equal(await kooks.evaluate(node => node.open), true);
    const seed = manifest.locator('sh-path-row[previewable]').first();
    await seed.locator('ui-button').click();
    assert.equal(await seed.evaluate(node => node.open), true, 'Mash alone opens the authored seed preview');
    assert.ok(await seed.locator('sh-myth[slot=preview]').isVisible());
    await seed.locator('ui-button').click();
    const source = page.locator('#wb-canvas > section[aria-label=Record] ui-accordion-item[value=source]');
    assert.equal(await source.evaluate(node => node.open), false);
    await source.locator('button').first().click();
    assert.match(await source.innerText(), /mani\{name=eden/);
    assert.equal(await source.locator('ui-scroll-area[mode=scrolling][size=medium]').count() > 0, true);
    await source.locator('button').first().click();
    if (app) {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'responsive document has no horizontal overflow');
      await page.locator('.wb-document-header').scrollIntoViewIfNeeded();
      await page.screenshot({path: '/private/tmp/shrine-manifest-' + name + '.png'});
      if (!touch) {
        const row = page.locator('#debug-path-tree ui-tree-item[data-path="/"]');
        await row.locator('button[role=treeitem]').first().hover();
        const bookmark = row.locator(':scope > .debug-bookmark-toggle');
        await bookmark.click();
        assert.equal(await bookmark.getAttribute('aria-pressed'), 'true');
        await page.mouse.move(1400, 900);
        assert.equal(await row.evaluate(node => Number(getComputedStyle(node.shadowRoot.querySelector('[part=actions]')).opacity)), 1, 'keyboard focus keeps the bookmark reachable');
        await page.locator('.wb-document-title').focus();
        assert.equal(await row.evaluate(node => Number(getComputedStyle(node.shadowRoot.querySelector('[part=actions]')).opacity)), 0);
        assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/');
      }
    }
    checks.push(name);
    await context.close();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(violations, []);
  console.log(JSON.stringify({passed: checks, liveCaptureGETs: process.env.DEBUG_DOCUMENT ? 0 : documents.size, unexpectedRequests: violations, errors}));
} finally {await browser.close();}
