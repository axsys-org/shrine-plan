// Grove authors both the inspection fragment and this bounded read descriptor.
// Presentation is never parsed back into records, values, lore or operations.
import {parseJournalPagination} from './journal.js';

const DECIMAL = /^(?:0|[1-9][0-9]*)$/;
const SCOPES = new Set(['document', 'workspace', 'outline', 'preview']);
const STATES = new Set(['live', 'structural', 'tombstone', 'unknown']);
const FIELDS = ['version', 'path', 'namespaceRoot', 'scope', 'kind', 'glyph', 'label', 'description',
  'state', 'hasRecord', 'writable', 'children', 'collection', 'pagination', 'previewSlots'];

function invalid() { throw new Error('The runtime returned an invalid Grove read descriptor.'); }
function object(value, fields) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== fields.length || fields.some(key => !Object.hasOwn(value, key))) invalid();
}
function text(value) { if (typeof value !== 'string') invalid(); return value; }
function decimal(value) { if (typeof value !== 'string' || !DECIMAL.test(value)) invalid(); return value; }
function pathOf(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || /[\u0000-\u001f\u007f]/.test(value) ||
      (value !== '/' && value.split('/').slice(1).some(part => !part || part === '.' || part === '..'))) invalid();
  return value;
}
function summary(value) {
  text(value.kind); text(value.label); text(value.description);
  // These are semantic Mash registry names, never URLs or application SVGs.
  if (typeof value.glyph !== 'string' || !/^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$/.test(value.glyph)) invalid();
}

/** The template is inert escaped text, independent of custom-element upgrade
 * and of the structure or wording of the visible Grove fragment. */
export function parseDebugDocument(doc) {
  const workspace = doc.querySelector('#debug-workspace');
  if (!workspace) throw new Error('The runtime did not return a namespace debug document.');
  const templates = workspace.querySelectorAll(':scope > template#debug-read-descriptor');
  if (templates.length !== 1) throw new Error('Missing Grove read descriptor.');
  if (templates[0].content.childElementCount) invalid();
  let value;
  try { value = JSON.parse(templates[0].content.textContent); }
  catch { invalid(); }
  object(value, FIELDS);
  if (value.version !== 1 || pathOf(value.path) !== pathOf(workspace.getAttribute('data-path')) ||
      !SCOPES.has(value.scope) || !STATES.has(value.state) ||
      typeof value.hasRecord !== 'boolean' || typeof value.writable !== 'boolean') invalid();
  if (value.hasRecord !== (value.state === 'live')) invalid();
  if (value.namespaceRoot !== '') pathOf(value.namespaceRoot);
  summary(value);

  if (!Array.isArray(value.children) || value.children.length > 40) invalid();
  const seen = new Set();
  const prefix = value.path === '/' ? '/' : value.path + '/';
  for (const child of value.children) {
    object(child, ['path', 'label', 'description', 'kind', 'glyph']);
    const path = pathOf(child.path);
    if (!path.startsWith(prefix) || !path.slice(prefix.length) || path.slice(prefix.length).includes('/') || seen.has(path)) invalid();
    seen.add(path); summary(child);
  }
  const children = value.children.map(child => child.path);
  object(value.collection, ['epoch', 'nextChildren', 'nextSlots', 'childCount', 'slotCount']);
  const collection = value.collection;
  decimal(collection.childCount); decimal(collection.slotCount);
  if (BigInt(collection.childCount) < BigInt(children.length)) invalid();
  if (collection.epoch !== null) decimal(collection.epoch);
  for (const cursor of [collection.nextChildren, collection.nextSlots]) {
    if (cursor !== null && (typeof cursor !== 'string' || !cursor || collection.epoch === null)) invalid();
  }

  if (!Array.isArray(value.previewSlots) || value.previewSlots.length > 3 ||
      BigInt(value.previewSlots.length) > BigInt(collection.slotCount)) invalid();
  const slots = new Set();
  for (const slot of value.previewSlots) {
    object(slot, ['key', 'text', 'reference']);
    pathOf(slot.key); text(slot.text);
    if (slots.has(slot.key) || new TextEncoder().encode(slot.text).length > 180) invalid();
    slots.add(slot.key);
    if (slot.reference !== null) pathOf(slot.reference);
  }
  if (!value.hasRecord && value.previewSlots.length) invalid();
  const pagination = parseJournalPagination(value.pagination, value.path, children);
  if (pagination && collection.childCount !== pagination.total) invalid();
  return {
    path: value.path, namespaceRoot: value.namespaceRoot, scope: value.scope,
    kind: value.kind, glyph: value.glyph, label: value.label, description: value.description,
    state: value.state, hasRecord: value.hasRecord, writable: value.writable,
    children, childSummaries: value.children, collection, pagination, previewSlots: value.previewSlots,
  };
}
