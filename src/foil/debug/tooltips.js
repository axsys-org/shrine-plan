import {legacyElement} from './legacy.js';
/** One passive Mash action hint; existing controls retain their DOM and behavior. */
const controllers = new WeakMap();
const overlayEvents = ['ui-menu-open-change', 'ui-popover-open-change', 'ui-context-menu-open-change', 'ui-preview-card-open-change'];
const cancelEvents = ['debug:navigation-start', 'debug:inspect-start', 'debug:read-complete'];

// Only shortcuts actually handled by this debugger are advertised.
const hints = {
  'wb-path-edit': {shortcut: 'Primary+L', keys: 'Control or Command plus L'},
};

function ancestors(element) {
  const nodes = [];
  for (let node = element; node; node = node.parentNode || node.host) nodes.push(node);
  return nodes;
}

/**
 * resolvePath(element) returns a truthy namespace target to reserve that control
 * for the caller's record preview. It must not fetch. Native title suppression
 * lasts until destroy(), so dismissal cannot summon a second browser bubble.
 */
export function createTooltips({resolvePath = () => null} = {}) {
  const doc = document;
  if (controllers.has(doc)) return controllers.get(doc);
  const declared = doc.querySelector('[data-grove-contract="debugger/v1"]');
  const tip = declared ? doc.querySelector('#wb-action-tooltip') : legacyElement('ui-tooltip');
  tip.id = 'wb-action-tooltip';
  tip.className = 'wb-action-tooltip';
  tip.setAttribute('trigger', 'manual');
  tip.setAttribute('placement', 'bottom');
  tip.setAttribute('align', 'center');
  tip.setAttribute('open-delay', '500');
  tip.setAttribute('close-delay', '120');
  tip.setAttribute('data-mash-size', 'small');
  if (!declared) (doc.querySelector('.debug-shell') || doc.body).append(tip);

  let current = null, openTimer = 0, closeTimer = 0, destroyed = false, modality = 'keyboard';
  let lastPointer = null;
  let version = 0;
  const titles = new Map();
  const openOverlays = new Set();
  const hover = matchMedia('(hover: hover) and (pointer: fine)');
  const listeners = [];
  const observer = new MutationObserver(() => {
    if (!current) return;
    if (!usable(current)) { dismiss(); return; }
    suppressTitles(current);
    paint(current);
  });
  const listen = (target, name, callback, options) => {
    target.addEventListener(name, callback, options);
    listeners.push(() => target.removeEventListener(name, callback, options));
  };
  const pathTarget = action => Boolean(resolvePath(action.host) || (action.host !== action.native && resolvePath(action.native)));
  const isBlocked = () => {
    for (const overlay of openOverlays) if (!overlay.isConnected || !overlay.open) openOverlays.delete(overlay);
    return openOverlays.size > 0;
  };
  const usable = action => action.native.isConnected && action.host.isConnected && !isBlocked() && !pathTarget(action) &&
    !action.native.matches(':disabled, [aria-disabled=true]') && !action.host.matches('[disabled], [loading], [aria-disabled=true], [hidden]') &&
    action.native.getClientRects().length > 0;
  const labelOf = action => (action.host.getAttribute('aria-label') || action.native.getAttribute('aria-label') ||
    action.host.getAttribute('title') || action.native.getAttribute('title') || titles.get(action.host) || titles.get(action.native) || '').trim();
  function candidate(event) {
    const path = event.composedPath();
    if (path.includes(tip)) return null;
    const native = path.find(node => node instanceof HTMLElement && node.matches('button, a[href], input[type=button], input[type=submit]'));
    if (!native) return null;
    const host = path.find(node => node instanceof HTMLElement && node.localName === 'ui-button') || native;
    // Visible labels, links, section headings and namespace paths explain
    // themselves. Only icon-only commands need an additional action label.
    if (!host.matches('[icon-only], .wb-icon-button') || path.some(node => node instanceof HTMLElement &&
      node.matches('ui-tooltip, ui-menu, ui-context-menu, ui-preview-card, [data-tooltip=off]'))) return null;
    const action = {host, native, fingerprint: ''};
    return labelOf(action) && usable(action) ? action : null;
  }
  function suppressTitles(action) {
    // Never remove semantic title properties from tree items, myths, paths, etc.
    for (const target of new Set([action.host, action.native])) {
      if (!target.matches('ui-button, button, a, input')) continue;
      if (!titles.has(target) || target.getAttribute('title') !== '') {
        titles.set(target, target.getAttribute('title'));
      }
      if (target.getAttribute('title') !== '') target.setAttribute('title', '');
    }
  }
  function restoreTitles() {
    for (const [target, title] of titles) if (target.getAttribute('title') === '') {
      if (title === null) target.removeAttribute('title'); else target.setAttribute('title', title);
    }
    titles.clear();
  }
  function paint(action) {
    const label = labelOf(action);
    const hint = hints[action.host.id] || (action.host.classList.contains('wb-path-cancel')
      ? {shortcut: 'Escape', keys: 'Escape'} : {});
    const fingerprint = JSON.stringify([label, hint.shortcut]);
    if (action.fingerprint === fingerprint) return;
    action.fingerprint = fingerprint;
    if (declared) {
      tip.querySelector('[data-tooltip-label]').textContent = label;
      const key = tip.querySelector('ui-kbd'); key.hidden = !hint.shortcut;
      key.setAttribute('shortcut', hint.shortcut || '');
      tip.querySelector('[data-tooltip-keys]').textContent = hint.keys ? ' · ' + hint.keys : '';
      return;
    }
    const content = legacyElement('span'); content.className = 'wb-tooltip-content';
    const heading = legacyElement('span'); heading.className = 'wb-tooltip-heading';
    const name = legacyElement('span'); name.textContent = label; heading.append(name);
    if (hint.shortcut) {
      const key = legacyElement('ui-kbd');
      key.setAttribute('shortcut', hint.shortcut); key.setAttribute('appearance', 'plain');
      heading.append(key);
      // ui-kbd's default slot must stay empty so Mash renders platform keys.
      // The description helper reads light text into the control's own scope;
      // this passive hidden text makes that shortcut understandable there too.
      const shortcutText = legacyElement('span'); shortcutText.hidden = true;
      shortcutText.textContent = ' · ' + hint.keys; heading.append(shortcutText);
    }
    content.append(heading);
    tip.replaceChildren(content);
  }
  function dismiss(reason = 'imperative') {
    version++;
    clearTimeout(openTimer); clearTimeout(closeTimer); openTimer = closeTimer = 0;
    observer.disconnect();
    tip.dismiss(reason);
    tip.anchorElement = null;
    current = null;
  }
  function enter(action, focus = false) {
    if (destroyed) return;
    if (current?.native === action.native) {
      clearTimeout(closeTimer);
      if (!focus || tip.open) return;
      clearTimeout(openTimer);
    } else {
      dismiss(); current = action;
      // Drop detached controls from this bounded page controller's ownership.
      for (const [target, title] of titles) if (!target.isConnected) {
        if (target.getAttribute('title') === '') {
          if (title === null) target.removeAttribute('title'); else target.setAttribute('title', title);
        }
        titles.delete(target);
      }
      suppressTitles(action); paint(action);
      // A row-action hint must not cover the next row's bookmark. Shared
      // collision handling may flip it to the other side of this action lane.
      tip.setAttribute('placement', action.host.classList.contains('debug-bookmark-toggle')
        ? (getComputedStyle(action.host).direction === 'rtl' ? 'left' : 'right') : 'bottom');
      tip.anchorElement = action.native;
      // Observe only the active control and its ancestor chain, not every
      // mutation in the workbench. Removal and disabled/label changes dismiss
      // or update the existing hint without polling or retaining old controls.
      for (const node of ancestors(action.native)) {
        if (node === doc) continue;
        observer.observe(node, {childList: true, ...(node === action.native || node === action.host ?
          {attributes: true, attributeFilter: ['title', 'aria-label', 'disabled', 'loading', 'aria-disabled', 'hidden']} : {})});
      }
    }
    const revision = ++version;
    const show = () => {
      openTimer = 0;
      if (revision !== version || !current || !usable(current)) { if (revision === version) dismiss(); return; }
      tip.show(focus ? 'focus' : 'hover');
    };
    if (focus) show(); else openTimer = setTimeout(show, 500);
  }
  const focused = () => {
    let active = doc.activeElement;
    while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
    return active;
  };
  const containsAction = target => current && target instanceof Node && ancestors(target).some(node => node === current.host || node === current.native);
  const leave = event => {
    if (!current || containsAction(event.relatedTarget) || (event.relatedTarget instanceof Node && ancestors(event.relatedTarget).includes(tip))) return;
    if (modality === 'keyboard' && focused() === current.native && current.native.matches(':focus-visible')) return;
    clearTimeout(openTimer); openTimer = 0;
    closeTimer = setTimeout(() => dismiss(), 120);
  };
  listen(doc, 'pointerover', event => {
    if (event.pointerType === 'touch' || !hover.matches) return;
    if (event.composedPath().includes(tip)) { clearTimeout(closeTimer); return; }
    const action = candidate(event);
    if (action) enter(action);
  }, true);
  listen(doc, 'pointerout', leave, true);
  listen(doc, 'pointermove', event => {
    if (event.pointerType === 'touch' || !hover.matches) return;
    const moved = !lastPointer || lastPointer.x !== event.clientX || lastPointer.y !== event.clientY;
    lastPointer = {x: event.clientX, y: event.clientY};
    if (!moved || !event.isTrusted || modality !== 'keyboard' || !current) return;
    const path = event.composedPath();
    if (path.includes(tip) || path.includes(current.native) || path.includes(current.host)) return;
    // Pointer intent supersedes a passive keyboard hint, without blurring its
    // owner or spending a click on dismissal before the next action works.
    modality = 'pointer'; dismiss();
  }, true);
  listen(doc, 'focusin', event => {
    const action = candidate(event);
    if (action && (modality === 'keyboard' || action.native.matches(':focus-visible'))) enter(action, true);
  }, true);
  listen(doc, 'focusout', () => {
    const previous = current;
    queueMicrotask(() => { if (current === previous && current && focused() !== current.native) dismiss(); });
  }, true);
  listen(doc, 'pointerdown', () => { modality = 'pointer'; dismiss(); }, true);
  listen(doc, 'pointercancel', () => dismiss(), true);
  listen(doc, 'keydown', event => {
    if (event.isComposing) return;
    modality = 'keyboard';
    if (event.key === 'Escape') {
      // A passive hint must not spend the Escape that dismisses the inspector,
      // path editor, or other owning surface. The shared tooltip now sees closed.
      dismiss('escape');
    }
  }, true);
  listen(doc, 'debug:path-overlay-open', event => {
    if (event.detail?.kind === 'menu' || event.detail?.kind === 'preview') dismiss();
  });
  for (const name of overlayEvents) listen(doc, name, event => {
    const overlay = event.composedPath()[0];
    if (event.detail?.open) { openOverlays.add(overlay); dismiss(); }
    else openOverlays.delete(overlay);
  }, true);
  for (const name of cancelEvents) listen(doc, name, () => dismiss());
  listen(window, 'blur', () => dismiss());
  listen(window, 'pagehide', () => dismiss());
  listen(doc, 'visibilitychange', () => { if (doc.hidden) dismiss(); });
  const controller = {dismiss, destroy() {
    if (destroyed) return;
    destroyed = true; dismiss(); restoreTitles();
    listeners.forEach(remove => remove()); openOverlays.clear(); tip.remove(); controllers.delete(doc);
  }};
  controllers.set(doc, controller);
  return controller;
}
