# Native Grove/Foil block document plan

Build a small block document on the text and presentation contracts in
`origin/lf/goo-contracts`. Grove declares the document, actions and views; Foil
implements the model, operations and derived presentations. Shrine owns accepted
state. Goo prepares the display; the shared host and Mash render it and capture
input. BlockSuite is a behavioral reference, not a runtime dependency.

The first delivery is a useful **block authoring prototype**: read a formatted
page, select a block, edit its text and formatting through a Grove form, apply
one atomic change, and insert, split, merge or reorder blocks. Existing plain
inputs edit individual run strings; the page renders the resulting rich text.
Direct rich-text caret editing is a subsequent shared-infrastructure milestone.

This replaces the previous requirement to deliver Unicode shaping and three
editable projections before proving a document. Canvas editing and durable
storage also move to follow-up milestones. The prototype uses the branch's
actual supported rendering coverage and runs within one sovereign lifetime;
it is not a general multilingual editor or a durable notes product.

## Baseline and existing capabilities

Inspected on 2026-10-22 against the local remote-tracking branch
`origin/lf/goo-contracts`, tip `1c3e3e6cea81af2f33b475d8500efabdb0fa3139`.
The shared ancestor with this workspace is `f373423`. This plan does not mean
that branch has been merged or that its tests have been rerun here. Preserve
ongoing workspace changes when integrating it. Record the selected commit,
paired Mash revision, assets and profile hashes in the implementation baseline.

The branch adds:

| Existing contract on the branch | Reuse |
| --- | --- |
| `goo/text = row[goo/runt]`, each run carrying `myth` and `lang` | Canonical rich text, rather than a second span/mark representation |
| `goo/text/pail` and Explorer text formatting | Carry rich text through namespace values into ordinary presentations |
| Run-preserving slicing, normalization and wrapping | Keep descriptors and source text connected through preparation |
| `/sys/font`, `/sys/modifiers`, `/sys/link` | Typed supported font, bold/italic/underline and internal/web-link descriptors |
| Prepared run fragments with boxes, baselines and resolved styling | Shared renderer paints supplied geometry and verified fonts |
| Portable paint, semantics, controls and presentation references | Reuse host contracts instead of parsing generated HTML |
| `pipeline=1` live preparation inspection | Diagnose the actual source-to-display preparation |

Source references below are paths **at the selected branch revision**; some do
not exist yet in the current checkout:

- `extras/mounts/goo/text.foil`, `text_tests.foil`: run values and codecs.
- `extras/mounts/goo/run_style.foil`, `run_style_tests.foil`: supported styles.
- `extras/mounts/goo/prepared.foil`, `PORTABLE.md`, `TYPES.md`: prepared output,
  versioning and limitations.
- `extras/mounts/explorer/goo_bridge.foil`: rich values and portable bindings.

The branch does not provide a rich-text editor. Native inputs remain plain and
single-line; styled input values are rejected. Only `en` and the existing ASCII
measurement coverage are supported. Structured links are descriptive metadata;
they do not supply navigation or invocation authority. HTML paints them as
non-navigating spans. No general caret, range-selection or IME geometry follows
from the presence of prepared rich-text fragments.

Unstyled displays remain version 1; styled displays are version 2. These display
versions do not identify Unicode shaping capability. A future Unicode service,
profile and editing contract need their own explicit capability/version choices.

## Smallest useful experience

A user opens a page containing a heading, two paragraphs, a bullet item and one
read-only reference block. They select a paragraph and edit it in a side form.
The form lists its runs as plain text fields with supported formatting controls.
They can add a run, set bold or italic, and apply the edited block. The formatted
page updates from the accepted document revision.

They insert another paragraph, split one at an explicit run/offset boundary,
merge compatible neighbors, and move a block up or down. A stale second tab
cannot overwrite their work: its apply is refused and its draft is retained.
They can undo an applied change and inspect the underlying document through the
namespace. Closing and reopening a view on the same running sovereign reads the
same accepted document.

This form is a deliberate first editing surface, not a promise of inline typing.
Run boundaries are visible in the form but are not line or word boundaries in
the page. Do not put styled `goo/text` directly into a native input or flatten a
formatted block into a string and discard its descriptors on save.

## Scope

| Deliver now | Follow-up |
| --- | --- |
| One document, one formatted page and one selected-block form | Outline, multiple document navigation and canvas |
| Heading, paragraph, flat bullet item and read-only reference block | Nested lists, code editor, tables, images and asset management |
| Supported text runs and explicit formatting controls | Rich-text caret selection, inline toolbars and structured clipboard |
| Atomic apply, structural operations, bounded undo/redo and stale refusal | Concurrent merge, presence and offline editing |
| Existing profile coverage, with explicit refusal and recoverable drafts | Qualified Unicode shaping, bidi, grapheme editing and real IME |
| Namespace state within one sovereign lifetime | Durable commit acknowledgment, crash recovery and retention |

A reference block names a subject and an allowed presentation slot. Start with
one vetted read-only presentation, for example a cell result. Preserve the
subject's identity rather than copying its displayed text. Reuse the shared
presentation host; if the ordinary page cannot embed it safely, add the narrow
checked adapter or display a reference summary first. Do not claim an actionable
embed until ownership, capture and retained-host behavior are qualified.

## Document state and identity

Keep the first document in one typed aggregate record. One admitted Grove action
can replace the document facet atomically while preserving unrelated facets.
There are no independently writable block mirrors or separate browser document
store. A document root can later own other namespace children without making
them part of this aggregate or source synchronization.

Proposed logical shape, not existing Grove declarations:

```text
Document
  schemaVersion, documentId, revision, nextBlockId
  order: ordered BlockId list
  blocks: BlockId -> Block
  undo, redo: bounded document-content checkpoints

Block
  id, incarnation
  content:
    heading(level, goo/text)
    paragraph(goo/text)
    bullet(goo/text)
    reference(subjectReference, presentationSlot)

Edit request
  expectedDocumentRevision, blockId, expectedIncarnation
  operation arguments
  existing Goo invocation identity and captured receiver evidence
```

Publish this as Grove roles and explicit Foil types/codecs where a closed content
sum is required. Grove's generated conversions and action contracts are the
schema boundary. JSON is transport/export data, not another document model.

Text content is exactly `goo/text`; do not add a parallel `text + marks` store.
The run `myth` holds descriptors, not a writable receiver or executable behavior.
Support only the branch's validated rendering descriptors in new authoring.
Preserve valid stored data during failed edits; reject unknown or unsupported
values explicitly instead of coercing or silently stripping them.

Allocate document-local block IDs on the authority and never reuse the allocator
when restoring history. Undo can restore a deleted semantic ID with a fresh
incarnation. Checkpoints contain content, not recursive copies of undo/redo or
invocation receipts. Cap retained checkpoints and report that bound. Coalesce
adjacent runs only when their complete descriptors and language match.

The first model is a flat ordered block list: every block appears exactly once.
No scenes, assets, nested parent indexes or generic block-plugin registry are
needed. A run index and offset are meaningful only within the captured document
revision. Do not persist them as cross-revision annotation anchors.

## Grove actions and Foil operations

Use ordinary declared actions on the document receiver, backed by pure Foil
validation and transformation. Reuse Goo's authority, publication, revision,
invocation and receipt mechanisms. A document revision field is not a replacement
for the existing namespace receiver checks.

| Operation | First contract |
| --- | --- |
| Apply block draft | Validate and replace one block's typed content; preserve other blocks and unrelated receiver facets |
| Insert block | Allocate an ID and insert a supported block at a checked position |
| Remove block | Remove one block and choose a surviving selection; retain an editable empty paragraph when needed |
| Move block | Change order with up/down commands; preserve identity and content |
| Split text block | Split at a checked run/logical-text offset; preserve descriptors and allocate the following block |
| Merge text blocks | Merge compatible adjacent blocks; retain runs and remove only the merged identity |
| Change kind | Convert paragraph, heading or bullet without losing its text runs |
| Undo / redo | Restore a bounded content checkpoint as a new revision; preserve allocator and receipt identity |

First supported offsets use the baseline's validated ASCII byte boundaries.
They are not a general Unicode anchor API. If a request is outside supported
coverage, refuse it with the draft intact. Line breaks require an explicit
structural operation in this prototype; a single-line input must never silently
turn pasted multiline content into a different document. A future code block
and multiline editor require their own qualified input contract.

One apply is one document transition and one checkpoint. Edit the form locally
and commit on explicit Apply rather than making each keystroke a namespace
mutation. A refusal changes no document content or undo history; shared admission
may retain its failure outcome. Repeated
identified invocations follow the shared Goo retry rules; do not implement an
application-side retry loop that gives an uncertain mutation a new identity.

The existing invocation journal is finite. Measure it and report exhaustion
honestly. Use bounded prototype sessions and preserve drafts on refusal. A
long-running editor requires shared receipt retention/compaction before release;
full-history storage and a custom task journal are not prototype prerequisites.

## Views, drafts and embeds

Use existing Grove views, groups, inputs and actions for the page and editing
form. Render rich text through the branch's ordinary text carrier. Format controls
modify the canonical run descriptors through typed operation arguments.

Selection is a local block identity plus its captured document revision and
incarnation. The generic namespace list source cannot automatically enumerate
logical blocks inside an aggregate. Start with a bounded typed block projection
and explicit target mapping; add a narrow shared source adapter only where the
existing view machinery requires it. Do not create four new document pane
constructors or writable shadow records to get a list.

Shared session machinery retains the selected block and unsaved form values.
Applying from another tab causes stale refusal and retains the draft for explicit
review/reapply. Do not silently rebase it. Refresh, width changes and entering a
reference presentation must not destroy the active input owner. Application
code must not replace an editing subtree with `innerHTML`.

Goo owns page wrapping, line boxes, run positions and paint. The form's existing
native controls retain their established input behavior; their geometry is not
used to position text or selections in the formatted page. No application-specific
contenteditable, canvas text measurer, DOM-range layout or JavaScript rich-text
store is introduced.

Pin the code/profile/fonts needed by the selected branch. The client must support
styled display version 2 before mounting those displays, and diagnose unsupported
contracts. Metadata on a link or reference grants no action authority. Historical
views are read-only and use captured references or an explicit unavailable state.

## Implementation footprint

Start with one mount, proposed as `extras/mounts/block-document/`:

| File | Responsibility |
| --- | --- |
| `main.grove` | Slots, roles, actions, page/form views and initial document fixture |
| `document.foil` | Typed content helpers, operation reducer, projection and bounded history helpers |
| `tests.foil` | Model, operation and integration fixtures |
| `mount.json` | Flat source registration and explicit dependencies |

Use the existing host entry/install convention. Add a small mount adapter only
if required by that convention. Split the Foil module when real complexity
warrants it; a separate core mount, provider framework, worker process and custom
application host are not initial deliverables.

Changes outside the mount must be justified by a demonstrated gap: carrying a
rich value through Grove, rendering a bounded block projection, retaining form
drafts, or admitting a checked read-only presentation. Place such behavior at the
shared Goo/Explorer/Mash boundary and test it there. Do not import the example
application into core runtime code.

## Delivery sequence

| Ticket | Work | Exit evidence |
| --- | --- | --- |
| B0 | Integrate the selected goo-contracts revision and matching renderer/assets without disturbing ongoing changes | Baseline and hashes recorded; existing text/style/prepared/profile and host checks pass |
| B1 | Declare the aggregate, run carriers and pure operations | Round-trip, descriptor preservation, split/merge, ordering, malformed input and bounded undo/redo tests pass |
| B2 | Render a seeded formatted page and select a block into a Grove form | Bold/italic/link runs survive wrapping; page and form identify the same canonical block |
| B3 | Wire explicit Apply and structural commands through existing admission | Create/edit/split/merge/reorder/undo works; two-tab stale refusal retains the draft; exact retry cannot duplicate a mutation |
| B4 | Present one checked read-only reference and qualify the authoring prototype | Referenced result is not copied; refresh/resize preserves input; renderer coverage and session limits documented; repeatable walkthrough |

B0–B4 are the first delivery. A reference summary is acceptable while an embed
adapter is unfinished, but report that explicitly; an inline embed claim requires
its actual retained presentation and binding checks. Each row is reviewable;
these are proposed tickets, not evidence of implemented behavior.

Then choose the next delivery from demonstrated use:

1. Shared direct text editing: prepared carets, logical selections, native input
   capture and composition, using the same `goo/text` values and document actions.
2. Unicode shaping/profile qualification from the
   [Unicode infrastructure specification](goo-unicode-text-infrastructure.md).
   This is required before claiming general multilingual inline editing.
3. Durable native commits, long-session receipts and recovery before presenting
   acknowledged edits as durable saves.
4. Outline/canvas projections, richer blocks, clipboard and transfer after the
   page authoring loop is qualified. Canvas geometry is separate from page order.

The direct-editing and Unicode contracts must be designed together; an ASCII
editing spike does not establish grapheme, bidi or IME correctness. Preserve
branch compatibility rather than assigning Unicode the already-used styled
`display.version = 2`. No calendar estimate is justified until B0/B2 establish
integration cost and the actual shared editing gap.

## Acceptance

Use a bounded fixture with a heading, an empty paragraph, a paragraph with plain,
bold and italic runs, a bullet item, a structured link and a read-only cell
reference. Exercise supported ASCII content and explicit unsupported-input cases.

1. Apply a paragraph draft; the formatted page reads exactly the accepted run
   values. The underlying `myth` descriptors survive wrapping and rereading.
2. Split within a styled run, merge again, and verify logical text and descriptors.
   Empty paragraphs remain selectable and editable through the form.
3. Insert, move, change kind and remove blocks. Order stays valid and IDs are not
   reused. Undo/redo restores content without restoring old action authority.
4. Submit concurrent drafts from two sessions. The stale one fails atomically
   and stays recoverable. A delayed response cannot overwrite a newer display.
5. Retry an identified Apply after an interrupted reply. It does not apply twice.
   Bounded journal/history exhaustion produces an explicit recoverable refusal.
6. Change width and refresh while a form is dirty. Input values, focus and selected
   block survive. Unsupported rendering/input never strips stored data.
7. Read the reference subject independently and compare it with the page's
   presentation. A derived subject remains read-only; metadata alone cannot
   invoke actions or bypass receiver checks.
8. Close and reopen the view on the running sovereign. Accepted state remains;
   unsaved drafts are clearly distinguished. Restart persistence is not claimed.

Run meaningful Foil model tests, branch text/style/profile conformance checks,
and shared host/browser checks for affected contracts. The example needs a real
browser walkthrough, not only generated HTML or model tests. Record commands,
versions and results; branch documentation's historical test counts are not a
substitute for executing the integrated baseline.

Measure first and warm page preparation, apply-to-display latency and payload
size on 20- and 100-block fixtures. Initial local target: warm p95 at most 150 ms
from explicit Apply to matching display on the 100-block fixture, reported with
hardware and build details. This is a proposed target, not a benchmark claim.
Report cold compiler/startup time separately. Bound run counts and text sizes;
refuse excess rather than silently truncating to a generic list source limit.
Virtualization and 1,000-block editing are follow-up work driven by measurements.

## Completion boundary

B0–B4 complete a native block authoring prototype using real rich-text values,
existing input contracts and one authority. They do not complete direct rich-text
editing, Unicode infrastructure, durability or BlockSuite parity. Keep those
capabilities named separately so the first working document does not grow into
a workspace framework before anyone can use it.
