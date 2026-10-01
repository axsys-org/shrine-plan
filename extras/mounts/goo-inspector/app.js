(async function() {
  'use strict';
  const M = GooInspector, host = document.querySelector('#workspace');
  const notice = document.querySelector('#notice'), address = document.querySelector('#path');
  const navigation = new M.Generation(), observation = new M.Generation();
  let controller, browsePath, inspectedKey = '', unsubscribe;
  const element = (tag, text, cls) => { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; };
  const report = text => { notice.textContent = text; };
  const anchor = (text, href) => { const a = element('a',text); a.href = href; return a; };
  const button = (text, fn) => { const b = element('button',text); b.type='button'; b.addEventListener('click',fn); return b; };
  function chosen() {
    const selection = [...controller.session.owners.values()].find(s => s.kind === 'selection');
    return selection ? controller.session.read(selection.ref).accepted : null;
  }
  function context() {
    const selected = chosen();
    return {target:selected?.subject || browsePath, selected};
  }
  async function read(target, extra = {}) {
    const query = new URLSearchParams({scope:'workspace',...extra});
    const response = await fetch('/debug' + (target === '/' ? '' : M.urlPath(target)) + '?' + query, {cache:'no-store',signal:AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error(`Inspection read failed (${response.status}); refresh if its epoch expired.`);
    const doc = new DOMParser().parseFromString(await response.text(),'text/html');
    const metadata = doc.querySelector('template#debug-read-descriptor');
    if (!metadata) throw new Error('Inspection read metadata unavailable.');
    return M.descriptor(JSON.parse(metadata.content.textContent), target);
  }
  async function bounded(promise) {
    let timer;
    try { return await Promise.race([promise,new Promise((_,reject)=>{ timer=setTimeout(()=>reject(new Error('View read timed out. Narrow the path or retry.')),30000); })]); }
    finally { clearTimeout(timer); }
  }
  function preview(template) {
    const copy = template.cloneNode(true);
    // Never bind action handlers to previews. Keep their text accessible while
    // disabling controls and links. The only live Goo follower is synthetic.
    for (const node of copy.querySelectorAll('script,iframe,object,embed')) node.remove();
    for (const node of copy.querySelectorAll('a')) { node.removeAttribute('href'); node.tabIndex = -1; }
    for (const node of copy.querySelectorAll('[contenteditable]')) node.contentEditable = 'false';
    for (const node of copy.querySelectorAll('button,input,textarea,select,fieldset')) node.disabled = true;
    return copy;
  }
  function field(list, key, value) { list.append(element('dt',key),element('dd',String(value ?? 'unavailable'))); }
  function evidence(target, data, status) {
    const panel = host.querySelector('#evidence'); panel.replaceChildren(element('h2','Observation evidence'));
    const facts = element('dl','');
    field(facts,'Subject',target); field(facts,'State',data.state);
    field(facts,'Inspection epoch',data.collection.epoch);
    field(facts,'Record version (x)',status.expected); field(facts,'Presentation version (y)',status.displayed);
    field(facts,'Record lifetime',status.life); field(facts,'View publication',status.publication);
    field(facts,'Physical children',data.collection.childCount); field(facts,'Slots',data.collection.slotCount);
    field(facts,'Namespace authority',data.namespaceRoot);
    panel.append(facts,element('p','Inspection metadata and Goo rendering are separately versioned observations. Refresh to observe newer state. No cross-endpoint atomic snapshot is implied.','hint'));
    const links = element('nav','');
    links.append(anchor('Exact values, versions & provenance','/debug'+M.urlPath(target)),anchor('Objects & operations','/ns'+M.urlPath(target)),anchor('Interactive views','/views'+M.urlPath(target)));
    panel.append(links);
    if (data.previewSlots?.length) {
      panel.append(element('h3','Slot excerpts'));
      const slots = element('dl','');
      for (const slot of data.previewSlots) {
        field(slots,slot.key,slot.text);
        if (slot.reference) { try { slots.append(anchor('Follow '+slot.reference,M.link(slot.reference))); } catch {} }
      }
      panel.append(slots,element('p','At most three excerpts from the existing inspection reader. Full bounded reflection is in Values.','hint'));
    }
  }
  function catalog(target, data, expanded) {
    const panel = host.querySelector('#view-catalog'); panel.replaceChildren(element('h2','Matching views'));
    panel.append(element('p','Read-only previews. Open the explorer to use actions. Pane compositions are not mounted inside these views.','hint'));
    const authored = data.templates.filter(t => t.dataset.slot !== M.SYNTHETIC && t.dataset.slot !== '/sys/slot/inspector_summary');
    if (!authored.length) panel.append(element('p','No authored views match this object.'));
    for (const template of authored) {
      const section = element('details',''); section.dataset.view = template.dataset.view; section.open = expanded.has(template.dataset.view);
      section.append(element('summary',`${template.dataset.slot} · ${template.dataset.view}`));
      const links = element('nav','');
      links.append(anchor('Inspect declaration',M.link(template.dataset.view)),anchor('Open interactive explorer','/views'+M.urlPath(target)));
      if (template.dataset.role) links.append(anchor('Inspect role',M.link(template.dataset.role)));
      section.append(links);
      if (template.querySelector('.goo-session')) section.append(element('p','This view declares a pane composition. Open it separately.','hint'));
      else section.append(preview(template));
      panel.append(section);
    }
  }
  async function inspect(force = false) {
    const {target,selected} = context();
    const key = JSON.stringify([target,selected?.life,selected?.expected,selected?.status]);
    host.dataset.selected = selected ? 'true' : 'false';
    if (!force && inspectedKey === key) return;
    inspectedKey = key;
    const ticket = observation.next();
    const oldCatalog = host.querySelector('#view-catalog');
    const expanded = new Set(oldCatalog?.dataset.target === target ? [...oldCatalog.querySelectorAll('details[open]')].map(d => d.dataset.view) : []);
    for (const id of ['view-catalog','evidence','current-values']) host.querySelector('#'+id)?.replaceChildren(element('p','Reading '+target+'…','hint'));
    if (selected && selected.status !== 'available') {
      for (const id of ['view-catalog','evidence']) host.querySelector('#'+id)?.replaceChildren(element('p','Selected record is unavailable. Clear selection or inspect another object.'));
      return;
    }
    try {
      const data = await read(target,{scope:'preview'});
      if (!observation.current(ticket)) return;
      const large = target.split('/').filter(Boolean).length <= 2 || BigInt(data.collection.childCount) > 64n;
      const views = large || !data.hasRecord ? {snapshot:{},templates:[]} : await bounded(GooActions.load(target));
      if (!observation.current(ticket)) return;
      if (selected && !large && (views.snapshot.life !== selected.life || views.snapshot.target !== selected.subject)) throw new Error('Selected record was replaced. Refresh the namespace.');
      catalog(target,views,expanded);
      if (large) host.querySelector('#view-catalog').append(element('p','View materialization is deferred for broad namespace roots and collections over 64 children. Inspect a child or use the full debugger.','hint'));
      host.querySelector('#view-catalog').dataset.target=target; evidence(target,data,views.snapshot);
      const current = host.querySelector('#current-values');
      if (!selected) {
        current.replaceChildren(element('h2',target));
        const synthetic = views.templates.find(t => t.dataset.slot === M.SYNTHETIC);
        current.append(large ? element('p','Large collection: use the bounded child navigation. Select a narrower path for Goo reflection.') : !data.hasRecord ? element('p','Structural namespace path; no own record. Browse its children.') : synthetic ? preview(synthetic) : element('p','No synthetic view available.'));
      }
      report(selected ? 'Selected '+target+' · read-only' : 'Inspecting '+target+' · select a child or browse deeper');
      const nav = host.querySelector('#navigation');
      let drill = nav.querySelector('[data-drill]');
      if (!drill) { drill = button('Browse selected children',()=>open(context().target)); drill.dataset.drill=''; nav.prepend(drill); }
      drill.disabled = !selected;
    } catch (error) {
      if (!observation.current(ticket)) return;
      inspectedKey = ''; report(error.message);
      for (const id of ['view-catalog','evidence','current-values']) host.querySelector('#'+id)?.replaceChildren(element('p',error.message,'error'));
    }
  }
  function navigationPanel(data, usable, ticket) {
    const panel = host.querySelector('#navigation'); panel.replaceChildren(element('h2',browsePath));
    panel.append(element('p',`${data.collection.childCount} children · ${data.collection.slotCount} slots`,'hint'));
    if (usable) {
      panel.append(element('p','Click or Enter selects; arrows move focus. Browse selected children descends into that object.','hint'));
      if (data.collection.childCount === '0') panel.append(element('p','No children. Values shows the current object.'));
      return;
    }
    panel.append(element('p','Using paginated navigation: this is a broad namespace root, structural path, or collection beyond the Goo source bound. Links open a new workspace.','hint'));
    const list = element('nav',''); list.className = 'child-links'; panel.append(list);
    const append = page => { for (const child of page.children) list.append(anchor(`${child.path} — ${child.label}`,M.link(child.path))); };
    append(data);
    let next = data.collection.nextChildren;
    const more = button('Next children',async()=>{
      more.disabled=true;
      try {
        const page = await read(browsePath,{scope:'outline',epoch:data.collection.epoch,children:next});
        if (!navigation.current(ticket)) return;
        // Replace a bounded page rather than retaining an unbounded DOM/cache.
        list.replaceChildren(); append(page); next=page.collection.nextChildren; more.hidden=!next;
      } catch(error) { report(error.message); }
      finally { more.disabled=false; }
    });
    more.hidden = !next; panel.append(more);
  }
  async function open(target, historyMode = 'push') {
    try { target = M.path(target); if (target === '/') target = GOO_INSPECTOR_ROOT; } catch(error) { report(error.message); return; }
    if (target === GOO_INSPECTOR_ROOT + '/lib') {
      report('The printable-path inspection reader cannot enumerate this library root safely. Enter a narrower library path or use the existing debugger physical inspector.');
      return;
    }
    const ticket = navigation.next(); observation.next(); inspectedKey='';
    document.querySelector('#refresh').disabled=true; host.inert=true; report('Reading '+target+'…');
    try {
      const data = await read(target,{scope:'outline'});
      if (!navigation.current(ticket)) return;
      let source = {bounded:false,life:'0'};
      if (data.hasRecord && target.split('/').filter(Boolean).length > 2 && BigInt(data.collection.childCount) <= 64n) {
        const response = await fetch('/goo/source?'+new URLSearchParams({target}),{cache:'no-store',signal:AbortSignal.timeout(30000)});
        if (!response.ok) throw new Error('Namespace source unavailable.');
        source = await response.json();
      }
      if (!navigation.current(ticket)) return;
      const usable = data.hasRecord && source.bounded && source.life !== '0';
      if (target !== browsePath || controller?.usable !== usable || controller?.sourceLife !== source.life) {
        unsubscribe?.();
        if (controller) await controller.close();
        if (!navigation.current(ticket)) return;
        controller = new GooPanes(host,{target,view:'',report,refresh:()=>open(browsePath,'replace')});
        controller.usable=usable; controller.sourceLife=source.life;
        browsePath=target;
      }
      unsubscribe?.(); unsubscribe = null;
      await controller.update(M.composition(target,usable),{path:target});
      if (!navigation.current(ticket)) return;
      navigationPanel(data,usable,ticket);
      unsubscribe?.(); unsubscribe=controller.session.subscribe(()=>{ void inspect(); });
      address.value=target;
      document.querySelector('#parent').disabled=target==='/';
      const crumbs=document.querySelector('#breadcrumbs'); crumbs.replaceChildren(anchor('/',M.link('/')));
      let prefix=''; for (const part of target.split('/').filter(Boolean)) { prefix+='/'+part; crumbs.append(anchor(part,M.link(prefix))); }
      if (historyMode !== 'none') history[historyMode+'State']({},'',M.link(target));
      await inspect(true);
    } catch(error) { if (navigation.current(ticket)) report(error.message); }
    finally { if (navigation.current(ticket)) { document.querySelector('#refresh').disabled=false; host.inert=false; } }
  }
  document.querySelector('#address').addEventListener('submit',event=>{event.preventDefault();void open(address.value);});
  document.querySelector('#parent').addEventListener('click',()=>open(M.parent(browsePath)));
  document.querySelector('#refresh').addEventListener('click',()=>open(browsePath,'replace'));
  document.addEventListener('click',event=>{
    const a=event.target.closest('a'); if (!a || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url=new URL(a.href); if (url.origin !== location.origin || url.pathname !== '/goo-inspector') return;
    event.preventDefault(); void open(url.searchParams.get('path') || GOO_INSPECTOR_ROOT);
  });
  window.addEventListener('popstate',()=>open(new URLSearchParams(location.search).get('path') || GOO_INSPECTOR_ROOT,'none'));
  document.querySelector('#app-root').href=M.link(GOO_INSPECTOR_ROOT+'/app');
  document.querySelector('#gov-root').href=M.link(GOO_INSPECTOR_ROOT+'/gov');
  await open(new URLSearchParams(location.search).get('path') || GOO_INSPECTOR_ROOT+'/app','replace');
})();
