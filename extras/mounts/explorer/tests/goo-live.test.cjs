const {test} = require('node:test');
const assert = require('node:assert/strict');
const live = require('../goo-live.js');
const {slotLayout, recordHTML, actionHTML, askedHTML, mcpSource, adapt} = live;

// ---- fixtures: read answers in the mount's own shape (knobs.md: {path, exists, reference, reference_y, reference_z, properties, children, nodes, next})
const N = '/0x11/user/org';
const ref = (care, cas, path) => `/h/${care}/${cas}/${path.split('/').length - 1}${path}`;
const members = {
  path: N + '/members', exists: true, reference: ref('x', 3, N + '/members'), reference_y: ref('y', 5, N + '/members'), reference_z: ref('z', 5, N + '/members'),
  properties: {'/team': 'eng'},
  children: [
    {path: N + '/members/alice', exists: true, reference: ref('x', 2, N + '/members/alice'), reference_y: null, reference_z: null,
      properties: {'/role': 'lead', '/salary': '165', '/manager': ref('x', 0, N + '/members/bob'), '/bio': 'joined in 2019 as the second engineer; leads the platform group and runs the weekly review'},
      children: []},
    {path: N + '/members/bob', exists: true, reference: ref('x', 1, N + '/members/bob'), reference_y: null, reference_z: null,
      properties: {'/role': 'eng', '/salary': '110', '/notes': {type: 'text', size: 12000, reference: ref('x', 1, N + '/members/bob')}},
      children: []}],
  nodes: 3, next: null};
const headcount = {
  path: N + '/views/headcount', exists: true, reference: ref('x', 1, N + '/views/headcount'), reference_y: null, reference_z: null,
  properties: {'/sys/weft': ref('x', 1, '/0x11/weft/stdlib/count'), '/sys/tack': ref('y', 0, N + '/members'), '/into': '/headcount'}, children: [], nodes: 1, next: null};
const payroll = {
  path: N + '/views/payroll', exists: true, reference: ref('x', 1, N + '/views/payroll'), reference_y: null, reference_z: null,
  properties: {'/sys/weft': ref('x', 1, '/0x11/weft/stdlib/sum'), '/sys/tack': ref('y', 4, N + '/members'), '/slot': '/salary', '/into': '/total', '/budget': ref('x', 0, N + '/budgets/2026')}, children: [], nodes: 1, next: null};
const xOf = (p, props, children = []) => ({path: '/x' + p, exists: true, reference: ref('x', 1, '/x' + p), reference_y: null, reference_z: null, properties: props, children, nodes: 1 + children.length, next: null});
const cOf = (p, props) => ({path: '/c/x' + p, exists: true, reference: ref('x', 1, '/c/x' + p), reference_y: null, reference_z: null, properties: props, children: [], nodes: 1, next: null});
const culled = {path: N + '/deals/f1', exists: false, reference: ref('x', 2, N + '/deals/f1'), reference_y: null, reference_z: null, properties: {}, children: [], nodes: 1, next: null};
const folder = {path: N + '/empty', exists: false, reference: null, reference_y: null, reference_z: null, properties: {}, children: [], nodes: 1, next: null};

// ---- slot layouts (GUIDE.md section 3)
test('slotLayout picks the figure, the grid, the list, and wraps long text', () => {
  assert.equal(slotLayout({}), '');
  assert.match(slotLayout({total: 395}), /class="sv-one">395<span class="u">total/);
  const grid = slotLayout({role: 'lead', team: 'eng', salary: 165});
  assert.match(grid, /^<div class="sv-grid">/);
  assert.equal((grid.match(/<div class="s /g) || []).length, 3);
  assert.match(slotLayout({a: 1, b: 2, c: 3, d: 4, e: 5, f: 6, g: 7}), /^<div class="sv-list">/);
  assert.match(slotLayout({note: 'x'.repeat(81), amount: 5}), /^<div class="sv-list">/);
  assert.match(slotLayout({note: 'a value of more than twenty-four characters', amount: 5}), /class="s wide"/);
  assert.match(slotLayout({client: '-> studio/clients/acme', amount: 5}), /class="sv-v ref" data-path="studio\/clients\/acme"/);
  assert.match(slotLayout({held: '-> /x/studio/views/closed @ 4', amount: 5}), /data-path="studio\/views\/closed"/);
});

// ---- the record card
const fakeSource = (answers, asked = new Map(), cells = new Map()) => ({async answer(p) { return answers[p]; }, _asked: asked, _cells: cells});
test('recordHTML on a cell shows the answer and folds made of', async () => {
  const cell = {formula: '-> /weft/stdlib/sum', over: '-> studio/people', slot: 'salary', into: 'total'};
  const source = fakeSource({'studio/views/payroll': {tree: {name: 'payroll', path: 'studio/views/payroll', slots: {total: 395}, kids: []}}});
  const html = await recordHTML(source, {path: 'studio/views/payroll', record: cell, kids: [], case: 3}, false, new Set());
  assert.match(html, /<div class="sv-rec " data-path="studio\/views\/payroll" data-case="3">/);
  assert.match(html, /class="sv-one">395<span class="u">total/);
  assert.match(html, /<details class="sv-made"><summary>made of<\/summary>/);
  assert.ok(html.indexOf('sv-one') < html.indexOf('sv-made'), 'the answer comes before made of');
  assert.match(html, /sv-made.*sum.*studio\/people/s);
  const faulted = await recordHTML(fakeSource({c: {bad: 'cycle through c'}}), {path: 'c', record: cell, kids: []}, false, new Set());
  assert.match(faulted, /<div class="sv-note bad">cycle through c<\/div>/);
  const gone = await recordHTML(fakeSource({}), {path: 'd', record: null, kids: []}, true, new Set());
  assert.match(gone, /<div class="sv-gone">deleted<\/div>/); assert.match(gone, /<span class="p">d<\/span>/);
});
test('recordHTML draws children as rows, nested, folded past three levels, and bumps the touched', async () => {
  const deep = {name: 'l3', path: 'a/l1/l2/l3', slots: {n: 3}, kids: [{name: 'l4', path: 'a/l1/l2/l3/l4', slots: {n: 4}, kids: []}]};
  const r = {path: 'a', record: {k: 'v'}, kids: [{name: 'l1', path: 'a/l1', slots: {n: 1}, kids: [{name: 'l2', path: 'a/l1/l2', slots: {n: 2}, kids: [deep]}]}, {name: 'f', path: 'a/f', slots: {}, kids: []}]};
  const html = await recordHTML(fakeSource({}), r, false, new Set(['a/l1']));
  assert.match(html, /<div class="sv-row bump" data-path="a\/l1"/);
  assert.match(html, /<span class="more">1 beneath<\/span>/);
  assert.doesNotMatch(html, /data-path="a\/l1\/l2\/l3\/l4"/);
  assert.match(html, /<span class="n folder">f<\/span>/);
});

// ---- the outline: what was asked of a thing hangs beneath it
test('the outline nests a chain two deep and names a join\'s second source', () => {
  const closed = {path: 'studio/views/closed', formula: 'where', answer: '2 rows', inputs: [{path: 'studio/deals', pin: null}]};
  const revenue = {path: 'studio/views/revenue', formula: 'sum', answer: '140 revenue', inputs: [{path: '/x/studio/views/closed', pin: null}]};
  const left = {path: 'studio/views/left', formula: 'subtract', answer: '360 left', inputs: [{path: '/x/studio/views/revenue', pin: null}, {path: 'studio/budgets/2026', pin: 4, view: true}]};
  const board = {path: 'studio/views/board', formula: 'sum', note: 'needs slot', inputs: [{path: 'studio/deals', pin: 7}]};
  const asked = new Map([['studio/deals', [{...closed, pin: null}, {...board, pin: 7}]], ['studio/views/closed', [{...revenue, pin: null}]], ['studio/views/revenue', [{...left, pin: null}]], ['studio/budgets/2026', [{...left, pin: 4, view: true}]]]);
  const html = askedHTML(fakeSource({}, asked), 'studio/deals', 1);
  const at = s => { const i = html.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(at('<span class="n">closed</span>') < at('<span class="n">revenue</span>') && at('<span class="n">revenue</span>') < at('<span class="n">left</span>'), 'deals -> closed -> revenue -> left');
  assert.equal((html.match(/<div class="sv-asked">/g) || []).length, 3, 'three levels of indentation');
  assert.match(html, /<span class="o">\+ 2026<\/span>/);
  assert.match(html, /<span class="f">sum · held at 7<\/span><span class="n">board<\/span><span class="m note">needs slot<\/span>/);
  assert.match(html, /<span class="f">subtract<\/span><span class="n">left<\/span><span class="o">\+ 2026<\/span><span class="m">360 left<\/span>/);
  assert.equal(askedHTML(fakeSource({}, asked), 'studio/nothing', 1), '');
});

// ---- the action tree
test('actionHTML collapses a batch to one line with the right count and what it moved', () => {
  const asked = new Map([['studio/deals', [{path: 'studio/views/closed', answer: '4 rows'}, {path: 'studio/views/by_owner', answer: '235 total'}]]]);
  const touched = Array.from({length: 20}, (_, i) => `studio/deals/w${i}`);
  const html = actionHTML(fakeSource({}, asked), {epoch: 12, label: 'make 20 deals', who: 'tester', touched}, false);
  assert.equal((html.match(/<summary>/g) || []).length, 1);
  assert.match(html, /^<details class="sv-act" data-epoch="12" >/);
  assert.match(html, /<span class="ep">12<\/span><span class="lab">make 20 deals<\/span><span class="who">tester<\/span><span class="cnt">20 records<\/span>/);
  assert.match(html, /<span class="mv">closed 4 rows · by_owner 235 total<\/span>/);
  assert.match(actionHTML(fakeSource({}, asked), {epoch: 3, label: 'poke alice', who: 'agent', touched: ['studio/people/alice']}, true), /data-epoch="3" open>.*<span class="cnt">1 record<\/span>/);
  assert.match(actionHTML(fakeSource({}), {epoch: 4, label: '<b>', who: 'agent', touched: ['a']}, false), /<span class="lab">&lt;b><\/span>/);
});
test('a presented item renders shown with the path it showed', () => {
  const html = actionHTML(fakeSource({}), {epoch: 'shown', label: 'show studio/views', who: 'agent', touched: [], shown: {path: 'studio/views', care: 'z', case: 0}}, true);
  assert.match(html, /<span class="ep">shown<\/span><span class="lab">show studio\/views<\/span><span class="who">agent<\/span><span class="cnt">studio\/views<\/span>/);
});

// ---- the adapter: a read answer to the tree shape
test('readOf maps a captured read answer to the tree shape', () => {
  const r = adapt.readOf(members);
  assert.equal(r.path, '0x11/user/org/members'); assert.equal(r.case, '3'); assert.equal(r.next, null);
  assert.deepEqual(r.record, {team: 'eng'});
  assert.equal(r.kids.length, 2);
  const [alice, bob] = r.kids;
  assert.equal(alice.name, 'alice'); assert.equal(alice.path, '0x11/user/org/members/alice'); assert.equal(alice.case, '2');
  assert.equal(alice.slots.salary, 165, 'a number as text becomes a number');
  assert.equal(alice.slots.manager, '-> 0x11/user/org/members/bob', 'a live reference is -> path');
  assert.equal(alice.slots.role, 'lead');
  assert.equal(bob.slots.notes, 'text, 12,000 bytes', 'a large value is its type and size');
  assert.deepEqual(adapt.readOf(culled).record, null, 'exists false with a case is a culled record');
  assert.deepEqual(adapt.readOf(folder).record, {}, 'exists false without a case is a bare folder');
});
test('slotsOf makes a cell the renderer recognises: weft as formula, tack as over with its pin', () => {
  const hc = adapt.slotsOf(headcount.properties);
  assert.deepEqual(hc, {formula: '-> /weft/stdlib/count', over: '-> 0x11/user/org/members', into: '/headcount'});
  const pr = adapt.slotsOf(payroll.properties);
  assert.equal(pr.over, '-> 0x11/user/org/members @ 4');
  assert.equal(pr.budget, '-> 0x11/user/org/budgets/2026');
  assert.equal(adapt.valueOf('/h/y/0/5/x/0x11/user/org/views/closed'), '-> /x/0x11/user/org/views/closed', 'a reference into /x keeps the /x the renderer strips');
  assert.equal(adapt.valueOf('/h/x/e12/4/0x11/user/org/members'), '-> 0x11/user/org/members @ 12');
  assert.equal(adapt.valueOf({type: 'reference', value: '/h/x/0/2/0x11/weft'}), '-> 0x11/weft');
});
test('answerOf reads the fault or note from the context and the tree from /x', () => {
  const p = N + '/views/headcount';
  const a = adapt.answerOf('0x11/user/org/views/headcount', xOf(p, {'/headcount': '2'}), cOf(p, {'/sys/tack/case': '5'}));
  assert.equal(a.tree.path, '0x11/user/org/views/headcount'); assert.deepEqual(a.tree.slots, {headcount: 2});
  assert.deepEqual(adapt.answerOf('c', xOf('/c', {}), cOf('/c', {'/sys/view/fault': 'cycle through /c'})), {bad: 'cycle through /c'});
  assert.deepEqual(adapt.answerOf('h', xOf('/h', {}), cOf('/h', {'/sys/view/missing': 'Supply /slot'})), {note: 'Supply /slot'});
  assert.deepEqual(adapt.answerOf('u', {...xOf('/u', {}), exists: false}, cOf('/u', {})), {bad: 'unknown'});
  assert.deepEqual(adapt.answerOf('e', {path: '/x/e', error: 'too large, page it'}, cOf('/e', {})), {bad: 'too large, page it'});
});
test('eventOf labels a history item by its first touched path when the line carries none', () => {
  assert.deepEqual(adapt.eventOf({epoch: 9, who: 'mcp', touched: [N + '/deals/d1', N + '/deals/d2'], touched_count: 2}), {epoch: 9, label: 'd1 (+1)', who: 'mcp', touched: ['0x11/user/org/deals/d1', '0x11/user/org/deals/d2'], count: 2, with: null});
  assert.equal(adapt.eventOf({epoch: 10, label: 'make cell vendors', who: 'tester', touched: [N + '/views/vendors']}).label, 'make cell vendors');
});

// ---- the adapter over a fake /mcp: the four calls
function fakeMcp(answer) {
  const calls = [];
  const fetch = async (url, options) => {
    const body = JSON.parse(options.body); calls.push({url, name: body.params.name, args: body.params.arguments});
    const out = answer(body.params.name, body.params.arguments);
    return {json: async () => ({jsonrpc: '2.0', id: body.id, result: out.error ? {content: [{type: 'text', text: out.error}], structuredContent: out, isError: true} : {content: [], structuredContent: out, isError: false}})};
  };
  return {fetch, calls};
}
test('read and answer go through tools/call mcp/read with the plan\'s arguments', async () => {
  const hc = N + '/views/headcount';
  const m = fakeMcp((name, a) => {
    if (a.paths) return {answers: a.paths.map(p => p.startsWith('/c/x') ? cOf(hc, {'/sys/tack/case': '5'}) : xOf(hc, {'/headcount': '2'}, [{path: '/x' + N + '/members/alice', exists: true, reference: ref('x', 2, N + '/members/alice'), properties: {'/salary': '165'}, children: []}]))};
    return a.path === N + '/members' ? members : folder;
  });
  const s = mcpSource({fetch: m.fetch, EventSource: null});
  const r = await s.read('0x11/user/org/members', 'z', 0);
  assert.deepEqual(m.calls[0], {url: '/mcp', name: 'mcp/read', args: {path: N + '/members', care: 'z', case: 0, limit: 200}});
  assert.equal(r.kids[0].slots.salary, 165);
  const a = await s.answer('0x11/user/org/views/headcount');
  assert.deepEqual(m.calls[1].args, {paths: ['/x' + hc, '/c/x' + hc], care: 'z', limit: 200});
  assert.deepEqual(a.tree.slots, {headcount: 2}); assert.equal(a.tree.kids[0].slots.salary, 165);
});
test('graph reads the views folder once and answers every cell in one paths read', async () => {
  const views = {path: N + '/views', exists: true, reference: ref('x', 1, N + '/views'), reference_y: null, reference_z: null, properties: {}, children: [headcount, payroll, {path: N + '/views/readme', exists: true, reference: ref('x', 1, N + '/views/readme'), properties: {'/text': 'not a cell'}, children: []}], nodes: 4, next: null};
  const m = fakeMcp((name, a) => a.paths ? {answers: a.paths.map(p => p.startsWith('/c/x') ? cOf(p.slice(4), p.includes('payroll') ? {'/sys/view/missing': 'Supply /slot'} : {}) : xOf(p.slice(2), p.includes('payroll') ? {} : {'/headcount': '2'}))} : views);
  const g = await mcpSource({fetch: m.fetch, views: '/0x11/user/org/views', EventSource: null}).graph();
  assert.equal(m.calls.length, 2);
  assert.deepEqual(m.calls[0].args, {path: N + '/views', care: 'y', limit: 500});
  assert.deepEqual(g.sources.map(s => s.path), ['0x11/user/org/members', '0x11/user/org/budgets/2026']);
  assert.equal(g.cells.length, 2);
  const [hc, pr] = g.cells;
  assert.deepEqual(hc, {path: '0x11/user/org/views/headcount', formula: 'count', settings: 'into /headcount', inputs: [{path: '0x11/user/org/members', pin: null}], answer: '2 headcount', note: undefined, bad: undefined});
  assert.deepEqual(pr.inputs, [{path: '0x11/user/org/members', pin: 4}, {path: '0x11/user/org/budgets/2026', pin: null, view: true}]);
  assert.equal(pr.note, 'Supply /slot'); assert.equal(pr.settings, 'slot /salary into /total');
  assert.deepEqual(await mcpSource({fetch: m.fetch, EventSource: null}).graph(), {sources: [], cells: []}, 'no views folder, no outline');
});
test('follow without a stream delivers the backlog, then polls history after with x; system events are hidden and a read answers from with', async () => {
  const ticks = [], timers = {setInterval: (f, ms) => { ticks.push({f, ms}); return 1; }, clearInterval: () => {}, setTimeout: () => {}};
  const log = [];
  let after = null;
  const alice = {path: N + '/members/alice', exists: true, reference: ref('x', 'e12', N + '/members/alice'), properties: {'/role': 'lead', '/salary': '165'}};
  const m = fakeMcp((name, a) => {
    if (name === 'mcp/read') return members;
    if (a.before !== undefined) return {events: [{epoch: 9, who: 'mcp', touched: [N + '/deals/d1'], touched_count: 1, with: null}, {epoch: 7, who: 'system', touched: ['/0x11/weft/x'], touched_count: 1, with: null}, {epoch: 5, who: 'mcp', touched: [N + '/members/alice', N + '/members/bob'], touched_count: 2, with: null}], next: null};
    after = a;
    return {events: [{epoch: 12, who: 'tester', touched: [N + '/members/alice'], touched_count: 1, with: {[N + '/members/alice']: alice}}, {shown: {path: N + '/views', care: 'z', case: 0}, epoch: 12}], next: null};
  });
  const s = mcpSource({fetch: m.fetch, EventSource: null, ...timers});
  s.follow(async ev => { log.push(ev); });
  await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r));
  assert.deepEqual(log.map(e => [e.epoch, e.label, e.quiet]), [[5, 'alice (+1)', true], [9, 'd1', false]], 'the backlog oldest first, only the last drawn, system hidden');
  assert.equal(ticks.length, 1); assert.equal(ticks[0].ms, 700);
  await ticks[0].f(); await new Promise(r => setImmediate(r));
  assert.deepEqual(after, {after: 9, limit: 40, with: 'x'});
  assert.deepEqual(log.slice(2).map(e => e.shown ? ['shown', e.shown.path] : [e.epoch, e.who, e.touched]), [[12, 'tester', ['0x11/user/org/members/alice']], ['shown', '0x11/user/org/views']]);
  const before = m.calls.length;
  const r = await s.read('0x11/user/org/members/alice', 'x', 0);
  assert.equal(m.calls.length, before, 'the touched record at x comes from the event\'s with, not a read');
  assert.deepEqual(r.record, {role: 'lead', salary: 165}); assert.equal(r.case, 'e12');
  await s.read('0x11/user/org/members/alice', 'z', 0);
  assert.equal(m.calls.length, before + 1, 'any other read goes to the mount');
  await ticks[0].f(); await new Promise(r => setImmediate(r));
  assert.equal(log.filter(e => e.epoch === 12).length, 1, 'an epoch already seen is not delivered twice');
});
test('who= filters the poll and the stream; who=all shows system events', async () => {
  const seenArgs = [];
  const m = fakeMcp((name, a) => { seenArgs.push(a); return {events: [], next: null}; });
  const timers = {setInterval: () => 1, clearInterval: () => {}, setTimeout: () => {}};
  mcpSource({fetch: m.fetch, EventSource: null, who: 'tester', ...timers}).follow(() => {});
  await new Promise(r => setImmediate(r));
  assert.deepEqual(seenArgs[0], {before: 0, limit: 40, who: 'tester'});
  // the stream: a fake EventSource handing lines straight to the page
  let es; const log = [];
  class ES { constructor(url) { this.url = url; es = this; } close() {} }
  mcpSource({fetch: fakeMcp(() => ({events: [], next: null})).fetch, EventSource: ES, who: 'all', ...timers}).follow(ev => { log.push(ev); });
  await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r));
  assert.equal(es.url, '/mcp/stream');
  es.onopen();
  es.onmessage({data: JSON.stringify({epoch: 3, label: 'boot', who: 'system', touched: ['/0x11/weft/x'], with: {}})});
  es.onmessage({data: JSON.stringify({epoch: 4, label: 'make cell vendors', who: 'agent', touched: [N + '/views/vendors'], with: {}})});
  es.onmessage({data: JSON.stringify({shown: {path: N + '/views', care: 'z', case: 0}})});
  es.onmessage({data: 'not json'});
  await new Promise(r => setImmediate(r));
  assert.deepEqual(log.map(e => e.shown ? 'shown ' + e.shown.path : `${e.epoch} ${e.who} ${e.label}`), ['3 system boot', '4 agent make cell vendors', 'shown 0x11/user/org/views']);
});
