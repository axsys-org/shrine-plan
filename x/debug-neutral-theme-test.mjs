// Real saved debugger shell + frozen local assets. No namespace or network fallback.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; live runtime access is forbidden');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-neutral-theme-fixture.invalid';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const versions = Object.fromEntries([...assets].map(([path, {body}]) => [path, createHash('sha256').update(body).digest('hex')]));
const reads = [], unexpected = [], errors = [], measurements = [], screenshots = [], contexts = [];
let passed = false, fixtures = {};
const browser = await chromium.launch();

function neutral(sample, label) {
  assert.ok(sample && sample[3] > 0, label + ' has visible paint: ' + JSON.stringify(sample));
  assert.ok(Math.max(...sample.slice(0, 3)) - Math.min(...sample.slice(0, 3)) <= 2,
    label + ' is monochrome: ' + JSON.stringify(sample));
}
async function paints(locator) {
  return locator.evaluate(element => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d', {willReadFrequently: true});
    const rgba = value => { context.clearRect(0, 0, 1, 1); context.fillStyle = value; context.fillRect(0, 0, 1, 1); return [...context.getImageData(0, 0, 1, 1).data]; };
    const css = getComputedStyle(element), selected = getComputedStyle(element, '::selection');
    const box = element.getBoundingClientRect();
    return {color: rgba(css.color), background: rgba(css.backgroundColor), border: rgba(css.borderInlineStartColor),
      outline: rgba(css.outlineColor), outlineStyle: css.outlineStyle, outlineWidth: parseFloat(css.outlineWidth),
      selection: {color: rgba(selected.color), background: rgba(selected.backgroundColor)},
      width: box.width, height: box.height, text: element.textContent.trim()};
  });
}
async function ready(page) {
  await page.waitForFunction(() => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === '/app/srs' && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, null, {timeout: 5000});
  await page.waitForFunction(() => {
    const legacy = document.querySelector('link[href="/style.css"]');
    return legacy?.disabled || legacy?.sheet?.disabled;
  }, null, {timeout: 5000});
}
async function settled(page) {
  await page.waitForFunction(() => {
    const roots = [document];
    for (const root of roots) for (const element of root.querySelectorAll('*')) {
      if (['ui-reveal', 'ui-menu', 'ui-tooltip', 'ui-preview-card'].includes(element.localName) &&
        element.matches(':state(entering), :state(exiting)')) return false;
      if (element.shadowRoot) roots.push(element.shadowRoot);
    }
    return true;
  }, null, {timeout: 5000});
}
async function capture(page, name) {
  await settled(page);
  const path = '/private/tmp/shrine-neutral-' + name + '.png';
  await page.screenshot({path}); screenshots.push(path);
}
try {
  const author = await browser.newPage();
  fixtures = await author.evaluate(shell => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw Error('Saved shell anatomy is not supported');
    const children = {'/': ['/app'], '/app': ['/app/srs', '/app/other'], '/app/srs': ['/app/srs/cards'], '/app/other': [], '/app/srs/cards': []};
    return Object.fromEntries(Object.entries(children).map(([path, paths]) => {
      const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
      Object.assign(ws.dataset, {path, kind: 'record', writable: 'false', label: path === '/app/srs' ? 'Spaced repetition' : path,
        fixture: 'neutral-theme', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch', 'description', 'descriptionSource']) delete ws.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, text] of [['/sys/lede', 'Spaced repetition'], ['/sys/help', 'Review cards in their namespace.'], ['/value', 'Exact namespace value']]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.title = key;
        const pail = doc.createElement('sh-pail'); pail.textContent = text;
        limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      const semantics = doc.querySelector('#debug-main section[aria-label=Semantics]');
      const note = doc.createElement('p'); note.id = 'fixture-statuses';
      for (const [tone, text] of [['positive', 'Validation passed'], ['critical', 'Validation failed']]) {
        const badge = doc.createElement('ui-badge'); badge.setAttribute('tone', tone); badge.textContent = text; note.append(badge);
      }
      semantics.append(note);
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of paths) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
        item.dataset.kind = 'record'; item.dataset.label = child.split('/').at(-1); item.title = item.dataset.label; tree.append(item);
      }
      return ['/debug' + (path === '/' ? '' : path), '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, shell);
  await author.close();

  for (const [theme, coarse] of [['light', false], ['dark', false], ['light', true], ['dark', true]]) {
    const context = await browser.newContext({viewport: {width: coarse ? 390 : 1440, height: 960},
      hasTouch: coarse, isMobile: coarse, colorScheme: theme, reducedMotion: 'reduce'});
    contexts.push(context); context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    await context.addInitScript(base => {
      if (typeof ServiceWorkerContainer !== 'undefined') Object.defineProperty(ServiceWorkerContainer.prototype, 'register', {
        configurable: true, value() { return Promise.reject(Error('Fixture forbids service workers')); },
      });
      if (location.origin !== base) return;
      localStorage.setItem('shrine-debug.v1.saved', JSON.stringify(['/app/srs']));
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: true, root: '/', expanded: ['/', '/app', '/app/srs']}));
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
    const page = await context.newPage(); await page.goto(base + '/debug/app/srs'); await ready(page);
    const name = theme + (coarse ? '-390-touch' : '-1440-keyboard');
    const sample = {name}; measurements.push(sample);
    sample.hero = await paints(page.locator('.wb-document-heading > .wb-icon'));
    neutral(sample.hero.color, name + ' main record icon'); neutral(sample.hero.background, name + ' main record icon surface');
    const pathRow = page.locator('sh-path-row').first();
    sample.path = await paints(pathRow.locator('a[part=link]'));
    neutral(sample.path.color, name + ' child path link');
    sample.pathIcon = await paints(pathRow.locator('ui-icon[slot=icon]'));
    neutral(sample.pathIcon.color, name + ' child path icon');
    const breadcrumb = page.locator('#wb-path-locator ui-link[current] a');
    sample.breadcrumb = await paints(breadcrumb); neutral(sample.breadcrumb.color, name + ' current breadcrumb');
    neutral(sample.breadcrumb.background, name + ' current breadcrumb surface');
    // Real authored statuses pass through the production semantic document adapter.
    sample.positive = await paints(page.locator('#fixture-statuses ui-badge[tone=positive] [part=root]'));
    sample.critical = await paints(page.locator('#fixture-statuses ui-badge[tone=critical] [part=root]'));
    assert.ok(sample.positive.background[1] > sample.positive.background[0] + 10, name + ' actual positive badge stays green');
    assert.ok(sample.critical.background[0] > sample.critical.background[1] + 10, name + ' actual critical badge stays red');
    const value = page.locator('.wb-properties sh-pail').filter({hasText: 'Exact namespace value'}).first();
    await value.evaluate(element => { const range = document.createRange(); range.selectNodeContents(element); const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range); });
    sample.value = await paints(value); neutral(sample.value.selection.background, name + ' selected namespace text background');
    neutral(sample.value.selection.color, name + ' selected namespace text foreground');
    await page.evaluate(() => getSelection().removeAllRanges());
    await capture(page, name + '-main');

    if (coarse) await page.locator('#debug-sidebar-toggle').tap();
    await page.waitForFunction(() => document.querySelector('#debug-section-tree')?.shadowRoot?.querySelector('ui-reveal')?.matches(':state(active)'), null, {timeout: 5000});
    const current = page.locator('#debug-path-tree ui-tree-item[data-path="/app/srs"]');
    await current.waitFor();
    await page.waitForFunction(() => document.querySelector('#debug-path-tree ui-tree-item[data-path="/app/srs"]')?.hasAttribute('selected'), null, {timeout: 5000});
    const row = current.locator(':scope > [part=root] > button[part=control]');
    if (!coarse) { await page.keyboard.press('Tab'); await row.focus(); }
    sample.tree = await paints(row); neutral(sample.tree.color, name + ' current tree text');
    neutral(sample.tree.background, name + ' selected tree surface'); neutral(sample.tree.border, name + ' current tree rail');
    sample.treeIcon = await paints(current.locator(':scope > ui-icon[slot=icon]')); neutral(sample.treeIcon.color, name + ' current tree icon');
    if (!coarse) { assert.equal(sample.tree.outlineStyle, 'solid'); neutral(sample.tree.outline, name + ' keyboard tree outline'); }
    else assert.ok(sample.tree.height >= 44 && sample.tree.width >= 44, 'real current tree native touch target stays44px');
    await page.waitForFunction(() => [...document.querySelectorAll('#debug-path-tree ui-tree-item[expanded]')].every(item => item.dataset.readState === 'ready'), null, {timeout: 5000});
    const beforeFilterReads = reads.length;
    const identity = await current.evaluateHandle(element => ({row: element, path: element.querySelector('ui-path')}));
    const filter = page.locator('#debug-filter input'); await filter.fill('srs');
    const mark = current.locator('ui-label.debug-search-label [part=highlight]').first();
    await mark.waitFor(); sample.search = await paints(mark);
    neutral(sample.search.color, name + ' matched path text'); neutral(sample.search.background, name + ' matched path surface');
    assert.equal(sample.search.text.toLowerCase(), 'srs', 'only the matching path substring is marked');
    assert.equal(await current.evaluate((element, before) => element === before.row && element.querySelector('ui-path') === before.path && before.path.getAttribute('path') === '/app/srs', identity), true,
      'filter retains native tree row, canonical ui-path identity and exact path');
    assert.equal(reads.length, beforeFilterReads, 'highlighting loaded text does not read the namespace');
    await capture(page, name + '-search');
    await filter.fill('');
    await page.waitForFunction(() => [...document.querySelectorAll('#debug-sidebar ui-label.debug-search-label')].every(label => !label.shadowRoot?.querySelector('[part~=highlight]')), null, {timeout: 5000});
    assert.equal(reads.length, beforeFilterReads, 'clearing a highlight does not read the namespace');
    await identity.dispose();
    await capture(page, name + '-tree');
    if (coarse) await page.locator('#debug-sidebar-toggle').tap();

    const menu = page.locator('.wb-path-menu[data-path="/app"]');
    const trigger = menu.getByRole('button', {name: 'Children of /app', exact: true});
    if (coarse) await trigger.tap(); else { await trigger.focus(); await trigger.press('ArrowDown'); }
    const selected = menu.locator('ui-menu-item[data-path="/app/srs"]');
    await selected.waitFor({state: 'visible'}); await settled(page);
    // Move away before checking persistent-current paint; focused/hover are separate below.
    await page.mouse.move(0, 950);
    sample.menuCurrent = await paints(selected.locator('[part=control]'));
    neutral(sample.menuCurrent.color, name + ' menu current text');
    // Current is a native trailing label, not a mandatory filled selection.
    if (sample.menuCurrent.background[3]) neutral(sample.menuCurrent.background, name + ' menu current surface');
    assert.equal(await selected.locator('[slot=shortcut]').innerText(), 'Current');
    sample.menuIcon = await paints(selected.locator('ui-icon[slot=prefix]')); neutral(sample.menuIcon.color, name + ' menu current icon');
    const other = menu.locator('ui-menu-item[data-path="/app/other"]');
    if (!coarse) {
      await other.locator('[part=control]').hover(); sample.menuHover = await paints(other.locator('[part=control]'));
      neutral(sample.menuHover.color, name + ' menu hover text'); neutral(sample.menuHover.background, name + ' menu hover background');
      // Pointer menus deliberately release keyboard focus. Begin a fresh real
      // keyboard interaction instead of sending navigation keys to document.body.
      await page.keyboard.press('Escape'); await settled(page);
      await trigger.press('ArrowDown');
      await page.waitForFunction(() => document.activeElement?.matches('ui-menu-item') &&
        document.activeElement.closest('.wb-path-menu')?.dataset.path === '/app', null, {timeout: 5000});
      await page.keyboard.press('Home'); await page.keyboard.press('End');
      const focused = menu.locator('ui-menu-item [part=control]:focus-visible');
      await focused.waitFor(); sample.menuKeyboard = await paints(focused);
      neutral(sample.menuKeyboard.color, name + ' menu keyboard text'); neutral(sample.menuKeyboard.background, name + ' menu keyboard surface');
    } else {
      assert.ok(sample.menuCurrent.height >= 44 && sample.menuCurrent.width >= 44, 'actual menu touch target stays44px');
    }
    await capture(page, name + '-menu');
    await page.keyboard.press('Escape'); await settled(page);
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/app/srs', 'theme inspection never changes namespace location');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no horizontal document overflow');
    await context.close();
  }
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []); passed = true;
  console.log(JSON.stringify({passed, fixtureReads: reads.length, liveReads: 0, writes: 0, themes: measurements.map(sample => sample.name), versions, screenshots}, null, 2));
} finally {
  await Promise.all(contexts.map(context => context.close().catch(() => {}))); await browser.close();
  await writeFile('/private/tmp/shrine-neutral-theme-evidence.json', JSON.stringify({passed, reads, unexpected, errors, versions, measurements, screenshots}, null, 2));
}
