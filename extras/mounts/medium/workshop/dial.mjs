// Grove's prepared radial encoding. The value has no write gesture; the target
// has the declared angle inverse only when its native field is writable.
import {inversePatch} from './encodings.mjs';
const NS='http://www.w3.org/2000/svg';
const svg=(tag,attrs={})=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;};
export function dialBindings(schema){
 const roles={value:'quantity',max:'max',limit:'limit',angle:'target'};
 return Object.fromEntries(Object.entries(roles).flatMap(([channel,role])=>{const fields=schema.filter(f=>f.role===role&&['Number','Natural'].includes(f.type));if(fields.length!==1)return [];const field=fields[0];return [[channel,{field:field.label,slot:field.slot,type:field.type,role:field.role,readonly:field.writable===false,mode:channel==='angle'&&field.writable!==false?'input':'source',axis:{min:0,from:-180,to:0,snap:.5}}]];}));
}
export function drawDial(block,rows,{pending,refresh,commit,say,gesture=()=>{}}){
 const row=rows[0],p=block.properties||{},read=key=>{const raw=row?.[p[key]?.field];return raw==null||raw===''?null:Number(raw);};
 const value=read('value'),maximum=read('max'),limit=read('limit'),target=read('angle');
 const root=document.createElement('div');root.className='dial-surface';
 const graph=svg('svg',{viewBox:'0 0 260 170',role:'img','aria-label':'Value and writable target'}),point=n=>{const a=(-180+n/maximum*180)*Math.PI/180;return [130+96*Math.cos(a),120+96*Math.sin(a)];};
 graph.append(svg('path',{d:'M34 120 A96 96 0 0 1 226 120',fill:'none',stroke:'#e2e8e2','stroke-width':13,'stroke-linecap':'round'}));
 const caption=svg('text',{x:130,y:153,'text-anchor':'middle','font-size':21,fill:'#243a35'});caption.textContent=value===null?'? value':String(value);graph.append(caption);
 if(maximum!==null&&maximum>0){
  for(const [n,label]of [[0,'0'],[maximum/2,String(maximum/2)],[maximum,String(maximum)]]){const [x,y]=point(n),t=svg('text',{x,y:y+19,'font-size':10,'text-anchor':'middle',fill:'#75847d'});t.textContent=label;graph.append(t);}
  if(limit!==null){const [x,y]=point(limit);graph.append(svg('line',{x1:130+(x-130)*.86,y1:120+(y-120)*.86,x2:130+(x-130)*1.11,y2:120+(y-120)*1.11,stroke:'#cfa664','stroke-width':3}));}
  if(value!==null){const [x,y]=point(Math.max(0,Math.min(maximum,value))),needle=svg('line',{x1:130,y1:120,x2:x,y2:y,stroke:'#35878a','stroke-width':4,'stroke-linecap':'round'});needle.dataset.channel='value';needle.onclick=e=>{e.stopPropagation();say('Value is from its source. It has no write handle.');};graph.append(needle,svg('circle',{cx:130,cy:120,r:5,fill:'#35878a'}));}
  if(target!==null){const [x,y]=point(target),marker=svg('circle',{cx:x,cy:y,r:7,fill:'#fff7ef',stroke:'#c96c35','stroke-width':2}),label=svg('text',{x:130,y:169,'text-anchor':'middle','font-size':10,fill:'#aa612f'});label.textContent='target '+target+(p.angle?.readonly?' · read-only':'');marker.setAttribute('aria-label','Target '+target);graph.append(marker,label);
   if(p.angle?.mode==='input'&&!p.angle.readonly){marker.style.cursor='grab';marker.onpointerdown=event=>{event.preventDefault();event.stopPropagation();const before=String(row[p.angle.field]);let patch=null;gesture(true);say("Editing target · release to save");marker.setPointerCapture(event.pointerId);marker.onpointermove=move=>{const bounds=graph.getBoundingClientRect(),x=(move.clientX-bounds.left)*260/bounds.width,y=(move.clientY-bounds.top)*170/bounds.height;const degrees=Math.atan2(Math.min(0,y-120),x-130)*180/Math.PI;const encoded={...block,properties:{...p,angle:{...p.angle,axis:{...p.angle.axis,maxField:p.max.field}}}};patch=inversePatch(encoded,'angle',degrees,row);const next=patch[p.angle.field],[px,py]=point(next);marker.setAttribute('cx',px);marker.setAttribute('cy',py);label.textContent='target '+next;pending(row.id,p.angle.field,String(next),before);refresh(block.id);};marker.onpointerup=()=>{gesture(false);marker.onpointermove=null;marker.onpointerup=null;marker.onpointercancel=null;if(patch)commit(block,row.id,p.angle.field,String(patch[p.angle.field]));};marker.onpointercancel=()=>{gesture(false);marker.onpointermove=null;pending(row.id,p.angle.field,null,before);refresh();};};}
  }
 }
 root.append(graph);
 for(const [channel,label]of [['value','value'],['max','max'],['limit','limit'],['angle','target']]){const chip=document.createElement('span');chip.dataset.channel=channel;chip.className='dial-port '+(p[channel]?.mode==='input'?'write':'source');chip.textContent=label+' '+(p[channel]?.field?'← '+p[channel].field:'?');root.append(chip);}
 return root;
}
