const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const context = {};
vm.runInNewContext(fs.readFileSync(require.resolve('../goo-actions.js'), 'utf8'), context);
const {choose} = context.GooActions;
const template = (kind, slot = '/summary', role = '/card') => ({
  dataset: {declarationKind: kind, slot, role}
});

test('view selection ignores panes with the same role and slot', () => {
  const view = template('view');
  assert.equal(choose([template('pane'), view], '/summary', '/card'), view);
});

test('a pane cannot satisfy a follower view selection', () => {
  assert.throws(() => choose([template('pane')], '/summary'), /No view/);
});

test('view ambiguity is still diagnosed after excluding panes', () => {
  assert.throws(() => choose([template('pane'), template('view'), template('view')], '/summary'), /Competing views/);
});
