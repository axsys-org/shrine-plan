# QA log: using the world as an agent would

One entry per thing used, seen and either fixed or left open. Newest last. The
rule: a gap between "I used it" and "it is reported" is a bug of its own.

| when | did | saw | expected | state |
|---|---|---|---|---|
| 2026-10-16 | `GET /mcp/stream` from a raw socket | no response head, nothing in the log | the event-stream head at once | fixed: the mount spelled the field-less action as a bare path; it is `.stream` typed as the action |
| 2026-10-16 | `history after … with x` after writing a cell | the cell's `/x` and `/c/x` inlined as `exists: false` | the cell's answer and context as of then | fixed: the epoch pin is spelled over the record (`/x/h/x/e<epoch>/…`); knobs.md says a live input reads as it is now |
| 2026-10-16 | a tack on another cell's `/x` with `<len>` one short | "slots: slot names to text, numbers, booleans or {type, value}" | a refusal that names the slot and the rule | fixed: a refused slot names itself and the reference rule; knobs.md states that the `x` counts |
| 2026-10-16 | two reads of one path with different formulas in `then` | one answer, the last | both | open: `then` is an object keyed by path; a `reads` list answers in order and is the way to ask twice |
| 2026-10-16 | a formula read | `{path, formula, result, context, nodes, next}` | what the first page says, "the tree" | fixed: the first page says a formula read answers `{path, formula, result, context}` |
| 2026-10-16 | seeding a pasted export with ids like `c-7`, `A-100` | "path: a segmented namespace address is required" | the rule | fixed: every path refusal states the rule (letters, digits, underscore; keep the original as a slot) |
| 2026-10-16 | a `reads` list with three unparsable paths | the three entries silently missing from `answers` | `{path, error}` per entry, as knobs.md promises | fixed: a bad entry answers `{path, error}`; a bad `then` read is still left out |
| 2026-10-16 | the live page after a 33-record seed | the newest event opened `/0x11` at z: the whole system tree, redrawn on every refresh | the records the event wrote | fixed: the page lists written records (never the node root, the journal tag or an ancestor), opens up to eight by itself at y, reads z on a click |
| 2026-10-16 | `history … with x` on that seed | 20 records inlined of 33: every folder record and every order record missing | all 33 | fixed: the mount's `wrote` dropped a written record whose child followed it in tap order; a diff never holds ancestors (they are signs), so the rule is gone |
| 2026-10-16 | the live page's cell lines | "2 scale", "Customers title" as a cell's answer | the figure, or the row count | fixed: the summary skips the input's title and scale, prefers a figure, else "N rows" |
| 2026-10-16 | `touched` on an event | the node root, the ancestors whose cases moved and the writer's tag record, before the records written | the written records first | open: `touched` is the signs; the page filters; the mount could list written records first |
| 2026-10-16 | the first stream line after a boot | once more than 50 ms after its write (every later line within 0.1 ms) | within the write's latency | open: nothing warms the stream path at boot |
