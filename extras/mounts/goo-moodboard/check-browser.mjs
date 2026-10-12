// Run only against an explicitly authorized local demo origin.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/goo-moodboard-browser']=process.argv.slice(2);
if(!base||!mash)throw Error('Usage: check-browser.mjs URL MASH_ROOT [OUTPUT]');
const engines=createRequire(resolve(mash,'tests/integration/package.json'))('@playwright/test');
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});const page=await browser.newPage({viewport:{width:1680,height:1050}});
 page.setDefaultTimeout(45000);const errors=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
 await page.addInitScript(()=>{
  window.forbiddenMeasurements=[];
  for(const key of ['getBoundingClientRect','getClientRects']){const original=Element.prototype[key];Element.prototype[key]=function(...args){if(this.closest?.('goo-patch-node,goo-patch-port,[data-patch-label]')){forbiddenMeasurements.push(key);throw Error('Forbidden content measurement');}return original.apply(this,args);};}
 });
 const runLabel=name+' '+Date.now();
 const saved=scope=>scope.locator('main[data-target] > [role=status]').filter({hasText:/^Saved\.$/}).waitFor();
 const ready=()=>page.waitForFunction(()=>{const p=document.querySelector('goo-patch');return p?.editable&&!p.pending.size && [...document.querySelectorAll('.goo-native')].every(el=>el.dataset.renderKey && !el.dataset.loadingKey);});
 const scene=()=>page.locator('goo-patch').evaluate(p=>p.installedScene);
 const form=label=>page.locator('.goo-native').filter({has:page.getByRole('button',{name:label,exact:true})});
 const check=text=>{checks.push(text);console.log(name,text);};
 try {
  await page.goto(base+'/goo-moodboard');await ready();
  const live=page.frameLocator('iframe[data-goo-presentation-frame]');
  const field=live.locator('input[data-input-slot$="/value"]');await field.waitFor();
  await page.waitForFunction(()=>document.querySelector('goo-patch-node[data-key="2"] img')?.complete);
  check('native image and live Goo card render');
  await page.screenshot({path:resolve(out,name+'-initial.png'),fullPage:true});
  await field.fill('Working brief '+runLabel);
  await field.dispatchEvent('compositionstart',{data:'Working'});
  await page.evaluate(()=>{window.originalFrame=document.querySelector('iframe[data-goo-presentation-frame]');window.originalDocument=originalFrame.contentDocument;});
  const before=await scene();
  await page.locator('goo-patch-node[data-key="1"] [data-patch-move][data-dx="10"]').click();
  await page.waitForFunction(x=>document.querySelector('goo-patch')?.installedScene.nodes.find(n=>n.key==='1').rect.x===x,before.nodes.find(n=>n.key==='1').rect.x+10);
  await ready();
  assert.equal(await field.inputValue(),'Working brief '+runLabel);
  assert.equal(await page.evaluate(()=>originalFrame===document.querySelector('iframe[data-goo-presentation-frame]')&&originalDocument===originalFrame.contentDocument),true);
  check('no-drag bound move preserves live document and synthetic composition');
  const dragStart = await page.locator('goo-patch').evaluate(p => {
    const r=p.installedScene.nodes.find(n=>n.key==='1').rect,c=p.getCamera(),m=p.mapping();
    return {x:m.left+(c.tx+(r.x+27)*c.scale)*m.sx,y:m.top+(c.ty+(r.y+r.height-22)*c.scale)*m.sy,old:r.x};
  });
  await page.mouse.move(dragStart.x,dragStart.y);await page.mouse.down();
  await page.mouse.move(dragStart.x+65,dragStart.y+45,{steps:12});await page.mouse.up();
  await page.waitForFunction(old=>document.querySelector('goo-patch').installedScene.nodes.find(n=>n.key==='1').rect.x!==old,dragStart.old);await ready();
  assert.equal(await field.inputValue(),'Working brief '+runLabel);
  check('real pointer dragging commits placement without disturbing the live editor');
  await field.dispatchEvent('compositionend',{data:'Working'});
  // Keyboard activation also avoids automation hit testing through a scaled iframe.
  await live.getByRole('button',{name:'Save brief',exact:true}).press('Enter');
  await live.getByText('Working brief '+runLabel,{exact:true}).first().waitFor();
  await saved(live);
  check('embedded save changes the actual Goo subject');
  await page.locator('.board-index button[data-id="1"]').click();
  await form('Save card').locator('input[data-input-slot$="/title"]').fill('Ideas '+runLabel);
  await form('Save card').getByRole('button',{name:'Save card',exact:true}).click();
  await page.waitForFunction(title=>document.querySelector('goo-patch-node[data-key="1"]')?.textContent.includes(title),'Ideas '+runLabel);
  await saved(page);await ready();
  assert.equal(await page.evaluate(()=>originalDocument===document.querySelector('iframe[data-goo-presentation-frame]').contentDocument),true);
  check('semantic board update retains unrelated live presentation');
  const positions=(await scene()).nodes.map(n=>[n.key,n.rect]);
  await ready();
  await page.reload();await ready();assert.deepEqual((await scene()).nodes.map(n=>[n.key,n.rect]),positions);
  await live.getByText('Working brief '+runLabel,{exact:true}).first().waitFor();
  check('board positions and actual subject edits survive reload');
  await page.getByRole('button',{name:'+ Note',exact:true}).click();
  await form('Add card').locator('input[data-input-slot$="/title"]').fill('New note '+name);
  await form('Add card').locator('input[data-input-slot$="/value"]').fill('A saved idea');
  const count=(await scene()).nodes.length;
  await form('Add card').getByRole('button',{name:'Add card',exact:true}).click();
  await page.waitForFunction(count=>document.querySelector('goo-patch').installedScene.nodes.length===count+1,count);
  await saved(page);await ready();
  const newest=(await scene()).nodes.at(-1);
  await page.locator(`goo-patch-node[data-key="${newest.key}"] [data-patch-select]`).click();
  await form('Delete card').getByRole('button',{name:'Delete card',exact:true}).click();
  await page.waitForFunction(count=>document.querySelector('goo-patch').installedScene.nodes.length===count,count);
  await saved(page);await ready();
  check('ordinary Goo creation and deletion update the canvas');
  await ready();
  assert.deepEqual(await page.evaluate(()=>forbiddenMeasurements),[]);assert.deepEqual(errors,[]);
  check('no node/port/label measurements or uncaught browser errors');
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  results.push({engine:name,version:browser.version(),checks,manualIME:false});
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});results.push({engine:name,version:browser.version(),checks,error:String(error),errors});throw error;}
 finally {await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2));await browser.close();}
}
