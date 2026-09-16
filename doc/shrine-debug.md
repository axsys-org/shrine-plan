# Namespace-native Grove debugger

Served at `/debug`; `/ns` remains the original explorer. Definitions live at
`/<node>/gov/debug`, with an installed application at `/<node>/app/debug`.
`<node>` is the configured hexadecimal namespace authority (for example `0x11`).
`/sys` is the selected system publication; `/` links the available authorities.

Current build, architecture and PR gates: [Debugger PR guide](debugger-pr.md).
Performance changes and remaining boundaries: [Debugger performance](debugger-performance.md).

## Namespace content first

The namespace already describes itself. The debugger presents that content,
not a parallel set of hand-written descriptions for each kind of record.

- The name segment is the primary identifier; the canonical path remains visible.
  Authored `/sys/lede` is a secondary title, never a replacement for identity.
  Case-only and punctuation-only repetitions are suppressed in the heading.
- `/sys/help` can be plain text or structured `lore` containing a head, body,
  and examples. Readable help appears in the main view without opening a
  generic Documentation drawer. Longer lore and examples disclose progressively.
- Ordinary slots remain directly readable. Clicking a slot name loads its
  actual namespace definition into the inspector without navigating the main view.
  That inspector shows the definition's own lede/help and available references,
  rather than repeating generic kind/state/access labels.
- Canonical `/sys/lash` metadata is folded into Record constraints, separate
  from application slots. Its supplied value and fidelity remain available there.
- Grove roles, actions, norms, sewn views, templates, and runtime events have
  source-derived structural views. Declaration names, export counts, and compiled
  exports belong under Implementation. They do not displace the name's own meaning.
- Each own slot appears once: ordinary Slots, Record constraints, or Source
  slots. Source slots retain exact supplied system metadata and compiled
  representations alongside their semantic presentation; they do not repeat
  the ordinary slots. These independent Mash disclosures preserve their body
  nodes while closed. No raw slot is removed from the namespace response.
- The same partition is used in the reference inspector. Because that panel
  does not mount the semantic surface, its semantic-kind slots remain readable
  under Slots. Slot-definition navigation and full-value actions work in each
  group. A uniformly unknown group of two or more values uses one static,
  accessible completeness note; mixed and standalone values keep their own
  annotations. This never upgrades unknown completeness to complete.

For example, when an SRS instance exists, `/<node>/app` presents the child identifier
`srs` alongside its authored lede. `/sys/about` presents its own help. The debugger does not synthesize an
application purpose from a generic record-kind sentence.

## Component-first interface

The debugger is declared in `src/grove/debugger.grove` and its sibling modules.
Its application slots and inspection role are declared in
`src/grove/debugger/application.grove`; instance seeds live in `instance.grove`.
`x/eden --debug` publishes `/<node>/gov/debug` and instantiates its template at
`/<node>/app/debug`. Add `--srs` for the optional example; `--srs` alone keeps
the ordinary explorer. Page, shell,
inspector and HTML response use real Grove types, norms and sewn values. See the
[declaration audit](debugger-declaration-audit.md) for the request-local adapter boundary.

Newly compiled namespaces emit `#debug-main[data-debug-fragment="inspect"]` as
the complete primary inspection document. The published Grove page owns its heading,
lore, semantic content, slot partition, child destinations, operation slots,
and implementation disclosures. Mash's attributes own accordion, path-preview,
form-label, overflow-mask, and scroll behavior; application initialization does
not replace this fragment. `document-fragment.js` connects namespace value and
lazy child reads without mirroring component open state. There is no legacy
document reconstruction fallback in this build.

Mounted records carrying a typed `mani` in their `pact` slot lead with a Manifest
section: name and authored lore, declared kooks, seed records with inlined Mash
previews, and requested versus granted capabilities. Seed and kook destinations
are rooted at the inspected mount, including history paths. The namespace path
`/<node>/pact` is the mounting behavior, not Eden's manifest. The original manifest slot
remains in Source slots; its structured presentation does not claim the printed
representation is complete.

Namespace rows opt into Mash's `actions-display="overlay"`: pointer hover or
keyboard focus reveals a small bookmark over the row, without reserving width
or shifting text. Touch and forced-colors modes keep separate visible actions.
Authored lore uses `ui-path`'s measured overflow mask, not an application observer.

The debugger uses Mash components and its stock semantic `ui-icon` registry.
There are no application-installed SVG packs, bespoke icons, case-pinning
controls, or comparison workbenches. Native case navigation remains available.

The inspector retains separate **x, y, and z cases**, each with its exact data
and shape counters. The data counter addresses dense local cases `1..N`; it is
not a sovereign epoch, and the shape counter is not used as a history address.
Each Mash accordion starts open with up to five native case links. Older/newer
ranges require no reads; an exact-case input reaches any reported case without
enumerating the whole history. Zero and unreported counters remain distinct.
State, first, now, block, and top metadata stays available below the histories.
These are publisher-owned slots; compact UI labels do not change their stored
identities. A local authority's epoch is never substituted for a system record's
epoch. A newly compiled server is required for changes to the Grove declarations.

- `sh-triptych` owns the sidebar, content, and independently visible inspector.
  Navigation and view controls stay in compact, consistent chrome.
  Both side panes resize through Mash's `ui-resizable` primitives: drag their
  edges, use arrow keys on the separators, or double-click to reset. Preferred
  widths persist locally and are released for the single-pane mobile layout.
- The path trail uses Mash `ui-path`, `ui-menu`, and `ui-scroll-area`. Select a
  segment to open that ancestor; its chevron lists real immediate children.
  `/` or Cmd/Ctrl+L opens the canonical path editor; Escape returns to the trail.
  Menus show up to 20 children and offer the complete parent view for the rest.
  Up to 24 ancestor menu snapshots are retained for 30 seconds across navigation.
  The current path always uses its fresh foreground response; explicit Refresh
  invalidates ancestor snapshots too. This bounds staleness and redundant reads.
- Sidebar, content, and inspector scroll independently with Mash's quiet
  scrollbars. Hover, keyboard, track clicks, and dragging use the primitive's
  native scroll viewport. Touch and forced-colors retain platform indicators.
- `sh-sidebar` contains a filter and three sections in a multiple-open quiet `ui-accordion`:
  Saved, Recent, and Tree. They can all be open or closed independently.
- Saved paths are pages. Selecting one navigates to it and anchors the Tree below
  that page. “Browse entire namespace” returns to the normal root hierarchy.
- Recent is this browser tab's deduplicated navigation trail, not namespace revisions.
- Tree is the default namespace browser, rooted at `/`. Hierarchy disclosure loads
  the immediate children. Every discovered child remains accessible in turn;
  there is no fixed namespace-depth limit. Navigation reveals the selected row's
  ancestors without opening every ancestor's metadata or the selected row's children.
- The hierarchy uses `sh-tree variant="namespace"` over one accessible `ui-tree`.
  Mash's `ui-tree-item` has a reusable `preview` slot before its children,
  including lazy-folder and preview-only record support. The namespace variant
  does not paint revision-graph lanes over containment relationships.
- `activation="split"` separates disclosure from selection: chevrons and
  Left/Right explore; selecting a label opens its record. Expansion never
  navigates the main pane.
- A separate Preview record action opens inline details without opening children
  or navigating. It uses Mash's optional `previewOpen` property: `true`/`false`
  independently control preview visibility; `null` preserves the component's
  earlier expansion-linked behavior. In markup, `preview-open` opens the preview,
  `preview-open="false"` closes it, and omitting the attribute keeps compatibility.
  Escape closes the sidebar preview and returns focus to its tree row.
- Inline previews compose `sh-myth`, `sh-limb`, `sh-slot`, and `sh-pail`.
  Slot keys remain within the record, never fabricated namespace children.
- Main-view child paths are compact rows with deliberate inline preview controls,
  not oversized cards. Reopening a loaded, unchanged preview makes no new request.
- Inspect reads the namespace response, bypassing custom faces.
- Rendered view is a lazy, sandboxed, passive preview. Its scripts and forms do
  not run. Open interface launches the original interactive face separately.
- The activity button opens the actual `/log` journal, not browser navigation.
  The latest 40 events show their task, target, and effect count. Individual
  events expose acknowledgements and outbound effects; earlier paths remain
  accessible. Journal records are read-only in the debugger.
- Only actual server-authored operations are offered. Operations and the
  definition inspector open on demand; authored help is already in the page.

Expansion and section state persist locally. Ordinary navigation preserves the
loaded tree and expanded branches. Inline previews deliberately start closed
after reload. The filter searches loaded paths and their known summaries, preserving
matching ancestors; it does not pretend to search unloaded namespace data.
Saved pages use the existing `shrine-debug.v1.saved` browser storage, so older
saved paths are retained. Storage failure does not prevent browsing.

Sidebar expansion has a bounded queue of at most three reads. The shared
`readPreview` queue for main-view inline previews admits at most two concurrent
reads in FIFO order; foreground navigation does not wait behind that queue.
Starting navigation cancels its outstanding main-view previews. Closing a preview
hides it immediately; an in-flight read may finish and populate its local cache.
If cancellation leaves a preview in the current document, it shows a paused state
with Retry instead of remaining stuck on Loading.
The two queues are separate limits, not a claim that the entire app makes at most two GETs.
Large child lists reveal 60 rows at a time, with “Show more” for the rest.
Failures stay on the affected row with Retry. There is no recursive background
crawl. Previews are reads taken on demand, not an atomic snapshot
of the entire namespace. Refresh invalidates cached summaries and reloads the
current record, visible expanded branches, and deliberately open sidebar previews,
preserving the tree's DOM and expansion. Existing child rows remain in place while
a branch refreshes. Errors do not silently replace the current document.

Narrow viewports reflow the command bar and content rather than shrinking the
desktop into horizontal overflow. At mobile widths, opening the sidebar closes
the inspector and vice versa, including opening the filter with Cmd/Ctrl+K.
Both panels can be dismissed, and mobile controls have larger targets.
Navigation originating in the main document moves focus to the new document
heading; navigation from the tree or chrome preserves that control's focus.
Closing a slot-definition inspector restores focus to its originating slot.
Focus states, coarse-pointer actions, dark mode, and reduced-motion preferences
are supported.

## Runtime and safety

Data comes from the real server-rendered debug response, parsed inertly.
Displayed values use text nodes; source markup is not executed. Navigation
uses same-origin namespace URLs. No fixtures appear in the running interface.

Operations retain server-authored forms and POST to the existing `/op` route.
Published Grove templates expose their existing `/grove/install` form, with
the real source path, version, and chosen instance root. No instance is installed
automatically. A successful response must explicitly acknowledge commitment.
Read-only server responses hide operations and reject programmatic submission.
Pending requests block duplicates; rejected requests preserve drafts. A lost
connection is an unknown commit outcome, never permission to retry automatically.
No speculative dry run or backend capabilities are invented.

Shortcuts: `/` focuses the address and Cmd/Ctrl+K focuses the sidebar filter.
Mash owns disclosure semantics, focus, keyboard navigation, and icon rendering.

The launcher creates a temporary bootstrap snapshot. It is not a verified
checkpoint of subsequent live edits. Keep an active namespace alive when its
state matters; a fresh preview is a different namespace. Preserve its work
directory and log after an abnormal exit, and investigate recovery separately
rather than assuming the bootstrap files restore the latest state.

`x/eden` launches Wisp with `restore_signals=False`, preserving Python's ignored
SIGPIPE disposition for that child. A closed HTTP client should produce a write
error handled by the HTTP foot, not terminate the whole process. This is a local
launcher safeguard, not a global runtime-installation change or a modification
to other running servers. Nonzero and signal exits are reported with their log
path and retained exit status.

## Build and run

Use the [portable build and test commands](debugger-pr.md#build-and-test).
The normal build writes to `.check/debug-assets/foil`, never live served files.
`x/eden --debug` publishes the Grove debugger; add `--srs` only to include
that optional example. Both the launcher and the disposable runtime controller
freeze verified assets with their backend source before serving.

## Verification

Use `python3 x/check-debugger.py --release` with an explicit pinned `MASH_ROOT`.
It compiles the Grove declaration, builds Mash, checks production byte/parser and
request-queue contracts, and runs the consolidated inert browser suite. See
[the PR guide](debugger-pr.md) for prerequisites and disposable real-HTTP checks.

The prototype-era per-feature browser harnesses were removed. They rebuilt
the retired DOM, used obsolete selectors/Preview mode, and repeated asset and
routing setup. Their replacements test the actual Grove output: desktop/dark/
touch layouts, exact inspector cases, shell preservation, navigation and failure
rollback, history, saved paths, filtering, resizing, context menus and stylesheet
fallback. This is targeted coverage, not a claim that every old pixel assertion
was migrated. Component-specific behavior remains tested in Mash.

Bounded journal, immutable value, physical cursor, read-only transport and
owned-runtime tests remain separate: these protect different protocol boundaries.
No tests should use a user's running namespace or restart it for convenience.

## Journal page contract

The new source route is `GET /debug/log`, with an optional exclusive decimal
`before` epoch and `limit` from 1 to 40 (default 40). `view=rendered` is the only
other accepted query option; unknown, duplicate, or noncanonical options are
rejected. Namespace path identity remains `/log`; a cursor is not a child name
or a case number. Epochs, cursors, and exact total counts remain decimal strings
in JavaScript, including values above its safe-integer range.

A paged response exposes `data-paging="journal"`, `data-page-before`,
`data-page-next-before`, `data-page-limit`, `data-page-epoch`, and
`data-child-count` on `#debug-workspace`. Empty cursor attributes mean absent
cursors. Both the event list and navigation contain the same selected physical
keys. An invalid event payload remains an inspectable path, not an omitted row.
The frontend rejects inconsistent metadata and preserves the last good view
when a page read fails. Empty/missing paging flags retain compatibility with
older kernels only for the default page, not an explicit older-page request.

Main-view page links retain cursors through navigation history, reload, and
refresh. The sidebar's explicit **Load older** action appends one bounded page,
preserves existing child state, and retries the same cursor on failure. Its
filter still searches only loaded names. This does not yet virtualize an
arbitrarily large, user-expanded tree or bound every other namespace route.

## Shared record composition

The main view and inspector use `sh-myth variant="embedded"`; inline tree
excerpts use `variant="preview"`. Both select the existing compact Mash size
context. Shared recipes own slot columns, typography, separators, wrapping,
identity, description, metadata, and actions. The app owns namespace reads,
authored excerpt selection, slot-definition routing, and bounded scroll-view
height. Opened record values preserve all text supplied by the runtime; only
explicit inline excerpts shorten text. Upstream rendering limits, if any, must
be audited independently of this frontend guarantee.

The record container, not the viewport, chooses its layout. At 448px or narrower,
keys sit above values. Wider records align ordinary short keys; intrinsically
long keys can wrap across a full row before their value. Complete text and
focused slot actions survive resizing.

Journal event links use Mash `ui-link` controls as well as the pager. Their
projected namespace content changes from columns to compact identity/action/target
lines in a narrow container. The native anchor spans the visual row. Coarse
pointers receive real 44px navigation targets rather than overlapping invisible
hit areas; inline prose links retain text-sized layout.

## Shared path gestures

`path-targets.js` resolves authored namespace destinations across the composed
DOM: native links, Mash path/tree controls, slot-definition buttons and explicit
path targets. It does not recognize arbitrary prose as a path. Editable text
keeps the browser's native text menu; external URLs keep their native link menu.

`path-menu.js` delegates right-click and Shift+F10/ContextMenu to one Mash
`ui-context-menu`. Copy path preserves canonical decoded identity; Copy link
preserves the authored debugger URL, including paging queries and escaped path
segments. Only explicit command selection calls Mash `ui-clipboard`; opening
the menu does not fetch or copy. Escape returns to the actual native invoker.
The shared `showAt(point, invoker)` API supplies positioning without wrapping
or moving any existing control.

`path-preview.js` composes one Mash `ui-preview-card` with an actual Shrine
Myth and Mash scroll area. Pointer/focus intent waits 320ms; a 180ms leave grace
bridges the path and its leaf-out. Authored lore and at most three slots are
excerpts, not a claim of complete values. Long text remains intact in the DOM
with three-line visual clamps. Open record retains the normal native URL.
Snapshots are shared across tree/main/inspector reads in a bounded 60-entry,
30-second cache. New reads use the existing cancellable preview queue.
Navigation cancels pending previews and ignores replacement rows under a
stationary pointer until a new real gesture. Menus opened inside a Myth keep
their containing preview alive through command selection and focus return.

The protected legacy runtime's uncached `/log` root is deliberately not read on
hover: that old route may serialize unbounded history. An already-loaded log
snapshot can still be previewed. Other backend read limits are unchanged.

`tooltips.js` uses one rich Mash `ui-tooltip` with native `ui-kbd` shortcut
rendering for non-path actions. It preserves native controls, restores browser
titles when dismissed, and associates descriptions within a control's own
shadow scope. Passive hints do not consume an owning panel's Escape gesture.
Touch interaction never triggers hover reads or hints.

The path hover/menu suites require `DEBUG_DOCUMENT` to name a saved shell;
all namespace responses are explicit fixtures on inert origins. They never
fall back to the protected runtime or the system clipboard. The tooltip suite
uses an isolated component fixture without any namespace reads. Set
`PLAYWRIGHT_MODULE` when the local Playwright package cannot be discovered.

## Isolated journal verification

The pagination, record, and action browser suites each read one initial `/app`
shell, then intercept fixture navigation and writes. Run them sequentially;
they do not exercise the live journal backend, and their success does not prove
that an already-running kernel has the new route.

Test the actual backend against a disposable 10,000-entry fixture with a compiler
bootstrap template, not a user's live namespace snapshot:

```sh
python3 x/journal-http-test.py --template /path/to/compiler-bootstrap --wisp /path/to/wisp
python3 x/journal-http-test.py --template /path/to/compiler-bootstrap --wisp /path/to/wisp --eden
```

The harness copies the template into a fresh temporary directory, chooses an
ephemeral port, and stops only its own runtime. It leaves HTML/results artifacts
and prints their location. The `--eden` mode instead checks a real disposable Eden
boot, including concurrent ordinary and journal requests. Focused native fixtures
live in `src/foil/tests/journal_page.foil` and `journal_http.foil`.

Pass the default harness's artifact directory through the production frontend
parser without contacting any namespace:

```sh
node x/debug-journal-contract-test.mjs /path/to/journal-http-artifacts
```

Set `PLAYWRIGHT_MODULE` if its module cannot be discovered locally. None of these
isolated checks activates backend changes in the protected runtime on 8138.
