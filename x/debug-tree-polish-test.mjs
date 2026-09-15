// Production Mash + debugger styles, inert markup only. Never reads a namespace.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const base = 'http://tree-polish-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/mash.js', '.debug-assets/mash.js', 'text/javascript'],
  ['/components.css', '.debug-assets/components.css', 'text/css'],
  ['/debug.css', 'debug.css', 'text/css'],
].map(async ([url, file, contentType]) => [url, {contentType, body: await readFile(root + '/src/foil/' + file)}])));
const icon = (slot, name) => `<ui-icon slot="${slot}" name="${name}" size="small"></ui-icon>`;
const bookmark = `<ui-button slot="actions" size="small" icon-only variant="ghost" aria-label="Save path">${icon('', 'object.bookmark')}</ui-button>`;
const row = (title, extra = '', children = '') => `<ui-tree-item actions-display="overlay" title="${title}" ${extra}>${icon('disclosure', 'navigation.disclosure')}${icon('icon', 'object.document')}
  <ui-path slot="meta" path="/test" size="small"><span slot="title">Authored namespace lore with a long title that fades at the edge.</span></ui-path>${bookmark}${children}</ui-tree-item>`;
const html = `<!doctype html><html data-mash-catalogue="mash"><head><meta name="viewport" content="width=device-width"><link rel="stylesheet" href="/components.css"><link rel="stylesheet" href="/debug.css"><script defer src="/mash.js"></script></head>
<body><div class="debug-shell"><div style="padding:12px;width:min(360px,100vw)">
<div id="debug-saved"><div class="debug-page-row"><ui-link variant="quiet" size="small" current class="debug-page-link" href="#">${icon('prefix', 'object.document')}Saved page</ui-link></div></div>
<sh-tree variant="namespace"><ui-tree slot="tree" label="Namespace">
${row('namespace', 'kind="folder" expanded', row('leaf', 'slot="children"'))}
${row('selected_path', 'current selected')}${row('ordinary_path')}
</ui-tree></sh-tree>
<ui-menu class="wb-path-menu" label="Paths" density="compact"><ui-button slot="trigger" size="small">Path menu</ui-button>
${Array.from({length: 24}, (_, i) => `<ui-menu-item class="mash-menu-rich" value="${i}">${icon('prefix','object.document')}<span class="mash-stack wb-path-option-copy"><strong class="wb-path-option-name">path_${i}</strong><small class="wb-path-option-lede">Namespace-authored description ${i}</small></span></ui-menu-item>`).join('')}
</ui-menu></div></div></body></html>`;
const browser = await chromium.launch(), errors = [], unexpected = [], evidence = [];
try {
  for (const [theme, touch, width] of [['light', false, 1197], ['dark', false, 390], ['light', true, 390]]) {
    const context = await browser.newContext({viewport: {width, height: 820}, hasTouch: touch, serviceWorkers: 'block'});
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET' || url.origin !== base) {unexpected.push(request.url()); return route.abort();}
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: html});
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
      unexpected.push(request.url()); return route.abort();
    });
    const page = await context.newPage(); page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.evaluate(async theme => {
      document.documentElement.dataset.theme = theme;
      for (const tag of ['ui-tree-item', 'ui-menu', 'ui-scroll-area']) await customElements.whenDefined(tag);
      await Promise.all([...document.querySelectorAll('*')].map(el => el.updateComplete));
    }, theme);
    const selected = page.locator('ui-tree-item[selected]');
    const geometry = await page.evaluate(() => {
      const part = (el, name) => el.shadowRoot.querySelector(`[part="${name}"]`);
      const rows = [...document.querySelectorAll('ui-tree-item')], saved = part(document.querySelector('#debug-saved ui-link'), 'control');
      return {saved: saved.getBoundingClientRect().height, rows: rows.map(el => {
        const control = part(el, 'control'), style = getComputedStyle(control);
        return {height: control.getBoundingClientRect().height, radius: style.borderRadius, border: style.borderWidth};
      }), parent: part(rows[0], 'icon').getBoundingClientRect().left, child: part(rows[1], 'icon').getBoundingClientRect().left};
    });
    assert.equal(geometry.saved, touch ? 44 : 24);
    assert.ok(geometry.rows.every(row => row.height === geometry.saved && row.radius === '8px' && row.border === '0px'), JSON.stringify(geometry));
    assert.equal(geometry.parent, geometry.child);
    if (!touch) {
      const fill = await selected.getByRole('treeitem').evaluate(el => getComputedStyle(el).backgroundColor);
      await selected.getByRole('treeitem').hover();
      await page.waitForFunction(() => +getComputedStyle(document.querySelector('ui-tree-item[selected]').shadowRoot.querySelector('[part=actions]')).opacity === 1);
      const colors = await selected.evaluate(el => ({fill: getComputedStyle(el.shadowRoot.querySelector('[part=control]')).backgroundColor, fade: getComputedStyle(el.shadowRoot.querySelector('[part=actions]')).backgroundImage}));
      assert.equal(colors.fill, fill); assert.ok(colors.fade.includes(fill), JSON.stringify(colors));
    }
    const treeScreenshot = `/private/tmp/shrine-tree-polish-${theme}-${touch ? 'touch' : 'desktop'}.png`;
    await page.locator('sh-tree').screenshot({path: treeScreenshot});
    await page.locator('ui-menu > ui-button').click();
    await page.waitForFunction(() => document.querySelector('ui-menu').matches(':state(active)'));
    const scroll = page.locator('ui-menu ui-scroll-area');
    await scroll.evaluate(el => el.updateComplete);
    const scrollState = await scroll.evaluate(el => {const vp = el.viewportElement; return {mode: el.mode, size: el.size, overflow: vp.scrollHeight > vp.clientHeight, native: getComputedStyle(vp).scrollbarWidth, gutter: vp.offsetWidth - vp.clientWidth};});
    assert.equal(scrollState.mode, 'scrolling'); assert.equal(scrollState.size, 'medium'); assert.equal(scrollState.overflow, true);
    if (!touch) {assert.equal(scrollState.native, 'none'); assert.equal(scrollState.gutter, 0);}
    await scroll.evaluate(el => el.scrollViewportTo({top: 110, behavior: 'instant'}));
    await page.waitForFunction(() => document.querySelector('ui-menu').shadowRoot.querySelector('ui-scroll-area').matches(':state(visible)'));
    const menuScreenshot = `/private/tmp/shrine-menu-polish-${theme}-${touch ? 'touch' : 'desktop'}.png`;
    await page.locator('ui-menu [part=popup]').screenshot({path: menuScreenshot});
    await page.mouse.move(width - 5, 800);
    await page.waitForFunction(() => !document.querySelector('ui-menu').shadowRoot.querySelector('ui-scroll-area').matches(':state(visible)'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    evidence.push({theme, touch, geometry, scrollState, treeScreenshot, menuScreenshot});
    await context.close();
  }
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
  console.log(JSON.stringify({passed: true, evidence, errors, unexpected}));
} finally {await browser.close();}
