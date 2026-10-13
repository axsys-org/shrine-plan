// Mutates the preferred face and grades a card: use a disposable namespace.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/srs-panes-browser']=process.argv.slice(2);
if(!base||!mash)throw Error('Usage: check-panes.mjs DISPOSABLE_URL MASH_ROOT [OUTPUT]');
const engines=createRequire(resolve(mash,'tests/integration/package.json'))('@playwright/test');
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(45000);
 const errors=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
 const entry='/0x11/app/cards', face='/0x11/gov/srs/workspace', card='/0x11/app/srs/cards/demo';
 const tab=()=>page.getByRole('tab',{name:'Panes',exact:true});
 const check=text=>{checks.push(text);console.log(name,text);};
 async function render(target,slot='/sys/slot/face') {
  return page.request.post(base+'/goo/render',{form:{target,slot,width:'800',textScale:'1',direction:'ltr'}});
 }
 async function setFace(path) {
  const current=await (await page.request.get(base+'/goo/status?'+new URLSearchParams({target:entry}))).json();
  const response=await page.request.post(base+'/goo/edit-value',{form:{target:entry,slot:'/sys/face',expected:current.expected,kind:'path',value:path,context:''}});
  assert.equal(response.status(),200,await response.text());
 }
 try {
  await page.goto(base+'/goo-documentation?path=/0x11/app');
  const cards=page.locator(`wa-tree-item[subject="${entry}"]`);
  await cards.waitFor();assert.equal(await tab().count(),0);
  await cards.press('Enter');await tab().waitFor();await tab().click();
  const framed=page.frameLocator('iframe[title="Goo pane"]');
  await framed.locator('.goo-session').waitFor();
  const choice=framed.getByRole('option').filter({hasText:'What does a Shrine name identify?'});
  await choice.waitFor();await choice.press('Enter');
  const grading=framed.locator('.goo-follow .preview');
  await grading.getByRole('button',{name:'Good',exact:true}).waitFor();
  check('app/cards resolves its face into a working SRS collection and selected-card review');
  const before=await (await page.request.get(base+'/goo/status?'+new URLSearchParams({target:card}))).json();
  const received=page.waitForResponse(r=>new URL(r.url()).pathname==='/goo/act');
  await grading.getByRole('button',{name:'Good',exact:true}).click();
  const response=await received;assert.equal(response.status(),200,await response.text());
  const saved=await response.json();assert(BigInt(saved.expected)>BigInt(before.expected));
  await engines.expect.poll(()=>grading.evaluate(el=>window.GooInspection.capture(window.GooInspection.find(el)).expected)).toBe(saved.expected);
  const after=await (await page.request.get(base+'/goo/status?'+new URLSearchParams({target:entry}))).json();
  const exact=await render(entry);assert.equal(exact.status(),200);assert.equal((await exact.json()).view,face);
  check('review actions update the selected card through the preferred pane');
  const frame=page.frames().find(f=>f.url().includes('/goo-face?'));
  await frame.evaluate(()=>window.retainedPane=true);
  await page.getByRole('tab',{name:'Values',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('form[data-goo-value="/sys/face"]'));
  assert.equal(await page.locator('form[data-goo-value="/sys/face"] [data-value-input="value"]').inputValue(),face);
  await tab().click();assert.equal(await frame.evaluate(()=>window.retainedPane),true);
  await grading.getByRole('button',{name:'Good',exact:true}).waitFor();
  await page.setViewportSize({width:1200,height:1050});
  await engines.expect.poll(()=>frame.evaluate(()=>window.retainedPane)).toBe(true);
  check('pane selection survives tab suspension and resize; Values exposes the stored face path');
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  await page.locator('wa-tree-item[subject="/0x11/app/srs"]').press('Enter');
  await engines.expect(tab()).toHaveCount(0);
  await engines.expect(page.getByRole('tab',{name:'Documentation',exact:true})).toHaveAttribute('aria-selected','true');
  await cards.press('Enter');await tab().waitFor();
  check('Panes disappears on records without a face and falls back to Documentation');
  assert.equal((await render(card)).status(),409);
  await setFace('/0x11/gov/srs/content');assert.equal((await render(entry)).status(),409);
  await setFace('/0x11/gov/goo_documentation/workspace');assert.equal((await render(entry)).status(),409);
  await setFace(face);assert.equal((await render(entry)).status(),200);
  check('missing faces, non-pane declarations, and incompatible receiver roles are rejected');
  assert.deepEqual(errors,[]);results.push({engine:name,version:browser.version(),checks});
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});results.push({engine:name,checks,error:String(error),errors});console.error(await page.locator('body').innerText());throw error;}
 finally {await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');await browser.close();}
}
