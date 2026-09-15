import {legacyElement} from './legacy.js';
import { button, icon, iconNames } from './icons.js';
import {declaredTemplate} from './declarations.js';

const element = (tag, className = '', text = '') => {
  const node = legacyElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
};
const basename = path => path === '/' ? '/' : path.split('/').filter(Boolean).at(-1);
const isEditing = event => event.composedPath().some(target => target?.matches?.(
  'input, textarea, select, [contenteditable]:not([contenteditable=false])'));
const CHILD_LIMIT = 20;
const CACHE_LIMIT = 24;
const CACHE_TTL_MS = 30_000;

/**
 * Persistent namespace navigation, composed from Mash path/menu primitives.
 * The existing form is MOVED, not replaced: navigation.js remains the sole
 * owner of canonical validation, dirty-draft protection, submit and routing.
 *
 * createPathLocator({ navigation, form, initialView }) returns:
 *   element — insert this in the command bar instead of the original form;
 *   edit() / close() — show the address editor / restore the trail;
 *   update(view, { refresh = false }) — redraw from an actual document;
 *   destroy() — remove listeners and cancel outstanding child reads.
 * It also owns debug:navigate / debug:navigation-start subscriptions and
 * unmodified / or Primary+L shortcuts. Import locator.css after compact.css.
 * Ancestor menus reuse at most 24 actual snapshots for 30 seconds. Ordinary
 * navigation retains this bounded LRU cache; explicit refresh clears it. The
 * current path always uses the fresh foreground document, never cached data.
 */
export function createPathLocator({ navigation, form, initialView, declared = false }) {
  declared = !__DEBUG_LEGACY__ || declared;
  if (!navigation || !form?.querySelector('ui-input') || !initialView?.path) {
    throw new TypeError('A path locator needs navigation, the existing path form, and an initial view.');
  }
  const root = declared ? document.querySelector('#wb-path-locator') : element('div', 'wb-path-locator');
  root.id = 'wb-path-locator';
  const trail = declared ? root.querySelector('.wb-path-trail') : element('nav', 'wb-path-trail');
  trail.setAttribute('aria-label', 'Namespace location');
  const scroll = declared ? trail.querySelector('.wb-path-scroll') : element('ui-scroll-area', 'wb-path-scroll mash-scroll-quiet');
  scroll.setAttribute('label', 'Namespace ancestors');
  scroll.setAttribute('orientation', 'horizontal');
  scroll.setAttribute('mode', 'scrolling');
  scroll.setAttribute('size', 'medium');
  const segments = declared ? scroll.querySelector('.wb-path-segments') : element('ol', 'wb-path-segments');
  if (!declared) scroll.append(segments);
  const editButton = declared ? root.querySelector('#wb-path-edit') : button('Edit namespace path', 'edit');
  editButton.addEventListener('click', () => edit());
  editButton.id = 'wb-path-edit';
  editButton.title = '';
  editButton.setAttribute('aria-controls', form.id);
  editButton.setAttribute('aria-expanded', 'false');
  editButton.setAttribute('aria-keyshortcuts', '/ Control+L Meta+L');
  const cancelButton = declared ? form.querySelector('.wb-path-cancel') : button('Cancel path edit', 'close');
  cancelButton.addEventListener('click', () => close());
  cancelButton.classList.add('wb-path-cancel');
  const inputGroup = form.querySelector('ui-input-group');
  if (inputGroup) cancelButton.slot = 'suffix';
  const input = form.querySelector('ui-input');
  input.setAttribute('label', 'Namespace path');
  input.setAttribute('aria-label', 'Namespace path');
  form.setAttribute('aria-label', 'Open namespace path');
  if (!declared) {
    (inputGroup || form).append(cancelButton);
    trail.append(scroll, editButton);
    root.append(trail, form);
  }
  let view = initialView;
  let editorOpen = false;
  let returnFocus = null;
  let destroyed = false;
  let generation = 0;
  const menus = new Set();
  const pending = new Map();
  const cache = new Map();

  function rememberView(snapshot) {
    cache.delete(snapshot.path);
    cache.set(snapshot.path, { view: snapshot, readAt: performance.now() });
    while (cache.size > CACHE_LIMIT) cache.delete(cache.keys().next().value);
  }

  function cachedView(path) {
    const entry = cache.get(path);
    if (!entry) return null;
    cache.delete(path);
    if (performance.now() - entry.readAt >= CACHE_TTL_MS) return null;
    cache.set(path, entry);
    return entry.view;
  }

  function closeMenus(except = null) {
    for (const menu of menus) if (menu !== except && menu.open) menu.dismiss('imperative');
  }

  function cancelReads() {
    generation++;
    for (const controller of pending.values()) controller.abort();
    pending.clear();
  }

  function clearAddressValidation() {
    if (inputGroup) inputGroup.invalid = false;
    input.invalid = false;
  }

  async function edit() {
    if (destroyed) return;
    closeMenus();
    if (!editorOpen) returnFocus = document.activeElement;
    editorOpen = true;
    clearAddressValidation();
    root.dataset.editing = 'true';
    form.hidden = false;
    trail.hidden = true;
    editButton.setAttribute('aria-expanded', 'true');
    input.value = view.path;
    await input.updateComplete;
    if (!editorOpen || destroyed) return;
    input.focus();
    // Mash input exposes selection through its native control, not a second
    // application input with divergent form state.
    input.select?.();
  }

  function close({ restoreFocus = true } = {}) {
    editorOpen = false;
    clearAddressValidation();
    delete root.dataset.editing;
    form.hidden = true;
    trail.hidden = false;
    input.value = view.path;
    editButton.setAttribute('aria-expanded', 'false');
    if (restoreFocus) {
      const target = returnFocus?.isConnected && !form.contains(returnFocus) && returnFocus !== document.body
        ? returnFocus : editButton;
      target.focus();
    }
    returnFocus = null;
  }

  function item(path, label = basename(path), glyph = 'record', className = '') {
    const option = declaredTemplate('path-option') || element('ui-menu-item', 'mash-menu-rich');
    if (className) option.classList.add(className);
    option.setAttribute('value', path);
    option.setAttribute('href', navigation.debugURL(path));
    option.setAttribute('aria-label', 'Open ' + path);
    option.dataset.path = path;
    const prefix = declared ? option.querySelector('ui-icon') : icon(glyph);
    prefix.setAttribute('name', iconNames[glyph]);
    prefix.slot = 'prefix';
    if (declared) option.querySelector('.wb-path-option-name').textContent = label;
    else {
      const copy = element('span', 'mash-stack wb-path-option-copy');
      copy.append(element('strong', 'wb-path-option-name', label)); option.append(prefix, copy);
    }
    if (path === view.path) {
      option.setAttribute('aria-current', 'page');
      const current = declared ? option.querySelector('[slot=shortcut]') : element('span', 'wb-path-option-current', 'Current');
      current.hidden = false;
      current.slot = 'shortcut';
      if (!declared) option.append(current);
    }
    return option;
  }

  function parentItem(path) {
    const open = item(path, path, 'roots', 'wb-path-menu-parent');
    if (path !== view.path) {
      const affordance = declared ? open.querySelector('[slot=shortcut]') : element('span');
      affordance.hidden = false; affordance.textContent = 'Open';
      affordance.slot = 'shortcut';
      if (!declared) open.append(affordance);
    }
    return open;
  }

  function replaceOptions(menu, ...rows) {
    menu.querySelectorAll(':scope > :not([slot=trigger])').forEach(node => node.remove());
    menu.append(...rows);
  }

  function populate(menu, parentView) {
    const children = parentView.children || [];
    const summaries = new Map((parentView.childSummaries || []).map(child => [child.path, child]));
    const rows = [];
    for (const path of children.slice(0, CHILD_LIMIT)) {
      const child = summaries.get(path);
      const glyph = { namespace: 'roots', template: 'roots', norm: 'branch',
        sewn: 'subtree', module: 'subtree', action: 'run',
        event: 'activity', journal: 'activity', http: 'activity' }[child?.kind] || 'record';
      const row = item(path, basename(path), glyph, 'wb-path-menu-child');
      // Keep the complete authored text available to accessibility and copying.
      // The menu's caption has a visual two-line bound, not a data truncation.
      const lede = child?.label && child.label !== path && child.label !== basename(path) ? child.label : '';
      const description = child?.description && child.description !== child.label ? child.description : '';
      if (lede || description) {
        if (declared) {
          const caption = row.querySelector('.wb-path-option-lede');
          caption.hidden = false; caption.textContent = [lede, description].filter(Boolean).join(' ');
        } else {
        const caption = element('small', 'wb-path-option-lede');
        if (lede) caption.append(element('span', '', lede));
        if (lede && description) caption.append(' ');
        if (description) caption.append(element('span', '', description));
        row.querySelector('.wb-path-option-copy').append(caption);
        }
      }
      rows.push(row);
    }
    if (!rows.length) {
      const empty = declaredTemplate('menu-status') || element('span', 'wb-path-menu-status'); empty.textContent = 'No child paths';
      empty.setAttribute('role', 'status');
      rows.push(empty);
    }
    const count = declaredTemplate('menu-heading') || element('ui-menu-label', 'wb-path-menu-heading');
    const total = parentView.collection?.childCount ?? children.length;
    count.textContent = total > Math.min(children.length, CHILD_LIMIT)
      ? `First ${Math.min(children.length, CHILD_LIMIT)} of ${total} paths · open path for more` : 'Paths';
    replaceOptions(menu, parentItem(parentView.path), ...(children.length ? [count] : []), ...rows);
    menu.removeAttribute('aria-busy');
  }

  async function load(menu, path) {
    const cached = cachedView(path);
    if (cached) { populate(menu, cached); return; }
    if (pending.has(menu)) return;
    const token = generation;
    const controller = new AbortController();
    pending.set(menu, controller);
    const loading = declaredTemplate('menu-status') || element('span', 'wb-path-menu-status'); loading.textContent = 'Loading child paths…';
    loading.setAttribute('role', 'status');
    replaceOptions(menu, parentItem(path), loading);
    menu.setAttribute('aria-busy', 'true');
    try {
      const answer = await navigation.readPreview(path, { signal: controller.signal, scope: 'outline' });
      if (destroyed || token !== generation || controller.signal.aborted || !menu.isConnected) return;
      rememberView(answer.view);
      populate(menu, answer.view);
    } catch (error) {
      if (destroyed || controller.signal.aborted || token !== generation || !menu.isConnected) return;
      loading.textContent = 'Could not load child paths.';
      loading.title = error.message;
      const retry = declaredTemplate('menu-retry') || element('ui-menu-item', 'wb-path-menu-retry', 'Try again');
      retry.setAttribute('value', ':retry');
      retry.setAttribute('aria-label', 'Retry children of ' + path);
      if (!declared) { const prefix = icon('live'); prefix.slot = 'prefix'; retry.prepend(prefix); }
      menu.append(retry);
    } finally {
      if (pending.get(menu) === controller) {
        pending.delete(menu);
        menu.removeAttribute('aria-busy');
      } else if (!pending.has(menu)) menu.removeAttribute('aria-busy');
    }
  }

  function makeMenu(path, authored = null) {
    const menu = authored || element('ui-menu', 'wb-path-menu');
    menu.setAttribute('label', 'Children of ' + path);
    menu.setAttribute('placement', 'bottom');
    menu.setAttribute('align', 'start');
    menu.setAttribute('offset', '4');
    menu.setAttribute('density', 'compact');
    menu.dataset.path = path;
    const trigger = authored ? menu.querySelector('[slot=trigger]') : button('Children of ' + path, 'chevron');
    trigger.setAttribute('aria-label', 'Children of ' + path);
    trigger.setAttribute('size', 'small');
    trigger.classList.add('wb-path-disclosure');
    trigger.slot = 'trigger';
    if (!authored) menu.append(trigger);
    menu.addEventListener('ui-menu-open-change', event => {
      if (event.target !== menu) return;
      if (event.detail.open) {
        closeMenus(menu);
        void load(menu, path);
      } else {
        pending.get(menu)?.abort();
        pending.delete(menu);
      }
    });
    menu.addEventListener('ui-menu-select', event => {
      if (event.target !== menu || event.detail.value !== ':retry') return;
      // The primitive dismisses after selection; reopen after that completes.
      queueMicrotask(() => { if (!destroyed && menu.isConnected) menu.show('imperative'); });
    });
    menus.add(menu);
    return menu;
  }

  function update(nextView, { refresh = false } = {}) {
    if (!nextView?.path || destroyed) return;
    const focusLocation = root.contains(document.activeElement);
    cancelReads();
    closeMenus();
    view = nextView;
    if (refresh) cache.clear();
    rememberView(view);
    menus.clear();
    root.dataset.path = view.path;
    trail.title = view.path;
    const parts = view.path.split('/').filter(Boolean);
    const paths = ['/', ...parts.map((_, index) => '/' + parts.slice(0, index + 1).join('/'))];
    const nodes = paths.map((path, index) => {
      const wrapper = declaredTemplate('path-segment') || element('li', 'wb-path-segment');
      wrapper.dataset.path = path;
      const current = index === paths.length - 1;
      const link = declared ? wrapper.querySelector('ui-link') : element('ui-link', 'wb-path-ancestor');
      link.setAttribute('variant', 'quiet');
      link.setAttribute('size', 'small');
      link.setAttribute('href', navigation.debugURL(path));
      link.title = path;
      link.setAttribute('label', path === '/' ? 'Namespace root' : 'Open ' + path);
      if (current) { link.setAttribute('current', ''); wrapper.dataset.current = 'true'; }
      if (path === '/') link.classList.add('wb-path-root');
      const glyph = path === '/' || !current ? 'roots' : {
        namespace: 'roots', template: 'roots', norm: 'branch', sewn: 'subtree',
        module: 'subtree', action: 'run', event: 'activity', journal: 'activity', http: 'activity',
      }[view.kind] || 'record';
      const prefix = declared ? link.querySelector('ui-icon') : icon(glyph);
      prefix.setAttribute('name', iconNames[glyph]);
      prefix.slot = 'prefix';
      if (declared) {
        link.querySelector('.wb-path-name').textContent = basename(path);
        makeMenu(path, wrapper.querySelector('ui-menu'));
      } else { link.append(prefix, element('span', 'wb-path-name', basename(path))); wrapper.append(link, makeMenu(path)); }
      return wrapper;
    });
    segments.replaceChildren(...nodes);
    // Current location stays visible even on a phone or a deep namespace.
    const revision = generation;
    void scroll.updateComplete.then(() => requestAnimationFrame(() => {
      if (destroyed || editorOpen || revision !== generation || !root.isConnected) return;
      scroll.scrollViewportTo({left: scroll.viewportElement.scrollWidth, behavior: 'instant'});
    }));
    close({ restoreFocus: false });
    if (focusLocation) {
      const current = segments.querySelector('ui-link[current]');
      const previousFocus = document.activeElement;
      // Lit creates the native anchor asynchronously. Preserve keyboard focus
      // only after that control exists, and never revive an obsolete trail.
      void current?.updateComplete.then(() => {
        if (!destroyed && !editorOpen && revision === generation && current.isConnected &&
            document.activeElement === previousFocus) current.focus();
      });
    }
  }

  function keydown(event) {
    if (event.defaultPrevented || event.isComposing || event.altKey) return;
    if (editorOpen && event.key === 'Escape' && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
      event.preventDefault(); event.stopPropagation(); close(); return;
    }
    const primaryL = (event.metaKey !== event.ctrlKey) && !event.shiftKey && event.key.toLowerCase() === 'l';
    const slash = !event.metaKey && !event.ctrlKey && !event.shiftKey && event.key === '/' && !isEditing(event);
    if (!primaryL && !slash) return;
    event.preventDefault(); event.stopPropagation(); void edit();
  }
  const onNavigate = event => {
    if (event.detail?.document) update(event.detail.document, { refresh: Boolean(event.detail.refresh) });
  };
  const onStart = () => { cancelReads(); closeMenus(); };
  document.addEventListener('debug:navigate', onNavigate);
  document.addEventListener('debug:navigation-start', onStart);
  document.addEventListener('keydown', keydown, true);
  update(initialView);
  return {
    element: root, edit, close, update,
    destroy() {
      destroyed = true;
      cancelReads(); closeMenus();
      cache.clear();
      document.removeEventListener('debug:navigate', onNavigate);
      document.removeEventListener('debug:navigation-start', onStart);
      document.removeEventListener('keydown', keydown, true);
    },
  };
}
