import {legacyElement} from './legacy.js';
import { icon, button, iconNames } from './icons.js';
import { assertJournalPage } from './journal.js';
import {declaredTemplate} from './declarations.js';
import {BoundedCache} from './bounded-cache.js';

const el = (tag, className = '', text = '') => {
  const node = legacyElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
};
const containsPath = (root, path) => root === '/' || root === path || path.startsWith(root + '/');
const isPath = path => typeof path === 'string' && path.startsWith('/') && path.length <= 2048 &&
  !path.split('/').some(segment => segment === '.' || segment === '..');
const PAGE_SIZE = 60;
const RECENT_LIMIT = 30;
const PLACES = [
  { path: '/', label: 'Namespace', glyph: 'branch' },
  { path: '/app', label: 'Applications', glyph: 'record' },
  { path: '/gov', label: 'Groves', glyph: 'subtree' },
  { path: '/weft', label: 'Components', glyph: 'roots' },
  { path: '/log', label: 'Activity', glyph: 'activity' },
  { path: '/sys', label: 'System', glyph: 'settings' },
];
const kindGlyph = kind => {
  if (kind === 'record') return 'record';
  if (/(?:journal|event|request)/.test(kind)) return 'activity';
  if (/(?:action|operation|behavior|handler)/.test(kind)) return 'run';
  if (/(?:norm|role|type|definition|grove|module|template)/.test(kind)) return 'subtree';
  if (/(?:face|component|render)/.test(kind)) return 'roots';
  return null;
};
const normalizedLabel = value => String(value || '').trim().replace(/^\/+|[.:]+$/g, '').toLocaleLowerCase();
const genericDescriptions = new Set([
  'Own record slots and namespace relationships.',
  'A structural namespace path. Child records may exist without a record here.',
]);
function orderedChildren(view) {
  const paths = [...new Set((view.children || []).filter(isPath))];
  if (view.path === '/log') paths.sort((a, b) => {
    const left = a.slice(5), right = b.slice(5);
    if (/^\d+$/.test(left) && /^\d+$/.test(right)) return BigInt(left) > BigInt(right) ? -1 : BigInt(left) < BigInt(right) ? 1 : 0;
    return /^\d+$/.test(left) ? -1 : /^\d+$/.test(right) ? 1 : left.localeCompare(right);
  });
  return paths;
}

/** Application data/loading composed into Mash's accessible tree/disclosures. */
export function createSidebar({ initialView, currentPath, navigate, toggleSaved, debugURL, visitURL, closeSidebar, report, read }) {
  const host = document.querySelector('#debug-sidebar');
  const input = document.querySelector('#debug-filter');
  const declared = !__DEBUG_LEGACY__ || Boolean(host.closest('[data-grove-contract="debugger/v1"]'));
  function control(id, label, glyph, action) {
    const result = declared ? host.querySelector('#' + id) : button(label, glyph);
    if (!result) throw new Error('Missing declared debugger control: ' + id);
    result.id = id;
    if (action) result.addEventListener('click', action);
    return result;
  }
  function instantiate(name) {
    const template = document.querySelector('#debug-template-' + name);
    if (!template?.content?.firstElementChild) throw new Error('Missing Grove row declaration: ' + name);
    return template.content.firstElementChild.cloneNode(true);
  }
  const preferencesKey = 'shrine-debug.sidebar.v2';
  const cache = new BoundedCache(128, 30000, [[initialView.path, initialView]]);
  const summaries = new BoundedCache(2048, 60000);
  const pending = new Map();
  const controllers = new Map();
  const expanded = new Set(['/']);
  const amounts = new BoundedCache(128);
  const sections = new Map();
  let rootPath = '/';
  let state = { currentPath: currentPath(), saved: [], visits: [], cursor: 0, busy: false };
  let preferences = { saved: true, recent: false, tree: true };
  let generation = 0;
  let invalidated = false;
  let statusId = 0;
  try {
    const stored = JSON.parse(localStorage.getItem(preferencesKey) || 'null');
    for (const name of ['saved', 'recent', 'tree']) if (typeof stored?.[name] === 'boolean') preferences[name] = stored[name];
    if (isPath(stored?.root)) rootPath = stored.root;
    if (Array.isArray(stored?.expanded)) stored.expanded.filter(isPath).slice(0, 500).forEach(path => expanded.add(path));
  } catch { /* Storage failure does not prevent browsing. */ }
  function persist() {
    try { localStorage.setItem(preferencesKey, JSON.stringify({ ...preferences, root: rootPath, expanded: [...expanded].slice(-500) })); }
    catch { /* Page saving reports storage availability through navigation. */ }
  }
  function pathLabel(path, title) {
    if (declared) {
      const label = instantiate('path-label');
      label.setAttribute('path', path);
      const text = label.querySelector('ui-label'); text.textContent = title; text.text = title;
      return label;
    }
    const label = el('ui-path');
    label.setAttribute('size', 'small'); label.setAttribute('path', path);
    const text = searchLabel(title); text.slot = 'title'; label.append(text);
    return label;
  }
  function searchLabel(text, className = '') {
    const label = el('ui-label', 'debug-search-label ' + className, text);
    label.text = text;
    label.highlightMatch = 'full';
    return label;
  }
  function highlightLabel(label, query) {
    // Preserve exact labels, including whitespace. The current shared matcher
    // indexes UTF-16 text, so skip only ambiguous length-changing case folds.
    const text = label.textContent;
    label.text = text;
    label.highlight = text.toLocaleLowerCase().length === text.length &&
      query.toLocaleLowerCase().length === query.length ? query : '';
  }
  function section(name, title, glyph, contentId) {
    const section = declared ? host.querySelector('#debug-section-' + name) : el('ui-accordion-item', 'debug-sidebar-section');
    section.id = 'debug-section-' + name; section.value = name; section.title = title; section.open = preferences[name];
    section.setAttribute('heading-level', '2');
    const content = declared ? section.querySelector('#' + contentId) : el('div', 'debug-section-body');
    if (!declared) {
    const label = el('span', '', title); label.slot = 'title';
    const prefix = icon(glyph); prefix.slot = 'prefix';
    const disclosure = icon('chevron'); disclosure.slot = 'disclosure';
    // These stock glyphs belong to the shared accordion's icon lanes, not
    // the debugger's legacy icon-size recipe.
    prefix.classList.remove('wb-icon'); disclosure.classList.remove('wb-icon');
    const count = el('span', 'debug-section-count'); count.slot = 'suffix'; count.dataset.count = name;
    content.id = contentId;
    section.append(prefix, label, count, disclosure, content);
    }
    section.addEventListener('ui-accordion-item-change', event => {
      if (event.target !== section) return;
      preferences[name] = event.detail.open; persist();
      if (name === 'tree' && event.detail.open) queueMicrotask(refreshExpanded);
    });
    sections.set(name, section);
    return { section, content };
  }

  const composer = declared ? host.querySelector('#debug-filter-composer') : el('ui-input-group'); composer.id = 'debug-filter-composer'; composer.slot = 'search';
  composer.setAttribute('size', 'small'); composer.setAttribute('touch-target', '');
  const places = declared ? host.querySelector('#debug-root-menu') : el('ui-menu'); places.id = 'debug-root-menu';
  places.slot = 'prefix';
  places.setAttribute('label', 'Namespace places'); places.setAttribute('density', 'compact');
  places.setAttribute('placement', 'bottom'); places.setAttribute('align', 'start');
  const search = control('debug-root-toggle', 'Choose namespace place', 'search'); search.slot = 'trigger';
  search.setAttribute('size', 'small');
  if (!declared) places.append(search);
  for (const place of PLACES) {
    const choice = declared ? [...places.querySelectorAll('ui-menu-item')].find(item => item.getAttribute('value') === place.path) : el('ui-menu-item', 'debug-root-link', place.label);
    choice.value = place.path;
    choice.href = debugURL(place.path);
    if (!declared) {
    const glyph = icon(place.glyph); glyph.slot = 'prefix';
    const path = el('code', '', place.path); path.slot = 'shortcut';
    choice.append(glyph, path); places.append(choice);
    }
    // Keep native link gestures intact. Selection events do not carry the
    // original pointer modifiers and cannot decide whether to route this tab.
    choice.addEventListener('click', async event => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      if (state.busy) return;
      if (await navigate(place.path)) {
        input.value = ''; filter();
        // Places navigate the real tree, not a second hard-coded hierarchy.
        sections.get('tree').open = true; preferences.tree = true; persist();
        queueMicrotask(refreshExpanded);
        if (matchMedia('(max-width: 832px)').matches) closeSidebar();
      }
    });
  }
  input.slot = 'control'; input.setAttribute('label', 'Filter loaded paths');
  input.setAttribute('size', 'inherit');
  input.setAttribute('autocomplete', 'off'); input.placeholder = 'Filter paths…';
  const clear = control('debug-filter-clear', 'Clear path filter', 'close', () => { input.value = ''; filter(); input.focus(); });
  clear.setAttribute('size', 'small');
  clear.id = 'debug-filter-clear'; clear.slot = 'suffix';
  if (!declared) composer.append(places, input, clear);
  const container = declared ? host.querySelector('#debug-sidebar-sections') : el('ui-accordion'); container.id = 'debug-sidebar-sections';
  // Set the policy before mounting remembered open items; default single mode
  // must not collapse another section during its initial slot synchronization.
  container.setAttribute('mode', 'multiple'); container.setAttribute('size', 'compact');
  container.setAttribute('variant', 'quiet');
  const savedSection = section('saved', 'Saved', 'record', 'debug-saved');
  const recentSection = section('recent', 'Recent', 'clock', 'debug-history');
  const treeSection = section('tree', 'Tree', 'branch', 'debug-children');
  if (!declared) {
    container.append(savedSection.section, recentSection.section, treeSection.section);
    host.replaceChildren(composer, container);
  }

  const toolbar = declared ? host.querySelector('#debug-tree-toolbar') : el('div'); toolbar.id = 'debug-tree-toolbar';
  const actions = declared ? host.querySelector('#debug-tree-actions') : el('ui-toolbar'); actions.id = 'debug-tree-actions';
  actions.setAttribute('label', 'Namespace tree actions');
  actions.setAttribute('data-mash-size', 'small');
  const rootLabel = declared ? host.querySelector('#debug-tree-root') : pathLabel(rootPath, rootPath === '/' ? 'Namespace' : rootPath); rootLabel.id = 'debug-tree-root';
  const reset = control('debug-tree-namespace', 'Browse entire namespace', 'back', () => setRoot('/'));
  reset.id = 'debug-tree-namespace';
  const collapse = control('debug-tree-collapse', 'Collapse all branches', 'branch', () => {
    expanded.clear(); expanded.add(rootPath);
    tree.querySelectorAll('ui-tree-item').forEach(item => {
      item.expanded = item.dataset.path === rootPath;
    });
    persist();
  });
  collapse.id = 'debug-tree-collapse';
  const refresh = control('debug-tree-refresh', 'Refresh tree root', 'live', () => {
    cache.delete(rootPath);
    const item = tree.querySelector('ui-tree-item');
    if (item) { expanded.add(rootPath); item.expanded = true; void load(item, true); }
  });
  refresh.id = 'debug-tree-refresh';
  const save = control('debug-save', 'Save current page', 'bookmark', () => toggleSaved());
  for (const control of [reset, collapse, refresh, save]) control.setAttribute('size', 'small');
  if (!declared) { actions.append(collapse, refresh, save); toolbar.append(reset, rootLabel, actions); }
  const graph = declared ? host.querySelector('#debug-path-tree') : el('sh-tree'); graph.id = 'debug-path-tree'; graph.setAttribute('variant', 'namespace');
  const tree = declared ? graph.querySelector('ui-tree') : el('ui-tree'); tree.slot = 'tree'; tree.setAttribute('label', 'Namespace hierarchy');
  tree.selectionFollowsFocus = false;
  if (!declared) graph.append(tree);
  const empty = declared ? host.querySelector('#debug-filter-empty') : el('p', 'debug-sidebar-empty', 'No matching loaded paths.'); empty.id = 'debug-filter-empty'; empty.hidden = true;
  if (!declared) treeSection.content.append(toolbar, graph, empty);

  function updateCounts() {
    const phrase = (number, noun) => number + ' ' + noun + (number === 1 ? '' : 's');
    const setCount = (name, number, text, description) => {
      const count = sections.get(name).querySelector('.debug-section-count');
      count.dataset.countValue = String(number ?? '');
      count.textContent = text; count.title = description;
    };
    setCount('saved', state.saved.length, phrase(state.saved.length, 'page'), 'Saved namespace pages');
    const unique = new Set(state.visits).size, shown = Math.min(RECENT_LIMIT, unique);
    setCount('recent', shown, shown < unique ? shown + ' of ' + unique + ' paths' : phrase(shown, 'path'),
      'The ' + shown + ' latest distinct paths from ' + unique + ' retained paths');
    const view = cache.get(rootPath);
    const children = view?.children.length;
    if (view?.pagination) {
      setCount('tree', children, children + ' loaded ' + (children === 1 ? 'entry' : 'entries'),
        'Loaded entry paths; the latest page reports ' + view.pagination.total + ' total. Loaded pages may span snapshots.');
    } else {
      setCount('tree', children, view ? phrase(children, 'name') : '', 'Direct child names in the root snapshot');
    }
  }
  function syncSelection() {
    tree.selectedValues = [state.currentPath];
    tree.querySelectorAll('ui-tree-item').forEach(item => {
      item.current = item.dataset.path === state.currentPath;
      item.selected = item.current;
      syncBookmark(item);
    });
    updateCounts();
  }
  function syncBookmark(item) {
    const bookmark = item.querySelector(':scope > .debug-bookmark-toggle');
    if (!bookmark) return;
    const saved = state.saved.includes(item.dataset.path);
    const label = (saved ? 'Unsave ' : 'Save ') + item.dataset.path;
    bookmark.disabled = state.busy;
    bookmark.selected = saved;
    bookmark.setAttribute('aria-pressed', String(saved));
    bookmark.setAttribute('aria-label', label);
    bookmark.title = '';
  }
  function makeItem(path) {
    const item = declared ? instantiate('namespace-row') : el('ui-tree-item', 'debug-namespace-node');
    item.dataset.path = path; item.value = path; item.path = path; item.kind = 'folder'; item.size = 'small';
    item.setAttribute('activation', 'split');
    item.setAttribute('actions-display', 'overlay');
    item.previewOpen = false;
    item.title = path === rootPath ? (path === '/' ? 'Namespace' : path.split('/').at(-1)) : path.split('/').at(-1);
    item.expanded = expanded.has(path);
    item.dataset.readState = cache.has(path) ? 'ready' : 'idle';
    const label = declared ? item.querySelector(':scope > [slot=label]') : pathLabel(path, item.title); label.slot = 'label';
    if (declared) {
      label.path = path;
      const text = label.querySelector('ui-label'); text.textContent = item.title; text.text = item.title;
    }
    const summary = cache.get(path) || summaries.get(path);
    const glyph = kindGlyph(summary?.kind || '') || (summary?.record ? 'record' : 'branch');
    const mark = declared ? item.querySelector(':scope > [slot=icon]') : icon(glyph); mark.slot = 'icon';
    mark.setAttribute('name', iconNames[glyph]);
    const disclosure = declared ? item.querySelector(':scope > [slot=disclosure]') : icon('chevron'); disclosure.slot = 'disclosure';
    // The namespace recipe owns adornment geometry, including RTL rotation.
    mark.classList.remove('wb-icon'); disclosure.classList.remove('wb-icon');
    const bookmark = declared ? item.querySelector('.debug-bookmark-toggle') : button('Save ' + path, 'bookmark');
    bookmark.addEventListener('click', event => {
      event.stopPropagation();
      toggleSaved(path);
    });
    bookmark.setAttribute('size', 'small');
    bookmark.querySelector('ui-icon')?.classList.remove('wb-icon');
    bookmark.slot = 'actions'; bookmark.classList.add('debug-bookmark-toggle');
    item.dataset.statusId = 'debug-node-status-' + (++statusId);
    if (!declared) item.append(disclosure, mark, label, bookmark);
    if (summary?.kind) item.dataset.kind = summary.kind;
    if (summary?.description) item.setAttribute('aria-description', summary.description);
    updateSummary(item, summary);
    syncBookmark(item);
    if (cache.has(path)) fill(item, cache.get(path));
    else if (item.expanded) queueMicrotask(() => {
      if (item.isConnected && sections.get('tree').open) void load(item);
    });
    return item;
  }
  function updateSummary(item, view) {
    let lede = item.querySelector(':scope > .debug-node-lede-path .debug-node-lede');
    const title = String(view?.label || '').trim();
    if (title && ![item.dataset.path, item.title].some(label => normalizedLabel(label) === normalizedLabel(title))) {
      if (!lede) {
        const path = pathLabel(item.dataset.path, title);
        path.slot = 'meta'; path.classList.add('debug-node-lede-path');
        lede = path.querySelector('ui-label'); lede.classList.add('debug-node-lede');
        item.append(path);
      }
      lede.textContent = title; lede.text = title;
    } else lede?.closest('ui-path')?.remove();
    const description = String(view?.description || '').trim();
    if (description && !genericDescriptions.has(description)) item.setAttribute('aria-description', description);
    else item.removeAttribute('aria-description');
  }
  function fill(item, view) {
    item.dataset.readState = 'ready'; item.removeAttribute('aria-busy');
    item.dataset.kind = view.kind || '';
    updateSummary(item, view);
    const glyph = kindGlyph(view.kind || '') || (view.record ? 'record' : 'branch');
    if (declared) item.querySelector(':scope > [slot=icon]').setAttribute('name', iconNames[glyph]);
    else {
      const mark = icon(glyph); mark.slot = 'icon'; mark.classList.remove('wb-icon');
      item.querySelector(':scope > [slot=icon]')?.replaceWith(mark);
    }
    item.querySelector(':scope > [slot=preview]')?.remove();
    item.previewOpen = false;
    item.querySelector(':scope > .debug-load-more')?.remove();
    item.querySelector(':scope > .debug-load-older')?.remove();
    item.querySelector(':scope > .debug-page-error')?.remove();
    const existing = new Map([...item.children].filter(child => child.localName === 'ui-tree-item').map(child => [child.dataset.path, child]));
    for (const summary of view.childSummaries || []) if (isPath(summary.path)) summaries.set(summary.path, summary);
    const children = orderedChildren(view);
    item.kind = children.length || view.pagination?.nextBefore || view.collection?.nextChildren ? 'folder' : 'file';
    const amount = view.pagination ? children.length : amounts.get(view.path) || PAGE_SIZE;
    const visiblePaths = children.filter((path, index) => index < amount || containsPath(path, state.currentPath));
    // A permalink can open an older event outside the loaded page. Include
    // that already-read record, not every intervening page or a fabricated row.
    const selectedKey = state.currentPath.match(/^\/log\/(0|[1-9][0-9]*)(?:\/|$)/)?.[1];
    const selectedEvent = selectedKey === undefined ? null : '/log/' + selectedKey;
    if (view.pagination && selectedEvent && cache.has(selectedEvent) && !visiblePaths.includes(selectedEvent)) {
      visiblePaths.push(selectedEvent);
      visiblePaths.sort((a, b) => BigInt(a.slice(5)) > BigInt(b.slice(5)) ? -1 : 1);
    }
    for (const child of existing.values()) if (!visiblePaths.includes(child.dataset.path)) child.remove();
    for (const [index, path] of visiblePaths.entries()) {
      const child = existing.get(path) || makeItem(path); child.slot = 'children';
      child.toggleAttribute('data-outside-page', !children.includes(path));
      const position = [...item.children].filter(node => node.localName === 'ui-tree-item')[index];
      if (position !== child) item.insertBefore(child, position || null);
    }
    if (children.length > visiblePaths.length) {
      const more = button('Show more children of ' + view.path, 'more', () => {
        amounts.set(view.path, amount + PAGE_SIZE); fill(item, view); filter(); syncSelection();
      }, 'Show ' + Math.min(PAGE_SIZE, children.length - visiblePaths.length) + ' more');
      more.classList.add('debug-load-more'); more.slot = 'children'; item.append(more);
    }
    if (view.pagination?.nextBefore !== null && view.pagination?.nextBefore !== undefined) {
      const more = button('Load older journal entries', 'more', () => void loadOlder(item, view, more), 'Load older');
      more.classList.add('debug-load-older'); more.slot = 'children'; item.append(more);
    }
    if (view.collection?.nextChildren) {
      const more = button('Load next paths', 'more', () => void loadChildrenPage(item, view, more), 'Load more');
      more.classList.add('debug-load-older'); more.slot = 'children'; item.append(more);
    }
    syncSelection(); filter();
  }
  async function loadOlder(item, view, control) {
    if (control.loading) return;
    const readGeneration = generation;
    const hadFocus = document.activeElement === control;
    let userMoved = false;
    const moved = () => { userMoved = true; };
    const focused = event => { if (event.target !== control) userMoved = true; };
    document.addEventListener('pointerdown', moved, true);
    document.addEventListener('keydown', moved, true);
    document.addEventListener('focusin', focused, true);
    item.querySelector(':scope > .debug-page-error')?.remove();
    control.loading = true;
    try {
      const next = await fetchNode(view.path, { before: view.pagination.nextBefore, limit: view.pagination.limit });
      if (!item.isConnected || generation !== readGeneration || cache.get(view.path) !== view) return;
      if (!next.pagination) throw new Error('This runtime does not support journal pages.');
      const merged = {
        ...view,
        children: [...new Set([...view.children, ...next.children])],
        childSummaries: [...new Map([...view.childSummaries, ...next.childSummaries].map(summary => [summary.path, summary])).values()],
        pagination: { ...next.pagination, before: view.pagination.before },
      };
      cache.set(view.path, merged);
      fill(item, merged);
    } catch (error) {
      if (!item.isConnected || generation !== readGeneration || cache.get(view.path) !== view) return;
      const status = declaredTemplate('page-error') || el('span', 'debug-page-error'); status.textContent = error.message;
      status.slot = 'children'; status.setAttribute('role', 'status'); item.append(status);
      (control.querySelector('span') || control).textContent = 'Retry older';
    } finally {
      control.loading = false;
      await new Promise(requestAnimationFrame);
      document.removeEventListener('pointerdown', moved, true);
      document.removeEventListener('keydown', moved, true);
      document.removeEventListener('focusin', focused, true);
      if (hadFocus && !userMoved && item.isConnected && generation === readGeneration && document.hasFocus() &&
          [document.body, document.documentElement, control].includes(document.activeElement)) {
        const next = item.querySelector(':scope > .debug-load-older');
        if (next) next.focus(); else item.focusControl();
      }
    }
  }
  async function loadChildrenPage(item, view, control) {
    if (control.loading) return;
    control.loading = true;
    try {
      const query = new URLSearchParams({epoch: view.collection.epoch, children: view.collection.nextChildren}).toString();
      const next = await fetchNode(view.path, null, query);
      if (!item.isConnected || !item.expanded || cache.get(view.path) !== view) return;
      const merged = {...next, children: [...new Set([...view.children, ...next.children])],
        childSummaries: [...new Map([...view.childSummaries, ...next.childSummaries].map(child => [child.path, child])).values()]};
      amounts.set(view.path, merged.children.length);
      cache.set(view.path, merged); fill(item, merged);
    } catch (error) {
      if (error.name !== 'AbortError') report('Could not load the next paths. Refresh if the namespace changed. ' + error.message, true);
    } finally { control.loading = false; }
  }
  async function fetchNode(path, page = null, query = '') {
    const url = debugURL(path, page) + '#' + query;
    if (pending.has(url)) return pending.get(url);
    const readGeneration = generation;
    const controller = new AbortController(); controllers.set(controller, path);
    const promise = (async () => {
      controller.signal.throwIfAborted();
      const {view} = await read(path, {signal: controller.signal, page, query, scope: 'outline'});
      controller.signal.throwIfAborted();
      if (view.path !== path) throw new Error('The runtime returned a different namespace path.');
      assertJournalPage(view, page || undefined);
      if (generation === readGeneration && !page && !query) {
        cache.set(path, view);
        document.dispatchEvent(new CustomEvent('debug:path-snapshot', {detail: {view}}));
      }
      return view;
    })().finally(() => {
      controllers.delete(controller);
      if (pending.get(url) === promise) pending.delete(url);
    });
    pending.set(url, promise); return promise;
  }
  async function load(item, force = false) {
    const readGeneration = generation;
    const path = item.dataset.path;
    if (!force && cache.has(path)) { fill(item, cache.get(path)); return; }
    item.dataset.readState = 'loading'; item.setAttribute('aria-busy', 'true');
    item.querySelector(':scope > [slot=preview]')?.remove();
    const status = declaredTemplate('node-status') || el('div', 'debug-node-preview debug-node-status', 'Loading…'); status.slot = 'preview'; status.id = item.dataset.statusId;
    status.setAttribute('role', 'status');
    if (!item.querySelector(':scope > ui-tree-item')) item.append(status);
    item.previewOpen = true;
    try {
      const view = await fetchNode(path);
      if (item.isConnected && generation === readGeneration) fill(item, view);
    } catch (error) {
      if (!item.isConnected || generation !== readGeneration) return;
      if (error.name === 'AbortError') {
        item.dataset.readState = 'idle'; item.removeAttribute('aria-busy'); status.remove(); item.previewOpen = false; return;
      }
      item.dataset.readState = 'error'; item.removeAttribute('aria-busy');
      if (!status.isConnected) item.append(status);
      const message = declared ? status.querySelector('[data-status-message]') : el('span');
      message.textContent = error.name === 'TimeoutError' ? 'Read timed out.' : error.message;
      message.title = error.message;
      if (declared) {
        const retry = status.querySelector('ui-button'); retry.hidden = false;
        retry.setAttribute('aria-label', 'Retry ' + path); retry.addEventListener('click', () => void load(item, true));
      } else status.replaceChildren(message, button('Retry ' + path, 'live', () => void load(item, true), 'Retry'));
    }
  }
  function refreshExpanded() {
    if (!sections.get('tree').open) return;
    for (const item of tree.querySelectorAll('ui-tree-item')) {
      if (!item.expanded || cache.has(item.dataset.path) || item.dataset.readState === 'loading') continue;
      let ancestor = item.parentElement;
      while (ancestor !== tree && ancestor?.localName === 'ui-tree-item' && ancestor.expanded) ancestor = ancestor.parentElement;
      if (ancestor === tree) void load(item);
    }
  }
  function expandCurrentAncestors() {
    if (!containsPath(rootPath, state.currentPath)) rootPath = '/';
    // Reveal the selected row, not all its data and descendants.
    let path = state.currentPath === rootPath ? rootPath : state.currentPath.slice(0, state.currentPath.lastIndexOf('/')) || '/';
    while (containsPath(rootPath, path)) {
      expanded.add(path);
      if (path === rootPath) break;
      path = path.slice(0, path.lastIndexOf('/')) || '/';
    }
  }
  function revealCurrent() {
    expandCurrentAncestors();
    tree.querySelectorAll('ui-tree-item').forEach(item => {
      if (expanded.has(item.dataset.path)) {
        item.expanded = true;
        const view = cache.get(item.dataset.path);
        if (view && ((view.pagination && /^\/log\//.test(state.currentPath)) || view.children.some(path => containsPath(path, state.currentPath) &&
          ![...item.children].some(child => child.localName === 'ui-tree-item' && child.dataset.path === path)))) {
          // Keep a directly navigated older event visible without expanding
          // every intervening journal page or replacing the existing tree.
          fill(item, view);
        } else if (item.dataset.readState === 'idle' && sections.get('tree').open) void load(item);
      }
    });
  }
  function renderTree() {
    // Update expansion preferences without reading the outgoing tree that is
    // about to be replaced. New visible items schedule their own missing data.
    expandCurrentAncestors();
    rootLabel.setAttribute('path', rootPath);
    rootLabel.querySelector('[slot=title]').textContent = rootPath === '/' ? 'Namespace' : rootPath;
    reset.hidden = rootPath === '/';
    tree.replaceChildren(makeItem(rootPath));
    syncSelection(); filter();
  }
  function setRoot(path) {
    rootPath = path;
    expanded.add(path); sections.get('tree').open = true; preferences.tree = true;
    renderTree(); renderPages(); persist();
  }
  function pageRow(path, savedPage) {
    const row = declared ? instantiate('page-row') : el('div', 'debug-page-row'); row.dataset.path = path;
    const link = declared ? row.querySelector('ui-link') : el('ui-link', 'debug-page-link'); link.href = debugURL(path);
    link.setAttribute('variant', 'quiet'); link.setAttribute('size', 'small');
    link.label = path;
    const title = path === '/' ? 'Namespace' : path.split('/').at(-1);
    if (declared) {
      const label = link.querySelector('ui-label'); label.textContent = title; label.text = title;
    } else {
      const glyph = icon('record'); glyph.slot = 'prefix'; link.append(glyph, searchLabel(title));
    }
    link.title = path;
    link.addEventListener('click', async event => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault(); event.stopPropagation();
      // A reused Recent row follows the latest occurrence of its path. Its
      // visit identity belongs to application history, not the link primitive.
      const recentIndex = savedPage ? null : Number(row.dataset.visit);
      if (await navigate(path, recentIndex)) {
        if (savedPage) setRoot(path);
        if (matchMedia('(max-width: 832px)').matches) closeSidebar();
      }
    });
    if (!declared) row.append(link);
    if (savedPage) {
      const remove = declared ? row.querySelector('ui-button') : button('Unsave ' + path, 'close');
      remove.setAttribute('aria-label', 'Unsave ' + path);
      remove.addEventListener('click', () => toggleSaved(path));
      remove.setAttribute('size', 'small');
      if (!declared) row.append(remove);
    } else if (declared) row.querySelector('ui-button').remove();
    return row;
  }
  function syncPages(content, entries, savedPage) {
    const rows = new Map([...content.querySelectorAll(':scope > .debug-page-row')].map(row => [row.dataset.path, row]));
    const focused = document.activeElement;
    const hadFocus = content.contains(focused);
    const focusedRow = focused?.closest('.debug-page-row');
    const focusedIndex = focusedRow ? [...rows.values()].indexOf(focusedRow) : 0;
    const query = (input.value || '').trim().toLocaleLowerCase();
    const desired = entries.map(([path, visit]) => {
      const row = rows.get(path) || pageRow(path, savedPage);
      row.hidden = !path.toLocaleLowerCase().includes(query);
      if (!savedPage) {
        row.dataset.visit = String(visit);
        row.querySelector('ui-link').href = visitURL(visit);
      }
      row.querySelector('ui-link').current = path === (savedPage ? rootPath : state.currentPath);
      return row;
    });
    if (savedPage && !desired.length) desired.push(content.querySelector(':scope > .wb-button') ||
      button('Save current page', 'bookmark', () => toggleSaved(), 'Save current page'));
    // Keep existing hosts, native anchors and scroll position. Ordinary
    // selection changes do not replace either list or drop keyboard focus.
    const retained = new Set(desired);
    for (const child of [...content.children]) if (!retained.has(child)) child.remove();
    desired.forEach((row, index) => {
      if (content.children[index] !== row) content.insertBefore(row, content.children[index] || null);
    });
    if (hadFocus && document.activeElement === document.body) {
      // Restore immediately where possible; never steal later user focus.
      // After Unsave, land on a destination, not another destructive action.
      const available = desired.filter(row => !row.hidden);
      const next = desired.slice(focusedIndex).find(row => !row.hidden) || available.at(-1);
      const target = focused.isConnected ? focused : next?.querySelector('ui-link') || next || input;
      target?.focus({ preventScroll: true });
      // The final Unsave creates a fresh empty-state button. Let its native
      // control mount, but do not override focus chosen in the meantime.
      if (target?.updateComplete) void target.updateComplete.then(() => {
        if (target.isConnected && document.activeElement === document.body) target.focus({ preventScroll: true });
      });
    }
  }
  function renderPages() {
    syncPages(savedSection.content, state.saved.map(path => [path, null]), true);
    const recent = new Map();
    state.visits.forEach((path, index) => { recent.delete(path); recent.set(path, index); });
    syncPages(recentSection.content, [...recent].reverse().slice(0, RECENT_LIMIT), false);
    updateCounts(); filter();
  }
  function filter() {
    const authoredQuery = (input.value || '').trim();
    const query = authoredQuery.toLocaleLowerCase();
    clear.hidden = !query;
    host.querySelectorAll('ui-label.debug-search-label').forEach(label => highlightLabel(label, authoredQuery));
    let count = 0;
    const items = [...tree.querySelectorAll('ui-tree-item')];
    for (const item of items.reverse()) {
      const summary = cache.get(item.dataset.path) || summaries.get(item.dataset.path);
      const searchable = [item.dataset.path, summary?.kind, summary?.label, summary?.description].filter(Boolean).join(' ');
      const match = searchable.toLocaleLowerCase().includes(query);
      const descendant = [...item.children].some(child => child.localName === 'ui-tree-item' && !child.hidden);
      item.hidden = Boolean(query) && !match && !descendant;
      if (!item.hidden) count++;
      item.expanded = query ? descendant || expanded.has(item.dataset.path) : expanded.has(item.dataset.path);
    }
    host.querySelectorAll('.debug-page-row').forEach(row => { row.hidden = !row.dataset.path.toLocaleLowerCase().includes(query); });
    empty.hidden = !query || count > 0;
  }
  input.addEventListener('input', filter);
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); input.value = ''; filter(); } });
  tree.addEventListener('ui-tree-toggle', event => {
    if (event.target !== tree) return;
    const path = event.detail.value;
    const item = [...tree.querySelectorAll('ui-tree-item')].find(item => item.dataset.path === path);
    if (!item) return;
    item.expanded = event.detail.expanded;
    if (item.expanded) { expanded.add(path); void load(item); }
    else {
      expanded.delete(path);
      for (const [controller, target] of controllers) if (containsPath(path, target)) controller.abort();
    }
    persist();
  });
  tree.addEventListener('ui-tree-select', event => {
    if (event.target !== tree || !isPath(event.detail.value) || state.busy) return;
    if (event.detail.value !== currentPath()) void navigate(event.detail.value);
  });

  document.addEventListener('debug:navigation-start', () => {
    for (const controller of controllers.keys()) controller.abort();
    pending.clear();
  });
  renderTree();
  return {
    /** Explicit refresh/write boundary; preserve tree DOM and user state. */
    invalidate() {
      generation++; invalidated = true;
      for (const controller of controllers.keys()) controller.abort();
      pending.clear(); cache.clear(); summaries.clear(); amounts.clear();
      for (const item of tree.querySelectorAll('ui-tree-item')) {
        item.dataset.readState = 'idle'; item.removeAttribute('aria-busy');
      }
    },
    seed(view) {
      cache.set(view.path, view);
      for (const item of tree.querySelectorAll('ui-tree-item')) if (item.dataset.path === view.path) fill(item, view);
      if (invalidated) {
        invalidated = false;
        // One explicit refresh pass, never a timer or background poll.
        queueMicrotask(refreshExpanded);
      }
    },
    update(next) {
      const changedPath = next.currentPath !== state.currentPath;
      const changedPages = JSON.stringify(next.saved) !== JSON.stringify(state.saved) || next.visits !== state.visits || next.cursor !== state.cursor;
      state = { ...next, saved: [...next.saved] };
      places.disabled = state.busy;
      save.disabled = state.busy;
      save.setAttribute('aria-pressed', String(state.saved.includes(state.currentPath)));
      save.setAttribute('aria-label', state.saved.includes(state.currentPath) ? 'Unsave current page' : 'Save current page');
      save.title = '';
      if (rootPath !== '/' && (!state.saved.includes(rootPath) || !containsPath(rootPath, state.currentPath))) {
        rootPath = '/'; renderTree(); persist();
      } else if (changedPath) revealCurrent();
      if (changedPages || changedPath) renderPages();
      syncSelection();
    },
  };
}
