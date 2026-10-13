// All responses are produced by the real mounted backend; interception only
// delays an actual inspection response to exercise capture/response ordering.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/goo-inspection-browser']=process.argv.slice(2);
const require=createRequire(resolve(mash,'tests/integration/package.json'));
const engines=require('@playwright/test'),results=[];await mkdir(out,{recursive:true});
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[],actions=[],captures=[];page.setDefaultTimeout(45000);
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{
  const path=new URL(request.url()).pathname;
  if(path==='/goo/act')actions.push(request.postData());
  if(path==='/goo/inspect')captures.push(Object.fromEntries(new URLSearchParams(request.postData())));
 });
 const panel=page.getByRole('complementary',{name:'Presentation inspection'}),picker=page.getByRole('button',{name:'Inspect a presentation',exact:true});
 const ready=()=>panel.getByRole('status').filter({hasText:'Captured observation.'}).waitFor();
 const pick=async locator=>{await picker.click();await locator.click();await ready();};
 try {
  await page.goto(base+'/goo-inspector?path=%2F0x11%2Fapp%2Ftree_pages%2Froot');
  const plain=page.locator('.goo-member[data-key$="/root/plain"] .goo-presentation');
  await plain.waitFor();
  const before=await page.request.get(base+'/goo/status?target=%2F0x11%2Fapp%2Ftree_pages%2Froot%2Fplain');
  const beforeState=await before.json();
  await pick(plain);
  assert.equal(captures.at(-1).subject,'/0x11/app/tree_pages/root/plain');
  assert.equal(captures.at(-1).view,'/0x11/gov/goo_inspector/summary');
  assert(Number(captures.at(-1).line)>0);assert(['sm','md','lg'].includes(captures.at(-1).layout));
  assert((await panel.locator('.goo-inspect-content').textContent()).includes('Browser capture'));
  assert((await panel.locator('.goo-inspect-content').textContent()).includes('/0x11/app/tree_pages/root/plain'));
  assert.equal(await page.locator('wa-tree-item[selected]').count(),0,'inspection pick does not select the row');
  assert.equal(await panel.getByRole('link',{name:'Subject:',exact:false}).getAttribute('href'),'/views/0x11/app/tree_pages/root/plain');
  assert.equal(await panel.locator('.goo-surface').count(),1,'typed records use the production synthetic renderer');
  const first=captures.at(-1).capture;
  await panel.getByRole('button',{name:'Capture again',exact:true}).click();await ready();
  assert.notEqual(captures.at(-1).capture,first);
  const original=captures.at(-1).capture;
  await pick(panel.locator('.goo-inspect-content .goo-surface'));
  assert.equal(captures.at(-1).kind,'inspection');assert.equal(captures.at(-1).parent,original);
  await panel.getByRole('button',{name:'Close inspection'}).click();

  let release,arrived;const gate=new Promise(r=>release=r),pending=new Promise(r=>arrived=r);let delay=true;
  await page.route('**/goo/inspect',async route=>{
   const response=await route.fetch();
   if(delay){delay=false;arrived();await gate;}
   await route.fulfill({response}).catch(()=>{});
  });
  await picker.click();await plain.click();await pending;
  const old=captures.at(-1).capture;
  await picker.click();await page.locator('.goo-member[data-key$="/root/leaf"] .goo-presentation').click();await ready();
  const newest=captures.at(-1).capture;assert.notEqual(old,newest);release();
  await page.unroute('**/goo/inspect');
  assert.equal(captures.at(-1).subject,'/0x11/app/tree_pages/root/leaf');
  assert((await panel.locator('.goo-inspect-content').textContent()).includes(newest));
  const after=await page.request.get(base+'/goo/status?target=%2F0x11%2Fapp%2Ftree_pages%2Froot%2Fplain');
  assert.deepEqual(await after.json(),beforeState,'inspection does not change the namespace');
  await panel.getByRole('button',{name:'Close inspection'}).click();

  // A real editable presentation, including an active composition and caret.
  await page.goto(base+'/views/0x11/app/panes/cards/a');
  const editor=page.locator('.preview[data-view$="/panes/edit"]'),input=editor.locator('input').first();
  await input.waitFor();await input.fill('Private unsaved inspection draft');
  await input.evaluate(node=>{window.inspectedInput=node;node.focus();node.setSelectionRange(4,9);node.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:'draft'}));});
  const oldValue=await input.inputValue();await input.press('Alt+i');await ready();
  assert.equal(captures.at(-1).view,'/0x11/gov/panes/edit');
  assert.equal(captures.at(-1).dirty,'1');assert.equal(captures.at(-1).composing,'1');
  assert(!JSON.stringify(captures.at(-1)).includes('Private unsaved'));
  assert(await input.evaluate(node=>node===window.inspectedInput));assert.equal(await input.inputValue(),oldValue);
  assert.deepEqual(await input.evaluate(node=>[node.selectionStart,node.selectionEnd]),[4,9]);
  await panel.getByRole('button',{name:'Close inspection'}).click();
  await input.evaluate(node=>node.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'draft'})));
  assert.deepEqual(actions,[]);assert.deepEqual(errors,[]);
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  results.push({engine:name,version:browser.version(),captures:captures.length,passed:true});console.log(JSON.stringify(results.at(-1)));
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});console.error(await page.locator('body').innerText());throw error;}
 finally{await browser.close();}
}
await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');
