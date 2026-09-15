// Shrine record composition and fidelity from a mandatory saved shell.
// Every request is intercepted at an inert fixture origin; no live fallback.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; no live namespace reads');
const base = 'http://debug-records-fixture.invalid';
const root = fileURLToPath(new URL('..', import.meta.url));
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const appCSS = await readFile(resolve(root, 'src/foil/debug/workbench.css'), 'utf8') + '\n' + await readFile(resolve(root, 'src/foil/debug/sidebar.css'), 'utf8');
assert.doesNotMatch(appCSS, /(?:\.wb-slot-row|\.debug-preview-slot|sh-limb)[^{]*\{[^}]*grid-template-columns/s,
  'the debugger composes record slots without overriding the Mash limb grid');
const initialHTML = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const longKey = '/' + 'unbroken_namespace_field_'.repeat(18);
const longText = '  \n' + Array.from({length: 180}, (_, index) =>
  'Fixture line ' + String(index).padStart(3, '0') + ': ' + 'complete authored data '.repeat(5)).join('\n') +
  '\n<img src="/__records_xss__" onerror="window.__recordsXSS=true">' +
  '\n<script>window.__recordsXSS=true</script>\nTAIL_MARKER_7a1c9\n  ';
assert.ok(longText.length > 12000);
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const reads = [], writes = [], unexpected = [], errors = [];
const fixtures = await page.evaluate(({html, longText, longKey}) => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  const make = (path, fields, children = []) => {
    const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
    ws.dataset.path = path; ws.dataset.kind = 'record'; ws.dataset.writable = 'false';
    ws.dataset.label = 'Browser-only record fixture'; ws.dataset.renderUrl = '/ns' + (path === '/' ? '' : path);
    ws.dataset.fixture = 'debug-records';
    const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
    for (const [key, text, reference] of fields) {
      const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
      if (reference) limb.dataset.reference = reference;
      const label = doc.createElement('sh-slot'); label.setAttribute('title', key);
      const pail = doc.createElement('sh-pail');
      if (reference) { const link = doc.createElement('a'); link.href = '/ns' + reference; link.textContent = text; pail.append(link); }
      else pail.textContent = text;
      limb.append(label, pail); myth.append(limb);
    }
    for (const label of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + label + '"]')?.replaceChildren();
    const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
    for (const path of children) {
      const item = doc.createElement('ui-tree-item'); item.dataset.path = path; item.dataset.label = path.split('/').at(-1);
      item.setAttribute('title', item.dataset.label); tree.append(item);
    }
    return '<!doctype html>' + doc.documentElement.outerHTML;
  };
  return {'/app': html, '/': make('/', [['/sys/lede', 'Browser-only record fixture']], ['/app', '/__records__', '/notes', '/target']),
    '/__records__': make('/__records__', [['/sys/lede', 'Browser-only record fixture'], ['/notes', longText], [longKey, 'Unbroken key value'], ['/reference', '/target', '/target'], ['/tiny', '42']]),
    '/notes': make('/notes', [['/sys/lede', 'Fixture slot definition'], ['/definition', longText], ['/format', 'text']]),
    '/target': make('/target', [['/sys/lede', 'Fixture reference target'], ['/value', 'Referenced fixture value']])};
}, {html: initialHTML, longText, longKey});
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url());
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) { writes.push(request.url()); return route.abort(); }
  if (url.origin === base && assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (url.origin === base && /^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/'; reads.push(path);
    if (fixtures[path]) return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
  }
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
});
page.on('pageerror', error => errors.push(error.message));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); }
  assert.fail(message);
}
const properties = () => page.locator('#wb-canvas > sh-myth.wb-properties');
const notes = () => properties().locator('sh-limb[data-key="/notes"] sh-pail pre');
const definitionButton = () => properties().getByRole('button', {name: 'Inspect slot definition /notes', exact: true});
async function ready(path) {
  await page.waitForFunction(path => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, path);
}
async function go(path) {
  if (!await page.locator('#debug-go').isVisible()) await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill(path); await page.locator('#debug-go input').press('Enter'); await ready(path);
}
async function composition(myth, variant) {
  assert.equal(await myth.evaluate(el => el.localName), 'sh-myth');
  assert.equal(await myth.getAttribute('variant'), variant);
  assert.equal(await myth.getAttribute('data-mash-size'), 'compact');
  assert.equal(await myth.locator(':scope > .wb-slot-row:not(sh-limb), :scope > .debug-preview-slot:not(sh-limb)').count(), 0);
  for (const limb of await myth.locator(':scope > sh-limb').all()) {
    assert.equal(await limb.locator(':scope > sh-slot[slot=label]').count(), 1);
    assert.equal(await limb.locator(':scope > sh-pail[slot=value]').count(), 1);
  }
}
async function noOverflow() {
  const checks = await page.evaluate(() => {
    const surfaces = [document.documentElement, document.querySelector('#debug-main'), document.querySelector('.wb-inspector')].filter(Boolean);
    const collect = root => [...root.querySelectorAll('ui-scroll-area')].flatMap(area => [area.viewportElement, ...collect(area.shadowRoot || area)]).filter(Boolean);
    const walk = root => [...root.querySelectorAll('*')].flatMap(el => el.shadowRoot ? [...collect(el.shadowRoot), ...walk(el.shadowRoot)] : []);
    return [...new Set([...surfaces, ...walk(document)])].filter(el => el.clientWidth > 0).map(el => ({
      node: el.id || el.getAttribute('part') || el.localName, width: el.clientWidth, scroll: el.scrollWidth,
    }));
  });
  assert.ok(checks.every(check => check.scroll <= check.width + 1), 'all visible record and scroll surfaces wrap: ' + JSON.stringify(checks));
}
async function recordLayout() {
  const myth = properties();
  const longField = myth.locator('sh-limb').filter({has: page.locator('sh-slot[title="' + longKey + '"]')});
  const key = await longField.locator(':scope > sh-slot').boundingBox();
  const value = await longField.locator(':scope > sh-pail').boundingBox();
  const row = await longField.boundingBox();
  assert.ok(key.width >= row.width - 2, 'a long key wraps across the slot width instead of forming a narrow tower');
  assert.ok(value.y >= key.y + key.height - 1, 'the long-key value follows its complete label');
  assert.equal(await longField.locator('ui-button').textContent(), longKey, 'responsive flow preserves the complete slot key');
  const shortField = myth.locator('sh-limb[data-key="/tiny"]');
  const shortKey = await shortField.locator(':scope > sh-slot').boundingBox();
  const shortValue = await shortField.locator(':scope > sh-pail').boundingBox();
  const width = (await myth.boundingBox()).width;
  if (width <= 448) assert.ok(shortValue.y >= shortKey.y + shortKey.height - 1, 'narrow record containers stack even ordinary slots');
  else assert.ok(Math.abs(shortKey.y - shortValue.y) <= 2, 'wide record containers retain aligned short-key scanning');
}
async function inspectDefinition() {
  const url = page.url();
  const control = properties().locator('ui-button[data-inspect="/notes"]');
  assert.equal(await control.getAttribute('variant'), 'text');
  await definitionButton().click();
  await settled(async () => await page.locator('#debug-workspace').getAttribute('data-inspector-path') === '/notes', 'slot definition is shown in the inspector');
  assert.equal(page.url(), url, 'slot inspection does not navigate the working record');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/__records__');
  const myth = page.locator('.wb-inspector sh-myth.wb-inspector-record');
  await composition(myth, 'embedded');
  const definition = myth.locator('sh-limb[data-key="/definition"] sh-pail pre');
  await definition.waitFor({state: 'visible'});
  assert.equal(await definition.textContent(), longText);
  return myth;
}

try {
  await page.goto(base + '/debug/app'); await ready('/app');
  await go('/__records__');
  await notes().waitFor({state: 'visible'});
  await composition(properties(), 'embedded');
  assert.equal(await properties().locator(':scope > sh-limb').count(), 4);
  assert.equal(await notes().textContent(), longText, 'all supplied text, surrounding whitespace and tail marker are retained');
  assert.equal(await properties().locator('sh-limb').filter({has: page.locator('sh-slot[title="' + longKey + '"]')}).count(), 1);
  await recordLayout();
  assert.notEqual(await properties().locator('sh-limb[data-key="/reference"] a').evaluate(el => getComputedStyle(el).color), 'rgb(0, 0, 238)',
    'record references use the Mash recipe instead of browser-default link blue');
  assert.equal(await page.evaluate(() => window.__recordsXSS), undefined);
  assert.equal(await properties().locator('img, script').count(), 0, 'value text never becomes executable markup');
  const area = properties().locator('sh-limb[data-key="/notes"] ui-scroll-area.wb-code-scroll');
  await area.waitFor();
  assert.equal(await area.locator('pre').textContent(), longText, 'Mash scroll promotion does not shorten the underlying value');
  const viewport = area.locator('[part=viewport]'), bar = area.locator('[part=block-scrollbar]');
  await settled(() => viewport.evaluate(el => el.scrollHeight > el.clientHeight + 10), 'long value has a real bounded scroll viewport');
  assert.ok(await viewport.evaluate(el => el.clientHeight <= 18 * parseFloat(getComputedStyle(document.documentElement).fontSize) + 1));
  await bar.focus(); await bar.press('End');
  await settled(() => viewport.evaluate(el => Math.abs(el.scrollTop - (el.scrollHeight - el.clientHeight)) < 2), 'keyboard scrolling reaches the untruncated value tail');
  assert.equal(await properties().locator('sh-limb[data-key="/tiny"] ui-scroll-area').count(), 0, 'tiny scalars do not add focus regions');
  await noOverflow();

  const treeItem = page.locator('#debug-path-tree ui-tree-item[data-path="/__records__"]');
  await treeItem.locator(':scope > ui-path').hover();
  const surface = page.locator('#wb-path-preview');
  await settled(() => surface.evaluate(el => el.open && el.dataset.path === '/__records__' && el.dataset.readState === 'ready'),
    'the current tree path exposes its cached Myth leaf-out');
  const preview = surface.locator('sh-myth'); await preview.waitFor({state: 'visible'});
  await composition(preview, 'preview');
  assert.equal(await preview.locator(':scope > sh-limb').count(), 3, 'hover preview is a deliberate three-slot excerpt');
  assert.equal(await preview.locator('.wb-hover-value').first().textContent(), longText, 'preview retains the full source behind its visual excerpt');
  await page.keyboard.press('Escape');
  await settled(() => surface.evaluate(el => !el.open), 'Escape dismisses the passive leaf-out');
  console.log('PASS: actual embedded/preview Shrine composition, unbroken keys, complete >12k text, safe markup, bounded Mash scrolling and tiny-value restraint.');

  await inspectDefinition(); await noOverflow();
  const handle = page.getByRole('separator', {name: 'Resize inspector', exact: true});
  await handle.focus();
  for (let step = 0; step < 30 && Number(await handle.getAttribute('aria-valuenow')) > Number(await handle.getAttribute('aria-valuemin')); step++)
    await handle.press('ArrowRight');
  await settled(() => page.locator('.wb-inspector').evaluate(el => el.getBoundingClientRect().width <= 226), 'keyboard resize narrows the actual inspector to its minimum');
  await noOverflow();
  const definition = page.locator('.wb-inspector-record sh-limb[data-key="/definition"]');
  const label = await definition.locator(':scope > sh-slot').boundingBox(), value = await definition.locator(':scope > sh-pail').boundingBox();
  assert.ok(value.y >= label.y + label.height - 1, 'the Mash record container stacks slots in a narrow pane');
  await page.screenshot({path: '/private/tmp/shrine-records-narrow-inspector.png', animations: 'disabled'});
  await page.locator('#debug-inspector-toggle').click();
  const reference = properties().locator('sh-limb[data-key="/reference"] sh-pail > a');
  assert.equal(await reference.getAttribute('href'), '/debug/target');
  await reference.click(); await ready('/target');
  await page.locator('#debug-back').click(); await ready('/__records__');
  await notes().waitFor({state: 'visible'});
  assert.equal(await notes().textContent(), longText);
  console.log('PASS: text-variant slot actions inspect without navigation; responsive narrow-pane composition; real reference links navigate and preserve record fidelity on return.');

  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844]]) {
    await page.setViewportSize({width, height}); await page.goto(base + '/debug/__records__'); await ready('/__records__');
    await notes().waitFor({state: 'visible'});
    await noOverflow(); await recordLayout(); assert.equal(await notes().textContent(), longText);
    await page.screenshot({path: '/private/tmp/shrine-records-light-' + width + '.png', animations: 'disabled'});
    await inspectDefinition(); await noOverflow();
    await page.locator('#debug-inspector-toggle').click();
  }
  await page.setViewportSize({width: 1440, height: 1000});
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await page.goto(base + '/debug/__records__'); await ready('/__records__');
  await inspectDefinition(); await noOverflow();
  await page.screenshot({path: '/private/tmp/shrine-records-dark.png', animations: 'disabled'});
  assert.equal(await page.evaluate(() => window.__recordsXSS), undefined);
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log('PASS: 1440/768/390px light/dark records and definitions, no horizontal overflow; ' + (process.env.DEBUG_DOCUMENT ? 0 : 1) + ' real /app shell GET(s), ' + reads.length + ' fixture reads, no live journal reads or mutations.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-records-failure.png'});
  console.error('Record context:', {url: page.url(), reads, writes, unexpected, errors}); throw error;
} finally { await browser.close(); }
