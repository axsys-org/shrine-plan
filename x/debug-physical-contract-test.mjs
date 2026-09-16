// Pure production-adapter regression. No browser, live endpoint, namespace
// mutation or unprovided fetch is permitted. Real HTTP artifacts are an
// additional explicit bridge, never synthesized to satisfy the parser.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const root = fileURLToPath(new URL('..', import.meta.url));
const source = await readFile(resolve(root, 'src/foil/debug/physical.js'), 'utf8');
const originalFetch = globalThis.fetch;
let unexpectedFetches = 0;
globalThis.fetch = async () => { unexpectedFetches++; throw new Error('No live fetch is permitted in this suite.'); };
const api = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const {physicalRequest, decodePhysicalKey, physicalKeyLess, parsePhysicalPage, mergePhysicalPages,
  parsePhysicalError, fetchPhysicalPage, PhysicalReadError, PHYSICAL_RESPONSE_BYTES} = api;
let checks = 0;
const check = (name, test) => { test(); checks++; };
const fails = (name, test) => check(name, () => assert.throws(test, TypeError, name));
const clone = value => JSON.parse(JSON.stringify(value));
const atom = (aura, number = 0n) => {
  let hex = ''; for (let value = BigInt(number); value; value >>= 8n) hex += Number(value & 255n).toString(16).padStart(2, '0');
  return 'v1/' + aura + ':' + hex;
};
const symbol = name => 'v1/ts:' + Buffer.from(name).toString('hex');
const text = value => ({type: 'text', encoding: 'hex', hex: Buffer.from(value).subarray(0, 256).toString('hex'),
  total: String(Buffer.byteLength(value)), complete: Buffer.byteLength(value) <= 256});
const node = (overrides = {}) => ({state: 'live', recordEpoch: '5', children: '3', fields: '8', label: text('Authored title'),
  labelSource: 'lede', help: text('One authored body line'), helpSource: 'lore-body', helpLine: 2, kind: 'record', ...overrides});
const request = physicalRequest({pathKey: symbol('app'), collection: 'children', epoch: '9007199254741999', limit: 2});
const child = (number, overrides = {}) => ({key: atom('u', number), displayKey: '/' + number,
  node: node({children: '0'}), ...overrides});
const wire = (overrides = {}) => ({version: 1, resolution: 'physical', pathKey: request.pathKey, displayPath: '/app', epoch: request.epoch,
  collection: 'children', after: null, next: atom('u', 2), limit: 2, total: '3', complete: false,
  own: node(), entries: [child(1), child(2)], ...overrides});
const response = (value, status = 200) => new Response(typeof value === 'string' ? value : JSON.stringify(value), {
  status, headers: {'content-type': 'application/json; charset=utf-8'},
});

try {
  check('import never reads', () => assert.equal(unexpectedFetches, 0));
  check('root differs from zero atom', () => {
    assert.deepEqual(decodePhysicalKey('v1'), []);
    assert.equal(decodePhysicalKey('v1/u:')[0].payload, 0n);
  });
  for (const aura of ['dm', 'dr', 'ds', 'f', 'r', 'rd', 'rs', 's', 'ta', 'ts', 'tu', 'u', 'w', 'x']) {
    check('all raw aura payloads: ' + aura, () => {
      const value = (1n << 256n) + 256n;
      assert.deepEqual(decodePhysicalKey(atom(aura, value))[0], {aura, hex: atom(aura, value).split(':')[1], payload: value});
    });
  }
  for (const key of ['', 'v0', 'V1', 'v1/', '/v1', 'v1//u:01', 'v1/u:01/', 'v1/u', 'v1/u::01',
    'v1/:01', 'v1/U:01', 'v1/ud:01', 'v1/u:0', 'v1/u:0A', 'v1/u:gg', 'v1/u: 1',
    'v1/u:00', 'v1/u:0100', 'v1/u:%30%31', 'v1/u:01?x', 'v1/tu:00']) fails('reject key ' + key, () => decodePhysicalKey(key));
  const maximumKey = atom('tu', 1n << 32736n);
  check('exact key byte limit', () => { assert.equal(maximumKey.length, 8192); assert.equal(decodePhysicalKey(maximumKey).length, 1); });
  fails('key above byte limit', () => decodePhysicalKey(maximumKey + '0'));
  check('deep keys have no artificial depth limit', () => assert.equal(decodePhysicalKey('v1' + '/u:'.repeat(2730)).length, 2730));
  fails('aggregate deep key budget', () => decodePhysicalKey('v1' + '/u:'.repeat(2731)));
  check('control/slash bytes remain structural', () => assert.equal(decodePhysicalKey('v1/tu:41002f41')[0].payload, 0x412f0041n));
  const ordered = list => {
    for (let i = 1; i < list.length; i++) { assert.equal(physicalKeyLess(list[i - 1], list[i]), true); assert.equal(physicalKeyLess(list[i], list[i - 1]), false); }
    for (const key of list) assert.equal(physicalKeyLess(key, key), false);
  };
  check('native aura rank', () => ordered(['dm', 'dr', 'ds', 'f', 'r', 'rd', 'rs', 's', 'ta', 'ts', 'tu', 'u', 'w', 'x'].map(tag => atom(tag))));
  for (const aura of ['ta', 'ts', 'tu']) check('native byte lexical ' + aura, () => ordered(['', 'a', 'aa', 'b'].map(value => 'v1/' + aura + ':' + Buffer.from(value).toString('hex'))));
  check('native signed zigzag', () => ordered([9n, 3n, 1n, 0n, 2n, 4n, 10n].map(value => atom('s', value))));
  check('native numeric not rendered order', () => ordered([0n, 2n, 9n, 10n, 256n, 1n << 256n].map(value => atom('u', value))));
  check('native rs IEEE order', () => ordered([0xff800000n, 0xbf800000n, 0x80000000n, 0n, 0x3f800000n, 0x7f800000n, 0x7fc00001n].map(value => atom('rs', value))));
  check('native rd IEEE order', () => ordered([0xfff0000000000000n, 0xbff0000000000000n, 0x8000000000000000n, 0n, 0x3ff0000000000000n, 0x7ff0000000000000n, 0x7ff8000000000001n].map(value => atom('rd', value))));
  for (const [aura, width] of [['rs', 32n], ['rd', 64n]]) check('native saturating overwidth ' + aura, () => {
    const a = atom(aura, (1n << width) + (1n << (width - 1n))), b = atom(aura, (1n << width) + (1n << (width - 1n)) + 1n);
    assert.equal(physicalKeyLess(a, b), true); assert.equal(physicalKeyLess(b, a), true);
    assert.equal(physicalKeyLess(a, a), false);
  });
  check('native opaque path prefix ordering', () => ordered(['v1', symbol('a'), symbol('a') + '/ts:62', symbol('b')]));

  check('request identity never uses display strings', () => {
    assert.equal(request.epoch, '9007199254741999');
    const url = new URL(request.url, 'https://inert.invalid');
    assert.equal(url.pathname, '/debug-read/physical'); assert.equal(url.searchParams.get('pathKey'), symbol('app'));
    assert.equal(url.searchParams.get('epoch'), request.epoch); assert.equal(url.searchParams.get('limit'), '2');
    assert.equal(Object.isFrozen(request), true);
  });
  check('defaults and empty slot cursor remain separate', () => {
    const initial = physicalRequest({pathKey: 'v1', collection: 'slots'});
    const afterEmpty = physicalRequest({pathKey: 'v1', collection: 'slots', epoch: '0', after: 'v1'});
    assert.equal(initial.after, null); assert.equal(initial.limit, 40);
    assert.equal(new URL(afterEmpty.url, 'https://inert.invalid').searchParams.get('after'), 'v1');
  });
  for (const override of [{pathKey: '/app'}, {collection: 'y'}, {limit: 0}, {limit: 41}, {limit: '2'}, {limit: 1.5},
    {epoch: 1}, {epoch: '01'}, {epoch: '-1'}, {epoch: '1e9'}, {epoch: '9'.repeat(129)},
    {after: 'v1'}, {after: symbol('a') + '/u:01'}, {epoch: null, after: atom('u', 1)}, {url: '/post'}]) {
    fails('malformed request ' + JSON.stringify(override), () => physicalRequest({...requestOptions(request), ...override}));
  }
  const queryBoundary = physicalRequest({pathKey: maximumKey, collection: 'slots', epoch: '9'.repeat(128), after: maximumKey});
  check('two maximal identities roundtrip within query budget', () => {
    const url = new URL(queryBoundary.url, 'https://inert.invalid');
    assert.equal(url.searchParams.get('after'), maximumKey); assert.equal(url.searchParams.get('pathKey'), maximumKey);
    assert.ok(url.search.length - 1 <= 32768);
  });
  check('two maximal deep keys preserve usable continuation budget', () => {
    const deep = 'v1' + '/f:'.repeat(2730);
    const request = physicalRequest({pathKey: deep, collection: 'slots', epoch: '9'.repeat(128), after: deep});
    const url = new URL(request.url, 'https://inert.invalid');
    assert.equal(url.origin, 'https://inert.invalid'); assert.equal(url.hash, '');
    assert.equal(url.searchParams.get('pathKey'), deep); assert.equal(url.searchParams.get('after'), deep);
    assert.ok(url.search.length - 1 <= 32768);
  });

  const valid = parsePhysicalPage(wire(), request);
  check('page exact identity and immutable cloned data', () => {
    assert.deepEqual(valid, wire()); assert.equal(Object.isFrozen(valid.entries[0].node.label), true);
    assert.equal(Object.hasOwn(valid.own, 'slots'), false, 'child metadata never fabricates loaded/complete slots');
    const original = wire(); const parsed = parsePhysicalPage(original, request); original.entries[0].node.label.hex = '';
    assert.equal(parsed.entries[0].node.label.hex, text('Authored title').hex);
  });
  const smallPage = wire({entries: [child(1)], next: atom('u', 1)});
  check('byte-budget-short page remains valid and incomplete', () => assert.equal(parsePhysicalPage(smallPage, request).entries.length, 1));
  for (const [field, value] of [['version', '1'], ['version', 2], ['resolution', 'y'], ['pathKey', symbol('other')],
    ['epoch', '5'], ['epoch', '01'], ['epoch', String(1n << 256n)], ['collection', 'slots'], ['after', atom('u', 0)],
    ['limit', 3], ['limit', '2'], ['total', '01'], ['total', 3], ['total', '1'], ['complete', true], ['complete', 'false'],
    ['next', atom('u', 3)], ['next', null], ['displayPath', 'javascript:alert(1)'], ['displayPath', '/bad\nname'],
    ['displayPath', '/' + '🐱'.repeat(300)], ['displayPath', '/\ud800'], ['entries', null],
    ['entries', [child(1), child(1)]], ['entries', [child(2), child(1)]], ['entries', [child(1), child(2), child(3)]],
    ['entries', [child(1, {key: 'v1'})]], ['entries', [child(1, {key: symbol('a') + '/u:01'})]]]) {
    fails('malformed envelope ' + field, () => parsePhysicalPage({...wire(), [field]: value}, request));
  }
  fails('missing envelope key', () => { const body = wire(); delete body.next; parsePhysicalPage(body, request); });
  fails('unknown envelope key', () => parsePhysicalPage({...wire(), html: '<script>bad()</script>'}, request));
  fails('accessor object does not execute', () => { const body = wire(); Object.defineProperty(body, 'own', {get: () => { throw Error('getter ran'); }}); parsePhysicalPage(body, request); });
  fails('non-enumerable envelope fields cannot disappear during cloning', () => { const body = wire(); Object.defineProperty(body, 'epoch', {enumerable: false}); parsePhysicalPage(body, request); });
  fails('non-enumerable entry identity is not JSON data', () => { const body = wire(); Object.defineProperty(body.entries[0], 'key', {enumerable: false}); parsePhysicalPage(body, request); });
  fails('sparse entries cannot skip validation', () => { const body = wire(); delete body.entries[0]; parsePhysicalPage(body, request); });
  fails('entry array accessors are not executed', () => { const body = wire(); Object.defineProperty(body.entries, '0', {get: () => { throw Error('array getter ran'); }}); parsePhysicalPage(body, request); });
  fails('entry array extra properties are not JSON data', () => { const body = wire(); body.entries.extra = true; parsePhysicalPage(body, request); });
  fails('entry array inherited methods are not executed', () => { const body = wire(); Object.setPrototypeOf(body.entries, {map() { throw Error('array method ran'); }}); parsePhysicalPage(body, request); });
  fails('unconstructed request not accepted', () => parsePhysicalPage(wire(), {...request}));
  for (const override of [{state: 'structural'}, {recordEpoch: null}, {recordEpoch: '9007199254742000'}, {fields: null}, {children: '4'},
    {kind: 'imagined'}, {labelSource: null}, {labelSource: 'generated'}, {helpLine: 4}, {helpLine: '2'},
    {helpSource: 'help-text', helpLine: 2}, {help: null}, {label: null}, {state: 'unknown', recordEpoch: '5'},
    {state: 'tombstone', fields: '0'}, {label: {...text('x'), type: 'natural'}}]) {
    fails('node invariant ' + JSON.stringify(override), () => parsePhysicalPage(wire({own: node(override)}), request));
  }
  check('transparent and tombstone nodes stay distinct', () => {
    for (const state of ['unknown', 'tombstone']) {
      const own = node({state, recordEpoch: state === 'unknown' ? null : '5', fields: null,
        label: null, labelSource: null, help: null, helpSource: null, helpLine: null, kind: 'namespace'});
      assert.equal(parsePhysicalPage(wire({own}), request).own.state, state);
    }
  });

  const slotRequest = physicalRequest({pathKey: request.pathKey, collection: 'slots', epoch: request.epoch});
  const values = [text('  \nExact <script>not executed</script>\n  '),
    {type: 'text', encoding: 'hex', hex: '4100ff1b42', total: '5', complete: true},
    {type: 'natural', encoding: 'hex', hex: '', total: '0', complete: true},
    {type: 'natural', encoding: 'hex', hex: '00'.repeat(256), total: '1025', complete: false},
    {type: 'path', pathKey: 'v1/ta:612f62/rd:010000000000f87f', displayPath: null},
    {type: 'opaque', reason: 'unsupported_type'}, {type: 'opaque', reason: 'key_too_large'}];
  const slotWire = () => wire({collection: 'slots', limit: 40, next: null, complete: true, total: String(values.length),
    own: node({fields: String(values.length)}), entries: values.map((value, i) => ({key: i ? atom('u', i) : 'v1', displayKey: null, value}))});
  check('value bytes and absent display identity remain exact', () => {
    const parsed = parsePhysicalPage(slotWire(), slotRequest);
    assert.deepEqual(parsed.entries.map(entry => entry.value), values);
    assert.equal(parsed.entries[0].key, 'v1'); assert.equal(parsed.entries[4].value.displayPath, null);
    assert.equal(parsed.own.helpLine, 2, 'complete scalar excerpt does not imply complete lore');
  });
  for (const value of [{...text('x'), hex: 'FF'}, {...text('x'), hex: 'f'}, {...text('x'), total: '2'},
    {...text('x'), complete: false}, {...text('x'), total: '257'}, {...text('x'), hex: 'ab'.repeat(257), total: '257'},
    {...text('x'), hex: '6100', total: '2'}, {type: 'natural', encoding: 'hex', hex: '00', total: '1', complete: true},
    {...text('x'), encoding: 'base64'}, {...text('x'), total: 1}, {type: 'path', pathKey: '/x', displayPath: null},
    {type: 'path', pathKey: 'v1', displayPath: null, care: 'y'}, {type: 'opaque', reason: 'secret'}, {type: 'safe', pathKey: 'v1'},
    {type: 'opaque', reason: 'unsupported_type', html: '<b>unsafe</b>'}]) {
    fails('value preview invariant ' + JSON.stringify(value), () => { const body = slotWire(); body.entries[0].value = value; parsePhysicalPage(body, slotRequest); });
  }

  const nextRequest = physicalRequest({...requestOptions(request), after: valid.next});
  const nextWire = wire({after: valid.next, entries: [child(3)], next: null, complete: true});
  const next = parsePhysicalPage(nextWire, nextRequest);
  const merged = mergePhysicalPages(valid, next);
  check('immutable contiguous merge', () => {
    assert.equal(valid.entries.length, 2); assert.equal(next.entries.length, 1); assert.equal(merged.entries.length, 3);
    assert.equal(merged.complete, true); assert.equal(merged.after, null); assert.equal(Object.isFrozen(merged.entries), true);
  });
  check('merge shares already immutable entries without sacrificing deep immutability', () => {
    assert.equal(merged.entries[0], valid.entries[0]); assert.equal(merged.entries[2], next.entries[0]);
    assert.throws(() => { merged.entries[0].node.label.hex = ''; }, TypeError);
    assert.throws(() => { merged.entries.push(child(4)); }, TypeError);
    const body = wire(); Object.freeze(body.own);
    const parsed = parsePhysicalPage(body, request);
    assert.notEqual(parsed.own, body.own);
    assert.equal(Object.isFrozen(parsed.own.label), true);
    body.own.label.hex = '';
    assert.equal(parsed.own.label.hex, text('Authored title').hex);
  });
  check('equivalent reordered node/preview JSON merges identically', () => {
    const reversed = value => value && typeof value === 'object' && !Array.isArray(value)
      ? Object.fromEntries(Object.entries(value).reverse().map(([key, child]) => [key, reversed(child)])) : value;
    assert.deepEqual(mergePhysicalPages(valid, parsePhysicalPage({...nextWire, own: reversed(nextWire.own)}, nextRequest)), merged);
  });
  fails('entry payload cannot spend the reserved envelope budget', () => {
    const huge = 'v1/tu:' + '61'.repeat(3500);
    const entries = Array.from({length: 15}, (_, index) => ({key: huge + '/u:' + (index + 1).toString(16).padStart(2, '0'), displayKey: null, value: {type: 'opaque', reason: 'unsupported_type'}}));
    const body = slotWire(); body.entries = entries; body.total = '15'; body.own.fields = '15';
    assert.ok(Buffer.byteLength(JSON.stringify(body)) < PHYSICAL_RESPONSE_BYTES);
    parsePhysicalPage(body, slotRequest);
  });
  fails('do not merge a repeated page', () => mergePhysicalPages(valid, valid));
  fails('do not merge after completion', () => mergePhysicalPages(merged, next));
  fails('do not merge caller-forged state', () => mergePhysicalPages({...valid}, next));
  for (const override of [{epoch: '9007199254742000'}, {pathKey: symbol('other')}, {limit: 1}]) {
    fails('merge identity ' + JSON.stringify(override), () => {
      const destination = physicalRequest({...requestOptions(nextRequest), ...override});
      const other = parsePhysicalPage({...nextWire, ...override}, destination);
      mergePhysicalPages(valid, other);
    });
  }
  fails('same epoch cannot change own metadata', () => mergePhysicalPages(valid, parsePhysicalPage({...nextWire, own: node({label: text('changed')})}, nextRequest)));
  fails('terminal first page cannot conceal missing entries', () => parsePhysicalPage(wire({next: null, complete: true}), request));
  fails('terminal merged collection cannot conceal missing entries', () => mergePhysicalPages(valid,
    parsePhysicalPage({...nextWire, entries: []}, nextRequest)));

  for (const [code, status] of Object.entries({invalid_query: 400, invalid_limit: 400, invalid_collection: 400, invalid_cursor: 400,
    epoch_required: 400, epoch_conflict: 409, derived_path: 422, path_missing: 404, record_missing: 404,
    record_deleted: 410, key_too_large: 422, read_failed: 500, response_too_large: 500})) {
    check('stable error ' + code, () => { const error = parsePhysicalError({version: 1, error: code}, status); assert.ok(error instanceof PhysicalReadError); assert.equal(error.code, code); });
  }
  for (const [body, status] of [[{version: 1, error: 'epoch_conflict'}, 200], [{version: 1, error: 'unknown'}, 500],
    [{version: 1, error: 'read_failed', detail: 'unsafe'}, 500], [{version: '1', error: 'read_failed'}, 500]]) {
    fails('malformed error envelope', () => parsePhysicalError(body, status));
  }

  let calls = 0;
  const fetched = await fetchPhysicalPage(request, {fetch: async (url, options) => {
    calls++; assert.equal(url, request.url); assert.equal(options.method, 'GET'); assert.equal(options.redirect, 'error');
    assert.equal(options.credentials, 'same-origin'); assert.equal(options.headers.Accept, 'application/json'); return response(wire());
  }});
  check('one explicit bounded read, no eager retries', () => { assert.deepEqual(fetched, valid); assert.equal(calls, 1); });
  await assert.rejects(fetchPhysicalPage(request, {fetch: async () => response(wire(), 201)}), /HTTP 200/); checks++;
  await assert.rejects(fetchPhysicalPage(request, {fetch: async () => response({version: 1, error: 'epoch_conflict'}, 409)}),
    error => error instanceof PhysicalReadError && error.code === 'epoch_conflict'); checks++;
  let cancelled = false;
  const stream = chunks => new ReadableStream({start(controller) { for (const chunk of chunks) controller.enqueue(chunk); }, cancel() { cancelled = true; }});
  await assert.rejects(fetchPhysicalPage(request, {fetch: async () => new Response(stream([new Uint8Array(PHYSICAL_RESPONSE_BYTES + 1)]),
    {headers: {'content-type': 'application/json'}})}), /byte budget/); checks++;
  check('oversized response stops and cancels stream', () => assert.equal(cancelled, true));
  cancelled = false;
  await assert.rejects(fetchPhysicalPage(request, {fetch: async () => new Response(stream([new Uint8Array([1])]),
    {headers: {'content-type': 'text/html'}})}), /content type/); checks++;
  check('wrong content type cancels without parsing', () => assert.equal(cancelled, true));
  for (const body of ['{"version":', Uint8Array.from([0xff, 0xff])]) {
    await assert.rejects(fetchPhysicalPage(request, {fetch: async () => response(body instanceof Uint8Array ? new TextDecoder('latin1').decode(body) : body)}), /malformed/); checks++;
  }
  // Invalid UTF-8 must be rejected before JSON replacement-character decoding.
  await assert.rejects(fetchPhysicalPage(request, {fetch: async () => new Response(Uint8Array.from([0x7b, 0xff, 0x7d]),
    {headers: {'content-type': 'application/json'}})}), /malformed UTF-8/); checks++;
  const aborted = new AbortController(); aborted.abort(new Error('fixture cancelled'));
  await assert.rejects(fetchPhysicalPage(request, {signal: aborted.signal, fetch: async () => { assert.fail('aborted request started'); }}), /fixture cancelled/); checks++;
  cancelled = false;
  const pendingController = new AbortController();
  const pending = fetchPhysicalPage(request, {signal: pendingController.signal, fetch: async () => new Response(stream([]),
    {headers: {'content-type': 'application/json'}})});
  await Promise.resolve(); await Promise.resolve(); pendingController.abort(new Error('cancel active stream'));
  await assert.rejects(pending, /cancel active stream/); checks++;
  check('active cancellation releases its stream', () => assert.equal(cancelled, true));
  check('no live reads', () => assert.equal(unexpectedFetches, 0));
  console.log('PASS: ' + checks + ' pure physical adapter checks; exact keys/native comparators, strict schemas, bounded previews, immutable epoch-safe merges and controlled fetch streams.');
  console.log('No browser, live requests, namespace writes, UI wiring or assets changed.');
  if (process.env.PHYSICAL_ARTIFACTS || process.env.PHYSICAL_EPOCH_ARTIFACTS) {
    assert.ok(process.env.PHYSICAL_ARTIFACTS && process.env.PHYSICAL_EPOCH_ARTIFACTS,
      'both PHYSICAL_ARTIFACTS (large) and PHYSICAL_EPOCH_ARTIFACTS (epoch) are required for the complete bridge');
    await verifyArtifacts(resolve(process.env.PHYSICAL_ARTIFACTS), resolve(process.env.PHYSICAL_EPOCH_ARTIFACTS));
  } else console.log('Real backend artifact bridge: NOT RUN (both scenario artifact directories must be supplied).');
} finally { globalThis.fetch = originalFetch; }

function requestOptions(value) {
  const {pathKey, collection, epoch, after, limit} = value; return {pathKey, collection, epoch, after, limit};
}
async function loadArtifacts(directory, scenario) {
  // The HTTP harness manifest is finalized by its owner; do not infer request
  // identities from response JSON, which would turn correlation into a tautology.
  const manifest = await readFile(resolve(directory, 'results.json'));
  const run = JSON.parse(manifest.toString('utf8'));
  assert.equal(run.passed, true, 'only completed real HTTP runs qualify as artifact evidence');
  assert.equal(run.scenario, scenario, 'the passing manifest belongs to this explicit scenario');
  assert.ok(Array.isArray(run.requests), 'real manifest records the original HTTP request identities');
  const results = new Map(), errors = new Map();
  let errorCount = 0;
  for (const entry of run.requests) {
    if (!entry.file) continue;
    const target = new URL(entry.path, 'http://artifact.invalid');
    if (target.pathname !== '/debug-read/physical') continue;
    assert.equal(entry.method, 'GET', 'saved physical artifacts came from read requests');
    assert.match(entry.file, /^[a-zA-Z0-9_.-]+\.json$/, 'artifact filename cannot escape the supplied directory');
    const raw = await readFile(resolve(directory, entry.file));
    assert.equal(raw.length, entry.bytes, 'recorded HTTP byte count matches untouched body');
    assert.ok(raw.length <= PHYSICAL_RESPONSE_BYTES, 'real response remains within wire budget');
    const before = createHash('sha256').update(raw).digest('hex');
    const data = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw));
    if (entry.status === 200) {
      const options = {pathKey: target.searchParams.get('pathKey'), collection: target.searchParams.get('collection')};
      if (target.searchParams.has('epoch')) options.epoch = target.searchParams.get('epoch');
      if (target.searchParams.has('after')) options.after = target.searchParams.get('after');
      if (target.searchParams.has('limit')) options.limit = Number(target.searchParams.get('limit'));
      const parsed = parsePhysicalPage(data, physicalRequest(options));
      results.set(entry.file, {request: options, page: parsed});
    } else { errors.set(entry.file, {request: target, error: parsePhysicalError(data, entry.status)}); errorCount++; }
    assert.equal(createHash('sha256').update(await readFile(resolve(directory, entry.file))).digest('hex'), before, 'untouched backend artifact');
  }
  const page = name => {
    assert.ok(results.has(name + '.json'), 'real artifact required: ' + name);
    return results.get(name + '.json').page;
  };
  assert.deepEqual(await readFile(resolve(directory, 'results.json')), manifest, 'scenario manifest remains untouched');
  return {run, results, errors, errorCount, page};
}
async function verifyArtifacts(directory, epochDirectory) {
  assert.notEqual(directory, epochDirectory, 'independent runtime scenarios require separate artifact directories');
  const large = await loadArtifacts(directory, 'large');
  const {results, errorCount, page} = large;
  const demo = page('demo-slots');
  assert.equal(demo.own.recordEpoch, '1'); assert.equal(demo.own.state, 'live'); assert.equal(demo.own.fields, '11');
  assert.equal(demo.own.labelSource, 'lede'); assert.equal(demo.own.label.hex, Buffer.from('Authored fixture').toString('hex'));
  assert.equal(demo.own.helpSource, 'lore-body'); assert.equal(demo.own.helpLine, 1);
  assert.equal(demo.own.help.hex, Buffer.from('Authored help').toString('hex'));
  const fields = new Map(demo.entries.map(entry => [entry.key, entry.value]));
  assert.equal(fields.get('v1').hex, Buffer.from('empty key').toString('hex'));
  assert.equal(fields.get(symbol('nul')).hex, '410042');
  assert.deepEqual(fields.get(symbol('long')), text('a'.repeat(255) + '€tail'), 'multibyte preview remains exact even when it ends inside a code point');
  assert.deepEqual(fields.get(symbol('zero')), {type: 'natural', encoding: 'hex', hex: '', total: '0', complete: true});
  assert.deepEqual(fields.get(symbol('huge')), {type: 'natural', encoding: 'hex', hex: '00'.repeat(256), total: '513', complete: false});
  assert.equal(fields.get(symbol('reference')).pathKey, symbol('elsewhere'));
  assert.deepEqual(fields.get(symbol('opaque')), {type: 'opaque', reason: 'unsupported_type'});
  assert.equal(fields.get(symbol('a') + '/ts:62').hex, Buffer.from('one opaque slot key').toString('hex'));
  const first = page('demo-first'), afterEmpty = page('demo-after-empty');
  assert.equal(first.next, 'v1'); assert.equal(afterEmpty.after, 'v1');
  assert.deepEqual(first.own, demo.own); assert.deepEqual(afterEmpty.own, demo.own);
  assert.equal(mergePhysicalPages(first, afterEmpty).entries.length, 2);
  assert.equal(page('empty').complete, true); assert.equal(page('empty').entries.length, 0);
  assert.equal(page('spine').own.state, 'unknown'); assert.equal(page('spine').entries[0].node.state, 'live');
  assert.equal(page('dead-children').own.state, 'tombstone'); assert.equal(page('root-slots').pathKey, 'v1/x:11');

  // Independently spell the persisted fixture's native order. Do not sort the
  // response with the comparator under test and then compare it to itself.
  const order = [atom('dm'), atom('dr'), atom('ds'), atom('f'), atom('f', 1), atom('f', 2), atom('r'),
    ...[0xbff0000000000000n, 0x8000000000000000n, 0n, 0x3ff0000000000000n, 0x7ff8000000000000n, 0x13ff0000000000000n].map(n => atom('rd', n)),
    ...[0xbf800000n, 0x80000000n, 0n, 0x3f800000n, 0x7fc00000n, 0x13f800000n].map(n => atom('rs', n)),
    ...[3n, 1n, 0n, 2n].map(n => atom('s', n)), 'v1/ta:6161', 'v1/ta:62',
    'v1/ts:6161', 'v1/ts:62', 'v1/ts:ff', 'v1/tu:6161', 'v1/tu:62', 'v1/tu:ff',
    atom('u'), atom('u', 10), atom('w'), atom('x')];
  assert.equal(order.length, 35);
  assert.deepEqual(page('order').entries.map(entry => entry.key), order, 'untouched server ordering matches independent native aura/payload expectations');
  for (const name of ['big', 'slots']) {
    const initial = page(name + '-first'), second = page(name + '-second');
    assert.equal(initial.total, '10000'); assert.equal(initial.entries.length, 40); assert.equal(second.entries.length, 40);
    const aggregate = mergePhysicalPages(initial, second);
    assert.deepEqual(aggregate.entries.map(entry => entry.key), Array.from({length: 80}, (_, index) => atom('u', index)));
    assert.equal(aggregate.complete, false); assert.equal(initial.entries.length, 40, 'real merge preserves previous page');
    for (const suffix of ['terminal', 'absent']) {
      assert.equal(page(name + '-' + suffix).complete, true); assert.equal(page(name + '-' + suffix).entries.length, 0);
    }
    assert.throws(() => mergePhysicalPages(initial, page(name + '-terminal')), TypeError, 'nonadjacent terminal artifact cannot conceal missing pages');
  }
  const wide = page('wide-first'), wideNext = page('wide-second');
  assert.ok(wide.entries.length > 0 && wide.entries.length < 20);
  const wideComplete = mergePhysicalPages(wide, wideNext);
  assert.equal(wideComplete.entries.length, 20); assert.equal(wideComplete.complete, true);
  assert.ok(errorCount >= 8, 'bridge also validates stable real HTTP failures');
  for (const name of ['maximum-identities.json', 'maximum-identities-after-walks.json']) {
    const maximum = large.errors.get(name);
    assert.ok(maximum, 'both actual maximum-key boundary requests are required');
    assert.equal(maximum.error.code, 'path_missing');
    const pathKey = maximum.request.searchParams.get('pathKey'), after = maximum.request.searchParams.get('after');
    assert.equal(pathKey, 'v1/x:11' + '/f:'.repeat(2727) + '/rd:'); assert.equal(after, pathKey);
    const constructed = physicalRequest({pathKey, collection: 'slots', epoch: maximum.request.searchParams.get('epoch'), after});
    assert.ok(constructed.url.split('?')[1].length <= 32768, 'both complete identities retain a usable continuation query');
  }

  // This scenario booted an independent clean runtime. Its epoch values are
  // compared only with its own before/after pages, never the large fixture.
  const epoch = await loadArtifacts(epochDirectory, 'epoch');
  const before = epoch.page('epoch-before'), epochFirst = epoch.page('epoch-first'), epochNext = epoch.page('epoch-next');
  const changed = epoch.page('epoch-after');
  assert.equal(before.pathKey, 'v1/x:11/ts:64656d6f'); assert.equal(before.collection, 'slots'); assert.equal(before.total, '11');
  assert.equal(before.complete, true); assert.equal(before.entries.length, 11);
  assert.equal(before.own.labelSource, 'lede'); assert.equal(before.own.label.hex, text('Authored fixture').hex);
  assert.equal(before.own.helpSource, 'lore-body'); assert.equal(before.own.helpLine, 1); assert.equal(before.own.help.hex, text('Authored help').hex);
  assert.equal(epochFirst.limit, 2); assert.equal(epochNext.limit, 2);
  assert.equal(epochFirst.epoch, before.epoch); assert.equal(epochNext.epoch, before.epoch);
  assert.deepEqual(epochFirst.own, before.own); assert.deepEqual(epochNext.own, before.own);
  const epochAggregate = mergePhysicalPages(epochFirst, epochNext);
  assert.deepEqual(epochAggregate.entries, before.entries.slice(0, 4)); assert.equal(epochAggregate.complete, false);
  const priorText = before.entries.find(entry => entry.key === symbol('text')).value;
  assert.deepEqual(priorText, text('hello'));
  assert.equal(changed.pathKey, before.pathKey); assert.equal(changed.collection, before.collection);
  assert.ok(BigInt(changed.epoch) > BigInt(before.epoch)); assert.equal(changed.own.recordEpoch, changed.epoch);
  assert.deepEqual(changed.entries.find(entry => entry.key === symbol('text')).value, text('changed'));
  assert.deepEqual(priorText, text('hello'), 'fresh response cannot mutate the earlier immutable snapshot');
  assert.throws(() => mergePhysicalPages(epochFirst, changed), TypeError, 'a fresh epoch page is never an implicit continuation');
  const stale = epoch.errors.get('epoch-stale.json');
  assert.ok(stale, 'the real old-epoch continuation response is required');
  assert.equal(stale.error.code, 'epoch_conflict'); assert.equal(stale.error.status, 409);
  assert.equal(stale.request.searchParams.get('epoch'), before.epoch);
  assert.equal(stale.request.searchParams.get('after'), epochFirst.next); assert.equal(stale.request.searchParams.get('limit'), '2');
  assert.ok(epoch.run.requests.some(entry => entry.path === '/edit/0x11/demo' && entry.method === 'POST' && entry.status === 200),
    'the clean runtime recorded an actual successful HTTP edit between its snapshots');
  console.log('PASS: untouched two-scenario real HTTP artifact bridge: large ' + results.size + ' successful pages/' + errorCount + ' errors; clean epoch ' + epoch.results.size + ' successful pages/' + epoch.errorCount + ' errors.');
  console.log('Verified exact metadata/bytes/native order, five within-runtime continuation pairs, both maximum-key requests, terminal gaps and a real clean-runtime write/epoch conflict.');
  console.log('Large artifacts: ' + directory + '\nEpoch artifacts: ' + epochDirectory + '\nNo artifacts were rewritten; no live requests or cross-runtime page merges were made.');
}
