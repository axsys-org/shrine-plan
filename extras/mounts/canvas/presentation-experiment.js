// A comparison instrument over native compiler output. This module neither
// parses Grove nor decides whether a proposed presentation is applicable.
const node=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls??'';if(text!==undefined)el.textContent=text;return el;};
const button=(text,action,cls='secondary')=>{const el=node('button',cls,text);el.type='button';el.onclick=action;return el;};

export function createPresentationExperiment({root,request,onOpen,onClose}) {
  const drafts=new Map();
  let selected=null,serial=0,current=null;
  const instrument=node('section','presentation-experiment');instrument.hidden=true;
  instrument.setAttribute('aria-label','Presentation experiment');
  const heading=node('div','surface-heading');
  const title=node('h3','','Try a presentation change');
  function dismiss(){serial++;instrument.hidden=true;onClose?.(instrument);}
  const close=button('Back to subject',dismiss,'text-button');
  heading.append(title,close);
  const notice=node('p','subtle','Preview against this subject. The installed controls and input placements stay fixed.');
  const editing=node('details','presentation-source');
  const summary=node('summary','','Authored Grove');
  const source=node('textarea');source.setAttribute('aria-label','Presentation source');source.spellcheck=false;source.rows=16;
  editing.append(summary,source);
  const footer=node('div','experiment-footer');
  const status=node('span');status.setAttribute('role','status');
  const evaluate=button('Preview change',preview,'primary');
  footer.append(status,evaluate);
  const comparison=node('div','presentation-comparison');
  const coverage=node('p','coverage');
  instrument.append(heading,notice,editing,footer,comparison,coverage);root.append(instrument);
  instrument.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();dismiss();}});
  source.addEventListener('input',()=>{
    if(!current)return;
    current.source=source.value;current.version++;
    status.textContent='Not evaluated · ⌘ Enter to preview';
    comparison.classList.add('outdated');coverage.textContent=current.result?'Previous preview — source has changed.':'';
  });
  source.addEventListener('keydown',event=>{
    if((event.metaKey||event.ctrlKey)&&event.key==='Enter'){event.preventDefault();preview();}
  });
  function showFrame(label,view) {
    const section=node('section');section.append(node('h4','',label));
    const surface=node('div','native-presentation');
    if(view.diagnostic)surface.textContent=view.diagnostic;
    else surface.innerHTML=view.html;
    // Candidate and historical controls cannot accidentally operate live state.
    for(const control of surface.querySelectorAll('input,textarea,button,select'))control.disabled=true;
    for(const link of surface.querySelectorAll('a')){link.removeAttribute('href');link.tabIndex=-1;}
    section.append(surface);return section;
  }
  function renderResult(result,outdated=false) {
    comparison.replaceChildren(showFrame('Installed',result.before),showFrame('Preview',result.after));
    comparison.classList.toggle('outdated',outdated);
    coverage.textContent=outdated?'Previous preview — source has changed.':result.coverage;
  }
  async function open(descriptor) {
    if(!descriptor?.presentation)return;
    selected={...descriptor.presentation};const generation=++serial;
    const key=JSON.stringify([selected.target,selected.view,selected.revision]);
    current=drafts.get(key)??null;
    instrument.hidden=false;title.textContent=`${descriptor.title} · presentation`;
    status.textContent='Reading the installed Grove…';evaluate.disabled=true;
    if(current){source.value=current.source;if(current.result)renderResult(current.result,current.resultVersion!==current.version);}
    else {source.value='';comparison.replaceChildren();coverage.textContent='';}
    instrument.scrollTop=0;onOpen?.(instrument,selected.target);
    try {
      const result=await request('source',{target:selected.view,revision:selected.revision});
      if(generation!==serial)return;
      if(typeof result.editable_source!=='string')throw new Error('This source does not yet expose one editable presentation. The full source remains available in the inspector.');
      if(!current){current={source:result.editable_source,version:0,result:null,resultVersion:null};drafts.set(key,current);source.value=current.source;}
      status.textContent='Local draft · nothing installed';editing.open=true;source.focus({preventScroll:true});
    } catch(error){if(generation===serial)status.textContent=error.message;}
    finally{if(generation===serial){evaluate.disabled=!current;onOpen?.(instrument,selected.target);}}
  }
  async function preview() {
    if(!current||evaluate.disabled)return;
    const draft=current,selection=selected,generation=++serial,version=draft.version,text=draft.source;
    evaluate.disabled=true;status.textContent='Compiling with Grove…';
    try {
      const result=await request('evaluate',{kind:'presentation',...selection,source:text});
      if(generation!==serial||draft!==current)return;
      draft.result=result;draft.resultVersion=version;renderResult(result,version!==draft.version);
      if(version!==draft.version){status.textContent='Your newer typing is kept. This preview uses the submitted version.';}
      else {
        status.textContent='Preview ready · not installed';
        editing.open=false;instrument.scrollTop=0;
      }
    } catch(error){if(generation===serial)status.textContent=error.message;}
    finally{if(generation===serial)evaluate.disabled=false;}
  }
  return {open};
}
