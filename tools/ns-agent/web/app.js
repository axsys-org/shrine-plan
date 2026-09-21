const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
let lastVersion = '', previousSession = '', busy = false, eventLength = 0, lastChats = '', posting = false, lastProposal = '';
const drafts = new Map();
const labels = { user: 'You', model: 'Model', operation: 'Operation', result: 'Shrine', external: 'External change', dependency: 'Dependency note', check: 'Independent check', error: 'Stopped', compression_proposal: 'Compression proposal', compaction: 'Context compacted', compression_cancelled: 'Context kept' };
function scalar(value) { return JSON.stringify(value); }

function goalNode(goal) {
  const box = el('div', 'goal-state');
  box.append(el('div', `goal-status ${goal.fulfilled ? 'fulfilled' : ''}`,
    goal.fulfilled ? '✓ Fulfilled · still watching' :
      Object.keys(goal.conditions).length ? '○ Open · conditions to check' : '○ Goal saved · defining conditions'));
  for (const [name, condition] of Object.entries(goal.conditions)) {
    const row = el('div', 'goal-condition');
    row.append(el('div', condition.met ? 'condition-met' : '', `${condition.met ? '✓' : '○'} ${name} · ${condition.met ? 'met' : 'not established'}`));
    row.append(el('div', 'goal-note', condition.note));
    row.append(el('div', 'goal-target', `${condition.path} · ${condition.care}`));
    box.append(row);
  }
  return box;
}

function eventNode(e) {
  const box = el('article', `event ${e.kind}`);
  box.id = e.id;
  box.append(el('span', 'event-icon'));
  const head = el('div', 'event-head');
  head.append(el('span', '', e.kind === 'user' && e.data.intent === 'goal' ? 'You · New goal' : labels[e.kind] || e.kind));
  if (e.parent) head.append(el('span', '', `↳ ${Array.isArray(e.parent) ? e.parent.join(' + ') : e.parent}`));
  head.append(el('span', 'ref', e.ref)); box.append(head);
  const d = e.data;
  if (e.kind === 'operation' || e.kind === 'external') {
    const card = el('div', 'op-card');
    const title = el('div', 'op-title'); title.append(el('span', `badge ${d.op}`, String(d.op || '?').toUpperCase()), el('span', '', d.path || ''));
    card.append(title);
    if (d.why) card.append(el('div', 'op-why', d.why));
    if (d.op === 'goal') card.append(el('pre', 'op-fields', JSON.stringify({note: d.note, conditions: d.conditions}, null, 2)));
    if (d.fields && Object.keys(d.fields).length) card.append(el('pre', 'op-fields', JSON.stringify(d.fields, null, 2)));
    box.append(card);
  } else if (e.kind === 'result') {
    const line = el('div', 'ack-line');
    line.append(el('span', 'ack-dot', d.ok ? '✓' : '×'));
    line.append(el('span', '', d.ok ? (d.review || (d.ack ? `ACK ${d.ack}` : `${(d.records || []).length} records read`)) : d.error));
    if (d.ack) line.append(el('span', '', `· ${(d.changes || []).length} changes`));
    if (d.runtime_ms !== undefined) line.append(el('span', '', `· ${d.runtime_ms} ms`));
    box.append(line);
    for (const change of d.changes || []) {
      const diff = el('div', 'effect'); diff.append(el('div', 'effect-path', change.path));
      if (change.after === null) diff.append(el('del', '', 'record removed'));
      else {
        for (const [key, value] of Object.entries(change.after)) {
          if (change.before && JSON.stringify(change.before[key]) === JSON.stringify(value)) continue;
          const row = el('div', ''); row.append(el('span', '', `${key}: `));
          if (change.before && Object.hasOwn(change.before, key)) row.append(el('del', '', scalar(change.before[key])), el('span', '', ' → '));
          row.append(el('ins', '', scalar(value))); diff.append(row);
        }
        for (const key of Object.keys(change.before || {})) if (!Object.hasOwn(change.after, key)) diff.append(el('div', '', `${key}: removed`));
        if (!Object.keys(change.after).length) diff.append(el('ins', '', '{}'));
      }
      box.append(diff);
    }
    if (d.records && d.records.length) {
      const details = el('details', ''); details.append(el('summary', '', 'Read result'), el('pre', '', JSON.stringify(d.records, null, 2))); box.append(details);
    }
    if (d.cascade_error) box.append(el('div', 'event-text', `Cascade error: ${d.cascade_error}`));
  } else if (e.kind === 'dependency') {
    const card = el('div', 'op-card');
    const title = el('div', 'op-title'); title.append(el('span', 'badge', 'WAKE'), el('span', '', d.watcher));
    card.append(title, el('div', 'op-why', d.note || 'A watched dependency changed.'));
    if (d.watcher_record?.['/app/goal']) card.append(goalNode(d.watcher_record['/app/goal']));
    card.append(el('div', 'op-fields', 'Changed: '+d.changed.map(x=>`${x.path} (${x.care})`).join(', ')));
    const details=el('details',''); details.append(el('summary','','Dependency context'),el('pre','',JSON.stringify(d.dependencies,null,2)));
    card.append(details);box.append(card);
  } else if (e.kind === 'compression_proposal') {
    box.append(el('div', 'event-text', d.summary));
    const details=el('details',''); details.append(el('summary','','Proposed goals'),el('pre','',JSON.stringify(d.goals,null,2)));box.append(details);
  } else if (e.kind === 'compaction') {
    box.append(el('div','event-text',d.text),el('div','op-why',`${(d.before_bytes/1024).toFixed(1)} KB → ${(d.after_bytes/1024).toFixed(1)} KB of model context`));
  } else if (e.kind === 'check') {
    box.append(el('div', `check-result ${d.pass ? '' : 'failed'}`, `${d.pass ? '✓' : '×'} Step ${d.step} · ${d.checks.filter(c => c.pass).length}/${d.checks.length} state checks passed`));
    const details = el('details', ''); details.append(el('summary', '', 'Inspect independent checks'), el('pre', '', JSON.stringify(d.checks, null, 2))); box.append(details);
  } else {
    box.append(el('div', 'event-text', d.text || (e.kind === 'model' ? 'Choosing the next operation.' : '')));
  }
  return box;
}

function renderCompression(s) {
  const box=$('compression-review'), p=s.pending_compression;
  if(!box)return; // An already-open page may predate the newly deployed template.
  const version=JSON.stringify([s.session_id,p]);
  if(version!==lastProposal){
    lastProposal=version;box.replaceChildren();box.hidden=!p;
    if(p){
      box.append(el('h3','','Review before compacting'),el('p','event-text',p.summary));
      for(const g of p.goals){
        const details=el('details','compression-goal');
        details.append(el('summary','',g.path),el('p','event-text',g.note));
        for(const [name,c] of Object.entries(g.conditions)) details.append(el('p','goal-note',`${name}: ${c.note} (${c.path}, ${c.care}; ${c.met ? 'assessed met' : 'not established'})`));
        box.append(details);
      }
      box.append(el('p','review-help','Approval installs these goals and starts fresh model context from persistent goals. Your namespace and visible history stay. Send corrections in chat to revise this proposal.'));
      const actions=el('div','goal-actions');
      const revise=el('button','secondary','Send corrections');revise.id='compression-revise';
      revise.onclick=()=>{$('prompt').value='Revise the compression proposal: ';$('prompt').focus();};
      const dismiss=el('button','quiet','Keep current context');dismiss.id='compression-dismiss';
      dismiss.onclick=()=>post('dismiss_compression',{proposal_ref:p.ref}).catch(fail);
      const accept=el('button','','Approve & compact');accept.id='compression-approve';
      accept.onclick=()=>post('approve_compression',{proposal_ref:p.ref}).catch(fail);
      actions.append(revise,dismiss,accept);box.append(actions);
    }
  }
  for(const button of box.querySelectorAll('button'))button.disabled=busy||posting;
  $('context-status').textContent=s.context_generation ? `Context compacted ${s.context_generation} time${s.context_generation===1?'':'s'}. Earlier history is kept for your inspection.` : 'Conversation stays in context until you approve compression.';
}

function renderNamespace(records, count) {
  const root = {children: new Map()};
  for (const record of records) {
    let n = root;
    for (const part of record.path.split('/').filter(Boolean)) {
      if (!n.children.has(part)) n.children.set(part, {children: new Map()});
      n = n.children.get(part);
    }
    n.record = record;
  }
  const target = $('namespace'); target.replaceChildren(el('div', 'ns-root', '/'));
  function walk(node, parent) {
    for (const [name, child] of [...node.children].sort(([a], [b]) => a.localeCompare(b))) {
      const block = el('div', 'ns-node'), label = el('div', 'ns-label');
      label.append(el('span', 'ns-folder', child.children.size ? '⌄' : '·'), el('span', '', name));
      if (child.record) label.append(el('span', 'case', `case ${child.record.case}`));
      block.append(label);
      if (child.record) {
        const fields = el('div', 'ns-fields');
        for (const [k, v] of Object.entries(child.record.fields)) {
          if (k === '/app/goal') { fields.append(goalNode(v)); continue; }
          const row = el('div', 'ns-field'); row.append(el('span', 'ns-key', k), el('span', 'ns-value', scalar(v))); fields.append(row);
        }
        if (!fields.childNodes.length) fields.append(el('span', 'ns-key', '{}'));
        block.append(fields);
      }
      walk(child, block); parent.append(block);
    }
  }
  walk(root, target);
  if (!records.length) target.append(el('div', 'ns-empty', 'No application records yet.'));
  const log = el('div', 'ns-node'); log.append(el('div', 'ns-label', `agent / events · ${count} observation records`)); target.append(log);
}

async function refresh() {
  try {
    const response = await fetch('/api/state'); if (!response.ok) throw Error('Connection lost');
    const s = await response.json();
    busy = s.busy; document.body.classList.toggle('busy', busy);
    $('connection').textContent = busy ? 'Shrine live · working' : 'Shrine live · native runtime';
    $('connection').classList.remove('failed');
    $('status').textContent = s.status;
    for (const id of ['send', 'new-chat', 'new-goal', 'chat-select', 'inject', 'goal-submit']) $(id).disabled = busy || posting;
    $('model-label').textContent = s.model.replace('anthropic/', '') + ' · OpenRouter';
    const m = s.metrics;
    const stats = [['Model calls', m.calls], ['NS operations', m.operations], ['Context', ((s.context_bytes ?? m.context_bytes)/1024).toFixed(1), 'KB'], ['API cost', '$'+m.cost.toFixed(3)]];
    $('metrics').replaceChildren(...stats.map(([label,value,unit]) => { const cell=el('div','metric'), val=el('div','metric-value',String(value)); if(unit)val.append(el('small','',unit)); cell.append(el('div','metric-label',label),val); return cell; }));
    $('event-count').textContent = `${s.events.length} events`;
    const stream = $('stream');
    const shouldScroll = stream.scrollHeight-stream.scrollTop-stream.clientHeight < 120 || eventLength === 0;
    if (previousSession !== s.session_id) {
      if (previousSession) drafts.set(previousSession, $('prompt').value);
      $('prompt').value = drafts.get(s.session_id) || '';
      stream.replaceChildren(); eventLength=0; previousSession=s.session_id; lastVersion='';
    }
    const chatVersion = JSON.stringify(s.chats.map(c => [c.id, c.title])) + s.session_id;
    if (chatVersion !== lastChats) {
      $('chat-select').replaceChildren(...s.chats.map(c => {const option=el('option','',c.title);option.value=c.id;return option;}));
      $('chat-select').value = s.session_id; lastChats = chatVersion;
    }
    if (!busy) $('chat-select').value = s.session_id;
    renderCompression(s);
    if (s.events.length > eventLength) {
      if (!eventLength) stream.replaceChildren();
      for (const e of s.events.slice(eventLength)) stream.append(eventNode(e));
      eventLength=s.events.length;
      if(shouldScroll)stream.scrollTop=stream.scrollHeight;
    }
    if (!eventLength && !stream.children.length) {
      const empty=el('div','empty'); empty.append(el('div','empty-symbol','+'),el('h3','','A new conversation. A place to start.'),el('p','','Give the model something to do, or create a goal. Each operation and its actual result will appear here.'));stream.append(empty);
    }
    const version=JSON.stringify(s.records)+s.events.length;
    if(version!==lastVersion){renderNamespace(s.records,s.events.length);lastVersion=version;}
  } catch(e) { $('connection').textContent='Runtime disconnected';$('connection').classList.add('failed'); }
}
async function post(action, data={}) {
  if(busy || posting)throw Error('The agent is still working. Your text has been kept.');
  posting=true;
  try {
    const r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat_id:previousSession,...data})});
    const d=await r.json();if(!r.ok)throw Error(d.error);
  } finally {posting=false;await refresh();}
}
function fail(e){$('status').textContent=e.message;}
$('composer').addEventListener('submit',async e=>{e.preventDefault();const prompt=$('prompt').value.trim();if(!prompt)return;try{await post('turn',{prompt});$('prompt').value='';}catch(e){fail(e);}});
$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();$('composer').requestSubmit();}});
$('new-chat').onclick=()=>post('new_chat').catch(fail);
$('chat-select').onchange=()=>post('switch_chat',{chat_id:$('chat-select').value}).catch(fail);
$('new-goal').onclick=()=>{$('goal-error').textContent='';$('goal-dialog').showModal();$('goal-description').focus();};
$('goal-cancel').onclick=()=>$('goal-dialog').close();
$('goal-form').addEventListener('submit',async e=>{
  e.preventDefault();const description=$('goal-description').value.trim();if(!description)return;
  try{await post('goal',{description});$('goal-description').value='';$('goal-dialog').close();}
  catch(error){$('goal-error').textContent=error.message;}
});
$('injection').value=JSON.stringify({op:'poke',path:'/users/josh',fields:{active:true}},null,2);
$('inject').onclick=()=>{try{post('turn',{external:JSON.parse($('injection').value)}).catch(fail);}catch(e){fail(e);}};
refresh();setInterval(refresh,800);
