// REAL Grove workflow against one manifest-owned disposable runtime.
// No fixture HTML, synthetic namespace data, live fallback, or user browser state.
import assert from 'node:assert/strict';
import {readFile, writeFile, mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {playwright} from './debug-tooling.mjs';

assert.ok(process.env.GROVE_RUNTIME, 'GROVE_RUNTIME must name an owned disposable controller manifest');
const root = fileURLToPath(new URL('..', import.meta.url));
const manifestPath = resolve(process.env.GROVE_RUNTIME);
const verified = JSON.parse(execFileSync('python3', [resolve(root, 'x/debug-grove-runtime.py'), 'verify', manifestPath], {encoding: 'utf8'}));
const seal = JSON.parse(await readFile(resolve(verified.work, 'assets.json'), 'utf8'));
assert.ok(seal.assets && seal.assetVersions.app && seal.assetVersions.components, 'Final frontend assets must be sealed before UI starts');
const base = verified.origin;
assert.equal(new URL(base).hostname, '127.0.0.1'); assert.notEqual(new URL(base).port, '8138');
assert.notEqual(new URL(base).port, '51571');
assert.notEqual(verified.pid, 39258);
const output = await mkdtemp(resolve(verified.work, 'ui-workflow-'));
// Every run owns a distinct install, even when diagnosing a harness failure.
const target = '/app/workflow_' + Date.now();
const cardPath = target + '/cards/demo';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
for (const asset of Object.values(seal.assets))
  assert.equal(digest(await readFile(resolve(verified.sourceSnapshot, asset.path))), asset.sha256);
const {chromium} = playwright();
const requests = [], replies = [], failures = [], unexpected = [], pageErrors = [], screenshots = [], checks = [];
const responseTasks = new Set(), documents = new Map(), assetReplies = new Map();
const requestRecords = new WeakMap();
const allowedValueReads = new Set();
let authorizedInstall = null, postCount = 0, activePage = null;
const run = {version: 1, evidence: 'real disposable Grove runtime, not fixture data', runtimeId: verified.id,
  origin: base, pid: verified.pid, backendSourceFiles: verified.backendSourceFiles,
  assets: seal.assets, assetVersions: seal.assetVersions, requests, replies, failures, unexpected, pageErrors,
  screenshots, checks, startedAt: new Date().toISOString(), passed: false};
const browser = await chromium.launch();

async function context(options = {}) {
  // Playwright 1.62's serviceWorkers:block script reads navigator.serviceWorker
  // inside every frame, throwing in the application's intentionally sandboxed
  // preview. Block registration without evaluating that forbidden getter.
  const context = await browser.newContext({viewport: {width: 1440, height: 960}, ...options});
  context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(20_000);
  await context.addInitScript(() => {
    if (typeof ServiceWorkerContainer !== 'undefined') Object.defineProperty(ServiceWorkerContainer.prototype, 'register', {
      configurable: true,
      value() { return Promise.reject(new Error('Service worker registration blocked by the isolated Grove workflow harness')); },
    });
  });
  await context.addInitScript(origin => {
    if (window !== window.top || location.origin !== origin || sessionStorage.getItem('grove-owned-profile')) return;
    localStorage.setItem('shrine-debug.v1.saved', '[]');
    // Browser preferences only. Namespace records always come from the server.
    localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false,
      tree: false, root: '/', expanded: ['/']}));
    sessionStorage.setItem('grove-owned-profile', '1');
  }, base);
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    const record = {method: request.method(), path: url.pathname + url.search, started: Date.now()};
    requests.push(record);
    requestRecords.set(request, record);
    if (url.origin !== base || requests.length > 120) {
      unexpected.push({reason: 'origin or bounded request budget', ...record}); return route.abort();
    }
    if (request.method() === 'POST') {
      const form = new URLSearchParams(request.postData());
      const exact = authorizedInstall && url.pathname === '/grove/install' && !url.search &&
        form.get('source') === authorizedInstall.source && form.get('version') === authorizedInstall.version &&
        form.get('root') === authorizedInstall.root && form.get('back') === '/debug/gov/srs' &&
        [...form.keys()].sort().join(',') === 'back,root,source,version' && postCount < 2;
      if (!exact) { unexpected.push({reason: 'unapproved write', ...record}); return route.abort(); }
      record.purpose = authorizedInstall.purpose; record.fields = [...form];
      authorizedInstall = null; postCount++;
      return route.continue(); // Only this proven owned-origin install reaches a real server.
    }
    if (request.method() !== 'GET') { unexpected.push(record); return route.abort(); }
    const path = url.pathname + url.search;
    const permitted = Object.hasOwn(seal.assets, url.pathname) && !url.search ||
      url.pathname === '/favicon.ico' && !url.search ||
      /^\/debug(?:\/|$)/.test(url.pathname) && [...url.searchParams].every(([key, value]) =>
        key === 'scope' && ['workspace', 'outline', 'preview'].includes(value)) || allowedValueReads.has(path);
    if (!permitted) { unexpected.push({reason: 'unapproved read', ...record}); return route.abort(); }
    return route.continue();
  });
  context.on('page', page => page.on('pageerror', error => pageErrors.push(error.message)));
  context.on('requestfailed', request => failures.push({url: request.url(), failure: request.failure()?.errorText}));
  context.on('response', response => {
    const task = (async () => {
      const url = new URL(response.url());
      if (url.origin !== base) return;
      const body = await response.body();
      const request = response.request();
      const match = requestRecords.get(request);
      const index = replies.length;
      const filename = String(index).padStart(3, '0') + (response.headers()['content-type']?.includes('json') ? '.json' : '.body');
      const result = {method: request.method(), path: url.pathname + url.search, status: response.status(),
        ms: Date.now() - (match?.started || Date.now()), bytes: body.length, sha256: digest(body), file: filename};
      replies.push(result); await writeFile(resolve(output, filename), body);
      if (Object.hasOwn(seal.assets, url.pathname)) assetReplies.set(url.pathname, result);
      if (/^\/debug(?:\/|$)/.test(url.pathname) && response.ok()) documents.set(url.pathname, body.toString());
    })();
    responseTasks.add(task); task.catch(error => pageErrors.push('Response capture: ' + error.message)).finally(() => responseTasks.delete(task));
  });
  return context;
}

async function ready(page, path) {
  await page.waitForFunction(path => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.path === path && workspace.dataset.readState === 'ready' && workspace.getAttribute('aria-busy') !== 'true';
  }, path, {timeout: 20_000}); // Matches the real production read timeout, not fixture timing.
}
async function go(page, path) {
  if (!await page.locator('#debug-go').isVisible()) await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  const input = page.locator('#debug-go input');
  await input.fill(path); await input.press('Enter'); await ready(page, path);
}
async function capture(page, name) {
  await page.waitForFunction(() => {
    const roots = [document];
    for (let i = 0; i < roots.length; i++) for (const element of roots[i].querySelectorAll('*')) {
      if (element.localName === 'ui-reveal' && element.matches(':state(entering),:state(leaving)')) return false;
      if (element.shadowRoot) roots.push(element.shadowRoot);
    }
    return true;
  }, null, {timeout: 5000});
  const geometry = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
    title: document.querySelector('.wb-document-title')?.getBoundingClientRect().toJSON()}));
  assert.ok(geometry.scroll <= geometry.width + 1, name + ': no document overflow');
  assert.ok(geometry.title?.width > 0 && geometry.title?.height > 0, name + ': real title is visible');
  const path = resolve(output, name + '.png'); await page.screenshot({path}); screenshots.push(path);
}
async function sourceDocument(page, path) {
  await Promise.all([...responseTasks]);
  const html = documents.get('/debug' + path);
  assert.ok(html, 'Untouched server document captured for ' + path);
  return page.evaluate(html => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return {workspace: {...doc.querySelector('#debug-workspace').dataset},
      children: [...(doc.querySelector('#debug-source-metadata')?.content || doc)
        .querySelectorAll('#debug-children ui-tree-item[data-path]')].map(item => item.dataset.path),
      fields: [...doc.querySelectorAll('#debug-main section[aria-label=Record] sh-myth > sh-limb')].map(limb => ({
        key: limb.querySelector('sh-slot')?.getAttribute('title'), text: limb.querySelector('sh-pail')?.textContent,
        ...limb.dataset,
      })), operations: [...doc.querySelectorAll('#debug-main section[aria-label=Operations] form')].map(form => ({
        action: form.getAttribute('action'), op: form.querySelector('[name=op]')?.getAttribute('value'),
        fields: [...form.querySelectorAll('ui-input[name]')].map(input => ({name: input.getAttribute('name'), type: input.getAttribute('placeholder')})),
      }))};
  }, html);
}
async function exactValue(page, metadata) {
  assert.ok(metadata.valueUrl, 'Real source metadata exposes an immutable exact read');
  const url = new URL(metadata.valueUrl, base);
  assert.equal(url.origin, base); assert.equal(url.pathname, '/debug-read/value');
  allowedValueReads.add(url.pathname + url.search);
  const answer = await page.evaluate(async url => {
    const response = await fetch(url, {signal: AbortSignal.timeout(20_000)});
    return {status: response.status, json: await response.json()};
  }, url.pathname + url.search);
  assert.equal(answer.status, 200);
  const value = answer.json;
  assert.equal(value.version, 1); assert.equal(value.encoding, 'hex'); assert.equal(value.epoch, metadata.valueEpoch);
  assert.equal(value.offset, '0'); assert.equal(value.complete, true); assert.equal(value.next, null);
  assert.equal(value.hex, Buffer.from(metadata.text).toString('hex'));
  return value;
}

try {
  const desktop = await context();
  try {
    const page = await desktop.newPage(); activePage = page;
    await page.goto(base + '/debug/gov/srs'); await ready(page, '/gov/srs');
    const install = page.locator('.wb-semantics form[action="/grove/install"]');
    await install.waitFor();
    const source = await install.locator('input[name=source]').inputValue();
    const version = await install.locator('input[name=version]').inputValue();
    assert.equal(source, '/gov/srs'); assert.match(version, /^[1-9]\d*$/);
    assert.match(await page.locator('#debug-main').innerText(), /Create an independent instance/);
    await capture(page, 'real-template-desktop');
    authorizedInstall = {purpose: 'install', source, version, root: target};
    await install.locator('ui-input[name=root] input').fill(target);
    const installedResponse = page.waitForResponse(response => response.request().method() === 'POST', {timeout: 30_000});
    await install.getByRole('button', {name: 'Install instance', exact: true}).click();
    const installed = await installedResponse;
    assert.equal(installed.status(), 200); assert.match(await installed.text(), /committed;/);
    await page.waitForFunction(() => /^Committed /.test(document.querySelector('#debug-status').textContent) &&
      document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true', null, {timeout: 20_000});
    await ready(page, '/gov/srs');
    checks.push('Real server-authored Install instance form committed exactly the chosen owned target');

    await go(page, cardPath);
    const card = await sourceDocument(page, cardPath);
    const prompt = card.fields.find(field => field.key === '/sys/req');
    const answer = card.fields.find(field => field.key === '/sys/res');
    assert.equal(prompt?.text, 'What does a Shrine name identify?');
    assert.equal(answer?.text, 'A versioned locus of state.');
    assert.match(await page.locator('#debug-main').innerText(), /What does a Shrine name identify/);
    const originalBytes = await exactValue(page, prompt);
    run.card = card; run.originalBytes = originalBytes;
    await capture(page, 'real-card-desktop');
    await page.locator('.wb-slot-key[data-inspect="/sys/req"]').first().click();
    await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.inspectorPath === '/sys/req' &&
      document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true', null, {timeout: 20_000});
    assert.match(await page.locator('.wb-inspector').innerText(), /The request record on a driver-minted node/);
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), cardPath);
    await capture(page, 'real-field-definition');
    await page.locator('#debug-inspector-toggle').click();
    checks.push('Installed starter card and its real slot definition render without fixture replacement');

    await go(page, '/gov/srs/card');
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'role');
    assert.match(await page.locator('#debug-main').innerText(), /Review card/);
    await capture(page, 'real-source-role');
    await go(page, '/gov/srs/finish');
    const action = await sourceDocument(page, '/gov/srs/finish');
    assert.equal(action.workspace.kind, 'action');
    assert.match(await page.locator('#debug-main').innerText(), /Finish review/);
    run.action = action;
    run.gradeWorkflow = card.operations.some(operation => /finish|grade/i.test(operation.op || ''))
      ? 'A server-authored candidate exists; execution requires separate exact schema review'
      : 'No registered grading form exists on the real installed card; compiled /gov/srs/finish metadata is not an executable /op form';
    // Never infer an operation payload from a compiled declaration or a legacy demo.
    await capture(page, 'real-source-action');
    const queuePath = '/x' + target + '/next';
    await go(page, queuePath);
    assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), 'false');
    const queue = await sourceDocument(page, queuePath); run.queue = queue;
    assert.deepEqual(queue.children, [queuePath + '/0'], 'The real sewn queue exposes the installed starter card');
    // /x treats its entire tail as the defining datum, not as a subtree
    // address. The resolver's /h framing separates target from result path.
    // This newly installed defining datum has exactly its first local case.
    const pinnedQueue = '/h/z/1/4' + queuePath;
    await go(page, pinnedQueue);
    const queuedRow = page.locator('.wb-child-row[data-path="' + pinnedQueue + '/0"]');
    await queuedRow.locator('[part="toggle"]').click();
    await queuedRow.locator('[data-preview-path][data-loaded=true]').waitFor({timeout: 20_000});
    assert.match(await queuedRow.locator('.wb-child-preview').innerText(), /What does a Shrine name identify/);
    await capture(page, 'real-derived-queue');
    checks.push('Actual source role/action and read-only sewn queue are distinguishable; no speculative grade was sent');

    await go(page, '/gov/srs');
    authorizedInstall = {purpose: 'duplicate-install', source, version, root: target};
    await install.locator('ui-input[name=root] input').fill(target);
    const rejectedResponse = page.waitForResponse(response => response.request().method() === 'POST', {timeout: 30_000});
    await install.getByRole('button', {name: 'Install instance', exact: true}).click();
    const rejected = await rejectedResponse;
    assert.equal(rejected.status(), 409); assert.match(await rejected.text(), /Installation rejected/);
    await ready(page, '/gov/srs');
    assert.equal(await install.locator('ui-input[name=root] input').inputValue(), target, 'Actual rejected installation retains its draft');
    assert.match(await page.locator('#wb-feedback').innerText(), /Operation rejected \(HTTP 409\)/);
    await capture(page, 'real-install-rejection');
    page.once('dialog', async dialog => {
      assert.match(dialog.message(), /discard unsubmitted operation inputs/); await dialog.accept();
    });
    const historical = '/h/x/e' + prompt.valueEpoch + '/4' + cardPath;
    await go(page, historical);
    const old = await sourceDocument(page, historical);
    assert.equal(old.fields.find(field => field.key === '/sys/req')?.text, prompt.text);
    assert.equal(old.workspace.writable, 'false');
    const replayedBytes = await exactValue(page, prompt);
    assert.deepEqual(replayedBytes, originalBytes, 'Original immutable exact-byte URL remains identical after later real reads/rejected install');
    checks.push('Historical epoch document and immutable exact bytes retain the real original card after later workflow activity');

    await page.locator('#wb-feedback').getByRole('button', {name: 'Dismiss notification'}).click();
    await go(page, cardPath);
    await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
    await capture(page, 'real-card-dark');
    await page.emulateMedia({colorScheme: 'light', reducedMotion: 'no-preference'});
    // At compact widths an explicitly open pane occupies the workspace.
    // Close it through the real control before asserting content visibility.
    if (await page.locator('#debug-sidebar-toggle').getAttribute('aria-expanded') === 'true')
      await page.locator('#debug-sidebar-toggle').click();
    await page.setViewportSize({width: 768, height: 1024});
    await capture(page, 'real-card-768');
  } finally { await desktop.close(); }
  const touch = await context({viewport: {width: 390, height: 844}, hasTouch: true});
  try {
    const page = await touch.newPage(); activePage = page;
    await page.goto(base + '/debug' + cardPath); await ready(page, cardPath);
    await capture(page, 'real-card-touch-390');
    await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
    await capture(page, 'real-card-touch-dark-390');
  } finally { await touch.close(); }
  await Promise.all([...responseTasks]);
  assert.equal(postCount, 2);
  assert.deepEqual(unexpected, []); assert.deepEqual(pageErrors, []); assert.deepEqual(failures, []);
  for (const [url, asset] of Object.entries(seal.assets)) assert.equal(assetReplies.get(url)?.sha256, asset.sha256,
    'Actual HTTP-served asset is the exact sealed candidate: ' + url);
  run.passed = true;
  console.log(JSON.stringify({passed: true, requests: requests.length, realOwnedPosts: postCount,
    gradeWorkflow: run.gradeWorkflow, output, checks}, null, 2));
} catch (error) {
  run.failure = error.stack;
  if (activePage && !activePage.isClosed()) await activePage.screenshot({path: resolve(output, 'failure.png')}).catch(() => {});
  console.error(JSON.stringify({failure: error.message, output, requests, replies, unexpected, failures, pageErrors}, null, 2));
  throw error;
} finally {
  await browser.close();
  await Promise.allSettled([...responseTasks]);
  run.finishedAt = new Date().toISOString();
  await writeFile(resolve(output, 'results.json'), JSON.stringify(run, null, 2) + '\n');
}
