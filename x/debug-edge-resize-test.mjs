// Isolated composition fixture: every request is fulfilled from frozen assets.
// Never starts, reads, or writes a namespace runtime.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const origin = 'http://edge-resize-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/mash.js','src/foil/.debug-assets/mash.js','application/javascript'],
  ['/components.css','src/foil/.debug-assets/components.css','text/css'],
  ['/debug.css','src/foil/debug.css','text/css'],
].map(async ([url,path,contentType])=>[url,{contentType,body:await readFile(resolve(root,path))}])));
const rows = Array.from({length:80},(_,i)=>`<div class="fixture-row"><span>Namespace path ${i+1}</span><ui-button icon-only size="small" variant="ghost" aria-label="Save path ${i+1}"><ui-icon name="object.bookmark"></ui-icon></ui-button></div>`).join('');
const html = `<!doctype html><html data-mash-catalogue="mash"><head><meta charset="utf-8"><link rel="stylesheet" href="/components.css"><link rel="stylesheet" href="/debug.css"><script defer src="/mash.js"></script><style>.fixture-row{display:flex;align-items:center;justify-content:space-between;min-height:32px;padding-inline:8px 0}.fixture-long{height:2600px;padding:24px}</style></head><body><div class="debug-shell">
  <header class="debug-header wb-commandbar"><ui-button id="outside" size="small">Workspace</ui-button></header>
  <sh-triptych id="debug-workspace" resizable sidebar-width="400" inspector-width="264">
    <sh-sidebar id="debug-sidebar" slot="sidebar"><ui-input id="debug-filter" slot="search" label="Filter paths" placeholder="Filter paths…"></ui-input><div>${rows}</div></sh-sidebar>
    <div id="debug-main" slot="content"><div class="fixture-long">Namespace record</div></div>
    <div slot="inspector" class="tinsp fixture-long">Inspector slots</div>
  </sh-triptych></div></body></html>`;
const browser = await chromium.launch();
const unexpected=[], errors=[], evidence=[];
try {
  for(const options of [{width:1197,theme:'light'},{width:1440,theme:'dark'},{width:1197,theme:'light',touch:true},{width:390,theme:'dark',touch:true}]){
    const {width,theme,touch=false}=options;
    const context=await browser.newContext({viewport:{width,height:900},colorScheme:theme,hasTouch:touch,reducedMotion:touch?'reduce':'no-preference',serviceWorkers:'block'});
    await context.route('**/*',route=>{
      const req=route.request(),url=new URL(req.url());
      if(req.method()!=='GET'||url.origin!==origin){unexpected.push(req.url());return route.abort();}
      if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
      if(assets.has(url.pathname))return route.fulfill(assets.get(url.pathname));
      if(url.pathname==='/favicon.ico')return route.fulfill({status:204});
      unexpected.push(req.url());return route.abort();
    });
    const page=await context.newPage();page.setDefaultTimeout(5000);page.on('pageerror',e=>errors.push(e.message));
    await page.goto(origin);
    await page.evaluate(async theme=>{document.documentElement.dataset.theme=theme;await customElements.whenDefined('sh-triptych');await customElements.whenDefined('sh-sidebar');},theme);
    const workspace=page.locator('#debug-workspace');
    await page.waitForFunction(w=>document.querySelector('#debug-workspace').matches(':state(resizable)')===(w>832),width);
    const area=page.locator('#debug-sidebar ui-scroll-area[part=body]');
    const viewport=area.locator('[part=viewport]'), bar=area.locator('[part=block-scrollbar]'),thumb=area.locator('[part=block-thumb]');
    await page.waitForFunction(()=>{const a=document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area');return a?.viewportElement?.scrollHeight>a.viewportElement.clientHeight+500;});
    const initial=await workspace.evaluate(w=>({sidebar:w.sidebarWidth,inspector:w.inspectorWidth}));
    const paneEdge=()=>workspace.locator('[part=sidebar]').evaluate(e=>e.getBoundingClientRect().right);
    assert.ok(Math.abs((await viewport.boundingBox()).x+(await viewport.boundingBox()).width-await paneEdge())<1,'scroller reaches the sidebar boundary');
    if(width>832){
      for(const side of ['sidebar','inspector']){
        const handle=workspace.locator(`[part=${side}-resizer]`),control=handle.locator('[part=control]');
        const b=await control.boundingBox();
        const geometry=await workspace.evaluate((w,side)=>{const part=n=>w.shadowRoot.querySelector(`[part=${n}]`).getBoundingClientRect();const p=part(side),m=part('main');return {edge:side==='sidebar'?p.right:p.left,neighbor:side==='sidebar'?m.left:m.right};},side);
        assert.ok(Math.abs(geometry.edge-geometry.neighbor)<1,'no reserved splitter column');
        assert.ok(Math.abs(b.x+b.width/2-geometry.edge)<1,'hit target is centered on the edge');
        assert.equal(b.width,touch?12:8);
        assert.equal(await handle.evaluate(h=>h.getBoundingClientRect().width),0);
        assert.equal(await handle.locator('[part=grip]').isVisible(),false);
        await page.mouse.move(b.x+b.width/2,b.y+100);
        assert.equal(await control.evaluate(c=>getComputedStyle(c).backgroundColor),'rgba(0, 0, 0, 0)','hover stays transparent');
        await page.mouse.down();
        assert.equal(await control.evaluate(c=>getComputedStyle(c).backgroundColor),'rgba(0, 0, 0, 0)','drag stays transparent');
        await page.mouse.move(b.x+b.width/2+(side==='sidebar'?24:-24),b.y+100,{steps:4});await page.mouse.up();
        await page.waitForFunction(({side,value})=>Math.abs(document.querySelector('#debug-workspace')[side+'Width']-value)<1,{side,value:initial[side]+24});
        await page.keyboard.press('Tab');await control.focus();
        assert.equal(await control.evaluate(c=>getComputedStyle(c).outlineStyle),'solid','keyboard focus remains visible');
        await control.press(side==='sidebar'?'ArrowRight':'ArrowLeft');
        await page.waitForFunction(({side,value})=>Math.abs(document.querySelector('#debug-workspace')[side+'Width']-value)<1,{side,value:initial[side]+32});
        await page.locator('#outside button').focus();
      }
    }else assert.equal(await workspace.locator('ui-resizable-handle').count(),0,'compact panes have no splitters');
    if(!touch){
      await viewport.hover({position:{x:24,y:120}});
      assert.equal(await area.getAttribute('mode'),'scrolling');
      assert.equal(await area.getAttribute('size'),'medium');
      await page.waitForFunction(()=>!document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').matches(':state(visible)'));
      assert.equal(await bar.evaluate(el=>getComputedStyle(el).opacity),'0','hover alone does not reveal the scrollbar');
      assert.equal(await bar.evaluate(el=>getComputedStyle(el).transitionDuration),'0.12s','activity scrollbars fade using Mash timing');
      await page.mouse.wheel(0,180);
      await page.waitForFunction(()=>Number(getComputedStyle(document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').shadowRoot.querySelector('[part=block-scrollbar]')).opacity)>0.99);
      assert.equal((await bar.boundingBox()).width,12,'medium hit area');
      assert.equal((await thumb.boundingBox()).width,4,'medium quiet indicator');
      await page.waitForFunction(()=>Number(getComputedStyle(document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').shadowRoot.querySelector('[part=block-scrollbar]')).opacity)===0);
      assert.equal(await area.evaluate(el=>el.matches(':state(hovered)')),true,'indicator fades even while pointer remains in the pane');
      await page.mouse.wheel(0,40);
      await page.waitForFunction(()=>Number(getComputedStyle(document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').shadowRoot.querySelector('[part=block-scrollbar]')).opacity)>0.99);
      const t=await thumb.boundingBox(),before=await workspace.evaluate(w=>w.sidebarWidth);
      assert.ok(Math.abs(t.x+t.width-(await paneEdge()-2))<1,'thumb sits 2px from the boundary');
      await page.mouse.move(t.x+t.width/2,t.y+t.height/2);await page.mouse.down();
      await page.mouse.move(t.x+t.width/2,t.y+t.height/2+90,{steps:6});await page.mouse.up();
      await page.waitForFunction(()=>document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').viewportElement.scrollTop>100);
      assert.equal(await workspace.evaluate(w=>w.sidebarWidth),before,'dragging the scrollbar never resizes the sidebar');
      await bar.focus();await bar.press('Home');
      await page.waitForFunction(()=>document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').viewportElement.scrollTop===0);
      const action=page.locator('.fixture-row ui-button button').first();await action.click();
      const actionBox=await action.boundingBox(),barBox=await bar.boundingBox();
      assert.ok(actionBox.x+actionBox.width<=barBox.x+1,'scrollbar never covers row actions');
      assert.equal(await workspace.evaluate(w=>w.sidebarWidth),before);
      await viewport.hover({position:{x:24,y:120}});
      await page.waitForFunction(()=>Number(getComputedStyle(document.querySelector('#debug-sidebar').shadowRoot.querySelector('ui-scroll-area').shadowRoot.querySelector('[part=block-scrollbar]')).opacity)===0);
      assert.equal(await action.evaluate(el=>el.getRootNode().activeElement===el),true,'a clicked row action does not pin its scroll indicator');
    }else assert.equal(await bar.isVisible(),false,'touch retains native scrolling');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    const shot=`/private/tmp/shrine-edge-resize-${theme}-${width}-${touch?'coarse':'fine'}.png`;
    await page.screenshot({path:shot});evidence.push({...options,screenshot:shot});await context.close();
  }
  assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
  await writeFile('/private/tmp/shrine-edge-resize-evidence.json',JSON.stringify({evidence,unexpected,errors},null,2));
  console.log(JSON.stringify({passed:true,evidence,unexpected,errors}));
}finally{await browser.close();}
