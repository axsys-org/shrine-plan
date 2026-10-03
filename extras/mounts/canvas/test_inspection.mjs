import test from 'node:test';
import assert from 'node:assert/strict';
import {InspectionState} from './inspection-state.mjs';

test('ordinary pointer movement cannot activate inspection',()=>{
  const s=new InspectionState();s.hover('reservation-a');assert.equal(s.visible,false);assert.equal(s.key,null);
});
test('hold and hover inspect without a click; releasing dismisses the preview',()=>{
  const s=new InspectionState();s.hold(true);s.hover('reservation-a');assert.equal(s.visible,true);
  s.hover('person-b');assert.equal(s.key,'person-b');s.hold(false);assert.equal(s.visible,false);
});
test('pin survives modifier release and unrelated pointer activity',()=>{
  const s=new InspectionState();s.hold(true);s.hover('reservation-a');s.pin();s.hold(false);
  s.hover('reservation-b');assert.equal(s.key,'reservation-a');assert.equal(s.visible,true);
});
test('persistent mode supports focus navigation and explicit follow after pinning',()=>{
  const s=new InspectionState();s.toggle();s.hover('rule');s.pin();s.follow();s.hover('case-q');
  assert.equal(s.key,'case-q');assert.equal(s.pinned,false);s.close();assert.equal(s.visible,false);assert.equal(s.active,false);
});
