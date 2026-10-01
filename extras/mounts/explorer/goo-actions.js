/* The only domain-action adapter. Local selection/deck gestures never call it. */
(function (root) {
  'use strict';
  const metrics = {activations: 0, dispatches: 0};
  const same = (a, b) => ['target', 'expected', 'displayed', 'publication', 'life'].every(k => a[k] === b[k]);
  async function status(target) {
    const response = await fetch(`/goo/status?${new URLSearchParams({target})}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }
  async function load(target) {
    for (let attempt = 0; attempt < 3; attempt++) {
      const before = await status(target);
      const response = await fetch(`/views${target === '/' ? '' : target}`, {cache: 'no-store'});
      if (!response.ok) throw new Error('Unable to load views.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const after = await status(target);
      if (same(before, after)) return {snapshot: after, templates: [...page.querySelectorAll('main > .preview')]};
    }
    throw new Error('Object changed during rendering; refresh to retry.');
  }
  const choose = (templates, slot, role) => {
    const choices = templates.filter(n => n.dataset.slot === slot && (!role || n.dataset.role === role));
    if (choices.length !== 1) throw new Error(choices.length ? 'Competing views for this slot.' : 'No view for this slot.');
    return choices[0];
  };
  function bind(container, context) {
    const controls = context.controls || JSON.parse(container.querySelector('.goo-preview')?.dataset.controls || '[]');
    for (const fieldset of container.querySelectorAll('.goo-preview')) fieldset.disabled = false;
    for (const control of controls) {
      const element = [...container.querySelectorAll('[data-node]')].find(n => n.dataset.node === control.id);
      if (!element) continue;
      if (control.kind === 'input') {
        element.dataset.inputSlot = control.slot;
        context.input?.(control.slot, element);
        continue;
      }
      let pending = null;
      element.addEventListener('click', async event => {
        event.stopPropagation();
        if (pending) return;
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
          pending = body.toString(); element.disabled = true;
          context.report('Applying…');
          let response;
          for (let attempt = 0; attempt < 2; attempt++) {
            try { metrics.dispatches++; response = await fetch('/goo/act', {method: 'POST', body: new URLSearchParams(pending)}); break; }
            catch (error) { if (attempt) throw error; }
          }
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Action failed.');
          await context.saved?.(result, savedInputs);
          if (control.become) await context.become(control.slot);
          context.report('Saved.');
        } catch (error) { context.report(error.message); }
        finally { pending = null; element.disabled = false; }
      });
    }
  }
  root.GooActions = {status, load, choose, bind, metrics};
  async function start() {
    const main = document.querySelector('main[data-target]'); if (!main) return;
    const target = main.dataset.target, frames = new Map();
    const notice = document.createElement('p'); notice.setAttribute('role', 'status'); main.prepend(notice);
    const report = text => { notice.textContent = text; };
    const button = document.createElement('button'); button.textContent = 'Refresh views'; button.type = 'button'; notice.after(button);
    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true; button.disabled = true;
      try {
        const data = await load(target), seen = new Set();
        for (const template of data.templates) {
          const key = template.dataset.view; seen.add(key);
          let frame = frames.get(key);
          if (!frame) {
            frame = {element: template.cloneNode(true), key, recipe: template.dataset.slot, inputs: new Map()};
            frames.set(key, frame); main.append(frame.element);
          }
          const description = template.querySelector('.goo-session');
          if (description) {
            if (!frame.element.querySelector('.goo-session')) {
              if (frame.inputs.size && !confirm('Discard unsaved input before replacing this view?')) continue;
              const next = template.cloneNode(true); frame.element.replaceWith(next); frame.element = next;
            }
            if (!frame.controller) frame.controller = new root.GooPanes(frame.element.querySelector('.goo-session'), {target, view: key, report, refresh});
            await frame.controller.update(JSON.parse(description.dataset.description), data.snapshot);
            continue;
          }
          if (frame.controller) {
            if (!(await frame.controller.close())) continue;
            frame.controller = null;
          }
          frame.data = data;
          const install = (slot) => {
            const next = choose(data.templates, slot, template.dataset.role).cloneNode(true);
            // Native inputs keep page-owned working values across rerenders.
            if (frame.element.querySelector('input:focus') || frame.composing) { frame.next = slot; return; }
            frame.element.replaceWith(next); frame.element = next; frame.recipe = slot;
            bind(next, {target, view: next.dataset.view, snapshot: data.snapshot, report,
              input: (key, input) => {
                if (frame.inputs.has(key)) input.value = frame.inputs.get(key);
                input.addEventListener('input', () => frame.inputs.set(key, input.value));
                input.addEventListener('compositionstart', () => { frame.composing = true; });
                input.addEventListener('compositionend', () => { frame.composing = false; });
              },
              become: async slot => { if (frame.inputs.size && !confirm('Discard unsaved input and change view?')) return; frame.inputs.clear(); install(slot); },
              saved: async (_result, savedInputs) => {
                for (const [key, value] of savedInputs) if (frame.inputs.get(key) === value) frame.inputs.delete(key);
                await refresh();
              }
            });
          };
          if (template.dataset.role) install(frame.recipe);
          else { const next = template.cloneNode(true); frame.element.replaceWith(next); frame.element = next; }
        }
        for (const [key, frame] of frames) if (!seen.has(key)) {
          if (frame.controller && !(await frame.controller.close())) continue;
          if (frame.inputs.size && !confirm('This view was removed. Discard its unsaved input?')) continue;
          frame.element.remove(); frames.delete(key);
        }
        report('');
      } catch (error) { report(error.message); }
      finally { refreshing = false; button.disabled = false; }
    }
    for (const node of main.querySelectorAll(':scope > .preview')) node.remove();
    button.addEventListener('click', refresh);
    await refresh();
  }
  if (typeof document !== 'undefined') start();
})(globalThis);
