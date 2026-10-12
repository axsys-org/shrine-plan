// Real Inspector page and source requests; no mocked domain responses.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/goo-incremental-browser']=process.argv.slice(2);
const require=createRequire(resolve(mash,'tests/integration/package.json'));
const {exerciseTopoi}=createRequire(import.meta.url)('../tests/goo-topoi.browser.cjs');
const engines=require('@playwright/test');await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});const page=await browser.newPage({viewport:{width:1400,height:1100}});
 const errors=[],sources=[],rowRenders=[];page.setDefaultTimeout(30000);
 let releasePage, pageReady;
 const delayed=new Promise(resolve=>pageReady=resolve), gate=new Promise(resolve=>releasePage=resolve);
 let delay=true;
 await page.addInitScript(()=>{
   window.preparedKeys=new Set();window.unpreparedRows=[];
   new MutationObserver(()=>{
     for(const row of document.querySelectorAll('.goo-member[data-key]'))
       if(window.preparedKeys.has(row.dataset.key) && !row.querySelector('.preview'))window.unpreparedRows.push(row.dataset.key);
   }).observe(document,{childList:true,subtree:true});
 });
 await page.route('**/goo/source?*',async route=>{
   const url=new URL(route.request().url()),response=await route.fetch();
   if(!response.ok())return route.fulfill({response});
   const data=await response.json();
   await page.evaluate(keys=>keys.forEach(key=>window.preparedKeys.add(key)),data.members.filter(m=>m.status==='available').map(m=>m.key));
   if(delay && url.searchParams.get('parent')==='/0x11/app/tree_pages/root/wide') {
     delay=false;pageReady();await gate;
   }
   await route.fulfill({response});
 });
 page.on('request',request=>{
   if(new URL(request.url()).pathname!=='/goo/render')return;
   const fields=new URLSearchParams(request.postData()||'');
   if(fields.get('target')?.includes('/wide/c') && fields.get('slot')==='/sys/slot/inspector_summary')rowRenders.push(fields.toString());
 });
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(new URL(r.url()).pathname==='/goo/source')sources.push(new URL(r.url()));});
 try {
  const documentResponse=await page.goto(base+'/goo-inspector?path=%2F0x11%2Fapp%2Ftree_pages%2Froot');
  assert((await documentResponse.text()).includes('>/0x11/app/tree_pages/root/plain</span>'),'SSR uses path(record) when lede is absent');
  await page.locator('wa-tree-item[subject="/0x11/app/tree_pages/root/wide"]').waitFor();
  const branch=page.locator('wa-tree-item[subject="/0x11/app/tree_pages/root/wide"]');
  await page.waitForFunction(()=>document.querySelector('wa-tree-item[subject="/0x11/app/tree_pages/root/wide"]')?.isLeaf===false);
  assert.equal(await branch.getAttribute('disabled'),null);
  assert(sources.every(url=>!url.searchParams.has('parent')),'initial load must not walk descendants');
  const plain=page.locator('wa-tree-item[subject="/0x11/app/tree_pages/root/plain"]');
  assert.equal((await plain.locator('.goo-presentation').textContent()).replace(/\s/g,''),'/0x11/app/tree_pages/root/plain');
  await plain.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.goo-follow .goo-presentation')?.textContent.includes('Record without a lede'));
  assert((await page.locator('.goo-follow .goo-presentation').textContent()).includes('/sys/req'),'synthetic slot headings use the path formatter');

  assert.equal(await page.locator('wa-tree-item[subject^="/0x11/app/tree_pages/root/wide/"]').count(),0);
  const held=await branch.locator(':scope > .goo-member').textContent();
  await branch.press('ArrowRight');
  let timer;
  try {await Promise.race([delayed,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Prepared child page did not arrive')),30000);})]);}
  finally {clearTimeout(timer);}
  assert.equal(await page.locator('wa-tree-item[subject^="/0x11/app/tree_pages/root/wide/"]').count(),0,'no partial children while the prepared page is delayed');
  assert.equal(await branch.locator(':scope > .goo-member').textContent(),held,'existing content remains visible');
  releasePage();
  await page.waitForFunction(()=>document.querySelectorAll('wa-tree-item[subject^="/0x11/app/tree_pages/root/wide/"]').length>0);
  assert(sources.some(url=>url.searchParams.get('parent')==='/0x11/app/tree_pages/root/wide'));
  const before=await page.locator('wa-tree-item[subject^="/0x11/app/tree_pages/root/wide/"]').count();
  assert.equal(await page.locator('wa-tree-item[subject$="/c000/deep"]').count(),0,'grandchildren remain deferred');
  const more=branch.getByRole('button',{name:'Load more children of /0x11/app/tree_pages/root/wide',exact:true});
  if(await more.count()) {
   await more.click();
   await page.waitForFunction(n=>document.querySelectorAll('wa-tree-item[subject^="/0x11/app/tree_pages/root/wide/"]').length>n,before);
   assert(sources.some(url=>url.searchParams.get('parent')==='/0x11/app/tree_pages/root/wide' && url.searchParams.has('after')));
  } else throw new Error('Expected the wide fixture to have more than 64 direct children');
  // Collapse/reopen retains materialized nodes and their identities, with no fetch.
  await branch.evaluate(el=>el.setAttribute('data-retained-test','yes'));
  const count=sources.length;await branch.press('ArrowLeft');await branch.press('ArrowRight');
  await page.locator('wa-tree-item[subject$="/wide/c079"]').waitFor({state:'visible'});
  assert.equal(await branch.getAttribute('data-retained-test'),'yes');assert.equal(sources.length,count);
  await page.locator('wa-tree-item[subject$="/wide/c000"]').press('ArrowRight');
  const deep=page.locator('wa-tree-item[subject$="/wide/c000/deep"]');
  await deep.waitFor({state:'visible'});
  await deep.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.goo-follow')?.textContent.includes('Deferred grandchild'));
  const stale=await page.request.get(base+'/goo/source?'+new URLSearchParams({target:'/0x11/app/tree_pages/root',topology:'tree',paged:'1',epoch:'0'}));
  assert.equal(stale.status(),409);
  const outside=await page.request.get(base+'/goo/source?'+new URLSearchParams({target:'/0x11/app/tree_pages/root',topology:'tree',paged:'1',parent:'/outside'}));
  assert.equal(outside.status(),409);
  assert.deepEqual(await page.evaluate(()=>window.unpreparedRows),[],'every available child is attached with its prepared presentation');
  assert.deepEqual(rowRenders,[],'prepared child variants reuse the ordinary owner cache');
  assert.deepEqual(errors,[]);
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  const topoi=await exerciseTopoi(page);assert.deepEqual(errors,[]);
  results.push({engine:name,version:browser.version(),topoiCases:topoi.cases,passed:true});console.log(JSON.stringify(results.at(-1)));
 } catch(error){await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});console.error(await page.locator('body').innerText());throw error;}
 finally{releasePage();await browser.close();}
}
await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');
