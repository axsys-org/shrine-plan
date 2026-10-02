const {test}=require('node:test');
const assert=require('node:assert/strict');
const {topology,focusMember}=require('../goo-topoi.js');
const tree=[{key:'root',parent:null},{key:'branch',parent:'root'},{key:'leaf',parent:'branch'}];
test('all topoi use the same keyed memberships',()=> {
 for(const renderer of ['list','diagram_tree','list_tree']) assert.deepEqual([...topology(tree,renderer).keys()],['root','branch','leaf']);
});
test('tree topology rejects ambiguity, orphans and cycles',()=> {
 assert.throws(()=>topology([...tree,{key:'root'}],'list'),/Duplicate/);
 assert.throws(()=>topology([{key:'a'},{key:'b'}],'diagram_tree'),/one root/);
 assert.throws(()=>topology([{key:'root'}, {key:'child',parent:'missing'}],'list_tree'),/Missing/);
 assert.throws(()=>topology([{key:'root'},{key:'a',parent:'b'},{key:'b',parent:'a'}],'diagram_tree'),/Cyclic/);
 assert.throws(()=>topology(tree,'unknown'),/Unknown/);
});

test('tab position requires an available member with the same life and source',()=> {
 const a={key:'a',life:'1',source:'/cards',sourceLife:'2',status:'available'};
 const b={...a,key:'b'}, unavailable={...a,key:'closed',status:'unavailable'};
 assert.equal(focusMember([a,b],b),b);
 assert.equal(focusMember([unavailable,a,b],{...b,life:'old'}),a);
 assert.equal(focusMember([a,b],{...b,sourceLife:'old'}),a);
 assert.equal(focusMember([a,b],{...b,axis:'y'}),a);
 assert.equal(focusMember([a,unavailable],unavailable),a);
 assert.equal(focusMember([unavailable],a),null);
});
