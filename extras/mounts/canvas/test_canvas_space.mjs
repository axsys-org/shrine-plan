import test from 'node:test';
import assert from 'node:assert/strict';
import {worldPoint,zoomAt,fitCamera,restoreLayout} from './canvas-space.mjs';

test('pinching keeps the subject under the pointer even on a panned canvas',()=>{
  const camera={x:-470,y:320,zoom:.75},pointer={x:614,y:222};
  const before=worldPoint(camera,pointer),after=worldPoint(zoomAt(camera,pointer,1.8),pointer);
  assert.ok(Math.abs(before.x-after.x)<1e-9);assert.ok(Math.abs(before.y-after.y)<1e-9);
});
test('zoom limits also preserve the pointer anchor',()=>{
  const camera={x:20,y:-400,zoom:1},pointer={x:30,y:20};
  const next=zoomAt(camera,pointer,99);
  assert.equal(next.zoom,2);assert.deepEqual(worldPoint(next,pointer),worldPoint(camera,pointer));
});
test('fit accommodates separate subjects without changing their coordinates',()=>{
  const cards=[{x:-320,y:100,width:360,height:200},{x:200,y:500,width:360,height:250}];
  const c=fitCamera(cards,1200,900);
  for(const r of cards){assert.ok(r.x*c.zoom+c.x>=69);assert.ok(r.y*c.zoom+c.y>=69);assert.ok((r.x+r.width)*c.zoom+c.x<=1131);assert.ok((r.y+r.height)*c.zoom+c.y<=831);}
  assert.equal(cards[0].x,-320);
});
test('restored positions remain keyed by stable subjects; corrupt geometry is dropped',()=>{
  const state=restoreLayout({version:1,camera:{x:0,y:2,zoom:100},positions:{'/first':{x:20,y:40},'/other':{x:-55,y:9},bad:{x:NaN,y:30}}});
  assert.equal(state.camera.zoom,2);assert.deepEqual(state.positions.get('/other'),{x:-55,y:9});assert.equal(state.positions.has('bad'),false);
  assert.equal(restoreLayout({version:99}),null);
});
