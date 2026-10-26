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
  const editor=page.getByRole('textbox',{name:'Document',exact:true});
  await expect(editor).toBeVisible({timeout:180000});
  await expect(page.locator('[data-slot="title"]',{hasText:'Notebook'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Save document',exact:true})).toBeEnabled();
  const summary=await page.locator('main').innerText();
  const revision=Number(/Revision (\d+)/.exec(summary)[1]);
  await editor.click();
  await editor.press('Control+End');
  await editor.press('Enter');
  await editor.press('/');
  await expect(page.getByRole('menu',{name:'Block style'})).toBeVisible();
  await page.getByRole('button',{name:'Heading',exact:true}).click();
  await editor.pressSequentially('Where does a puddle go?');
  await editor.press('Enter');
  await editor.pressSequentially('Water becomes vapor.');
  // Rich formatting, undo, and resize retention belong to goo-components.
  // This check owns document structure and the application's typed save.
  await expect(editor).not.toHaveAttribute('aria-busy','true');
  const draft=await page.locator('.goo-rich-input').evaluate(node=>node.value);
  await page.screenshot({path:join(output,'editor.png'),fullPage:true});
  const request=page.waitForRequest(request=>request.url().endsWith('/goo/act'));
  await page.getByRole('button',{name:'Save document',exact:true}).click();
  const body=new URLSearchParams((await request).postData());
  assert.equal(body.get('input:/0x11/gov/block_document/page'),draft);
  await expect(page.getByText(new RegExp(`Revision ${revision+1} /`))).toBeVisible();
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(editor).toContainText('Where does a puddle go?');
  await expect(editor).toContainText('Water becomes vapor.');
  const persisted=await page.locator('.goo-rich-input').evaluate(node=>JSON.parse(node.value));
  assert.deepEqual(persisted,JSON.parse(draft));
  assert.deepEqual(errors,[]);
  console.log('PASS: inline editing, slash heading, typed save and exact persisted reread.');
} catch(e) {
  await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});
  await writeFile(join(output,'failure.html'),await page.content());
  throw e;
} finally { await browser.close(); }
