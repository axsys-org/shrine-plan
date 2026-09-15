// Exclusive record groups over test-owned data and a mandatory saved shell.
// No live namespace read, operation, browser state or runtime fallback exists.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live namespace access is forbidden');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-record-partition-fixture.invalid';
const epoch = '9007199254741999';
const exact = '  \n' + 'Exact bytes, not inferred completeness.\n'.repeat(140) + 'TAIL\n  ';
const payload = new TextEncoder().encode(exact);
assert.ok(payload.length > 4096 && payload.length < 8192);
const valueURL = '/debug-read/value?path=%2Fmixed&slot=%2Fbody&epoch=' + epoch + '&offset=0&limit=65536';
const sourceValueURL = valueURL.replace('slot=%2Fbody', 'slot=%2Fsys%2Fhelp');
const whitespace = '  leading \n\tindented line\ntrailing  \n  ';
const meta = name => [{key: '/sys/lede', text: 'Authored ' + name + ' title'},
  {key: '/sys/help', text: '  Authored help for ' + name + '.\n  Exact source whitespace.  '}];
const definitions = {
  '/': {fields: [{key: '/root', text: 'Test-owned fixture root'}]},
  '/uniform': {fields: [...meta('uniform'), {key: '/body', text: whitespace},
    {key: '/definition', text: '/definition', reference: '/definition'}, {key: '/count', text: '4'},
    {key: '/sys/lash', text: 'Authored constraint fixture'}]},
  '/semantic': {semantics: true, kind: 'role', fields: [...meta('semantic'),
    {key: '/role', text: 'Raw authored role payload', kind: 'role'},
    {key: '/action', text: 'Raw authored action payload', kind: 'action'},
    {key: '/body', text: whitespace}, {key: '/future', text: 'Unknown kinds remain ordinary slots', kind: 'future-kind'},
    {key: '/sys/lash', text: 'Role constraint stays distinct'}]},
  '/definition': {semantics: true, kind: 'role', fields: [...meta('definition'),
    {key: '/role', text: 'Definition role raw value', kind: 'role'},
    {key: '/behavior', text: 'Definition behavior raw value', kind: 'behavior'},
    {key: '/body', text: whitespace}, {key: '/sys/lash', text: 'Definition constraint'}]},
  '/mixed': {fields: [...meta('mixed').map(field => field.key === '/sys/help' ? {...field, text: exact.slice(0, 48),
    state: 'preview', reason: 'byte-limit', bytes: String(payload.length), previewBytes: '48', epoch,
    representation: 'utf8-bytes', url: sourceValueURL} : field),
    {key: '/complete', text: 'Complete value', state: 'complete', bytes: '14', previewBytes: '14', epoch, representation: 'utf8-bytes'},
    {key: '/body', text: exact.slice(0, 48), state: 'preview', reason: 'byte-limit', bytes: String(payload.length),
      previewBytes: '48', epoch, representation: 'utf8-bytes', url: valueURL},
    {key: '/opaque', text: 'Opaque authored summary', state: 'opaque', reason: 'semantic-summary'},
    {key: '/unknown', text: 'Authored … is not proof of truncation'},
    {key: '/invalid', text: 'Invalid metadata stays unknown', state: 'preview', reason: 'byte-limit', bytes: '20',
      previewBytes: '5', epoch, representation: 'utf8-bytes', url: 'javascript:window.__partitionExecuted=true'},
    {key: '/sys/lash', text: 'Mixed constraint'}]},
  '/invalid-only': {fields: [{key: '/legacy', text: whitespace},
    {key: '/invalid', text: 'Untrusted metadata', state: 'complete', bytes: '01', previewBytes: '1', epoch, representation: 'utf8-bytes'}]},
  '/single': {fields: [{key: '/single', text: whitespace}]},
  '/empty': {fields: []},
};
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const byteFixtures = new Map(['/body', '/sys/help'].flatMap(slot => [0, 4096].map(start => {
  const offset = Math.max(0, start - 3), end = Math.min(payload.length, start + 4096 + 3);
  const url = new URL(slot === '/body' ? valueURL : sourceValueURL, base); url.searchParams.set('offset', String(offset)); url.searchParams.set('limit', String(end - offset));
  return [url.pathname + url.search, {version: 1, path: '/mixed', slot, epoch, recordEpoch: epoch,
    type: 'text', representation: 'utf8-bytes', encoding: 'hex', total: String(payload.length), offset: String(offset),
    next: end < payload.length ? String(end) : null, complete: end === payload.length,
    hex: Buffer.from(payload.slice(offset, end)).toString('hex')}];
})));
const reads = [], valueReads = [], writes = [], unexpected = [], errors = [], screenshots = [];
let heldByte = null;
async function bounded(promise, label) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(label + ' did not settle within5000ms')), 5000); })]); }
  finally { clearTimeout(timer); }
}
let activePage;
const browser = await chromium.launch();
try {
  let fixtures;
  const author = await browser.newContext({serviceWorkers: 'block'});
  try {
    await author.route('**/*', route => { unexpected.push('Author request: ' + route.request().url()); return route.abort(); });
    const page = await author.newPage();
    fixtures = Object.freeze(await page.evaluate(({shell, definitions}) => {
      const original = new DOMParser().parseFromString(shell, 'text/html');
      if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell lacks the expected server record anatomy');
      return Object.fromEntries(Object.entries(definitions).map(([path, fixture]) => {
        const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
        const label = fixture.fields.find(field => field.key === '/sys/lede')?.text || path.split('/').at(-1) || 'Namespace';
        Object.assign(workspace.dataset, {path, kind: fixture.kind || 'record', writable: 'false', label,
          description: '', descriptionSource: '/sys/help', fixture: 'record-partition', renderUrl: '/ns' + path});
        for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
        const record = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); record.replaceChildren();
        for (const field of fixture.fields) {
          const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = field.kind || 'text';
          if (field.reference) limb.dataset.reference = field.reference;
          if (field.state) Object.assign(limb.dataset, {valueState: field.state, previewReason: field.reason || '',
            valueBytes: field.bytes || '', valuePreviewBytes: field.previewBytes || '', valueEpoch: field.epoch || '',
            valueRepresentation: field.representation || '', valueUrl: field.url || ''});
          const key = doc.createElement('sh-slot'); key.setAttribute('title', field.key);
          const value = doc.createElement('sh-pail');
          if (field.reference) { const anchor = doc.createElement('a'); anchor.href = '/ns' + field.reference; anchor.textContent = field.text; value.append(anchor); }
          else value.textContent = field.text;
          limb.append(key, value); record.append(limb);
        }
        for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
        if (fixture.semantics) {
          const section = doc.querySelector('#debug-main section[aria-label=Semantics]');
          const prose = doc.createElement('p'); prose.textContent = 'Test-owned semantic presentation; exact source slots remain separately accessible.';
          section.append(prose);
        }
        doc.querySelector('#debug-children').replaceChildren();
        doc.querySelector('#debug-workspace [slot=inspector]')?.replaceChildren();
        doc.querySelector('#debug-activity')?.replaceChildren();
        doc.querySelector('#debug-go ui-input')?.setAttribute('value', path);
        doc.title = 'Test-owned record partition · ' + path;
        const url = '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
        return [url, '<!doctype html>' + doc.documentElement.outerHTML];
      }));
    }, {shell, definitions}));
  } finally { await author.close(); }

  async function createContext(options = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, serviceWorkers: 'block', ...options});
    context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    await context.addInitScript(({base}) => {
      if (location.origin !== base || sessionStorage.getItem('record-partition-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: false, root: '/', expanded: []}));
      sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: ['/uniform'], pages: [null], cursor: 0}));
      sessionStorage.setItem('record-partition-fixture', 'seeded');
    }, {base});
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET') { writes.push(request.method() + ' ' + request.url()); return route.abort(); }
      if (url.origin !== base) { unexpected.push(request.url()); return route.abort(); }
      const bytes = byteFixtures.get(url.pathname + url.search);
      if (bytes) {
        valueReads.push(url.pathname + url.search);
        const gate = heldByte?.slot === bytes.slot ? heldByte : null;
        if (gate) { gate.started(); await gate.released; }
        try { return await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(bytes)}); }
        catch (error) { if (!gate) throw error; }
        finally { gate?.finished(); }
        return;
      }
      if (url.search) { unexpected.push(request.url()); return route.abort(); }
      if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (!Object.hasOwn(fixtures, url.pathname)) { unexpected.push(request.url()); return route.abort(); }
      reads.push(url.pathname); return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[url.pathname]});
    });
    return context;
  }
  async function ready(page, path) {
    await page.waitForFunction(path => { const workspace = document.querySelector('#debug-workspace'); return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true'; }, path, {timeout: 5000});
  }
  async function go(page, path) {
    if (!await page.locator('#debug-go').isVisible()) await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
    await page.locator('#debug-go input').fill(path); await page.locator('#debug-go input').press('Enter'); await ready(page, path);
  }
  const scope = page => page.locator('#wb-canvas');
  const rawRows = root => root.locator('sh-myth.wb-record-body > sh-limb.wb-slot-row');
  const field = (root, key) => root.locator('sh-limb.wb-slot-row[data-key=' + JSON.stringify(key) + ']');
  const value = (root, key) => field(root, key).locator(':scope > sh-pail');
  async function openDetails(root) {
    for (const item of await root.locator('ui-accordion.wb-record-details > ui-accordion-item').all()) {
      if (!await item.evaluate(element => element.open)) await item.getByRole('button').first().click();
      await item.evaluate(element => element.updateComplete);
      assert.equal(await item.evaluate(element => element.open), true);
    }
  }
  function expectedGroups(path, inspector) {
    const expected = {fields: [], constraints: [], source: []};
    const semanticKinds = new Set(['role', 'action', 'norm', 'sewn', 'template', 'module', 'event', 'behavior']);
    for (const entry of definitions[path].fields) {
      const group = entry.key === '/sys/lash' ? 'constraints' : ['/sys/lede', '/sys/help'].includes(entry.key) ||
        (!inspector && definitions[path].semantics && semanticKinds.has(entry.kind)) ? 'source' : 'fields';
      expected[group].push(entry.key);
    }
    return expected;
  }
  async function partition(root, path, inspector = false) {
    const keys = await rawRows(root).evaluateAll(rows => rows.map(row => row.dataset.key));
    assert.deepEqual([...keys].sort(), definitions[path].fields.map(field => field.key).sort(), 'every raw slot is present exactly once in ' + path + (inspector ? ' reference inspector' : ' main'));
    assert.equal(new Set(keys).size, keys.length, 'no primary/source/constraint duplication');
    const expected = expectedGroups(path, inspector);
    for (const [group, selector] of Object.entries({fields: inspector ? '.wb-inspector-record' : '.wb-properties', constraints: '.wb-constraint-record', source: '.wb-record'})) {
      const records = root.locator('sh-myth' + selector);
      const emptyPrimary = group === 'fields' && definitions[path].fields.length === 0;
      assert.equal(await records.count(), expected[group].length || emptyPrimary ? 1 : 0, group + ' exists for its slots or the explicit empty-record state');
      assert.deepEqual(await records.locator(':scope > sh-limb.wb-slot-row').evaluateAll(rows => rows.map(row => row.dataset.key)), expected[group], 'exclusive ' + group + ' preserves authored order');
      if (emptyPrimary) assert.equal(await records.locator('.wb-context-note').textContent(), 'This record has no slots.');
    }
    if (expected.source.length) {
      const item = root.locator('ui-accordion-item.wb-raw-details');
      assert.equal(await item.getAttribute('title'), 'Source slots');
      assert.equal(await item.locator('sh-myth.wb-record .wb-slot-row').count(), expected.source.length);
    }
    if (expected.constraints.length) assert.equal(await root.locator('ui-accordion-item.wb-constraints').getAttribute('title'), 'Record constraints');
    assert.equal(await root.locator('details.wb-raw-details, details.wb-constraints').count(), 0, 'shared accordion owns record disclosure');
    await openDetails(root);
    for (const entry of definitions[path].fields) {
      const pail = value(root, entry.key);
      if (entry.reference) {
        assert.equal(await pail.locator('a').first().getAttribute('href'), href(entry.reference));
        assert.equal(await pail.locator('a').first().textContent(), entry.text);
      } else assert.equal(await pail.locator('pre.wb-value').textContent(), entry.text, 'complete displayed source text/whitespace survives for ' + entry.key);
      assert.equal(await field(root, entry.key).getByRole('button', {name: 'Inspect slot definition ' + entry.key, exact: true}).count(), 1);
    }
  }
  async function unknownAnnotations(root) {
    const states = await root.locator('sh-myth.wb-record-body').evaluateAll(records => records.map(record => {
      const rows = [...record.querySelectorAll(':scope > sh-limb.wb-slot-row')], pails = rows.map(row => row.querySelector(':scope > sh-pail'));
      const annotations = [...record.querySelectorAll(':scope > span[slot=annotation].wb-record-annotation')];
      return {keys: rows.map(row => row.dataset.key), states: pails.map(pail => pail.dataset.valueState),
        annotations: annotations.map(node => ({id: node.id, text: node.textContent})),
        pails: pails.map((pail, index) => ({role: pail.getAttribute('role'), label: pail.getAttribute('aria-label'),
          describedby: pail.getAttribute('aria-describedby'), statuses: pail.querySelectorAll(':scope > .wb-value-status').length,
          annotationFound: annotations.some(node => node.id && node.id === pail.getAttribute('aria-describedby') && node.isConnected), key: rows[index].dataset.key}))};
    }));
    const ids = [];
    for (const record of states) {
      const shared = record.keys.length >= 2 && record.states.every(state => state === 'unknown');
      assert.equal(record.annotations.length, shared ? 1 : 0, 'only uniform multi-value unknown groups share an annotation: ' + JSON.stringify(record));
      if (shared) {
        assert.equal(record.annotations[0].text, 'Value completeness is not reported by this runtime.'); assert.ok(record.annotations[0].id); ids.push(record.annotations[0].id);
        assert.ok(record.pails.every(pail => pail.role === 'group' && pail.label === 'Value of ' + pail.key && pail.annotationFound && pail.statuses === 0),
          'every unknown value is labelled and describes the one mounted annotation, without duplicated status slots');
      } else assert.ok(record.pails.every(pail => pail.statuses === 1), 'mixed or standalone values keep their individual fidelity statuses');
    }
    assert.equal(new Set(ids).size, ids.length, 'each group annotation has a unique id');
  }
  async function geometry(page) {
    await page.waitForFunction(() => {
      const roots = [document];
      for (let index = 0; index < roots.length; index++) for (const element of roots[index].querySelectorAll('*')) {
        if (element.localName === 'ui-reveal' && element.matches(':state(entering), :state(leaving)')) return false;
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
      return true;
    }, null, {timeout: 5000});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'record page has no horizontal overflow');
    const bad = await page.evaluate(() => [...document.querySelectorAll('sh-myth.wb-record-body')].filter(record => record.clientWidth && record.scrollWidth > record.clientWidth + 1).map(record => record.className));
    assert.deepEqual(bad, [], 'all record groups fit their own containers');
  }

  async function responsiveFocus(page) {
    const workspace = page.locator('#debug-workspace');
    const sidebarToggle = page.getByRole('button', {name: 'Toggle sidebar', exact: true});
    const inspectorToggle = page.getByRole('button', {name: 'Toggle inspector', exact: true});
    const panes = () => workspace.evaluate(element => ({sidebar: element.sidebarOpen, inspector: element.inspectorOpen}));
    const frame = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    async function expectPanes(sidebar, inspector, compact) {
      await page.waitForFunction(({sidebar, inspector}) => {
        const element = document.querySelector('#debug-workspace');
        return element.sidebarOpen === sidebar && element.inspectorOpen === inspector;
      }, {sidebar, inspector}, {timeout: 5000});
      await frame();
      assert.equal(await page.locator('#debug-sidebar').isVisible(), sidebar);
      assert.equal(await page.locator('.wb-inspector').isVisible(), inspector);
      assert.equal(await page.locator('#debug-main').isVisible(), !compact || (!sidebar && !inspector));
      if (compact) assert.equal(sidebar && inspector, false, 'compact mode never activates both auxiliary panes');
    }
    async function focus(control) {
      await control.focus();
      assert.equal(await control.evaluate(element => {
        let active = document.activeElement;
        while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
        window.__responsiveExpectedFocus = element;
        return active === element;
      }), true, 'a real native control owns focus before resizing');
    }
    async function retained(checkFocus = true) {
      const result = await page.evaluate(checkFocus => {
        const held = window.__responsiveRetained;
        let active = document.activeElement;
        while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
        const checks = {main: held.main === document.querySelector('#debug-main'), canvas: held.canvas === document.querySelector('#wb-canvas'),
          draft: held.draft === document.querySelector('#fixture-responsive-draft'), draftValue: held.draft.value === 'Unsent fixture draft: preserve this selection',
          value: held.value === document.querySelector('#wb-canvas [data-key="/body"] .wb-full-value'),
          pre: held.pre === held.value.querySelector('pre'), preText: held.pre.textContent === held.text,
          rows: held.rows.every((row, index) => row === document.querySelectorAll('#wb-canvas .wb-slot-row')[index]),
          focus: !checkFocus || active === window.__responsiveExpectedFocus};
        const element = document.querySelector('#debug-workspace');
        return {checks, active: active?.outerHTML.slice(0, 500), expected: window.__responsiveExpectedFocus?.outerHTML.slice(0, 500),
          panes: {sidebar: element.sidebarOpen, inspector: element.inspectorOpen}, width: window.innerWidth};
      }, checkFocus);
      assert.ok(Object.values(result.checks).every(Boolean), 'responsive changes preserve the record, draft, exact-value DOM and active native focus: ' + JSON.stringify(result));
    }
    await page.setViewportSize({width: 1440, height: 1000}); await frame();
    if (!(await panes()).sidebar) await sidebarToggle.click();
    if (!(await panes()).inspector) await inspectorToggle.click();
    await expectPanes(true, true, false);
    // Real keyboard resizing creates distinct persisted preferences; the
    // breakpoint handler must not overwrite them with compact pixel widths.
    for (const [name, key] of [['sidebar', 'ArrowRight'], ['inspector', 'ArrowLeft']]) {
      const handle = page.getByRole('separator', {name: 'Resize ' + name, exact: true});
      await handle.focus(); await handle.press(key); await frame();
    }
    const desktop = await workspace.evaluate(element => ({
      preferred: {sidebarWidth: element.sidebarWidth, inspectorWidth: element.inspectorWidth},
      actual: Object.fromEntries(['sidebar', 'inspector'].map(name => [name, element.shadowRoot.querySelector('[part="' + name + '"]').getBoundingClientRect().width])),
      storage: localStorage.getItem('shrine-debug:pane-widths'),
    }));
    await value(scope(page), '/body').getByRole('button', {name: 'Inspect value', exact: true}).click();
    await page.waitForFunction(expected => document.querySelector('#wb-canvas [data-key="/body"] .wb-full-value pre')?.textContent === expected, exact.slice(0, 4096));
    await page.evaluate(() => {
      // Explicitly test-owned editing sentinel, not a claimed Grove form.
      const label = document.createElement('label'); label.textContent = 'Responsive fixture draft';
      const input = document.createElement('input'); input.id = 'fixture-responsive-draft'; input.setAttribute('aria-label', 'Responsive fixture draft');
      label.append(input); document.querySelector('#wb-canvas').append(label);
    });
    const draft = page.getByRole('textbox', {name: 'Responsive fixture draft', exact: true});
    await draft.fill('Unsent fixture draft: preserve this selection');
    await draft.evaluate(element => element.setSelectionRange(3, 16));
    await page.evaluate(() => {
      const area = document.querySelector('#wb-canvas [data-key="/body"] .wb-full-value');
      window.__responsiveRetained = {main: document.querySelector('#debug-main'), canvas: document.querySelector('#wb-canvas'),
        draft: document.querySelector('#fixture-responsive-draft'), value: area, pre: area.querySelector('pre'), text: area.querySelector('pre').textContent,
        rows: [...document.querySelectorAll('#wb-canvas .wb-slot-row')]};
    });
    const before = {documents: reads.length, values: valueReads.length};
    async function narrow(sidebar, inspector) {
      await page.setViewportSize({width: 768, height: 1000}); await expectPanes(sidebar, inspector, true); await retained();
    }
    async function widen(sidebar = true, inspector = true, checkFocus = true) {
      await page.setViewportSize({width: 1440, height: 1000}); await expectPanes(sidebar, inspector, false); await retained(checkFocus);
      const actual = await workspace.evaluate(element => ({sidebarWidth: element.sidebarWidth, inspectorWidth: element.inspectorWidth,
        storage: localStorage.getItem('shrine-debug:pane-widths'), widths: Object.fromEntries(['sidebar', 'inspector'].map(name => [name, element.shadowRoot.querySelector('[part="' + name + '"]')?.getBoundingClientRect().width ?? 0]))}));
      assert.deepEqual({sidebarWidth: actual.sidebarWidth, inspectorWidth: actual.inspectorWidth}, desktop.preferred, 'preferred pane widths survive breakpoint cycles');
      assert.equal(actual.storage, desktop.storage, 'responsive changes never overwrite persisted widths');
      for (const [name, open] of [['sidebar', sidebar], ['inspector', inspector]]) if (open)
        assert.ok(Math.abs(actual.widths[name] - desktop.actual[name]) <= 1, 'wide ' + name + ' restores its actual preferred width');
    }
    await focus(draft); await narrow(false, false);
    assert.deepEqual(await draft.evaluate(element => [element.selectionStart, element.selectionEnd]), [3, 16], 'main draft selection survives shrinking');
    await widen();
    const filter = page.locator('#debug-filter input'); await focus(filter); await narrow(true, false); await widen();
    const inspectorRegion = page.locator('.wb-inspector');
    await focus(inspectorRegion); await narrow(false, true); await widen();
    const chrome = page.getByRole('button', {name: 'Refresh current record', exact: true});
    await focus(chrome); await narrow(false, false); await widen();

    // A compact pane explicitly opened by the person must not be discarded
    // solely because the earlier desktop preference for that pane was closed.
    await inspectorToggle.click(); await expectPanes(true, false, false);
    await focus(draft); await narrow(false, false);
    await inspectorToggle.click(); await expectPanes(false, true, true);
    await focus(inspectorRegion);
    await widen(true, true);
    // Closed desktop preferences are also real preferences, not a request to
    // reapply the initial default of an open navigation sidebar.
    await inspectorToggle.click(); await sidebarToggle.click(); await expectPanes(false, false, false);
    await focus(draft); await narrow(false, false); await widen(false, false);
    // A newer actual native focus choice during the breakpoint handoff wins.
    await focus(draft);
    await page.evaluate(() => {
      matchMedia('(max-width: 832px)').addEventListener('change', () => {
        const chosen = document.querySelector('#wb-refresh').shadowRoot.querySelector('button');
        chosen.focus(); window.__responsiveExpectedFocus = chosen;
      }, {once: true});
    });
    await narrow(false, false); await widen(false, false);
    // Deliberately leaving a visible editor must not revive its stale focus on
    // the next breakpoint. This differs from CSS briefly hiding that editor.
    await focus(draft); await draft.evaluate(element => element.blur());
    const bodyFocused = () => page.evaluate(() => document.activeElement === document.body);
    assert.equal(await bodyFocused(), true);
    await page.setViewportSize({width: 768, height: 1000}); await expectPanes(false, false, true); await retained(false);
    assert.equal(await bodyFocused(), true, 'intentional blur is not undone by shrinking');
    await widen(false, false, false);
    assert.equal(await bodyFocused(), true, 'intentional blur is not undone by widening');
    assert.deepEqual({documents: reads.length, values: valueReads.length}, before, 'eight real viewport cycles cause no additional document or value reads');
    await retained(false); await geometry(page);
    console.log('PASS: native main/sidebar/inspector/header focus through eight real wide↔768 cycles; newer focus and intentional blur respected; drafts, value DOM, pane preferences and widths preserved; no extra GETs.');
  }

  const context = await createContext();
  try {
    const page = await context.newPage(); activePage = page;
    await page.goto(base + href('/uniform')); await ready(page, '/uniform');
    await partition(scope(page), '/uniform'); await unknownAnnotations(scope(page));
    const source = scope(page).locator('ui-accordion-item.wb-raw-details');
    await source.evaluate(item => { window.__partitionSourceNodes = {item, record: item.querySelector('sh-myth'), rows: [...item.querySelectorAll('sh-limb')], annotation: item.querySelector('.wb-record-annotation')}; });
    await source.getByRole('button').first().click();
    assert.equal(await source.evaluate(item => item.open), false);
    await source.getByRole('button').first().click();
    await source.evaluate(item => item.updateComplete);
    assert.equal(await source.evaluate(item => {
      const prior = window.__partitionSourceNodes;
      return item.open && item === prior.item && item.querySelector('sh-myth') === prior.record &&
        prior.rows.every((row, index) => row === item.querySelectorAll('sh-limb')[index]) && item.querySelector('.wb-record-annotation') === prior.annotation;
    }), true, 'owned Source slots disclosure keeps its record, rows and shared annotation mounted across close/reopen');
    const initialKeys = await rawRows(scope(page)).evaluateAll(rows => rows.map(row => row.dataset.key));
    await field(scope(page), '/definition').getByRole('button', {name: 'Inspect slot definition /definition', exact: true}).click();
    await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.inspectorPath === '/definition' && document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true');
    const inspector = page.locator('.wb-inspector');
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/uniform');
    await partition(inspector, '/definition', true); await unknownAnnotations(inspector);
    assert.equal(await inspector.locator('.wb-inspector-record > [data-key="/role"]').isVisible(), true, 'semantic-kind raw role is visible in reference inspector without a semantic renderer');
    assert.equal(await inspector.locator('.wb-inspector-record > [data-key="/behavior"]').isVisible(), true);
    assert.deepEqual(await rawRows(scope(page)).evaluateAll(rows => rows.map(row => row.dataset.key)), initialKeys, 'reference inspection never replaces or duplicates main slots');
    const annotationIds = await page.locator('.wb-record-annotation').evaluateAll(nodes => nodes.map(node => node.id));
    assert.equal(new Set(annotationIds).size, annotationIds.length, 'main and inspector annotations do not collide');
    await page.locator('#debug-inspector-toggle').click();
    assert.equal(await field(scope(page), '/definition').locator('.wb-slot-key').evaluate(host => document.activeElement === host), true, 'reference dismissal restores the original slot action');

    for (const path of ['/semantic', '/invalid-only', '/single', '/empty']) {
      await go(page, path); await partition(scope(page), path); await unknownAnnotations(scope(page));
      if (path === '/invalid-only') {
        assert.equal(await scope(page).getByRole('button', {name: 'Inspect value', exact: true}).count(), 0, 'invalid metadata cannot manufacture exact-value actions');
        assert.equal(await scope(page).locator('sh-pail[data-value-state=complete]').count(), 0, 'invalid complete metadata is never trusted');
      }
    }
    await go(page, '/mixed'); await partition(scope(page), '/mixed'); await unknownAnnotations(scope(page));
    const statuses = {};
    for (const key of ['/complete', '/body', '/opaque', '/unknown', '/invalid']) statuses[key] = await value(scope(page), key).locator('.wb-value-status').textContent();
    assert.match(statuses['/complete'], /^Complete.*14 bytes/);
    assert.match(statuses['/body'], /^Preview.*48.*bytes/);
    assert.match(statuses['/opaque'], /Summary.*unavailable/);
    assert.equal(statuses['/unknown'], 'Completeness unknown'); assert.equal(statuses['/invalid'], 'Completeness unknown');
    assert.equal(await value(scope(page), '/invalid').getByRole('button', {name: 'Inspect value', exact: true}).count(), 0);
    const body = value(scope(page), '/body'), original = await body.locator('pre.wb-value').textContent();
    const readBefore = valueReads.length;
    await body.getByRole('button', {name: 'Inspect value', exact: true}).click();
    await body.locator('.wb-full-value pre').waitFor();
    assert.equal(await body.locator('.wb-full-value pre').textContent(), exact.slice(0, 4096));
    await body.getByRole('button', {name: 'Next bytes', exact: true}).click();
    await page.waitForFunction(expected => document.querySelector('#wb-canvas [data-key="/body"] .wb-full-value pre')?.textContent === expected, exact.slice(4096));
    assert.equal(await body.getByRole('button', {name: 'Next bytes', exact: true}).isDisabled(), true);
    await body.getByRole('button', {name: 'Earlier bytes', exact: true}).click();
    await page.waitForFunction(expected => document.querySelector('#wb-canvas [data-key="/body"] .wb-full-value pre')?.textContent === expected, exact.slice(0, 4096));
    assert.equal(valueReads.length, readBefore + 3, 'only explicit exact-byte actions fetch the three requested windows');
    assert.equal(await body.locator('pre.wb-value').textContent(), original, 'exact inspection never replaces the original preview');
    await body.getByRole('button', {name: 'Close value', exact: true}).click();
    assert.equal(await body.locator('.wb-full-value').count(), 0);
    await partition(scope(page), '/mixed'); await unknownAnnotations(scope(page));
    const sourceItem = scope(page).locator('ui-accordion-item.wb-raw-details');
    const sourceValue = value(scope(page), '/sys/help');
    let started, release, finished;
    const began = new Promise(resolve => { started = resolve; });
    const released = new Promise(resolve => { release = resolve; });
    const ended = new Promise(resolve => { finished = resolve; });
    heldByte = {slot: '/sys/help', started, released, finished};
    try {
      await sourceValue.getByRole('button', {name: 'Inspect value', exact: true}).click();
      await bounded(began, 'Source exact read');
      assert.equal(await sourceValue.locator('.wb-value-status').textContent(), 'Reading value bytes…');
      await sourceItem.getByRole('button').first().click();
      assert.equal(await sourceItem.evaluate(item => item.open), false);
      await page.waitForFunction(() => document.querySelector('#wb-canvas .wb-raw-details [data-key="/sys/help"] .wb-value-status')?.textContent.startsWith('Preview'));
      release(); await bounded(ended, 'Cancelled fixture response'); heldByte = null;
      await sourceItem.getByRole('button').first().click();
      assert.equal(await sourceValue.locator('.wb-full-value').count(), 0, 'closing Source slots cancels its read; a late fixture response cannot reopen exact content');
      assert.equal(await sourceValue.getByRole('button', {name: 'Inspect value', exact: true}).isEnabled(), true);
      await sourceValue.getByRole('button', {name: 'Inspect value', exact: true}).click();
      await page.waitForFunction(expected => document.querySelector('#wb-canvas .wb-raw-details [data-key="/sys/help"] .wb-full-value pre')?.textContent === expected, exact.slice(0, 4096));
      await sourceValue.getByRole('button', {name: 'Close value', exact: true}).click();
    } finally { release(); heldByte = null; }
    await partition(scope(page), '/mixed'); await unknownAnnotations(scope(page));
    assert.equal(await page.evaluate(() => window.__partitionExecuted), undefined);
    await responsiveFocus(page);
    console.log('PASS: exclusive main/reference partitions, independent constraints/source, exact raw slots, shared unknown vs mixed/invalid states, references and byte actions.');
  } catch (error) {
    await activePage.screenshot({path: '/private/tmp/shrine-record-partition-failure.png'}).catch(() => {}); throw error;
  } finally { await context.close(); }

  for (const specimen of [{width: 1440, height: 1000, theme: 'light'}, {width: 1024, height: 900, theme: 'dark'},
    {width: 390, height: 844, theme: 'light', coarse: true}]) {
    const context = await createContext({viewport: {width: specimen.width, height: specimen.height}, colorScheme: specimen.theme,
      hasTouch: !!specimen.coarse, isMobile: !!specimen.coarse});
    try {
      const page = await context.newPage(); activePage = page;
      await page.goto(base + href('/uniform')); await ready(page, '/uniform');
      await partition(scope(page), '/uniform'); await unknownAnnotations(scope(page)); await geometry(page);
      const path = '/private/tmp/shrine-record-partition-' + specimen.theme + '-' + specimen.width + (specimen.coarse ? '-coarse' : '') + '.png';
      await page.screenshot({path}); screenshots.push(path);
      await field(scope(page), '/definition').getByRole('button', {name: 'Inspect slot definition /definition', exact: true}).click();
      await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.inspectorPath === '/definition' && document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true');
      await partition(page.locator('.wb-inspector'), '/definition', true); await unknownAnnotations(page.locator('.wb-inspector')); await geometry(page);
      const inspectorPath = path.replace('.png', '-inspector.png'); await page.screenshot({path: inspectorPath}); screenshots.push(inspectorPath);
    } catch (error) {
      await activePage.screenshot({path: '/private/tmp/shrine-record-partition-failure.png'}).catch(() => {}); throw error;
    } finally { await context.close(); }
  }
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log(JSON.stringify({screenshots, fixtureDocumentReads: reads.length, explicitByteReads: valueReads.length, liveReads: 0, writes: 0}, null, 2));
} catch (error) {
  console.error(JSON.stringify({writes, unexpected, errors, reads, valueReads, screenshots}, null, 2)); throw error;
} finally { await browser.close(); }
