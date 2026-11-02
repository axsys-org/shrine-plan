const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the page chrome against the existing Goo outcome subscription.
// The harness exposes no transport: the parent must never issue the action.
function fixture() {
  const listeners = new Set(), frames = [], animation = [];
  const status = {textContent: ''}, textarea = {value: 'saved source', addEventListener() {}};
  let mutation, reloads = 0, unsubscriptions = 0;
  const events = new Map();
  const frame = {
    isConnected: true,
    contentWindow: {GooActions: {subscribeOutcomes(listener) {
      listeners.add(listener);
      return () => { listeners.delete(listener); unsubscriptions++; };
    }}},
    parentElement: {querySelector() { return status; }},
    addEventListener(name, callback) { events.set(name, callback); },
    removeEventListener(name) { events.delete(name); }
  };
  frames.push(frame);
  const shell = {
    dataset: {page: '/0x11/app/nenex/w/procedure', corpus: '/0x11/app/nenex/w'},
    querySelectorAll(selector) { return selector === 'iframe[data-nenex-publication]' ? frames : []; },
    addEventListener() {}
  };
  const document = {
    querySelector(selector) {
      return selector === '.wiki-shell' ? shell : selector === '#page-source' ? textarea : null;
    },
    addEventListener() {}, getElementById() { return null; }
  };
  const context = {
    document, window: {}, location: {hash: '', reload() { reloads++; }},
    addEventListener() {}, requestAnimationFrame(callback) { animation.push(callback); },
    MutationObserver: class { constructor(callback) { mutation = callback; } observe() {} },
    URL, Map
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../interface.js'), 'utf8'), context);
  return {frame, textarea, status, events, listeners,
    decorate() { mutation(); },
    outcome(outcome) { for (const listener of [...listeners]) listener({outcome}); },
    settle() { while (animation.length) animation.shift()(); },
    remove() { frame.isConnected = false; frames.length = 0; mutation(); },
    counts() { return {reloads, unsubscriptions, listeners: listeners.size}; }};
}

const clean = fixture();
clean.decorate(); clean.decorate();
assert.equal(clean.listeners.size, 1, 'decoration does not duplicate subscriptions');
clean.outcome('unknown'); clean.outcome('rejected'); clean.settle();
assert.equal(clean.counts().reloads, 0, 'uncertain or rejected actions cannot refresh the page');
assert.equal(clean.status.textContent, '', 'uncertain or rejected actions do not claim publication');
clean.outcome('accepted'); clean.outcome('accepted'); clean.settle();
assert.equal(clean.counts().reloads, 1, 'accepted publication refreshes once');

const dirty = fixture();
dirty.textarea.value = 'unsaved authored procedure';
dirty.outcome('accepted'); dirty.settle();
assert.equal(dirty.counts().reloads, 0, 'publication does not discard source drafts');
assert.equal(dirty.textarea.value, 'unsaved authored procedure');
assert.match(dirty.status.textContent, /unsaved source is retained/);
dirty.events.get('load')();
assert.deepEqual(dirty.counts(), {reloads: 0, unsubscriptions: 1, listeners: 1}, 'frame reload replaces its subscription');
dirty.outcome('accepted'); dirty.remove(); dirty.settle();
assert.deepEqual(dirty.counts(), {reloads: 0, unsubscriptions: 2, listeners: 0}, 'removed frame releases subscription and queued refresh');
assert.equal(dirty.events.size, 0, 'removed frame releases its load handler');
console.log('PASS Nenex publication chrome (10 assertions)');
