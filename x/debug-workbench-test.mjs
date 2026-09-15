// Legacy disposable-runtime diagnostic; NOT the authoritative partition suite.
// Namespace GETs can append journal entries, even when POSTs are blocked. Never
// use this against a protected runtime. Pass14 updated selectors/source-value
// assertions without executing this script; x/debug-record-partition-test.mjs
// is the isolated fixture proof. Values below come from actual document bytes.
import assert from 'node:assert/strict';
assert.ok(process.env.DEBUG_URL, 'Set DEBUG_URL to an explicitly disposable runtime; this legacy script issues namespace GETs.');
const baseURL = new URL(process.env.DEBUG_URL);
assert.notEqual(baseURL.port, '8138', 'Port 8138 is protected; use a disposable runtime.');
assert.ok(baseURL.pathname === '/' && !baseURL.search && !baseURL.hash, 'DEBUG_URL must be a runtime origin.');
const base = baseURL.origin;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
// A fresh context has no installed workers. Playwright's serviceWorkers:block
// shim itself accesses navigator.serviceWorker inside sandboxed frames, which
// creates SecurityErrors unrelated to the passive renderer being tested.
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const writes = [];
const retiredReads = [];
const protectedReads = [];
const errors = [];
await context.route('**/*', async route => {
  const request = route.request();
  const url = new URL(request.url()), path = url.pathname;
  if (url.port === '8138') { protectedReads.push(request.url()); await route.abort(); return; }
  if (path === '/op' || path.startsWith('/op/') || !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
    writes.push(request.method() + ' ' + request.url());
    await route.abort();
    return;
  }
  if (/^\/(?:debug|ns)\/h(?:\/|$)/.test(path)) {
    retiredReads.push(request.url());
    await route.abort();
    return;
  }
  await route.continue();
});
await context.addInitScript(() => {
  window.__workbenchReads = [];
  document.addEventListener('debug:read-complete', event => window.__workbenchReads.push(event.detail));
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));

async function ready(path) {
  await page.waitForFunction(expected => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.readState === 'ready'
      && workspace.dataset.path === expected
      && workspace.getAttribute('aria-busy') !== 'true'
      && window.__workbenchReads.at(-1)?.path === expected;
  }, path, { timeout: 30000 });
}

const recordGroups = {
  fields: '#wb-canvas > sh-myth.wb-properties',
  constraints: '#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item.wb-constraints > sh-myth.wb-constraint-record',
  source: '#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item.wb-raw-details > sh-myth.wb-record',
};
const recordSelector = Object.values(recordGroups).join(', ');
const semanticKinds = new Set(['role', 'action', 'norm', 'sewn', 'template', 'module', 'event', 'behavior']);
async function setRecordGroupOpen(item, open) {
  await item.evaluate(element => element.updateComplete);
  const trigger = item.locator('button[part="trigger"]').first();
  if (await item.evaluate(element => element.open) !== open) await trigger.click();
  const element = await item.elementHandle();
  try {
    await page.waitForFunction(({element, open}) => {
      const trigger = element.shadowRoot?.querySelector('button[part=trigger]');
      const reveal = element.shadowRoot?.querySelector('ui-reveal[part=content]');
      const content = reveal?.shadowRoot?.querySelector('[part=content]');
      const measure = reveal?.shadowRoot?.querySelector('[part=measure]');
      if (element.open !== open || trigger?.getAttribute('aria-expanded') !== String(open) || !reveal || !content || !measure) return false;
      if (!open) return !reveal.matches(':state(active), :state(entering), :state(exiting)') && content.getBoundingClientRect().height === 0;
      return reveal.matches(':state(active)') && !reveal.matches(':state(entering)') &&
        content.getBoundingClientRect().height >= measure.getBoundingClientRect().height - .6;
    }, {element, open}, {timeout: 5000});
  } finally { await element.dispose(); }
}

async function assertCurrentDocument(response, path) {
  assert.equal(response.ok(), true, 'the inspected live document was read successfully');
  const expected = await page.evaluate(html => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const workspace = doc.querySelector('#debug-workspace');
    const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth');
    return {
      path: workspace.dataset.path,
      writable: workspace.dataset.writable,
      kind: workspace.dataset.kind || 'record',
      record: Boolean(myth),
      semantics: doc.querySelector('#debug-main section[aria-label=Semantics]')?.textContent.trim() || '',
      children: [...doc.querySelectorAll('#debug-children ui-tree-item[data-path]')]
        .map(item => item.dataset.path).filter(child => child !== workspace.dataset.path),
      slots: [...(myth?.querySelectorAll(':scope > sh-limb') || [])].map(limb => {
        const key = limb.querySelector(':scope > sh-slot')?.getAttribute('title');
        const pail = limb.querySelector(':scope > sh-pail')?.cloneNode(true);
        pail?.querySelectorAll('script, style, template, summary').forEach(node => node.remove());
        const text = pail?.textContent || '';
        const preserveWhitespace = limb.dataset.valueKind === 'text' ||
          ['/method', '/url', '/body', '/res_ctype', '/res_body'].includes(key);
        return [key, preserveWhitespace ? text : text.trim(), limb.dataset.valueKind || 'value'];
      }).filter(([key]) => key),
    };
  }, await response.text());
  await ready(path);
  assert.equal(expected.path, path);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), expected.writable);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), expected.kind);
  assert.equal(await page.locator('.wb-document-header').count(), 1, 'one header identifies the inspected namespace object');
  assert.equal(await page.locator('#wb-path-locator').getAttribute('data-path'), path);
  assert.equal(await page.locator('.wb-document-title').getAttribute('title'), path,
    'canonical identity remains in the locator and document title without repeating a subtitle');
  const semantics = page.locator('#wb-canvas > .wb-semantics');
  assert.equal(await semantics.count(), Number(Boolean(expected.semantics)));
  if (expected.semantics) assert.equal((await semantics.evaluate(element => {
    const copy = element.cloneNode(true);
    copy.querySelectorAll('.wb-implementation > summary').forEach(summary => summary.remove());
    return copy.textContent;
  })).trim(), expected.semantics,
    'the semantic view preserves actual server-decoded values');
  const record = page.locator(recordSelector);
  const grouped = {fields: [], constraints: [], source: []};
  for (const entry of expected.slots) {
    const [key, , kind] = entry;
    const group = key === '/sys/lash' ? 'constraints' :
      ['/sys/lede', '/sys/help'].includes(key) || (expected.semantics && semanticKinds.has(kind)) ? 'source' : 'fields';
    grouped[group].push(entry);
  }
  const groupCount = Object.values(grouped).filter(slots => slots.length).length || Number(expected.record);
  assert.equal(await record.count(), groupCount, 'only nonempty exclusive groups, or one genuinely empty record, are mounted');
  assert.equal(await page.locator('#wb-canvas details.wb-raw-details, #wb-canvas details.wb-constraints').count(), 0,
    'shared Mash accordion, not native summary selectors, owns secondary slot groups');
  if (expected.record) {
    const details = page.locator('#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item');
    for (const item of await details.all()) {
      assert.equal(await item.evaluate(element => element.open), false, 'secondary source/constraint slots start collapsed');
      await setRecordGroupOpen(item, true);
    }
    const keys = [];
    for (const [name, selector] of Object.entries(recordGroups)) {
      const group = page.locator(selector);
      assert.equal(await group.count(), Number(grouped[name].length > 0 || (name === 'fields' && !expected.slots.length)), name + ' has exactly its own slots');
      if (!await group.count()) continue;
      assert.equal(await group.getAttribute('data-path'), path);
      const actual = await group.locator(':scope > sh-limb.wb-slot-row').evaluateAll(rows => rows.map(row => {
        const value = row.querySelector('sh-pail[slot=value]');
        // Reference shortcuts, static provenance and byte-read statuses are
        // separate from the original server display, never replacements for it.
        const primary = value?.querySelector(':scope > pre, :scope > ui-scroll-area.wb-code-scroll > pre, :scope > a');
        return [row.querySelector('sh-slot[slot=label]')?.getAttribute('title'), primary?.textContent || ''];
      }));
      assert.deepEqual(actual, grouped[name].map(([key, text]) => [key, text === '' ? '""' : text]),
        name + ' preserves complete server display strings and original within-group order, with no frontend truncation allowance');
      keys.push(...actual.map(([key]) => key));
    }
    assert.deepEqual([...keys].sort(), expected.slots.map(([key]) => key).sort(), 'the group union includes every source slot exactly once');
    assert.equal(new Set(keys).size, keys.length, 'no key is duplicated between primary, constraints and source');
    for (const limb of await record.locator(':scope > sh-limb.wb-slot-row').all()) {
      assert.equal(await limb.locator('sh-slot[slot=label]').isVisible(), true, 'the namespace slot label is visible through the component slot');
      const value = limb.locator('sh-pail[slot=value]');
      if ((await value.textContent()).trim()) {
        assert.equal(await value.isVisible(), true, 'nonempty slot values are visible through the component slot');
      }
    }
    if (!expected.slots.length) assert.match(await record.innerText(), /no slots/i);
    for (const item of await details.all()) await setRecordGroupOpen(item, false);
  } else if (!expected.children.length && !expected.semantics) {
    assert.equal(await page.locator('#wb-canvas > .wb-empty').count(), 1, 'a structural name is not fabricated into a record');
  }
  const cards = page.locator('#wb-canvas sh-path-row [part="link"]');
  assert.equal(await cards.count(), expected.kind === 'journal' ? 0 : Math.min(expected.children.length, 60),
    'the overview shows real immediate child paths; the expandable hierarchy remains in the sidebar');
  const cardPaths = await cards.evaluateAll(links => links.map(link =>
    decodeURIComponent(new URL(link.href).pathname.replace(/^\/debug/, '') || '/')));
  assert.deepEqual(cardPaths, expected.kind === 'journal' ? [] : expected.children.slice(0, 60));
  assert.equal(await page.locator('#wb-canvas ui-tree-item').count(), 0);
  console.log('PASS: current document ' + path + ' matches ' + expected.slots.length + ' actual server slots.');
}

function nextLiveResponse(path) {
  const url = base + '/debug' + (path === '/' ? '' : path);
  return page.waitForResponse(response => response.url() === url && response.request().resourceType() === 'fetch');
}
async function go(path) {
  const response = nextLiveResponse(path);
  if (!await page.locator('#debug-go').isVisible())
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  const input = page.locator('#debug-go input');
  await input.fill(path);
  await input.press('Enter');
  await assertCurrentDocument(await response, path);
}
async function historyControl(id, path) {
  const response = nextLiveResponse(path);
  await page.locator(id).click();
  await assertCurrentDocument(await response, path);
}

try {
  const initial = await page.goto(base + '/debug/app');
  const initialHTML = await initial.text();
  await assertCurrentDocument(initial, '/app');
  assert.equal(await page.locator('#debug-back button').isDisabled(), true);
  assert.equal(await page.locator('#debug-forward button').isDisabled(), true);
  assert.equal(await page.locator('.debug-header #debug-go').count(), 1);
  assert.equal(await page.locator('#wb-version, #wb-history, #wb-history-care, #wb-case-input, #wb-pin, #wb-compare, .wb-scopes').count(), 0);
  assert.equal(await page.locator('#debug-refresh, #debug-sidebar > .debug-roots, .debug-locator').count(), 0);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-care'), null);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-case'), null);
  assert.equal(new URL(page.url()).search, '');

  // The current runtime intentionally may have an empty /hello and no operation
  // registry. Compare its actual document rather than assuming an old fixture.
  await go('/boot');
  await go('/hello');
  await historyControl('#debug-back', '/boot');
  assert.equal(await page.locator('#debug-forward button').isDisabled(), false);
  await historyControl('#debug-forward', '/hello');
  assert.equal(await page.locator('#debug-forward button').isDisabled(), true);
  await go('/app');
  console.log('PASS: address form and browser back/forward navigate live documents only.');

  // Inspect and Rendered are separate surfaces. Merely inspecting a path must
  // not load its face. The iframe is passive; interaction requires opening it.
  const frame = page.locator('#wb-rendered iframe');
  assert.equal(await frame.getAttribute('src'), null, 'a renderer is not loaded by inspection');
  assert.equal(await frame.getAttribute('sandbox'), '', 'the preview allows no scripts, forms, or same-origin privileges');
  assert.equal(await frame.getAttribute('referrerpolicy'), 'no-referrer');
  await page.locator('#wb-mode-rendered').click();
  assert.equal(await page.locator('#wb-canvas').isVisible(), false);
  assert.equal(await page.locator('#wb-rendered').isVisible(), true);
  assert.equal(await page.locator('.wb-document-header').isVisible(), true);
  assert.equal(await frame.getAttribute('src'), base + '/ns/app');
  assert.equal(new URL(page.url()).searchParams.get('view'), 'rendered');
  const openInterface = page.locator('.wb-render-open');
  assert.equal(await openInterface.getAttribute('target'), '_blank');
  assert.match(await openInterface.getAttribute('rel'), /noopener/);
  const renderedRefresh = nextLiveResponse('/app');
  await page.locator('#wb-refresh').click();
  assert.equal((await renderedRefresh).ok(), true);
  await ready('/app');
  assert.equal(await page.locator('#wb-mode-rendered').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('#wb-rendered').isVisible(), true);
  assert.equal(new URL(page.url()).searchParams.get('view'), 'rendered', 'refresh preserves the chosen mode');
  await go('/boot');
  const restoredRendered = nextLiveResponse('/app');
  await page.goBack();
  const restoredResponse = await restoredRendered;
  await ready('/app');
  assert.equal(await page.locator('#wb-rendered').isVisible(), true);
  assert.equal(new URL(page.url()).searchParams.get('view'), 'rendered', 'browser history restores the recorded view mode');
  await page.locator('#wb-mode-inspect').click();
  await assertCurrentDocument(restoredResponse, '/app');
  assert.equal(await page.locator('#wb-canvas').isVisible(), true);
  assert.equal(await page.locator('#wb-rendered').isVisible(), false);
  assert.equal(new URL(page.url()).search, '');
  console.log('PASS: renderer is lazy and fully sandboxed; refresh and browser history preserve its mode.');

  // Browser-only value fixture: no namespace state is created or modified.
  // Preserve actual whitespace and distinguish it from the empty string.
  const whitespacePath = '/__debug_whitespace_fixture__';
  const longLiteral = 'Beginning\n  ' + 'complete source '.repeat(1000) + '\nEnd';
  const whitespaceHTML = await page.evaluate(({html, path, longLiteral}) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const workspace = doc.querySelector('#debug-workspace');
    Object.assign(workspace.dataset, {path, kind: 'record', label: 'Whitespace fixture', description: '', renderUrl: '/ns/app'});
    doc.querySelector('#debug-children').replaceChildren();
    doc.querySelector('#debug-main section[aria-label=Semantics]').replaceChildren();
    doc.querySelector('#debug-main section[aria-label=Documentation]').replaceChildren();
    const myth = doc.querySelector('#debug-main section[aria-label=Record] > sh-myth');
    myth.replaceChildren();
    for (const [key, kind, text] of [
      ['/literal', 'text', ' \tmeaningful\n '],
      ['/blank', 'text', ' \n\t '],
      ['/empty', 'text', ''],
      ['/body', 'value', '\nHTTP body\n '],
      ['/long', 'text', longLiteral],
      ['/sys/lash', 'value', 'Test-only record constraint'],
    ]) {
      const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = kind;
      const slot = doc.createElement('sh-slot'); slot.slot = 'label'; slot.setAttribute('title', key);
      const value = doc.createElement('sh-pail'); value.slot = 'value'; value.textContent = text;
      limb.append(slot, value); myth.append(limb);
    }
    const operations = doc.querySelector('#debug-main section[aria-label=Operations]');
    const form = doc.createElement('form'); form.method = 'post'; form.action = '/op/fixture-never-submit';
    const control = doc.createElement('ui-button'); control.setAttribute('type', 'submit'); control.textContent = 'Do not submit';
    form.append(control); operations.replaceChildren(form);
    return doc.documentElement.outerHTML;
  }, {html: initialHTML, path: whitespacePath, longLiteral});
  await page.route('**/debug' + whitespacePath, route => route.fulfill({status: 200, contentType: 'text/html', body: whitespaceHTML}));
  await go(whitespacePath);
  const literalValues = await page.locator(recordGroups.fields).locator(':scope > sh-limb.wb-slot-row pre').allTextContents();
  assert.deepEqual(literalValues, [' \tmeaningful\n ', ' \n\t ', '""', '\nHTTP body\n ', longLiteral],
    'primary slots preserve all whitespace and a source value longer than 12,000 characters');
  assert.equal(await page.locator(recordGroups.source).count(), 0, 'an unrelated duplicate all-slots record is not fabricated');
  const constraints = page.locator('#wb-canvas > ui-accordion.wb-record-details > ui-accordion-item.wb-constraints');
  assert.equal(await constraints.evaluate(element => element.open), false, 'record constraints are secondary');
  assert.equal(await constraints.getAttribute('title'), 'Record constraints');
  await setRecordGroupOpen(constraints, true);
  assert.equal(await page.locator(recordGroups.constraints).locator('pre').textContent(), 'Test-only record constraint');
  assert.equal(await page.locator(recordSelector).locator(':scope > sh-limb.wb-slot-row[data-key="/sys/lash"]').count(), 1);
  await setRecordGroupOpen(constraints, false);
  await page.locator('#wb-operations-toggle').click();
  assert.equal(await page.locator('#wb-operations').isVisible(), true);
  await page.locator('#wb-mode-rendered').click();
  assert.equal(await page.locator('#wb-operations').isVisible(), false, 'operation panels are not part of passive rendering');
  assert.equal(await page.locator('#wb-operations-toggle').isVisible(), false);
  assert.equal(await page.locator('#wb-operations ui-button').evaluate(control => control.disabled), true);
  const fixtureRefresh = nextLiveResponse(whitespacePath);
  await page.locator('#wb-refresh').click();
  assert.equal((await fixtureRefresh).ok(), true);
  await ready(whitespacePath);
  assert.equal(await page.locator('#wb-rendered').isVisible(), true);
  assert.equal(await page.locator('#wb-operations ui-button').evaluate(control => control.disabled), true,
    'refresh cannot re-enable operations in passive mode');
  await go('/app');
  await page.unroute('**/debug' + whitespacePath);
  console.log('PASS: whitespace, empty values, and operation isolation remain correct in browser-only fixtures.');

  // The inspector is optional; namespace activity is the real event journal.
  assert.equal(await page.locator('#debug-workspace').getAttribute('inspector-open'), null);
  await page.locator('#debug-inspector-toggle').click();
  assert.equal(await page.locator('#debug-workspace [slot=inspector]').isVisible(), true);
  assert.equal(await page.locator('.wb-inspector-path').textContent(), 'Details');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-inspector-path'), '/app');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/app');
  assert.equal(await page.locator('ui-table[label=version], #debug-inspector-path').count(), 0);
  await page.locator('#debug-inspector-toggle').click();
  assert.equal(await page.locator('#debug-workspace').getAttribute('inspector-open'), null);
  assert.equal(await page.locator('.debug-footer').isVisible(), false);
  await go('/log');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'journal');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), 'false');
  assert.equal(await page.locator('.debug-footer').isVisible(), false);
  assert.equal(await page.locator('.debug-events').count() > 0, true);
  assert.equal(await page.locator('.debug-event').count() > 0, true);
  const eventTarget = await page.locator('.debug-event').first().getAttribute('data-reference');
  assert.match(eventTarget, /^\/log\/[^/]+$/);
  const eventResponse = nextLiveResponse(eventTarget);
  await page.locator('.debug-event').first().click();
  await assertCurrentDocument(await eventResponse, eventTarget);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'event');
  assert.match(await page.locator('.wb-semantics').textContent(), /Task/);
  await go('/gov/srs/card');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'role');
  assert.equal(await page.locator('.debug-schema-field').count() > 0, true);
  assert.equal(await page.locator('#wb-canvas ui-accordion-item.wb-raw-details').evaluate(element => element.open), false);
  await go('/app');
  console.log('PASS: namespace journal, decoded event facts, and real Grove role slots are inspectable.');

  // A failed live read keeps the previous record and reports the failure.
  const failurePath = '/__debug_read_failure_fixture__';
  const beforeFailureFields = await page.locator(recordSelector).evaluateAll(records => records.map(record => ({path: record.dataset.path,
    keys: [...record.querySelectorAll(':scope > sh-limb')].map(limb => limb.dataset.key)})));
  await page.route('**/debug' + failurePath, route => route.fulfill({ status: 503, body: 'Browser-only read failure fixture.' }));
  await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  await page.locator('#debug-go input').fill(failurePath);
  await page.locator('#debug-go input').press('Enter');
  await page.waitForFunction(() => document.querySelector('#debug-status').textContent.includes('Navigation failed'));
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/app');
  assert.deepEqual(await page.locator(recordSelector).evaluateAll(records => records.map(record => ({path: record.dataset.path,
    keys: [...record.querySelectorAll(':scope > sh-limb')].map(limb => limb.dataset.key)}))), beforeFailureFields,
    'a failed read preserves every existing slot group, not only a former raw duplicate');
  assert.equal(await page.locator('#wb-feedback[data-failed=true]').isVisible(), true);
  await page.unroute('**/debug' + failurePath);
  await page.getByRole('button', { name: 'Dismiss notification', exact: true }).click();
  await page.locator('#debug-go input').fill('/app');
  for (const missing of ['main', 'inspector']) {
    const malformedPath = '/__debug_missing_' + missing + '_fixture__';
    const body = '<sh-triptych id="debug-workspace" data-path="' + malformedPath + '" data-writable="true">' +
      (missing === 'main' ? '<div slot="inspector"></div>' : '<div id="debug-main"></div>') + '</sh-triptych>';
    await page.route('**/debug' + malformedPath, route => route.fulfill({status: 200, contentType: 'text/html', body}));
    const before = await page.locator('#wb-canvas').innerHTML();
    const malformedResponse = nextLiveResponse(malformedPath);
    await page.locator('#debug-go input').fill(malformedPath);
    await page.locator('#debug-go input').press('Enter');
    assert.equal((await malformedResponse).ok(), true, 'the malformed fixture deliberately returns HTTP 200');
    await page.waitForFunction(() => document.querySelector('#debug-workspace').getAttribute('aria-busy') === 'false'
      && document.querySelector('#debug-status').textContent.includes('requested debug workspace'));
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/app');
    assert.equal(await page.locator('#wb-canvas').innerHTML(), before, 'malformed content is rejected before replacing the current view');
    assert.equal(new URL(page.url()).pathname, '/debug/app');
    await page.unroute('**/debug' + malformedPath);
    await page.getByRole('button', { name: 'Dismiss notification', exact: true }).click();
  }
  await page.locator('#debug-go input').fill('/app');
  console.log('PASS: inspector and failed-read feedback preserve the current live record.');

  // Every app glyph is realized by Mash, with no per-app sources or SVG drawings.
  assert.equal(await page.locator('svg.wb-icon, ui-icon[name^="shrine."]').count(), 0);
  assert.equal(await page.locator('.wb-icon').count() > 0, true);
  await page.waitForFunction(() => [...document.querySelectorAll('.wb-icon')].every(icon =>
    icon.localName === 'ui-icon' && icon.dataset.iconSource === 'Mash'
    && globalThis.Mash.hasIcon(icon.getAttribute('name'))
    && icon.shadowRoot?.querySelector('svg[part=source]')));
  for (const control of await page.locator('ui-button').all()) {
    if (!await control.isVisible()) continue;
    assert.match(await control.ariaSnapshot(), /button "[^"\n]+"/, 'visible icon-only buttons have accessible names');
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  if (process.env.DEBUG_DESKTOP_SCREENSHOT) await page.screenshot({ path: process.env.DEBUG_DESKTOP_SCREENSHOT, animations: 'disabled' });

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.reload();
  await assertCurrentDocument(mobile, '/app');
  assert.equal(await page.locator('#wb-canvas').isVisible(), true);
  assert.equal(await page.locator('#debug-back').isVisible(), true);
  assert.equal(await page.locator('#debug-forward').isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.locator('#wb-canvas').click({ position: { x: 8, y: 8 } });
  await page.keyboard.press('/');
  assert.equal(await page.locator('#debug-go input').evaluate(input => input.matches(':focus')), true);
  await page.keyboard.press('Meta+k');
  assert.equal(await page.locator('#debug-filter-composer').isVisible(), true);
  assert.equal(await page.locator('#debug-filter input').evaluate(input => input.matches(':focus')), true);
  assert.equal(await page.locator('#debug-go').isVisible(), true, 'the address remains available when the mobile sidebar is open');
  assert.equal(await page.locator('#debug-back').isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  if (process.env.DEBUG_MOBILE_SCREENSHOT) await page.screenshot({ path: process.env.DEBUG_MOBILE_SCREENSHOT, animations: 'disabled' });

  assert.deepEqual(writes, [], 'no operation or write request escaped the test guard');
  assert.deepEqual(retiredReads, [], 'no history/case endpoint is requested');
  assert.deepEqual(protectedReads, [], 'no request targets protected port 8138');
  assert.deepEqual(errors, []);
  console.log('PASS: server display fidelity, exclusive slot groups, semantic objects, namespace activity, isolated rendering, navigation failures, Mash icons, keyboard and mobile layout. No client write or historical-endpoint requests; namespace GETs may journal.');
} catch (error) {
  console.error('Workbench failure context:', await page.evaluate(() => ({
    url: location.href,
    state: { ...document.querySelector('#debug-workspace')?.dataset },
    lastRead: window.__workbenchReads?.at(-1)?.path,
    status: document.querySelector('#debug-status')?.textContent,
  })), errors);
  if (process.env.DEBUG_FAILURE_SCREENSHOT) await page.screenshot({ path: process.env.DEBUG_FAILURE_SCREENSHOT, animations: 'disabled' });
  throw error;
} finally {
  await browser.close();
}
