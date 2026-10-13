// Run against a disposable tutorial instance. Save and restore the first note.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/hello-grove-browser']=process.argv.slice(2);
if(!base||!mash)throw Error('Usage: check-browser.mjs URL MASH_ROOT [OUTPUT]');
const engines=createRequire(resolve(mash,'tests/integration/package.json'))('@playwright/test');
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1350,height:900}});
 page.setDefaultTimeout(30000);
 const errors=[],actions=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(new URL(r.url()).pathname==='/goo/act')actions.push(r);});
 const first=page.locator('.goo-topos-member[subject="/0x11/app/hello_grove/notes/first"]');
 const reader=page.locator('.goo-follow');
 const text='Edited in '+name+' and retained after browser reload.';
 try {
  const response=await page.goto(base+'/hello-grove');assert.equal(response.status(),200);
  await first.waitFor();await first.press('Enter');
  await reader.getByText('Hello from Grove.',{exact:true}).waitFor();
  await reader.getByRole('button',{name:'Edit',exact:true}).click();
  const input=reader.locator('input[data-input-slot="/sys/content"]');
  await input.waitFor();assert.equal(await input.inputValue(),'Hello from Grove.');
  assert.equal(actions.length,0,'selection and recipe changes do not write records');
  await input.fill(text);
  await reader.getByRole('button',{name:'Save and read',exact:true}).click();
  await reader.getByText(text,{exact:true}).waitFor();assert.equal(actions.length,1);
  await page.reload();await first.waitFor();await first.press('Enter');
  await reader.getByText(text,{exact:true}).waitFor();
  await reader.getByRole('button',{name:'Edit',exact:true}).click();
  await input.fill('Hello from Grove.');
  await reader.getByRole('button',{name:'Save and read',exact:true}).click();
  await reader.getByText('Hello from Grove.',{exact:true}).waitFor();
  await page.setViewportSize({width:680,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  results.push({engine:name,version:browser.version(),passed:true,checks:['keyboard selection','read/edit/save','no write on selection or Edit','reload restoration','restore original text','narrow layout','no uncaught errors']});
  console.log(name,'passed');
 } catch(error) {
  await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});
  console.error(await page.locator('body').innerText());
  results.push({engine:name,version:browser.version(),passed:false,error:String(error),errors});throw error;
 } finally {await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');await browser.close();}
}
