// Frozen production assets over a saved real shell, with exact inert fixtures.
// Every browser request is intercepted; there is deliberately no live fallback.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live namespace access is forbidden');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://namespace-tree-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const segments = ['app', 'srs', 'collections', 'review-queue', 'cards-with-an-intentionally-long-unbroken-namespace-name-0123456789', 'variants', 'localized', '日本語-price?#%λ'];
const chain = segments.map((_, index) => '/' + segments.slice(0, index + 1).join('/'));
const leaf = chain.at(-1) + '/leaf';
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const reads = [], writes = [], unexpected = [], errors = [], screenshots = [], gestures = [];
const failures = new Map();
let activePage;
const browser = await chromium.launch();
try {
  const author = await browser.newPage();
  const fixtures = await author.evaluate(({shell, chain, leaf}) => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell is not the current debugger anatomy');
    const children = {'/': ['/landing', chain[0], '/fault', '/bare', '/wide', '/structural'], '/structural': ['/structural/child'],
      '/landing': Array.from({length: 80}, (_, index) => '/landing/row-' + index),
      '/wide': Array.from({length: 45}, (_, index) => '/wide/sibling-' + String(index).padStart(2, '0'))};
    chain.forEach((path, index) => { children[path] = [chain[index + 1] || leaf, path + '/sidecar']; });
    const paths = [...new Set([...Object.keys(children), ...Object.values(children).flat(), '/fault', '/bare', leaf])];
    return Object.fromEntries(paths.map(path => {
      const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
      Object.assign(workspace.dataset, {path, kind: path === '/structural' ? 'namespace' : 'record', writable: 'false',
        label: path.split('/').at(-1) || 'Namespace', fixture: 'namespace-tree', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch', 'description', 'descriptionSource']) delete workspace.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      if (path === '/structural') myth.remove();
      else if (path !== '/bare') {
        const slots = [
          ['/sys/lede', chain.includes(path) ? 'Authored title for level ' + (chain.indexOf(path) + 1) : 'Record ' + path],
          ['/sys/help', 'Authored help explains ' + path + ' without invented interpretation.'],
          ['/state', 'ready'], ['/reference', '/bare'], ['/long-key-' + 'x'.repeat(64), 'Long value with <script>window.__treeExecuted = true</script> kept as literal text.'], ['/omitted', 'Fourth preview slot stays in full record'],
        ];
        for (const [key, text] of slots) {
          const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
          const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
          const pail = doc.createElement('sh-pail');
          if (key === '/reference') { const anchor = doc.createElement('a'); anchor.href = '/debug/bare'; anchor.textContent = text; pail.append(anchor); }
          else pail.textContent = text;
          limb.append(slot, pail); myth.append(limb);
        }
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of children[path] || []) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.dataset.kind = child === '/structural' ? 'namespace' : 'record';
        item.dataset.label = child.split('/').at(-1); item.title = item.dataset.label; tree.append(item);
      }
      return [path, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, {shell, chain, leaf});
  await author.close();

  async function context(options = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 960}, ...options});
    context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    await context.addInitScript(({base}) => {
      if (location.origin !== base || sessionStorage.getItem('namespace-tree-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: true, root: '/', expanded: ['/']}));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: ['/landing'], pages: [null], cursor: 0}));
      sessionStorage.setItem('namespace-tree-fixture', 'seeded');
    }, {base});
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET') { writes.push(request.method() + ' ' + request.url()); return route.abort(); }
      if (url.origin !== base || url.search) { unexpected.push(request.url()); return route.abort(); }
      if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      let path;
      try { path = decodeURIComponent(url.pathname.replace(/^\/debug/, '')) || '/'; } catch { /* Rejected below. */ }
      if (!/^\/debug(?:\/|$)/.test(url.pathname) || !Object.hasOwn(fixtures, path)) { unexpected.push(request.url()); return route.abort(); }
      reads.push({path, url: request.url(), page: request.frame().page()});
      if (failures.get(path)) { failures.set(path, failures.get(path) - 1); return route.fulfill({status: 503, contentType: 'text/plain', body: 'Intentional fixture read failure'}); }
      return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
    });
    return context;
  }
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function settled(check, message) { for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); } assert.fail(message); }
  const item = (page, path) => page.locator('#debug-path-tree ui-tree-item[data-path=' + JSON.stringify(path) + ']');
  const control = (page, path) => item(page, path).locator(':scope > [part=root] > button[part=control]');
  const disclosure = (page, path) => control(page, path).locator('[part=disclosure]');
  const bookmark = (page, path) => item(page, path).locator(':scope > ui-button.debug-bookmark-toggle[slot=actions]');
  const bookmarkButton = (page, path) => bookmark(page, path).locator('button[part=control]');
  const savedLink = (page, path) => page.locator('#debug-saved .debug-page-row[data-path=' + JSON.stringify(path) + '] > ui-link.debug-page-link');
  const hoverMyth = page => page.locator('#wb-path-preview sh-myth[variant=preview]');
  const current = page => page.locator('#debug-workspace').getAttribute('data-path');
  const pageReads = page => reads.filter(read => read.page === page).map(read => read.path);
  async function ready(page, path) {
    await page.waitForFunction(path => { const ws = document.querySelector('#debug-workspace'); return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true'; }, path, {timeout: 5000});
  }
  async function loaded(page, path) { await settled(async () => await item(page, path).getAttribute('data-read-state') === 'ready', 'tree snapshot loaded: ' + path); }
  async function showSidebar(page) {
    if (!await page.locator('#debug-filter input').isVisible()) await page.locator('#debug-sidebar-toggle').click();
    await page.waitForFunction(() => {
      const section = document.querySelector('#debug-section-tree'), reveal = section?.shadowRoot?.querySelector('ui-reveal');
      return section?.open && reveal?.matches(':state(active)') && section.querySelector('#debug-children').getBoundingClientRect().height > 0;
    }, null, {timeout: 5000});
  }
  async function expand(page, path, gesture = 'pointer') {
    const before = await current(page);
    if (await item(page, path).getAttribute('expanded') === null) {
      if (gesture === 'keyboard') { await control(page, path).focus(); await control(page, path).press('ArrowRight'); }
      else if (gesture === 'touch') await disclosure(page, path).tap();
      else await disclosure(page, path).click();
    }
    await loaded(page, path);
    assert.equal(await item(page, path).getAttribute('expanded') !== null, true, 'branch activation expands its hierarchy');
    assert.equal(await current(page), before, 'branch disclosure does not select or navigate');
    gestures.push(gesture);
  }
  async function assertSaved(page, path, expected) {
    const label = (expected ? 'Unsave ' : 'Save ') + path;
    await settled(async () => await bookmarkButton(page, path).getAttribute('aria-pressed') === String(expected), 'native bookmark pressed state follows Saved');
    assert.equal(await bookmarkButton(page, path).getAttribute('aria-label'), label, 'native bookmark name includes the exact canonical path');
    assert.equal(await bookmark(page, path).evaluate(el => el.selected), expected, 'Mash selected state follows the actual Saved state');
    assert.equal(await page.evaluate(path => JSON.parse(localStorage.getItem('shrine-debug.v1.saved')).includes(path), path), expected);
    assert.equal(await savedLink(page, path).count(), expected ? 1 : 0, 'Saved page destination synchronizes without navigating');
    if (expected) assert.equal(await savedLink(page, path).getAttribute('href'), href(path), 'Saved retains the canonical encoded destination');
  }
  async function toggleBookmark(page, path, gesture = 'pointer') {
    const before = {path: await current(page), url: page.url(), expanded: await item(page, path).getAttribute('expanded'), reads: pageReads(page).length,
      saved: await bookmarkButton(page, path).getAttribute('aria-pressed') === 'true'};
    const node = await item(page, path).elementHandle(), action = await bookmarkButton(page, path).elementHandle();
    if (gesture === 'keyboard') { await bookmarkButton(page, path).focus(); await bookmarkButton(page, path).press('Enter'); }
    else if (gesture === 'touch') await bookmarkButton(page, path).tap();
    else { await control(page, path).hover(); await bookmarkButton(page, path).click(); }
    await assertSaved(page, path, !before.saved);
    assert.equal(await current(page), before.path, 'bookmark does not select or navigate');
    assert.equal(page.url(), before.url, 'bookmark does not add browser history');
    assert.equal(await item(page, path).getAttribute('expanded'), before.expanded, 'bookmark does not toggle branch expansion');
    assert.equal(pageReads(page).length, before.reads, 'save and unsave do not read namespace data');
    assert.ok(await node.evaluate(el => el.isConnected) && await action.evaluate(el => el.isConnected), 'bookmark updates preserve the row and native action identities');
    assert.equal(await item(page, path).locator(':scope > sh-myth[slot=preview]').count(), 0, 'bookmark does not restore the retired inline record preview');
    const glyph = bookmark(page, path).locator('ui-icon');
    assert.equal(await glyph.getAttribute('name'), 'object.bookmark'); assert.equal(await glyph.getAttribute('data-icon-source'), 'Mash');
    assert.equal(await glyph.locator('svg').count(), 1, 'bookmark uses the stock Mash icon');
    gestures.push('bookmark-' + gesture);
  }
  // Metadata moved out of the tree. Preserve its fidelity coverage on the
  // surviving shared hover Myth, not a fabricated replacement inline panel.
  async function openHover(page, path) {
    const before = await current(page), expanded = await item(page, path).getAttribute('expanded');
    await page.mouse.move(1430, 940); await control(page, path).hover();
    await page.waitForFunction(path => { const card = document.querySelector('#wb-path-preview'); return card?.open && card.matches(':state(active)') && card.dataset.path === path && card.dataset.readState === 'ready'; }, path, {timeout: 5000});
    await hoverMyth(page).waitFor({state: 'visible'});
    assert.equal(await current(page), before); assert.equal(await item(page, path).getAttribute('expanded'), expanded);
    assert.equal(await item(page, path).locator(':scope > sh-myth[slot=preview]').count(), 0);
  }
  async function closeHover(page) {
    await page.keyboard.press('Escape'); await page.mouse.move(1430, 940);
    await settled(() => page.locator('#wb-path-preview').evaluate(el => !el.open), 'Escape closes the shared hover Myth');
  }
  async function deep(page) {
    await loaded(page, '/');
    for (const [index, path] of chain.entries()) {
      const before = pageReads(page).length, already = await item(page, path).getAttribute('data-read-state') === 'ready';
      await expand(page, path, index % 2 ? 'keyboard' : 'pointer');
      assert.equal(pageReads(page).length - before, already ? 0 : 1, 'each new branch reads only its own snapshot once');
      assert.equal(await item(page, path).locator(':scope > ui-tree-item').count(), 2, 'each fixture branch exposes exactly its direct children');
      assert.equal(await item(page, path).locator(':scope > [slot=preview]').count(), 0, 'hierarchy expansion does not automatically dump metadata');
    }
    assert.equal(await control(page, chain.at(-1)).getAttribute('aria-level'), '9', 'eight namespace levels retain their full accessible hierarchy below root');
  }
  async function geometry(page, path, coarse = false, focus = true) {
    const row = control(page, path); await row.scrollIntoViewIfNeeded();
    if (focus) { await row.focus(); await row.press('Tab'); await page.keyboard.press('Shift+Tab'); }
    const state = await row.evaluate(el => {
      const box = el.getBoundingClientRect(), style = getComputedStyle(el), host = el.getRootNode().host;
      const rect = node => { const b = node.getBoundingClientRect(); return {x: b.x, y: b.y, width: b.width, height: b.height, right: b.right, bottom: b.bottom}; };
      const reach = style.outlineStyle === 'none' ? 0 : Math.max(0, parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset));
      const ring = {x: box.x - reach, y: box.y - reach, right: box.right + reach, bottom: box.bottom + reach};
      const clips = []; let ancestor = el;
      while (ancestor) {
        ancestor = ancestor.assignedSlot || ancestor.parentNode; if (ancestor instanceof ShadowRoot) ancestor = ancestor.host;
        if (!(ancestor instanceof Element)) continue;
        const css = getComputedStyle(ancestor), bound = ancestor.getBoundingClientRect();
        if (/^(hidden|clip|auto|scroll)$/.test(css.overflowX) || /^(hidden|clip|auto|scroll)$/.test(css.overflowY)) clips.push({name: ancestor.id || ancestor.getAttribute('part') || ancestor.localName,
          x: bound.x + ancestor.clientLeft, y: bound.y + ancestor.clientTop, right: bound.x + ancestor.clientLeft + ancestor.clientWidth, bottom: bound.y + ancestor.clientTop + ancestor.clientHeight,
          clipX: /^(hidden|clip|auto|scroll)$/.test(css.overflowX), clipY: /^(hidden|clip|auto|scroll)$/.test(css.overflowY)});
      }
      const action = host.querySelector(':scope > ui-button.debug-bookmark-toggle[slot=actions]')?.shadowRoot.querySelector('button');
      return {control: rect(el), label: rect(el.querySelector('[part=label]')), disclosure: rect(el.querySelector('[part=disclosure]')), action: action ? rect(action) : null,
        ring, clips, outline: style.outlineStyle, outlineWidth: parseFloat(style.outlineWidth), focused: el.getRootNode().activeElement === el};
    });
    assert.ok(state.label.width >= 23.9, 'deep labels retain at least24px of useful reading lane: ' + JSON.stringify(state));
    assert.ok(state.control.right <= state.action.x + .6, 'native row and bookmark action do not overlap: ' + JSON.stringify(state));
    if (coarse) for (const name of ['control', 'disclosure', 'action']) assert.ok(state[name].width >= 43.9 && state[name].height >= 43.9, 'native touch ' + name + ' has44px in both axes: ' + JSON.stringify(state));
    else {
      assert.ok(Math.abs(state.control.height - 28) < .6, 'fine-pointer namespace rows retain the shared compact28px rhythm: ' + JSON.stringify(state));
      assert.ok(Math.abs(state.action.width - 24) < .6 && Math.abs(state.action.height - 24) < .6, 'fine-pointer bookmark action uses the stock small24px square');
    }
    if (focus) assert.ok(state.focused && state.outline !== 'none' && state.outlineWidth > 0, 'native tree keyboard focus is visible');
    assert.ok(state.clips.every(clip => (!clip.clipX || state.ring.x >= clip.x - .6 && state.ring.right <= clip.right + .6) &&
      (!clip.clipY || state.ring.y >= clip.y - .6 && state.ring.bottom <= clip.bottom + .6)), 'native tree control and full focus outline fit every clipping ancestor: ' + JSON.stringify(state));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'namespace page does not overflow horizontally');
    return state;
  }
  async function hoverGeometry(page) {
    const bounds = await hoverMyth(page).evaluate(el => {
      const box = el.getBoundingClientRect(), root = el.shadowRoot.querySelector('[part=root]').getBoundingClientRect();
      const open = el.querySelector(':scope > a[slot=actions]').getBoundingClientRect();
      const slots = [...el.querySelectorAll(':scope > sh-limb')].map(limb => ({
        key: limb.querySelector('sh-slot')?.getAttribute('title') || '',
        label: limb.shadowRoot.querySelector('[part~=label]').getBoundingClientRect().toJSON(),
        value: limb.shadowRoot.querySelector('[part=value]').getBoundingClientRect().toJSON(),
      }));
      return {box: box.toJSON(), root: root.toJSON(), open: open.toJSON(), slots, threshold: 28 * parseFloat(getComputedStyle(document.documentElement).fontSize),
        coarse: matchMedia('(pointer: coarse)').matches, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth};
    });
    assert.ok(bounds.root.left >= bounds.box.left - .6 && bounds.root.right <= bounds.box.right + .6 && bounds.open.left >= bounds.box.left - .6 && bounds.open.right <= bounds.box.right + .6,
      'preview content and its actual action stay inside the available lane: ' + JSON.stringify(bounds));
    assert.ok(bounds.scrollWidth <= bounds.clientWidth + 1, 'long authored preview metadata does not cause horizontal overflow');
    for (const {key, label, value} of bounds.slots) {
      if (bounds.clientWidth <= bounds.threshold) assert.ok(value.top >= label.bottom + 3.9 && Math.abs(value.left - label.left) < .6,
        'a narrow record container stacks each value below its complete key, including legacy preview variants: ' + JSON.stringify(bounds));
      else if (key.length <= 20) assert.ok(value.left >= label.right - .6, 'a wide record retains distinct columns for short keys with room');
    }
    if (bounds.coarse) assert.ok(bounds.open.width >= 43.9 && bounds.open.height >= 43.9, 'hover preview action preserves44px native touch target');
  }
  async function resizeExtreme(page, direction) {
    const resize = page.getByRole('separator', {name: 'Resize sidebar', exact: true});
    const box = await resize.boundingBox(); await page.mouse.move(box.x + box.width / 2, box.y + 100); await page.mouse.down();
    await page.mouse.move(box.x + direction * 1200, box.y + 100, {steps: 10}); await page.mouse.up();
    await settled(() => page.locator('#debug-workspace').evaluate((el, direction) => Math.abs(el.shadowRoot.querySelector('[part=sidebar]').getBoundingClientRect().width - (direction < 0 ? el.sidebarMinWidth : el.sidebarMaxWidth)) < 1, direction), 'sidebar reaches its supported ' + (direction < 0 ? 'minimum' : 'maximum'));
  }
  async function capture(page, name) {
    await showSidebar(page);
    const path = '/private/tmp/shrine-namespace-tree-' + name + '.png'; await page.screenshot({path, animations: 'disabled'}); screenshots.push(path);
    assert.equal(await page.evaluate(() => window.__treeExecuted), undefined, 'authored text never executes markup');
  }

  const desktop = await context(); const page = await desktop.newPage(); activePage = page;
  await page.goto(base + href('/landing')); await ready(page, '/landing'); await showSidebar(page); await loaded(page, '/');
  assert.deepEqual(pageReads(page), ['/landing', '/'], 'initial namespace view reads only document and root');
  assert.equal(await page.locator('#debug-path-tree').getAttribute('variant'), 'namespace');
  assert.equal(await page.locator('#debug-path-tree > ui-tree').evaluate(el => el.selectionFollowsFocus), false);
  assert.equal(await page.locator('#debug-path-tree [slot=preview]').count(), 0);
  assert.equal(await page.locator('#debug-path-tree').evaluate(el => {
    const graph = el.shadowRoot.querySelector('[part=graph]'); return !graph || getComputedStyle(graph).display === 'none';
  }), true, 'namespace hierarchy has no invented revision-graph overlay');
  for (const path of ['/', chain[0]]) {
    const glyph = item(page, path).locator(':scope > ui-icon[slot=icon]');
    assert.equal(await glyph.getAttribute('data-icon-source'), 'Mash');
    assert.match(await glyph.getAttribute('name'), /^object\./);
    assert.equal(await glyph.locator('svg').count(), 1, 'stock Mash registry supplies the actual visible icon');
  }
  const rootNode = await item(page, '/').elementHandle(), rootControl = await control(page, '/').elementHandle();
  await control(page, chain[0]).click(); await ready(page, chain[0]); await loaded(page, chain[0]);
  assert.equal(await item(page, chain[0]).getAttribute('expanded'), null, 'split row selection does not expand the branch');
  assert.equal(await control(page, chain[0]).getAttribute('aria-current'), 'page');
  assert.equal(await control(page, chain[0]).getAttribute('aria-selected'), 'true');
  const selectedNode = await item(page, chain[0]).elementHandle(), selectedControl = await control(page, chain[0]).elementHandle();
  await toggleBookmark(page, chain[0]); await toggleBookmark(page, chain[0]);
  const beforePreview = pageReads(page).length; await openHover(page, chain[0]);
  assert.equal(pageReads(page).length, beforePreview, 'loaded hover metadata opens without a read');
  assert.equal(await hoverMyth(page).getAttribute('title'), 'Authored title for level 1');
  assert.match(await hoverMyth(page).locator(':scope > [slot=description]').textContent(), /^Authored help explains/);
  assert.equal(await hoverMyth(page).locator('sh-limb').count(), 3, 'shared compact hover limits visible data slots to 3');
  assert.equal(await hoverMyth(page).locator('sh-slot[title="/sys/lede"], sh-slot[title="/sys/help"]').count(), 0, 'authored documentation is not duplicated as data rows');
  assert.equal(await hoverMyth(page).locator('sh-pail a').getAttribute('href'), href('/bare'));
  assert.match(await hoverMyth(page).locator('sh-pail').last().textContent(), /<script>window\.__treeExecuted = true<\/script>/, 'long authored slot text remains literal and complete in the preview DOM');
  await hoverGeometry(page); await capture(page, 'authored-hover-1440'); await closeHover(page); await deep(page);
  assert.equal(await rootNode.evaluate(el => el.isConnected), true); assert.equal(await rootControl.evaluate(el => el.isConnected), true);
  assert.equal(await selectedNode.evaluate(el => el.isConnected), true); assert.equal(await selectedControl.evaluate(el => el.isConnected), true);
  const beforeFocus = pageReads(page).length;
  await control(page, chain[0]).focus(); await control(page, chain[0]).press('ArrowDown');
  assert.equal(await control(page, chain[1]).evaluate(el => el.getRootNode().activeElement === el), true, 'ArrowDown moves native tree focus to its visible child');
  assert.equal(await current(page), chain[0]); assert.equal(await control(page, chain[0]).getAttribute('aria-selected'), 'true');
  assert.equal(pageReads(page).length, beforeFocus, 'roving keyboard focus neither selects nor reads another record');
  await control(page, chain[1]).press('ArrowUp');
  assert.equal(await control(page, chain[0]).evaluate(el => el.getRootNode().activeElement === el), true);
  await control(page, chain[2]).focus(); await control(page, chain[2]).press('Tab');
  assert.equal(await bookmarkButton(page, chain[2]).evaluate(el => el.getRootNode().activeElement === el), true, 'Tab reveals and enters the current row bookmark action');
  assert.ok(await bookmark(page, chain[2]).evaluate(el => Number(getComputedStyle(el).opacity) > 0), 'keyboard-only bookmark action is visually available');
  await toggleBookmark(page, chain[2], 'keyboard');
  assert.equal(await bookmarkButton(page, chain[2]).evaluate(el => el.getRootNode().activeElement === el), true, 'saving preserves native bookmark keyboard focus');
  await toggleBookmark(page, chain[2], 'keyboard');
  assert.equal(pageReads(page).length, beforeFocus, 'keyboard bookmark activation never reads a snapshot');
  const beforeCached = pageReads(page).length;
  await toggleBookmark(page, chain[3]); await toggleBookmark(page, chain[5]); await toggleBookmark(page, chain[5]);
  await assertSaved(page, chain[3], true); await assertSaved(page, chain[5], false);
  await control(page, chain[3]).focus(); await control(page, chain[3]).press('ArrowLeft');
  await assertSaved(page, chain[3], true);
  assert.equal(await item(page, chain[4]).isVisible(), false, 'collapsed branch hides its child hierarchy');
  await expand(page, chain[3], 'keyboard'); await assertSaved(page, chain[3], true); await toggleBookmark(page, chain[3]);
  assert.equal(pageReads(page).length, beforeCached, 'cached disclosure and independent bookmark cycles make no extra reads');
  const filter = page.locator('#debug-filter input'), beforeFilter = pageReads(page).length;
  await filter.fill('Authored title for level 8');
  assert.equal(await item(page, chain.at(-1)).isVisible(), true); assert.equal(await item(page, '/wide').isVisible(), false);
  assert.equal(await control(page, chain[0]).getAttribute('aria-current'), 'page', 'filtering preserves namespace selection');
  await filter.press('Escape'); assert.equal(await filter.inputValue(), '');
  assert.equal(pageReads(page).length, beforeFilter, 'filter searches loaded authored metadata only');
  assert.equal(await item(page, '/bare').getAttribute('data-read-state'), 'idle');
  await toggleBookmark(page, '/bare'); await toggleBookmark(page, '/bare');
  assert.equal(await item(page, '/bare').getAttribute('data-read-state'), 'idle', 'bookmarking an unread path does not hydrate it');
  const beforeBare = pageReads(page).length;
  await openHover(page, '/bare'); assert.match(await hoverMyth(page).locator(':scope > [slot=meta]').textContent(), /0 slots/);
  assert.equal(await hoverMyth(page).locator('sh-limb').count(), 0); await closeHover(page);
  assert.deepEqual(pageReads(page).slice(beforeBare), ['/bare'], 'explicit hover intent reads the empty record once');
  assert.equal(await item(page, '/bare').locator(':scope > [slot=meta]').count(), 0, 'absent metadata does not create authored filler');
  assert.equal(await control(page, '/bare').locator('[part=meta]').evaluate(el => el.getBoundingClientRect().width), 0, 'absent metadata releases its layout lane');
  await expand(page, '/structural'); await openHover(page, '/structural');
  assert.equal(await hoverMyth(page).locator('sh-limb').count(), 0, 'structural namespaces do not invent record slots');
  assert.match(await hoverMyth(page).locator(':scope > [slot=meta]').textContent(), /No own record/); await closeHover(page);
  failures.set('/fault', 1); const beforeError = pageReads(page).length;
  await disclosure(page, '/fault').click(); await settled(async () => await item(page, '/fault').getAttribute('data-read-state') === 'error', '503 becomes a bounded inline error');
  assert.equal(await current(page), chain[0]); assert.match(await item(page, '/fault').locator(':scope > [slot=preview]').textContent(), /503/);
  await item(page, '/fault').getByRole('button', {name: 'Retry /fault', exact: true}).click(); await loaded(page, '/fault');
  assert.deepEqual(pageReads(page).slice(beforeError), ['/fault', '/fault'], 'retry reads exactly the same failed path once');
  assert.equal(await item(page, '/fault').locator(':scope > .debug-node-status').count(), 0);
  await control(page, chain.at(-1)).focus(); await control(page, chain.at(-1)).press('Enter'); await ready(page, chain.at(-1));
  assert.equal(await control(page, chain.at(-1)).getAttribute('aria-current'), 'page', 'Enter selects the deep canonical namespace path');
  assert.equal(await control(page, chain.at(-1)).getAttribute('aria-selected'), 'true');
  assert.equal(await control(page, chain[0]).getAttribute('aria-selected'), 'false', 'previous row relinquishes selection without being replaced');
  console.log('PASS: eight-level lazy split navigation, independent bookmarks without reads, authored hover fidelity, cached DOM/focus, filter, empty and retry states.');

  await control(page, '/landing').click(); await ready(page, '/landing'); await expand(page, '/wide');
  const scrolls = await page.evaluateHandle(() => ({
    sidebar: document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area'),
    main: document.querySelector('#debug-workspace').shadowRoot.querySelector('ui-scroll-area[part=main-body]'),
  }));
  await scrolls.evaluate(({sidebar, main}) => { sidebar.scrollViewportTo({top: 0, behavior: 'instant'}); main.scrollViewportTo({top: 0, behavior: 'instant'}); });
  const sidebarBox = await page.locator('#debug-sidebar').boundingBox(); await page.mouse.move(sidebarBox.x + sidebarBox.width / 2, sidebarBox.y + sidebarBox.height / 2); await page.mouse.wheel(0, 200);
  await settled(() => scrolls.evaluate(({sidebar}) => sidebar.viewportElement.scrollTop > 0), 'actual wheel scrolls the sidebar owner');
  assert.equal(await scrolls.evaluate(({main}) => main.viewportElement.scrollTop), 0, 'sidebar wheel leaves main scroll untouched');
  const sidebarScroll = await scrolls.evaluate(({sidebar}) => sidebar.viewportElement.scrollTop);
  const mainBox = await page.locator('#debug-main').boundingBox(); await page.mouse.move(mainBox.x + mainBox.width / 2, 400); await page.mouse.wheel(0, 200);
  await settled(() => scrolls.evaluate(({main}) => main.viewportElement.scrollTop > 0), 'actual wheel scrolls the main owner');
  assert.equal(await scrolls.evaluate(({sidebar}) => sidebar.viewportElement.scrollTop), sidebarScroll, 'main wheel leaves sidebar scroll untouched');
  await resizeExtreme(page, -1); await toggleBookmark(page, chain.at(-1)); await geometry(page, chain.at(-1)); await capture(page, 'minimum-1440');
  await resizeExtreme(page, 1); await assertSaved(page, chain.at(-1), true); await geometry(page, chain.at(-1)); await capture(page, 'maximum-1440');
  assert.equal(await rootNode.evaluate(el => el.isConnected), true, 'pane resize and independent scroll preserve the tree root');
  console.log('PASS: native wheel independence and real sidebar min/max drags preserve deep tree geometry.');
  await desktop.close();

  for (const width of [1440, 768, 390]) {
    const responsive = await context({viewport: {width, height: width === 390 ? 844 : 960}}); const page = await responsive.newPage(); activePage = page;
    await page.goto(base + href('/landing')); await ready(page, '/landing'); await showSidebar(page); await deep(page);
    await toggleBookmark(page, chain.at(-1)); await geometry(page, chain.at(-1)); await capture(page, 'light-' + width);
    await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'}); await assertSaved(page, chain.at(-1), true); await geometry(page, chain.at(-1)); await capture(page, 'dark-' + width);
    await responsive.close();
  }
  const coarseDesktop = await context({hasTouch: true}); const coarsePage = await coarseDesktop.newPage(); activePage = coarsePage;
  await coarsePage.goto(base + href('/landing')); await ready(coarsePage, '/landing'); await showSidebar(coarsePage); await loaded(coarsePage, '/');
  assert.equal(await coarsePage.evaluate(() => matchMedia('(pointer: coarse)').matches), true);
  for (const path of chain) await expand(coarsePage, path, 'touch');
  await resizeExtreme(coarsePage, -1); await geometry(coarsePage, chain.at(-1), true);
  await toggleBookmark(coarsePage, chain.at(-1), 'touch'); await geometry(coarsePage, chain.at(-1), true); await capture(coarsePage, 'touch-minimum-1440');
  await toggleBookmark(coarsePage, chain.at(-1), 'touch'); await coarseDesktop.close();
  const touch = await context({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce'}); const pageTouch = await touch.newPage(); activePage = pageTouch;
  await pageTouch.goto(base + href('/landing')); await ready(pageTouch, '/landing'); await showSidebar(pageTouch); await loaded(pageTouch, '/');
  for (const path of chain) await expand(pageTouch, path, 'touch');
  await toggleBookmark(pageTouch, chain.at(-1), 'touch'); await geometry(pageTouch, chain.at(-1), true); await capture(pageTouch, 'touch-390');
  await pageTouch.emulateMedia({colorScheme: 'dark'}); await geometry(pageTouch, chain.at(-1), true); await capture(pageTouch, 'touch-dark-390');
  await toggleBookmark(pageTouch, chain.at(-1), 'touch'); await touch.close();
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, liveReads: 0, protectedRuntimeReads: 0, fixtureReads: reads.length, gestures, screenshots}, null, 2));
} catch (error) {
  await activePage?.screenshot({path: '/private/tmp/shrine-namespace-tree-failure.png', animations: 'disabled'}).catch(() => {});
  console.error(JSON.stringify({reads: reads.map(({path}) => path), writes, unexpected, errors}, null, 2)); throw error;
} finally { await browser.close(); }
