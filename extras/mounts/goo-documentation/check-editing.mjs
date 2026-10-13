// Mutates records: run only against a disposable Eden namespace.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/goo-editing-browser']=process.argv.slice(2);
if(!base||!mash)throw Error('Usage: check-editing.mjs DISPOSABLE_URL MASH_ROOT [OUTPUT]');
const engines=createRequire(resolve(mash,'tests/integration/package.json'))('@playwright/test');
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(45000);
 const errors=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
 const target='/0x11/lib/pact/lore', title='/sys/lede';
 const check=text=>{checks.push(text);console.log(name,text);};
 const tab=(p,name)=>p.getByRole('tab',{name,exact:true});
 const form=(p,slot=title)=>p.locator(`form[data-goo-value="${slot}"]`);
 const field=(p,slot=title)=>form(p,slot).locator('[data-value-input="value"]');
 async function open(p,path=target) {
  await p.goto(base+'/goo-documentation?'+new URLSearchParams({path}));
  await p.locator('.goo-documentation').waitFor();
 }
 async function edit(p,slot=title) {
  await tab(p,'Values').click();
  const details=p.locator(`details[data-value-slot="${slot}"]`);await details.waitFor();
  if(!await details.evaluate(el=>el.open))await details.locator('summary').click();
  await p.locator('.goo-follow[data-status="current"]:visible').waitFor();
 }
 async function save(p,status=200,slot=title) {
  const received=p.waitForResponse(r=>new URL(r.url()).pathname==='/goo/edit-value');
  await form(p,slot).getByRole('button',{name:'Save',exact:true}).click();
  const response=await received;assert.equal(response.status(),status,await response.text());
  return response.json();
 }
 async function storedText(p,text,slot=title) {
  await p.waitForFunction(({slot,text})=>document.querySelector(`form[data-goo-value="${slot}"] [data-value-input="value"]`)?.getAttribute('value')===text,{slot,text});
 }
 try {
  await open(page);const session=await page.locator('#workspace').getAttribute('data-target');
  await edit(page);const original=await field(page).inputValue();
  const changed='Live name — '+name;
  await field(page).fill(changed);await save(page);await storedText(page,changed);
  await page.screenshot({path:resolve(out,name+'-values.png'),fullPage:true});
  await tab(page,'Documentation').click();
  await page.waitForFunction(text=>document.querySelector('.goo-documentation')?.textContent.includes(text),changed);
  check('text saves update stored documentation without a page reload');
  await edit(page);await field(page).fill('Unsaved draft');
  await page.setViewportSize({width:1000,height:1100});
  await page.locator('.goo-follow[data-status="current"]:visible').waitFor();
  assert.equal(await field(page).inputValue(),'Unsaved draft');
  await tab(page,'Documentation').click();await tab(page,'Values').click();
  assert.equal(await field(page).inputValue(),'Unsaved draft');
  await page.locator('wa-tree-item[subject="/0x11/lib/pact/lore/line"]').press('Enter');
  await page.getByRole('button',{name:'Stay',exact:true}).click();
  assert.equal(await field(page).inputValue(),'Unsaved draft');
  await form(page).getByRole('button',{name:'Cancel',exact:true}).click();
  await edit(page);assert.equal(await field(page).inputValue(),changed);
  check('drafts survive resizing, tab suspension, and guarded selection; Cancel restores the stored value');
  await form(page).locator('select').selectOption('foil');
  await field(page).fill('(pails/t "Foil name")');await save(page);await storedText(page,'Foil name');
  await form(page).locator('select').selectOption('foil');
  await form(page).locator('[data-value-input="context"]').fill(target);
  await field(page).fill('(pails/t "Context name")');await save(page);await storedText(page,'Context name');
  check('Foil expressions evaluate in both default and explicit compiled contexts');
  await form(page).locator('select').selectOption('foil');
  await field(page).fill('(pails/n 42)');await save(page);await storedText(page,'42');
  assert.equal(await form(page).locator('select').inputValue(),'number');
  await field(page).fill('43');await save(page);await storedText(page,'43');
  await form(page).locator('select').selectOption('foil');
  await field(page).fill('(pails/t "Context name")');await save(page);await storedText(page,'Context name');
  check('changing a datatype replaces its available scalar input');
  await form(page).locator('select').selectOption('foil');
  await field(page).fill('(missing_name');await save(page,409);
  assert.equal(await field(page).inputValue(),'(missing_name');
  assert((await form(page).getByRole('status').innerText()).length>0);
  await form(page).getByRole('button',{name:'Cancel',exact:true}).click();
  check('invalid Foil reports an error and preserves the draft');
  const stale=await browser.newPage({viewport:{width:1440,height:1100}});stale.setDefaultTimeout(45000);
  await open(stale);await edit(stale);await field(stale).fill('Stale draft');
  await edit(page);await field(page).fill('Concurrent name');await save(page);await storedText(page,'Concurrent name');
  await stale.setViewportSize({width:1000,height:1100});
  await stale.locator('.goo-follow[data-status="current"]:visible').waitFor();
  await save(stale,409);assert.equal(await field(stale).inputValue(),'Stale draft');await stale.close();
  check('concurrent changes reject stale drafts even after a layout refresh');
  await edit(page,'/sys/help');
  assert.equal(await form(page,'/sys/help').locator('select').inputValue(),'foil');
  await field(page,'/sys/help').fill('(lore "" ["Edited structured help"] [])');
  await edit(page);await field(page).fill('Two slot drafts');await save(page);await storedText(page,'Two slot drafts');
  assert.equal(await field(page,'/sys/help').inputValue(),'(lore "" ["Edited structured help"] [])');
  await save(page,200,'/sys/help');
  await tab(page,'Documentation').click();
  await page.waitForFunction(()=>document.querySelector('.goo-documentation')?.textContent.includes('Edited structured help'));
  check('structured lore uses the fallback and drafts in other slots survive a save');
  await edit(page);await field(page).fill(original);await save(page);await storedText(page,original);
  await tab(page,'Views').click();
  await page.frameLocator('iframe[data-goo-presentation-frame]').getByText('No Goo views match this entry.',{exact:true}).waitFor();
  check('Views has an explicit empty state for unmatched entries');
  await open(page,session);await tab(page,'Views').click();
  const gallery=page.frameLocator('iframe[data-goo-presentation-frame]');
  await gallery.locator('.goo-session').first().waitFor();
  const frame=page.frames().find(f=>f.url().includes('/goo-views?'));
  await frame.evaluate(()=>window.framePreserved='yes');
  await page.setViewportSize({width:1200,height:1050});
  await page.locator('.goo-follow[data-status="current"]:visible').waitFor();
  assert.equal(await frame.evaluate(()=>window.framePreserved),'yes');
  check('matching Goo panes render in Views and retain their document across resizing');
  await page.screenshot({path:resolve(out,name+'-views.png'),fullPage:true});
  await open(page,'/sys/about');await tab(page,'Values').click();
  await page.locator('.goo-follow[data-status="current"]:visible').waitFor();
  assert.equal(await page.locator('form[data-goo-value]').count(),0);
  assert.deepEqual(errors,[]);check('trusted system records stay read-only; no uncaught browser errors');
  results.push({engine:name,version:browser.version(),checks});
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});results.push({engine:name,checks,error:String(error),errors});console.error(await page.locator('body').innerText());throw error;}
 finally {await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');await browser.close();}
}
