// The server owns these nodes; Mash owns their controls. This module only
// attaches namespace data reads, with cancellation and no disclosure mirroring.
export function bindDocumentFragment(main, view, {readPreview, attachValueInspection, requests}) {
  const pending = new WeakMap();
  const slots = new Map(view.record?.slots.map(slot => [slot.key, slot]) || []);
  for (const limb of main.querySelectorAll('#wb-canvas > section[aria-label=Record] sh-limb[data-key]')) {
    const slot = slots.get(limb.dataset.key);
    if (slot) attachValueInspection(limb.querySelector(':scope > sh-pail'), slot);
  }
  main.addEventListener('sh-path-row-toggle', async event => {
    const row = event.target;
    const preview = row.querySelector?.(':scope > [data-preview-path]');
    if (preview && !event.detail.open) { pending.get(preview)?.abort(); return; }
    if (!preview || !event.detail.open || preview.dataset.loaded || preview.hasAttribute('aria-busy')) return;
    const controller = new AbortController();
    pending.set(preview, controller);
    requests.add(controller);
    preview.setAttribute('aria-busy', 'true');
    preview.textContent = 'Loading…';
    try {
      const {workspace} = await readPreview(preview.dataset.previewPath, {signal: controller.signal});
      if (!preview.isConnected || controller.signal.aborted) return;
      const authored = workspace.querySelector('template#debug-path-preview');
      const declared = workspace.matches('[data-grove-contract="debugger/v1"]') &&
        ['workspace', 'preview'].includes(workspace.dataset.scope);
      if (!authored && !declared) throw new Error('Missing Grove path-preview declaration');
      const fragment = authored ? authored.content.cloneNode(true) : document.createDocumentFragment();
      if (!authored) for (const source of workspace.querySelectorAll('#wb-canvas > section:is([aria-label=Documentation], [aria-label=Semantics], [aria-label=Record])')) fragment.append(source.cloneNode(true));
      // Only inert Grove-authored content crosses the preview boundary.
      fragment.querySelectorAll('script,style,iframe,object,embed,form').forEach(node => node.remove());
      for (const node of fragment.querySelectorAll('*')) {
        for (const attr of [...node.attributes]) {
          if (/^on/i.test(attr.name) || ['id', 'srcdoc'].includes(attr.name)) node.removeAttribute(attr.name);
        }
        if (node.hasAttribute('href') && !/^\/debug(?:\/|$)/.test(node.getAttribute('href'))) node.removeAttribute('href');
      }
      preview.replaceChildren(fragment);
      if (!preview.textContent.trim()) preview.textContent = 'No slots or documentation at this path.';
      preview.dataset.loaded = 'true';
    } catch (error) {
      if (preview.isConnected) preview.textContent = controller.signal.aborted
        ? 'Preview paused. Close and reopen to load it.' : 'Could not load this path. Close and reopen to retry.';
    } finally {
      preview.removeAttribute('aria-busy');
      requests.delete(controller);
      if (pending.get(preview) === controller) pending.delete(preview);
    }
  });
}
