// Exact Saved/Recent row composition, using built production styles and Mash.
// All requests are fulfilled locally; there is no live namespace fallback.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const origin = 'http://page-spacing-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {contentType, body: await readFile(resolve(root, path))}])));
const names = ['fresh', 'Namespace', 'srs', 'sys', 'weft', 'app'];
const rows = saved => names.map((name, i) => `<div class="debug-page-row" data-path="/${name}">
  <ui-link class="debug-page-link" variant="quiet" size="small" href="/debug/${name}" ${i === 0 ? 'current' : ''}><ui-icon class="wb-icon" slot="prefix" name="object.document"></ui-icon><ui-label>${name}</ui-label></ui-link>
  ${saved ? `<ui-button icon-only size="small" variant="ghost" aria-label="Unsave ${name}"><ui-icon name="action.dismiss"></ui-icon></ui-button>` : ''}
</div>`).join('');
const html = `<!doctype html><html data-mash-catalogue="mash"><head><meta charset="utf-8"><link rel="stylesheet" href="/components.css"><link rel="stylesheet" href="/debug.css"><script defer src="/mash.js"></script></head>
<body><div class="debug-shell"><sh-sidebar id="debug-sidebar" style="width:min(440px,100vw)"><div id="debug-saved">${rows(true)}</div><div id="debug-history">${rows(false)}</div></sh-sidebar></div></body></html>`;
const browser = await chromium.launch(), unexpected = [], errors = [], evidence = [];
try {
  for (const options of [{width: 1197, theme: 'light'}, {width: 390, theme: 'dark'}, {width: 390, theme: 'light', touch: true}]) {
    const {width, theme, touch = false} = options;
    const context = await browser.newContext({viewport: {width, height: 820}, colorScheme: theme, hasTouch: touch, serviceWorkers: 'block'});
    await context.route('**/*', route => {
      const req = route.request(), url = new URL(req.url());
      if (req.method() !== 'GET' || url.origin !== origin) { unexpected.push(req.url()); return route.abort(); }
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: html});
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
      unexpected.push(req.url()); return route.abort();
    });
    const page = await context.newPage(); page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin);
    await page.evaluate(async theme => {
      document.documentElement.dataset.theme = theme;
      for (const tag of ['sh-sidebar', 'ui-link', 'ui-button', 'ui-label', 'ui-icon']) await customElements.whenDefined(tag);
      await Promise.all([...document.querySelectorAll('ui-link, ui-button')].map(el => el.updateComplete));
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }, theme);
    async function checkSpacing() {
      for (const id of ['debug-saved', 'debug-history']) {
        const boxes = await page.locator(`#${id} .debug-page-row:not([hidden]) > ui-link`).evaluateAll(links => links.map(link => {
          const rect = link.shadowRoot.querySelector('[part=control]').getBoundingClientRect();
          return {top: rect.top, bottom: rect.bottom, height: rect.height};
        }));
        assert.ok(boxes.length >= 3);
        for (const [i, box] of boxes.entries()) {
          assert.equal(box.height, touch ? 44 : 24, 'Mash control heights remain unchanged');
          if (i) assert.equal(box.top - boxes[i - 1].bottom, 1, `${id}: exactly 1px between native row surfaces`);
        }
      }
    }
    await checkSpacing();
    const link = page.locator('#debug-saved ui-link').nth(1).locator('a[part=control]');
    await link.focus();
    assert.equal(await link.evaluate(el => getComputedStyle(el).outlineStyle), 'solid');
    assert.equal(await link.evaluate(el => getComputedStyle(el).outlineOffset), '-2px', 'keyboard focus does not collide with adjacent rows');
    await link.blur();
    if (!touch) await link.hover();
    const screenshot = `/private/tmp/shrine-page-spacing-${theme}-${width}-${touch ? 'coarse' : 'fine'}.png`;
    await page.locator('#debug-sidebar').screenshot({path: screenshot});
    // Filtered rows must not leave either their old padding or a double gap.
    await page.locator('#debug-saved .debug-page-row').nth(2).evaluate(el => { el.hidden = true; });
    await page.locator('#debug-history .debug-page-row').nth(2).evaluate(el => { el.hidden = true; });
    await checkSpacing();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    evidence.push({...options, gap: 1, rowHeight: touch ? 44 : 24, screenshot});
    await context.close();
  }
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, evidence, unexpected, errors}));
} finally { await browser.close(); }
