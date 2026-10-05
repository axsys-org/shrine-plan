import {createInspector} from './canvas-inspector.js';
import {createInfiniteCanvas} from './infinite-canvas.js';
import {createPresentationExperiment} from './presentation-experiment.js';
const $ = id => document.getElementById(id);
const caseNodes = new Map();
let live, frame, experiment = false, dirty = false, revision = 0, editRevision = 0, previewPending = false, previewTimer, previewRequest = 0, toastTimer;
let inspectedCase = null;
let inspectedDescriptor = null;
let inspectedSource = null, sourceRequest = 0;
let presentationContext = null;
let timelineRange = {start:0,end:1440,anchor:0};
const recordNodes = new Map(), equipmentNodes = new Map();
const inspector = createInspector({panel:$('inspector'),toggle:$('open-inspector'),close:$('close-inspector'),pin:$('pin-inspector'),render:showInspection});
const nativeSurfaces=createInfiniteCanvas({root:$('native-workspace'),inspector,request,onMutation:value=>{$('error').hidden=true;live=value;revision++;render(value);},onError:failure});
const presentationExperiment=createPresentationExperiment({root:$('native-workspace'),request,
  onOpen:(node,subject)=>{inspector.dismiss();nativeSurfaces.attachInstrument(node,subject);},
  onClose:node=>nativeSurfaces.releaseInstrument(node)});
function workspace(native) {
  document.body.classList.toggle('canvas-mode',native);
  $('native-workspace').hidden=!native;$('booking-workspace').hidden=native;$('booking-nav').hidden=native;
  $('show-native').classList.toggle('selected',native);$('show-booking').classList.toggle('selected',!native);
  inspector.refresh();
}
workspace(true);
$('show-native').onclick=()=>{workspace(true);nativeSurfaces.refresh().catch(failure);};
$('show-booking').onclick=()=>workspace(false);
const time = value => `${String(Math.floor(Number(value)/60)).padStart(2,'0')}:${String(Number(value)%60).padStart(2,'0')}`;
const minute = value => { const [h,m] = value.split(':').map(Number); return String(h*60+m); };
const text = (id,value) => { if($(id).textContent!==value) $(id).textContent = value; };
const policy = () => ({turnaround:$('turnaround').value, same_person:String($('same-person').checked), intent:$('intent').value || 'Explore the handover interval'});
function toast(message) { text('toast',message); $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,3800); }
function failure(error) { text('error',error.message); $('error').hidden=false; }
async function request(operation,body={},options={}) {
  const response = await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,expected:options.expected??live?.expected??'0',event:options.event??crypto.randomUUID(),body})});
  const value = await response.json();
  if (!response.ok) throw Object.assign(new Error(value.error || `Native action failed (${response.status})`),{status:response.status});
  return value;
}
async function change(operation,body={}) {
  $('error').hidden=true;
  const editedAtStart=editRevision, preserveDraft=operation==='reserve' && dirty;
  clearTimeout(previewTimer);previewRequest++;
  const value = await request(operation,body);
  live=value; dirty=preserveDraft || editRevision!==editedAtStart; revision++; frame=value; render(value);
  if(dirty)queuePreview(false);
  return value;
}
function syncPolicy(value) {
  const p=value.candidate?.policy??value.policy;
  $('turnaround').value=p.turnaround; $('same-person').checked=p.same_person;
  if (value.candidate?.intent && document.activeElement!==$('intent') && !$('intent').value) $('intent').value=value.candidate.intent;
  drawBuffer();
}
function drawBuffer() {
  const n=Number($('turnaround').value);
  text('minutes',`${n} min`); text('buffer-label',`${n} min turnaround`);
  const record=frame?.reservations.find(item=>item.id===$('handover-record').value);
  $('timeline').hidden=!record;
  if(!record)return;
  const names=new Map([...frame.people,...frame.equipment].map(item=>[item.id,item.label]));
  const start=Math.max(0,Math.floor((Number(record.start)-60)/60)*60);
  const end=Math.ceil((Number(record.finish)+150)/60)*60;
  timelineRange={start,end,anchor:Number(record.finish)};
  const position=value=>(Number(value)-start)/(end-start)*100;
  const block=$('handover-reservation');
  block.style.left=`${position(record.start)}%`;block.style.width=`${position(record.finish)-position(record.start)}%`;
  block.textContent=`${names.get(record.person)||record.person} · ${time(record.start)}–${time(record.finish)}`;
  text('handover-label',names.get(record.equipment)||record.equipment);
  $('timeline-ticks').replaceChildren(...Array.from({length:5},(_,i)=>{const label=document.createElement('span');label.textContent=time(start+(end-start)*i/4);return label;}));
  $('buffer-block').style.left=`${position(record.finish)}%`;
  $('buffer-block').style.width=`${n/(end-start)*100}%`;
  $('buffer-handle').style.left=`${position(Number(record.finish)+n)}%`;text('buffer-text',n?`${n} min`:'');
  $('buffer-handle').setAttribute('aria-label',`Handover interval: ${n} minutes. Drag or use left and right arrow keys.`);
}
function selectOptions(id,items) {
  const select=$(id), current=select.value;
  if (JSON.stringify([...select.options].map(x=>[x.value,x.text]))===JSON.stringify(items.map(x=>[x.id,x.label]))) return;
  select.replaceChildren(...items.map(item=>{const option=document.createElement('option');option.value=item.id;option.textContent=item.label;return option;}));
  if(items.some(x=>x.id===current)) select.value=current;
}
function outcome(value,key,basis,existing) {
  const node=existing??document.createElement('span');node.className=`outcome ${value.kind}`;
  node.textContent=({available:'● Available',unavailable:'◷ Unavailable',unknown:'? Unknown'})[value.kind];
  node.title=value.label;
  return node;
}
function renderInspection(value) {
  const item=value.cases.find(item=>JSON.stringify(item.query)===inspectedCase);
  $('case-inspection').hidden=!item;
  if(!item)return;
  const names=new Map([...value.people,...value.equipment].map(item=>[item.id,item.label]));
  text('case-query',`${names.get(item.query.person)||item.query.person} · ${names.get(item.query.equipment)||item.query.equipment} · ${time(item.query.start)}–${time(item.query.finish)}`);
  const panels=[['Installed',item.before],...(experiment?[['Experiment',item.after]]:[])].map(([basis,result])=>{
    const panel=document.createElement('div');panel.className=`result-explanation ${result.kind}`;
    const title=document.createElement('b');title.textContent=`${basis} · ${result.kind}`;
    const reason=document.createElement('p');reason.textContent=result.label;panel.append(title,reason);
    const record=value.reservations.find(record=>record.id===result.reservation);
    if(record){
      const link=document.createElement('button');link.className='text-button';
      link.textContent=`${names.get(record.person)||record.person} · ${time(record.start)}–${time(record.finish)} ↗`;
      link.title=record.id;
      link.onclick=()=>{
        inspector.select(`record:${record.id}`);
        const node=[...document.querySelectorAll('.record')].find(node=>node.dataset.subject===record.id);
        if(node)node.scrollIntoView({behavior:'smooth',block:'center'});
      };
      panel.append(link);
    }
    return panel;
  });
  $('case-explanations').replaceChildren(...panels);
  text('case-basis',`${item.origin} · ${value.reservations.length} current reservations · native basis ${value.expected}${previewPending?' · updating experiment…':''}`);
}
function render(value,{preview=false}={}) {
  frame=value;document.body.dataset.ready='true';inspector.begin();
  if(!preview && !dirty) syncPolicy(value);
  text('connection','● Connected to your machine');text('live-revision',`Installed · v${value.revision}`);
  text('rule-summary',`${value.policy.turnaround} min turnaround${value.policy.same_person?' · same-person exception':''}`);
  text('booking-count',`${value.reservations.length} shared reservation${value.reservations.length===1?'':'s'}`);
  text('equipment-count',String(value.equipment.length));
  text('candidate-ref',preview?'Unsaved preview · installed behavior is unchanged':value.candidate?`Revision ${value.candidate.revision} · based on v${value.candidate.basis}`:'No proposed change');
  $('welcome').hidden=true;
  if(value.candidate) experiment=true;
  $('experiment').hidden=!experiment;
  $('start-experiment').hidden=experiment;
  text('mode-label',`${value.policy.turnaround} minutes between different people${value.policy.same_person?' · same person can continue':''}`);
  text('mode-detail',experiment?'Experiment against retained cases. Publish only when the intended outcomes hold.':'This installed native rule evaluates every new reservation.');
  text('candidate-column',experiment?'Experiment':'Same behavior');
  const rows = value.cases.map((item,index)=>{
    const key=JSON.stringify(item.query);
    let row=caseNodes.get(key);
    if(!row) {
      row=document.createElement('tr');
      for(let n=0;n<4;n++)row.append(document.createElement('td'));
      const button=document.createElement('button');button.className='remember';button.textContent='Keep';
      button.title='Remember this outcome: evaluate it against every future rule';
      button.addEventListener('click',()=>remember(key).catch(failure));
      row.children[3].append(button);caseNodes.set(key,row);
    }
    row.dataset.index=String(index);row.className=item.changed?'changed':'';
    const [label,before,after,control]=row.children;
    label.textContent=item.label;label.title=item.origin;
    const left=outcome(item.before,key,'installed',before.firstElementChild);
    const right=outcome(item.after,key,experiment?'experiment':'installed',after.firstElementChild);
    if(!before.firstElementChild)before.append(left);
    if(!after.firstElementChild)after.append(right);
    for(const [node,basis,result] of [[left,'installed',item.before],[right,'candidate',item.after]]) {
      bind(node,`case:${key}:${basis}`,{title:`${item.label} · ${result.kind}`,kind:'Native result',subject:value.subject,
        description:result.label,caseKey:key,rule:true,fields:[['Evaluation',basis==='candidate'&&experiment?'Candidate / preview':'Installed'],['Origin',item.origin],['Source',value.source]]});
    }
    bind(label,`query:${key}`,{title:item.label,kind:'Declared input case',subject:value.subject,caseKey:key,
      fields:Object.entries(item.query),description:item.origin});
    const button=control.firstElementChild;
    button.hidden=!experiment || item.after.kind==='unknown';
    button.disabled=previewPending;
    button.setAttribute('aria-label',`Remember: ${item.label} is ${item.after.kind}`);
    return row;
  });
  // Preserve existing focused controls when only their derived values change.
  const parent=$('case-rows');
  for(let index=0;index<rows.length;index++)if(parent.children[index]!==rows[index])parent.insertBefore(rows[index],parent.children[index]??null);
  for(const node of [...parent.children])if(!rows.includes(node))node.remove();
  for(const key of caseNodes.keys())if(!value.cases.some(item=>JSON.stringify(item.query)===key))caseNodes.delete(key);
  text('coverage',value.coverage);
  $('commitment-panel').hidden=!value.commitments.length;
  $('commitment-rows').replaceChildren(...value.commitments.map(item=>{
    const node=document.createElement('div');node.className=`commitment ${item.kind}`;
    const label=document.createElement('span');label.textContent=`${item.kind==='holding'?'✓':'!'} ${item.statement}`;
    const note=document.createElement('small');note.textContent=`${item.provenance} · ${item.detail}`;node.append(label,note);
    bind(node,`commitment:${item.key}`,{title:item.statement,kind:'Retained commitment',subject:value.subject,description:item.detail,
      fields:[['Commitment key',item.key],['Provenance',item.provenance],['Verdict',item.kind]],rule:true});return node;
  }));
  // Only the installed native candidate may be approved, never an ephemeral preview.
  const candidate=live?.candidate;
  $('publication').hidden=!candidate;
  const valid=candidate?.admissible && !dirty && !preview;
  $('publish').disabled=!valid;
  $('publication').classList.toggle('blocked',Boolean(candidate&&!candidate.admissible));
  text('publish-heading',candidate?.admissible?'Ready to become the rule.':'This would break something you asked to keep.');
  text('publish-detail',dirty?'Keep your latest experiment as the candidate before publishing.':candidate?.admissible?`Candidate ${candidate.revision} · ${candidate.new_commitments} new example(s) retained on publication.`:'The failed commitment above must hold before this version can be published.');
  const names = new Map([...value.people,...value.equipment].map(x=>[x.id,x.label]));
  const rowsForRecords=value.reservations.map(item=>{
    let node=recordNodes.get(item.id);
    if(!node){node=document.createElement('div');node.className='record';node.dataset.subject=item.id;
      node.append(document.createElement('span'),document.createElement('div'),document.createElement('span'));recordNodes.set(item.id,node);}
    const [avatar,label,clock]=node.children;
    avatar.className='avatar';avatar.textContent=(names.get(item.person)||'?').slice(0,1);
    label.replaceChildren(document.createTextNode(names.get(item.person)||item.person));
    const sub=document.createElement('small');sub.textContent=names.get(item.equipment)||item.equipment;label.append(sub);
    clock.className='time';clock.textContent=`${time(item.start)} — ${time(item.finish)}`;
    bind(node,`record:${item.id}`,recordDescriptor(item,value));
    bind(label,`record:${item.id}:person`,entityDescriptor(item.person,value));
    bind(sub,`record:${item.id}:equipment`,entityDescriptor(item.equipment,value));
    bind(clock,`record:${item.id}:time`,{...recordDescriptor(item,value),title:`${time(item.start)}–${time(item.finish)}`,description:'Time fields of this reservation. The record identity stays the same when its position in the list changes.'});
    return node;
  });
  reconcile($('reservation-rows'),rowsForRecords);
  for(const id of recordNodes.keys())if(!value.reservations.some(record=>record.id===id))recordNodes.delete(id);
  renderEquipment(value);
  selectOptions('handover-record',value.reservations.map(record=>({id:record.id,label:`${names.get(record.person)||record.person} · ${names.get(record.equipment)||record.equipment} · ${time(record.start)}–${time(record.finish)}`})));
  drawBuffer();
  const handover=value.reservations.find(item=>item.id===$('handover-record').value);
  if(handover)bind($('handover-reservation'),`handover:${handover.id}`,recordDescriptor(handover,value));
  const rule={title:'Availability rule',kind:'Installed behavior',subject:value.subject,rule:true,
    description:'A native program over reservation records. The controls expose turnaround and same-person behavior; arbitrary source authoring is not connected yet.',
    fields:[['Implementation source',value.source],['Installed revision',value.revision],['Turnaround',`${value.policy.turnaround} min`],['Same-person exception',String(value.policy.same_person)]]};
  for(const id of ['rule-surface','turnaround','same-person','buffer-handle','start-experiment','save-experiment','publication'])bind($(id),`rule:${id}`,rule);
  bind($('new-booking'),'action:reserve',{title:'Create reservation',kind:'Native action',subject:value.subject,description:'The installed rule evaluates the selected person, equipment and interval. The native owner checks the current basis before writing a record.',fields:[['Operation','reserve'],['Authority','Application administrator']]});
  bind($('records'),'collection:reservations',{title:'Reservations',kind:'Shared records',subject:value.subject,fields:[['Members',String(value.reservations.length)]],description:'Exact member identities are supplied by the native frame.'});
  selectOptions('person',value.people);selectOptions('equipment',value.equipment);
  $('intention-list').replaceChildren(...value.intentions.map(intent=>{const li=document.createElement('li');li.textContent=intent;return li;}));
  if(!preview) text('preview-status',value.candidate?'Candidate saved · installed behavior is unchanged':'Experiment only · installed behavior is unchanged');
  inspector.end();
}
function queuePreview(userEdit=true) {
  if(userEdit)editRevision++;
  previewPending=true;
  for(const button of document.querySelectorAll('.remember'))button.disabled=true;
  dirty=true;drawBuffer();text('preview-status','Evaluating in Shrine…');$('publish').disabled=true;
  clearTimeout(previewTimer);const id=++previewRequest, basis=revision;
  previewTimer=setTimeout(async()=>{
    try {const result=await request('evaluate',policy());if(id!==previewRequest||basis!==revision)return;previewPending=false;render(result,{preview:true});text('preview-status','Native preview · not published');}
    catch(error) {if(id===previewRequest){failure(error);text('preview-status','Last valid preview retained');}}
  },200);
}
async function keep() {clearTimeout(previewTimer);previewRequest++;previewPending=false;await change('stage',policy());toast('Candidate saved. Installed behavior is unchanged.');}
async function remember(key) {
  const item=frame.cases.find(item=>JSON.stringify(item.query)===key);
  if(!item || previewPending)throw new Error('Wait for the current situation to finish evaluating.');
  if(dirty || !live.candidate) await keep();
  if(!item.query) throw new Error('This case has no native input reference.');
  await change('demonstrate',{...item.query,label:`${item.label}: ${item.after.kind}`,available:String(item.after.kind==='available')});
  toast('This example will be retained when you publish.');
}
$('start-experiment').onclick=()=>{beginDirectExperiment();$('situations').open=true;queuePreview();};
$('handover-record').onchange=()=>render(frame,{preview:dirty});
const handle=$('buffer-handle');
function beginDirectExperiment(){experiment=true;$('experiment').hidden=false;$('start-experiment').hidden=true;}
function moveBuffer(event){
  const bounds=$('timeline').querySelector('.track').getBoundingClientRect();
  $('turnaround').value=String(Math.max(0,Math.min(120,Math.round(((event.clientX-bounds.left)/bounds.width*(timelineRange.end-timelineRange.start)+timelineRange.start-timelineRange.anchor)/5)*5)));
  queuePreview();
}
handle.addEventListener('pointerdown',event=>{event.preventDefault();beginDirectExperiment();handle.setPointerCapture(event.pointerId);moveBuffer(event);});
handle.addEventListener('pointermove',event=>{if(handle.hasPointerCapture(event.pointerId))moveBuffer(event);});
handle.addEventListener('pointerup',event=>{if(handle.hasPointerCapture(event.pointerId))handle.releasePointerCapture(event.pointerId);});
handle.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();beginDirectExperiment();$('turnaround').value=String(Math.max(0,Math.min(120,Number($('turnaround').value)+(event.key==='ArrowRight'?5:-5))));queuePreview();}});
$('turnaround').addEventListener('input',queuePreview);$('same-person').addEventListener('change',queuePreview);
$('intent').addEventListener('input',()=>{editRevision++;dirty=true;$('publish').disabled=true;});
$('save-experiment').onclick=()=>keep().catch(failure);
$('publish').onclick=async()=>{try{await change('publish',{revision:live.candidate.revision});experiment=false;$('experiment').hidden=true;$('start-experiment').hidden=false;render(live);toast('Published. This rule now governs real bookings.');}catch(error){failure(error);}};
$('discard').onclick=async()=>{try{await change('discard');experiment=false;render(live);toast('Candidate discarded. Installed rule retained.');}catch(error){failure(error);}};
$('source-toggle').onclick=async()=>{try{inspector.select('rule:rule-surface');$('source').hidden=false;const response=await fetch('/source');if(!response.ok)throw new Error('Source is unavailable.');text('source',await response.text());$('source').scrollIntoView({behavior:'smooth',block:'start'});}catch(error){failure(error);}};
$('attach-intent').onclick=()=>keep().catch(failure);
$('new-booking').onclick=()=>{$('booking-form').hidden=!$('booking-form').hidden;};
$('booking-form').onsubmit=async event=>{event.preventDefault();try{await change('reserve',{person:$('person').value,equipment:$('equipment').value,start:minute($('start').value),finish:minute($('finish').value)});toast('Reservation created through the installed rule.');$('booking-form').hidden=true;}catch(error){failure(error);}};
for(const button of document.querySelectorAll('[data-focus]'))button.onclick=()=>{document.querySelectorAll('[data-focus]').forEach(x=>x.classList.toggle('selected',x===button));const focus=button.dataset.focus;if(focus==='reservations')$('records').scrollIntoView({behavior:'smooth',block:'center'});else if(focus==='equipment')$('equipment-surfaces').scrollIntoView({behavior:'smooth',block:'start'});else $('rule-surface').scrollIntoView({behavior:'smooth',block:'start'});};
function reconcile(parent,nodes) {
  for(let i=0;i<nodes.length;i++)if(parent.children[i]!==nodes[i])parent.insertBefore(nodes[i],parent.children[i]??null);
  for(const child of [...parent.children])if(!nodes.includes(child))child.remove();
}
function bind(node,key,descriptor) {inspector.bind(node,key,()=>({...descriptor,basis:frame.expected}));}
function entityDescriptor(id,value) {
  const entity=[...value.people,...value.equipment].find(item=>item.id===id);
  const records=value.reservations.filter(record=>record.person===id||record.equipment===id);
  return {title:entity?.label||id,kind:value.people.some(item=>item.id===id)?'Person':'Equipment',subject:id,
    description:'Shared native subject. Reservations refer to this exact identity.',fields:[['Reservations',String(records.length)]],
    relations:records.map(record=>({key:`record:${record.id}`,label:`Reservation · ${time(record.start)}–${time(record.finish)}`,subject:record.id}))};
}
function recordDescriptor(item,value) {
  const names=new Map([...value.people,...value.equipment].map(x=>[x.id,x.label]));
  return {title:`${names.get(item.person)||item.person} · ${time(item.start)}–${time(item.finish)}`,kind:'Reservation',subject:item.id,
    description:'Persisted reservation supplied by the native owner.',
    fields:[['From',time(item.start)],['Until',time(item.finish)]],
    relations:[{key:`person:${item.person}`,label:`Person · ${names.get(item.person)||item.person}`,subject:item.person},
      {key:`equipment:${item.equipment}`,label:`Equipment · ${names.get(item.equipment)||item.equipment}`,subject:item.equipment}]};
}
function renderEquipment(value) {
  const nodes=value.equipment.map(item=>{
    let node=equipmentNodes.get(item.id);
    if(!node){node=document.createElement('article');node.className='equipment-card';node.append(document.createElement('h3'),document.createElement('p'),document.createElement('div'));equipmentNodes.set(item.id,node);}
    const [title,count,list]=node.children;title.textContent=item.label;
    const records=value.reservations.filter(record=>record.equipment===item.id).sort((a,b)=>Number(a.start)-Number(b.start));
    count.className='subtle';count.textContent=records.length?`${records.length} reservation${records.length===1?'':'s'}`:'No reservations recorded';
    const entries=records.map(record=>{const row=document.createElement('div');row.className='schedule-entry';
      const name=value.people.find(person=>person.id===record.person)?.label||record.person;
      const label=document.createElement('span');label.textContent=name;
      const timeNode=document.createElement('span');timeNode.textContent=`${time(record.start)}–${time(record.finish)}`;
      row.append(label,timeNode);bind(row,`schedule:${record.id}`,recordDescriptor(record,value));return row;});
    list.replaceChildren(...entries);bind(node,`equipment:${item.id}`,entityDescriptor(item.id,value));return node;
  });
  reconcile($('equipment-surfaces'),nodes);
  for(const id of equipmentNodes.keys())if(!value.equipment.some(item=>item.id===id))equipmentNodes.delete(id);
  // People may only be visible through a reservation; retain an explicit relation target.
  for(const person of value.people) {
    const node=[...$('reservation-rows').children].find(node=>value.reservations.find(record=>record.id===node.dataset.subject)?.person===person.id);
    if(node)inspector.bind(node.children[0],`person:${person.id}`,()=>({...entityDescriptor(person.id,frame),basis:frame.expected}));
  }
}
function showInspection(descriptor,{pinned}) {
  const identity=JSON.stringify([descriptor?.subject,descriptor?.source,descriptor?.sourceRevision]);
  const changed=inspectedDescriptor!==identity;
  inspectedDescriptor=identity;
  if(changed){$('source').hidden=true;$('inspector').scrollTop=0;sourceRequest++;}
  inspectedSource=descriptor?.sourceRevision?{target:descriptor.source,revision:descriptor.sourceRevision}:null;
  presentationContext=descriptor?.presentation?descriptor:null;
  $('refine-presentation').hidden=!presentationContext;
  $('native-source').hidden=!inspectedSource;
  $('approved-intentions').hidden=!!inspectedSource;
  text('inspection-kind',`${pinned?'PINNED · ':''}${descriptor?.kind||'NO LONGER PRESENT'}`);
  text('inspector-title',descriptor?.title||'This occurrence is no longer in the current frame.');
  text('inspection-description',descriptor?.description||'Its context is not being redirected to another record. Select another subject to continue.');
  text('subject-ref',descriptor?.subject||'Unavailable');text('basis-ref',descriptor?.basis||'Unavailable');
  $('intention-editor').hidden=!descriptor?.rule;
  $('inspection-fields').replaceChildren(...(descriptor?.fields||[]).map(([label,value])=>{
    const row=document.createElement('div');row.className='inspection-field';const key=document.createElement('span');key.textContent=label;
    const content=document.createElement('span');content.textContent=value;row.append(key,content);return row;
  }));
  $('inspection-relations').replaceChildren(...(descriptor?.relations||[]).map(relation=>{
    const button=document.createElement('button');button.className='relation-link';button.textContent=`${relation.label} ↗`;button.title=relation.subject;
    button.onclick=()=>inspector.select(relation.key);return button;
  }));
  inspectedCase=descriptor?.caseKey||null;
  if(frame)renderInspection(frame);
}
$('refine-presentation').onclick=()=>presentationExperiment.open(presentationContext);
$('native-source').onclick=async()=>{
  if(!inspectedSource)return;
  const selected=inspectedDescriptor, serial=++sourceRequest;
  $('source').hidden=false;text('source','Loading the published source…');
  try {
    const result=await request('source',inspectedSource);
    if(selected!==inspectedDescriptor||serial!==sourceRequest)return;
    text('source',result.files.map(file=>`${file.name}\n\n${file.text}`).join('\n\n'));
  } catch(error) {if(selected===inspectedDescriptor&&serial===sourceRequest)text('source',error.message);}
};
async function refresh(){
  const response=await fetch('/api');const value=await response.json();
  if(!response.ok)throw Object.assign(new Error(value.error),{status:response.status});
  text('connection','● Connected to your machine');
  if(live&&value.expected===live.expected)return;
  live=value;revision++;render(value);
  // A remote continuation or ordinary action can change the comparison basis.
  // Preserve local edits, but discard their obsolete findings and evaluate again.
  if(dirty)queuePreview(false);
}
$('refresh').onclick=()=>refresh().catch(failure);
async function start(){
  const token=new URLSearchParams(location.hash.slice(1)).get('session');
  if(token){history.replaceState(null,'',location.pathname);const response=await fetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});if(!response.ok)throw new Error('Open Grove Canvas from Applications to reconnect this browser.');}
  let polling=false;
  async function poll(){
    if(polling || document.hidden)return;
    polling=true;
    try{await refresh();$('browser-connect').hidden=true;}
    catch(error){
      if(error.status===401 || error.status===403){$('browser-connect').hidden=false;$('error').hidden=true;text('connection','Open Grove Canvas to connect');}
      else text('connection',live?'Reconnecting · your draft is here':'Starting your native world…');
    }finally{polling=false;}
  }
  await poll();
  try {await nativeSurfaces.read();}catch(error){if(live&&error.status!==401&&error.status!==403)failure(error);}
  setInterval(poll,3000);
  let surfacePolling=false;
  setInterval(async()=>{
    if(document.hidden||surfacePolling||$('native-workspace').hidden)return;
    surfacePolling=true;try{await nativeSurfaces.refresh();}catch(error){if(error.status!==401&&error.status!==403)failure(error);}finally{surfacePolling=false;}
  },12000);
}
start().catch(error=>{$('welcome').hidden=false;failure(error);text('connection','Not connected');});
