import {SurfaceDrafts, basis} from './surface-state.mjs';

const element=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls??'';if(text!==undefined)node.textContent=text;return node;};
const button=(text,fn,cls='secondary')=>{const node=element('button',cls,text);node.type='button';node.onclick=fn;return node;};

// Render authored native frames. No domain-specific action names or evaluators.
export function createNativeSurfaces({root,inspector,request,onMutation,onError,embedded=false,scope='native-surfaces',onFrame}) {
  const drafts=new SurfaceDrafts();
  let frame=null, selectedSlot='/sys/slot/detail', selectedView=null, generation=0, navigation=0, signature='', inFlight=false,noticeTimer;
  const heading=element('div','native-heading');
  const back=button('Workspace',()=>read(), 'text-button');
  const title=element('h2','','Your workspace');
  const add=button('New concept',create);
  heading.append(back,title,add);
  heading.hidden=embedded;
  const contents=element('div','native-contents');
  const message=element('p','native-notice');message.hidden=true;message.setAttribute('role','status');
  root.append(heading,message,contents);

  async function read(target,options={}) {
    if(target!==frame?.target)navigation++;
    const current=++generation;
    const value=await request('present',{...(target?{target}:{}),...(embedded?{width:'316'}:{}),...options});
    if(current!==generation)return;
    if(value.protocol!=='canvas-surface/1')throw new Error('This world does not expose native surfaces.');
    if(frame?.target!==value.target) {selectedSlot='/sys/slot/detail';selectedView=null;signature='';}
    frame=value;render();onFrame?.(value);return value;
  }
  function notify(text) {clearTimeout(noticeTimer);message.textContent=text;message.hidden=!text;if(text==='Saved.')noticeTimer=setTimeout(()=>{message.hidden=true;},2400);}
  function reject(error) {notify(error.message);onError?.(error);}
  async function create() {
    if(inFlight)return;
    // Creation leaves an honest concept, not an invented working application.
    inFlight=true;add.disabled=true;
    try {
      const value=await request('construct',{label:'Untitled concept'});
      onMutation(value.frame);
      await read(value.created);
      selectedSlot='/sys/slot/edit';signature='';render();
      contents.querySelector('input')?.focus();
    } catch(error) {reject(error);} finally {inFlight=false;add.disabled=false;signature='';render();}
  }
  function descriptor(view,occurrence) {
    const reads=occurrence?.reads??[];
    const fields=view.fields.filter(field=>reads.includes(field.slot)||field.slot===occurrence?.slot);
    return {title:fields.length===1?fields[0].name:frame.label||'Native subject', kind:occurrence?.kind==='action'?'Declared action':'Native presentation',
      subject:frame.subject,basis:frame.expected,source:view.id,sourceRevision:view.revision,
      presentation:frame.capabilities?.presentation_refinement?{target:frame.target,view:view.id,revision:view.revision,publication:frame.publication,...(frame.width?{width:frame.width}:{})}:null,
      description:occurrence?`Declared ${occurrence.kind} in this Grove view.`:'This presentation was evaluated by the native owner.',
      fields:[['Presentation',view.id],['Revision',view.revision],['Role',view.role],
        ...(occurrence?[['Source position',`${occurrence.line}:${occurrence.column}`],['Control route',occurrence.control]]:[]),
        ...fields.flatMap(field=>[[field.name,field.value??'Absent'],['Exact slot',field.slot],['Opaque key',field.slot_key]])]};
  }
  function render() {
    if(!frame)return;
    // Global journal progress is a paging basis, not a visual change. An
    // unrelated mutation must not replace focused controls or interrupt IME.
    const key=JSON.stringify([{...frame,epoch:undefined},selectedSlot,selectedView]);
    if(key===signature)return;
    signature=key;
    const active=document.activeElement;
    const focus=contents.contains(active)?{id:active.closest('[data-node]')?.dataset.node,start:active.selectionStart,end:active.selectionEnd}:null;
    inspector.begin(scope);
    title.textContent=frame.label||'Your workspace';
    contents.replaceChildren();
    back.hidden=frame.target.endsWith('/app/workspace');
    if(!frame.catalog_complete||frame.more_views) {
      contents.append(element('p','native-notice','View discovery reached its current limit. More applicable presentations may exist.'));
    }
    const views=frame.views;
    let view=views.find(item=>item.id===selectedView&&item.slot===selectedSlot)??views.find(item=>item.slot===selectedSlot);
    if(!view&&views.length) {view=views.find(item=>item.slot==='/sys/slot/detail')??views[0];selectedSlot=view.slot;}
    if(views.length>1&&!embedded) {
      const nav=element('nav','native-view-switcher');nav.setAttribute('aria-label','Subject presentations');
      for(const item of views) {
        const label=item.slot==='/sys/slot/edit'?'Edit':item.slot==='/sys/slot/detail'?'View':item.slot;
        const control=button(label,()=>{selectedSlot=item.slot;selectedView=item.id;signature='';render();},'text-button');
        control.setAttribute('aria-pressed',String(item.id===view?.id));control.title=item.id;nav.append(control);
      }
      contents.append(nav);
    }
    if(view)renderView(view);
    if(frame.children.length) {
      const list=element('div','native-subjects');
      for(const child of frame.children) {
        const node=button(child.label,()=>read(child.id).catch(reject),'native-subject');
        inspector.bind(node,`native-child:${child.id}`,()=>({title:child.label,kind:'Native subject',subject:child.id,basis:frame.epoch,description:'Existing child in the native namespace.',fields:[]}));
        list.append(node);
      }
      contents.append(list);
    } else if(!view) {
      const empty=element('div','native-empty');
      empty.append(element('p','','Start with something you want to make.'),element('p','subtle','A concept is a place to keep its intent. Its behavior can grow around it.'));
      empty.append(button('Create a concept',create,'primary'));
      contents.append(empty);
    }
    if(frame.next_children) contents.append(button('Next subjects',()=>read(frame.target,{children:frame.next_children,epoch:frame.epoch}).catch(reject)));
    inspector.end();
    if(focus?.id) {
      const node=[...contents.querySelectorAll('[data-node]')].find(node=>node.dataset.node===focus.id);
      const control=node?.matches('input,textarea,button')?node:node?.querySelector('input,textarea,button');
      control?.focus({preventScroll:true});
      if(control?.setSelectionRange&&focus.start!==null)control.setSelectionRange(focus.start,focus.end);
    }
  }
  function renderView(view) {
    const panel=element('article','native-presentation');panel.dataset.view=view.id;
    if(view.diagnostic) {panel.append(element('p','native-notice',view.diagnostic));contents.append(panel);return;}
    // The native Goo renderer escapes values and emits the component tree.
    panel.innerHTML=view.html;
    const nodes=new Map([...panel.querySelectorAll('[data-node]')].map(node=>[node.dataset.node,node]));
    const controls=view.occurrences??[];
    const initial={};
    for(const item of controls) {
      const node=nodes.get(item.id);
      if(!node)continue;
      inspector.bind(node,`native:${frame.target}:${view.id}:${view.revision}:${item.id}`,()=>descriptor(view,item));
      if(item.kind!=='input')continue;
      const input=node.matches('input,textarea')?node:node.querySelector('input,textarea');
      if(!input)continue;
      initial[item.slot]=input.value;
    }
    const draft=drafts.get(frame,view);
    for(const item of controls) {
      const node=nodes.get(item.id);
      if(!node)continue;
      if(item.kind==='input') {
        const input=node.matches('input,textarea')?node:node.querySelector('input,textarea');
        if(!input)continue;
        input.setAttribute('aria-label',view.fields.find(field=>field.slot===item.slot)?.name??item.slot);
        if(draft&&Object.hasOwn(draft.inputs,item.slot))input.value=draft.inputs[item.slot];
        input.oninput=()=>{drafts.edit(frame,view,item.slot,input.value,initial);notify(controls.filter(c=>c.kind==='action'&&c.invoke).length===1?'Unsaved changes · ⌘ Enter to save':'Unsaved changes');};
      }
      if(item.kind==='action') {
        const action=node.matches('button')?node:node.querySelector('button');
        if(!action)continue;
        action.type='button';action.disabled=inFlight;
        action.onclick=()=>perform(view,item,panel,initial).catch(reject);
      }
    }
    panel.addEventListener('keydown',event=>{
      if((event.metaKey||event.ctrlKey)&&event.key==='Enter') {
        const actions=controls.filter(item=>item.kind==='action'&&item.invoke);
        if(actions.length===1){event.preventDefault();perform(view,actions[0],panel,initial).catch(reject);}
      }
    });
    contents.append(panel);
    if(drafts.stale(frame,view)) {
      const review=element('details','native-review');
      review.append(element('summary','','This subject changed. Review your retained draft.'));
      const table=element('table');
      const head=element('tr');for(const label of ['Field','When you started','Current','Your draft'])head.append(element('th','',label));table.append(head);
      for(const [slot,value] of Object.entries(draft.inputs)) {
        const row=element('tr');for(const cell of [slot,draft.original[slot],initial[slot],value])row.append(element('td','',cell??'Absent'));table.append(row);
      }
      review.append(table,button('Use my draft on the current subject',()=>{drafts.review(frame,view);signature='';notify('Current basis selected. Save still requires native validation.');render();}));
      contents.append(review);
    }
  }
  async function perform(view,control,panel,initial) {
    if(inFlight)return;
    if(!control.invoke) {
      if(control.become){selectedSlot=control.slot;selectedView=null;signature='';render();focusInput();}
      return;
    }
    if(drafts.stale(frame,view)) {
      const review=contents.querySelector('.native-review');
      if(review) {review.open=true;review.querySelector('summary')?.focus({preventScroll:true});}
      throw new Error('Review the newer subject before applying this retained draft.');
    }
    const inputs={...initial,...drafts.get(frame,view)?.inputs};
    const subject=frame;
    const selection=navigation;
    const draftRevision=drafts.get(subject,view)?.revision??0;
    const body={target:subject.target,subject:subject.subject,view:view.id,control:control.control,...basis(subject),inputs};
    inFlight=true;panel.querySelectorAll('button').forEach(node=>node.disabled=true);
    try {
      const value=await request('perform',body);
      drafts.clear(subject,view,draftRevision);onMutation(value);
      if(navigation!==selection||frame.target!==subject.target)return;
      if(control.become&&!drafts.get(subject,view)){selectedSlot=control.slot;selectedView=null;}
      signature='';await read(subject.target);
      notify(drafts.get(subject,view)?'Saved the submitted version. Your newer typing is still here.':'Saved.');
    } catch(error) {
      // Never retry a mutation with a new identity, and never erase its draft.
      if(error.status===409&&navigation===selection&&frame.target===subject.target) {signature='';await read(subject.target);}
      throw error;
    } finally {inFlight=false;signature='';render();}
  }
  function focusInput(){contents.querySelector('input,textarea')?.focus({preventScroll:true});}
  return {read,refresh:()=>read(frame?.target),
    edit:()=>{selectedSlot='/sys/slot/edit';selectedView=null;signature='';render();focusInput();},
    destroy:()=>{generation++;inspector.begin(scope);inspector.end();root.replaceChildren();},
    show:()=>{root.hidden=false;},hide:()=>{root.hidden=true;}};
}
