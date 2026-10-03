// Local presentation selection only. No namespace writes or applicability rules.
export class InspectionState {
  mode = false;
  held = false;
  pinned = false;
  key = null;
  get active() { return this.mode || this.held; }
  get visible() { return this.pinned || (this.active && this.key !== null); }
  hover(key) { if (this.active && !this.pinned) this.key = key; }
  hold(value) { this.held = value; if (!this.active && !this.pinned) this.key = null; }
  toggle() { this.mode = !this.mode; if (!this.active && !this.pinned) this.key = null; }
  pin(key = this.key) { if (key !== null) { this.key = key; this.pinned = true; } }
  follow() { this.pinned = false; this.mode = true; }
  close() { this.mode = false; this.held = false; this.pinned = false; this.key = null; }
}
