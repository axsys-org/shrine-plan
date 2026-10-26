// Run only against this gallery's disposable sample world.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';

const [base='http://127.0.0.1:8144', mash, output='/tmp/goo-components-browser'] = process.argv.slice(2);
if (!mash) throw Error('Usage: node check-browser.mjs URL MASH_PATH [OUTPUT]');
const require=createRequire(join(mash,'tests/integration/package.json'));
const {chromium,expect:baseExpect}=require('@playwright/test');
const expect=baseExpect.configure({timeout:120000});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
await mkdir(output,{recursive:true});
const page=await browser.newPage({viewport:{width:1180,height:960}});
page.setDefaultTimeout(120000);
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
page.on('dialog',dialog=>dialog.accept());
const go=async key=>{
  await page.goto(`${base}/goo-components?component=${key}`,{waitUntil:'domcontentloaded'});
  await expect(page.locator('main [data-node]').first()).toBeVisible();
};
try {
  await go('card');
  await expect(page.locator('main')).toContainText('A place for an idea');
  await page.screenshot({path:join(output,'card.png'),fullPage:true});
  const source=await page.locator('main').getAttribute('data-target');
  await go('compact-card');
  assert.equal(await page.locator('main').getAttribute('data-target'),source);
  await expect(page.locator('main')).toContainText('A place for an idea');
  await expect(page.locator('main')).not.toContainText('Capture a thought');

  await go('figure');
  const photo=page.locator('main img');
  const fullPhoto=async()=>{
    await expect.poll(()=>photo.evaluate(node=>{
      const box=node.getBoundingClientRect();
      return node.complete && box.width>0 && node.naturalWidth>0 &&
        Math.abs(box.height-box.width*node.naturalHeight/node.naturalWidth)<0.5;
    })).toBe(true);
  };
  await expect(photo).toHaveAttribute('alt','Clay sculpture with multiple human faces, held in a workshop.');
  await fullPhoto();
  await expect(page.locator('main')).toContainText('Clay study. Several faces, one form.');
  await expect(page.getByRole('link',{name:'Open full image',exact:true})).toHaveAttribute('href','/goo-components/sculpture.jpg');
  await page.screenshot({path:join(output,'figure.png'),fullPage:true});
  const widePhoto=await photo.boundingBox();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(async()=>(await photo.boundingBox())?.width).toBeLessThan(widePhoto.width);
  await fullPhoto();
  await page.screenshot({path:join(output,'figure-resized.png'),fullPage:true});
  await page.setViewportSize({width:1180,height:960});
  await fullPhoto();
  const photoSource=await photo.getAttribute('src');
  await go('image');
  await expect(photo).toHaveAttribute('src',photoSource);
  await fullPhoto();
  await expect(page.locator('main')).not.toContainText('Clay study.');

  await go('text-field');
  const input=page.locator('main input[data-input-slot]');
  const original=await input.inputValue();
  const revised=original+' - checked';
  await input.fill(revised);
  await page.setViewportSize({width:760,height:960});
  await expect(input).toHaveValue(revised);
  await expect(page.getByRole('button',{name:'Save text',exact:true})).toBeEnabled();
  const saved=page.waitForResponse(response=>response.url().endsWith('/goo/act')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Save text',exact:true}).click();
  assert((await saved).ok());
  await expect(page.locator('main')).toContainText('Saved');
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(input).toHaveValue(revised);
  await input.fill('caf\u00e9');
  const refused=page.waitForResponse(response=>response.url().endsWith('/goo/act')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Save text',exact:true}).click();
  await refused;
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(input).toHaveValue(revised);
  await input.fill(original);
  await page.getByRole('button',{name:'Save text',exact:true}).click();
  await expect(page.locator('main')).toContainText('Saved');

  await go('rich-editor');
  const editor=page.locator('main [contenteditable="true"]');
  await expect(editor).toBeVisible();
  const runs=()=>page.locator('main .goo-rich-input').evaluate(node=>JSON.parse(node.value));
  const before=await runs();
  const links=before.filter(run=>run.myth['/sys/link']).map(run=>run.myth['/sys/link']);
  assert(links.length);
  await editor.click();
  await editor.press('Control+Home');
  for(let i=0;i<4;i++) await editor.press('Shift+ArrowRight');
  await page.getByRole('button',{name:'Bold',exact:true}).click();
  await expect.poll(async()=>(await runs())[0].myth['/sys/modifiers']?.value).toContain('bold');
  await editor.press('Control+z');
  await expect.poll(runs).toEqual(before);
  await editor.press('Control+End');
  await editor.pressSequentially(' Kept through saving.');
  const draft=await runs();
  await page.setViewportSize({width:1180,height:960});
  await expect.poll(runs).toEqual(draft);
  await page.screenshot({path:join(output,'rich-editor.png'),fullPage:true});
  await page.getByRole('button',{name:'Save rich text',exact:true}).click();
  await expect(page.locator('main')).toContainText('Saved');
  await page.reload({waitUntil:'domcontentloaded'});
  await expect(editor).toContainText('Kept through saving.');
  assert.deepEqual((await runs()).filter(run=>run.myth['/sys/link']).map(run=>run.myth['/sys/link']),links);
  await go('rich-text');
  await expect(page.locator('main')).toContainText('Kept through saving.');
  await go('rich-editor');
  await page.locator('main .goo-rich-input').evaluate((node,value)=>{
    node.value=JSON.stringify(value);
    node.dispatchEvent(new Event('input',{bubbles:true}));
  },before);
  await page.getByRole('button',{name:'Save rich text',exact:true}).click();
  await expect(page.locator('main')).toContainText('Saved');

  await page.setViewportSize({width:390,height:844});
  await go('card');
  await expect(page.locator('main')).toContainText('A place for an idea');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:join(output,'narrow.png'),fullPage:true});
  await go('figure');
  await fullPhoto();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:join(output,'figure-narrow.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await writeFile(join(output,'results.json'),JSON.stringify({passed:true,checks:['shared card source','namespace image decoded','source aspect ratio retained on resize','contextual image alt text','shared image/figure source','plain save and reload','unsupported text refused without mutation','selection formatting and undo','draft retained on resize','rich save and link preservation','shared reader/editor source','390px layout'],errors},null,2));
  console.log('PASS: full images and aspect ratio on resize, alt text, composition, plain/rich saves, formatting and undo, resize retention, metadata preservation, reload, narrow layout.');
} catch(error) {
  await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});
  await writeFile(join(output,'failure.html'),await page.content());
  throw error;
} finally {
  await browser.close();
}
