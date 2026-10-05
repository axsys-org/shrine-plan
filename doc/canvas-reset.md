# Canvas: wireframe outward, connect inward

Approved 2026-10-04. Reference and proof evidence:
`~/.local/share/shrine/reviews/canvas-reset-20261004/`.

## Product authority and reference alignment

`doc/grove-product.md` preserves the user's supplied "Grove: what we are building"
verbatim. It defines the product and feel. The archived v2 demos give the visual
reference, and their REFERENCE.md supplies timestamps and failure cases. This file
is the implementation and acceptance plan. The user's later JS/NS execution choice
and prepared-first-generation foundation refine the engineering interpretation;
references saying every calculation must execute natively do not override them.
The optional engineering appendix mentioned in the product description was not
supplied and is not assumed to be a dependency.

## Product target clarified by the user (2026-10-04)

Build the real, freely interactive version of the supplied canvas and renovation
movies, as close as practical in visual quality, behavior and response speed.
The demos are the product bar, not decorative inspiration. Slower model generation
is expected sometimes; it is a reason to keep useful work local and progressive,
not to lower the ambition to forms, static mockups or a technically connected shell.

The reviewed reference includes both Downloads MP4s, both reference archives and
both REFERENCE documents. Renovation demonstrates the primary connected visual
flow; the Task demo covers recursive construction, identity, reuse and persistence;
the node demo expands the visual vocabulary. Scripted timings are target feel,
not measured evidence. Preserve the approved JS/NS execution-placement policy.

Match these observable behaviors in real use:
- Drawing, dimensions, dragging, resizing, selection and camera motion respond
  locally; linked plan, 3D, chart and total update together during wall edits.
- Sketch regions progressively become polished, usable presentations in place.
  Keep the layout stable, focus and drafts intact, and other regions interactive.
- Selecting a subject carries across presentations. Swapping bars for a donut
  preserves bindings and selection. Existing adapters and presentations reuse
  without model calls; saved quotes remain frozen while the live views change.
- Upstream/downstream navigation preserves context and unfinished work. Drop
  choices and proposals appear beside the affected connection, not in a global
  wizard. Successful constructions remain reusable on different compatible data.

Reduce avoidable model latency: send the structured sketch and only relevant
contracts; ask for small typed patches; cache pinned catalog metadata and compatible
reuse results; keep expensive rendering resources warm and bounded; validate and
show each complete region when ready. Do not serialize unrelated regions behind
one request or wait for semantic ranking before showing cached compatibility.
Cancel obsolete generations and prioritize the active region. Reuse established
operations immediately. New implementation work stays in the background while
placeholders and established regions remain editable. No artificial stream delays.

Compare real recordings side by side with matching demo moments. Record input to
first feedback, gesture completion to first useful validated region, full readiness,
linked-update frame times and owner acknowledgement separately, including cold and
warm runs and injected 2 s response delay. Retain the existing p95 targets. Exercise
unscripted geometry and different inputs; a replay of the reference sequence alone
does not pass. When a target is missed, identify whether input, computation,
rendering, model, validation or commit time accounts for the delay and improve the
responsible path. A fast placeholder alone does not prove a responsive finished UI.

## Construction

### Prepared web environment from the first generation

Start the authoring model in a working, styled web environment before its first
request, including for novel interfaces. Do not require building a proprietary
catalog first, or discovering a missing catalog item before permitting custom UI.
Supply pinned, prebundled libraries, shared theme/fonts/icons, editable working
examples, region mounting and the typed NS bridge. Give the model a short capability
index plus relevant APIs/examples on demand, not the entire library source in every
prompt. Retain the running preview/build environment across edits.

The researched candidate stack is React + shadcn/ui/Tailwind for styled controls,
Konva for 2D manipulation, Three.js/R3F/Drei for 3D, ECharts for charts, and React
Flow for node views. Web Awesome/Lit with direct JS graphics libraries is the
alternative compatible with the current plain-JS shell. These are candidates,
not installed dependencies or a measured performance verdict. Choose a coherent
starter through a bounded integration comparison on the first renovation regions;
do not rebuild engines these libraries already supply or rewrite the whole shell
solely to adopt a library. Add the necessary NS correspondence and commit bindings.

From its first pass the model may compose supplied components, edit their source,
or author custom HTML/CSS/JS, Canvas/SVG/WebGL and scoped computations. Validate
complete modules and their contracts before activation, keep the last working
region on failure, and preserve drafts during replacement. Reusable spec generation
is an optimization, not an expressive ceiling or a mandatory preliminary step.
Successful implementations become versioned, discoverable NS constructions.

Research references:
- v0 prepared starters: https://v0.app/docs/design-systems-2
- Editable source components: https://ui.shadcn.com/docs/new
- 2D manipulation: https://konvajs.org/docs/react/Transformer.html
- 3D components: https://r3f.docs.pmnd.rs/getting-started/introduction
- Custom charts: https://echarts.apache.org/handbook/en/how-to/custom-series/
- Custom node views: https://reactflow.dev/learn/customization/custom-nodes
- Plain HTML alternative: https://webawesome.com/support and https://lit.dev/docs/v3/

### Sketching acceptance (product sections 1 and 3)

Use precise local geometry with the rough pencil appearance: grid/edge snapping,
alignment guides, nested containers, labels typed into selection, field/button/list/
table shorthand, visual stamps, anchored behavior notes and connectors that remain
attached when regions move. Recognize simple freehand boxes/lines/arrows locally
on pen-up; preserve ambiguous strokes as annotations without inventing text or
meaning. Sketching never requires a model request. Each operation supports local
undo and draft persistence. Keep actual data drawing inside an established editor
distinct from sketching the interface around it.

### V2: fast, high-ceiling presentations

The revised experience reference is archived under the evidence directory at
`reference-v2/grove-reference/`. Read its REFERENCE.md alongside the user's
Downloads/REFERENCE(1).md and accompanying catalog note. These are experience
references, never scripted product code. Renovation is now the primary visual
proof; the original task flow still supplies required interaction cases.

Use four execution tiers as available paths, not sequential prerequisites or
product modes. Custom generation is available on the first request:

- Tier 0: create an editable local placeholder in the first frame. Precise sketch
  geometry, containment, labels and stamps support snapping and quick-add. A
  locally inferred presentation is tentative, not a checked native binding.
- Tier 1: select a pinned catalog presentation and stream a small typed spec.
  Target 1–2 seconds to the first validated useful region; report from gesture
  completion AND request dispatch separately, including the 700 ms idle window.
  Record cold/warm, model, queue, validation and injected-delay times separately.
  This is a measured target, not a guaranteed model response time. A slow or
  failed request leaves the Tier 0 surface usable.
- Tier 2: compose existing presenters, layouts and exact bindings for a novel
  surface. Reuse partial presentations, not only entire screens. Do not generate
  renderer code when composition suffices.
- Tier 3: author a new presentation using the prepared web libraries and custom
  code in bounded background work, including on first use. Check its typed contract,
  correspondence, input actions, resource bounds and accessibility before activation.
  Retain a pinned implementation through NS so the next use can follow Tier 1.
  Preserve the previous working surface on failure; incomplete or unchecked generated
  code is not activated.

The catalog is discoverable native presentation definitions, not a parallel host
application registry. Specs name pinned definitions, stable region IDs, typed
parameters, exact bindings and unresolved commitments. Extend existing Goo/Grove
structures and codecs instead of introducing a browser semantic path language.
Host drawing capabilities may be rich: Canvas/SVG, meshes/raster, clipping,
transforms, camera controls, pointer capture and DOM text/IME. Use the execution
backend best suited to each operation: retain fast existing NS/Foil computation;
use JavaScript, workers or GPU facilities for expensive or frame-sensitive work.
NS retains authoritative records, identities, contracts, bindings, ownership,
transactions and history. Transport JSON encodes scoped inputs and results.

Integrate existing libraries depth first: shape editor, 3D viewport, chart family,
table, picker, document/snapshot and image surface. Include selection, editing, holes, proposals,
exact picking and failure states in each. Layout/text/action/total primitives
support these; do not build dozens of shallow widgets first. Bars and donuts are
presentations of the same binding; extrusion is a reusable typed geometry adapter
whose implementation may run in JavaScript or a worker. A 3D face, chart mark and wall handle resolve to the
same underlying identity and their exact typed selections/derived bases.

Preserve the first two gates: local interaction, then NEW Foil publication.
After those, prove the renovation sequence: four sketched regions and contracts;
dimensioned drawing with a proposed native shape; reuse extrusion and shared
2D/3D selection; ingest prices with local units/meaning ambiguity; author a small
missing cost behavior; construct a downstream snapshot with explicit provenance;
edit geometry while the saved snapshot stays frozen; swap chart presentation;
operate with AI off. Reuse these primitives in the task and image proofs. The
node-canvas reference extends the visual vocabulary, not the immediate scope.

### Execution placement (user revision, 2026-10-04)

Every-frame interaction must work during a two-second owner-response delay.
Local execution of the same pinned native computation is NOT a prerequisite.
Keep fast NS/Foil operations as they are; use JavaScript for expensive or latency-
sensitive geometry, extrusion, image processing and linked previews when that is
more practical. Use workers/GPU for heavy work rather than blocking input. Choose
placement from actual cost and responsiveness, not a blanket native-only rule.

Expose external computation through reusable typed operations discoverable from
NS, with versioned implementation identity, scoped native inputs, declared outputs
and exact picking/correspondence. NS owns durable state and write authority; a JS
backend does not require a parallel application database or dependency engine.
Do not duplicate algorithms merely to retain a native implementation: an admitted
JS operation can supply derived results and be reused with AI off. Record the
implementation and input revisions used for any persisted derived result.

During manipulation, update geometry and linked views locally, then reconcile
with asynchronous guarded owner admission. Fast existing NS formulas remain in
NS; if their round trip prevents responsive linked feedback, use a scoped local
preview implementation or move the operation behind the typed JS boundary. If
preview and committed implementations differ, verify their agreement on relevant
inputs and expose discrepancies rather than silently persisting a different value.
Pending previews must not be presented as acknowledged state. Discard stale worker
results; coalesce obsolete preview work, never durable user operations. Preserve
drafts on conflicts. Distinguish preview, committed and snapshot revisions; saved
quotes stay frozen. Measure local feedback and acknowledgement separately.

Record actual proof clips against v2 stills, plus the existing failure cases.
Measure region readiness separately from full semantic completion. Test reuse of
a promoted presentation with AI off and different compatible inputs. Keep focus,
IME, local drafts, target identity and selection across all tier transitions.

Research rationale: A2UI describes catalog-based, incrementally updated specs
(https://github.com/a2ui-project/a2ui); json-render similarly separates catalog
schemas from generated specs (https://github.com/vercel-labs/json-render).
Borrow that generation strategy, not their host data/authority architecture.
The note's universal convergence claim, 30–40-entry count, and speed estimates
are not evidence or requirements. No generated latency figures count as proof.

The model turns a sketch into editable presentation and open contracts:
inputs, outputs, intended local behavior, and unresolved connections. First
pass does not search the world or invent data. Inputs/outputs connect to native
material, a result/construction, an adapter, or a new child sketch. Human input
is a valid leaf. Completion is neither selection nor invocation.

Needs offer native material, result/construction, adapter, then draw here.
Drop progress is factual: resolve, native check, reuse, minimum adaptation,
local semantic choice if necessary. Skip unneeded work without fake delays.
Explicit previewed drops and child outputs connect after native checks;
incidental matches remain suggestions. New structures/effects show the actual
diff, preview, destination, owner and scope with one Accept. Search coverage
accompanies duplicate claims. No source mutation is distinct from no NS writes.

Upstream and downstream construction push an addressable context trail; return
preserves children, bindings, drafts and view position. Several parents may
share a producer. Cycles need native state/event semantics, not a browser engine.
Components on layout embed; components on needs supply outputs. Preview the
uniquely appropriate output; ask locally for ambiguous outputs.

## Boundaries

Persistent tabs, readable material/construction sidebar, ordinary scrolling,
lightweight sketch tools, and hideable factual activity. Raw NS is inspectable.
Use existing records, Grove contracts, Goo/Weft, Foil/Enki, crews, transactions
and history. No parallel app registry or universal wrapper. Typed JS computation
is permitted under the execution-placement policy above. Every
meaningful region resolves to exact native focus/action, including repetition.

700 ms idle starts region-local refinement; gestures/IME defer it. Validated
complete patches stream as available. Never replace focused controls or accept
old generations. Keep local drafts across reload; reconcile commits separately.
Presentation swaps retain source/output/selection. Source swaps retain compatible
presentation. Native retained commitments are separate from tentative needs.

Actions capture native target, opaque slot, typed selection, pinned implementation,
relevant preconditions and event identity. Owner validates authority/dependencies
and applies atomic scoped changes. Creation needs owned construction capability.
Conditional bounded visible-region refresh transports native changes only.

OpenRouter Astra handles presentation/novel adaptation. Jev ranks bounded
candidates independently in a separate queue with a 2 s soft deadline and
revision-aware cache. Model judgment is not native type compatibility. Each
authoring job has exact inputs, destinations, effects and checks. Reuse first;
compile/evaluate small missing behavior in isolation; owner alone admits.
Cancellation prevents late admission; failure preserves the last good definition.

## Build and proof order

First prepare the shared web environment and pass the local interaction gate
with real +2 s response delay. Immediately spike genuinely new Foil compilation,
publication, invocation and failure preservation; retain this existing native path
proof without requiring all new behavior to be Foil. Then complete renovation.

### Primary proof: renovation (product section 11)

Reference times identify scenes, not deadlines for performing the whole workflow.
All rows require real user input, NS identities and measured results. At this
alignment checkpoint they are unverified; reference videos do not mark them passed.

| Reference | Real behavior required | Evidence of completion |
|---|---|---|
| 0:06 / stills 01–02 | Sketch plan, 3D, chart and total; useful regions appear in place with contracts. | Prepared starter used on first generation; first-feedback and first-useful-region timing; focus preserved. |
| 0:23 / stills 03–04 | Draw dimensioned rooms; propose Room structure once; draw more rooms. | Live dimensions, precise units, real proposal/destination/scope and distinct persistent room identities. |
| 0:35 / stills 05–06 | Resolve Scene through reusable extrusion; orbit and select. | Zero model calls for established adapter; same room selected in plan, 3D and linked chart when bound. |
| 0:46 / stills 07–10 | Ingest prices, resolve floor/wall ambiguity locally, choose room materials. | Original file retained, decoded data addressable, actual drop stages, unresolved floors stay visible. |
| 1:08 / stills 11–12 | Note paint behavior; search reuse, author missing computation, check and activate. | Real generated definition, declared inputs/effects, checked results, stacked chart and affected scene update. |
| 1:18 / stills 13–14 | Follow Total output into a sketched Quote document; propose storage; invoke creation. | Trail survives return; constructor creates nothing until invoked; snapshot carries real input revisions and receipt. |
| 1:40 / still 15 | Drag walls with linked plan, 3D, cost and total feedback. | Actual frame distributions under delayed responses; frozen quote unchanged; pending/committed state distinct. |
| 1:45–1:50 / stills 16–17 | Swap bars to donut; disable AI, edit material and make a new quote. | Same bindings and selection; new persistent snapshot; zero additional model calls. |

### Reuse proof: Task and image (01-canvas-reset)

Cover sketch → Assignee need → child picker → People ingest → explicit selection
and return → downstream Task list → collection/insertion proposal → genuinely new
status behavior → create and inspect → edit across re-sort → presentation swap →
reuse picker on another input → reload with draft and trail → AI off. Repeat with
exact image selection, transformation preview/commit and reuse on a different image.
Use the library-backed construction path; do not hard-code separate demo apps.

### Visual range: photo pipeline (03-node-canvas)

Retain curves, heightfield/3D relief, linked brushing, a newly authored glow kernel,
timeline/keyframes and source replacement as the next connected extension. This is
part of the intended product range, not a prerequisite to the first renovation proof
or a reason to constrain first-generation custom graphics.

### Acceptance interpretations

A finished picker supplies its chosen output only after explicit selection. Return
navigation preserves the child even when its need remains unresolved. Proposals
cover new inferred structure/effects once; direct user edits and already-previewed
drops do not gain extra approval dialogs. Provide one-action undo of refinement and
accepted changes through identity-preserving history; conflicts stay local instead
of erasing later unrelated work. "Green/native" means checked and established in NS,
including admitted JS-backed operations; it does not assert a Foil-only backend.
Numbers such as Quote#41 and sample prices are illustrative, never fixed identities.

Capture bounded real-browser clips and raw timings per gate/step. Pair each
with reference stills in a local evidence index; unpassed steps stay unpassed.
Also capture same-target conflict, stale generation during IME, event retry,
cancellation, failed publication keeping working code, undo refinement, source
swap and ambiguous multi-output selection. Do not fake-clock reenact. Video
does not prove latency. Existing new-Foil publication failure remains a blocker.

## Feel and measured acceptance

Local pointer/drawing/typing/selection/hover/drag p95 <=16 ms under delayed
responses. Warm native acknowledgement p95 <150 ms measured separately; report
actual delayed end-to-end acknowledgement too. Record count, p50/p95/p99/max,
clock definitions, delay placement, environment and dropped frames. Cached fit
is instant; uncached fit is unknown. Later ranking never shifts items.

Blue pencil=sketch; amber dashed=need; violet=proposal; green=native checked;
ink=user action. Labels/shapes duplicate color meaning. Fades 200–300 ms quadratic
ease-in-out; reorder <=450 ms; confirmation ring about 1 s. Respect reduced motion.
Region shimmer stops on cancel/failure. No simulated stream cadence or minimum
shimmer time. Activity reports local/native/check/model/Jev/elsewhere, real p95s,
and actual model calls. Popovers stay anchored and inside the visible viewport.

Correct reference inconsistencies: connected outputs become established; creates
are writes; AI off forbids model calls (explicitly re-enable for inference);
grouping preserves or explicitly adapts the contract. Reference section 3 copy,
numbers and example choices are non-binding; section 4 failures are mandatory.

## Rollout

Preserve archive and historical worlds. Build a fresh compatible world on a
separate entry. Remove obsolete whole-app/flow/prototype paths after replacements
pass. Keep proven native primitives and normal-browser authentication. Switch
normal entry only after both connected proofs, retaining recovery.
