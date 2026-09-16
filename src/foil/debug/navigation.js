/* Progressive enhancements for /debug. All data and write verdicts come
 * from the existing Shrine HTTP foot; this file has no mock state. */

import {declaredTemplate} from './declarations.js';
import { parseDebugDocument } from './namespace.js';
import { createSidebar } from './sidebar.js';
import {debugReads} from './read-coordinator.js';
import { isJournalRoot, journalPage, journalPageFromURL, journalQuery, sameJournalPage, assertJournalPage } from './journal.js';
export const initialView = parseDebugDocument(document);
export let navigation;
(() => {
  'use strict';
  const get = (selector) => document.querySelector(selector);
  let busy = false;
  let activeNavigation = null;
  let finishBusyFocus = null;
  const storageKey = 'shrine-debug.v1';
  const currentPath = () => get('#debug-workspace').dataset.path;
  const validPath = (value) => typeof value === 'string' && value.startsWith('/') && value.length <= 2048 &&
    !value.split('/').some((part) => part === '.' || part === '..');
  let saved = [];
  let visits = [currentPath()];
  let page = initialView.pagination ? journalPage(initialView.pagination) : null;
  let visitPages = [page];
  const collectionQuery = search => {
    const input = new URLSearchParams(search), output = new URLSearchParams();
    for (const key of ['epoch', 'children', 'slots']) if (input.has(key)) {
      if (input.getAll(key).length !== 1 || input.get(key).length > 8192) throw new Error('Invalid collection cursor.');
      output.set(key, input.get(key));
    }
    return output.toString();
  };
  let collection = isJournalRoot(currentPath()) ? '' : collectionQuery(location.search);
  let visitCollections = [collection];
  let cursor = 0;
  let sidebar;
  let storageFailed = false;
  // Authored availability is distinct from temporary busy/preview states.
  // Weak ownership follows moved controls without retaining old documents.
  const authoredDisabled = new WeakSet();
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey + '.saved') || '[]');
    if (Array.isArray(stored)) saved = [...new Set(stored.filter(validPath))].slice(0, 50);
    const session = JSON.parse(sessionStorage.getItem(storageKey + '.navigation') || 'null');
    if (Array.isArray(session?.visits) && session.visits.length <= 100 &&
        session.visits.every(validPath) && Number.isInteger(session.cursor) &&
        session.cursor >= 0 && session.cursor < session.visits.length &&
        session.visits[session.cursor] === currentPath()) {
      const pages = session.visits.map((path, index) => isJournalRoot(path)
        ? journalPage(session.pages?.[index] || undefined) : null);
      visits = session.visits;
      cursor = session.cursor;
      visitPages = pages;
      visitCollections = visits.map((path, index) => isJournalRoot(path) ? '' : collectionQuery(session.collections?.[index] || ''));
      // The server document is authoritative after a direct link/reload.
      visitPages[cursor] = page;
      visitCollections[cursor] = collection;
    }
  } catch { storageFailed = true; }

  function persist() {
    try {
      localStorage.setItem(storageKey + '.saved', JSON.stringify(saved));
      sessionStorage.setItem(storageKey + '.navigation', JSON.stringify({ visits, pages: visitPages, collections: visitCollections, cursor }));
    } catch {
      storageFailed = true;
      report('Browser storage is unavailable. Navigation and saved paths last only until reload.', true);
    }
  }

  function controls() {
    const locked = busy && !activeNavigation;
    get('#debug-back').disabled = locked || cursor === 0;
    get('#debug-forward').disabled = locked || cursor === visits.length - 1;
    sidebar?.update({ currentPath: currentPath(), saved, visits, cursor, busy: locked });
  }
  function focusedWithinMain() {
    // document.activeElement is the owning host for focused custom controls,
    // so this also covers inputs/buttons inside their shadow roots.
    return Boolean(get('#debug-main')?.contains(document.activeElement));
  }
  function setPanelOpen(key, open) {
    const workspace = get('#debug-workspace');
    workspace[key] = open;
    if (open && matchMedia('(max-width: 832px)').matches) {
      workspace[key === 'sidebarOpen' ? 'inspectorOpen' : 'sidebarOpen'] = false;
    }
    get('#debug-sidebar-toggle').setAttribute('aria-expanded', String(workspace.sidebarOpen));
    get('#debug-inspector-toggle').setAttribute('aria-expanded', String(workspace.inspectorOpen));
  }
  async function closeSidebar() {
    const workspace = get('#debug-workspace');
    const origin = document.activeElement;
    const ownedFocus = get('#debug-sidebar').contains(origin);
    setPanelOpen('sidebarOpen', false);
    await workspace.updateComplete;
    // A selected destination is now hidden by the narrow-screen transition.
    // Continue in the rendered document, without overriding a newer focus choice.
    if (ownedFocus && !workspace.sidebarOpen &&
        (document.activeElement === origin || document.activeElement === document.body)) {
      get('.wb-document-title')?.focus({ preventScroll: true });
    }
  }
  function renderNavigation() { controls(); }
  function toggleSaved(path = currentPath()) {
    if (busy || !validPath(path)) return;
    if (saved.includes(path)) saved = saved.filter(item => item !== path);
    else if (saved.length < 50) saved.push(path);
    else return report('Saved pages are limited to 50. Remove one before saving another.', true);
    persist(); controls();
  }

  // Encode individual namespace segments, not the path separators. Never
  // treat namespace input as an origin, query, or fragment to navigate to.
  function debugURL(path, page = null) {
    const segments = path.trim().split('/').filter(Boolean);
    if (segments.some((part) => part === '.' || part === '..')) {
      throw new Error('Use a canonical namespace path, without . or .. segments.');
    }
    return '/debug' + (segments.length ? '/' + segments.map(encodeURIComponent).join('/') : '') +
      (isJournalRoot('/' + segments.join('/')) && page ? journalQuery(page) : '');
  }

  // Recent links retain the recorded page, including native modifier opens.
  function visitURL(index) {
    if (!Number.isInteger(index) || index < 0 || index >= visits.length) {
      throw new RangeError('Unknown navigation visit.');
    }
    return debugURL(visits[index], visitPages[index]) + (visitCollections[index] ? '?' + visitCollections[index] : '');
  }

  function currentURL() {
    const url = new URL(debugURL(currentPath(), page), location.href);
    if (collection) url.search = collection;
    return url.pathname + url.search;
  }

  // Feedback belongs to an operation, not an English message prefix. Quiet
  // successes can settle their own navigation failure without dismissing an
  // unrelated write warning or work that is still pending.
  function report(message, failed = false, {
    operation = 'general', phase = failed ? 'error' : 'info', context = null, quiet = !failed,
  } = {}) {
    const status = get('#debug-status');
    status.textContent = message;
    status.dataset.failed = String(failed);
    const item = declaredTemplate('activity-entry');
    item.textContent = new Date().toLocaleTimeString() + ' — ' + message;
    const activity = get('#debug-activity');
    activity.prepend(item);
    while (activity.children.length > 20) activity.lastElementChild.remove();
    document.dispatchEvent(new CustomEvent('debug:status', { detail: { message, failed, operation, phase, context, quiet } }));
  }

  function preserveBusyFocus() {
    const origin = document.activeElement;
    const chrome = origin?.matches('#debug-back, #debug-forward, #wb-refresh');
    const submit = origin?.matches('ui-button[type=submit], button[type=submit]') &&
      origin.closest('#debug-workspace');
    if (!chrome && !submit) return null;
    let userMoved = false;
    const moved = () => { userMoved = true; };
    const focused = event => { if (event.target !== origin) userMoved = true; };
    document.addEventListener('pointerdown', moved, true);
    document.addEventListener('keydown', moved, true);
    document.addEventListener('focusin', focused, true);
    return async () => {
      // Native disabled/loading buttons lose focus. Wait for the app's async
      // handler and Mash's reflected states/roving tab stops to settle first.
      await new Promise(requestAnimationFrame);
      document.removeEventListener('pointerdown', moved, true);
      document.removeEventListener('keydown', moved, true);
      document.removeEventListener('focusin', focused, true);
      if (busy || userMoved || !document.hasFocus() || !origin.isConnected) return;
      const active = document.activeElement;
      if (active && active !== document.body && active !== document.documentElement) return;
      const unavailable = control => !control || control.matches(
        ':disabled, [disabled], [loading], [hidden], [inert], [aria-disabled="true"]');
      // Reaching a history boundary can leave the original button disabled.
      // Mash selects its available peer. A rejected operation instead returns
      // to its own still-enabled control; committed views remove that node.
      const target = unavailable(origin)
        ? chrome && origin.closest('ui-toolbar')?.querySelector('ui-button[tabindex="0"]') : origin;
      if (!unavailable(target) && target.getClientRects().length) target.focus({preventScroll: true});
    };
  }

  function setBusy(value) {
    if (value && !busy) finishBusyFocus = preserveBusyFocus();
    busy = value;
    if (value) document.dispatchEvent(new CustomEvent('debug:navigation-start'));
    get('#debug-workspace').setAttribute('aria-busy', String(value));
    document.querySelectorAll('.debug-journal-pagination ui-link').forEach(link => { link.disabled = value; });
    document.querySelectorAll('#debug-workspace ui-button[type=submit], #debug-workspace button[type=submit]').forEach((button) => {
      // Case jumps are read navigation, not namespace operations. They share
      // the pending-work lock but do not require write access to this record.
      const caseNavigation = button.closest('form[data-debug-navigation="case"]');
      button.disabled = authoredDisabled.has(button) || value || (!caseNavigation &&
        get('#debug-workspace').dataset.writable !== 'true');
    });
    controls();
    if (!value) {
      const finish = finishBusyFocus;
      finishBusyFocus = null;
      void finish?.();
    }
  }

  async function read(path, { signal, page = null, scope = 'workspace', priority = 1, query = '' } = {}) {
    const url = new URL(debugURL(path, page), location.href);
    if (query) for (const [key, value] of new URLSearchParams(query)) {
      if (['epoch', 'children', 'slots'].includes(key)) url.searchParams.set(key, value);
    }
    if (!isJournalRoot(path)) url.searchParams.set('scope', scope);
    // A richer in-flight fragment can satisfy a smaller read, never the
    // reverse. Each consumer still parses its own inert Document.
    const alternatives = (scope === 'outline' ? ['preview', 'workspace'] : scope === 'preview' ? ['workspace'] : [])
      .map(value => { const candidate = new URL(url); candidate.searchParams.set('scope', value); return candidate.pathname + candidate.search; });
    const text = await debugReads.read(url.pathname + url.search, {signal, priority, alternatives});
    signal?.throwIfAborted();
    const next = new DOMParser().parseFromString(text, 'text/html');
    if (document.querySelector('[data-grove-contract="debugger/v1"]') &&
        !next.querySelector('[data-grove-contract="debugger/v1"]')) {
      throw new Error('The response is missing the published Grove debugger contract. Reload after updating the namespace.');
    }
    const workspace = next.querySelector('#debug-workspace');
    if (!workspace || !validPath(workspace.dataset.path) ||
        debugURL(workspace.dataset.path) !== debugURL(path) ||
        !workspace.querySelector('#debug-main') ||
        !workspace.querySelector('[slot=inspector]')) {
      throw new Error('The server did not return the requested debug workspace.');
    }
    const view = parseDebugDocument(next);
    assertJournalPage(view, page || undefined);
    document.dispatchEvent(new CustomEvent('debug:path-snapshot', {detail: {view}}));
    return { workspace, view, query: collectionQuery(query) };
  }

  function readPreview(path, options = {}) {
    return read(path, {scope: 'preview', priority: 0, ...options});
  }

  function show({ workspace, view, query = '' }, notify = true, refreshed = false, focusMain = false) {
    const root = get('#debug-workspace');
    for (const name of ['path', 'namespaceRoot', 'writable', 'kind', 'label', 'description', 'descriptionSource']) {
      root.dataset[name] = workspace.dataset[name] || '';
    }
    for (const name of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch', 'scope', 'readEpoch', 'nextChildren', 'nextSlots', 'slotCount']) {
      if (workspace.dataset[name] === undefined) delete root.dataset[name];
      else root.dataset[name] = workspace.dataset[name];
    }
    page = view.pagination ? journalPage(view.pagination) : null;
    collection = query;
    delete root.dataset.dirty;
    get('#debug-main').replaceWith(workspace.querySelector('#debug-main'));
    root.querySelector('[slot=inspector]').replaceWith(workspace.querySelector('[slot=inspector]'));
    root.dataset.inspectorPath = currentPath();
    get('#debug-go ui-input').value = currentPath();
    document.title = 'Shrine debug · ' + currentPath();
    prepare({ freshMain: true });
    sidebar.seed(view);
    renderNavigation();
    if (notify) document.dispatchEvent(new CustomEvent('debug:navigate', { detail: { document: view, refresh: refreshed, focusMain } }));
  }

  async function reloadCurrent(focusMain = focusedWithinMain()) {
    const answer = await read(currentPath(), { page });
    sidebar.invalidate();
    show(answer, true, true, focusMain);
    // Refresh deliberately returns collection continuations to a fresh first
    // page; never leave an old epoch/cursor in the visible address or history.
    visitCollections[cursor] = collection;
    visitPages[cursor] = page;
    persist();
    history.replaceState({shrineDebug: true, cursor}, '', currentURL());
  }
  async function refresh() {
    if (busy) return false;
    const focusMain = focusedWithinMain();
    setBusy(true);
    try { await reloadCurrent(focusMain); return true; }
    finally { setBusy(false); }
  }

  function mayLeave() {
    return get('#debug-workspace').dataset.dirty !== 'true' ||
      window.confirm('Leave this view and discard unsubmitted operation inputs?');
  }

  async function navigate(path, visit = null, fromPop = false, requestedPage = undefined, requestedCollection = undefined) {
    if ((busy && !activeNavigation) || !mayLeave()) return false;
    activeNavigation?.abort();
    const controller = new AbortController();
    activeNavigation = controller;
    const focusMain = focusedWithinMain();
    setBusy(true);
    try {
      const nextPage = isJournalRoot(path) ? journalPage(requestedPage ||
        (visit !== null ? visitPages[visit] : undefined) || undefined) : null;
      const nextCollection = isJournalRoot(path) ? '' : collectionQuery(requestedCollection ?? (visit !== null ? visitCollections[visit] : '') ?? '');
      const answer = await read(path, { page: nextPage, query: nextCollection, signal: controller.signal });
      if (activeNavigation !== controller) return false;
      show(answer, false);
      if (visit !== null && visits[visit] === currentPath() && sameJournalPage(visitPages[visit], page) && visitCollections[visit] === collection) cursor = visit;
      else if (visits[cursor] !== currentPath() || !sameJournalPage(visitPages[cursor], page) || visitCollections[cursor] !== collection) {
        visits = visits.slice(0, cursor + 1).concat(currentPath()).slice(-100);
        visitPages = visitPages.slice(0, cursor + 1).concat(page).slice(-100);
        visitCollections = visitCollections.slice(0, cursor + 1).concat(collection).slice(-100);
        cursor = visits.length - 1;
      }
      if (!fromPop) history.pushState({ shrineDebug: true, cursor }, '', currentURL());
      persist();
      renderNavigation();
      document.dispatchEvent(new CustomEvent('debug:navigate', { detail: { fromPop, document: answer.view, focusMain } }));
      report('Opened ' + currentPath() + '.', false, {operation: 'navigate', phase: 'success', context: currentPath()});
      return true;
    } catch (error) {
      if (controller.signal.aborted) return false;
      report('Navigation failed. ' + error.message, true, {operation: 'navigate', context: path});
      return false;
    } finally {
      if (activeNavigation === controller) { activeNavigation = null; setBusy(false); }
    }
  }

  async function inspect(path) {
    if (busy) return;
    document.dispatchEvent(new CustomEvent('debug:inspect-start', { detail: { path } }));
    setBusy(true);
    try {
      const { workspace, view } = await read(path);
      const panel = workspace.querySelector('[slot=inspector]');
      const reference = panel.querySelector('.wb-declared-reference');
      for (const record of workspace.querySelectorAll('#wb-canvas > section:is([aria-label=Documentation], [aria-label=Record])')) reference?.append(record);
      get('#debug-workspace [slot=inspector]').replaceWith(panel);
      get('#debug-workspace').dataset.inspectorPath = workspace.dataset.path;
      setPanelOpen('inspectorOpen', true);
      prepare();
      document.dispatchEvent(new CustomEvent('debug:inspect', { detail: { document: view } }));
      report('Inspecting ' + workspace.dataset.path + ' · workspace remains at ' + currentPath() + '.', false,
        {operation: 'inspect', phase: 'success', context: workspace.dataset.path});
    } catch (error) { report('Inspection failed. ' + error.message, true, {operation: 'inspect', context: path}); }
    finally { setBusy(false); }
  }

  function prepare({ freshMain = false } = {}) {
    // Inspector-only reads reuse the current main, whose controls are already
    // temporarily disabled. Capture availability only from a fresh document.
    if (freshMain) get('#debug-main').querySelectorAll('form ui-button[type=submit][disabled], form button[type=submit][disabled]')
      .forEach(control => authoredDisabled.add(control));
    get('#debug-workspace').dataset.inspectorPath ||= currentPath();
    // Arrow keys explore the hierarchy; Enter/Space activates navigation.
    const navigation = get('#debug-path-tree ui-tree');
    if (navigation) navigation.selectionFollowsFocus = false;
    // Keep reference and history links in the debugger.
    document.querySelectorAll('#debug-workspace a[href^="/ns"]').forEach((link) => {
      const href = link.getAttribute('href');
      if (href === '/ns' || href.startsWith('/ns/')) link.setAttribute('href', '/debug' + href.slice(3));
    });
  }

  document.addEventListener('click', (event) => {
    const target = event.composedPath().find((node) => node?.matches?.('ui-button, a'));
    if (!target || event.defaultPrevented) return;
    if (target.id === 'debug-sidebar-toggle' || target.id === 'debug-inspector-toggle') {
      const key = target.id === 'debug-sidebar-toggle' ? 'sidebarOpen' : 'inspectorOpen';
      const open = !get('#debug-workspace')[key];
      setPanelOpen(key, open);
      if (key === 'inspectorOpen') document.dispatchEvent(new CustomEvent('debug:inspector-toggle', { detail: { open } }));
      return;
    }
    if (target.id === 'debug-back' && cursor > 0) return void navigate(visits[cursor - 1], cursor - 1);
    if (target.id === 'debug-forward' && cursor < visits.length - 1) return void navigate(visits[cursor + 1], cursor + 1);
    if (target.dataset.inspect) return void inspect(target.dataset.inspect);
    if (!target.matches('a') || target.target === '_blank' || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    const url = new URL(target.href, location.href);
    if (url.origin !== location.origin || !(url.pathname === '/debug' || url.pathname.startsWith('/debug/'))) return;
    event.preventDefault();
    if (!busy || activeNavigation) {
      try {
        const path = decodeURIComponent(url.pathname.slice(6)) || '/';
        void navigate(path, target.dataset.visit === undefined ? null : Number(target.dataset.visit), false,
          isJournalRoot(path) ? journalPageFromURL(url) : undefined, collectionQuery(url.search));
      } catch (error) { report(error.message, true, {operation: 'navigate', context: url.pathname}); }
    }
  });

  window.addEventListener('popstate', async (event) => {
    try {
      const path = decodeURIComponent(location.pathname.slice(6)) || '/';
      const index = Number.isInteger(event.state?.cursor) && visits[event.state.cursor] === path ? event.state.cursor : null;
      if (await navigate(path, index, true, isJournalRoot(path) ? journalPageFromURL(new URL(location.href)) : undefined, collectionQuery(location.search))) return;
    } catch (error) { report(error.message, true, {operation: 'navigate', context: location.pathname}); }
    history.pushState({ shrineDebug: true, cursor }, '', currentURL());
  });

  document.addEventListener('input', (event) => {
    if (event.target === get('#debug-go ui-input')) {
      event.target.invalid = false;
      const group = get('#wb-path-input-group');
      if (group) group.invalid = false;
    }
    if (event.composedPath().some((node) => node?.matches?.('form[action^="/op/"], form[action="/grove/install"]'))) {
      get('#debug-workspace').dataset.dirty = 'true';
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (form.id !== 'debug-go' && !form.closest('#debug-workspace')) return;
    event.preventDefault();
    if (busy && !(activeNavigation && form.id === 'debug-go')) return;
    if (form.id === 'debug-go') {
      const path = new FormData(form).get('path') || '/';
      const input = form.querySelector('ui-input');
      const group = form.querySelector('ui-input-group');
      // Use the same route validation before any read starts. A malformed
      // address is an input error; an unavailable server is not.
      try { debugURL(path); }
      catch (error) {
        input.invalid = true;
        if (group) group.invalid = true;
        report(error.message, true, {operation: 'navigate', context: path}); input.focus();
        return;
      }
      input.invalid = false;
      if (group) group.invalid = false;
      await navigate(path);
      return;
    }
    if (get('#debug-workspace').dataset.writable !== 'true') {
      report('This view is read-only. No operation was sent.', true, {operation: 'write', context: form.getAttribute('action')});
      return;
    }
    const url = new URL(form.action, location.href);
    if (url.origin !== location.origin ||
        !(url.pathname.startsWith('/op/') || url.pathname === '/grove/install')) {
      report('Unsupported operation endpoint. No request was sent.', true, {operation: 'write', context: form.getAttribute('action')});
      return;
    }
    // Capture form-associated custom-element values before disabling buttons.
    const body = new URLSearchParams(new FormData(form));
    body.set('back', location.pathname);
    const operation = body.get('op') || url.pathname;
    const feedbackContext = {operation: 'write', context: operation};
    const focusMain = focusedWithinMain();
    setBusy(true);
    report('Running ' + operation + '…', false, {...feedbackContext, phase: 'pending', quiet: false});
    try {
      const response = await fetch(url, {
        method: 'POST', body, signal: AbortSignal.timeout(30000),
      });
      const text = await response.text();
      if (!response.ok) {
        report('Operation rejected (HTTP ' + response.status + '): ' + text.slice(0, 600), true, feedbackContext);
        return;
      }
      // The HTTP foot acknowledges a committed write with http_driver/back.
      // A timeout, proxy page, or other HTTP 200 is not a commit verdict.
      const verdict = new DOMParser().parseFromString(text, 'text/html');
      if (!verdict.body.textContent.trim().startsWith('committed;')) {
        report('Unexpected response. Commit status is unknown; refresh before retrying.', true,
          {...feedbackContext, phase: 'unknown'});
        return;
      }
      report('Committed ' + operation + '.', false, {...feedbackContext, phase: 'success', quiet: false});
      delete get('#debug-workspace').dataset.dirty;
      try { await reloadCurrent(focusMain); }
      catch (error) {
        report('Operation committed, but refresh failed. Do not resubmit; reload the page. ' + error.message, true, feedbackContext);
      }
    } catch (error) {
      report('Connection interrupted. Commit status is unknown; refresh before retrying. ' + error.message, true,
        {...feedbackContext, phase: 'unknown'});
    } finally { setBusy(false); }
  });

  // Bind the persistent Grove sidebar; Mash owns its keyboard contract.
  sidebar = createSidebar({ initialView, currentPath, navigate, inspect, toggleSaved, debugURL, visitURL, closeSidebar, report, read: readPreview });
  get('#debug-status').textContent = 'Snapshot loaded.';
  prepare({ freshMain: true });
  // Bind the persistent, declared session panel.
  const sessionPanel = get('.debug-footer');
  sessionPanel.querySelector('details').open = true;
  const clearActivity = get('#debug-clear-activity');
  clearActivity.addEventListener('click', () => get('#debug-activity').replaceChildren());

  const wide = !window.matchMedia('(max-width: 832px)').matches;
  get('#debug-workspace').sidebarOpen = wide;
  get('#debug-workspace').inspectorOpen = false;
  get('#debug-sidebar-toggle').setAttribute('aria-expanded', String(wide));
  get('#debug-inspector-toggle').setAttribute('aria-expanded', 'false');
  history.replaceState({ shrineDebug: true, cursor }, '', currentURL());
  renderNavigation();
  navigation = { initialView, navigate, inspect, read, readPreview, report, currentPath, mayLeave, refresh, debugURL,
    isAuthoredDisabled: control => authoredDisabled.has(control), get busy() { return busy; } };
  if (storageFailed) report('Browser storage is unavailable. Saved paths are temporary.', true);
})();
