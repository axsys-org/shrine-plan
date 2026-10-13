# Goo moodboard

A Grove mount of the existing Goo patching topos. It holds notes, image references,
and live Goo presentations on one canvas. There are no graph ports or edges.

```sh
GOO_PATCH_MASH_ROOT=/path/to/mash python3 x/eden --mount goo-moodboard --port 8135
```

Open `/goo-moodboard`. Use **+ Note**, **+ Image**, or **+ Live Goo** to populate
the ordinary **Add card** form. For a live card, enter an absolute namespace
subject path and its presentation slot (usually `/sys/slot/content`). Exactly
one matching view or port-free pane must resolve for that slot. Missing or
ambiguous recipes produce a diagnostic inside the card and an Open subject link.
The sample live card edits `/0x11/app/goo_moodboard/brief` through its published
`save_brief` action; this is actual Shrine data, not a client imitation.

Select a card in the canvas or the left-hand list to populate **Save card** and
**Delete card**. Drag its Move handle, or use the four named move buttons. The
shared canvas supplies selection, pan, zoom, and Fit. Native card content owns
its own text selection, inputs, actions, and scrolling. Long notes scroll within
the server-sized card. Image cards accept HTTPS or local absolute image URLs;
there is no upload service in this mount.

The board is typed namespace data at `/0x11/app/goo_moodboard/board` in the default
Eden node. Identity allocation is monotonic; renames retain identity and deletes
remove placement. Placement is a separate typed table, using signed world
coordinates and captured-base validation. Namespace edits survive browser
reloads. The development Eden launcher creates a fresh namespace on each launch;
this mount does not add separate disk persistence or localStorage.

## Reused boundaries

- `main.grove`: one ordinary `@pane`, `patch`, typed dynamic population, and
  `patch_operation("move-nodes")`. Creation, updates, and deletion are ordinary
  `on / action / myth` forms. Mutations use the existing server binding admission,
  action deduplication, and operation receipts.
- `model.foil`: bounded typed board and authoritative edit validation.
- `scene.foil`: server-owned SceneSnapshot, dimensions, initial placement,
  selector references, and passive native Goo content. No DOM measurement or
  automatic layout is added.
- `goo_patch.foil`: existing dynamic occurrences now admit native Goo images and
  a server-authored `patch_presentation` body node. This narrow node takes subject,
  slot, title, key, width, height, and top; it can only emit the shared local
  presentation route, never an arbitrary embedded website.
- `/goo-presentation`: the explorer resolves a matching published recipe and
  renders a compact document through `goo_browser/preview_at`. It loads the same
  Goo actions, panes, inspection, and SSR machinery as `/views`. Each live card
  has its own document so its real receiver and encounter remain independent.
  Use its **Inspect a presentation** control to inspect the actual compiled view.
- `goo-actions.js`: admitted same-lifetime card updates retain an unchanged direct
  presentation iframe *in place*, including its live document. Changing its
  subject/slot or retiring the occurrence replaces the document. This does not
  rely on moving an iframe or a browser-specific move API.
- `app.js`: presentation chrome, read-only board summary, and filling the ordinary
  Goo forms. No client board model, custom action endpoint, or evaluator.

No Mash component changes are required by this mount. The board app, shared
server projection additions, and iframe retention are in Reaver.

## Limits

Fixed server card sizes; no resizing, file uploads, rich text, or nesting/grouping
UI. The installed Goo font metrics currently support printable ASCII; note text
and titles are validated before committing rather than saving an unrenderable
board. An existing subject's presentation retains the normal Goo renderer's
capabilities and diagnostics. External changes to a live subject can be fetched
with its ordinary Refresh views control.

The seed uses the default Eden node `/0x11`; when authoring a mount for a different
node, point its seed live card at that node's installed subject.

## Verification

Native suites: `WISP=... python3 extras/x/check --mount goo-moodboard`.
JavaScript adapters: `node --test extras/mounts/explorer/tests/*.test.cjs`.
Browser flow, against an authorized disposable local instance:

```sh
node extras/mounts/goo-moodboard/check-browser.mjs \
  http://127.0.0.1:8135 /path/to/mash /tmp/goo-moodboard-browser
```

The browser test covers live subject edits, no-drag movement, real pointer drag,
frame retention with synthetic composition, board edit/create/delete, reload
restoration, and instrumented `getBoundingClientRect`/`getClientRects` reads on
card, port, and label elements. Synthetic composition is not manual OS IME
coverage. Live Save brief uses keyboard activation; card dragging uses real
pointer events.

Verified 2026-10-06 against the real local Eden mount (see `browser-results.json`):

- 685 native checks passed (135 web, 514 explorer, 36 moodboard), plus the mount
  contract and six profile-script checks.
- 84 JavaScript adapter tests passed, including three frame-retention checks.
- Chromium 151.0.7922.34, Firefox 153.0, and WebKit 26.5 completed all eight
  browser checks. No forbidden rectangle reads or uncaught errors in passing runs.
- The initial WebKit run exposed a test reload race; the harness now waits for
  Goo's completed Saved status and fresh bindings before the next edit/reload.
- No manual OS IME testing was performed.
