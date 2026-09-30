/* Interaction identities and argument bindings come from the published Grove.
 * Keep transitions local to each preview; refresh all instances after writes. */
(() => {
  const main = document.querySelector('main[data-target]');
  if (!main) return;
  const target = main.dataset.target;
  let snapshot, templates = [], busy = false;
  const notice = document.createElement('p');
  notice.setAttribute('role', 'status');
  main.prepend(notice);
  const status = async () => {
    const response = await fetch(`/goo/status?${new URLSearchParams({target})}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  };
  const same = (a, b) => ['target', 'expected', 'displayed', 'publication'].every(key => a[key] === b[key]);
  function freeze(value) {
    busy = value;
    for (const fieldset of main.querySelectorAll('.goo-preview')) fieldset.disabled = value || !snapshot;
  }
  function report(error) { notice.textContent = error.message || String(error); }
  function transition(frame, slot) {
    const choices = templates.filter(node => node.dataset.slot === slot && node.dataset.role === frame.dataset.role);
    if (choices.length !== 1) throw new Error(choices.length ? 'Competing views for this slot.' : 'No view for this slot.');
    const replacement = choices[0].cloneNode(true);
    replacement.dataset.frame = frame.dataset.frame;
    frame.replaceWith(replacement);
    bind(replacement);
  }
  function bind(frame) {
    const fieldset = frame.querySelector('.goo-preview');
    if (!fieldset) return;
    fieldset.disabled = false;
    const controls = JSON.parse(fieldset.dataset.controls);
    for (const control of controls) {
      const element = [...fieldset.querySelectorAll('[data-node]')].find(node => node.dataset.node === control.id);
      if (!element) continue;
      if (control.kind === 'input') { element.dataset.inputSlot = control.slot; continue; }
      element.addEventListener('click', async () => {
        if (busy) return;
        notice.textContent = '';
        try {
          if (control.become && !control.invoke) { transition(frame, control.slot); return; }
          const inputs = [...fieldset.querySelectorAll('input[data-input-slot]')];
          const body = new URLSearchParams({
            target, subject: snapshot.target, view: frame.dataset.view, control: control.control,
            expected: snapshot.expected, displayed: snapshot.displayed, publication: snapshot.publication
          });
          for (const input of inputs) body.append(`input:${input.dataset.inputSlot}`, input.value);
          freeze(true);
          notice.textContent = 'Applying…';
          const response = await fetch('/goo/act', {method: 'POST', body});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Action failed.');
          await refresh();
          if (control.become) {
            const current = [...main.querySelectorAll('.preview')].find(node => node.dataset.frame === frame.dataset.frame);
            if (current) transition(current, control.slot);
          }
          notice.textContent = 'Saved.';
        } catch (error) { report(error); }
        finally { freeze(false); }
      });
    }
  }
  async function refresh() {
    const previousViews = new Set((templates.length ? templates : [...main.querySelectorAll('.preview')]).map(node => node.dataset.view));
    const frames = [...main.querySelectorAll('.preview')].map((frame, index) => ({
      id: frame.dataset.frame || String(index), view: frame.dataset.view
    }));
    // Capture versions on either side of rendering. A publication or object
    // change during the render retries, rather than attaching a fresh version
    // to stale controls or stale input values.
    for (let attempt = 0; attempt < 3; attempt++) {
      const before = await status();
      const response = await fetch(`/views${target === '/' ? '' : target}`, {cache: 'no-store'});
      if (!response.ok) throw new Error('Unable to refresh views.');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const after = await status();
      if (!same(before, after)) continue;
      snapshot = after;
      templates = [...page.querySelectorAll('.preview')];
      for (const old of main.querySelectorAll('.preview')) old.remove();
      const desired = frames.length ? frames : templates.map((node, index) => ({id: String(index), view: node.dataset.view}));
      if (frames.length) for (const template of templates) {
        if (!previousViews.has(template.dataset.view)) desired.push({id: `new:${template.dataset.view}`, view: template.dataset.view});
      }
      for (const frame of desired) {
        const template = templates.find(node => node.dataset.view === frame.view);
        if (!template) continue;
        const element = template.cloneNode(true);
        element.dataset.frame = frame.id;
        main.append(element);
        bind(element);
      }
      return;
    }
    throw new Error('Object kept changing during refresh. Reload to try again.');
  }
  const reload = document.createElement('button');
  reload.type = 'button';
  reload.textContent = 'Refresh views';
  reload.addEventListener('click', async () => {
    if (busy) return;
    freeze(true);
    notice.textContent = 'Refreshing…';
    try { await refresh(); notice.textContent = ''; }
    catch (error) { report(error); }
    finally { freeze(false); }
  });
  notice.after(reload);
  freeze(true);
  notice.textContent = 'Connecting controls…';
  refresh().then(() => { notice.textContent = ''; }).catch(report).finally(() => { freeze(false); });
})();
