// Operation UI contracts over a saved real shell and exact inert fixtures.
// No live fallback, route.fetch/continue, operation integration, or user state.
// Even the deliberate POSTs terminate here as held/rejected fixture responses.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

assert.ok(process.env.DEBUG_DOCUMENT, 'DEBUG_DOCUMENT is mandatory; the live namespace is never contacted');
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = fileURLToPath(new URL('..', import.meta.url));
const shell = await readFile(process.env.DEBUG_DOCUMENT, 'utf8');
const base = 'http://operation-ui-fixture.invalid';
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
  ['/forms.js', 'src/foil/debug/forms.js', 'application/javascript'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path), 'utf8'), contentType}])));
const reads = [], posts = [], rendered = [], unexpected = [], errors = [], screenshots = [], cases = [];
let activePage;
const browser = await chromium.launch();
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) { for (let i = 0; i < 120; i++) { if (await check()) return; await wait(25); } assert.fail(message); }
try {
  const author = await browser.newPage();
  const fixtures = await author.evaluate(shell => {
    const original = new DOMParser().parseFromString(shell, 'text/html');
    if (!original.querySelector('#debug-main > section[aria-label=Record] > sh-myth')) throw new Error('Saved shell is not the expected server document anatomy');
    const operationHTML = `
      <div class="opform fixture-authored" id="fixture-opform">
        <div class="muted fixture-authored" id="fixture-lede">Set the authored message. <code>Text is preserved.</code></div>
        <form method="post" action="/op/hello" class="wf fixture-authored" id="fixture-form">
          <ui-input id="fixture-message" class="fixture-authored" label="message" name="message" placeholder="text" required></ui-input>
          <ui-input id="fixture-disabled-input" class="fixture-authored" label="Unavailable field" name="excluded" value="not submitted" disabled></ui-input>
          <ui-input id="fixture-readonly-input" class="fixture-authored" label="Immutable context" name="context" value="fixed context" readonly></ui-input>
          <input id="fixture-op" class="fixture-authored" type="hidden" name="op" value="/hello/op/set_message">
          <ui-button id="fixture-submit" class="fixture-authored" type="submit" size="small" variant="secondary" tone="critical">set_message</ui-button>
          <ui-button id="fixture-locked" class="fixture-authored" type="submit" variant="ghost" disabled>Unavailable operation</ui-button>
        </form>
      </div>
      <div class="opform fixture-authored" id="fixture-existing-opform">
        <div class="muted fixture-authored" id="fixture-existing-lede">Existing field composition stays intact.</div>
        <form method="post" action="/op/hello" class="wf fixture-authored" id="fixture-existing-form">
          <ui-field id="fixture-existing-field" class="fixture-authored" label="Existing visible label" description="Authored supporting text" required>
            <ui-input id="fixture-existing-input" class="fixture-authored" slot="control" name="existing" placeholder="existing type" value="Existing value" required></ui-input>
          </ui-field>
          <ui-input id="fixture-invalid-input" class="fixture-authored" label="Invalid authored value" name="invalid" value="kept invalid" invalid></ui-input>
          <input type="hidden" name="op" value="/hello/op/existing">
          <ui-button id="fixture-existing-submit" class="fixture-authored" type="submit" variant="secondary">Apply existing fields</ui-button>
        </form>
      </div>
      <div class="opform fixture-authored" id="fixture-grove-opform">
        <div class="muted fixture-authored" id="fixture-grove-lede">Install the authored Grove template.</div>
        <form method="post" action="/grove/install" class="wf fixture-authored" id="fixture-grove-form">
          <label for="fixture-grove-name" id="fixture-grove-label" class="fixture-authored">Instance name</label>
          <input id="fixture-grove-name" class="fixture-authored" name="name" placeholder="instance-name" value="localcopy" pattern="[a-z]+" required>
          <input type="hidden" name="template" value="/gov/srs">
          <ui-button id="fixture-grove-submit" class="fixture-authored" type="submit" variant="secondary">Install Grove</ui-button>
        </form>
      </div>`;
    return Object.fromEntries(['/', '/hello', '/read-only', '/no-forms', '/child'].map(path => {
      const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
      Object.assign(ws.dataset, {path, kind: 'record', writable: String(path !== '/read-only'), label: 'Operation UI fixture', renderUrl: '/ns' + path});
      for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete ws.dataset[key];
      const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
      for (const [key, value] of [['/sys/lede', 'Authored operation fixture'], ['/message', 'Current namespace value']]) {
        const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text'; const slot = doc.createElement('sh-slot'); slot.title = key;
        const pail = doc.createElement('sh-pail'); pail.textContent = value; limb.append(slot, pail); myth.append(limb);
      }
      for (const name of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + name + '"]').replaceChildren();
      const operations = doc.querySelector('#debug-main section[aria-label=Operations]');
      operations.dataset.operationFixture = path === '/no-forms' ? 'no-forms' : 'forms';
      operations.innerHTML = path === '/no-forms' ? '<p class="muted">No registered operations at this path.</p>' : operationHTML;
      if (path !== '/no-forms') doc.querySelector('#debug-main section[aria-label=Semantics]').innerHTML = `
        <ui-card id="fixture-template-card" class="fixture-authored">
          <p>Create an independent instance using these definitions.</p>
          <form method="post" action="/grove/install" class="wf fixture-authored" id="fixture-template-form">
            <input type="hidden" name="source" value="/gov/srs"><input type="hidden" name="version" value="17">
            <label id="fixture-template-label" class="fixture-authored">Instance root <input id="fixture-template-root" class="fixture-authored" type="text" name="root" required placeholder="/app/srs"></label>
            <ui-button id="fixture-template-submit" class="fixture-authored" type="submit">Install instance</ui-button>
          </form>
        </ui-card>`;
      const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
      for (const child of path === '/' ? ['/hello', '/read-only', '/no-forms', '/child'] : []) {
        const item = doc.createElement('ui-tree-item'); item.dataset.path = child; item.title = child.slice(1); tree.append(item);
      }
      const snapshot = doc.createElement('script');
      snapshot.textContent = 'window.fixtureAuthoredNodes = [...document.querySelectorAll(".fixture-authored")]; window.fixtureAuthoredAttributes = Object.fromEntries(window.fixtureAuthoredNodes.map(el => [el.id, Object.fromEntries([...el.attributes].map(a => [a.name,a.value]))]));';
      doc.querySelector('script[src="/debug.js"]').before(snapshot);
      return [path, '<!doctype html>' + doc.documentElement.outerHTML];
    }));
  }, shell);
  await author.close();

  async function create(options = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 960}, ...options});
    context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(5000);
    const held = [], ownPosts = []; let hold = false;
    await context.addInitScript(({base}) => {
      if (window.top !== window || location.origin !== base || sessionStorage.getItem('operation-ui-fixture')) return;
      localStorage.setItem('shrine-debug.v1.saved', '[]');
      localStorage.setItem('shrine-debug.sidebar.v2', JSON.stringify({saved: false, recent: false, tree: false, root: '/', expanded: ['/']}));
      sessionStorage.setItem('operation-ui-fixture', 'seeded');
    }, {base});
    context.on('page', page => { page.on('pageerror', error => errors.push(error.message)); page.on('dialog', dialog => dialog.dismiss()); });
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== base || url.search) { unexpected.push(request.method() + ' ' + url.href); return route.abort(); }
      if (request.method() === 'POST' && ['/op/hello', '/grove/install'].includes(url.pathname)) {
        const body = new URLSearchParams(request.postData()), record = {path: url.pathname, data: [...body], contentType: request.headers()['content-type']};
        posts.push(record); ownPosts.push(record);
        const reject = () => route.fulfill({status: 409, contentType: 'text/plain', body: 'Isolated fixture rejection; no namespace operation occurred.'});
        if (hold) return new Promise(resolve => held.push(async () => { await reject(); resolve(); }));
        return reject();
      }
      if (request.method() !== 'GET') { unexpected.push(request.method() + ' ' + url.href); return route.abort(); }
      if (assets.has(url.pathname)) return route.fulfill(assets.get(url.pathname));
      if (url.pathname === '/helper') return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><script defer src="/debug-mash.js"></script><link rel="stylesheet" href="/debug-components.css"></head><body><section id="helper"><form id="helper-form"><ui-input id="helper-custom" label="Focused custom" name="custom" value="Exact draft" required></ui-input><label for="helper-native">Focused native</label><input id="helper-native" name="native" value="Native draft" required><label for="helper-labelled">External custom label</label><ui-input id="helper-labelled" label="Existing name" name="labelled"></ui-input><ui-input id="helper-associated" label="Associated name" aria-describedby="helper-description"></ui-input><p id="helper-description">Authored associated help</p></form></section></body></html>'});
      if (url.pathname === '/favicon.ico') return route.fulfill({status: 204, body: ''});
      if (url.pathname === '/ns/hello') { rendered.push(url.pathname); return route.fulfill({contentType: 'text/html', body: '<!doctype html><p>Isolated rendered fixture.</p>'}); }
      const path = url.pathname.startsWith('/debug') ? decodeURIComponent(url.pathname.slice(6)) || '/' : null;
      if (path && Object.hasOwn(fixtures, path)) { reads.push(path); return route.fulfill({contentType: 'text/html', body: fixtures[path]}); }
      unexpected.push(request.method() + ' ' + url.href); return route.abort();
    });
    const page = await context.newPage(); activePage = page;
    return {context, page, ownPosts, held, hold: value => hold = value};
  }
  async function ready(page, path = '/hello') {
    await page.waitForFunction(path => document.querySelector('#debug-workspace')?.dataset.path === path && document.querySelector('#debug-workspace')?.dataset.readState === 'ready' && document.querySelector('#debug-workspace')?.getAttribute('aria-busy') !== 'true', path, {timeout: 5000});
  }
  const control = (page, id) => page.locator('#' + id + ' input');
  const submit = page => page.locator('#fixture-submit button');
  async function open(page) {
    if (!await page.locator('#fixture-form').isVisible()) await page.getByRole('button', {name: 'Open operations', exact: true}).click();
    await page.locator('#fixture-form').waitFor({state: 'visible'});
  }
  async function identity(page) {
    assert.equal(await page.evaluate(() => window.fixtureAuthoredNodes.every(node => node.isConnected && document.getElementById(node.id) === node)), true, 'enhancement preserves every authored form/control/lede node');
    const state = await page.evaluate(() => {
      const form = document.querySelector('#fixture-form'), input = document.querySelector('#fixture-message'), button = document.querySelector('#fixture-submit');
      return {action: form.getAttribute('action'), method: form.getAttribute('method'), wf: form.classList.contains('wf'), input: Object.fromEntries(['label', 'name', 'placeholder', 'required'].map(key => [key, input.getAttribute(key)])),
        submit: Object.fromEntries(['type', 'size', 'variant', 'tone'].map(key => [key, button.getAttribute(key)])), label: button.textContent.trim(),
        op: document.querySelector('#fixture-op').value, hidden: document.querySelector('#fixture-op').type,
        existingField: document.querySelector('#fixture-existing-input').closest('ui-field')?.id,
        nestedFields: document.querySelectorAll('ui-field ui-field').length,
        nativeLabels: document.querySelector('#fixture-grove-name').labels.length,
        nativeLabel: document.querySelector('#fixture-grove-name').labels[0]?.textContent,
        nativeOwner: document.querySelector('#fixture-grove-name').form?.id,
        lede: document.querySelector('#fixture-lede').textContent};
    });
    assert.deepEqual(state.input, {label: 'message', name: 'message', placeholder: 'text', required: ''});
    assert.deepEqual(state.submit, {type: 'submit', size: 'small', variant: 'secondary', tone: 'critical'});
    assert.equal(state.action, '/op/hello'); assert.equal(state.method, 'post'); assert.equal(state.wf, true); assert.equal(state.label, 'set_message');
    assert.equal(state.op, '/hello/op/set_message'); assert.equal(state.hidden, 'hidden'); assert.equal(state.existingField, 'fixture-existing-field'); assert.equal(state.nestedFields, 0);
    assert.equal(state.nativeLabels, 1); assert.equal(state.nativeLabel, 'Instance name'); assert.equal(state.nativeOwner, 'fixture-grove-form');
    assert.equal(await page.locator('#fixture-template-root').evaluate(el=>el.closest('label')?.id),'fixture-template-label','real Grove input remains inside its original native label');
    assert.equal(await page.locator('#fixture-template-root').evaluate(el=>el.labels.length),1);
    assert.equal(await page.locator('#fixture-template-root').getAttribute('placeholder'),'/app/srs');
    assert.equal(await page.locator('#fixture-template-root').evaluate(el=>el.required&&el.form.id==='fixture-template-form'),true);
    assert.deepEqual(await page.locator('#fixture-template-form').evaluate(form=>{const data=new FormData(form);return [data.get('source'),data.get('version')];}),['/gov/srs','17']);
    assert.equal(state.lede, 'Set the authored message. Text is preserved.');
    assert.equal(await control(page, 'fixture-message').getAttribute('aria-label'), 'message');
    await settled(async()=>await control(page,'fixture-existing-input').getAttribute('aria-label')==='Existing visible label',
      'existing field forwards its authored accessible label: '+JSON.stringify(await page.locator('#fixture-existing-field').evaluate(el=>({field:el.outerHTML,input:el.querySelector('ui-input').shadowRoot?.innerHTML}))));
    assert.equal(await control(page, 'fixture-message').evaluate(el => el.required), true);
    assert.equal(await control(page, 'fixture-disabled-input').isDisabled(), true);
    assert.equal(await control(page, 'fixture-readonly-input').getAttribute('readonly') !== null, true);
    assert.equal(await control(page, 'fixture-invalid-input').getAttribute('aria-invalid'), 'true');
    assert.equal(await page.locator('#fixture-locked button').isDisabled(), true);
  }
  async function visibleLabels(page) {
    for (const [id, text] of [['fixture-message', 'message'], ['fixture-disabled-input', 'Unavailable field'], ['fixture-readonly-input', 'Immutable context'], ['fixture-invalid-input', 'Invalid authored value']]) {
      const label = page.locator('#' + id).locator('..').locator('label[part=label]');
      assert.equal(await label.count(), 1, 'otherwise-unlabelled operation input gets one existing Mash field label');
      assert.match(await label.textContent(), new RegExp(text)); const box = await label.boundingBox(); assert.ok(box.width > 15 && box.height > 8, 'authored field name is visibly projected');
    }
  }
  async function layout(page, coarse) {
    const boxes = await page.evaluate(() => {
      const rect = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}; };
      const controls = [...document.querySelectorAll('#wb-operations ui-input')].map(host => ({id:host.id, ...rect(host.shadowRoot.querySelector('input'))}));
      controls.push({id:'fixture-grove-name', ...rect(document.querySelector('#fixture-grove-name'))});
      controls.push({id:'fixture-template-root', ...rect(document.querySelector('#fixture-template-root'))});
      const buttons = [...document.querySelectorAll('#wb-operations ui-button,#fixture-template-submit')].map(host => ({id:host.id, ...rect(host.shadowRoot.querySelector('button'))}));
      const forms = [...document.querySelectorAll('#wb-operations form,#fixture-template-form')].map(form => ({id:form.id, ...rect(form), scroll:form.scrollWidth, client:form.clientWidth}));
      return {controls, buttons, forms, width:innerWidth, scroll:document.documentElement.scrollWidth};
    });
    assert.ok(boxes.scroll <= boxes.width + 1, 'document does not horizontally overflow');
    for (const box of [...boxes.controls, ...boxes.buttons]) assert.ok(box.width >= (coarse ? 43.9 : 20) && box.height >= (coarse ? 43.9 : 20) && box.x >= -1 && box.right <= boxes.width + 1, 'actual native control fits and retains shared target: ' + JSON.stringify(box));
    for (const form of boxes.forms) assert.ok(form.width > 100 && form.scroll <= form.client + 1, 'operation form fits without hidden horizontal content: ' + JSON.stringify(form));
    for (const id of ['fixture-grove-name','fixture-template-root']) {
      const appearance=await page.locator('#'+id).evaluate(el=>{const s=getComputedStyle(el);return {group:el.closest('ui-input-group')?.getAttribute('typography'),border:s.borderTopWidth,padding:s.paddingInlineStart,background:s.backgroundColor};});
      assert.deepEqual(appearance,{group:'code',border:'0px',padding:'0px',background:'rgba(0, 0, 0, 0)'},'native control uses the single shared group surface, not an unlayered legacy input override');
    }
    for (let i=0;i<boxes.controls.length;i++) for(let j=i+1;j<boxes.controls.length;j++) {
      const a=boxes.controls[i],b=boxes.controls[j]; assert.ok(a.right <= b.x+.5 || b.right <= a.x+.5 || a.bottom <= b.y+.5 || b.bottom <= a.y+.5, 'native input targets never overlap');
    }
    await visibleLabels(page);
  }
  async function capture(page, name) { const path = '/private/tmp/shrine-operation-ui-' + name + '.png'; await page.screenshot({path, animations:'disabled'}); screenshots.push(path); }

  const test = await create(); await test.page.goto(base + '/debug/no-forms'); await ready(test.page, '/no-forms');
  assert.equal(await test.page.locator('#wb-operations-toggle').isVisible(), false); assert.equal(await test.page.locator('#wb-operations form').count(), 0); assert.equal(test.ownPosts.length, 0);
  cases.push('no operations means no actionable drawer');
  await test.page.goto(base + '/debug/hello'); await ready(test.page); await open(test.page); await identity(test.page); await visibleLabels(test.page);
  const message = control(test.page,'fixture-message');
  await test.page.locator('ui-field[data-debug-form-field]').filter({has:test.page.locator('#fixture-message')}).locator('label[part=label]').click();
  assert.equal(await message.evaluate(el=>el.getRootNode().activeElement===el),true,'visible Mash label focuses its preserved input');
  await submit(test.page).click(); assert.equal(test.ownPosts.length,0, 'required empty custom input prevents submission');
  assert.equal(await message.evaluate(el=>el.getRootNode().activeElement===el),true, 'required validation focuses the actual field');
  const draft = '  Keep my unsent draft λ & reserved=characters  '; await message.fill(draft); test.hold(true); await submit(test.page).click();
  await settled(()=>test.held.length===1,'one real fixture request is held');
  assert.equal(await submit(test.page).isDisabled(),true); await test.page.locator('#fixture-form').evaluate(form=>form.requestSubmit()); assert.equal(test.ownPosts.length,1,'busy guard prevents duplicate submissions');
  const data = new URLSearchParams(test.ownPosts[0].data); assert.equal(data.get('message'),draft); assert.equal(data.get('context'),'fixed context'); assert.equal(data.has('excluded'),false); assert.equal(data.get('op'),'/hello/op/set_message'); assert.equal(data.get('back'),'/debug/hello');
  await message.focus(); await Promise.all(test.held.splice(0).map(release=>release())); test.hold(false);
  await settled(async()=>!(await submit(test.page).isDisabled()) && (await test.page.locator('#debug-status').textContent()).includes('Operation rejected (HTTP 409)'),'rejection settles into actionable error');
  assert.equal(await message.inputValue(),draft); assert.equal(await message.evaluate(el=>el.getRootNode().activeElement===el),true,'rejection does not steal focus from edited draft'); await identity(test.page);
  const formdata=await test.page.locator('#fixture-form').evaluate(form=>[...new FormData(form)]); assert.equal(new URLSearchParams(formdata).get('message'),draft);
  cases.push('required validation, exact FormData, duplicate guard, rejection draft and focus retention');
  await test.page.locator('#wb-mode-rendered button').click(); assert.equal(await test.page.locator('#wb-operations-toggle').isVisible(),false);
  await test.page.locator('#fixture-form').evaluate(form=>form.requestSubmit()); await settled(async()=>(await test.page.locator('#debug-status').textContent()).includes('read-only'),'rendered mode rejects programmatic submission'); assert.equal(test.ownPosts.length,1);
  await test.page.locator('#wb-mode-inspect button').click(); await open(test.page); await identity(test.page); assert.equal(await message.inputValue(),draft);
  // Native Grove validation remains native; no replacement or proxy form.
  const native = test.page.locator('#fixture-grove-name'); await native.fill('INVALID VALUE'); await test.page.locator('#fixture-grove-submit button').click(); assert.equal(test.ownPosts.length,1); assert.equal(await native.evaluate(el=>el.validity.patternMismatch),true);
  await native.fill('newinstance'); await test.page.locator('#fixture-grove-submit button').click(); await settled(()=>test.ownPosts.length===2,'native Grove fixture posts once');
  await settled(async()=>(await test.page.locator('#debug-workspace').getAttribute('aria-busy'))==='false','native rejection settles');
  assert.equal(new URLSearchParams(test.ownPosts[1].data).get('name'),'newinstance'); assert.equal(new URLSearchParams(test.ownPosts[1].data).get('template'),'/gov/srs'); assert.equal(await native.inputValue(),'newinstance');
  await settled(async()=>await test.page.locator('#fixture-grove-submit button').evaluate(el=>el.getRootNode().activeElement===el),
    'rejected operation restores its still-enabled invoking control when the user has not moved focus');
  await test.page.locator('#fixture-template-submit button').click(); assert.equal(test.ownPosts.length,2,'native semantic required field blocks an empty root');
  await test.page.locator('#fixture-template-root').fill('/app/new-instance'); await test.page.locator('#fixture-template-submit button').click();
  await settled(()=>test.ownPosts.length===3,'real semantic Grove form posts only to the fixture');
  await settled(async()=>(await test.page.locator('#debug-workspace').getAttribute('aria-busy'))==='false','semantic native rejection settles');
  const templateData=new URLSearchParams(test.ownPosts[2].data); assert.equal(templateData.get('root'),'/app/new-instance'); assert.equal(templateData.get('source'),'/gov/srs'); assert.equal(templateData.get('version'),'17');
  cases.push('mode read-only and native Grove validation/identity');
  await test.page.goto(base+'/debug/read-only'); await ready(test.page,'/read-only'); assert.equal(await test.page.locator('#wb-operations-toggle').isVisible(),false); assert.equal(await submit(test.page).isDisabled(),true);
  await test.page.locator('#fixture-message').evaluate(async el=>{el.value='Attempted fixture';await el.updateComplete;}); await test.page.locator('#fixture-form').evaluate(form=>form.requestSubmit());
  await settled(async()=>(await test.page.locator('#debug-status').textContent()).includes('read-only'),'read-only server response guards direct submission'); assert.equal(test.ownPosts.length,3);
  cases.push('server read-only rejects programmatic submissions'); await test.context.close();

  const helper=await create(); await helper.page.goto(base+'/helper');
  await helper.page.waitForFunction(()=>document.querySelector('#helper-custom')?.shadowRoot?.querySelector('input'),null,{timeout:5000});
  await helper.page.evaluate(async()=>{window.fixtureEnhance=(await import('/forms.js')).enhanceForms;window.helperNodes=[...document.querySelector('#helper-form').children];window.helperNative=document.querySelector('#helper-native');window.helperNative.remove();});
  await helper.page.locator('#helper-custom input').fill('Still editing exact draft'); await helper.page.locator('#helper-custom input').focus();
  await helper.page.evaluate(()=>window.fixtureEnhance(document.querySelector('#helper')));
  assert.equal(await helper.page.locator('#helper-custom').evaluate(el=>el.parentElement.id),'helper-form','focused custom control is not reparented');
  assert.equal(await helper.page.locator('#helper-custom input').evaluate(el=>el.getRootNode().activeElement===el),true);
  await helper.page.evaluate(()=>document.querySelector('#helper-form').append(window.helperNative));
  await helper.page.locator('#helper-native').focus(); await helper.page.evaluate(()=>window.fixtureEnhance(document.querySelector('#helper')));
  assert.equal(await helper.page.locator('#helper-native').evaluate(el=>el.parentElement.id),'helper-form','focused native control is not reparented');
  assert.equal(await helper.page.locator('#helper-native').evaluate(el=>document.activeElement===el),true);
  await helper.page.locator('#helper-native').blur(); await helper.page.evaluate(()=>window.fixtureEnhance(document.querySelector('#helper')));
  const wrappers=await helper.page.evaluateHandle(()=>[...document.querySelectorAll('[data-debug-form-field],[data-debug-form-native]')]);
  await helper.page.evaluate(()=>{window.fixtureEnhance(document.querySelector('#helper'));window.fixtureEnhance(document.querySelector('#helper'));});
  assert.equal(await wrappers.evaluate(nodes=>nodes.length===2&&nodes.every(el=>el.isConnected)),true,'repeated helper calls retain exactly the existing field and native group');
  assert.equal(await helper.page.locator('#helper-labelled').evaluate(el=>el.parentElement.id),'helper-form','external label ownership is not duplicated');
  assert.equal(await helper.page.locator('#helper-associated').evaluate(el=>el.parentElement.id),'helper-form','authored aria association is not rewritten');
  assert.equal(await helper.page.evaluate(()=>window.helperNodes.every(el=>el.isConnected)),true,'helper preserves every authored node');
  assert.equal(await helper.page.locator('#helper-custom input').inputValue(),'Still editing exact draft');
  assert.equal(await helper.page.locator('#helper-form').evaluate(el=>new FormData(el).get('custom')),'Still editing exact draft');
  assert.equal(await helper.page.locator('#helper-native').evaluate(el=>el.required&&el.form.id==='helper-form'),true);
  cases.push('helper idempotence, focused-control skip, existing labels and native owner preservation'); await helper.context.close();

  for(const width of [1440,768,390]) for(const coarse of [false,true]) {
    const view=await create({viewport:{width,height:width===390?844:1000},hasTouch:coarse}); await view.page.goto(base+'/debug/hello'); await ready(view.page); await open(view.page); await identity(view.page);
    await control(view.page,'fixture-message').fill('A retained responsive draft');
    for(const scheme of ['light','dark']) {
      await view.page.emulateMedia({colorScheme:scheme,reducedMotion:'reduce'}); await layout(view.page,coarse);
      await control(view.page,'fixture-message').focus(); await control(view.page,'fixture-message').press('ArrowLeft');
      assert.equal(await control(view.page,'fixture-message').evaluate(el=>el.getRootNode().activeElement===el),true);
      const focus=await control(view.page,'fixture-message').evaluate(el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect(),outset=parseFloat(s.outlineWidth)+parseFloat(s.outlineOffset);return {visible:el.matches(':focus-visible'),style:s.outlineStyle,width:parseFloat(s.outlineWidth),left:r.left-outset,right:r.right+outset,viewport:innerWidth};});
      assert.ok(focus.visible&&focus.style!=='none'&&focus.width>0&&focus.left>=0&&focus.right<=focus.viewport,'shared keyboard focus remains visible and horizontally contained: '+JSON.stringify(focus));
      await view.page.locator('#fixture-opform').scrollIntoViewIfNeeded();
      await capture(view.page,scheme+'-'+width+(coarse?'-touch':''));
      await view.page.locator('#fixture-grove-opform').scrollIntoViewIfNeeded(); await layout(view.page,coarse); await capture(view.page,'grove-'+scheme+'-'+width+(coarse?'-touch':''));
      await view.page.locator('#fixture-template-card').scrollIntoViewIfNeeded(); await layout(view.page,coarse); await capture(view.page,'template-'+scheme+'-'+width+(coarse?'-touch':''));
    }
    assert.equal(view.ownPosts.length,0,'responsive checks never submit fixture operations'); await view.context.close();
  }
  assert.deepEqual(unexpected,[]); assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,cases,fixtureReads:reads.length,fixturePosts:posts.length,renderedFixtures:rendered.length,liveReads:0,liveWrites:0,unexpected:0,errors:0,screenshots},null,2));
} catch(error) {
  if(activePage&&!activePage.isClosed()) {
    await activePage.screenshot({path:'/private/tmp/shrine-operation-ui-failure.png',animations:'disabled'}).catch(()=>{});
    const focus=await activePage.evaluate(()=>{const active=document.activeElement;return {documentFocused:document.hasFocus(),active:active?.localName,id:active?.id,shadowActive:active?.shadowRoot?.activeElement?.outerHTML,submit:document.querySelector('#fixture-grove-submit')?.outerHTML};}).catch(()=>null);
    console.error(JSON.stringify({url:activePage.url(),errors,unexpected,posts,focus},null,2));
  }
  throw error;
} finally { await browser.close(); }
