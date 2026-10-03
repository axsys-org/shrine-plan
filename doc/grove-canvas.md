# Grove Canvas: a composable native computing environment

Revised October 2, 2026. This is the current implementation plan. It supersedes
previous product directions in this checkout; it does not claim they or this plan
are implemented. Actual results belong in [the status record](grove-canvas-status.md).
Continue on `codex/grove-canvas`, preserving its dirty work and pinned worlds.

Read the [manifesto](grove-manifesto.md) for the premise and the
[native world specification](grove-native-world-spec.md) for normative semantics.
This document is the source-level implementation roadmap. The specification governs
identity, projections, edits, closure and execution; this roadmap selects the proofs
and work needed to establish them.

## 1. The product

The architectural premise is that application boundaries are optional constructions.
Re-derive the user-facing computational model from stable identity, state, structure,
computation, behavior, dependencies, constraints, presentation and history. File, application,
window, document, database, workflow, plugin and dashboard are useful arrangements
that people may build, not fundamental categories imposed on every native subject.

The model makes this practical by authoring the intermediate abstractions between
primitive native material and useful software. Its remit includes new code, types,
constructors and presentations, rather than only selecting predefined components.
Those artifacts become persistent software available for subsequent construction.
Native execution and assessment supply continuity after the inference is finished.

Give someone a persistent canvas in which they can create, combine, use and change
software. A region becomes the working spreadsheet, simulation, editor or instrument.
That live result is immediately an ordinary composable subject at the next level.
Its behavior, state, presentation and open connections can also become a reusable
native template; capture is not required before another behavior can use the result.

The browser provides the display and input machinery. Shrine is the computational
world; Foil executes behavior; Grove/Rex author its definitions; Goo presents it.
The model authors unfamiliar behavior and presentations against that world. Once
established, software runs through native execution without a model on every action.

The ambition is to rebuild the application layer above the host OS. Replacing its
kernel, graphics drivers or networking stack is not a prerequisite. The first proof
is deliberately closed: application behavior must work without a SaaS API, an external
application, or JavaScript domain logic doing the interesting computation. An external
model may help author it. This is a release boundary, not a permanent ban on drivers.

```text
name / arrange / compose / manipulate / describe
                         │
        known native action or reusable template
                         │
          unfamiliar intent → model authors source
                         │
             compile → assess → guarded install
                         │
           native state + behavior + dependencies
                         │
                Goo presentation of a region
                         │
            use it as working software
                         │
         compose the live result again
                         │
       optionally capture a reusable constructor/template
```

### Closure is the architectural acceptance law

Every successfully established composition remains native material. Its result can
be referenced by another subject, supplied at a compatible computation boundary,
presented inside another region, inspected, or acted on by another behavior through
the same native mechanisms. There is no required export-to-app, host-plugin build,
manual library registration or template-promotion step before that participation.

This is typed, conditional closure: accepted constructions produce native results;
it does not mean every pair of objects has a valid or unambiguous composition. A
constructor, live instance, value and presentation retain their distinct contracts.
Their common property is continued participation in the same world, not universal
interchangeability or permission to invoke any executable value.

Construction, use, inspection and modification are local interactions with these
same subjects. Candidate state still has a distinct basis and admission boundary,
but it must not require a separate preview application and export workflow. When
the user finishes constructing an editor, that editor is already the usable tool.

Every established definition extends the environment's available vocabulary through
the generic native publication/discovery path. The Foundry offers relevant material
without requiring a new host widget or an application-specific integration. A
particular successful instance becomes referenceable immediately; generalizing it
into a constructor requires explicit boundaries, state policy and checks. Success
in one situation does not establish universal reuse.

Templates carry executable arrangements, not just appearances. They are not the
previous package-transfer or marketplace product. No equivalence between unrelated
namespaces is assumed. Exact references, explicit boundary contracts and checked
adaptations remain the basis for reuse.

### The material includes the machinery

The latest refinement goes beyond composing complete applications. The user can
define the kinds of objects the computer understands, the machinery that creates
and operates on them, and machinery that operates on that machinery. Every useful
result can re-enter this process. The implementation gates below select manageable
proofs of this property; they do not define a fixed catalogue of allowed software.

Data, constructors, transformations, editors, viewers, compilers and workspaces
participate through ordinary native definitions, references and checked operations.
They are roles that native objects can acquire, not mutually exclusive core kinds.
An object need not contain its own editor or know every behavior that can use it.
"Thing" is user-facing shorthand, not a new universal VM wrapper around all values.

For example, one Image subject can be read by an ImageViewer, changed by an
ImageEditor and consumed by a Thumbnailer. A MakeImage constructor creates new
instances. Each piece is separately addressable and reusable. A template can collect
them into an ImageWorkbench while keeping those separations and shared references.
Closing the viewer does not delete the image; replacing the editor does not change
its identity. Competing mutations still need the native action and case checks.

```text
                         MakeImage
                             │ creates
                             ▼
                          Image#44
                      ┌──────┼──────┐
                      ▼      ▼      ▼
                    Viewer Editor Thumbnailer
                      └──────┼──────┘
                             ▼
                 reusable ImageWorkbench
                             │
                material for another construction
```

The corresponding user journey may grow from Document to TextEditor, from Cells to
Spreadsheet, and from those pieces to ExperimentWorkbench. TextEditor + Compiler +
Project can become DevelopmentEnvironment. Eventually that environment can operate
on the native definitions of the Canvas itself. None of these application names is
a privileged runtime constructor, and this journey is not a scripted onboarding demo.

A blank canvas hides a real bootstrap: pinned compiler/runtime code, native data and
action facilities, persistence and a generic display/input host. It does not imply
that every compiler or text-input mechanism must be regenerated before the first edit.

### The execution floor already exists

The local source identifies PLAN as the execution ISA; the current Enki dependency
and patches implement its evaluator, bytecode execution paths and actor facilities.
Grove/Foil compilation already produces native artifacts for that runtime. Reuse this
path. Do not build a canvas interpreter, a new VM or an application-language runtime
in Python or JavaScript.

This is not a serial stack in which Enki sends results to a separate Shrine database.
Shrine's native world and operations are implemented by programs executing on that
runtime. Grove/Rex provide authored definitions and checked compilation; Foil provides
their behavior; Goo presents selected native state through the browser. Existing
source, publication, action and persistence boundaries remain authoritative.

The model helps invent, repair and generalize those artifacts. Disabling the model
must leave installed editors, calculations, constructors, simulations and presentations
usable. Composition has no fixed application-level ceiling; each execution still has
explicit authority, termination/resource budgets and an inspectable outcome.

## 2. What the user experiences

The runtime needs state, functions, control flow, collections, reactions, time,
constraints and operations. These do not become a palette of programming constructs.
The surface shows objects, their meaningful arrangement, editable and derived values,
controls and locally incomplete places. Deeper structure appears where inspected.

A tiny number and a complete simulation use the same interaction conventions.
A diagram is an available presentation, not the permanent shape of the environment.
Names may be enough to start. Properties and descriptions are optional; the user
never has to complete a schema before a useful interaction can happen.

| Human action | Immediate experience | Native meaning and limit |
| --- | --- | --- |
| Place | A region follows the pointer and stays where placed. | View geometry changes locally; ordinary arrangement does not rewrite the namespace or invoke a model. |
| Compose | A target previews the proposed relationship and placement. | A deliberate semantic drop invokes an existing action or stages a proposed binding. Proximity alone proves nothing. |
| Open | That region unfolds into its contents without losing its place. | A bounded presentation exposes subjects and relations; it does not copy them. |
| Separate | Pulling out a visible participant previews what disconnects. | Separate view extraction, reference removal and owned-data extraction. The native transformation determines consequences; shared data is preserved. |
| Edit | The value or object changes under the user's hand. | An authoritative edit is checked against identity, case and constraints. A derived value instead exposes its governing inputs or an authored inverse action. |
| Use | The spreadsheet calculates, the simulation steps, the editor edits. | Invoke installed native behavior. No inference for an established operation. |
| Describe | Language stays attached to the selected object, edge or result. | Scoped intent informs a source candidate; prose is not executable authority. |
| Fill | A value, object, behavior or example can satisfy a visible need. | Check the exact open boundary. An empty collection or an installed control waiting for input is not automatically incomplete software. |
| Inspect | Causality, cases, source and history peel open locally. | Exact subject, slot, occurrence, implementation and basis are retained. No DOM-text matching. |
| Reuse | The working region becomes a piece usable elsewhere. | Capture an explicit template boundary; instantiate fresh state or share a reference through distinct operations. |

The Foundry is a native, contextual view of available material: values, definitions,
constructors, actions, presentations and complete arrangements. It is not a second
application database or an app store. A newly established editor, constructor or
workbench appears there through its native exports and provenance. Suggested
groupings are presentation choices, not a hard Primitive/Software/App type hierarchy.

Placement must matter without becoming mysterious. A semantic drop has a stable
preview: inside a specific position, before an item, beside a lane, or attached to
an exposed boundary. The presentation owns that authored drop contract. A free canvas
move merely changes layout. Do not infer business behavior from every pixel moved.
Keyboard operations provide the same targets and previews.

A task shown inside both a person and a project is still one task. Moving one view
must not secretly change its ownership or remove the other view. Reference identity
is preserved independently of visual nesting and the namespace's physical paths.

### Two local depths

Normal use shows the software itself: a grid, image, timeline, document or game board.
Inspection reveals why it works: references, inputs, rules, observations, constraints,
source and history. Open this depth locally, retaining spatial context and drafts.
Use hold-to-inspect and a keyboard-accessible persistent equivalent; no bespoke
Inspect button on each component, and no inspection gesture also executes a control.

Behavior appears where its consequence lives. Selecting an area of 200 can reveal
`width × height` with actual inputs. Selecting a simulation cell can reveal its
previous state, neighbors and governing rule. A compact rule handle can itself be
reused. Source is one disclosure deeper, not the only explanation offered.

Temporary highlights show actual causal updates, then disappear. A dependency graph
is available on demand. Do not permanently cover the canvas with wires. Highlight only
recorded dependencies; unresolved or declared scopes must remain visibly distinguished
from fully traced edges.

### The interface is the medium of collaboration

The model can create an experiment, alternative layout, comparison, timeline, example,
explanation or real editor at the place of work. It is not restricted to asking form
questions or emitting a fixed catalogue of cards. User responses may be gestures,
examples, ordinary use, language or local corrections.

A new composition first preserves the user's concrete objects and arrangement. The
model works in the background on the smallest unresolved intent. Existing regions
continue to work. A late result must recheck its source basis and must not overwrite
newer user work. Repeated model refinements cannot shift a region under the pointer.

Within existing editing authority, reversible candidates that pass the required
native checks may install directly with local feedback and undo. Do not require
Shape, Build or Publish buttons for every gesture. When meaning remains ambiguous,
show a reversible alternative at the affected location. Known contradictions or an
authority expansion require a specific decision, not an automatic install.

Correcting one example is not evidence of a universal rule. Preserve the distinction
between an example, an inferred interpretation and an endorsed commitment. Successful
use alone is not blanket consent to change shared behavior or retire commitments.

### Constraints and incomplete places

A rejected move can ghost at its attempted location and return, explaining the exact
constraint locally. A draft may display an invalid total while committed state stays
valid. Elastic redistribution requires an authored redistribution policy; there is
no magical generic solver that invents which other values should change.

Missing input, unresolved behavior, waiting for an event, unavailable input and failed
checks are different native conditions. Present each appropriately. A valid empty list
gets an ordinary add affordance; a missing required owner gets a boundary to satisfy.
Never fabricate a default zero or display an inferred success as an established result.

### Visual quality and interaction stability

Use a quiet infinite canvas with clear typography, precise selection and predictable
spacing. Regions choose their useful shape and size. A name can be only a name; a grid
must have the density of a grid. There is no mandatory card shell, inspector column,
status badge pile or configuration form around everything.

Keep pointer capture, focus, selection, text drafts, scroll and viewport position
through unrelated native updates. Do not remount an entire region for one changed
value. Preserve child positions and occurrence identities through composition. Models
can propose a different presentation but cannot constantly rearrange the workspace.

A failed or obsolete interpretation must not leave empty wrappers forever. Remove
transient highlights and unused presentation scaffolding; retire unreferenced generated
work through native ownership rules. Shared subjects, endorsed templates, evidence and
history survive. UI cleanup is distinct from persistent-store garbage collection.

## 3. Verified starting point and actual gaps

The latest recorded small-grammar proof is the starting point, not the product ceiling.
It has native names and literal properties, exact associations, OpenRouter-authored
Grove/Foil, native actions and Goo output. Recorded live cases include multiplication,
an input edit without inference, exact association reuse, a description changing the
behavior, and a bare-name composition with a working action. Authoring took roughly
16–31 seconds in those few cases. The interface and latency are not accepted yet.

The existing implementation provides useful machinery:

- `grove_role_runtime.foil`: roles, action schemas, realizations, binding positions,
  contracts, explicit instance-relative references and template values.
- `grove_template.foil`: version-3 seed instantiation and explicit reference rebasing.
  It does not yet capture an arbitrary executable arrangement.
- `grove_authoring.foil`, the Grove backend and Eden: actual compilation, diagnostics,
  pinned implementation identity, bounded candidate evaluation and publication paths.
- `grove_actions.foil`, `grove_install.foil`, `interaction_runtime.foil` and
  `goo_runtime.foil`: native action/event and guarded state-change facilities.
- `commitment.foil`: retained checkers with holding, failed and unknown verdicts.
  Integrating them into all future edits is still release work.
- Goo's native parser, layout, measurement, rendering, occurrence metadata and action
  bridge. Goo actions already connect to Shrine actions; do not rebuild this bridge.

The medium proof currently imposes specific ceilings: 64 workspace subjects, 32 literal
properties per subject, bounded input lists, 64 settling rounds, own-record output
restrictions, explicit input-graph settling and `render_at 360`. Its generic action
handler shape is largely record-to-record. This is not yet a maintained arbitrary
computational world with multi-subject operations, clock-driven behavior or recursive
capture. The current Goo primitive vocabulary includes buttons, inputs, code, avatars,
media and bars; the general graphical/input surface required here is additional work.

Some collection, cardinality, subset extraction and template operations remain partial.
There is a recorded ASCII-only measurement limitation. Runtime time/actor primitives
must be inventoried before selecting an adapter; their absence cannot be inferred from
the proof's UI. Recorded tests establish their own narrow cases, not this new release.

## 4. Native model and consistency

### The equivalent of a file is not one compulsory bundle

A persistent subject supplies identity, state and relations. An authored definition
describes a reusable kind or behavior. A running binding relates particular subjects
to pinned implementations and their conditions. A presentation exposes some of that
world. Keep these distinct even when one compact region makes them feel unified.

A reusable computational definition can expose the following facets through existing
Grove declarations and Foil exports. This is a description of responsibilities, not
a proposed `thing/shape/construct/run/view` language or mandatory list of fields:

| Facet | Native realization |
| --- | --- |
| Structure | Roles, native codecs, slots, references and collection/region contracts. |
| Construction | A pinned native constructor with arguments, explicit reused inputs and guarded operations creating owned state and bindings. |
| Conditions | Input requirements, applicability, authority and hard invariants distinguished from each other. |
| Computation | Foil transformations over values and referenced native inputs. |
| Reaction | Subscriptions or explicit events connected to checked state transitions. |
| Operations | Applicable native actions with exact receivers and argument codecs. |
| Presentation | Separately authored Goo views and editors bound to native subjects/actions. |
| Continuity | Source/implementation pins, basis, history, retained cases and commitments. |

Facets may be separate native definitions reused by many arrangements. A Document
can have several editors and viewers; an editor can accept several compatible kinds
of document. An editor or constructor can itself be inspected and changed using
another native tool. A generic fallback must keep otherwise unpresented values
inspectable without requiring them to invent a viewer first.

Construction is software. A MakeGrid definition should be selectable, parameterizable
and callable through the same native action path as an editor action. Composing it
with another constructor produces a checked construction program. Its output must be
ordinary subjects/bindings suitable for further use, not an opaque host object.

Changing a constructor affects subsequent constructions at its new pin. Existing
instances preserve their state and pins unless an explicit assessed update targets
them. A constructor that generates or changes source produces a normal compilation
candidate; being inside the native world does not bypass admission. A familiar label
or suggestive arrangement can inspire a model proposal, but establishes no type or
behavior by itself.

### Identity and representation

Keep these concepts distinct, using existing native types and references wherever they
already express them:

| Concept | Required representation |
| --- | --- |
| Subject | Stable native identity and current case; may contain structured values or references. |
| Definition | Pinned roles, codecs, behavior, actions, contracts and presentation exports. |
| Instance | Definition reference, local state and explicit boundary realizations. |
| Presentation occurrence | One rendering of a subject on a selected basis; several may show the same subject. |
| Placement | Presentation position and authored drop target; not automatically a native address. |
| Boundary | Stable key, required role/cardinality, care, relevant constraints and current binding. |
| Candidate | Proposed code/operations, basis, affected consumers, retained checks and findings. |
| Commitment | Scoped endorsed example or invariant with a pinned checker and provenance. |

Do not add a parallel JavaScript or Python object graph as the authoritative world.
Native slot keys, child paths, boundary keys and DOM/graphics identities are distinct.
Resolve an event to its native subject and expected case; never mutate by row number,
label, visual coordinate alone or the last segment of a path.

Collections have declared shape and stable member identities. Cardinality is checked
against the relevant relation or collection, not every record under a cared subtree.
A first observed member does not prove a one-only contract. Adapting one-to-many or
changing a nominal value requires authored code and consumer checks.

Foil may operate on native arrays, maps, trees, matrices and other typed values without
allocating a persistent record per pixel, character or matrix element. Addressable
subvalues need a codec and identity/basis-aware access path; paths into an edited dense
value are not automatically stable identities.

### Computation, events and world changes

Use Foil's existing control and functional facilities. There is no second expression
language for formulas, reactions or constraints. Convenient formula text, if provided,
must compile through an explicit native language boundary and retain its source.

Distinguish authoritative state, maintained derived publications and disposable render
caches. Reading or expanding a view is not a domain mutation. Derived values retain the
implementation and input basis that established them; stale results are not current.

Extend the present own-record action path to support guarded operations over an explicit
owned or granted target set: create, update, unlink, retire and emit a native event.
Preparation is effect-free and returns proposed operations plus checks. The existing
owner transaction validates cases, ownership and constraints, then commits atomically.
Version the extension so old action handlers and pinned worlds keep their meaning.

Use existing crews/subscriptions and native journal changes to maintain dependencies.
Record selected reads, missing references and membership boundaries. Recalculate edges
when a reference is retargeted. Keep declared read scopes for custom code whose reads
cannot be captured. An exhausted traversal or incomplete scope cannot establish safety.
Do not grow the proof's scan-all-nodes loop into a second reactive runtime.

Instantaneous dependency cycles remain invalid unless an explicit bounded fixed-point
procedure defines their semantics. Stateful feedback is separate: event n transforms
committed state n into state n+1. A simulation, game or editor can therefore react over
time without pretending a cyclic derivation establishes itself.

A hard invariant rejects an inadmissible transition. Ordinary missing inputs can suspend
an affected derived use while leaving independent behavior active. Recovery rechecks the
same dependencies. Installed waiting-for-input behavior remains usable software.

### Time, randomness and restart

Clock readings and input events are host observations. Calendar time, scheduling and
simulation clocks are ordinary native constructions, not compulsory object kinds.
Keep the clock adapter as a reusable boundary binding over existing runtime facilities.

Separate logical simulation time, wall-clock observations and visual interpolation.
A model-authored native step function consumes explicit events and state. Step, run,
pause, rate and reset operate on that same function. Browser animation may interpolate
a committed result; it does not advance authoritative simulation state.

First inventory existing Enki/host timing and supervision. Add only the missing native
clock binding over those facilities. Use one supervised scheduler with bounded queues,
backpressure and explicit tick ordering. Persist logical event identity and seed where
randomness matters. Resume from a declared policy; a restart must not invent all missed
wall-clock ticks or replay physical effects.

A bounded batch may advance several logical steps in native execution and commit its
result with the event range and implementation basis. Retain enough inputs for the
claimed replay. Measure storage before enabling sustained runs. Do not journal a full
independent world copy per frame, or quietly move business state into JavaScript to
hide persistence cost. Edited-code evaluation and same-program replay remain distinct.

### Templates are executable boundaries

Extend Grove's existing template representation with a versioned capture descriptor:

- Owned seed/structure closure and exact definition/import pins.
- Stable open positions, cared references and declared relationships.
- State initialization policy: fresh, explicit seed, or shared reference.
- Behavior, actions, event/reaction declarations and derived-publication policy.
- Presentation exports, relevant constraints, examples and commitments.
- Provenance and explicit transformations for extraction, separation and replacement.

Capture the selected arrangement, not the entire reachable world. Outgoing shared
references become explicit boundaries or deliberately shared anchors. Never infer that
all reachable state is owned, portable or appropriate to copy. Caches and transient
selection are not captured domain state. Source evidence remains historical; a new
instance still checks its local bindings.

Capture must also work for a constructor, transformation or presentation alone. A
complete rendered application is not required. Compositions may share a definition,
invoke an existing constructor, or bind a different viewer onto unchanged data.
Reusable code and a particular invocation's mutable state must remain distinct.

Instantiating a template, duplicating current values and showing another view of the
same instance are different operations. The user should be able to tell which will
happen before releasing the gesture. A nested template participates through the same
boundary contract as a leaf; do not flatten it into copied constituents.

Definition-wide changes require explicit scope and re-evaluation of affected instances.
An occurrence-specific edit must not silently change every sibling. Removing a member
from a composition follows ownership and dependency checks. Undo restores an assessed
native relationship/state transition, not an old whole-world snapshot over later work.

## 5. Presentation and agent implementation

### Goo is the native presentation path

Extend the existing Goo frontend, not a competing component registry. Definitions may
produce native Goo for dense grids, editable text, scenes, paths, plots, timelines and
nested interactive regions. Generic drawing/input mechanics are boot facilities;
application semantics remain authored Foil/Grove.

Add a native graphical surface description with text, paths, shapes, raster tiles,
transforms, clipping, child regions, semantic hit targets and accessibility information.
Its purpose is rendering, not a new application evaluator. Browser code executes these
bounded rendering instructions and reports input. It cannot contain an automaton step,
a booking rule, a formula evaluator or an application-specific subject matcher.

Each hit target carries an occurrence, selected basis, native action reference and
argument codec. A grid presentation may translate a pointer location into a proposed
cell operation; native code checks the target against the current grid before mutation.
Coalesce a paint stroke into a bounded input batch with explicit ordering and undo
scope. A local paint preview remains pending until native acknowledgement.

Maintain text selection, IME composition, focus and draft buffers in the browser.
Commit through native editing actions; preserve drafts when their basis becomes stale.
Support accessible DOM equivalents for graphical controls. Ordinary text must be
measured correctly beyond ASCII; unsupported output must be diagnosed, not erased.

The model can author new presentations from intent or a rough sketch. It receives the
actual available native subjects/actions and renderer facilities, and can compose the
low-level vocabulary freely. It is not restricted to choosing a business widget.
A useful presentation can be retained with its native template. Mash may contribute
interaction design or host mechanics after an explicit review, but is not a second
semantic authority or a prerequisite for this release. Shears is not an additional
mandatory shell on top of the existing Goo frontend.

### Fast known operations; bounded novel authoring

Known edits, actions, exact boundary reuse and template instances run without inference.
Ordinary movement performs no authoring request. A new interpretation gets one capable
source-author request with a bounded native context: selection, definitions, bindings,
source, relevant state, commitments, available exports and precise unresolved work.
Do not send the whole workspace's rendered HTML as semantic context.

Retain OpenRouter in the existing host. Credentials stay in host configuration.
The compiler/runtime is authoritative; Jev or another routing/inference model is
optional only where measurements demonstrate value. Do not restore a mandatory
selector → inference → author → inference pipeline for every small composition.

Record model, timing, proposed source, diagnostics and actual execution receipts.
A native compilation failure may trigger a bounded repair using the real diagnostic.
An unsupported facility must remain explicit rather than turn into a fake HTML demo.
Cancel superseded work; key acceptance to the selected basis and intent revision.

When checks pass, installation preserves retained examples and commitments. Retiring
a commitment is a distinct assessed change. Inspectable claims must refer to actual
results or be marked interpretation. Agent-generated counterexamples supplement real
retained interactions and declared boundary cases; they are not stronger evidence.

Keep canvas and external-agent access on the same native action path. Existing
status/read/write/compile/eval/observe/source/context/events remain the small transport
surface. Contextual tool projection and MCP must not add independent behavior. Full
external-client parity waits until the canvas loop works; read and continuation access
can reuse the current transport in the meantime.

## 6. Concrete source changes

Paths below are relative to this checkout. **Extend** means the file already exists.
**Add** means planned source, not something currently available. Additions are staged
behind the experience gates; this table is not permission to build a framework first.

The implementation kernel is the existing native system plus a thin composition,
authoring and presentation loop. The numbered software exercises are agent-authored
native constructions, not host subsystems to hand-build. Start with the existing
action/view/binding contracts, then extend only a demonstrated missing facility.
The candidate new helper files below are extraction destinations, not mandatory
frameworks that must all exist before the first interaction works.

The central operation is applying existing native machinery to a selected subject.
Native checks establish known connections; remaining needs can require a choice,
input, projection, structural change or new code. The model works on that exact
remainder, and its established result returns to the native vocabulary. Do not
restore the earlier universal package matcher or a separate hole-solving runtime.

| Files | Work |
| --- | --- |
| **Extend** `extras/mounts/medium/medium.foil`, `tests.foil` | Preserve names, identities, associations and native operations. Replace fixed rendering assumptions; integrate retained commitments and general composition boundaries. Move dependency maintenance onto existing native machinery. Keep limits explicit while generalizing. |
| **Extend** `src/foil/grove_role_runtime.foil`, `grove_template.foil`, `grove_install.foil` | Versioned template capture/instance policy, explicit external positions, nested compositions and guarded multi-target operations. Preserve old seed templates and action compatibility. |
| **Extend** `src/foil/grove_actions.foil`, `interaction_runtime.foil`, `goo_runtime.foil` | Typed input envelopes, bounded event batches, preparation and target/case checks, atomic action application, suspension and current-result metadata. Reuse the existing Goo-to-Shrine action connection. |
| **Extend** `src/foil/grove_authoring.foil`, `grove_bundle.foil`, `grove_view_publication.foil` | Exact source/import closure, candidate assessment, native presentation exports and dependency/basis reporting. |
| **Extend** `src/foil/grove_views.foil`, `grove_app.foil` | Preserve independently selectable native views over the same subjects; expose exact published view/action references to composition and inspection. Keep view capture separate from owning or copying its input. |
| **Add if repeated use requires extraction** `src/foil/grove_projection.foil`, `src/foil/tests/grove_projection.foil` | Start with existing view/action contracts. Extract shared native projection helpers only when needed by independent constructions: exact subjects/positions, pinned readers, optional writers, basis, ownership and dependency coverage. No path-expression interpreter or copied application model. |
| **Extend** `src/foil/grove_ui_runtime.foil`, `presentation_edit.foil` | Preserve native reference/value codecs and exact action identities when re-presenting subjects; keep appearance-only changes distinct from explicit behavior changes. |
| **Extend** `src/reaver/foil-grove-backend.rvr`, `eden.rvr` only for missing native exports | Compiler metadata and publication integration where the above contracts require them. No parallel evaluator or gratuitous language syntax. |
| **Add if capture outgrows the existing module** `src/foil/grove_template_capture.foil` | Pure bounded capture assessment over selected owned records/definitions; export explicit boundaries and initialization policies into the existing template format. Reuse `grove_template.foil` first. |
| **Extend** `src/foil/commitment.foil`, `tests/commitment.foil` | Wire scoped examples/invariants into all relevant source changes; retain prior checkers, coverage and explicit retirement findings. |
| **Extend** `extras/mounts/goo/types.foil`, `read.foil`, `passes.foil`, `measurement.foil`, `layout.foil`, `display.foil`, `html.foil`, `html_api.foil` | Graphical/nested region vocabulary, viewport sizing, input/accessibility metadata and correct text measurement. Preserve existing native layout and omission rules. |
| **Extend** `extras/mounts/goo/inspection.foil`, `application_json.foil`, `grove_bridge.foil` | Exact occurrence/subject/basis references, graphical hit targets and local causal inspection. Remove the assumption that every result is a 360-pixel card. |
| **Add** `extras/mounts/goo/graphics.foil`, `graphics_tests.foil` | Native drawing data and lowering/validation helpers; reuse Goo's render path. This file contains no domain algorithms. |
| **Extend** `extras/mounts/medium/proof/app.js`, `style.css`, `index.html` | Evolve the current entry point into a region host. Preserve drafts/geometry; remove mandatory card chrome and demo-specific workflows after replacements pass. |
| **Add** `extras/mounts/medium/proof/surface-host.js`, `native-input.js` | Generic incremental display/input mechanics, pointer capture, keyboard/IME, hit-target transport, pending previews and accessibility. Split from the current entry point only as the working path needs it. |
| **Extend** `extras/mounts/medium/model.py`, `proof/authoring.txt`, `test_model.py` | Selected native-context authoring, broad Foil/Goo freedom, cancellation and basis checks, diagnostic repair and measured routing. |
| **Extend** `extras/mounts/medium/host.py`, `webhost.py`, `test_proof.py` | Versioned transport, cancellation, ordinary-browser local authentication and bounded native frame/input delivery. No business logic. |
| **Add** `extras/mounts/medium/clock.foil` | Native logical clock/step/run/pause binding over existing timing/actor primitives. Add a host scheduler adapter in the existing host only if the inventory shows it is missing. |
| **Add** `extras/mounts/medium/workspace.grove` | Native workspace declarations, the Foundry as a view of actual exports, available composition/inspection actions and template references. Gradually replace host-specific workspace policy, without persisting every pointer movement. |
| **Add** `extras/mounts/medium/fixtures/calculator.grove`, `document.grove`, `spreadsheet.grove`, `shared_subjects.grove`, `drawing.grove`, `compiler.grove`, `workbench.grove`, `grid.grove`, `automaton.grove`, `instrument.grove` | Ordinary native examples, constructors and regression inputs. Shared-subject fixtures test Person/Org projections, authoritative membership, explicit rename versus reassignment and downstream computation. There are no hidden domain handlers in the renderer. |
| **Extend** `extras/mounts/medium/mount.json`, `medium_mount.foil`, `extras/mounts/goo/mount.json` | Register added native modules, Grove declarations, tests and browser assets through the existing mount/build machinery. |
| **Extend** `src/foil/tests/grove_template.foil`, `tests/grove_install.foil`, `tests/goo_runtime.foil` | Capture ownership, nested instance identity, multi-target atomicity, stale/duplicate events and compatibility cases. |
| **Extend** Goo's existing `type_tests.foil`, `layout_tests.foil`, `html_tests.foil`, `semantic_tests.foil` | New region primitives, native target retention, accessibility/measurement and visible unsupported-rendering errors. |
| **Add** `x/check_closed_canvas.py` | Serial native acceptance runner: no browser simulation or substitute evaluator; retain inputs, source, results, timings and resource measurements. Browser checks use the actual running client separately. |
| **Extend** `x/eden_runtime.py`, `x/eden_mounts.py`, existing Enki patches only for demonstrated failures | Bounded worker/storage and actual runtime lifetime defects. Do not make a new Enki rewrite a precondition for the first useful interaction. |

Application fixtures in this table are retained native examples and regression cases;
they must not supply secret host behavior that lets a live authoring demo appear to
succeed. Record the generated native source and its actual results separately.

Use existing Rex and Grove declarations for roles, views, actions, templates and
compositions. New native structs require export registration and versioned codecs;
new Goo constructors require validation, lowering and host support. Creating a Foil
file alone is not integration. Every stage must exercise the compiled mount and
native action path, not just inspect generated source.

## 7. Build order and acceptance gates

This progression follows the [native world specification](grove-native-world-spec.md).
Each stage must retain reusable machinery and immediately composable live results.
The examples test semantics, not feature parity with entire commercial applications.
They are not hard-coded product modes or a scripted sequence forced on the user.

### Stage 0 — establish a bounded baseline

Record exact dirty source, engine/compiler identities, current world and evidence.
Keep the user's objects and compatible engine. Limit the initial runtime investigation
to one working day: establish whether the small native loop can run for an hour within
current guards. Fix a measured blocker before expanding scope; do not silently relax
guards or start a general runtime rewrite. Use serial disposable stores.

Inventory native view/action contracts, subscription behavior, text measurement,
primitive timing/input facilities and template limits. Record current versus missing
capabilities. The status document must distinguish old evidence from fresh execution.

### Stage 1 — calculator and the smallest enjoyable interaction

Preserve NAME, optional PROPERTY, NAME + NAME and optional DESCRIPTION. Names begin
as native subjects without mandatory schema. Build a real small calculator composition
through actual model-authored Foil/Grove, with typed input and result inspection.
Known edits, operations and exact reuse execute without a model.

Make movement local and immediate. A novel composition preserves its concrete inputs
and geometry while the model works. Reject failed or stale candidates without losing
the prior behavior or the draft. No forced card shell or setup wizard.

Acceptance: create an unfamiliar calculation, operate it, change an input, inspect
its rule, change intent and undo. Use its live result as input to another calculation
before any template capture. Move its view without network requests. Review the real
interaction with the user; a slow or awkward demonstration does not pass merely
because the native result is correct.

### Stage 2 — native text and editing machinery

Create a Document with editable native text and a separate read-only presentation of
the same subject. Native actions insert, remove and replace sequence content. Generic
browser mechanics retain cursor/selection, IME and drafts. Make undo a guarded native
operation and preserve unrelated updates.

Show one document in two organizational collections by reference. Editing it from one
surface changes the other; changing view placement does not duplicate or relocate it.
Inspect the editor actions and retain that editing arrangement for reuse. Editing must
continue with the model disabled. This is a plain-text editor, not a full word processor.

### Stage 3 — spreadsheet over the actual native world

Create a grid with native local inputs and formula evaluation, then project existing
Person/Organization/Task subjects into it. A row retains its subject and stable column
bindings. The sheet adds projection/occurrence metadata without importing another copy
of those domain subjects. Run every shared-spreadsheet case in the specification.

Demonstrate both directions: rename a Person in a separate editor and see the sheet
update; edit its field from the sheet and see the same editor update. Reassign an Org
reference through an identity-aware picker. The inverse membership updates while the
organization's own name remains unchanged. Exercise its explicit rename separately.

Add relational calculations, including membership-dependent counts. Delete or retarget
an input and expose unavailability/unknown coverage rather than a fabricated result.
Sort, page, move columns and switch presentation with a pending edit; the subject and
expected basis determine what can commit.

Feed a native derived Cost into ProjectBudget and OrganizationForecast. Inspect the
actual dependency chain. Use the live sheet inside an ExperimentWorkbench before
capture. Retain an endorsed calculation and show a later regression being caught.

Request a column requiring genuinely new computation, such as CompletionEstimate.
Show the unresolved input/behavior boundary, let the model author the native missing
piece, then use that same piece from a second presentation. The runtime must retain
the computation as ordinary reusable software, not spreadsheet-specific host glue.

Now generalize the editor/evaluator arrangement into a template with explicit boundaries.
Instantiate fresh local state against another compatible collection while preserving
shared source identities. Ambiguity or an incompatible role remains explicit. This is
both the first main product proof and a test of machinery added to the native vocabulary.

### Stage 4 — drawing and spatial construction

Add generic Goo graphics/input support for shapes, text, transforms, clipping and
nested regions. Author native geometry and guarded manipulation over it. Pointer
feedback is local; committed geometry and constraints are native.

Compose, resize, group, separate and re-present shapes while preserving stable subject
identity. Distinguish moving a view from changing native geometry or a relation. Illegal
moves show their exact constraint. An authored adjustment policy may move other values;
the host must not invent one.

Retain Scene, selection operations and presentation machinery as ordinary definitions.
Use a native grid/evaluator from the spreadsheet in this drawing surface without
copying its semantics into JavaScript. Wireframes can guide presentation authoring;
the resulting controls must bind to real native actions.

### Stage 5 — native compiler as a reusable subject

Specify a small expression language and author its parser, AST transformation, checks
and lowering in Foil. Execute actual compiled results under the existing bounded
runtime. Show real source diagnostics and inspect intermediate native structures.

Each stage and the whole Compiler are addressable native definitions. Present the
Compiler reference in a grid cell, open it, then invoke it through its declared native
action. A code reference is not ambient permission to execute it. Retain the parser,
transformation and diagnostics as reusable machinery.

This is a small language implementation and a higher-order computation test. Reuse
the existing Foil/Grove compiler for Shrine source; do not rewrite it for this exercise.

### Stage 6 — simulation and observation driven software

Reuse the grid and graphical presentation to create a paintable 32-by-32 simulation.
A real model authors the native neighbor rule. Step executes it on committed state.
Run/pause consume bounded observations through an ordinary native clock binding;
Time is not a new compulsory core kind. Inspect previous state, neighbors and result.

Expose the constructor that creates a grid, binds its editor and installs a chosen
rule. Invoke it twice with independent seeds. Change its default and show that only
future constructions change. Bind another view and a statistics behavior to one
existing grid without duplicating it.

Compose a native Population History and chart with the simulation, yielding an
Instrument. Reuse it inside a Comparison. Separate and reconnect the chart, exposing
exact affected boundaries while the independent simulation continues. Test instance
edits and explicitly shared rule changes, retained cases and restart policy.

Disable model access and keep editing, stepping, instantiating and inspecting. Record
actual logical-step latency, queue bounds, memory and storage over sustained execution.

### Stage 7 — development environment and native canvas editing

Compose the established editor, callable compiler, project/source references and
native diagnostics into a DevelopmentEnvironment. Also expose the existing native
Foil/Grove compiler through its normal checked publication path. These are ordinary
components, not a host IDE mode.

Represent a limited part of the workspace natively: selected subjects, Foundry,
available actions and inspection presentations. Use the composed environment to edit
and install one of those actual definitions. Keep pointer/focus/camera mechanics in
the generic host where appropriate.

A deliberate compile error must preserve the working canvas. Retain a pinned bootstrap
recovery surface. Record exactly which part edits itself. The proof does not claim to
have recreated Enki, the browser or a complete production IDE from scratch.

### Stage 8 — operational and experience acceptance

Run the complete native, browser, model-unavailable and resource acceptance. Preserve
real prompts, generated source, diagnostics and execution results separately from
prewritten regression fixtures. A replayed animation or a success record created by
the harness is not evidence of the native behavior.

Observe five developers using the actual build. At least four must complete creation,
local inspection, correction and reuse without an operator explaining the runtime
schema. Include one non-developer session as an early signal. Record confusing moments
and failed tasks as evidence. Broader release waits for the experience and resource
gates, not the number of sample applications on the canvas.

## 8. Release requirements

These are targets to measure, not claims about the current proof.

| Area | Gate |
| --- | --- |
| Local mechanics | Pointer feedback on the next frame; target 60 Hz during drag/pan on the test machine. No model/native request for ordinary placement. |
| Established operations | Warm small native input-to-visible-result p95 at most 250 ms across 100 measured actions. Immediate pending feedback where needed. |
| Simulation | 32-by-32 native simulation sustains 10 logical steps/second for an hour, within existing resource guards, with responsive painting and pause. Record missed deadlines and queue bounds. |
| Novel authoring | Across 20 declared small tasks, target median useful checked result within 5 seconds and p95 within 12 seconds, including repairs. Report actual success and latency, cancellations and failures; current 16–31-second cases do not pass. Do not trade native checks for a benchmark win. |
| Presentation quality | Regions preserve focus, drafts and placement; no mandatory card shell; dense surfaces stay dense; keyboard/IME and accessible alternatives work. Participant findings determine whether the interaction feels coherent. |
| Recursive reuse | Two levels of template composition preserve ownership, independent state, explicit sharing, retained checks and exact boundaries. |
| Shared native projections | The specification's spreadsheet cases pass: one authoritative subject, edits from both presentations, explicit reference retargeting, inverse membership, dependency updates and stable targets after sorting. |
| Closure and vocabulary growth | A freshly established live composition is accepted at a compatible higher-order boundary before template capture. A new constructor, behavior or presentation becomes discoverable and usable through generic native mechanisms without application-specific host changes. Trace both uses to the exact same native subject where sharing is intended. |
| Machinery as material | A constructor, editor and viewer are independently inspectable/reusable native definitions. An authored higher-order constructor creates working instances without host application code. Multiple tools operate on the same native subject without duplication. |
| Runtime independence | Disable model access after establishment. Construction from existing templates, editing, computation, simulation, inspection and rendering still work. Model unavailability affects novel authoring, not installed execution. |
| Honesty | Partial coverage, waiting, unknown, stale, unsupported and failed states remain distinguishable. Historical evidence does not automatically establish a new implementation. |

Native regressions must cover stale/duplicate inputs, reordered collections, absent
references, membership changes, multi-target failure atomicity, cycles, tick ordering,
pause/restart, template closure limits, shared-data separation and commitment removal.
Browser checks must use real actions after sorting/zooming and retain drafts across
unrelated updates. Candidate source cannot escape native authority through raw effects.

Closure is an acceptance condition throughout implementation, not a feature postponed
until Stage 3. A stage fails if its successful output is an opaque application island
that the existing native composition/inspection machinery cannot address. Stage 3
adds a deeper live exercise and template generalization of the same condition.

Keep the inherited resource acceptance: 10,000 unchanged read/frame requests after
warm-up cause no canonical-store or pin growth; charged-memory growth over the final
half remains within 16 MiB and the aggregate guard. Run 50 serial compile/evaluate/
discard cycles; successful disposable stores must not accumulate. Also measure durable
bytes per logical event during the hour-long simulation. Set and document a sustainable
retention policy based on native reachability before enabling unlimited runs.

Use local storage outside iCloud, one development world and serial test workers.
Retain at most two unresolved failure stores; discard diagnosed disposable copies
while preserving small logs, source and receipts. Archive source once by hash. Never
truncate live pins, repeatedly copy whole worlds or call host deletion compaction.
No speculative performance exception changes the stored meaning of a world.

## 9. Retire or defer

After equivalent replacement checks pass:

- Retire fixed-width card rendering as the universal surface; retain a generic fallback
  for unpresented data. Retire mandatory property/schema setup and demo-specific
  Shape/Publish flows from ordinary reversible editing.
- Remove the mandatory multi-model inference pipeline from the active path. Preserve
  useful inference experiments separately; native validity never comes from a model.
- Consolidate duplicate medium frontend paths once the replacement is actually used.
  Preserve useful native/compiler, driver, identity, history and browser regressions.
- Stop treating booking, Relay, submission upgrades and generic package correspondence
  as concurrent product goals. They may remain fixtures or archived work; do not port
  their bespoke product shells into this canvas.
- Avoid new global widget, workflow or requirements languages. Keep Grove/Foil and Goo
  expressive instead of hard-coding each new application into the host.

Defer marketplaces, arbitrary package-to-package semantic matching, full MCP parity,
remote accounts, external workflow automation, high-performance 3D and full editor/IDE
self-hosting. Preserve the native boundaries needed to add them later. The closed
canvas must first prove that it can build and reuse real software by itself.

## 10. Continuity and source preservation

This revision changes documentation only. It does not switch the active client,
rewrite a running world's journal, commit or push source, or remove previous code.
Implementation reuses the current checkout and preserves unrelated dirty work.

The previous plan is archived once at
[grove-canvas-before-closed-world-b0279c28eb3d.md](archive/grove-canvas-before-closed-world-b0279c28eb3d.md).
SHA-256: `b0279c28eb3d45c675fdb94690cdb52e8803213f7c044a371cf33543765d853e`.
Restore that source file to recover the prior plan; no runtime store is involved.
Historical status/evidence remains below the current entry in the status record.

The new completion criterion is concrete: a person builds and operates a native
computational region, changes it through local interaction, reuses the whole result
and its construction/presentation machinery in larger compositions, and still
understands and controls what happened. The productive machinery is itself material
inside the same world.

## 11. Next live proving phase (2026-10-02 user alignment)

Finish the current native correctness checkpoint, then keep an actual user world
available in the browser while extending it. Demonstrate the complete loop, not
only regression results: construct or ingest native material, find/apply machinery,
inspect exact correspondence, correct a mismatch, and reuse the resulting native
computation or presentation in a second construction. Keep progress visible at
natural checkpoints and preserve the user's working surface.

Manual construction, model authoring, file decoding, existing NS subjects and
imported native machinery converge on one typed native world. They are not modes
with separate data models. Reuse a type when it actually fits; make uncertain
interpretation visible, retain file provenance, and never silently equate identity
by similar names. CSV rows, raster bytes, recoverable PDF structure and source text
are ingress evidence; the original format does not own the resulting ontology.

Use varied material to test the same mechanisms: people through a table and an org
chart; tasks through a timeline; a matrix through image editing and simulation;
source and diagnostics through an editor/compiler; a decoded document through
reading/search. These are expressiveness tests, not feature-parity commitments or
new host subsystems. Unsupported decoding or missing structure remains explicit.

Exercise one actual correspondence repair and later correction. For example, an
authored Task-to-Interval computation remains native and reusable after a timeline
uses it; a correction updates its binding and consumers instead of regenerating
the whole surface. Model calls serve novelty, while established operations work
with the model disconnected. No speculative Foundry framework precedes this proof.

Use Canvas/SVG/raster drawing wherever arbitrary or dense geometry benefits from
it: matrices, graphs, images, timelines, games, handles and transient previews.
Use DOM/native controls where text entry, focus, IME or accessibility benefits.
Drawing is a presentation escape hatch, not an ontology or a fixed component
catalogue. Avoid representing dense graphical surfaces as thousands of DOM boxes.
Generated hit correspondence resolves against the displayed native basis to an
exact subject, slot, typed selection or derived result. Physical coordinates and
input delivery belong in the host; gesture/key interpretation and state changes
belong in native machinery bound to the current focus/context. The same matrix
rendering boundary must serve image editing and simulation without either one's
algorithms moving into the browser.

Retain the current plan's stricter warm native acknowledgement target: p95 below
150 ms, distinct from the earlier input-to-visible-result target above. The running
status document records which native, live-browser, resource and experience checks
have actually passed. A demonstrated small surface does not establish the full
spreadsheet/compiler/IDE/image/game/workspace construction sequence.
