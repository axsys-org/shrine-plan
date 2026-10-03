// Browser continuity only. No application values, actions or constraints are evaluated here.
export class FrameGate {
  revision = 0;
  pending = 0;
  beginWrite() { this.pending++; this.revision++; }
  endWrite() { this.pending--; this.revision++; }
  accepted() { this.revision++; }
  beginRead() { return this.pending ? null : this.revision; }
  mayRead(ticket) { return ticket !== null && !this.pending && ticket === this.revision; }
}

export function acknowledgedDraft(draft, submitted, established) {
  // Transport success need not mean the submitted value was accepted. Clear
  // only the version actually sent and subsequently echoed by the native view.
  return draft !== undefined && draft.value === submitted && established === submitted;
}

export function sameFrame(a, b) {
  return !!a && a.workspace === b.workspace && a.expected === b.expected && a.publication === b.publication;
}

export function occurrenceSelection(node, occurrence) {
  return {subject: node.id, owner: node.id,
    slots: [...new Set([...(occurrence.reads || []), ...(occurrence.slot && occurrence.slot !== '/' ? [occurrence.slot] : [])])],
    occurrence: occurrence.id, kind: occurrence.kind, label: node.label,
    source: {view: node.view.id, line: occurrence.line, column: occurrence.column},
    basis: {expected: node.expected, displayed: node.displayed}};
}
