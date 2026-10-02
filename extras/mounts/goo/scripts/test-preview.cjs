'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const { renderDocument } = require('../static/inspector/preview.js');

test('preview sends its render context to Goo and preserves the returned surface', async (t) => {
  const requests = [];
  const html = '<div class="goo-surface" dir="rtl">server result</div>';
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    requests.push(JSON.parse(options.body));
    return { ok: true, json: async () => ({ measurement: { plan: null }, html }) };
  });
  const previousObserver = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
  t.after(() => { globalThis.ResizeObserver = previousObserver; });
  const target = {
    style: {}, dataset: {}, innerHTML: '',
    querySelectorAll: () => [], contains: () => false,
    firstElementChild: { setAttribute: () => assert.fail('server direction must not be rewritten') },
  };
  const doc = {
    documentElement: { style: { setProperty() {} } },
    getElementById: (id) => id === 'goo-render-root' ? target : {
      textContent: JSON.stringify({ version: 1, tree: null, viewPath: '/full' }),
    },
  };
  const dispose = await renderDocument(doc, () => {}, { contentWidth: 143.5, textScale: 1.25, direction: 'rtl' });
  assert.deepEqual(requests, [{ version: 1, tree: null, width: 143.5, textScale: 1.25, direction: 'rtl' }]);
  assert.equal(target.innerHTML, html);
  assert.equal(target.dataset.layoutReady, 'true');
  dispose();
});
