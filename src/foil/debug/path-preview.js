
import {declaredTemplate} from './declarations.js';

const OPEN_DELAY = 320;
const CLOSE_DELAY = 180;
const CACHE_LIMIT = 60;
const CACHE_TTL = 30_000;

export function createMythPreview(view, href) {
  const authored = declaredTemplate('hover-myth');
  const myth = authored;
  myth.setAttribute('variant', 'preview'); myth.setAttribute('data-mash-size', 'compact');
  myth.setAttribute('title', view.label || view.path);
  const path = myth.querySelector('.wb-hover-path');
  path.textContent = view.path; path.slot = 'path'; path.href = href;

  if (view.description && view.description.trim() !== view.label?.trim()) {
    const description = myth.querySelector('.wb-hover-description');
    description.hidden = false; description.textContent = view.description; description.slot = 'description';
  }
  const slots = view.record?.slots || [];
  const slotCount = view.collection?.slotCount ?? slots.length;
  const shown = slots.filter(slot => !['/sys/lede','/sys/help','/sys/lash'].includes(slot.key)).slice(0, 3);
  for (const slot of shown) {
    const limb = declaredTemplate('hover-slot');
    const key = limb.querySelector('sh-slot'); key.slot = 'label'; key.setAttribute('title', slot.key);
    const definition = key.querySelector('ui-button'); definition.textContent = slot.key;
    definition.setAttribute('variant', 'text'); definition.setAttribute('size', 'small'); definition.setAttribute('type', 'button');
    definition.dataset.inspect = slot.key; definition.setAttribute('aria-label', 'Inspect slot definition ' + slot.key);

    const value = limb.querySelector('sh-pail'); value.slot = 'value';
    const candidate = slot.reference || (slot.links?.length === 1 &&
      [slot.links[0].text, slot.links[0].path].includes(slot.text) ? slot.links[0].path : null);
    const reference = typeof candidate === 'string' && candidate.startsWith('/') &&
      !candidate.split('/').some(part => part === '.' || part === '..') ? candidate : null;
    const text = value.querySelector(reference ? 'a' : 'span');
    text.hidden = false; text.textContent = slot.text === '' ? '""' : slot.text;
    if (reference) text.href = '/debug' + reference.split('/').filter(Boolean).map(part => '/' + encodeURIComponent(part)).join('');
     myth.append(limb);
  }
  const metadata = myth.querySelector('.wb-hover-meta'); metadata.slot = 'meta';
  const children = view.pagination?.total ?? String(view.collection?.childCount ?? view.children.length);
  metadata.textContent = (view.record ? slotCount + (slotCount === 1 ? ' slot' : ' slots') :
    view.state === 'tombstone' ? 'Removed record' : 'No own record') + ' · ' + children + (children === '1' ? ' child' : ' children');

  if (shown.length) {
    const note = myth.querySelector('.wb-hover-note');
    note.hidden = false; note.textContent = 'Preview · ' + shown.length + ' of ' + slotCount + ' slots';
    note.slot = 'annotation';
  }
  const open = myth.querySelector('.wb-hover-open'); open.slot = 'actions'; open.href = href;
  open.setAttribute('aria-label', 'Open ' + view.path);
  return myth;
}

export function createPathPreview({resolvePath, readPreview, initialView, renderRecord = createMythPreview}) {
  const card = document.querySelector('#wb-path-preview'); card.id = 'wb-path-preview';
  card.setAttribute('trigger', 'manual'); card.setAttribute('placement', 'right'); card.setAttribute('align', 'start');
  card.setAttribute('collision-padding', '12'); card.setAttribute('offset', '8');
  card.setAttribute('data-mash-size', 'compact');

  let target = null, openTimer, closeTimer, request = null, generation = 0, suppressed = null, menuOpen = false;
  let navigationQuiet = false, lastPointer = null;
  const cache = new Map();
  const controller = new AbortController();
  const listen = (name, handler, capture = false) => document.addEventListener(name, handler, {capture, signal: controller.signal});
  const remember = view => {
    if (!view?.path || view.scope === 'outline') return;
    cache.delete(view.path); cache.set(view.path, {view, time: performance.now()});
    while (cache.size > CACHE_LIMIT) cache.delete(cache.keys().next().value);
  };
  remember(initialView);
  function cancelRead() { generation++; request?.abort(); request = null; }
  function dismiss(reason = 'imperative') {
    clearTimeout(openTimer); clearTimeout(closeTimer); cancelRead(); card.dismiss(reason); target = null;
  }
  function setContent(state, content) {
    card.dataset.readState = state;
    card.querySelector('ui-scroll-area').replaceChildren(content);
    card.setAttribute('aria-busy', String(state === 'loading')); card.requestUpdate(); return;
  }
  async function load(chosen) {
    cancelRead(); const token = generation;
    const stored = cache.get(chosen.path);
    if (stored && performance.now() - stored.time < CACHE_TTL) {
      setContent('ready', renderRecord(stored.view, chosen.href)); return;
    }
    if (chosen.path === '/log') {
      const note = declaredTemplate('context-note'); note.textContent = 'Open activity to inspect its entries.';
      setContent('unavailable', note); return;
    }
    const loading = declaredTemplate('context-note'); loading.textContent = 'Loading record…'; loading.setAttribute('role', 'status');
    setContent('loading', loading);
    request = new AbortController(); const signal = request.signal;
    try {
      const answer = await readPreview(chosen.path, {signal});
      if (signal.aborted || token !== generation || target !== chosen || !chosen.element.isConnected) return;
      remember(answer.view); setContent('ready', renderRecord(answer.view, chosen.href));
    } catch (error) {
      if (signal.aborted || token !== generation || target !== chosen) return;
      const content = declaredTemplate('hover-error');
      content.querySelector('p').textContent = 'Could not preview this path. ' + error.message;
      content.querySelector('ui-button').addEventListener('click', () => void load(chosen));
      setContent('error', content);
    }
  }
  async function open(chosen, reason) {
    if (target !== chosen || menuOpen || !chosen.element.isConnected || !chosen.element.getClientRects().length) return;
    // Keep a tree leaf-out beyond the complete row, including its sibling
    // bookmark lane. The actual path control still owns hover/focus identity.
    const treeItem = chosen.element.matches('[role=treeitem]') ? chosen.element.getRootNode().host : null;
    card.anchorElement = treeItem?.matches('ui-tree-item.debug-namespace-node')
      ? treeItem.shadowRoot.querySelector('[part=root]') : chosen.element;
    card.dataset.path = chosen.path;
    card.setAttribute('label', 'Preview ' + chosen.path);
    card.show(reason);
    document.dispatchEvent(new CustomEvent('debug:path-overlay-open', {detail: {kind: 'preview'}}));
    void load(chosen);
  }
  function schedule(found, reason) {
    if (!found || navigationQuiet || menuOpen || found.element === suppressed) return;
    clearTimeout(closeTimer);
    if (target?.element === found.element && target.path === found.path) return;
    // Native browser bubbles must not compete with the authored Myth. Do not
    // remove semantic title attributes from Mash/Shine custom elements.
    const described = [found.element, ...found.element.querySelectorAll('[title]'),
      ...(found.element.shadowRoot?.querySelectorAll('[title]') || [])];
    for (const node of described) if (!node.localName.includes('-')) node.removeAttribute('title');
    // Explicit empty native title also stops an ancestor's browser hint from
    // leaking through (tree-item.title remains the actual authored row label).
    if (!found.element.localName.includes('-')) found.element.setAttribute('title', '');
    dismiss(); target = found; openTimer = setTimeout(() => void open(found, reason), OPEN_DELAY);
  }
  function leave() {
    if (menuOpen) return;
    clearTimeout(openTimer);
    if (!card.open) { dismiss(); return; }
    clearTimeout(closeTimer); closeTimer = setTimeout(() => dismiss('hover'), CLOSE_DELAY);
  }
  function inside(source, owner) {
    if (!owner) return false;
    if (source?.composedPath?.().includes(owner)) return true;
    for (let node = source; node instanceof Node; node = node.assignedSlot || node.parentNode || node.host) if (node === owner) return true;
    return false;
  }
  const insideCard = source => inside(source, card);
  function insideOwnedMenu(source) {
    const menu = document.getElementById('wb-path-menu');
    return menuOpen && insideCard(menu?.anchorElement) && inside(source, menu);
  }
  listen('pointermove', event => {
    if (event.pointerType === 'touch') return;
    const moved = !lastPointer || lastPointer.x !== event.clientX || lastPointer.y !== event.clientY;
    lastPointer = {x: event.clientX, y: event.clientY};
    // Replacing content under a stationary pointer is not fresh hover intent.
    if (navigationQuiet && moved && event.isTrusted) {
      navigationQuiet = false;
      if (!insideCard(event)) schedule(resolvePath(event), 'hover');
    }
  });
  listen('pointerover', event => {
    if (event.pointerType === 'touch' || navigationQuiet) return;
    if (insideCard(event)) { clearTimeout(closeTimer); return; }
    const found = resolvePath(event);
    if (found?.element !== suppressed) suppressed = null;
    if (found) schedule(found, 'hover'); else leave();
  });
  listen('pointerout', event => {
    if (suppressed && resolvePath(event)?.element === suppressed && resolvePath(event.relatedTarget)?.element !== suppressed) suppressed = null;
    if (event.pointerType === 'touch' || insideCard(event.relatedTarget) || insideOwnedMenu(event.relatedTarget)) return;
    const related = resolvePath(event.relatedTarget);
    if (related?.element === target?.element) return;
    if (insideCard(event) || resolvePath(event)?.element === target?.element) leave();
  });
  let touchFocusUntil = 0;
  listen('pointerdown', event => {
    lastPointer = {x: event.clientX, y: event.clientY};
    if (event.pointerType === 'touch') touchFocusUntil = performance.now() + 1000;
  }, true);
  listen('focusin', event => {
    if (navigationQuiet || performance.now() < touchFocusUntil) return;
    if (insideOwnedMenu(event)) return;
    if (insideCard(event)) { clearTimeout(closeTimer); return; }
    const found = resolvePath(event);
    if (found?.element !== suppressed) suppressed = null;
    if (found) schedule(found, 'focus'); else dismiss('focus');
  });
  listen('focusout', event => {
    if (insideCard(event.relatedTarget) || insideOwnedMenu(event.relatedTarget) || resolvePath(event.relatedTarget)?.element === target?.element) return;
    leave();
  });
  listen('keydown', event => {
    if (event.isTrusted) navigationQuiet = false;
    if (event.key !== 'Escape' || !target || menuOpen) return;
    const visible = card.open;
    suppressed = target.element; dismiss('escape');
    if (visible) { event.preventDefault(); event.stopPropagation(); }
  }, true);
  listen('pointerdown', event => { if (!insideCard(event) && !insideOwnedMenu(event)) dismiss('outside'); }, true);
  listen('contextmenu', event => { if (!insideCard(event) && !insideOwnedMenu(event)) dismiss('contextmenu'); }, true);
  listen('debug:navigation-start', () => { dismiss(); cache.clear(); navigationQuiet = true; });
  listen('debug:path-snapshot', event => remember(event.detail?.view));
  listen('debug:navigate', event => remember(event.detail?.document));
  listen('debug:inspect', event => remember(event.detail?.document));
  listen('debug:path-overlay-open', event => {
    if (event.detail?.kind === 'preview') return;
    if (event.detail?.kind === 'menu' && insideCard(event.detail.invoker)) {
      menuOpen = true; clearTimeout(closeTimer); clearTimeout(openTimer); cancelRead();
    } else dismiss();
  });
  for (const name of ['ui-context-menu-open-change','ui-menu-open-change','ui-popover-open-change']) {
    listen(name, event => {
      menuOpen = Boolean(event.detail?.open);
      if (menuOpen && !insideCard(event.target?.anchorElement)) dismiss();
    });
  }
  card.addEventListener('ui-preview-card-open-change', event => {
    if (event.detail?.open === false) { clearTimeout(openTimer); clearTimeout(closeTimer); cancelRead(); }
  });
  const observer = new MutationObserver(() => { if (target && !target.element.isConnected) dismiss(); });
  observer.observe(document.querySelector('.debug-shell'), {childList: true, subtree: true});
  return {dismiss, destroy() { dismiss(); controller.abort(); observer.disconnect(); card.remove(); cache.clear(); }};
}
