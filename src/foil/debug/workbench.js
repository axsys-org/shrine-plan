import {legacyElement} from './legacy.js';
import { navigation, initialView } from './navigation.js';
import { button, icon } from './icons.js';
import { createPathLocator } from './locator.js';
import { attachValueInspection, cancelValueInspections } from './value-view.js';
import { beginStylesheetHandoff } from './stylesheets.js';
import { enhanceForms } from './forms.js';
import { caseInspector, bindCaseInspector } from './cases.js';
import { resolvePath } from './path-targets.js';
import { createPathPreview } from './path-preview.js';
import { createPathMenu } from './path-menu.js';
import { createTooltips } from './tooltips.js';
import { bindDocumentFragment } from './document-fragment.js';

const $ = selector => document.querySelector(selector);
const node = (tag, className = '', text = '') => {
  const element = legacyElement(tag);
  element.className = className;
  if (text) element.textContent = text;
  return element;
};
const kindIcons = {
  record: 'record', namespace: 'roots', role: 'record', action: 'run',
  norm: 'branch', sewn: 'subtree', template: 'roots', module: 'subtree',
  event: 'activity', journal: 'activity', http: 'activity', behavior: 'settings',
};
const kindLabels = {
  namespace: 'Namespace', role: 'Role', action: 'Action', norm: 'Collection',
  sewn: 'Derived view', template: 'App template', module: 'Module',
  event: 'Event', journal: 'Activity', http: 'HTTP request', behavior: 'Behavior',
  record: 'Record',
};
let currentView = initialView;
let operations = null;
let sourceWritable = Boolean(initialView.writable);
let feedbackTimer;
let mode = 'inspect';
let inspectorReturnFocus = null;
const previewRequests = new Set();
const metadataKeys = new Set(['/sys/lede', '/sys/help']);
// Shrine's commit gate reads this canonical slot as the record's constraint;
// it is not an application slot or prose. Keep it available, but secondary.
const constraintKeys = new Set(['/sys/lash']);
const semanticKinds = new Set(['role', 'action', 'norm', 'sewn', 'template', 'module', 'event', 'behavior']);
const pathName = path => path === '/' ? '/' : path.split('/').filter(Boolean).at(-1);
const comparableLabel = value => value.trim().replace(/[.!?]+$/, '').toLocaleLowerCase();
const authoredLede = view => view.label && view.label !== view.path &&
  comparableLabel(view.label) !== comparableLabel(pathName(view.path)) ? view.label : '';
function cancelPreviews() {
  for (const controller of previewRequests) controller.abort();
  previewRequests.clear();
}
document.addEventListener('debug:navigation-start', cancelPreviews);

function namespaceLink(path, text = path, className = '') {
  const link = node('a', className, text);
  link.href = navigation.debugURL(path);
  return link;
}

function iconify(id, name, label) {
  const control = $('#' + id);
  if (!control) return;
  control.setAttribute('aria-label', label);
  control.title = '';
  control.classList.add('wb-icon-button');
  control.setAttribute('icon-only', '');
  control.setAttribute('size', 'compact');
  control.setAttribute('variant', 'ghost');
  control.setAttribute('tone', 'neutral');
  control.replaceChildren(icon(name));
}

function configureChrome() {
  const declared = !__DEBUG_LEGACY__ || Boolean(document.querySelector('[data-grove-contract="debugger/v1"]'));
  document.documentElement.dataset.debugWorkbench = 'true';
  if (!declared) {
    iconify('debug-sidebar-toggle', 'sidebar', 'Toggle sidebar');
    iconify('debug-inspector-toggle', 'inspector', 'Toggle inspector');
  }
  const header = $('.debug-header');
  header.classList.add('wb-commandbar');
  const tools = declared ? $('#wb-header-actions') : node('ui-toolbar', 'debug-toolbar wb-header-tools');
  tools.setAttribute('label', 'Workspace actions');
  tools.setAttribute('data-mash-size', 'small');
  tools.id = 'wb-header-actions';
  const refresh = declared ? $('#wb-refresh') : button('Refresh current record', 'live');
  refresh.addEventListener('click', async () => {
    if (navigation.busy || !navigation.mayLeave()) return;
    refresh.loading = true;
    try { await navigation.refresh(); navigation.report('Snapshot refreshed.', false,
      {operation: 'refresh', phase: 'success', context: navigation.currentPath(), quiet: false}); }
    catch (error) { navigation.report('Refresh failed. ' + error.message, true,
      {operation: 'refresh', context: navigation.currentPath()}); }
    finally { refresh.loading = false; }
  });
  refresh.id = 'wb-refresh';
  const inspectorToggle = $('#debug-inspector-toggle');
  if (!declared) tools.append(refresh, inspectorToggle);
  const workspace = $('#debug-workspace');
  if (!declared) workspace.resizable = true;
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
  if (declared) {
    $('#wb-feedback-dismiss').addEventListener('click', () => { $('#wb-feedback').hidden = true; });
    createPathLocator({navigation, form: $('#debug-go'), initialView, declared: true});
    return;
  }
  const footer = $('.debug-footer');
  footer.classList.add('wb-activity');
  footer.hidden = true;
  const bottom = node('div', 'wb-bottom');
  bottom.slot = 'main-footer';
  footer.removeAttribute('slot');
  bottom.append(footer);
  workspace.append(bottom);
  const go = $('#debug-go');
  const submit = go.querySelector('ui-button');
  submit.setAttribute('aria-label', 'Open namespace path');
  submit.title = 'Open namespace path';
  submit.classList.add('wb-icon-button');
  submit.setAttribute('icon-only', '');
  submit.setAttribute('size', 'compact');
  submit.setAttribute('variant', 'ghost');
  submit.setAttribute('tone', 'neutral');
  submit.replaceChildren(icon('arrow'));
  const inputGroup = node('ui-input-group');
  inputGroup.id = 'wb-path-input-group';
  inputGroup.setAttribute('size', 'small');
  inputGroup.setAttribute('typography', 'code');
  inputGroup.setAttribute('touch-target', '');
  const pathInput = go.querySelector('ui-input');
  pathInput.slot = 'control'; pathInput.setAttribute('size', 'inherit');
  submit.slot = 'suffix';
  inputGroup.append(pathInput, submit);
  go.append(inputGroup);
  const locator = createPathLocator({ navigation, form: go, initialView });
  header.replaceChildren($('#debug-sidebar-toggle'), $('#debug-history-nav'), locator.element, tools);
  $('.debug-locator')?.remove();
  $('.debug-sidebar-footer')?.remove();
  const feedback = node('div', 'wb-feedback');
  feedback.id = 'wb-feedback';
  feedback.hidden = true;
  feedback.setAttribute('role', 'status');
  feedback.setAttribute('aria-live', 'polite');
  $('.debug-shell').append(feedback);
}

function setReadonly() {
  $('#debug-workspace').dataset.writable = String(sourceWritable);
  if (operations) operations.hidden = mode !== 'inspect' || !sourceWritable || !operations.open;
  $('#debug-main').querySelectorAll('ui-button[type=submit], button[type=submit]').forEach(control => {
    control.disabled = navigation.isAuthoredDisabled(control) || mode !== 'inspect' || !sourceWritable || navigation.busy;
  });
  const toggle = $('#wb-operations-toggle');
  if (toggle) {
    toggle.hidden = mode !== 'inspect' || !sourceWritable || !operations?.querySelector('form');
    toggle.setAttribute('aria-expanded', String(!operations?.hidden));
  }
}

// Client-owned reference reads use the same declarative scroll composition as
// the HTTP fragments. Mash measures overflow; the app does not promote nodes.
function valueBlock(text, label) {
  const area = node('ui-scroll-area', 'wb-code-scroll');
  area.setAttribute('label', label);
  area.setAttribute('mode', 'scrolling');
  area.setAttribute('size', 'medium');
  area.setAttribute('orientation', 'vertical');
  area.append(node('pre', 'wb-value', text));
  return area;
}

function slotRow(slot, valueContext = null) {
  const row = node('sh-limb', 'wb-slot-row');
  row.dataset.key = slot.key;
  const key = node('sh-slot');
  key.slot = 'label';
  key.setAttribute('title', slot.key);
  const definition = node('ui-button', 'wb-slot-key', slot.key);
  definition.setAttribute('type', 'button');
  definition.setAttribute('variant', 'text');
  definition.setAttribute('size', 'small');
  definition.setAttribute('aria-label', 'Inspect slot definition ' + slot.key);
  definition.title = 'Inspect slot definition ' + slot.key;
  definition.dataset.inspect = slot.key;
  key.append(definition);
  const value = node('sh-pail');
  value.slot = 'value';
  value.setAttribute('role', 'group');
  value.setAttribute('aria-label', 'Value of ' + slot.key);
  const links = [...(slot.links || [])];
  if (slot.reference && !links.some(link => link.path === slot.reference)) links.push({path: slot.reference, text: slot.reference});
  if (links.length === 1 && (slot.text === links[0].text || slot.text === links[0].path)) {
    value.append(namespaceLink(links[0].path, links[0].text));
  } else {
    const text = slot.text;
    value.append(valueBlock(text === '' ? '""' : text, 'Value of ' + slot.key));
    if (links.length) {
      const references = node('div', 'wb-slot-links');
      for (const link of links) references.append(namespaceLink(link.path, link.text));
      value.append(references);
    }
  }
  attachValueInspection(value, slot, {unknownContext: valueContext});
  row.append(key, value);
  return row;
}

let valueContextId = 0;
function recordSurface(record, className = 'wb-record', title = 'Slots') {
  const myth = node('sh-myth', className + ' wb-record-body');
  myth.setAttribute('variant', 'embedded');
  myth.setAttribute('data-mash-size', 'compact');
  myth.dataset.path = record.path;
  const heading = node('span');
  heading.slot = 'title';
  heading.append(icon('record'), node('span', '', title));
  const count = node('ui-badge', '', String(record.slots.length));
  count.slot = 'meta'; count.setAttribute('tone', 'neutral');
  if (title) myth.append(heading, count);
  // A shared note is valid only for this exact, uniformly unknown group.
  // Known, partial and mixed values retain their own fidelity/actions.
  let valueContext = null;
  if (record.slots.length > 1 && record.slots.every(slot => !slot.fidelity || slot.fidelity.state === 'unknown')) {
    valueContext = node('span', 'wb-record-annotation', 'Value completeness is not reported by this runtime.');
    valueContext.slot = 'annotation';
    valueContext.id = 'wb-value-context-' + (++valueContextId);
    myth.append(valueContext);
  }
  for (const slot of record.slots) myth.append(slotRow(slot, valueContext));
  if (!record.slots.length) myth.append(node('p', 'wb-context-note', 'This record has no slots.'));
  return myth;
}

function loreSurface(view, serverDocumentation = null) {
  const text = view.description?.trim();
  const lines = view.lore?.lines?.length ? view.lore.lines : text ? [text] : [];
  const meaningful = lines.filter(line => line.trim() && line.trim() !== view.label && line.trim() !== view.path);
  const tests = serverDocumentation ? [...serverDocumentation.querySelectorAll('.row')]
    .filter(row => row.querySelector('.dtsrc')) : [];
  if (!meaningful.length && !tests.length) return null;
  const surface = node('section', 'wb-lore');
  surface.setAttribute('aria-label', 'About this path');
  const prose = node('div', 'wb-lore-prose');
  for (const line of meaningful.slice(0, 6)) prose.append(node('p', '', line));
  surface.append(prose);
  if (meaningful.length > 6) {
    const more = node('details', 'wb-lore-more');
    more.append(node('summary', '', 'Read more'));
    for (const line of meaningful.slice(6)) more.append(node('p', '', line));
    surface.append(more);
  }
  if (tests.length) {
    const examples = node('details', 'wb-doctests');
    examples.append(node('summary', '', 'Examples · ' + tests.length), ...tests);
    surface.append(examples);
  }
  return surface;
}

function slotGroups(record, hasSemantics = false) {
  const groups = {slots: [], constraints: [], source: []};
  // Keep every original slot object exactly once, in its original group order.
  // A semantic surface does not prove completeness of a compiled value: its
  // raw representation remains available in Source slots, with fidelity.
  for (const slot of record.slots) {
    const group = constraintKeys.has(slot.key) ? 'constraints' :
      metadataKeys.has(slot.key) || (hasSemantics && semanticKinds.has(slot.kind)) ? 'source' : 'slots';
    groups[group].push(slot);
  }
  return groups;
}

function visibleProperties(view, hasSemantics = false, className = 'wb-properties') {
  if (!view.record) return null;
  const slots = slotGroups(view.record, hasSemantics).slots;
  return slots.length ? recordSurface({...view.record, slots}, className, 'Slots') : null;
}

function appendRecordSlots(container, view, hasSemantics = false, className = 'wb-properties') {
  if (!view.record) return;
  const groups = slotGroups(view.record, hasSemantics);
  if (groups.slots.length || !view.record.slots.length) {
    container.append(recordSurface({...view.record, slots: groups.slots}, className));
  }
  const details = node('ui-accordion', 'wb-record-details');
  details.setAttribute('variant', 'quiet');
  details.setAttribute('size', 'compact');
  details.setAttribute('mode', 'multiple');
  for (const [group, title, itemClass, recordClass] of [
    ['constraints', 'Record constraints', 'wb-constraints', 'wb-constraint-record'],
    ['source', 'Source slots', 'wb-raw-details', 'wb-record'],
  ]) {
    const slots = groups[group];
    if (!slots.length) continue;
    const item = node('ui-accordion-item', itemClass);
    item.setAttribute('value', group);
    item.setAttribute('title', title);
    item.setAttribute('heading-level', '2');
    const disclosure = icon('chevron'); disclosure.slot = 'disclosure';
    const count = node('span', '', slots.length + (slots.length === 1 ? ' slot' : ' slots'));
    count.slot = 'suffix';
    item.append(disclosure, count, recordSurface({...view.record, slots}, recordClass, ''));
    item.addEventListener('ui-accordion-item-change', event => {
      if (event.target === item && !event.detail.open) cancelValueInspections(item);
    });
    details.append(item);
  }
  if (details.children.length) container.append(details);
}

function safeSection(section) {
  if (!section) return null;
  // Compatibility for generated role chrome in the preserved running kernel.
  // Do not rename words inside authored lore or exact slot values.
  if (section.getAttribute('aria-label') === 'Semantics') {
    for (const empty of section.querySelectorAll('.debug-role-fields > p.muted')) {
      if (empty.textContent.trim() === 'No declared fields.') empty.textContent = 'No declared slots.';
    }
  }
  // Keep server-authored structures and forms, never executable value markup.
  section.querySelectorAll('script,style,iframe,object,embed').forEach(item => item.remove());
  for (const element of section.querySelectorAll('*')) {
    for (const attribute of [...element.attributes]) {
      if (/^on/i.test(attribute.name) || attribute.name === 'srcdoc') element.removeAttribute(attribute.name);
    }
    if (element.matches('a[href]')) {
      const href = element.getAttribute('href');
      if (!href.startsWith('/') || href.startsWith('//')) element.removeAttribute('href');
      else if (/^\/ns(?:\/|$)/.test(href)) element.setAttribute('href', '/debug' + href.slice(3));
    }
  }
  return section;
}

function foldImplementation(semantics) {
  const exports = semantics?.querySelector(':scope > .debug-exports');
  if (!exports) return;
  const fields = [];
  let previous = exports.previousElementSibling;
  while (previous?.matches('.debug-fact') && ['Declaration', 'Exports'].includes(previous.dataset.key)) {
    fields.unshift(previous);
    previous = previous.previousElementSibling;
  }
  const implementation = node('details', 'wb-implementation');
  implementation.append(node('summary', '', 'Implementation'));
  (fields[0] || exports).before(implementation);
  implementation.append(...fields, exports);
}

function consolidateRequirements(semantics) {
  for (const requirements of semantics?.querySelectorAll('.debug-requirements') || []) {
    const fields = requirements.previousElementSibling;
    if (!fields?.matches('.debug-role-fields')) continue;
    const required = new Set([...fields.querySelectorAll('.debug-schema-field')]
      .filter(field => field.querySelector('.muted')?.textContent.trim() === 'required')
      .map(field => field.dataset.reference));
    for (const group of requirements.querySelectorAll('.debug-requirement')) {
      const links = [...group.querySelectorAll('a[data-reference]')];
      if (links.length === 1 && required.has(links[0].dataset.reference)) group.hidden = true;
    }
    if (![...requirements.querySelectorAll('.debug-requirement')].some(group => !group.hidden)) requirements.hidden = true;
  }
}

function childrenSurface(view) {
  const surface = node('section', 'wb-children-section');
  const heading = node('div', 'wb-record-heading');
  heading.append(node('span', '', 'Paths'),
    node('span', 'wb-record-count', String(view.children.length)));
  surface.append(heading);
  const list = node('div', 'wb-children');
  list.setAttribute('role', 'list');
  list.setAttribute('aria-label', 'Child paths');
  const summaries = new Map(view.childSummaries?.map(item => [item.path, item]));
  let shown = 0;
  const more = button('Show more child paths', 'more', () => append(), 'Show more');
  function append() {
    for (const path of view.children.slice(shown, shown + 60)) {
      const summary = summaries.get(path);
      const row = node('sh-path-row', 'wb-child-row');
      row.setAttribute('role', 'listitem');
      row.dataset.path = path;
      row.href = navigation.debugURL(path);
      row.label = pathName(path);
      row.previewable = true;
      row.previewLabel = 'Preview ' + path;
      const mark = icon(kindIcons[summary?.kind] || 'record');
      mark.slot = 'icon';
      const label = node('span', 'wb-child-name', pathName(path));
      label.slot = 'label';
      row.append(mark, label);
      const lede = summary && authoredLede(summary);
      const description = summary?.description !== summary?.label ? summary?.description : '';
      if (lede || description) {
        const meta = node('span');
        meta.slot = 'meta';
        if (lede) meta.append(node('span', 'wb-child-lede', lede));
        if (lede && description) meta.append(' ');
        if (description) meta.append(node('span', 'wb-child-description', description));
        row.append(meta);
      }
      const preview = node('div', 'wb-child-preview');
      preview.slot = 'preview';
      preview.hidden = true;
      let loaded = false;
      let loading = false;
      async function loadPreview() {
        if (!row.open || loaded || loading) return;
        loading = true;
        preview.replaceChildren(node('p', 'wb-loading', 'Loading ' + pathName(path) + '…'));
        preview.setAttribute('aria-busy', 'true');
        const controller = new AbortController();
        previewRequests.add(controller);
        try {
          const answer = await navigation.readPreview(path, {signal: controller.signal});
          if (!preview.isConnected) return;
          const document = answer.view;
          preview.replaceChildren();
          const lore = loreSurface(document);
          if (lore) preview.append(lore);
          const properties = visibleProperties(document, false, 'wb-preview-record');
          if (properties) preview.append(properties);
          if (document.children.length) {
            const paths = node('div', 'wb-preview-paths');
            for (const child of document.children.slice(0, 20)) {
              paths.append(namespaceLink(child, pathName(child), 'wb-preview-path'));
            }
            if (document.children.length > 20) paths.append(namespaceLink(path,
              '+' + (document.children.length - 20) + ' more paths', 'wb-preview-path'));
            preview.append(paths);
          }
          if (!preview.children.length) preview.append(node('p', 'wb-context-note', authoredLede(document) || 'No slots or child paths.'));
          preview.append(namespaceLink(path, 'Open ' + pathName(path), 'wb-preview-open'));
          loaded = true;
        } catch (error) {
          if (preview.isConnected) preview.replaceChildren(
            node('p', 'wb-context-note', controller.signal.aborted ?
              'Preview paused while opening another view.' : 'Could not load this path. ' + error.message),
            button('Retry preview ' + path, 'live', loadPreview, 'Retry'));
        } finally {
          loading = false;
          previewRequests.delete(controller);
          preview.removeAttribute('aria-busy');
        }
      }
      row.addEventListener('sh-path-row-toggle', event => {
        if (event.target !== row) return;
        preview.hidden = !event.detail.open;
        if (event.detail.open) void loadPreview();
      });
      row.append(preview);
      list.append(row);
    }
    shown += 60;
    more.hidden = shown >= view.children.length;
  }
  append();
  surface.append(list, more);
  return surface;
}

function emptyRecord(view) {
  const empty = node('div', 'wb-empty');
  empty.append(icon(view.state === 'tombstone' ? 'history' : 'roots'),
    node('strong', '', view.state === 'tombstone' ? 'This record was removed' :
      view.children.length ? 'A namespace containing child paths' : 'No record at this path'));
  if (view.state === 'tombstone') {
    empty.append(node('p', '', 'Its earlier state is still available.'));
    const previous = view.historyLinks?.filter(link => /^\/h\/x\//.test(link.path)).at(-2);
    if (previous) empty.append(namespaceLink(previous.path, 'Inspect last recorded value', 'wb-reference-link'));
  } else if (!view.children.length) {
    empty.append(node('p', '', 'Choose a path in the tree, or enter a different address above.'));
  }
  return empty;
}

function renderedSurface(view) {
  const surface = node('section', 'wb-rendered');
  surface.id = 'wb-rendered';
  surface.hidden = true;
  const toolbar = node('div', 'wb-render-toolbar');
  toolbar.append(node('span', 'wb-context-note', 'Isolated preview. Open the interface to interact with it.'));
  const target = new URL(view.renderURL, location.origin);
  const allowed = target.origin === location.origin && /^\/ns(?:\/|$)/.test(target.pathname);
  if (!allowed) return surface;
  const open = node('a', 'wb-render-open', 'Open interface');
  open.href = target.href;
  open.target = '_blank';
  open.rel = 'noopener noreferrer';
  open.append(icon('arrow'));
  toolbar.append(open);
  surface.append(toolbar);
  const frame = node('iframe', 'wb-render-frame');
  frame.title = 'Rendered interface for ' + view.path;
  // Namespace renderers execute separately from the debugger; no script can
  // reach the inspection tree or submit namespace forms inside this preview.
  frame.setAttribute('sandbox', '');
  frame.referrerPolicy = 'no-referrer';
  frame.dataset.src = target.href;
  surface.append(frame);
  return surface;
}

function setMode(next) {
  if (!__DEBUG_LEGACY__) next = 'inspect'; // Retired Preview URLs cannot hide the native document.
  mode = next;
  $('#debug-workspace').dataset.viewMode = next;
  $('#wb-canvas').hidden = next !== 'inspect';
  $('#wb-rendered').hidden = next !== 'rendered';
  for (const name of ['inspect', 'rendered']) {
    const control = $('#wb-mode-' + name);
    if (!control) continue;
    control.setAttribute('aria-pressed', String(next === name));
    control.selected = next === name;
  }
  if (next === 'rendered') {
    const frame = $('#wb-rendered iframe');
    if (frame && !frame.getAttribute('src')) frame.src = frame.dataset.src;
  }
  const url = new URL(location.href);
  if (next === 'rendered') url.searchParams.set('view', 'rendered');
  else url.searchParams.delete('view');
  history.replaceState(history.state, '', url.pathname + url.search);
  setReadonly();
}

function enhanceJournal(semantics, view) {
  // Keep the server's event identity and exact text. Mash owns the native
  // navigation control; only the namespace-specific content layout lives here.
  for (const anchor of semantics?.querySelectorAll('.debug-events > a.debug-event') || []) {
    const link = node('ui-link');
    for (const attribute of anchor.attributes) link.setAttribute(attribute.name, attribute.value);
    link.setAttribute('variant', 'quiet'); link.setAttribute('data-mash-size', 'compact');
    const content = node('span', 'debug-event-content');
    content.append(...anchor.childNodes);
    link.append(content); anchor.replaceWith(link);
  }
  const pager = semantics?.querySelector('.debug-journal-pagination');
  if (!pager || !view.pagination) return;
  const count = node('span', 'wb-journal-page-count',
    view.children.length + ' entries · ' + view.pagination.total + ' total');
  const actions = node('div', 'wb-journal-page-actions');
  for (const anchor of pager.querySelectorAll('a[href]')) {
    const link = node('ui-link', '', anchor.textContent);
    for (const attribute of anchor.attributes) link.setAttribute(attribute.name, attribute.value);
    link.setAttribute('variant', 'quiet'); link.setAttribute('data-mash-size', 'compact');
    const older = new URL(anchor.href, location.href).searchParams.has('before');
    const glyph = icon(older ? 'forward' : 'back'); glyph.slot = older ? 'suffix' : 'prefix';
    link.append(glyph); actions.append(link);
  }
  if (!view.pagination.nextBefore) actions.append(node('span', '', 'End of journal'));
  pager.replaceChildren(count, actions);
}

function mountView(view, nextMode = 'inspect') {
  cancelPreviews();
  cancelValueInspections();
  currentView = view;
  sourceWritable = Boolean(view.writable);
  const workspace = $('#debug-workspace');
  const main = $('#debug-main');
  if (!__DEBUG_LEGACY__ || main.dataset.debugFragment === 'inspect') {
    if (main.dataset.debugFragment !== 'inspect') throw new Error('Missing Grove inspect fragment');
    // The HTTP foot owns the document. Mash upgrades its declarative controls;
    // application code only connects namespace reads and write verdicts.
    operations = null;
    $('#wb-operations-toggle')?.remove();
    main.querySelector('#wb-mode-inspect')?.addEventListener('click', () => setMode('inspect'));
    bindDocumentFragment(main, view, {readPreview: navigation.readPreview, attachValueInspection, requests: previewRequests});
    workspace.dataset.kind = view.kind;
    workspace.dataset.readState = 'ready';
    renderInspector(view);
    setMode(nextMode);
    document.dispatchEvent(new CustomEvent('debug:read-complete', {detail: view}));
    return;
  }
  // Compatibility only for an already-running namespace compiled before the
  // fragment contract. New server documents never enter this legacy renderer.
  const serverOperations = safeSection(main.querySelector('section[aria-label=Operations]'));
  const serverDocumentation = safeSection(main.querySelector('section[aria-label=Documentation]'));
  const semantics = safeSection(main.querySelector('section[aria-label=Semantics]'));
  enhanceForms(serverOperations);
  enhanceForms(semantics);
  enhanceJournal(semantics, view);
  const hasSemantics = Boolean(semantics?.textContent.trim());
  const header = node('header', 'wb-document-header');
  const heading = node('div', 'wb-document-heading');
  heading.append(icon(kindIcons[view.kind] || 'record'));
  const title = node('div', 'wb-document-titles');
  const titleRow = node('div', 'wb-document-title-row');
  titleRow.append(node('h1', 'wb-document-title', pathName(view.path)));
  titleRow.firstElementChild.tabIndex = -1;
  titleRow.firstElementChild.title = view.path;
  titleRow.firstElementChild.dataset.pathTarget = view.path;
  if (authoredLede(view)) titleRow.append(node('span', 'wb-document-lede', authoredLede(view)));
  if (!['record', 'namespace', 'module'].includes(view.kind)) titleRow.append(node('span', 'wb-kind', kindLabels[view.kind] || view.kind));
  title.append(titleRow);
  heading.append(title);
  const modes = node('ui-toolbar', 'wb-mode-switch');
  modes.setAttribute('label', 'View mode');
  for (const [name, text, glyph] of [['inspect', 'Inspect', 'inspect']]) {
    const control = button(text, glyph, () => setMode(name), text);
    control.id = 'wb-mode-' + name;
    control.classList.add('wb-mode-button');
    control.setAttribute('aria-pressed', String(name === 'inspect'));
    modes.append(control);
  }
  header.append(heading, modes);
  const canvas = node('div', 'wb-canvas');
  canvas.id = 'wb-canvas';
  canvas.setAttribute('aria-label', 'Namespace inspection');
  const lore = loreSurface(view, serverDocumentation);
  if (lore) canvas.append(lore);
  if (hasSemantics) {
    semantics.classList.add('wb-semantics');
    consolidateRequirements(semantics);
    foldImplementation(semantics);
    canvas.append(semantics);
  }
  if (view.children.length && view.kind !== 'journal') canvas.append(childrenSurface(view));
  appendRecordSlots(canvas, view, hasSemantics);
  if (!view.record && !hasSemantics && !view.children.length) canvas.append(emptyRecord(view));
  operations = node('details', 'wb-operations');
  operations.id = 'wb-operations';
  operations.append(node('summary', '', 'Operations'));
  if (serverOperations) operations.append(serverOperations);
  $('#wb-operations-toggle')?.remove();
  const run = button('Open operations', 'run', () => {
    operations.open = !operations.open;
    setReadonly();
    if (operations.open) operations.scrollIntoView({block: 'nearest',
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  });
  run.id = 'wb-operations-toggle';
  run.setAttribute('aria-expanded', 'false');
  $('#wb-header-actions').prepend(run);
  const rendered = renderedSurface(view);
  main.replaceChildren(header, canvas, rendered, operations);
  workspace.dataset.kind = view.kind;
  workspace.dataset.readState = 'ready';
  setReadonly();
  renderInspector(view);
  setMode(nextMode);
  document.dispatchEvent(new CustomEvent('debug:read-complete', { detail: view }));
}

function renderInspector(view) {
  const workspace = $('#debug-workspace');
  const panel = workspace.querySelector('[slot=inspector]');
  if (!panel) return;
  cancelValueInspections(panel);
  if (!__DEBUG_LEGACY__ || panel.dataset.debugFragment === 'inspector') {
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
    return;
  }
  if (__DEBUG_LEGACY__) {
  panel.replaceChildren();
  panel.className = 'wb-inspector';
  panel.tabIndex = -1;
  panel.setAttribute('role', 'region');
  panel.setAttribute('aria-label', view.path === currentView.path ? 'Details' : 'Inspect reference');
  workspace.dataset.inspectorPath = view.path;
  const header = node('header', 'wb-inspector-header');
  header.append(node('span', 'wb-inspector-path', view.path === currentView.path ? 'Details' : 'Inspect reference'));
  panel.append(header);
  if (view.path !== currentView.path) {
    panel.append(node('strong', 'wb-inspector-lede', authoredLede(view) || pathName(view.path)),
      namespaceLink(view.path, view.path, 'wb-reference-link'));
    const lore = loreSurface(view);
    if (lore) panel.append(lore);
    // No semantic surface is mounted in the reference inspector. Do not hide
    // its semantic-kind values merely because the main document has one.
    appendRecordSlots(panel, view, false, 'wb-inspector-record');
    if (!view.record && !view.children.length) panel.append(node('p', 'wb-context-note', 'No definition at ' + view.path + '. This key has no record in the namespace.'));
  }
  const links = new Map();
  for (const slot of view.record?.slots || []) {
    for (const link of slot.links || []) links.set(link.path, link.text);
    if (slot.reference) links.set(slot.reference, slot.reference);
  }
  if (links.size) {
    panel.append(node('h2', 'wb-section-title', 'References'));
    for (const [path, label] of links) panel.append(namespaceLink(path, label, 'wb-reference-link'));
  }
  panel.append(caseInspector(view, {link: namespaceLink, navigate: navigation.navigate}));
  if (!links.size && view.path === currentView.path) {
    panel.append(node('p', 'wb-context-note', 'Select a slot name to read its definition here.'));
  }
  }
}

// Keep the original explorer recipe as a fallback until this exact frontend
// build is styled and its enhancement has initialized successfully.
const stylesheetHandoff = beginStylesheetHandoff({
  appVersion: typeof __DEBUG_STYLE_APP__ === 'string' ? __DEBUG_STYLE_APP__ : '',
  componentsVersion: typeof __DEBUG_STYLE_COMPONENTS__ === 'string' ? __DEBUG_STYLE_COMPONENTS__ : '',
});
const initialRendered = new URL(location.href).searchParams.get('view') === 'rendered';
configureChrome();
mountView(initialView, initialRendered ? 'rendered' : 'inspect');
createPathPreview({resolvePath, readPreview: navigation.readPreview, initialView});
createPathMenu({resolvePath, report: navigation.report});
createTooltips({resolvePath});
document.addEventListener('debug:navigate', event => {
  if (!event.detail?.document) return;
  const nextMode = event.detail.refresh ? mode :
    event.detail.fromPop && new URL(location.href).searchParams.get('view') === 'rendered' ? 'rendered' : 'inspect';
  mountView(event.detail.document, nextMode);
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
      if (!feedback.closest('[data-grove-contract="debugger/v1"]')) feedback.replaceChildren();
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
  if (messageSlot) {
    messageSlot.textContent = message;
    feedback.querySelector('ui-icon').setAttribute('name', failed ? phase === 'unknown' ? 'status.warning' : 'status.error' : 'object.terminal');
  } else feedback.replaceChildren(icon(failed ? phase === 'unknown' ? 'warning' : 'error' : 'activity'), node('span', '', message),
    button('Dismiss notification', 'close', () => { feedback.hidden = true; }));
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
  if (event.key === 'Escape' && operations?.open) {
    operations.open = false;
    setReadonly();
    $('#wb-operations-toggle').focus();
  } else if (event.key === 'Escape' && $('#debug-workspace').inspectorOpen) {
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
stylesheetHandoff.commit();
