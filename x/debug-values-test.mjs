// Exact-value UI and production parser/byte-window regression. A saved shell
// avoids live reads; without DEBUG_DOCUMENT, at most one /debug/app GET is
// allowed. Every namespace/value request after that is a browser-only fixture.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = new URL(process.env.DEBUG_URL || 'http://127.0.0.1:8138').origin;
const root = fileURLToPath(new URL('..', import.meta.url));
const assets = new Map(await Promise.all([
  ['/debug-mash.js', 'src/foil/.debug-assets/mash.js', 'application/javascript'],
  ['/debug-components.css', 'src/foil/.debug-assets/components.css', 'text/css'],
  ['/debug.js', 'src/foil/debug.js', 'application/javascript'],
  ['/debug.css', 'src/foil/debug.css', 'text/css'],
  ['/style.css', 'src/foil/style.css', 'text/css'],
].map(async ([url, path, contentType]) => [url, {body: await readFile(resolve(root, path)), contentType}])));
const initialHTML = process.env.DEBUG_DOCUMENT ? await readFile(process.env.DEBUG_DOCUMENT, 'utf8') : await (async () => {
  const response = await fetch(base + '/debug/app', {signal: AbortSignal.timeout(15000)});
  assert.equal(response.ok, true, 'the single initial document is available'); return response.text();
})();
const epoch = '9007199254741999';
const fixturePath = '/__values__';
const text = ('  \n' + 'A line of exact namespace bytes.\n'.repeat(160)).slice(0, 4095) +
  '💠猫e\u0301\r\n' + 'Windowed content stays exact.\n'.repeat(410) +
  '<img src="/__value_xss__" onerror="window.__valueXSS=true">\n<script>window.__valueXSS=true</script>\nTAIL_EXACT_97\n  ';
const bytes = new TextEncoder().encode(text);
assert.equal(bytes[4095], 0xf0, 'the first display window splits a four-byte UTF-8 character');
assert.ok(bytes.length > 8192);
const payloads = new Map([
  ['/payload/body', {bytes, type: 'text', representation: 'utf8-bytes'}],
  ['/invalid', {bytes: Uint8Array.from([0x41, 0x00, 0xff, 0xc0, 0x80, 0x42]), type: 'text', representation: 'utf8-bytes'}],
  ['/control', {bytes: Uint8Array.from([0x41, 0x00, 0x09, 0x1b, 0x42]), type: 'text', representation: 'utf8-bytes'}],
  ['/natural', {bytes: Uint8Array.from([0, 1, 255, 128]), type: 'natural', representation: 'natural-le-bytes'}],
  ['/zero', {bytes: new Uint8Array(), type: 'natural', representation: 'natural-le-bytes'}],
  ['/empty', {bytes: new Uint8Array(), type: 'text', representation: 'utf8-bytes'}],
]);
const valueURL = slot => '/debug-read/value?path=' + encodeURIComponent(fixturePath) + '&slot=' + encodeURIComponent(slot) + '&epoch=' + epoch + '&offset=0&limit=65536';
const fields = [
  {key: '/sys/lede', text: 'Exact value fixture'},
  {key: '/legacy', text: 'Authored ellipsis…'},
  {key: '/complete', text: 'A complete supplied value.', state: 'complete', reason: '', bytes: '26', previewBytes: '26', epoch, representation: 'utf8-bytes'},
  {key: '/payload/body', text: text.slice(0, 120) + '…', state: 'preview', reason: 'byte-limit', bytes: String(bytes.length), previewBytes: '120', epoch, representation: 'utf8-bytes', url: valueURL('/payload/body')},
  {key: '/opaque', text: 'form', state: 'opaque', reason: 'semantic-summary', bytes: '', previewBytes: '', epoch, representation: ''},
  {key: '/invalid', text: 'Non-text bytes', state: 'preview', reason: 'non-text-bytes', bytes: '6', previewBytes: '0', epoch, representation: 'utf8-bytes', url: valueURL('/invalid')},
  {key: '/control', text: 'Non-printing bytes', state: 'preview', reason: 'non-text-bytes', bytes: '5', previewBytes: '0', epoch, representation: 'utf8-bytes', url: valueURL('/control')},
  {key: '/natural', text: '4 byte numeric value', state: 'preview', reason: 'numeric-summary', bytes: '4', previewBytes: '0', epoch, representation: 'natural-le-bytes', url: valueURL('/natural')},
  {key: '/zero', text: '0', state: 'complete', reason: '', bytes: '0', previewBytes: '0', epoch, representation: 'natural-le-bytes', url: valueURL('/zero')},
  {key: '/empty', text: '', state: 'complete', reason: '', bytes: '0', previewBytes: '0', epoch, representation: 'utf8-bytes', url: valueURL('/empty')},
];
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
const page = await context.newPage();
const reads = [], valueReads = [], writes = [], unexpected = [], errors = [];
const slotGates = new Map();
let fault = null, gate = null, release = null;
const fixtures = await page.evaluate(({html, fields, fixturePath}) => {
  const original = new DOMParser().parseFromString(html, 'text/html');
  if (!original.querySelector('#debug-workspace') || !original.querySelector('#debug-main > section[aria-label=Record] > sh-myth'))
    throw new Error('The captured shell lacks the actual debugger document anatomy.');
  const make = (path, entries, children = []) => {
    const doc = original.cloneNode(true), ws = doc.querySelector('#debug-workspace');
    ws.dataset.path = path; ws.dataset.kind = 'record'; ws.dataset.writable = 'false';
    ws.dataset.label = 'Browser-only exact value fixture'; ws.dataset.fixture = 'debug-values';
    ws.dataset.renderUrl = '/ns' + (path === '/' ? '' : path);
    for (const key of ['paging', 'pageBefore', 'pageNextBefore', 'pageLimit', 'childCount', 'pageEpoch']) delete ws.dataset[key];
    const myth = doc.querySelector('#debug-main > section[aria-label=Record] > sh-myth'); myth.replaceChildren();
    for (const field of entries) {
      const limb = doc.createElement('sh-limb'); limb.dataset.valueKind = 'text';
      if (field.state) Object.assign(limb.dataset, {valueState: field.state, previewReason: field.reason,
        valueBytes: field.bytes, valuePreviewBytes: field.previewBytes, valueEpoch: field.epoch,
        valueRepresentation: field.representation, valueUrl: field.url || ''});
      const label = doc.createElement('sh-slot'); label.setAttribute('title', field.key);
      const pail = doc.createElement('sh-pail'); pail.textContent = field.text;
      limb.append(label, pail); myth.append(limb);
    }
    for (const label of ['Semantics', 'Documentation', 'Operations']) doc.querySelector('#debug-main section[aria-label="' + label + '"]')?.replaceChildren();
    const tree = doc.querySelector('#debug-children'); tree.replaceChildren();
    for (const child of children) {
      const item = doc.createElement('ui-tree-item'); item.dataset.path = child;
      item.dataset.label = child.split('/').at(-1); item.setAttribute('title', item.dataset.label); tree.append(item);
    }
    return '<!doctype html>' + doc.documentElement.outerHTML;
  };
  return {[fixturePath]: make(fixturePath, fields), '/': make('/', [{key: '/sys/lede', text: 'Browser-only value fixture root'}], [fixturePath, '/other']),
    '/other': make('/other', [{key: '/sys/lede', text: 'Other fixture record'}, {key: '/result', text: 'Navigation cancelled the old value read.'}])};
}, {html: initialHTML, fields: [...fields, {...fields.find(field => field.key === '/payload/body'),
  key: '/unsafe', text: 'Untrusted slot metadata fixture', url: 'javascript:window.__valueXSS=true'}], fixturePath});

function envelope(url) {
  const slot = url.searchParams.get('slot'), source = payloads.get(slot);
  assert.ok(source, 'only explicitly authored fixture slots may be fetched');
  assert.equal(url.searchParams.get('path'), fixturePath, 'an opaque slot is not appended to its record path');
  assert.equal(url.searchParams.get('epoch'), epoch, 'the full arbitrary-precision epoch is retained');
  assert.deepEqual([...url.searchParams.keys()].sort(), ['epoch', 'limit', 'offset', 'path', 'slot']);
  const offset = Number(url.searchParams.get('offset')), limit = Number(url.searchParams.get('limit'));
  assert.ok(Number.isSafeInteger(offset) && offset >= 0 && offset <= source.bytes.length);
  assert.ok(Number.isSafeInteger(limit) && limit >= 1 && limit <= 4102, 'one explicit request is a bounded display window plus at most six context bytes');
  const end = Math.min(source.bytes.length, offset + limit), chunk = source.bytes.slice(offset, end);
  return {version: 1, path: fixturePath, slot, epoch, recordEpoch: epoch, type: source.type,
    representation: source.representation, encoding: 'hex', total: String(source.bytes.length), offset: String(offset),
    next: end < source.bytes.length ? String(end) : null, complete: end >= source.bytes.length,
    hex: Buffer.from(chunk).toString('hex')};
}
async function routeFixtures(route) {
  const request = route.request(), url = new URL(request.url());
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) { writes.push(request.url()); return route.abort(); }
  if (url.origin === base && assets.has(url.pathname)) return route.fulfill({status: 200, ...assets.get(url.pathname)});
  if (url.origin === base && /^\/__values_test__\/[a-z-]+\.js$/.test(url.pathname))
    return route.fulfill({status: 200, contentType: 'application/javascript', body: await readFile(resolve(root, 'src/foil/debug', url.pathname.split('/').at(-1)))});
  if (url.origin === base && url.pathname === '/debug-read/value') {
    valueReads.push(url.pathname + url.search);
    const pending = slotGates.get(url.searchParams.get('slot')) || gate; if (pending) await pending;
    const failure = fault; fault = null;
    if (failure === 'http') return route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({version: 1, error: 'fixture_unavailable'})});
    if (failure === 'json') return route.fulfill({status: 200, contentType: 'application/json', body: '{"version":1,"hex":'});
    if (failure === 'oversize') return route.fulfill({status: 200, contentType: 'application/json', body: ' '.repeat(196609)});
    if (failure === 'content-type') return route.fulfill({status: 200, contentType: 'text/html', body: '<script>window.__valueXSS=true</script>'});
    if (failure === 'redirect') return route.fulfill({status: 302, headers: {location: 'https://elsewhere.invalid/stolen-value'}});
    const body = envelope(url);
    if (failure === 'identity') body.epoch = '9007199254741998';
    if (failure === 'assertion') body.recordEpoch = '9007199254741998';
    if (failure === 'invalid') body.hex = 'not-hex';
    return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
  }
  if (url.origin === base && /^\/debug(?:\/|$)/.test(url.pathname)) {
    const path = decodeURIComponent(url.pathname.slice('/debug'.length)) || '/'; reads.push(path);
    if (fixtures[path]) return route.fulfill({status: 200, contentType: 'text/html', body: fixtures[path]});
  }
  if (url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
}
await context.route('**/*', routeFixtures);
page.on('pageerror', error => errors.push(error.message));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function settled(check, message) {
  for (let index = 0; index < 120; index++) { if (await check()) return; await wait(25); }
  assert.fail(message);
}
async function ready(path = fixturePath, target = page) {
  await target.waitForFunction(path => {
    const ws = document.querySelector('#debug-workspace');
    return ws?.dataset.path === path && ws.dataset.readState === 'ready' && ws.getAttribute('aria-busy') !== 'true';
  }, path);
}
const field = (key = '/payload/body', target = page) => target.locator('#wb-canvas > sh-myth.wb-properties > sh-limb[data-key="' + key + '"]');
const full = (key, target = page) => field(key, target).locator('.wb-full-value');
const action = (name, key = '/payload/body', target = page) => field(key, target).getByRole('button', {name, exact: true});
const exactText = (key = '/payload/body', target = page) => full(key, target).locator('pre').last();
async function shown(text, key = '/payload/body', target = page) {
  await settled(async () => await full(key, target).count() === 1 && (text === '' || await full(key, target).isVisible()) && await exactText(key, target).textContent() === text,
    'the requested exact byte window is presented without altering source text');
}
async function noOverflow(target = page) {
  const defects = await target.evaluate(() => {
    const problems = [];
    if (document.documentElement.scrollWidth > innerWidth + 1) problems.push('document');
    for (const el of document.querySelectorAll('.wb-properties, .wb-full-value, .wb-value-status')) {
      if (el.clientWidth && el.scrollWidth > el.clientWidth + 1) problems.push(el.className);
    }
    for (const field of document.querySelectorAll('.wb-properties > sh-limb')) {
      const controls = [...field.querySelectorAll('ui-button')].filter(el => /^(Inspect value|Earlier bytes|Next bytes|Close value)$/.test(el.getAttribute('aria-label') || el.textContent.trim()));
      const bounds = controls.map(el => el.shadowRoot?.querySelector('button')?.getBoundingClientRect()).filter(box => box?.width && box?.height);
      for (const box of bounds) {
        if (box.left < -1 || box.right > innerWidth + 1) problems.push('action outside viewport');
        if (matchMedia('(pointer: coarse)').matches && (box.width < 44 || box.height < 44)) problems.push('touch target below 44px: ' + box.width + '×' + box.height);
      }
      for (let i = 0; i < bounds.length; i++) for (let j = i + 1; j < bounds.length; j++) {
        const a = bounds[i], b = bounds[j];
        if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) problems.push('overlapping actions');
      }
    }
    return problems;
  });
  assert.deepEqual(defects, [], 'exact-value panes and native actions remain within their layout: ' + defects.join(', '));
}

try {
  await page.goto(base + '/debug' + fixturePath); await ready();
  const contract = await page.evaluate(async ({fields, fixturePath, epoch, text, sources}) => {
    const api = await import('/__values_test__/values.js');
    const {parseValueMetadata, valueWindowURL, parseValueChunk, renderValueWindow} = api;
    const limbFor = field => {
      const limb = document.createElement('sh-limb');
      if (field.state) Object.assign(limb.dataset, {valueState: field.state, previewReason: field.reason,
        valueBytes: field.bytes, valuePreviewBytes: field.previewBytes, valueEpoch: field.epoch,
        valueRepresentation: field.representation, valueUrl: field.url || ''});
      return limb;
    };
    const metadata = field => parseValueMetadata(limbFor(field), fixturePath, field.key);
    const byKey = Object.fromEntries(fields.map(field => [field.key, metadata(field)]));
    const reference = fields.find(field => field.key === '/payload/body');
    const invalidMetadata = [];
    for (const [key, value] of [
      ['valueState', 'raw'], ['previewReason', 'guess'], ['valueBytes', '01'], ['valueBytes', '-1'],
      ['valueBytes', '1e9'], ['valuePreviewBytes', String(Number(reference.bytes) + 1)],
      ['valueEpoch', 'Infinity'], ['valueEpoch', '9007199254741999.0'], ['valueRepresentation', 'javascript'],
      ['valueUrl', 'javascript:alert(1)'], ['valueUrl', '//elsewhere.invalid/debug-read/value'],
      ['valueUrl', 'https://elsewhere.invalid/debug-read/value'], ['valueUrl', '/post'],
      ['valueUrl', reference.url + '#fragment'], ['valueUrl', reference.url + '&epoch=' + epoch],
      ['valueUrl', reference.url + '&unknown=1'], ['valueUrl', reference.url + '&'],
      ['valueUrl', reference.url.replace('offset=0', 'offset=1')],
      ['valueUrl', reference.url.replace('limit=65536', 'limit=65537')],
      ['valueUrl', reference.url.replace(encodeURIComponent(fixturePath), encodeURIComponent('/other'))],
      ['valueUrl', reference.url.replace(encodeURIComponent('/payload/body'), encodeURIComponent('/other'))],
      ['valueUrl', reference.url.replace('epoch=' + epoch, 'epoch=3')],
    ]) {
      const limb = limbFor(reference); limb.dataset[key] = value;
      try { parseValueMetadata(limb, fixturePath, reference.key); invalidMetadata.push({key, value, rejected: false}); }
      catch (error) { invalidMetadata.push({key, value, rejected: true, message: error.message}); }
    }
    const orphan = limbFor({}); orphan.dataset.valueUrl = reference.url;
    let orphanRejected = false;
    try { parseValueMetadata(orphan, fixturePath, reference.key); } catch { orphanRejected = true; }
    const opaque = limbFor({...reference, state: 'opaque', reason: 'semantic-summary'});
    let opaqueURLRejected = false;
    try { parseValueMetadata(opaque, fixturePath, reference.key); } catch { opaqueURLRejected = true; }
    const makeChunk = (request, source) => {
      const offset = Number(request.offset), end = Math.min(source.bytes.length, offset + request.limit);
      return {version: 1, path: request.path, slot: request.slot, epoch: request.epoch, recordEpoch: request.epoch,
        type: source.type, representation: source.representation, encoding: 'hex', total: String(source.bytes.length),
        offset: request.offset, next: end < source.bytes.length ? String(end) : null, complete: end >= source.bytes.length,
        hex: source.bytes.slice(offset, end).map(byte => byte.toString(16).padStart(2, '0')).join('')};
    };
    const windows = [], allBytes = [], textSource = sources['/payload/body'];
    for (let start = 0; start < textSource.bytes.length; start += 4096) {
      const request = valueWindowURL(byKey['/payload/body'], String(start));
      const json = makeChunk(request, textSource);
      const parsed = parseValueChunk(json, request), window = renderValueWindow(parsed, request);
      windows.push({request, text: window.text, format: window.format, start: window.start, end: window.end});
      allBytes.push(...window.bytes);
    }
    const sampleRequest = valueWindowURL(byKey['/payload/body'], '4096');
    const sample = makeChunk(sampleRequest, textSource), invalidChunks = [];
    const previousAssertion = parseValueChunk({...sample, recordEpoch: String(BigInt(epoch) - 1n)}, sampleRequest).recordEpoch;
    const hugeWindow = valueWindowURL({...byKey['/payload/body'], bytes: '18014398509499999'}, '9007199254741999');
    for (const [key, value] of [
      ['version', 2], ['path', '/other'], ['slot', '/other'], ['epoch', '3'], ['recordEpoch', '01'],
      ['recordEpoch', String(BigInt(epoch) + 1n)], ['type', 'natural'], ['representation', 'natural-le-bytes'],
      ['encoding', 'base64'], ['total', '01'], ['total', String(textSource.bytes.length + 1)],
      ['offset', '0'], ['offset', 'NaN'], ['next', '01'], ['next', '0'], ['next', null],
      ['complete', true], ['complete', 'false'], ['hex', 'abc'], ['hex', 'FF'], ['hex', 'zz'], ['hex', ''],
    ]) {
      try { parseValueChunk({...sample, [key]: value}, sampleRequest); invalidChunks.push({key, value, rejected: false}); }
      catch (error) { invalidChunks.push({key, value, rejected: true, message: error.message}); }
    }
    for (const value of [null, [], 'not an envelope', {version: 1, error: 'not_a_success'}]) {
      try { parseValueChunk(value, sampleRequest); invalidChunks.push({value, rejected: false}); }
      catch (error) { invalidChunks.push({value, rejected: true, message: error.message}); }
    }
    const special = {};
    for (const key of ['/invalid', '/control', '/natural', '/zero', '/empty']) {
      const request = valueWindowURL(byKey[key], '0');
      const json = makeChunk(request, sources[key]);
      const parsed = parseValueChunk(json, request), window = renderValueWindow(parsed, request);
      special[key] = {format: window.format, text: window.text, bytes: [...window.bytes], json};
    }
    return {byKey, invalidMetadata, invalidChunks, orphanRejected, opaqueURLRejected, previousAssertion, hugeWindow, windows, allBytes, special,
      composedText: windows.map(window => window.text).join(''), expectedText: text};
  }, {fields, fixturePath, epoch, text, sources: Object.fromEntries([...payloads].map(([key, value]) => [key, {...value, bytes: [...value.bytes]}]))});
  assert.equal(contract.byKey['/legacy'].state, 'unknown');
  assert.equal(contract.byKey['/legacy'].url, null);
  assert.equal(contract.byKey['/complete'].state, 'complete');
  assert.equal(contract.byKey['/opaque'].state, 'opaque');
  assert.equal(contract.byKey['/opaque'].url, null);
  assert.equal(contract.byKey['/payload/body'].epoch, epoch);
  assert.equal(contract.byKey['/payload/body'].slot, '/payload/body', 'slot keys remain opaque record keys');
  assert.ok(contract.invalidMetadata.every(result => result.rejected && result.message), 'malformed or unsafe metadata fails closed: ' + JSON.stringify(contract.invalidMetadata));
  assert.ok(contract.orphanRejected, 'partial metadata is not mistaken for metadata-free legacy output');
  assert.ok(contract.opaqueURLRejected, 'an opaque summary cannot advertise an exact read endpoint');
  assert.equal(contract.previousAssertion, String(BigInt(epoch) - 1n), 'an unchanged assertion may predate the requested sovereign epoch');
  assert.equal(contract.hugeWindow.start, '9007199254741999');
  assert.equal(contract.hugeWindow.offset, '9007199254741996');
  assert.equal(contract.hugeWindow.end, '9007199254746095');
  assert.equal(contract.hugeWindow.limit, 4102, 'huge byte addresses never pass through floating-point arithmetic');
  assert.ok(contract.invalidChunks.every(result => result.rejected && result.message), 'invalid chunk envelopes fail closed: ' + JSON.stringify(contract.invalidChunks));
  assert.deepEqual(contract.allBytes, [...bytes], 'logical byte windows reconstruct every original byte without overlap/context leakage');
  assert.equal(contract.composedText, text, 'multibyte boundary context assigns each complete UTF-8 character exactly once');
  assert.ok(contract.windows.every(window => window.format === 'utf8' && window.request.limit <= 4102));
  assert.equal(contract.special['/invalid'].format, 'hex');
  assert.equal(contract.special['/control'].format, 'hex');
  assert.equal(contract.special['/natural'].format, 'hex');
  for (const key of ['/invalid', '/control', '/natural', '/zero', '/empty']) assert.deepEqual(contract.special[key].bytes, [...payloads.get(key).bytes]);
  assert.equal(contract.special['/zero'].json.hex, '');
  assert.equal(contract.special['/zero'].json.next, null);
  assert.equal(contract.special['/zero'].json.complete, true);
  assert.equal(contract.special['/empty'].text, '');
  assert.deepEqual(valueReads, [], 'module/parser checks and initial render do not eagerly fetch exact values');
  console.log('PASS: production metadata/envelope parsers reject malformed inputs, exact arbitrary-precision identity survives, byte windows reconstruct text/naturals including multibyte boundaries and empty/invalid bytes.');

  assert.match(await field('/legacy').textContent(), /unknown|not reported|unverified/i, 'legacy data must not be advertised as complete');
  assert.match(await field('/opaque').textContent(), /summary|opaque|unavailable/i);
  assert.match(await field('/payload/body').textContent(), /preview/i);
  assert.equal(await action('Inspect value', '/legacy').count(), 0);
  assert.equal(await action('Inspect value', '/opaque').count(), 0);
  assert.equal(await action('Inspect value', '/unsafe').count(), 0, 'invalid slot metadata is quarantined without crashing the record or exposing an unsafe action');
  assert.match(await field('/unsafe').textContent(), /unknown|unavailable|invalid|unreported/i);
  const suppliedPreview = await field().locator('pre').first().textContent();
  await action('Inspect value').focus(); await action('Inspect value').press('Enter');
  await shown(contract.windows[0].text);
  await settled(() => full().locator('[part=viewport]').evaluate(el => el.getRootNode().activeElement === el),
    'keyboard inspection places focus in the exact Mash byte viewport');
  assert.equal(valueReads.length, 1, 'Inspect value fetches only the first bounded window');
  assert.equal(await action('Earlier bytes').isDisabled(), true);
  assert.equal(await action('Next bytes').isEnabled(), true);
  assert.equal(await field().locator('pre').first().textContent(), suppliedPreview, 'the supplied semantic preview remains separate from exact inspection');
  assert.notEqual(await page.evaluate(() => document.activeElement?.localName), 'body', 'keyboard activation does not lose focus into the document');
  await action('Next bytes').click(); await shown(contract.windows[1].text);
  assert.equal(valueReads.length, 2, 'the next window is read only after explicit activation');
  assert.ok(contract.windows[0].text.endsWith('💠'));
  assert.ok(contract.windows[1].text.startsWith('猫'));
  await action('Earlier bytes').click(); await shown(contract.windows[0].text);
  const beforeFailure = valueReads.length;
  fault = 'http'; await action('Next bytes').click();
  await settled(async () => /fail|unavailable|retry/i.test(await field().locator('.wb-value-status').last().textContent()), 'read failure is reported in the value status');
  assert.equal(await exactText().textContent(), contract.windows[0].text, 'failure retains the last good exact window');
  assert.equal(valueReads.length, beforeFailure + 1);
  const failedURL = valueReads.at(-1);
  await action('Next bytes').click(); await shown(contract.windows[1].text);
  assert.equal(valueReads.at(-1), failedURL, 'retry preserves the failed epoch/offset/limit');
  fault = 'identity'; await action('Next bytes').click();
  await settled(async () => /fail|invalid|identity|epoch|changed/i.test(await field().locator('.wb-value-status').last().textContent()), 'cross-window assertion identity drift is rejected');
  assert.equal(await exactText().textContent(), contract.windows[1].text);
  fault = 'assertion'; await action('Next bytes').click();
  await settled(async () => /fail|invalid|identity|epoch|changed|assertion/i.test(await field().locator('.wb-value-status').last().textContent()), 'the same requested version cannot switch its selected assertion between windows');
  assert.equal(await exactText().textContent(), contract.windows[1].text);
  fault = 'invalid'; await action('Next bytes').click();
  await settled(async () => /fail|invalid|hex/i.test(await field().locator('.wb-value-status').last().textContent()), 'invalid response bytes are rejected');
  assert.equal(await exactText().textContent(), contract.windows[1].text);
  for (const failure of ['json', 'oversize', 'content-type', 'redirect']) {
    fault = failure; await action('Next bytes').click();
    await settled(async () => /fail|invalid|exceed|data|fetch/i.test(await field().locator('.wb-value-status').last().textContent()), failure + ' transport response is rejected');
    assert.equal(await exactText().textContent(), contract.windows[1].text, failure + ' does not replace the last good bytes');
  }
  // Rejecting a response from headers must cancel its body stream too. These
  // browser-only Response objects deliberately never finish producing bytes.
  for (const failure of ['http', 'content-type']) {
    await page.evaluate(failure => {
      const original = window.fetch;
      window.__valueHeaderCancelled = false;
      window.__restoreValueFetch = () => { window.fetch = original; delete window.__restoreValueFetch; };
      window.fetch = (...args) => {
        const url = new URL(typeof args[0] === 'string' ? args[0] : args[0].url, location.href);
        if (url.pathname !== '/debug-read/value') return original(...args);
        const body = new ReadableStream({cancel() { window.__valueHeaderCancelled = true; }});
        return Promise.resolve(new Response(body, {status: failure === 'http' ? 404 : 200,
          headers: {'content-type': failure === 'http' ? 'application/json' : 'text/html'}}));
      };
    }, failure);
    try {
      await action('Next bytes').click();
      await settled(() => page.evaluate(() => window.__valueHeaderCancelled), failure + ' header rejection cancels the unconsumed response body');
      assert.equal(await exactText().textContent(), contract.windows[1].text);
    } finally { await page.evaluate(() => window.__restoreValueFetch?.()); }
  }
  await action('Next bytes').click(); await shown(contract.windows[2].text);
  for (let index = 3; index < contract.windows.length; index++) { await action('Next bytes').click(); await shown(contract.windows[index].text); }
  assert.equal(await action('Next bytes').isDisabled(), true, 'the terminal byte window has no false continuation');
  assert.match(await exactText().textContent(), /TAIL_EXACT_97\n  $/);
  assert.equal(await page.evaluate(() => window.__valueXSS), undefined);
  assert.equal(await full().locator('img,script').count(), 0, 'exact bytes remain inert text, never authored markup');
  await action('Close value').click();
  assert.equal(await full().isVisible(), false, 'exact inspection is reversible');
  console.log('PASS: explicit bounded windows, UTF-8 continuation, terminal state, failure/retry identity, inert content and preview preservation.');

  // A held request lets cancellation be tested without arbitrary response
  // delays. Returning the stale response must not reopen or overwrite a view.
  await page.reload(); await ready();
  gate = new Promise(resolve => { release = resolve; });
  const pendingStart = valueReads.length;
  await action('Inspect value').click();
  await settled(async () => valueReads.length === pendingStart + 1, 'one initial read is in flight');
  await action('Close value').click(); release(); gate = null; release = null;
  await settled(() => action('Inspect value').evaluate(el => el.getRootNode().activeElement === el),
    'closing a pending read restores native focus after re-enabling Inspect');
  await wait(100);
  assert.equal(await full().isVisible(), false, 'a late response cannot reopen collapsed inspection');
  assert.equal(await action('Inspect value').isEnabled(), true);
  await page.reload(); await ready();
  gate = new Promise(resolve => { release = resolve; });
  const escapeStart = valueReads.length;
  await action('Inspect value').click();
  await settled(async () => valueReads.length === escapeStart + 1, 'a value read is pending before Escape');
  await action('Close value').press('Escape'); release(); gate = null; release = null;
  await settled(() => action('Inspect value').evaluate(el => el.getRootNode().activeElement === el),
    'Escape cancels pending inspection and restores the originating native action');
  assert.equal(await full().isVisible(), false);
  await page.reload(); await ready();
  gate = new Promise(resolve => { release = resolve; });
  const movedStart = valueReads.length;
  await action('Inspect value').click();
  await settled(async () => valueReads.length === movedStart + 1, 'a value read is pending before focus moves');
  const editPath = page.getByRole('button', {name: 'Edit namespace path', exact: true});
  await editPath.focus(); release(); gate = null; release = null;
  await shown(contract.windows[0].text);
  assert.equal(await editPath.evaluate(el => el.getRootNode().activeElement === el), true, 'read completion never steals deliberately moved focus');
  await page.reload(); await ready();
  gate = new Promise(resolve => { release = resolve; });
  const navigationStart = valueReads.length;
  await action('Inspect value').click();
  await settled(async () => valueReads.length === navigationStart + 1, 'a value read is pending before navigation');
  await page.getByRole('button', {name: 'Edit namespace path', exact: true}).click();
  await page.locator('#debug-go input').fill('/other'); await page.locator('#debug-go input').press('Enter'); await ready('/other');
  release(); gate = null; release = null; await wait(100);
  assert.equal(await page.locator('#debug-workspace').getAttribute('data-path'), '/other');
  assert.equal(await page.locator('.wb-full-value').count(), 0);
  assert.equal(await field('/result').locator('pre').first().textContent(), 'Navigation cancelled the old value read.');
  console.log('PASS: collapsing and navigating cancel in-flight inspection; stale replies do not reopen or replace content.');

  await page.goto(base + '/debug' + fixturePath); await ready();
  let releaseFirst, releaseSecond;
  slotGates.set('/payload/body', new Promise(resolve => { releaseFirst = resolve; }));
  slotGates.set('/invalid', new Promise(resolve => { releaseSecond = resolve; }));
  const queueStart = valueReads.length;
  try {
    await action('Inspect value', '/payload/body').click();
    await action('Inspect value', '/invalid').click();
    await settled(async () => valueReads.length === queueStart + 2, 'exactly two explicit reads occupy the shared request slots');
    await action('Inspect value', '/natural').click();
    await action('Close value', '/natural').waitFor({state: 'visible'});
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(valueReads.length, queueStart + 2, 'the third explicitly opened slot waits without starting a request');
    await action('Close value', '/natural').click();
    releaseFirst(); slotGates.delete('/payload/body');
    await shown(contract.windows[0].text, '/payload/body');
    assert.equal(valueReads.length, queueStart + 2, 'freeing one active slot never starts the cancelled queued request');
    assert.equal(await full('/natural').count(), 0);
    releaseSecond(); slotGates.delete('/invalid');
    await shown(contract.special['/invalid'].text, '/invalid');
    assert.equal(valueReads.length, queueStart + 2, 'settling both active reads does not trigger eager caching or a removed request');
    assert.deepEqual(valueReads.slice(queueStart).map(url => new URL(url, base).searchParams.get('slot')), ['/payload/body', '/invalid']);
  } finally {
    releaseFirst(); releaseSecond(); slotGates.clear();
  }
  console.log('PASS: only two exact reads start concurrently; cancelling a queued third slot removes it before either active request is released.');

  for (const key of ['/invalid', '/control', '/natural', '/zero', '/empty']) {
    await page.goto(base + '/debug' + fixturePath); await ready();
    await action('Inspect value', key).click(); await shown(contract.special[key].text, key);
    assert.equal(await action('Earlier bytes', key).isDisabled(), true);
    assert.equal(await action('Next bytes', key).isDisabled(), true);
    if (key === '/invalid' || key === '/control' || key === '/natural') assert.match(await field(key).locator('.wb-value-status').textContent(), /hex|bytes/i, 'non-text/natural representation is explicit');
    if (key === '/empty') assert.match(await field(key).locator('.wb-value-status').textContent(), /empty text.*0 bytes/i);
    if (key === '/zero') assert.match(await field(key).locator('.wb-value-status').textContent(), /zero.*0 bytes/i);
  }

  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844]]) {
    await page.setViewportSize({width, height}); await page.goto(base + '/debug' + fixturePath); await ready();
    await action('Inspect value').click(); await shown(contract.windows[0].text); await noOverflow();
    const area = full(); await area.waitFor();
    assert.equal(await area.evaluate(el => el.localName), 'ui-scroll-area', 'exact inspection uses the actual Mash scroll component');
    const viewport = area.locator('[part=viewport]'), bar = area.locator('[part=block-scrollbar]');
    await settled(() => viewport.evaluate(el => el.scrollHeight > el.clientHeight + 10), 'exact windows use a bounded Mash scroll viewport');
    assert.ok(await viewport.evaluate(el => el.clientHeight <= 22 * parseFloat(getComputedStyle(document.documentElement).fontSize) + 1));
    await bar.focus(); await bar.press('End');
    await settled(() => viewport.evaluate(el => Math.abs(el.scrollTop - (el.scrollHeight - el.clientHeight)) < 2), 'Mash keyboard scrolling reaches the exact window end');
    await page.screenshot({path: '/private/tmp/shrine-values-light-' + width + '.png', animations: 'disabled'});
  }
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await page.goto(base + '/debug' + fixturePath); await ready();
  await action('Inspect value').click(); await shown(contract.windows[0].text); await noOverflow();
  await page.screenshot({path: '/private/tmp/shrine-values-dark-390.png', animations: 'disabled'});
  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true});
  try {
    await touchContext.route('**/*', routeFixtures);
    const target = await touchContext.newPage(); target.on('pageerror', error => errors.push(error.message));
    await target.goto(base + '/debug' + fixturePath); await ready(fixturePath, target);
    const beforeTouch = valueReads.length;
    await action('Inspect value', '/payload/body', target).tap(); await shown(contract.windows[0].text, '/payload/body', target);
    assert.equal(valueReads.length, beforeTouch + 1);
    await target.screenshot({path: '/private/tmp/shrine-values-touch-390.png', animations: 'disabled'});
    await noOverflow(target);
    await action('Next bytes', '/payload/body', target).tap(); await shown(contract.windows[1].text, '/payload/body', target);
    await noOverflow(target);
    await target.screenshot({path: '/private/tmp/shrine-values-touch-390.png', animations: 'disabled'});
  } finally { await touchContext.close(); }
  assert.deepEqual(writes, []); assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log('PASS: 1440/768/390 light/dark/touch exact-value states, native focus/actions and bounded Mash scrolling; ' + (process.env.DEBUG_DOCUMENT ? 0 : 1) + ' live shell GET(s), ' + valueReads.length + ' fixture chunk reads; no live namespace writes.');
} catch (error) {
  await page.screenshot({path: '/private/tmp/shrine-values-failure.png'});
  console.error('Value context:', {url: page.url(), reads, valueReads, writes, unexpected, errors}); throw error;
} finally { release?.(); await browser.close(); }
