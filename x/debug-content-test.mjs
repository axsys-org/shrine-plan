// Namespace-first presentation regression over a mandatory saved real shell.
// All namespace data/prose below is test-owned, not evidence of a live Grove.
// Frozen local assets and exact inert fixtures are the only allowed requests.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is required; live namespace access is forbidden');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://debug-content-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const href = path => '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
const browser = await chromium.launch();
try {
const context = await browser.newContext({viewport: {width: 1440, height: 960}, serviceWorkers: 'block'});
context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
const writes = [], fixturePosts = [], errors = [], reads = [], unexpected = [];
const heldDocuments = new Map(), unavailableDocuments = new Set();
let fixtures = Object.freeze({}), heldPreview = null, nextOperation = null;
await context.addInitScript(({base}) => {
  window.fixtureStatusEvents = [];
  document.addEventListener('debug:status', event => window.fixtureStatusEvents.push({...event.detail}));
  if (location.origin !== base || sessionStorage.getItem('debug-content-fixture')) return;
  localStorage.setItem('shrine-debug.v1.saved', '[]');
  localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: true, recent: false, tree: true, root: '/', expanded: ['/']}));
  sessionStorage.setItem('shrine-debug.v1.navigation', JSON.stringify({visits: ['/app'], pages: [null], cursor: 0}));
  sessionStorage.setItem('debug-content-fixture', 'seeded');
}, {base});
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url());
  if (url.origin === base && !url.search && request.method() === 'POST' &&
      url.pathname === '/op/__feedback__' && nextOperation) {
    // Deliberate operation feedback only: terminate this exact POST in the
    // harness. There is no live write, commit verdict, or route continuation.
    const planned = nextOperation; nextOperation = null;
    fixturePosts.push({url: url.href, data: [...new URLSearchParams(request.postData())]});
    planned.started();
    await planned.released;
    return route.fulfill({status: planned.status, contentType: 'text/plain',
      body: 'Test-owned operation response; no namespace operation occurred.'}).catch(() => {});
  }
  if (request.method() !== 'GET') { writes.push(request.method() + ' ' + request.url()); return route.abort(); }
  if (url.origin !== base || url.search) { unexpected.push(request.url()); return route.abort(); }
  if (assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
  if (url.pathname === '/debug/__unavailable_preview_test__' || unavailableDocuments.has(url.pathname)) {
    reads.push(url.pathname);
    return route.fulfill({status: 503, contentType: 'text/plain', body: 'Test-owned unavailable path'});
  }
  const body = fixtures[url.pathname];
  if (!body) { unexpected.push(request.url()); return route.abort(); }
  reads.push(url.pathname);
  if (url.pathname === '/debug/gov/srs/card' && heldPreview) {
    const gate = heldPreview; await gate;
    return route.abort().catch(() => {});
  }
  if (heldDocuments.has(url.pathname)) await heldDocuments.get(url.pathname);
  return route.fulfill({status: 200, contentType: 'text/html', body}).catch(() => {});
});
const page = await context.newPage();
context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
page.on('pageerror', error => errors.push(error.message));
const ready = path => page.waitForFunction(path => {
  const ws = document.querySelector('#debug-workspace');
  return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
}, path, {timeout: 5000});
async function startGo(path) {
  if (!await page.locator('#debug-go').isVisible())
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  const input = page.locator('#debug-go input');
  await input.fill(path); await input.press('Enter');
}
async function go(path) { await startGo(path); await ready(path); }
const feedback = () => page.locator('#wb-feedback');
async function feedbackState() {
  return feedback().evaluate(element => ({hidden: element.hidden, text: element.textContent,
    operation: element.dataset.operation, phase: element.dataset.phase, context: element.dataset.context,
    failed: element.dataset.failed}));
}
async function assertFeedback(operation, phase, context) {
  await page.waitForFunction(({operation, phase, context}) => {
    const element = document.querySelector('#wb-feedback');
    return element && !element.hidden && element.dataset.operation === operation &&
      element.dataset.phase === phase && element.dataset.context === context;
  }, {operation, phase, context}, {timeout: 5000});
  return feedbackState();
}
async function failNavigation() {
  const before = reads.filter(path => path === '/debug/__unavailable_preview_test__').length;
  await startGo('/__unavailable_preview_test__');
  await page.waitForFunction(() => document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true', null, {timeout: 5000});
  assert.equal(reads.filter(path => path === '/debug/__unavailable_preview_test__').length, before + 1);
  assert.match(await page.locator('#debug-status').textContent(), /Navigation failed/);
}
function planOperation(status) {
  assert.equal(nextOperation, null, 'only one exact fixture operation is planned at a time');
  let started, release;
  const startedPromise = new Promise(resolve => { started = resolve; });
  const released = new Promise(resolve => { release = resolve; });
  nextOperation = {status, started, released};
  return {started: async () => {
    let timer;
    try { await Promise.race([startedPromise,
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Expected exact fixture POST did not start')), 5000); })]); }
    finally { clearTimeout(timer); }
  }, release};
}
async function openOperations() {
  if (!await page.locator('#wb-operations').evaluate(element => element.open))
    await page.getByRole('button', {name: 'Open operations', exact: true}).click();
}
async function noOverflow() {
  const result = await page.evaluate(() => ({
    width: innerWidth,
    document: document.documentElement.scrollWidth,
    main: document.querySelector('#debug-main').getBoundingClientRect().width,
  }));
  assert.ok(result.document <= result.width + 1, 'the document never horizontally overflows');
  assert.ok(result.main <= result.width + 1, 'main content fits the viewport');
}
async function capture(path) {
  // Screenshots must show settled content, not a half-open Mash reveal.
  // Inspect actual lifecycle state; do not replace it with a fixed delay.
  await page.waitForFunction(() => {
    const roots = [document];
    for (let index = 0; index < roots.length; index++) {
      for (const element of roots[index].querySelectorAll('*')) {
        if (element.localName === 'ui-reveal' && element.matches(':state(entering), :state(leaving)')) return false;
        if (element.shadowRoot) roots.push(element.shadowRoot);
      }
    }
    return true;
  }, null, {timeout: 5000});
  await page.screenshot({path});
}
try {
  fixtures = Object.freeze(await page.evaluate(({shell}) => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell is not the current debugger anatomy');
    const children = {'/': ['/app', '/gov', '/sys'], '/app': ['/app/srs'], '/gov': ['/gov/srs'],
      '/gov/srs': ['/gov/srs/card', '/gov/srs/queue'], '/sys': ['/sys/about', '/sys/lede', '/sys/help']};
    const authored = {
      '/app': ['Applications.', 'Test-owned applications fixture.'],
      '/gov/srs': ['Fixture collection', 'Test-owned definitions for preview regression.'],
      '/gov/srs/card': ['Fixture card definition', 'Test-owned card prose; this is not a live Grove definition.'],
      '/sys/about': ['About', 'The subject this record describes.\nTest-owned help for the content regression, not namespace documentation.'],
      '/sys/lede': ['Short title', 'A short title for this name. Test-owned slot definition.'],
    };
    const paths = [...new Set([...Object.keys(children), ...Object.values(children).flat(), '/__feedback__'])];
    return Object.fromEntries(paths.map(path => {
      const doc = original.cloneNode(true), workspace = doc.querySelector('#debug-workspace');
      const [label, help] = authored[path] || [path.split('/').at(-1) || 'Namespace', 'Test-owned content fixture for ' + path + '.'];
      Object.assign(workspace.dataset, {path, kind: path === '/gov/srs/card' ? 'role' : 'record', writable: String(path === '/__feedback__'),
        label, fixture: 'debug-content', description: help, descriptionSource: '/sys/help', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete workspace.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, text] of [['/sys/lede', label], ['/sys/help', help], ['/value', 'Test-owned exact value at ' + path]]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
        const slot = doc.createElement('sh-slot'); slot.setAttribute('title', key);
        const pail = doc.createElement('sh-pail'); pail.textContent = text;
        limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]')?.replaceChildren();
      if (path === '/__feedback__') {
        doc.querySelector('#debug-main section[aria-label=Operations]').innerHTML = `
          <div class="opform"><div class="muted">Test-owned feedback operation; every response is intercepted.</div>
            <form method="post" action="/op/__feedback__" class="wf" id="fixture-feedback-form">
              <input type="hidden" name="op" value="/__feedback__/op/test">
              <ui-button type="submit" variant="secondary" id="fixture-feedback-submit">Test feedback operation</ui-button>
            </form>
          </div>`;
      }
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of children[path] || []) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.dataset.kind = child === '/gov/srs/card' ? 'role' : 'record';
        item.dataset.label = authored[child]?.[0] || child.split('/').at(-1); item.title = child.split('/').at(-1); tree.append(item);
      }
      // No original namespace content leaks into fixture inspector/version data.
      doc.querySelector('#debug-workspace [slot=inspector]')?.replaceChildren();
      doc.querySelector('#debug-activity')?.replaceChildren();
      const target = '/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
      return [target, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, {shell}));
  await page.goto(base + '/debug/app'); await ready('/app');
  assert.equal(await page.locator('.wb-document-title').textContent(), 'app');
  assert.equal(await page.locator('.wb-document-lede').textContent(), 'Applications.');
  assert.doesNotMatch(await page.locator('#debug-main').innerText(), /Own record slots and namespace relationships/);
  assert.equal(await page.locator('#wb-canvas > details.wb-documentation').count(), 0, 'lore is not hidden behind Documentation');
  for (const row of await page.locator('.wb-child-row').all()) {
    const path = await row.getAttribute('data-path');
    assert.equal(await row.locator('.wb-child-name').textContent(), path.split('/').at(-1), 'a lede never replaces path identity');
    assert.equal(await row.locator('.wb-child-preview').isVisible(), false);
    const box = await row.boundingBox();
    assert.ok(box.height <= 64, 'an unexpanded child occupies a compact row');
  }
  await noOverflow();
  await page.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor();
  await capture('/private/tmp/shrine-content-app-desktop.png');
  console.log('PASS: fixture identifiers, authored ledes, compact rows, and no boilerplate.');

  await go('/gov/srs');
  const row = page.locator('.wb-child-row[data-path="/gov/srs/card"]');
  const preview = row.locator('.wb-child-preview');
  const before = reads.filter(path => path === '/debug/gov/srs/card').length;
  await row.locator('[part="toggle"]').click();
  await preview.locator('.wb-preview-open').waitFor();
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs', 'preview does not navigate');
  assert.equal(await preview.isVisible(), true);
  await capture('/private/tmp/shrine-content-open-preview.png');
  const loaded = reads.filter(path => path === '/debug/gov/srs/card').length;
  assert.ok(loaded >= before + 1, 'first preview reads the fixture record through the production loader');
  await row.locator('[part="toggle"]').click();
  assert.equal(await preview.isVisible(), false);
  await row.locator('[part="toggle"]').click();
  assert.equal(await preview.isVisible(), true);
  assert.equal(reads.filter(path => path === '/debug/gov/srs/card').length, loaded, 'reopening an unchanged preview makes no request');
  await preview.locator('.wb-preview-open').click(); await ready('/gov/srs/card');
  assert.equal(await page.locator('.wb-document-title').evaluate(el => el === document.activeElement), true,
    'opening a main-content link moves keyboard focus to the new document');
  await capture('/private/tmp/shrine-content-role-desktop.png');
  console.log('PASS: lazy child preview, instant reopen, and open-record navigation.');

  await go('/gov/srs');
  let releasePreview;
  heldPreview = new Promise(resolve => { releasePreview = resolve; });
  try {
    await row.locator('[part="toggle"]').click();
    await preview.locator('.wb-loading').waitFor();
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
    await page.locator('#debug-go input').fill('/__unavailable_preview_test__');
    await page.locator('#debug-go input').press('Enter');
    await page.locator('#wb-feedback').getByText(/Navigation failed/).waitFor();
    await preview.getByRole('button', {name: 'Retry preview /gov/srs/card'}).waitFor();
    assert.equal(await preview.locator('.wb-loading').count(), 0, 'cancellation never leaves an infinite loading message');
    assert.equal(await preview.getAttribute('aria-busy'), null);
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/gov/srs');
  } finally {
    releasePreview();
    heldPreview = null;
  }
  await preview.getByRole('button', {name: 'Retry preview /gov/srs/card'}).click();
  await preview.locator('.wb-preview-open').waitFor();
  console.log('PASS: interrupted previews settle visibly, failed navigation retains the page, and retry recovers.');

  const failedNavigation = await assertFeedback('navigate', 'error', '/__unavailable_preview_test__');
  let releaseAbout;
  heldDocuments.set('/debug/sys/about', new Promise(resolve => { releaseAbout = resolve; }));
  try {
    await startGo('/sys/about');
    await page.waitForFunction(() => document.querySelector('#debug-workspace').getAttribute('aria-busy') === 'true', null, {timeout: 5000});
    assert.deepEqual(await feedbackState(), failedNavigation, 'pending navigation does not dismiss the previous failure before recovery');
  } finally { releaseAbout(); heldDocuments.delete('/debug/sys/about'); }
  await ready('/sys/about');
  assert.equal(await feedback().isVisible(), false, 'a successful navigation clears its own earlier navigation failure');
  assert.equal(await feedback().textContent(), '', 'recovery removes stale navigation text');
  assert.deepEqual(await page.evaluate(() => window.fixtureStatusEvents.at(-1)), {
    message: 'Opened /sys/about.', failed: false, operation: 'navigate', phase: 'success', context: '/sys/about', quiet: true,
  }, 'navigation emits typed feedback rather than requiring an English-prefix classifier');
  const prose = await page.locator('#wb-canvas > .wb-lore').innerText();
  assert.match(prose, /The subject this record describes/);
  assert.equal(await page.locator('.wb-document-title').textContent(), 'about');
  assert.equal(await page.locator('.wb-document-lede').count(), 0, 'case-only title repetition is suppressed');
  assert.doesNotMatch(prose, /Own record slots/);
  await page.locator('#wb-canvas .wb-raw-details').getByRole('button', {name: /^Source slots/}).click();
  await page.locator('#wb-canvas .wb-record .wb-slot-key[data-inspect="/sys/lede"]').click();
  await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.inspectorPath === '/sys/lede' && document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/sys/about');
  assert.match(await page.locator('.wb-inspector').innerText(), /A short title for this name/);
  assert.equal(await page.locator('.wb-inspector').getByText('Live record', {exact: true}).count(), 0);
  await capture('/private/tmp/shrine-content-field-definition.png');
  console.log('PASS: fixture plain-text help and contextual slot definition inspection.');

  await page.locator('#debug-inspector-toggle').click();
  assert.equal(await page.locator('#wb-canvas .wb-record .wb-slot-key[data-inspect="/sys/lede"]').evaluate(el => el === document.activeElement), true,
    'closing the inspector returns focus to the original slot');

  unavailableDocuments.add('/debug/sys/lede');
  try {
    await page.locator('#wb-canvas .wb-record .wb-slot-key[data-inspect="/sys/lede"]').click();
    await assertFeedback('inspect', 'error', '/sys/lede');
  } finally { unavailableDocuments.delete('/debug/sys/lede'); }
  const failedInspection = await feedbackState();
  await go('/app');
  assert.deepEqual(await feedbackState(), failedInspection, 'navigation success does not clear a different inspection failure');
  await go('/sys/about');
  await page.locator('#wb-canvas .wb-raw-details').getByRole('button', {name: /^Source slots/}).click();
  await page.locator('#wb-canvas .wb-record .wb-slot-key[data-inspect="/sys/lede"]').click();
  await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.inspectorPath === '/sys/lede' &&
    document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true', null, {timeout: 5000});
  assert.equal(await feedback().isVisible(), false, 'successful inspection clears only its own earlier inspection failure');
  await page.locator('#debug-inspector-toggle').click();
  console.log('PASS: typed navigation recovery, pending-read retention, and independent inspection feedback ownership.');

  await go('/__feedback__'); await openOperations();
  const rejected = planOperation(503);
  try {
    await page.locator('#fixture-feedback-submit button').click(); await rejected.started();
    const pending = await assertFeedback('write', 'pending', '/__feedback__/op/test');
    // Explicit listener-contract probes, not simulated namespace outcomes:
    // an unrelated read notification must not overwrite a held real UI submit.
    await page.evaluate(() => {
      for (const detail of [
        {message: 'Test-owned quiet navigation success probe', failed: false, operation: 'navigate', phase: 'success', context: '/app', quiet: true},
        {message: 'Test-owned refresh success probe', failed: false, operation: 'refresh', phase: 'success', context: '/app', quiet: false},
        {message: 'Test-owned unrelated navigation error probe', failed: true, operation: 'navigate', phase: 'error', context: '/app', quiet: false},
      ]) document.dispatchEvent(new CustomEvent('debug:status', {detail}));
    });
    assert.deepEqual(await feedbackState(), pending, 'unrelated successes and failures preserve pending work until its own settlement');
    assert.equal(await page.locator('#debug-workspace').getAttribute('aria-busy'), 'true');
  } finally { rejected.release(); }
  const writeRejected = await assertFeedback('write', 'error', '/__feedback__/op/test');
  await ready('/__feedback__');
  assert.match(writeRejected.text, /Operation rejected \(HTTP 503\)/);
  await failNavigation();
  assert.deepEqual(await feedbackState(), writeRejected, 'navigation failure stays in activity without replacing the write rejection');
  await go('/app');
  assert.deepEqual(await feedbackState(), writeRejected, 'navigation recovery never clears the unrelated write failure');
  await feedback().getByRole('button', {name: 'Dismiss notification', exact: true}).click();

  await go('/__feedback__'); await openOperations();
  const unknown = planOperation(200);
  try {
    await page.locator('#fixture-feedback-submit button').click(); await unknown.started();
    await assertFeedback('write', 'pending', '/__feedback__/op/test');
  } finally { unknown.release(); }
  const unknownCommit = await assertFeedback('write', 'unknown', '/__feedback__/op/test');
  await ready('/__feedback__');
  assert.match(unknownCommit.text, /Commit status is unknown/);
  await failNavigation();
  assert.deepEqual(await feedbackState(), unknownCommit, 'failed navigation cannot erase an uncertain commit warning');
  await go('/app');
  assert.deepEqual(await feedbackState(), unknownCommit, 'successful navigation cannot erase an uncertain commit warning');
  await capture('/private/tmp/shrine-content-retained-warning.png');
  await go('/__feedback__'); await openOperations();
  const sameContext = planOperation(503);
  try {
    await page.locator('#fixture-feedback-submit button').click(); await sameContext.started();
    assert.deepEqual(await feedbackState(), unknownCommit, 'a new same-context attempt does not resolve an earlier uncertain commit');
  } finally { sameContext.release(); }
  await ready('/__feedback__');
  assert.deepEqual(await feedbackState(), unknownCommit, 'a same-context rejection cannot establish the previous attempt outcome');
  assert.match(await page.locator('#debug-status').textContent(), /Operation rejected/);
  await feedback().getByRole('button', {name: 'Dismiss notification', exact: true}).click();
  assert.equal(await feedback().isVisible(), false, 'explicit dismissal still works for an uncertain commit warning');
  const realWriteEvents = await page.evaluate(() => window.fixtureStatusEvents.filter(event => event.operation === 'write'));
  assert.deepEqual(realWriteEvents.map(({phase}) => phase), ['pending', 'error', 'pending', 'unknown', 'pending', 'error']);
  assert.ok(realWriteEvents.every(event => event.context === '/__feedback__/op/test' && event.quiet === false));
  assert.equal(fixturePosts.length, 3);
  for (const post of fixturePosts) assert.deepEqual(post, {url: base + '/op/__feedback__',
    data: [['op', '/__feedback__/op/test'], ['back', '/debug/__feedback__']]});
  await go('/sys/about');
  console.log('PASS: intercepted pending/rejected/unknown operation feedback survives unrelated failures and recovery until explicit dismissal.');

  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await capture('/private/tmp/shrine-content-dark.png');
  await noOverflow();
  await page.emulateMedia({colorScheme: 'light', reducedMotion: 'no-preference'});
  for (const [width, height] of [[1024, 768], [768, 1024], [390, 844]]) {
    await page.setViewportSize({width, height});
    await page.goto(base + href('/sys/about')); await ready('/sys/about');
    await noOverflow();
    assert.equal(await page.locator('#debug-main').isVisible(), true);
    assert.match(await page.locator('#wb-canvas > .wb-lore').innerText(), /The subject this record describes/);
    await capture('/private/tmp/shrine-content-' + width + '.png');
  }
  await page.getByRole('button', {name: 'Toggle sidebar', exact: true}).click();
  assert.equal(await page.locator('#debug-sidebar').isVisible(), true);
  await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  assert.equal(await page.locator('.wb-inspector').isVisible(), true, 'mobile inspector replaces the open sidebar');
  assert.equal(await page.locator('#debug-sidebar').isVisible(), false);
  assert.equal(await page.locator('#debug-sidebar-toggle').getAttribute('aria-expanded'), 'false');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#debug-main').isVisible(), true);
  await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  await page.keyboard.press('Control+k');
  await page.waitForFunction(() => document.querySelector('#debug-filter') === document.activeElement);
  assert.equal(await page.locator('#debug-sidebar').isVisible(), true);
  assert.equal(await page.locator('.wb-inspector').isVisible(), false);
  assert.equal(await page.locator('#debug-inspector-toggle').getAttribute('aria-expanded'), 'false');
  assert.deepEqual(writes, []);
  assert.deepEqual(unexpected, []);
  assert.deepEqual(errors, []);
  console.log('PASS: 1024 / 768 / 390px, sidebar toggles, filter shortcut, zero live writes, unexpected requests or page errors.');
  console.log('Fixture namespace reads: ' + reads.length + '; rejected/unknown fixture POSTs: ' + fixturePosts.length +
    '; live reads/writes: 0. All prose is test-owned, not evidence of a real Grove.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-content-failure.png'}).catch(() => {});
  console.error(JSON.stringify({writes, fixturePosts, unexpected, errors, reads}, null, 2));
  throw error;
} finally {
  await context.close();
}
} finally {
  await browser.close();
}
