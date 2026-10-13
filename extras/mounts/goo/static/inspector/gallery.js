// A bounded, lazy render queue keeps the entire catalogue browseable while
// preserving one isolated style/measurement epoch per example.
'use strict';
const $ = s => document.querySelector(s);
const controls = {view:$('#gallery-view'),budget:$('#gallery-budget'),width:$('#gallery-width'),uniform:$('#gallery-uniform')};
const states = [...document.querySelectorAll('tr[data-example]')].map(row => {
  const meta=JSON.parse(row.dataset.case), settings=meta?.settings??{};
  const widths=settings.widths??[180,320,720];
  const select=row.querySelector('.case-width');
  for(const w of widths) select.add(new Option(`${w}px`,String(w)));
  select.value=String(widths.includes(320)?320:widths[Math.min(1,widths.length-1)]);
  const category=/^a\d{2}-/.test(row.dataset.example)?'a':/^g\d{3}-/.test(row.dataset.example)?'g':'other';
  const search=row.querySelector('td').textContent.toLowerCase();
  const s={row,settings,select,category,search,near:false,dirty:true,revision:0,stop:()=>{},abort:null};
  select.addEventListener('change',()=>invalidate(s));
  return s;
});
const queue=new Set(); let active=0;
function status(s,message,error=false) {
  const p=s.row.querySelector('.case-status');p.textContent=message;
  p.classList.toggle('text-danger',error);
}
function enqueue(s) {
  if(s.near && !s.row.hidden && s.dirty) {queue.add(s);pump();}
}
function invalidate(s) {
  s.revision++;s.dirty=true;s.stop();s.abort?.abort();
  status(s,'Waiting to render…');enqueue(s);
}
function pump() {
  while(active<3 && queue.size) {
    const s=queue.values().next().value;queue.delete(s);
    if(!s.near || s.row.hidden || !s.dirty)continue;
    s.dirty=false;active++;
    render(s).finally(()=>{active--;pump();});
  }
}
async function render(s) {
  const rev=s.revision, current=()=>rev===s.revision;
  const controller=new AbortController();s.abort=controller;
  const width=Number(controls.width.value||s.select.value);
  const budget=Number(controls.budget.value==='case'?(s.settings.budget??2):controls.budget.value);
  const view=controls.view.value==='case'?(s.settings.view??'/sys/slots/summary'):controls.view.value;
  const direction=s.settings.direction??'ltr',textScale=s.settings.textScale??1;
  s.select.disabled=controls.width.value!=='';
  s.row.querySelector('.case-settings').textContent=`${view.split('/').pop()} · ${['minimal','compact','full'][budget]} · ${direction} · ${textScale}× text`;
  s.row.querySelector('a').href=`/?${new URLSearchParams({example:s.row.dataset.example,view})}`;
  if(!Number.isFinite(width)||width<1||width>5000) {status(s,'Choose a content width between 1 and 5000px.',true);return;}
  status(s,'Compiling…');
  try {
    const query=new URLSearchParams({view,budget,uniform:controls.uniform.checked?'1':'0',outputOnly:'1',hiddenPaths:JSON.stringify(s.settings.hiddenPaths??[])});
    const response=await fetch(`/lower?${query}`,{method:'POST',body:s.row.querySelector('.gallery-source').textContent,headers:{'content-type':'text/plain; charset=utf-8'},signal:controller.signal});
    if(!response.ok)throw Error(await response.text());
    const data=await response.json();if(!current())return;
    const container=s.row.querySelector('.gallery-preview');
    s.stop();container.replaceChildren();
    if(data.errors||data.crashed) {
      status(s,data.crashed?`Compiler error in ${data.crashed}`:`${data.errors} source error(s)`,true);
      const diagnostics=document.createElement('ul');diagnostics.className='diags text-danger';diagnostics.innerHTML=data.diagnostics;container.append(diagnostics);return;
    }
    const frame=document.createElement('iframe');frame.title=`Rendered ${s.row.dataset.example}`;
    frame.setAttribute('sandbox','allow-same-origin');frame.style.width=(width+48)+'px';frame.style.height='160px';
    await new Promise((resolve,reject)=>{
      const abort=()=>{frame.remove();resolve();};
      controller.signal.addEventListener('abort',abort,{once:true});
      frame.addEventListener('load',async()=>{
        try {
          if(!current())return;
          const stop=await GooReference.renderDocument(frame.contentDocument,result=>{
            if(!current())return;
            if(result.error){status(s,result.error,true);return;}
            const height=result.plan?.h??0;
            frame.style.height=Math.max(96,Math.min(600,Math.ceil(height)+56))+'px';
            status(s,result.plan?`${result.width}px content · ${Math.round(height*100)/100}px high · ${result.trace.length} edges`:'Empty visible tree');
          },{contentWidth:width,direction,textScale});
          if(current())s.stop=stop;else stop();
        } catch(e) {reject(e);} finally {controller.signal.removeEventListener('abort',abort);resolve();}
      },{once:true});
      frame.srcdoc=data.output;container.append(frame);
    });
  } catch(e) {if(current()&&e.name!=='AbortError')status(s,e.message,true);}
}
const observer=new IntersectionObserver(entries=>{
  for(const entry of entries){const s=states.find(s=>s.row===entry.target);s.near=entry.isIntersecting;enqueue(s);}
},{rootMargin:'600px'});
states.forEach(s=>observer.observe(s.row));
for(const control of Object.values(controls))control.addEventListener('change',()=>states.forEach(invalidate));
function filterExamples() {
  const query=$('#gallery-filter').value.toLowerCase().trim();
  const category=$('#gallery-category').value;
  let shown=0;
  for(const s of states) {
    s.row.hidden=(category!=='all'&&s.category!==category)||!s.search.includes(query);
    if(!s.row.hidden)shown++;
    enqueue(s);
  }
  $('#gallery-count').textContent=shown===states.length?`All examples · ${shown}`:`Examples · ${shown} / ${states.length}`;
}
$('#gallery-filter').addEventListener('input',filterExamples);
$('#gallery-category').addEventListener('change',filterExamples);
$('#gallery-refresh').addEventListener('click',()=>location.reload());
window.addEventListener('pagehide',()=>{observer.disconnect();states.forEach(s=>{s.stop();s.abort?.abort();});});
let version=null;
setInterval(async()=>{
  try {
    const res=await fetch('/version',{cache:'no-store'});const next=await res.json();
    if(version&&next.assets!==version.assets){location.reload();return;}
    if(version&&next.boot!==version.boot)states.forEach(invalidate);
    version=next;
  } catch { /* Each row retains its current output while the server restarts. */ }
},1500);
