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
      if (target.startsWith(corpus + '/') && target.slice(corpus.length + 1).split('/').length === 1)
        link.href = '/nenex?path=' + encodeURIComponent(target);
    }
  };
  new MutationObserver(decorate).observe(shell, {childList: true, subtree: true});
  decorate();
})();
