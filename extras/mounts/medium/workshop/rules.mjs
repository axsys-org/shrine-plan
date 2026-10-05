// Preview constraints over the same declared encoding channels. Durable writes
// are rechecked in Shrine against current records before the scoped transaction.
export function overlap(shape,rows,changed,layout){
 if(!shape.rules?.some(r=>r.kind==='no_overlap'))return null;
 const placed=layout(shape,rows),candidate=placed.find(p=>p.id===changed);
 if(!candidate||candidate.width<=0)return null;
 const other=placed.find(p=>p.id!==changed&&p.lane===candidate.lane&&p.width>0&&candidate.x<p.x+p.width&&p.x<candidate.x+candidate.width);
 return other?{kind:'no_overlap',record:changed,other:other.id,lane:candidate.lane}:null;
}
