/** Versioned physical read transport, not a derived view or a complete record.
 * No request runs at import time. Callers must negotiate support separately;
 * failures never fall back to an ordinary, potentially unbounded debug read. */
export const PHYSICAL_RESPONSE_BYTES = 131072;
export const PHYSICAL_KEY_BYTES = 8192;
const ENDPOINT = '/debug-read/physical';
const AURAS = ['dm', 'dr', 'ds', 'f', 'r', 'rd', 'rs', 's', 'ta', 'ts', 'tu', 'u', 'w', 'x'];
const KINDS = new Set(['namespace', 'record', 'role', 'action', 'norm', 'sewn', 'template', 'event', 'http', 'behavior', 'module']);
const PAGE_FIELDS = ['version', 'resolution', 'pathKey', 'displayPath', 'epoch', 'collection', 'after', 'next', 'limit', 'total', 'complete', 'own', 'entries'];
const NODE_FIELDS = ['state', 'recordEpoch', 'children', 'fields', 'label', 'labelSource', 'help', 'helpSource', 'helpLine', 'kind'];
const PREVIEW_FIELDS = ['type', 'encoding', 'hex', 'total', 'complete'];
const REQUEST_FIELDS = ['pathKey', 'collection', 'epoch', 'after', 'limit'];
const STATUS = Object.freeze({invalid_query: 400, invalid_limit: 400, invalid_collection: 400, invalid_cursor: 400,
  epoch_required: 400, epoch_conflict: 409, derived_path: 422, path_missing: 404, record_missing: 404,
  record_deleted: 410, key_too_large: 422, read_failed: 500, response_too_large: 500});
const MAX_COUNTER = (1n << 256n) - 1n;
const encoder = new TextEncoder();
const requests = new WeakSet();
const pages = new WeakSet();

function invalid(message) { throw new TypeError('Invalid physical read: ' + message + '.'); }
function object(value, keys, exact = true) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      ![Object.prototype, null].includes(Object.getPrototypeOf(value))) invalid('expected a data object');
  const descriptors = Object.getOwnPropertyDescriptors(value);
  if (Reflect.ownKeys(descriptors).some(key => typeof key !== 'string' || !keys.includes(key) ||
      !Object.hasOwn(descriptors[key], 'value') || !descriptors[key].enumerable) ||
      (exact && keys.some(key => !Object.hasOwn(descriptors, key)))) invalid('unexpected or missing fields');
  return value;
}
function decimal(value, counter = false) {
  if (typeof value !== 'string' || value.length > 128 || !/^(?:0|[1-9][0-9]*)$/.test(value)) invalid('noncanonical decimal');
  if (counter && BigInt(value) > MAX_COUNTER) invalid('counter exceeds 256 bits');
  return value;
}
function display(value) {
  if (value === null) return null;
  // Presentation is never converted back into a path key or URL.
  if (typeof value !== 'string' || value.length > 1024 || !value.startsWith('/') || !value.isWellFormed() ||
      /[\u0000-\u001f\u007f]/.test(value) || encoder.encode(value).length > 1024) invalid('unsafe display spelling');
  return value;
}
function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}

/** Decode structural identity without lexical, Unicode, or Number coercion. */
export function decodePhysicalKey(key) {
  if (typeof key !== 'string' || key.length > PHYSICAL_KEY_BYTES || !/^v1(?:\/|$)/.test(key)) invalid('key encoding');
  if (key === 'v1') return Object.freeze([]);
  return Object.freeze(key.slice(3).split('/').map(segment => {
    const match = /^(dm|dr|ds|f|r|rd|rs|s|ta|ts|tu|u|w|x):((?:[0-9a-f]{2})*)$/.exec(segment);
    if (!match || match[2].endsWith('00')) invalid('noncanonical key segment');
    const [, aura, hex] = match;
    let payload = 0n;
    for (let index = hex.length - 2; index >= 0; index -= 2) payload = (payload << 8n) + BigInt(parseInt(hex.slice(index, index + 2), 16));
    return Object.freeze({aura, hex, payload});
  }));
}
function iotaLess(left, right) {
  if (left.aura !== right.aura) return AURAS.indexOf(left.aura) < AURAS.indexOf(right.aura);
  const a = left.payload, b = right.payload;
  if (a === b) return false;
  if (['ta', 'ts', 'tu'].includes(left.aura)) {
    // Minimal LE hex is a byte string, not its numeric atom ordering.
    const length = Math.min(left.hex.length, right.hex.length);
    for (let index = 0; index < length; index += 2) {
      const x = parseInt(left.hex.slice(index, index + 2), 16), y = parseInt(right.hex.slice(index, index + 2), 16);
      if (x !== y) return x < y;
    }
    return left.hex.length < right.hex.length;
  }
  if (left.aura === 's') {
    const negativeA = a % 2n === 1n, negativeB = b % 2n === 1n;
    return negativeA === negativeB ? negativeA ? b <= a : a <= b : negativeA;
  }
  if (left.aura === 'rs' || left.aura === 'rd') {
    const width = left.aura === 'rs' ? 32n : 64n, sign = 1n << (width - 1n), maximum = (1n << width) - 1n;
    // Native Sub saturates at zero. Do not reject overwidth raw payloads or
    // invent a total-order tie break: native strict lt is raw-neq && lte.
    const order = value => (value & sign) !== 0n ? value > maximum ? 0n : maximum - value : value + sign;
    return order(a) <= order(b);
  }
  return a <= b;
}
function keyLess(left, right) {
  for (let index = 0; index < Math.min(left.length, right.length); index++) {
    if (iotaLess(left[index], right[index])) return true;
    if (iotaLess(right[index], left[index])) return false;
  }
  return left.length < right.length;
}
/** Mirrors native lt_pith, including its raw IEEE overwidth semantics. */
export function physicalKeyLess(left, right) { return keyLess(decodePhysicalKey(left), decodePhysicalKey(right)); }
function key(value, collection = null) {
  const parts = decodePhysicalKey(value);
  if (collection === 'children' && parts.length !== 1) invalid('child cursor must contain exactly one iota');
  return value;
}

/** Construct a request from identities only. Null after differs from root v1. */
export function physicalRequest(options) {
  object(options, REQUEST_FIELDS, false);
  const {pathKey, collection, epoch = null, after = null, limit = 40} = options;
  key(pathKey);
  if (!['children', 'slots'].includes(collection)) invalid('collection');
  if (!Number.isInteger(limit) || limit < 1 || limit > 40) invalid('limit');
  if (epoch !== null) decimal(epoch);
  if (after !== null) { key(after, collection); if (epoch === null) invalid('continuation needs an epoch'); }
  // Validated keys contain only safe query alphabet letters/digits/:. Escaping
  // their separators would strand a maximal deep cursor beyond the URL budget.
  const params = ['pathKey=' + pathKey, 'collection=' + collection];
  if (epoch !== null) params.push('epoch=' + epoch);
  if (after !== null) params.push('after=' + after);
  if (limit !== 40) params.push('limit=' + limit);
  const query = params.join('&'), url = ENDPOINT + '?' + query;
  if (query.length > 32768) invalid('request exceeds the encoded query budget');
  const result = Object.freeze({pathKey, collection, epoch, after, limit, url});
  requests.add(result);
  return result;
}
function assertRequest(request) { if (!requests.has(request)) invalid('use physicalRequest to construct the request'); }
function preview(value, metadata = false) {
  object(value, ['type', 'encoding', 'hex', 'total', 'complete', 'pathKey', 'displayPath', 'reason'], false);
  if (value.type === 'text' || (!metadata && value.type === 'natural')) {
    object(value, PREVIEW_FIELDS);
    decimal(value.total, true);
    if (value.encoding !== 'hex' || typeof value.hex !== 'string' || value.hex.length > 512 || !/^(?:[0-9a-f]{2})*$/.test(value.hex)) invalid('scalar byte preview');
    const count = BigInt(value.hex.length / 2), total = BigInt(value.total);
    if (count !== (total < 256n ? total : 256n) || value.complete !== (count === total)) invalid('scalar preview completeness');
    if (value.complete && count > 0n && value.hex.endsWith('00')) invalid('complete scalar has a nonminimal high zero byte');
    return {type: value.type, encoding: 'hex', hex: value.hex, total: value.total, complete: value.complete};
  }
  if (!metadata && value.type === 'path') {
    object(value, ['type', 'pathKey', 'displayPath']); key(value.pathKey); display(value.displayPath);
    return {type: 'path', pathKey: value.pathKey, displayPath: value.displayPath};
  }
  if (!metadata && value.type === 'opaque') {
    object(value, ['type', 'reason']);
    if (!['unsupported_type', 'key_too_large'].includes(value.reason)) invalid('opaque value reason');
    return {type: 'opaque', reason: value.reason};
  }
  invalid('value preview type');
}
function node(value, epoch) {
  object(value, NODE_FIELDS);
  if (!['live', 'tombstone', 'unknown'].includes(value.state) || !KINDS.has(value.kind)) invalid('node state or kind');
  decimal(value.children, true);
  if (value.state === 'unknown') {
    if (value.recordEpoch !== null) invalid('unknown node has an assertion epoch');
  } else if (BigInt(decimal(value.recordEpoch, true)) > BigInt(epoch)) invalid('assertion is newer than the page');
  if (value.state === 'live') decimal(value.fields, true);
  else if (value.fields !== null || value.kind !== 'namespace' || value.label !== null || value.help !== null) invalid('non-live node has record metadata');
  const label = value.label === null ? null : preview(value.label, true);
  if (label === null ? value.labelSource !== null : !['lede', 'lore-head'].includes(value.labelSource)) invalid('label provenance');
  const help = value.help === null ? null : preview(value.help, true);
  if (help === null ? value.helpSource !== null || value.helpLine !== null :
      value.helpSource === 'help-text' ? value.helpLine !== null :
      value.helpSource !== 'lore-body' || !Number.isInteger(value.helpLine) || value.helpLine < 0 || value.helpLine > 3) invalid('help provenance');
  // Canonical field order makes immutable equality semantic, not dependent on
  // a valid JSON object's arbitrary member order.
  return {state: value.state, recordEpoch: value.recordEpoch, children: value.children, fields: value.fields,
    label, labelSource: value.labelSource, help, helpSource: value.helpSource, helpLine: value.helpLine, kind: value.kind};
}

/** Validate the untouched ordered response before any filtering or display. */
export function parsePhysicalPage(json, request) {
  assertRequest(request);
  object(json, PAGE_FIELDS);
  if (json.version !== 1 || json.resolution !== 'physical') invalid('protocol version or resolution');
  for (const field of ['pathKey', 'collection', 'after', 'limit']) if (json[field] !== request[field]) invalid('response request identity');
  decimal(json.epoch, true); decimal(json.total, true); display(json.displayPath);
  if (request.epoch !== null && json.epoch !== request.epoch) invalid('response epoch');
  if (!Array.isArray(json.entries) || Object.getPrototypeOf(json.entries) !== Array.prototype ||
      json.entries.length > request.limit || json.entries.length > 40 ||
      BigInt(json.entries.length) > BigInt(json.total)) invalid('entry count');
  const entryDescriptors = Object.getOwnPropertyDescriptors(json.entries);
  if (Reflect.ownKeys(entryDescriptors).length !== json.entries.length + 1 ||
      Array.from({length: json.entries.length}, (_, index) => entryDescriptors[index]).some(descriptor =>
        !descriptor || !Object.hasOwn(descriptor, 'value') || !descriptor.enumerable)) invalid('entries must be a dense JSON data array');
  if (json.next !== null) key(json.next, json.collection);
  if (typeof json.complete !== 'boolean' || json.complete !== (json.next === null)) invalid('collection completeness');
  const own = node(json.own, json.epoch);
  if (json.collection === 'children' ? own.children !== json.total : own.state !== 'live' || own.fields !== json.total) invalid('own collection total');
  let previous = request.after;
  const seen = new Set();
  const entries = json.entries.map(entry => {
    object(entry, json.collection === 'children' ? ['key', 'displayKey', 'node'] : ['key', 'displayKey', 'value']);
    key(entry.key, json.collection); display(entry.displayKey);
    if (seen.has(entry.key) || (previous !== null && !physicalKeyLess(previous, entry.key)) ||
        (request.after !== null && !physicalKeyLess(request.after, entry.key))) invalid('duplicate or unordered entries');
    seen.add(entry.key); previous = entry.key;
    return json.collection === 'children' ? {...entry, node: node(entry.node, json.epoch)} : {...entry, value: preview(entry.value)};
  });
  if (json.next !== null && (!entries.length || json.next !== entries.at(-1).key || BigInt(entries.length) >= BigInt(json.total))) invalid('continuation must be the last included key');
  if (request.after === null && json.complete && BigInt(entries.length) !== BigInt(json.total)) invalid('initial complete page omitted entries');
  if (entries.reduce((bytes, entry) => bytes + encoder.encode(JSON.stringify(entry)).length + 1, 0) > 98304) invalid('entries exceed their byte budget');
  if (encoder.encode(JSON.stringify(json)).length > PHYSICAL_RESPONSE_BYTES) invalid('response exceeds byte budget');
  const result = freeze({...json, own, entries});
  pages.add(result);
  return result;
}

/** An immutable loaded collection, not a wire page. Never serialize it as one.
 * Old state remains usable if validation/conflict fails; no dedup or re-sort. */
export function mergePhysicalPages(current, next) {
  if (!pages.has(current) || !pages.has(next)) invalid('merge needs parsed pages');
  if (current.complete || current.next === null || next.after !== current.next) invalid('noncontiguous continuation');
  for (const field of ['pathKey', 'epoch', 'collection', 'limit', 'total']) if (current[field] !== next[field]) invalid('mixed collection identity or epoch');
  if (JSON.stringify(current.own) !== JSON.stringify(next.own) || current.displayPath !== next.displayPath) invalid('node changed within an epoch');
  const entries = [...current.entries, ...next.entries];
  if (BigInt(entries.length) > BigInt(current.total) || new Set(entries.map(entry => entry.key)).size !== entries.length ||
      (current.entries.length && next.entries.length && !physicalKeyLess(current.entries.at(-1).key, next.entries[0].key)) ||
      (current.after === null && next.complete && BigInt(entries.length) !== BigInt(current.total))) invalid('invalid merged collection');
  const result = freeze({...current, next: next.next, complete: next.complete, entries});
  pages.add(result);
  return result;
}

export class PhysicalReadError extends Error {
  constructor(code, status) {
    super(code === 'epoch_conflict' ? 'The namespace changed. Refresh this collection before continuing.' : 'Physical read failed: ' + code + '.');
    this.name = 'PhysicalReadError'; this.code = code; this.status = status;
  }
}
export function parsePhysicalError(json, status) {
  object(json, ['version', 'error']);
  if (json.version !== 1 || typeof json.error !== 'string' || !Object.hasOwn(STATUS, json.error) || STATUS[json.error] !== status) invalid('error envelope or HTTP status');
  return new PhysicalReadError(json.error, status);
}

async function boundedJSON(response, signal) {
  if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get('content-type') || '')) {
    await response.body?.cancel().catch(() => {}); invalid('expected JSON content type');
  }
  const reader = response.body?.getReader();
  if (!reader) invalid('missing response body');
  const cancel = () => { void reader.cancel(signal.reason).catch(() => {}); };
  signal.addEventListener('abort', cancel, {once: true});
  const chunks = []; let length = 0;
  try {
    while (true) {
      signal.throwIfAborted();
      const {done, value} = await reader.read();
      if (done) { signal.throwIfAborted(); break; }
      length += value.byteLength;
      if (length > PHYSICAL_RESPONSE_BYTES) invalid('response exceeds byte budget');
      chunks.push(value);
    }
  } catch (error) { await reader.cancel().catch(() => {}); throw error; }
  finally { signal.removeEventListener('abort', cancel); reader.releaseLock(); }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes)); }
  catch { invalid('malformed UTF-8 or JSON'); }
}

/** Explicit read only; no fallback, cache, retries, prefetch or capability probe. */
export async function fetchPhysicalPage(request, {signal, fetch: fetcher = globalThis.fetch} = {}) {
  assertRequest(request); signal?.throwIfAborted();
  const timeout = AbortSignal.timeout(20000);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const destination = globalThis.location ? new URL(request.url, globalThis.location.origin).href : request.url;
  const response = await fetcher(destination, {method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    headers: {Accept: 'application/json'}, signal: combined});
  if (response.redirected) { await response.body?.cancel().catch(() => {}); invalid('redirected response'); }
  if (response.ok && response.status !== 200) { await response.body?.cancel().catch(() => {}); invalid('expected HTTP 200 success'); }
  const json = await boundedJSON(response, combined);
  if (!response.ok) throw parsePhysicalError(json, response.status);
  return parsePhysicalPage(json, request);
}
