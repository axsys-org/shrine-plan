async function behaviorCall(body){const r=await fetch('/api/behavior',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),result=await r.json();if(!r.ok)throw Error(result.error||'Native computation unavailable');return result;}
const behaviorValues=new Map(),behaviorRuns=new Map();
function shapeForNote(note){return active().filter(b=>b.part==='shape'&&b.shape!=='label'&&Object.values(b.mapping||{}).some(Boolean)).sort((a,b)=>Math.hypot(a.rect.x+a.rect.w/2-note.rect.x,a.rect.y+a.rect.h-note.rect.y)-Math.hypot(b.rect.x+b.rect.w/2-note.rect.x,b.rect.y+b.rect.h-note.rect.y))[0];}
async function interpretRuleMark(note){
 if(!maker||title(note).trim()!=='×')return;
 const target=shapeForNote(note);if(!target||!['x','width','row'].every(c=>target.mapping?.[c])){say('Place × beside a shape with start, duration and row mappings',true);return;}
 if(target.properties.x?.type!=='Date'||target.properties.width?.type!=='Duration'){say('This prepared interval rule needs Date and Duration encodings',true);return;}
 const existing=target.rules?.find(r=>r.mark===note.id);if(existing)return;
 target.rules=[...(target.rules||[]),{kind:'no_overlap',mark:note.id,status:'checking'}];save(target);renderMaker();say('Checking the interval rule in Shrine…');
 try{const descriptor=await behaviorCall({action:'overlap'});const rule=target.rules.find(r=>r.mark===note.id);if(!rule)return;Object.assign(rule,{status:'ready',implementation:descriptor.implementation,hash:descriptor.hash});save(target);renderMaker();log('× → no overlap in a row','local','Native guard compiled and checked; half-open intervals');say('Rule ready · overlap will be refused');}
 catch(error){target.rules.find(r=>r.mark===note.id).status='error';save(target);report(error);renderMaker();}
}
async function proposeNote(note){
 if(!ai){say('AI is off. The note is kept; new logic needs the author.',true);return;}
 const target=shapeForNote(note);if(!target||!collection(target)){say('Map the shape to native fields first',true);return;}
 if(note.behaviorJob?.status==='running')return;
 note.behaviorJob={status:'running'};save(note);renderItem(note,true);say('Authoring one pure function; the component stays usable');
 try{
  const job=await behaviorCall({action:'propose',note:title(note),collection:collection(target),mappings:target.mapping});note.behaviorJob={id:job.id,status:'running',target:target.id};save(note);
  let current=job;
  while(['interpreting','checking'].includes(current.status)){await new Promise(resolve=>setTimeout(resolve,1500));const r=await fetch('/api/jobs/'+job.id);current=await r.json();if(!r.ok)throw Error(current.error||'Authoring receipt unavailable');say(current.message);}
  log('Authored behavior · '+current.status,'large',(current.model_calls||0)+' model calls · '+(current.receipts||[]).map(r=>Math.round(r.elapsed_ms||0)+' ms').join(', '));
  if(current.status!=='ready')throw Error(current.message);
  note.behaviorJob={id:job.id,status:'ready',target:target.id,name:current.name,reason:current.message,source:current.candidate.pure_source,requires:current.requires};save(note);renderItem(note,true);say('Checked function ready for review');
 }catch(error){note.behaviorJob={...note.behaviorJob,status:'error',error:error.message};save(note);renderItem(note,true);report(error);}
}
function noteControls(note,node){
 if(!maker||dateAxis(title(note),makerSandbox.find(r=>Object.values(r).some(v=>dateDay(v)!==null))?Object.values(makerSandbox.find(r=>Object.values(r).some(v=>dateDay(v)!==null))).find(v=>dateDay(v)!==null):null)||title(note).trim()==='×'||!title(note).trim())return;
 const job=note.behaviorJob,box=element('div',undefined,'note-behavior');
 if(job?.status==='ready'){
  box.append(element('span','Checked · '+job.name));const inspect=element('details');inspect.append(element('summary','Function and checks'),element('pre',job.source));box.append(inspect);
  const accept=element('button','Use this behavior');accept.onclick=async()=>{accept.disabled=true;try{const activated=await behaviorCall({action:'activate',id:job.id});const target=byId(job.target);target.behavior={id:job.id,name:job.name,requires:activated.requires,descriptor:activated.descriptor,trueColour:'#cb604a'};note.behaviorJob.status='active';save(target);save(note);render();refreshBehavior(target,true);log('Activated '+job.name,'local','Native compiled function · pinned implementation · no write capability');}catch(error){report(error);accept.disabled=false;}};
  const decline=element('button','Keep original fill');decline.onclick=()=>{note.behaviorJob.status='declined';save(note);renderItem(note,true);};box.append(accept,decline);
 }else if(job?.status==='running')box.append(element('span','Checking new behavior…'));
 else if(job?.status==='active')box.append(element('span','✓ '+job.name+' · native'));
 else {const make=element('button',job?.status==='error'?'Retry behavior':'Use as behavior');make.onclick=()=>proposeNote(note);box.append(make);if(job?.error)box.append(element('span',job.error));}
 node.append(box);
}
async function refreshBehavior(b,force=false){
 if(!b.behavior)return;const id=b.behavior.id,data=maker?makerSandbox:nativeRows(collection(b));
 const signature=JSON.stringify([id,data]);if(!force&&behaviorValues.get(b.id)?.signature===signature||behaviorRuns.has(b.id))return;
 behaviorRuns.set(b.id,true);
 try{const value=await behaviorCall({action:'evaluate',id,collection:collection(b),...(maker?{sandbox:data}:{})});behaviorValues.set(b.id,{signature,values:new Map(value.value.map(r=>[r.id,r.value]))});if(maker)renderMakerPreview();else renderItem(b,true);}
 catch(error){behaviorValues.set(b.id,{signature,error:error.message});say('Derived colour is unresolved: '+error.message,true);}
 finally{behaviorRuns.delete(b.id);}
}
