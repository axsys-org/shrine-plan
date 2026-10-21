# Goo Grove Mash document workspace implementation plan

Build one authoritative document in Shrine and expose it simultaneously through
Goo page, outline, and canvas projections. Grove declares the application,
types, views, and actions. Goo prepares every content box, line, glyph advance,
caret stop, and selection rectangle. Mash captures interaction and paints those
prepared results.

The first delivery is reusable Unicode text infrastructure: a versioned Goo
text service, pinned fonts, prepared editing geometry, and a matching Mash
painter. The first document prototype uses that infrastructure in all three
views. The next delivery adds durable storage, history, formatting, and transfer.
There is no separate ASCII-only editor release.

The [Unicode infrastructure specification](goo-unicode-text-infrastructure.md)
defines the service boundary, font policy, painter, and first implementation
tickets. All new APIs and modules in these documents are proposed work.

## Scope and decisions

1. The document is typed Foil data held by one Grove application record.
   JSON is a versioned transport and export format.
2. Application composition is Grove/Goo. Shared interaction code belongs in
   Mash and the existing Goo host. The application mount has no custom browser
   editor or layout code.
3. There is no BlockSuite, ProseMirror, TipTap, Yjs, or independent JavaScript
   document store in this implementation. Pinned HarfBuzz and ICU libraries
   provide low-level text services beneath Goo.
4. Goo retains server layout ownership. Mash may measure its viewport and map
   pointer coordinates, but may not measure document text, choose wrapping,
   infer line heights, or use CSS layout as document geometry.
5. Unicode text infrastructure precedes the editor. The first release qualifies
   accented Latin, combining marks, Hebrew/English, Arabic, CJK, and emoji
   sequences against a pinned font bundle. Uncovered glyphs use an explicit
   prepared fallback without replacing stored text. Font coverage and resource
   limits remain explicit; an ASCII character whitelist does not define them.
6. The first writer workflow is local and single-user. Multiple browser tabs
   use revision checks; conflicting edits remain recoverable and are not
   automatically merged.
7. Page order and canvas placement are independent. Reordering a paragraph
   changes document order. Moving its canvas occurrence changes its placement.
   Both actions target the same block.
8. Start with one document, one canvas scene, and at most one canvas occurrence
   per block. Keep scene and occurrence identities in the protocol so later
   multiple placements do not require changing block identity.

First document proof: multilingual paragraph, heading, and code blocks;
insert/delete text; split and merge; reorder; selection shared across all three
views; canvas move and width resize. The useful-editor milestone adds bullet
items, images, basic marks, undo/redo, structured clipboard, export/import, and
durable restart.

Tables, comments, embeds, freehand drawing, rotation, arbitrary connectors,
multi-document navigation, multiplayer, and offline editing are later work.

## Implementation baseline

The source baseline inspected on 2026-10-20 is Shrine `73166778`, local Mash
`568b50d`, and standalone Haskell Goo `2f89dc4`. Shrine's Extras configuration pins
Mash `16b8a9079e8a45dc2681cf3210e1d186e5cbe622`.

Use Shrine's Foil Goo implementation as the production base. Use the Haskell
checkout only as a reference. Select a Mash development branch containing the
pinned patch implementation; do not reset the existing local checkout to make
the versions match. Subsequent paired releases update the immutable pin and
import the matching renderer profile together.

Useful existing code:

| Existing source | Reuse |
| --- | --- |
| [Goo preparation](../../extras/mounts/goo/prepared.foil) and [rendering contract](../../extras/mounts/goo/HTML.md) | Validated geometry and renderer ownership |
| [Grove views](../../src/foil/grove_views.foil) | Constructor checking, declared panes, explicit selection ports |
| [Goo runtime](../../src/foil/goo_runtime.foil) | Authority, revision checks, invocation capture, action admission |
| [Goo session](../../extras/mounts/explorer/goo-session.js) and [panes](../../extras/mounts/explorer/goo-panes.js) | Selection, retained work, composition and departure lifecycle |
| [Patch host](../../extras/mounts/explorer/goo-patch.js) | Scene admission, occurrence identity, graphical operation bindings |
| [Hello Grove](../../extras/mounts/hello-grove/main.grove) | Declarative application composition |
| [Grove playground model](../../extras/mounts/grove-playground/model.foil) | Typed aggregate data with separate placements |
| [Mash document model](../../../mash/apps/catalog/src/stories/documents-model.ts) | Examples of marks, editing operations, and history fixtures |
| [Mash workspace architecture](../../../mash/docs/document-workspace-architecture.md) | Document, session, accessory, and projection boundaries |

Mash's catalog code is a behavioral reference. Its localStorage store, direct
DOM editing, canvas geometry, and notebook snapshots do not become a second
authority alongside Shrine.

## Infrastructure before the document editor

The shared text service is a persistent native worker built with pinned
HarfBuzz and ICU. Goo's trusted host connects to it through a checked,
versioned request/response protocol. Use a worker boundary first; a runtime
primitive is an optimization only if profiling later justifies it.

ICU supplies segmentation, candidate line breaks, and bidi analysis. HarfBuzz
shapes explicitly selected font runs. Goo chooses actual line breaks, requests
reshaping at those boundaries, applies per-line bidi ordering, and prepares the
final positions. The worker has no document mutation API and does not run a
paragraph or page layout engine.

Mash's profile owns the font manifest, fallback order, styles, and paint
recipes. It identifies the matching engine/data revisions. The server never
consults installed system fonts or downloads a font during a preparation.
Version 1 retains its existing ASCII semantics for compatibility; new document
surfaces explicitly request the Unicode version 2 profile.

The initial version 2 painter consumes positioned glyph outlines through SVG
paths and cached definitions. A semantic text layer and native input capture
provide accessibility and text operations without driving visual geometry.
Monochrome emoji are sufficient for the first font bundle; color glyph painting
is a separately declared capability. Do not pass shaped runs back through
ordinary browser text rendering.

Keep workers and fonts loaded. Cache analysis independently of width, shaped
runs by their complete context, and final preparation by layout context. The
first multilingual text specimen must pass painting, caret, real IME,
accessibility, and local latency gates before the document UI is assembled.

## State and identity

Use a single aggregate document record initially. An operation can then update
text, structure, placements, history, and its receipt as one staged namespace
transition. Avoid separately writing each block and repairing partial edits.

The following are proposed logical records, not existing Foil or Grove APIs:

```text
Document
  schemaVersion, documentId, revision, nextBlockId
  rootChildren: ordered BlockId list
  blocks: BlockId -> Block
  scenes: SceneId -> ordered Placement list
  assets: AssetId -> AssetMetadata

Block
  id, incarnation, kind, schemaVersion
  props, text, marks, children: ordered BlockId list

Placement
  occurrenceId, blockId, x, y, width, order

TextAnchor
  documentId, blockId, incarnation, utf8Offset, affinity

EditorSelection
  text: anchor + focus, or blocks: ordered BlockId list

EditEnvelope
  documentId, baseRevision, invocationId, clientSessionId, sequence
  selectionBefore, operations, historyGroup
```

Block IDs are document-local, allocated by the authority, and never reused.
Undo restores a removed block's semantic ID with a new incarnation so old
captures do not regain authority. Goo compiler node IDs and canvas occurrence
IDs are render identities, never persisted text anchors.

Parentage is defined only by ordered child lists. Validate unique membership,
reachability, kind-specific nesting, and absence of cycles. Derived parent and
lookup indexes are caches. An outline initially shows the entire block tree in
document order; a headings-only outline can be a later filtered projection.

Placement width is authored; content height is derived by Goo. Persist signed,
finite model coordinates using the checked numeric codecs. Do not copy the
playground's application-specific biased-coordinate representation.

Text offsets are UTF-8 byte boundaries, matching Foil's byte-oriented strings.
The input adapter converts browser UTF-16 offsets explicitly. The server
validates scalar boundaries and requires grapheme boundaries for user cursor
movement and deletion. It never assumes bytes, code points, UTF-16 units,
graphemes, and shaping clusters are interchangeable. Normalize CRLF and CR to LF
on ingestion; do not otherwise normalize Unicode or change content during
rendering.

Selection, scroll position, viewport, active tool, pending input, and composition
are local session state. History stores the selection before and after an edit
for restoration. Ordinary selection or camera changes create no undo entries.

## Operations and transactions

Implement one pure operation reducer returning either a complete next state or
a typed rejection. Initial operations are:

| Operation | Required behavior |
| --- | --- |
| `replace_text` | Replace a logical range; update marks and anchors |
| `split_block` | Split content and marks, allocate the following block, move the caret |
| `merge_blocks` | Merge compatible adjacent blocks and map affected anchors |
| `insert_blocks` | Allocate IDs and insert a validated slice |
| `remove_blocks` | Remove a subtree and its placements; select a surviving neighbor |
| `move_blocks` | Reorder/reparent atomically; reject cycles |
| `set_block_kind` | Convert only when the target schema can preserve the content |
| `set_mark` | Add/remove a supported mark over a logical range |
| `set_placement` | Move or change the width of an existing scene occurrence |
| `undo` and `redo` | Apply recorded semantic inverses and restore valid selections |

Enter splits; Backspace at a block start merges compatible siblings. A
cross-block deletion is one operation batch with one history entry. Code blocks
retain Enter as a newline. Initial list nesting is restricted to explicit
bullet-item children.

All toolbar, keyboard, menu, outline, and canvas actions go through the same
Grove action binding and existing Goo invocation capture. The action validates
the document revision, block incarnations, schema, and authority. Browser
properties cannot select a different writable receiver.

One mutation is in flight per document session. Buffer subsequent edits as
ordered logical intents. After acknowledgment, map their anchors through the
accepted operation results before sending the next batch. A stale base revision
caused by another writer stops the queue and retains its pending text for
recovery; this release does not claim concurrent text rebasing.

History grouping is separate from transport batching. Consecutive typing may
share a history group; selection changes, block changes, formatting, paste,
composition completion, and structural commands close the group.

## Prepared text and document layout

Introduce the version 2 Unicode prepared-text contract and paired Mash profile
through the infrastructure tickets. Preserve version 1 behavior for existing
consumers; do not reinterpret the current `lines` field or change legacy
empty-text sizing.

A prepared text block must carry:

- Document/block/incarnation identity, document revision, and draft sequence.
- Profile revision, content hash, available width, scale, and direction.
- Explicit lines, visual runs, styles, baselines, and advance positions.
- Glyph/font/paint references and logical text ranges mapped to visual runs.
- Valid caret stops with affinity and their rectangles.
- Hit regions and enough range geometry to paint logical selections.
- An editable empty-line box and a final-newline caret line, even where the
  static version 1 text primitive has no line box.

The Unicode service supplies shaped runs and cluster maps for the selected
fonts, language, script, direction, and style. Goo derives lines and editing
geometry from them. Store logical-to-visual maps and boundary affinity from the
start, including ligature caret policy and mixed-direction selections. Rich
text uses this same path when marked spans are added.

Mash uses explicit positions. It may search prepared hit regions, transform
coordinates, and paint carets/selections. It may not call `measureText`, derive
document geometry from DOM `Range` rectangles, or let a contenteditable region
rewrap the document.

The page projection prepares an ordered vertical document surface. The outline
prepares compact block summaries. The canvas prepares each block at its
placement width. The same block can therefore have different line breaks in the
page and canvas while sharing all content and identity.

Goo also supplies outline indentation, row heights, disclosure boxes, and row
positions. Reuse Mash's tree interaction and accessibility conventions without
using an independently laid-out tree as the geometry authority. Workspace
chrome may allocate pane rectangles; document content inside those rectangles
always follows Goo preparation.

Each view is prepared from the same captured document revision. On a commit,
invalidate all three views. Stage their new displays and publish a coherent
workspace revision; late responses from another width, profile, incarnation, or
draft cannot overwrite the current display.

During canvas dragging, Mash may translate the existing prepared occurrence as
a transient gesture preview. During width resize it shows an outline and
requests a Goo preview at the proposed width; existing text is not stretched or
rewrapped by the browser. Goo supplies the accepted height and final geometry.
Panning and zooming transform the prepared scene without changing text layout.

Cache preparation by content/marks/schema/profile/context. Recompute changed
blocks and dependent following positions, preserving unaffected occurrence
shells and active input capture. Start with correctness before virtualization.

## Input and composition

Add a shared Mash `goo-text-editor` element. It contains a native input capture
surface and a Goo-prepared visual surface. The native control supplies keyboard,
clipboard, accessibility, and OS composition events; its own layout is never
used for the visible document. Position the capture surface using Goo's caret
rectangle, including the canvas transform.

Use `beforeinput`, `input`, and composition events to produce logical intents.
Retain a fallback for browser event differences. During IME composition, keep
the native capture node alive and preserve its buffer. Request read-only Goo
preparation of the draft text to paint preedit content; commit the completed
composition as one transaction. Cancellation must restore the accepted content.
Native candidate windows remain OS input UI, not document layout.

The read-only draft operation applies pending intents to an ephemeral copy of
an authorized document revision and invokes the same Goo preparation. It never
changes namespace state, history, receipts, or persistence. Bound draft payload
size and work; accept neither arbitrary HTML nor executable source.

Pending text can advance ahead of the last painted geometry. Only a matching
Goo response advances visible text and its caret together. Do not invent
positions for unprepared text. On slow or disconnected responses, retain the
buffer and show its pending state. Unsupported input remains recoverable without
being committed as silently altered content. Missing font coverage is handled
by a Goo-prepared fallback while preserving valid text; it does not invoke a
browser font fallback.

Use one active text capture session per document workspace. Clicking the same
block in another view transfers the logical selection and keeps pending edits.
Toolbars retain that selection without starting another text owner. Browser
undo is intercepted and translated to document history.

The first input spike must include VoiceOver and keyboard-only use, capture
focus, copy/paste, and native composition events. A visually correct painter
with an inaccessible editing surface does not pass.

## Projection and selection integration

Current Goo selection sources describe namespace records or patch occurrences.
A document's blocks are logical members of an aggregate, so add an explicit
document-block source adapter. Do not create independently writable mirror
records merely to make the existing list source accept them.

Register the adapter through trusted host configuration, like the existing
patch query provider pattern. Its records include document path, document ID,
block ID, incarnation, order, parent, and revision. Extend capture validation to
resolve those references against the current aggregate.

Proposed pane constructors are `document_selection`, `document_page`,
`document_outline`, and `document_canvas`; proposed view content uses
`editable_text`. These names require compiler, IR, host, and renderer changes
before they are valid Goo syntax.

The workspace declares one selection owner and passes its port explicitly to
Page, Outline, and Canvas panes. Text selections identify their containing
blocks. Canvas occurrence targets map to those block identities before entering
the shared owner. Preserve encounter/incarnation checks and departure guards.

The current patch population accepts passive Goo content. Extend it with a
checked editable-text occurrence binding instead of allowing arbitrary actions
inside scene data. Bind that occurrence to a statically published edit action,
the document provider, and its current block evidence. The shared text editor
then follows the same invocation and input lifecycle in both page and canvas.

The outline offers the same reorder commands as the page. Initially use buttons
and keyboard commands for reorder; semantic drag can reuse the commands after
the basic contract is proven. Do not rely on the generic physical-child listing
order or silently truncate a document to its existing finite source limit.

## Repository changes

Names marked new are planned additions. Mount source files remain flat; logical
module paths are declared in `mount.json`.

| Location | Responsibility |
| --- | --- |
| `extras/mounts/goo/native/text-service/` — new | Persistent native HarfBuzz/ICU worker, protocol codecs, glyph outline extraction and service tests |
| `extras/mounts/goo/text.foil`, `text_codec.foil`, `text_layout.foil` — new | Typed text-service continuation, response validation, Goo-owned line fitting and editing geometry |
| `extras/mounts/goo/host/text_service.py` — new | Shared worker lifecycle, requests, cancellation and revision checks for CLI and live preparation |
| Goo/root Nix package definitions and locks | Pin service build, HarfBuzz, ICU and Unicode data; include them in production fingerprints |
| `extras/mounts/document-core/` — new | `model.foil`, `operations.foil`, `selection.foil`, `history.foil`, `codec.foil`, `tests.foil`; typed document rules without DOM or persistence I/O |
| `extras/mounts/document-workspace/` — new | `main.grove`, `mount.foil`, `projection.foil`, `storage.foil`, `host.py`, fixtures and browser checks; `/document-workspace` entrypoint |
| `src/foil/goo.foil`, `grove_views.foil`, `goo_runtime.foil` | Declared document constructors, typed source/binding adapters, capture validation, compatible receipt extension |
| `extras/mounts/goo/types.foil`, `codecs.foil`, `layout.foil`, `prepared.foil`, `html.foil` | Version 2 text integration and profile dispatch; preserve `ascii.foil` for version 1 |
| `extras/mounts/explorer/goo_document.foil`, `goo-document.js` — new | Generic host lowering, session integration, input/projection reconciliation |
| Existing Explorer session/actions/panes/patch files | Reuse established lifecycle and operation paths |
| Mash `packages/shrine-components/src/text/` — new | Reusable version 2 glyph painter, semantic text and native input capture |
| Mash `packages/shrine-components/src/document/` — new | Document composition, prepared selection overlays and Goo adapter over the shared text element |
| Mash `packages/goo-profile/` on the selected baseline | Unicode profile, pinned font/fallback bundle, geometry schema and conformance fixtures |
| `src/foil/eden.foil`, `http_foot.foil`, host mount hooks as needed | Durable commit acknowledgment boundary; no renderer-specific storage logic |

`document-core` depends only on core Foil/data facilities. `document-workspace`
depends on `document-core`, Explorer, and codecs, and installs the domain
providers. Explorer's shared bridge consumes declared provider contracts rather
than importing the example application. No reverse dependency from Mash to the
application is introduced.

## Storage and invocation receipts

Two existing constraints must be addressed before calling this a usable editor:
the development launcher seeds a fresh namespace on restart, and the generic
Goo invocation journal rejects new identified actions after 1024 entries.
Typing must not exhaust that journal or require restarting to continue.

Add a trusted receipt-store capability for document actions while preserving
the default behavior of existing applications. Store the document revision,
history transition, request identity/hash, and operation outcome together.
Repeated identical requests return the same outcome; changed payloads with the
same identity fail. Compaction must retain non-replayable identity information:
an expired response cannot turn an old edit into a new mutation.

Provide an explicit state directory through the application host, initially
`GOO_DOCUMENT_STATE_DIR`. This is a proposed option, not an existing launcher
feature. The host owns disk I/O; Foil owns the validated record format and
replay semantics.

Stage one validated transition, append its document/history/receipt record to a
checksummed durable log, flush it, publish the namespace transition, then
acknowledge. The document commit path remains serialized throughout. A crash
after logging but before publication recovers by replay; a crash before durable
logging cannot have produced a successful acknowledgment.

Checkpoint complete states with atomic replacement and retain enough log to
recover the last acknowledged operation. On startup, load and validate stored
state before opening the workspace; seed only a genuinely absent document.
Reject unsupported schema versions without overwriting them. Export/import is
useful recovery functionality, but does not substitute for durable restart.

The first durability patch must verify the supervisor's actual effect and
publication boundary. If the current host cannot enforce the sequence above,
extend that boundary before exposing a “saved” outcome. A save performed after
an already successful action response is insufficient.

## Delivery sequence

Each row is a reviewable change with a required exit condition. Estimates are
engineer-days for planning, not commitments. Text infrastructure is delivered
before the first document prototype. The document model can proceed alongside
it once the text/anchor contract is fixed.

| Change | Scope | Depends on | Exit condition | Effort |
| --- | --- | --- | --- | --- |
| T1 | Compatible baseline, native service packaging, protocol and font manifest | — | Reproducible build; capability handshake identifies every text input dependency; version 1 gates pass | 2–3 |
| T2 | ICU analysis, pinned fallback and HarfBuzz shaping | T1 | Multilingual analysis/shape fixtures pass with correct UTF-8 maps and no system-font lookup | 5–8 |
| T3 | Goo line fitting, line-specific bidi/reshaping, prepared editing geometry | T2 | Wrapping, ligatures, empty lines, carets and selections pass the text corpus | 7–12 |
| T4 | Mash SVG glyph painter, semantic layer and native input spike | T2, T3 | Geometry follows Goo; real IME, copy/paste, focus and VoiceOver work | 6–10 |
| T5 | Persistent host integration, incremental caches and profile coexistence | T3, T4 | CLI/live paths use the same service; late responses and invalidations are correct; latency measured | 5–8 |
| T6 | Cross-platform/font/browser qualification and paired infrastructure release | T5 | Required multilingual corpus passes on supported hosts and browsers | 4–6 |
| D1 | Typed aggregate, IDs, codecs and pure document operations | T1 | Model round-trips; operations preserve Unicode and reject invalid anchors atomically | 4–6 |
| D2 | Grove document source/selection adapter and three projections | D1, T6 | Same multilingual block selected and rendered in all views from one revision | 4–6 |
| D3 | Shared edit loop; split/merge, reorder, canvas move/resize | D2 | Page/canvas edits update all views; caret and composition survive projection changes | 5–8 |
| D4 | History, anchor restoration and durable receipt semantics | D3 | Undo/redo preserve grapheme boundaries; 10,000 edits work; retries never duplicate edits | 4–7 |
| D5 | Durable host commit and recovery | D4 | Crash/restart tests recover exactly the acknowledged state and receipts | 6–10 |
| D6 | Marks, bullets and structured text clipboard | D3, D4 | Marked multilingual split/merge and slices round-trip | 5–8 |
| D7 | Images, asset storage, export and validated import | D5, D6 | IDs/assets remap correctly; semantic export preserves text; import is atomic | 4–7 |
| D8 | Document-scale, browser/accessibility qualification and paired release | D5, D6, D7 | Full workflow, storage and performance gates pass | 5–8 |

T1–T6 deliver reusable text infrastructure. D1–D3 deliver the first shared
document proof; D4–D8 deliver the useful editor. For two engineers, use an initial
budget of 6–10 calendar weeks for infrastructure, 10–16 weeks cumulatively for
the document proof, and 16–24 weeks for the useful release. Re-estimate after T4
proves the native-input and exact-painter combination. These broader ranges
include the Unicode work that the earlier ASCII-first sequence deferred.

The immediate tickets are T1 and T2. Start D1 once T1 fixes identity, offset,
and profile contracts. Preserve the text-first gate before assembling the
document prototype.

## Acceptance and performance gates

The proof fixture contains a heading, multilingual paragraphs, an empty
paragraph, and a code block. Its text includes the required corpus from the
infrastructure specification. All three views are open at once.

1. Select a paragraph in the outline. Page and canvas indicate the same block.
2. Type in its page occurrence. The canvas receives the same accepted text.
3. Continue editing in the canvas with the same logical caret and pending queue.
4. Press Enter to split, then Backspace to merge. All views agree on identities,
   order, content and selection.
5. Reorder in the outline. Page order changes; canvas placement stays fixed.
6. Move and resize a canvas occurrence. Page order and page width stay fixed;
   canvas text receives freshly prepared Goo geometry.
7. Change page width while typing. Stale geometry cannot replace the new
   context, and focus/composition survive.
8. Undo text, structure, reorder, and placement after history is added.
9. Restart the server after storage is added. The same IDs, content, placement,
   history and acknowledged outcomes return.

Automated validation includes pure operation/inverse tests, malformed protocol
rejection, browser coordinate checks against prepared data, delayed/reordered
responses, duplicate invocation replay, 10,000 sequential edits, and crash
injection before/after each durable commit boundary.

Retain the existing compatibility checks:

```sh
python3 extras/mounts/goo/scripts/sync-mash-profile.py --check
WISP=/path/to/locked/wisp python3 extras/mounts/goo/scripts/check-profile.py
node --test extras/mounts/explorer/tests/*.test.cjs
```

Add `extras/mounts/goo/scripts/check-text.py` in T6 for the native service,
Unicode conformance corpus, version 2 preparation, and paired painter. This is
a planned command. Version 1 conformance remains a separate compatibility gate.

Add mount tests and browser drivers as part of the corresponding changes:

```sh
# Planned commands; the document mounts and driver do not exist yet.
WISP=/path/to/locked/wisp python3 extras/x/check --mount document-workspace
node extras/mounts/document-workspace/check-browser.mjs \
  http://127.0.0.1:8137 /path/to/compatible/mash /tmp/goo-document-check
```

Use the paired Mash build's browser tooling for renderer conformance and
cross-browser runs. Run storage crash tests against an isolated state directory.

Use 100-block and 1,000-block documents for scale, including one 20,000-character
text block. No document may be silently shortened by the generic 64-member
source limit. Report preparation time, end-to-end input latency, payload size,
mounted node count and retained input/receipt memory.

Initial local-host targets are p95 at most 50 ms for incremental preparation and
120 ms from input to a matching painted display on the 100-block fixture.
Record the hardware, build and sample count with measurements. These are
acceptance targets, not existing benchmarks. A 1,000-block edit should avoid
rebuilding every block's text layout. Long code/text lines must remain bounded.

Simulate 150 ms and 500 ms transport delay plus disconnection. Content and
ordering must remain correct; full WAN typing responsiveness is not promised.
If the local latency gate fails, profile Foil evaluation, serialization,
preparation caching and DOM admission before expanding features. Do not solve
the failure by transferring wrapping to the browser. Running the same Goo
engine nearer the user is a later deployment option that needs its own
conformance gate.

Browser qualification covers Chromium, Firefox and WebKit; keyboard-only use;
VoiceOver; zoom/text scale; focus movement; and real OS IME. Synthetic
composition events alone are insufficient. Test both page and transformed
canvas editing. Audit allowed viewport measurements separately from prohibited
document text measurement.

## Later capabilities

Additional scripts and font styles extend the pinned profile and its
qualification corpus. Color glyph painting, variable font axes, vertical
writing, language-specific hyphenation, and browser-side execution of the same
Goo engine are separate capabilities. They do not justify delaying the
required multilingual coverage until after the editor.

Exact visual export uses the prepared glyph painter. Semantic HTML export
preserves Unicode and marks but can reflow in its consuming application; it
does not claim to reproduce Goo geometry outside the prepared renderer.

Collaboration comes after the single-writer transaction, anchor, receipt, and
durability contracts are stable. It requires an explicit native merge/rebase
model, presence separate from document history, selective undo, reconnect and
offline behavior. Revision rejection alone does not meet that requirement.

Broader canvas tools, comments and tables then use the same operations,
selection, prepared geometry, assets and persistence contracts.

## Completion criteria

The infrastructure release is complete when T1–T6 pass the required
multilingual, geometry, input, accessibility, compatibility and performance
gates.

The first document proof is complete when D1–D3 pass the shared-document
workflow and local latency gate using that released infrastructure, with no
application-specific browser editor code.

The useful release is complete when D4–D8 additionally pass durability,
history, transfer, scale and accessibility qualification. Published font/script
coverage remains explicit. Full BlockSuite parity is not a completion criterion
for this sequence.
