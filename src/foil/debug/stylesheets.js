const controllers = new WeakMap();
const attributes = ['href', 'rel', 'media', 'disabled', 'data-mash-tokens'];
const versionIdentifier = /^asset-[a-f0-9]{1,64}$/;

/**
 * Retire only the exact same-origin /style.css after enhancement commits and
 * both replacement stylesheets prove their build identity. Link nodes stay in
 * place; pre-disabled legacy sheets are never owned or enabled by this module.
 *
 * commit() arms retirement; restore() disarms it; dispose() also removes every
 * observer/listener. check() reconciles synchronously. Each returns a frozen
 * { ready, committed, active, reason, legacyCount, disabledCount } snapshot.
 * A matching call in this module reuses the same Document controller.
 *
 * DOM changes, stylesheet load/error and media-query changes reconcile in one
 * microtask. CSSOM-only edits have no platform change event: callers changing
 * sheet.disabled, sheet.media or rules directly must explicitly call check().
 * No polling, network requests, global CSSOM patches or frame traversal occur.
 */
export function beginStylesheetHandoff({
  document: doc = globalThis.document,
  appVersion,
  componentsVersion,
} = {}) {
  const registrable = doc && typeof doc === 'object';
  const previous = registrable ? controllers.get(doc) : null;
  if (previous && previous.appVersion === appVersion && previous.componentsVersion === componentsVersion) {
    return previous.api;
  }
  previous?.api.dispose();

  const view = doc?.defaultView;
  const owned = new Map();
  const fresh = new Map();
  const media = new Map();
  const metadata = new Set();
  let observer;
  let committed = false;
  let disposed = false;
  let checking = false;
  let scheduled = false;
  let ready = false;
  let reason = 'awaiting-styles';
  let legacyCount = 0;

  function snapshot() {
    return Object.freeze({
      ready,
      committed,
      active: !disposed && committed && ready,
      reason: disposed ? 'disposed' : ready && !committed ? 'awaiting-commit' : reason,
      legacyCount,
      disabledCount: owned.size,
    });
  }

  function exactLink(node, path) {
    if (node?.ownerDocument !== doc || !node.isConnected || node.localName !== 'link' || !node.hasAttribute('href')) return false;
    const rel = node.rel.toLowerCase().split(/\s+/);
    if (!rel.includes('stylesheet') || rel.includes('alternate')) return false;
    try {
      const url = new URL(node.getAttribute('href') || '', doc.baseURI);
      return url.origin === view.location.origin && url.pathname === path && !url.search && !url.hash;
    } catch { return false; }
  }

  function restoreOwned() {
    for (const [link, original] of owned) {
      // A detached/repointed node is still ours to restore, but an adopted node
      // belongs to its new Document and must not be changed from this one.
      if (link.ownerDocument === doc) {
        try {
          link.disabled = original.linkDisabled;
          if (link.sheet === original.sheet && original.sheet) original.sheet.disabled = original.sheetDisabled;
        } catch { /* Optional styling must not interrupt the workbench. */ }
      }
      owned.delete(link);
    }
  }

  function schedule() {
    if (disposed || scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      if (!disposed) check();
    });
  }

  function watchLinks(links) {
    for (const [link, state] of fresh) {
      if (links.includes(link)) continue;
      link.removeEventListener('load', state.load);
      link.removeEventListener('error', state.error);
      fresh.delete(link);
    }
    for (const link of links) {
      const signature = `${link.href}\n${link.rel}`;
      const existing = fresh.get(link);
      if (existing) {
        if (existing.signature !== signature) {
          existing.signature = signature;
          existing.failed = false;
        }
        continue;
      }
      const state = { signature, failed: false };
      state.load = () => { state.failed = false; schedule(); };
      state.error = () => { state.failed = true; schedule(); };
      link.addEventListener('load', state.load);
      link.addEventListener('error', state.error);
      fresh.set(link, state);
    }
  }

  function watchMedia(nodes) {
    const queries = new Set();
    for (const node of nodes) {
      for (const query of [node.media, node.sheet?.media?.mediaText]) {
        if (query?.trim()) queries.add(query.trim());
      }
    }
    for (const [query, list] of media) {
      if (queries.has(query)) continue;
      list.removeEventListener('change', schedule);
      media.delete(query);
    }
    for (const query of queries) {
      if (media.has(query)) continue;
      const list = view.matchMedia(query);
      list.addEventListener('change', schedule);
      media.set(query, list);
    }
  }

  function activeSheet(node) {
    if (!node.isConnected || node.disabled || !node.sheet || node.sheet.disabled ||
        node.sheet.ownerNode !== node || fresh.get(node)?.failed) return false;
    return [node.media, node.sheet.media?.mediaText].every(query =>
      !query?.trim() || media.get(query.trim())?.matches === true);
  }

  function observe(nodes) {
    observer.disconnect();
    const targets = new Map();
    const add = (node, options) => {
      if (node) targets.set(node, { ...targets.get(node), ...options });
    };
    // Current server HTML places fresh links directly in body, not head. Watch
    // metadata and known ancestor boundaries, never the changing app subtree.
    add(doc.documentElement, { childList: true });
    add(doc.body, { childList: true });
    for (const node of nodes) {
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        add(parent, { childList: true });
      }
      add(node, {
        attributes: true,
        attributeFilter: attributes,
        ...(node.localName === 'style' ? { childList: true, characterData: true, subtree: true } : {}),
      });
    }
    add(doc.head, {
      childList: true, characterData: true, subtree: true,
      attributes: true, attributeFilter: attributes,
    });
    for (const [node, options] of targets) observer.observe(node, options);
  }

  function check() {
    if (disposed || checking) return snapshot();
    checking = true;
    try {
      ready = false;
      if (!view || view.top !== view || doc.nodeType !== 9 || !observer) {
        reason = 'unsupported-document';
      } else if (!versionIdentifier.test(appVersion || '') || !versionIdentifier.test(componentsVersion || '')) {
        reason = 'invalid-versions';
      } else {
        const links = [...doc.querySelectorAll('link')];
        const legacy = links.filter(link => exactLink(link, '/style.css'));
        const app = links.filter(link => exactLink(link, '/debug.css'));
        const components = links.filter(link => exactLink(link, '/debug-components.css'));
        const tokens = [...doc.querySelectorAll('style[data-mash-tokens]')];
        const watched = [...legacy, ...app, ...components, ...tokens];
        for (const node of [...links, ...tokens]) metadata.add(node);
        for (const node of metadata) {
          if (!node.isConnected || node.ownerDocument !== doc) metadata.delete(node);
        }
        legacyCount = legacy.length;
        watchLinks([...app, ...components]);
        watchMedia(watched);
        // Keep a formerly matching body node observable while connected: its
        // href, rel or token marker may be corrected without a new insertion.
        observe(metadata);
        if (!app.length) reason = 'missing-app';
        else if (!components.length) reason = 'missing-components';
        else if (!app.some(activeSheet)) reason = 'inactive-app';
        else if (!components.some(activeSheet)) reason = 'inactive-components';
        else if (!tokens.length) reason = 'missing-tokens';
        else if (!tokens.some(node => activeSheet(node) && node.sheet.cssRules.length > 0)) reason = 'inactive-tokens';
        else {
          const style = view.getComputedStyle(doc.documentElement);
          if (!style.getPropertyValue('--color-text').trim() || !style.getPropertyValue('--type-code-font-family').trim()) reason = 'incomplete-tokens';
          else if (style.getPropertyValue('--shrine-debug-app-ready').trim() !== appVersion) reason = 'app-version-mismatch';
          else if (style.getPropertyValue('--shrine-debug-components-ready').trim() !== componentsVersion) reason = 'components-version-mismatch';
          else { ready = true; reason = 'ready'; }
        }
        if (ready && committed) {
          for (const [link, original] of owned) {
            if (legacy.includes(link)) continue;
            if (link.ownerDocument === doc) {
              link.disabled = original.linkDisabled;
              if (link.sheet === original.sheet && original.sheet) original.sheet.disabled = original.sheetDisabled;
            }
            owned.delete(link);
          }
          for (const link of legacy) {
            if (owned.has(link)) {
              if (!link.disabled) link.disabled = true;
            } else if (!link.disabled && !link.sheet?.disabled) {
              owned.set(link, { linkDisabled: link.disabled, sheet: link.sheet, sheetDisabled: link.sheet?.disabled });
              link.disabled = true;
            }
          }
        }
      }
      if (!ready || !committed) restoreOwned();
    } catch {
      ready = false;
      reason = 'check-error';
      restoreOwned();
    } finally {
      checking = false;
    }
    return snapshot();
  }

  const api = Object.freeze({
    check,
    commit() {
      if (!disposed) committed = true;
      return check();
    },
    restore() {
      committed = false;
      restoreOwned();
      return check();
    },
    dispose() {
      if (disposed) return snapshot();
      committed = false;
      disposed = true;
      ready = false;
      restoreOwned();
      observer?.disconnect();
      for (const [link, state] of fresh) {
        link.removeEventListener('load', state.load);
        link.removeEventListener('error', state.error);
      }
      for (const list of media.values()) list.removeEventListener('change', schedule);
      fresh.clear();
      media.clear();
      metadata.clear();
      if (registrable && controllers.get(doc)?.api === api) controllers.delete(doc);
      return snapshot();
    },
  });
  if (registrable) controllers.set(doc, { appVersion, componentsVersion, api });
  try {
    if (view?.MutationObserver && view.top === view) observer = new view.MutationObserver(schedule);
  } catch { /* Unsupported documents keep their original stylesheet. */ }
  check();
  return api;
}
