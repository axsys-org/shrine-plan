// Isolated action-hint fixture. Every request is fulfilled from source/assets
// or aborted; this script never reads a namespace or starts a runtime.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const root = fileURLToPath(new URL('..', import.meta.url));
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = 'http://tooltip-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/tooltips.js', 'src/foil/debug/tooltips.js', 'application/javascript'],
].map(async ([url, file, contentType]) => [url, {contentType, body: await readFile(resolve(root, file))}])));
const html = `<!doctype html><html data-mash-catalogue="mash"><head><meta charset="utf-8">
  <link rel="stylesheet" href="/debug-components.css"><link rel="stylesheet" href="/debug.css">
  <script defer src="/debug-mash.js"></script>
  <style>body{margin:0;padding:64px 24px;display:block;background:var(--color-surface);color:var(--color-text)}#fixture-actions{display:flex;gap:16px;align-items:center}#fixture-focus{display:block;margin-block:96px}</style>
  </head><body>
  <div id="fixture-actions">
    <ui-button id="wb-path-edit" aria-label="Edit namespace path" title="Edit namespace path · /" icon-only size="compact" variant="ghost" tone="neutral"><ui-icon name="action.edit"></ui-icon></ui-button>
    <ui-button id="wb-refresh" aria-label="Refresh current record" title="Refresh current record" icon-only size="compact" variant="ghost" tone="neutral"><ui-icon name="action.refresh"></ui-icon></ui-button>
    <ui-button id="fixture-path" data-path-tooltip="/demo" aria-label="Inspect slot definition /demo" title="Authored path title" icon-only size="compact"><ui-icon name="object.code"></ui-icon></ui-button>
    <ui-button id="fixture-disabled" aria-label="Disabled action" title="Disabled action" disabled icon-only><ui-icon name="action.edit"></ui-icon></ui-button>
  </div>
  <ui-button id="fixture-text" aria-label="Inspect" title="" size="small">Inspect</ui-button>
  <button id="fixture-focus">Unrelated focus target</button>
  <ui-tree-item id="semantic-item" title="Authored tree title"></ui-tree-item>
  <sh-myth id="semantic-record" title="Authored record title"></sh-myth>
  <script type="module">
    await customElements.whenDefined('ui-tooltip'); await customElements.whenDefined('ui-button');
    const {createTooltips} = await import('/tooltips.js');
    window.createTooltips = createTooltips;
    window.resolveFixturePath = element => element.closest('[data-path-tooltip]')?.dataset.pathTooltip || null;
    window.hints = createTooltips({resolvePath: window.resolveFixturePath});
    window.ownerEscapes = 0;
    document.addEventListener('keydown', event => {if(event.key==='Escape'&&!event.defaultPrevented) window.ownerEscapes++;});
    window.originalNodes = [...document.querySelectorAll('#fixture-actions ui-button')];
    window.fixtureReady = true;
  </script></body></html>`;
const browser = await chromium.launch();
const unexpected = [], errors = [];
let assertions = 0;
const equal = (actual, expected, message) => { assert.equal(actual, expected, message); assertions++; };
try {
  for (const options of [{width:1440, colorScheme:'light'}, {width:390, colorScheme:'dark', hasTouch:true, reducedMotion:'reduce'}]) {
    const {width, ...contextOptions} = options;
    const context = await browser.newContext({viewport:{width,height:720}, ...contextOptions});
    context.setDefaultTimeout(5000);
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET' || url.origin !== base) { unexpected.push(request.method() + ' ' + request.url()); return route.abort(); }
      if (url.pathname === '/') return route.fulfill({contentType:'text/html',body:html});
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (url.pathname === '/favicon.ico') return route.fulfill({status:204});
      unexpected.push(request.url()); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.waitForFunction(() => window.fixtureReady, null, {timeout:5000});
    const tip = page.locator('#wb-action-tooltip');
    const edit = page.locator('#wb-path-edit button');
    const refresh = page.locator('#wb-refresh button');
    const open = () => page.waitForFunction(() => document.querySelector('#wb-action-tooltip').open, null, {timeout:5000});
    const closed = () => page.waitForFunction(() => !document.querySelector('#wb-action-tooltip').open, null, {timeout:5000});
    equal(await page.evaluate(() => window.createTooltips({resolvePath:window.resolveFixturePath}) === window.hints), true, 'one controller per document');
    await edit.focus(); await open();
    equal(await tip.locator('ui-kbd').getAttribute('shortcut'), 'Primary+L', 'Mash owns the real path-editor shortcut');
    equal(await page.locator('#wb-path-edit').getAttribute('title'), '', 'empty title blocks inherited native bubbles');
    equal(await edit.getAttribute('title'), '', 'native control also blocks title inheritance');
    const description = await edit.evaluate(control => (control.ariaDescribedByElements || []).map(node => ({text:node.textContent,own:node.getRootNode()===control.getRootNode()})));
    assert.ok(description.some(value => value.own && /Edit namespace path/.test(value.text) && /Control or Command plus L/.test(value.text))); assertions++;
    equal(await tip.locator('.wb-tooltip-detail').count(), 0, 'no verbose second description');
    equal(await edit.evaluate(control => control.getRootNode().activeElement === control), true, 'opening does not move native focus');
    await edit.press('Escape'); await closed();
    equal(await page.evaluate(() => window.ownerEscapes),1,'passive hint dismissal preserves its owning surface’s Escape');
    equal(await page.locator('#wb-path-edit').getAttribute('title'), '', 'dismiss cannot summon a competing native bubble');
    equal(await edit.getAttribute('title'), '', 'native suppression survives Escape');
    equal(await edit.evaluate(control => (control.ariaDescribedByElements || []).length), 0, 'dismiss removes only the owned description');
    await refresh.focus(); await open();
    equal(await tip.locator('ui-kbd').count(), 0, 'refresh does not invent a shortcut');
    equal(await page.locator('#wb-path-edit').getAttribute('title'), '', 'retargeting leaves native hints suppressed');
    await page.evaluate(() => document.querySelector('#wb-refresh').setAttribute('aria-label', 'Refresh exact current record'));
    await page.waitForFunction(() => document.querySelector('.wb-tooltip-heading').textContent.includes('Refresh exact current record'), null, {timeout:5000});
    await page.evaluate(() => document.querySelector('#wb-refresh').disabled = true); await closed();
    equal(await refresh.evaluate(control => (control.ariaDescribedByElements || []).length), 0, 'a newly disabled action loses the stale hint');
    await page.evaluate(() => document.querySelector('#wb-refresh').disabled = false);
    await page.locator('#fixture-path button').focus(); await closed();
    equal(await page.locator('#fixture-path').getAttribute('title'), 'Authored path title', 'path targets belong to record previews, not action hints');
    equal(await page.locator('#semantic-item').getAttribute('title'), 'Authored tree title', 'semantic tree titles are untouched');
    equal(await page.locator('#semantic-record').getAttribute('title'), 'Authored record title', 'semantic myth titles are untouched');
    await page.locator('#fixture-text button').focus(); await closed();
    equal(await tip.evaluate(element => element.open), false, 'visible text controls do not get redundant action hints');
    for (const eventName of ['debug:navigation-start','debug:inspect-start','debug:read-complete']) {
      await edit.focus(); await open();
      await page.evaluate(name => document.dispatchEvent(new CustomEvent(name)), eventName); await closed();
      await page.locator('#fixture-focus').focus();
    }
    for (const kind of ['menu','preview']) {
      await edit.focus(); await open();
      await page.evaluate(kind => document.dispatchEvent(new CustomEvent('debug:path-overlay-open',{detail:{kind}})), kind); await closed();
      await page.locator('#fixture-focus').focus();
    }
    await edit.focus(); await open();
    await page.evaluate(() => {
      const menu = document.createElement('ui-menu'); menu.id='fixture-menu'; document.body.append(menu);
      menu.open=true; menu.dispatchEvent(new CustomEvent('ui-menu-open-change',{bubbles:true,composed:true,detail:{open:true}}));
    }); await closed();
    await refresh.focus();
    equal(await tip.evaluate(element => element.open), false, 'an open menu suppresses competing action hints');
    await page.evaluate(() => document.querySelector('#fixture-menu').remove());
    await edit.focus(); await open();
    await page.waitForFunction(() => document.querySelector('#wb-action-tooltip').matches(':state(active)'),null,{timeout:5000});
    const shortcut = await tip.locator('ui-kbd').evaluate(element => ({light:element.textContent,keys:[...element.shadowRoot.querySelectorAll('[part~=key]')].map(key=>key.textContent.trim())}));
    equal(shortcut.light,'','no fallback prose replaces Mash’s generated shortcut');
    assert.ok(shortcut.keys.includes('L') && shortcut.keys.length===2,'Mash renders the actual platform shortcut keys'); assertions++;
    await page.screenshot({path:'/private/tmp/shrine-action-tooltips-'+options.colorScheme+'-'+width+'.png'});
    const rect = await tip.locator('[part=popup]').boundingBox();
    assert.ok(rect.height <= 23, 'action hint is a single compact help tag: ' + rect.height); assertions++;
    equal(await tip.locator('[part=popup]').evaluate(el => getComputedStyle(el).fontSize), '11px', 'shared tooltip typography');
    assert.ok(rect && rect.x>=0 && rect.x+rect.width<=width+1 && rect.y>=0 && rect.y+rect.height<=721, 'rich hint stays in the viewport'); assertions++;
    await page.locator('#fixture-focus').focus(); await closed();
    if (!options.hasTouch) {
      await edit.hover(); await open();
      // Popup text is passive but can be hovered without losing the hint.
      await tip.locator('[part=popup]').hover(); equal(await tip.evaluate(element => element.open),true,'tooltip remains hoverable');
      await page.mouse.move(width-5,715); await closed();
    } else {
      await edit.tap(); await closed();
      equal(await tip.evaluate(element => element.open),false,'touch activation does not summon a hover hint');
    }
    await page.evaluate(() => {
      const control=document.querySelector('#wb-refresh'); control.focus();
    }); await open();
    await page.evaluate(() => document.querySelector('#wb-refresh').remove()); await closed();
    equal(await page.evaluate(() => window.originalNodes.filter(node=>node.isConnected).every(node=>node.parentElement.id==='fixture-actions')),true,'control identity and parentage survive all hints');
    await page.evaluate(() => window.hints.destroy());
    equal(await tip.count(),0,'destroy removes the single tooltip');
    equal(await page.locator('#wb-path-edit').getAttribute('title'),'Edit namespace path · /','destroy preserves original action titles');
    await edit.focus(); equal(await page.locator('ui-tooltip').count(),0,'destroy removes delegated listeners');
    await context.close();
  }
  assert.deepEqual(unexpected,[],'no namespace, write, or external request occurred');
  assert.deepEqual(errors,[],'no browser errors occurred');
  console.log('PASS: '+assertions+' rich Mash tooltip assertions across light/fine and dark/coarse/reduced-motion; zero runtime requests.');
} finally { await browser.close(); }
