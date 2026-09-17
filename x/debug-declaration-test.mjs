// Render actual compiler-produced Grove output with the real Mash bundle.
// All requests stay inside an inert fixture; never reads a live namespace.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {outputRoot, playwright, esbuild, root} from './debug-tooling.mjs';
const evidence = process.env.TEST_RUN_DIR || tmpdir();
const log = await readFile(process.env.GROVE_CHECK_LOG, 'utf8');
assert.match(log, /"DEBUGGER-DECLARATION-PASS"/);
assert.match(log, /"DEBUGGER-APPLICATION-PASS"/);
assert.doesNotMatch(log, /\("ERROR"/);
function decode(name) {
  const match = log.match(new RegExp('\\("' + name + '"\\s+(\\d+)\\)'));
  assert.ok(match, name);
  let hex = BigInt(match[1]).toString(16); if (hex.length % 2) hex = '0' + hex;
  return Buffer.from(hex.match(/../g).reverse().join(''), 'hex').toString();
}
const shell = decode('DEBUGGER-PAGE-HTML');
const details = decode('DEBUGGER-DETAILS-HTML');
const document = decode('DEBUGGER-DOCUMENT-HTML');
const edge = decode('DEBUGGER-EDGE-HTML');
assert.ok(document.includes(shell), 'HTTP framing preserves the Grove page');
assert.doesNotMatch(document, /href="\/style\.css"|<style\b/);
assert.match(document, /href="\/debug-components\.css"/);
assert.match(document, /href="\/debug\.css"/);
assert.doesNotMatch(shell + details, /x-bad-selector/);
assert.doesNotMatch(shell, /id="debug-source-metadata"|id="debug-version-metadata"/, 'no presentation-shaped transport copies');
assert.match(shell, /class="debug-shell"[^>]*data-mash-size="compact"/, 'Grove owns the coordinated Mash density');
assert.doesNotMatch(shell, /id="wb-rendered"|class="wb-render-frame"|<iframe\b/, 'no retired Preview declaration');
for (const name of ['namespace-row', 'page-row', 'path-segment', 'hover-myth', 'button', 'value-window']) assert.ok(shell.includes('id="debug-template-' + name + '"'), name);
const assets = new Map(await Promise.all([
  ['/debug-mash.js', '.debug-assets/mash.js', 'text/javascript'],
  ['/debug-components.css', '.debug-assets/components.css', 'text/css'],
  ['/debug.css', 'debug.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {contentType, body: await readFile(resolve(outputRoot,path), 'utf8')}])));
const compiled = {outputFiles:[{text:await readFile(resolve(outputRoot,'debug.js'),'utf8')}]};
const parser = await esbuild().build({entryPoints:[resolve(root,'src/foil/debug/namespace.js')],bundle:true,write:false,format:'esm'});
const parserURL = 'data:text/javascript;base64,' + Buffer.from(parser.outputFiles[0].text).toString('base64');
const html = body => document.replace(shell, () => body);
const {chromium} = playwright();
const browser = await chromium.launch();
const checks = [], errors = [], violations = [], factories = [];
const base = 'http://grove-declaration.invalid';
try {
  // The model must come only from the versioned descriptor. Deliberately
  // contradictory presentation proves this is not another HTML scraper.
  const contractPage = await browser.newPage();
  await contractPage.route('**/*', route => route.abort());
  const contract = await contractPage.evaluate(async ({parserURL, shell, edge, framedHtml}) => {
    const {parseDebugDocument} = await import(parserURL);
    const huge = '900719925474099312345';
    const descriptor = {version:1,path:'/0x11/example',namespaceRoot:'/0x11',scope:'document',kind:'custom-kind',
      glyph:'object.document',label:'Authored label',description:'Authored help',state:'live',hasRecord:true,writable:false,
      children:[{path:'/0x11/example/child',label:'Child',description:'Child help',kind:'custom-child',glyph:'object.folder'}],
      collection:{epoch:huge,nextChildren:null,nextSlots:null,childCount:huge,slotCount:huge},pagination:null,
      previewSlots:[{key:'/opaque/slot',text:'summary',reference:null}]};
    const escape = text => text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    const template = value => '<template id="debug-read-descriptor">' + escape(JSON.stringify(value)) + '</template>';
    const workspace = (content,path='/0x11/example') => '<sh-triptych id="debug-workspace" data-path="' + path + '">' + content + '</sh-triptych>';
    const document = content => new DOMParser().parseFromString(content,'text/html');
    const clean = parseDebugDocument(document(workspace(template(descriptor))));
    const distracting = '<main id="debug-main"><section aria-label="Record"><sh-myth><sh-limb data-value-kind="text">' +
      '<sh-slot title="/sys/lede"></sh-slot><sh-pail>Wrong label</sh-pail></sh-limb></sh-myth></section>' +
      '<section aria-label="Operations"><form action="/wrong"><button type="submit">Wrong operation</button></form></section></main>' +
      '<ui-table label="version"><ui-table-row><ui-table-cell>/x_data</ui-table-cell><ui-table-cell>1</ui-table-cell></ui-table-row></ui-table>';
    const noisy = parseDebugDocument(document(workspace(distracting + template(descriptor))));
    const failures = [];
    const rejects = (name, markup) => { try {parseDebugDocument(document(markup)); failures.push(name);} catch {} };
    rejects('missing', workspace(distracting));
    rejects('malformed JSON', workspace('<template id="debug-read-descriptor">{broken</template>' + distracting));
    rejects('unsupported version', workspace(template({...descriptor,version:2})));
    rejects('identity mismatch', workspace(template({...descriptor,path:'/0x11/other'})));
    rejects('nested descriptor', workspace('<div>' + template(descriptor) + '</div>'));
    rejects('duplicate descriptor', workspace(template(descriptor) + template(descriptor)));
    rejects('numeric epoch', workspace(template({...descriptor,collection:{...descriptor.collection,epoch:Number(huge)}})));
    rejects('non-child path', workspace(template({...descriptor,children:[{...descriptor.children[0],path:'/0x11/elsewhere'}]})));
    rejects('oversized child page', workspace(template({...descriptor,children:Array.from({length:41},(_,index)=>
      ({...descriptor.children[0],path:'/0x11/example/child-' + index}))})));
    rejects('live state without record', workspace(template({...descriptor,hasRecord:false,previewSlots:[]})));
    rejects('tombstone state with record', workspace(template({...descriptor,state:'tombstone',previewSlots:[]})));
    const journal = {...descriptor,path:'/0x11/log',kind:'journal',hasRecord:false,state:'structural',previewSlots:[],
      children:[{...descriptor.children[0],path:'/0x11/log/' + huge}],
      collection:{...descriptor.collection,childCount:'1'},
      pagination:{kind:'journal',before:null,nextBefore:null,limit:1,total:'1',epoch:huge}};
    const journalView = parseDebugDocument(document(workspace(template(journal),journal.path)));
    rejects('journal total mismatch', workspace(template({...journal,pagination:{...journal.pagination,total:'2'}}),journal.path));
    const compiled = parseDebugDocument(document(shell));
    const edgeDocument = document(edge), edgeView = parseDebugDocument(edgeDocument);
    const measuredDocument = document(framedHtml);
    for (let index=0;index<150;index++) parseDebugDocument(measuredDocument);
    const measure = action => Array.from({length:7},() => {
      const start=performance.now(); for (let index=0;index<300;index++) action();
      return (performance.now()-start)/300;
    }).sort((left,right)=>left-right);
    const model=measure(()=>parseDebugDocument(measuredDocument));
    const total=measure(()=>parseDebugDocument(document(framedHtml)));
    return {clean,noisy,failures,journalView,compiled,edgeView,edgeMarkup:edgeDocument.querySelectorAll('img,script,[onerror],[onclick]').length,
      descriptorCount:document(shell).querySelectorAll('#debug-workspace > #debug-read-descriptor').length,
      benchmark:{samples:7,iterationsPerSample:300,modelMedianMs:model[3],modelRangeMs:[model[0],model[6]],
        documentAndModelMedianMs:total[3],documentAndModelRangeMs:[total[0],total[6]]}};
  }, {parserURL,shell,edge,framedHtml:document});
  assert.deepEqual(contract.noisy,contract.clean,'presentation changes do not change namespace meaning');
  assert.deepEqual(contract.failures,[],'missing, malformed or mismatched descriptors fail closed');
  assert.equal(contract.clean.collection.epoch,'900719925474099312345');
  assert.equal(contract.clean.collection.childCount,'900719925474099312345');
  assert.equal(contract.clean.collection.slotCount,'900719925474099312345');
  assert.equal(contract.journalView.pagination.epoch,'900719925474099312345');
  assert.deepEqual(contract.clean.children,['/0x11/example/child']);
  assert.equal(contract.clean.childSummaries[0].glyph,'object.folder','Grove owns glyph choice');
  assert.equal(contract.clean.kind,'custom-kind','new namespace kinds need no browser classification');
  for (const field of ['record','slots','operations','version','lore','semanticSlots']) assert.equal(Object.hasOwn(contract.clean,field),false,field + ' is not duplicated');
  assert.equal(contract.descriptorCount,1);
  assert.equal(contract.compiled.path,'/hello');
  assert.equal(contract.edgeMarkup,0,'real Grove encoder cannot break out of the inert text descriptor');
  assert.ok(JSON.stringify(contract.edgeView).includes('</template>'),'adversarial authored text round-trips through the real Grove encoder');
  assert.deepEqual(contract.edgeView.previewSlots.map(slot=>slot.key),['/a','/b','/c'],'only three non-metadata excerpts travel with the descriptor');
  assert.equal(contract.edgeView.previewSlots[0].text,'€'.repeat(59) + '…','the 180-byte preview limit preserves UTF-8 boundaries');
  assert.equal(contract.edgeView.previewSlots[2].reference,'/reference');
  for (const field of ['epoch','childCount','slotCount']) assert.equal(contract.edgeView.collection[field],'900719925474099312345',field + ' is lossless through the real backend encoder');
  await contractPage.close();
  checks.push('versioned descriptor independent of presentation');
  for (const [name, app, width, touch, colorScheme] of [['mash-only',false,1440,false,'light'],['desktop',true,1440,false,'light'],['dark',true,1440,false,'dark'],['touch',true,390,true,'light'],['cases',true,1440,false,'light'],['legacy-view',true,1440,false,'light'],['navigation',true,1440,false,'light']]) {
    const context = await browser.newContext({viewport: {width, height: 1000}, hasTouch: touch, isMobile: touch, colorScheme, reducedMotion: 'reduce'});
    context.setDefaultTimeout(5000);
    await context.addInitScript(() => {
      if (location.origin !== 'http://grove-declaration.invalid') return;
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({root:'/hello',expanded:['/hello'],saved:true,recent:false,tree:true}));
      localStorage.setItem('shrine-debug.v1.saved', JSON.stringify(['/hello']));
    });
    await context.route('**/*', route => {
      const req = route.request(), url = new URL(req.url());
      const scoped = name === 'navigation' && /^\?scope=(workspace|outline|preview)$/.test(url.search);
      const pinned = name === 'navigation' && url.pathname === '/debug/epoch' && url.searchParams.size === 2 &&
        url.searchParams.get('epoch') === '900719925474099312345' && url.searchParams.get('scope') === 'workspace';
      if (req.method() !== 'GET' || url.origin !== base || (url.search && !scoped && !pinned && !(name === 'legacy-view' && url.search === '?view=rendered'))) { violations.push(req.url()); return route.abort(); }
      if (url.pathname === '/debug.js') {
        const capture = `window.__serverNodes=[...document.querySelectorAll('.debug-header,#wb-path-locator,#debug-history-nav,#wb-header-actions,#debug-sidebar,#debug-main,#wb-canvas,.wb-inspector,#wb-path-menu,#wb-path-preview')];window.__factories=[];const originalCreate=document.createElement;document.createElement=function(...args){const caller=new Error().stack?.split('\\n')[2];if(caller?.includes('/debug.js'))__factories.push([args[0],caller]);return originalCreate.apply(this,args)};\n`;
        return route.fulfill({contentType:'text/javascript', body: app ? capture + compiled.outputFiles[0].text : ''});
      }
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (name === 'navigation' && url.pathname === '/debug/fail') return route.fulfill({status:503,body:'Expected unavailable fixture'});
      if (name === 'navigation' && url.pathname === '/debug/malformed') {
        const body = shell.replaceAll('/hello','/malformed').replace(/<template id="debug-read-descriptor">[\s\S]*?<\/template>/,'');
        return route.fulfill({contentType:'text/html',body:html(body)});
      }
      if (name === 'navigation' && ['/debug/poor-scope','/debug/epoch'].includes(url.pathname)) {
        let body = shell.replaceAll('/hello',url.pathname.slice('/debug'.length));
        if (url.pathname === '/debug/poor-scope') {
          const poorer = body.replace(/((?:&quot;|")scope(?:&quot;|")\s*:\s*(?:&quot;|"))document((?:&quot;|"))/,'$1outline$2');
          assert.notEqual(poorer,body,'fixture changes only the descriptor scope'); body=poorer;
        }
        return route.fulfill({contentType:'text/html',body:html(body)});
      }
      if (url.pathname === '/debug/hello' || name === 'navigation' && ['/debug/other','/debug'].includes(url.pathname)) {
        // Reuse the compiler-authored declaration; vary data, never rebuild its DOM.
        const path = url.pathname.slice('/debug'.length) || '/';
        let body = shell.replaceAll('/hello',path);
        if (path === '/other') body = body.replaceAll('Hello namespace','Other namespace');
        if (name === 'cases') {
          const start = body.indexOf('<div class="wb-inspector"'), end = body.indexOf('<div class="wb-bottom"',start);
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
    if (!touch) {
      // This works with Mash alone: no debugger tooltip event delegation.
      const refresh = page.locator('#wb-refresh');
      const tip = refresh.locator('..');
      assert.equal(await tip.evaluate(n => n.localName), 'ui-tooltip');
      await refresh.hover();
      await page.waitForFunction(() => document.querySelector('#wb-refresh').parentElement.open);
      assert.equal(await tip.evaluate(n => n.label), 'Refresh current record');
      await page.keyboard.press('Escape');
      assert.equal(await tip.evaluate(n => n.open), false);
      await refresh.locator('button').focus();
      await page.keyboard.press('ArrowRight');
      assert.equal(await page.locator('#debug-inspector-toggle').evaluate(n =>
        n.shadowRoot.activeElement === n.shadowRoot.querySelector('button')), true,
        'Mash toolbar navigation crosses declared tooltip wrappers');
      await page.locator('.wb-document-title').focus();
      await page.locator('.wb-document-title').hover();
    }
    if (app) {
      await page.waitForFunction(() => document.querySelector('#debug-workspace').dataset.readState === 'ready');
      assert.equal(await page.locator('#wb-canvas').isVisible(),true,'native inspection remains visible');
      assert.equal(new URL(page.url()).searchParams.has('view'),false,'retired view state is normalized');
      assert.equal(await page.locator('#debug-workspace').getAttribute('data-view-mode'), null, 'inspection does not create retired mode state');
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
      if (name === 'navigation') {
        const workspace = page.locator('#debug-workspace');
        const ready = path => page.waitForFunction(path => document.querySelector('#debug-workspace').dataset.path === path &&
          document.querySelector('#debug-workspace').getAttribute('aria-busy') !== 'true', path);
        const go = async path => {
          await page.locator('#wb-path-edit').click();
          await page.locator('#debug-go ui-input input').fill(path);
          await page.locator('#debug-go ui-input input').press('Enter');
        };
        await go('/other'); await ready('/other');
        assert.match(await page.locator('#debug-main').innerText(),/Other namespace/);
        assert.equal(await page.evaluate(() => __serverNodes.filter(n => !n.matches('#debug-main,#wb-canvas,.wb-inspector')).every(n=>n.isConnected)),true,
          'navigation replaces scoped content, not the persistent shell');
        await page.locator('#debug-save').click();
        await page.waitForFunction(() => JSON.parse(localStorage.getItem('shrine-debug.v1.saved')).includes('/other'));
        assert.equal(await page.locator('#debug-saved [data-path="/other"]').count(),1);
        await page.locator('#debug-back').click(); await ready('/hello');
        await page.locator('#debug-forward').click(); await ready('/other');
        await go('/fail');
        await page.waitForFunction(() => document.querySelector('#wb-feedback').textContent.includes('Navigation failed'));
        await ready('/other');
        assert.equal(new URL(page.url()).pathname,'/debug/other','failed read does not move the address');
        assert.match(await page.locator('#debug-main').innerText(),/Other namespace/);
        await page.keyboard.press('Escape'); // Failed locator input remains editable until dismissed.
        await go('/malformed');
        await page.waitForFunction(() => document.querySelector('#wb-feedback').textContent.includes('Navigation failed'));
        await ready('/other');
        assert.equal(new URL(page.url()).pathname,'/debug/other','missing descriptor does not replace the current route');
        assert.match(await page.locator('#debug-main').innerText(),/Other namespace/);
        await page.keyboard.press('Escape');
        await go('/poor-scope');
        await page.waitForFunction(() => document.querySelector('#wb-feedback').textContent.includes('Navigation failed'));
        await ready('/other');
        assert.equal(new URL(page.url()).pathname,'/debug/other','a poorer descriptor cannot replace workspace content');
        await page.keyboard.press('Escape');
        // Add only a test link; invoke the real delegated navigation gesture.
        await page.evaluate(() => {
          const link=document.createElement('a'); link.id='test-pinned-read'; link.textContent='Read pinned fixture';
          link.href='/debug/epoch?epoch=900719925474099312345'; document.querySelector('#debug-main').prepend(link);
        });
        await page.locator('#test-pinned-read').click();
        await page.waitForFunction(() => document.querySelector('#wb-feedback').textContent.includes('Navigation failed'));
        await ready('/other');
        assert.equal(new URL(page.url()).pathname,'/debug/other','a mismatched epoch cannot replace the selected version');
        assert.match(await page.locator('#debug-main').innerText(),/Other namespace/);
        assert.equal(await workspace.locator(':scope > #debug-read-descriptor').evaluate(template=>JSON.parse(template.content.textContent).path),'/other');
        await page.locator('#test-pinned-read').evaluate(link=>link.remove());
        await page.locator('#debug-filter input').fill('hello');
        assert.equal(await page.locator('#debug-saved [data-path="/other"]').isVisible(),false);
        await page.locator('#debug-filter-clear').click();
        assert.equal(await page.locator('#debug-saved [data-path="/other"]').isVisible(),true);
        await page.locator('#debug-section-recent button').first().click();
        assert.equal(await page.locator('#debug-section-recent').evaluate(n=>n.open),true);
        await page.locator('#debug-inspector-toggle').click();
        assert.equal(await workspace.evaluate(n=>n.inspectorOpen),true);
        await page.waitForFunction(()=>document.activeElement?.matches('.wb-inspector'));
        await page.keyboard.press('Escape');
        await page.waitForFunction(()=>!document.querySelector('#debug-workspace').inspectorOpen);
        const handle = workspace.locator('[part=sidebar-resizer] [role=separator]');
        const before = await workspace.evaluate(n=>n.sidebarWidth);
        await handle.focus(); await page.keyboard.press('ArrowRight');
        await page.waitForFunction(before => document.querySelector('#debug-workspace').sidebarWidth > before,before);
        assert.ok(await page.evaluate(()=>JSON.parse(localStorage.getItem('shrine-debug:pane-widths')).sidebarWidth)>before);
        // Only the platform clipboard boundary is stubbed; invoke the actual Mash menu.
        await page.evaluate(() => { const c=document.querySelector('#wb-path-clipboard');c.copy=async()=>{window.__copied=c.value;}; });
        await page.locator('#debug-saved [data-path="/other"] ui-link').click({button:'right'});
        await page.locator('#wb-path-menu ui-menu-item[value=path]').click();
        await page.waitForFunction(()=>window.__copied==='/other');
        await page.locator('#debug-root-toggle').click();
        await page.locator('#debug-root-menu ui-menu-item[value="/"]').click();
        await ready('/');
        assert.equal(new URL(page.url()).pathname, '/debug', 'places bind the declared menu destination');
        // Grove's asset envelope has no second styling owner to activate later.
        assert.equal(await page.locator('link[href="/style.css"]').count(), 0);
        assert.equal(await page.locator('link[rel=stylesheet]').count(), 2);
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
  console.log(JSON.stringify({passed:checks,liveGETs:0,errors,violations,factories,
    measurement:{htmlBytes:{page:Buffer.byteLength(shell),details:Buffer.byteLength(details),document:Buffer.byteLength(document)},parser:contract.benchmark}}));
} finally {await browser.close();}
