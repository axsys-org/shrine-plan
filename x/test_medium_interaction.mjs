// State/transport regression tests, not a substitute for browser or usability acceptance.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FrameGate, acknowledgedDraft, sameFrame, occurrenceSelection} from '../extras/mounts/medium/proof/interaction.mjs';

test('late reads cannot overwrite actions, accepted jobs, or queued mutations', () => {
  const gate = new FrameGate(), read = gate.beginRead();
  gate.beginWrite(); gate.beginWrite();
  assert.equal(gate.mayRead(read), false);
  assert.equal(gate.beginRead(), null);
  gate.endWrite(); assert.equal(gate.beginRead(), null);
  gate.endWrite(); assert.equal(gate.mayRead(read), false);
  const fresh = gate.beginRead(); assert.equal(gate.mayRead(fresh), true);
  gate.accepted(); assert.equal(gate.mayRead(fresh), false);
});
test('action completion keeps text typed after submission', () => {
  assert.equal(acknowledgedDraft({value:'next draft'}, 'submitted draft', 'submitted draft'), false);
  assert.equal(acknowledgedDraft({value:'submitted draft'}, 'submitted draft', 'submitted draft'), true);
  assert.equal(acknowledgedDraft(undefined, 'submitted draft', 'submitted draft'), false);
  assert.equal(acknowledgedDraft({value:'invalid number'}, 'invalid number', '11'), false);
});
test('unchanged basis is local to one world and includes native publication', () => {
  const frame={workspace:'a',expected:'9',publication:'10'};
  assert.equal(sameFrame(frame,{...frame}),true);
  assert.equal(sameFrame(frame,{...frame,publication:'11'}),false);
  assert.equal(sameFrame(frame,{...frame,workspace:'b'}),false);
});
test('pointing carries opaque slots and exact view source; labels do not infer identity', () => {
  const node={id:'/native/$123',label:'Same label',expected:'4',displayed:'3',view:{id:'/gov/$456/view'}};
  const occurrence={id:'/gov/$456/view:8',kind:'input',reads:['/opaque/$aaa'],slot:'/opaque/$bbb',line:'62',column:'7'};
  const selection=occurrenceSelection(node,occurrence);
  assert.deepEqual(selection.slots,['/opaque/$aaa','/opaque/$bbb']);
  assert.equal(selection.subject,node.id);
  assert.equal(selection.source.view,node.view.id);
  assert.deepEqual(selection.basis,{expected:'4',displayed:'3'});
});
