'use strict';
let data=null, course='all', view='upcoming', search='', selected=null, loading=false;
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=(e,options)=>new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',...options}).format(new Date(e*1000));
const day=e=>date(e,{year:'numeric',month:'2-digit',day:'2-digit'});
const age=e=>{if(!e)return 'not yet observed';let m=Math.max(0,Math.floor((Date.now()/1000-e)/60));return m<1?'just now':m<60?`${m}m ago`:m<1440?`${Math.floor(m/60)}h ago`:`${Math.floor(m/1440)}d ago`};
const safeURL=url=>{try{let u=new URL(url);return u.protocol==='https:'&&u.hostname==='sit.instructure.com'?u.href:'https://sit.instructure.com/'}catch{return 'https://sit.instructure.com/'}};
const courseFor=id=>data.courses.find(c=>c.id===id);
const code=id=>courseFor(id)?.code||'Canvas';
const when=a=>a.due_precision==='date'?'Time not supplied':date(a.due_epoch,{hour:'numeric',minute:'2-digit'});
async function api(path,body){let r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});let v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v;}
function fail(e){$('error').hidden=false;$('error').textContent=e.message||String(e)}
async function load(){if(loading)return;loading=true;try{data=await api('/api/state');$('error').hidden=true;render()}catch(e){fail(e)}finally{loading=false}}
function render(){
 let now=data.clock.epoch||data.server_epoch;
 $('today').textContent=date(now,{weekday:'long',month:'long',day:'numeric'});
 $('classCount').textContent=data.courses.length;$('total').textContent=data.assignments.length;
 $('soonCount').textContent=data.assignments.filter(a=>a.phase==='due_soon'&&!a.local_done&&a.calendar_status!=='CANCELLED').length;
 $('eventCount').textContent=data.events.filter(a=>a.start_epoch>=now&&a.start_epoch<=now+604800&&a.calendar_status!=='CANCELLED').length;
 let stale=data.source.freshness!=='recent'||data.source.availability!=='available';
 $('sourceBadge').textContent=data.syncing?'Refreshing':stale?'Check source':'Feed connected';$('sourceBadge').className='source-pill'+(stale?' stale':'');
 $('synced').textContent='Last observed '+age(data.source.observed_epoch);$('refresh').disabled=data.syncing;
 $('refresh').textContent=data.syncing?'Refreshing…':'↻ Refresh feed';
 if(data.source.last_error)fail(Error(data.source.last_error));
 $('courses').innerHTML=data.courses.map(c=>`<button data-course="${c.id}" class="${course===String(c.id)?'active':''}"><b><span class="course-dot"></span>${esc(c.code)}</b><small>${esc(c.name)}</small></button>`).join('');
 $('courseSelect').innerHTML='<option value="all">All coursework</option>'+data.courses.map(c=>`<option value="${c.id}">${esc(c.code)} · ${esc(c.name)}</option>`).join('');$('courseSelect').value=course;
 document.querySelector('.nav').classList.toggle('active',course==='all');
 let c=courseFor(Number(course));$('heading').innerHTML=c?`${esc(c.code)}<br><em>in view.</em>`:'Your semester,<br><em>in view.</em>';
 $('subtitle').textContent=c?c.name:'Classes, deadlines, and the space to make a plan.';
 const rows=data.assignments.filter(a=>(course==='all'||String(a.course_id)===course)&&(!search||(`${a.title} ${code(a.course_id)} ${a.note||''}`).toLowerCase().includes(search))&&
   (view==='all'||view==='planned'&&a.local_done||view==='history'&&a.phase==='due_passed'&&!a.local_done||view==='upcoming'&&['upcoming','due_soon','undated'].includes(a.phase)&&!a.local_done))
   .sort((a,b)=>view==='history'?b.due_epoch-a.due_epoch:a.due_epoch-b.due_epoch);
 $('listCount').textContent=rows.length;
 let last='';$('assignments').innerHTML=rows.map(a=>{
   let d=a.due_date||'No date';let header=d!==last?`<div class="group-label">${esc(a.due_date?date(new Date(a.due_date+'T12:00:00-04:00').getTime()/1000,{weekday:'long',month:'short',day:'numeric'}):'No date')}</div>`:'';last=d;
   let urgent=a.phase==='due_soon'&&day(a.due_epoch)===day(now);
   let label=a.local_done?'Planned done':a.phase==='due_passed'?'Verify submission':urgent?'Due today':a.phase==='due_soon'?'Coming up':'';
   return header+`<article class="assignment"><button class="check ${a.local_done?'done':''}" data-toggle="${esc(a.uid)}" aria-label="${a.local_done?'Undo local done for':'Mark planned done locally:'} ${esc(a.title)}" title="Local planning only">${a.local_done?'✓':''}</button><div><button class="assignment-title" data-detail="${esc(a.uid)}">${esc(a.title)}</button><div class="meta"><span class="code">${esc(code(a.course_id))}</span> &nbsp;·&nbsp; Submission unknown${a.note?' &nbsp;·&nbsp; Has note':''}${a.present_in_latest===0?' &nbsp;·&nbsp; Not in latest feed':''}</div></div><div class="due">${esc(when(a))}${label?`<br><span class="pill ${urgent?'urgent':a.phase==='due_passed'?'warning':''}">${esc(label)}</span>`:''}${a.due_precision==='browser'?'<small>Browser-verified time</small>':''}</div></article>`;
 }).join('')||'<div class="empty">Nothing in this view.<br>Canvas may have work outside the calendar feed.</div>';
 const events=data.events.filter(e=>e.start_epoch>=now&&e.start_epoch<now+604800&&(course==='all'||String(e.course_id)===course)&&e.calendar_status!=='CANCELLED').sort((a,b)=>a.start_epoch-b.start_epoch).slice(0,8);
 $('calendar').innerHTML=events.map(e=>`<div class="event"><div class="event-day">${date(e.start_epoch,{day:'numeric'})}<small>${date(e.start_epoch,{weekday:'short'}).toUpperCase()}</small></div><div><a href="${esc(safeURL(e.url))}" target="_blank" rel="noopener">${esc(e.title)}</a><p>${esc(code(e.course_id))} · ${e.due_precision==='date'?'All day':date(e.start_epoch,{hour:'numeric',minute:'2-digit'})}</p></div></div>`).join('')||'<p class="muted">No observed events in the next seven days.</p>';
 $('window').textContent=`Current feed: ${data.source.item_count||0} items, ${data.source.window_start||'?'} → ${data.source.window_end||'?'}. All times Eastern.`;
 $('noticeCount').textContent=`${data.notices.filter(n=>n.kind==='notice').length} native notice records. Statements and raw evidence are available in the separate inspector.`;
}
function details(uid){selected=data.assignments.find(a=>a.uid===uid);if(!selected)return;let a=selected;$('detailCourse').textContent=code(a.course_id);$('detailTitle').textContent=a.title;$('detailDate').textContent=`${a.due_date} · ${when(a)} · Eastern`;$('note').value=a.note||'';$('canvasLink').href=safeURL(a.url);$('detailInfo').textContent=`Canvas submission: unknown. ${a.local_done?'Marked done in your local plan. ':' '}${a.due_precision==='browser'?`Exact time observed in the browser ${age(a.exact_time_observed_epoch)}; the feed confirms the date only.`:a.due_precision==='date'?'The feed supplies a date, but no exact time. Check Canvas before relying on it.':'Exact timestamp supplied by Canvas’s feed.'}`;$('detailProvenance').textContent=`Native record: ${a._path} · phase ${a.phase} · observed ${age(a.observed_epoch)} · source ${a.evidence?.path||'unknown'}`;$('detail').showModal()}
document.addEventListener('click',async e=>{let b=e.target.closest('button');if(!b)return;if(b.dataset.course){course=b.dataset.course;render()}if(b.dataset.view){view=b.dataset.view;document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('selected',x===b));render()}if(b.dataset.detail)details(b.dataset.detail);if(b.dataset.toggle){let a=data.assignments.find(a=>a.uid===b.dataset.toggle);b.disabled=true;try{await api('/api/plan',{uid:a.uid,local_done:a.local_done?0:1,case:a._case});await load()}catch(e){fail(e);await load()}}});
 $('search').addEventListener('input',e=>{search=e.target.value.toLowerCase();render()});
 $('courseSelect').addEventListener('change',e=>{course=e.target.value;render()});
 $('refresh').onclick=async()=>{try{await api('/api/sync',{});$('refresh').disabled=true;$('refresh').textContent='Refreshing…';setTimeout(load,1000)}catch(e){fail(e)}};
 $('closeDetail').onclick=()=>$('detail').close();
 $('saveNote').onclick=async()=>{if(!selected)return;$('saveNote').disabled=true;try{await api('/api/plan',{uid:selected.uid,note:$('note').value,case:selected._case});$('detail').close();await load()}catch(e){fail(e)}finally{$('saveNote').disabled=false}};
 load();setInterval(load,15000);
