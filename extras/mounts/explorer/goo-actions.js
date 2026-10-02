/* The only domain-action adapter. Local selection/deck gestures never call it. */
(function (root) {
  'use strict';
  const metrics = {activations: 0, dispatches: 0};
  const bindings = new WeakMap();
  const pendingScopes = new WeakMap();
  let profileRequest;
  const same = (a, b) => ['target', 'expected', 'displayed', 'publication', 'life', 'subject'].every(k => a[k] === b[k]);
  async function status(target) {
    const response = await fetch(`/goo/status?${new URLSearchParams({target})}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  function context(element) {
    // Explorer chrome is outside Goo's allocation. Once mounted, measure the
    // presentation's content box, including the narrower member/follow frame.
    const content = element.querySelector?.(':scope > .preview > .goo-presentation') || element;
    const style = getComputedStyle(content), rect = content.getBoundingClientRect();
    const width = Math.max(0, Math.min(100000, (content.clientWidth || rect.width) - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0)));
    const textScale = Number(style.getPropertyValue('--goo-text-scale').trim() || 1);
    if (!Number.isFinite(textScale) || textScale <= 0 || textScale > 10) throw new Error('Invalid Goo text scale');
    return {width, textScale, direction: style.direction === 'rtl' ? 'rtl' : 'ltr'};
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
  async function load(target, options = {}) {
    const requested = options.context;
    if (!requested || !Number.isFinite(requested.width) || requested.width < 0 || requested.width > 100000 || !Number.isFinite(requested.textScale) || requested.textScale <= 0 || requested.textScale > 10 || !['ltr','rtl'].includes(requested.direction)) throw new Error('A valid render context is required');
    const fields = {target, width:String(requested.width), textScale:String(requested.textScale), direction:requested.direction};
    for (const name of ['view','slot','role','node','workspace']) if (options[name] !== undefined && options[name] !== '') fields[name] = options[name];
    const [profile, response] = await Promise.all([installedProfile(), fetch('/goo/render', {
      method:'POST', cache:'no-store', body:new URLSearchParams(fields), signal:options.signal
    })]);
    if (response.headers?.get('content-type') && !response.headers.get('content-type').includes('json')) throw new Error(await response.text() || `Goo render failed (${response.status})`);
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `Goo render failed (${response.status})`);
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
    return data;
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
  function mount(container, data, preserve = false, section = true) {
    const next = section ? presentation(data) : document.createElement('div');
    if (!section) next.innerHTML = data.html;
    const active = container.contains(document.activeElement) ? document.activeElement : null;
    const selection = active?.tagName === 'INPUT' ? [active.selectionStart,active.selectionEnd,active.selectionDirection] : null;
    const existing = preserve ? new Map([...container.querySelectorAll('input[data-input-slot]')].map(input => [input.dataset.inputSlot,input])) : new Map();
    for (const control of data.controls || []) if (control.kind === 'input') {
      const input = [...next.querySelectorAll('input[data-node]')].find(element => element.dataset.node === control.id);
      if (!input) continue;
      input.dataset.inputSlot = control.slot;
      const held = existing.get(control.slot);
      if (!held) continue;
      // Preserve the actual native control, including its working value/caret.
      for (const attr of [...held.attributes]) if (!input.hasAttribute(attr.name)) held.removeAttribute(attr.name);
      for (const attr of [...input.attributes]) held.setAttribute(attr.name,attr.value);
      input.replaceWith(held);
    }
    container.replaceChildren(...(section ? [next] : [...next.childNodes]));
    container.dataset.renderContext = JSON.stringify(data.context);
    container.dataset.profileRevision = data.profile?.revision || '';
    container.gooDisplay = data.display;
    if (active?.isConnected && document.activeElement !== active) {
      active.focus({preventScroll:true});
      if (selection && selection[0] !== null) active.setSelectionRange(...selection);
    }
    return section ? next : container;
  }
  function bind(container, context) {
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
          // Capture before any asynchronous work. The exact form and invocation
          // identity are retained for network retry; no live selection operand.
          metrics.activations++;
          const invocation = crypto.randomUUID();
          const captures = context.capture?.(control.captures || [], invocation) || [];
          const snapshot = context.snapshot;
          const body = new URLSearchParams({target: context.target, subject: snapshot.target,
            view: context.view, control: control.control, expected: snapshot.expected,
            displayed: snapshot.displayed, publication: snapshot.publication, invocation});
          const savedInputs = new Map();
          for (const input of container.querySelectorAll('input[data-input-slot]')) {
            body.append(`input:${input.dataset.inputSlot}`, input.value); savedInputs.set(input.dataset.inputSlot, input.value);
          }
          for (const capture of captures) body.append(`input:${capture.slot}`, JSON.stringify(capture.value));
          pending = {body:body.toString(),elements:new Map([[element,binding]])}; pendingActions.set(actionKey,pending); element.disabled = true;
          context.report('Applying…');
          let response;
          for (let attempt = 0; attempt < 2; attempt++) {
            try { metrics.dispatches++; response = await fetch('/goo/act', {method: 'POST', body: new URLSearchParams(pending.body)}); break; }
            catch (error) { if (attempt) throw error; }
          }
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Action failed.');
          await context.saved?.(result, savedInputs);
          if (control.become) await context.become(control.slot);
          context.report('Saved.');
        } catch (error) { context.report(error.message); }
        finally {
          if (pending && pendingActions.get(actionKey) === pending) {
            pendingActions.delete(actionKey);
            for(const [held,owner] of pending.elements) if(bindings.get(held)===owner) held.disabled=false;
          }
          pending=null;
        }
      }, {signal:binding.signal});
    }
  }
  root.GooActions = {status, load, bind, context, observe, mount, presentation, metrics};
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
        const data = await load(target,{context:context(main),signal:request.signal});
        if (current !== revision) return;
        const seen = new Set(), errors = [];
        for (const view of data.views) {
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
        report(errors.join(' '));
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
      const lifetime = JSON.stringify([data.snapshot.subject,data.snapshot.life,data.snapshot.publication,data.view]);
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
    observe(main,() => refresh());
    await refresh();
  }
  if (typeof document !== 'undefined') start();
})(globalThis);
