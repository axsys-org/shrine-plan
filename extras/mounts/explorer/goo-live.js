// Shrine live page: the viewer (live/viewer.js, verbatim but for the module wrapper) and the /mcp source adapter.
// mountViewer(element, source) draws the record the last write touched, resolved, with its flow above.
// source: { read(path, care, case), answer(path), graph(), follow(handler) }  (see live/GUIDE.md section 1)
// Everything in the renderer is a pure function from data to HTML, reconciled by data-path and data-case.
// mcpSource({views, who}) is that source over the mount's JSON-RPC at /mcp and its stream at /mcp/stream.
(function (root) {
'use strict';

function mountViewer(el, source, opts = {}) {
  el.classList.add('sv');
  el.innerHTML = `<div class="sv-bar"><div class="sv-crumb"><span data-path="">namespace</span></div><div class="sv-qa"></div><div class="sv-when"></div></div><div class="sv-cells"></div><div class="sv-main"><div class="sv-now"></div><div class="sv-earlier"></div></div>`;
  const $ = sel => el.querySelector(sel);
  const state = { events: [], shown: null, drawn: false };
  const views = local(opts.views !== undefined ? opts.views : opts.crumb);   // the page's folder: an agent's QA writes show only on the QA folder's page

  async function index() {
    const g = await source.graph();
    const asked = new Map();
    for (const c of g.cells) for (const i of c.inputs) { const k = i.path.replace(/^\/x\//, ''); (asked.get(k) || asked.set(k, []).get(k)).push({ ...c, pin: i.pin, view: !!i.view }); }
    source._asked = asked; source._cells = new Map(g.cells.map(c => [c.path, c]));
  }
  async function fillAction(det, ev, openRecords) {
    const body = det.querySelector('.body'); if (body.dataset.filled) return; body.dataset.filled = '1';
    const paths = ev.shown ? [ev.shown.path] : (ev.records || ev.touched);
    openRecords = openRecords && paths.length <= 8;   // a big batch opens record by record, on a click
    const items = await Promise.all(paths.map(async p => {
      const r = await source.read(p, ev.shown ? (ev.shown.care || 'y') : 'x', ev.shown ? ev.shown.case : 0);
      let line;
      if (r && r.record === null) return '';                                                   // deleted: not listed
      else if (r && isCell(r.record)) { const a = await source.answer(p); if (a.bad === 'unknown') return ''; line = `<span class="m ${a.bad ? 'bad' : a.note ? 'note' : ''}">${esc(a.bad || a.note || (a.tree ? summary(a.tree) : ''))}</span>`; }
      else line = `<span class="m">${r ? lineHTML(r.record) : ''}</span>`;
      return `<details class="sv-recd" data-path="${esc(p)}" ${openRecords ? 'open' : ''}><summary><span class="n">${esc(last(p))}</span>${goHTML(p, folderOf(p), p, 'p')}${line}</summary><div class="body"></div></details>`;
    }));
    body.innerHTML = items.join('');
    for (const d of body.querySelectorAll('details.sv-recd')) { if (d.open) await fillRecord(d, ev, 'y'); d.addEventListener('toggle', () => d.open && fillRecord(d, ev, 'z')); }
  }
  // a record opened by the page shows itself and its children (y); one the person opens shows its whole subtree (z)
  async function fillRecord(det, ev, care) {
    const body = det.querySelector('.body'); if (body.dataset.filled) return; body.dataset.filled = '1';
    const r = await source.read(det.dataset.path, ev.shown && ev.shown.care === 'z' ? 'z' : care, ev.shown ? ev.shown.case : 0);
    body.innerHTML = r ? await recordHTML(source, r, false, new Set()) : '';
    if (r && source.referencedBy) { try { body.innerHTML += referencedHTML(await source.referencedBy(det.dataset.path)); } catch (e) { /* a mount without the knob */ } }
  }

  // the QA chip: the score of an agent's QA tree, when one exists; a click flips the page to that folder
  async function chip() {
    if (!source.qa) return;
    const q = await source.qa();
    $('.sv-qa').innerHTML = q ? qaChipHTML(q) : '';
    const a = $('.sv-qa a'); if (a) a.addEventListener('click', e => { e.preventDefault(); if (opts.flip) opts.flip(q.folder); else root.location.search = '?views=/' + q.folder; });
  }
  async function draw(ev) {
    state.drawn = true;
    await index();
    $('.sv-cells').innerHTML = cellsHTML([...source._cells.values()]);
    chip();
    const nowEl = $('.sv-now'), earlier = $('.sv-earlier');
    nowEl.innerHTML = actionHTML(source, ev, true);
    const det = nowEl.querySelector('details.sv-act'); await fillAction(det, ev, true);
    earlier.innerHTML = state.events.filter(e => e !== ev).slice().reverse().map(e => actionHTML(source, e, false)).join('');
    for (const d of earlier.querySelectorAll('details.sv-act')) d.addEventListener('toggle', () => { if (!d.open) return; const e = state.events.find(x => String(x.epoch) === d.dataset.epoch); fillAction(d, e, false); });
    $('.sv-when').innerHTML = ev.shown ? `<span class="shown">shown as is</span>` : `now <b>${ev.epoch}</b>`;
  }

  const inside = p => !views || p === views || p.startsWith(views + '/');
  source.follow(async msg => {
    if (msg.shown) {
      // presented off this page's folder: the page moves there, so the person sees what the agent showed
      if (!inside(msg.shown.path)) { const folder = folderOf(msg.shown.path); if (opts.flip) return opts.flip(folder); if (root.location) { root.location.search = '?views=/' + folder; return; } }
      const ev = { epoch: 'shown', label: 'show ' + msg.shown.path, who: 'agent', touched: [], shown: msg.shown }; return draw(ev);
    }
    if (!msg.touched || !msg.touched.length) return;
    // the agent's QA stays behind the chip; housekeeping, deletions and unknowns are never shown: when such a line closes
    // the backlog, the last real event is drawn instead
    if (qaHidden(msg, views) || quietLine(msg)) { if (!msg.quiet && !state.drawn && state.events.length) return draw(state.events[state.events.length - 1]); return; }
    state.events.push(msg); if (msg.quiet) return;   // quiet: the backlog on load, kept for `earlier` and drawn with the last
    return draw(msg);
  });
  if (opts.crumb !== undefined) $('.sv-crumb').innerHTML = crumbHTML(opts.crumb);
  // a click on a path or a reference: the person's cursor is written (the agent sees it on the stream), then the page
  // moves to that folder; the link itself works without script
  async function go(path, folder) {
    if (source.cursor) await source.cursor(path).catch(() => {});
    if (opts.flip) opts.flip(folder); else root.location.search = '?views=/' + folder;
  }
  el.addEventListener('click', e => {
    const a = e.target && e.target.closest ? e.target.closest('a[data-go]') : null; if (!a) return;
    e.preventDefault(); go(a.dataset.go, a.dataset.folder);
  });
  return { draw, go };
}

// what a write moved: the cells that read any touched path, one hop
const moved = (source, touched) => { const out = new Set(); for (const t of touched) for (const q of (source._asked.get(t) || [])) out.add(last(q.path) + (q.answer ? ' ' + q.answer : '')); for (const t of touched) { const seg = t.split('/'); for (let i = seg.length - 1; i > 0; i--) for (const q of (source._asked.get(seg.slice(0, i).join('/')) || [])) out.add(last(q.path) + (q.answer ? ' ' + q.answer : '')); } return [...out]; };

// an agent's QA writes stay behind the chip: an event whose every written record sits under /<node>/agent/<name>/qa is
// drawn only when the page's views folder is that QA folder or inside it; its score still reaches the chip through qa()
const qaFolderOf = p => { const m = /^([^/]+\/agent\/[^/]+\/qa)(\/|$)/.exec(p); return m ? m[1] : null; };
// housekeeping: a seen mark, the hands' folder, the person's cursor, the clock, the journal
const HOUSEKEEPING = /\/agent\/[^/]+\/seen$|\/agent\/hands(\/|$)|\/agent\/person(\/|$)|\/agent\/launcher(\/|$)|\/clock$|\/agent\/journal(\/|$)/;
const HANDS = /^(clock|source)(_|$)/;
// a line the page never shows: a hand's, one that only moved housekeeping records, one that only deleted things,
// or one whose written cells all read unknown; what remains is the person's and the agents' work on the data
const quietLine = ev => {
  if (ev.shown) return false;
  if (HANDS.test(ev.who || '')) return true;
  const all = ev.touched || [], t = all.filter(p => !/\/agent\/journal(\/|$)/.test(p) && !all.some(q => q !== p && q.startsWith(p + '/')));   // the deepest paths, the journal aside
  if (t.length > 0 && t.every(p => HOUSEKEEPING.test(p))) return true;
  const w = ev.with && typeof ev.with === 'object' ? Object.entries(ev.with).filter(([k]) => !/^\/x\/|^\/c\/x\//.test(k)) : [];
  const nothing = ([k, v]) => !v || v.exists === false || (v.properties && '/sys/weft' in v.properties && ev.with['/x' + k] && ev.with['/x' + k].exists === false);
  return w.length > 0 && w.every(nothing);
};
const cursorLine = quietLine;   // the old name
const qaHidden = (ev, views) => {
  const recs = ev.records || ev.touched || []; if (ev.shown || !recs.length) return false;
  const folders = recs.map(qaFolderOf); if (folders.includes(null)) return false;
  const at = local(views); return !folders.some(f => at === f || at.startsWith(f + '/'));
};
// one action: a line; opens into its records, each a line that opens into the card
function actionHTML(source, ev, open) {
  const n = (ev.records || ev.touched).length, more = ev.count && ev.count > n + 3 ? '+' : '', mv = moved(source, ev.touched);
  const sum = `<summary><span class="ep">${ev.shown ? 'shown' : ev.epoch}</span><span class="lab">${esc(ev.label)}</span><span class="who">${esc(ev.who)}</span><span class="cnt">${ev.shown ? esc(ev.shown.path) : n + more + (n === 1 ? ' record' : ' records')}</span>${mv.length ? `<span class="mv">${esc(mv.slice(0, 3).join(' · '))}${mv.length > 3 ? ' …' : ''}</span>` : ''}</summary>`;
  return `<details class="sv-act" data-epoch="${ev.epoch}" ${open ? 'open' : ''}>${sum}<div class="body"></div></details>`;
}

// what references a record: cells and rows as links, a cell waiting there marked; nothing when nothing does
function referencedHTML(rb) {
  const ms = rb.matches || [], ws = rb.watchers || [];
  if (!ms.length && !ws.length) return '';
  const row = m => `<div class="sv-refby ${m.cell ? 'cell' : 'rec'} ${m.hole ? 'hole' : ''}">${goHTML(m.path, folderOf(m.path), last(m.path), 'ref')}<span class="s">${esc(m.slot)}</span>${m.hole ? '<span class="h">waiting</span>' : ''}</div>`;
  return `<div class="sv-refd"><div class="k">referenced by</div>${ms.map(row).join('')}${ws.map(w => `<div class="sv-refby crew">${goHTML(w.path, folderOf(w.path), last(w.path), 'ref')}<span class="s">crew, ${esc(w.care)}</span></div>`).join('')}</div>`;
}

// the QA chip: green and quiet at zero, the count otherwise; the href is the QA folder on this same page
function qaChipHTML(q) {
  const n = Number(q.changed) || 0;
  return `<a class="sv-chip ${n ? 'off' : 'ok'}" href="?views=/${esc(q.folder)}" title="QA: ${n ? n + ' check' + (n === 1 ? '' : 's') + ' disagree' : 'every check agrees'}">QA ${n}</a>`;
}
// the standing outline: every cell of the views folder with what it says now (the scoreboard, the bug list, the plan)
function cellsHTML(cells) {
  if (!cells.length) return '';
  return `<div class="sv-outline">${cells.map(c => `<div class="sv-cell ${c.bad ? 'bad' : c.note ? 'note' : ''}" data-path="${esc(c.path)}"><span class="n">${esc(c.rel || last(c.path))}</span><span class="f">${esc(c.formula)}</span><span class="a">${esc(c.bad || c.note || c.answer || '')}</span></div>`).join('')}</div>`;
}
// ---------- rendering ----------
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const last = p => p ? p.split('/').pop() : 'namespace';
// a record's folder is the one above it; a reference names the thing a cell reads, usually a folder, so it is its own
const folderOf = p => { const i = String(p).lastIndexOf('/'); return i > 0 ? p.slice(0, i) : p; };
// a path the person can click: the page moves to `folder`, and the click writes the cursor at `path`
const goHTML = (path, folder, text, cls) => `<a class="${cls} go" href="?views=/${esc(folder)}" data-go="${esc(path)}" data-folder="${esc(folder)}">${esc(text)}</a>`;
const isCell = rec => !!rec && typeof rec.formula === 'string' && rec.formula.startsWith('-> /weft/stdlib/');
const refOf = s => { const m = /^-> (\S+)(?: @ (\d+))?$/.exec(s || ''); return m ? { path: m[1], pin: m[2] ? Number(m[2]) : null } : null; };

// a number as text: a year (four digits) or a day (eight digits, YYYYMMDD) is drawn as written, a quantity grouped
const numText = v => (Number.isInteger(v) && (String(v).length === 4 || String(v).length === 8)) ? String(v) : v.toLocaleString();
// one value, by kind; the only place a value's kind is decided
function valueHTML(v, cls = 'sv-v') {
  if (typeof v === 'number') return `<span class="${cls}">${numText(v)}</span>`;
  const s = String(v);
  const r = refOf(s); if (r) { const p = r.path.replace(/^\/x\//, ''); return `<span class="${cls} ref" data-path="${esc(p)}">${goHTML(p, p, s, 'r')}</span>`; }
  if (/^blob:/.test(s)) { const [, hash, mime, size] = s.split(':'); return `<span class="${cls} blob">${mime && mime.startsWith('image') ? `<img alt="" src="/blob/${esc(hash)}">` : ''}${esc(hash.slice(0, 8))} &middot; ${esc(size || '')}</span>`; }
  if (s === 'yes' || s === 'no') return `<span class="${cls} flag ${s}">${s}</span>`;
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return `<span class="${cls}">${esc(s)}</span>`;
  return `<span class="${cls} text">${esc(s)}</span>`;
}
const isShort = v => typeof v === 'number' || String(v).length < 24;

// the record body: layout chosen from the slots handed in (GUIDE.md section 2)
function slotLayout(slots) {
  const s = Object.entries(slots || {});
  if (!s.length) return '';
  if (s.length === 1 && typeof s[0][1] === 'number') return `<div class="sv-one">${numText(s[0][1])}<span class="u">${esc(s[0][0])}</span></div>`;
  const long = s.some(([, v]) => typeof v !== 'number' && String(v).length > 80);
  if (s.length > 6 || long) return `<div class="sv-list">${s.map(([k, v]) => `<span class="sv-k">${esc(k)}</span>${valueHTML(v)}`).join('')}</div>`;
  return `<div class="sv-grid">${s.map(([k, v]) => `<div class="s ${isShort(v) ? '' : 'wide'}"><span class="sv-k">${esc(k)}</span>${valueHTML(v)}</div>`).join('')}</div>`;
}

async function rowSlots(source, node) {
  let slots = node.slots;
  if (isCell(slots)) { const r = await source.answer(node.path); slots = r.tree ? (Object.keys(r.tree.slots).length ? r.tree.slots : { '': r.tree.kids.length + ' rows' }) : { '': r.note || r.bad }; }
  return Object.entries(slots).filter(([k]) => k !== 'scale' && !k.endsWith('/scale')).map(([k, v]) => `<span>${k ? `<span class="k">${esc(k)}</span>` : ''}${valueHTML(v, 'v')}</span>`).join('');   // a scale rides with its number, it is not a fact of the row
}

async function kidHTML(source, node, depth, bump) {
  const s = Object.keys(node.slots || {}).length;
  const row = `<div class="sv-row ${bump.has(node.path) ? 'bump' : ''}" data-path="${esc(node.path)}" data-case="${node.case || ''}"><span class="n ${s ? '' : 'folder'}">${esc(node.name)}</span><span class="sl">${await rowSlots(source, node)}</span></div>`;
  const kids = node.kids || [];
  const inner = !kids.length ? '' : depth >= 3 ? `<div class="sv-row"><span class="more">${kids.length} beneath</span></div>` : (await Promise.all(kids.map(k => kidHTML(source, k, depth + 1, bump)))).join('');
  return `<div class="sv-kid">${row}${askedHTML(source, node.path, 1)}${inner}</div>`;
}

async function recordHTML(source, r, showPath, bump) {
  const node = { name: last(r.path), path: r.path, slots: r.record || {}, kids: r.kids || [] };
  let body;
  if (r.record === null) body = `<div class="sv-gone">deleted</div>`;
  else if (isCell(node.slots)) {
    // a cell's card: the result first, at its care (a figure, or the rows), then the formula and its settings folded,
    // then the chain the result came up, then what was asked of it; what references it follows the card
    const a = await source.answer(node.path);
    const { formula, over, ...settings } = node.slots;
    const made = `<details class="sv-made"><summary>${esc(formula.slice(16))}${over ? ' over ' + esc(String(over).replace(/^-> /, '')) : ''}</summary>${slotLayout(settings)}</details>${chainHTML(source, node.path)}`;
    if (a.bad) body = `<div class="sv-note bad">${esc(a.bad)}</div>${made}`;
    else if (a.note) body = `<div class="sv-note">${esc(a.note)}</div>${made}`;
    else body = `${slotLayout(a.tree.slots)}${a.tree.kids.length ? `<div class="sv-kids">${(await Promise.all(a.tree.kids.map(k => kidHTML(source, k, 1, bump)))).join('')}</div>` : ''}${made}`;
  } else body = `${slotLayout(node.slots)}${node.kids.length ? `<div class="sv-kids">${(await Promise.all(node.kids.map(k => kidHTML(source, k, 1, bump)))).join('')}</div>` : ''}`;
  return `<div class="sv-rec ${bump.has(node.path) ? 'bump' : ''}" data-path="${esc(node.path)}" data-case="${r.case || ''}"><div class="sv-head"><span class="n">${esc(node.name)}</span>${showPath ? `<span class="p">${esc(node.path)}</span>` : ''}</div>${body}${askedHTML(source, node.path, 1)}</div>`;
}




// ---------- the composition as an outline: what was asked of a thing hangs beneath it ----------
function askedHTML(source, path, depth, seen = new Set()) {
  const qs = (source._asked && source._asked.get(path)) || [];
  if (!qs.length || depth > 4 || seen.has(path)) return '';
  seen = new Set(seen); seen.add(path);
  return `<div class="sv-asked">${qs.map(q => {
    const other = q.inputs.filter(i => i.path.replace(/^\/x\//, '') !== path).map(i => `<span class="o">+ ${esc(last(i.path.replace(/^\/x\//, '')))}</span>`).join('');
    const meta = q.bad ? `<span class="m bad">${esc(q.bad)}</span>` : q.note ? `<span class="m note">${esc(q.note)}</span>` : `<span class="m">${esc(q.answer || '')}</span>`;
    return `<div class="sv-q"><div class="l" data-path="${esc(q.path)}"><span class="f">${esc(q.view ? 'view' : q.formula)}${q.pin ? ` · held at ${q.pin}` : ''}</span><span class="n">${esc(last(q.path))}</span>${other}${meta}</div>${askedHTML(source, q.path, depth + 1, seen)}</div>`;
  }).join('')}</div>`;
}
function fromHTML(source, path) {
  const c = source._cells && source._cells.get(path); if (!c) return '';
  return `<div class="sv-from"><span class="f">${esc(c.formula)}</span>${c.inputs.map(i => { const p = i.path.replace(/^\/x\//, ''); return `<span class="sv-pill ${source._cells.has(p) ? 'cell' : ''}" data-path="${esc(p)}">${esc(source._cells.has(p) ? last(p) : p)}${i.pin ? `<span class="pin">held at ${i.pin}</span>` : ''}${i.view ? '<span class="pin">view</span>' : ''}</span>`; }).join('')}</div>`;
}
// the chain a cell's answer came up: one line per stage, walked upward by the tack (the first input) while it is a
// cell of the folder, the formula and its settings, the input as a link, a pin or a secondary input noted
function chainHTML(source, path) {
  const cells = source._cells; if (!cells || !cells.has(path)) return '';
  const lines = [], seen = new Set(); let p = path;
  while (cells.has(p) && !seen.has(p) && lines.length < 8) {
    seen.add(p); const c = cells.get(p);
    const tack = c.inputs.find(i => !i.view) || c.inputs[0], others = c.inputs.filter(i => i !== tack);
    const ip = tack ? tack.path.replace(/^\/x\//, '') : '';
    const link = !ip ? '' : cells.has(ip) ? goHTML(ip, folderOf(ip), last(ip), 'r cell') : goHTML(ip, ip, ip, 'r');
    lines.push(`<div class="sv-stage"><span class="f">${esc(c.formula)}</span>${c.settings ? `<span class="s">${esc(c.settings)}</span>` : ''}<span class="over">over</span>${link}${tack && tack.pin ? `<span class="pin">held at ${tack.pin}</span>` : ''}${others.map(o => { const op = o.path.replace(/^\/x\//, ''); return `<span class="o">+ ${goHTML(op, cells.has(op) ? folderOf(op) : op, cells.has(op) ? last(op) : op, 'r')}${o.pin ? ` held at ${o.pin}` : ''}</span>`; }).join('')}</div>`);
    p = ip;
  }
  return `<div class="sv-chain">${lines.join('')}</div>`;
}

// ---------- the world, drawn: what was written on the left growing down, what was asked to the right growing out ----------
// g = { sources: [{path, meta}], cells: [{path, formula, settings, answer, note, bad, inputs: [{path, pin, view}]}] }
const W = { col: 224, row: 38, pillW: 168, pillH: 24, padX: 18, padY: 10 };
function worldGraphHTML(g, focus, bump) {
  const byPath = new Map();
  for (const s of g.sources) byPath.set(s.path, { ...s, kind: 'data', depth: 0, ins: [] });
  for (const c of g.cells) byPath.set(c.path, { ...c, kind: 'cell', depth: null, ins: c.inputs.map(i => ({ ...i, path: i.path.replace(/^\/x\//, '') })) });
  // depth: longest path from a source; unknown inputs count as depth 0 sources
  for (const n of byPath.values()) for (const i of n.ins) if (!byPath.has(i.path)) byPath.set(i.path, { path: i.path, meta: '', kind: 'data', depth: 0, ins: [] });
  let changed = true, guard = 0;
  while (changed && guard++ < 50) { changed = false; for (const n of byPath.values()) { if (n.kind !== 'cell') continue; const ds = n.ins.map(i => byPath.get(i.path).depth); if (ds.some(d => d === null)) continue; const d = Math.max(0, ...ds) + 1; if (n.depth !== d) { n.depth = d; changed = true; } } }
  for (const n of byPath.values()) if (n.depth === null) n.depth = 1;   // a cycle: park it in column one
  // rows: sources in path order; a cell wants the mean of its inputs' rows, then is pushed down past the last in its column
  const cols = new Map();
  for (const n of byPath.values()) (cols.set(n.depth, cols.get(n.depth) || []), cols.get(n.depth).push(n));
  const D = Math.max(...cols.keys());
  cols.get(0).sort((a, b) => a.path.localeCompare(b.path)).forEach((n, i) => n.y = i);
  for (let d = 1; d <= D; d++) {
    const col = (cols.get(d) || []).map(n => ({ n, want: n.ins.length ? n.ins.reduce((a, i) => a + (byPath.get(i.path).y || 0), 0) / n.ins.length : 0 })).sort((a, b) => a.want - b.want || a.n.path.localeCompare(b.n.path));
    let lastY = -1; for (const { n, want } of col) { n.y = Math.max(want, lastY + 1); lastY = n.y; }
  }
  const nodes = [...byPath.values()], maxY = Math.max(0, ...nodes.map(n => n.y));
  const X = n => W.padX + n.depth * W.col, Y = n => W.padY + n.y * W.row;
  const width = W.padX * 2 + D * W.col + W.pillW, height = W.padY * 2 + maxY * W.row + W.pillH;
  const edges = [];
  for (const n of nodes) if (n.kind === 'cell') n.ins.forEach((i, k) => edges.push({ from: byPath.get(i.path), to: n, label: i.view ? 'view' : n.formula, sub: i.view ? '' : (n.settings || ''), pin: i.pin }));
  const paths = edges.map(e => {
    const x1 = X(e.from) + W.pillW, y1 = Y(e.from) + W.pillH / 2, x2 = X(e.to), y2 = Y(e.to) + W.pillH / 2, mx = (x1 + x2) / 2;
    const lit = bump.has(e.to.path) || bump.has(e.from.path);
    // the label sits three quarters along the curve, so labels of edges into different targets separate
    const t = 0.74, u = 1 - t, lx = u * u * u * x1 + 3 * u * u * t * mx + 3 * u * t * t * mx + t * t * t * x2, ly = u * u * u * y1 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y2;
    return `<path class="${lit ? 'lit' : ''}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/><text x="${lx}" y="${ly - 4}" text-anchor="middle"><title>${esc(e.sub)}</title>${esc(e.label)}${e.pin ? ` · held at ${e.pin}` : ''}</text>`;
  }).join('');
  const pills = nodes.map(n => {
    const here = n.path === focus, cls = (n.kind === 'cell' ? 'cell' : 'data') + (here ? ' here' : '') + (bump.has(n.path) ? ' bump' : '') + (n.bad ? ' bad' : n.note ? ' note' : '');
    const label = n.kind === 'cell' ? last(n.path) : n.path, meta = n.kind === 'cell' ? (n.bad || n.note || n.answer) : n.meta;
    return `<span class="sv-pill ${cls}" data-path="${esc(n.path)}" style="left:${X(n)}px;top:${Y(n)}px;width:${W.pillW}px"><span class="l">${esc(label)}</span><span class="m">${esc(meta || '')}</span></span>`;
  }).join('');
  return `<div class="sv-tree" style="width:${width}px;height:${height}px"><svg width="${width}" height="${height}" aria-hidden="true">${paths}</svg>${pills}</div>`;
}

// ---------- the context tree: upstream to the left, the focus, what reads it to the right ----------
const G = { col: 236, row: 40, pillW: 172, pillH: 24, padX: 18, padY: 10 };
function graphHTML(root, deps) {
  // upstream layout: leaves get rows first, a node sits at the mean of its inputs; depth = longest path from a leaf
  const nodes = [], edges = []; let rows = 0;
  const place = node => {
    const ins = node.kind === 'cell' ? node.inputs : [];
    const placed = ins.map(place);
    const y = placed.length ? placed.reduce((a, c) => a + c.y, 0) / placed.length : rows++;
    const depth = placed.length ? Math.max(...placed.map(c => c.depth)) + 1 : 0;
    const me = { ...node, y, depth, id: nodes.length }; nodes.push(me);
    for (const c of placed) edges.push({ from: c, to: me, label: node.formula, sub: node.settings || '' });
    return me;
  };
  const focus = place(root); focus.here = true;
  const D = focus.depth;
  // downstream: cells that read the focus, one column to the right, centred on the focus
  const start = focus.y - (deps.length - 1) / 2;
  deps.forEach((d, i) => { const me = { kind: 'cell', path: d.path, answer: d.answer, formula: d.formula, settings: d.settings, y: start + i, depth: D + 1, id: nodes.length }; nodes.push(me); edges.push({ from: focus, to: me, label: d.formula, sub: d.settings || '' }); });
  const minY = Math.min(...nodes.map(n => n.y)), maxY = Math.max(...nodes.map(n => n.y));
  const X = n => G.padX + n.depth * G.col, Y = n => G.padY + (n.y - minY) * G.row;
  const W = G.padX * 2 + (D + (deps.length ? 1 : 0)) * G.col + G.pillW, H = G.padY * 2 + (maxY - minY) * G.row + G.pillH;
  const paths = edges.map(e => {
    const x1 = X(e.from) + G.pillW, y1 = Y(e.from) + G.pillH / 2, x2 = X(e.to), y2 = Y(e.to) + G.pillH / 2, mx = (x1 + x2) / 2;
    return `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/><text x="${mx}" y="${(y1 + y2) / 2 - 3}" text-anchor="middle"><title>${esc(e.sub)}</title>${esc(e.label)}</text>`;
  }).join('');
  const pills = nodes.map(n => {
    const cls = n.kind === 'cell' ? 'cell' + (n.here ? ' here' : '') : (n.here ? 'here' : '');
    const label = n.kind === 'cell' ? last(n.path) : n.path, meta = n.kind === 'cell' ? n.answer : n.meta;
    return `<span class="sv-pill ${cls}" data-path="${esc(n.path)}" style="left:${X(n)}px;top:${Y(n)}px;width:${G.pillW}px"><span class="l">${esc(label)}</span>${n.pin ? `<span class="pin">held at ${n.pin}</span>` : ''}<span class="m">${esc(meta || '')}</span></span>`;
  }).join('');
  return `<div class="sv-tree" style="width:${W}px;height:${H}px"><svg width="${W}" height="${H}" aria-hidden="true">${paths}</svg>${pills}</div>`;
}

function stripHTML(node, here) {
  const pill = (cls, path, label, meta, pin) => `<span class="sv-pill ${cls}" data-path="${esc(path)}">${esc(label)}${pin ? `<span class="pin">held at ${pin}</span>` : ''}<span class="m">${esc(meta)}</span></span>`;
  if (node.kind === 'data') return pill('', node.path, node.path, node.meta, node.pin);
  const ins = node.inputs.length === 1 ? stripHTML(node.inputs[0], false) : `<span class="sv-join">${node.inputs.map(i => `<span class="sv-branch">${stripHTML(i, false)}</span>`).join('')}</span>`;
  return `${ins}<span class="sv-arrow"><span class="f">${esc(node.formula)}</span><span class="a"></span></span>${pill('cell' + (here ? ' here' : ''), node.path, last(node.path), node.answer, node.pin)}`;
}

function crumbHTML(p) {
  const parts = p ? p.split('/') : [];
  return `<span data-path="">namespace</span>` + parts.map((c, n) => n === parts.length - 1 ? `<span class="sep">/</span><span class="here">${esc(c)}</span>` : `<span class="sep">/</span><span data-path="${esc(parts.slice(0, n + 1).join('/'))}">${esc(c)}</span>`).join('');
}

// keep DOM for nodes whose (path, case) did not change; replace the rest
function reconcile(container, html) {
  const next = document.createElement('div'); next.innerHTML = html;
  const old = new Map();
  for (const n of container.querySelectorAll('[data-path][data-case]')) if (n.dataset.case) old.set(n.dataset.path + '@' + n.dataset.case, n);
  for (const n of next.querySelectorAll('[data-path][data-case]')) {
    const k = n.dataset.path + '@' + n.dataset.case; const prev = old.get(k);
    if (prev && !n.classList.contains('bump') && prev.outerHTML.length === n.outerHTML.length) n.replaceWith(prev);
  }
  container.replaceChildren(...next.childNodes);
}

// ---------- the source adapter: the four calls over the mount's JSON-RPC (live/PLAN.md section 3) ----------
// Paths in the viewer are world paths without their leading slash (`0x11/user/org/deals`), the demo's spelling, so
// `/x/` + path is a cell's answer; `world()` puts the slash back for the wire and `local()` takes it off.
const world = p => '/' + String(p || '').replace(/^\//, '');
const local = p => String(p || '').replace(/^\//, '');
// a reference's spelling: /h/<care>/<case>/<len>/<path>, case 0 live, e<epoch> as of an epoch
const spelling = s => { const m = /^\/h\/([xyz])\/(e?\d+)\/\d+(\/.*)$/.exec(String(s)); return m ? { care: m[1], case: m[2], path: m[3] } : null; };
const asInput = p => p.startsWith('/x/') ? '/x/' + local(p.slice(3)) : local(p);
// one value: a number as text becomes a number, a reference `-> path @ case`, a large or typed value its text
function valueOf(v) {
  if (v && typeof v === 'object') return v.size !== undefined ? `${v.type}, ${Number(v.size).toLocaleString()} bytes` : valueOf(v.value);
  const s = String(v), r = spelling(s);
  if (r) return '-> ' + asInput(r.path) + (r.case !== '0' ? ' @ ' + r.case.replace(/^e/, '') : '');
  return /^\d+$/.test(s) ? Number(s) : s;
}
// a record's properties as the viewer's slots: keys without their slash; a cell's weft as `formula`, its tack as `over`
function slotsOf(props) {
  const out = {};
  for (const [k, v] of Object.entries(props || {})) {
    const key = k.replace(/^\//, '');
    if (key === 'sys/weft') { const r = spelling(String(v)); out.formula = '-> /weft/stdlib/' + (r ? r.path.split('/').pop() : String(v)); }
    else if (key === 'sys/tack') out.over = valueOf(v);
    else out[key] = valueOf(v);
  }
  return out;
}
// a read answer's node as a tree node; a shell (`paged`) is a node with nothing of its own
function nodeOf(n) {
  const path = local(n.path), c = spelling(n.reference || '');
  return { name: last(path), path, slots: n.paged ? {} : slotsOf(n.properties), kids: (n.children || []).map(nodeOf), case: c ? c.case : '' };
}
// a read answer as the viewer's read: record null for a culled path (no record, but a case), {} for a bare folder
function readOf(a) {
  const node = nodeOf(a);
  const bare = a.exists === false && (!a.reference || (a.children || []).length > 0);   // a folder: no record of its own, children beneath
  return { path: node.path, record: a.exists === false ? (bare ? {} : null) : node.slots, kids: node.kids, case: node.case, next: a.next || null };
}
// a cell's answer from its /x and /c/x: the fault or note from the context, else the tree (unknown when /x is empty)
function answerOf(path, x, c) {
  const ctx = (c && c.properties) || {};
  if (c && c.error) return { bad: c.error };
  if (ctx['/sys/view/fault']) return { bad: ctx['/sys/view/fault'] };
  if (ctx['/sys/view/missing']) return { note: ctx['/sys/view/missing'] };
  if (!x || x.error) return { bad: (x && x.error) || 'unknown' };
  if (x.exists === false) return ctx['/sys/view/asking'] ? { note: ctx['/sys/view/asking'] } : { bad: 'unknown' };
  const tree = nodeOf(x); tree.path = local(path); tree.name = last(tree.path);
  return { tree };
}
// what an answer is, in a few words: its first figure, else its first telling slot, else its row count;
// the input's own title and scale ride on a result's root and say nothing about it
const telling = slots => Object.entries(slots || {}).filter(([k]) => !/^(scale|title|sys\/)/.test(k) && !k.endsWith('/scale'));
const summary = t => {
  const sl = t.slots || {};
  if ('added' in sl && 'removed' in sl && 'changed' in sl) { const d = ['added', 'removed', 'changed'].filter(k => Number(sl[k])).map(k => sl[k] + ' ' + k); return d.length ? d.join(' · ') : 'agree'; }
  const s = telling(sl), num = s.find(([, v]) => typeof v === 'number');
  return num ? num[1].toLocaleString() + ' ' + num[0] : s.length ? String(s[0][1]).slice(0, 24) + ' ' + s[0][0] : t.kids.length + (t.kids.length === 1 ? ' row' : ' rows');
};
// a record's line: the slots that tell what it is first (text, title, name, what, asked, word), two of them, with room
const TELLING = ['text', 'title', 'name', 'what', 'asked', 'word', 'question', 'error', 'cause', 'about'];
const lineSlots = rec => { const e = Object.entries(rec || {}); const first = TELLING.flatMap(k => e.filter(([kk]) => kk === k)); const rest = e.filter(([k]) => !TELLING.includes(k)); return first.concat(rest).slice(0, first.length ? 2 : 3); };
const lineHTML = rec => lineSlots(rec).map(([k, v]) => esc(k) + ' ' + (typeof v === 'number' ? v.toLocaleString() : esc(String(v)).slice(0, 48))).join(' · ');
// the records an event wrote, as the page lists them: the keys of its `with` (the written records; a cell's
// /x and /c/x ride along and are left out), else its touched paths without the node root, the writer's
// journal tag and the ancestors whose cases moved (a touched path that is a proper prefix of another)
const writtenOf = e => {
  const t = (e.touched || []).map(local);
  const out = t.filter(p => p.includes('/') && !/^[^/]+\/agent\/journal\//.test(p) && !t.some(q => q !== p && q.startsWith(p + '/')));
  const w = e.with && typeof e.with === 'object' ? Object.keys(e.with).filter(k => !/^\/x\/|^\/c\/x\//.test(k)).map(local) : [];
  for (const p of w) if (!out.includes(p)) out.push(p);
  return out.sort();
};
// a journaled event as the viewer's event; the label the line carries, else the first written record's tail (+N)
const labelOf = written => written.length ? last(written[0]) + (written.length > 1 ? ` (+${written.length - 1})` : '') : 'write';
const eventOf = e => { const records = writtenOf(e); return { epoch: e.epoch, label: e.label || labelOf(records), who: e.who || 'agent', touched: (e.touched || []).map(local), records, count: e.touched_count, with: e.with || null }; };

function mcpSource(opts = {}) {
  const base = opts.base || '', views = local(opts.views), who = opts.who || '';
  const doFetch = opts.fetch || ((u, o) => root.fetch(u, o)), ES = 'EventSource' in opts ? opts.EventSource : root.EventSource;
  const every = opts.setInterval || root.setInterval, clear = opts.clearInterval || root.clearInterval, later = opts.setTimeout || root.setTimeout;
  let seq = 0, latest = null;   // latest: the newest event's `with`, keyed by world path; the one payload a read may answer from
  async function rpc(name, args) {
    const res = await doFetch(base + '/mcp', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: ++seq, method: 'tools/call', params: { name: 'mcp/' + name, arguments: args } }) });
    const j = await res.json();
    if (j.error) throw new Error(j.error.message || 'rpc failed');
    if (j.result && j.result.isError) throw new Error((j.result.content && j.result.content[0] && j.result.content[0].text) || 'rpc failed');
    return j.result.structuredContent;
  }
  const carried = p => { const n = latest && latest[p]; return n && !n.poked && !n.paged ? n : null; };
  // the person's cursor: one record under the node's /agent/person, signed person, so the agent sees the click as a line
  async function cursor(path) {
    const node = local(path).split('/')[0]; if (!node) return null;
    return rpc('write', { who: 'person', records: [{ path: '/' + node + '/agent/person/cursor', slots: { path: world(path) } }] });
  }
  async function read(path, care, cas) {
    const w = world(path), held = care === 'x' && !cas ? carried(w) : null;
    return readOf(held || await rpc('read', { path: w, care: care || 'z', case: cas || 0, limit: 200 }));
  }
  async function answer(path) {
    const w = world(path), x = carried('/x' + w), c = carried('/c/x' + w);
    if (x && c) return answerOf(path, x, c);
    const a = await rpc('read', { paths: ['/x' + w, '/c/x' + w], care: 'z', limit: 200 });
    return answerOf(path, a.answers[0], a.answers[1]);
  }
  // the cells under the views folder, three levels down (a plan, a qa tree with its diff and score folders);
  // a folder with a hundred or more children is left unopened
  async function graph() {
    if (!views) return { sources: [], cells: [] };
    const folder = await rpc('read', { path: world(views), care: 'y', limit: 500 });
    const cells = [], sources = new Set(), seen = new Set();
    const take = ch => {
      if (!ch.properties || !('/sys/weft' in ch.properties) || seen.has(ch.path)) return;
      seen.add(ch.path);
      const slots = slotsOf(ch.properties), inputs = [], settings = [];
      const o = refOf(slots.over); if (o) inputs.push({ path: o.path, pin: o.pin });
      for (const [k, v] of Object.entries(slots)) { if (k === 'formula' || k === 'over') continue; const r = refOf(v); if (r) inputs.push({ path: r.path, pin: r.pin, view: true }); else settings.push(k + ' ' + v); }
      for (const i of inputs) if (!i.path.startsWith('/x/')) sources.add(i.path);
      cells.push({ path: local(ch.path), rel: local(ch.path).slice(local(views).length + 1), formula: slots.formula.slice(16), settings: settings.join(' '), inputs });
    };
    const folders = f => (f.children || []).filter(ch => ch.exists !== false && !(ch.properties && '/sys/weft' in ch.properties) && (ch.children || []).length < 100 && !(ch.properties && '/sys/tack' in ch.properties));
    let level = [folder];
    for (let depth = 0; depth < 3 && level.length; depth++) {
      for (const f of level) for (const ch of f.children || []) take(ch);
      const below = level.flatMap(folders).filter(ch => depth < 2 && (ch.children || []).length);
      if (!below.length) break;
      const pages = await rpc('read', { reads: below.map(ch => ({ path: ch.path, care: 'y', limit: 100 })) });
      level = (pages.answers || []).filter(a => a && !a.error);
    }
    if (cells.length) {
      const a = await rpc('read', { reads: cells.flatMap(c => ['/x' + world(c.path), '/c/x' + world(c.path)]), care: 'z', limit: 200 });
      cells.forEach((c, i) => { const r = answerOf(c.path, a.answers[2 * i], a.answers[2 * i + 1]); Object.assign(c, { answer: r.tree ? summary(r.tree) : '', note: r.note, bad: r.bad }); });
    }
    return { sources: [...sources].map(path => ({ path, meta: '' })), cells };
  }
  // what references a path: the records and cells under the page's folder (and under /agent) whose reference slots point
  // at it or beneath it, each with the slot and whether a cell is waiting there; plus the kernel's crews on it
  async function referencedBy(path) {
    const node = local(views).split('/')[0], roots = [world(views)].concat(node ? ['/' + node + '/agent'] : []);
    const out = { matches: [], watchers: [] };
    for (const r of roots) {
      const a = await rpc('read', { path: r, referencing: world(path), limit: 200 });
      out.matches.push(...(a.matches || []).map(m => ({ path: local(m.path), slot: m.slot, cell: !!m.cell, hole: !!m.hole })));
      if (!out.watchers.length) out.watchers = (a.watchers || []).map(w => ({ path: local(w.path), care: w.care }));
    }
    return out;
  }
  // the QA tree, if an agent keeps one under this node: the first /agent/<name>/qa/score that answers, with its folder
  async function qa() {
    const node = local(views).split('/')[0];
    if (!node) return null;
    const agents = await rpc('read', { path: '/' + node + '/agent', care: 'y', limit: 50 });
    for (const ch of agents.children || []) {
      const name = last(ch.path);
      if (name === 'journal' || name === 'hands') continue;
      const score = await rpc('read', { path: '/x/' + node + '/agent/' + name + '/qa/score', care: 'x' });
      if (score && score.exists) return { folder: node + '/agent/' + name + '/qa', changed: (score.properties || {})['/changed'] || '0' };
    }
    return null;
  }
  // follow: the stream when it answers, the history poll (700 ms, with x) when it does not; one handler, same events
  function follow(handler) {
    let last = 0, queue = Promise.resolve(), polling = null, stream = null;
    const wanted = e => who === 'all' || (who ? e.who === who : e.who !== 'system');
    const deliver = lines => { for (const l of lines) queue = queue.then(() => handler(l)).catch(() => {}); return queue; };
    const seen = e => { if (!(e.epoch > last)) return false; last = e.epoch; return true; };
    const line = e => e.shown ? { shown: { ...e.shown, path: local(e.shown.path) } } : (latest = e.with || null, eventOf(e));
    async function poll() {
      const page = await rpc('history', { after: last, limit: 40, with: 'x', ...(who ? { who } : {}) });
      const fresh = (page.events || []).filter(e => e.shown ? true : seen(e) && wanted(e));
      if (page.next > last) last = page.next;
      return deliver(fresh.map(line));
    }
    async function backlog() {   // what happened before the page opened: the last page of history, oldest first, drawn once
      const page = await rpc('history', { before: 0, limit: 40, with: 'x', ...(who ? { who } : {}) });   // with x: the quiet rule reads what each event wrote
      const events = (page.events || []).filter(e => !e.shown && wanted(e)).reverse();
      for (const e of events) seen(e);
      return deliver(events.map((e, i) => ({ ...eventOf(e), quiet: i < events.length - 1 })));
    }
    const startPoll = () => { if (!polling) polling = every(() => poll().catch(() => {}), 700); };
    const stopPoll = () => { if (polling) { clear(polling); polling = null; } };
    function open() {
      if (!ES) return startPoll();
      let opened = false;
      try { stream = new ES(base + '/mcp/stream'); } catch (e) { return startPoll(); }
      stream.onopen = () => { opened = true; stopPoll(); poll().catch(() => {}); };
      stream.onmessage = m => { let e; try { e = JSON.parse(m.data); } catch (err) { return; } if (e.shown || (seen(e) && wanted(e))) deliver([line(e)]); };
      stream.onerror = () => { stream.close(); stream = null; startPoll(); later(open, opened ? 2000 : 30000); };
    }
    backlog().catch(() => {}).then(open);
    return { stop: () => { stopPoll(); if (stream) stream.close(); } };
  }
  return { read, answer, graph, follow, qa, rpc, cursor, referencedBy };
}

// the page: /live?views=<folder>&who=<writer>
function start(doc) {
  const el = doc.getElementById('live'); if (!el) return null;
  const q = new URLSearchParams(doc.location ? doc.location.search : '');
  const views = local(q.get('views') || ''), who = q.get('who') || '';
  return mountViewer(el, mcpSource({ views, who }), { crumb: views, views });
}

const GooLive = { mountViewer, mcpSource, start, slotLayout, recordHTML, actionHTML, moved, askedHTML, fromHTML, chainHTML, cursorLine, quietLine, worldGraphHTML, graphHTML, stripHTML, crumbHTML, cellsHTML, lineHTML, qaChipHTML, qaHidden, qaFolderOf, referencedHTML,
  adapt: { valueOf, slotsOf, nodeOf, readOf, answerOf, eventOf, labelOf, writtenOf, summary, world, local, spelling, folderOf, goHTML } };
root.GooLive = GooLive;
if (typeof module !== 'undefined') module.exports = GooLive;
if (typeof document !== 'undefined') { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => start(document)); else start(document); }
})(globalThis);
