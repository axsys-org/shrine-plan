# The live viewer: implementation plan

What is being built: the page that sits beside the chat. It shows what the
agent did as a tree of actions, newest open, with every record resolved and
the questions asked of it hanging beneath. No controls beyond open and close.
It redraws by itself when the world changes.

This plan is written against `ic-cells` as of f8aacd0, after reading the
explorer mount, the goo pane docs, the MCP mount and the foot. Each decision
below names the evidence.

## 0. Decisions

| question | decision | why |
|---|---|---|
| goo native or JS pane | **JS pane**, served as an explorer asset, same origin as the mount | goo's `list_tree` is bounded to 64 nodes, has no lazy loading, no background watchers (PANES.md: "this slice does not add background watchers"), and its sources are namespace paths, so it cannot present the journal. Everything the page needs is three JSON calls. |
| data source | **`/mcp` JSON-RPC**, `tools/call` on `read` and `history` | same origin, no session handshake (`tools/call` is dispatched directly), the only API that already pages, resolves `/x`, and knows epochs. The explorer's `/ns` and `/views` routes are HTML, not JSON. |
| liveness | **push from the commit**: a `stream` action in the foot, one line per journaled event carrying the touched records resolved; the poll of `history after` only as the fallback | no server push exists on this branch yet (no `event-stream`, no `EventSource`, no follow route in `src` or `extras`); the foot has `reply`, `bytes`, `batch`, `snapshot` actions and no long-lived reply. The supervisor already produces the journal entry per commit, so the stream is a list of open connections and one write each. About 100 lines in `http_foot`, ours, no kernel change. Commit to pixel is then the write floor plus one socket write, with no round trip from the page. |
| rendering | HTML and CSS, the goo profile's fonts and roles, no framework | the explorer already serves `goo-profile.css` and the Goo Sans and Goo Mono files from `/static`; the page links them and uses the same sizes. |
| state | none beyond the DOM; `details` open or closed is the only state | the user's constraint: open and close, nothing else. |
| interaction | open and close; links optional and off by default | same. |

## 1. Files

All in `extras/mounts/explorer/`. Asset names must start with `goo-`:
`asset_files` keeps only names with that prefix (`explorer_mount.foil` line 10).

```
goo-live.html        the page: links goo-profile.css, goo-live.css, goo-live.js; one <div id="live">
goo-live.css         viewer.css from the scratchpad, renamed selectors kept (.sv-*)
goo-live.js          viewer.js from the scratchpad plus the /mcp source adapter (section 3)
mount.json           three asset lines under "assets"
explorer_mount.foil  one route: "/live" -> serves goo-live.html as text/html (copy the face handler, no path field)
tests/goo-live.test.cjs   node --test over the pure functions (section 7)
```

The record-card renderer, the slot layouts, the outline and the action tree
are the files already written (`viewer.js`, `viewer.css`, GUIDE.md). They
are pure functions from JSON to HTML; nothing in them changes for the host.

## 2. Two mount additions (Foil, about 30 lines)

In `extras/mounts/mcp/mcp_mount.foil`:

1. **`history after <epoch>`**: the forward page. The `events` routine takes
   `before` today (line 58). Add `after`: events with epoch greater than it,
   oldest first, same item shape `{epoch, touched}`, same `next`. This is the
   poll. Without it the page would page backward from the top every tick.
2. **`read … present: true`**: the presented read. The read answers as usual
   and the mount records `{shown: {path, care, case}, at: <now epoch>}` in a
   one-slot ring in the mount's own memory (not the namespace, not the
   journal). `history after` includes it as a pseudo-item
   `{shown: {...}, epoch: <the epoch it was seen at>}` once, then drops it.
   Nothing is written; no epoch moves.

Both are mount-local; the kernel and the foot are untouched.

## 3. The source adapter (JS, about 60 lines, inside goo-live.js)

The viewer consumes four calls. Each maps to one `/mcp` request:

```
read(path, care, case)  -> tools/call read {path, care, case, limit: 200}
   answer: { path, properties, exists, reference, children: [node...], nodes, next }
   adapt:  node.slots = properties with "/" stripped from keys and {type,value} unwrapped;
           node.kids = children (already nested at z, paged by limit; follow next only if the
           page asked for it, never automatically); record === null when exists is false and
           a case says it was culled.
answer(path)            -> tools/call read {path: "/x/" + path, care: "z", limit: 200}
                           plus tools/call read {path: "/c/x/" + path, care: "x"} for note | bad
   adapt:  tree from the first; note = context's /sys/view/missing, bad = /sys/view/message.
graph()                 -> tools/call read {path: <views folder>, care: "y", limit: 500} once per draw,
                           then answer(p) for each child that has a /sys/weft slot
   adapt:  cells = [{path, formula (tail of /sys/weft), settings (other slots), inputs: from
           /sys/tack and any reference slot, pin from the reference's case, view: slot != tack}]
           sources = the distinct input paths that are not /x/
follow(handler)         -> setInterval 700ms: tools/call history {after: last, limit: 40}
   adapt:  for each item: handler({epoch, label, who, touched}) or handler({shown});
           label = first touched path's tail + " (+N)" until the mount carries one;
           who = "agent" until authorities exist; last = newest epoch seen.
```

The views folder is whatever folder the page is opened for: `/live?views=/0x11/org/views`.
`graph()` over a folder of a few hundred cells is a few hundred free reads;
when that is slow, scope it to the cells that read the touched paths (the
same function over a smaller list).

## 4. The page, exactly

```
┌─ bar ─────────────────────────────────────────────────────────────────────┐
│ namespace / studio / views                                     now 10      │
├─ now ─────────────────────────────────────────────────────────────────────┤
│ ▾ 10  poke alice          agent  1 record      payroll 395 · budget_left 105│
│    ▾ alice   studio/people/alice                 role lead · team eng · 165│
│      ┌─ card ─────────────────────────────────────────────────────────┐    │
│      │ alice                                                          │    │
│      │ role      team      salary                                     │    │
│      │ lead      eng       165                                        │    │
│      └────────────────────────────────────────────────────────────────┘    │
├─ earlier ─────────────────────────────────────────────────────────────────┤
│ ▸ 9   poke globex         agent  1 record      closed 4 rows · by_owner 235│
│ ▸ 8   make cell payroll_board  agent  1 record                             │
│ ▸ 5   make 2 cells        agent  2 records     revenue 235                 │
│ …                                                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

- **bar**: crumb of the folder the page watches (text, not links), and `now <epoch>`
  or `shown as is` in violet after a presented read.
- **now**: the latest action, open; its records as lines; the first record open
  into its card. The line: epoch in mono 10px faint, label 550 weight, who as a
  sage chip, count in mono 10px, and on the right what it moved: the cells that
  read any touched path, with their answers now, three at most then `…`.
- **earlier**: every previous action collapsed to its line, newest first, under
  a hairline. Opening one fills its body the first time (records as lines);
  opening a record fills its card the first time. Bodies are kept once filled.
- **card** (section 3 of GUIDE.md): the record's slots by the layout rules; a cell
  shows its `from` line (formula chip, input pills, `held at N`, `view`), then
  what it produces, then `made of` folded; beneath every record, the outline of
  questions asked of it (formula chip, cell, `+ other source`, answer; nested).
- **marks**: bump (inset green ring fading 0.8 s) on everything the last event
  touched; amber note, rust fault, rust deleted, violet pin and `shown`.

## 5. Style, exactly

Linked, not copied: `/static/goo-profile.css` supplies Goo Sans and Goo Mono
with their metrics. `goo-live.css` uses:

- body 13px Goo Sans, line 1.5, kerning and ligatures off (the profile's own rule)
- labels 10 to 11px at 600, soft `#666`; mono values Goo Mono 11 to 14px; the figure 30px mono, tracking -0.8px
- colours: page `#fafafa`, paper `#fffefa`, hairlines `#ddd` and `#e8e8e4`, wash `#f0f3e9`, tint `#eaf1e3`, green `#34573e`, teal `#245a63`, rust `#9a4938`, amber `#8a6a1f`, violet `#4f4a8a`: all taken from `goo-profile.css` and the explorer's existing chrome
- radius 5 to 6px, borders 1px, no shadows except the bump ring, no icons

## 6. Responsive, exactly

One column always. 16px gutters outside, 18px inside the card. The slot grid is
`repeat(auto-fill, minmax(118px, 1fr))`. Below 520px: row slots wrap under
the name, the "moved" summary and record paths hide, action lines keep
epoch, label and count. The page never scrolls horizontally. No fixed heights.

## 7. Real time, exactly

**Stream (the ideal, built first).** The foot's new `stream` action: `GET /mcp/stream`
keeps the connection open with `Content-Type: text/event-stream`, and after
every commit the foot writes one line to every open stream:

```
data: {"epoch": 11, "label": "make cell vendors", "who": "agent",
       "touched": ["/0x11/studio/views/vendors"],
       "with": { "/0x11/studio/views/vendors": { record, children, answer, says } } }
```

`with` is the touched records resolved at x, and for a cell its `/x` and
`/c/x`, so the page redraws without asking anything back. A presented read is
pushed on the same stream as `{"shown": {path, care, case}}` and is never
journaled. The foot's connection actors are spawned once with the routes, so a
stream is one actor that never replies and is dropped when the socket closes.

**The stream in the actor-per-connection foot.**

- A stream is a connection actor that never replies. It handles `GET /mcp/stream`,
  writes the headers, registers itself in the foot's stream registry, and waits
  for messages instead of closing. The socket closing retires it and removes it
  from the registry.
- The pool is adjusted once: streams do not count against the connection pool,
  or a few open tabs would starve it. A separate small set for streams, or an
  unbounded spawn for that one route.
- Broadcast lives where writes already finish. The foot's write path receives
  the admitted event with its epoch and touched paths; the `then` machinery
  already reads the admitted state in the same reply. The stream line is that
  event plus `then`-style reads of the touched paths, sent to every registered
  stream actor. One write path, one place to add it.
- Back-pressure: a slow or dead client never blocks a commit. Each stream writes
  from a small bounded buffer and is dropped if it stalls; a write never waits
  on a tab.
- Many sessions: every stream sees every commit. The page filters with
  `views=<folder>` (scopes the outline and moved summaries) and `who=<writer>`
  (the mount tags each MCP connection; with networking this becomes the
  authority). No server-side notion of a session exists.

**The skill.** One line: "When you connect, open `/live?views=<the folder you
are working in>` in the person's browser once; if you cannot open a browser,
give them the link."

**Poll (fallback only).** If `/mcp/stream` is not served, `follow` polls
`history after last` every 700 ms and reads the touched paths itself. Same
handler, same events, one extra round trip.

**On an event.** Append it; redraw `now` from `with`; demote the previous `now`
to the top of `earlier`, collapsed; refill only open bodies whose records are
in `touched`; recompute the moved summary from the cells that read a touched
path (the mount can send that list in the event too, which removes the last
read). DOM keyed by `data-path` and `data-case`; untouched nodes keep their
element. No client cache of data; the world is the cache.

## 8. What the page does not do

No back and forward, no revert, no care toggle, no mode toggle, no search, no
edit. No reads shown except presented ones. No graph with lines. No state
survives reload except what the browser keeps for open `details`, which is
nothing. Nothing reads the namespace through any route but `/mcp`.

## 9. Tests

- `tests/goo-live.test.cjs`, `node --test`: `slotLayout` picks figure, grid,
  list and wraps long text; `recordHTML` on a cell shows the answer and folds
  `made of`; the outline nests a chain two deep and names a join's second
  source; `actionHTML` collapses a batch to one line with the right count; a
  presented item renders `shown`; the adapter maps a real `read` answer
  (fixture captured from the product test world) to the tree shape.
- `host.py` `check`: GET `/live` is 200 with `text/html`, and the three assets
  are 200 from `/static/`.
- One live check in `product.py` after step 20: `history after` returns the
  twenty-record batch as one item, and `read … present: true` leaves the epoch
  unchanged and appears once in the next `history after`.

## 10. Order and size

1. foot: the `stream` action (about 100 lines of Foil) with a foot test: two clients,
   one write, both receive one line within the write's own latency; a closed socket
   drops its stream; a presented read arrives and is not journaled.
2. mount: `with` on the stream line, `present` on `read` (15 lines), `history after`
   for the fallback (15 lines), with the product checks.
3. explorer: copy the three files in, register assets, add `/live` (20 lines of Foil).
4. adapter: `follow` over the stream, the three reads over `/mcp` for opened bodies (60 lines of JS).
5. host check and the node tests.
6. Open `/live?views=/0x11/org/views` beside a Claude session with the skill, run the
   product script against the world, and watch it. Fix what reads wrong.

About 250 lines of new code beyond the files already written. No kernel change.

## 11. Later, and why not now

- **Goo native**: when goo topoi can present a bounded, lazily loaded source and
  refresh on a watcher, the record card becomes a Grove `@view` and gets the
  profile's layout engine for free. The outline and the action tree stay JS
  until the journal is presentable as a source.
- **Authorities on the `who` chip**: arrives with networking; the line already has
  the slot for it.
