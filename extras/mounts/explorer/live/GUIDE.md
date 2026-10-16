# The viewer: goo component and responsive guide

One component, no interaction, real time. The viewer shows the record the last
write touched, resolved, with its flow above it. It never takes input. It
redraws when the world changes and only where it changed.

Files beside this guide:

- `viewer.css`: tokens and the component styles, in Shrine's own look.
- `viewer.js`: the binding. `mountViewer(element, source)` and nothing else.
- `viewer-demo.html`: the binding driven by an in-memory source that behaves
  like the mount, so the component can be developed without a world.

## 1. What the binding consumes

Three calls on a `source`, which is the mount over HTTP in production and the
in-memory world in the demo. Nothing else is ever asked of the server.

```
source.read(path, care, case)   -> { path, record | null, kids: [tree...], case }
source.answer(path)             -> { tree } | { note } | { bad }      (/x of a cell)
source.graph()                  -> { sources: [{path, meta}],
                                     cells: [{path, formula, settings, answer, note, bad, inputs: [{path, pin, view}]}] }
source.follow(handler)          -> handler({ epoch, label, who, touched: [paths] })   (one per event)
                                   handler({ shown: { path, care, case } })   (a presented read)
```

A tree node is `{ name, path, slots: {k: v}, kids: [node] }`. A value is a
number, text, date text, a flag text (`yes`/`no`), or a reference
`-> path` optionally `@ case`. The binding never sees a type beyond that.

## 2. The action tree

The page is a tree of what the agent did, newest first.

- **Now.** The latest action, open: its line, then its records as lines,
  the first open into its card. A line reads `epoch · label · who · N records`
  and, on the right, what the write moved: the cells that read what it
  touched, with their answers now.
- **Earlier.** Every previous action collapsed to its line. Open one and its
  records appear as lines; open a record and its card appears. Nothing
  closed is rendered: a body is filled the first time it opens and kept.
- **A presented read** is an action too, marked `shown`, with the path it
  showed; it is not in history and it carries no epoch.

Open and close is the only interaction, and it is the browser's own
`details` element, so it costs nothing and needs no state.

## 3. The record card

A node is drawn by one function at three depths:

- **x**: the record's slots.
- **y**: the record's slots, then each child drawn as a row.
- **z**: the same, and each child's children as rows nested beneath it.

The viewer always draws z and stops where the tree stops. Depth is not a
control; the data decides.

### Slot rendering, for an unknown number of slots

The number and kind of slots is never known in advance, so the record body
chooses a layout from what it is handed:

| slots | layout |
|---|---|
| none | nothing; the name alone (a folder) |
| one, numeric | the figure: mono, 30px, slot name beside it |
| two to six, all short | a grid of label-over-value cells, 118px minimum, wraps |
| more than six, or any long text | a two-column key/value list, one slot per line |
| a reference | a teal value, wraps, never truncated |
| a blob by hash | a chip with the hash prefix and size; an image shows a thumbnail |
| text over 80 characters | spans the full row, wraps |

Short means under 24 characters. These rules are in `slotLayout()` and nowhere
else, so a new kind of value is one more row in that function.

### Rows, for children

A child is a row: name left, its slots right, inline, in the order written.
When a row's slots do not fit on one line at the current width, they wrap
under the name rather than truncate. A child that is a cell shows its answer
on its row, not its formula: a figure if it produces one, otherwise `N rows`.
A folder (no record) is a muted name.

Nesting indents by 14px with a hairline on the left. Depth is unbounded in
the data; the viewer folds anything deeper than three levels behind the
row's count (`12 beneath`) so a wide tree never becomes a wall.

### Cells

A cell draws what it produces, not what it is made of. The answer is drawn
with the same rules as any record: a figure, a grid of slots, rows, groups
with rows inside. What it is made of (formula, inputs, settings) sits folded
under "made of". A cell that cannot answer draws one quiet line in its place:
`needs slot`, `points back at itself`, `waits on closed`.

### The composition, as an outline

No lines. The context chain is drawn the way a file tree is drawn, by
indentation, so it scales the way a file tree scales.

Under any record, the questions asked of it hang as an indented list: one
line per cell that reads it, with a formula chip, the cell's name, any other
source it also reads (`+ 2026`), and its answer on the right. Under each of
those hang the questions asked of that cell. So a chain is depth, a join is
a line that names a second source, a split is two lines under one record,
and a pin is `held at N` on the chip. A cell that cannot answer shows its
note in amber or its fault in rust where the answer would be.

A cell in focus shows a `from` line under its name: the formula chip and a
pill per input, pinned ones marked, so where it comes from reads in one
line and what depends on it hangs beneath as above.

This gives `(context, ns) -> (context', ns')` its horizontal form without a
graph: the written records are the trunk, the questions are the branches,
and reading downward and inward is reading the composition.

### A batch

When one event touched several paths, the card is a stack: one record per
path, each with its path in small mono on the right, deleted ones marked.

### State marks, the only colour in the body

- `bump`: a two-tone inset ring that fades over 0.8s on anything the last
  event touched. Reduced-motion users get no animation.
- `note` (amber): a cell waiting on something.
- `bad` (rust): a cycle or an unknown.
- `gone` (rust): a record deleted in this write.
- `pin` (violet): a held input.

Nothing else is coloured. Links are teal. Cells are tinted sage.

## 4. Responsive rules

- The app is one column at every width. The sheet never needs two.
- Side gutters are 16px on phones, 18px inside the card.
- The slot grid uses `repeat(auto-fill, minmax(118px, 1fr))`; it is one
  column at 320px and six at 900px with no media query.
- Row slots wrap under the name below 520px (`.row` goes to one column).
- The strip scrolls; the page never scrolls horizontally.
- Text roles follow the goo profile: body 13px, labels 10 to 11px at weight
  600, values in mono, figures 30px mono with negative tracking.
- No fixed heights anywhere; the card is as tall as its content.

## 5. Real time, and what gets refetched

The follow stream reports each event's touched paths. On an event:

1. If the event touched the focus path or anything beneath it, or a path in
   the focus cell's lineage, refetch the focus with one `read` (and one
   `answer` if it is a cell). Reads are free and single-digit milliseconds;
   fetching the focus again is cheaper than reasoning about it.
2. Otherwise do nothing.

Rendering is a reconciliation keyed by `data-path` and `data-case`: a node
whose case did not change keeps its DOM. So a write to one deal under a
folder of five hundred redraws one row. The bump mark is applied to the
touched paths only.

There is no client cache of data, and there should not be one: the world is
the cache. On the server, Liam's overlay cache is per path and opt-in; turn
it on for a cell only when its evaluation is measurably slow. Until the
rendering fix in the mount lands, a folder over a few hundred children is
the one case where the refetch is not cheap, and the page cap on children
is what bounds it.

## 6. Presented reads

Reads never appear, with one deliberate exception: a read the agent makes in
order to show you something. "Show me the sales folder as it is" is a read,
not a write, and must not become one.

The mount gets one flag: `read … present: true`. It answers as usual and
also pushes `{ shown: { path, care, case } }` on the follow stream. Nothing is
journaled; no epoch moves; history does not know it happened. The viewer
treats it as a focus change: it draws that path, as is, with a small
"shown" mark in the bar instead of an event label. The next write replaces
it like any other focus.

That keeps the invariant exact: the world records only writes, and the
viewer shows the world plus what the agent chose to point at.

## 7. The binding plan

1. `viewer.js` as it is here is the renderer. It has no knowledge of HTTP.
2. The explorer JS pane gets a `source` built from three existing routes:
   `/record` for reads, `/record?path=/x/…` for answers, the follow SSE for
   events. About 60 lines. This is the path that works today.
3. The mount gets `present: true` on `read` and the `shown` notice on the
   stream. About 15 lines, no kernel change.
4. Lineage: today the page can rebuild it by reading a cell's record and
   following its reference slots. The mount can offer it in one call later
   (`read … lineage: true`), which saves a round trip per hop.
5. When Liam's goo workspace can list a folder's children with a derived read
   per child and refresh on the stream, the same renderer becomes a Grove
   template with his styling for free. Nothing in `viewer.js` depends on
   which host it has.

No back and forward, no buttons, no clicks required. If links are wanted
later, every pill and row already carries `data-path`; a host can wire them
or leave them inert. The demo wires them, the product does not have to.
