/* Page chrome only. Goo owns library preparation, membership and selection;
   Nenex's existing forms and document components own every domain write. */
(() => {
  'use strict';
  const shell = document.querySelector('.wiki-shell');
  if (!shell) return;
  const page = shell.dataset.page, corpus = shell.dataset.corpus;
  const source = document.querySelector('#source');
  const textarea = document.querySelector('#page-source');
  const editor = document.querySelector('#editor');
  const status = document.querySelector('#save-state');
  const original = textarea?.value;
  let submitting = false;
  const dirty = () => textarea && textarea.value !== original;
  const update = () => { if (status) status.textContent = dirty() ? 'Unsaved changes' : 'No unsaved changes'; };
  textarea?.addEventListener('input', update);
  editor?.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    status.textContent = 'Saving page...';
    const button = editor.querySelector('[type=submit]');
    button.disabled = true;
    try {
      const response = await fetch(editor.action, {
        method: 'POST',
        body: new URLSearchParams(new FormData(editor)),
        signal: AbortSignal.timeout(30000)
      });
      if (!response.ok) throw new Error('Save failed');
      location.assign(editor.querySelector('[name=back]').value);
    } catch {
      submitting = false;
      button.disabled = false;
      status.textContent = 'Could not save. Your draft is still here; please try again.';
    }
  });
  document.querySelector('#discard')?.addEventListener('click', () => {
    textarea.value = original; update(); source.open = false;
  });
  // Domain forms call native namespace commands; the response only selects
  // the next reader page. Hands own requests, execution and publication.
  document.addEventListener('submit', async event => {
    const form = event.target.closest('form[data-native-flow]');
    if (!form) return;
    event.preventDefault();
    if (form.dataset.submitting) return;
    if (dirty()) {
      form.querySelector('[data-flow-status]').textContent = 'Save or discard your source changes first.';
      return;
    }
    form.dataset.submitting = 'true';
    const button = form.querySelector('[type=submit]');
    const feedback = form.querySelector('[data-flow-status]');
    button.disabled = true;
    feedback.textContent = 'Applying…';
    try {
      const response = await fetch(form.getAttribute('action'), {
        method: 'POST', body: new URLSearchParams(new FormData(form)),
        signal: AbortSignal.timeout(240000)
      });
      const body = await response.text();
      let result;
      try { result = JSON.parse(body); }
      catch { throw new Error(body || 'The operation returned no result.'); }
      if (!response.ok || result.error) throw new Error(result.error || 'Operation refused');
      submitting = true;
      const next = new URL(result.redirect, location.href);
      // Hash navigation alone would leave the old publication controls visible.
      if (next.pathname === location.pathname && next.search === location.search) {
        location.hash = next.hash;
        location.reload();
      } else location.assign(next.href);
    } catch (error) {
      delete form.dataset.submitting;
      button.disabled = false;
      feedback.textContent = error.message || 'Could not apply. Your entries are still here.';
    }
  });
  addEventListener('beforeunload', event => {
    if (dirty() && !submitting) { event.preventDefault(); event.returnValue = ''; }
  });
  const reveal = () => {
    const target = document.getElementById(location.hash.slice(1));
    if (target?.tagName === 'DETAILS') { target.open = true; target.scrollIntoView(); }
  };
  addEventListener('hashchange', reveal); reveal();
  document.querySelector('[name=new]')?.setAttribute('pattern', '[A-Za-z_][A-Za-z0-9_-]*');
  const decorate = () => {
    for (const form of shell.querySelectorAll('form[data-native-flow]')) {
      if (form.dataset.ready) continue;
      form.dataset.ready = 'true';
      form.querySelector('[type=submit]').disabled = false;
    }
    for (const cell of shell.querySelectorAll('[data-native-cell]')) {
      if (cell.dataset.mounted || !window.GooLive || !cell.closest('details')?.open) continue;
      cell.dataset.mounted = 'true';
      const path = cell.dataset.nativeCell;
      window.GooLive.mountViewer(cell, window.GooLive.mcpSource({views: path}), {crumb: path, views: path});
    }
    for (const row of shell.querySelectorAll('.goo-topos-member, .goo-member[data-key]')) {
      const selected = (row.getAttribute('subject') || row.dataset.key) === page;
      row.toggleAttribute('data-current', selected);
      const link = row.querySelector('a[data-goo-navigation], a[href*="path="]');
      if (link) {
        if (selected) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
    }
    for (const link of shell.querySelectorAll('.reader a[href]')) {
      const url = new URL(link.getAttribute('href'), location.href);
      if (url.origin !== location.origin) continue;
      const target = url.pathname.replace(/^\/ns(?=\/)/, '');
      const parts = target.slice(corpus.length + 1).split('/');
      // Runtime containers use the namespace inspector; named chapters use the reader.
      const runtime = parts.slice(1).some(part => ['flows', 'work', 'inputs', 'cells', 'holes'].includes(part));
      if (target.startsWith(corpus + '/') && !runtime && parts.every(part => /^[A-Za-z_][A-Za-z0-9_-]*$/.test(part)))
        link.href = '/nenex?path=' + encodeURIComponent(target);
    }
  };
  new MutationObserver(decorate).observe(shell, {childList: true, subtree: true});
  shell.addEventListener('toggle', decorate, true);
  decorate();
})();
