// Physical interaction and rendering only. Opaque keys return to native
// resolvers; there is no application discriminator or expression evaluator.
const $ = s => document.querySelector(s);
const space = $('#space'), viewport = $('#viewport'), occurrences = new Map();
let selected = null, inspecting = false, hovered = null;
let agentHealth = null, authorOccurrence = null, browseSubject='/0x11/app/user';
const nativeSelection=new Map();
// Native occurrences supply membership and order. Scrolling and drafts are
// local presentation state; visual adjacency never asserts a native dependency.
const arrangement='/0x11/app/user/canvas_places/surface';
let arrangementFrame=null, anchors=[], placements=[], activeFlow='home', restoring=false;
let arrangementQueue=Promise.resolve(), journalOccurrence=null, requestFlow=null, flowRestored=false;
const scrollPositions=new Map();
const friendly = value => value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
function arrangementAction(key,values){
  const run=async()=>{
    const frame=await call('native/frame',{subject:arrangement,viewport:[]});
    const arguments_=Object.entries(values).map(([name,value])=>({slot:'/'+name,kind:typeof value==='number'?'natural':'text',value:String(value)}));
    await call('native/act',{subject:arrangement,viewport:[],basis:frame.basis,key,parameters:[],arguments:arguments_},crypto.randomUUID());
    await readArrangement();
  };
  const result=arrangementQueue.then(run);arrangementQueue=result.catch(()=>{});return result;
}
async function readArrangement(){
  const frame=await call('native/frame',{subject:arrangement,viewport:[]});arrangementFrame=frame;
  const doc=new DOMParser().parseFromString(frame.html,'text/html');
  anchors=[...doc.querySelectorAll('[data-canvas-flow]')].map(el=>({id:el.dataset.canvasFlow,label:el.textContent,subject:el.dataset.canvasAnchor}));
  placements=[...doc.querySelectorAll('[data-canvas-occurrence]')].map(el=>({id:el.dataset.canvasOccurrence,flow:el.dataset.canvasFlowId,subject:el.dataset.canvasSubject,x:Number(el.dataset.canvasX),y:Number(el.dataset.canvasY)}));
  const list=$('#flow-list');list.replaceChildren();
  for(const anchor of anchors){const button=node('button',anchor.label,'flow-pin');button.setAttribute('aria-current',anchor.id===activeFlow?'page':'false');button.onclick=()=>switchFlow(anchor.id);list.append(button);}
  $('#flow-name').textContent=anchors.find(a=>a.id===activeFlow)?.label||'My space';
}
function updateEmpty(){
  $('#empty-flow').hidden=!!authorOccurrence?.surface.querySelector('[data-turn]')||[...occurrences.values()].some(occ=>occ.flow===activeFlow);
}
function updateOutline(){
  const outline=$('#flow-outline');outline.replaceChildren();
  for(const occ of occurrences.values())if(occ.flow===activeFlow){
    const button=node('button',occ.label||'Native material');
    button.onclick=()=>focusOccurrence(occ);outline.append(button);
  }
}
function updateContext(){
  const count=nativeSelection.size;
  $('#prompt-context').textContent=count ? 'Working with '+[...nativeSelection.values()].map(item=>item.label||friendly(item.subject.split('/').at(-1))).join(' + ') : 'New material or a change to this flow';
}
function focusOccurrence(occ){
  occ.el.scrollIntoView({block:'start',behavior:'smooth'});
  occ.el.classList.add('located');setTimeout(()=>occ.el.classList.remove('located'),900);selected=occ;
}
async function switchFlow(id){
  if(!anchors.some(a=>a.id===id))return;
  if(flowRestored)localStorage.setItem('shrine.flowDraft.'+activeFlow,$('#intent-text').value);
  scrollPositions.set(activeFlow,viewport.scrollTop);activeFlow=id;localStorage.setItem('shrine.activeFlow',id);
  $('#intent-text').value=localStorage.getItem('shrine.flowDraft.'+id)||'';selected=null;flowRestored=true;
  for(const occ of occurrences.values())if(occ.flow)occ.el.hidden=occ.flow!==id;
  restoring=true;
  try{for(const item of placements.filter(p=>p.flow===id))if(!occurrences.has(item.id))await open(item.subject,item.x,item.y,space,item.id);}
  finally{restoring=false;}
  nativeSelection.clear();$('#selected-paths').replaceChildren();updateContext();
  $('#flow-name').textContent=anchors.find(a=>a.id===id).label;
  for(const button of $('#flow-list').children)button.setAttribute('aria-current',button.textContent===anchors.find(a=>a.id===id).label?'page':'false');
  await showAgent();updateOutline();viewport.scrollTop=scrollPositions.get(id)||0;
  browse(anchors.find(a=>a.id===id).subject);
  if(innerWidth<=850)worldVisible(false);
}
async function openHere(subject,near=selected,focus=true){
  const existing=[...occurrences.values()].find(occ=>occ.flow===activeFlow&&occ.subject===subject);
  if(existing){if(focus)focusOccurrence(existing);return existing;}
  const occ=await open(subject);if(focus)focusOccurrence(occ);return occ;
}
function node(tag,text,className) {const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function selectNative(item,button) {
  const id=JSON.stringify([item.subject,item.slot||'',item.parameters||[]]);
  if(nativeSelection.has(id))nativeSelection.delete(id);else nativeSelection.set(id,item);
  if(button){button.dataset.selectionId=id;button.classList.toggle('chosen',nativeSelection.has(id));button.setAttribute('aria-pressed',String(nativeSelection.has(id)));}
  const bar=$('#selected-paths');bar.replaceChildren();
  highlightSelection();
  updateContext();
  if(!nativeSelection.size)return;
  for(const [key,focus] of nativeSelection){const chip=node('button',(focus.label||friendly(focus.subject.split('/').at(-1)))+(focus.slot&&!focus.artifact?' · '+friendly(focus.slot.replace(/^\//,'')):'')+' ×','selection-chip');chip.title=focus.subject+(focus.slot?' · '+focus.slot:'');chip.onclick=()=>{selectNative(focus);};bar.append(chip);}
}
function highlightSelection(){
  for(const occ of occurrences.values()){
    for(const el of occ.surface.querySelectorAll('[data-grove-key],[data-grove-row]')){
      const focus=occ.frame?.occurrences.find(item=>item.key===el.dataset.groveKey);
      const matches=[...nativeSelection.values()].some(item=>(focus?.focus.subject===item.subject&&(!item.slot||focus.slot===item.slot))||(!item.slot&&el.dataset.groveRow===item.subject));
      el.classList.toggle('world-selected',matches);
    }
  }
  for(const el of document.querySelectorAll('[data-selection-id]')){const yes=nativeSelection.has(el.dataset.selectionId);el.classList.toggle('chosen',yes);el.setAttribute('aria-pressed',String(yes));}
}
function worldVisible(visible){$('#explorer').hidden=!visible;document.body.classList.toggle('world-open',visible);$('#browse').setAttribute('aria-expanded',String(visible));}
worldVisible(innerWidth>850);
const undoHistory=[];
const status = text => $('#status').textContent = text;
const notify = text => { $('#notice').hidden = !text; $('#notice').textContent = text; };
async function call(operation, body, event = '') {
  const response = await fetch('/api/native', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,body,event})});
  const result = await response.json();
  if (!response.ok) throw Object.assign(new Error(result.error || `Native response ${response.status}`), {status:response.status});
  return result;
}
function base(occ) {return {subject:occ.subject,viewport:occ.viewport||[]};}
function keyOf(node) {return node.nodeType === 1 && (node.getAttribute('data-grove-key') || node.getAttribute('data-grove-row') || node.getAttribute('data-turn') || node.getAttribute('data-native-mount'));}
function hasDraft(node, occ) {
  return node.nodeType === 1 && [...node.querySelectorAll('[data-grove-key]'),node]
    .some(el => occ.drafts.has(el.getAttribute('data-grove-key')));
}
function patch(old, next, occ) {
  if (old.nodeType !== next.nodeType || old.nodeName !== next.nodeName) {
    if (hasDraft(old,occ)) {old.classList.add('draft-conflict');return old;}
    const replacement=next.cloneNode(true);old.replaceWith(replacement);return replacement;
  }
  if (old.nodeType !== 1) {if(old.nodeValue !== next.nodeValue) old.nodeValue = next.nodeValue; return;}
  if(old.hasAttribute('data-native-mount')&&old.getAttribute('data-native-mount')===next.getAttribute('data-native-mount'))return old;
  const key = old.getAttribute('data-grove-key');
  const protectedDraft = key && occ.drafts.has(key);
  // Disclosure state belongs to the user's current occurrence. Unchanged
  // native frames must not close a document while the user is reading it.
  const localDisclosure = old instanceof HTMLDetailsElement;
  for (const attr of [...old.attributes]) if (!next.hasAttribute(attr.name) && !['class'].includes(attr.name) && !(localDisclosure && attr.name === 'open')) old.removeAttribute(attr.name);
  for (const attr of next.attributes) if (old.getAttribute(attr.name) !== attr.value && !(protectedDraft && attr.name === 'value') && !(localDisclosure && attr.name === 'open')) old.setAttribute(attr.name, attr.value);
  if (old instanceof HTMLInputElement || old instanceof HTMLTextAreaElement) {
    if (!protectedDraft && document.activeElement !== old && old.value !== next.value) old.value = next.value;
    return;
  }
  const keyed = new Map([...old.childNodes].filter(keyOf).map(node => [keyOf(node), node]));
  let position = old.firstChild;
  for (const child of next.childNodes) {
    const key = keyOf(child);
    let current = key ? keyed.get(key) : (position && !keyOf(position) ? position : null);
    if (!current) {current = child.cloneNode(true);old.insertBefore(current, position);}
    else {if(current !== position) old.insertBefore(current, position);current=patch(current, child, occ) || current;}
    position = current.nextSibling;
  }
  while(position) {
    const nextPosition = position.nextSibling;
    // An unresolved draft retains its original element and key. It cannot be
    // retargeted to a newly occupying row by a refresh.
    if (hasDraft(position,occ)) {
      position.classList.add('draft-conflict');
    } else position.remove();
    position = nextPosition;
  }
}
function nativeLocation(value) {
  try {
    const url=new URL(value,location.href), keys=[...url.searchParams.keys()];
    return url.origin===location.origin && url.pathname==='/' && !url.hash &&
      keys.length===1 && ['subject','inspect'].includes(keys[0]) && url.searchParams.get(keys[0]).startsWith('/');
  } catch {return false;}
}
function render(occ, frame) {
  const template = document.createElement('template');template.innerHTML = frame.html;
  // Scripts and browser-dispatched effects cannot cross the rendering boundary.
  for (const node of template.content.querySelectorAll('script,iframe,object,embed,link,meta,base')) node.remove();
  for (const node of template.content.querySelectorAll('*')) for (const attr of [...node.attributes]) {
    const localLink=node.tagName==='A' && attr.name==='href' && nativeLocation(attr.value);
    const inlineImage=node.tagName==='IMG' && attr.name==='src' && attr.value.length<=700000 && /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]*={0,2}$/.test(attr.value);
    if (/^on/i.test(attr.name) || ['srcdoc','formaction','action'].includes(attr.name) || (/^(href|src)$/i.test(attr.name) && !attr.value.startsWith('#') && !localLink && !inlineImage)) node.removeAttribute(attr.name);
  }
  const next = document.createElement('div');next.className = 'surface';next.append(template.content);
  patch(occ.surface,next,occ);occ.frame=frame;
  const title=occ.surface.querySelector('h1,h2')?.textContent?.trim();
  if(title&&title!==occ.label){occ.label=title;occ.el.querySelector('.occurrence-name').textContent=title;updateOutline();}
  occ.el.querySelector('.surface-status').hidden=true;
  reconcileMounts(occ).catch(error=>notify(error.message));
  if(occ===authorOccurrence){
    const list=$('#created-material');list.replaceChildren();
    const seen=new Set();
    for(const link of occ.surface.querySelectorAll('[data-native-material]')){
      const ref=link.dataset.nativeMaterial;if(seen.has(ref))continue;seen.add(ref);
      const button=node('button',link.textContent,'material-link');button.title=ref;
      button.onclick=()=>{worldVisible(true);browse(ref);};list.append(button);
    }
    const latest=[...seen].at(-1);
    if(latest&&occ.lastMaterial!==latest){occ.lastMaterial=latest;browse(latest);}
    updateEmpty();
  }
  for(const canvas of occ.surface.querySelectorAll('canvas[data-grove-raster]')) {
    const signature=`${canvas.width}:${canvas.height}:${canvas.dataset.groveRaster}`;
    if(canvas.renderedRaster===signature)continue;
    try {
      if(canvas.width*canvas.height>1048576)throw new Error('Raster tile exceeds the physical rendering bound.');
      const samples=JSON.parse(canvas.dataset.groveRaster);
      if(!Array.isArray(samples)||samples.length!==canvas.width*canvas.height||samples.some(v=>!Number.isInteger(v)||v<0||v>0xffffff))throw new Error('Invalid native RGB tile.');
      const bytes=new Uint8ClampedArray(samples.length*4);
      samples.forEach((value,i)=>{bytes[4*i]=value>>>16;bytes[4*i+1]=(value>>>8)&255;bytes[4*i+2]=value&255;bytes[4*i+3]=255;});
      canvas.getContext('2d').putImageData(new ImageData(bytes,canvas.width,canvas.height),0,0);
      canvas.renderedRaster=signature;
    }catch(error){notify(error.message);}
  }
}
// Nested native presentations use the same renderer/actions, with independent
// captured bases. The host does not interpret the application or merge its data.
async function reconcileMounts(parent){
  if(parent.mounting)return;parent.mounting=true;
  try{
    for(const child of [...occurrences.values()])if(child.parent===parent&&!child.el.isConnected){dropOccurrence(child);}
    const mounts=[...parent.surface.querySelectorAll('[data-native-mount]')].filter(el=>!el.closest('[data-native-preview]')&&(!el.parentElement.closest('[data-native-mount]')||!parent.surface.contains(el.parentElement.closest('[data-native-mount]'))));
    for(const mount of mounts.slice(0,20)){
      if([...occurrences.values()].some(occ=>occ.parent===parent&&occ.el.parentElement===mount))continue;
      const ref=mount.dataset.nativeMount;let ancestor=parent,depth=0,cycle=false;
      while(ancestor){depth++;if(ancestor.subject===ref)cycle=true;ancestor=ancestor.parent;}
      if(cycle||depth>=4){mount.textContent='Open this reference separately to continue.';continue;}
      const child=await open(ref,0,0,mount,null,parent);child.el.classList.add('embedded-occurrence');
    }
  }finally{parent.mounting=false;}
}
function dropOccurrence(occ){for(const child of [...occurrences.values()])if(child.parent===occ)dropOccurrence(child);occurrences.delete(occ.id);occ.el.remove();}
function pointAt(field,event) {
  const bounds=field.getBoundingClientRect();
  return {x:Math.floor((event.clientX-bounds.left)*field.width/bounds.width),y:Math.floor((event.clientY-bounds.top)*field.height/bounds.height)};
}
function positionParameters(field,point) {
  if(!(field instanceof HTMLCanvasElement))return [];
  return Object.entries({...point,width:field.width,height:field.height}).map(([name,value])=>({slot:`/${name}`,kind:'natural',value:String(value)}));
}
async function refresh(occ) {
  if (occ.reading || occ.saving || document.hidden || occ.el.hidden || !occ.el.isConnected || occ.el.closest('[hidden]')) return;
  occ.reading = true;
  try { const frame = await call('native/frame',base(occ));render(occ,frame);highlightSelection();status('Connected'); }
  catch (error) {
    const message=occ.el.querySelector('.surface-status');message.hidden=false;
    message.firstChild.textContent=occ.frame ? 'This view could not refresh. The last result is still shown.' : 'This material does not have a working presentation yet.';
    message.querySelector('code').textContent=error.message;
  }
  finally {occ.reading=false;}
}
async function open(subject, x=0, y=0, container=space, identity=null,parent=null) {
  const el = document.createElement('section');el.className='occurrence';
  el.innerHTML='<header class="occurrence-tools"><span class="occurrence-name">Native material</span><button class="use-occurrence">Work with this</button><button class="inspect-occurrence" aria-label="Inspect this material">↗</button><button class="close-occurrence" aria-label="Close this view">×</button></header><div class="surface-status" hidden><p></p><details><summary>Native diagnostic</summary><code></code></details></div><div class="surface"></div>';
  const occ={id:identity||crypto.randomUUID(),flow:container===space?activeFlow:null,subject,parent,label:friendly(subject.split('/').at(-1)),el,surface:el.querySelector('.surface'),frame:null,drafts:new Map(),x,y};
  el.querySelector('.occurrence-name').textContent=occ.label;
  occurrences.set(occ.id,occ);container.append(el);if(container!==space)el.classList.add("docked-occurrence");
  el.querySelector('.close-occurrence').onclick=async()=>{if(occ.drafts.size){notify('Finish or cancel the draft before closing this view.');return;}try{if(occ.flow)await arrangementAction('/remove',{id:occ.id,flow:occ.flow});occurrences.delete(occ.id);el.remove();if(selected===occ)selected=null;updateEmpty();updateOutline();}catch(error){notify(error.message);}};
  el.querySelector('.use-occurrence').onclick=async()=>{nativeSelection.clear();selectNative({subject:occ.subject,label:occ.label,care:'x'});selected=occ;await showAgent();$('#intent-text').focus();};
  el.querySelector('.inspect-occurrence').onclick=()=>{worldVisible(true);$('#world-browser').open=true;browse(occ.subject);};
  el.addEventListener('pointerdown',()=>{if(occ.flow||occ.parent)selected=occ;});
  el.addEventListener('focusin',()=>{if(occ.flow||occ.parent)selected=occ;});
  const element = event => {const field=event.target.closest('[data-grove-key]');return field&&!field.closest('[data-native-preview]')&&field.closest('.occurrence')===el?field:null;};
  el.addEventListener('pointerdown',event=>{
    const field=element(event);
    if(!field?.dataset.grovePointer || inspecting || !occ.frame)return;
    event.preventDefault();field.focus();field.setPointerCapture(event.pointerId);
    const first=pointAt(field,event), points=[first], basis=occ.frame.basis;
    field.physicalPosition=first;field.classList.add('input-capture');
    const move=e=>{
      const point=pointAt(field,e);field.physicalPosition=point;
      if(point.x<0||point.y<0||point.x>=field.width||point.y>=field.height)return;
      const last=points[points.length-1];if(point.x===last.x&&point.y===last.y)return;
      if(points.length<64)points.push(point);else points[63]=point;
    };
    const finish=e=>{
      field.removeEventListener('pointermove',move);field.removeEventListener('pointerup',finish);field.removeEventListener('pointercancel',cancel);field.classList.remove('input-capture');
      if(field.hasPointerCapture(event.pointerId))field.releasePointerCapture(event.pointerId);
      if(e.type==='pointercancel')return;
      move(e);
      const key=field.dataset.groveKey,old=occ.drafts.get(key);
      occ.drafts.set(key,{basis,revision:(old?.revision||0)+1,parameters:positionParameters(field,first),arguments:[{slot:'/points',kind:'points',value:points.map(p=>({x:String(p.x),y:String(p.y)}))}]});
      save(occ,field);
    };
    const cancel=e=>finish(e);
    field.addEventListener('pointermove',move);field.addEventListener('pointerup',finish);field.addEventListener('pointercancel',cancel);
  });
  el.addEventListener('input',event=>{
    const field=element(event);if (!field || !occ.frame) return;
    const key=field.dataset.groveKey, old=occ.drafts.get(key);
    occ.drafts.set(key,{basis:old?.basis || occ.frame.basis,value:field.value,revision:(old?.revision || 0)+1});
  });
  el.addEventListener('compositionstart',()=>occ.composing=true);
  el.addEventListener('compositionend',()=>occ.composing=false);
  el.addEventListener('change',event=>{
    const field=element(event);if(field?.dataset.groveEdit && !occ.composing) save(occ,field);
  });
  el.addEventListener('keydown',event=>{
    const field=element(event);
    if(event.key==='Enter' && field instanceof HTMLInputElement && !event.isComposing && !occ.composing) {
      event.preventDefault();save(occ,field);
    }
    if(event.key==='Escape' && field) {occ.drafts.delete(field.dataset.groveKey);field.classList.remove('draft-conflict');field.blur();refresh(occ);}
  });
  el.addEventListener('click',event=>{
    if(event.target.closest('.occurrence')!==el||event.target.closest('[data-native-preview]'))return;
    const page=event.target.closest('[data-native-viewport-slot]');
    if(page && !(inspecting || event.altKey)){event.preventDefault();occ.viewport=(occ.viewport||[]).filter(item=>item.slot!==page.dataset.nativeViewportSlot);occ.viewport.push({slot:page.dataset.nativeViewportSlot,kind:page.dataset.nativeViewportKind,value:page.dataset.nativeViewportValue});refresh(occ);return;}
    const link=event.target.closest('a[href]');
    if(link&&!event.metaKey&&!event.ctrlKey&&!event.altKey){
      const destination=new URL(link.href,location.href);
      if(destination.origin===location.origin){
        const ref=destination.searchParams.get('subject'),at=destination.searchParams.get('inspect');
        if(ref||at){event.preventDefault();
          if(at){worldVisible(true);browse(at);}
          else {
            openHere(ref,occ.flow?occ:selected);
          }return;
        }
      }
    }
    const field=element(event);if(!field)return;
    if(inspecting || event.altKey){event.preventDefault();inspect(occ,field);return;}
    if(field.dataset.groveAct)save(occ,field);
  });
  el.addEventListener('pointermove',event=>{
    const field=element(event);if(!(inspecting || event.altKey) || !field)return;
    hovered?.classList.remove('native-inspected');hovered=field;field.classList.add('native-inspected');
    if(field instanceof HTMLCanvasElement)field.physicalPosition=pointAt(field,event);
    inspect(occ,field);
  });
  if(occ.flow&&!restoring)await arrangementAction('/place',{id:occ.id,flow:occ.flow,subject:occ.subject,x:Math.max(0,Math.round(x)),y:Math.max(0,Math.round(y))});
  await refresh(occ);updateEmpty();updateOutline();return occ;
}
async function save(occ,field) {
  if(!occ.frame)return;
  if(field.dataset.groveEdit && !occ.drafts.has(field.dataset.groveKey))return;
  if(occ.saving){(occ.pending ||= new Set()).add(field);return;}
  const key=field.dataset.groveKey,draft=occ.drafts.get(key),revision=draft?.revision;
  const args=draft?.arguments || (field.dataset.argumentSlot ? [{slot:field.dataset.argumentSlot,kind:field.dataset.argumentKind || 'text',value:field.value}] : []);
  const parameters=draft?.parameters || [];
  occ.saving=true;status('Applying native action');
  const started=performance.now();
  try {
    const event=crypto.randomUUID();
    await call('native/act',{...base(occ),basis:draft?.basis || occ.frame.basis,key,parameters,arguments:args},event);
    undoHistory.push({occ,key,parameters,event});
    if(occ.drafts.get(key)?.revision===revision)occ.drafts.delete(key);
    field.classList.remove('draft-conflict');notify('');status(`Native acknowledgement · ${Math.round(performance.now()-started)} ms`);
  } catch(error) {field.classList.add('draft-conflict');notify(error.message);}
  finally {
    occ.saving=false;
    const pending=occ.pending?.values().next().value;
    if(pending){occ.pending.delete(pending);save(occ,pending);}
    else for(const view of occurrences.values())refresh(view);
  }
}
let inspectionToken=0, lastInspection='';
async function inspect(occ,field) {
  if(!occ.frame)return;
  const parameters=positionParameters(field,field.physicalPosition || {x:0,y:0});
  const key=field.dataset.groveKey, signature=JSON.stringify([occ.id,key,parameters,occ.frame.basis]);
  if(signature===lastInspection)return;lastInspection=signature;const token=++inspectionToken;
  $('#inspection').hidden=false;$('#selection-title').textContent='Resolving this selection…';
  $('#selection-summary').replaceChildren();
  $('#selection-detail').textContent='Waiting for the native correspondence on the displayed basis.';
  try {
    const result=await call('native/inspect',{...base(occ),basis:occ.frame.basis,key,parameters});
    if(token!==inspectionToken)return;
    $('#selection-title').textContent=result.occurrence.description;
    $('#selection-detail').textContent=JSON.stringify(result,null,2);
    const item=result.occurrence, summary=$('#selection-summary');summary.replaceChildren();
    for(const [label,value] of [['Subject',item.focus.subject],['Field',item.slot],['Basis','Case '+item.focus.case+' · care '+item.focus.care],['Action',item.action||'Read only'],['Implementation',result.basis.implementation.subject]]){
      const line=node('div',undefined,'inspection-line');line.append(node('small',label),node('code',value));summary.append(line);
    }
    const pick=node('button','Use this selection');pick.onclick=()=>selectNative({subject:item.focus.subject,slot:item.slot,care:item.focus.care,case:item.focus.case,parameters,surface:occ.subject,key:item.key},pick);summary.append(pick);
  }catch(error){if(token===inspectionToken){
    lastInspection=null;
    $('#selection-title').textContent='This selection needs a refresh';
    $('#selection-detail').textContent=error.message;
    const summary=$('#selection-summary');
    summary.replaceChildren(node('p',error.message));
    const retry=node('button','Refresh and inspect');
    retry.onclick=async()=>{
      retry.disabled=true;
      await refresh(occ);
      if(field.isConnected)await inspect(occ,field);
      else summary.replaceChildren(node('p','The presentation changed. Inspect the element again to select its current binding.'));
    };
    summary.append(retry);
  }}
}
async function browse(subject,cursor,epoch,slotCursor) {
  browseSubject=subject;$('#address').value=subject;
  try {
    const page=await call('native/discover',{subject,...(cursor?{cursor}:{}),...(slotCursor?{slot_cursor:slotCursor}:{}),...(epoch?{epoch}:{})});
    const lede=page.slots.find(s=>s.slot==='/sys/lede')?.value;
    const label=(lede&&lede!=='Grove installation.'?lede:null)||friendly(subject.split('/').at(-1))||'World';
    $('#world-location').replaceChildren(node('strong',label));$('#world-location').title=subject;
    const list=$('#listing');list.replaceChildren();
    const select=node('button','Select this location','select-location');select.onclick=()=>selectNative({subject,label,care:'x',observed_epoch:page.epoch},select);list.append(select);
    if(page.slots.some(slot=>slot.slot==='/sys/goo/surface')){
      const button=node('button','Bring into this flow ↗','open-surface');button.onclick=async()=>{await openHere(subject);if(innerWidth<=850)worldVisible(false);};list.append(button);
    }
    if(page.children.length)list.append(node('h3','Inside'));
    for(const entry of page.children){
      const row=node('div',undefined,'world-item'), name=(entry.label&&entry.label!=='Grove installation.'?entry.label:null)||friendly(entry.subject.split('/').at(-1));
      const pick=node('button','○','pick-reference');pick.setAttribute('aria-label','Select '+name);pick.onclick=()=>selectNative({subject:entry.subject,label:name,care:'x',observed_epoch:page.epoch},pick);
      const button=node('button',name+' ›','world-child');button.title=entry.subject;button.onclick=event=>{if(!event.shiftKey&&!event.metaKey&&!event.ctrlKey)nativeSelection.clear();selectNative({subject:entry.subject,label:name,care:'x',observed_epoch:page.epoch});browse(entry.subject);};row.append(pick,button);list.append(row);
    }
    const technical=node('details',undefined,'technical-fields');technical.append(node('summary','Native definitions & metadata'));
    // These are the native Grove installation envelope, not user fields. Keep
    // them available in the existing inspection disclosure. Ordinary records
    // with fields named status/module are unaffected.
    const installation=page.slots.some(slot=>slot.slot.endsWith('/publisher_vocabulary/grove/source'));
    const envelope=new Set(['/module','/pact','/status','/grants/fetch','/grants/serve','/wants/fetch','/wants/serve']);
    const technicalSlot=slot=>slot.slot.startsWith('/sys/')||slot.slot.startsWith('/0x')||(installation&&envelope.has(slot.slot));
    const fields=page.slots.filter(slot=>!technicalSlot(slot));
    if(fields.length)list.append(node('h3','Fields'));
    for(const slot of page.slots){
      if(slot.slot==='/sys/lede')continue;
      const button=node('button',undefined,'world-field');button.title=subject+' · '+slot.slot;
      const display=node('small',slot.kind==='reference'?friendly(slot.value.split('/').at(-1))+' ↗':slot.kind==='native'?'Native value':String(slot.value??'Unknown'));
      button.append(node('span',friendly(slot.slot.replace(/^\//,'').replaceAll('/',' · '))),display,node('em',slot.kind));
      if(slot.kind==='reference')call('native/discover',{subject:slot.value}).then(target=>{
        if(!display.isConnected)return;
        const name=target.slots.find(field=>field.slot==='/sys/lede')?.value;
        if(name&&name!=='Grove installation.')display.textContent=name+' ↗';
      }).catch(()=>{display.textContent+=' · unavailable';});
      button.onclick=()=>selectNative({subject,label,slot:slot.slot,kind:slot.kind,care:'x',observed_epoch:page.epoch},button);
      (technicalSlot(slot)?technical:list).append(button);
    }
    if(technical.children.length>1)list.append(technical);
    if(page.next){const button=node('button','More items…');button.onclick=()=>browse(subject,page.next,page.epoch);list.append(button);}
    if(page.next_slots){const button=node('button','More fields…');button.onclick=()=>browse(subject,undefined,page.epoch,page.next_slots);list.append(button);}
  }catch(error){notify(error.message);}
}
$('#browse').onclick=()=>worldVisible($('#explorer').hidden);
$('#world-up').onclick=()=>browse(browseSubject.split('/').slice(0,-1).join('/')||'/');
for(const button of document.querySelectorAll('[data-root]'))button.onclick=()=>browse(button.dataset.root);
$('#locate').onsubmit=event=>{event.preventDefault();browse($('#address').value);};
$('#close-inspection').onclick=()=>{$('#inspection').hidden=true;lastInspection='';inspecting=false;hovered?.classList.remove('native-inspected');++inspectionToken;};
document.addEventListener('keydown',event=>{
  if(event.key==='Alt'){inspecting=true;const field=document.activeElement?.closest('[data-grove-key]');if(field&&selected)inspect(selected,field);}
  if((event.metaKey||event.ctrlKey)&&event.key==='d'&&selected&&!event.target.matches('input,textarea')){event.preventDefault();open(selected.subject,selected.x+50,selected.y+80);}
  if((event.metaKey||event.ctrlKey)&&event.key==='z'&&!event.shiftKey&&!event.target.matches('input,textarea,[contenteditable]')) {
    const change=undoHistory.at(-1);if(!change)return;
    event.preventDefault();undo(change);
  }
});
async function undo(change) {
  const {occ,key,parameters,event}=change;
  if(occ.saving)return;
  await refresh(occ);occ.saving=true;
  try {
    await call('native/undo',{...base(occ),basis:occ.frame.basis,key,parameters,arguments:[],prior:event},crypto.randomUUID());
    undoHistory.pop();notify('');
  }catch(error){notify(error.message);}
  finally{occ.saving=false;for(const view of occurrences.values())refresh(view);}
}
document.addEventListener('keyup',event=>{if(event.key==='Alt'){inspecting=false;hovered?.classList.remove('native-inspected');}});
window.addEventListener('blur',()=>{inspecting=false;hovered?.classList.remove('native-inspected');});
// Bootstrap compiler controls. Source/definitions/templates remain native;
// the browser forwards text and exact references to the existing compiler.
let sourceBasis=null, sourceTarget=null;
$('#author').onclick=()=>{$('#source-panel').hidden=!$('#source-panel').hidden;};
$('#close-source').onclick=()=>{$('#source-panel').hidden=true;};
$('#read-source').onclick=async()=>{
  try {const subject=$('#source-ref').value;const result=await call('native/source',{subject});
    sourceBasis=result.basis;sourceTarget=subject;$('#source-text').value=result.source;$('#source-status').textContent='Native source opened';
  }catch(error){notify(error.message);}
};
$('#compile-source').onclick=async()=>{
  const subject=$('#source-ref').value, source=$('#source-text').value;
  $('#compile-source').disabled=true;$('#source-status').textContent='Native compilation…';
  try {
    if(sourceTarget!==subject){const current=await call('native/source',{subject});
      if(current.basis.epoch!==null)throw new Error('Open the existing source before editing its definition. Your draft is retained.');
      sourceTarget=subject;sourceBasis=current.basis;}
    sourceBasis=await call('native/author',{subject,source,expected:sourceBasis.epoch || ''},crypto.randomUUID());
    $('#source-status').textContent='Compiled · native definitions retained';notify('');
  }catch(error){$('#source-status').textContent='Source retained · compilation not installed';notify(error.message);}
  finally{$('#compile-source').disabled=false;}
};
$('#instantiate-source').onclick=async()=>{
  try {if(!sourceBasis?.case||sourceTarget!==$('#source-ref').value)throw new Error('Compile or open the selected native definition first.');
    const subject=$('#instance-ref').value;
    await call('native/instantiate',{subject,source:sourceTarget,version:sourceBasis.case,expected:''},crypto.randomUUID());
    await browse(subject);$('#source-status').textContent='Native material established';$('#source-panel').hidden=true;notify('');
  }catch(error){notify(error.message);}
};
await fetch('/connect',{method:'POST'});
async function refreshAgent() {
  if(document.hidden)return;
  try {
    const response=await fetch('/api/agent');
    if(!response.ok)throw new Error('The Canvas model connection is unavailable.');
    agentHealth=await response.json();
    const ready=agentHealth.running && ['ready','working'].includes(agentHealth.state);
    $('#agent').textContent=ready ? (agentHealth.state==='working'?'AI · working':'AI · ready') : 'AI · offline';
    $('#agent').dataset.connected=String(ready);
    const route=agentHealth.routing?.author;
    $('#agent').title=(agentHealth.message || 'Open the native OpenRouter author')+(route?` Authoring: ${route.model} · ${route.reasoning} reasoning.`:'');
  } catch(error) {
    agentHealth={state:'unavailable',message:error.message};
    $('#agent').textContent='AI · offline';$('#agent').dataset.connected='false';$('#agent').title=error.message;
  }
}
async function showAgent() {
  updateContext();
  if(!authorOccurrence)authorOccurrence=await open('/0x11/app/user/author/surface',0,0,$('#request-thread'));
  if(authorOccurrence.viewport?.find(item=>item.slot==='/flow')?.value!==activeFlow)authorOccurrence.viewport=[{slot:'/flow',kind:'text',value:activeFlow}];
  await refresh(authorOccurrence);
  return authorOccurrence;
}
$('#agent').onclick=async()=>{
  await refreshAgent();
  if(!agentHealth?.running || !['ready','working'].includes(agentHealth.state))notify(agentHealth?.message || 'The native author is unavailable.');
  $('#activity-toggle').click();
};
$('#start-here').onclick=async()=>{await showAgent();$('#intent-text').focus();};
$('#choose-material').onclick=()=>worldVisible(true);
let fileSurface=null;
async function fileInputReference(){
  const home=await call('native/discover',{subject:'/0x11/app/user/personal/home'});
  const binding=home.slots.find(field=>field.slot==='/files'&&field.kind==='reference');
  if(!binding)throw new Error('Choose a native file input for this workspace.');
  fileSurface=binding.value;return fileSurface;
}
async function attachFiles(files){
  try{await fileInputReference();}catch(error){notify(error.message);return;}
  for(const file of files){
    if(file.size>524288){notify(file.name+' is larger than the current 512 KiB attachment bound. No bytes were imported.');continue;}
    try{
      const bytes=new Uint8Array(await file.arrayBuffer());
      let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
      let text='',decoded='no';
      if(bytes.length<=32768){try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(!text.includes('\u0000'))decoded='yes';else text='';}catch{}}
      const values={id:crypto.randomUUID(),name:file.name,media:file.type||'application/octet-stream',digest,size:file.size,bytes:btoa(binary),text,decoded};
      const frame=await call('native/frame',{subject:fileSurface,viewport:[]});
      const args=Object.entries(values).map(([name,value])=>({slot:'/'+name,kind:typeof value==='number'?'natural':'text',value:String(value)}));
      await call('native/act',{subject:fileSurface,viewport:[],basis:frame.basis,key:'/attach',parameters:[],arguments:args},crypto.randomUUID());
      selectNative({subject:'/0x11/app/user/files/originals',slot:'/originals',artifact:values.id,label:file.name,care:'x',surface:fileSurface,viewport:[{slot:'/artifact',kind:'text',value:values.id}]});
      notify('Attached '+file.name+'. Describe what it means or what you want to use from it.');
    }catch(error){notify(file.name+': '+error.message);}
  }
}
$('#attach-file').onclick=()=>$('#file-input').click();
$('#file-input').onchange=event=>{attachFiles([...event.target.files]);event.target.value='';};
viewport.addEventListener('dragover',event=>{if(event.dataTransfer.types.includes('Files')){event.preventDefault();viewport.classList.add('file-drop');}});
viewport.addEventListener('dragleave',event=>{if(!viewport.contains(event.relatedTarget))viewport.classList.remove('file-drop');});
viewport.addEventListener('drop',event=>{if(!event.dataTransfer.files.length)return;event.preventDefault();viewport.classList.remove('file-drop');attachFiles([...event.dataTransfer.files]);});
$('#anchor-home').onclick=()=>viewport.scrollTo({top:0,behavior:'smooth'});
$('#create-flow').onsubmit=async event=>{
  event.preventDefault();const label=$('#flow-label').value.trim();if(!label)return;
  try{const id=crypto.randomUUID();const anchor=[...nativeSelection.values()][0]?.subject||'/0x11/app/user';
    await arrangementAction('/new',{id,label,subject:anchor});$('#flow-label').value='';$('#new-flow').open=false;await switchFlow(id);
  }catch(error){notify(error.message);}
};
$('#activity-toggle').onclick=async()=>{
  const panel=$('#agent-journal');panel.hidden=!panel.hidden;$('#activity-toggle').setAttribute('aria-expanded',String(!panel.hidden));
  if(!panel.hidden){if(!journalOccurrence)journalOccurrence=await open('/0x11/app/user/author_activity/surface',0,0,$('#journal-surface'));else await refresh(journalOccurrence);}
};
$('#close-journal').onclick=()=>{$('#agent-journal').hidden=true;$('#activity-toggle').setAttribute('aria-expanded','false');};
async function localPrompt(event){
  if(event.target.closest('[data-native-preview]'))return;
  const control=event.target.closest('[data-grove-key]');
  const occurrence=[...occurrences.values()].find(occ=>occ.el===event.target.closest('.occurrence'));
  if(control&&occurrence?.frame){
    try{
      const parameters=positionParameters(control,control.physicalPosition||{x:0,y:0});
      const result=await call('native/inspect',{...base(occurrence),basis:occurrence.frame.basis,key:control.dataset.groveKey,parameters});
      const item=result.occurrence,focus={subject:item.focus.subject,slot:item.slot,case:item.focus.case,care:item.focus.care,surface:occurrence.subject,key:item.key,parameters};
      if(!event.shiftKey)nativeSelection.clear();selectNative(focus);
    }catch(error){notify(error.message);return;}
  }else if(occurrence&&!nativeSelection.size){selectNative({subject:occurrence.subject,care:'x'});}
  await showAgent();$('#intent-text').focus();
}
viewport.addEventListener('contextmenu',event=>{if(event.target.closest('input,textarea,[contenteditable]'))return;event.preventDefault();localPrompt(event);});
$('#listing').addEventListener('contextmenu',event=>{event.preventDefault();localPrompt(event);});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&event.target===$('#intent-text')){event.target.blur();return;}
  if(event.code==='Space'&&!event.target.closest('input,textarea,button,a,[contenteditable]')){event.preventDefault();localPrompt(event);}
  if((event.metaKey||event.ctrlKey)&&event.key==='k'){event.preventDefault();worldVisible(true);$('#world-browser').open=true;$('#address').closest('details').open=true;$('#address').focus();$('#address').select();}
});
$('#intent-text').addEventListener('input',()=>localStorage.setItem('shrine.flowDraft.'+activeFlow,$('#intent-text').value));
$('#intent-text').addEventListener('keydown',event=>{
  if(event.key==='Enter'&&(event.metaKey||event.ctrlKey)&&!event.isComposing){event.preventDefault();$('#intent').requestSubmit();}
});
$('#intent').onsubmit=async event=>{
  event.preventDefault();const field=$('#intent-text'),draft=field.value;if(!draft.trim())return;
  $('#send-intent').disabled=true;
  try {
    const surface=await showAgent();
    surface.viewport=surface.viewport.filter(item=>item.slot!=='/offset');
    const writer={subject:'/0x11/app/user/author/surface',viewport:[]};
    const frame=await call('native/frame',writer);
    const selection=nativeSelection.size?[...nativeSelection.values()]:(selected?[{subject:selected.subject,label:selected.label,care:'x'}]:[]);
    const context={anchor:anchors.find(a=>a.id===activeFlow),selection,surrounding_subjects:placements.filter(p=>p.flow===activeFlow).map(p=>p.subject),previous_material:[...surface.surface.querySelectorAll('[data-native-material]')].at(-1)?.dataset.nativeMaterial||'',previous_reply:[...surface.surface.querySelectorAll('[data-native-reply]')].at(-1)?.textContent||''};
    const value=draft+'\n\nCurrent native context (not additional authority):\n'+JSON.stringify(context);
    // Ignore the previous request's result until a different result arrives.
    // The native work record can retain that result while the next request starts.
    requestFlow={id:activeFlow,origin:selected?.flow===activeFlow?selected.id:null,lastResult:surface.surface.querySelector('[data-canvas-result]')?.dataset.canvasResult||''};
    await call('native/act',{...writer,basis:frame.basis,key:'/request',parameters:[],arguments:[{slot:'/value',kind:'text',value},{slot:'/prompt',kind:'text',value:draft},{slot:'/flow',kind:'text',value:activeFlow}]},crypto.randomUUID());
    if(field.value===draft){field.value='';localStorage.removeItem('shrine.flowDraft.'+activeFlow);}
    viewport.scrollTo({top:viewport.scrollHeight,behavior:'smooth'});
    notify('');await refresh(surface);await refreshAgent();
  }catch(error){notify(error.message);}finally{$('#send-intent').disabled=false;}
};
refreshAgent();
setInterval(refreshAgent,5000);
// A reference is the entry point, never a host-side application type.
const entry=new URL(location.href).searchParams, reference=entry.get('subject'), inspection=entry.get('inspect');
try{await readArrangement();await switchFlow(localStorage.getItem('shrine.activeFlow')||'home');
  await open('/0x11/app/user/personal_navigation/surface',0,0,$('#personal-navigation'));
  if(inspection){worldVisible(true);$('#world-browser').open=true;await browse(inspection);}
  else if(reference)await openHere(reference);
}catch(error){notify('Could not restore this arrangement: '+error.message);await browse('/0x11/app/user');}
// File readiness is independent of restoring the flow. An unavailable native
// file presentation must not make the workspace look disconnected.
try{await fileInputReference();await call('native/frame',{subject:fileSurface,viewport:[]});$('#attach-file').disabled=false;$('#attach-file').title='Retain an original file in your world';}
catch(error){$('#attachment-status').textContent='File input needs repair';$('#attach-file').title=error.message;}
setInterval(()=>{for(const occ of occurrences.values())refresh(occ);},1200);
