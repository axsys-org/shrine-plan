// Read-only checks against real Grove SSR. The install request below is
// intercepted in-browser; it never reaches or mutates the namespace.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.DEBUG_URL || 'http://127.0.0.1:8136';
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
const errors = [], unexpectedWrites = [], installs = [];
let allowInstallFixture = false;
await context.route('**/*', async route => {
  const request = route.request();
  if (['GET', 'HEAD', 'OPTIONS'].includes(request.method())) return route.continue();
  if (allowInstallFixture && new URL(request.url()).pathname === '/grove/install' && request.method() === 'POST') {
    installs.push(new URLSearchParams(request.postData()));
    return route.fulfill({ status: 409, contentType: 'text/plain', body: 'Browser fixture: target already exists.' });
  }
  unexpectedWrites.push(request.method() + ' ' + request.url());
  return route.abort();
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
page.on('dialog', dialog => dialog.accept());
async function ready(path) {
  await page.waitForFunction(path => {
    const workspace = document.querySelector('#debug-workspace');
    return workspace?.dataset.path === path && workspace.dataset.readState === 'ready'
      && workspace.getAttribute('aria-busy') !== 'true';
  }, path, { timeout: 30000 });
}
async function go(path) {
  if (!await page.locator('#debug-go').isVisible())
    await page.getByRole('button', { name: 'Edit namespace path', exact: true }).click();
  await page.locator('#debug-go input').fill(path);
  await page.locator('#debug-go input').press('Enter');
  await ready(path);
}
try {
  await page.goto(base + '/debug/weft');
  await ready('/weft');
  assert.match(await page.locator('#wb-canvas').innerText(), /No components are registered/i);
  assert.equal(await page.locator('#wb-rendered iframe').getAttribute('src'), null);
  await page.locator('#wb-mode-rendered').click();
  assert.equal(await page.locator('#wb-canvas').isVisible(), false);
  assert.equal(await page.locator('#wb-rendered iframe').getAttribute('sandbox'), '');
  assert.equal(await page.locator('#wb-rendered iframe').getAttribute('src'), base + '/ns/weft');
  assert.equal(await page.locator('.wb-render-open').getAttribute('href'), base + '/ns/weft');
  await page.reload();
  await ready('/weft');
  assert.equal(await page.locator('#wb-mode-rendered').getAttribute('aria-pressed'), 'true');
  await page.locator('#wb-mode-inspect').click();
  assert.equal(await page.locator('#wb-canvas').isVisible(), true);
  console.log('PASS: custom faces cannot replace inspection; rendered mode is lazy, passive, and reloadable.');

  await go('/gov/srs/card');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'role');
  const role = await page.locator('.wb-semantics').innerText();
  assert.match(role, /due/);
  assert.match(role, /interval/);
  assert.match(role, /required/);
  assert.equal(await page.locator('.wb-empty').count(), 0);
  assert.equal(await page.locator('.wb-raw-details').count(), 1);
  const exportCount = Number(await page.locator('.wb-semantics [data-key="Exports"] .debug-fact-value').textContent());
  assert.equal(await page.locator('.debug-exports .debug-fact').count(), Math.min(exportCount, 80),
    'short export lists contain no padded declarations');
  await go('/gov/srs/finish');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'action');
  assert.match(await page.locator('.wb-semantics').innerText(), /Receiver role/);
  assert.equal(await page.locator('.wb-semantics a[href="/debug/gov/srs/recall"]').count() > 0, true);
  assert.match(await page.locator('.wb-semantics').innerText(), /grade/);
  assert.match(await page.locator('.wb-semantics').innerText(), /now/);
  assert.equal(await page.locator('#wb-operations form').count(), 0, 'a declaration is not a fabricated runnable operation');
  await go('/gov/srs/queue');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'sewn');
  assert.match(await page.locator('.wb-semantics').innerText(), /Source norm/);
  assert.match(await page.locator('.wb-semantics').innerText(), /Target norm/);
  await go('/gov/srs/cards_by_id');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'norm');
  assert.match(await page.locator('.wb-semantics').innerText(), /Path pattern/);
  console.log('PASS: real Grove roles, actions, norms, and derived views have semantic inspectors.');

  await go('/gov/srs');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'template');
  const seedCount = Number(await page.locator('.wb-semantics [data-key="Instance records"] .debug-fact-value').textContent());
  assert.equal(await page.locator('.debug-seed').count(), Math.min(seedCount, 80),
    'relative instance paths contain exactly the real template seeds');
  const install = page.locator('form[action="/grove/install"]');
  assert.equal(await install.isVisible(), true);
  assert.equal(await install.locator('input[name=source]').inputValue(), '/gov/srs');
  assert.match(await install.locator('input[name=version]').inputValue(), /^\d+$/);
  allowInstallFixture = true;
  await install.locator('input[name=root]').fill('/app/browser-fixture');
  await install.getByRole('button', { name: 'Install instance', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#debug-status').textContent.includes('Operation rejected'));
  assert.equal(installs.length, 1);
  assert.equal(installs[0].get('source'), '/gov/srs');
  assert.equal(installs[0].get('root'), '/app/browser-fixture');
  assert.equal(await install.locator('input[name=root]').inputValue(), '/app/browser-fixture');
  console.log('PASS: the real install form submits its fields and retains rejected drafts (intercepted; no runtime write).');

  await go('/log');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'journal');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), 'false');
  const events = page.locator('.wb-semantics ui-link.debug-event');
  assert.equal(await events.count() > 0, true);
  assert.equal(await events.count() <= 40, true);
  const ids = await page.locator('.debug-event-id').allTextContents();
  assert.deepEqual(ids, [...ids].sort((a, b) => BigInt(a) > BigInt(b) ? -1 : 1));
  const target = (await events.first().getAttribute('href')).slice(6);
  await events.first().click();
  await ready(target);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-kind'), 'event');
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-writable'), 'false');
  assert.match(await page.locator('.wb-semantics').innerText(), /Task/);
  assert.match(await page.locator('.wb-semantics').innerText(), /Outbound effects/);
  const effectCount = Number(await page.locator('.wb-semantics [data-key="Outbound effects"] .debug-fact-value').textContent());
  assert.equal(await page.locator('.debug-effect').count(), Math.min(effectCount, 40),
    'zero and short effect lists must not fabricate rows');
  assert.equal(await page.locator('#wb-operations-toggle').isVisible(), false);
  assert.deepEqual(unexpectedWrites, []);
  assert.deepEqual(errors, []);
  console.log('PASS: bounded newest-first journal, meaningful event details, and read-only journal records.');
} catch (error) {
  console.error('Semantic test context', await page.evaluate(() => ({
    url: location.href, state: {...document.querySelector('#debug-workspace')?.dataset},
    status: document.querySelector('#debug-status')?.textContent,
    content: document.querySelector('#debug-main')?.textContent.slice(0, 1800),
  })), errors);
  throw error;
} finally {
  await browser.close();
}
