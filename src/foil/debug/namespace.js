/**
 * Read-only bridge to Shrine's server-rendered namespace explorer.
 *
 * Local data cases are not sovereign epochs. Live reads freeze one reported
 * /top through an e<epoch> history route before walking the answer; historical
 * reads use exactly the requested (path, care, case). Slot keys never become
 * child paths. No source HTML is inserted into the active document.
 */
import { parseJournalPagination } from './journal.js';
import { parseValueMetadata } from './values.js';

const CARES = new Set(['x', 'y', 'z']);
const VERSION_FIELDS = new Set([
  'x_data', 'x_shape', 'y_data', 'y_shape', 'z_data', 'z_shape',
  'top', 'first', 'now', 'block', 'state',
]);
const MAX_NODES = 120;
const CONCURRENCY = 4;
const REQUEST_TIMEOUT_MS = 20_000;

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

function debugURL(path) {
  return '/debug' + (path === '/' ? '' : '/' + segmentsOf(path).map(encodeURIComponent).join('/'));
}

function joinPath(parent, suffix) {
  return pathOf((parent === '/' ? '' : parent) + '/' + suffix.replace(/^\//, ''));
}

function relativeTo(path, parent) {
  if (path === parent) return '';
  const prefix = parent === '/' ? '/' : parent + '/';
  return path.startsWith(prefix) ? path.slice(prefix.length) : null;
}

function escaped(text) {
  return text.replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
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
    // Compatibility field only: escaped text, never executable source markup.
    html: escaped(text),
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
  const record = myth ? { path, sourcePath: path, state: 'live', slots } : null;
  const documentationCards = [...doc.querySelectorAll('#debug-main section[aria-label="Documentation"] ui-card')];
  const help = slots.find(slot => slot.key === '/sys/help');
  const lede = slots.find(slot => slot.key === '/sys/lede');
  const label = labelOf(path, lede?.kind === 'text' ? lede.text : workspace.dataset.label);
  const loreLines = documentationCards.flatMap(card =>
    [...card.querySelectorAll('.lore-line')].map(line => line.textContent));
  // Older running kernels sent a generic description attribute and omitted
  // plain-text help from Documentation. Read the actual slot instead, so a
  // frontend refresh can recover authored content without restarting state.
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
  const historyLinks = [...doc.querySelectorAll('ui-table[label="version"] a[href]')]
    .map(namespaceLink).filter(Boolean).filter(link => /^\/h\/[xyz]\//.test(link.path));
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
    renderURL: workspace.dataset.renderUrl || '/ns' + (path === '/' ? '' : '/' + path.split('/').filter(Boolean).map(encodeURIComponent).join('/')),
    childSummaries,
    semanticSlots,
    historyLinks,
    sourcePath: path,
    record,
    records: record ? [record] : [],
    children,
    pagination: parseJournalPagination(workspace, path, children),
    version,
    state,
    writable: workspace.getAttribute('data-writable') === 'true' && !/^\/log(?:\/|$)/.test(path),
    documentation: documentationCards.map(card => card.textContent.trim()).filter(Boolean)
      .concat(!documentationCards.length && description ? [description] : []),
    operations,
  };
}

async function readDocument(path, signal) {
  signal?.throwIfAborted();
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
  try {
    const response = await fetch(debugURL(path), {
      method: 'GET', credentials: 'same-origin', cache: 'no-store', signal: requestSignal,
      headers: { Accept: 'text/html' },
    });
    if (!response.ok) throw new Error(`Namespace read failed (${response.status}) at ${path}.`);
    const type = response.headers.get('content-type') || '';
    if (!type.includes('text/html')) throw new Error(`Expected an HTML namespace response at ${path}.`);
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    return parseDebugDocument(doc, path);
  } catch (error) {
    // Preserve user/navigation cancellation instead of misreporting it as a
    // runtime failure when cancellation and the timeout happen together.
    signal?.throwIfAborted();
    if (timeout.aborted) {
      throw new Error(`Namespace read timed out after 20 seconds at ${path}. Retry or narrow the path or scope.`, { cause: error });
    }
    throw error;
  }
}

async function readVersion(path, signal) {
  const segments = segmentsOf(path);
  const view = await readDocument('/h/v/' + segments.length + (segments.length ? '/' + segments.join('/') : ''), signal);
  return versionFromEntries((view.record?.slots || []).map(slot => [slot.key, slot.text]));
}

function scopePath(path, care, mark) {
  const segments = segmentsOf(path);
  return '/h/' + care + '/' + mark + '/' + segments.length + (segments.length ? '/' + segments.join('/') : '');
}

function derivedPath(path) {
  return /^\/(?:h|o|x)(?:\/|$)/.test(path);
}

/**
 * Return a bounded namespace snapshot. `version` and `latestCase` describe the
 * initial LIVE metadata read, including when `caseNumber` selects history.
 * `pinnedEpoch` is not a data case. Null counters remain unavailable, not zero.
 * Historical tombstones and unknowns both render as empty HTML; this API does
 * not pretend to distinguish those without explicit live version metadata.
 * `onProgress({visitedCount, recordCount, queuedCount, limit})` runs after each
 * completed traversal batch. Callback errors do not invalidate namespace data.
 * Every HTTP request has a 20-second timeout, including reading its body.
 */
export async function readSnapshot({ path = '/', care = 'y', caseNumber = null, signal, maxNodes = 100, onProgress } = {}) {
  path = pathOf(path);
  if (!CARES.has(care)) throw new TypeError('Care must be x, y, or z.');
  if (caseNumber !== null && (!Number.isSafeInteger(caseNumber) || caseNumber < 1)) {
    throw new TypeError('A historical case must be a positive safe integer.');
  }
  const limit = Math.min(MAX_NODES, Math.max(1, Number.isFinite(maxNodes) ? Math.floor(maxNodes) : 100));
  const initial = await readDocument(path, signal);
  const derived = derivedPath(path);
  const version = initial.version || (!derived ? await readVersion(path, signal) : null);
  const latestCase = Number.isSafeInteger(version?.[care + '_data']) && version[care + '_data'] > 0
    ? version[care + '_data'] : null;
  if (caseNumber !== null && latestCase !== null && caseNumber > latestCase) {
    throw new RangeError(`${care.toUpperCase()} case ${caseNumber} has not been minted at ${path}.`);
  }
  if (caseNumber !== null && derived) {
    throw new Error('This derived view does not expose a local case ledger. Navigate its existing historical address directly.');
  }

  const warnings = [];
  let pinnedEpoch = null;
  let sourcePath = path;
  let coherent = false;
  let root = initial;
  if (caseNumber !== null) {
    sourcePath = scopePath(path, care, caseNumber);
    root = await readDocument(sourcePath, signal);
    coherent = true;
  } else if (!derived) {
    const epochVersion = version?.top ? version : await readVersion('/', signal);
    if (Number.isSafeInteger(epochVersion?.top) && epochVersion.top > 0) {
      pinnedEpoch = epochVersion.top;
      // Runtime y/z reads require a record at the anchor. A structural anchor
      // can still be read coherently by dipping the sovereign root's z answer.
      sourcePath = !initial.record && care !== 'x'
        ? joinPath(scopePath('/', 'z', 'e' + pinnedEpoch), path)
        : scopePath(path, care, 'e' + pinnedEpoch);
      root = await readDocument(sourcePath, signal);
      coherent = true;
    } else {
      warnings.push('The runtime supplied no epoch pin; this view may change while it is read.');
    }
  } else {
    // /h case/epoch projections are stable; /h/v and computed overlays are not.
    coherent = /^\/h\/[xyz]\/(?:e)?[1-9]\d*\/\d+(?:\/|$)/.test(path);
    if (!coherent) warnings.push('This derived view has no exposed snapshot clock; it is read without a coherence guarantee.');
  }

  const records = [];
  const structuralPaths = [];
  const unknownPaths = [];
  const visited = new Set();
  let frontier = [{ sourcePath, result: root }];
  let truncated = false;
  const toLogicalPath = candidate => {
    const relative = relativeTo(candidate, sourcePath);
    return relative === null ? null : relative ? joinPath(path, relative) : path;
  };

  while (frontier.length) {
    signal?.throwIfAborted();
    if (visited.size >= limit) {
      truncated = true;
      break;
    }
    const batch = [];
    while (frontier.length && batch.length < CONCURRENCY && visited.size < limit) {
      const item = frontier.shift();
      if (visited.has(item.sourcePath)) continue;
      visited.add(item.sourcePath);
      batch.push(item);
    }
    const pages = await Promise.all(batch.map(async item => ({
      ...item,
      result: item.result || await readDocument(item.sourcePath, signal),
    })));
    for (const { sourcePath: fetchedPath, result } of pages) {
      const logicalPath = toLogicalPath(fetchedPath);
      if (!logicalPath) continue;
      if (result.record) {
        records.push({ ...result.record, path: logicalPath, sourcePath: fetchedPath });
      } else if (result.children.length) {
        structuralPaths.push(logicalPath);
      } else {
        unknownPaths.push(logicalPath);
      }
      // The y frontier stops at a live descendant, never at a structural path.
      const descend = care === 'z' || (care === 'y' && (logicalPath === path || !result.record));
      if (!descend) continue;
      for (const child of result.children) {
        if (toLogicalPath(child) !== null && !visited.has(child)) frontier.push({ sourcePath: child });
      }
    }
    if (typeof onProgress === 'function') {
      try {
        const reported = onProgress({
          visitedCount: visited.size,
          recordCount: records.length,
          queuedCount: frontier.length,
          limit,
        });
        // A UI callback may be async, but its rendering must not delay reads
        // or produce an unhandled rejection that masks a valid snapshot.
        Promise.resolve(reported).catch(() => {});
      } catch {
        // Progress is advisory. The completed namespace read remains valid.
      }
    }
  }
  if (truncated) warnings.push(`Only the first ${limit} namespace paths were read. Narrow the path or scope to inspect the remainder.`);
  // x has no children by definition, but the initial live document can still
  // identify its anchor as structural. Keep that distinction without inventing
  // a record or borrowing an ancestor's local clocks.
  if (caseNumber === null && care === 'x' && !root.record && initial.state === 'structural') {
    structuralPaths.push(path);
    const unknownIndex = unknownPaths.indexOf(path);
    if (unknownIndex !== -1) unknownPaths.splice(unknownIndex, 1);
  }
  const state = records.some(record => record.path === path) ? 'live'
    : caseNumber === null && version?.state === 'tombstone' ? 'tombstone'
      : structuralPaths.includes(path) ? 'structural' : 'unknown';
  if (state === 'unknown' && caseNumber !== null) {
    warnings.push('The runtime returns the same empty view for an unknown name and a historical tombstone.');
  }
  return {
    path, care, caseNumber, latestCase, version, versionSource: 'live',
    records, structuralPaths, unknownPaths, truncated, sourcePath, pinnedEpoch,
    coherent, state, warnings, visitedCount: visited.size,
    writable: caseNumber === null && initial.writable,
    documentation: root.documentation,
    operations: caseNumber === null ? initial.operations : [],
  };
}
