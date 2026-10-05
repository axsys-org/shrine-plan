// Physical drafts, keyed rendering and native transport. No application evaluator.
const $=s=>document.querySelector(s),sheet=$('#sheet'),viewport=$('#viewport');
const storage='grove.workshop.drafts.v1',freshTab=()=>({id:crypto.randomUUID(),name:'Untitled',regions:[],scroll:0});
let saved;try{saved=JSON.parse(localStorage.getItem(storage));}catch{}
let tabs=saved?.tabs?.length?saved.tabs:[freshTab()],active=saved?.active||tabs[0].id;
let tool='select',selected=null,gesture=null,composing=false,delayMs=0,persistTimer;
const undo=[],surfaces=new Map(),samples={local:[],native:[],roundTrip:[],frames:[]},journal=[];
const tab=()=>tabs.find(t=>t.id===active)||tabs[0];
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const percentile=(values,p)=>values.length?[...values].sort((a,b)=>a-b)[Math.ceil(values.length*p)-1]:null;
function log(lane,message,data){
  journal.push({at:performance.now(),lane,message,data});
  const item=el('li');item.dataset.lane=lane;item.append(el('span',lane,'lane'),el('span',message));
  $('#events').prepend(item);while($('#events').children.length>80)$('#events').lastChild.remove();
}
function measure(event){
  const origin=event.timeStamp>1e12?event.timeStamp-performance.timeOrigin:event.timeStamp;
  requestAnimationFrame(()=>samples.local.push({kind:event.type,ms:performance.now()-origin,at:performance.now()}));
}
let previousFrame=performance.now();
function frame(now){samples.frames.push(now-previousFrame);previousFrame=now;if(samples.frames.length>18000)samples.frames.shift();requestAnimationFrame(frame);}
requestAnimationFrame(frame);
setInterval(()=>{const l=percentile(samples.local.map(s=>s.ms),.95),n=percentile(samples.native.map(s=>s.ms),.95);$('#local-p95').textContent=l===null?'—':l.toFixed(1)+' ms';$('#native-p95').textContent=n===null?'—':n.toFixed(1)+' ms';},500);
function persist(){clearTimeout(persistTimer);persistTimer=setTimeout(()=>{tab().scroll=viewport.scrollTop;try{localStorage.setItem(storage,JSON.stringify({tabs,active}));$('#draft-state').textContent='Draft saved on this browser';}catch{log('error','Local draft storage is full; export before closing.');}},120);}
function snapshot(){undo.push(JSON.stringify({tabs,active}));if(undo.length>40)undo.shift();}
function outline(){
  $('#outline').replaceChildren();
  for(const r of tab().regions){const b=el('button',r.text||'Region');b.onclick=()=>{choose(r.id);sheet.querySelector('[data-region="'+r.id+'"]')?.scrollIntoView({block:'nearest'});};$('#outline').append(b);}
  $('#empty').hidden=tab().regions.length>0||surfaces.size>0;
}
function position(node,r){Object.assign(node.style,{left:r.x+'px',top:r.y+'px',width:r.w+'px',height:r.h+'px'});}
function drawRegion(r){
  const node=el('section',undefined,'sketch');node.dataset.region=r.id;node.dataset.kind=r.kind;position(node,r);
  const grip=el('div',undefined,'grip');grip.title='Move region';node.append(grip);
  const label=el('div',r.text,'label');label.contentEditable='true';label.setAttribute('role','textbox');label.setAttribute('aria-label','Sketch label');label.spellcheck=false;node.append(label);
  if(r.kind==='input'){const input=el('input');input.setAttribute('aria-label','Sketch input');input.placeholder='Type here';input.value=r.value||'';node.append(input);}
  const handle=el('button',undefined,'handle');handle.setAttribute('aria-label','Resize region');node.append(handle,el('span','draft','local-mark'));
  sheet.append(node);return node;
}
function renderTab(){
  for(const child of sheet.querySelectorAll('.sketch'))child.remove();
  for(const r of tab().regions)drawRegion(r);
  for(const s of surfaces.values())s.node.hidden=s.tab!==active;
  $('#tabs').replaceChildren();
  for(const t of tabs){const b=el('button',t.name);b.setAttribute('aria-current',t.id===active?'page':'false');b.onclick=()=>{tab().scroll=viewport.scrollTop;active=t.id;selected=null;renderTab();persist();};b.ondblclick=()=>{b.contentEditable='true';b.focus();};b.onblur=()=>{t.name=b.textContent.trim()||'Untitled';b.contentEditable='false';$('#trail').textContent=t.name;persist();};$('#tabs').append(b);}
  $('#trail').textContent=tab().name;viewport.scrollTop=tab().scroll;outline();
}
function choose(id){selected=id;for(const n of sheet.querySelectorAll('.sketch'))n.classList.toggle('selected',n.dataset.region===id);}
function selectTool(value){tool=value;for(const b of document.querySelectorAll('[data-tool]'))b.setAttribute('aria-pressed',String(b.dataset.tool===value));}
for(const b of document.querySelectorAll('[data-tool]'))b.onclick=()=>selectTool(b.dataset.tool);
function point(event){const b=sheet.getBoundingClientRect();return{x:Math.max(0,event.clientX-b.left),y:Math.max(0,event.clientY-b.top)};}
sheet.addEventListener('pointerdown',event=>{
  if(event.button!==0||event.target.closest('.native-surface'))return;
  const node=event.target.closest('.sketch'),p=point(event);
  if(node&&tool==='select'){
    choose(node.dataset.region);if(event.target.closest('input,[contenteditable]'))return;
    snapshot();const r=tab().regions.find(r=>r.id===selected);gesture={mode:event.target.closest('.handle')?'resize':'move',r,node,start:p,before:{...r}};
  }else if(tool!=='select'){
    event.preventDefault();snapshot();
    const r={id:crypto.randomUUID(),kind:tool,x:p.x,y:p.y,w:160,h:tool==='input'?110:70,text:tool==='region'?'':tool==='input'?'Label':'Text',value:''};
    tab().regions.push(r);const created=drawRegion(r);choose(r.id);gesture={mode:'draw',r,node:created,start:p,before:{...r}};
  }else{choose(null);measure(event);return;}
  gesture.node.classList.add('dragging');sheet.setPointerCapture(event.pointerId);measure(event);
});
sheet.addEventListener('pointermove',event=>{
  if(!gesture)return;const p=point(event),{r,start,before,mode,node}=gesture;
  if(mode==='move'){r.x=Math.max(0,before.x+p.x-start.x);r.y=Math.max(0,before.y+p.y-start.y);}
  else{r.w=Math.max(100,(mode==='draw'?0:before.w)+p.x-start.x);r.h=Math.max(r.kind==='input'?92:44,(mode==='draw'?0:before.h)+p.y-start.y);}
  position(node,r);measure(event);
});
function finish(event,cancel=false){
  if(!gesture)return;const g=gesture;gesture=null;
  if(cancel){const prior=undo.pop();if(prior){const r=JSON.parse(prior);tabs=r.tabs;active=r.active;renderTab();}}
  else{g.node.classList.remove('dragging');outline();persist();log('local',g.mode+' · local draft',{region:g.r.id});}
  if(sheet.hasPointerCapture(event.pointerId))sheet.releasePointerCapture(event.pointerId);
  selectTool('select');measure(event);
}
sheet.addEventListener('pointerup',event=>finish(event));
sheet.addEventListener('pointercancel',event=>finish(event,true));
sheet.addEventListener('compositionstart',()=>composing=true);
sheet.addEventListener('compositionend',()=>{composing=false;persist();});
sheet.addEventListener('input',event=>{
  const node=event.target.closest('.sketch');if(!node)return;
  const r=tab().regions.find(r=>r.id===node.dataset.region);
  if(event.target.matches('input'))r.value=event.target.value;else r.text=event.target.textContent;
  measure(event);persist();
});
sheet.addEventListener('focusout',()=>outline());
viewport.addEventListener('scroll',event=>{measure(event);persist();},{passive:true});
$('#duplicate').onclick=()=>{const r=tab().regions.find(r=>r.id===selected);if(!r)return;snapshot();const c={...r,id:crypto.randomUUID(),x:r.x+28,y:r.y+28};tab().regions.push(c);drawRegion(c);choose(c.id);outline();persist();};
$('#delete').onclick=()=>{if(!selected)return;snapshot();tab().regions=tab().regions.filter(r=>r.id!==selected);renderTab();selected=null;persist();};
$('#undo').onclick=()=>{if(!undo.length)return;const p=JSON.parse(undo.pop());tabs=p.tabs;active=p.active;renderTab();persist();log('local','Undid local sketch change');};
$('#add-tab').onclick=()=>{tab().scroll=viewport.scrollTop;const t=freshTab();tabs.push(t);active=t.id;renderTab();persist();};
$('#activity-toggle').onclick=()=>{const h=!$('#activity').hidden;$('#activity').hidden=h;document.body.classList.toggle('no-activity',h);$('#activity-toggle').setAttribute('aria-expanded',String(!h));};
$('#delay').onclick=()=>{delayMs=delayMs?0:2000;$('#delay').textContent=delayMs?'Network +2.0 s':'Network delay off';$('#delay').setAttribute('aria-pressed',String(!!delayMs));log('local','Response delay '+delayMs+' ms; native duration measured separately');};
function evidence(){
  const dist=list=>{const a=list.map(s=>s.ms);return{count:a.length,p50:percentile(a,.5),p95:percentile(a,.95),p99:percentile(a,.99),max:a.length?Math.max(...a):null};};
  return{version:1,url:location.origin,created:new Date().toISOString(),browser:navigator.userAgent,viewport:[innerWidth,innerHeight],devicePixelRatio,delayMs,clocks:{local:'DOM event timestamp to next requestAnimationFrame (paint opportunity; not hardware presentation)',native:'host arrival to native response including owner queue, excluding injected delay',roundTrip:'fetch start to decoded response including injected delay'},summary:{local:dist(samples.local),native:dist(samples.native),roundTrip:dist(samples.roundTrip)},samples,journal};
}
window.groveEvidence=evidence; // Diagnostics only; proof gestures use browser input.
$('#export-evidence').onclick=()=>{const l=el('a');l.href=URL.createObjectURL(new Blob([JSON.stringify(evidence(),null,2)],{type:'application/json'}));l.download='grove-interaction-evidence.json';l.click();setTimeout(()=>URL.revokeObjectURL(l.href),1000);};
async function call(operation,body,event=''){
  const started=performance.now(),response=await fetch('/api/native',{method:'POST',headers:{'Content-Type':'application/json','X-Proof-Delay-Ms':String(delayMs)},body:JSON.stringify({operation,body,event})});
  const result=await response.json(),ended=performance.now();
  const timing=response.headers.get('Server-Timing')?.match(/native;dur=([\d.]+)/),native=timing?Number(timing[1]):null;
  samples.roundTrip.push({operation,ms:ended-started,status:response.status,delayMs});
  if(native!==null)samples.native.push({operation,ms:native,status:response.status});
  log(response.ok?'native':'error',operation.replace('native/','')+' · '+response.status+' · round trip '+Math.round(ended-started)+' ms',{nativeMs:native,event,result:response.ok?undefined:result});
  if(!response.ok)throw Object.assign(new Error(result.error||'Native response '+response.status),{result,status:response.status});
  return result;
}
async function discover(subject='/0x11/app/material'){
  try{const d=await call('native/discover',{subject});$('#connection').textContent='Native connected · AI not started';$('#material').replaceChildren();
    if(subject!=='/0x11/app'){const up=el('button','‹ Parent');up.onclick=()=>discover(subject.slice(0,subject.lastIndexOf('/')));$('#material').append(up);}
    for(const c of d.children){const b=el('button',c.label||c.subject.split('/').at(-1));b.title=c.subject;b.draggable=true;b.dataset.subject=c.subject;b.onclick=()=>discover(c.subject);b.ondblclick=()=>openSurface(c.subject);b.ondragstart=e=>e.dataTransfer.setData('application/x-grove-reference',c.subject);$('#material').append(b);}
    const open=el('button','Open this native surface');open.onclick=()=>openSurface(subject);$('#material').append(open);
  }catch(e){$('#connection').textContent='Native unavailable · drafts retained';log('error',e.message);}
}
sheet.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-grove-reference'))e.preventDefault();});
sheet.addEventListener('drop',e=>{const s=e.dataTransfer.getData('application/x-grove-reference');if(!s)return;e.preventDefault();openSurface(s,point(e));measure(e);});
$('#refresh-world').onclick=()=>discover();
$('#search').oninput=()=>{for(const b of $('#material').children)b.hidden=!b.textContent.toLowerCase().includes($('#search').value.toLowerCase());};
const protectedNode=n=>n.nodeType===1&&(n.contains(document.activeElement)||n.matches('[data-draft]')||n.querySelector('[data-draft]'));
const key=n=>n.nodeType===1&&(n.getAttribute('data-grove-key')||n.getAttribute('data-grove-row'));
function patch(old,next){
  if(protectedNode(old)&&old.matches('input,textarea,[contenteditable]'))return old;
  if(old.nodeType!==next.nodeType||old.nodeName!==next.nodeName){if(protectedNode(old))return old;const r=next.cloneNode(true);old.replaceWith(r);return r;}
  if(old.nodeType!==1){old.nodeValue=next.nodeValue;return old;}
  for(const a of [...old.attributes])if(!next.hasAttribute(a.name)&&a.name!=='data-draft')old.removeAttribute(a.name);
  for(const a of next.attributes)if(old.getAttribute(a.name)!==a.value)old.setAttribute(a.name,a.value);
  if(old.matches('input,textarea')){old.value=next.value;return old;}
  const keyed=new Map([...old.childNodes].filter(key).map(n=>[key(n),n]));let at=old.firstChild;
  for(const n of next.childNodes){let current=key(n)?keyed.get(key(n)):at&&!key(at)?at:null;
    if(!current){current=n.cloneNode(true);old.insertBefore(current,at);}
    else{if(current!==at)old.insertBefore(current,at);current=patch(current,n);}at=current.nextSibling;}
  while(at){const following=at.nextSibling;if(!protectedNode(at))at.remove();at=following;}return old;
}
function renderSurface(s,result){
  const next=el('div',undefined,'content');next.innerHTML=result.html;
  for(const n of next.querySelectorAll('script,iframe,object,embed,link,meta,base'))n.remove();
  for(const n of next.querySelectorAll('*'))for(const a of [...n.attributes])if(/^on/i.test(a.name)||['srcdoc','formaction','action','href','src'].includes(a.name))n.removeAttribute(a.name);
  patch(s.content,next);s.frame=result;
}
async function refresh(s){if(s.reading)return;s.reading=true;try{renderSurface(s,await call('native/frame',{subject:s.subject,viewport:[]}));}catch(e){s.feedback.textContent=e.message;}finally{s.reading=false;}}
async function openSurface(subject,p={x:45,y:80}){
  const node=el('section',undefined,'native-surface arrived');Object.assign(node.style,{left:p.x+'px',top:p.y+'px',width:'600px'});
  const heading=el('header'),close=el('button','×');heading.append(el('span',subject),close);
  const content=el('div',undefined,'content'),feedback=el('div',undefined,'feedback');node.append(heading,content,feedback);sheet.append(node);
  const s={id:crypto.randomUUID(),tab:active,subject,node,content,feedback,drafts:new Map(),frame:null};surfaces.set(s.id,s);close.onclick=()=>{node.remove();surfaces.delete(s.id);outline();};
  content.addEventListener('input',e=>{const f=e.target.closest('[data-grove-key]');if(!f||!s.frame)return;const k=f.dataset.groveKey,prior=s.drafts.get(k);s.drafts.set(k,{basis:prior?.basis||s.frame.basis,value:f.value,revision:(prior?.revision||0)+1});f.dataset.draft='true';measure(e);});
  async function action(f){
    if(!s.frame||s.saving)return;const k=f.dataset.groveKey,draft=s.drafts.get(k);if(f.dataset.groveEdit&&!draft)return;
    const args=f.dataset.argumentSlot?[{slot:f.dataset.argumentSlot,kind:f.dataset.argumentKind||'text',value:draft?.value??f.value}]:[];
    s.saving=true;f.classList.add('pending');const revision=draft?.revision;
    try{const event=crypto.randomUUID();await call('native/act',{subject,basis:draft?.basis||s.frame.basis,viewport:[],key:k,parameters:[],arguments:args},event);
      if(s.drafts.get(k)?.revision===revision){s.drafts.delete(k);delete f.dataset.draft;}
      feedback.textContent='';for(const other of surfaces.values())refresh(other);
    }catch(e){f.classList.add('conflict');feedback.textContent=e.message;}finally{s.saving=false;f.classList.remove('pending');}
  }
  content.addEventListener('change',e=>{const f=e.target.closest('[data-grove-edit]');if(f&&!composing)action(f);});
  content.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('input')&&!e.isComposing){e.preventDefault();action(e.target);}});
  content.addEventListener('click',async e=>{const f=e.target.closest('[data-grove-key]');if(!f)return;if(e.altKey){e.preventDefault();$('#inspector').hidden=false;try{$('#native-result').textContent=JSON.stringify(await call('native/inspect',{subject,basis:s.frame.basis,viewport:[],key:f.dataset.groveKey,parameters:[]}),null,2);}catch(error){feedback.textContent=error.message;}}else if(f.dataset.groveAct)action(f);});
  outline();await refresh(s);return s;
}
let sourceBasis=null,sourceTarget=null;
$('#inspect-toggle').onclick=()=>$('#inspector').hidden=!$('#inspector').hidden;
$('#inspect-close').onclick=()=>$('#inspector').hidden=true;
$('#native-open').onclick=()=>{openSurface($('#native-subject').value);$('#inspector').hidden=true;};
$('#native-read').onclick=async()=>{try{sourceTarget=$('#native-subject').value;const r=await call('native/source',{subject:sourceTarget});sourceBasis=r.basis;$('#native-source').value=r.source;$('#native-result').textContent=JSON.stringify(r.basis,null,2);}catch(e){$('#native-result').textContent=e.message;}};
$('#native-compile').onclick=async()=>{
  const b=$('#native-compile');b.disabled=true;$('#native-result').textContent='Native compilation and publication pending…';
  try{const subject=$('#native-subject').value;if(sourceTarget!==subject){const current=await call('native/source',{subject});if(current.basis.epoch!==null)throw new Error('Read the existing definition before replacing it. Draft preserved.');sourceTarget=subject;sourceBasis=current.basis;}
    sourceBasis=await call('native/author',{subject,source:$('#native-source').value,expected:sourceBasis.epoch||''},crypto.randomUUID());$('#native-result').textContent=JSON.stringify(sourceBasis,null,2);
  }catch(e){$('#native-result').textContent='Not installed; source draft retained.\n'+e.message;}finally{b.disabled=false;}
};
$('#native-instantiate').onclick=async()=>{try{if(!sourceBasis?.case||sourceTarget!==$('#native-subject').value)throw new Error('Read or compile the definition first.');const subject=$('#native-instance').value;const r=await call('native/instantiate',{subject,source:sourceTarget,version:sourceBasis.case,expected:''},crypto.randomUUID());$('#native-result').textContent=JSON.stringify(r,null,2);discover(subject);}catch(e){$('#native-result').textContent=e.message;}};
renderTab();
await fetch('/connect',{method:'POST'});
log('local','Physical draft surface ready. Model refinement is not implemented yet.');
discover();
