// Inspector case navigation over a saved document shell. All namespace values
// below are test-owned fixtures; no runtime, browser profile or write is used.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; no live fallback is permitted');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-inspector-cases-fixture.invalid';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const versions = Object.fromEntries([...assets].map(([name, asset]) => [name,
  createHash('sha256').update(asset.body).digest('hex')]));
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const casePath = (path, care, number) => '/h/' + care + '/' + number + '/' + path.split('/').filter(Boolean).length + (path === '/' ? '' : path);
const huge = '9007199254741099007199254741099';
const hugeShape = '9007199254741111007199254741111';
const top = '9007199254741999007199254741999';
const mainPath = '/app/cases', largePath = '/app/many-cases', absentPath = '/app/unreported';
const escapedPath = '/app/name #?%&/λ';
const raw = {top, first: '2', now: '0', block: '0', state: 'live'};
const ordinary = {...raw, x_data: '7', x_shape: '9', y_data: '2', y_shape: '3', z_data: '1', z_shape: '1'};
const specs = new Map([
  [mainPath, ordinary], [escapedPath, ordinary],
  [largePath, {...raw, x_data: '10000', x_shape: '20', y_data: huge, y_shape: hugeShape, z_data: '0', z_shape: '0'}],
  [absentPath, {top: '4', state: 'live', x_data: '0', x_shape: '0', y_shape: '4'}],
  ['/', {...raw, x_data: '1', x_shape: '1', y_data: '1', y_shape: '1', z_data: '1', z_shape: '1'}],
]);
// Explicit finite historical destinations: no arbitrary request fallback.
for (const [path, care, numbers] of [
  [mainPath, 'x', ['3']], [mainPath, 'y', ['1']], [mainPath, 'z', ['1']],
  [largePath, 'x', ['42', '9996']], [largePath, 'y', [huge]],
  [escapedPath, 'z', ['1']], ['/', 'x', ['1']],
]) for (const number of numbers) specs.set(casePath(path, care, number), {...raw});
const reads = [], unexpected = [], errors = [], screenshots = [], checks = [];
const browser = await chromium.launch();
let fixtures = Object.freeze({}), activePage, passed = false;
let heldRead = null;
const contexts = [];
async function newContext(options = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, ...options});
  contexts.push(context); context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
  await context.addInitScript(base => {
    // Unlike Playwright serviceWorkers:block, do not access the restricted
    // navigator getter inside the application's sandboxed rendered frame.
    if (typeof ServiceWorkerContainer !== 'undefined') Object.defineProperty(ServiceWorkerContainer.prototype, 'register', {
      configurable: true, value() { return Promise.reject(new Error('Case fixture forbids service workers')); },
    });
    if (location.origin !== base) return;
    localStorage.setItem('shrine-debug.v1.saved', '[]');
    localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: false, root: '/', expanded: ['/']}));
  }, base);
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (request.method() !== 'GET' || url.origin !== base || url.search || url.hash) {
      unexpected.push({url: request.url(), method: request.method()}); return route.abort();
    }
    if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
    if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
    const body = fixtures[url.pathname];
    if (!body) { unexpected.push({url: request.url(), method: request.method()}); return route.abort(); }
    reads.push(url.pathname);
    if (heldRead?.path === url.pathname) {
      heldRead.reached();
      await heldRead.wait;
    }
    return route.fulfill({status: 200, contentType: 'text/html', body});
  });
  context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
  return context;
}
async function ready(page, path) {
  await page.waitForFunction(path => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true';
  }, path, {timeout: 5000});
}
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
async function inspect(page) {
  if (!await page.locator('#debug-workspace').evaluate(element => element.inspectorOpen))
    await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  await settle(page);
  assert.equal(await page.locator('.wb-cases ui-accordion-item').count(), 3);
}
async function visit(page, path) {
  activePage = page; await page.goto(base + href(path)); await ready(page, path); await inspect(page);
}
const section = (page, care) => page.locator('.wb-cases ui-accordion-item[data-care="' + care + '"]');
const links = (page, care) => section(page, care).getByRole('link');
async function linkHrefs(page, care) { return links(page, care).evaluateAll(nodes => nodes.map(node => node.getAttribute('href'))); }
async function expectCases(page, path, care, numbers) {
  const expected = numbers.map(number => href(casePath(path, care, number)));
  assert.deepEqual(await linkHrefs(page, care), expected, care + ' links retain exact case identity and ascending order');
  assert.equal(await section(page, care).locator('.wb-case-link').count(), expected.length);
  assert.ok(expected.length <= 5, 'no more than five case links are mounted per care');
  for (const link of await links(page, care).all()) {
    assert.equal(await link.evaluate(node => node.localName), 'a', 'case actions are genuine native anchors');
    assert.equal(await link.getAttribute('aria-current'), null, 'latest local case is not misrepresented as current');
  }
}
async function counts(page, care, data, shape) {
  const item = section(page, care), suffix = item.locator(':scope > [slot=suffix]');
  assert.equal((await suffix.textContent()).trim(), `${data ?? '—'} data · ${shape ?? '—'} shape`);
  const header = item.getByRole('button').first();
  assert.equal(await header.getAttribute('aria-expanded'), 'true', 'all three case lists are initially open');
  assert.match(await header.getAttribute('aria-controls') || '', /\S/, 'Mash header controls its labelled case body');
  assert.equal(await item.getAttribute('title'), care + ' cases');
}
async function currentPath(page) { return page.locator('#debug-workspace').getAttribute('data-path'); }
async function primaryCase(page, source, care, number) {
  const destination = casePath(source, care, number), before = reads.length;
  // Find by exact native href, independent of optional accessible name prose.
  const targets = await links(page, care).all();
  const target = (await Promise.all(targets.map(async link => [link, await link.getAttribute('href')]))).find(([, url]) => url === href(destination))?.[0];
  assert.ok(target, 'expected native case destination exists');
  await target.click(); await ready(page, destination);
  assert.equal(new URL(page.url()).pathname, href(destination));
  assert.ok(reads.slice(before).includes(href(destination)), 'primary case action performs the matching fixture read');
  assert.equal(await currentPath(page), destination);
}
async function geometry(page, coarse = false) {
  const result = await page.evaluate(() => {
    const panel = document.querySelector('.wb-inspector'), box = panel.getBoundingClientRect();
    return {viewport: innerWidth, document: document.documentElement.scrollWidth, left: box.left, right: box.right,
      width: panel.clientWidth, scrollWidth: panel.scrollWidth,
      regions: [...panel.querySelectorAll('.wb-cases, .wb-case-jump, .wb-version')].map(node => {
        const rect = node.getBoundingClientRect(); return {name: node.className, left: rect.left, right: rect.right, width: rect.width};
      })};
  });
  assert.ok(result.document <= result.viewport + 1, 'the complete document never horizontally overflows');
  assert.ok(result.scrollWidth <= result.width + 1, 'exact large counters and controls fit the inspector');
  for (const region of result.regions) assert.ok(region.width > 0 && region.left >= result.left - 1 && region.right <= result.right + 1, JSON.stringify(region));
  if (coarse) {
    const controls = section(page, 'x').locator('a, button, input');
    const boxes = [];
    for (const control of await controls.all()) {
      if (!await control.isVisible()) continue;
      const box = await control.boundingBox();
      assert.ok(box.width >= 43.5 && box.height >= 43.5, 'actual native coarse target is at least44×44: ' + JSON.stringify(box));
      boxes.push(box);
    }
    for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
      const first = boxes[a], second = boxes[b];
      assert.ok(Math.min(first.x + first.width, second.x + second.width) - Math.max(first.x, second.x) <= .5 ||
        Math.min(first.y + first.height, second.y + second.height) - Math.max(first.y, second.y) <= .5, 'native touch targets do not overlap');
    }
  }
}
async function focusRing(control) {
  await control.scrollIntoViewIfNeeded(); await control.focus();
  await control.press('Tab'); await control.page().keyboard.press('Shift+Tab');
  const data = await control.evaluate(element => {
    const css = getComputedStyle(element), box = element.getBoundingClientRect();
    const reach = Math.max(0, parseFloat(css.outlineWidth) + parseFloat(css.outlineOffset));
    const ring = {left: box.left - reach, right: box.right + reach, top: box.top - reach, bottom: box.bottom + reach};
    const clips = [{name: 'viewport', x: true, y: true, left: 0, right: innerWidth, top: 0, bottom: innerHeight}];
    let node = element;
    while (node) {
      node = node.assignedSlot || node.parentNode;
      if (node instanceof ShadowRoot) node = node.host;
      if (!(node instanceof Element)) continue;
      const style = getComputedStyle(node), rect = node.getBoundingClientRect();
      const x = /^(auto|scroll|clip|hidden)$/.test(style.overflowX), y = /^(auto|scroll|clip|hidden)$/.test(style.overflowY);
      if (x || y) clips.push({name: node.id || node.getAttribute('part') || node.localName, x, y,
        left: rect.left + node.clientLeft, right: rect.left + node.clientLeft + node.clientWidth,
        top: rect.top + node.clientTop, bottom: rect.top + node.clientTop + node.clientHeight});
    }
    return {active: element.getRootNode().activeElement === element, outline: css.outlineStyle,
      width: parseFloat(css.outlineWidth), color: css.outlineColor, ring, clips};
  });
  assert.equal(data.active, true, 'native case destination retains keyboard focus');
  assert.ok(data.outline !== 'none' && data.width > 0 && !['transparent', 'rgba(0, 0, 0, 0)'].includes(data.color), 'native keyboard ring is visible');
  for (const clip of data.clips) assert.ok((!clip.x || data.ring.left >= clip.left - .6 && data.ring.right <= clip.right + .6) &&
    (!clip.y || data.ring.top >= clip.top - .6 && data.ring.bottom <= clip.bottom + .6), 'focus ring fits ' + JSON.stringify({clip, ring: data.ring}));
}
async function capture(page, name) {
  await settle(page); await geometry(page, await page.evaluate(() => matchMedia('(pointer:coarse)').matches));
  const path = '/private/tmp/shrine-inspector-cases-' + name + '.png';
  await page.screenshot({path}); screenshots.push(path);
}
try {
  const context = await newContext(), page = await context.newPage(); activePage = page;
  fixtures = Object.freeze(await page.evaluate(({shell, entries}) => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved document anatomy is unsupported');
    return Object.fromEntries(entries.map(([path, version]) => {
      const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
      Object.assign(workspace.dataset, {path, kind: 'record', writable: 'false', label: 'Case fixture',
        description: 'Test-owned case counters, not a runtime record.', descriptionSource: '/sys/help', fixture: 'inspector-cases',
        renderUrl: '/ns' + path.split('/').filter(Boolean).map(segment => '/' + encodeURIComponent(segment)).join('')});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, text] of [['/sys/lede', 'Case fixture'], ['/value', 'Test-owned scalar']]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
        const pail = doc.createElement('sh-pail'); pail.textContent = text; limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      const operation = doc.createElement('form'); operation.action = '/op/fixture'; operation.method = 'post';
      const operationSubmit = doc.createElement('ui-button'); operationSubmit.id = 'fixture-operation-submit';
      operationSubmit.setAttribute('type', 'submit'); operationSubmit.textContent = 'Test-owned operation';
      operation.append(operationSubmit); doc.querySelector('#debug-main section[aria-label=Operations]').append(operation);
      doc.querySelector('#debug-children').replaceChildren();
      const inspector = workspace.querySelector('[slot=inspector]'); inspector.replaceChildren();
      const table = doc.createElement('ui-table'); table.setAttribute('label', 'version');
      for (const [key, value] of Object.entries(version)) {
        const row = doc.createElement('ui-table-row'), keyCell = doc.createElement('ui-table-cell'), valueCell = doc.createElement('ui-table-cell');
        keyCell.textContent = '/' + key; valueCell.textContent = value; row.append(keyCell, valueCell); table.append(row);
      }
      inspector.append(table); doc.querySelector('#debug-activity')?.replaceChildren();
      const url = '/debug' + path.split('/').filter(Boolean).map(segment => '/' + encodeURIComponent(segment)).join('');
      return [url, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, {shell, entries: [...specs]}));

  await visit(page, mainPath);
  for (const care of ['x', 'y', 'z']) await counts(page, care, ordinary[care + '_data'], ordinary[care + '_shape']);
  await expectCases(page, mainPath, 'x', ['3', '4', '5', '6', '7']);
  await expectCases(page, mainPath, 'y', ['1', '2']); await expectCases(page, mainPath, 'z', ['1']);
  const metadata = await page.locator('.wb-version .wb-meta-row').evaluateAll(nodes => nodes.map(node => [...node.children].map(child => child.textContent.trim())));
  assert.deepEqual(Object.fromEntries(metadata), Object.fromEntries(Object.entries(raw).map(([key, value]) => ['/' + key, value])));
  assert.doesNotMatch(await page.locator('#debug-workspace').innerText(), /Record revision|Earlier values|\bfields\b/i, 'namespace UI uses cases and slots, not field or revision substitutes');
  await capture(page, 'ordinary-desktop');
  checks.push('all three cares, exact raw version metadata, semantic terminology');

  // A full reload never runs the outgoing/incoming setBusy lifecycle. Enter
  // another read-only record through the real SPA editor before testing jump.
  await page.evaluate(() => { window.caseSpaIdentity = 'retained'; });
  await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill(largePath);
  await page.locator('#debug-go input').press('Enter');
  await ready(page, largePath); await inspect(page);
  assert.equal(await page.evaluate(() => window.caseSpaIdentity), 'retained', 'the transition keeps the current document rather than reloading');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), 'false');
  const spaJump = section(page, 'x').locator('.wb-case-jump');
  assert.equal(await spaJump.getAttribute('data-debug-navigation'), 'case', 'the case form declares read-navigation intent');
  const spaSubmit = spaJump.locator('ui-button[type=submit] button');
  assert.equal(await spaSubmit.isDisabled(), false, 'read-only SPA navigation must re-enable the native case-jump submit button');
  assert.equal(await page.locator('#fixture-operation-submit button').isDisabled(), true, 'read-only operation submits remain disabled');
  const beforeSpaJump = reads.length;
  await spaJump.getByRole('textbox', {name: 'Open x case', exact: true}).fill('42');
  let reached, release;
  const reachedRead = new Promise(resolve => { reached = resolve; });
  const wait = new Promise(resolve => { release = resolve; });
  heldRead = {path: href(casePath(largePath, 'x', '42')), reached, wait, release};
  await spaSubmit.click();
  let readDeadline;
  try {
    await Promise.race([reachedRead, new Promise((_, reject) => {
      readDeadline = setTimeout(() => reject(new Error('The native case submit did not reach its fixture route')), 5000);
    })]);
    assert.equal(await spaSubmit.isDisabled(), true, 'pending read navigation still disables its native submit');
    assert.equal(await page.locator('#fixture-operation-submit button').isDisabled(), true, 'operations remain disabled while the case read is pending');
  } finally {
    clearTimeout(readDeadline); release(); heldRead = null;
  }
  await ready(page, casePath(largePath, 'x', '42'));
  assert.deepEqual(reads.slice(beforeSpaJump), [href(casePath(largePath, 'x', '42'))], 'native case submit is exactly one read, never an operation');
  checks.push('read-only SPA transition retains an enabled native case jump and its exact historical route');
  await visit(page, mainPath);

  const beforePaging = reads.length;
  await section(page, 'x').getByRole('button', {name: 'Older x cases', exact: true}).click();
  await expectCases(page, mainPath, 'x', ['1', '2']);
  assert.equal(await section(page, 'x').getByRole('button', {name: 'Older x cases', exact: true}).isDisabled(), true);
  await section(page, 'x').getByRole('button', {name: 'Newer x cases', exact: true}).click();
  await expectCases(page, mainPath, 'x', ['3', '4', '5', '6', '7']);
  assert.equal(await section(page, 'x').getByRole('button', {name: 'Newer x cases', exact: true}).isDisabled(), true);
  assert.equal(reads.length, beforePaging, 'case range paging performs zero namespace GETs');
  for (const [care, number] of [['x', '3'], ['y', '1'], ['z', '1']]) { await visit(page, mainPath); await primaryCase(page, mainPath, care, number); }
  await visit(page, escapedPath); await primaryCase(page, escapedPath, 'z', '1');
  await visit(page, '/'); await primaryCase(page, '/', 'x', '1');
  checks.push('bounded local paging without reads; native x/y/z, reserved segments and root history paths');

  await visit(page, largePath);
  await counts(page, 'x', '10000', '20'); await counts(page, 'y', huge, hugeShape);
  await expectCases(page, largePath, 'x', ['9996', '9997', '9998', '9999', '10000']);
  await expectCases(page, largePath, 'y', Array.from({length: 5}, (_, index) => String(BigInt(huge) - 4n + BigInt(index))));
  const beforeLargePaging = reads.length;
  await section(page, 'y').getByRole('button', {name: 'Older y cases', exact: true}).click();
  await expectCases(page, largePath, 'y', Array.from({length: 5}, (_, index) => String(BigInt(huge) - 9n + BigInt(index))));
  await section(page, 'y').getByRole('button', {name: 'Newer y cases', exact: true}).click();
  assert.equal(reads.length, beforeLargePaging);
  const jump = section(page, 'x').locator('.wb-case-jump'), input = jump.getByRole('textbox', {name: 'Open x case', exact: true});
  assert.equal(await input.evaluate(node => node.localName), 'input');
  assert.equal(await input.getAttribute('type'), 'text', 'case IDs never pass through Number input coercion');
  assert.equal(await input.evaluate(node => node.validity.valid), true, 'an untouched empty optional jump is not already an error');
  for (const value of ['', '0', '01', '+1', ' 1', '1 ', '1.0', '1e3', '10001']) {
    const before = reads.length; await input.fill(value); await input.press('Enter');
    assert.equal(await currentPath(page), largePath); assert.equal(reads.length, before, 'invalid exact case never reads');
    const validity = await input.evaluate(node => ({valid: node.validity.valid, message: node.validationMessage}));
    assert.equal(validity.valid, false, 'invalid case retains actual native invalidity: ' + JSON.stringify(value));
    assert.ok(validity.message, 'native validation explains the rejected case');
  }
  await input.fill('42'); await input.press('Enter'); await ready(page, casePath(largePath, 'x', '42'));
  await visit(page, largePath);
  const hugeInput = section(page, 'y').getByRole('textbox', {name: 'Open y case', exact: true});
  await hugeInput.fill(huge); await hugeInput.press('Enter'); await ready(page, casePath(largePath, 'y', huge));
  checks.push('10,000 and unsafe-integer counts; exact jump validation; huge route fidelity');

  await visit(page, absentPath);
  await counts(page, 'x', '0', '0'); await counts(page, 'y', null, '4'); await counts(page, 'z', null, null);
  assert.match(await section(page, 'x').innerText(), /No cases\./);
  for (const care of ['y', 'z']) assert.match(await section(page, care).innerText(), /Not reported\./);
  assert.equal(await page.locator('.wb-cases .wb-case-link, .wb-cases .wb-case-jump').count(), 0);
  await capture(page, 'empty-unreported'); checks.push('zero is distinct from unavailable counters');

  await visit(page, mainPath);
  const native = links(page, 'x').first();
  const beforeModified = reads.length, beforePath = await currentPath(page);
  const defaultPreserved = await native.evaluate(anchor => {
    const outcomes = [];
    for (const init of [{ctrlKey: true}, {metaKey: true}, {shiftKey: true}, {altKey: true}, {button: 1}]) {
      const event = new MouseEvent('click', {bubbles: true, composed: true, cancelable: true, ...init});
      // Prevent platform navigation only after the app has observed propagation.
      const capture = observed => { outcomes.push(!observed.defaultPrevented); observed.preventDefault(); };
      window.addEventListener('click', capture, {once: true}); anchor.dispatchEvent(event);
    }
    return outcomes;
  });
  assert.deepEqual(defaultPreserved, [true, true, true, true, true], 'modified native navigation is not claimed by the SPA');
  assert.equal(reads.length, beforeModified); assert.equal(await currentPath(page), beforePath);
  const [other] = await Promise.all([context.waitForEvent('page', {timeout: 5000}), native.click({modifiers: ['Meta']})]);
  try {
    await other.bringToFront();
    await other.waitForURL(base + href(casePath(mainPath, 'x', '3')), {timeout: 5000});
    await other.locator('#debug-workspace').waitFor({state: 'attached', timeout: 5000});
    assert.equal(await currentPath(page), beforePath, 'native modified click leaves the original tab unchanged');
  } finally { await other.close(); await page.bringToFront(); }
  checks.push('modified native defaults and a real separate-tab case destination');

  for (const width of [1440, 768, 390]) {
    const visualContext = await newContext({viewport: {width, height: 1000}}), visual = await visualContext.newPage();
    await visit(visual, largePath);
    await focusRing(links(visual, 'x').first()); await capture(visual, 'light-' + width);
    await visual.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
    await focusRing(links(visual, 'x').first()); await capture(visual, 'dark-' + width);
    await visualContext.close();
  }
  const touchContext = await newContext({viewport: {width: 390, height: 1000}, hasTouch: true, isMobile: true}), touch = await touchContext.newPage();
  await visit(touch, largePath); assert.equal(await touch.evaluate(() => matchMedia('(pointer:coarse)').matches), true);
  await focusRing(links(touch, 'x').first()); await capture(touch, 'touch-light-390');
  await touch.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'}); await capture(touch, 'touch-dark-390');
  checks.push('1440/768/390 light and dark; real focus rings;44px nonoverlapping coarse native controls');
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  passed = true;
  console.log(JSON.stringify({passed: true, checks, fixtureReads: reads.length, liveReads: 0, writes: 0, unexpected, errors, assets: versions, screenshots}, null, 2));
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({path: '/private/tmp/shrine-inspector-cases-failure.png'}).catch(() => {});
  console.error(JSON.stringify({passed: false, error: error.stack, checks, reads, unexpected, errors, screenshots}, null, 2));
  throw error;
} finally {
  heldRead?.release();
  for (const context of contexts) await context.close().catch(() => {});
  await browser.close();
  await writeFile('/private/tmp/shrine-inspector-cases-evidence.json', JSON.stringify({passed, checks, reads, unexpected, errors, screenshots, assets: versions, liveReads: 0, writes: 0}, null, 2));
}
