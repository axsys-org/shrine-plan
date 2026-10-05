// Collection authoring overlays. Drafts are local; schemas and records are
// committed through the native owner supplied by the workspace.
export const fieldTypes = ['Text','Enum','Ref','Many','Date','Duration','Number','Natural','Boolean','Image','File','Sequence','List','Object'];
export const roles = ['', 'title','group','start','end','duration','quantity','min','max','limit','target','geo','ref'];
export function inferRole(name,type,fields=[]) {
  const n=name.trim().toLowerCase().replaceAll(' ','_');
  if (['name','title','label','who'].includes(n) && type==='Text') return 'title';
  if (['status','state','stage','phase','type','category','group','room','crew'].includes(n) && type==='Enum') return 'group';
  if (['start','from','begins','start_date'].includes(n) && type==='Date') return 'start';
  if (['end','to','ends','end_date'].includes(n) && type==='Date') return 'end';
  if (['Number','Natural'].includes(type)) {if(['min','max','limit','target'].includes(n))return n;if(['value','amount','reading'].includes(n))return 'quantity';}
  if (type==='Duration') return 'duration';
  if (type==='Ref') return 'ref';
  return '';
}
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const input=(label,value='')=>{const n=el('input');n.setAttribute('aria-label',label);n.value=value;return n;};
function select(label,options,value,change){const n=el('select');n.setAttribute('aria-label',label);for(const [v,t] of options){const o=el('option',t);o.value=v;n.append(o);}n.value=value;n.onchange=()=>change(n.value);return n;}
export function collectionAuthoring({host,collections,create,record,rows,changed,describe}) {
  let draft,form,refreshRecords=()=>{},controls=new Map();
  const key='grove.collection-draft.v1';
  try {draft=JSON.parse(localStorage.getItem(key)||'null');}catch{}
  const remember=()=>localStorage.setItem(key,JSON.stringify(draft));
  function header(panel,title,close){const h=el('header');h.append(el('strong',title));const b=el('button','×');b.type='button';b.setAttribute('aria-label','Close '+title);b.onclick=close;h.append(b);panel.append(h);}
  function open(target){draft=draft||{name:'',fields:[{name:'',type:'Text',role:'',writable:true,choices:[]}],event:crypto.randomUUID()};draft.target=target;draw();host.querySelector('[aria-label="Collection name"]')?.focus();}
  function draw(){
    host.querySelector('.schema-overlay')?.remove();if(!draft)return;
    const panel=el('section',undefined,'schema-overlay author-overlay');panel.setAttribute('aria-label','New collection');
    header(panel,'New collection',()=>panel.remove());
    const label=el('label','Name'),name=input('Collection name',draft.name);name.placeholder='People';name.oninput=()=>{draft.name=name.value;remember();};label.append(name);panel.append(label);
    const headings=el('div',undefined,'schema-columns');for(const t of ['Field','Type','Role','Writes',''])headings.append(el('span',t));panel.append(headings);
    const body=el('div',undefined,'schema-rows');panel.append(body);
    draft.fields.forEach((f,i)=>{
      const row=el('div',undefined,'schema-columns'),group=el('div',undefined,'schema-row-group'),field=input('Field '+(i+1)+' name',f.name);field.placeholder='Field name';
      const role=select('Field '+(i+1)+' role',roles.map(r=>[r,r||'—']),f.role||'',v=>{f.role=v;f.roleSet=true;remember();});
      const auto=()=>{if(!f.roleSet){f.role=inferRole(f.name,f.type,draft.fields);role.value=f.role;}};
      field.oninput=()=>{f.name=field.value;auto();remember();};
      const kind=select('Field '+(i+1)+' type',fieldTypes.map(t=>[t,t]),f.type,v=>{f.type=v;auto();remember();draw();});
      const writable=el('span','●','field-writable');writable.title='Writable · only a connected source can lock a field';writable.setAttribute('aria-label','Field '+(i+1)+' writable');
      const remove=el('button','−');remove.type='button';remove.setAttribute('aria-label','Remove field '+(i+1));remove.disabled=draft.fields.length===1;remove.onclick=()=>{draft.fields.splice(i,1);remember();draw();};
      row.append(field,kind,role,writable,remove);group.append(row);
      if(f.type==='Enum'){
        const choices=el('div',undefined,'enum-editor');for(const [j,value] of (f.choices||[]).entries()){const chip=el('button',value+' ×','enum-chip');chip.type='button';chip.setAttribute('aria-label','Remove option '+value);chip.onclick=()=>{f.choices.splice(j,1);remember();draw();};choices.append(chip);}
        const option=input('Field '+(i+1)+' new option');option.placeholder='Option + Enter';option.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();const value=option.value.trim();if(value&&!f.choices.includes(value)){f.choices.push(value);remember();draw();host.querySelector('[aria-label="Field '+(i+1)+' new option"]')?.focus();}}};choices.append(option);group.append(choices);
      }
      if(['Ref','Many'].includes(f.type))group.append(select('Field '+(i+1)+' reference collection',[['','Choose collection…'],['self','This collection (self)'],...collections().map(c=>[c.id,c.label])],f.target||'',v=>{f.target=v;remember();}));
      if(f.type==='Duration'){f.unit='days';group.append(el('small','Unit: days · step 1','field-unit'));}
      body.append(group);
    });
    const add=el('button','＋ field','add-field');add.type='button';add.disabled=draft.fields.length>=16;add.onclick=()=>{draft.fields.push({name:'',type:'Text',role:'',writable:true,choices:[]});remember();draw();host.querySelector('[aria-label="Field '+draft.fields.length+' name"]')?.focus();};panel.append(add);
    const status=el('div','','form-error');status.setAttribute('role','status');panel.append(status);
    const commit=el('button','Create collection','native-create');commit.onclick=async()=>{commit.disabled=true;commit.textContent='Checking…';try{const result=await create(structuredClone(draft));draft=null;localStorage.removeItem(key);panel.remove();showRecords(result.collection);describe(result.collection);changed();}catch(e){status.textContent=e.message;commit.disabled=false;commit.textContent='Create collection';}};panel.append(commit);host.append(panel);
  }
  function showRecords(id,defaults={}){
    host.querySelector('.records-overlay')?.remove();const c=collections().find(c=>c.id===id);if(!c)return;
    form={id,event:crypto.randomUUID(),values:{}};controls=new Map();const panel=el('section',undefined,'records-overlay author-overlay');header(panel,'Add '+(c.collectionSchema?.singular||c.label.replace(/s$/,'')),()=>panel.remove());
    const fields=el('form',undefined,'record-fields');panel.append(fields);
    for(const f of c.properties||[]){const label=el('label',f.label);const control=valueControl(f,{collections,rows});control.setAttribute('aria-label',f.label);if(defaults[f.label]!==undefined)control.value=defaults[f.label];controls.set(f.label,control);label.append(control);fields.append(label);}
    const error=el('div','','form-error');error.setAttribute('role','status');const add=el('button','Add','native-create');add.type='submit';fields.append(error,add);
    const table=el('div',undefined,'record-receipts');panel.append(table);
    const update=()=>{table.replaceChildren();const current=rows(id);table.append(el('small',current.length+' records'));const t=el('table'),h=el('tr');for(const f of c.properties||[])h.append(el('th',f.label));t.append(h);for(const r of current){const tr=el('tr');for(const f of c.properties||[])tr.append(el('td',displayValue(r[f.label],f,{collections,rows})));t.append(tr);}table.append(t);};refreshRecords=()=>{if(!panel.isConnected)return;update();for(const f of c.properties||[]){if(!['Ref','Many'].includes(f.type))continue;const previous=controls.get(f.label),signature=JSON.stringify(rows(f.target).map(r=>[r.id,r.name,r.title]));if(previous.dataset.options===signature)continue;const next=valueControl(f,{collections,rows});next.dataset.options=signature;next.setAttribute('aria-label',f.label);next.value=previous.value;previous.replaceWith(next);controls.set(f.label,next);}};update();
    fields.onsubmit=async e=>{e.preventDefault();add.disabled=true;error.textContent='';const values=Object.fromEntries([...controls].map(([k,v])=>[k,v.value]));try{await record(id,values,form.event);form.event=crypto.randomUUID();for(const f of c.properties||[]){let control=controls.get(f.label);if(f.type==='Many'){const next=valueControl(f,{collections,rows});next.setAttribute('aria-label',f.label);control.replaceWith(next);controls.set(f.label,next);control=next;}control.value=defaults[f.label]??(f.type==='Duration'?'1':'');}update();changed();controls.values().next().value?.focus();}catch(e){error.textContent=e.message;}finally{add.disabled=false;}};host.append(panel);controls.values().next().value?.focus();
  }
  return {open,showRecords,refresh:()=>refreshRecords()};
}
export function displayValue(value,field,{rows=()=>[]}={}){
  if(['Ref','Reference'].includes(field.type)){const row=rows(field.target).find(r=>r.id===value);return row?String(row.name||row.title||Object.values(row).find((v,i)=>i&&v)||value):value||'—';}
  if(field.type==='Many'){try{return JSON.parse(value||'[]').map(v=>displayValue(v,{...field,type:'Ref'},{rows})).join(', ')||'—';}catch{return value;}}
  return String(value??'');
}
export function valueControl(field,{collections=()=>[],rows=()=>[],compact=false}={}){
  const type=field?.type||'Text';let control;
  if(!compact&&['Enum','Choice'].includes(type)&&(field.choices||[]).length<=4){
    control=el('div',undefined,'enum-control');control.setAttribute('role','radiogroup');let value='';
    Object.defineProperty(control,'value',{get:()=>value,set:v=>{value=String(v||'');for(const button of control.children)button.setAttribute('aria-checked',String(button.dataset.value===value));}});
    for(const option of field.choices||[]){const button=el('button',option);button.type='button';button.setAttribute('role','radio');button.setAttribute('aria-label',option);button.setAttribute('aria-checked','false');button.dataset.value=option;button.onclick=()=>{control.value=option;control.dispatchEvent(new Event('input',{bubbles:true}));};control.append(button);}
  }else if(['Enum','Choice','Boolean','Ref','Reference'].includes(type)){
    const options=type==='Boolean'?[['true','Yes'],['false','No']]:['Ref','Reference'].includes(type)?rows(field.target).map(r=>[r.id,r.name||r.title||Object.values(r).find((v,i)=>i&&v)||r.id]):(field.choices||[]).map(v=>[v,v]);
    control=select(field.label||'', [['','Choose…'],...options],'',()=>{});
  }else if(type==='Many'){
    control=el('div',undefined,'many-control');const selected=new Set();Object.defineProperty(control,'value',{get:()=>JSON.stringify([...selected]),set:v=>{selected.clear();try{for(const id of JSON.parse(v||'[]'))selected.add(id);}catch{}for(const box of control.querySelectorAll('input'))box.checked=selected.has(box.value);}});
    for(const row of rows(field.target)){const label=el('label'),box=input('Include '+(row.title||row.name||row.id));box.type='checkbox';box.value=row.id;box.onchange=()=>{box.checked?selected.add(row.id):selected.delete(row.id);control.dispatchEvent(new Event('input',{bubbles:true}));};label.append(box,el('span',row.title||row.name||row.id));control.append(label);}if(!control.children.length)control.append(el('small','No records yet'));
  }else if(['List','Sequence','Object'].includes(type)){control=el('textarea');control.rows=3;control.placeholder=type==='Object'?'{}':type==='Sequence'?'[12, 18, 9]':'[]';}
  else {control=el('input');if(['Duration','Natural','Number'].includes(type)){control.type='number';control.step=type==='Number'?'any':'1';if(type!=='Number')control.min='0';if(type==='Duration')control.value='1';}else if(type==='Date')control.type='date';}
  if(type==='Many'&&compact){
    const choices=control,details=el('details',undefined,'many-cell'),summary=el('summary');
    const label=()=>{summary.textContent=displayValue(choices.value,field,{rows});};
    Object.defineProperty(details,'value',{get:()=>choices.value,set:value=>{choices.value=value;label();}});
    choices.addEventListener('input',label);details.append(summary,choices);label();return details;
  }
  return control;
}
