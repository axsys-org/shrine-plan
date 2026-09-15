import {legacyElement} from './legacy.js';
const editing = event => event.composedPath().some(element => element?.matches?.(
  'input, textarea, select, [contenteditable]:not([contenteditable=false])'));

/**
 * One delegated Mash context menu for canonical namespace targets.
 * resolvePath(event) supplies {element, path, href, label}; this module never
 * infers an identity from visible prose or fetches namespace data.
 * report(message, failed, statusOptions) follows navigation.report's contract.
 * Clipboard writes use Mash's public copy() API, only after menu selection.
 */
export function createPathMenu({resolvePath, report = () => {}}) {
  if (typeof resolvePath !== 'function') throw new TypeError('Path actions need a canonical target resolver.');
  const declared = document.querySelector('[data-grove-contract="debugger/v1"]');
  const menu = declared ? declared.querySelector('#wb-path-menu') : legacyElement('ui-context-menu');
  menu.id = 'wb-path-menu';
  menu.setAttribute('density', 'compact');
  menu.setAttribute('sizing', 'content');
  menu.setAttribute('label', 'Path actions');
  const commands = new Map();
  for (const [value, label, name] of [['path', 'Copy path', 'action.duplicate'], ['link', 'Copy link', 'action.connect']]) {
    if (declared) { commands.set(value, menu.querySelector('[value="' + value + '"]')); continue; }
    const item = legacyElement('ui-menu-item');
    item.setAttribute('value', value); item.textContent = label;
    const icon = legacyElement('ui-icon');
    icon.slot = 'prefix'; icon.setAttribute('name', name); icon.setAttribute('size', 'small'); icon.setAttribute('aria-hidden', 'true');
    item.append(icon); menu.append(item); commands.set(value, item);
  }
  // The portable clipboard API owns platform support, fallback and errors.
  // Its hidden button is not another command or a nested focus stop.
  const clipboard = declared ? declared.querySelector('#wb-path-clipboard') : legacyElement('ui-clipboard');
  clipboard.hidden = true; clipboard.setAttribute('aria-hidden', 'true');
  if (!declared) (document.querySelector('.debug-shell') || document.body).append(menu, clipboard);
  let current = null, destroyed = false, copying = false;
  const observer = new MutationObserver(() => {
    if (current && !current.element.isConnected) dismiss();
  });

  function watchTarget(element) {
    observer.disconnect();
    // Include shadow ownership changes as well as removal of an outer host.
    let root = element.getRootNode();
    while (root) {
      observer.observe(root, {childList: true, subtree: true});
      root = root instanceof ShadowRoot ? root.host.getRootNode() : null;
    }
  }
  function dismiss() {
    observer.disconnect();
    current = null;
    menu.dismiss('imperative');
  }
  function open(event, keyboard) {
    if (destroyed || event.defaultPrevented || editing(event) || typeof menu.showAt !== 'function') return;
    const target = resolvePath(event);
    if (!target?.element?.isConnected || !target.element.getClientRects().length) return;
    event.preventDefault();
    current = target;
    menu.setAttribute('label', 'Path actions for ' + target.path);
    document.dispatchEvent(new CustomEvent('debug:path-overlay-open', {detail: {kind: 'menu', invoker: target.element}}));
    watchTarget(target.element);
    if (keyboard) { menu.anchorElement = target.element; menu.show('keyboard'); }
    else menu.showAt({x: event.clientX, y: event.clientY}, target.element);
  }
  function onContextMenu(event) { open(event, false); }
  function onKeydown(event) {
    if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ContextMenu' || event.key === 'F10' && event.shiftKey) open(event, true);
  }
  function onOpenChange(event) {
    if (event.target === menu && !event.detail.open) {
      observer.disconnect(); current = null;
    }
  }
  async function onSelect(event) {
    if (event.target !== menu || !current || copying || !commands.has(event.detail.value)) return;
    const target = current, kind = event.detail.value;
    copying = true;
    for (const item of commands.values()) item.disabled = true;
    clipboard.value = kind === 'path' ? target.path : target.href;
    try {
      await clipboard.copy();
      if (!destroyed) report(kind === 'path' ? 'Path copied.' : 'Link copied.', false,
        {operation: 'clipboard', phase: 'success', context: target.path, quiet: false});
    } catch {
      if (!destroyed) report('Could not copy the ' + kind + '. Clipboard access was denied or unavailable.', true,
        {operation: 'clipboard', phase: 'error', context: target.path, quiet: false});
    } finally {
      copying = false;
      for (const item of commands.values()) item.disabled = false;
    }
  }
  function onOverlay(event) { if (event.detail?.kind !== 'menu') dismiss(); }
  document.addEventListener('contextmenu', onContextMenu);
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('debug:navigation-start', dismiss);
  document.addEventListener('debug:path-overlay-open', onOverlay);
  menu.addEventListener('ui-context-menu-open-change', onOpenChange);
  menu.addEventListener('ui-context-menu-select', onSelect);
  return {
    dismiss,
    destroy() {
      if (destroyed) return;
      destroyed = true; dismiss();
      document.removeEventListener('contextmenu', onContextMenu);
      document.removeEventListener('keydown', onKeydown);
      document.removeEventListener('debug:navigation-start', dismiss);
      document.removeEventListener('debug:path-overlay-open', onOverlay);
      menu.removeEventListener('ui-context-menu-open-change', onOpenChange);
      menu.removeEventListener('ui-context-menu-select', onSelect);
      menu.remove(); clipboard.remove();
    },
  };
}
