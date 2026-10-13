'use strict';
(() => {
  const el = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  let source = params.get('source') || '', root = params.get('root') || '';
  let selected = params.get('selected') || '', mode = params.get('mode') || 'views';
  if (!['objects', 'views', 'internals'].includes(mode)) mode = 'views';
  let snapshot, busy = false;
  const route = {objects:'/ns', views:'/views', internals:'/debug'};
  const unit = () => snapshot?.units.find(u => u.source === source);
  function message(text, error = false) { el('status').textContent = text; el('status').dataset.error = error; }
  function lock(value) {
    busy = value;
    el('inspector').style.pointerEvents = value ? 'none' : '';
    for (const id of ['source','root','use-root','rebuild','install','delete']) el(id).disabled = value;
    if (!value) {
      el('rebuild').disabled = !unit();
      el('install').disabled = !unit()?.version || !!snapshot?.occupied;
      el('delete').disabled = !snapshot?.installed;
    }
  }
  function remember() {
    const p = new URLSearchParams({source, root, selected, mode});
    history.replaceState(null, '', '/grove/dev?' + p);
  }
  function navigate(reload = false) {
    el('selection').value = selected;
    for (const name of Object.keys(route)) { el(name).href = route[name] + selected; el(name).setAttribute('aria-current', String(name === mode)); }
    el('template').href = '/debug' + source;
    const url = route[mode] + selected;
    el('open').href = url;
    if (reload || el('inspector').getAttribute('src') !== url) el('inspector').src = url;
    remember();
  }
  async function request(operation, fields = {}) {
    const body = new URLSearchParams({source, root, selected, ...fields});
    const response = await fetch('/grove/dev/' + operation + (operation === 'status' ? '?' + body : ''), {
      method: operation === 'status' ? 'GET' : 'POST', cache:'no-store',
      ...(operation === 'status' ? {} : {body})
    });
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); } catch (_) { throw new Error(text || 'Development request failed'); }
    if (!response.ok) {
      const explanations = {
        stale_instance:'The instance changed since this operation started. Refresh and retry.',
        stale_template:'A newer template was published. Refresh and retry.',
        stale_scan:'Another rescan has started. Refresh and retry.',
        stale_publication:'The publication changed. Refresh and retry.',
        publication_pending:'A source scan is still pending. Wait for publication before installing.',
        publication_failed:'Compilation failed. Fix the source and rebuild; the existing instance is retained.',
        unrelated_instance:'This root contains an unrelated installation. Choose an empty root or its own Grove.',
        invalid_instance_root:'Choose an instance root below this node’s /app namespace.',
        installation_root_exists:'The instance root is occupied. Use Rebuild to reset it.'
      };
      throw new Error(explanations[result.error] || result.error || text);
    }
    return result;
  }
  function render() {
    const u = unit();
    el('source').replaceChildren(...snapshot.units.map(item => {
      const option = document.createElement('option'); option.value = item.source;
      option.textContent = `${item.mount} — ${item.source}`; return option;
    }));
    el('source').value = source; el('root').value = root;
    el('metadata').textContent = u ? `Source: ${u.files.map(f => `${u.mount}/${f}`).join(', ')} · published ${u.version ?? 'absent'} · installed ${snapshot.installed ?? 'absent'} · instance revision ${snapshot.expected ?? 'absent'}` : 'No published Grove mounts available.';
    el('diagnostic').textContent = u?.diagnostic || 'No publication errors.';
    el('diagnostics').open = !!u?.diagnostic;
    el('mount-link').href = '/ns' + (u?.home || '');
    lock(busy);
  }
  async function refresh() {
    snapshot = await request('status');
    if (!source) source = snapshot.source && snapshot.source !== '/' ? snapshot.source : (snapshot.units.find(u => u.mount === 'grove-dev') || snapshot.units[0])?.source || '';
    if (!root) root = snapshot.root && snapshot.root !== '/' ? snapshot.root : source.replace('/gov/', '/app/');
    if (!selected) selected = root;
    // Initial context discovery may have chosen a default root after the read.
    if (snapshot.root !== root) snapshot = await request('status');
    render(); remember(); return snapshot;
  }
  async function act(operation) {
    if (busy) return;
    lock(true);
    try {
      await refresh();
      const expected = snapshot.expected ?? '';
      let u = unit();
      if (!u) throw new Error('Select a Grove first.');
      if (operation === 'rebuild') {
        message('Scanning source and compiling…');
        const started = await request('rescan', {scan:u.requested});
        const requested = started.units.find(x => x.source === source).requested;
        const deadline = Date.now() + 10 * 60 * 1000;
        while (true) {
          await refresh(); u = unit();
          if (u.requested !== requested) throw new Error('Another rescan superseded this rebuild. Refresh and retry.');
          if (BigInt(u.completed) >= BigInt(requested)) break;
          if (Date.now() > deadline) throw new Error('Publication is still pending. The instance has not been replaced; refresh status before retrying.');
          await new Promise(resolve => setTimeout(resolve, 350));
        }
        if (!u.ready) throw new Error(u.message || 'Compilation failed; the existing instance was retained.');
        message('Publication succeeded. Replacing the instance…');
        operation = 'replace';
      } else message(operation === 'delete' ? 'Deleting instance subtree…' : 'Installing published template…');
      snapshot = await request(operation, {expected, version:u.version || '0', scan:u.completed});
      if (operation !== 'delete') selected = snapshot.selected || root;
      else selected = root;
      render(); navigate(true);
      message(operation === 'delete' ? 'Instance deleted. Published definitions remain available for Install latest.' : 'Instance installed from the published Grove. Seed data is current.');
    } catch (error) {
      try { await refresh(); } catch (_) {}
      message(error.message + ' Existing instance state was retained if replacement failed.', true);
    } finally { lock(false); }
  }
  el('rebuild').onclick = () => act('rebuild');
  el('install').onclick = () => act('install');
  el('delete').onclick = () => act('delete');
  el('source').onchange = async () => {
    source = el('source').value; root = source.replace('/gov/', '/app/'); selected = root;
    try { await refresh(); navigate(true); message('Ready.'); } catch (e) { message(e.message, true); }
  };
  el('use-root').onclick = async () => {
    root = el('root').value; selected = root;
    try { await refresh(); navigate(true); message('Ready.'); } catch (e) { message(e.message, true); }
  };
  el('go').onclick = () => { selected = el('selection').value; navigate(true); };
  for (const name of Object.keys(route)) el(name).onclick = event => { event.preventDefault(); mode = name; navigate(); };
  async function syncSelection() {
    if (busy) return;
    try {
      const path = el('inspector').contentWindow.location.pathname;
      const prefix = route[mode];
      if (path === prefix || path.startsWith(prefix + '/')) {
        selected = decodeURIComponent(path.slice(prefix.length)) || '/';
        el('selection').value = selected; el('open').href = path; remember();
        const viewed = selected;
        const context = await request('status', {source:'', root:'', selected:viewed});
        if (!busy && selected === viewed && context.installed && context.root !== root) {
          source = context.source; root = context.root; snapshot = context;
          render(); remember();
        }
      }
    } catch (_) {}
  }
  el('inspector').onload = () => {
    // The debugger navigates within its document, without reloading the iframe.
    try { el('inspector').contentDocument.addEventListener('debug:navigate', syncSelection); } catch (_) {}
    return syncSelection();
  };
  refresh().then(() => { navigate(); message('Ready. Edit a Grove file, then rebuild.'); }).catch(e => message(e.message, true));
})();
