/* Read-only, explicit observations of installed presentations. No handles,
 * input values, namespace writes, or domain invocations cross this boundary. */
(function(root) {
  'use strict';
  const installed = new WeakMap();
  const session = root.crypto?.randomUUID?.() || `page-${Date.now()}`;
  let serial=0;
  const scalar=value=>typeof value==='string'||typeof value==='number'?String(value):'';
  const count=value=>Number.isSafeInteger(value)&&value>=0?String(value):'0';
  function record(element, data, local) {
    const previous=installed.get(element);
    const packet={};
    for(const key of ['snapshot','view','role','slot','kind','node','origin','context','profile','layout','capture'])
      if(data[key]!==undefined)packet[key]=structuredClone(data[key]);
    packet.nodes=Array.isArray(data.display?.nodes)?data.display.nodes.length:0;
    packet.height=data.display?.height;
    installed.set(element,{packet,local:local||previous?.local});
  }
  function bind(element, local) { const held=installed.get(find(element));if(held)held.local=local; }
  function find(element) {
    for(let node=element;node;node=node.parentElement)if(installed.has(node))return node;
    return null;
  }
  function capture(element) {
    const held=installed.get(element);
    if(!held || !element.isConnected)throw new Error('Presentation is no longer installed.');
    const data=held.packet, local=held.local?.()||{}, snapshot=data.snapshot||{};
    if(local.live===false)throw new Error('Presentation encounter has retired.');
    const subject=scalar(snapshot.subject||snapshot.target||local.subject);
    if(!subject)throw new Error('This presentation has no captured subject.');
    // Explicit whitelist: inspection cannot accidentally serialize a capability,
    // action token object, DOM node, or the contents of an unsaved input.
    return Object.freeze({capture:`${session}:${++serial}`,parent:scalar(data.capture),
      subject,target:scalar(snapshot.target||subject),life:scalar(snapshot.life),
      displayed:scalar(snapshot.displayed),expected:scalar(snapshot.expected),projectionSeq:scalar(snapshot.projectionSeq),
      view:scalar(data.view),role:scalar(data.role),slot:scalar(data.slot),publication:scalar(snapshot.publication),
      kind:scalar(data.kind),node:scalar(data.node),line:count(data.origin?.line),column:count(data.origin?.column),
      layout:scalar(data.layout||'exact'),renderHeight:scalar(data.height),renderWidth:scalar(data.context?.width),renderScale:scalar(data.context?.textScale),
      renderDirection:scalar(data.context?.direction),profile:scalar(data.profile?.id),profileRevision:scalar(data.profile?.revision),nodes:count(data.nodes),
      session,revision:count(local.revision),owner:scalar(local.owner),incarnation:count(local.incarnation),
      encounter:scalar(local.encounter),generation:count(local.generation),selection:scalar(local.selection),
      pending:String(!!local.pending),dirty:count(local.dirty),composing:count(local.composing),live:'true'});
  }
  root.GooInspection={record,bind,find,capture};
  if(typeof module!=='undefined')module.exports=root.GooInspection;
  if(!root.document)return;
  const el=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
  const picker=el('button','Inspect a presentation');picker.type='button';picker.className='goo-inspect-picker';
  picker.setAttribute('aria-pressed','false');picker.title='Choose a presentation, or press Alt+I while focused inside one.';
  const panel=el('aside');panel.className='goo-inspect-panel';panel.hidden=true;panel.setAttribute('aria-label','Presentation inspection');
  const title=el('h2','Inspect this presentation'), provenance=el('p','Frozen browser observation. Namespace links open current records.');
  const close=el('button','Close inspection'), refresh=el('button','Capture again'), links=el('nav'), status=el('p'), body=el('div');
  close.type=refresh.type='button';links.setAttribute('aria-label','Inspection references');status.setAttribute('role','status');body.className='goo-inspect-content';
  panel.append(title,close,refresh,provenance,links,status,body);document.body.append(picker,panel);
  let picking=false,selected,observation,request,revision=0,returnFocus,stopObserving;
  const pick=value=>{picking=value;picker.setAttribute('aria-pressed',String(value));picker.textContent=value?'Cancel inspection pick':'Inspect a presentation';document.documentElement.classList.toggle('goo-inspect-picking',value);};
  const current=()=>selected?.isConnected && installed.has(selected);
  async function render() {
    if(!observation||panel.hidden)return;
    request?.abort();request=new AbortController();const turn=++revision,captured=observation;
    status.textContent='Preparing captured observation…';
    try {
      const context=root.GooActions.context(body),fields={...captured,width:context.width,textScale:context.textScale,direction:context.direction};
      const response=await fetch('/goo/inspect',{method:'POST',cache:'no-store',body:new URLSearchParams(fields),signal:request.signal});
      if(!response.ok)throw new Error(await response.text());
      const data=await response.json();
      if(turn!==revision||panel.hidden)return;
      if(data.version!==1||data.kind!=='inspection'||data.capture!==captured.capture||data.controls?.length!==0)throw new Error('Invalid inspection response.');
      if(['width','textScale','direction'].some(key=>data.context?.[key]!==context[key]))throw new Error('Inspection context mismatch.');
      const profile=await (await fetch('/static/goo-profile.json',{cache:'no-store',signal:request.signal})).json();
      if(turn!==revision||panel.hidden)return;
      if(['id','version','revision'].some(key=>data.profile?.[key]!==profile[key]||data.display?.profile?.[key]!==profile[key]))throw new Error('Inspection profile mismatch.');
      root.GooActions.mount(body,data,false,false);
      // Inspecting the inspector captures this generated presentation, linked
      // to its parent capture. It does not recursively expand it.
      bind(body,()=>({subject:captured.subject,owner:'inspection',revision:turn,live:!panel.hidden}));
      status.textContent='Captured observation. Use Capture again to observe the currently installed presentation.';
    } catch(error) {if(error.name!=='AbortError'&&turn===revision&&!panel.hidden)status.textContent=error.message;}
  }
  function show(element) {
    const captured=capture(element); // Capture synchronously before any request.
    selected=element;observation=captured;if(!panel.contains(document.activeElement))returnFocus=document.activeElement;pick(false);panel.hidden=false;
    links.replaceChildren();
    for(const [label,path] of [['Subject',captured.subject],['Writable receiver',captured.target],['Recipe',captured.view]]) {
      const link=el('a',`${label}: ${path}`);link.href='/views'+path.split('/').map(encodeURIComponent).join('/');link.target='_blank';link.rel='noopener';links.append(link);
    }
    // Previous capture content must not appear under the new capture's links.
    body.replaceChildren();installed.delete(body);status.textContent='Preparing captured observation…';
    stopObserving?.();stopObserving=root.GooActions.observe(body,()=>render());render();
  }
  picker.addEventListener('click',()=>pick(!picking));
  document.addEventListener('click',event=>{
    if(!picking||event.target===picker)return;
    const target=find(event.target);if(!target)return;
    event.preventDefault();event.stopImmediatePropagation();
    try{show(target);}catch(error){pick(false);panel.hidden=false;status.textContent=error.message;}
  },true);
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&picking){pick(false);event.preventDefault();return;}
    if(event.altKey&&event.key.toLowerCase()==='i') {
      const target=find(event.target);if(!target)return;
      event.preventDefault();try{show(target);}catch(error){panel.hidden=false;status.textContent=error.message;}
    }
  },true);
  refresh.addEventListener('click',()=>{
    if(!current()){status.textContent='Original presentation was removed. Pick another presentation.';return;}
    try{show(selected);}catch(error){status.textContent=error.message;}
  });
  close.addEventListener('click',()=>{panel.hidden=true;++revision;request?.abort();stopObserving?.();pick(false);if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});});
})(globalThis);
