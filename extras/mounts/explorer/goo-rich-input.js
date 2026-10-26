/* Shared display-v3 input. Durable values and actions remain in Grove/Foil. */
(function (root) {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  const text = runs => runs.map(run => run.lang.en.txt).join('');
  const canonical = myth => {
    const result = {};
    for (const key of Object.keys(myth).sort()) {
      if (key === '/sys/link') continue;
      const pail = clone(myth[key]);
      if (key === '/sys/modifiers') {
        if (pail.kind !== 'modifiers' || !Array.isArray(pail.value)) throw Error('Invalid modifiers');
        pail.value.sort(); if (!pail.value.length) continue;
      }
      result[key] = pail;
    }
    return JSON.stringify(result);
  };
  const run = (txt, myth = {}) => ({myth:clone(myth), lang:{en:{txt}}});
  function normalize(runs) {
    const out = [];
    for (const item of runs) {
      if (!item.lang.en.txt) continue;
      const previous = out.at(-1);
      if (previous && JSON.stringify(previous.myth) === JSON.stringify(item.myth)) previous.lang.en.txt += item.lang.en.txt;
      else out.push(clone(item));
    }
    return out.length ? out : [run('')];
  }
  function slice(runs, start, end) {
    let offset = 0; const out = [];
    for (const item of runs) {
      const length = item.lang.en.txt.length, a = Math.max(0,start-offset), b = Math.min(length,end-offset);
      if (b > a) out.push(run(item.lang.en.txt.slice(a,b),item.myth));
      offset += length;
    }
    return out;
  }
  const replace = (runs,a,b,insert) => normalize([...slice(runs,0,a),...insert,...slice(runs,b,text(runs).length)]);
  function palette(contract) {
    if (contract?.version !== 1 || contract.encoding !== 'goo-text-v1' || contract.maxBytes !== 65536 || !Array.isArray(contract.styles)) throw Error('Unsupported rich input contract');
    const options = new Map();
    for (const option of contract.styles) {
      const style = option.resolved?.textStyle;
      if (option.resolved?.version !== 1 || !style || !['Goo Sans','Goo Mono'].includes(style.family) ||
          !/^[a-f0-9]{64}$/.test(style.fontSHA256) || !['normal','italic'].includes(style.style) ||
          ![style.fontSize,style.lineHeight,style.letterSpacing,style.weight].every(Number.isFinite) ||
          style.fontSize<=0 || style.lineHeight<=0 || !/^#[0-9a-f]{6}$/i.test(option.resolved.foreground)) throw Error('Invalid rich input style');
      options.set(canonical(option.myth),option.resolved);
    }
    if (!options.has('{}')) throw Error('Missing default rich input style');
    return options;
  }
  function validate(runs, contract, options = palette(contract)) {
    if (!Array.isArray(runs) || runs.length > 10000 || new TextEncoder().encode(JSON.stringify(runs)).length > contract.maxBytes) throw Error('Document exceeds the rich input limit');
    for (const item of runs) {
      if (!item || Object.keys(item).sort().join() !== 'lang,myth' || !item.myth || Array.isArray(item.myth) ||
          Object.keys(item.lang||{}).join()!=='en' || Object.keys(item.lang.en||{}).join()!=='txt' ||
          typeof item.lang.en.txt!=='string' || /[^\x09\x0a\x0d\x20-\x7e]/.test(item.lang.en.txt)) throw Error('This text profile supports English/ASCII characters');
      if (!options.has(canonical(item.myth))) throw Error('Formatting is not supported by this editor');
      const link=item.myth['/sys/link'];
      if(link && !(typeof link.value==='string' && (link.kind==='path' && /^\/(?:[^\s/]+(?:\/[^\s/]+)*)?$/.test(link.value) || link.kind==='weblink' && /^https?:\/\/[^\s]+$/.test(link.value)))) throw Error('Invalid link metadata');
    }
    return runs;
  }
  function compatible(element,node) {
    if (!element.gooEditor) return !node?.editing;
    if (!node?.editing) return false;
    try {
      const options=palette(node.editing); validate(element.gooEditor.runs,node.editing,options);
      return [...element.gooEditor.options].every(([key,value])=>options.has(key) && options.get(key).textStyle.fontSHA256===value.textStyle.fontSHA256);
    } catch { return false; }
  }
  function create(element,node) {
    let contract=node.editing; const options=palette(contract);
    let runs=normalize(validate(clone(node.textRuns),contract,options)), typing=null, selection={a:0,b:0}, composing=null;
    const past=[], future=[], queuedInput=[];
    let revision=0, pending=false, hostContext=null, hostSignal=null, toolsKey='', toolsRequest=null, loadedTools='', commandButtons=[], choices=[], menuIndex=0, dismissed=false;
    element.classList.add('goo-rich-input'); element.removeAttribute('role');
    const area=element.querySelector('[data-goo-editable]');
    if(!area)throw Error('Rich input requires a native prepared editing viewport');
    area.classList.add('goo-rich-area');area.contentEditable='true';
    area.setAttribute('role','textbox'); area.setAttribute('aria-multiline','true'); area.setAttribute('aria-label','Document');
    area.spellcheck=false;
    const toolbar=document.createElement('div'); toolbar.className='goo-surface goo-rich-toolbar'; toolbar.hidden=true; toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','Text formatting');
    const menu=document.createElement('div');menu.className='goo-surface goo-rich-menu';menu.hidden=true;menu.setAttribute('role','menu');menu.setAttribute('aria-label','Block style');
    const notice=document.createElement('div');notice.className='goo-surface goo-rich-notice';notice.setAttribute('role','status');
    // Browser popovers supply top-layer placement only; their entire visual
    // content is a prepared Goo surface, including diagnostics.
    for(const popup of [toolbar,menu,notice]){popup.setAttribute('popover','manual');popup.style.inset='auto';popup.hidden=true;}
    const complain=error=>root.GooActions.feedback(notice,error.message,Math.min(window.innerWidth,element.clientWidth)).then(()=>{if(!notice.hidden&&element.isConnected)place(notice,false);});
    function readSelection() {
      const held=window.getSelection(); if(!held.rangeCount || !area.contains(held.anchorNode) || !area.contains(held.focusNode)) return null;
      const offset=(node,at)=>{const range=document.createRange();range.selectNodeContents(area);range.setEnd(node,at);return range.toString().length;};
      const anchor=offset(held.anchorNode,held.anchorOffset), focus=offset(held.focusNode,held.focusOffset);
      return {a:Math.min(anchor,focus),b:Math.max(anchor,focus),backward:anchor>focus};
    }
    function restore(value=selection) {
      const length=text(runs).length;
      const point=offset=>{
        const walker=document.createTreeWalker(area,NodeFilter.SHOW_TEXT);let current;
        while((current=walker.nextNode())) { if(offset<=current.length)return [current,offset];offset-=current.length; }
        return [area,area.childNodes.length];
      };
      const a=point(Math.min(value.a,length)),b=point(Math.min(value.b,length));
      const held=window.getSelection();held.setBaseAndExtent(...(value.backward?b:a),...(value.backward?a:b));
      selection={...value,a:Math.min(value.a,length),b:Math.min(value.b,length)};
    }
    function style(span,myth) {
      const resolved=options.get(canonical(myth)), s=resolved.textStyle;
      Object.assign(span.style,{fontFamily:`"${s.family}"`,fontSize:`${s.fontSize}px`,fontWeight:String(s.weight),fontStyle:s.style,lineHeight:`${s.lineHeight}px`,letterSpacing:`${s.letterSpacing}px`,color:resolved.foreground});
      if(myth['/sys/modifiers']?.value.includes('underline'))span.style.textDecoration='underline';
      if(myth['/sys/link']) {span.style.backgroundColor=contract.linkStyle?.highlight?.fill||'transparent';span.title=myth['/sys/link'].value;}
    }
    function resizeBlock(){
      if(['rich-block','rich-heading','rich-code'].includes(node.slot)){area.style.height='auto';element.style.height=`${Math.max(node.box.height,area.scrollHeight+node.textStyle.insetY)}px`;}
    }
    function paint(focus=false) {
      area.replaceChildren();
      for(const item of runs) {const span=document.createElement('span');span.textContent=item.lang.en.txt;style(span,item.myth);area.append(span);}
      // An empty final line needs a caret box, without adding a stored character.
      if(!text(runs) || text(runs).endsWith('\n'))area.append(document.createElement('br'));
      area.dataset.empty=String(!text(runs));
      resizeBlock();
      if(focus){area.focus({preventScroll:true});restore();}
    }
    function checkpoint(){past.push({runs:clone(runs),selection:{...selection},typing:clone(typing)});if(past.length>100)past.shift();future.length=0;}
    function changed(){revision++;dismissed=false;root.GooActions.feedback(notice,'');element.dispatchEvent(new Event('input',{bubbles:true}));widgets();}
    function apply(next,at,remember=true){validate(next,contract,options);if(remember)checkpoint();runs=normalize(next);selection={a:at,b:at};paint(true);changed();}
    function metadata(){if(typing)return clone(typing);const pos=Math.max(0,selection.a-(selection.a?1:0));return clone(slice(runs,pos,pos+1)[0]?.myth||{});}
    function insert(value){const normalized=value.replace(/\r\n?/g,'\n');apply(replace(runs,selection.a,selection.b,[run(normalized,metadata())]),selection.a+normalized.length);}
    function undo(redo=false){const from=redo?future:past,to=redo?past:future;if(!from.length)return;to.push({runs:clone(runs),selection:{...selection},typing:clone(typing)});const held=from.pop();runs=held.runs;selection=held.selection;typing=held.typing;paint(true);changed();}
    // Command surfaces are ordinary Grove views, prepared by Goo. The host only
    // anchors them to the platform selection and binds their declared commands.
    async function ensureTools() {
      if(!hostContext || hostSignal?.aborted)return;
      if(loadedTools===toolsKey)return;
      if(toolsRequest)return toolsRequest;
      const key=toolsKey, signal=hostSignal, context=hostContext;
      const prepare=async(popup,slot,width)=>{
        const data=await root.GooActions.load(context.target,{slot,context:{...context.renderContext,width,layout:undefined},signal});
        if(data.description || !data.display || data.controls?.length)throw Error('Text tools must be a pure Goo presentation');
        const content=document.createElement('div');content.innerHTML=data.html;
        const buttons=[];
        for(const node of data.display.nodes)if(node.kind==='button') {
          if(!node.slot.startsWith('/sys/edit/'))throw Error('Invalid native text command');
          const button=[...content.querySelectorAll('[data-node]')].find(e=>e.dataset.node===node.id);
          if(!button || button.tagName!=='BUTTON')throw Error('Missing prepared command control');
          button.dataset.textCommand=node.slot.slice('/sys/edit/'.length);
          button.gooAnchor=document.createComment('native command');button.before(button.gooAnchor);
          button.addEventListener('pointerdown',event=>event.preventDefault());
          button.addEventListener('click',event=>{event.stopPropagation();dispatch(button.dataset.textCommand);});
          buttons.push(button);
        }
        return {popup,content,buttons};
      };
      const request=Promise.all([
        prepare(toolbar,'/sys/slot/text_toolbar',Math.min(400,window.innerWidth-32)),
        prepare(menu,'/sys/slot/text_commands',Math.min(260,window.innerWidth-32))
      ]).then(results=>{
        if(signal.aborted || key!==toolsKey)return;
        for(const {popup,content,buttons} of results){popup.replaceChildren(content);if(popup===menu)commandButtons=buttons;}
        loadedTools=key;widgets();
      }).catch(error=>{if(error.name!=='AbortError')complain(error);}).finally(()=>{if(toolsRequest===request)toolsRequest=null;});
      toolsRequest=request;return request;
    }
    async function dispatch(command) {
      if(pending || composing || element.gooFrozen)return;
      selection=readSelection()||selection;
      if(hostContext?.textCommand && !(command==='paragraph-break'&&node.slot==='rich-code') && !['bold','italic','underline','clear'].includes(command)){
        try { if(await hostContext.textCommand(command,{...selection})!==false)return; } catch(error) { complain(error); return; }
      }
      const before=revision, range={...selection}, signal=hostSignal;
      pending=true;area.setAttribute('aria-busy','true');toolbar.hidden=menu.hidden=true;
      try {
        const response=await fetch('/goo/text-command',{method:'POST',signal,body:new URLSearchParams({
          command,value:JSON.stringify(runs),start:String(range.a),end:String(range.b),typing:JSON.stringify(metadata())
        })});
        if(!response.ok)throw Error(await response.text());
        const result=await response.json();
        signal?.throwIfAborted();
        if(before!==revision || composing || !element.isConnected)throw Error('Text changed while the command was running. Choose the command again.');
        validate(result.textRuns,contract,options);validate([run('',result.typing)],contract,options);
        if(result.version!==1 || !Number.isSafeInteger(result.start) || !Number.isSafeInteger(result.end) || result.start<0 || result.end<result.start || result.end>text(result.textRuns).length)throw Error('Invalid native text-command result');
        apply(result.textRuns,result.start);typing=result.typing;selection={a:result.start,b:result.end};restore();
      }catch(error){if(error.name!=='AbortError')complain(error);}
      finally{
        pending=false;area.removeAttribute('aria-busy');
        // Compatible repreparation may rebind this same draft. Detached owners
        // must never replay queued events into a replacement editor.
        if(element.isConnected){while(!pending&&queuedInput.length)queuedInput.shift()();}
        else queuedInput.length=0;
        widgets();
      }
    }
    function place(popup,above){
      if(!popup.matches(':popover-open'))popup.showPopover();
      const held=window.getSelection(),fallback=area.getBoundingClientRect();
      const selected=held.rangeCount?held.getRangeAt(0).getBoundingClientRect():fallback;
      const rect=selected.width||selected.height?selected:fallback;
      popup.style.left=`${Math.max(0,Math.min(rect.left,window.innerWidth-popup.offsetWidth))}px`;
      popup.style.top=`${Math.max(0,Math.min(above?rect.top-popup.offsetHeight:rect.bottom,window.innerHeight-popup.offsetHeight))}px`;
    }
    function widgets(){
      if(composing||pending)return;
      const current=readSelection();if(!current){toolbar.hidden=true;menu.hidden=true;return;}selection=current;
      const prefix=text(runs).slice(0,selection.a),line=prefix.slice(prefix.lastIndexOf('\n')+1);
      const slash=selection.a===selection.b && /^\/([a-z ]*)$/i.test(line) && !dismissed;
      if(loadedTools!==toolsKey){toolbar.hidden=menu.hidden=true;if(selection.a!==selection.b||slash)ensureTools();return;}
      toolbar.hidden=selection.a===selection.b;if(!toolbar.hidden)place(toolbar,true);
      choices=commandButtons.filter(button=>button.textContent.toLowerCase().includes(line.slice(1).trim().toLowerCase()));commandButtons.forEach(button=>{if(choices.includes(button)){if(!button.isConnected)button.gooAnchor.after(button);}else button.remove();});menu.hidden=!slash||!choices.length;
      if(!menu.hidden){menuIndex=Math.min(menuIndex,choices.length-1);choices.forEach((button,index)=>{button.classList.toggle('highlight',index===menuIndex);button.setAttribute('aria-current',String(index===menuIndex));});place(menu,false);}
    }
    function input(kind,data) {
      selection=readSelection()||selection;
      try {
        if(kind==='insertText'||kind==='insertReplacementText')insert(data||'');
        else if(kind==='insertParagraph'||kind==='insertLineBreak') {
          if(kind==='insertLineBreak')insert('\n');else dispatch('paragraph-break');
        } else if(kind==='deleteContentBackward'||kind==='deleteContentForward'||kind==='deleteWordBackward'||kind==='deleteWordForward'||kind==='deleteByCut') {
          let {a,b}=selection;const source=text(runs);
          if(kind==='deleteContentBackward' && a===0 && b===0 && hostContext?.textCommand){dispatch('merge');return;}
          if(a===b){if(kind==='deleteWordBackward')a=source.slice(0,a).replace(/\s*\S+\s*$/,'').length;else if(kind==='deleteWordForward'){const m=/^\s*\S+\s*/.exec(source.slice(b));b+=m?m[0].length:0;}else if(kind==='deleteContentBackward')a=Math.max(0,a-1);else b=Math.min(source.length,b+1);}
          apply(replace(runs,a,b,[]),a);typing=null;
        } else if(kind==='historyUndo'||kind==='historyRedo')undo(kind==='historyRedo');
        else if(['formatBold','formatItalic','formatUnderline'].includes(kind))dispatch(kind.slice(6).toLowerCase());
      }catch(error){complain(error);}
     }
    area.addEventListener('beforeinput',event=>{
      if(element.gooFrozen){event.preventDefault();return;}
      if(composing||event.isComposing)return;event.preventDefault();
      const kind=event.inputType,data=event.data;
      if(pending)queuedInput.push(()=>input(kind,data));else input(kind,data);
    });
    area.addEventListener('keydown',event=>{
      if(element.gooFrozen){event.preventDefault();return;}
      if(composing)return;selection=readSelection()||selection;
      if(pending && (event.ctrlKey||event.metaKey||['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','Escape','Tab'].includes(event.key))){event.preventDefault();return;}
      if(!menu.hidden && ['ArrowDown','ArrowUp','Enter','Escape'].includes(event.key)) {event.preventDefault();event.stopPropagation();if(event.key==='Escape'){dismissed=true;menu.hidden=true;return;}if(event.key==='Enter'){dispatch(choices[menuIndex].dataset.textCommand);return;}menuIndex=(menuIndex+(event.key==='ArrowDown'?1:choices.length-1))%choices.length;widgets();return;}
      if((event.ctrlKey||event.metaKey)&&!event.altKey){const key=event.key.toLowerCase();if(['b','i','u','z','y'].includes(key)){event.preventDefault();try{if(key==='z'||key==='y')undo(key==='y'||event.shiftKey);else dispatch({b:'bold',i:'italic',u:'underline'}[key]);}catch(error){complain(error);}}}
      if(hostContext?.documentNavigate && selection.a===selection.b && ((event.key==='ArrowUp'&&selection.a===0)||(event.key==='ArrowDown'&&selection.b===text(runs).length))){event.preventDefault();hostContext.documentNavigate(event.key==='ArrowUp'?-1:1);}
      if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))typing=null;
    });
    area.addEventListener('paste',event=>{event.preventDefault();if(element.gooFrozen)return;const value=event.clipboardData.getData('text/plain');if(pending)queuedInput.push(()=>input('insertText',value));else input('insertText',value);});
    area.addEventListener('cut',event=>{if(pending||element.gooFrozen){event.preventDefault();return;}selection=readSelection()||selection;if(selection.a===selection.b)return;event.preventDefault();event.clipboardData.setData('text/plain',text(runs).slice(selection.a,selection.b));apply(replace(runs,selection.a,selection.b,[]),selection.a);});
    area.addEventListener('drop',event=>event.preventDefault());
    area.addEventListener('compositionstart',()=>{selection=readSelection()||selection;composing={...selection};toolbar.hidden=menu.hidden=true;});
    area.addEventListener('compositionend',event=>{selection=composing||selection;composing=null;try{insert(event.data||'');}catch(error){paint(true);complain(error);}});
    area.addEventListener('input',event=>{if(event.target===area)event.stopPropagation();});
    area.addEventListener('pointerdown',event=>{if(pending)event.preventDefault();});
    area.addEventListener('pointerup',()=>{typing=null;widgets();});area.addEventListener('keyup',widgets);
    // Document listeners exist only while this input has an admitted binding.
    function bind(ownerSignal,context){
      hostSignal=ownerSignal;hostContext=context;
      if(!toolbar.isConnected)document.body.append(toolbar,menu,notice);
      const key=JSON.stringify([context.target,context.snapshot.publication,context.renderContext.textScale,context.renderContext.direction]);
      if(key!==toolsKey){toolsKey=key;loadedTools='';commandButtons=[];toolbar.replaceChildren();menu.replaceChildren();toolsRequest=null;}

      const lifetime=new AbortController(),signal=lifetime.signal;
      const detached=new MutationObserver(()=>{if(!element.isConnected){lifetime.abort();for(const popup of [toolbar,menu,notice])popup.remove();}});
      detached.observe(document.body,{childList:true,subtree:true});
      signal.addEventListener('abort',()=>detached.disconnect(),{once:true});
      ownerSignal.addEventListener('abort',()=>lifetime.abort(),{once:true});
      document.addEventListener('pointerdown',event=>{if(!element.contains(event.target)&&!toolbar.contains(event.target)&&!menu.contains(event.target))toolbar.hidden=menu.hidden=true;},{signal});
      document.addEventListener('selectionchange',()=>{if(element.isConnected)widgets();},{signal});
      window.addEventListener('scroll',()=>{toolbar.hidden=menu.hidden=true;},{capture:true,signal});
    }
    Object.defineProperty(element,'value',{get:()=>JSON.stringify(runs),set:value=>{const next=normalize(validate(JSON.parse(value),contract,options));if(JSON.stringify(next)===JSON.stringify(runs))return;const focused=area.contains(document.activeElement);selection=readSelection()||selection;runs=next;typing=null;revision++;paint(focused);}});
    element.gooEditor={get runs(){return runs;},get pending(){return pending;},options,bind,reconfigure(nextNode){node=nextNode;const next=palette(node.editing);options.clear();for(const [key,value] of next)options.set(key,value);contract=node.editing;area.style.height=`${Math.max(0,node.box.height-node.textStyle.insetY)}px`;[...area.querySelectorAll('span')].forEach((span,i)=>style(span,runs[i].myth));resizeBlock();},selection:()=>readSelection()||selection,restore,area};
    element.setAttribute('value',JSON.stringify(runs));paint();
    return element;
  }
  const api={text,run,normalize,slice,replace,canonical,palette,validate,compatible,create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.GooRichInput=api;
})(typeof window==='undefined'?globalThis:window);
