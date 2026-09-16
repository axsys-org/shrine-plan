// Read-only UI verification against a manifest-owned real Grove namespace.
import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {playwright} from './debug-tooling.mjs';
const root=fileURLToPath(new URL('..',import.meta.url));
assert.ok(process.env.GROVE_RUNTIME);
const runtime=JSON.parse(execFileSync(process.env.PYTHON || 'python3',[root+'/x/debug-grove-runtime.py','verify',process.env.GROVE_RUNTIME],{encoding:'utf8'}));
assert.match(runtime.node, /^0x(?:[0-9a-f]{2})+$/);
assert.ok(!runtime.node.endsWith('00'));
const authority = '/' + runtime.node;
assert.notEqual(new URL(runtime.origin).port,'8138');
const seal=JSON.parse(await readFile(runtime.work+'/assets.json','utf8'));
const {chromium}=playwright();
const browser=await chromium.launch(), errors=[], requests=[], violations=[], checks=[], pending=[];
try {
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  context.setDefaultTimeout(10000);
  await context.addInitScript(origin=>{
    if(location.origin!==origin)return;
    localStorage.setItem('shrine-debug.sidebar.v2',JSON.stringify({saved:false,recent:false,tree:false,root:'/',expanded:[]}));
  },runtime.origin);
  await context.route('**/*',route=>{
    const request=route.request(), url=new URL(request.url());
    requests.push({method:request.method(),path:url.pathname+url.search});
    if(url.origin!==runtime.origin||request.method()!=='GET'||requests.length>45){violations.push(request.url());return route.abort();}
    return route.continue();
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('response',response=>{
    const path=new URL(response.url()).pathname,asset=seal.assets[path];
    if(asset)pending.push(response.body().then(body=>assert.equal(createHash('sha256').update(body).digest('hex'),asset.sha256,path)));
  });
  await page.goto(runtime.origin+'/debug'+authority);
  await page.waitForFunction(()=>document.querySelector('#debug-workspace')?.dataset.readState==='ready');
  assert.equal(await page.locator('[data-grove-contract="debugger/v1"]').count(),1);
  assert.match(await page.locator('.wb-manifest').innerText(),/eden/);
  assert.match(await page.locator('.wb-manifest').innerText(),/Eden: the live namespace/);
  checks.push('published Grove page renders the native mani');
  const kooks=page.locator('.wb-manifest ui-accordion-item[value=kooks]');
  await kooks.locator('button').first().click();assert.equal(await kooks.evaluate(n=>n.open),false);
  await kooks.locator('button').first().click();assert.equal(await kooks.evaluate(n=>n.open),true);
  const seed=page.locator('.wb-manifest sh-path-row[previewable]').first();
  await seed.locator('ui-button').click();assert.equal(await seed.evaluate(n=>n.open),true);
  checks.push('Mash disclosures and inline seed previews');
  const menu=page.locator('.wb-path-menu').first();
  await menu.locator('[slot=trigger]').click();
  await page.waitForFunction(()=>document.querySelector('.wb-path-menu')?.open);
  await menu.locator('ui-menu-item').first().waitFor();
  assert.ok(await menu.locator('ui-scroll-area[mode=scrolling][size=medium]').count()>0);
  await page.keyboard.press('Escape');checks.push('Grove menu rows with Mash scrolling');
  await page.locator('#debug-inspector-toggle').click();
  assert.equal(await page.locator('.wb-inspector [data-care]').count(),3);
  assert.ok(await page.locator('.wb-inspector [data-care=x] .wb-case-link').count()<=5);
  checks.push('three bounded inspector case lanes');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:runtime.work+'/grove-debugger-desktop.png'});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:runtime.work+'/grove-debugger-narrow.png'});
  checks.push('responsive document without horizontal overflow');
  if(runtime.entry === 'eden:start-debug') {
    await page.goto(runtime.origin + '/debug' + authority + '/gov');
    await page.waitForFunction(()=>document.querySelector('#debug-workspace')?.dataset.readState === 'ready');
    const children = await page.locator('#debug-source-metadata').evaluate(template =>
      [...template.content.querySelectorAll('[data-path]')].map(node=>node.dataset.path));
    assert.ok(!children.includes(authority + '/gov/srs'),'debugger-only startup does not publish the optional SRS app');
    assert.equal(await page.locator('[data-grove-contract="debugger/v1"]').count(),1);
    checks.push('debugger startup independent of SRS');
  }
  await Promise.all(pending);assert.deepEqual(errors,[]);assert.deepEqual(violations,[]);
  const evidence={passed:true,origin:runtime.origin,runtimeId:runtime.id,checks,errors,violations,requests};
  await writeFile(runtime.work+'/declaration-ui-evidence.json',JSON.stringify(evidence,null,2));
  console.log(JSON.stringify(evidence));
}finally{await browser.close();}
