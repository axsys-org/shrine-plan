// Real compiled Goo layouts and existing pane/input owners. No mocked render data.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {mkdir,writeFile} from 'node:fs/promises';
const [base,mash,out='/tmp/goo-pane-layout-browser']=process.argv.slice(2);
const require=createRequire(resolve(mash,'tests/integration/package.json'));
const engines=require('@playwright/test');
const expect=engines.expect.configure({timeout:45000});
await mkdir(out,{recursive:true});const results=[];
for(const name of (process.env.BROWSERS||'chromium,firefox,webkit').split(',')) {
 const browser=await engines[name].launch({headless:true});
 const page=await browser.newPage({viewport:{width:1400,height:1100}});
 const errors=[],renders=[];page.setDefaultTimeout(45000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(new URL(r.url()).pathname==='/goo/render')renders.push(Object.fromEntries(new URLSearchParams(r.postData())));});
 try {
  await page.goto(base+'/goo-inspector?path=%2F0x11%2Fapp%2Ftree_pages%2Froot');
  const sidebar=page.locator('.goo-pane[aria-label$="/Namespace"]');
  const leaf=page.locator('.goo-member[data-key$="/root/leaf"]');
  await expect(leaf).toHaveAttribute('data-goo-layout','sm');
  for(const width of [532,380,1400]) {
   await page.setViewportSize({width,height:1100});
   await expect.poll(()=>leaf.evaluate(el=>JSON.parse(el.dataset.renderContext).width===GooActions.context(el).width)).toBe(true);
   await expect.poll(()=>sidebar.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
   await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  }
  await page.locator('wa-tree-item[subject$="/root/wide"]').press('ArrowRight');
  await page.locator('wa-tree-item[subject$="/wide/c000"]').waitFor({state:'visible'});
  await page.locator('wa-tree-item[subject$="/wide/c000"]').press('ArrowRight');
  const deep=page.locator('wa-tree-item[subject$="/wide/c000/deep"]');
  await deep.waitFor({state:'visible'});await deep.press('Enter');
  await expect(page.locator('.goo-follow')).toContainText('Deferred grandchild');
  await page.setViewportSize({width:380,height:1100});
  await expect.poll(()=>sidebar.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await expect(deep).toHaveAttribute('aria-selected','true');
  await page.screenshot({path:resolve(out,name+'-inspector.png'),fullPage:true});

  // Mount a real native edit component into a deliberately resizable pane.
  // The test supplies only the allocation and standard pane descriptor; Goo
  // resolves the existing Grove view, controls, bindings and all geometry.
  await page.setViewportSize({width:1400,height:1100});
  await page.evaluate(async()=>{
   const target='/0x11/app/panes/cards/a',view='/0x11/gov/panes/edit';
   const data=await GooActions.load(target,{view,context:{width:240,textScale:1,direction:'ltr'}});
   const host=document.createElement('div');host.id='layout-specimen';host.className='goo-session';
   host.style.cssText='width:260px;max-width:none;margin:20px';document.body.append(host);
   const controller=new GooPanes(host,{target,view,report:message=>{host.dataset.diagnostic=message;}});
   globalThis.layoutSpecimen={host,controller};
   await controller.update([{kind:'native',node:'0',children:[]}],data.snapshot);
  });
  const host=page.locator('#layout-specimen'),frame=host.locator('.goo-native');
  const editor=frame.locator('input[data-input-slot="/sys/req"]');
  await expect(frame).toHaveAttribute('data-goo-layout','sm');
  const original='Card A';await editor.fill('Retained layout draft');
  await editor.evaluate(el=>{globalThis.retainedLayoutInput=el;el.setSelectionRange(2,8,'backward');});
  const initial=renders.filter(r=>r.view==='/0x11/gov/panes/edit' && r.node==='0').length;
  const resize=async(width,size)=>{
   await host.evaluate((el,width)=>{el.style.width=width+'px';},width);
   await expect(frame).toHaveAttribute('data-goo-layout',size);
   await expect.poll(()=>frame.evaluate(el=>el.gooDisplay.context.width===GooActions.context(el).width)).toBe(true);
   await expect.poll(()=>host.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  };
  await resize(520,'md');await resize(760,'lg');await resize(560,'md');
  assert.equal(renders.filter(r=>r.view==='/0x11/gov/panes/edit' && r.node==='0').length,initial,'resizing selects cached server layouts');
  assert.deepEqual(await editor.evaluate(el=>({same:el===retainedLayoutInput,focus:el===document.activeElement,value:el.value,start:el.selectionStart,end:el.selectionEnd})),
   {same:true,focus:true,value:'Retained layout draft',start:2,end:8});
  await editor.evaluate(el=>el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:'draft'})));
  await host.evaluate(el=>{el.style.width='300px';});
  // Wait for the actual allocation to settle, then confirm composition deferred installation.
  await expect.poll(()=>frame.evaluate(el=>GooActions.context(el).width)).toBe(240);
  assert.equal(await frame.getAttribute('data-goo-layout'),'md');
  await editor.evaluate(el=>el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'draft'})));
  await expect(frame).toHaveAttribute('data-goo-layout','sm');await expect(editor).toHaveValue('Retained layout draft');
  await resize(180,'sm');
  assert.equal(await frame.evaluate(el=>el.gooDisplay.context.width),180);
  await resize(760,'lg');
  await host.evaluate(el=>{el.dir='rtl';el.style.setProperty('--goo-text-scale','1.25');});
  await expect.poll(()=>frame.evaluate(el=>el.gooDisplay.context)).toEqual({width:720,textScale:1.25,direction:'rtl'});
  await expect(editor).toHaveValue('Retained layout draft');
  // A real action refresh changes the semantic basis; old cached content cannot return.
  await frame.getByRole('button',{name:'Save',exact:true}).click();
  await expect.poll(()=>host.getAttribute('data-diagnostic')).toBe('Saved.');
  await resize(520,'md');
  assert.equal(await editor.getAttribute('value'),'Retained layout draft');
  await editor.fill(original);await frame.getByRole('button',{name:'Save',exact:true}).click();
  await expect(editor).toHaveAttribute('value',original);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:resolve(out,name+'-editor.png'),fullPage:true});
  results.push({engine:name,version:browser.version(),passed:true});console.log(JSON.stringify(results.at(-1)));
 } catch(error) {await page.screenshot({path:resolve(out,name+'-failure.png'),fullPage:true});console.error(await page.locator('body').innerText());throw error;}
 finally {await browser.close();}
}
await writeFile(resolve(out,'results.json'),JSON.stringify(results,null,2)+'\n');
