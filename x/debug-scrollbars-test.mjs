// Legacy disposable-runtime scrollbar diagnostic, not an isolated fixture suite.
// Long filler is browser-local, but namespace GETs can still append journal
// entries. Pass14 adapted slot-group selectors without executing this script;
// x/debug-record-partition-test.mjs is the authoritative isolated partition proof.
import assert from 'node:assert/strict';

assert.ok(process.env.DEBUG_URL, 'Set DEBUG_URL to an explicitly disposable runtime; this legacy script issues namespace GETs.');
const baseURL = new URL(process.env.DEBUG_URL);
assert.notEqual(baseURL.port, '8138', 'Port 8138 is protected; use a disposable runtime.');
assert.ok(baseURL.pathname === '/' && !baseURL.search && !baseURL.hash, 'DEBUG_URL must be a runtime origin.');
const base = baseURL.origin;
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 900}});
const writes = [], errors = [], protectedReads = [];
await context.route('**/*', async route => {
  if (new URL(route.request().url()).port === '8138') { protectedReads.push(route.request().url()); return route.abort(); }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
    writes.push(route.request().url());
    return route.abort();
  }
  return route.continue();
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
const owners = {
  sidebar: '#debug-sidebar ui-scroll-area[part="body"]',
  main: '#debug-workspace ui-scroll-area[part="main-body"]',
  inspector: '#debug-workspace ui-scroll-area[part="inspector-body"]',
};
const recordGroups = {
  fields: '#wb-canvas > sh-myth.wb-properties',
  constraints: '#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item.wb-constraints > sh-myth.wb-constraint-record',
  source: '#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item.wb-raw-details > sh-myth.wb-record',
};
const recordSelector = Object.values(recordGroups).join(', ');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let attempt = 0; attempt < 80; attempt++) {
    if (await check()) return;
    await sleep(50);
  }
  assert.fail(message);
}
const top = viewport => viewport.evaluate(el => el.scrollTop);
const css = (locator, property) => locator.evaluate((el, property) => getComputedStyle(el)[property], property);
async function scrollSettled(viewport) {
  let previous = await top(viewport), stable = 0;
  for (let attempt = 0; attempt < 80; attempt++) {
    await sleep(50);
    const current = await top(viewport);
    stable = current === previous ? stable + 1 : 0;
    if (stable >= 4) return current;
    previous = current;
  }
  assert.fail('native keyboard scrolling settles without a perpetual animation');
}
async function overflowingFixtures(targetPage) {
  await targetPage.evaluate(() => {
    for (const selector of ['#debug-sidebar-sections', '#wb-canvas', '.wb-inspector']) {
      const parent = document.querySelector(selector);
      if (!parent) continue;
      const section = document.createElement('section');
      section.dataset.scrollbarFixture = '';
      section.setAttribute('aria-label', 'Browser-only scrollbar regression fixture');
      for (let row = 0; row < 120; row++) {
        const line = document.createElement('div');
        line.style.cssText = 'min-height:24px;padding:4px 8px';
        line.textContent = 'Namespace fixture ' + (row + 1);
        section.append(line);
      }
      parent.append(section);
    }
  });
}
async function openRecordGroups() {
  for (const item of await page.locator('#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item').all()) {
    await item.evaluate(element => element.updateComplete);
    if (!await item.evaluate(element => element.open)) await item.locator('button[part="trigger"]').first().click();
    await settled(() => item.evaluate(element => {
      const trigger = element.shadowRoot?.querySelector('button[part=trigger]');
      const reveal = element.shadowRoot?.querySelector('ui-reveal[part=content]');
      const content = reveal?.shadowRoot?.querySelector('[part=content]');
      const measure = reveal?.shadowRoot?.querySelector('[part=measure]');
      return element.open && trigger?.getAttribute('aria-expanded') === 'true' && reveal?.matches(':state(active)') &&
        !reveal.matches(':state(entering)') && content && measure &&
        content.getBoundingClientRect().height >= measure.getBoundingClientRect().height - .6;
    }), 'native record disclosure and its full content settle before scrollbar measurements');
  }
}

try {
  await page.goto(base + '/debug/app');
  await page.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  await page.locator('.wb-inspector').waitFor();
  await overflowingFixtures(page);

  for (const [name, selector] of Object.entries(owners)) {
    const area = page.locator(selector);
    const viewport = area.locator('[part="viewport"]');
    const bar = area.locator('[part="block-scrollbar"]');
    const track = area.locator('[part="block-track"]');
    const thumb = area.locator('[part="block-thumb"]');
    await settled(() => viewport.evaluate(el => el.scrollHeight > el.clientHeight + 500), name + ' remains a bounded native viewport');
    assert.equal(await css(viewport, 'overflowY'), 'auto', name + ' preserves native scrolling');
    assert.equal(await css(viewport, 'scrollbarWidth'), 'none', name + ' has no duplicate OS scrollbar');
    assert.equal(await css(bar, 'position'), 'absolute', name + ' uses the Mash overlay recipe');
    assert.equal(await area.getAttribute('mode'), 'hover');
    assert.equal(await bar.getAttribute('role'), 'scrollbar');
    assert.equal(await bar.getAttribute('aria-controls'), await viewport.getAttribute('id'));

    await viewport.hover({position: {x: 32, y: 64}});
    await settled(async () => Number(await css(bar, 'opacity')) > .99, name + ' reveals its scrollbar on hover');
    assert.equal(await css(bar, 'pointerEvents'), 'auto');
    assert.ok(parseFloat(await css(thumb, 'width')) >= 4, name + ' thumb is painted');
    assert.notEqual(await css(thumb, 'backgroundColor'), 'rgba(0, 0, 0, 0)');

    await bar.focus();
    await bar.press('Home');
    await settled(async () => await top(viewport) === 0, name + ' scrollbar Home works');
    await bar.press('End');
    await settled(() => viewport.evaluate(el => Math.abs(el.scrollTop - (el.scrollHeight - el.clientHeight)) < 2), name + ' scrollbar End reaches all content');
    await bar.press('ArrowUp');
    await settled(() => viewport.evaluate(el => el.scrollTop < el.scrollHeight - el.clientHeight - 10), name + ' scrollbar ArrowUp works');
    await bar.press('Home');

    const bounds = await thumb.boundingBox();
    const trackBounds = await track.boundingBox();
    assert.ok(bounds && trackBounds && trackBounds.height > 0, name + ' has usable scrollbar geometry');
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + Math.min(bounds.height / 2, 12));
    await page.mouse.down();
    await page.mouse.move(bounds.x - 24, bounds.y + Math.min(trackBounds.height / 2, 220), {steps: 8});
    await settled(async () => await top(viewport) > 100, name + ' thumb drag scrolls the native viewport outside the rail');
    assert.equal(await area.evaluate(el => el.matches(':state(dragging)')), true);
    await page.mouse.up();
    assert.equal(await area.evaluate(el => el.matches(':state(dragging)')), false);

    await bar.press('Home');
    await track.click({position: {x: trackBounds.width / 2, y: trackBounds.height * .75}});
    await settled(async () => await top(viewport) > 100, name + ' track click works');
    await viewport.focus();
    await viewport.press('Home');
    await settled(async () => await top(viewport) === 0, name + ' viewport Home remains native');
    await scrollSettled(viewport);
    await viewport.press('PageDown');
    await settled(async () => await top(viewport) > 100, name + ' viewport keyboard scrolling remains native');
    await scrollSettled(viewport);
    console.log('PASS: ' + name + ' Mash scrollbar hover, native overflow, keyboard, track click, and captured drag.');
  }

  const main = page.locator(owners.main), mainViewport = main.locator('[part="viewport"]');
  const mainBar = main.locator('[part="block-scrollbar"]');
  const sidebarTop = await top(page.locator(owners.sidebar).locator('[part="viewport"]'));
  const inspectorTop = await top(page.locator(owners.inspector).locator('[part="viewport"]'));
  const mainTop = await top(mainViewport);
  await mainViewport.hover({position: {x: 80, y: 100}});
  await page.mouse.wheel(0, 360);
  await settled(async () => await top(mainViewport) > mainTop + 100, 'wheel movement scrolls only its native viewport');
  await settled(() => main.evaluate(el => el.matches(':state(active)')), 'wheel activity exposes the shared Mash activity state');
  await scrollSettled(mainViewport);
  assert.equal(await top(page.locator(owners.sidebar).locator('[part="viewport"]')), sidebarTop);
  assert.equal(await top(page.locator(owners.inspector).locator('[part="viewport"]')), inspectorTop);
  await page.screenshot({path: '/private/tmp/shrine-mash-scrollbars.png'});
  await page.locator('#debug-inspector-toggle').focus();
  await page.mouse.move(5, 5);
  await settled(async () => Number(await css(mainBar, 'opacity')) < .01, 'scrollbar rests quietly after hover, focus and activity end');
  console.log('PASS: independent panes, wheel activity, quiet idle state.');

  await page.emulateMedia({forcedColors: 'active'});
  for (const selector of Object.values(owners)) {
    const area = page.locator(selector);
    assert.equal(await css(area.locator('[part="viewport"]'), 'scrollbarWidth'), 'auto');
    assert.equal(await css(area.locator('[part="block-scrollbar"]'), 'display'), 'none');
  }
  await page.emulateMedia({forcedColors: 'none', reducedMotion: 'reduce'});
  assert.equal(await css(mainBar, 'transitionDuration'), '0s');
  console.log('PASS: forced-colors native fallback and reduced-motion support.');

  const source = await page.goto(base + '/debug');
  assert.equal(source.ok(), true, 'the disposable root document was read successfully');
  const expected = await page.evaluate(html => {
    const document = new DOMParser().parseFromString(html, 'text/html');
    const slots = [...document.querySelectorAll('#debug-main > section[aria-label=Record] > sh-myth > sh-limb')].map(limb => {
      const key = limb.querySelector(':scope > sh-slot')?.getAttribute('title');
      const pail = limb.querySelector(':scope > sh-pail').cloneNode(true);
      pail.querySelectorAll('script, style, template, summary').forEach(node => node.remove());
      const preserveWhitespace = limb.dataset.valueKind === 'text' || ['/method', '/url', '/body', '/res_ctype', '/res_body'].includes(key);
      return {key, kind: limb.dataset.valueKind || 'value', text: preserveWhitespace ? pail.textContent : pail.textContent.trim()};
    });
    return {slots, semantics: Boolean(document.querySelector('#debug-main section[aria-label=Semantics]')?.textContent.trim())};
  }, await source.text());
  await page.waitForFunction(() => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.path === '/' && workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true';
  }, null, {timeout: 5000});
  assert.ok(expected.slots.some(slot => slot.key === '/pact'), 'this legacy diagnostic requires a disposable root containing /pact');
  const expectedPact = expected.slots.find(slot => slot.key === '/pact').text;
  const groups = {fields: [], constraints: [], source: []};
  const semanticKinds = new Set(['role', 'action', 'norm', 'sewn', 'template', 'module', 'event', 'behavior']);
  for (const slot of expected.slots) {
    const group = slot.key === '/sys/lash' ? 'constraints' : ['/sys/lede', '/sys/help'].includes(slot.key) ||
      (expected.semantics && semanticKinds.has(slot.kind)) ? 'source' : 'fields';
    groups[group].push(slot);
  }
  assert.equal(await page.locator('#wb-canvas details.wb-raw-details, #wb-canvas details.wb-constraints').count(), 0);
  await openRecordGroups();
  const keys = [];
  for (const [name, selector] of Object.entries(recordGroups)) {
    const records = page.locator(selector);
    assert.equal(await records.count(), Number(groups[name].length > 0), name + ' group exists only for its own values');
    const actual = await records.locator(':scope > sh-limb.wb-slot-row').evaluateAll(rows => rows.map(row => {
      const pail = row.querySelector(':scope > sh-pail');
      const primary = pail.querySelector(':scope > pre, :scope > ui-scroll-area.wb-code-scroll > pre, :scope > a');
      return [row.dataset.key, primary?.textContent || ''];
    }));
    assert.deepEqual(actual, groups[name].map(slot => [slot.key, slot.text === '' ? '""' : slot.text]),
      name + ' retains every complete server display string, with no frontend truncation allowance');
    keys.push(...actual.map(([key]) => key));
  }
  assert.deepEqual([...keys].sort(), expected.slots.map(slot => slot.key).sort(), 'exclusive groups preserve the complete source-key union');
  assert.equal(new Set(keys).size, keys.length, 'no duplicated primary/source/constraint slots');
  // Constrain the document with its peer pane. Only actual overflow should
  // trigger enhancement; no value length or copied-string cutoff is assumed.
  await page.setViewportSize({width: 1000, height: 900});
  if (!await page.locator('#debug-workspace').evaluate(element => element.inspectorOpen))
    await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  const pact = page.locator(recordSelector).locator(':scope > sh-limb.wb-slot-row[data-key="/pact"]');
  assert.equal(await pact.count(), 1, 'the real pact slot is mounted once, in its own group');
  const codeArea = pact.locator('ui-scroll-area.wb-code-scroll');
  await codeArea.waitFor({timeout: 5000});
  assert.equal(await codeArea.locator('pre').textContent(), expectedPact, 'the full received pact display remains unchanged; this is not a claim about backend serialization fidelity');
  const codeViewport = codeArea.locator('[part="viewport"]');
  const codeBar = codeArea.locator('[part="block-scrollbar"]');
  await settled(() => codeViewport.evaluate(el => el.scrollHeight > el.clientHeight + 10), 'the long real slot has a bounded Mash viewport');
  assert.ok(await codeViewport.evaluate(el => el.clientHeight <= 18 * parseFloat(getComputedStyle(document.documentElement).fontSize) + 1));
  assert.equal(await css(codeViewport, 'scrollbarWidth'), 'none');
  assert.equal(await css(codeArea.locator('pre'), 'overflowY'), 'visible', 'the original pre no longer owns a second scrollbar');
  await codeArea.hover();
  await settled(async () => Number(await css(codeBar, 'opacity')) > .99, 'the value uses Mash quiet hover controls');
  await codeBar.press('End');
  await settled(() => codeViewport.evaluate(el => Math.abs(el.scrollTop - (el.scrollHeight - el.clientHeight)) < 2), 'the entire real value remains reachable by keyboard');
  const tiny = page.locator(recordSelector).locator(':scope > sh-limb.wb-slot-row[data-key="/grants/fetch"]');
  assert.equal(await tiny.count(), 1, 'the tiny scalar is present exactly once');
  assert.equal(await tiny.locator('ui-scroll-area').count(), 0, 'a tiny scalar adds no scroll component or tab stop');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({path: '/private/tmp/shrine-mash-long-value.png'});
  await page.emulateMedia({forcedColors: 'active'});
  assert.equal(await css(codeViewport, 'scrollbarWidth'), 'auto');
  assert.equal(await css(codeBar, 'display'), 'none');
  await page.emulateMedia({forcedColors: 'none'});
  console.log('PASS: long pact display uses Mash, preserves all received text, stays within 18rem, and remains keyboard reachable; tiny values stay plain.');

  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
  await touchContext.route('**/*', route => {
    if (new URL(route.request().url()).port === '8138') { protectedReads.push(route.request().url()); return route.abort(); }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) { writes.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const touch = await touchContext.newPage();
  touch.on('pageerror', error => errors.push(error.message));
  await touch.goto(base + '/debug/app');
  await touch.waitForFunction(() => document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
  await overflowingFixtures(touch);
  assert.equal(await touch.evaluate(() => matchMedia('(hover: none) and (pointer: coarse)').matches), true);
  const touchArea = touch.locator(owners.main);
  assert.equal(await css(touchArea.locator('[part="viewport"]'), 'scrollbarWidth'), 'auto');
  assert.equal(await css(touchArea.locator('[part="block-scrollbar"]'), 'display'), 'none');
  assert.ok(await touch.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await touchContext.close();
  assert.deepEqual(writes, []);
  assert.deepEqual(protectedReads, [], 'no request targets protected port 8138');
  assert.deepEqual(errors, []);
  console.log('PASS: touch platform scrolling, responsive width, zero client write requests and page errors; namespace GETs may journal.');
} catch (error) {
  console.error(await page.evaluate(() => {
    const collect = root => [...root.querySelectorAll('*')].flatMap(el => [
      ...(el.matches('ui-scroll-area') ? [{label: el.label, host: el.getBoundingClientRect().toJSON(), viewport: {height: el.viewportElement.clientHeight, top: el.viewportElement.scrollTop, scrollHeight: el.viewportElement.scrollHeight, focused: el.shadowRoot.activeElement === el.viewportElement}}] : []),
      ...(el.shadowRoot ? collect(el.shadowRoot) : []),
    ]);
    return collect(document);
  }));
  await page.screenshot({path: '/private/tmp/shrine-mash-scrollbars-failure.png'});
  throw error;
} finally {
  await browser.close();
}
