import {createNativeSurfaces} from './native-surfaces.js';
import {worldPoint,zoomAt,fitCamera,restoreLayout} from './canvas-space.mjs';

const el=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls??'';if(text!==undefined)n.textContent=text;return n;};
const control=(label,action,cls='canvas-tool')=>{const b=el('button',cls,label);b.type='button';b.onclick=action;return b;};
const editing=target=>target?.closest('input,textarea,select,[contenteditable=true]');

// Spatial organization is local presentation state. Moving a card never moves
// its native subject, rewrites its relations, or publishes application history.
export function createInfiniteCanvas({root,inspector,request,onMutation,onError}) {
  const cards=new Map(),instruments=new Map();let positions=new Map(),camera={x:90,y:90,zoom:1};
  let catalog=null,storageKey=null,selected=null,creating=false,loading=false,hand=false,space=false,drag=null,saveTimer,statusTimer,arrangeOnLoad=false;
  const viewport=el('div','canvas-viewport');viewport.tabIndex=0;viewport.setAttribute('aria-label','Infinite canvas');
  const plane=el('div','canvas-plane');viewport.append(plane);
  const links=document.createElementNS('http://www.w3.org/2000/svg','svg');
  links.classList.add('canvas-instrument-links');links.setAttribute('aria-hidden','true');plane.append(links);
  const empty=el('div','canvas-empty');
  const start=control('Put something here',()=>create(), 'canvas-start');start.disabled=true;
  empty.append(el('span','canvas-empty-mark','✳'),el('h1','','What are you making?'),
    el('p','','Start anywhere. Give an idea some room.'),
    start,el('small','','Double-click anywhere to begin.'));
  viewport.append(empty);
  const corner=el('div','canvas-location');corner.append(el('span','','Your canvas'));
  const count=el('span','canvas-count','');corner.append(count);
  const more=control('Load more',()=>refresh(true).catch(fail),'text-button');more.hidden=true;corner.append(more);
  const status=el('div','canvas-status');status.setAttribute('role','status');status.hidden=true;
  const dock=el('nav','canvas-dock');dock.setAttribute('aria-label','Canvas tools');
  const add=control('+ New concept',()=>create(),'canvas-tool canvas-add');add.title='New concept · N';add.disabled=true;
  const move=control('Hand',()=>{hand=!hand;move.setAttribute('aria-pressed',String(hand));viewport.classList.toggle('hand',hand);});
  move.title='Pan · hold Space or drag the background';move.setAttribute('aria-pressed','false');
  const minus=control('−',()=>zoom(.8));minus.setAttribute('aria-label','Zoom out');
  const percent=control('100%',()=>setZoom(1));percent.title='Reset zoom';
  const plus=control('+',()=>zoom(1.25));plus.setAttribute('aria-label','Zoom in');
  const fit=control('Fit',()=>fitAll());fit.title='Fit subjects · ⌘0';
  dock.append(add,el('span','dock-divider'),move,el('span','dock-divider'),minus,percent,plus,fit);
  const hint=el('div','canvas-gesture-hint','Pan with two fingers · pinch to zoom · hold ⌥ to inspect');
  root.append(viewport,corner,status,dock,hint);
  function say(text){clearTimeout(statusTimer);status.textContent=text;status.hidden=!text;}
  function fail(error){say(error.message);onError?.(error);}
  function persist(){
    clearTimeout(saveTimer);saveTimer=setTimeout(()=>{
      if(!storageKey)return;
      try{localStorage.setItem(storageKey,JSON.stringify({version:1,camera,positions:Object.fromEntries(positions)}));}
      catch{say('Your arrangement is kept for this session. Browser storage is unavailable.');}
    },200);
  }
  function paint(){
    plane.style.transform=`translate(${camera.x}px,${camera.y}px) scale(${camera.zoom})`;
    viewport.style.backgroundSize=`${24*camera.zoom}px ${24*camera.zoom}px`;
    viewport.style.backgroundPosition=`${camera.x}px ${camera.y}px`;
    percent.textContent=`${Math.round(camera.zoom*100)}%`;
    drawLinks();inspector.refresh();persist();
  }
  function midpoint(){return {x:viewport.clientWidth/2,y:viewport.clientHeight/2};}
  function setZoom(value,anchor=midpoint()){camera=zoomAt(camera,anchor,value);paint();scheduleVisible();}
  function zoom(factor){setZoom(camera.zoom*factor);}
  function point(event){const r=viewport.getBoundingClientRect();return {x:event.clientX-r.left,y:event.clientY-r.top};}
  function itemPosition(item){return item.instrument?item.position:positions.get(item.id);}
  function place(card){const p=itemPosition(card);card.node.style.left=`${p.x}px`;card.node.style.top=`${p.y}px`;drawLinks();}
  function rectangle(item){return {...itemPosition(item),width:item.node.offsetWidth,height:item.node.offsetHeight};}
  function drawLinks(){
    for(const instrument of instruments.values()){
      const owner=cards.get(instrument.subject),p=owner&&itemPosition(owner),q=instrument.position;
      instrument.link.hidden=!owner||instrument.node.hidden;
      if(!owner||instrument.node.hidden){instrument.link.setAttribute('d','');continue;}
      const x=p.x+owner.node.offsetWidth,y=p.y+36,endX=q.x,endY=q.y+36;
      const bend=Math.max(40,Math.abs(endX-x)/2);
      instrument.link.setAttribute('d',`M ${x} ${y} C ${x+bend} ${y}, ${endX-bend} ${endY}, ${endX} ${endY}`);
    }
  }
  function visible(card){
    const p=positions.get(card.id),x=p.x*camera.zoom+camera.x,y=p.y*camera.zoom+camera.y;
    return x>-600&&y>-800&&x<viewport.clientWidth+300&&y<viewport.clientHeight+300;
  }
  function select(card){
    selected=card?.id??null;
    for(const item of cards.values())item.node.classList.toggle('selected',item.id===selected);
  }
  function fitAll(){
    camera=fitCamera([...cards.values(),...[...instruments.values()].filter(i=>!i.node.hidden)].map(rectangle),viewport.clientWidth,viewport.clientHeight-90);
    paint();scheduleVisible();
  }
  function addCard(subject,index){
    if(cards.has(subject.id))return cards.get(subject.id);
    if(!positions.has(subject.id))positions.set(subject.id,{x:(index%3)*420,y:Math.floor(index/3)*430});
    const node=el('article','canvas-subject');node.dataset.subject=subject.id;node.setAttribute('aria-label',subject.label||'Untitled concept');
    const handle=el('div','canvas-card-handle');handle.tabIndex=0;handle.title='Drag to arrange · arrow keys move the card';
    handle.setAttribute('aria-label',`Move ${subject.label||'concept'}`);
    const title=el('span','canvas-card-name',subject.label||'Untitled concept');
    const indicator=el('span','canvas-card-state','');handle.append(el('span','canvas-grip','⠿'),title,indicator);
    const body=el('div','canvas-card-body');body.append(el('p','canvas-loading','Opening native subject…'));
    node.append(handle,body);plane.append(node);
    const card={id:subject.id,node,handle,title,indicator,body,loaded:false,pending:false,surface:null};
    cards.set(card.id,card);place(card);
    card.surface=createNativeSurfaces({root:body,inspector,request,onMutation,onError:fail,embedded:true,scope:`canvas:${card.id}`,
      onFrame:frame=>{
        title.textContent=frame.label||'Untitled concept';node.setAttribute('aria-label',title.textContent);handle.setAttribute('aria-label',`Move ${title.textContent}`);indicator.textContent='';
        // New worlds lay out Goo at this width. Older pinned frames can use
        // ordinary browser wrapping without changing any native action route.
        inspector.begin(`canvas-shell:${card.id}`);
        inspector.bind(handle,`canvas-subject:${card.id}`,()=>({title:title.textContent,kind:'Native subject',subject:frame.subject,basis:frame.expected,description:'Its position is local to your canvas. Its data and actions live in Shrine.',fields:[]}));
        inspector.end();
      }});
    node.addEventListener('pointerdown',()=>select(card));
    handle.addEventListener('pointerdown',event=>beginDrag(event,card));
    handle.addEventListener('keydown',event=>{
      if(document.body.classList.contains('inspecting'))return;
      const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];
      if(!delta)return;event.preventDefault();const p=positions.get(card.id),step=event.shiftKey?40:10;
      positions.set(card.id,{x:p.x+delta[0]*step,y:p.y+delta[1]*step});select(card);place(card);persist();inspector.refresh();
    });
    return card;
  }
  async function load(card,force=false){
    if(card.pending||(!force&&card.loaded))return;
    card.pending=true;
    try{await card.surface.read(card.id);card.loaded=true;card.body.querySelector('.canvas-loading')?.remove();}
    catch(error){card.indicator.textContent='Unavailable';fail(error);}
    finally{card.pending=false;}
  }
  async function scheduleVisible(){
    if(loading||root.hidden)return;loading=true;
    try{for(const card of cards.values())if(visible(card)&&!card.loaded)await load(card);}
    finally{loading=false;}
  }
  async function refresh(next=false){
    const previouslyLoaded=new Set([...cards.values()].filter(c=>c.loaded).map(c=>c.id));
    const value=await request('present',next&&catalog?.next_children?{target:catalog.target,children:catalog.next_children,epoch:catalog.epoch}:{});
    if(value.protocol!=='canvas-surface/1')throw new Error('This world does not expose native surfaces.');
    if(!storageKey){
      storageKey=`grove:canvas:1:${location.origin}:${value.target}`;
      arrangeOnLoad=true;
      try{const saved=restoreLayout(JSON.parse(localStorage.getItem(storageKey)));if(saved){positions=saved.positions;if(saved.camera)camera=saved.camera;arrangeOnLoad=false;}}catch{}
    }
    catalog=value;
    add.disabled=creating;start.disabled=creating;
    value.children.forEach((subject,i)=>addCard(subject,cards.size));
    // Absence only means deletion when this is the entire native collection.
    if(!next&&!value.next_children){
      const present=new Set(value.children.map(c=>c.id));
      for(const [id,card]of cards)if(!present.has(id)){card.surface.destroy();inspector.begin(`canvas-shell:${card.id}`);inspector.end();card.node.remove();cards.delete(id);positions.delete(id);}
    }
    count.textContent=`${cards.size} ${cards.size===1?'subject':'subjects'}`;more.hidden=!value.next_children;
    empty.hidden=cards.size>0;paint();await scheduleVisible();
    if(arrangeOnLoad&&cards.size){
      arrangeOnLoad=false;let x=0;
      for(const card of cards.values()){positions.set(card.id,{x,y:0});place(card);x+=card.node.offsetWidth+60;}
      fitAll();
    }
    for(const card of cards.values())if(previouslyLoaded.has(card.id)&&visible(card)&&!card.pending)await load(card,true);
  }
  async function create(at){
    if(!catalog){say('Connecting to your native workspace…');return;}
    if(creating)return;creating=true;add.disabled=true;say('Making a place…');
    const origin=selected&&positions.get(selected),center=worldPoint(camera,midpoint());
    const p=at??(origin?{x:origin.x+420,y:origin.y}:{x:center.x-180,y:center.y-140});
    const pending=el('div','canvas-subject canvas-pending');pending.setAttribute('role','status');
    pending.style.left=`${p.x}px`;pending.style.top=`${p.y}px`;
    pending.append(el('div','canvas-card-handle','New concept'),el('p','canvas-loading','Establishing its native subject…'));plane.append(pending);
    camera={...camera,x:viewport.clientWidth/2-(p.x+180)*camera.zoom,y:Math.max(75,viewport.clientHeight/2-200)-p.y*camera.zoom};paint();
    try{
      const value=await request('construct',{label:'Untitled concept'});onMutation(value.frame);
      positions.set(value.created,p);
      const card=addCard({id:value.created,label:'Untitled concept'},cards.size);empty.hidden=true;select(card);place(card);
      await load(card);card.surface.edit();say('Start here. Your words stay with this subject.');
      statusTimer=setTimeout(()=>say(''),4000);
      count.textContent=`${cards.size} ${cards.size===1?'subject':'subjects'}`;
    }catch(error){fail(error);}finally{pending.remove();creating=false;add.disabled=false;}
  }
  function beginDrag(event,card=null){
    if(document.body.classList.contains('inspecting')||event.button>1)return;
    if(card&&(space||hand||event.button===1))card=null;
    if(event.target.closest('button,input,textarea,select,a'))return;
    event.preventDefault();event.stopPropagation();const start=point(event),origin=card?itemPosition(card):{x:camera.x,y:camera.y};
    drag={card,start,origin:{...origin},target:event.currentTarget,pointer:event.pointerId};
    drag.target.setPointerCapture(event.pointerId);viewport.classList.add('dragging');
    if(card&&!card.instrument)select(card);
  }
  viewport.addEventListener('pointerdown',event=>{
    if(event.target.closest('.canvas-subject,.canvas-instrument')&&!space&&!hand&&event.button!==1)return;
    if(event.target.closest('button,input,textarea,select,a')&&!space&&!hand)return;
    beginDrag(event);
  });
  viewport.addEventListener('pointermove',event=>{
    if(!drag)return;const p=point(event),dx=p.x-drag.start.x,dy=p.y-drag.start.y;
    if(drag.card){
      const p={x:drag.origin.x+dx/camera.zoom,y:drag.origin.y+dy/camera.zoom};
      if(drag.card.instrument)drag.card.position=p;else positions.set(drag.card.id,p);
      place(drag.card);inspector.refresh();
    }
    else{camera={...camera,x:drag.origin.x+dx,y:drag.origin.y+dy};paint();}
  });
  function endDrag(){if(!drag)return;if(drag.target.hasPointerCapture(drag.pointer))drag.target.releasePointerCapture(drag.pointer);drag=null;viewport.classList.remove('dragging');persist();scheduleVisible();}
  viewport.addEventListener('pointerup',endDrag);viewport.addEventListener('pointercancel',endDrag);
  viewport.addEventListener('dblclick',event=>{if(!event.target.closest('.canvas-subject,.canvas-instrument,button')&&!document.body.classList.contains('inspecting'))create(worldPoint(camera,point(event)));});
  viewport.addEventListener('wheel',event=>{
    if((editing(event.target)||event.target.closest('.canvas-instrument'))&&!event.ctrlKey&&!event.metaKey)return;
    event.preventDefault();
    if(event.ctrlKey||event.metaKey)setZoom(camera.zoom*Math.exp(-event.deltaY*.008),point(event));
    else{camera={...camera,x:camera.x-event.deltaX,y:camera.y-event.deltaY};paint();scheduleVisible();}
  },{passive:false});
  document.addEventListener('keydown',event=>{
    if(root.hidden||editing(event.target)||event.target.closest('#inspector,.presentation-experiment'))return;
    if(event.code==='Space'){event.preventDefault();space=true;viewport.classList.add('hand');}
    if((event.metaKey||event.ctrlKey)&&event.key==='0'){event.preventDefault();fitAll();}
    if(event.key.toLowerCase()==='n'&&!event.metaKey&&!event.ctrlKey&&!event.altKey){event.preventDefault();create();}
  });
  document.addEventListener('keyup',event=>{if(event.code==='Space'){space=false;viewport.classList.toggle('hand',hand);}});
  window.addEventListener('blur',()=>{space=false;viewport.classList.toggle('hand',hand);endDrag();});
  new ResizeObserver(()=>{paint();scheduleVisible();}).observe(viewport);
  function attachInstrument(node,subject){
    node.style.maxHeight=`${Math.max(320,viewport.clientHeight-130)}px`;
    let instrument=instruments.get(node);
    if(!instrument){
      const link=document.createElementNS('http://www.w3.org/2000/svg','path');links.append(link);
      instrument={node,subject,link,instrument:true,position:{x:0,y:0}};instruments.set(node,instrument);
      node.classList.add('canvas-instrument');plane.append(node);
      const handle=node.querySelector('.surface-heading');handle.classList.add('canvas-instrument-handle');
      handle.tabIndex=0;handle.setAttribute('aria-label','Move presentation experiment');
      handle.addEventListener('pointerdown',event=>beginDrag(event,instrument));
      handle.addEventListener('keydown',event=>{
        if(event.target!==handle)return;
        const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];
        if(!delta)return;event.preventDefault();const step=event.shiftKey?40:10;
        instrument.position={x:instrument.position.x+delta[0]*step,y:instrument.position.y+delta[1]*step};place(instrument);
      });
      new ResizeObserver(drawLinks).observe(node);
    }
    const owner=cards.get(subject),p=owner?positions.get(subject):worldPoint(camera,midpoint());
    if(instrument.subject!==subject||!instrument.positioned){
      instrument.position={x:p.x+(owner?.node.offsetWidth??360)+60,y:p.y};instrument.positioned=true;
    }
    instrument.subject=subject;place(instrument);
    // The line denotes this exact presentation's subject, not an invented
    // application relation. Focus the pair when readable, otherwise the tool.
    const pair=[...(owner?[rectangle(owner)]:[]),rectangle(instrument)];
    const fit=fitCamera(pair,viewport.clientWidth,viewport.clientHeight-90,40);
    camera=fit.zoom>=.8?fit:fitCamera([rectangle(instrument)],viewport.clientWidth,viewport.clientHeight-90,40);
    paint();scheduleVisible();
  }
  function releaseInstrument(node){
    const instrument=instruments.get(node);if(!instrument)return;
    drawLinks();const owner=cards.get(instrument.subject);if(!owner)return;
    // Return to the same subject. A tool can be reopened with its draft intact.
    camera=fitCamera([rectangle(owner)],viewport.clientWidth,viewport.clientHeight-90,70);
    paint();owner.handle.focus({preventScroll:true});
  }
  return {read:refresh,refresh,fit:fitAll,attachInstrument,releaseInstrument,show:()=>{root.hidden=false;scheduleVisible();},hide:()=>{root.hidden=true;}};
}
