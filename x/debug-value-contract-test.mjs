// Bridge untouched disposable-backend artifacts into the production browser
// DOM and value parsers. This test never contacts a runtime or rewrites a
// document/response. Generate VALUE_ARTIFACTS with x/value-http-test.py first.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {playwright} from './debug-tooling.mjs';

assert.ok(process.env.VALUE_ARTIFACTS, 'Set VALUE_ARTIFACTS to a completed x/value-http-test.py artifact directory.');
const directory = resolve(process.env.VALUE_ARTIFACTS);
const source = fileURLToPath(new URL('../src/foil/debug/', import.meta.url));
const cases = [
  ['text.json', '/text', 0, 4096, 'document.html', '68656c6c6f'],
  ['middle.json', '/text', 2, 2, 'document.html', '6c6c'],
  ['eof.json', '/text', 5, 1, 'document.html', ''],
  ['utf8-split.json', '/long', 2048, 1, 'document.html', '82'],
  ['nul.json', '/nul', 0, 4096, 'document.html', '410042'],
  ['invalid-utf8.json', '/invalid', 0, 4096, 'document.html', 'ff'],
  ['zero.json', '/zero', 0, 4096, 'document.html', ''],
  ['natural.json', '/huge', 255, 2, 'document.html', '0001'],
  ['opaque-key.json', '/a/b', 0, 4096, 'document.html', Buffer.from('opaque slot key').toString('hex')],
  ['large-first.json', '/large', 0, 65536, 'document.html', null],
  ['large-last.json', '/large', 65536, 65536, 'document.html', null],
  ['changed.json', '/text', 0, 4096, 'changed.html', Buffer.from('changed').toString('hex')],
  ['old-after-change.json', '/text', 0, 4096, 'document.html', '68656c6c6f'],
  ['old-after-delete.json', '/text', 0, 4096, 'document.html', '68656c6c6f'],
];
const names = ['document.html', 'root.html', 'changed.html', 'results.json', ...cases.map(entry => entry[0])];
const files = Object.fromEntries(await Promise.all(names.map(async name => [name, await readFile(resolve(directory, name), 'utf8')])));
const hash = text => createHash('sha256').update(text).digest('hex');
const hashes = Object.fromEntries(names.map(name => [name, hash(files[name])]));
const run = JSON.parse(files['results.json']);
assert.equal(run.passed, true, 'the disposable HTTP harness completed successfully');
assert.ok(Number.isInteger(run.port) && run.port > 0 && run.port !== 8138, 'these artifacts came from an isolated port, not the protected live runtime');
assert.ok(Array.isArray(run.requests) && run.requests.length > cases.length);

const {chromium} = playwright();
const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const unexpected = [], errors = [];
const origin = 'http://value-artifacts.invalid';
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url());
  if (request.method() !== 'GET') { unexpected.push(request.method() + ' ' + request.url()); return route.abort(); }
  if (url.origin === origin && url.pathname === '/') return route.fulfill({status: 200, contentType: 'text/html',
    body: '<!doctype html><meta charset="utf-8"><title>Untouched backend artifact parser bridge</title>'});
  if (url.origin === origin && /^\/bridge\/[a-z-]+\.js$/.test(url.pathname)) return route.fulfill({status: 200, contentType: 'application/javascript',
    body: await readFile(resolve(source, url.pathname.split('/').at(-1)), 'utf8')});
  if (url.origin === origin && url.pathname === '/favicon.ico') return route.fulfill({status: 204});
  unexpected.push(request.url()); return route.abort();
});
page.on('pageerror', error => errors.push(error.message));

try {
  await page.goto(origin);
  const parsed = await page.evaluate(async ({files, cases, requests}) => {
    const {parseDebugDocument} = await import('/bridge/namespace.js');
    const {parseValueMetadata, valueWindowURL, parseValueChunk, renderValueWindow} = await import('/bridge/values.js');
    const documents = {}, explicit = {};
    for (const name of ['document.html', 'root.html', 'changed.html']) {
      // Parse the server bytes directly. No selectors, metadata or content are
      // inserted/rewritten before either production parser sees this document.
      const doc = new DOMParser().parseFromString(files[name], 'text/html');
      const view = parseDebugDocument(doc);
      if (!view.record) throw new Error(name + ' did not expose a real own record.');
      const slots = Object.fromEntries(view.record.slots.map(slot => [slot.key, slot]));
      explicit[name] = [];
      for (const limb of doc.querySelectorAll('#debug-main section[aria-label="Record"] sh-myth > sh-limb')) {
        const key = limb.querySelector(':scope > sh-slot')?.getAttribute('title');
        // The namespace adapter deliberately quarantines malformed metadata.
        // Calling the strict parser too proves no server field was silently
        // downgraded to unknown by that compatibility behavior.
        const fidelity = parseValueMetadata(limb, view.path, key);
        explicit[name].push({key, fidelity, adapted: slots[key]?.fidelity});
      }
      documents[name] = {path: view.path, slots, children: view.children};
    }
    const checked = [];
    for (const [name, slot, offset, limit, documentName] of cases) {
      const metadata = documents[documentName].slots[slot]?.fidelity;
      if (!metadata?.url) throw new Error(name + ' lacks a real metadata-provided exact endpoint.');
      const destination = new URL(metadata.url, location.href);
      const entry = requests.find(entry => {
        if (entry.status !== 200 || !entry.path.startsWith('/debug-read/value?')) return false;
        const url = new URL(entry.path, location.href), query = url.searchParams;
        return query.get('path') === metadata.path && query.get('slot') === slot && query.get('epoch') === metadata.epoch &&
          query.get('offset') === String(offset) && query.get('limit') === String(limit);
      });
      if (!entry) throw new Error('No real successful HTTP request matches ' + name + '.');
      const url = new URL(entry.path, location.href), query = url.searchParams;
      const request = {url: entry.path, path: query.get('path'), slot: query.get('slot'), epoch: query.get('epoch'),
        representation: metadata.representation, total: metadata.bytes, offset: query.get('offset'), limit: Number(query.get('limit'))};
      const json = JSON.parse(files[name]);
      const chunk = parseValueChunk(json, request);
      const rendered = renderValueWindow(chunk, {...request, start: request.offset, end: String(BigInt(request.offset) + BigInt(chunk.bytes.length))});
      checked.push({name, metadata, request, endpoint: {path: destination.searchParams.get('path'), slot: destination.searchParams.get('slot'), epoch: destination.searchParams.get('epoch')},
        json, bytes: [...chunk.bytes], rendered: {text: rendered.text, format: rendered.format, bytes: [...rendered.bytes]}, firstWindow: valueWindowURL(metadata)});
    }
    return {documents, explicit, checked};
  }, {files, cases, requests: run.requests});

  const original = parsed.documents['document.html'], changed = parsed.documents['changed.html'];
  assert.equal(original.path, '/0x11/demo'); assert.equal(changed.path, '/0x11/demo');
  assert.equal(parsed.documents['root.html'].path, '/0x11');
  assert.deepEqual(Object.keys(original.slots).sort(), ['/a/b', '/body', '/escaped', '/huge', '/invalid', '/large', '/long', '/nul', '/opaque', '/text', '/threshold', '/zero'].sort());
  const expected = {
    '/text': ['complete', null, '5', '5', 'utf8-bytes'],
    '/threshold': ['complete', null, '2048', '2048', 'utf8-bytes'],
    '/long': ['preview', 'byte-limit', '2054', '2047', 'utf8-bytes'],
    '/large': ['preview', 'byte-limit', '70003', '2048', 'utf8-bytes'],
    '/body': ['preview', 'byte-limit', '1025', '1024', 'natural-le-bytes'],
    '/huge': ['preview', 'numeric-summary', '257', null, 'natural-le-bytes'],
    '/nul': ['preview', 'non-text-bytes', '3', null, 'utf8-bytes'],
    '/invalid': ['preview', 'non-text-bytes', '1', null, 'utf8-bytes'],
    '/zero': ['complete', null, '0', '0', 'natural-le-bytes'],
    '/opaque': ['opaque', 'semantic-summary', null, null, null],
    '/a/b': ['complete', null, '15', '15', 'utf8-bytes'],
  };
  const epoch = original.slots['/text'].fidelity.epoch;
  assert.match(epoch, /^(0|[1-9]\d*)$/);
  for (const [key, values] of Object.entries(expected)) {
    const metadata = original.slots[key].fidelity;
    assert.deepEqual([metadata.state, metadata.reason, metadata.bytes, metadata.previewBytes, metadata.representation], values, 'exact server fidelity for ' + key);
    assert.equal(metadata.epoch, epoch, 'one original record carries one immutable read epoch');
    assert.equal(metadata.path, '/0x11/demo'); assert.equal(metadata.slot, key);
    if (key === '/opaque') assert.equal(metadata.url, null);
    else {
      const url = new URL(metadata.url, origin);
      assert.equal(url.pathname, '/debug-read/value');
      assert.equal(url.searchParams.get('path'), '/0x11/demo'); assert.equal(url.searchParams.get('slot'), key);
      assert.equal(url.searchParams.get('epoch'), epoch); assert.equal(url.searchParams.get('offset'), '0');
      assert.equal(url.searchParams.get('limit'), '65536');
    }
  }
  assert.equal(original.slots['/text'].text, 'hello');
  assert.equal(original.slots['/threshold'].text, 'a'.repeat(2048));
  assert.equal(original.slots['/long'].text, 'a'.repeat(2047) + '…', 'real preview stops before the incomplete euro scalar');
  assert.equal(original.slots['/body'].text, 'b'.repeat(1024) + '…');
  assert.equal(original.slots['/escaped'].text, '<script>alert(1)</script> & quoted');
  assert.equal(original.slots['/a/b'].text, 'opaque slot key');
  assert.equal(original.children.includes('/0x11/demo/a'), false, 'the opaque multi-segment slot key is not manufactured into a child namespace');
  assert.equal(original.slots['/opaque'].reference, '/other', 'opaque exact inspection does not erase authored reference semantics');
  for (const [name, fields] of Object.entries(parsed.explicit)) {
    assert.ok(fields.length > 0, name + ' exposes real slot metadata');
    for (const field of fields) {
      assert.notEqual(field.fidelity.state, 'unknown', name + ': ' + field.key + ' has explicit valid metadata');
      assert.deepEqual(field.adapted, field.fidelity, 'the namespace adapter retains strict backend fidelity without compatibility downgrade');
      assert.match(field.fidelity.epoch, /^(0|[1-9]\d*)$/, name + ': verified epoch remains decimal text');
    }
  }
  const chunks = Object.fromEntries(parsed.checked.map(entry => [entry.name, entry]));
  for (const [name, , , , , hex] of cases) {
    const entry = chunks[name];
    assert.equal(Buffer.from(entry.bytes).toString('hex'), entry.json.hex, name + ': parsing preserves every byte');
    assert.deepEqual(entry.rendered.bytes, entry.bytes, name + ': rendering never rewrites the logical raw bytes');
    if (hex !== null) assert.equal(entry.json.hex, hex, name + ': backend fixture expected bytes');
    assert.deepEqual(entry.endpoint, {path: entry.metadata.path, slot: entry.metadata.slot, epoch: entry.metadata.epoch});
    assert.equal(entry.firstWindow.start, '0'); assert.ok(entry.firstWindow.limit <= 4102);
  }
  assert.equal(chunks['text.json'].rendered.text, 'hello');
  assert.equal(chunks['middle.json'].rendered.text, 'll');
  for (const name of ['utf8-split.json', 'nul.json', 'invalid-utf8.json', 'natural.json', 'zero.json']) assert.equal(chunks[name].rendered.format, 'hex');
  assert.equal(chunks['utf8-split.json'].rendered.text, '82', 'an isolated incomplete UTF-8 byte remains exact hex, not a replacement character');
  assert.equal(chunks['zero.json'].json.total, '0'); assert.equal(chunks['zero.json'].json.complete, true);
  assert.equal(chunks['eof.json'].json.next, null); assert.equal(chunks['eof.json'].json.hex, '');
  assert.equal(Buffer.concat([Buffer.from(chunks['large-first.json'].bytes), Buffer.from(chunks['large-last.json'].bytes)]).toString('utf8'), 'a'.repeat(70000) + 'END');
  assert.equal(chunks['large-first.json'].json.recordEpoch, chunks['large-last.json'].json.recordEpoch);
  assert.equal(changed.slots['/text'].text, 'changed');
  assert.equal(changed.slots['/text'].fidelity.bytes, '7');
  assert.ok(BigInt(changed.slots['/text'].fidelity.epoch) > BigInt(epoch));
  assert.ok(BigInt(chunks['changed.json'].json.recordEpoch) > BigInt(chunks['text.json'].json.recordEpoch));
  assert.deepEqual(chunks['old-after-change.json'].json, chunks['text.json'].json, 'old epoch after edit still selects the identical exact original assertion');
  assert.deepEqual(chunks['old-after-delete.json'].json, chunks['text.json'].json, 'old epoch after deletion still selects the identical exact original assertion');
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  for (const name of names) assert.equal(hash(await readFile(resolve(directory, name), 'utf8')), hashes[name], name + ' was not rewritten');
  console.log('PASS: untouched real backend HTML and ' + cases.length + ' saved HTTP chunks pass production DOM/metadata/byte parsers; exact text, UTF-8 split, naturals, root epochs, opaque slot identities and old-after-edit/delete fidelity.');
  console.log('Artifacts: ' + directory + '; disposable port ' + run.port + '; zero live requests or artifact mutations.');
} finally { await browser.close(); }
