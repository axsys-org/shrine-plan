// Render actual compiler-produced Grove output with the real Mash bundle.
// All requests stay inside an inert fixture; never reads a live namespace.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {outputRoot, playwright} from './debug-tooling.mjs';
const evidence = process.env.TEST_RUN_DIR || tmpdir();
const log = await readFile(process.env.GROVE_CHECK_LOG, 'utf8');
assert.match(log, /\("DEBUGGER-DECLARATION-PASS" 19\)/);
assert.doesNotMatch(log, /\("ERROR"/);
function decode(name) {
  const match = log.match(new RegExp('\\("' + name + '"\\s+(\\d+)\\)'));
  assert.ok(match, name);
  let hex = BigInt(match[1]).toString(16); if (hex.length % 2) hex = '0' + hex;
  return Buffer.from(hex.match(/../g).reverse().join(''), 'hex').toString();
}
const shell = decode('DEBUGGER-PAGE-HTML');
const details = decode('DEBUGGER-DETAILS-HTML');
assert.doesNotMatch(shell + details, /x-bad-selector/);
for (const name of ['namespace-row', 'page-row', 'path-segment', 'hover-myth', 'button', 'value-window']) assert.ok(shell.includes('id="debug-template-' + name + '"'), name);
const assets = new Map(await Promise.all([
  ['/debug-mash.js', '.debug-assets/mash.js', 'text/javascript'],
  ['/debug-components.css', '.debug-assets/components.css', 'text/css'],
  ['/debug.css', 'debug.css', 'text/css'], ['/style.css', 'style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {contentType, body: await readFile(resolve(outputRoot,path), 'utf8')}])));
const compiled = {outputFiles:[{text:await readFile(resolve(outputRoot,'debug.js'),'utf8')}]};
const html = body => '<!doctype html><html data-mash-catalogue="mash"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/debug-components.css"><link rel="stylesheet" href="/debug.css"><script defer src="/debug-mash.js"></script><script defer src="/debug.js"></script></head><body>' + body + '</body></html>';
const {chromium} = playwright();
const browser = await chromium.launch();
const checks = [], errors = [], violations = [], factories = [];
const base = 'http://grove-declaration.invalid';
try {
  for (const [name, app, width, touch, colorScheme] of [['mash-only',false,1440,false,'light'],['desktop',true,1440,false,'light'],['dark',true,1440,false,'dark'],['touch',true,390,true,'light'],['cases',true,1440,false,'light'],['legacy-view',true,1440,false,'light']]) {
    const context = await browser.newContext({viewport: {width, height: 1000}, hasTouch: touch, isMobile: touch, colorScheme, reducedMotion: 'reduce'});
    context.setDefaultTimeout(5000);
    await context.addInitScript(() => {
      if (location.origin !== 'http://grove-declaration.invalid') return;
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({root:'/hello',expanded:['/hello'],saved:true,recent:false,tree:true}));
      localStorage.setItem('shrine-debug.v1.saved', JSON.stringify(['/hello']));
    });
    await context.route('**/*', route => {
      const req = route.request(), url = new URL(req.url());
      if (req.method() !== 'GET' || url.origin !== base || (url.search && !(name === 'legacy-view' && url.search === '?view=rendered'))) { violations.push(req.url()); return route.abort(); }
      if (url.pathname === '/debug.js') {
        const capture = `window.__serverNodes=[...document.querySelectorAll('.debug-header,#wb-path-locator,#debug-history-nav,#wb-header-actions,#debug-sidebar,#debug-main,#wb-canvas,.wb-inspector,#wb-path-menu,#wb-action-tooltip,#wb-path-preview')];window.__factories=[];const originalCreate=document.createElement;document.createElement=function(...args){const caller=new Error().stack?.split('\\n')[2];if(caller?.includes('/debug.js'))__factories.push([args[0],caller]);return originalCreate.apply(this,args)};\n`;
        return route.fulfill({contentType:'text/javascript', body: app ? capture + compiled.outputFiles[0].text : ''});
      }
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (url.pathname === '/debug/hello') {
        let body = shell;
        if (name === 'cases') {
          const start = body.indexOf('<div class="wb-inspector"'), end = body.indexOf('<template id="debug-source-metadata"');
          assert.ok(start > 0 && end > start);
          body = body.slice(0,start) + details + body.slice(end);
        }
        return route.fulfill({contentType:'text/html',body:html(body)});
      }
      if (url.pathname === '/favicon.ico') return route.fulfill({status:204,body:''});
      violations.push(url.pathname); return route.abort();
    });
    const page = await context.newPage(); page.on('pageerror', e => errors.push(name + ': ' + e.message));
    await page.goto(base + '/debug/hello' + (name === 'legacy-view' ? '?view=rendered' : ''));
    await page.waitForFunction(() => document.querySelector('sh-triptych')?.shadowRoot && customElements.get('ui-menu'));
    assert.equal(await page.locator('[data-grove-contract="debugger/v1"]').count(),1);
    assert.match(await page.locator('#debug-main').innerText(), /An authored slot/);
    const source = page.locator('#wb-canvas > section[aria-label=Record] ui-accordion-item[value=source]');
    await source.locator('button').first().click();
    assert.equal(await source.evaluate(el => el.open),true,'Mash owns the authored disclosure');
    if (app) {
      await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.readState === 'ready');
      assert.equal(await page.locator('#wb-canvas').isVisible(),true,'native inspection remains visible');
      assert.equal(new URL(page.url()).searchParams.has('view'),false,'retired view state is normalized');
      assert.deepEqual(errors,[], 'initialization errors');
      await page.screenshot({path:resolve(evidence,'grove-declaration-' + name + '.png')});
      assert.equal(await page.evaluate(() => __serverNodes.length > 8 && __serverNodes.every(n => n.isConnected)),true,'Grove node identity survives data binding');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1),true,'no document horizontal overflow');
      if (name === 'cases') {
        await page.locator('#debug-inspector-toggle').click();
        const x = page.locator('.wb-inspector [data-care=x]');
        assert.equal(await x.locator('.wb-case-link').count(),5);
        assert.equal(await x.locator('.wb-case-link').last().textContent(),'900719925474099312345');
        assert.match(await page.locator('.wb-inspector [data-care=y]').innerText(),/No cases/);
        assert.match(await page.locator('.wb-inspector [data-care=z]').innerText(),/Not reported/);
        await x.locator('[data-case-older]').click();
        assert.equal(await x.locator('.wb-case-link').count(),5);
        assert.equal(await x.locator('.wb-case-link').last().textContent(),'900719925474099312340');
        await x.locator('[data-case-newer]').click();
        assert.equal(await x.locator('.wb-case-link').last().textContent(),'900719925474099312345');
        assert.equal(await x.locator('[data-case-newer]').evaluate(el=>el.disabled),true);
      }
      if (!touch) {
        const row = page.locator('#debug-path-tree ui-tree-item[data-path="/hello"]');
        await row.waitFor();
        const geometry = await row.evaluate(el => {const b=el.shadowRoot.querySelector('[part=control]');return {height:b.getBoundingClientRect().height,radius:getComputedStyle(b).borderRadius};});
        assert.equal(geometry.radius,'8px'); assert.equal(geometry.height,24);
        await row.locator('button[role=treeitem]').first().hover();
        await page.waitForFunction(() => document.querySelector('#wb-path-preview').open);
        assert.match(await page.locator('#wb-path-preview').innerText(), /Hello namespace|hello/);
        await page.keyboard.press('Escape');
        await row.locator('button[role=treeitem]').first().click({button:'right'});
        await page.waitForFunction(() => document.querySelector('#wb-path-menu').open);
        assert.equal(await page.locator('#wb-path-menu ui-menu-item').count(),2);
        await page.keyboard.press('Escape');
      }
      factories.push(...await page.evaluate(() => __factories.map(x=>[...x])));
    }
    await page.screenshot({path:resolve(evidence,'grove-declaration-' + name + '.png')});
    checks.push(name); await context.close();
  }
  assert.deepEqual(errors,[]); assert.deepEqual(violations,[]);
  assert.deepEqual(factories,[], 'Application must bind declarations, not call createElement');
  const missing = await browser.newContext();
  const rejected = [];
  await missing.route('**/*', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/debug.js') return route.fulfill({contentType:'text/javascript',body:compiled.outputFiles[0].text});
    return route.fulfill({contentType:'text/html',body:'<!doctype html><script src="/debug.js"></script><main>Legacy document</main>'});
  });
  const absent = await missing.newPage();
  absent.on('pageerror', error => rejected.push(error.message));
  await absent.goto(base + '/missing-declaration');
  await absent.waitForFunction(() => document.readyState === 'complete');
  assert.equal(rejected.length,1);
  assert.match(rejected[0], /Grove debugger declaration missing/);
  assert.equal(await absent.locator('sh-triptych,ui-tree').count(),0,'no legacy document enhancement');
  await missing.close();
  checks.push('missing declaration rejected');
  console.log(JSON.stringify({passed:checks,liveGETs:0,errors,violations,factories}));
} finally {await browser.close();}
