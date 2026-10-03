import {InspectionState} from './inspection-state.mjs';

// Each renderer supplies explicit occurrence -> native context correspondence.
// Never infer subjects from prose, CSS names, a row index or a path suffix.
export function createInspector({panel, toggle, close, pin, render}) {
  const state = new InspectionState();
  const entries = new Map();
  const nodes = new WeakMap();
  const outline = document.createElement('div');
  outline.className = 'inspection-outline'; outline.hidden = true;
  document.body.append(outline);
  let seen = new Set(), scope = 'default', lastElement = null, scheduled = false;
  const editable = node => node?.closest('input,textarea,select,[contenteditable=true]');
  function locate(node) {
    if (!(node instanceof Element) || panel.contains(node)) return null;
    for(let current = node; current; current = current.parentElement) {
      if(nodes.has(current)) return nodes.get(current);
    }
    return null;
  }
  function position() {
    const entry = entries.get(state.key);
    const visible = state.visible && entry?.node.isConnected;
    outline.hidden = !visible;
    if(!visible) return;
    const rect = entry.node.getBoundingClientRect();
    Object.assign(outline.style, {left:`${rect.left-3}px`,top:`${rect.top-3}px`,width:`${rect.width+6}px`,height:`${rect.height+6}px`});
  }
  function update() {
    document.body.classList.toggle('inspecting', state.active);
    toggle.setAttribute('aria-pressed',String(state.mode));
    panel.hidden = !state.visible;
    pin.textContent = state.pinned ? 'Follow pointer' : 'Pin · Enter';
    pin.setAttribute('aria-label',state.pinned ? 'Resume following inspected elements' : 'Pin inspected subject');
    if(state.visible) render(entries.get(state.key)?.describe() ?? null, {pinned:state.pinned});
    position();
  }
  function hover(node) {
    lastElement = node;
    if(panel.contains(node)) return;
    const key = locate(node);
    if(key === null || key === state.key || !state.active || state.pinned) return;
    state.hover(key); update();
  }
  document.addEventListener('pointermove',event=>hover(event.target),{passive:true});
  document.addEventListener('focusin',event=>hover(event.target));
  // Inspection gestures cannot also book, publish, or start a timeline drag.
  for(const type of ['pointerdown','click','dblclick']) document.addEventListener(type,event=>{
    const key = locate(event.target);
    if(!state.active || key === null) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if(type === 'click') { state.pin(key); update(); }
  },true);
  document.addEventListener('keydown',event=>{
    if(event.key === 'Alt' && !editable(event.target)) {
      state.hold(true); hover(lastElement ?? document.activeElement); update();
    }
    if((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'i') {
      event.preventDefault(); state.toggle(); hover(lastElement ?? document.activeElement); update();
    }
    if(event.key === 'Escape') { state.close(); update(); }
    if(event.key === 'Enter' && state.active && state.key && !editable(event.target) && !panel.contains(event.target)) {
      event.preventDefault(); event.stopImmediatePropagation(); state.pin(); update();
    }
    // Range, checkbox and text controls keep their normal keyboard semantics
    // outside inspect mode. While inspecting, only navigation reaches them.
    if(state.active && locate(event.target) && !panel.contains(event.target)
       && !['Tab','Alt','Shift','Control','Meta','Escape'].includes(event.key)
       && !event.metaKey && !event.ctrlKey) {
      event.preventDefault(); event.stopImmediatePropagation();
      if(event.key === 'Enter') {state.pin();update();}
    }
  },true);
  document.addEventListener('keyup',event=>{if(event.key === 'Alt'){state.hold(false);update();}});
  window.addEventListener('blur',()=>{state.hold(false);update();});
  for(const event of ['scroll','resize']) window.addEventListener(event,()=>{
    if(scheduled) return; scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;position();});
  },{capture:true,passive:true});
  toggle.onclick=()=>{state.toggle();hover(lastElement);update();};
  close.onclick=()=>{state.close();update();};
  pin.onclick=()=>{if(state.pinned)state.follow();else state.pin();update();};
  return {
    begin(owner = 'default') { scope = owner; seen = new Set(); },
    bind(node,key,describe) {
      if(!node) return;
      nodes.set(node,key); entries.set(key,{node,describe,scope}); seen.add(key);
      node.dataset.inspection = key;
      if(!node.matches('button,input,select,textarea,a,[tabindex]')) node.tabIndex=0;
    },
    end() {
      for(const [key,entry] of entries) if(entry.scope === scope && !seen.has(key)) entries.delete(key);
      // A removed pinned occurrence stays absent. Never jump to the new row.
      update();
    },
    select(key) {state.pin(key);update();},
    dismiss() {state.close();update();},
    refresh:update
  };
}
