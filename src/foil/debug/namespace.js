// Parse the bounded, server-authored Grove inspection document. Namespace
// requests and cancellation belong to navigation's shared read coordinator.
import { parseJournalPagination } from './journal.js';
import { parseValueMetadata } from './values.js';

const VERSION_FIELDS = new Set([
  'x_data', 'x_shape', 'y_data', 'y_shape', 'z_data', 'z_shape',
  'top', 'first', 'now', 'block', 'state',
]);

function pathOf(value = '/') {
  if (typeof value !== 'string' || !value.startsWith('/')) {
    throw new TypeError('A namespace path must begin with /.');
  }
  const segments = value.split('/').filter(Boolean);
  if (segments.some(segment => segment === '.' || segment === '..')) {
    throw new TypeError('Relative dot segments are not namespace addresses.');
  }
  return '/' + segments.join('/');
}

function segmentsOf(path) {
  return path.split('/').filter(Boolean);
}

function labelOf(path, label) {
  return label && label !== path ? label : (path === '/' ? 'Namespace' : segmentsOf(path).at(-1));
}

function relativeTo(path, parent) {
  if (path === parent) return '';
  const prefix = parent === '/' ? '/' : parent + '/';
  return path.startsWith(prefix) ? path.slice(prefix.length) : null;
}

function scalar(text) {
  if (/^\d+$/.test(text)) {
    const number = Number(text);
    if (Number.isSafeInteger(number)) return number;
  }
  return text;
}

function versionFromEntries(entries) {
  const version = {};
  for (const [key, value] of entries) {
    const name = key.replace(/^\//, '');
    if (VERSION_FIELDS.has(name)) version[name] = scalar(value.trim());
  }
  return Object.keys(version).length ? version : null;
}

function namespaceLink(anchor) {
  const href = anchor.getAttribute('href') || '';
  if (!/^\/(?:ns|debug)(?:\/|$)/.test(href)) return null;
  try {
    const path = pathOf(decodeURIComponent(href.replace(/^\/(?:ns|debug)/, '') || '/'));
    return { path, text: anchor.textContent.trim() };
  } catch {
    return null;
  }
}

function slotOf(limb, recordPath) {
  const key = limb.querySelector(':scope > sh-slot')?.getAttribute('title');
  const value = limb.querySelector(':scope > sh-pail');
  if (!key || !value) return null;
  const copy = value.cloneNode(true);
  copy.querySelectorAll('script,style,template,summary').forEach(node => node.remove());
  const preserveWhitespace = limb.dataset.valueKind === 'text' ||
    ['/method', '/url', '/body', '/res_ctype', '/res_body'].includes(key);
  const text = preserveWhitespace ? copy.textContent : copy.textContent.trim();
  let fidelity;
  try { fidelity = parseValueMetadata(limb, recordPath, key); }
  catch { fidelity = {state: 'unknown', reason: null, bytes: null, previewBytes: null, epoch: null,
    representation: null, url: null, path: recordPath, slot: key}; }
  return {
    key,
    text,
    kind: limb.dataset.valueKind || 'value',
    fidelity,
    reference: limb.dataset.reference || null,
    links: [...value.querySelectorAll('a[href]')].map(namespaceLink).filter(Boolean),
  };
}

/** Parse an inert DOMParser document; no custom elements or scripts execute. */
export function parseDebugDocument(doc, sourcePath = '/') {
  const workspace = doc.querySelector('#debug-workspace');
  if (!workspace) throw new Error('The runtime did not return a namespace debug document.');
  const path = pathOf(workspace.getAttribute('data-path') || sourcePath);
  const sourceMetadata = doc.querySelector('#debug-source-metadata')?.content || doc;
  const recordSection = doc.querySelector('#debug-main section[aria-label="Record"]');
  const myth = recordSection?.querySelector('sh-myth');
  const slots = myth ? [...recordSection.querySelectorAll('sh-myth > sh-limb')].map(limb => slotOf(limb, path)).filter(Boolean) : [];
  const versionMetadata = doc.querySelector('#debug-version-metadata')?.content;
  const version = versionFromEntries(versionMetadata ? [...versionMetadata.querySelectorAll('[data-version-key]')]
    .map(row => [row.dataset.versionKey, row.dataset.versionValue]) : [...doc.querySelectorAll('ui-table[label="version"] ui-table-row')].map(row => {
    const cells = row.querySelectorAll(':scope > ui-table-cell');
    return [cells[0]?.textContent.trim() || '', cells[1]?.textContent.trim() || ''];
  }));
  const children = [...new Set([...sourceMetadata.querySelectorAll('#debug-children ui-tree-item[data-path]')]
    .map(item => item.getAttribute('data-path'))
    .filter(child => child && relativeTo(child, path) && !relativeTo(child, path).includes('/'))
    .map(pathOf))];
  const state = myth ? 'live' : version?.state === 'tombstone' ? 'tombstone' : children.length ? 'structural' : 'unknown';
  const record = myth ? { path, state: 'live', slots } : null;
  const documentationCards = [...doc.querySelectorAll('#debug-main section[aria-label="Documentation"] ui-card')];
  const help = slots.find(slot => slot.key === '/sys/help');
  const lede = slots.find(slot => slot.key === '/sys/lede');
  const label = labelOf(path, lede?.kind === 'text' ? lede.text : workspace.dataset.label);
  const loreLines = documentationCards.flatMap(card =>
    [...card.querySelectorAll('.lore-line')].map(line => line.textContent));
  // The lede and help paths are stable system slots. Prefer the record's authored
  // content; compact outline responses carry only its source-tagged summary.
  const description = help?.kind === 'text' ? help.text : loreLines.length ? loreLines.join('\n') :
    workspace.dataset.descriptionSource === '/sys/help' ? workspace.dataset.description || '' : '';
  const semantics = doc.querySelector('#debug-main section[aria-label="Semantics"]');
  const childPaths = new Set(children);
  const childSummaries = [...sourceMetadata.querySelectorAll('#debug-children ui-tree-item[data-path]')]
    .filter(item => childPaths.has(item.dataset.path)).map(item => ({
      path: item.dataset.path,
      kind: item.dataset.kind || '',
      label: labelOf(item.dataset.path, item.dataset.label || item.getAttribute('title')),
      description: item.dataset.descriptionSource === '/sys/help' ? item.dataset.description || '' : '',
    }));
  const semanticSlots = [...(semantics?.querySelectorAll('[data-debug-field]') || [])].slice(0, 6).map(field => ({
    key: field.dataset.key || field.dataset.debugField || '',
    text: field.dataset.reference ||
      (field.querySelector('.debug-fact-value, [data-debug-value]') || field).textContent.trim().slice(0, 180),
    href: field.querySelectorAll('a').length === 1 ? field.querySelector('a').getAttribute('href') : null,
  }));
  const operations = [...doc.querySelectorAll('#debug-main section[aria-label="Operations"] form')].map(form => ({
    action: form.getAttribute('action'),
    path: form.querySelector('input[name="op"]')?.getAttribute('value') || null,
    label: form.querySelector('[type="submit"]')?.textContent.trim() || 'Operation',
    fields: [...form.querySelectorAll('ui-input[name]')].map(input => ({
      name: input.getAttribute('name'),
      label: input.getAttribute('label'),
      placeholder: input.getAttribute('placeholder') || '',
    })),
  }));
  return {
    path,
    namespaceRoot: workspace.getAttribute('data-namespace-root') || '',
    scope: workspace.dataset.scope || 'document',
    collection: workspace.dataset.readEpoch ? {
      epoch: workspace.dataset.readEpoch,
      nextChildren: workspace.dataset.nextChildren || null,
      nextSlots: workspace.dataset.nextSlots || null,
      childCount: Number(workspace.dataset.childCount),
      slotCount: Number(workspace.dataset.slotCount),
    } : null,
    kind: workspace.dataset.kind || (state === 'structural' ? 'namespace' : 'record'),
    label,
    description,
    lore: { lines: loreLines, text: description, head: label },
    childSummaries,
    semanticSlots,
    record,
    children,
    pagination: parseJournalPagination(workspace, path, children),
    version,
    state,
    writable: workspace.getAttribute('data-writable') === 'true',
    operations,
  };
}
