// Grove-owned encoding mechanics. The same version runs in maker and live uses.
// No source names or application categories participate in layout or inversion.
export const REVISION = 'grove.encodings/3';
export function day(value){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(value)))return null;const n=Date.parse(value+'T00:00:00Z')/86400000;return Number.isFinite(n)&&new Date(n*86400000).toISOString().slice(0,10)===value?n:null;}
export function numeric(value) {
  if(value === '' || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
export function initials(value) {
  return String(value ?? '').trim().split(/\s+/).filter(Boolean).slice(0,2).map(x=>[...x][0]).join('').toUpperCase();
}
export function colour(value) {
  let hash=2166136261;
  for(const c of String(value ?? '')) hash=Math.imul(hash^c.codePointAt(0),16777619);
  return `hsl(${(hash>>>0)%360} 35% 51%)`;
}
export function encodedValue(shape, channel, row, rows) {
  const spec=shape.properties?.[channel]||{};
  const field=spec.field||shape.mapping?.[channel];
  if(!field || spec.mode==='static') return null;
  let value=row[field];
  if(spec.adapter?.kind==='end-minus-start'){
    const start=day(row[spec.adapter.start]),end=day(row[spec.adapter.end]);
    if(start===null||end===null||end<start)return null;
    value=end-start;
  }
  if(spec.operation==='initials') value=initials(value);
  if(channel==='colour') {
    if(value === '' || value == null)return null;
    const index=spec.choices?.indexOf(String(value));
    return index>=0?['#8ca5b7','#d7ab58','#6d9e80','#9c83bd','#579ca6'][index%5]:colour(value);
  }
  if(channel==='label'||channel==='text') return value == null ? null : String(value);
  if(channel==='row') return [...new Set(rows.map(r=>String(r[field]??'')))].indexOf(String(value??''));
  const number=spec.type==='Date'?day(value):numeric(value);if(number===null)return null;
  const axis=spec.axis||{};
  if(channel==='angle'){
    const min=numeric(row[axis.minField])??numeric(axis.min)??0;
    const max=numeric(row[axis.maxField])??numeric(axis.max)??100;
    if(max<=min)return null;
    return (axis.from??-180)+(number-min)/(max-min)*((axis.to??0)-(axis.from??-180));
  }
  return (number-(axis.origin??0))*(axis.scale??shape.scale??16)+(axis.offset??0);
}
export function inverse(shape, channel, pixels, row) {
  const spec=shape.properties?.[channel]||{},axis=spec.axis||{};
  if(spec.mode!=='input'||!spec.field||spec.readonly||spec.operation) throw Error('This channel has no writable inverse');
  let value;
  if(channel==='angle'){
    const min=numeric(row[axis.minField])??numeric(axis.min)??0,max=numeric(row[axis.maxField])??numeric(axis.max)??100;
    const from=axis.from??-180,to=axis.to??0;
    if(max<=min||to===from)throw Error('Choose a nonzero angle scale');
    value=min+(pixels-from)/(to-from)*(max-min);
    value=Math.max(min,Math.min(max,value));
  } else {
    const scale=axis.scale??shape.scale??16;
    if(!Number.isFinite(scale)||scale===0)throw Error('Choose a nonzero scale');
    value=(pixels-(axis.offset??0))/scale+(axis.origin??0);
  }
  const snap=axis.snap??.01;
  if(snap>0)value=Math.round(value/snap)*snap;
  if(channel==='width'||channel==='height')value=Math.max(0,value);
  return spec.type==='Date'?new Date(Math.round(value)*86400000).toISOString().slice(0,10):Math.round(value*1e8)/1e8;
}
export function layout(shape, rows) {
  const valid=rows.filter(row=>missing(shape,row).length===0);
  return valid.map((row,index)=>{
    const at=channel=>encodedValue(shape,channel,row,valid);
    const lane=at('row'),mappedY=at('y');
    return {id:row.id,row,x:at('x')??0,y:mappedY??(lane!==null?lane*44:index*44),
      width:Math.max(2,at('width')??shape.rect.w),height:Math.max(2,at('height')??Math.min(32,shape.rect.h)),
      angle:at('angle'),fill:at('colour')??shape.fill??'#d8dfcf',label:at('label')??at('text')??'',
      lane:lane!==null?String(row[shape.mapping?.row||shape.properties?.row?.field]??''):null};
  });
}
export function missing(shape,row){
  return ['x','y','width','height','angle','row'].filter(channel=>{
    const spec=shape.properties?.[channel]||{},field=spec.field||shape.mapping?.[channel];
    if(!field||spec.mode==='static')return false;
    const value=row[field];
    return channel==='row'?value==null||value==='':encodedValue(shape,channel,row,[row])===null;
  }).map(channel=>shape.properties?.[channel]?.field||shape.mapping[channel]);
}
export function inversePatch(shape,channel,pixels,row){
  const spec=shape.properties?.[channel]||{},value=inverse(shape,channel,pixels,row);
  const adapter=shape.properties?.width?.adapter;
  const iso=n=>new Date(n*86400000).toISOString().slice(0,10);
  if(adapter?.kind==='end-minus-start'){
    const start=day(row[adapter.start]),end=day(row[adapter.end]);
    if(start===null||end===null||end<start)throw Error('The interval has unresolved endpoints');
    if(channel==='width')return {[adapter.end]:iso(start+value)};
    if(channel==='x'&&spec.field===adapter.start){const next=day(value);if(next===null)throw Error('The new start is not a date');return {[adapter.start]:value,[adapter.end]:iso(end+next-start)};}
  }
  return {[spec.field]:value};
}
