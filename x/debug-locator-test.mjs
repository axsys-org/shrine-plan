// Actual Mash path-locator interactions over a saved debugger shell. Every
// document and asset is fulfilled locally; even GET never reaches a runtime.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
assert.ok(process.env.DEBUG_DOCUMENT, 'Set DEBUG_DOCUMENT to a saved debugger HTML document; this test never reads a live runtime.');
const base = 'http://locator-fixtures.invalid';
const root = fileURLToPath(new URL('..', import.meta.url));
const initialHTML = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const browser = await chromium.launch();
try {
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, serviceWorkers: 'block' });
await context.addInitScript(() => {
  window.__copies = [];
  Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: async value => window.__copies.push(value)}});
  document.execCommand = () => {throw new Error('System clipboard access is forbidden in this fixture');};
});
const errors = [], writes = [], reads = [], unexpected = [];
const failedPaths = new Set();
await context.route('**/*', route => {unexpected.push(route.request().url()); return route.abort();});
const page = await context.newPage();
const fixtures = await page.evaluate(html => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  if (!original.querySelector('#debug-workspace') || !original.querySelector('#debug-main > section[aria-label=Record] > sh-myth'))
    throw new Error('The saved shell lacks the actual debugger document anatomy.');
  const children = {
    '/': ['/gov', '/sys', '/app', '/deep'],
    '/gov': ['/gov/srs'],
    '/gov/srs': ['/gov/srs/card', ...Array.from({length: 24}, (_, i) => '/gov/srs/kind_' + i)],
    '/sys': ['/sys/about'], '/app': [],
    '/deep': ['/deep/namespace'], '/deep/namespace': ['/deep/namespace/contains'],
    '/deep/namespace/contains': ['/deep/namespace/contains/another'],
    '/deep/namespace/contains/another': ['/deep/namespace/contains/another/record'],
  };
  const paths = new Set([...Object.keys(children), ...Object.values(children).flat()]);
  return Object.fromEntries([...paths].map(path => {
    const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
    Object.assign(ws.dataset, {path, kind: 'record', writable: 'false', label: 'Browser-only locator fixture',
      fixture: 'debug-locator', renderUrl: '/ns' + (path === '/' ? '' : path)});
    for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete ws.dataset[key];
    const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
    for (const [key, text] of [['/sys/lede', 'Browser-only locator fixture'], ['/value', 'Fixture record at ' + path]]) {
      const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
      const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
      const value = doc.createElement('sh-pail'); value.textContent = text;
      limb.append(slot, value); myth.append(limb);
    }
    for (const label of ['Semantics', 'Documentation', 'Operations'])
      doc.querySelector('#debug-main section[aria-label="' + label + '"]')?.replaceChildren();
    const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
    for (const child of children[path] || []) {
      const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
      const name = child.split('/').at(-1);
      item.dataset.kind = 'record'; item.dataset.label = name === 'kind_1' ? name :
        name === 'card' ? 'Card definition' : name === 'kind_0' ? 'Authored long description' : 'Fixture ' + name;
      if (name === 'card' || name === 'kind_0') {
        item.dataset.descriptionSource = '/sys/help';
        item.dataset.description = name === 'card' ? 'Stores the prompt and answer for a study card.' : 'Exact help  '.repeat(1000) + 'END OF AUTHORED HELP';
      }
      item.setAttribute('title', item.dataset.label); tree.append(item);
    }
    return [path, '<!doctype html>' + doc.documentElement.outerHTML];
  }));
}, initialHTML);
async function routeFixture(route) {
  const request = route.request();
  if (request.method() !== 'GET') {
    writes.push(request.url());
    return route.abort();
  }
  const url = new URL(request.url());
  if (url.origin !== base || url.search) {unexpected.push(request.url()); return route.abort();}
  if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (/^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/';
    reads.push(url.pathname);
    if (failedPaths.has(path)) return route.fulfill({status: 503, contentType: 'text/plain', body: 'Read-only retry fixture'});
    if (Object.hasOwn(fixtures, path)) return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
  }
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
}
await context.route('**/*', routeFixture);
page.on('pageerror', error => errors.push(error.message));
const ready = path => page.waitForFunction(path => {
  const workspace = document.querySelector('#debug-workspace');
  return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' &&
    workspace.getAttribute('aria-busy') !== 'true';
}, path);
const form = page.locator('#debug-go');
const input = form.locator('input');
const locator = page.locator('#wb-path-locator');
const menuAt = path => locator.locator('ui-menu.wb-path-menu').filter({ has: page.getByRole('button', { name: 'Children of ' + path, exact: true }) });
async function go(path) {
  await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  await input.fill(path);
  await input.press('Enter');
  await ready(path);
}
async function fits() {
  const sizes = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth,
    locator: document.querySelector('#wb-path-locator').getBoundingClientRect().width }));
  assert.ok(sizes.page <= sizes.viewport + 1, 'no document horizontal overflow');
  assert.ok(sizes.locator <= sizes.viewport + 1, 'locator fits its viewport');
}
async function settleChooser(page, menu) {
  await menu.evaluate(async node => {await node.updateComplete;});
  await page.waitForFunction(() => [...document.querySelectorAll('.wb-path-menu[open]')].every(node => node.matches(':state(active)')) &&
    [...document.querySelectorAll('ui-tooltip')].every(node => !node.open && !node.matches(':state(present)')));
}
async function focusRingGeometry(anchor) {
  return anchor.evaluate(node => {
    const scroll = node.getRootNode().host.closest('ui-scroll-area');
    const rect = node.getBoundingClientRect(), viewport = scroll.viewportElement.getBoundingClientRect();
    const css = getComputedStyle(node), outset = parseFloat(css.outlineWidth) + parseFloat(css.outlineOffset);
    const thumb = scroll.shadowRoot.querySelector('[part=inline-thumb]');
    const thumbRect = thumb?.getBoundingClientRect();
    return {outline: css.outlineStyle, outset, height: rect.height,
      ring: {left: rect.left - outset, right: rect.right + outset, top: rect.top - outset, bottom: rect.bottom + outset},
      viewport: {left: viewport.left, right: viewport.right, top: viewport.top, bottom: viewport.bottom},
      thumb: thumbRect && {left: thumbRect.left, right: thumbRect.right, top: thumbRect.top, bottom: thumbRect.bottom,
        opacity: getComputedStyle(thumb).opacity, width: thumbRect.width, height: thumbRect.height},
      scrollLeft: scroll.viewportElement.scrollLeft};
  });
}
function assertRingContained(geometry, label) {
  assert.equal(geometry.outline, 'solid', label + ': actual native focus ring is visible');
  const {ring, viewport, thumb} = geometry;
  assert.ok(ring.left >= viewport.left - .5 && ring.right <= viewport.right + .5 &&
    ring.top >= viewport.top - .5 && ring.bottom <= viewport.bottom + .5,
  label + ': complete focus ring stays inside the scroll viewport ' + JSON.stringify(geometry));
  if (thumb?.width && thumb.height && Number(thumb.opacity) > 0)
    assert.ok(ring.bottom <= thumb.top + .5, label + ': scrollbar thumb has a separate lane below the ring');
}
try {
  await page.goto(base + '/debug/gov/srs/card');
  await ready('/gov/srs/card');
  await locator.waitFor();
  assert.equal(await form.isVisible(), false, 'the permanent input is replaced by the path trail');
  assert.deepEqual(await locator.locator('.wb-path-segment').evaluateAll(nodes => nodes.map(node => node.dataset.path)),
    ['/', '/gov', '/gov/srs', '/gov/srs/card']);
  assert.equal(await locator.locator('ui-link[current]').getAttribute('href'), '/debug/gov/srs/card');
  assert.equal(await locator.locator('ui-link[current] a').getAttribute('aria-current'), 'page');
  assert.equal(await locator.locator('ui-link[current] a').evaluate(node => getComputedStyle(node).boxShadow),
    'none', 'quiet current state overrides legacy base recipes without a duplicate inset outline');
  assert.equal(await locator.locator('ui-link[variant=quiet][size=small]').count(), 4, 'Mash owns every dense breadcrumb link');
  assert.ok((await locator.locator('ui-link a').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height)))
    .every(height => height >= 24 && height <= 25), 'small desktop breadcrumbs retain the shared 24px control rhythm');
  assert.equal(await locator.locator('ui-link > ui-icon[slot=prefix][data-icon-source=Mash]').count(), 4);
  assert.equal(await locator.locator('ui-path, a.wb-path-ancestor').count(), 0, 'no nested path presentation or hand-painted native links');
  assert.equal(await locator.locator('ui-scroll-area.mash-scroll-quiet').count(), 1, 'Mash owns the quiet trail scrollbar');
  assert.deepEqual(await locator.locator('ui-link a').evaluateAll(nodes => nodes.map(node => node.getAttribute('href'))),
    ['/debug', '/debug/gov', '/debug/gov/srs', '/debug/gov/srs/card']);
  await fits();
  await page.keyboard.press('Tab');
  const desktopRoot = locator.locator('.wb-path-root a');
  await desktopRoot.focus();
  assertRingContained(await focusRingGeometry(desktopRoot), 'desktop root');
  console.log('PASS: canonical ancestor trail, current location, Mash primitives, compact default.');

  await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  assert.equal(await form.isVisible(), true);
  assert.equal(await form.locator('ui-input-group > .wb-path-cancel[slot=suffix]').count(), 1);
  assert.equal(await input.inputValue(), '/gov/srs/card');
  assert.deepEqual(await input.evaluate(node => [node.selectionStart, node.selectionEnd]), [0, 13]);
  await input.fill('/unsubmitted-path');
  await form.evaluate(node => {
    node.querySelector('ui-input-group').invalid = true;
    node.querySelector('ui-input').invalid = true;
  });
  await input.press('Escape');
  assert.deepEqual(await form.evaluate(node => [node.querySelector('ui-input-group').invalid, node.querySelector('ui-input').invalid]), [false, false]);
  assert.equal(await form.isVisible(), false);
  assert.equal(await page.locator('#wb-path-edit').evaluate(node => node === document.activeElement), true);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs/card');
  await page.keyboard.press('/');
  assert.equal(await form.isVisible(), true, 'slash opens the existing editor');
  assert.equal(await input.inputValue(), '/gov/srs/card', 'cancel discards only the address draft');
  await input.fill('/app');
  await input.press('Control+l');
  assert.equal(await input.inputValue(), '/gov/srs/card', 'Primary+L reselects canonical address');
  await input.press('Escape');
  const modifiers = await page.evaluate(() => {
    return [{key: 'l', ctrlKey: true, altKey: true}, {key: 'L', ctrlKey: true, shiftKey: true},
      {key: '/', isComposing: true}].map(options => {
        const event = new KeyboardEvent('keydown', { ...options, bubbles: true, cancelable: true });
        document.dispatchEvent(event);
        return event.defaultPrevented;
      });
  });
  assert.deepEqual(modifiers, [false, false, false], 'unsupported shortcut combinations remain untouched');
  console.log('PASS: explicit edit, canonical selection, slash/Primary+L, Escape and modifier handling.');

  const cardMenu = menuAt('/gov/srs/card');
  const cardTrigger = cardMenu.getByRole('button', { name: 'Children of /gov/srs/card', exact: true });
  const pageBefore = await page.locator('#debug-workspace').getAttribute('data-path');
  await cardTrigger.focus();
  await cardTrigger.press('Enter');
  await cardMenu.getByRole('status').waitFor();
  assert.match(await cardMenu.getByRole('status').innerText(), /No child paths/);
  assert.equal(await cardMenu.locator('.wb-path-menu-parent').getAttribute('href'), '/debug/gov/srs/card');
  assert.equal(await cardMenu.locator('.wb-path-menu-parent [slot=shortcut]').innerText(), 'Current',
    'an empty current parent still exposes its canonical link and current state');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), pageBefore);
  await cardMenu.evaluate(menu => {
    window.locatorCloseoutProof = new Promise(resolve => {
      const capture = async event => {
        if (event.target !== menu || event.detail.open) return;
        menu.removeEventListener('mash-presence-start', capture);
        await menu.updateComplete;
        await new Promise(requestAnimationFrame);
        const popup = menu.shadowRoot.querySelector('[part=popup]');
        const animations = popup.getAnimations({subtree: true});
        const popupAnimation = animations.find(animation => animation.effect?.target === popup);
        if (!popupAnimation) { resolve({error: 'No popup closeout animation'}); return; }
        const materialAnimations = menu.shadowRoot.querySelector('[part=material]')?.getAnimations() || [];
        const closeout = [...animations, ...materialAnimations];
        // Sample the actual CSS exit at a deterministic midpoint. This is an
        // animation regression, not a delay that hides an outgoing popup.
        for (const animation of closeout) {
          animation.pause();
          animation.currentTime = Number(animation.effect.getTiming().duration) / 2;
        }
        await new Promise(requestAnimationFrame);
        const snapshot = () => ({open: menu.open, present: menu.matches(':state(present)'),
          exiting: menu.matches(':state(exiting)'), popupOpacity: Number(getComputedStyle(popup).opacity),
          content: ['header', 'viewport', 'footer'].map(part => {
            const region = menu.shadowRoot.querySelector('[part=' + part + ']');
            return {part, opacity: Number(getComputedStyle(region).opacity), animations: region.getAnimations().length};
          }), width: popup.getBoundingClientRect().width,
          height: popup.getBoundingClientRect().height, text: menu.textContent,
          animation: popupAnimation.animationName});
        const during = snapshot();
        for (const animation of closeout) animation.play();
        await Promise.allSettled(closeout.map(animation => animation.finished));
        await menu.updateComplete;
        await new Promise(requestAnimationFrame);
        resolve({during, after: snapshot()});
      };
      menu.addEventListener('mash-presence-start', capture);
    });
  });
  await page.keyboard.press('Escape');
  const closeout = await page.evaluate(() => window.locatorCloseoutProof);
  assert.equal(closeout.error, undefined, 'Escape creates the shared popup closeout animation');
  assert.deepEqual([closeout.during.open, closeout.during.present, closeout.during.exiting], [false, true, true]);
  assert.ok(closeout.during.popupOpacity > 0 && closeout.during.popupOpacity < 1,
    'the whole outgoing shell fades instead of lingering as an opaque empty rectangle');
  assert.ok(closeout.during.content.every(region => region.opacity === 1 && region.animations === 0),
    'legacy child-region fades are reset, so authored content is not double-faded');
  assert.match(closeout.during.text, /No child paths/);
  assert.deepEqual([closeout.after.present, closeout.after.exiting, closeout.after.width, closeout.after.height],
    [false, false, 0, 0], 'actual animation completion removes popup presence and geometry');
  assert.equal(closeout.after.text, closeout.during.text, 'dismissal retains authored content for reopening');
  assert.equal(await cardTrigger.getAttribute('aria-expanded'), 'false');
  await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Children of /gov/srs/card');
  assert.equal(await cardTrigger.evaluate(node => node === document.activeElement ||
    node.getRootNode().host === document.activeElement), true, 'Mash menu restores focus');

  const srsMenu = menuAt('/gov/srs');
  const trigger = srsMenu.getByRole('button', { name: 'Children of /gov/srs', exact: true });
  await trigger.click();
  await srsMenu.locator('ui-menu-item[data-path="/gov/srs/card"]').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs/card', 'child disclosure never navigates');
  const firstReadCount = reads.filter(path => path === '/debug/gov/srs').length;
  await page.keyboard.press('Escape');
  await trigger.click();
  await srsMenu.locator('ui-menu-item[data-path="/gov/srs/card"]').waitFor({ state: 'visible' });
  assert.equal(reads.filter(path => path === '/debug/gov/srs').length, firstReadCount, 'unchanged menu reopens without an extra read');
  const menuCount = await srsMenu.locator(':scope > .wb-path-menu-child').count();
  assert.equal(menuCount, 20, 'a larger fixture child list is capped to 20 inline choices');
  assert.equal(await srsMenu.locator(':scope > [slot=header], :scope > [slot=footer]').count(), 0,
    'no disconnected header/footer chrome surrounds the actual path choices');
  assert.equal(await srsMenu.locator('ui-menu-label').innerText(), 'First 20 of 25 paths');
  assert.equal(await srsMenu.locator(':scope > ui-menu-item').first().getAttribute('href'), '/debug/gov/srs');
  assert.equal(await srsMenu.locator('.wb-path-menu-parent [slot=shortcut]').innerText(), 'Open');
  assert.equal(await srsMenu.locator('.wb-path-menu-child[aria-current=page] [slot=shortcut]').innerText(), 'Current');
  assert.equal(await srsMenu.locator('.wb-path-menu-child[data-path="/gov/srs/kind_1"] .wb-path-option-lede').count(), 0,
    'identity-only children reserve no empty description');
  assert.equal(await srsMenu.locator('.wb-path-menu-child[data-path="/gov/srs/card"] .wb-path-option-lede').textContent(),
    'Card definition Stores the prompt and answer for a study card.');
  assert.equal(await srsMenu.locator('.wb-path-menu-child[data-path="/gov/srs/kind_0"] .wb-path-option-lede').textContent(),
    'Authored long description ' + 'Exact help  '.repeat(1000) + 'END OF AUTHORED HELP', 'full authored help remains in the DOM');
  const richGeometry = await srsMenu.locator('.wb-path-menu-child').evaluateAll(rows => rows.map(row => {
    const label = row.querySelector('.wb-path-option-name').getBoundingClientRect();
    const caption = row.querySelector('.wb-path-option-lede');
    const rect = caption?.getBoundingClientRect();
    const control = row.shadowRoot.querySelector('[part=control]');
    return {label: {left: label.left, right: label.right, bottom: label.bottom},
      caption: rect && {left: rect.left, top: rect.top, height: rect.height, lineHeight: parseFloat(getComputedStyle(caption).lineHeight)},
      height: control.getBoundingClientRect().height, native: control.localName, href: control.getAttribute('href'),
      fontSize: getComputedStyle(row.querySelector('.wb-path-option-name')).fontSize};
  }));
  assert.ok(richGeometry.every(row => row.native === 'a' && row.href.startsWith('/debug/gov/srs/')),
    'all child choices retain actual native href anchors');
  assert.ok(richGeometry.every(row => row.fontSize === '12px'), 'path identity uses the compact workbench body size');
  assert.ok(richGeometry.every(row => !row.caption || row.caption.top >= row.label.bottom &&
    Math.abs(row.caption.left - row.label.left) < 1 && row.caption.height <= row.caption.lineHeight * 2 + 1),
    'authored captions align below identity and occupy at most two lines');
  assert.ok(richGeometry.every(row => row.height < 85), 'a 10k help string cannot dominate the chooser');
  const regions = await srsMenu.evaluate(menu => {
    const popup = menu.shadowRoot.querySelector('[part=popup]').getBoundingClientRect();
    const viewport = menu.shadowRoot.querySelector('[part=viewport]');
    const parent = menu.querySelector('.wb-path-menu-parent').getBoundingClientRect();
    return {topGap: parent.top - popup.top, height: viewport.clientHeight, content: viewport.scrollHeight,
      width: popup.width, left: popup.left, right: popup.right};
  });
  assert.ok(regions.topGap <= 12, 'the parent link starts immediately inside the shared shell');
  assert.ok(regions.height <= 400 && regions.content > regions.height, 'the actual menu viewport bounds long child lists');
  await settleChooser(page, srsMenu);
  await page.screenshot({ path: '/private/tmp/shrine-locator-menu.png' });
  // Context copy uses the same canonical native href without navigation or reads.
  const childAnchor = srsMenu.locator('.wb-path-menu-child[data-path="/gov/srs/card"] a');
  const beforeCopy = reads.length;
  await childAnchor.click({button: 'right'});
  const copyMenu = page.locator('#wb-path-menu');
  await copyMenu.getByRole('menuitem', {name: 'Copy link', exact: true}).click();
  await page.waitForFunction(() => window.__copies.length === 1);
  assert.equal(await page.evaluate(() => window.__copies[0]), base + '/debug/gov/srs/card');
  assert.equal(reads.length, beforeCopy, 'context copy does not read the namespace');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs/card');
  await copyMenu.locator('[role=menu]').waitFor({state: 'hidden'});
  if (!await srsMenu.evaluate(menu => menu.open)) await trigger.click();
  for (const options of [{modifiers: ['Meta']}, {button: 'middle'}]) {
    const popupEvent = context.waitForEvent('page');
    await childAnchor.click(options);
    const popup = await popupEvent;
    await popup.waitForURL(base + '/debug/gov/srs/card');
    await popup.close();
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs/card');
    assert.equal(await srsMenu.evaluate(menu => menu.open), true, 'modified/auxiliary activation retains the chooser');
  }
  for (const [theme, width] of [['dark', 1024], ['light', 390]]) {
    await page.keyboard.press('Escape');
    await srsMenu.locator('[role=menu]').waitFor({state: 'hidden'});
    await page.setViewportSize({width, height: 960});
    await page.evaluate(theme => document.body.setAttribute('data-theme', theme), theme);
    await trigger.click();
    await childAnchor.waitFor({state: 'visible'});
    const bounds = await srsMenu.locator('[part=popup]').boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width, 'chooser collision placement stays in viewport');
    await settleChooser(page, srsMenu);
    await page.screenshot({path: `/private/tmp/shrine-locator-menu-${theme}-${width}.png`});
  }
  await page.setViewportSize({width: 1440, height: 960});
  await page.evaluate(() => document.body.setAttribute('data-theme', 'light'));
  await page.keyboard.press('Escape');
  // Pointer dismissal deliberately clears transient focus on a later frame.
  // Wait for that closeout before beginning a distinct keyboard interaction.
  await page.waitForFunction(() => !document.querySelector('.wb-path-menu[data-path="/gov/srs"]')?.matches(':state(present)'));
  await trigger.press('ArrowDown');
  await page.waitForFunction(() => document.activeElement?.matches('ui-menu-item') &&
    document.activeElement.closest('.wb-path-menu')?.dataset.path === '/gov/srs');
  await srsMenu.locator('[role=menu]').waitFor({ state: 'visible' });
  await page.keyboard.press('End');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.path), '/gov/srs/kind_18');
  await page.keyboard.press('Home');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.path), '/gov/srs',
    'Home reaches the first canonical parent link without a separate footer focus region');
  await page.keyboard.type('card');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.path), '/gov/srs/card',
    'native menu typeahead searches basename before supporting lore');
  assert.ok(await srsMenu.locator('ui-menu-item').evaluateAll(nodes => nodes.some(node => node === document.activeElement)),
    'Mash menu owns keyboard selection');
  await page.keyboard.press('Escape');
  console.log('PASS: real child menus, empty leaf, non-navigation disclosure, cache and keyboard/focus behavior.');

  // The ancestor has not been read by this locator; a failed request must
  // settle visibly and remain recoverable without manufacturing children.
  failedPaths.add('/gov');
  const govMenu = menuAt('/gov');
  await govMenu.getByRole('button', { name: 'Children of /gov', exact: true }).click();
  await govMenu.getByRole('menuitem', { name: 'Try again', exact: true }).waitFor();
  assert.equal(await govMenu.getAttribute('aria-busy'), null);
  assert.equal(await govMenu.locator('ui-menu-item[data-path="/gov/srs"]').count(), 0);
  assert.equal(await govMenu.locator('.wb-path-menu-parent a').getAttribute('href'), '/debug/gov',
    'a failed child read does not remove the real parent destination');
  failedPaths.delete('/gov');
  await govMenu.getByRole('menuitem', { name: 'Try again', exact: true }).click();
  await govMenu.locator('ui-menu-item[data-path="/gov/srs"]').waitFor({ state: 'visible' });
  const recoveredLink = govMenu.locator('ui-menu-item[data-path="/gov/srs"] a');
  await recoveredLink.focus();
  await recoveredLink.press('Enter');
  await ready('/gov/srs');
  assert.equal(await form.isVisible(), false);
  assert.equal(await locator.locator('ui-menu[open]').count(), 0, 'navigation closes stale menus');
  console.log('PASS: failed reads settle, retry recovers, real menu links navigate and close.');

  // Wait for the independent sidebar reader before measuring locator reads.
  // This avoids confusing its ancestor reveal with a path-menu cache miss.
  const sidebarReady = path => page.waitForFunction(path =>
    [...document.querySelectorAll('#debug-path-tree ui-tree-item')].some(row =>
      row.dataset.path === path && row.dataset.readState === 'ready'), path);
  await sidebarReady('/gov/srs');
  const parentBeforeNavigation = reads.filter(path => path === '/debug/gov/srs').length;
  let parentMenu = menuAt('/gov/srs');
  await parentMenu.getByRole('button', { name: 'Children of /gov/srs', exact: true }).click();
  await parentMenu.locator('ui-menu-item[data-path="/gov/srs/card"]').click();
  await ready('/gov/srs/card');
  parentMenu = menuAt('/gov/srs');
  await parentMenu.getByRole('button', { name: 'Children of /gov/srs', exact: true }).click();
  await parentMenu.locator('ui-menu-item[data-path="/gov/srs/card"]').waitFor({ state: 'visible' });
  assert.equal(reads.filter(path => path === '/debug/gov/srs').length, parentBeforeNavigation,
    'ordinary child navigation reuses its recently read parent menu');
  await page.keyboard.press('Escape');
  await parentMenu.locator('[role=menu]').waitFor({ state: 'hidden' });
  const refreshResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === '/debug/gov/srs/card' && response.request().resourceType() === 'fetch');
  await page.locator('#wb-refresh').click();
  await refreshResponse;
  await ready('/gov/srs/card');
  await sidebarReady('/gov/srs');
  const parentAfterRefresh = reads.filter(path => path === '/debug/gov/srs').length;
  parentMenu = menuAt('/gov/srs');
  await parentMenu.getByRole('button', { name: 'Children of /gov/srs', exact: true }).click();
  await parentMenu.locator('ui-menu-item[data-path="/gov/srs/card"]').waitFor({ state: 'visible' });
  assert.ok(reads.filter(path => path === '/debug/gov/srs').length > parentAfterRefresh,
    'explicit refresh invalidates ancestor menus before they reopen');
  await page.keyboard.press('Escape');
  await parentMenu.locator('[role=menu]').waitFor({ state: 'hidden' });
  console.log('PASS: bounded-freshness parent menus survive child navigation and invalidate on explicit refresh.');

  await go('/sys/about');
  await page.evaluate(() => {
    const chooseAnotherControl = event => {
      if (event.detail?.document?.path !== '/sys') return;
      document.removeEventListener('debug:navigate', chooseAnotherControl);
      // Move focus after the locator schedules its new native anchor, but
      // before Lit resolves it. That newer choice must win the microtask.
      document.querySelector('#debug-filter').focus();
    };
    document.addEventListener('debug:navigate', chooseAnotherControl);
  });
  await locator.getByRole('link', {name: 'Open /sys', exact: true}).click();
  await ready('/sys');
  assert.equal(await locator.locator('ui-link[current]').getAttribute('href'), '/debug/sys');
  assert.equal(await page.evaluate(async () => {
    await document.querySelector('.wb-path-ancestor[current]').updateComplete;
    await new Promise(requestAnimationFrame);
    return document.activeElement === document.querySelector('#debug-filter');
  }), true, 'async native-anchor readiness does not steal a newer focus choice');
  await page.screenshot({ path: '/private/tmp/shrine-locator-desktop.png' });
  for (const size of [{ width: 768, height: 1024 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    await go('/gov/srs/card');
    await fits();
    await page.screenshot({ path: '/private/tmp/shrine-locator-' + size.width + '.png' });
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
    await fits();
    await input.press('Escape');
  }
  await go('/deep/namespace/contains/another/record');
  const scroll = locator.locator('ui-scroll-area.wb-path-scroll');
  await page.waitForFunction(() => document.querySelector('.wb-path-scroll')?.matches(':state(scrollable-inline)'));
  await scroll.hover();
  const rail = scroll.locator('[part=inline-scrollbar]');
  await rail.waitFor({state: 'visible'});
  assert.ok((await rail.boundingBox()).height >= 8, 'Mash retains its actual pointer lane instead of the bespoke 4px rail');
  const beforeScroll = await scroll.evaluate(node => node.viewportElement.scrollLeft);
  await rail.focus();
  await rail.press('Home');
  await page.waitForFunction(() => document.querySelector('.wb-path-scroll').viewportElement.scrollLeft === 0);
  assert.ok(beforeScroll > 0, 'the current deep path is automatically revealed');
  const fineRoot = locator.locator('.wb-path-root a');
  await fineRoot.focus();
  assertRingContained(await focusRingGeometry(fineRoot), 'fine deep root after Home');
  await rail.focus();
  await rail.press('End');
  await page.waitForFunction(() => document.querySelector('.wb-path-scroll').viewportElement.scrollLeft > 0);
  await locator.locator('ui-link[current] a').focus();
  const fineCurrentGeometry = await focusRingGeometry(locator.locator('ui-link[current] a'));
  assertRingContained(fineCurrentGeometry, 'fine deep current after End');
  console.log('Fine deep focus geometry:', JSON.stringify(fineCurrentGeometry));
  await fits();
  await page.screenshot({path: '/private/tmp/shrine-locator-deep.png'});
  console.log('PASS: quiet Mash horizontal overflow, full pointer lane, Home/End and current-path reveal.');

  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, serviceWorkers: 'block'});
  await touchContext.route('**/*', routeFixture);
  const touchPage = await touchContext.newPage();
  touchPage.on('pageerror', error => errors.push(error.message));
  await touchPage.goto(base + '/debug/gov/srs/card');
  await touchPage.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  const touchRoot = touchPage.locator('.wb-path-root a');
  await touchRoot.scrollIntoViewIfNeeded();
  await touchPage.keyboard.press('Tab');
  await touchRoot.focus();
  const touchRootGeometry = await focusRingGeometry(touchRoot);
  assertRingContained(touchRootGeometry, 'coarse root');
  assert.equal(touchRootGeometry.viewport.bottom - touchRootGeometry.viewport.top, 52, '44px touch target reserves the full two-sided4px ring');
  console.log('Coarse root focus geometry:', JSON.stringify(touchRootGeometry));
  const targets = await touchPage.locator('.wb-path-ancestor a').evaluateAll(nodes => nodes.map(node => {
    const rect = node.getBoundingClientRect(); return {width: rect.width, height: rect.height};
  }));
  assert.ok(targets.every(rect => rect.width >= 44 && rect.height >= 44), 'every coarse breadcrumb, including root, has a real 44px native target on both axes');
  const touchMenu = touchPage.locator('.wb-path-menu[data-path="/gov/srs"]');
  await touchMenu.getByRole('button', {name: 'Children of /gov/srs', exact: true}).tap();
  await touchMenu.locator('.wb-path-menu-child').first().waitFor({state: 'visible'});
  const menuTargets = await touchMenu.locator('ui-menu-item a').evaluateAll(nodes => nodes.map(node => {
    const rect = node.getBoundingClientRect(); return {width: rect.width, height: rect.height};
  }));
  assert.ok(menuTargets.every(rect => rect.width >= 44 && rect.height >= 44), 'rich child and parent links keep real44px coarse targets');
  const touchBounds = await touchMenu.locator('[part=popup]').boundingBox();
  assert.ok(touchBounds.x >= 0 && touchBounds.x + touchBounds.width <= 390);
  await settleChooser(touchPage, touchMenu);
  await touchPage.screenshot({path: '/private/tmp/shrine-locator-menu-light-390-coarse.png'});
  await touchPage.keyboard.press('Escape');
  await touchRoot.tap();
  await touchPage.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.path === '/' &&
    document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  assert.equal(await touchPage.locator('.wb-path-root[current] a').getAttribute('aria-current'), 'page');
  await touchPage.screenshot({path: '/private/tmp/shrine-locator-touch.png'});
  await touchPage.getByRole('button', {name: 'Edit namespace path', exact: true}).tap();
  const touchInput = touchPage.locator('#debug-go input');
  await touchInput.fill('/deep/namespace/contains/another/record');
  await touchInput.press('Enter');
  await touchPage.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.path === '/deep/namespace/contains/another/record' &&
    document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  const touchLast = touchPage.locator('.wb-path-ancestor[current] a');
  await touchLast.focus();
  assertRingContained(await focusRingGeometry(touchLast), 'coarse deep current auto-reveal');
  await touchRoot.scrollIntoViewIfNeeded();
  await touchRoot.focus();
  assertRingContained(await focusRingGeometry(touchRoot), 'coarse deep first endpoint');
  await touchLast.scrollIntoViewIfNeeded();
  await touchLast.focus();
  const touchDeepGeometry = await focusRingGeometry(touchLast);
  assertRingContained(touchDeepGeometry, 'coarse deep last endpoint');
  console.log('Coarse deep focus geometry:', JSON.stringify(touchDeepGeometry));
  await touchPage.screenshot({path: '/private/tmp/shrine-locator-touch-deep.png'});
  await touchContext.close();
  assert.deepEqual(writes, []);
  assert.deepEqual(unexpected, []);
  assert.deepEqual(errors, []);
  console.log('PASS: ancestor links, fresh navigation state, 768/390px, coarse root activation, zero runtime requests/writes/page errors. Fixture GETs:', reads.length);
} catch (error) {
  console.error('Locator failure context:', await page.evaluate(() => {
    const active = document.activeElement;
    return {
      active: active?.outerHTML.slice(0, 1000),
      innerActive: active?.shadowRoot?.activeElement?.outerHTML.slice(0, 1000),
      menus: [...document.querySelectorAll('.wb-path-menu')].map(menu => ({
        path: menu.dataset.path, open: menu.open, busy: menu.getAttribute('aria-busy'),
      })),
    };
  }).catch(() => null), errors);
  await page.screenshot({ path: '/private/tmp/shrine-locator-failure.png' }).catch(() => {});
  throw error;
} finally {
  await context.close();
}
} finally {
  await browser.close();
}
