// Real browser application gate. All view/source/action responses come from
// the mounted Reaver HTTP runtime; interception only delays real responses.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {join} from 'node:path';

const [base, mash, output, subset] = process.argv.slice(2);
const require = createRequire(join(mash, 'tests/integration/package.json'));
const {chromium, expect:baseExpect} = require('@playwright/test');
const expect=baseExpect.configure({timeout:45000});
const {exerciseTopoi} = createRequire(import.meta.url)('../tests/goo-topoi.browser.cjs');
const {exerciseActionsMount} = createRequire(import.meta.url)('../tests/goo-actions.browser.cjs');
const browser = await chromium.launch({headless:true});
const results = [], failures = [], renders = [], actions = [], actionResponses=[];
let lastGeometry=[];
const context = await browser.newContext({viewport:{width:1440,height:1100}});
const page = await context.newPage();
page.setDefaultTimeout(45000);
page.on('pageerror', error => failures.push(error.message));
page.on('request', request => {
  if (new URL(request.url()).pathname === '/goo/act') actions.push(request.postData());
});
page.on('response', async response => {
  if(new URL(response.url()).pathname === '/goo/act') {
    try { actionResponses.push({status:response.status(),body:await response.json()}); } catch {}
    return;
  }
  if (new URL(response.url()).pathname !== '/goo/render') return;
  try {
    const request=Object.fromEntries(new URLSearchParams(response.request().postData()));
    const packet=await response.json();
    const body=packet.layouts?.findLast(entry=>entry.render.context.width<=Number(request.width))?.render || packet;
    renders.push({request,status:response.status(),body});
  } catch {}
});
await page.addInitScript(() => {
  // Observe actual session instances without replacing their behavior.
  globalThis.__gooControllers = [];
  let implementation;
  Object.defineProperty(globalThis, 'GooPanes', {configurable:true,
    get:() => implementation,
    set:Class => { implementation = class extends Class {
      constructor(...args) { super(...args); globalThis.__gooControllers.push(this); }
    }; }
  });
});

const study = '/0x11/app/panes/study', cards = '/0x11/app/panes/cards';
const ownerSelector = id => `[data-owner=${JSON.stringify(id)}]`;
const workspace = () => page.locator('main .preview[data-view$="/panes/workspace"]');
const inspect = () => page.evaluate(() => {
  const controller = globalThis.__gooControllers.find(c => c.context.view.endsWith('/panes/workspace') && !c.session.closed);
  if (!controller) return null;
  return controller.session.inspect();
});
const selection = async () => (await inspect())?.owners.find(s => s.kind === 'selection' && s.id.includes('workspace_1'));
const follower = async () => (await inspect())?.owners.find(s => s.kind === 'follow' && s.id.includes('detail_1'));
const detail = async () => page.locator(ownerSelector((await follower()).id));
const row = async letter => {
  const state = (await inspect()).owners.find(s => ['list','topos'].includes(s.kind) && s.id.includes('queue_1'));
  return page.locator(ownerSelector(state.id)).locator(`[data-key$="/cards/${letter}"]`).first();
};
const accepted = async () => (await selection())?.accepted?.subject ?? null;
const choose = async letter => { await (await row(letter)).click(); };
const assertSelected = letter => expect.poll(accepted, {timeout:45000}).toBe(letter ? `${cards}/${letter}` : null);
async function step(name, run) {
  const start = Date.now();
  await run();
  results.push({name,milliseconds:Date.now()-start});
  console.log(`PASS ${name}`);
}
async function render(target, view, overrides = {}) {
  const response = await page.request.post(`${base}/goo/render`, {form:{target,view,width:'360',textScale:'1',direction:'ltr',...overrides}});
  assert.equal(response.status(), 200, await response.text());
  const data = await response.json();
  assert.equal(data.ok,true);
  return data;
}
async function assertGeometry() {
  const widths = await page.locator('[data-render-context]').evaluateAll(elements => elements.flatMap(element => {
    if (!element.gooDisplay || !element.getClientRects().length) return [];
    const surface=element.querySelector(':scope > .preview > .goo-presentation') || element;
    const style=getComputedStyle(surface);
    const available=surface.clientWidth-(parseFloat(style.paddingLeft)||0)-(parseFloat(style.paddingRight)||0);
    return available>0 ? [{available,prepared:element.gooDisplay.context.width}] : [];
  }));
  lastGeometry=widths;
  assert(widths.length>0,'Expected a mounted portable display');
  assert(widths.every(({available,prepared})=>prepared>0 && prepared<=available+.75),JSON.stringify(widths));
}

try {
  await step('real compiled endpoint and inert hydration', async () => {
    const data = await render(`${cards}/a`, '/0x11/gov/panes/content');
    assert.equal(data.profile.id,'mash-goo');
    assert.equal(data.context.width,360);
    assert.equal(data.context.direction,'ltr');
    assert.match(data.html,/Card A/);
    assert.equal(data.display.coordinates,'absolute-css-px');
    await page.goto(`${base}/views${study}`);
    await expect.poll(async () => (await inspect())?.owners.length || 0).toBeGreaterThan(0);
    await expect(workspace()).toBeVisible();
    await expect(await row('a')).toContainText('Card A');
    await expect.poll(async () => (await inspect()).owners.filter(s => s.kind === 'selection').some(s => s.accepted?.subject === `${cards}/a`)).toBe(true);
    await assertSelected(null);
    assert.equal(actions.length,0);
    assert.deepEqual(await page.evaluate(() => GooActions.metrics),{activations:0,dispatches:0});
  });

  await step('accepted selection and independent workspace', async () => {
    await choose('b');
    await assertSelected('b');
    await expect(await detail()).toContainText('Actions capture that context.');
    const choices = (await inspect()).owners.filter(s => s.kind === 'selection').map(s => s.accepted?.subject);
    assert(choices.includes(`${cards}/a`));
    assert.equal(actions.length,0);
  });

  await step('actual container resize and RTL context reach server', async () => {
    const count = renders.length;
    await workspace().evaluate(preview => { const element=preview.closest('.goo-view-host'); element.style.width='480px'; element.dir='rtl'; element.style.setProperty('--goo-text-scale','1.25'); });
    await expect.poll(() => renders.slice(count).some(r => r.status === 200 && r.body.context?.direction === 'rtl' && r.body.context?.textScale === 1.25 && r.body.context.width <= 480)).toBe(true);
    const contextual = renders.slice(count).findLast(r => r.status === 200 && r.body.context?.direction === 'rtl' && r.body.context?.textScale === 1.25);
    assert(contextual.body.context.width > 0);
    assert.equal(contextual.body.profile.id,'mash-goo');
    await expect.poll(async () => { try { await assertGeometry(); return true; } catch { return false; } }).toBe(true);
    await workspace().evaluate(preview => { const element=preview.closest('.goo-view-host'); element.style.width=''; element.dir='ltr'; element.style.setProperty('--goo-text-scale','1'); });
    await expect.poll(() => renders.at(-1)?.body.context?.direction).toBe('ltr');
    await assertSelected('b');
    await expect.poll(async () => { try { await assertGeometry(); return true; } catch { return false; } }).toBe(true);
  });

  await step('dirty editing and composition survive relayout and guard departure', async () => {
    await (await detail()).getByRole('button',{name:'Edit',exact:true}).click();
    const editor = (await detail()).locator('input[data-input-slot="/sys/req"]');
    await expect(editor).toHaveValue('Card B');
    await editor.fill('Card B unsaved integration draft');
    await editor.evaluate(input => { globalThis.__integrationInput=input; input.setSelectionRange(7,12); input.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:'draft'})); });
    await workspace().evaluate(preview => { preview.closest('.goo-view-host').style.width='440px'; });
    await choose('c');
    await assertSelected('b');
    await expect(editor).toHaveValue('Card B unsaved integration draft');
    assert.equal(await editor.evaluate(input => input === globalThis.__integrationInput),true);
    await editor.evaluate(input => input.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'draft'})));
    await choose('c');
    await expect((await detail()).getByRole('button',{name:'Stay',exact:true})).toBeVisible();
    await assertSelected('b');
    await (await detail()).getByRole('button',{name:'Stay',exact:true}).click();
    await expect(editor).toHaveValue('Card B unsaved integration draft');
    await choose('c');
    await (await detail()).getByRole('button',{name:'Discard and leave',exact:true}).click();
    await assertSelected('c');
    await expect(await detail()).toContainText('Recipes belong to the encounter.');
    assert.equal(actions.length,0);
  });

  await step('delayed real response cannot overwrite newer accepted selection', async () => {
    let release, finished;
    const held = new Promise(resolve => { release=resolve; });
    const delivered = new Promise(resolve => { finished=resolve; });
    let delayed=false, ready=false;
    const handler = async route => {
      const fields = new URLSearchParams(route.request().postData());
      if (!delayed && fields.get('target') === `${cards}/a` && (fields.get('slot')?.endsWith('/content') || fields.get('view')?.endsWith('/content'))) {
        delayed=true;
        const response = await route.fetch();
        ready=true;
        await held;
        try { await route.fulfill({response}); } catch {} finally { finished(); }
      } else await route.continue();
    };
    await page.route('**/goo/render',handler);
    try {
      await choose('a');
      await expect.poll(() => ready,{timeout:45000,message:'Expected actual A render request'}).toBe(true);
      await choose('c');
      await assertSelected('c');
      await expect(await detail()).toContainText('Recipes belong to the encounter.');
      release();
      await delivered;
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect.poll(async () => (await detail()).textContent()).not.toContain('Selection owns the context.');
      await assertSelected('c');
    } finally { release(); await page.unroute('**/goo/render',handler); }
    assert.equal(actions.length,0);
  });

  await step('real action persists accepted input and refreshes its projections', async () => {
    await choose('b');
    await assertSelected('b');
    await (await detail()).getByRole('button',{name:'Edit',exact:true}).click();
    const editor = (await detail()).locator('input[data-input-slot="/sys/req"]');
    await editor.fill('Card B saved by integration gate');
    const completed=page.waitForResponse(response=>new URL(response.url()).pathname==='/goo/act');
    await (await detail()).getByRole('button',{name:'Save',exact:true}).click();
    const response=await completed;
    assert.equal(response.status(),200,await response.text());
    await expect.poll(() => actions.length).toBe(1);
    await expect.poll(async () => (await render(`${cards}/b`,'/0x11/gov/panes/content')).display.nodes.some(node=>node.payload==='Card B saved by integration gate')).toBe(true);
    await expect(await row('b')).toContainText('Card B saved by integration gate');
    const metrics = await page.evaluate(() => GooActions.metrics);
    assert.equal(metrics.activations,1);
    assert.equal(metrics.dispatches,1);
  });

  await step('actual instance replacement retires old member lifetime', async () => {
    const before = await selection();
    const source = '/0x11/gov/panes', root = '/0x11/app/panes';
    const response = await page.request.get(`${base}/grove/dev/status`,{params:{source,root,selected:study}});
    assert.equal(response.status(),200,await response.text());
    const status = await response.json(), unit = status.units.find(unit => unit.source === source);
    assert(unit?.ready);
    const replaced = await page.request.post(`${base}/grove/dev/replace`,{form:{source,root,selected:study,expected:status.expected,version:unit.version,scan:unit.completed}});
    assert.equal(replaced.status(),200,await replaced.text());
    await page.getByRole('button',{name:'Refresh views',exact:true}).click();
    await expect.poll(async () => { const current=await selection(); return !!current?.source && current.source.life!==before.source.life; }).toBe(true);
    await assertSelected(null);
    await expect(await row('b')).toContainText('Card B');
    await expect(await row('b')).not.toContainText('saved by integration gate');
    assert(!(await inspect()).owners.some(state => state.kind === 'follow' && state.encounter?.member?.life === before.accepted?.life));
    assert.equal(actions.length,1,'namespace fixture replacement is not a Goo domain activation');
  });

  await step('real Mash topology hydration and focus projection', async () => {
    await page.waitForFunction(() => customElements.get('goo-tree') && customElements.get('goo-tidy-tree'));
    const result = await exerciseTopoi(page);
    results.push({topoi:result});
    assert.equal(actions.length,1);
  });
  await step('actual control remount preserves native state without duplicate events', async () => {
    results.push({controls:await exerciseActionsMount(page)});
    assert.equal(actions.length,1);
  });
  await page.screenshot({path:join(output,'panes.png'),fullPage:true});
  for(const hostName of subset==='--panes-only' ? [] : ['goo-inspector']) {
    await step(`${hostName} registered workspace and synthetic follower`, async () => {
      const requestStart=renders.length;
      await page.goto(`${base}/${hostName}?path=${encodeURIComponent(cards)}`);
      const host=page.locator('.goo-session[data-workspace]');
      await expect(host).toBeVisible();
      const hostedState=()=>page.evaluate(() => globalThis.__gooControllers.find(c=>!c.session.closed)?.session.inspect());
      await expect.poll(async () => (await hostedState())?.owners.filter(s=>s.kind==='selection').length || 0).toBe(1);
      const item=host.locator('[data-key$="/cards/a"]').first();
      await expect(item).toBeVisible();
      await item.click();
      await expect.poll(async () => (await hostedState()).owners.find(s=>s.kind==='selection')?.accepted?.subject).toBe(`${cards}/a`);
      const followState=(await hostedState()).owners.find(s=>s.kind==='follow');
      const content=page.locator(ownerSelector(followState.id));
      await expect(content).toContainText('Card A');
      await expect(content).toContainText('Selection owns the context.');
      assert(renders.slice(requestStart).some(r=>r.status===200&&r.request.workspace?.endsWith('/workspace')),'Expected trusted workspace render request');
      assert(renders.slice(requestStart).some(r=>r.status===200&&r.request.slot==='/sys/slot/synthetic'),'Expected structured synthetic follower render');
      await host.evaluate(element=>{element.style.width='700px';element.dir='rtl';element.style.setProperty('--goo-text-scale','1.1');});
      await expect.poll(async () => host.evaluate(element=>{const c=JSON.parse(element.dataset.renderContext||'{}');return c.direction==='rtl'&&c.textScale===1.1&&c.width<=700;})).toBe(true);
      await expect.poll(async () => { try { await assertGeometry(); return true; } catch { return false; } }).toBe(true);
      await expect(content).toContainText('Card A');
      assert.equal(actions.length,1,'Hosted hydration, selection and relayout must not activate domain actions');
      assert.deepEqual(await page.evaluate(()=>GooActions.metrics),{activations:0,dispatches:0});
      await page.screenshot({path:join(output,`${hostName}.png`),fullPage:true});
    });
  }
  assert.deepEqual(failures,[],'uncaught browser errors');
  await page.screenshot({path:join(output,'application.png'),fullPage:true});
  await writeFile(join(output,'browser-results.json'),JSON.stringify({base,subset:subset||null,results,renderResponses:renders.length,actionRequests:actions.length,actionResponses,failures},null,2)+'\n');
  console.log(`${subset ? 'Panes diagnostic subset' : 'Real application gate'} passed: ${results.filter(r=>r.name).length} scenarios, ${renders.length} real render responses, ${actions.length} deliberate action.`);
} catch (error) {
  await page.screenshot({path:join(output,'failure.png'),fullPage:true}).catch(()=>{});
  const state = await inspect().catch(()=>null);
  const text = await page.locator('body').innerText().catch(()=>null);
  await writeFile(join(output,'browser-failure.json'),JSON.stringify({results,failures,renders:renders.slice(-12),actions,actionResponses,state,text,lastGeometry,error:error.stack},null,2)+'\n');
  throw error;
} finally {
  await browser.close();
}
