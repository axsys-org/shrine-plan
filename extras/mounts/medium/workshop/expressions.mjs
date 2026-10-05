// Small, versioned expressions are parsed as data. No eval, dynamic code, or
// namespace-name dispatch. References resolve once to native identities.
export function countExpression(source,nodes){
 if(!source.trim().startsWith('='))return null;
 const terms=source.trim().slice(1).split('·').map(s=>s.trim());let owner=null;
 const segments=terms.map(term=>{
  const match=/^count\(\s*(.*?)\s*\)$/.exec(term);if(!match)throw Error('Use count(Collection) or count(field = value), separated by ·');
  const condition=/^(.+?)\s*=\s*(.+)$/.exec(match[1]);
  if(!condition){const choices=nodes.filter(n=>!n.parent||n.parent==='/' ).filter(n=>n.label===match[1]);if(choices.length!==1)throw Error('Choose an exact collection: '+match[1]);owner=choices[0];return {collection:owner.id,label:owner.label.toLowerCase()};}
  if(!owner)throw Error('Name a collection with count(Collection) first');
  const field=owner.properties?.find(f=>f.label===condition[1].trim());if(!field)throw Error('Missing field '+condition[1]);
  const value=condition[2].trim().replace(/^(?:"(.*)"|'(.*)')$/,'$1$2');
  if(field.choices?.length&&!field.choices.includes(value))throw Error('Choose one of '+field.choices.join(', '));
  return {collection:owner.id,field:field.label,slot:field.slot,equals:value,label:value.toLowerCase()};
 });
 return {revision:'grove.count-text/1',source,segments};
}
export function countText(expression,rows){
 if(expression.revision!=='grove.count-text/1')return '? expression revision';
 return expression.segments.map(s=>{const data=rows(s.collection),n=s.field?data.filter(r=>String(r[s.field])===s.equals).length:data.length;return n+' '+s.label;}).join(' · ');
}
