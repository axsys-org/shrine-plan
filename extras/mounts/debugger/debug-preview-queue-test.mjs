// Test the production transport, not a second implementation of its scheduler.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const load = async name => import('data:text/javascript;base64,' + Buffer.from(readFileSync(new URL('./' + name, import.meta.url))).toString('base64'));
const {createReadCoordinator} = await load('read-coordinator.js');
const {BoundedCache} = await load('bounded-cache.js');
const {isJournalRoot} = await load('journal.js');
for (const path of ['/0x11/log', '/0x0001/log', '/0xff/log']) assert.ok(isJournalRoot(path));
for (const path of ['/0x1/log', '/0x00/log', '/0x1100/log', '/0xFF/log', '/sys/log', '/0x11/log/1'])
  assert.equal(isJournalRoot(path), false, path);
const started = [], pending = new Map();
let active = 0, maximum = 0;
const fetcher = (url, {signal}) => new Promise((resolve, reject) => {
  started.push(url); active++; maximum = Math.max(maximum, active);
  const done = fn => value => { active--; signal.removeEventListener('abort', abort); fn(value); };
  const abort = () => done(reject)(signal.reason);
  signal.addEventListener('abort', abort, {once: true});
  pending.set(url, {resolve: done(resolve), reject: done(reject), signal});
});
const reader = createReadCoordinator({fetcher});
const response = text => new Response(text, {headers: {'content-type': 'text/html'}});
const drain = () => new Promise(resolve => setImmediate(resolve));
const a = reader.read('/a'), b = reader.read('/b');
const obsolete = new AbortController();
const c = reader.read('/c', {signal: obsolete.signal});
const d = reader.read('/d');
assert.deepEqual(started, ['/a', '/b'], 'background work leaves foreground capacity');
const foreground = reader.read('/foreground', {priority: 1});
assert.deepEqual(started, ['/a', '/b', '/foreground']);
obsolete.abort();
await assert.rejects(c, {name: 'AbortError'});
assert.ok(!started.includes('/c'));
pending.get('/foreground').resolve(response('foreground')); await foreground;
pending.get('/b').resolve(response('B')); assert.equal(await b, 'B'); await drain();
assert.ok(started.includes('/d'));
pending.get('/a').resolve(response('A')); pending.get('/d').resolve(response('D'));
assert.deepEqual(await Promise.all([a, d]), ['A', 'D']);
assert.equal(maximum, 3); assert.equal(reader.size, 0);

const one = new AbortController(), two = new AbortController();
const shared1 = reader.read('/shared', {signal: one.signal});
const shared2 = reader.read('/shared', {signal: two.signal, priority: 1});
assert.equal(started.filter(url => url === '/shared').length, 1);
one.abort(); await assert.rejects(shared1, {name: 'AbortError'});
assert.equal(pending.get('/shared').signal.aborted, false, 'one subscriber does not cancel another');
pending.get('/shared').resolve(response('shared')); assert.equal(await shared2, 'shared');
const rich = reader.read('/scope?workspace', {priority:1});
const light = reader.read('/scope?outline', {alternatives:['/scope?workspace']});
assert.equal(started.includes('/scope?outline'),false);
pending.get('/scope?workspace').resolve(response('rich'));
assert.deepEqual(await Promise.all([rich, light]), ['rich','rich'], 'compatible scopes share immutable text');
const cancelled = new AbortController();
const old = reader.read('/old', {signal: cancelled.signal}); cancelled.abort();
await assert.rejects(old, {name: 'AbortError'}); await drain();
assert.equal(reader.size, 0);
const fresh = reader.read('/old'); pending.get('/old').resolve(response('fresh'));
assert.equal(await fresh, 'fresh');
const before = started.length;
await assert.rejects(reader.read('/already', {signal: AbortSignal.abort()}), {name: 'AbortError'});
assert.equal(started.length, before);
const bad = reader.read('/bad'); pending.get('/bad').reject(new Error('network'));
await assert.rejects(bad, /network/); assert.equal(reader.active, 0);

const bounded = createReadCoordinator({maxBytes: 3, fetcher: async () => response('large')});
await assert.rejects(bounded.read('/large'), /budget/);
assert.equal(bounded.size, 0);
let aborted = false;
const timed = createReadCoordinator({timeout: 5, fetcher: (url, {signal}) => new Promise((resolve, reject) => signal.addEventListener('abort', () => {aborted = true; reject(signal.reason);}))});
await assert.rejects(timed.read('/slow'), {name: 'TimeoutError'}); assert.ok(aborted);

let now = 0;
const cache = new BoundedCache(2, 30, [], () => now);
cache.set('a', 1).set('b', 2); assert.equal(cache.get('a'), 1);
cache.set('c', 3); assert.equal(cache.has('b'), false);
now = 31; assert.equal(cache.has('a'), false); assert.equal(cache.get('c'), undefined);
for (let i = 0; i < 2000; i++) cache.set(i, i);
assert.equal(cache.size, 2); assert.equal(cache.expiry.size, 2);
cache.clear(); assert.equal(cache.expiry.size, 0);
console.log('PASS: shared budget, foreground reserve, deduplication, independent cancellation, deadlines, byte limits, bounded LRU and TTL.');

const navigationSource = readFileSync(new URL('./navigation.js', import.meta.url), 'utf8');
const start = navigationSource.indexOf('  async function navigate(');
const end = navigationSource.indexOf('  async function inspect(', start);
assert.ok(start >= 0 && end > start);
const navigations = new Map();
const harness = new Function('read', 'document', 'history', 'CustomEvent', 'isJournalRoot', `
  let busy=false, activeNavigation=null, current='/initial', visits=['/initial'], visitPages=[null], visitCollections=[''], cursor=0, page=null, collection='';
  const collectionQuery=value=>value||'';
  const mayLeave=()=>true, focusedWithinMain=()=>false, setBusy=value=>{busy=value;};
  const show=answer=>{current=answer.path; collection=answer.query||'';}, currentPath=()=>current;
  const sameJournalPage=()=>true, currentURL=()=>current, persist=()=>{}, renderNavigation=()=>{}, report=()=>{}, journalPage=()=>null;
  ${navigationSource.slice(start, end)}
  return {navigate, current:()=>current, busy:()=>busy, lock:()=>{busy=true; activeNavigation=null;}};
`)((path, options) => new Promise(resolve => navigations.set(path, {resolve, signal: options.signal})),
  {dispatchEvent() {}}, {pushState() {}}, class {constructor(type, data) {this.type=type; this.detail=data?.detail;}}, isJournalRoot);
const first = harness.navigate('/first');
const second = harness.navigate('/second');
assert.ok(navigations.get('/first').signal.aborted);
navigations.get('/second').resolve({path:'/second', view:{}});
assert.equal(await second, true);
navigations.get('/first').resolve({path:'/first', view:{}});
assert.equal(await first, false);
assert.equal(harness.current(), '/second', 'late response cannot overwrite newer navigation');
assert.equal(harness.busy(), false);
harness.lock(); assert.equal(await harness.navigate('/during-write'), false);
assert.equal(navigations.has('/during-write'), false, 'write locking remains intact');
console.log('PASS: latest navigation wins even when the old transport resolves late; writes remain locked.');
