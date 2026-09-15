// Real pointer and keyboard checks for the Mash-composed debugger panels.
// Each browser context is disposable; every runtime write is intercepted.
import assert from 'node:assert/strict';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.DEBUG_URL || 'http://127.0.0.1:8138';
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 960}});
const writes = [], errors = [];
await context.route('**/*', async route => {
  if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
    writes.push(route.request().url());
    return route.abort();
  }
  return route.continue();
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
const workspace = page.locator('#debug-workspace');
const panel = name => page.locator(`#debug-workspace ui-resizable-panel[part="${name}"]`);
const handle = name => page.locator(`#debug-workspace ui-resizable-handle[part="${name}-resizer"] [role="separator"]`);
const width = name => panel(name).evaluate(el => el.getBoundingClientRect().width);
const near = (actual, expected, message) => assert.ok(Math.abs(actual - expected) <= 1, `${message}: ${actual} ≈ ${expected}`);
const frame = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
async function ready() {
  await page.waitForFunction(() => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  });
  await frame();
  // Let the real initial namespace read finish before this suite deliberately
  // reloads the page; other suites separately exercise request cancellation.
  await page.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor();
}
async function openInspector() {
  if (!await workspace.evaluate(el => el.inspectorOpen))
    await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  await page.locator('.wb-inspector').waitFor();
  await frame();
}
async function drag(name, delta) {
  const bounds = await handle(name).boundingBox();
  assert.ok(bounds && bounds.width >= 6 && bounds.height > 200, name + ' has a usable full-height resize edge');
  const start = {x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2};
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + delta, start.y + 12, {steps: 12});
  assert.equal(await workspace.evaluate(el => el.matches(':state(resizing)')), true, name + ' captures the active drag');
  await page.mouse.up();
  await frame();
  assert.equal(await workspace.evaluate(el => el.matches(':state(resizing)')), false, name + ' ends the active drag');
}
async function noOverflow() {
  const sizes = await page.evaluate(() => {
    const ws = document.querySelector('#debug-workspace');
    const root = ws.shadowRoot;
    return {
      page: document.documentElement.scrollWidth, viewport: innerWidth,
      shell: root.querySelector('[part="shell"]').getBoundingClientRect().width,
      main: root.querySelector('[part="main"]').getBoundingClientRect().width,
      mainMin: ws.mainMinWidth,
    };
  });
  assert.ok(sizes.page <= sizes.viewport + 1, 'the document never horizontally overflows');
  if (sizes.viewport > 832) assert.ok(sizes.main >= sizes.mainMin - 1, 'resizing preserves a usable main workspace');
}
async function paneStorage() {
  return page.evaluate(() => JSON.parse(localStorage.getItem('shrine-debug:pane-widths') || '{}'));
}

try {
  await page.goto(base + '/debug/app'); await ready();
  await openInspector();
  assert.equal(await workspace.evaluate(el => el.matches(':state(resizable)')), true);
  const defaults = {sidebar: await width('sidebar'), inspector: await width('inspector')};
  await page.evaluate(() => {
    const input = document.createElement('input');
    input.setAttribute('aria-label', 'Browser-only panel preservation fixture');
    input.value = 'Unsent browser-local draft';
    document.querySelector('#wb-canvas').append(input);
    window.__panelDraftFixture = input;
    window.__panelContentFixture = document.querySelector('#debug-workspace').shadowRoot.querySelector('[part="main-body"]');
  });

  await drag('sidebar', 64);
  near(await width('sidebar'), defaults.sidebar + 64, 'sidebar follows the pointer');
  await drag('inspector', -56);
  near(await width('inspector'), defaults.inspector + 56, 'inspector follows a leftward pointer drag');
  assert.equal(await page.evaluate(() => document.querySelector('[aria-label="Browser-only panel preservation fixture"]') === window.__panelDraftFixture), true);
  assert.equal(await page.evaluate(() => document.querySelector('#debug-workspace').shadowRoot.querySelector('[part="main-body"]') === window.__panelContentFixture), true);
  assert.equal(await page.getByRole('textbox', {name: 'Browser-only panel preservation fixture'}).inputValue(), 'Unsent browser-local draft');
  await noOverflow();
  console.log('PASS: both real pointer drags, captured edges, flexible content, and unsent DOM state preservation.');

  const keyboardBefore = {sidebar: await width('sidebar'), inspector: await width('inspector')};
  await handle('sidebar').focus(); await handle('sidebar').press('ArrowRight'); await frame();
  near(await width('sidebar'), keyboardBefore.sidebar + 8, 'sidebar keyboard step');
  assert.equal(await handle('sidebar').getAttribute('aria-valuenow'), String(Math.round(await width('sidebar'))));
  assert.equal(await handle('sidebar').getAttribute('aria-controls'), await panel('sidebar').getAttribute('id'));
  await handle('inspector').focus(); await handle('inspector').press('ArrowLeft'); await frame();
  near(await width('inspector'), keyboardBefore.inspector + 8, 'inspector keyboard step');
  // Inspector controls must announce the inspector itself, not the main width.
  assert.equal(await handle('inspector').getAttribute('aria-valuenow'), String(Math.round(await width('inspector'))));
  assert.equal(await handle('inspector').getAttribute('aria-controls'), await panel('inspector').getAttribute('id'));
  assert.notEqual(await handle('inspector').evaluate(el => getComputedStyle(el).outlineStyle), 'none', 'keyboard focus is visible');
  const stored = await paneStorage();
  near(stored.sidebarWidth, await width('sidebar'), 'sidebar width persists');
  near(stored.inspectorWidth, await width('inspector'), 'inspector width persists');
  await page.reload(); await ready(); await openInspector();
  near(await width('sidebar'), stored.sidebarWidth, 'sidebar reload persistence');
  near(await width('inspector'), stored.inspectorWidth, 'inspector reload persistence');
  console.log('PASS: keyboard resizing, accurate accessible ranges, focus indication, and reload persistence.');

  await drag('sidebar', 1200);
  near(await width('sidebar'), await workspace.evaluate(el => el.sidebarMaxWidth), 'sidebar maximum');
  await drag('sidebar', -1200);
  near(await width('sidebar'), await workspace.evaluate(el => el.sidebarMinWidth), 'sidebar minimum');
  await drag('inspector', -1200);
  near(await width('inspector'), await workspace.evaluate(el => el.inspectorMaxWidth), 'inspector maximum');
  await drag('inspector', 1200);
  near(await width('inspector'), await workspace.evaluate(el => el.inspectorMinWidth), 'inspector minimum');
  await noOverflow();
  await handle('sidebar').dblclick(); await frame();
  await handle('inspector').dblclick(); await frame();
  near(await width('sidebar'), defaults.sidebar, 'sidebar double-click reset');
  near(await width('inspector'), defaults.inspector, 'inspector double-click reset');
  assert.deepEqual(await paneStorage(), {sidebarWidth: defaults.sidebar, inspectorWidth: 0}, 'the latest reset preserves the other pane and stores the reset sentinel');
  console.log('PASS: min/max constraints and double-click reset without document overflow.');

  await drag('sidebar', 40); await drag('inspector', -40);
  const desktop = {sidebar: await width('sidebar'), inspector: await width('inspector')};
  const desktopStorage = await paneStorage();
  await page.setViewportSize({width: 390, height: 844}); await frame();
  assert.equal(await workspace.evaluate(el => el.sidebarOpen && !el.inspectorOpen), true,
    'entering mobile with both desktop panes open keeps only the sidebar active');
  assert.equal(await workspace.evaluate(el => el.matches(':state(resizable)')), false);
  assert.equal(await page.locator('#debug-workspace ui-resizable-handle').count(), 0);
  await noOverflow();
  if (!await page.locator('#debug-main').isVisible()) {
    await page.getByRole('button', {name: 'Toggle sidebar', exact: true}).click();
  }
  assert.equal(await page.locator('#debug-main').isVisible(), true, 'mobile has usable full-width content');
  await page.getByRole('button', {name: 'Toggle sidebar', exact: true}).click();
  assert.equal(await page.locator('#debug-sidebar').isVisible(), true);
  assert.equal(await page.locator('#debug-main').isVisible(), false);
  await page.getByRole('button', {name: 'Toggle inspector', exact: true}).click();
  assert.equal(await page.locator('.wb-inspector').isVisible(), true);
  assert.equal(await page.locator('#debug-sidebar').isVisible(), false);
  assert.equal(await page.locator('#debug-main').isVisible(), false);
  assert.deepEqual(await paneStorage(), desktopStorage, 'mobile mode never replaces preferred widths');
  await page.screenshot({path: '/private/tmp/shrine-panels-mobile.png'});
  await page.setViewportSize({width: 1440, height: 960}); await frame();
  if (!await workspace.evaluate(el => el.sidebarOpen))
    await page.getByRole('button', {name: 'Toggle sidebar', exact: true}).click();
  await openInspector(); await frame();
  near(await width('sidebar'), desktop.sidebar, 'desktop sidebar restores after mobile');
  near(await width('inspector'), desktop.inspector, 'desktop inspector restores after mobile');
  await noOverflow();
  await page.locator('#debug-path-tree ui-tree-item[data-path="/app"]').waitFor();
  await page.screenshot({path: '/private/tmp/shrine-panels-desktop.png'});
  assert.deepEqual(writes, []);
  assert.deepEqual(errors, []);
  console.log('PASS: single-pane mobile, desktop width recovery, zero runtime writes and zero page errors.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-panels-failure.png'}).catch(() => {});
  throw error;
} finally {
  await browser.close();
}
