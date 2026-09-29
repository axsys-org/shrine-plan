'use strict';
(function(host){
  const {VERSION,finite,decodeInput}=typeof module!=='undefined'&&module.exports?require('./protocol.js'):host.GooProtocol;
  async function renderDocument(doc, onResult=()=>{}, options={}) {
    const input=doc.getElementById('goo-render-input');if(!input)return ()=>{};
    const config=decodeInput(JSON.parse(input.textContent)),target=doc.getElementById('goo-render-root');
    const scale=options.textScale??1;
    if(!Number.isFinite(scale)||scale<=0||scale>10)throw Error('Text scale must be >0 and <=10');
    doc.documentElement.dir=options.direction??'ltr';
    doc.documentElement.style.setProperty('--goo-text-scale',scale);
    if(options.contentWidth!==undefined)target.style.width=finite(options.contentWidth,'Content width')+'px';
    let stopped=false,lastWidth=-1,revision=0,request;
    async function render(force=false) {
      if(stopped)return;
      // The only DOM measurement left is the host's available container width.
      const width=options.contentWidth??target.getBoundingClientRect().width;
      if(!force&&width===lastWidth)return;lastWidth=width;
      const current=++revision;request?.abort();request=new AbortController();
      try {
        const response=await host.fetch('/layout',{method:'POST',headers:{'content-type':'application/json'},
          body:JSON.stringify({version:VERSION,tree:config.tree,width,textScale:scale}),signal:request.signal});
        if(!response.ok)throw Error(await response.text());
        const data=await response.json();if(stopped||revision!==current)return;
        const result=data.measurement;
        const previousInputs=new Map([...target.querySelectorAll('input[data-node]')].map(e=>[e.dataset.node,e.value]));
        const focused=target.contains(doc.activeElement)?doc.activeElement:null;
        const focusId=focused?.dataset.node;
        const selection=focused?.tagName==='INPUT'?[focused.selectionStart,focused.selectionEnd]:null;
        target.style.outlineStyle=result.plan?'solid':'none';
        if(typeof data.html!=='string')throw Error('Missing server-rendered HTML');
        target.innerHTML=data.html;
        target.firstElementChild?.setAttribute('dir',options.direction??'ltr');
        for(const e of target.querySelectorAll('[data-node]')) {
          if(e.tagName==='INPUT'&&previousInputs.has(e.dataset.node))e.value=previousInputs.get(e.dataset.node);
          if(focusId===e.dataset.node){e.focus({preventScroll:true});if(selection)e.setSelectionRange(...selection);}
        }
        target.dataset.layoutReady='true';onResult(result);
      } catch(e){if(!stopped&&revision===current&&e.name!=='AbortError'){target.textContent='Layout error: '+e.message;onResult({error:e.message});}}
    }
    // Wait for the pinned faces before painting; geometry itself is font-file based.
    if(doc.fonts){await Promise.all([...[400,520,550,620,650,750].map(w=>doc.fonts.load(`${w} 14px "Goo Sans"`)),doc.fonts.load('11px "Goo Mono"'),doc.fonts.load('italic 17px "Goo Sans"')]);await doc.fonts.ready;}
    await render();
    const observer=new host.ResizeObserver(()=>render());observer.observe(target);
    const fontsChanged=()=>render(true);doc.fonts?.addEventListener('loadingdone',fontsChanged);
    return ()=>{stopped=true;++revision;request?.abort();observer.disconnect();doc.fonts?.removeEventListener('loadingdone',fontsChanged);};
  }
  const api={renderDocument};
  if(typeof module!=="undefined"&&module.exports)module.exports=api;else host.GooReference=api;
})(typeof window==='undefined'?globalThis:window);
