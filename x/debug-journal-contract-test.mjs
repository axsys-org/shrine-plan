// Validate real, isolated HTTP harness artifacts with the production browser
// parser. No namespace is contacted and source HTML is never executed.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {playwright} from './debug-tooling.mjs';

const directory = process.argv[2];
if (!directory) throw new Error('Pass the artifact directory from the isolated journal HTTP harness.');
const {chromium} = playwright();
const dataURL = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const journalSource = await readFile(new URL('../src/foil/debug/journal.js', import.meta.url), 'utf8');
const valueSource = await readFile(new URL('../src/foil/debug/values.js', import.meta.url), 'utf8');
const parserSource = await readFile(new URL('../src/foil/debug/namespace.js', import.meta.url), 'utf8');
assert.ok(parserSource.includes("from './journal.js'"), 'use the production parser dependency');
const parserURL = dataURL(parserSource.replace("from './journal.js'", 'from ' + JSON.stringify(dataURL(journalSource)))
  .replace("from './values.js'", 'from ' + JSON.stringify(dataURL(valueSource))));
const expected = {
  latest: {before: null, nextBefore: '9961', limit: 40, first: 10000, count: 40},
  older: {before: '9961', nextBefore: '9921', limit: 40, first: 9960, count: 40},
  empty: {before: '1', nextBefore: null, limit: 40, first: 0, count: 0},
  last: {before: '2', nextBefore: null, limit: 1, first: 1, count: 1},
  huge: {before: '123456789012345678901234567890', nextBefore: '9999', limit: 2, first: 10000, count: 2},
  repeated: {before: null, nextBefore: '9961', limit: 40, first: 10000, count: 40},
};
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.route('**/*', route => route.abort());
  for (const [name, contract] of Object.entries(expected)) {
    const html = await readFile(resolve(directory, name + '.html'), 'utf8');
    const actual = await page.evaluate(async ({html, parserURL}) => {
      const {parseDebugDocument} = await import(parserURL);
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const view = parseDebugDocument(doc);
      return {path: view.path, kind: view.kind, writable: view.writable, pagination: view.pagination,
        children: view.children, summaries: view.childSummaries.map(summary => summary.path),
        events: [...doc.querySelectorAll('.debug-events > .debug-event')].map(event => event.dataset.reference),
        older: doc.querySelector('[data-journal-older]')?.getAttribute('href') || null,
        latest: doc.querySelector('[data-journal-latest]')?.getAttribute('href') || null};
    }, {html, parserURL});
    const journalRoot = '/0x11/log';
    const children = Array.from({length: contract.count}, (_, index) => journalRoot + '/' + (contract.first - index));
    assert.equal(actual.path, journalRoot); assert.equal(actual.kind, 'journal'); assert.equal(actual.writable, false);
    assert.deepEqual(actual.pagination, {kind: 'journal', before: contract.before, nextBefore: contract.nextBefore,
      limit: contract.limit, total: '10000', epoch: '10000'}, name + ': exact physical metadata');
    assert.deepEqual(actual.children, children, name + ': descending selected keys');
    assert.deepEqual(actual.summaries, children, name + ': matching navigation summaries');
    assert.deepEqual(actual.events, children, name + ': matching event rows including malformed payloads');
    assert.equal(actual.older ? new URL(actual.older, 'http://test.invalid').searchParams.get('before') : null, contract.nextBefore);
    assert.equal(Boolean(actual.latest), contract.before !== null);
    console.log('PASS: real HTTP ' + name + ' document matches the production parser and native pager.');
  }
} finally { await browser.close(); }
