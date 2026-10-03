# Shrine native computational world specification

This document specifies the intended semantics of the Grove Canvas environment.
It is a normative design, not a claim of completed implementation. The
[manifesto](grove-manifesto.md) explains the product premise. The
[implementation plan](grove-canvas.md) maps the work to source files and release
gates. The [status record](grove-canvas-status.md) carries actual evidence.

MUST denotes a release requirement. SHOULD denotes a default whose exceptions
require an explicit rationale. Examples and record outlines below describe native
contracts; they do not introduce a new programming language or a second evaluator.

## 1 Scope and architectural laws

The environment provides a persistent native world in which objects, executable
definitions, constructors, actions and presentations can participate in further
construction. Application categories remain userland arrangements.

| Law | Required behavior |
| --- | --- |
| Native closure | Every established construction returns native material that can participate at compatible boundaries without export or host integration. |
| Shared identity | Independent uses can retain the same subject reference. A presentation MUST NOT silently create another authoritative domain object. |
| Native execution | Established behavior executes through the Foil/Grove compilation and Enki runtime path. The model and browser are not alternative domain evaluators. |
| Local continuity | Construction, use, inspection and modification address the same native subjects, with explicit live, historical or candidate bases. |
| Growing vocabulary | Newly published definitions become available through generic native discovery and invocation. Each new kind MUST NOT require an application-specific host handler. |
| Explicit generalization | A live result participates immediately. Template capture additionally declares a reproducible construction boundary and initialization policy. |
| Maintained intent | Relevant endorsed examples and constraints are checked on subsequent changes, including changes that remove a checker. |
| Bounded authority | Common representation does not erase types, ownership, permissions, resource limits or the difference between a value and authority to execute it. |

The initial product uses one local deployment and a browser host. Distributed
agreement, automatic matching of unrelated people or namespaces, and a worldwide
shared ontology are outside this release. Names and apparent similarity do not
establish identity. The environment may contain several intentionally different
representations connected by explicit native adapters.

The implementation SHOULD add the smallest mechanism needed to exercise these
laws using existing native facilities. New reusable application code belongs in
the native world. An editor, spreadsheet or compiler is not justification for an
application-specific host subsystem. Generic abstractions should be extracted
from demonstrated repeated needs rather than built speculatively before use.

## 2 Existing substrate and responsibilities

Reuse the implementation already in this checkout:

| Layer | Responsibility |
| --- | --- |
| Shrine namespace | Native state, addressed identity, cases, care, history, subscriptions and guarded operations. |
| Foil | Typed computation, constructors, transformations, action preparation, reactions, checks and presentation functions. |
| Grove and Rex | Structured source, roles, codecs, definitions, checked linking, compilation and source diagnostics. |
| Enki | Execution of the compiled native programs, actors and bounded runtime/resource facilities. The local source targets the PLAN ISA. |
| Goo | Native presentation declarations, layout/rendering descriptions, occurrence metadata, inspection and the existing native action connection. |
| Browser host | Rendering, pointer/keyboard mechanics, focus, IME, drafts, accessibility, viewport and incremental display. |
| Host supervisor | Authentication, credentials, model transport, physical input/output and resource supervision. |
| Model | Propose new source, interpretations, adaptations and presentations against selected native context. |

Shrine is implemented by native programs executing on the runtime; it is not an
unrelated database after the VM. Definitions and compiled exports already have native
representations and publication identities. Extend those representations rather
than introducing a universal `Thing` wrapper or a parallel object store.

Existing role/action/template interfaces are narrower than this specification.
New codecs or action envelopes MUST be versioned. Pinned old worlds retain their
compatible interpretation; a new client cannot reinterpret an old journal in place.

## 3 Native identity and representation

A subject is an addressed native object. A definition, compiler, editor and data
record may all be subjects while retaining different types and callable contracts.
The following facets can be separately declared and referenced; none is a mandatory
eight-field record every value must contain:

- State and structure: values, native slots, collections and explicit references.
- Behavior: pinned native exports and the roles they accept or produce.
- Construction: guarded operations that create subjects and connect behavior.
- Requirements: stable open positions and their applicable constraints.
- Actions: explicit operations with receiver and argument codecs.
- Presentation: native views/editors over selected subjects and bases.
- Continuity: source, implementation, evidence, commitments and history.

An exact reference MUST preserve the native authority, address, care and selected
version/case information required by the operation. `Person#17` is explanatory
notation for such a reference, not a proposed new UUID store. The current namespace
is addressed by native paths; stable subject addresses must be kept separate from
display names and organizational placement.

Renaming a label, sorting rows, moving a canvas occurrence or showing the same subject
under another parent MUST NOT rename its underlying slot keys or relocate its native
address. An actual namespace relocation is an explicit transformation with reference
and consumer assessment. It is not merely a layout operation.

Presentation occurrences, collection memberships and subjects have distinct identities.
One subject may have several occurrences and several memberships. A visual hierarchy
does not by itself transfer ownership. Removing a view does not delete its subject.

Typed arrays, maps, matrices and sequences may live inside native values. An image
need not allocate a namespace record for each pixel. Edits to such values use their
codec, owner reference and expected basis; stable element identity is explicit when
the operation requires it. Dense-value indices are not universally stable identities.

## 4 Projections over shared subjects

A projection connects a native subject or collection to a presented or computed
result. It MUST retain enough information to explain the result and, where allowed,
route an edit to its actual target. The logical contract includes:

| Field | Meaning |
| --- | --- |
| Source | Exact subject, collection or relation reference and selected basis. |
| Position | Stable native key for the projected boundary or column; distinct from screen coordinates. |
| Read behavior | Pinned Foil export and any explicit path/relation navigation. |
| Result contract | Native codec/role, cardinality, availability and coverage. |
| Dependencies | Observed reads, relation/membership edges, missing targets and declared scopes. |
| Write behavior | Optional native action, target-resolution rule and argument codec. |
| Ownership | Source-owned, locally owned or derived result; also whether a value is a historical snapshot. |
| Provenance | Implementation, source/evidence basis and relevant commitments. |

These fields may reuse existing native view/action records. They are not a path
expression language interpreted in the browser. Arbitrary navigation and computation
remain authored native code with explicit dependency coverage.

### A spreadsheet row is a use of a subject

For the acceptance fixture, define `Person.org` as the authoritative organization
reference. `Org.people` is a derived inverse relation. The system MUST NOT maintain
two independent editable truths for that membership without an authored atomic rule.

```text
PeopleSheet
  source: Org#3.people
  row occurrence:
    subject: Person#17
    Name:      read Person#17.name
    Org:       follow Person#17.org; present its name
    Tasks:     count members of Person#17.tasks
    OpenTasks: count established members whose done value is false
```

The row occurrence and projection definition may be sheet-owned. The Person and
Organization remain the original native subjects. Render caches are permitted, but
they MUST NOT become another editable source of the same domain facts.

### Cell presentation does not determine write semantics

| Cell behavior | Source and permissible edit |
| --- | --- |
| Direct field projection | Read an authoritative slot; an authorized edit invokes the native action for that subject and slot. |
| Reference projection | Present a referred subject. Selecting another subject retargets the declared relation through a native action. |
| Derived result | Run pinned computation. The result is read-only unless an explicit inverse/goal-setting action defines how an edit changes inputs. |
| Sheet-owned input | Store a local value or reference owned by the sheet's subject. It remains native and inspectable. |
| Sheet-owned computation | Derive from local and/or shared inputs with the same dependency rules. Local ownership does not make a derived result directly editable. |
| Explicit snapshot | Retain a value on a historical basis and show that it is a snapshot; do not present it as a live projection. |

Ownership and derivation are independent dimensions. A local value can be authoritative
or computed. A shared cell can display a reference, a field or a derived result.

For an Org cell displaying “Acme,” the native action must distinguish:

1. Rename `Org#3.name`, which changes the organization for all its presentations.
2. Reassign `Person#17.org` to `Org#9`, which changes that person's membership.

The current editor affordance MUST identify the operation. A label string MUST NOT
choose an organization identity or infer which of these operations the user meant.
Opening a displayed reference reveals the referenced subject. Dragging it out creates
another occurrence of that subject, unless a separate copy operation was selected.

Sorting, column movement and switching from table to cards MUST preserve the source
references and action targets. A pending edit retains its original subject even if
the row subsequently appears at a different screen position.

### Reference formulas and coordinate formulas

A projected formula over `Person#17.tasks` follows native references and slots.
Display labels may change without changing that binding. The spreadsheet MAY also
support its own coordinate/range semantics. Those formulas must specify whether
they address stable cell subjects, positions, or relative locations in a native grid.

Moving, inserting or deleting cells is then an authored spreadsheet operation with
defined consequences. Merely sorting a projection of people cannot reinterpret
which person a formula addresses. Formula syntax is optional input compiled into
native behavior; it is not a JavaScript spreadsheet evaluator.

## 5 Computation and dependency maintenance

A computation consumes native values/references under a selected basis and produces
a typed result or proposed operations. Native functions may use branching, iteration,
recursion and higher-order composition already supported by Foil. Operation budgets
and native type checks remain effective.

The system MUST distinguish authoritative state, maintained derived publications and
disposable rendering state. A derived publication retains its implementation and input
basis. It is current only while its declared dependencies and applicability remain valid.

Dependency maintenance MUST cover field reads, reference traversal, collection
membership, missing targets and the relevant selection boundary. A count over tasks
depends on membership and the tested task fields, not just the members initially seen.
Retargeting `Person.org` must replace obsolete subscription edges with the new ones.

Reuse native crews, journal changes and subscriptions. Helpers may trace navigation;
custom code must declare read scope where tracing is incomplete. Never claim universal
dependency inference from arbitrary code. Incomplete or truncated evaluation is not
evidence of absence, a zero count, full coverage or compatibility.

The maintained sequence is:

```text
guarded native mutation
        ↓
affected dependency routes
        ↓
invalidated derived uses
        ↓
bounded native re-evaluation
        ↓
new publication or explicit unavailable/unknown result
        ↓
affected presentation updates
```

Frames MUST identify their basis. While re-evaluation is pending, historical results
may remain visible with their original basis and stale status; they must not silently
appear as current values alongside newer inputs. Unaffected computations remain usable.
Unchanged meaningful results SHOULD suppress downstream display churn.

Instantaneous dependency cycles require an explicit bounded fixed-point algorithm
or are rejected. Stateful feedback occurs through committed events and transitions.
It does not justify treating a circular derivation as already established.

Shared identity removes the need to reconcile separate app-owned copies within this
world. It does not remove dependency scheduling, caches, transaction coordination or
the need to reconcile genuinely external observations. No cross-machine coherence is
implied by this local release.

## 6 Actions and guarded changes

Canvas controls, direct manipulation and agent tools invoke the same native action.
The transport carries an authenticated principal, event identity, exact subject and
action/binding reference, expected basis and typed arguments. The native handler
decodes arguments through the pinned codec and resolves actual targets.

Preparation MUST be effect-free. It produces proposed native operations, read/write
basis and relevant checks. Operations may span an explicit owned or granted set of
subjects. The owner transaction revalidates the basis and applies the accepted change
atomically. Invalid arguments, stale cases or failed hard invariants leave committed
state intact and preserve the user's draft.

Duplicate committed event IDs return the recorded outcome within the declared
deduplication contract. Ordering-sensitive input batches retain order and bounded
size. A delayed event from an old binding cannot silently execute its replacement.
Historical and candidate views cannot accidentally dispatch live mutations.

Actions that edit a shared definition declare their scope. An instance edit must not
silently rewrite all consumers. Deletion checks incoming references, ownership and
commitments. Removing a presentation or binding cleans up its owned artifacts; shared
data and another binding's outputs survive.

Undo is a guarded native transition against the current world. It preserves unrelated
intervening work and exposes conflicts. Physical effects, if later enabled, require
their own compensation semantics; reversing a native record does not undo reality.

## 7 Construction and composition

A constructor is a native definition with parameters, reused anchors, required
authority, guarded output operations and a result contract. Its output includes
ordinary native subjects and bindings. Constructors may be referenced, inspected,
parameterized and composed through native mechanisms like other callable behavior.

A composition may combine existing instances, new instances, code, projections or
other compositions. Connections are explicit and checked. A successful live result
MUST be usable at another compatible boundary immediately, without template capture,
host registration or export.

Spatial operations separate three meanings: moving an occurrence, connecting a
declared relation/boundary, and transforming owned structure. A semantic drop previews
its meaning. Proximity may inform a model proposal but does not itself establish a
relation or authorize a mutation. Native checks govern installation.

The result of taking a composition apart may include reusable constituents and
explicit open boundaries. Decomposition is not promised as a lossless mathematical
inverse for arbitrary effects or computation. Its authored transformation must state
what is retained, shared, disconnected, newly created or retired.

A successful instance is not automatically a universal pattern. Scope and open
positions become explicit when it is generalized. Definitions available for reuse
come from actual native publications and contracts, not inferred name similarity.

### Applying existing machinery to another subject

A spreadsheet, calculator, compiler or IDE is an ordinary computational subject
with declared boundaries. Applying it to another subject uses the same composition
path. There is no special universal Machine type or mandatory application importer.

The native assessment establishes supplied connections and records the exact
remaining mismatch. Known authored routes, explicit references and applicable
contracts can support direct binding. A model may propose a route or interpretation
for an unfamiliar pairing, but field names or structural resemblance alone do not
establish semantic agreement.

A residual need MUST retain its owning instance/position, provided anchors, required
contract, relevant consumers, basis, findings and proposed continuations. Extend
existing boundary/work records; do not introduce a second requirements language or
a universal semantic resolver as a prerequisite.

| Remainder | Appropriate continuation |
| --- | --- |
| Several compatible existing inputs | Make the choice locally inspectable; the user or an explicitly authored selection policy chooses. |
| Missing fact or preference | Obtain it from a valid source or the user. Model inference must not manufacture the fact. |
| Required derivation | Author a native computation with explicit inputs and checks; retain it as reusable software. |
| Missing structural relation | Propose guarded construction or an explicit existing route, then assess consumers and ownership. |
| Missing parser, evaluator or other substantial behavior | Author ordinary native definitions and their checks. Decompose the work into further residual needs where necessary. |
| Contract conflict, uncertainty or resource limit | Preserve the unresolved boundary and working unaffected parts; do not claim completion. |

For example, applying a Spreadsheet to Organization may expose a People relation.
Adding an Expected Finish column can require a new CompletionEstimate behavior over
tasks, dependencies and estimates. Missing durations remain explicit. The estimator
must be separately discoverable and reusable by a Timeline without copying a hidden
spreadsheet algorithm or regenerating the same code.

Similarly, applying compiler machinery to a workflow requires an explicit source
representation, semantics and lowering. Similar-looking graphs do not prove that
one program implements another. A proposed adapter must pass its actual checks,
retained examples and stated scope of verification.

## 8 Templates and the growing vocabulary

A template describes construction of an arrangement. Capture MUST identify owned
structure, exact implementation/import pins, shared references, local initialization,
open positions, presentation/action exports, commitments and provenance.

Capture follows the selected ownership boundary. Reachability alone is not permission
to copy. Shared outgoing references remain explicit anchors or parameters. Transient
selection, model credentials and display caches do not become portable domain state.

The following operations remain distinct:

- Show another occurrence of an existing subject.
- Create a fresh instance from a template's initialization policy.
- Duplicate chosen current values into a new owned instance.
- Capture or modify a reusable construction definition.

Changing a constructor affects future constructions at its new pin. Existing
instances retain their state and selected pins until an assessed update targets
them. A template can be just an editor, viewer, constructor or transformation;
it need not describe a complete application.

The Foundry is a contextual native view of reusable definitions and relevant live
subjects. New material appears through the generic publication/discovery path.
The browser MUST NOT acquire new business code whenever this vocabulary grows.
Discovery may be bounded and must report that bound. It need not expose every
artifact globally or claim two similarly named definitions are interchangeable.

## 9 Presentations and interaction

Goo presents native subjects and action capabilities on selected bases. Definitions
may produce tables, documents, timelines, graphs, scenes, images, controls or nested
regions. The rendered result MUST retain exact occurrence, subject, slot and action
metadata needed for inspection and interaction.

The surface may be visually fused while its meaningful parts retain precise native
correspondence. Inspection of a displayed value/control must recover its subject,
read or computation, basis, ownership/derivation and action target. One bar and one
number may present the same publication. Decorative pixels do not require their
own native subjects. This is source/interaction correspondence, not DOM scraping.

The browser supplies generic rendering and input mechanisms. A native graphical
description can contain shapes, text, transforms, clipping, raster tiles, semantic
hit targets and accessibility metadata. Model-authored domain algorithms MUST NOT
become arbitrary JavaScript callbacks hidden behind those targets.

Pointer coordinates propose an interaction with a declared target. Native validation
resolves the actual subject/element against the current basis. Sorting, zooming,
paging, overlap and stale geometry cannot redirect an edit to the wrong subject.
Continuous gestures may use bounded batches and immediate pending previews.

Focus, text drafts, IME composition, scroll, camera and ordinary selection mechanics
remain local unless explicitly committed as useful application state. Native updates
must preserve unrelated drafts and pointer capture. A view change should patch the
affected result rather than remount the whole workspace.

The ordinary surface is the working software. Inspection reveals its causal and
structural depth locally. A result can unfold into inputs, cases, rule, source and
history, then return to ordinary use. Keyboard and pointer users receive equivalent
inspection without triggering the underlying action accidentally.

The model may communicate with an experiment, comparison, temporary editor, diagram,
candidate presentation or local explanation. Users may respond through manipulation,
examples, language, drawing or normal use. A form question is one available interaction,
not the required protocol for resolving every uncertainty.

Open boundaries, valid empty state, waiting for input, waiting for an observation,
unavailable input, conflict and failed evaluation have distinct native states.
The presentation MUST NOT collapse them into a spinner, a fabricated zero or a
generic success. Unsupported rendering produces an inspectable diagnostic.

Presentation constraints can produce ghosted or rejected moves. Automatic adjustment
of other values requires an authored policy. The renderer is not a hidden constraint
solver inventing application behavior from visual proximity.

## 10 Host observations and runtime execution

The foundation needs native values, computation, events and guarded transitions.
It does not require Time, Calendar, Mouse or Keyboard as compulsory application kinds.
Host facilities supply observations; native programs define what they mean.

A wall-clock reading, monotonic elapsed duration and logical step number are different
inputs. Native scheduling and simulation programs must choose explicitly. Local
calendar interpretation, timelines and time zones are domain behavior where needed.
Visual interpolation may smooth a presentation but cannot advance authoritative state.

The clock adapter reuses existing runtime primitives and host supervision. Queueing,
backpressure, step batching, event order, missed deadlines and restart policy are
explicit. Native randomness, where used, records the seed or observed input sufficient
for the claimed replay. A stopped program does not silently consume invented ticks.

An addressed subject is not necessarily an operating-system process or an Enki actor.
Actors supply execution and isolation where required; one actor per displayed object
is not the data model. Long-running native computations are bounded/cancellable and
must not prevent unrelated controls from responding.

Physical effects stay behind declared driver authority. Candidate evaluation may
propose a request but cannot dispatch it. Installed requests are committed before
dispatch, outcomes retain their original basis and uncertain completion remains
explicit. External observations remain evidence even when reconciliation fails.

The closed acceptance suite uses native computation and generic display/input
facilities. It does not outsource its formulas, compiler, game rules or document
semantics to a remote application. Model authoring is allowed; model-backed runtime
answers for established actions are not.

## 11 Model authoring and admission

The model may author ordinary Foil/Grove definitions, new roles/codecs, constructors,
adaptations and Goo presentations. The available native facilities must not reduce
it to selecting business widgets or filling a fixed schema. Conversely, source is
a proposal until compiled and checked by the native system.

Each authoring request uses the selected native closure: subjects, relevant state,
definitions, imports, boundary contracts, dependencies, source, retained cases and
the user's local intent. Context pages remain bounded and carry continuation refs.
Unrelated workspace state and model credentials do not enter this payload.

Known native edits, actions, exact reuse and established construction need no model.
Novel intent can go directly to a capable author. Any routing/type-inference stage
is justified by measured benefit; it does not replace native checking or add mandatory
serial latency to every gesture.

Candidate assessment MUST record:

- Source and compiled artifacts on the exact compiler/import basis.
- Proposed native changes and affected owners/consumers.
- Navigation, absence, membership and policy dependencies.
- Retained commitments and new check results with coverage and uncertainty.
- Proposed presentations and their actual native targets.
- Authoring/execution provenance, including diagnostics and resource limits.

Publication revalidates that basis. A superseded model result cannot overwrite a
newer user edit. Compiler failure, an unknown required check, a stale basis or failed
hard constraint preserves installed behavior. Incomplete unrelated work may remain
explicit while independently established work proceeds.

Within already granted editing authority, reversible established changes may install
with local feedback and undo. The experience must not require a generic Publish
ceremony for every edit. Explicit shared scope, authority expansion or retirement
of an endorsed constraint remains a specific user decision where required.

MCP and canvas actions are presentations of the same native operations. Retain the
small existing status/read/write/compile/eval/observe/source/context/events transport
and version its envelopes where necessary. No independent per-application API or
Python semantic service is required to make a new native definition usable.

## 12 Evidence and commitments

An example records inputs, expected or observed result, basis and provenance. A
commitment additionally states that a scoped check must continue to hold. An explicit
user-endorsed example should become a retained case when its change is installed;
an inferred example is not silently promoted to universal intent.

Every later candidate affecting that scope evaluates the retained checkers from the
prior basis alongside new checks. Removing or replacing the current source checker
cannot erase the old obligation. Retirement is an explicit assessed change with
visible affected uses.

Agent claims, agent-generated cases, user demonstrations, retained real interactions
and authenticated execution receipts remain distinguishable. Natural-language
explanations link to actual results or state that they are interpretations.
Partial evaluation is never labelled complete.

Same-program deterministic replay and evaluation of changed code are different.
A historical external outcome can support changed-code evaluation only where its
request contract and relevant inputs still match. Native state snapshots are not
evidence that an external effect can safely be repeated.

## 13 Persistence and lifecycle

Authoritative native state, pinned implementations, endorsed commitments and relevant
history persist. Derived publications retain their basis. Render caches, viewport
motion and unchanged reads must not create persistent application history.

Retiring a view, binding, candidate or generated definition follows ownership and
consumer reachability. Unused visual scaffolding should disappear. Shared data,
referenced code and retained evidence must not be deleted to clean up the screen.

Runtime transport, abandoned queues and disposable compilation stores are released
when no longer owned. The development setup retains at most two unresolved failure
stores and discards diagnosed disposable stores while keeping small reproducible
inputs, source, logs and receipts. New stores live outside iCloud.

Do not truncate live pins or repeatedly archive full worlds. Native compaction needs
a reachability and recovery proof. Until a sustainable history policy is established,
long-running examples remain bounded by measured storage and memory guards.

## 14 Acceptance for the shared native spreadsheet

These cases are the first decisive proof of the common-substrate claim. Use actual
native execution, real browser events and retained source/receipt evidence. The
Person/Organization/Task vocabulary is an ordinary fixture, not privileged core code.

| Case | Required observation |
| --- | --- |
| Shared row identity | Place an existing person in a sheet and a separate editor. Both resolve to the same native subject; only occurrence/projection metadata is newly created. |
| Edit from either surface | Rename the person in each surface in turn. One authoritative mutation changes both presentations; no copy reconciliation runs. |
| Reference retarget | Choose a different organization through a reference editor. Only the intended membership changes; the old and new inverse People views update. Neither organization is renamed. |
| Explicit rename | Invoke the organization rename action separately. All relevant presentations of that organization update without changing membership. |
| Relational calculation | Add/remove a task and change its completion. Counts update from membership and field dependencies. Unknown fields are reported rather than treated as false or zero. |
| Topology change | Retarget a reference, delete a target and restore an applicable input. Correct dependencies are replaced; affected uses become unavailable and recover; unrelated results survive. |
| Stable UI targeting | Sort rows, move columns, page and switch to cards with an edit pending. It either applies to the original subject on a valid basis or is rejected as stale. |
| Native cell content | Put a Person reference and a callable Compiler definition reference in cells. Open/drag them as those native subjects. Execution still requires the declared callable contract and authority. |
| Local state | Add sheet-owned input and a local formula. They remain separate from the Person's authoritative fields and from a derived shared result. |
| Downstream composition | Feed a native Cost publication into ProjectBudget and OrganizationForecast. Change its input through the sheet; inspect the affected native chain on consistent bases. |
| Live closure | Pass the working sheet to another computation and embed another presentation before creating a template. No export or host application handler is added. |
| Reuse and generalization | Capture a sheet/evaluator arrangement with explicit subject boundaries. Bind a new instance to different compatible data and retain unresolved positions where it does not fit. |
| Substantial adaptation | Request an Expected Finish column requiring missing computation. Retain explicit missing inputs, establish a native estimator and bind the same estimator into another presentation without copying or regenerating it. |
| Commitment regression | Endorse a demonstrated calculation; propose a change violating it and removing its current checker. Prior retained evidence still exposes the failure. |
| Model unavailable | Disable model access. Established editing, recalculation, inspection and instantiation still work. |

## 15 Capability progression and self hosting

Implement in increasing expressive demand, retaining usable native machinery from
each step:

| Step | Semantics to establish | Material retained for further construction |
| --- | --- | --- |
| Calculator | Typed inputs, operations, actual calculation, local inspection and errors. | Computations, parameter controls and result presentations. |
| Plain text editor | Sequence edits, selection/drafts, guarded writes and undo. | Editor actions, text presentation and reusable editing arrangement. |
| Spreadsheet | Native references, projections, editable bindings, formulas, ranges and dependency propagation. | Grid, evaluator, projection definitions and higher-order sheet. |
| Drawing environment | Geometry, transforms, grouping, constraints and direct manipulation. | Scene, selection and authored spatial operations. |
| Small compiler | A declared small language, parse/tree transform/check/lower stages and real diagnostics. | Parser, transformation pipeline and callable compiler. |
| Rule system or simulation | Authored legal moves or state transitions, observation-driven execution and inspection. | State machine, optional clock binding and graphical instrument. |
| Development environment | Compose the retained editor, compiler, source/project references and diagnostics. | A higher-order tool that operates on native definitions. |
| Native canvas editing | Use those tools to change a native workspace presentation/action through normal admission. | A demonstrated self-editing part of the construction environment. |

The compiler exercise uses a small specified language, not a rewrite of the existing
Foil compiler. The development environment also exposes the already installed native
compiler as a callable component. The final test changes a real native canvas
definition and preserves a pinned recovery interface when compilation fails.

Games, image editing, slide composition, sequencers and query environments remain
additional tests of generality. They are not all required feature-complete products
in this release. Each must eventually use native machinery rather than a host switch
on an application name. Live authoring evidence must be distinct from prewritten
deterministic regression fixtures.

## 16 Performance and implementation evidence

The implementation plan defines measured latency, hour-long operation, memory and
storage gates. Ordinary layout is local; established actions do not call the model.
Tests must report actual workload, hardware, warm-up, failures and resource use.
No manufactured pass records or mock renderer can establish native acceptance.

The current small-grammar proof is partial: its native checks, real generated Foil
and working Goo actions are useful evidence. General projections, broader guarded
action targets, full maintained dependency integration, the spreadsheet acceptance,
recursive capture and the self-editing environment still require implementation.

Source responsibility stays in existing Grove/action/view/publication modules,
native Goo rendering, the current medium and the existing runtime/host boundaries.
The plan's file map identifies extensions and additions. New projection metadata
must reuse native view/action contracts; a second data model or evaluator would
violate this specification.
