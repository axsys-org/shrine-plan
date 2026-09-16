// Resolve authored namespace destinations, never guess paths from prose.
// Walk composed ancestry so native controls inside Mash shadows behave alike.
function ancestry(source) {
  if (typeof source?.composedPath === 'function') return source.composedPath().filter(node => node instanceof Element);
  const nodes = [];
  for (let node = source; node; node = node.assignedSlot || node.parentNode || node.host) {
    if (node instanceof Element) nodes.push(node);
  }
  return nodes;
}
function canonical(path) {
  return typeof path === 'string' && path.startsWith('/') && !path.split('/').some(part => part === '.' || part === '..')
    ? '/' + path.split('/').filter(Boolean).join('/') : null;
}
function debugHref(path) {
  return new URL('/debug' + path.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join(''), location.origin).href;
}
export function resolvePath(source) {
  const chain = ancestry(source);
  if (chain.some(node => node.matches('input,textarea,select,[contenteditable]:not([contenteditable=false])'))) return null;
  // A composed path label can appear before its native anchor in the event
  // path. The real href is authoritative, including authored paging queries.
  const authoredLink = chain.find(node => node.matches('a[href],ui-link[href],ui-menu-item[href]'));
  if (authoredLink && chain[0] !== authoredLink) return resolvePath(authoredLink);
  let native = null;
  for (const element of chain) {
    if (element.matches('a[href],ui-link[href],ui-menu-item[href]')) {
      try {
        const url = new URL(element.getAttribute('href'), location.href);
        if (url.origin !== location.origin || !/^\/(debug|ns)(\/|$)/.test(url.pathname)) return null;
        const path = canonical(decodeURIComponent(url.pathname.replace(/^\/(debug|ns)/, '') || '/'));
        if (!path) return null;
        if (/^\/ns(?:\/|$)/.test(url.pathname)) url.pathname = '/debug' + url.pathname.slice(3);
        return {element: native || element, path, href: url.href, label: element.textContent.trim() || path};
      } catch { return null; }
    }
    const path = canonical(element.dataset.inspect || element.dataset.pathTarget ||
      (element.matches('ui-path[path],ui-tree-item[data-path],ui-menu-item[data-path]') ? element.getAttribute('path') || element.dataset.path : null));
    if (path) {
      const anchor = native || chain.find(node => node.matches('[role=treeitem]')) ||
        (element.matches('ui-tree-item') ? element.shadowRoot?.querySelector('[role=treeitem]') : null) || element;
      return {element: anchor, path, href: debugHref(path), label: element.textContent.trim() || path};
    }
    if (element.matches('button,[role=treeitem]')) {
      native ||= element;
      // A tree row is a destination; its sibling action/disclosure buttons are not.
      if (!element.matches('[role=treeitem]') && !chain.some(node => node.matches('[data-inspect],[data-path-target],ui-menu-item[data-path]'))) return null;
    }
    if (element.matches('ui-button') && !element.hasAttribute('data-inspect') && !element.hasAttribute('data-path-target')) return null;
  }
  return null;
}
