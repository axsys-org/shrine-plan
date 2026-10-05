import test from 'node:test';
import assert from 'node:assert/strict';
import {SurfaceDrafts} from './surface-state.mjs';

const first={subject:'/world/a',expected:'10',displayed:'11',publication:'12'};
const view={id:'/gov/authored/edit'};
test('a reordered or separately selected subject cannot inherit another subject’s draft',()=>{
  const drafts=new SurfaceDrafts();drafts.edit(first,view,'/opaque/slot','Mine',{'/opaque/slot':'Before'});
  assert.equal(drafts.get({...first,subject:'/world/b'},view),undefined);
  assert.equal(drafts.get(first,{id:'/gov/another/edit'}),undefined);
  assert.equal(drafts.get(first,view).inputs['/opaque/slot'],'Mine');
});
test('changed subject and changed publication require explicit review without discarding text',()=>{
  const drafts=new SurfaceDrafts();drafts.edit(first,view,'/opaque/slot','Mine',{'/opaque/slot':'Before'});
  assert.equal(drafts.stale(first,view),false);
  const changed={...first,publication:'13'};
  assert.equal(drafts.stale(changed,view),true);
  assert.equal(drafts.get(changed,view).original['/opaque/slot'],'Before');
  assert.equal(drafts.get(changed,view).inputs['/opaque/slot'],'Mine');
  drafts.review(changed,view);assert.equal(drafts.stale(changed,view),false);
  assert.equal(drafts.stale({...changed,expected:'14'},view),true);
});
test('successful native acknowledgement clears only the acknowledged draft',()=>{
  const drafts=new SurfaceDrafts(),second={...first,subject:'/world/b'};
  drafts.edit(first,view,'/x','A',{});drafts.edit(second,view,'/x','B',{});
  drafts.clear(first,view);assert.equal(drafts.get(first,view),undefined);
  assert.equal(drafts.get(second,view).inputs['/x'],'B');
});
test('typing during an in-flight save survives acknowledgement of the older draft',()=>{
  const drafts=new SurfaceDrafts();
  const submitted=drafts.edit(first,view,'/x','Sent',{}).revision;
  drafts.edit(first,view,'/x','Still typing',{});
  drafts.clear(first,view,submitted);
  assert.equal(drafts.get(first,view).inputs['/x'],'Still typing');
  const latest=drafts.get(first,view).revision;
  drafts.clear(first,view,latest);
  assert.equal(drafts.get(first,view),undefined);
});
test('reviewing one edited field cannot restore an untouched field over a concurrent edit',()=>{
  const drafts=new SurfaceDrafts();
  drafts.edit(first,view,'/name','Mine',{'/name':'Before','/intent':'Old intent'});
  const changed={...first,expected:'14'};
  drafts.review(changed,view);
  const latest={'/name':'Before','/intent':'A concurrent improvement'};
  assert.deepEqual({...latest,...drafts.get(changed,view).inputs},{'/name':'Mine','/intent':'A concurrent improvement'});
});
