// Integrated Mash input groups, text actions and breadcrumbs. This suite
// requires a saved real shell. Every request is intercepted; it never contacts
// a runtime, performs an operation, or reads/writes the user's browser state.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT must name an existing real /app shell; no live fallback');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = 'http://debug-controls.invalid';
const root = fileURLToPath(new URL('..', import.meta.url));
const html = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const parentPath = '/__controls__', childPath = parentPath + '/alpha';
const encodedPath = childPath + '/price?#%λ';
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
let activePage = page;
const reads = [], renderedReads = [], writes = [], unexpected = [], errors = [], screenshots = [];
const fixtures = await page.evaluate(({html, parentPath, childPath, encodedPath}) => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth'))
    throw new Error('Saved shell lacks the current server document anatomy');
  const children = {'/': ['/app', parentPath, '/boot', '/sys'], [parentPath]: [childPath, parentPath + '/beta'], [childPath]: [encodedPath]};
  const paths = ['/', '/app', '/boot', '/sys', '/notes', parentPath, childPath, parentPath + '/beta', encodedPath];
  return Object.fromEntries(paths.map(path => {
    const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
    workspace.dataset.path = path; workspace.dataset.kind = 'record'; workspace.dataset.writable = String(path === parentPath);
    workspace.dataset.label = path.split('/').at(-1) || 'Namespace';
    workspace.dataset.renderUrl = '/ns' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
    workspace.dataset.fixture = 'debug-controls';
    const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
    for (const [key, value] of [['/sys/lede', 'Browser-only control fixture'], ['/notes', 'Authored record value']]) {
      const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
      const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
      const pail = doc.createElement('sh-pail'); pail.textContent = value;
      limb.append(slot, pail); myth.append(limb);
    }
    for (const name of ['Semantics', 'Documentation', 'Operations'])
      doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
    const form = doc.createElement('form'); form.action = '/op/__controls__/fixture'; form.method = 'post';
    const action = doc.createElement('ui-button'); action.id = 'fixture-operation';
    action.setAttribute('type', 'submit'); action.setAttribute('variant', 'secondary'); action.setAttribute('outline', '');
    action.setAttribute('tone', 'critical'); action.setAttribute('size', 'large');
    action.textContent = 'Apply fixture change with the authored operation label preserved';
    const disabled = doc.createElement('ui-button'); disabled.id = 'fixture-disabled-action';
    disabled.setAttribute('type', 'button'); disabled.setAttribute('variant', 'ghost'); disabled.setAttribute('disabled', '');
    disabled.textContent = 'Unavailable fixture action';
    const locked = doc.createElement('ui-button'); locked.id = 'fixture-disabled-submit';
    locked.setAttribute('type', 'submit'); locked.setAttribute('disabled', ''); locked.textContent = 'Locked fixture change';
    form.append(action, disabled, locked);
    doc.querySelector('#debug-main section[aria-label=Operations]').append(form);
    const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
    for (const child of children[path] || []) {
      const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
      item.dataset.label = child.split('/').at(-1); item.setAttribute('title', item.dataset.label); tree.append(item);
    }
    doc.querySelector('#debug-go ui-input')?.setAttribute('value', path);
    return [path, '<!doctype html>' + doc.documentElement.outerHTML];
  }));
}, {html, parentPath, childPath, encodedPath});

async function fixtureRoute(route) {
  const request = route.request(), url = new URL(request.url());
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
    writes.push(request.method() + ' ' + request.url()); return route.abort();
  }
  if (url.origin === base && assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (url.origin === base && /^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/'; reads.push(path);
    if (path === '/unavailable') return route.fulfill({status: 503, contentType: 'text/plain', body: 'Browser-only unavailable path'});
    if (fixtures[path]) return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
  }
  if (url.origin === base && /^\/ns(?:\/|$)/.test(url.pathname)) {
    renderedReads.push(url.pathname);
    return route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Isolated rendered fixture</title><p>Browser-only rendered view.</p>'});
  }
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
}
await context.route('**/*', fixtureRoute);
context.on('page', target => target.on('pageerror', error => errors.push(error.message)));
page.on('pageerror', error => errors.push(error.message));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); }
  assert.fail(message);
}
async function ready(target, path) {
  await target.waitForFunction(path => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, path);
}
const native = host => host.locator('button[part=control]');
const input = target => target.locator('#debug-go ui-input input');
const pathGroup = target => target.locator('#wb-path-input-group');
const groupPartStyle = (group, part, property) => group.evaluate((el, {part, property}) =>
  getComputedStyle(el.shadowRoot.querySelector('[part="' + part + '"]'))[property], {part, property});
const groupPartHidden = (group, part) => group.evaluate((el, part) =>
  el.shadowRoot.querySelector('[part="' + part + '"]').hidden, part);
async function nativeFocus(control) {
  return control.evaluate(el => el.getRootNode().activeElement === el);
}
async function edit(target) {
  await target.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await settled(() => nativeFocus(input(target)), 'the real address input receives focus');
}
async function go(target, path) {
  if (!await target.locator('#debug-go').isVisible()) await edit(target);
  await input(target).fill(path); await input(target).press('Enter'); await ready(target, path);
}
async function sidebar(target) {
  if (!await target.locator('#debug-filter').isVisible()) await target.locator('#debug-sidebar-toggle').click();
  await target.locator('#debug-filter input').waitFor({state: 'visible'});
  await settled(() => target.locator('#debug-filter').evaluate(el => el.getBoundingClientRect().height > 0), 'sidebar has settled visible geometry');
}
async function noOverflow(target) {
  assert.equal(await target.locator('#wb-activity-toggle').count(), 0, 'removed activity shortcut is not mounted');
  assert.equal(await target.locator('#wb-mode-rendered').count(), 0, 'Preview control is removed');
  for (const selector of ['#wb-mode-inspect', '#wb-refresh']) {
    const radii = await native(target.locator(selector)).evaluate(el => {
      const style = getComputedStyle(el);
      return [style.borderTopLeftRadius, style.borderTopRightRadius, style.borderBottomRightRadius, style.borderBottomLeftRadius];
    });
    assert.deepEqual(radii, Array(4).fill('8px'), selector + ' inherits the shared Mash control radius at every viewport');
  }
  assert.ok(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'the page fits the viewport');
  const selectors = ['.debug-header.wb-commandbar', '#debug-go', '#wb-path-input-group', '#debug-filter-composer', '.wb-document-header', '.wb-mode-switch'];
  for (const selector of selectors) for (const surface of await target.locator(selector).all()) {
    if (!await surface.isVisible()) continue;
    const metrics = await surface.evaluate(el => ({width: el.clientWidth, scroll: el.scrollWidth, box: el.getBoundingClientRect().toJSON()}));
    assert.ok(metrics.scroll <= metrics.width + 1, selector + ' has no clipped horizontal content: ' + JSON.stringify(metrics));
    assert.ok(metrics.box.left >= -1 && metrics.box.right <= await target.evaluate(() => innerWidth) + 1,
      selector + ' stays inside the viewport: ' + JSON.stringify(metrics));
  }
}
async function groupGeometry(group, coarse = false) {
  const controls = group.locator('input, button[part=control]');
  const bounds = [];
  const box = await group.boundingBox();
  for (const control of await controls.all()) {
    if (!await control.isVisible()) continue;
    const bound = await control.boundingBox(); bounds.push(bound);
    assert.ok(bound.x >= box.x - 1 && bound.x + bound.width <= box.x + box.width + 1 && bound.y >= box.y - 1 && bound.y + bound.height <= box.y + box.height + 1,
      'integrated input/action hit area is contained by its group: ' + JSON.stringify({box, bound}));
    if (coarse) assert.ok(bound.width >= 43.9 && bound.height >= 43.9, 'coarse native group control is at least44px in both axes: ' + JSON.stringify(bound));
  }
  for (let i = 0; i < bounds.length; i++) for (let j = i + 1; j < bounds.length; j++) {
    const a = bounds[i], b = bounds[j];
    assert.ok(Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) <= 1 ||
      Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) <= 1,
    'native input/action targets do not overlap: ' + JSON.stringify({a, b}));
  }
}
async function integratedGroup(group, targetInput) {
  assert.equal(await group.evaluate(el => el.localName), 'ui-input-group');
  assert.equal(await group.getAttribute('size'), 'small');
  assert.equal(await group.getAttribute('touch-target'), '');
  const control = await targetInput.evaluate(el => {
    const style = getComputedStyle(el);
    return {border: style.borderWidth, outline: style.outlineStyle, shadow: style.boxShadow};
  });
  assert.equal(control.border, '0px', 'the native field does not add a second boundary');
  assert.equal(control.outline, 'none', 'the native field delegates its focus ring to the group');
  assert.equal(control.shadow, 'none');
  await targetInput.focus();
  assert.notEqual(await groupPartStyle(group, 'root', 'outlineStyle'), 'none', 'the whole integrated group has visible focus');
  await groupGeometry(group);
}
async function filterFocusContained(group) {
  const geometry = await group.evaluate(el => {
    const surface = el.shadowRoot.querySelector('[part=root]'), style = getComputedStyle(surface);
    const box = surface.getBoundingClientRect();
    const reach = Math.max(0, parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset));
    const sidebar = el.closest('sh-sidebar');
    const workspace = sidebar.closest('sh-triptych');
    const viewport = workspace.shadowRoot.querySelector('[part~="sidebar-body"]')?.viewportElement;
    const clips = [sidebar.shadowRoot.querySelector('[part=root]'), viewport];
    return {reach, outline: {left: box.left - reach, top: box.top - reach, right: box.right + reach, bottom: box.bottom + reach},
      clips: clips.map(clip => clip?.getBoundingClientRect().toJSON())};
  });
  assert.ok(geometry.reach > 0, 'the focused filter exposes its actual outline geometry');
  assert.equal(geometry.clips.filter(Boolean).length, 2, 'both actual sidebar clipping boundaries are measured');
  for (const clip of geometry.clips) assert.ok(geometry.outline.left >= clip.left - .5 && geometry.outline.right <= clip.right + .5 &&
    geometry.outline.top >= clip.top - .5 && geometry.outline.bottom <= clip.bottom + .5,
  'the complete filter focus outline clears sidebar root and viewport clipping: ' + JSON.stringify(geometry));
}
async function filterChecks(target, coarse = false) {
  await sidebar(target);
  const filter = target.locator('#debug-filter input'), group = target.locator('#debug-filter-composer');
  const clear = target.locator('#debug-filter-clear');
  await integratedGroup(group, filter);
  await filterFocusContained(group);
  assert.equal(await target.locator('#debug-root-menu').getAttribute('slot'), 'prefix');
  assert.equal(await target.locator('#debug-filter').getAttribute('slot'), 'control');
  assert.equal(await clear.getAttribute('slot'), 'suffix');
  await settled(() => groupPartHidden(group, 'suffix'), 'empty filter has no trailing adornment');
  assert.equal(await groupPartHidden(group, 'suffix-separator'), true);
  const alpha = target.locator('#debug-path-tree ui-tree-item[data-path="' + childPath + '"]');
  const beta = target.locator('#debug-path-tree ui-tree-item[data-path="' + parentPath + '/beta"]');
  await alpha.waitFor({state: 'attached'}); await beta.waitFor({state: 'attached'});
  const before = reads.length;
  await filter.fill('alpha');
  await settled(() => beta.evaluate(el => el.hidden), 'nonmatching loaded paths hide');
  assert.equal(await alpha.evaluate(el => el.hidden), false, 'matching loaded path remains');
  assert.equal(await clear.isVisible(), true);
  assert.equal(await groupPartHidden(group, 'suffix'), false);
  await groupGeometry(group, coarse);
  await filter.fill('no-such-loaded-path');
  await target.locator('#debug-filter-empty').waitFor({state: 'visible'});
  await clear.click();
  await settled(() => nativeFocus(filter), 'clearing restores native input focus');
  assert.equal(await filter.inputValue(), '');
  assert.equal(await target.locator('#debug-filter-empty').isVisible(), false);
  await settled(() => groupPartHidden(group, 'suffix'), 'clear removes the suffix wrapper dynamically');
  await filter.fill('beta'); await filter.press('Escape');
  assert.equal(await filter.inputValue(), '');
  assert.equal(await nativeFocus(filter), true, 'Escape clears filtering without ejecting input focus');
  assert.equal(await beta.evaluate(el => el.hidden), false);
  assert.equal(reads.length, before, 'filtering is local to loaded paths, with no implicit namespace search');
  await noOverflow(target);
}
async function breadcrumbs(target, path, coarse = false) {
  const links = target.locator('.wb-path-ancestor');
  assert.ok(await links.count() >= 1);
  const expected = ['/', ...path.split('/').filter(Boolean).map((_, index, parts) => '/' + parts.slice(0, index + 1).join('/'))];
  assert.deepEqual(await links.evaluateAll(elements => elements.map(el => el.getAttribute('href'))), expected.map(href));
  for (let index = 0; index < expected.length; index++) {
    const link = links.nth(index), anchor = link.locator('a[part=control]');
    assert.equal(await link.evaluate(el => el.localName), 'ui-link');
    assert.equal(await link.getAttribute('variant'), 'quiet');
    assert.equal(await link.getAttribute('size'), 'small', 'breadcrumb scale comes from Mash');
    assert.equal(await anchor.getAttribute('href'), href(expected[index]));
    assert.equal(await anchor.getAttribute('aria-current'), index === expected.length - 1 ? 'page' : null);
    assert.equal(await anchor.getAttribute('aria-label'), expected[index] === '/' ? 'Namespace root' : 'Open ' + expected[index]);
    assert.equal(await link.locator(':scope > ui-icon[slot=prefix]').count(), 1, 'breadcrumb uses the stock Mash prefix anatomy');
    if (coarse) {
      const box = await anchor.boundingBox();
      assert.ok(box.width >= 43.9 && box.height >= 43.9, 'all breadcrumb anchors, including root, have44px actual touch targets: ' + JSON.stringify(box));
    } else {
      const box = await anchor.boundingBox();
      assert.ok(Math.abs(box.height - 24) < .6, 'small desktop breadcrumb native height is24px: ' + JSON.stringify(box));
    }
  }
  const current = links.last().locator('a[part=control]');
  await target.locator('#debug-sidebar-toggle').focus();
  assert.equal(await nativeFocus(current), false, 'resting current-link style is checked without keyboard focus');
  assert.equal(await current.evaluate(el => getComputedStyle(el).boxShadow), 'none', 'current breadcrumbs remain flat even beside the server’s older embedded Mash recipe');
  await current.focus();
  assert.notEqual(await current.evaluate(el => getComputedStyle(el).outlineStyle), 'none', 'breadcrumb keyboard focus has a visible Mash ring');
  assert.equal(await current.evaluate(el => getComputedStyle(el).boxShadow), 'none', 'focus is a separate outline, not an inset current-state border');
  const modifiers = await links.first().locator('a[part=control]').evaluate(anchor => ['metaKey', 'ctrlKey', 'shiftKey', 'altKey'].map(modifier => {
    // Synthetic modified clicks avoid invoking OS/browser download or window
    // shortcuts. They prove app routing leaves the native default untouched;
    // plain pointer navigation is exercised separately below.
    const event = new MouseEvent('click', {bubbles: true, composed: true, cancelable: true, button: 0, [modifier]: true});
    let prevented = null;
    const intercept = observed => {
      if (observed !== event) return;
      prevented = observed.defaultPrevented;
      // Observe after production's document listener, then suppress the
      // browser window/download default in this isolated diagnostic only.
      observed.preventDefault();
    };
    window.addEventListener('click', intercept);
    anchor.dispatchEvent(event); window.removeEventListener('click', intercept);
    return {modifier, prevented};
  }));
  assert.ok(modifiers.every(result => !result.prevented), 'modified breadcrumb links retain native defaults: ' + JSON.stringify(modifiers));
}
async function modes(target, coarse = false) {
  const inspect = target.locator('#wb-mode-inspect');
  const toolbar = target.locator('.wb-mode-switch');
  assert.equal(await toolbar.evaluate(el => el.localName), 'ui-toolbar');
  assert.equal(await target.getByRole('toolbar', {name: 'View mode', exact: true}).count(), 1);
  assert.equal(await target.locator('#wb-mode-rendered').count(), 0);
  assert.equal(await native(inspect).getAttribute('aria-pressed'), 'true');
  assert.equal(await inspect.evaluate(el => el.selected), true);
  await settled(() => toolbar.evaluate(el => [...el.children].filter(control => control.tabIndex === 0).length === 1), 'mode toolbar has one Tab stop');
  await inspect.focus(); await inspect.press('ArrowRight');
  await settled(() => nativeFocus(native(inspect)), 'single-control toolbar keeps keyboard focus');
  await inspect.press('Home'); await inspect.press('End'); await inspect.press('Space');
  assert.equal(await nativeFocus(native(inspect)), true, 'keyboard mode activation retains control focus');
  if (coarse) for (const control of [inspect]) {
    assert.equal(await control.getAttribute('touch-target'), '');
    const box = await native(control).boundingBox();
    assert.ok(box.width >= 43.9 && box.height >= 43.9, 'mode text actions have actual44px touch targets: ' + JSON.stringify(box));
  }
}
async function inspectorControls(target, coarse = false) {
  const toggle = target.locator('#debug-inspector-toggle');
  const panel = target.locator('.wb-inspector');
  assert.equal(await target.getByRole('button', {name: 'Close inspector', exact: true}).count(), 0, 'no duplicate inspector close button is mounted');
  assert.equal(await panel.locator('.wb-inspector-header ui-button').count(), 0);
  await toggle.focus();
  if (coarse) await native(toggle).tap(); else await native(toggle).click();
  await settled(() => panel.evaluate(el => document.activeElement === el), 'opening focuses the named inspector region');
  assert.equal(await panel.getAttribute('role'), 'region');
  assert.equal(await panel.getAttribute('aria-label'), 'Details');
  assert.equal(await panel.getAttribute('tabindex'), '-1', 'inspector focus does not add another Tab stop');
  assert.equal(await panel.evaluate(el => getComputedStyle(el).outlineStyle), 'none', 'the reading destination does not acquire a panel-sized native focus border');
  assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
  await screenshot(target, 'inspector-' + target.viewportSize().width + (coarse ? '-touch' : ''));
  await target.keyboard.press('Escape');
  await settled(() => target.locator('#debug-workspace').evaluate(el => !el.inspectorOpen), 'Escape closes the inspector without a close button');
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
  assert.equal(await nativeFocus(native(toggle)), true, 'Escape returns focus to the opener');
  await native(toggle).click();
  await settled(() => panel.evaluate(el => document.activeElement === el), 'inspector can reopen');
  await native(toggle).click();
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false', 'toolbar toggle still closes the inspector');
  assert.equal(await nativeFocus(native(toggle)), true);
}
async function operationControls(target, coarse = false) {
  const action = target.locator('#fixture-operation'), unavailable = target.locator('#fixture-disabled-action');
  const locked = target.locator('#fixture-disabled-submit');
  assert.equal(await action.getAttribute('type'), 'submit');
  assert.equal(await action.getAttribute('variant'), 'secondary');
  assert.equal(await action.getAttribute('outline'), '', 'authored outline axis is preserved');
  assert.equal(await action.getAttribute('tone'), 'critical');
  assert.equal(await action.getAttribute('size'), 'large', 'authored operation size is preserved');
  assert.equal(await action.textContent(), 'Apply fixture change with the authored operation label preserved');
  assert.equal(await unavailable.evaluate(el => el.closest('form').getAttribute('data-mash-size')), 'small', 'the authored form supplies the compact Mash context');
  assert.equal(await unavailable.getAttribute('size'), 'inherit', 'unsized authored actions retain shared inherited sizing');
  assert.equal(await native(unavailable).isDisabled(), true, 'authored non-submit disabled state survives enhancement');
  assert.equal(await native(locked).isDisabled(), true, 'authored submit disabled state survives the initial read and enhancement');
  await target.getByRole('button', {name: 'Open operations', exact: true}).click();
  await native(action).waitFor({state: 'visible'});
  assert.equal(await native(action).isDisabled(), false, 'writable inspect mode enables the original native submit');
  await target.locator('#wb-canvas > sh-myth.wb-properties').getByRole('button', {name: 'Inspect slot definition /notes', exact: true}).click();
  await target.waitForFunction(() => {
    const ws = document.querySelector('#debug-workspace');
    return ws.dataset.inspectorPath === '/notes' && ws.getAttribute('aria-busy') === 'false';
  });
  assert.equal(await native(action).isDisabled(), false, 'inspector-only busy/read cycle restores the writable submit, not temporary disabled state');
  assert.equal(await native(locked).isDisabled(), true, 'inspector-only read preserves the authored disabled submit');
  assert.equal(await target.locator('#debug-workspace').getAttribute('data-path'), parentPath, 'inspection leaves the main document unchanged');
  await target.locator('#debug-inspector-toggle').click();
  await native(action).scrollIntoViewIfNeeded();
  for (const host of [action, unavailable, locked]) {
    assert.equal(await host.getAttribute('touch-target'), '');
    const box = await native(host).boundingBox();
    if (coarse) assert.ok(box.width >= 43.9 && box.height >= 43.9, 'authored native form target is44px or larger: ' + JSON.stringify(box));
    else assert.ok(Math.abs(box.height - (host === action ? 32 : 24)) < .6,
      'fine-pointer authored large/inherited small actions use the actual32/24px native scale: ' + JSON.stringify(box));
    assert.ok(await native(host).evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'authored operation label is not clipped');
  }
  if (coarse) await screenshot(target, 'operations-touch-390');
  // Existing rendered URLs remain safe/read-only; the toolbar no longer
  // advertises this mode. This fixture request is intercepted like every read.
  const renderedURL = new URL(target.url()); renderedURL.searchParams.set('view', 'rendered');
  await target.goto(renderedURL.href); await ready(target, parentPath);
  assert.equal(await native(action).isDisabled(), true, 'preview mode leaves the native submit read-only');
  assert.equal(await native(locked).isDisabled(), true, 'authored disabled submit remains disabled in preview');
  await target.locator('#wb-mode-inspect').click();
  assert.equal(await native(action).isDisabled(), false, 'returning to inspection restores its writable state');
  assert.equal(await native(locked).isDisabled(), true, 'returning to inspection must not enable an authored disabled submit');
  if (await target.locator('#wb-operations').evaluate(el => el.open))
    await target.getByRole('button', {name: 'Open operations', exact: true}).click();
}
async function textTargets(target) {
  for (const host of await target.locator('ui-button.wb-button').all()) {
    if (!await host.isVisible()) continue;
    assert.equal(await host.getAttribute('touch-target'), '', 'application text actions opt into Mash touch geometry');
    const control = native(host), box = await control.boundingBox();
    assert.ok(box.width >= 43.9 && box.height >= 43.9, 'native text-action target is44px or larger: ' + JSON.stringify(box));
    assert.ok(await control.evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'text action does not clip its label');
    const glyph = host.locator(':scope > ui-icon');
    if (await glyph.count()) assert.equal(await glyph.getAttribute('slot'), 'prefix', 'text action uses Mash prefix icon layout');
  }
}
async function screenshot(target, name) {
  const path = '/private/tmp/shrine-controls-' + name + '.png';
  await target.screenshot({path, animations: 'disabled'}); screenshots.push(path);
}

try {
  await page.goto(base + href(parentPath)); await ready(page, parentPath);
  assert.equal(await native(page.locator('#fixture-disabled-submit')).isDisabled(), true, 'initial authored disabled submit stays disabled');
  await edit(page);
  assert.equal(await pathGroup(page).getAttribute('typography'), 'code');
  await integratedGroup(pathGroup(page), input(page));
  assert.deepEqual(await input(page).evaluate(el => [el.selectionStart, el.selectionEnd]), [0, parentPath.length], 'opening selects the current canonical address');
  const normalBoundary = await groupPartStyle(pathGroup(page), 'root', 'borderColor');
  const originalURL = page.url(), count = reads.length;
  await input(page).fill('/../bad'); await input(page).press('Enter');
  await settled(() => pathGroup(page).evaluate(el => el.invalid), 'invalid canonical address marks the integrated boundary');
  assert.equal(await input(page).getAttribute('aria-invalid'), 'true', 'native input announces the invalid state');
  assert.notEqual(await groupPartStyle(pathGroup(page), 'root', 'borderColor'), normalBoundary);
  assert.equal(page.url(), originalURL); assert.equal(reads.length, count, 'invalid address is rejected before any fixture read');
  assert.equal(await page.locator('#debug-status').getAttribute('data-failed'), 'true');
  await input(page).fill(childPath);
  assert.equal(await pathGroup(page).evaluate(el => el.invalid), false, 'editing clears the obsolete address error');
  assert.notEqual(await input(page).getAttribute('aria-invalid'), 'true');
  await input(page).press('Escape');
  assert.equal(await page.locator('#debug-go').isVisible(), false);
  await settled(() => nativeFocus(native(page.locator('#wb-path-edit'))), 'Escape restores the editor trigger focus');
  await edit(page);
  assert.equal(await input(page).inputValue(), parentPath, 'reopening discards the invalid address');
  assert.equal(await pathGroup(page).evaluate(el => el.invalid), false);
  assert.notEqual(await input(page).getAttribute('aria-invalid'), 'true');
  await input(page).fill('/unavailable'); await input(page).press('Enter');
  await page.waitForFunction(() => document.querySelector('#debug-status').textContent.includes('Navigation failed.') &&
    document.querySelector('#debug-workspace').getAttribute('aria-busy') === 'false');
  assert.equal(page.url(), originalURL, 'a failed read preserves the original page');
  assert.equal(await pathGroup(page).evaluate(el => el.invalid), false, 'a backend failure is not a malformed address');
  assert.notEqual(await input(page).getAttribute('aria-invalid'), 'true');
  await input(page).fill(childPath); await input(page).press('Enter'); await ready(page, childPath);
  assert.equal(await native(page.locator('#fixture-operation')).isDisabled(), true, 'read-only fixture retains a disabled native operation submit');
  assert.equal(new URL(page.url()).pathname, href(childPath));
  await breadcrumbs(page, childPath);
  await page.getByRole('link', {name: 'Namespace root', exact: true}).click(); await ready(page, '/');
  await go(page, encodedPath); await breadcrumbs(page, encodedPath);
  assert.equal(new URL(page.url()).pathname, href(encodedPath), 'reserved namespace bytes cannot become URL query/fragment delimiters');
  assert.equal(new URL(page.url()).search, ''); assert.equal(new URL(page.url()).hash, '');
  await go(page, parentPath); await filterChecks(page); await modes(page); await operationControls(page);
  assert.equal(await native(page.locator('#fixture-disabled-submit')).isDisabled(), true, 'successful navigation settles without enabling an authored disabled submit');
  console.log('PASS: integrated path focus/invalid/Escape/Enter, encoded Mash breadcrumbs, local filter/clear, keyboard and pointer mode state.');

  for (const width of [1440, 1197, 768, 390]) {
    await page.setViewportSize({width, height: width === 390 ? 844 : 1000});
    await page.goto(base + href(parentPath)); await ready(page, parentPath);
    await noOverflow(page); await screenshot(page, 'light-' + width);
    await inspectorControls(page);
    await edit(page); await integratedGroup(pathGroup(page), input(page)); await noOverflow(page);
    await screenshot(page, 'address-light-' + width);
    await input(page).press('Escape');
    if (width === 390) {
      await filterChecks(page); await screenshot(page, 'filter-light-390');
      await page.locator('#debug-sidebar-toggle').click();
    }
  }
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await edit(page); await integratedGroup(pathGroup(page), input(page));
  await noOverflow(page); await screenshot(page, 'address-dark-focus-390'); await input(page).press('Escape');
  await modes(page); await noOverflow(page);
  for (const mode of ['#wb-mode-inspect'])
    assert.equal(await native(page.locator(mode)).evaluate(el => getComputedStyle(el).transitionDuration), '0s', 'reduced-motion Mash actions do not animate');
  await screenshot(page, 'dark-390');

  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce'});
  await touchContext.route('**/*', fixtureRoute);
  const touch = await touchContext.newPage(); touch.on('pageerror', error => errors.push(error.message));
  activePage = touch;
  await touch.goto(base + href(parentPath)); await ready(touch, parentPath);
  assert.equal(await touch.evaluate(() => matchMedia('(pointer: coarse)').matches), true);
  await inspectorControls(touch, true);
  await breadcrumbs(touch, parentPath, true); await modes(touch, true); await operationControls(touch, true); await textTargets(touch); await noOverflow(touch);
  await screenshot(touch, 'touch-390');
  await edit(touch); await integratedGroup(pathGroup(touch), input(touch)); await groupGeometry(pathGroup(touch), true);
  await textTargets(touch); await noOverflow(touch); await screenshot(touch, 'address-touch-390'); await input(touch).press('Escape');
  await filterChecks(touch, true); await textTargets(touch); await screenshot(touch, 'filter-touch-390');
  const save = touch.locator('#debug-saved').getByRole('button', {name: 'Save current page', exact: true});
  await save.click();
  await touch.locator('.debug-page-row[data-path="' + parentPath + '"] a').first().waitFor({state: 'attached'});
  assert.ok(await touch.evaluate(path => JSON.parse(localStorage.getItem('shrine-debug.v1.saved')).includes(path), parentPath), 'touch text action updates isolated saved state');
  await touchContext.close();
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, liveReads: 0, fixtureReads: reads.length, renderedFixtures: renderedReads.length, screenshots}, null, 2));
} catch (error) {
  await activePage.screenshot({path: '/private/tmp/shrine-controls-failure.png', animations: 'disabled'}).catch(() => {});
  console.error(JSON.stringify({reads, renderedReads, writes, unexpected, errors}, null, 2));
  throw error;
} finally {
  await browser.close();
}
