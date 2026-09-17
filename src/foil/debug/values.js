/** Exact, bounded inspection of physical typed values. Pretty output is never
 * evidence of completeness; only the runtime's explicit contract is trusted. */
export const VALUE_WINDOW_BYTES = 4096n;
const ORIGIN = 'http://debug.invalid';
const REASONS = new Set(['byte-limit', 'numeric-summary', 'semantic-summary', 'unsupported-representation', 'non-text-bytes']);
const REPRESENTATIONS = new Set(['utf8-bytes', 'natural-le-bytes']);
const PARAMETERS = ['path', 'slot', 'epoch', 'offset', 'limit'];
const CHUNK_FIELDS = ['version', 'path', 'slot', 'epoch', 'recordEpoch', 'type', 'representation', 'encoding', 'total', 'offset', 'next', 'complete', 'hex'];

function decimal(value) {
  if (typeof value !== 'string' || !/^(0|[1-9]\d*)$/.test(value)) throw new Error('Invalid value byte address.');
  return value;
}
function address(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || /[\u0000-\u001f\u007f]/.test(value) ||
    (value !== '/' && value.split('/').slice(1).some(part => !part || part === '.' || part === '..'))) {
    throw new Error('Invalid value path.');
  }
  return value;
}
function endpoint(value, metadata) {
  if (typeof value !== 'string' || value.split('?')[0] !== '/debug-read/value' ||
    !value.split('?')[1]?.split('&').every(part => part && part.includes('=')) || /[\s\\]/.test(value)) {
    throw new Error('Invalid value read endpoint.');
  }
  const url = new URL(value, ORIGIN);
  if (url.origin !== ORIGIN || url.pathname !== '/debug-read/value' || url.hash ||
    [...url.searchParams.keys()].length !== PARAMETERS.length ||
    PARAMETERS.some(key => url.searchParams.getAll(key).length !== 1) ||
    [...url.searchParams.keys()].some(key => !PARAMETERS.includes(key))) throw new Error('Invalid value read endpoint.');
  const params = url.searchParams;
  if (params.get('path') !== metadata.path || params.get('slot') !== metadata.slot ||
    params.get('epoch') !== metadata.epoch || params.get('offset') !== '0' ||
    BigInt(decimal(params.get('limit'))) < 1n || BigInt(params.get('limit')) > 65536n ||
    /^\/(?:h|o|x)(?:\/|$)/.test(metadata.path)) throw new Error('Value read identity does not match its slot.');
  return url;
}

export function parseValueMetadata(limb, recordPath, slotKey) {
  const data = limb.dataset;
  const result = {state: 'unknown', reason: null, bytes: null, previewBytes: null, epoch: null,
    representation: null, url: null, path: address(recordPath), slot: address(slotKey)};
  const names = ['valueState', 'valueReason', 'previewReason', 'valueBytes', 'valuePreviewBytes', 'valueEpoch', 'valueRepresentation', 'valueUrl'];
  if (!names.some(name => data[name] !== undefined)) return result;
  if (!['complete', 'preview', 'opaque'].includes(data.valueState)) throw new Error('Invalid value fidelity state.');
  result.state = data.valueState;
  result.reason = data.previewReason || null;
  if ((result.state === 'complete' && result.reason !== null) ||
    (result.state !== 'complete' && !REASONS.has(result.reason))) throw new Error('Invalid value preview reason.');
  for (const [field, attribute] of [['bytes', 'valueBytes'], ['previewBytes', 'valuePreviewBytes'], ['epoch', 'valueEpoch']]) {
    result[field] = data[attribute] ? decimal(data[attribute]) : null;
  }
  result.representation = data.valueRepresentation || null;
  if (result.representation && !REPRESENTATIONS.has(result.representation)) throw new Error('Unknown value representation.');
  if (result.previewBytes !== null && (result.bytes === null || BigInt(result.previewBytes) > BigInt(result.bytes))) {
    throw new Error('Invalid value preview length.');
  }
  if (data.valueUrl) {
    if (result.state === 'opaque') throw new Error('An opaque summary cannot advertise exact inspection.');
    if (result.bytes === null || result.epoch === null || !result.representation) throw new Error('Incomplete value read identity.');
    const url = endpoint(data.valueUrl, result);
    result.url = url.pathname + url.search;
  }
  return result;
}

/** Bind a rendered limb's explicit read contract without interpreting its
 * displayed value or looking up a second copy in the document descriptor. */
export function valueBinding(limb, recordPath) {
  const key = limb.dataset.key;
  if (!key) return null;
  let fidelity;
  try { fidelity = parseValueMetadata(limb, recordPath, key); }
  catch { fidelity = {state: 'unknown'}; }
  return {key, fidelity};
}

export function valueWindowURL(metadata, start = '0') {
  if (!metadata.url || metadata.bytes === null) throw new Error('Exact inspection is unavailable for this value.');
  const url = endpoint(metadata.url, metadata);
  const total = BigInt(decimal(metadata.bytes));
  const beginning = BigInt(decimal(start));
  if (beginning > total) throw new Error('Value window starts past the end.');
  const end = beginning + VALUE_WINDOW_BYTES < total ? beginning + VALUE_WINDOW_BYTES : total;
  const context = metadata.representation === 'utf8-bytes' ? 3n : 0n;
  const offset = beginning > context ? beginning - context : 0n;
  const ending = end + context < total ? end + context : total;
  const limit = Math.max(1, Number(ending - offset));
  url.searchParams.set('offset', String(offset));
  url.searchParams.set('limit', String(limit));
  return {url: url.pathname + url.search, path: metadata.path, slot: metadata.slot, epoch: metadata.epoch,
    representation: metadata.representation, total: metadata.bytes, offset: String(offset), limit,
    start, end: String(end)};
}

export function parseValueChunk(json, request) {
  if (!json || typeof json !== 'object' || Array.isArray(json) ||
    Object.keys(json).length !== CHUNK_FIELDS.length || CHUNK_FIELDS.some(key => !Object.hasOwn(json, key)) ||
    json.version !== 1 || json.encoding !== 'hex' ||
    json.type !== (request.representation === 'utf8-bytes' ? 'text' : 'natural')) throw new Error('Invalid value response schema.');
  for (const key of ['path', 'slot', 'epoch', 'representation', 'total', 'offset']) {
    if (json[key] !== request[key]) throw new Error('Value response does not match the requested version and byte window.');
  }
  const total = BigInt(decimal(json.total)), offset = BigInt(decimal(json.offset));
  if (BigInt(decimal(json.recordEpoch)) > BigInt(decimal(json.epoch)) || offset > total ||
    !Number.isInteger(request.limit) || request.limit < 1 || request.limit > 65536) throw new Error('Invalid value response bounds.');
  if (typeof json.hex !== 'string' || json.hex.length > request.limit * 2 || !/^(?:[0-9a-f]{2})*$/.test(json.hex)) {
    throw new Error('Invalid value byte encoding.');
  }
  const length = BigInt(json.hex.length / 2);
  if (length !== (total - offset < BigInt(request.limit) ? total - offset : BigInt(request.limit))) {
    throw new Error('The runtime returned an incomplete byte window.');
  }
  const next = offset + length < total ? String(offset + length) : null;
  if (json.next !== next || json.complete !== (next === null)) throw new Error('Invalid value continuation.');
  const bytes = Uint8Array.from(json.hex.match(/../g) || [], byte => parseInt(byte, 16));
  return {...json, bytes};
}

function sequenceLength(byte) {
  if (byte < 0x80) return 1;
  if (byte >= 0xc2 && byte <= 0xdf) return 2;
  if (byte >= 0xe0 && byte <= 0xef) return 3;
  if (byte >= 0xf0 && byte <= 0xf4) return 4;
  throw new Error('Not UTF-8.');
}
function hexText(bytes) {
  const lines = [];
  for (let index = 0; index < bytes.length; index += 16) {
    lines.push([...bytes.slice(index, index + 16)].map(byte => byte.toString(16).padStart(2, '0')).join(' '));
  }
  return lines.join('\n');
}

/** A character belongs to the window containing its leading byte. Context
 * permits a four-byte UTF-8 sequence to cross a window without replacement.
 * The returned bytes always contain ONLY the exact logical byte window. */
export function renderValueWindow(chunk, request) {
  const first = Number(BigInt(request.start) - BigInt(request.offset));
  const last = Number(BigInt(request.end) - BigInt(request.offset));
  const bytes = chunk.bytes.slice(first, last);
  const base = {bytes, start: request.start, end: request.end};
  if (request.representation === 'utf8-bytes') {
    try {
      const decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true});
      let beginning = first;
      if (beginning < chunk.bytes.length && (chunk.bytes[beginning] & 0xc0) === 0x80) {
        let lead = beginning;
        while (lead > 0 && (chunk.bytes[lead] & 0xc0) === 0x80) lead--;
        const length = sequenceLength(chunk.bytes[lead]);
        if (lead + length <= beginning || lead + length > chunk.bytes.length) throw new Error('Invalid UTF-8 boundary.');
        decoder.decode(chunk.bytes.slice(lead, lead + length));
        beginning = lead + length;
      }
      let ending = beginning;
      while (ending < last) {
        const length = sequenceLength(chunk.bytes[ending]);
        if (ending + length > chunk.bytes.length) throw new Error('Incomplete UTF-8 boundary.');
        ending += length;
      }
      const text = decoder.decode(chunk.bytes.slice(beginning, ending));
      if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)) throw new Error('Non-printing bytes.');
      return {...base, text, format: 'utf8'};
    } catch { /* Preserve invalid/non-printing bytes visibly as hex. */ }
  }
  return {...base, text: hexText(bytes), format: 'hex'};
}
