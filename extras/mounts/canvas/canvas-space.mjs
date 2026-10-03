// Browser geometry only. Native subjects and actions remain authoritative.
export const limitZoom = value => Math.max(.3,Math.min(2,value));
export const worldPoint = (camera,point) => ({x:(point.x-camera.x)/camera.zoom,y:(point.y-camera.y)/camera.zoom});
export function zoomAt(camera,point,zoom) {
  const anchor=worldPoint(camera,point),next=limitZoom(zoom);
  return {x:point.x-anchor.x*next,y:point.y-anchor.y*next,zoom:next};
}
export function fitCamera(rectangles,width,height,padding=70) {
  if(!rectangles.length)return {x:width/2-180,y:height/2-120,zoom:1};
  const left=Math.min(...rectangles.map(r=>r.x)),top=Math.min(...rectangles.map(r=>r.y));
  const right=Math.max(...rectangles.map(r=>r.x+r.width)),bottom=Math.max(...rectangles.map(r=>r.y+r.height));
  const zoom=limitZoom(Math.min(1,(width-padding*2)/(right-left),(height-padding*2)/(bottom-top)));
  return {x:(width-(right-left)*zoom)/2-left*zoom,y:(height-(bottom-top)*zoom)/2-top*zoom,zoom};
}
export function restoreLayout(value) {
  const finite=number=>typeof number==='number'&&Number.isFinite(number)&&Math.abs(number)<1e7;
  if(!value||value.version!==1)return null;
  const c=value.camera;
  const camera=c&&finite(c.x)&&finite(c.y)&&finite(c.zoom)?{x:c.x,y:c.y,zoom:limitZoom(c.zoom)}:null;
  const positions=new Map();
  for(const [id,point] of Object.entries(value.positions??{})) {
    if(typeof id==='string'&&point&&finite(point.x)&&finite(point.y))positions.set(id,{x:point.x,y:point.y});
  }
  return {camera,positions};
}
