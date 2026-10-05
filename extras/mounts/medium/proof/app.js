// Browser mechanics only. Every value, program, action and binding comes from
// Shrine. This renderer has no calculator/editor/application dispatch table.
import {FrameGate, acknowledgedDraft, sameFrame, occurrenceSelection} from './interaction.mjs';
const $ = selector => document.querySelector(selector);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const canvas = $('#canvas'), plane = $('#plane'), objects = $('#objects');
let state, selected = null, connecting = null, applying = null, drag = null, pan = null;
let job = null, queue = Promise.resolve(), storageKey, timer, hasSavedLayout = false;
let inspected = null, inspectMode = false, etag = '', polling = false, reconnecting = false;
let newPosition = null;
let space = null;
let intentKey = '';
const intentDrafts = new Map();
const gate = new FrameGate();
const sizes = new ResizeObserver(() => {draw(); positionComposer();});
const pendingActions = new Set();
let layout = {positions: {}, camera: {x: 260, y: 100, z: 1}};
const expanded = new Set(), drafts = new Map();
const get = id => state?.nodes.find(n => n.id === id);
const visibleNodes = () => (state?.nodes || []).filter(n => (n.parent || '/') === (space || '/'));
function enterSpace(id) {
  rememberDrafts(); layout.cameras ||= {}; layout.cameras[space || '/'] = {...layout.camera};
  space = id; layout.space = id; selected = null; inspected = null; newPosition = null;
  layout.camera = layout.cameras[id || '/'] || {x: 248, y: 44, z: .9};
  transform(); render(); save();
}
const selection = n => ({subject: n.id, owner: n.id, slots: [], occurrence: '', kind: 'subject', label: n.label});
const position = id => layout.positions[id] || {x: 0, y: 0};
const save = () => storageKey && localStorage.setItem(storageKey, JSON.stringify(layout));
const transform = () => {
  const c = layout.camera;
  plane.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.z})`;
  $('#zoom').textContent = Math.round(c.z * 100) + '%';
  positionComposer();
};
const point = (x, y) => {
  const r = canvas.getBoundingClientRect(), c = layout.camera;
  return {x: (x - r.left - c.x) / c.z, y: (y - r.top - c.y) / c.z};
};
function feedback(message, error = false) {
  clearTimeout(timer);
  $('#feedback').hidden = !message;
  $('#feedback').classList.toggle('error', error);
  const content = $('#feedback span'); content.replaceChildren();
  if (error && message.length > 220) {
    content.append(el('span', '', 'This interaction needs attention.'));
    const detail = el('details'), title = el('summary', '', 'Diagnostic');
    detail.append(title, el('pre', '', message)); content.append(detail);
  } else content.textContent = message;
  if (!error) timer = setTimeout(() => $('#feedback').hidden = true, 4500);
}
async function api(path, data) {
  const response = await fetch(path, {method: data ? 'POST' : 'GET',
    headers: data ? {'Content-Type': 'application/json'} : {},
    ...(data ? {body: JSON.stringify(data)} : {})});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The native operation was rejected.');
  return result;
}
function cancel() {
  job = null; $('#working').hidden = true;
  api('/api/cancel', {}).catch(() => {}); render();
}
function op(operation, body = {}) {
  gate.beginWrite();
  const work = async () => {
    if (job) cancel();
    const next = await api('/api', {operation, body, expected: state.expected, event: crypto.randomUUID()});
    accept(next); return next;
  };
  const pending = queue.then(work).finally(() => gate.endWrite());
  queue = pending.catch(error => feedback(error.message, true));
  return pending;
}
function accept(frame) {
  gate.accepted();
  const changed = new Set(state?.nodes.filter(n => {
    const next = frame.nodes.find(other => other.id === n.id);
    return next && n.view?.html !== next.view?.html;
  }).map(n => n.id));
  const key = 'grove-world:' + location.port + ':' + frame.workspace;
  if (storageKey !== key) {
    storageKey = key;
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      hasSavedLayout = !!saved && Object.keys(saved.positions || {}).length > 0;
      if (hasSavedLayout) {layout = saved; space = saved.space || null;}
    } catch {}
  }
  const previous = state; state = frame;
  const live = new Set(frame.nodes.map(n => n.id));
  for (const id of Object.keys(layout.positions)) if (!live.has(id)) delete layout.positions[id];
  for (const key of drafts.keys()) if (!live.has(key.split('|')[0])) drafts.delete(key);
  if (!live.has(selected)) selected = null;
  if (space && !live.has(space)) space = null;
  if (inspected) {
    const owner = frame.nodes.find(n => n.id === inspected.subject);
    // Source locations and occurrences belong to the displayed revision.
    if (!owner || owner.expected !== inspected.basis.expected || owner.displayed !== inspected.basis.displayed) inspected = null;
  }
  const counters = new Map();
  frame.nodes.forEach(n => {
    const index = counters.get(n.parent) || 0; counters.set(n.parent, index+1);
    const old = previous?.nodes.find(other => other.id === n.id);
    if (old && old.parent !== n.parent) delete layout.positions[n.id];
    layout.positions[n.id] ||= {x: (index % 3) * 450, y: Math.floor(index / 3) * 700};
  });
  $('#undo').disabled = !frame.can_undo;
  $('#connection').textContent = 'Shrine connected'; $('#connection').className = 'online';
  transform(); render(); save();
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) for (const id of changed) {
    cardFor(id)?.animate([
      {boxShadow: '0 0 0 3px #76a88865'},
      {boxShadow: '0 0 0 0px #76a88800'}
    ], {duration: 650});
  }
}
function rememberDrafts() {
  for (const input of objects.querySelectorAll('[data-key]')) {
    drafts.set(input.dataset.key, {value: input.value, dirty: input.value !== input.defaultValue,
      focus: input === document.activeElement, start: input.selectionStart, end: input.selectionEnd});
  }
}
function restoreDrafts() {
  for (const input of objects.querySelectorAll('[data-key]')) {
    const prior = drafts.get(input.dataset.key); if (!prior) continue;
    if (prior.dirty) input.value = prior.value;
    if (prior.focus) {input.focus({preventScroll: true}); try {input.setSelectionRange(prior.start, prior.end);} catch {}}
  }
}
function focus(id, center = false) {
  const parent = get(id)?.parent;
  if (parent && parent !== (space || '/')) enterSpace(parent === '/' ? null : parent);
  if (selected !== id) inspected = null;
  selected = id; applying = null; newPosition = null;
  if (center) {
    const p = position(id), c = layout.camera;
    c.x = canvas.clientWidth / 2 - (p.x + 200) * c.z; c.y = 65 - p.y * c.z;
    transform(); save();
  }
  render();
}
function cardFor(id) {return [...objects.children].find(n => n.dataset.id === id);}
function geometry(id) {
  const box = cardFor(id); return {...position(id), w: box?.offsetWidth || 400, h: box?.offsetHeight || 100};
}
function controls(n, box) {
  const footer = el('div', 'object-tools');
  const children = state.nodes.filter(other => other.parent === n.id);
  if (children.length) {
    const open = el('button', '', 'Open · '+children.length+' things'); open.onclick = () => enterSpace(n.id); footer.append(open);
  }
  if (n.authored) {
    const use = el('button', '', 'Use this');
    use.onclick = () => {
      if (!n.inputs.length) apply(n, null);
      else {applying = n.id; feedback('Choose what ' + n.label + ' should operate on.'); render();}
    };
    footer.append(use);
  }
  const inspect = el('button', '', expanded.has(n.id) ? 'Hide source' : 'Source');
  inspect.onclick = () => {expanded.has(n.id) ? expanded.delete(n.id) : expanded.add(n.id); render();};
  footer.append(inspect); box.append(footer);
}
function nativeSurface(n, box) {
  const surface = el('div', 'native-surface'); surface.innerHTML = n.view.html;
  box.append(surface);
  const parts = new Map([...surface.querySelectorAll('[data-node]')].map(part => [part.dataset.node, part]));
  for (const occurrence of n.view.occurrences) {
    const part = parts.get(occurrence.id); if (!part) continue;
    part.addEventListener('pointerover', event => {
      if (!(inspectMode || event.altKey) || event.target.closest('[data-node]') !== part) return;
      selected = n.id; inspected = occurrenceSelection(n, occurrence);
      objects.querySelectorAll('.inspected').forEach(element => element.classList.remove('inspected'));
      part.classList.add('inspected');
      for (const card of objects.children) card.classList.toggle('selected', card.dataset.id === selected);
      syncIntent(); showInspection(); positionComposer();
    });
    if (occurrence.kind === 'input') {
      const input = part.matches('input,textarea') ? part : part.querySelector('input,textarea');
      if (input) {input.dataset.nativeSlot = occurrence.slot; input.dataset.key = n.id + '|native:' + occurrence.slot;}
    }
    if (occurrence.kind !== 'action' || !occurrence.invoke) continue;
    const button = part.matches('button') ? part : part.querySelector('button');
    if (!button) continue;
    button.dataset.nativeDisabled = String(button.disabled);
    button.disabled ||= pendingActions.has(n.id);
    button.onclick = async () => {
      const current = get(n.id), inputs = {}, held = [...surface.querySelectorAll('[data-native-slot]')];
      for (const input of held) inputs[input.dataset.nativeSlot] = input.value;
      // Clear only the submitted drafts after successful native execution.
      // Failed compilation preserves typed source and the installed program.
      pendingActions.add(n.id); button.disabled = true;
      const status = cardFor(n.id)?.querySelector('.thing-kind'); if (status) status.textContent = 'Updating…';
      cardFor(n.id)?.querySelectorAll('[data-native-disabled]').forEach(control => control.disabled = true);
      try {
        await op('act', {target: n.id, control: occurrence.control, expected: current.expected,
          displayed: current.displayed, publication: state.publication, inputs});
        for (const input of cardFor(n.id)?.querySelectorAll('[data-key]') || []) {
          if (input.dataset.nativeSlot in inputs && acknowledgedDraft(drafts.get(input.dataset.key), inputs[input.dataset.nativeSlot], input.defaultValue)) {
            input.value = input.defaultValue; drafts.delete(input.dataset.key);
          }
        }
      } catch {} finally {
        pendingActions.delete(n.id);
        const current = cardFor(n.id); current?.querySelectorAll('[data-native-disabled]').forEach(control => control.disabled = control.dataset.nativeDisabled === 'true');
        const status = current?.querySelector('.thing-kind'); if (status) status.textContent = '';
      }
    };
  }
  for (const input of surface.querySelectorAll('input,textarea')) input.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || (input.matches('textarea') && !(event.metaKey || event.ctrlKey))) return;
    // Submit only an unambiguous control in the enclosing native group.
    // This is a keyboard equivalent of clicking it, not an inferred application action.
    let group = input.parentElement;
    while (group && group !== surface) {
      const buttons = [...group.querySelectorAll('button')];
      if (buttons.length) {
        if (buttons.length === 1) {event.preventDefault(); buttons[0].click();}
        return;
      }
      group = group.parentElement;
    }
  });
}
function properties(n, box) {
  if (!n.properties?.length && !expanded.has(n.id) && n.view) return;
  const list = el('div', 'properties');
  for (const field of n.properties || []) {
    const row = el('label', 'property'), name = el('span', '', field.label), input = el('input');
    input.value = input.defaultValue = field.value; input.placeholder = '—';
    input.dataset.key = n.id + '|' + field.slot; input.setAttribute('aria-label', n.label + ' ' + field.label);
    input.onchange = async () => {
      const value = input.value;
      try {await op('property', {target: n.id, slot: field.slot, value});
        const current = [...(cardFor(n.id)?.querySelectorAll('[data-key]') || [])].find(el => el.dataset.key === input.dataset.key);
        if (current && acknowledgedDraft(drafts.get(input.dataset.key), value, current.defaultValue)) {
          current.value = current.defaultValue; drafts.delete(input.dataset.key);
        }
      } catch {}
    };
    input.onkeydown = event => {if (event.key === 'Enter') input.blur();};
    row.append(name, input); list.append(row);
  }
  box.append(list);
  if (!expanded.has(n.id)) return;
  const form = el('form', 'property-form'), name = el('input'), value = el('input'), add = el('button', '', '+');
  name.placeholder = 'Property'; name.required = true; name.dataset.key = n.id + '|property-name';
  name.setAttribute('aria-label', 'New property name'); value.placeholder = 'Value'; value.dataset.key = n.id + '|property-value';
  form.append(name, value, add);
  form.onsubmit = async event => {event.preventDefault(); try {
    await op('property', {target: n.id, label: name.value.trim(), value: value.value});
    drafts.delete(name.dataset.key); drafts.delete(value.dataset.key);
  } catch {}};
  box.append(form);
}
function render() {
  if (!state) return;
  rememberDrafts();
  const visible = visibleNodes(), shown = new Set(visible.map(n => n.id));
  for (const box of [...objects.children]) if (!shown.has(box.dataset.id)) {sizes.unobserve(box); box.remove();}
  for (const n of visible) {
    let box = cardFor(n.id);
    if (!box) {box = el('article', 'thing'); box.dataset.id = n.id; box.tabIndex = 0; objects.append(box); sizes.observe(box);}
    box.className = 'thing' + (n.view ? ' native' : '') + (selected === n.id ? ' selected' : '') +
      (job?.subject === n.id ? ' thinking' : '') + (applying && applying !== n.id ? ' applicable' : '');
    box.style.left = position(n.id).x + 'px'; box.style.top = position(n.id).y + 'px';
    const signature = JSON.stringify([n, expanded.has(n.id), job?.subject === n.id, state.nodes.filter(child => child.parent === n.id).map(child => child.id)]);
    if (box.dataset.signature === signature) continue;
    box.dataset.signature = signature; box.replaceChildren();
    const head = el('div', 'thing-head'), title = el('span', 'thing-title', n.label), kind = el('span', 'thing-kind', pendingActions.has(n.id) ? 'Updating…' : '');
    head.append(title, kind); box.append(head);
    const port = el('button', 'port', '+'); port.title = 'Compose with another thing';
    port.setAttribute('aria-label', 'Connect ' + n.label);
    port.onclick = () => {connecting = n.id; feedback('Choose another thing to compose with ' + n.label + '.');}; box.append(port);
    if (n.inputs.length) {
      const inputs = el('div', 'inputs');
      n.inputs.forEach((input, index) => {
        const open = (n.open || []).includes(String(index));
        const ref = el('button', open ? 'open-input' : '', open ? '+ bind input' : get(input.subject)?.label || 'Unresolved');
        ref.onclick = () => {
          if (open) {applying = {target: n.id, index, slots: input.slots}; feedback('Choose the subject for this input.');}
          else focus(input.subject, true);
        };
        inputs.append(ref);
      }); box.append(inputs);
    }
    properties(n, box);
    if (n.view) nativeSurface(n, box);
    else if (n.open?.length) box.append(el('p', 'quiet', 'Ready to be applied. Its inputs stay open.'));
    else if (!n.authored) box.append(el('p', 'quiet', 'A name is enough to begin.'));
    if (job?.subject === n.id) {
      const work = el('div', 'local-work'); work.setAttribute('role', 'status');
      const label = el('span', '', job.message || 'Reading native state…'), stop = el('button', '', 'Stop');
      stop.onclick = cancel; work.append(label, stop); box.append(work);
    }
    controls(n, box);
    if (expanded.has(n.id)) {
      const details = el('div', 'details');
      details.append(el('code', 'identity', n.id));
      if (n.description || n.intent) details.append(el('p', '', n.description || n.intent));
      const source = n.source || state.nodes.find(other => other.pattern === n.pattern && other.source)?.source;
      if (source) {const disclosure = el('details'), summary = el('summary', '', 'Native source'); disclosure.append(summary, el('pre', '', source)); details.append(disclosure);}
      const remove = el('button', 'remove', 'Remove from this world'); remove.onclick = () => op('retire', {target: n.id}).catch(() => {}); details.append(remove);
      box.append(details);
    }
  }
  restoreDrafts();
  const spaces = $('#spaces'); spaces.replaceChildren();
  for (const n of state.nodes) if (state.nodes.some(other => other.parent === n.id)) {
    const open = el('button', 'space-name'+(space === n.id ? ' active' : ''), n.label);
    open.onclick = () => enterSpace(n.id); spaces.append(open);
  }
  $('#spaces-heading').hidden = !spaces.children.length;
  $('#space-title').textContent = space ? get(space)?.label : 'All things';
  $('#space-back').hidden = !space;
  const library = $('#definitions'); library.replaceChildren();
  const seen = new Set();
  for (const n of state.nodes) if (n.authored && !seen.has(n.pattern)) {
    seen.add(n.pattern);
    const row = el('div', 'definition'), name = el('button', 'definition-name', n.label), use = el('button', 'definition-use', '+');
    name.onclick = () => focus(n.id, true); use.title = 'Use ' + n.label;
    use.onclick = () => {if (!n.inputs.length) apply(n, null); else {applying = n.id; feedback('Choose what ' + n.label + ' should operate on.');}};
    row.append(name, use); library.append(row);
  }
  if (!seen.size) library.append(el('p', 'quiet', 'Working definitions appear here. Each can be used again.'));
  $('#count').textContent = state.nodes.length + ' things · ' + seen.size + ' definitions';
  $('#welcome').hidden = !!visible.length;
  $('#scope').textContent = inspected ? get(selected)?.label + ' · ' + inspected.kind : selected ? get(selected)?.label : 'New thing';
  $('#intent').placeholder = selected ? 'Change this, explain it, or try an idea…' : 'What shall we make?';
  $('#clear-selection').hidden = !selected;
  syncIntent(); showInspection();
  requestAnimationFrame(() => {draw(); positionComposer();});
}

function syncIntent() {
  const key = (selected || '')+'|'+(inspected?.occurrence || '');
  if (key === intentKey) return;
  intentDrafts.set(intentKey, $('#intent').value);
  intentKey = key; $('#intent').value = intentDrafts.get(key) || '';
}

function positionComposer() {
  const form = $('#intent-form'); if (!form) return;
  const card = selected && cardFor(selected);
  const bound = card?.getBoundingClientRect(), c = layout.camera, rect = canvas.getBoundingClientRect();
  const width = Math.min(440, window.innerWidth - (window.innerWidth > 750 ? 250 : 160));
  if (bound || newPosition) {
    const x = bound?.left ?? rect.left + c.x + newPosition.x*c.z;
    const y = bound ? bound.bottom+12 : rect.top+c.y+newPosition.y*c.z;
    form.classList.add('attached'); form.style.width = width+'px';
    form.style.left = Math.max(window.innerWidth > 750 ? 228 : 150, Math.min(x, window.innerWidth-width-16))+'px';
    form.style.top = Math.max(78, Math.min(y, window.innerHeight-form.offsetHeight-40))+'px';
  } else {
    form.classList.remove('attached'); form.style.width = ''; form.style.left = ''; form.style.top = '';
  }
}
function showInspection() {
  const panel = $('#inspection'); panel.replaceChildren(); panel.hidden = !inspected;
  if (!inspected) return;
  const node = get(inspected.subject); if (!node) return;
  panel.append(el('strong', '', node.label + ' · ' + inspected.kind));
  for (const slot of inspected.slots) {
    const field = node.fields?.find(f => f.slot === slot), row = el('div', 'inspection-field');
    row.append(el('code', '', slot), el('span', '', field ? (field.value.length > 100 ? field.value.slice(0, 100) + '…' : field.value) : 'Exact native slot'));
    panel.append(row);
  }
  panel.append(el('small', '', 'Source line '+inspected.source.line+' · Enter to work here'));
  $('#scope').textContent = node.label+' · '+inspected.kind;
}
function curve(a, b, active = false) {
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path'), d = Math.max(40, Math.abs(b.x - a.x) / 2);
  path.setAttribute('d', `M${a.x},${a.y} C${a.x+d},${a.y} ${b.x-d},${b.y} ${b.x},${b.y}`);
  path.classList.toggle('active', active); return path;
}
function draw(cursor) {
  const wires = $('#wires'); wires.replaceChildren();
  for (const n of visibleNodes()) {
    const b = geometry(n.id);
    n.inputs.forEach((input, index) => {
      if (!cardFor(input.subject) || (n.open || []).includes(String(index)) || n.id === input.subject) return;
      const a = geometry(input.subject);
      wires.append(curve({x: a.x+a.w, y: a.y+25}, {x: b.x, y: b.y+25+index*14}, selected === n.id || selected === input.subject));
    });
  }
  if (connecting && cursor) {const a = geometry(connecting); wires.append(curve({x: a.x+a.w, y: a.y+25}, cursor, true));}
}
function placeNew(frame, previous, near) {
  const n = frame.nodes.find(item => !previous.has(item.id)); if (!n) return;
  const at = near ? geometry(near) : {x: -layout.camera.x/layout.camera.z+300, y: -layout.camera.y/layout.camera.z+80, w: 0};
  layout.positions[n.id] = {x: at.x+at.w+90, y: at.y}; selected = n.id; save(); render(); return n;
}
async function apply(pattern, subject) {
  applying = null;
  const previous = new Set(state.nodes.map(n => n.id));
  const inputs = pattern.inputs.map((input, i) => ({...input, subject: i === 0 && subject ? subject : '/'}));
  try {
    let frame = await op('instantiate', {pattern: pattern.id, inputs});
    const added = frame.nodes.find(n => !previous.has(n.id));
    if (space && added) frame = await op('place', {target: added.id, parent: space});
    placeNew(frame, previous, subject || (cardFor(pattern.id) ? pattern.id : null));
  } catch {}
}
async function connect(a, b) {
  connecting = null; if (a === b) return;
  const known = state.nodes.find(n => n.relation && n.inputs.length === 2 && n.inputs[0].subject === a && n.inputs[1].subject === b);
  if (known) {focus(known.id, true); feedback('Using the established connection.'); return;}
  try {
    const before = new Set(state.nodes.map(n => n.id));
    let frame = await op('relate', {source: a, destination: b});
    const added = frame.nodes.find(n => !before.has(n.id));
    if (space && added) frame = await op('place', {target: added.id, parent: space});
    const n = placeNew(frame, before, b); if (n) infer(n.id, '');
  } catch {}
}
async function infer(id, text, exact = null) {
  const node = get(id); if (!node) return;
  if (job) cancel();
  const current = {subject: id, started: performance.now(), message: 'Reading the selected things'}; job = current; render();
  try {
    const request = await api('/api/gesture', {kind: 'refine', selected: exact || selection(node), text, inference: !text});
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 500)); if (job !== current) return;
      const result = await api('/api/jobs/' + request.id); if (job !== current) return;
      const elapsed = Math.round((performance.now() - current.started)/1000);
      current.message = ({reading: 'Reading native state', selecting: 'Preparing context', interpreting: 'Writing Grove / Foil', repairing: 'Responding to compiler feedback', checking: 'Compiling and checking', assessing: 'Assessing the candidate'}[result.status] || 'Working') + ' · ' + elapsed + 's';
      const progress = cardFor(id)?.querySelector('.local-work span'); if (progress) progress.textContent = current.message;
      if (result.status === 'done') {
        current.published = true;
        // Another client can act after this job commits. Read the current world
        // instead of painting the job's now historical result over that activity.
        const ticket = gate.beginRead(), latest = await api('/api/read');
        if (job !== current) return;
        job = null; $('#working').hidden = true;
        if (gate.mayRead(ticket)) accept(latest); else render();
        cardFor(id)?.classList.add('arrived'); feedback(result.message || 'Running in Shrine.'); return;
      }
      if (['error', 'cancelled'].includes(result.status)) throw Error(result.message);
    }
  } catch (error) {if (job === current) {
    job = null; $('#working').hidden = true; render();
    feedback(current.published ? 'The native interaction completed, but its current view could not be fetched. Reconnecting…' : error.message, true);
    // Keep the unsuccessful request available to correct, without erasing a follow-up draft.
    if (!current.published && selected === id && !$('#intent').value) $('#intent').value = text;
  }}
}
$('#intent-form').onsubmit = async event => {
  event.preventDefault(); const input = $('#intent'), text = input.value.trim(); if (!text || !state) return;
  input.value = '';
  if (selected) {infer(selected, text, inspected); return;}
  try {
    const before = new Set(state.nodes.map(n => n.id));
    let frame = await op('define', {label: text.length > 72 ? text.slice(0, 69) + '…' : text});
    const added = frame.nodes.find(n => !before.has(n.id));
    if (space && added) frame = await op('place', {target: added.id, parent: space});
    const at = newPosition && {...newPosition}; const n = placeNew(frame, before);
    if (n && at) {layout.positions[n.id] = at; newPosition = null; render(); save();}
    if (n) infer(n.id, text);
  } catch {input.value = text;}
};
$('#clear-selection').onclick = () => {selected = null; inspected = null; newPosition = null; render(); $('#intent').focus();};
$('#undo').onclick = () => op('undo').catch(() => {});
$('#space-back').onclick = () => {const parent = get(space)?.parent; enterSpace(parent && parent !== '/' ? parent : null);};
$('#cancel').onclick = cancel; $('#dismiss-feedback').onclick = () => $('#feedback').hidden = true;
$('#fit').onclick = () => {
  const boxes = visibleNodes().map(n => geometry(n.id)); if (!boxes.length) return;
  const l = Math.min(...boxes.map(b => b.x)), t = Math.min(...boxes.map(b => b.y)), r = Math.max(...boxes.map(b => b.x+b.w)), b = Math.max(...boxes.map(b => b.y+b.h));
  const z = Math.max(.22, Math.min(1, (canvas.clientWidth-320)/(r-l), (canvas.clientHeight-190)/(b-t)));
  layout.camera = {x: 240+(canvas.clientWidth-270-(r-l)*z)/2-l*z, y: 35-t*z, z}; transform(); save();
};
canvas.addEventListener('pointerdown', event => {
  if (event.button !== 0 || !state) return;
  if (event.altKey || inspectMode) {event.preventDefault(); return;}
  const box = event.target.closest('.thing'), id = box?.dataset.id;
  if (applying && id) {
    event.preventDefault();
    if (typeof applying === 'string') apply(get(applying), id);
    else {const binding = applying; applying = null; op('rebind', {target: binding.target, index: String(binding.index), selection: {subject: id, slots: binding.slots, occurrence: ''}}).catch(() => {});}
    return;
  }
  if (connecting && id && connecting !== id) {event.preventDefault(); connect(connecting, id); return;}
  if (id) {
    inspected = null;
    objects.querySelectorAll('.inspected').forEach(part => part.classList.remove('inspected'));
  }
  if (event.target.closest('input,textarea,button,summary,details')) {if (id) focus(id); return;}
  if (id) {
    focus(id);
    if (!event.target.closest('.thing-head')) return;
    drag = {id, x: event.clientX, y: event.clientY, origin: {...position(id)}};
  }
  else {selected = null; inspected = null; newPosition = null; connecting = null; applying = null; pan = {x: event.clientX, y: event.clientY, camera: {...layout.camera}}; render();}
  event.preventDefault();
});
document.addEventListener('pointermove', event => {
  if (drag) {
    layout.positions[drag.id] = {x: drag.origin.x+(event.clientX-drag.x)/layout.camera.z, y: drag.origin.y+(event.clientY-drag.y)/layout.camera.z};
    const box = cardFor(drag.id); box.style.left = position(drag.id).x+'px'; box.style.top = position(drag.id).y+'px'; draw(); positionComposer();
  } else if (pan) {layout.camera.x = pan.camera.x+event.clientX-pan.x; layout.camera.y = pan.camera.y+event.clientY-pan.y; transform();}
  else if (connecting) draw(point(event.clientX, event.clientY));
});
document.addEventListener('pointerup', () => {if (drag || pan) save(); drag = null; pan = null;});
canvas.addEventListener('dblclick', event => {
  if (event.target.closest('.thing') || !state) return;
  newPosition = point(event.clientX,event.clientY); selected = null; inspected = null;
  render(); positionComposer(); $('#intent').focus();
});
// Inspection is a temporary pointing mode, not a separate inspector workflow.
canvas.addEventListener('click', event => {if (event.altKey || inspectMode) {event.preventDefault(); event.stopImmediatePropagation();}}, true);
canvas.addEventListener('wheel', event => {
  if (event.target.closest('textarea,pre')) return;
  event.preventDefault(); const c = layout.camera;
  if (event.ctrlKey || event.metaKey) {
    const p = point(event.clientX, event.clientY), r = canvas.getBoundingClientRect();
    c.z = Math.max(.22, Math.min(1.8, c.z*Math.exp(-event.deltaY*.008)));
    c.x = event.clientX-r.left-p.x*c.z; c.y = event.clientY-r.top-p.y*c.z;
  } else {c.x -= event.deltaX; c.y -= event.deltaY;}
  transform(); save();
}, {passive: false});
document.addEventListener('keydown', event => {
  if (event.key === 'Alt') {inspectMode = true; canvas.classList.add('inspecting');}
  if (event.key === 'Escape') {selected = null; inspected = null; newPosition = null; applying = null; connecting = null; render(); draw();}
  if (event.target.closest('input,textarea,button,[contenteditable]')) return;
  if ((event.metaKey || event.ctrlKey) && event.key === 'z') {event.preventDefault(); op('undo').catch(() => {});}
  if ((event.metaKey || event.ctrlKey) && event.key === '0') {event.preventDefault(); $('#fit').click();}
  if (event.key === 'Enter') $('#intent').focus();
});
document.addEventListener('keyup', event => {if (event.key === 'Alt') {inspectMode = false; canvas.classList.remove('inspecting');}});
window.addEventListener('blur', () => {inspectMode = false; canvas.classList.remove('inspecting');});
window.addEventListener('resize', positionComposer);

async function refresh() {
  if (polling || document.hidden || !state) return;
  const ticket = gate.beginRead(); if (ticket === null) return;
  polling = true;
  try {
    const response = await fetch('/api/read', {headers: etag ? {'If-None-Match': etag} : {}});
    if (response.status === 401 && !reconnecting) {
      reconnecting = true; try {await api('/connect', {});} finally {reconnecting = false;}
      return;
    }
    if (response.status === 304) {
      $('#connection').textContent = 'Shrine connected'; $('#connection').className = 'online'; return;
    }
    const frame = await response.json();
    if (!response.ok) throw Error(frame.error || 'Native owner unavailable');
    if (!gate.mayRead(ticket)) return;
    etag = response.headers.get('ETag') || '';
    if (!sameFrame(state, frame)) accept(frame);
    $('#connection').textContent = 'Shrine connected'; $('#connection').className = 'online';
  } catch {
    $('#connection').textContent = 'Reconnecting…'; $('#connection').className = '';
  } finally {polling = false;}
}
setInterval(refresh, 2200);
document.addEventListener('visibilitychange', refresh);
function followLocation() {
  let subject;
  try {subject = decodeURIComponent(location.hash.slice(1));} catch {return false;}
  if (!get(subject)) return false;
  if (state.nodes.some(n => n.parent === subject)) enterSpace(subject);
  else focus(subject, true);
  return true;
}
window.addEventListener('hashchange', followLocation);
async function start() {
  try {
    await api('/connect', {}); accept(await api('/api/read'));
    const subject = decodeURIComponent(location.hash.slice(1));
    if (get(subject) && state.nodes.some(n => n.parent === subject)) {enterSpace(subject); return;}
    if (layout.space === undefined && !subject) {
      const newest = [...state.nodes].reverse().find(n => state.nodes.some(child => child.parent === n.id));
      if (newest) {enterSpace(newest.id); return;}
    }
    const initial = get(subject) || state.nodes.at(-1);
    if (initial && !hasSavedLayout) {
      // First opening only: put a construction beside its actual inputs.
      // Existing user placement is never recomposed by an update or inference.
      const inputs = [...new Set(initial.inputs.map(input => input.subject))].filter(id => get(id) && id !== initial.id);
      let y = 0;
      for (const id of inputs) {layout.positions[id] = {x: 0, y}; y += geometry(id).h + 32;}
      layout.positions[initial.id] = {x: inputs.length ? 450 : 0, y: 0};
      let rest = 0;
      for (const node of state.nodes) if (node.id !== initial.id && !inputs.includes(node.id)) {
        layout.positions[node.id] = {x: 960, y: rest}; rest += geometry(node.id).h + 32;
      }
      layout.camera = {x: 250, y: 48, z: Math.min(1, Math.max(.5, (canvas.clientWidth - 280) / (inputs.length ? 850 : 400)))};
      selected = initial.id; hasSavedLayout = true; transform(); render(); save();
    } else if (get(subject)) focus(subject, true);
  } catch (error) {
    feedback(error.message, true); $('#connection').textContent = 'Reconnecting…';
    setTimeout(start, 2500);
  }
}
start();
