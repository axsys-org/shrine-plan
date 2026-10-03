// Drafts belong to exact native subjects and pinned views, never visual rows.
export const surfaceKey = (frame, view) => JSON.stringify([frame.subject, view.id]);
export const basis = frame => ({expected:frame.expected, displayed:frame.displayed, publication:frame.publication});
export const sameBasis = (a, b) => ['expected','displayed','publication'].every(key=>a[key]===b[key]);

export class SurfaceDrafts {
  constructor() { this.values = new Map(); }
  get(frame, view) { return this.values.get(surfaceKey(frame,view)); }
  edit(frame, view, slot, value, initial) {
    const key=surfaceKey(frame,view);
    const draft=this.values.get(key) ?? {basis:basis(frame), inputs:{}, original:{...initial}, revision:0};
    draft.inputs[slot]=value;
    draft.revision++;
    this.values.set(key,draft);
    return draft;
  }
  stale(frame,view) { const draft=this.get(frame,view);return !!draft&&!sameBasis(draft.basis,basis(frame)); }
  review(frame,view) {
    const draft=this.get(frame,view);
    if(draft) draft.basis=basis(frame);
  }
  clear(frame,view,revision) {
    if(revision!==undefined&&this.get(frame,view)?.revision!==revision)return;
    this.values.delete(surfaceKey(frame,view));
  }
}
