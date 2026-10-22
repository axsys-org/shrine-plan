// Exercise the actual Grove/Foil application, not a browser-side model.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
const [base='http://127.0.0.1:8137', mash, output='/tmp/block-document-browser'] = process.argv.slice(2);
if (!mash) throw new Error('Usage: node check-browser.mjs URL PINNED_MASH_PATH [OUTPUT]');
const require=createRequire(join(mash,'tests/integration/package.json'));
const {chromium,expect:baseExpect}=require('@playwright/test');
const expect=baseExpect.configure({timeout:120000});
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM || '/usr/bin/chromium',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1180,height:1000}});
page.setDefaultTimeout(120000);
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
try {
  await page.goto(base+'/block-document',{waitUntil:'domcontentloaded',timeout:180000});
  await expect(page.getByRole('button',{name:'Apply text and style',exact:true})).toBeEnabled({timeout:180000});
  await page.screenshot({path:join(output,'initial.png'),fullPage:true});
  const text=await page.locator('main').innerText();
  const match=/Revision (\d+) \/ (\d+) blocks/.exec(text);
  assert(match,'Document revision must be visible');
  const revision=Number(match[1]), blocks=Number(match[2]);
  const summary=(delta,count)=>`Revision ${revision+delta} / ${count} blocks / undo keeps 50 changes`;
  await page.locator('input[data-input-slot$="/selected_text"]').fill('An edit made through Grove. ');
  await page.locator('input[data-input-slot$="/selected_style"]').fill('bold italic');
  await page.getByRole('button',{name:'Apply text and style',exact:true}).click();
  await expect(page.getByText(summary(1,blocks),{exact:true})).toBeVisible();
  await expect(page.getByText('An edit made through Grove.',{exact:false}).first()).toBeVisible();
  await page.getByRole('button',{name:'Insert paragraph after',exact:true}).click();
  await expect(page.getByText(summary(2,blocks+1),{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Undo',exact:true}).click();
  await expect(page.getByText(summary(3,blocks),{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Redo',exact:true}).click();
  await expect(page.getByText(summary(4,blocks+1),{exact:true})).toBeVisible();
  await page.screenshot({path:join(output,'edited.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: native form apply, rich style, insert, undo and redo.');
} catch(e) {
  await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});
  await writeFile(join(output,'failure.html'),await page.content());
  throw e;
} finally { await browser.close(); }
