// Grades the demo card: run only against a disposable Eden namespace.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/srs-views-browser']=process.argv.slice(2);
if(!base||!mash)throw Error('Usage: check-views.mjs DISPOSABLE_URL MASH_ROOT [OUTPUT]');
const engines=createRequire(resolve(mash,'tests/integration/package.json'))('@playwright/test');
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(45000);
 const errors=[],checks=[];page.on('pageerror',error=>errors.push(error.message));
 const target='/0x11/app/srs/cards/demo';
 const content='/0x11/gov/srs/content', review='/0x11/gov/srs/review';
 const check=text=>{checks.push(text);console.log(name,text);};
 async function render(target,slot) {
  const response=await page.request.post(base+'/goo/render',{form:{target,slot,width:'800',textScale:'1',direction:'ltr'}});
  assert.equal(response.status(),200,await response.text());return response.json();
 }
 async function values() {
  const data=await render(target,'/sys/slot/synthetic');
  return page.evaluate(html=>Object.fromEntries([...new DOMParser().parseFromString(html,'text/html').querySelectorAll('form[data-goo-value]')].map(form=>[form.dataset.gooValue,form.querySelector('[data-value-input="value"]').getAttribute('value')])),data.html);
 }
 try {
  await page.goto(base+'/goo-documentation?'+new URLSearchParams({path:target}));
  await page.getByRole('tab',{name:'Views',exact:true}).click();
  const gallery=page.frameLocator('iframe[data-goo-presentation-frame]');
  const qa=gallery.locator(`.preview[data-view="${content}"]`);
  const grading=gallery.locator(`.preview[data-view="${review}"]`);
  await qa.waitFor();await grading.waitFor();
  assert((await qa.innerText()).includes('What does a Shrine name identify?'));
  assert((await qa.innerText()).includes('A versioned locus of state.'));
  assert.equal(await qa.getByRole('button').count(),0);
  check('Views lists both published SRS views and renders the question and answer');
  let previous=await values();
  for(const [grade,interval] of [['Again',60000],['Hard',80000],['Good',160000],['Easy',480000]]) {
   const started=Date.now();
   const received=page.waitForResponse(r=>new URL(r.url()).pathname==='/goo/act');
   await grading.getByRole('button',{name:grade,exact:true}).click();
   const response=await received;assert.equal(response.status(),200,await response.text());
   const result=await response.json();
   await engines.expect.poll(()=>grading.evaluate(el=>window.GooInspection.capture(window.GooInspection.find(el)).expected)).toBe(result.expected);
   const stored=await values();
   assert.equal(Number(stored['/0x11/gov/srs/interval']),interval);
   assert(Number(stored['/0x11/gov/srs/due'])>0);
   assert.equal(stored['/sys/req'],previous['/sys/req']);
   assert.equal(stored['/sys/res'],previous['/sys/res']);
   const date=(await grading.innerText()).match(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)? UTC/)[0];
   const due=Date.parse(date.replace(' UTC','Z').replace(' ','T'));
   assert(due>=started+interval-2000&&due<=Date.now()+interval+2000,'Due time uses the current server clock');
   previous=stored;
  }
  check('all four grades update the real schedule and preserve question/answer values');
  const source=await (await page.request.get(base+'/ns/0x11/gov/srs')).text();
  const version=source.match(/name="version" value="(\d+)"/)[1];
  const secondRoot='/0x11/app/srs_view_'+name+'_'+Date.now();
  const installed=await page.request.post(base+'/grove/install',{form:{source:'/0x11/gov/srs',version,root:secondRoot}});
  assert.equal(installed.status(),200,await installed.text());
  const second=await render(secondRoot+'/cards/demo','/sys/slot/review');
  assert.equal(second.view,review);assert.equal(second.controls.length,4);
  check('the same declarations match a separately installed SRS instance');
  await page.screenshot({path:resolve(out,name+'.png'),fullPage:true});
  assert.deepEqual(errors,[]);results.push({engine:name,version:browser.version(),checks});
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});results.push({engine:name,checks,error:String(error),errors});console.error(await page.locator('body').innerText());throw error;}
 finally {await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');await browser.close();}
}
