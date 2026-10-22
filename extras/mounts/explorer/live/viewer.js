// Shrine viewer: one component, no interaction, real time.
// mountViewer(element, source) draws the record the last write touched, resolved, with its flow above.
// source: { read(path, care, case), answer(path), graph(), follow(handler) }  (see GUIDE.md section 1)
// Everything here is a pure function from data to HTML, reconciled by data-path and data-case.

export function mountViewer(el, source, opts = {}) {
  el.classList.add('sv');
  el.innerHTML = `<div class="sv-bar"><div class="sv-crumb"><span data-path="">namespace</span></div><div class="sv-when"></div></div><div class="sv-main"><div class="sv-now"></div><div class="sv-earlier"></div></div>`;
  const $ = sel => el.querySelector(sel);
  const state = { events: [], shown: null };

  async function index() {
    const g = await source.graph();
    const asked = new Map();
    for (const c of g.cells) for (const i of c.inputs) { const k = i.path.replace(/^\/x\//, ''); (asked.get(k) || asked.set(k, []).get(k)).push({ ...c, pin: i.pin, view: !!i.view }); }
    source._asked = asked; source._cells = new Map(g.cells.map(c => [c.path, c]));
  }
  // what a write moved: the cells that read any touched path, one hop
  const moved = touched => { const out = new Set(); for (const t of touched) for (const q of (source._asked.get(t) || [])) out.add(last(q.path) + (q.answer ? ' ' + q.answer : '')); for (const t of touched) { const seg = t.split('/'); for (let i = seg.length - 1; i > 0; i--) for (const q of (source._asked.get(seg.slice(0, i).join('/')) || [])) out.add(last(q.path) + (q.answer ? ' ' + q.answer : '')); } return [...out]; };

  // one action: a line; opens into its records, each a line that opens into the card
  function actionHTML(ev, open) {
    const n = ev.touched.length, mv = moved(ev.touched);
    const sum = `<summary><span class="ep">${ev.shown ? 'shown' : ev.epoch}</span><span class="lab">${esc(ev.label)}</span><span class="who">${esc(ev.who)}</span><span class="cnt">${ev.shown ? esc(ev.shown.path) : n + (n === 1 ? ' record' : ' records')}</span>${mv.length ? `<span class="mv">${esc(mv.slice(0, 3).join(' · '))}${mv.length > 3 ? ' …' : ''}</span>` : ''}</summary>`;
    return `<details class="sv-act" data-epoch="${ev.epoch}" ${open ? 'open' : ''}>${sum}<div class="body"></div></details>`;
  }
  async function fillAction(det, ev, openRecords) {
    const body = det.querySelector('.body'); if (body.dataset.filled) return; body.dataset.filled = '1';
    const paths = ev.shown ? [ev.shown.path] : ev.touched;
    const items = await Promise.all(paths.map(async p => {
      const r = await source.read(p, 'x', ev.shown ? ev.shown.case : 0);
      let line;
      if (r && r.record === null) line = '<span class="m gone">deleted</span>';
      else if (r && isCell(r.record)) { const a = await source.answer(p); const sl = a.tree ? Object.entries(a.tree.slots) : []; line = `<span class="m ${a.bad ? 'bad' : a.note ? 'note' : ''}">${esc(a.bad || a.note || (sl.length ? sl[0][1].toLocaleString() + ' ' + sl[0][0] : (a.tree ? a.tree.kids.length + ' rows' : '')))}</span>`; }
      else { const sl = r ? Object.entries(r.record || {}).slice(0, 3) : []; line = `<span class="m">${sl.map(([k, v]) => esc(k) + ' ' + (typeof v === 'number' ? v.toLocaleString() : esc(String(v)).slice(0, 24))).join(' · ')}</span>`; }
      return `<details class="sv-recd" data-path="${esc(p)}" ${openRecords ? 'open' : ''}><summary><span class="n">${esc(last(p))}</span><span class="p">${esc(p)}</span>${line}</summary><div class="body"></div></details>`;
    }));
    body.innerHTML = items.join('');
    for (const d of body.querySelectorAll('details.sv-recd')) { if (d.open) await fillRecord(d, ev); d.addEventListener('toggle', () => d.open && fillRecord(d, ev)); }
  }
  async function fillRecord(det, ev) {
    const body = det.querySelector('.body'); if (body.dataset.filled) return; body.dataset.filled = '1';
    const r = await source.read(det.dataset.path, 'z', ev.shown ? ev.shown.case : 0);
    body.innerHTML = r ? await recordHTML(source, r, false, new Set()) : '';
  }

  async function draw(ev) {
    await index();
    const nowEl = $('.sv-now'), earlier = $('.sv-earlier');
    nowEl.innerHTML = actionHTML(ev, true);
    const det = nowEl.querySelector('details.sv-act'); await fillAction(det, ev, true);
    earlier.innerHTML = state.events.filter(e => e !== ev).slice().reverse().map(e => actionHTML(e, false)).join('');
    for (const d of earlier.querySelectorAll('details.sv-act')) d.addEventListener('toggle', () => { if (!d.open) return; const e = state.events.find(x => String(x.epoch) === d.dataset.epoch); fillAction(d, e, false); });
    $('.sv-when').innerHTML = ev.shown ? `<span class="shown">shown as is</span>` : `now <b>${ev.epoch}</b>`;
  }

  source.follow(async msg => {
    if (msg.shown) { const ev = { epoch: 'shown', label: 'show ' + msg.shown.path, who: 'agent', touched: [], shown: msg.shown }; return draw(ev); }
    if (!msg.touched || !msg.touched.length) return;
    state.events.push(msg); return draw(msg);
  });
  return { draw };
}

// ---------- rendering ----------
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const last = p => p ? p.split('/').pop() : 'namespace';
const isCell = rec => !!rec && typeof rec.formula === 'string' && rec.formula.startsWith('-> /weft/stdlib/');
const refOf = s => { const m = /^-> (\S+)(?: @ (\d+))?$/.exec(s || ''); return m ? { path: m[1], pin: m[2] ? Number(m[2]) : null } : null; };

// one value, by kind; the only place a value's kind is decided
function valueHTML(v, cls = 'sv-v') {
  if (typeof v === 'number') return `<span class="${cls}">${v.toLocaleString()}</span>`;
  const s = String(v);
  const r = refOf(s); if (r) return `<span class="${cls} ref" data-path="${esc(r.path.replace(/^\/x\//, ''))}">${esc(s)}</span>`;
  if (/^blob:/.test(s)) { const [, hash, mime, size] = s.split(':'); return `<span class="${cls} blob">${mime && mime.startsWith('image') ? `<img alt="" src="/blob/${esc(hash)}">` : ''}${esc(hash.slice(0, 8))} &middot; ${esc(size || '')}</span>`; }
  if (s === 'yes' || s === 'no') return `<span class="${cls} flag ${s}">${s}</span>`;
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return `<span class="${cls}">${esc(s)}</span>`;
  return `<span class="${cls} text">${esc(s)}</span>`;
}
const isShort = v => typeof v === 'number' || String(v).length < 24;

// the record body: layout chosen from the slots handed in (GUIDE.md section 2)
export function slotLayout(slots) {
  const s = Object.entries(slots || {});
  if (!s.length) return '';
  if (s.length === 1 && typeof s[0][1] === 'number') return `<div class="sv-one">${s[0][1].toLocaleString()}<span class="u">${esc(s[0][0])}</span></div>`;
  const long = s.some(([, v]) => typeof v !== 'number' && String(v).length > 80);
  if (s.length > 6 || long) return `<div class="sv-list">${s.map(([k, v]) => `<span class="sv-k">${esc(k)}</span>${valueHTML(v)}`).join('')}</div>`;
  return `<div class="sv-grid">${s.map(([k, v]) => `<div class="s ${isShort(v) ? '' : 'wide'}"><span class="sv-k">${esc(k)}</span>${valueHTML(v)}</div>`).join('')}</div>`;
}

async function rowSlots(source, node) {
  let slots = node.slots;
  if (isCell(slots)) { const r = await source.answer(node.path); slots = r.tree ? (Object.keys(r.tree.slots).length ? r.tree.slots : { '': r.tree.kids.length + ' rows' }) : { '': r.note || r.bad }; }
  return Object.entries(slots).map(([k, v]) => `<span>${k ? `<span class="k">${esc(k)}</span>` : ''}${valueHTML(v, 'v')}</span>`).join('');
}

async function kidHTML(source, node, depth, bump) {
  const s = Object.keys(node.slots || {}).length;
  const row = `<div class="sv-row ${bump.has(node.path) ? 'bump' : ''}" data-path="${esc(node.path)}" data-case="${node.case || ''}"><span class="n ${s ? '' : 'folder'}">${esc(node.name)}</span><span class="sl">${await rowSlots(source, node)}</span></div>`;
  const kids = node.kids || [];
  const inner = !kids.length ? '' : depth >= 3 ? `<div class="sv-row"><span class="more">${kids.length} beneath</span></div>` : (await Promise.all(kids.map(k => kidHTML(source, k, depth + 1, bump)))).join('');
  return `<div class="sv-kid">${row}${askedHTML(source, node.path, 1)}${inner}</div>`;
}

export async function recordHTML(source, r, showPath, bump) {
  const node = { name: last(r.path), path: r.path, slots: r.record || {}, kids: r.kids || [] };
  let body;
  if (r.record === null) body = `<div class="sv-gone">deleted</div>`;
  else if (isCell(node.slots)) {
    const a = await source.answer(node.path);
    const made = `<details class="sv-made"><summary>made of</summary>${slotLayout(node.slots)}</details>`;
    if (a.bad) body = `<div class="sv-note bad">${esc(a.bad)}</div>${made}`;
    else if (a.note) body = `<div class="sv-note">${esc(a.note)}</div>${made}`;
    else body = `${slotLayout(a.tree.slots)}${a.tree.kids.length ? `<div class="sv-kids">${(await Promise.all(a.tree.kids.map(k => kidHTML(source, k, 1, bump)))).join('')}</div>` : ''}${made}`;
  } else body = `${slotLayout(node.slots)}${node.kids.length ? `<div class="sv-kids">${(await Promise.all(node.kids.map(k => kidHTML(source, k, 1, bump)))).join('')}</div>` : ''}`;
  return `<div class="sv-rec ${bump.has(node.path) ? 'bump' : ''}" data-path="${esc(node.path)}" data-case="${r.case || ''}"><div class="sv-head"><span class="n">${esc(node.name)}</span>${showPath ? `<span class="p">${esc(node.path)}</span>` : ''}</div>${fromHTML(source, node.path)}${body}${askedHTML(source, node.path, 1)}</div>`;
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

// ---------- the world, drawn: what was written on the left growing down, what was asked to the right growing out ----------
// g = { sources: [{path, meta}], cells: [{path, formula, settings, answer, note, bad, inputs: [{path, pin, view}]}] }
const W = { col: 224, row: 38, pillW: 168, pillH: 24, padX: 18, padY: 10 };
export function worldGraphHTML(g, focus, bump) {
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
export function graphHTML(root, deps) {
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

export function stripHTML(node, here) {
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
