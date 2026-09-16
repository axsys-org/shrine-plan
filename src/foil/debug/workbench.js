import { navigation, initialView } from './navigation.js';
import { createPathLocator } from './locator.js';
import { attachValueInspection, cancelValueInspections } from './value-view.js';

import {bindCaseInspector} from './cases.js';
import { resolvePath } from './path-targets.js';
import { createPathPreview } from './path-preview.js';
import { createPathMenu } from './path-menu.js';
import { bindDocumentFragment } from './document-fragment.js';

const $ = selector => document.querySelector(selector);
let currentView = initialView;
let sourceWritable = Boolean(initialView.writable);
let feedbackTimer;
let inspectorReturnFocus = null;
const previewRequests = new Set();
function cancelPreviews() {
  for (const controller of previewRequests) controller.abort();
  previewRequests.clear();
}
document.addEventListener('debug:navigation-start', cancelPreviews);

function configureChrome() {
  document.documentElement.dataset.debugWorkbench = 'true';

  const refresh = $('#wb-refresh');
  refresh.addEventListener('click', async () => {
    if (navigation.busy || !navigation.mayLeave()) return;
    refresh.loading = true;
    try { await navigation.refresh(); navigation.report('Snapshot refreshed.', false,
      {operation: 'refresh', phase: 'success', context: navigation.currentPath(), quiet: false}); }
    catch (error) { navigation.report('Refresh failed. ' + error.message, true,
      {operation: 'refresh', context: navigation.currentPath()}); }
    finally { refresh.loading = false; }
  });
  const inspectorToggle = $('#debug-inspector-toggle');

  const workspace = $('#debug-workspace');

  // Persist only user-sized panes, not viewport-dependent responsive sizes.
  const paneKey = 'shrine-debug:pane-widths';
  try {
    const widths = JSON.parse(localStorage.getItem(paneKey) || '{}');
    for (const name of ['sidebarWidth', 'inspectorWidth']) {
      if (Number.isFinite(widths[name]) && widths[name] >= 0 && widths[name] <= 1000) workspace[name] = widths[name];
    }
  } catch { /* Storage may be unavailable; layout remains fully functional. */ }
  workspace.addEventListener('sh-triptych-resize', event => {
    try { localStorage.setItem(paneKey, JSON.stringify(event.detail)); } catch { /* Session-only widths. */ }
  });
  workspace.inspectorOpen = false;
  inspectorToggle.setAttribute('aria-expanded', 'false');
  const compactViewport = window.matchMedia('(max-width: 832px)');
  let focusedPane = 'main';
  let focusedControl = null;
  let focusRevision = 0;
  let breakpointRevision = 0;
  let desktopPanels = compactViewport.matches ? {sidebarOpen: true, inspectorOpen: false} : null;
  // Remember focus before responsive CSS can hide and blur a pane. The main
  // document remains the default when a chrome control has focus.
  document.addEventListener('focusin', event => {
    focusedPane = $('#debug-sidebar').contains(event.target) ? 'sidebar' :
      workspace.querySelector('[slot=inspector]')?.contains(event.target) ? 'inspector' : 'main';
    focusedControl = event.composedPath()[0];
    focusRevision++;
  });
  document.addEventListener('focusout', event => {
    // An intentional blur of a visible control is not a resize casualty.
    // Responsive CSS can instead blur it while its old pane is briefly hidden.
    if (event.composedPath()[0] === focusedControl && !event.relatedTarget && focusedControl.getClientRects().length) {
      focusedControl = null;
      focusedPane = 'main';
      focusRevision++;
    }
  });
  compactViewport.addEventListener('change', async event => {
    const retained = focusedControl;
    const focusAtResize = focusRevision;
    const resize = ++breakpointRevision;
    const selection = retained && typeof retained.selectionStart === 'number' ?
      {start: retained.selectionStart, end: retained.selectionEnd, direction: retained.selectionDirection, value: retained.value} : null;
    if (event.matches) {
      desktopPanels = {sidebarOpen: workspace.sidebarOpen, inspectorOpen: workspace.inspectorOpen};
      // A desktop navigation rail must not replace the record on resize. Keep
      // an auxiliary pane only when the person was actively working inside it.
      workspace.sidebarOpen = desktopPanels.sidebarOpen && focusedPane === 'sidebar';
      workspace.inspectorOpen = desktopPanels.inspectorOpen && focusedPane === 'inspector';
    } else if (desktopPanels) {
      // Restore the wide arrangement, while retaining an auxiliary pane the
      // person explicitly opened on compact screens. Widths/DOM are untouched.
      workspace.sidebarOpen = desktopPanels.sidebarOpen || workspace.sidebarOpen;
      workspace.inspectorOpen = desktopPanels.inspectorOpen || workspace.inspectorOpen;
      desktopPanels = null;
    }
    $('#debug-sidebar-toggle').setAttribute('aria-expanded', String(workspace.sidebarOpen));
    inspectorToggle.setAttribute('aria-expanded', String(workspace.inspectorOpen));
    // CSS may hide the old pane before the media-query callback updates Mash's
    // reflected state. Restore only that lost focus, never a newer interaction.
    await workspace.updateComplete;
    await new Promise(resolve => requestAnimationFrame(resolve));
    if (resize !== breakpointRevision || focusAtResize !== focusRevision || !retained?.isConnected ||
        !document.hasFocus() || !retained.getClientRects().length || retained.matches(':disabled') ||
        getComputedStyle(retained).visibility === 'hidden') return;
    let active = document.activeElement;
    while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
    if (active && active !== document.body) return;
    retained.focus({preventScroll: true});
    if (selection && retained.value === selection.value) retained.setSelectionRange(selection.start, selection.end, selection.direction);
  });
  $('#wb-feedback-dismiss').addEventListener('click', () => { $('#wb-feedback').hidden = true; });
  createPathLocator({navigation, form: $('#debug-go'), initialView});
}

function setReadonly() {
  $('#debug-workspace').dataset.writable = String(sourceWritable);
  $('#debug-main').querySelectorAll('ui-button[type=submit], button[type=submit]').forEach(control => {
    control.disabled = navigation.isAuthoredDisabled(control) || !sourceWritable || navigation.busy;
  });

}

function enableInspection() {
  $('#debug-workspace').dataset.viewMode = 'inspect';
  $('#wb-canvas').hidden = false;
  $('#wb-rendered').hidden = true;
  const control = $('#wb-mode-inspect');
  if (control) { control.setAttribute('aria-pressed', 'true'); control.selected = true; }
  // Old Preview links resolve to the native inspection document.
  const url = new URL(location.href);
  url.searchParams.delete('view');
  history.replaceState(history.state, '', url.pathname + url.search);
  setReadonly();
}

function mountView(view) {
  cancelPreviews();
  cancelValueInspections();
  currentView = view;
  sourceWritable = Boolean(view.writable);
  const workspace = $('#debug-workspace');
  const main = $('#debug-main');
  if (main.dataset.debugFragment !== 'inspect') throw new Error('Missing Grove inspect fragment');
  // The HTTP foot owns the document. Mash upgrades its declarative controls;
  // application code only connects namespace reads and write verdicts.
  main.querySelector('#wb-mode-inspect')?.addEventListener('click', enableInspection);
  bindDocumentFragment(main, view, {readPreview: navigation.readPreview, attachValueInspection, requests: previewRequests});
  workspace.dataset.kind = view.kind;
  workspace.dataset.readState = 'ready';
  renderInspector(view);
  enableInspection();
  document.dispatchEvent(new CustomEvent('debug:read-complete', {detail: view}));
}

function renderInspector(view) {
  const workspace = $('#debug-workspace');
  const panel = workspace.querySelector('[slot=inspector]');
  if (!panel) return;
  cancelValueInspections(panel);
  if (panel.dataset.debugFragment !== 'inspector') throw new Error('Missing Grove inspector fragment');
  const reference = view.path !== currentView.path;
  panel.setAttribute('aria-label', reference ? 'Inspect reference' : 'Details');
  panel.querySelector('.wb-inspector-path').textContent = reference ? 'Inspect reference' : 'Details';
  panel.querySelector('.wb-declared-reference').hidden = !reference;
  panel.querySelector('[data-inspector-hint]').hidden = reference;
  workspace.dataset.inspectorPath = view.path;
  bindCaseInspector(panel, {navigate: navigation.navigate});
  const slots = new Map(view.record?.slots.map(slot => [slot.key, slot]) || []);
  for (const limb of panel.querySelectorAll('sh-limb[data-key]')) {
    const slot = slots.get(limb.dataset.key);
    if (slot) attachValueInspection(limb.querySelector(':scope > sh-pail'), slot);
  }
}

configureChrome();
mountView(initialView);
createPathPreview({resolvePath, readPreview: navigation.readPreview, initialView});
createPathMenu({resolvePath, report: navigation.report});
document.addEventListener('debug:navigate', event => {
  if (!event.detail?.document) return;
  mountView(event.detail.document);
  if (event.detail.focusMain) $('.wb-document-title')?.focus();
});
function captureInspectorFocus() {
  const active = document.activeElement;
  // A definition can itself contain inspectable keys. Keep the original page
  // anchor when the currently focused control belongs to the replaced panel.
  if (active && active !== document.body && !active.closest('.wb-inspector')) inspectorReturnFocus = active;
}
function focusInspector() {
  const workspace = $('#debug-workspace');
  workspace.updateComplete.then(() => {
    if (workspace.inspectorOpen) $('.wb-inspector')?.focus({preventScroll: true});
  });
}
function closeInspector() {
  cancelValueInspections($('.wb-inspector'));
  $('#debug-workspace').inspectorOpen = false;
  $('#debug-inspector-toggle').setAttribute('aria-expanded', 'false');
  (inspectorReturnFocus?.isConnected ? inspectorReturnFocus : $('#debug-inspector-toggle')).focus();
}
document.addEventListener('debug:inspect-start', captureInspectorFocus);
document.addEventListener('debug:inspector-toggle', event => {
  if (event.detail.open) { captureInspectorFocus(); focusInspector(); }
  else closeInspector();
});
document.addEventListener('debug:inspect', event => {
  if (event.detail?.document) {
    renderInspector(event.detail.document);
    focusInspector();
  }
});
document.addEventListener('ui-input-enter', event => {
  if (event.target === $('#debug-go ui-input')) $('#debug-go').requestSubmit();
});
document.addEventListener('debug:status', event => {
  const {message, failed, operation = 'general', phase = failed ? 'error' : 'info',
    context = null, quiet = !failed} = event.detail;
  const feedback = $('#wb-feedback');
  if (!feedback) return;
  // A later attempt is not proof of an earlier uncertain commit's outcome.
  // Keep that warning until explicit dismissal; all reports still enter activity.
  if (!feedback.hidden && feedback.dataset.operation === 'write' && feedback.dataset.failed === 'true' &&
      (feedback.dataset.phase === 'unknown' || operation !== 'write')) return;
  if (quiet) {
    if (!failed && phase === 'success' && ['navigate', 'inspect'].includes(operation) &&
        feedback.dataset.operation === operation && feedback.dataset.failed === 'true' && feedback.dataset.phase === 'error') {
      clearTimeout(feedbackTimer);
      feedback.hidden = true;
    }
    return;
  }
  const sameOwner = feedback.dataset.operation === operation &&
    (['navigate', 'inspect'].includes(operation) || feedback.dataset.context === String(context ?? ''));
  if (!feedback.hidden && !sameOwner &&
      (feedback.dataset.phase === 'unknown' || feedback.dataset.phase === 'pending' ||
        !failed && feedback.dataset.failed === 'true')) return;
  clearTimeout(feedbackTimer);
  feedback.hidden = false;
  feedback.dataset.failed = String(failed);
  feedback.dataset.operation = operation;
  feedback.dataset.phase = phase;
  feedback.dataset.context = String(context ?? '');
  const messageSlot = feedback.querySelector('[data-feedback-message]');
  messageSlot.textContent = message;
  feedback.querySelector('ui-icon').setAttribute('name', failed ? phase === 'unknown' ? 'status.warning' : 'status.error' : 'object.terminal');
  if (!failed && phase !== 'pending') feedbackTimer = setTimeout(() => { feedback.hidden = true; }, 7000);
});
document.addEventListener('keydown', async event => {
  if (event.defaultPrevented) return;
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    const workspace = $('#debug-workspace');
    workspace.sidebarOpen = true;
    if (window.matchMedia('(max-width: 832px)').matches) {
      workspace.inspectorOpen = false;
      $('#debug-inspector-toggle').setAttribute('aria-expanded', 'false');
    }
    $('#debug-sidebar-toggle').setAttribute('aria-expanded', 'true');
    await workspace.updateComplete;
    $('#debug-filter').focus();
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey || event.isComposing ||
      event.composedPath().some(target => target?.matches?.('input, textarea, select, [contenteditable=true]'))) return;
  if (event.key === 'Escape' && $('#debug-workspace').inspectorOpen) {
    event.preventDefault();
    closeInspector();
  } else if (event.key === 'Escape' && window.matchMedia('(max-width: 832px)').matches && $('#debug-workspace').sidebarOpen) {
    event.preventDefault();
    $('#debug-workspace').sidebarOpen = false;
    $('#debug-sidebar-toggle').setAttribute('aria-expanded', 'false');
    $('#debug-sidebar-toggle').focus();
  }
});
// Any synchronous initialization failure above leaves the fallback enabled.
