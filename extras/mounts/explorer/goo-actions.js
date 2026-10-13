/* The only domain-action adapter. Local selection/deck gestures never call it. */
(function (root) {
  'use strict';
  const metrics = {activations: 0, dispatches: 0};
  const bindings = new WeakMap();
  const pendingScopes = new WeakMap();
  const valueEdits = new WeakMap();
  const layoutCache = new WeakMap();
  const layoutSizes = Object.freeze([['sm',240],['md',480],['lg',720]].map(Object.freeze));
  let profileRequest;
  const same = (a, b) => ['target', 'expected', 'displayed', 'publication', 'life', 'subject'].every(k => a[k] === b[k]);
  async function status(target) {
    const response = await fetch(`/goo/status?${new URLSearchParams({target})}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  function context(element) {
    // Read only the allocated host box, never the prepared Goo descendants.
    // Preview chrome consumes part of that allocation but cannot enlarge it.
    const style = getComputedStyle(element);
    const preview = element.querySelector?.(':scope > .preview');
    const chrome = preview ? getComputedStyle(preview) : null;
    const horizontal = (style, names) => names.reduce((total,name)=>total+(parseFloat(style?.[name])||0),0);
    const width = Math.floor(Math.max(0, Math.min(100000, element.clientWidth
      - horizontal(style,['paddingLeft','paddingRight'])
      - horizontal(chrome,['paddingLeft','paddingRight','borderLeftWidth','borderRightWidth','marginLeft','marginRight']))));
    const textScale = Number(style.getPropertyValue('--goo-text-scale').trim() || 1);
    if (!Number.isFinite(textScale) || textScale <= 0 || textScale > 10) throw new Error('Invalid Goo text scale');
    const [layout, allocation] = layoutSizes.findLast(([,minimum])=>minimum<=width) || ['sm',width];
    return {width:allocation, textScale, direction: style.direction === 'rtl' ? 'rtl' : 'ltr', layout};
  }
  function observe(element, changed) {
    let previous = JSON.stringify(context(element)), queued = false, stopped = false;
    const check = () => {
      if (queued || stopped) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false; if (stopped || !element.isConnected) return;
        const current = context(element), key = JSON.stringify(current);
        if (current.width > 0 && key !== previous) { previous = key; changed(current); }
      });
    };
    const resize = new ResizeObserver(check); resize.observe(element);
    // Direction/text scale may change without changing the container's width.
    const attributes = new MutationObserver(records => {
      if (!records || records.some(record => element.contains(record.target) || record.target.contains(element))) check();
    });
    attributes.observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['dir','style','class']});
    return () => { stopped = true; resize.disconnect(); attributes.disconnect(); };
  }
  async function installedProfile() {
    if (!profileRequest) profileRequest = fetch('/static/goo-profile.json', {cache:'no-store'}).then(async response => {
      if (!response.ok) throw new Error('Goo profile is unavailable');
      const profile = await response.json();
      return {id:profile.id,version:profile.version,revision:profile.revision};
    }).catch(error => { profileRequest = null; throw error; });
    return profileRequest;
  }
  const layoutKey = (target, options, requested) => requested.layout && options.owner && options.basis !== undefined
    ? JSON.stringify([target,...['view','slot','role','node','workspace'].map(key=>options[key]||''),options.basis,requested.textScale,requested.direction]) : null;
  function validateLayouts(data, requested, profile) {
    if(data.version!==1 || data.ok!==true || data.layoutPolicy!=='pane-v1' || !Array.isArray(data.layouts) || data.layouts.length!==3) throw new Error('Invalid pane layout bundle');
    if(!data.context || ['width','textScale','direction'].some(key=>data.context[key]!==requested[key])) throw new Error('Goo render context mismatch');
    let snapshot;
    for(const [index,variant] of data.layouts.entries()) {
      const [name,width]=layoutSizes[index];
      if(variant.size!==name || !variant.render) throw new Error('Invalid pane layout variant');
      validate(variant.render,{...requested,width:name==='sm'?Math.min(width,requested.width):width},profile);
      const basis=JSON.stringify(variant.render.snapshot);
      if(snapshot!==undefined && snapshot!==basis) throw new Error('Mixed pane layout snapshots');
      snapshot=basis;
    }
  }
  async function prepareChildren(page, slots, requested) {
    const profile=await installedProfile(), prepared=new Map();
    if(!Array.isArray(page.presentations))throw new Error('Missing prepared child presentations');
    const members=new Map(page.members.map(member=>[member.key,member]));
    for(const {key,slot,bundle} of page.presentations) {
      const member=members.get(key), identity=JSON.stringify([key,slot]);
      if(!member || member.status!=='available' || !slots.includes(slot) || prepared.has(identity))throw new Error('Unexpected child presentation');
      validateLayouts(bundle,{...requested,width:240},profile);
      // Action versions belong to the resolved writable receiver, which may
      // differ from this projected member. Subject/life and page epoch bind it.
      for(const {render} of bundle.layouts) {
        if(render.description || render.slot!==slot || (render.snapshot.subject||render.snapshot.target)!==member.subject ||
          render.snapshot.life!==member.life ||
          String(render.snapshot.projectionSeq)!==page.epoch)throw new Error('Child presentation changed; refresh before continuing.');
      }
      prepared.set(identity,bundle);
    }
    for(const member of members.values())if(member.status==='available')for(const slot of slots)
      if(!prepared.has(JSON.stringify([member.key,slot])))throw new Error('Missing child presentation');
    return prepared;
  }
  function adoptLayouts(target, options, bundle) {
    const key=layoutKey(target,options,{...bundle.context,layout:'sm'});
    if(key)layoutCache.set(options.owner,{key,layouts:bundle.layouts});
  }
  function chooseLayout(bundle, requested) {
    if(['textScale','direction'].some(key=>bundle.context[key]!==requested[key]))return null;
    const chosen=bundle.layouts.findLast(({render})=>render.context.width<=requested.width);
    return chosen?.size===requested.layout && chosen.render.context.width===requested.width ? {...chosen.render,layout:chosen.size} : null;
  }
  async function load(target, options = {}) {
    const requested = options.context;
    if (!requested || !Number.isFinite(requested.width) || requested.width < 0 || requested.width > 100000 || !Number.isFinite(requested.textScale) || requested.textScale <= 0 || requested.textScale > 10 || !['ltr','rtl'].includes(requested.direction)) throw new Error('A valid render context is required');
    if (requested.layout !== undefined && !layoutSizes.some(([name,width])=>name===requested.layout && (width===requested.width || name==='sm' && requested.width<width))) throw new Error('Invalid pane layout context');
    const fields = {target, width:String(requested.width), textScale:String(requested.textScale), direction:requested.direction};
    if (requested.layout) fields.layouts='pane-v1';
    for (const name of ['view','slot','role','node','workspace']) if (options[name] !== undefined && options[name] !== '') fields[name] = options[name];
    // A cache belongs to one existing presentation owner and a semantic basis.
    // Refreshes/retirements change that basis; geometry changes alone do not.
    const cacheKey = layoutKey(target,options,requested);
    const cached = cacheKey && layoutCache.get(options.owner);
    const choose = layouts => layouts.findLast(({render})=>render.context.width<=requested.width);
    if (cached?.key===cacheKey) {
      const chosen=choose(cached.layouts);
      if(chosen?.size===requested.layout && chosen.render.context.width===requested.width) {
        options.signal?.throwIfAborted();
        return {...chosen.render,layout:chosen.size};
      }
    }
    const [profile, response] = await Promise.all([installedProfile(), fetch('/goo/render', {
      method:'POST', cache:'no-store', body:new URLSearchParams(fields), signal:options.signal
    })]);
    if (response.headers?.get('content-type') && !response.headers.get('content-type').includes('json')) throw new Error(await response.text() || `Goo render failed (${response.status})`);
    let data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `Goo render failed (${response.status})`);
    if (requested.layout) {
      validateLayouts(data,requested,profile);
      const chosen=choose(data.layouts);
      if(!chosen || chosen.size!==requested.layout || chosen.render.context.width!==requested.width) throw new Error('No fitting pane layout');
      options.signal?.throwIfAborted();
      if(cacheKey)layoutCache.set(options.owner,{key:cacheKey,layouts:data.layouts});
      return {...chosen.render,layout:chosen.size};
    }
    validate(data,requested,profile);
    return data;
  }
  function validate(data,requested,profile) {
    if (data.version !== 1 || !data.snapshot) throw new Error('Unsupported Goo render response');
    if (!data.profile || ['id','version','revision'].some(key => data.profile[key] !== profile[key])) throw new Error('Goo renderer profile mismatch');
    if (!data.context || ['width','textScale','direction'].some(key => data.context[key] !== requested[key])) throw new Error('Goo render context mismatch');
    for (const view of data.views || [data]) {
      if (Array.isArray(data.views) && typeof view.error === 'string' && typeof view.view === 'string') continue;
      if (typeof view.html !== 'string' || !Array.isArray(view.controls)) throw new Error('Invalid Goo presentation');
      if (view.profile && ['id','version','revision'].some(key => view.profile[key] !== profile[key])) throw new Error('Goo presentation profile mismatch');
      if (view.display && ['id','version','revision'].some(key => view.display.profile?.[key] !== profile[key])) throw new Error('Goo display profile mismatch');
      if (view.display && ['width','textScale','direction'].some(key => view.display.context?.[key] !== requested[key])) throw new Error('Goo display context mismatch');
    }
  }
  function presentation(data) {
    const section = document.createElement('section'); section.className = 'preview';
    for (const key of ['view','slot','role']) section.dataset[key] = data[key] || '';
    section.dataset.declarationKind = data.kind || 'view';
    const heading = document.createElement('h2'); heading.textContent = data.view;
    const meta = document.createElement('p'); meta.className = 'meta'; meta.textContent = `${data.kind === 'pane' ? 'Pane' : 'View'} · ${data.slot}`;
    section.append(heading, meta);
    const body = document.createElement('div'); body.className = 'goo-presentation'; body.innerHTML = data.html;
    section.append(body); return section;
  }
  function prepareMount(container, data, preserve = false, section = true) {
    const next = section ? presentation(data) : document.createElement('div');
    if (!section) next.innerHTML = data.html;
    // Preparation never moves a working input or touches the installed DOM.
    return {proposed:next, commit() {
      const active = container.contains(document.activeElement) ? document.activeElement : null;
      const selection = ['INPUT','TEXTAREA'].includes(active?.tagName) ? [active.selectionStart,active.selectionEnd,active.selectionDirection] : null;
      const existing = preserve ? new Map([...container.querySelectorAll('input[data-input-slot]')].map(input => [input.dataset.inputSlot,input])) : new Map();
      for (const control of data.controls || []) if (control.kind === 'input') {
        const input = [...next.querySelectorAll('input[data-node]')].find(element => element.dataset.node === control.id);
        if (!input) continue;
        input.dataset.inputSlot = control.slot;
        const held = existing.get(control.slot);
        if (!held) continue;
        for (const attr of [...held.attributes]) if (!input.hasAttribute(attr.name)) held.removeAttribute(attr.name);
        for (const attr of [...input.attributes]) held.setAttribute(attr.name,attr.value);
        input.replaceWith(held);
      }
      if (preserve) {
        const values = new Map([...container.querySelectorAll('[data-value-key]')].map(node => [node.dataset.valueKey,node]));
        for (const input of next.querySelectorAll('[data-value-key]')) {
          const held=values.get(input.dataset.valueKey);
          if (!held || held.tagName!==input.tagName) continue;
          for (const attr of [...input.attributes]) held.setAttribute(attr.name,attr.value);
          if(held.tagName==='SELECT') {
            const value=held.value;held.replaceChildren(...input.childNodes);held.value=value;
          }
          input.replaceWith(held);
        }
        const open = new Set([...container.querySelectorAll('details[data-value-slot][open]')].map(node=>node.dataset.valueSlot));
        for (const details of next.querySelectorAll('details[data-value-slot]')) details.open=open.has(details.dataset.valueSlot);
      }
      const proposedHost=section ? next.querySelector('.goo-presentation') : next;
      const retainedHost=section ? container.querySelector(':scope > .preview > .goo-presentation') : container;
      const proposedFrames = preserve ? [...proposedHost.children].filter(node => node.matches('iframe[data-goo-presentation-frame]')) : [];
      const retainedFrames = proposedFrames.map(node => [...(retainedHost?.children||[])].find(old =>
        old.matches('iframe[data-goo-presentation-frame]') && old.dataset.gooPresentationFrame === node.dataset.gooPresentationFrame && old.getAttribute('src') === node.getAttribute('src')));
      // One direct presentation document per occurrence. Changing its subject/slot
      // retires it; title or geometry changes keep its actual focused/composing DOM.
      if (proposedFrames.length === 1 && retainedFrames[0]) {
        const proposed = proposedFrames[0], held = retainedFrames[0];
        for (const attr of [...held.attributes]) if (!proposed.hasAttribute(attr.name)) held.removeAttribute(attr.name);
        for (const attr of [...proposed.attributes]) if (held.getAttribute(attr.name) !== attr.value) held.setAttribute(attr.name, attr.value);
        if(section) {
          const wrapper=retainedHost.parentElement;
          Object.assign(wrapper.dataset,next.dataset);
          wrapper.querySelector('h2').textContent=next.querySelector('h2').textContent;
          wrapper.querySelector('.meta').textContent=next.querySelector('.meta').textContent;
        }
        for (const child of [...retainedHost.childNodes]) if (child !== held) child.remove();
        let after = false;
        for (const child of [...proposedHost.childNodes]) {
          if (child === proposed) { after = true; continue; }
          if (after) retainedHost.append(child); else retainedHost.insertBefore(child, held);
        }
      } else container.replaceChildren(...(section ? [next] : [...next.childNodes]));
      container.dataset.renderContext = JSON.stringify(data.context);
      if(data.layout)container.dataset.gooLayout=data.layout;
      else delete container.dataset.gooLayout;
      container.dataset.profileRevision = data.profile?.revision || '';
      container.gooDisplay = data.display;
      root.GooInspection?.record(container,data);
      if (active?.isConnected && document.activeElement !== active) {
        active.focus({preventScroll:true});
        if (selection && selection[0] !== null) active.setSelectionRange(...selection);
      }
      return section ? container.firstElementChild : container;
    }};
  }
  function mount(container, data, preserve = false, section = true) {
    return prepareMount(container,data,preserve,section).commit();
  }
  // Shared activation boundary for native controls and direct-manipulation topoi.
  // Protected receiver/publication/control evidence is captured once, before async work.
  const activations = new WeakMap();
  const outcomes = new Map();
  const outcomeListeners = new Set();
  function captureActivation(container, context, control) {
    const operationId = crypto.randomUUID(), activationRef = crypto.randomUUID();
    const captures = context.capture?.(control.captures || [], operationId) || [];
    const snapshot = context.snapshot;
    const body = new URLSearchParams({target:context.target,subject:snapshot.target,
      view:context.view,control:control.control,expected:snapshot.expected,
      displayed:snapshot.displayed,publication:snapshot.publication,invocation:operationId});
    const savedInputs = new Map();
    for (const input of container.querySelectorAll('input[data-input-slot]')) {
      body.append(`input:${input.dataset.inputSlot}`,input.value);savedInputs.set(input.dataset.inputSlot,input.value);
    }
    for (const capture of captures) body.append(`input:${capture.slot}`,JSON.stringify(capture.value));
    const handle = Object.freeze({operationId,activationRef});
    activations.set(handle,{body:body.toString(),savedInputs,context,control});
    return handle;
  }
  function discardCaptured(handle) {
    const held=activations.get(handle);
    if(held && held.arguments===undefined){held.context.releaseCapture?.(handle.operationId);activations.delete(handle);}
  }
  function recordOutcome(operationId, outcome, result) {
    const previous=outcomes.get(operationId);
    if(previous?.outcome==='accepted'||previous?.outcome==='rejected') return previous;
    const receipt=Object.freeze({operationId,outcome,result});outcomes.set(operationId,receipt);
    // Bound completed history; unresolved records are never described as failures.
    while(outcomes.size>128){const key=[...outcomes].find(([,v])=>v.outcome!=='unknown')?.[0];if(!key)break;outcomes.delete(key);}
    for(const listener of outcomeListeners){try{listener(receipt);}catch{/* A presentation listener cannot rewrite a recorded domain outcome. */}}return receipt;
  }
  async function activateCaptured(handle, inputs = []) {
    const held=activations.get(handle);if(!held)throw new Error('Unknown captured activation');
    const serialized=JSON.stringify(inputs);
    if(held.arguments!==undefined&&held.arguments!==serialized)throw new Error('Captured invocation arguments changed');
    if(held.promise)return held.promise;
    if(held.result)return held.result;
    if(held.rejection)throw held.rejection;
    if(held.arguments===undefined){
      if([...outcomes.values()].filter(v=>v.outcome==='unknown').length>=128)throw new Error('Unresolved invocation bound exceeded');
      held.arguments=serialized;
      const body=new URLSearchParams(held.body);
      for(const [slot,value] of inputs){if(typeof slot!=='string'||typeof value!=='string')throw new Error('Invalid bound input');body.set(`input:${slot}`,value);}
      held.body=body.toString();metrics.activations++;
    }
    held.promise=(async()=>{
      let response;
      try {
        for(let attempt=0;attempt<2;attempt++){
          try {metrics.dispatches++;response=await fetch('/goo/act',{method:'POST',body:new URLSearchParams(held.body)});break;}
          catch(error){if(attempt)throw error;}
        }
        const result=await response.json();
        if(!response.ok&&response.status>=500)throw new Error('Uncertain server outcome');
        if(!response.ok){recordOutcome(handle.operationId,'rejected',result);held.context.releaseCapture?.(handle.operationId);held.rejection=Object.assign(new Error(result.error||'Action failed.'),{rejected:true});throw held.rejection;}
        held.result={result,savedInputs:held.savedInputs};recordOutcome(handle.operationId,'accepted',result);held.context.releaseCapture?.(handle.operationId);return held.result;
      } catch(error) {
        if(!error.rejected){recordOutcome(handle.operationId,'unknown',null);throw Object.assign(new Error('Outcome unknown; reconcile before retrying.'),{code:'outcome-unknown'});}
        throw error;
      } finally {held.promise=null;}
    })();
    return held.promise;
  }
  function subscribeOutcomes(listener){outcomeListeners.add(listener);return ()=>outcomeListeners.delete(listener);}
  function workState() {
    const inputs=[...document.querySelectorAll('[data-input-slot],[data-value-key]')];
    return {dirty:inputs.some(input=>input.value!==(input.getAttribute('value')||'')),composing:inputs.some(input=>input.gooComposing)};
  }
  function trackComposition(input,signal) {
    input.addEventListener('compositionstart',()=>{input.gooComposing=true;},{signal});
    input.addEventListener('compositionend',()=>{input.gooComposing=false;},{signal});
  }
  function bindValues(container, context) {
    for (const form of container.querySelectorAll('form[data-goo-value]')) {
      bindings.get(form)?.abort(); const binding=new AbortController(); bindings.set(form,binding);
      const fields=[...form.querySelectorAll('[data-value-key]')];
      const scope=context.actionScope||container;
      if(!valueEdits.has(scope))valueEdits.set(scope,new Map());
      const edits=valueEdits.get(scope), key=JSON.stringify([context.target,context.snapshot.life,form.dataset.gooValue]);
      let edit=edits.get(key);
      if(!edit){edit={target:context.target,expected:context.snapshot.expected,pending:false,message:''};edits.set(key,edit);}
      const dirty=fields.some(input=>{const work=scope.inputs?.get(input.dataset.valueKey);return work?.dirty||input.value!==(input.getAttribute('value')||'');});
      if(!dirty&&!edit.pending)edit.expected=context.snapshot.expected;
      for(const input of fields) {
        bindings.get(input)?.abort(); const owner=new AbortController();bindings.set(input,owner);
        context.input?.(input.dataset.valueKey,input,owner.signal);
        trackComposition(input,owner.signal);
      }
      const kind=form.querySelector('[data-value-input="kind"]'), value=form.querySelector('[data-value-input="value"]');
      const status=form.querySelector('[role="status"]'), button=form.querySelector('[type="submit"]');
      const showMode=()=>{for(const node of form.querySelectorAll('[data-foil-context]'))node.hidden=kind.value!=='foil';};
      edit.button=button;edit.status=status;
      showMode();button.disabled=edit.pending;status.textContent=edit.message;
      kind.addEventListener('change',()=>{value.value='';value.dispatchEvent(new Event('input',{bubbles:true}));showMode();},{signal:binding.signal});
      form.querySelector('[data-value-cancel]').addEventListener('click',()=>{
        for(const input of fields){input.value=input.getAttribute('value')||'';input.dispatchEvent(new Event('input',{bubbles:true}));
          const work=context.actionScope?.inputs?.get(input.dataset.valueKey);if(work&&typeof work==='object')work.dirty=false;}
        edit.expected=context.snapshot.expected;edit.message='';status.textContent='';showMode();form.closest('details').open=false;
      },{signal:binding.signal});
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(edit.pending)return;
        if(fields.some(input=>input.gooComposing||context.actionScope?.inputs?.get(input.dataset.valueKey)?.composing))return;
        const savedInputs=new Map(fields.map(input=>[input.dataset.valueKey,input.value]));
        const body=new URLSearchParams({target:context.target,slot:form.dataset.gooValue,expected:edit.expected,
          kind:kind.value,value:value.value,context:form.querySelector('[data-value-input="context"]').value});
        const expected=edit.expected;
        edit.pending=true;button.disabled=true;edit.message='Saving…';status.textContent=edit.message;
        try {
          let response;
          try { response=await fetch('/goo/edit-value',{method:'POST',body}); }
          catch { throw new Error('Save outcome unknown. Refresh Values before retrying; your draft has been kept.'); }
          const result=await response.json();
          if(!response.ok)throw new Error(result.error||'Unable to save value.');
          for(const other of edits.values())if(other.target===context.target&&other.expected===expected)other.expected=result.expected;
          edit.pending=false;edit.message='';
          await context.saved?.(result,savedInputs);
          context.report('Saved.');
          for(const frame of document.querySelectorAll('iframe[data-goo-presentation-frame]'))frame.contentWindow?.postMessage({type:'goo-values-saved'},location.origin);
        } catch(error) {edit.message=error.message;edit.status.textContent=error.message;context.report(error.message);}
        finally {edit.pending=false;edit.button.disabled=false;}
      },{signal:binding.signal});
    }
  }
  function bind(container, context) {
    bindValues(container,context);
    root.GooInspection?.bind(container,context.inspect || (()=>({owner:"view",generation:context.actionScope?.generation,dirty:context.actionScope?.inputs?.size||0,composing:context.actionScope?.composing?1:0,live:true})));
    const scope=context.actionScope || container;
    if(!pendingScopes.has(scope)) pendingScopes.set(scope,new Map());
    const pendingActions=pendingScopes.get(scope);
    const controls = context.controls || [];
    for (const fieldset of container.querySelectorAll('.goo-preview')) fieldset.disabled = false;
    for (const control of controls) {
      const element = [...container.querySelectorAll('[data-node]')].find(n => n.dataset.node === control.id);
      if (!element) continue;
      bindings.get(element)?.abort();
      const binding = new AbortController(); bindings.set(element,binding);
      if (control.kind === 'input') {
        element.dataset.inputSlot = control.slot;
        context.input?.(control.slot, element, binding.signal);
        trackComposition(element,binding.signal);
        continue;
      }
      const actionKey=JSON.stringify([context.target,context.view,context.snapshot.life,context.snapshot.publication,control.control]);
      const existing=pendingActions.get(actionKey);
      if(existing) { element.disabled=true; existing.elements.set(element,binding); }
      let pending = null;
      element.addEventListener('click', async event => {
        event.stopPropagation();
        if (pendingActions.has(actionKey)) return;
        try {
          if (control.become && !control.invoke) { await context.become(control.slot); return; }
          const captured=captureActivation(container,context,control);
          // Receipt correlation for hosts invoking an ordinary bound control.
          element.dataset.gooInvocation=captured.operationId;
          pending = {captured,elements:new Map([[element,binding]])}; pendingActions.set(actionKey,pending); element.disabled = true;
          context.report('Applying…');
          const held=pending;held.unsubscribe=subscribeOutcomes(receipt=>{if(receipt.operationId!==captured.operationId||receipt.outcome==='unknown')return;held.unsubscribe?.();held.unsubscribe=null;if(pendingActions.get(actionKey)===held){pendingActions.delete(actionKey);for(const [element,owner] of held.elements)if(bindings.get(element)===owner)element.disabled=false;}});
          const {result,savedInputs}=await activateCaptured(captured);
          await context.saved?.(result, savedInputs);
          if (control.become) await context.become(control.slot);
          context.report('Saved.');
        } catch (error) { context.report(error.message); }
        finally {
          if (pending && pendingActions.get(actionKey) === pending && outcomes.get(pending.captured.operationId)?.outcome!=='unknown') {
            pending.unsubscribe?.();
            pendingActions.delete(actionKey);
            for(const [held,owner] of pending.elements) if(bindings.get(held)===owner) held.disabled=false;
          }
          pending=null;
        }
      }, {signal:binding.signal});
    }
  }
  root.GooActions = {workState, status, load, prepareChildren, adoptLayouts, chooseLayout, bind, context, observe, mount, prepareMount, presentation, metrics, captureActivation, discardCaptured, activateCaptured, subscribeOutcomes, outcome: id => outcomes.get(id), recordOutcome};
  async function start() {
    const main = document.querySelector('main[data-target]'); if (!main) return;
    const target = main.dataset.target, frames = new Map();
    const notice = document.createElement('p'); notice.setAttribute('role', 'status'); main.prepend(notice);
    const report = text => { notice.textContent = text; };
    const button = document.createElement('button'); button.textContent = 'Refresh views'; button.type = 'button'; notice.after(button);
    let revision = 0, request;
    async function refresh() {
      const current = ++revision; request?.abort(); request = new AbortController(); button.disabled = true;
      try {
        const data = await load(target,{...(main.hasAttribute('data-face') ? {slot:'/sys/slot/face'} : {view:main.dataset.view || undefined}),context:context(main),signal:request.signal});
        if (current !== revision) return;
        const seen = new Set(), errors = [];
        const visible=(data.views||[data]).filter(view=>!main.hasAttribute('data-views-only')||view.slot!=='/sys/slot/synthetic');
        for (const view of visible) {
          const key = view.view; seen.add(key);
          let frame = frames.get(key);
          if (!frame) {
            const element = document.createElement('div'); element.className = 'goo-view-host'; main.append(element);
            frame = {element,key,recipe:view.slot,inputs:new Map(),generation:0}; frames.set(key,frame);
            frame.stop = observe(element, () => render(frame).catch(error => report(error.message)));
          }
          frame.view = view; frame.snapshot = data.snapshot; frame.pendingRemoval = false;
          try {
            if (view.error) throw new Error(view.error);
            await render(frame);
          } catch (error) {
            if (error.name !== 'AbortError' && current === revision) {
              errors.push(`${view.view}: ${error.message}`);
              if (!frame.error) { frame.error = document.createElement('p'); frame.error.setAttribute('role','status'); frame.element.prepend(frame.error); }
              frame.error.textContent = error.message;
            }
          }
          if (current !== revision) return;
        }
        for (const [key,frame] of frames) if (!seen.has(key)) {
          if (frame.composing) { frame.pendingRemoval = true; continue; }
          if (frame.controller) {
            const controller=frame.controller, closed=await controller.close();
            if(closed && frame.controller===controller) frame.controller=null;
            if(current!==revision) return;
            if(!closed) continue;
          }
          if (frame.inputs.size && !confirm('This view was removed. Discard its unsaved input?')) continue;
          frame.stop(); frame.request?.abort(); frame.element.remove(); frames.delete(key);
        }
        report(errors.join(' ') || (visible.length ? '' : 'No Goo views match this entry.'));
      } catch (error) { if (error.name !== 'AbortError' && current === revision) report(error.message); }
      finally { if (current === revision) button.disabled = false; }
    }
    async function render(frame) {
      if (!frame.view || frame.composing) { frame.pending = true; return; }
      const generation = ++frame.generation; frame.request?.abort(); frame.request = new AbortController();
      const selector = frame.recipe === frame.view.slot ? {view:frame.key} : {slot:frame.recipe,role:frame.view.role};
      const data = await load(target,{...selector,context:context(frame.element),signal:frame.request.signal});
      if (generation !== frame.generation || frame.composing || !frame.element.isConnected) { frame.pending = true; return; }
      frame.error?.remove(); frame.error = null;
      if (data.description) {
        const lifetime = JSON.stringify([data.snapshot.subject || data.snapshot.target,data.snapshot.life,data.view]);
        if (frame.controller && frame.paneLifetime !== lifetime) {
          const controller=frame.controller, closed=await controller.close();
          if(closed && frame.controller===controller) frame.controller=null;
          if(generation!==frame.generation || !frame.element.isConnected || !closed) return;
        }
        if (!frame.controller) {
          if (frame.inputs.size && !confirm('Discard unsaved input before replacing this view?')) return;
          frame.inputs.clear(); frame.lifetime = null; frame.pending = false;
          mount(frame.element,data);
          frame.controller = new root.GooPanes(frame.element.querySelector('.goo-session'), {target,view:frame.key,report,refresh});
          frame.paneLifetime = lifetime;
        }
        await frame.controller.update(data.description,data.snapshot,{signal:frame.request.signal,onApplied:() => {
          if (generation !== frame.generation) return;
          root.GooInspection?.record(frame.element,data,()=>frame.controller.inspectionState());
          frame.element.dataset.renderContext = JSON.stringify(data.context);
          frame.element.dataset.profileRevision = data.profile.revision;
        }});
        return;
      }
      if (frame.controller) {
        const controller=frame.controller, closed=await controller.close();
        if(closed && frame.controller===controller) frame.controller=null;
        if(generation!==frame.generation || !frame.element.isConnected || !closed) return;
      }
      const lifetime = JSON.stringify([data.snapshot.subject,data.snapshot.life,data.snapshot.recipePublication ?? data.snapshot.publication,data.view]);
      if (frame.lifetime && frame.lifetime !== lifetime && frame.inputs.size) {
        if (!confirm('This view was replaced. Discard its unsaved input?')) return;
        frame.inputs.clear();
      }
      const preserve = frame.lifetime === lifetime; frame.lifetime = lifetime;
      const next = mount(frame.element,data,preserve);
      bind(next,{actionScope:frame,target,view:data.view,snapshot:data.snapshot,controls:data.controls,report,
        input: (key,input,signal) => {
          if (frame.inputs.has(key)) input.value = frame.inputs.get(key);
          else input.value = input.getAttribute('value') ?? input.value;
          input.addEventListener('input',() => {
            if (input.value === input.getAttribute('value')) frame.inputs.delete(key);
            else frame.inputs.set(key,input.value);
          },{signal});
          input.addEventListener('compositionstart',() => { frame.composing = true; },{signal});
          input.addEventListener('compositionend',() => {
            frame.composing = false;
            if (frame.pendingRemoval) { frame.pendingRemoval = false; refresh(); }
            else if (frame.pending) { frame.pending = false; render(frame).catch(error => report(error.message)); }
          },{signal});
        },
        become: async slot => {
          if (generation !== frame.generation) return;
          if (frame.inputs.size && !confirm('Discard unsaved input and change view?')) return;
          frame.inputs.clear(); frame.recipe = slot; await render(frame);
        },
        saved: async (_result,savedInputs) => {
          if (frame.lifetime === lifetime) for (const [key,value] of savedInputs) if (frame.inputs.get(key) === value) frame.inputs.delete(key);
          await refresh();
        }
      });
    }
    // Every presentation, including readonly reflection, uses the same live
    // boundary instead of parsing a second whole page.
    for (const node of main.querySelectorAll(':scope > .preview[data-view]')) node.remove();
    button.addEventListener('click',refresh);
    root.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===root.parent&&event.data?.type==='goo-values-saved')refresh();});
    observe(main,() => refresh());
    await refresh();
  }
  if (typeof document !== 'undefined') start();
})(globalThis);
