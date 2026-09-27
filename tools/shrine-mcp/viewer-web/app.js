const $=id=>document.getElementById(id), records=new Map();let cursor=0, selected=null, selectedCase=null, worldId=null;
async function rpc(method,args={}){const r=await fetch('/api?'+new URLSearchParams({method,args:JSON.stringify(args)}));const d=await r.json();if(!r.ok)throw Error(d.error);return d}
function node(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e}
function fields(record){return Object.fromEntries((record?.slots||[]).map(s=>[s.key.join('/'),s.value]))}
function paths(){const q=$('filter').value.toLowerCase();$('nodes').replaceChildren();for(const p of [...records.keys()].sort().filter(p=>p.toLowerCase().includes(q)).slice(0,250)){const b=node('button',p);b.onclick=()=>inspect(p);$('nodes').append(b)}}
function card(title,value){const c=node('div','','card');c.append(node('h3',title),node('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));const hashes=new Set();function scan(v){if(!v||typeof v!=='object')return;if(typeof v.sha256==='string'&&/^[0-9a-f]{64}$/.test(v.sha256))hashes.add(v.sha256);for(const child of Object.values(v))scan(child)}scan(value);for(const hash of hashes){const a=node('a','Open retained artifact '+hash.slice(0,12));a.href='/artifact/'+hash;a.target='_blank';a.rel='noopener';c.append(a)}return c}
function show(record){$('details').replaceChildren();if(!record){$('details').append(card('Absent','No current record at this exact path.'));return}selected=record.path;$('title').textContent=record.path;$('case').textContent='case '+record.case;$('hint').textContent='Slots retain opaque native keys. Renderings are for inspection; pinned references retain the value.';for(const s of record.slots){const c=card(JSON.stringify(s.key),{value:s.value,type:s.type,render:s.render,reference:s.ref});$('details').append(c)}if(record.crew?.length)$('details').prepend(card('Native crew',record.crew));if(record.behaviors?.length)$('details').prepend(card('Behavior references',record.behaviors))}
async function inspect(path,caseNumber=null){try{
  $('path').value=path;selectedCase=caseNumber;
  const d=await rpc('read',{path:records.get(path)?.path_segments||path,recursive:caseNumber===null,case:caseNumber,limit:30});
  if(caseNumber===null)for(const r of d.records)records.set(r.path,r);
  paths();show(d.records.find(r=>r.path===path));$('connections').replaceChildren();
  if(caseNumber!==null){$('hint').textContent='Historical case '+caseNumber+'. Current connections and incoming updates do not replace this original basis.';return}
  const c=await rpc('context',{subjects:[path],limits:{items:12,bytes:12288}});
  for(const item of c.items){
    const el=node('div','','edge'),b=node('button',item.path);
    if(item.availability==='external_world'){b.disabled=true;el.append(node('div','External world: '+item.world))}
    else b.onclick=()=>inspect(item.path,item.availability==='historical_reference'?item.case:null);
    el.append(node('span',item.category+' → '),b,node('div',item.route.map(r=>(r.direction==='reverse'?'← ':'→ ')+r.relation).join(' · ')));
    if(item.availability)el.append(node('small',item.availability));
    $('connections').append(el)
  }
}catch(e){$('health').textContent=e.message}}
async function tick(){try{const status=await rpc('status');if(worldId&&worldId!==status.world_id){cursor=0;records.clear();selected=null;$('events').replaceChildren();$('details').replaceChildren();$('connections').replaceChildren()}worldId=status.world_id;$('health').textContent='v5 · '+status.world_id.slice(0,10)+' · '+status.cursor+' committed';const d=await rpc('events',{cursor,limit:30});for(const e of d.events){for(const c of e.result?.changes||[]){if(c.record)records.set(c.path,c.record);else records.delete(c.path);if(selected===c.path&&selectedCase===null)show(c.record)}const el=node('div','','event');el.append(node('div','#'+e.sequence+' '+e.operation.op+' '+(Array.isArray(e.operation.path)?e.operation.path.join('/'):e.operation.path||'')),node('small',e.at));if(e.result?.error)el.append(node('div',e.result.error));el.onclick=()=>{selected=null;$('details').replaceChildren(card('Actual event receipt',e))};$('events').prepend(el)}while($('events').children.length>100)$('events').lastChild.remove();cursor=d.cursor;paths();setTimeout(tick,d.more?100:1000)}catch(e){$('health').textContent='Disconnected · '+e.message;setTimeout(tick,3000)}}
$('browse').onsubmit=e=>{e.preventDefault();inspect($('path').value)};$('filter').oninput=paths;tick();
