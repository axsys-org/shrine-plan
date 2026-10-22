# Shrine cooperative agent substrate implementation plan

## Current implementation scope — 2026-10-22

The first deliverable is the backend harness in
[`extras/mounts/cooperate`](../../extras/mounts/cooperate/README.md). External
agents use MCP to open work beneath an existing document, capture selected
namespace inputs, append linked observations and outputs, and finish with a
typed result that another cell can consume. Shared namespace admission checks
dependencies and commits each command atomically. Context snapshots, pinned
branch/reply references and retry keys preserve the trace.

This scope does not require an example application, a new editor, a model
provider, a scheduler, or a human acceptance step. Completion checks freshness;
human review can be added by a workflow that needs it. The workspace and research
stories below are possible applications, not implementation prerequisites.
The detailed managed-runtime and durable-effect contracts remain later work.
The mount README records the implemented interface and its current limits.

## Longer-term direction

Build cooperation around a Nenex document that is a functional namespace
subtree. Its prose, inputs, evidence, cell bindings, work traces and results
have addressable names. Nenex presents that material to the human; MCP lets
agents inspect and contribute to the same material; cells derive useful values
from its declared inputs. A document can consume another document's result by
reference. This shared document loop is the first deliverable.

The cooperative substrate supplies the rules for contributing to that loop:
capture what an agent saw, preserve its contributions, detect changed dependencies,
and admit coherent results. Managed workers, scheduling and durable effect
recovery extend the loop after it works. Grove describes record roles and
actions; Foil implements transitions and derivations; shared Goo/Mash components
present them.

The primary deliverable is functional material: a namespace-resident result
with declared inputs, contracts and useful behavior that another person or
procedure can apply or compose. Markdown is a readable projection or supporting
evidence. Completing a conversation and saving its prose is insufficient to
demonstrate this substrate.

One illustrative workflow is choosing a workspace: two agents contribute cost
evidence and a recommendation, the human changes a constraint, live calculations
change, and an outdated recommendation cannot be accepted. The accepted result
feeds a budget document; the same comparison logic works on another candidate
set. Preserve the distinction between definitions, applications, attempts and
effects wherever those lifecycle facts are needed.

This is an implementation proposal against Shrine `63fa89b`, revised on
2026-10-21 after inspecting the Nenex, cells and MCP implementations.
Names, schemas, commands, module paths, and budgets introduced below are
proposed contracts. Existing behavior is identified separately. Plan review
completed on 2026-10-21.

## Focus and scope

Assume a familiar Notion-like block surface. The work here is letting those
blocks contain or reference useful Shrine data, declarations, computations and
results, with people and models able to contribute through the same operations.
Workspace design, navigation systems, canvas authoring and a new block editor
are not prerequisites or primary deliverables.

Prove one small loop first: put input in a block, apply named logic, inspect its
result inline, change the input or logic, and use the result in another block.
Then let two model workers contribute to that same loop. Keep terminology and
runtime bookkeeping beneath the interface; do not require users to organize
their work around a new taxonomy or introduce a general object/workflow layer.

Use the native mechanisms required by that concrete loop. The detailed runtime
contracts below describe correctness and recovery obligations, not a mandate
to build a general framework before the example works. Editor or host changes
are justified only where they block that loop, such as preserving a draft
during refresh or capturing the right declaration revision.

Start with the [proof of concept](#proof-of-concept-choose-a-workspace), then use the
[phased tickets](#phases-and-tickets) for implementation and the
[verification matrix](#verification-matrix) for release evidence.

## Outcomes and release boundaries

Deliver the visible document proof first, followed by a managed runtime and
durable release. Keep editor alignment on a separate optional track:

| Milestone | User outcome | Required boundary |
| --- | --- | --- |
| Document loop proof | Human and external MCP agents operate on one Nenex subtree; changed criteria invalidate a proposal; accepted output is consumed elsewhere | Safe document ownership, typed cells, bounded atomic captures, immutable proposals, shared revision-checked review; one running sovereign |
| Managed runtime proof | Shrine assigns and joins work, with deterministic fake workers | Claims, budgets, cancellation, captured effects and executable failure tests |
| Durable cooperative MVP | Humans and managed model workers cooperate through Nenex, with restart recovery | Durable namespace state, one real worker adapter, Grove work controls, bounded scheduling |
| Optional Grove Nenex alignment | Existing editing and presentation use shared Grove/Goo infrastructure | Follow the separate shared-editor work where needed; no workspace redesign prerequisite |

### Functional outputs

A successful workflow must leave at least one useful operational artifact,
not only its transcript, report or execution log. That artifact can be a
parameterized cell, a constrained plan with declared actions, an installed
procedure, or a reusable transformation. Functionality may come from typed
data bound to existing published behavior; it does not require generating new
code or making every evidence record a function.

| Story | Delivered artifact | What the user can do with it |
| --- | --- | --- |
| Research | Evidence-backed comparison with declared criteria, input bindings and evaluation views | Change a criterion, inspect affected claims, bind another evidence set, or feed its typed result into another procedure |
| Personal planning | Constraint-aware plan with alternatives, dependency bindings and action contracts | Explore a changed circumstance, compare a candidate plan and authorize a resulting action |
| Multiple models | Validated procedure or tool assembled from model contributions and published operations | Apply it to new input, substitute an implementation satisfying its contract, or compose its output with another tool |

Render each artifact through Grove and expose its applicable operations to
agents through the same contracts. Pure evaluation stays separate from admitted
external effects. The MVP uses the vetted operation vocabulary; arbitrary source
generation remains outside its execution policy.

The release test must apply a delivered artifact to a second input without
reconstructing its instructions from prose, and consume its typed output in
another declared operation. The artifact remains usable after the producing
attempt finishes; the durable MVP also proves reuse after restart. Reusing only
the workflow that produced a static report does not satisfy this gate.

The cooperative MVP may retain the existing Semidoc source-editing route as
an explicitly transitional interface. Its work, review, and execution controls
must use Grove. Full Grove compliance is a separate gate dependent on the
shared text infrastructure; do not report that gate complete while custom
Nenex save, draft, or selection logic remains.

The initial deployment is one local sovereign, one human owner, and a bounded
set of workers. Support different model providers through adapters after one
adapter passes the execution contract. Distributed scheduling, tenant isolation,
arbitrary process migration, autonomous procedure publication, unrestricted
code generation, and automatic general-purpose merge are later work.

## Proof of concept: choose a workspace

**User story:** I want one working document where I can compare workspaces,
ask agents to contribute evidence and advice, change my requirements, and see
which conclusions still hold. When I decide, my budget document can use the
decision directly. I can apply the comparison to another set of places without
reconstructing a prompt or copying a report.

### What the human experiences

1. Open **Choose a workspace** in Nenex. The page contains ordinary prose,
   editable criteria, an evidence table, a live comparison and a review area.
   Start with a monthly budget of 450, a commute limit of 30 minutes, and a
   requirement for quiet space. Use three fictional, locally supplied listings
   so the proof has no dependency on browsing or external purchases.
2. Ask an agent through MCP to extract costs with citations to those listings.
   It reads a bounded captured evidence set and submits typed candidate facts
   under this document. The page shows the proposal; accepting it populates
   the canonical candidate records. Costs are derived by cells from rent plus
   fees. The agent does not invent a second copy of the comparison in chat.
3. Ask a second MCP agent to assess fit and recommend an eligible candidate.
   Its capture includes accepted facts, current criteria and comparison logic.
   Keep this recommendation pending while the human edits the document.
4. Lower the budget to 350. The next live cell read shows **no qualifying
   workspace**. The pending recommendation is visibly stale and acceptance
   refuses it even if the UI has not refreshed. The cost evidence stays usable:
   extracting rent and fees did not depend on the budget. Explicitly request
   another assessment; changing an input does not itself call a model.
5. The agent explains the conflict and proposes relaxing the quiet requirement.
   The human explicitly makes that change. Harbor now qualifies at 300, leaving
   50. The agent submits a recommendation against this new capture; the human
   accepts it. The decision records the exact criteria, evidence, logic and
   selected result. Earlier proposals and decisions remain inspectable.
6. In **Monthly budget**, bind a cell to that accepted decision's typed monthly
   cost and subtract it from 350. It displays 50 without parsing the advice.
   Keep this binding pinned to the decision until the human chooses to advance
   it; a live binding to the comparison is also possible but visibly distinct.
7. Apply the same pinned comparison recipe to a second candidate collection
   with independent criteria. It produces another typed result without another
   model call or copied instructions. Editing prose or removing an inline
   occurrence in either document preserves the underlying calculation.

The deterministic fixture is:

| Candidate | Rent | Fees | Total | Commute | Quiet |
| --- | --- | --- | --- | --- | --- |
| Cedar | 320 | 40 | 360 | 25 | Yes |
| Harbor | 280 | 20 | 300 | 20 | No |
| Loft | 390 | 30 | 420 | 15 | Yes |

The rule is cheapest eligible candidate, with canonical name as a deterministic
tie-break. Initially Cedar wins. At budget 350 with quiet required, none qualify.
At budget 350 with quiet optional, Harbor wins. Missing or malformed facts yield
diagnostics, not zero costs. No-match is a typed result, not an empty name that
can accidentally be accepted as a recommendation.

### One document namespace, several views

Use named children alongside Nenex's existing numbered content tree. The names
below are a proposed fixture convention; the numeric-versus-named ownership
boundary already exists. Every collection used as a pinned input has an
explicit root record, not just descendants beneath a structural folder.

```text
/0x11/user/docs/workspace-choice
  src (slot)               Semidoc source on the page record
  0/, 1/, ...              Numbered expanded Semidoc content
  inputs/criteria          Budget, commute, quiet requirement
  inputs/candidates/       Accepted candidate facts with stable identities
  evidence/                Listing snapshots and source references
  logic/comparison         Binding to a pinned published comparison recipe
  cells/                   Cost, eligibility, ranking and result bindings
  work/                    Applications, captures and immutable contributions
  decisions/               Accepted result snapshots and review evidence
  bindings/                Inline occurrences and referenced subjects

/0x11/user/docs/monthly-budget
  src (slot), 0/, ...      Existing Semidoc representation
  bindings/workspace       Reference to one accepted decision above
  cells/headroom           Subtraction using that decision's monthly cost
```

These are ownership conventions, not a fixed schema that every document must
instantiate. Published behavior may live under `gov/cooperate`; shared evidence
or artifacts may be referenced from elsewhere. Locally produced work belongs
under the document by default. Containment does not replace dependency edges,
grant execution authority, or make every referenced record owned by the page.

Nenex edits and displays these names; MCP reads and submits against these same
names. Cells bind primary and secondary inputs explicitly and expose values at
`/x` and diagnostics at `/c/x`. They evaluate through native dependency
resolution. The UI refreshes affected views; no background model execution is
implied. A proposal carries its captured read-set. A human acceptance checks
that read-set and writes the decision, canonical changes and receipt together.

Capture dependencies at the declared input boundary: cost extraction depends
on listings; fit depends on candidate facts, criteria and comparison logic.
Include collection membership where selection depends on it. Do not invalidate
every contribution merely because something in its document subtree changed,
or let a client omit required dependencies to make a proposal appear current.

Distinguish three things in the UI and API: the **live calculated result**, an
agent's **proposed interpretation**, and a **captured accepted decision**. A
changed input updates the first, may invalidate the second, and leaves the
third as historical evidence with an explicit indication of whether it still
matches current inputs. An accepted claim is not silently rewritten by a cell.

### What exists and what must be built

| Part of the loop | Reuse now | Small required addition |
| --- | --- | --- |
| Addressable material | Namespace records, references, history, bounded MCP reads and Nenex's numeric-versus-named child boundary | Document-local ownership convention and preservation tests |
| Computation | `/x`, `/c/x`, published transforms and standard arithmetic/collection cells | Typed comparison transform with candidates and criteria as explicit inputs, validation and stable result identity |
| Agent access | MCP `read`, `write`, `history`, `apply` | Shared admitted capture, submit, revise and accept operations with manifests and receipts |
| Human view | Nenex source editing and reference transclusion; Grove/Goo views | Inline input/result/review bindings, stable occurrences and retained controls |
| Cooperation | External MCP clients can read and contribute to a running sovereign | Immutable proposals, dependency-specific staleness and human acceptance |
| Reuse | Named definitions, pinned references and cell composition | A parameterized comparison recipe, second-input fixture and cross-document binding |

Current `between`/`where` predicates use literal parameters; they do not by
themselves implement a live predicate driven by another criteria record. Add a
small vetted comparison transform instead of claiming the existing filter can
already do this. Reuse standard cells where their contracts fit. Preserve
canonical candidate references through sorting; generated row positions are
not candidate identities. A reference stored in a field is data until an
operation explicitly resolves it as an input.

Current MCP `apply` operates on a record; it is not already the atomic
multi-record acceptance protocol. Add a narrow adapter into shared admission,
using the same declared commands as Grove. Capture inputs atomically on the
server; several separately timed MCP reads are not a coherent execution
snapshot. Restrict raw writes to governed lifecycle fields. `who` is an audit
label, not authenticated identity; this local proof does not establish isolation
between mutually untrusted agents.

Nenex reconstructs its page record during expansion, but Semidoc reads only
numbered children. Named direct children such as `inputs`, `cells` and `work`
already stay outside source synchronization, and expansion only writes or culls
source-derived numeric paths. Put harness state beneath those named children,
not on the reconstructed page record or beneath numbered prose nodes. Test that
contract; no content relocation or migration adapter is required for this
backend boundary. A generic namespace explorer alone does not prove the Nenex
experience.

### Deliberate first-proof limits

Use one human and two manually prompted external MCP sessions. One session can
exercise the vertical slice first; two distinct contributions complete the
cooperation demonstration. They submit captured observations and proposals;
Shrine does not yet manage their model dispatch, credentials, retries or cost.
Capture provenance describes the material supplied through the protocol, not
an assertion that an external client's hidden context or execution is known.
Use scripted equivalent submissions for repeatable correctness tests.

The first proof runs within one sovereign lifetime. It must not claim durable
acknowledgment or resume after restart. Managed execution, leases, effect
receipts and native persistence belong to the next milestones. Human review,
input coherence, stale refusal, document preservation and typed reuse are
required now. Do not defer them behind a scheduler, new editor, generated code,
web research, or a general-purpose agent framework.

## Architectural decisions

1. Shrine owns authoritative work state, history, commands, and receipts.
   Host workers may hold disposable execution state and bounded caches.
   A Nenex document's subtree is the default home of its locally owned inputs,
   cells and work; shared material is connected through explicit references.
2. Foil implements typed values and pure transitions. Grove declares roles,
   norms, actions, views, and panes. Goo prepares presentation and interaction;
   Mash paints and captures input through shared components.
3. Use publisher-owned slot identities. Import shared slots and role
   declarations; avoid application-specific interpretations of generic global
   keys such as `status` or `result`.
4. Use orthogonal roles rather than a universal discriminator for skill,
   conversation, and issue. Preserve unrelated facets during every update.
5. Keep definition identity, application identity, attempt identity, and effect
   identity separate. Retries and revisions must remain distinguishable.
6. Reads and derived projections never launch effects. A command requests
   execution. The first proof uses explicit external-client requests; managed
   execution later passes through scheduler admission and a bound worker.
7. A concrete attempt begins with an immutable execution manifest. Each later
   observation and model request has its own recorded inputs. Live references
   may describe desired work, but never substitute for execution evidence.
8. Contributions are immutable proposals with provenance. Acceptance is a
   revision-checked transition against canonical state.
9. Reuse the namespace journal and history. Add durable storage at the
   sovereign boundary rather than introducing a separate task database.
10. Keep computation bounded and paged. Avoid whole-world prompts, whole-world
    subscriptions, deep nested live projections, and repeated full graph scans.
11. Preserve current Nenex content and URLs using the existing named-child boundary.
    Editing document content must not rewrite execution history.
12. Improve reusable procedures by publishing successor revisions after review.
    Already-running attempts keep their original definition.
13. Implement coordination as Foil behavior over namespace records. Reuse
    native dependency settlement and Grove publication/installation; the host
    adapter must not grow a second workflow interpreter or subscription engine.

## Native implementation contract

### Names, declarations and values

There is no separate executable-object model. Identity is a namespace name;
an exact historical reference additionally identifies its care and revision.
A declaration publishes typed values and metadata at names. A named record can
bind published behavior and inputs, while derived paths resolve transformations
of those values. "Functional artifact" is product language for these named
values and bindings, not a universal record wrapper, class, object heap or
independent identity registry.

Grove roles describe structural participation; actions and Foil laws are
published declarations with explicit receivers/arguments. They are not methods
owned by a new executable-object base class. Definition, application, attempt,
contribution and receipt distinguish necessary lifecycle facts in ordinary
namespace records, not mutually exclusive object classes. A pure named function
or derived view needs no application/attempt record merely to be used. Create
execution records when policy, effects, provenance or recovery require them.

Use the namespace as the execution medium as well as the record store. Grove
publishes the cooperative vocabulary and reusable installations; Foil supplies
typed executable behavior. The work graph describes instances and dependencies,
while pinned Foil laws give those records their meaning.

| Concern | Native mechanism to reuse | New work actually required |
| --- | --- | --- |
| State evolution | `form` laws, `bowl`, `yell`, `writ` and emitted cards | Cooperative transition rules, fenced admission and durable effect ordering |
| Dependency wakeup | Named `/sys/crew` bindings, `hear`/`take`, existing hive and change signs | Bounded ready/lease indexes; improve native indexing only where measured |
| References and versions | `safe`, `definition_reference`, per-care data/shape counters, `/h` | Complete capture closure and input-policy checks |
| Record facets | Grove `@role` composition and generated `from_myth`/`to_myth`, stored role contracts | Cooperative fields and value codecs; protect lifecycle fields |
| Reusable graph skeleton | Grove `@tree` templates, explicit instance references, `grove_install/instantiate` | Validated input binding, budget admission and application generation |
| Published behavior | Versioned compiler definitions, `/sys/mold`, module bundles and publication batches | Exact behavior/contract references in attempts and reviewable successors |
| Commands and discovery | Published Grove action schema/handler plus shared admission | Multi-record command result support and codec reflection for machine tools |
| Pure interpretations | Standard cells, `/o`, `/x`, captured `@sewn` norms | Domain-specific candidate/validation logic and provenance where missing |

### Namespace behavior and reactive dependencies

Implement the coordinator's durable transitions in Foil and expose them through
native behavior and admission adapters. Use `init`/`talk` for local setup and
commands, and `take`/`hear` where subtree or declared dependency changes need a
bounded response. Return namespace cards and typed request records; do not run
model calls inside a behavior law. The current `dead`/`goof` arms are vocabulary
only and cannot be the cancellation or failure implementation.

Use named crew bindings and the native hive for dependency notification. A ready
queue or lease index is a rebuildable scheduling projection, not a duplicate
graph of subscriptions maintained by Python. Distinguish data changes from
membership/shape changes when deciding what to recompute. Care `.y` still
includes record data; it is not itself a shape-only subscription.
Keep reactive cooperation records under the application namespace. Native
observer construction excludes `/io` records and filters `/log` dependencies;
use narrow `/io` bindings for transport and the journal API for recovery.

Use `fresh` only for deliberately live desired bindings. Immutable attempt
manifests, accepted evidence and executable definition references must retain
their captured versions; attaching the fresh behavior would advance top-level
`safe` values. Preserve unknown, tombstoned and known resolution states as
distinct typed outcomes.

Stored `lash` contracts provide native record-shape checking. They do not prove
legal state transitions or grant authority: current admission permits contract
adoption, and culls bypass record-shape checking. Protect contract and lifecycle
changes through the governed command boundary. Treat operation cards and
`writ/warp` as useful single-record adapters, not as an existing implementation
of captured, authorized, multi-record commands.

Use the trusted `helm/card/snapshot` route for bounded reads from one namespace
state. Extend it for typed capture instead of assembling a snapshot from
separately timed MCP reads. Admission still checks the selected revisions and
commits the manifest atomically; the read route itself is not a transaction.

### Grove publication, reuse and introspection

Publish each reusable work definition with its roles, action declarations,
view contracts, compiled behavior references and optional Grove tree template.
Instantiate graph skeletons using the existing installer. Retain its pinned
`/sys/grove/source`; rebase only explicit instance references. Keep shared code,
publisher slots and ordinary opaque paths unchanged. A parameter binder is a
typed admitted operation, not ad hoc string substitution into paths.

Install bounded collections with `@tree #like` so Grove supplies the existing
ward/lash behavior as well as validation. Keep contracts on non-overlapping
collection roots: nested or overlapping `#like` installations currently require
norm composition and are rejected. Retain actual module bundles, typed exports
and reachable compiler/dependency artifacts in execution references, not merely
a semantic version label. Check template-added fresh behavior when installing
cells; no immutable execution reference may inherit it accidentally.

The current installer requires an absent root and can produce a shared-code
instance. It does not supply cooperative budgets or input capture, so those
remain admission work. Do not use `grove_install/replace` to upgrade active
work: it culls and reinstantiates the instance. Publish a successor definition
and explicitly create or migrate an application generation instead.

Human controls and agent tools should discover the same published actions,
argument contracts, documentation and refusal reasons. Derive their adapters
from Grove declarations and exported codecs rather than maintaining a second
hand-written JSON schema. Current `grove_role_schema` records slots and presence,
not a complete JSON encoding schema; add a narrow codec-descriptor reflection
extension before promising automatic tool-schema generation. Captured publication
identity and authority checks still apply to every invocation.

Reuse declaration and Goo inspection to expose canonical receiver, role/action,
publication, source location and refusal reason. Browser captures are observations,
not replayable authority. First reuse parameterizes existing published code.
Later source-changing improvements should use registered draft, preview and
validated publication machinery, adapting its destructive instance replacement
before applying it to active work.

### Foil as the execution language

Use Foil sum/product types for commands, observations, step outcomes, refusals
and effect requests. Use Grove-generated role converters at the open-record
boundary so unrelated facets survive. Do not hand-write a second closed record
model duplicating those generated converters.

Represent a resumable worker step as a pinned behavior definition plus explicit
typed state. Given that state and a recorded observation, its pure transition
returns the next state and bounded requests/cards. Compose these typed laws and
parameterized values directly in Foil; the dependency graph remains inspectable
namespace data, not a separate language interpreted by the provider adapter.
Definitions may call shared published helpers and reuse standard cells where
their semantics fit. Add new overlay laws only for missing domain semantics.

The host owns transport, credentials, timeouts and external capability handles.
It does not decide acceptance, graph expansion, budget policy or the next agent
step. Initial integration may use Python for provider transport, but the
orchestration stays in Foil/PLAN. Prefer explicit continuation data plus a code
reference to hidden host stacks. C3 must prove restoration of the actual values
and their reachable pins before declaring continuations durable; native function
values alone do not establish on-disk recovery.

Keep runtime inputs explicitly bound or unbound in typed values; Foil's type
holes are compile-time polymorphism, not suspended runtime arguments. Decode
and validate host messages even when a nominal cast succeeds. Foil is lazy:
force required validation and the bounded next-state/request envelope inside
the error boundary before admission. Pass wall-clock observations and entropy
as recorded inputs; `bowl.now` is a logical activation clock, not a deadline.

The native-composition acceptance test installs one published definition at two
roots, applies an additional role without replacing existing facets, composes
two derived views, and invokes one declared command through both UI and MCP.
The instances share pinned code but keep independent inputs, attempts and
budgets. Updating the publication must leave their captured behavior unchanged.

## Existing foundations and required extensions

| Foundation | Existing behavior | Extension required |
| --- | --- | --- |
| [Namespace resolver](../../src/foil/lain_peek.foil) | Historical and nested derived reads; live and pinned input references | Complete execution snapshot capture and explicit limits |
| [View constructors](../../src/foil/sys/view.foil) | Record and tree transformations, parameterized views, cells | Cooperative projection library and contracts |
| [Standard cells](../../src/foil/weft_std.foil) | Composition, amendments, stamped model answers | Multi-input execution identity and strict acceptance |
| [Overlay cache](../../src/foil/overlay_cache.foil) | Optional non-authoritative materialization, nested dependency updates | Measured use for expensive shared projections |
| [Grove roles](../../src/foil/grove_roles.foil) | Typed fields, role composition, preservation of extra fields | Shared cooperation roles and domain codecs |
| [Grove transformations](../../src/foil/grove_sewn.foil) | Source and target norm checks captured with compiled transformation | Contracted work collections and context projections |
| [Goo admission](../../src/foil/goo_runtime.foil) | Publication, subject, authority, lifetime and revision checks | Shared typed command admission for multi-record transitions |
| [MCP mount](../../extras/mounts/mcp/mcp_mount.foil) | Bounded reads, batched writes, history, operation application | Governed work commands using the same authority boundary as UI |
| [Chat extra](../../extras/mounts/chat/main.foil) | Addressable requests, tool traffic, parked reads, branching | Reuse patterns; replace transcript-driven execution identity and cancellation |
| [Nenex](../../extras/mounts/nenex/main.foil) | Atomic Semidoc expansion and record/source synchronization | Explicit content ownership, stable identity, shared edit transition |
| [Supervisor](../../src/foil/helm.foil) | Atomic admitted cascades and registered host endpoints | Persistence and a dedicated worker registration path |
| [Native behavior vocabulary](../../src/foil/sys/hand.foil) | Typed behavior laws, cards and named dependency context | Cooperative command and step adapters |
| [Grove installation](../../src/foil/grove_install.foil) | Versioned templates, explicit instance references, atomic installation | Admitted parameter binding and non-destructive definition upgrades |
| [Compiler publication](../../src/foil/publication.foil) | Expected-revision publication batches and typed definition metadata | Review and capture of exact cooperative behavior generations |

Current chat comments do not establish a working model transport. The present
supervisor rejects outbound moves; chat tests use a dummy model driver. The
new runtime must have its own demonstrated adapter and must not depend on
enabling general outbound routing as an incidental prerequisite.

External MCP sessions can exercise the document loop without adding an internal
model transport. The current MCP `ask` hand is a reference implementation, not
the production scheduler. It reads context and live input separately, caps input at one page,
and stamps only case, prompt, and model. Replace that execution path with
captured input manifests, distinct attempts, bounded retries, and receipts.

## Record model and ownership

Use ordinary addressable records and typed references. Keep hot mutable
coordination records small; store long evidence, transcripts, and artifacts
separately. Do not put the entire work graph in one aggregate.

| Record | Essential fields | Mutation rule |
| --- | --- | --- |
| Definition revision | Procedure or composition reference, input/output contracts, acceptance contract, declared effect requirements, parent revision | Published revision is immutable; changes produce a successor |
| Application | Definition reference, desired input bindings, specification generation, run and owner references, dependency edges, execution policy, accepted contribution reference | Commands revise specification or lifecycle with expected generation |
| Attempt | Application generation, run and owner references, initial manifest, observation/effect references, worker binding, lease generation, budget reservation, state | Runtime owns transitions; terminal outcome and recorded inputs remain historical |
| Contribution | Producing attempt or human identity, base references, artifact references, proposed changes, validation evidence | Immutable once submitted |
| Effect | Logical operation ID, immutable request digest and payload, recovery policy, dispatch references, outcome | Each dispatch records its attempt, lease generation, authority, reservation and receipt; changed payload requires new intent |
| Decision | Accepted/rejected contribution, reviewer, criteria revision, input generation, evidence | Append-only decision; current acceptance is a separate application reference |
| Document | Content identity, revision, Semidoc representation or shared document value | Document operations own content updates |

Discussion entries, progress reports, and tool observations are typed ordinary
records attached by reference. They do not become a second authoritative
lifecycle. A worker's final message is evidence; it does not itself complete
an application.

The proposed mount is `cooperate`. Its source package lives in
`extras/mounts/cooperate`; declarations publish under `gov/cooperate`.
Install document-local inputs, cell bindings, applications, contributions and
decisions beneath the owning document, following the proof's layout. Add
attempts and effects there when managed execution needs them. Published reusable
definitions and genuinely shared work may live elsewhere and be bound by
reference. A global `/<node>/app/cooperate` location may hold runtime policy or
indexes, but must not become a mandatory alternative home for every document's
work. Other authorized names can satisfy the same declared contracts.

Namespace containment establishes storage organization; authority comes from
the admitted bindings and applicable namespace policy. A path alone is not a
security boundary. Explicit run and execution-owner references govern budget
inheritance and cancellation across record collections. Give each attempt and
owned subtask one execution owner; reject ownership cycles.

Dependency, discussion, derivation, review, and presentation-grouping edges
are separately typed references. A shared dependency is not owned by every
consumer. These relations must not acquire different meanings merely because
the UI draws them as a tree.

### Structural roles

Start with `Readable`, `Applicable`, `Reviewable`, `Evidenced`, and
`ExecutableRequest`, plus narrow receiver roles for individual commands.
Role names describe contracts, not worker personalities.

A definition and an application can both be readable and reviewable. A
document can become evidence without being converted into another object
kind. A contribution can be consumed by several applications.

Grove role matching establishes shape, not permission. Matching an executable
role never grants the ability to execute it. Authority is checked by the
command boundary and worker binding.

Use typed codecs for references, state enums, budgets, generations, and
artifacts. Use norms for bounded collection shapes where appropriate. Keep
open-ended heterogeneous graphs connected by explicit references rather than
forcing the complete namespace into one rigid norm.

## Overlay and cell composition

Use `dyed` for record transformations, `knit` for expanding a definition into
a plan, `felt` for reducing a subtree, and `sewn` for restructuring a tree.
Use `/x` cells when a transformation needs parameters, primary and secondary
inputs, or diagnostics exposed through `/c/x`.

There is an implementation distinction: current Grove `@sewn` compiles to a
`spun` value with captured norm contracts. Compose that declaration through
the `/x` mechanism. The `/o` resolver directly accepts `dyed`, `knit`, `felt`,
and `sewn`; do not assume every Grove transformation can be used as a raw
`/o` function. Add a tested adapter only if a concrete use requires it.

The eventual projection library contains the following views. The first proof
needs comparison, context, validation and review; managed readiness and progress
follow with the scheduler.

| Projection | Inputs | Output |
| --- | --- | --- |
| Candidate | Pinned base, ordered typed proposals | Proposed state and conflict diagnostics |
| Readiness | Application metadata, accepted dependency results, execution policy | Eligible, waiting, stale, or blocked applications with reasons |
| Context | Selected work, explicit evidence, definition and policy | Bounded input tree and complete selection manifest |
| Validation | Candidate, output contract, recorded checks | Contract result and evidence references |
| Review | Candidate, base, validation and decisions | Differences, unresolved objections, acceptance state |
| Work summary | Application, attempts and accepted result | Compact record for lists and boards |
| Discussion | Selected work and its referenced events | Human-readable conversation projection |

These are proposed reusable transformations. Their outputs must retain the
canonical subject and input references needed to explain where a value came
from. Generated row position is a presentation identity, not a domain identity.

### Alternatives and higher order work

A branch is a pinned base plus a set of contributions and a candidate
projection. It does not require copying the full conversation or namespace.
A review projection can consume that candidate; a definition can itself be
the base of another proposal.

Represent composition recipes as typed records referencing published
transformations. Start with explicit application, selection, collection,
composition, and join operations. Do not introduce another general language
or allow generated code to execute by being attached to a page.

An accepted graph becomes reusable by identifying its parameters, pinning
its operation definitions, retaining its acceptance fixtures, and publishing
a definition revision. Historical secrets, incidental conversation, and
worker-local paths are excluded from that reusable interface.

The active derivation and execution-dependency slices must remain acyclic;
discussion and ordinary reference graphs may contain cycles. Feedback creates
a successor application generation or attempt. The current traversal limit
can reject large acyclic graphs as well as cycles; expose a specific diagnostic
and partition large plans instead of silently raising the limit.

### Historical interpretation

Ordinary case-based `/h` over `/o` follows the constructor's source timeline;
there is no independent journal of overlay outputs. Epoch-based historical
resolution uses a different path and must not be treated as arbitrary
derived-view-at-epoch support.

A cell's defining record case does not identify every possible result of
its live dependencies. A reproducible execution therefore needs pinned
dependency closure or an immutable captured input value with its selection
manifest. Cache entries are never execution evidence.

## Input capture and reproducibility

The document proof uses bounded atomic input captures and read-set checks from
this contract. Provider request serialization, budget reservation and adaptive
effect observations become required when Shrine owns execution. An external
MCP contribution records its supplied manifest and submitted output without
pretending to be a managed, replayable model effect.

Capture an attempt's initial inputs in one admitted namespace operation:

1. Validate the application generation and exact definition revision.
2. Resolve required input roles and acceptance dependencies.
3. Capture all source references, care levels, incarnations where relevant,
   and case identities from one committed namespace snapshot.
4. Resolve derived inputs through a bounded dependency closure. Pin all
   relevant inputs or retain the selected output as an immutable artifact.
5. Assemble the initial worker-visible context and logical request, including
   explicit selection policy, provider/model configuration and tool schemas.
   Keep this transition pure and bounded; perform no provider or filesystem I/O.
6. Persist the manifest, its digest, budget reservation, and queued attempt
   atomically. Dispatch only after durable acknowledgment.

The initial manifest records procedure and transformation revisions, primary
and secondary inputs, output and acceptance contracts, model settings,
context selection rules, and effect requirements.

An adaptive attempt also has an append-only sequence of observations and
effects. Every model effect captures its exact serialized input, configuration,
tool schema versions, and observation cutoff before dispatch. A lazy read must
use the initial snapshot or explicitly capture a new observation snapshot.
Required external file or tool data becomes a recorded observation before a
model consumes it. Later observations cannot rewrite earlier requests.

Provider-specific encoding may occur outside the pure reducer, but its exact
payload must enter a validated, durable effect intent before transmission.
Model/provider aliases may change externally; retain provider request IDs and
reported model version when available. Recorded outputs, rather than resampling
the model, provide replay.

The context collector follows explicit references only. It pages selected
inputs within one captured snapshot, detects missing or culled records,
and refuses required input beyond budget. Optional evidence may be summarized
or omitted only under a recorded policy. Summaries used during pure capture
must be deterministic or previously recorded artifacts; a new model summary
is a separate effect. Never silently send the first page
while presenting the answer as based on the complete input.

An application may contain live desired bindings. Their change marks the
current result outdated and creates a new executable generation through a
command. Old accepted results remain valid historical decisions about their
captured inputs. Default execution policy is manual; dependency-ready work
within an admitted run may continue automatically. Automatic reruns on external
changes require an explicit policy and budget.

Only accepted changes to instructions, bindings, or execution policy advance
the specification generation. Comments and progress events do not silently
invalidate a run. Record any steering contribution adopted by a new generation.

## Commands and admission

Implement one pure transition library and one authority-aware admission
boundary. Both Grove controls and MCP operations invoke that boundary.
Raw MCP writes to coordination records must not bypass lifecycle invariants:
protect governed fields through namespace behavior and authority, or restrict
those records to command submission and runtime-owned state.

Every command contains an operation ID, receiver identity, expected generation
or revision, typed arguments, and a validated caller binding. The operation ID
deduplicates retries; a reused ID with different arguments is rejected.
`who` remains an audit label and is not an authenticated principal.

| Command family | Required result |
| --- | --- |
| Create and revise application | Validate definition and bindings; increment specification generation |
| Request execution | Admit policy and reserve bounded work; expose waiting reasons |
| Claim and renew | Atomically bind an eligible attempt to a worker and lease generation |
| Record observation or prepare effect | Append captured inputs or a bounded effect intent under the active claim and budget |
| Authorize dispatch | Atomically check cancellation, attempt state, current lease, authority and budget; record one dispatch authorization |
| Record effect outcome | Attach a validated receipt to the correct operation and attempt |
| Submit contribution | Preserve immutable output and its captured bases |
| Validate and accept | Check contracts, generation, relevant source/read-set and target revisions; commit decision and changes together |
| Reject or request revision | Preserve evidence and explicit reasons; leave previous accepted result intact |
| Cancel | Stop new scheduling and request interruption of outstanding effects |
| Retry or supersede | Create a new attempt or application generation under an explicit recovery policy |
| Reconcile effect | Record evidence resolving an unknown outcome before permitting an unsafe retry |
| Publish definition revision | Accept a reviewed procedure change and retain prior revisions |

Use existing event-loop admission for read-check-write atomicity. Do not
perform a client-side check followed by an unrelated write. Acceptance that
touches several records commits its state changes, decision, and command
receipt in one atomic admission.

Acceptance revalidates the manifest's source/read-set against the application's
input policy in that same admission. Generation checks alone are insufficient:
a source may have changed before an invalidation notification arrives. Live
desired bindings must still match the captured relevant revisions; explicitly
pinned historical inputs are checked against those pins, not the latest head.
Include transformation, schema, validator and target revisions in this check.
Reject stale proposals with inspectable differences.

Goo's current declared action returns a replacement receiver. A cooperative
transition may require several record writes. Add a narrow shared command
adapter rather than broadening every view into an arbitrary write capability.
Its publication, receiver, argument, revision, lifetime, and authority checks
must apply equally to UI and MCP invocation.

## Scheduler and worker lifecycle

This section implements the managed-runtime milestone after the document loop
proof. Dependency-aware cells and proposal validation do not require a worker
scheduler. Explicit manual requests are sufficient for the first demonstration.

The scheduler owns eligibility, claims, budgets, dependency wakeups, and
recovery. It is a small deterministic coordinator; workers own the reasoning
inside admitted attempts. Agent-planned subtasks use ordinary create/link
commands and inherit limits from their parent run.
Reject creation of an owned child after its owner's cancellation commits.

Use a bounded ready index and timer queue over native crew/hive dependency
notifications. Any extra dependency metadata is a projection of those bindings,
not another subscription engine. Feed indexes from admitted changes, with
rebuild support from authoritative records. Indexes
must be reproducible and must not become a second store of lifecycle truth.
Stream notifications are hints; journal cursors provide catch-up after loss.
Worker restart must recover pending work as well as its event cursor.

Start with two concurrent model workers and one coordinator. Synthesis runs
when its required contributions are accepted. Make concurrency configurable,
but enforce a run-wide ceiling, depth ceiling, token/cost budget, deadline,
and maximum admitted applications. Reserve child budgets before dispatch so
concurrent children cannot each spend the parent's full remainder.
Reserve within that allocation before each billable dispatch and settle against
reported usage. Keep a conservative reservation or charge for unknown outcomes
until reconciled; retrying an unknown model call needs an additional reservation.
Lease expiry does not refund an in-flight request or authorize a
duplicate effect. Admit at most one mutating effect per canonical target until
its outcome is known; independent targets may proceed concurrently.

Attempt states are `queued`, `running`, `waiting`, `succeeded`, `failed`,
`cancel_requested`, `cancelled`, and `interrupted_unknown`. Waiting records
name the dependency, human input, or effect receipt that can unblock them.
Application readiness is derived; accepted-result state remains explicit.
`succeeded` means the attempt produced a candidate. It does not mean that the
application accepted it or that dependent applications may consume it.

A lease is a claim with an expiry and a monotonically increasing generation.
Each worker submission carries that generation. An expired worker cannot
accept work, renew a replaced claim, or overwrite a newer attempt. A late
external receipt can still be retained against its original effect for
reconciliation without making its contribution current.

After cancellation commits, no new dispatch authorization may be admitted.
A dispatch authorized earlier can still reach the provider; cancellation does
not undo it. Mark an attempt cancelled only when outstanding work is known to be
stopped or safely reconciled; otherwise retain an explicit unknown outcome.
Propagate cancellation through ownership edges, without cancelling a shared
dependency merely because one consumer stopped.

## Effect execution and durable recovery

Use a registered host foot with a narrow namespace endpoint. The first adapter
supports model requests and returns normalized response artifacts, usage,
request IDs, errors, and completion state. Keep provider credentials in the
host credential boundary; expose opaque capability references in the work
graph.

Reuse supervisor registration and endpoint capability transfer; add worker
policy records and restart enrollment without a parallel actor registry.
Restoring namespace records does not restore process capabilities. Closing a
local handle is not worker cancellation; cancellation uses the recorded fencing
and cooperative interruption protocol.

The first managed agent loop supports a bounded set of substrate operations:
read selected records, propose subtasks, submit contributions, request
clarification, and request authorized effects. Arbitrary shell execution and
unrestricted MCP discovery are not required for managed execution.
Additional tool adapters must declare schemas, authority, timeout, recovery
policy, and result limits.

The host executes only durably admitted dispatches. Preparing an intent does
not authorize transmission: dispatch admission checks current claim generation,
cancellation, capability binding and budget together. This fences a replaced
worker before external I/O, as well as fencing its later submissions.

Persist the effect intent before dispatch and the outcome before marking its
attempt successful. Distinguish:

| Recovery class | Behavior after interruption |
| --- | --- |
| Pure local derivation | Recompute from pinned inputs |
| Recorded model response | Reuse the stored response |
| Model call with unknown outcome | Record unknown; retry only within explicit cost policy as a new execution |
| External action with idempotency support | Reconcile or retry with the same logical operation key |
| External action without idempotency support | Require reconciliation or an explicit retry decision |

A new attempt does not automatically mean a new external logical operation.
Carry the same operation identity when reconciling or retrying the same
intended effect; allocate a new one only for a deliberately new action.
Store separate dispatch records beneath the logical effect so retries retain
their attempt and lease provenance. Reusing an operation key with a different
request digest is rejected. An idempotency-capable provider receives the same
logical key on safe retries; adapters without that guarantee preserve the
unknown outcome and require the stated reconciliation or retry policy.

Durability belongs at the sovereign boundary. Persist ordered admitted
transitions and the reachable values needed to restore them, plus periodic
checkpoints. One supervisor admission can settle a cascade containing several
journal entries. Persist that complete candidate as a committed batch, with
an atomic commit marker or equivalent storage transaction; recovery exposes
all of the admission or none of it.

Use `helm/supervisor/access[s]` as the integration seam for durable state and
admission. The current loop notifies registered feet after `handle` returns and
before the write acknowledgement. The durable admission wrapper must therefore
commit the complete candidate before returning it to that loop; persisting only
before acknowledgement is too late. Preserve the previous state and suppress
notifications if durable commit fails.

Restore namespace state, case/history identities, receipt
deduplication, and attempt manifests before registering new host capabilities.
Process handles and credentials are re-established after recovery.

Before implementing storage, verify the runtime's supported serialization of
PLAN values, pins, compiled declarations, and referenced artifacts. A JSON
export of task rows is insufficient if it loses function versions or reference
identities. Record the storage format version and migration strategy.

The durable acknowledgment must follow the storage commit. Truncated or corrupt
journal tails must fail safely; recovery must never report an unrecorded
effect completed. Replaying committed state must not replay external I/O.
Do not enable external side effects in a release advertised as recoverable
until crash tests prove this ordering.

## Nenex content ownership

Keep content, cooperative metadata, and execution artifacts separately owned.
Nenex's page root currently mixes Semidoc content with a small set of
application fields. `expand` reconstructs that root; source regeneration
filters only known application slots. Adding arbitrary work fields there can
erase them or render them as source attributes.

Keep the current page record and numbered Semidoc children. The existing
`semidoc/kid_nodes` traversal ignores named children, and `expand` only creates
or culls paths produced by the numbered source expansion. Named direct children
`inputs`, `evidence`, `logic`, `cells`, `work`, `decisions` and `bindings` can
therefore hold ordinary namespace material owned by their respective operations.
Numeric descendants inside those named subtrees remain outside Semidoc too.

Do not attach harness state to numbered prose nodes: removing such a node can
cull its whole subtree. Source edits, direct record edits and removal/reordering
of prose must preserve named work subtrees and exclude them from regenerated
source. Existing document URLs and historical paths stay unchanged; a `content`
relocation and compatibility migration are unnecessary for this boundary.

Extract the deletion-aware document transition from `doc_talk` and share it
with Grove command admission. It receives the current document and previous
source, validates the edit, produces the new content, and removes stale
expanded nodes in the same transaction.

Do not replace this with a direct Grove update of `src`: Goo currently commits
`writ/make`, while Nenex initialization expands with no prior source. The
shared transition must explicitly prove deletion and named-subtree preservation.
Keep source and expanded records as synchronized representations of one
document, with one operation contract.

Use stable document identity and revision. If sections need durable annotation
anchors, add stable node identity and incarnation mapping before attaching
accepted contributions to them. Numeric position alone cannot identify a
section after insertion or reordering.

## Nenex block integration

Use Nenex's assumed block surface for inputs, named logic and results. Add the
smallest Grove presentation and command bindings required to operate them in
place. Reuse existing navigation and selection behavior. Dedicated library,
inspector, review and history panes are optional presentations, not MVP gates.

Publish role-specific views for summary, content, input bindings, candidate
differences, validation evidence, attempt progress, and effect outcomes.
Reuse these views for definition revisions and ordinary work. A procedure
revision is reviewed through the same contribution interface.

Derived collections remain read-only. A command from a projection identifies
its canonical target through an admitted binding, with expected revision and
captured inputs. Goo's existing `tack` plus `sys/from` mapping covers only
specific identity-preserving projections. Joined, summarized, or synthesized
rows require an explicit target adapter; never infer write authority from a
derived address.

Definition and input pickers use trusted selection captures for reference-valued
bindings. The browser cannot gain authority by submitting an arbitrary path
string. U1 must expose creating or selecting a declaration, binding its inputs
and invoking it inline, with concise result and failure inspection.

Introduce a shared command/operation component for progress, retry, draft
retention, and stale-input rejection. Put reusable behavior in the Goo host
and Mash components. Avoid new Nenex-specific browser state machines.

Coordinate source editing with the
[document workspace plan](goo-document-workspace-plan.md) and
[Unicode infrastructure plan](goo-unicode-text-infrastructure.md).
Use the same preparation, input capture, revision, and draft protocols.
Keep the full editor on that infrastructure track; do not build a second
document engine or weaken its Unicode requirements to accelerate this plan.

Shared-editor alignment may later replace the existing source editor and
remaining custom composition. Keep it on its own track. This plan's required
surface is the inline contribution/evaluation loop and the host behavior needed
to keep that loop correct; it does not require redesigning the rest of Nenex.

### Inline declarations and bindings in Nenex

Present a namespace name inside the document flow through a declared view.
Nenex stores the occurrence and surrounding prose. Inputs, logic, drafts and
results remain named values and bindings; execution records are linked when
needed. No additional executable-object identity sits between the document
reference and namespace resolution. The same name may appear in several places
with different views. Dependencies follow explicit bindings, independently of
the order of paragraphs.

The default inline view exposes useful inputs and the accepted result. Provide
declared views for Logic, Evidence and History, plus applicable commands such as
Run, Review or Apply elsewhere. Logic can be edited in place when source
authoring is enabled, but edits target one canonical definition draft. Do not
keep independent copies of source in a document literal and a program record.
Portable export can bundle referenced source and pinned dependencies explicitly.

Semidoc already has reference transclusion through `/doc/embed`; its parser
supports single-valued path and text attributes. Add a presentation binding to
reference nodes rather than a new document language. Illustrative proposed
vocabulary, not currently implemented:

```text
;@ /doc/present ;/0x11/gov/cooperate/inline
;@ /doc/occurrence comparison-1
;/0x11/user/docs/workspace-choice/cells/comparison
```

The first attribute selects a declared view slot, the second identifies the
document occurrence, and the reference identifies the canonical subject.
Validate occurrence identity within the document and retain an incarnation for
action captures. Reordering preserves the occurrence; duplication allocates
another occurrence; deletion removes presentation without cancelling the run
or deleting the shared artifact. Numeric Semidoc positions and the current
target-derived `embed_id` cannot supply this identity.

Reuse the existing `/goo-presentation` subject/slot resolution and shared Goo
host, with a checked inline embedding adapter. Current `present`/`pane`
composition does not allow an arbitrary foreign receiver, and legacy
`/doc/embed` mounts `/o` HTML fragments with a renderer case fixed to one.
Neither is already the complete inline Grove binding. Capture the artifact's
receiver, view publication, revisions and authority for each command.

Retain inline host occurrences across document updates. The current Nenex
reader polls a whole-document fragment whose replacement uses `innerHTML`;
placing an editor inside it would lose drafts, focus and composition. Extend
shared Goo frame retention and departure guards before making the inline
surface interactive. Do not add another Nenex-specific editor lifecycle.

Current-page bindings may follow live artifact state. Historical pages must
use the artifact and presentation captures recorded with that document revision,
rendered read-only. Show an unavailable historical binding when no capture
exists; do not silently display a live actionable widget inside old prose.
The current history scrubber rewrites only fragment URLs and does not supply
this guarantee for Grove presentations.

Deliver in two stages:

1. **Document loop proof, extended in the MVP:** inline presentations bind vetted
   published procedures, typed parameters and upstream references, and expose
   their results and commands.
   Logic inspection is available; editing a composition uses declared operations.
2. **Source authoring extension:** the shared Unicode editor edits the canonical
   Grove/Foil draft inline. Reuse registered draft, preview and publication
   machinery, with validated procedure exports and bounded compilation/evaluation.
   This follows the custom-code execution boundary; it is not implied by adding
   a code textarea or by the legacy `/chore/eval` example form.

For source authoring, Run may coordinate compile, validate, publish and invoke
as one user interaction with explicit intermediate states. Keep the last usable
publication while a draft is invalid. Current `grove_draft` recompiles at public
publication after preview, so source revision alone does not identify the final
artifact. Capture compiler/import inputs and validate the final public definition,
or implement exact candidate promotion. Bind the attempt to that final definition
moment. A type signature or successful compilation does not confer effect
authority or bound arbitrary evaluation.

The inline acceptance fixture displays one calculation twice: parameter edits
update both results, moving prose preserves a draft, removing one occurrence
preserves the calculation, stale controls reject, and history shows captured
read-only results. The artifact also works outside Nenex through the same
published contract.

## Performance architecture

Optimize the deterministic control path independently from model latency.
Every performance report separates cold publication, warm evaluation,
durable admission, provider latency, and browser presentation.

1. Use the narrowest correct care for each dependency. Materialize compact
   scheduling metadata outside large content trees.
2. Maintain reverse dependency and ready indexes from admitted changes.
   Process bounded batches and yield between them.
3. Cache expensive shared projections only after profiling. Keep cache records
   outside their input subtrees and allow complete rebuild without losing work.
4. Key computation by definition revision, full input identities, care,
   parameters, and relevant contract versions. An enclosing cell case alone
   is insufficient for a live dependency.
5. Capture initial context once per attempt. Reuse pinned artifacts and append
   bounded observations; record each assembled model request without repeatedly
   traversing all ancestor transcripts.
6. Reference compiled behavior and immutable artifacts rather than embedding
   large closure values or copying evidence into each child.
7. Bound graph expansion, result bytes, context bytes, tool-call count, queue
   depth, retries, and retained diagnostics. Fail with a useful limit reason.
8. Separate ownership subscriptions from content subscriptions. Batch small
   telemetry updates so progress does not invalidate document layout or
   recompute every work view.
9. Limit eager cascades. Expensive maintenance and further planning become
   explicit queued work rather than unbounded synchronous reactions.
10. Measure the existing subscriber machinery before promising affected-graph
    complexity. Current reaction rounds rebuild subscriber indexes; a change
    may cost more than its apparent dependency neighborhood.
11. Keep registered worker inboxes small. Native notification currently compares
    each registered foot's full `.y` binding after state advances; it does not
    already provide notification work proportional only to affected workers.

Initial policy defaults are two model workers, fan-out four per application,
depth four, and at most 128 admitted applications per run. Cap assembled
worker context at 64 KiB of UTF-8 plus an independently enforced provider
token budget. These are adjustable product limits, not claims about maximum
kernel capacity. Required input overflow blocks execution with a diagnostic.
Initially bound one capture to 16 derivation levels and 32 distinct reachable
cell dependencies. Test shared diamond dependencies and count both closure
traversal and norm validation. These product limits sit below the current
conservative traversal guard and can change after measurement.

Output size alone does not bound evaluation. For the MVP, admit a vetted set
of projection definitions at fixed revisions with bounded input shapes. Limit
one capture to 500 distinct input records, 1 MiB of loaded data, and 128 traversed
dependency edges; stop collection before exceeding those limits. Memoize shared
pure subgraphs within the request. Charge repeated stages and norm checks to
the measured evaluation work, even when their output is tiny.

Do not evaluate arbitrary published transformation code inside coordinator
admission. Publication and type checks do not establish a runtime bound. Adding
that capability requires an interruptible evaluation boundary with resource
limits; checking elapsed time after a blocking call is insufficient. Until
then, reject unsupported definitions with a diagnostic and compose reusable
procedures from the vetted operation vocabulary.

### Performance acceptance

The checked-in [MCP performance suite](../../extras/mounts/mcp/tests/perf.py)
already specifies a warm record-read p99 ceiling of 20 ms and a four-step
cell-chain p99 ceiling of 60 ms, plus zero-event reads and writes that mint at
most one event.
These are existing test thresholds, not measured results from this plan.
Preserve them under the suite's defined setup.

Add the following proposed release targets on one documented development
machine, one world, warm compilation, and a deterministic fake worker:

| Operation | Initial target | Measurement |
| --- | --- | --- |
| Work summary or ready page | p95 at most 50 ms | 100 returned items from the performance fixture |
| Claim, renewal, contribution or acceptance | p95 at most 100 ms | Includes durable local acknowledgment; bounded payload |
| Committed change to eligible local dispatch | p95 at most 100 ms | Excludes intentionally scheduled delay and provider time |
| Changed work to updated visible summary | p95 at most 200 ms | Local host and browser; ordinary summary view |
| Freeze bounded context | p95 at most 250 ms | Up to 64 KiB output and documented dependency limit |
| Restart from checkpoint and replay | Usable within 5 seconds | At most 10,000 replay entries; zero repeated completed effects |
| Unrelated write under subscribed load | At most 20 percent regression from the recorded control | Same fixture, subscriber count and warm runtime |

Use a fixture with 10,000 records, 1,000 applications, 340 derived views,
100 active subscriptions, and two workers. Also run a small interactive
fixture and a load staircase that independently varies dependency depth,
subscriber count, context size, and concurrent workers. Include a deliberately
expensive overlay to reveal synchronous cascade amplification.

Report p50, p95, p99, bytes read/written, events, resolver calls, recomputation
count, journal lag, queue depth, and resident memory. Record hardware and
build identifiers, warmup, sample count, and fixture seed. Establish memory
and cold-start baselines in P0; do not disguise publication time as model
latency or claim unmeasured speedups.

Bound each UI response by both item count and bytes, initially 100 items and
256 KiB, with continuation. Give every cache explicit entry and byte limits;
repeated view reads must reach a retained-memory plateau. Unchanged reads mint
no namespace events and never schedule a model or tool. An unrelated change
must not launch affected-work evaluation solely because a global event moved.

If a target fails, first narrow reads, remove redundant context assembly,
or materialize one measured bottleneck. Changes to dependency indexing or
kernel caches require existing resolver and transaction suites to remain
green. A cache hit must never bypass authority or current-generation checks.

## Implementation modules

Keep mount bags flat; logical module identities may still be hierarchical.
The proposed division is:

| Location | Responsibility |
| --- | --- |
| `extras/mounts/cooperate/types.foil` | Domain values, command/observation/outcome sums and codecs; consume Grove-generated facet converters |
| `extras/mounts/cooperate/commands.foil` | Pure validation and transition planning |
| `extras/mounts/cooperate/runtime.foil` | Foil behavior and step laws; admission, claims, budgets and scheduling over native dependency settlement |
| `extras/mounts/cooperate/context.foil` | Snapshot capture, dependency closure and manifests |
| `extras/mounts/cooperate/projections.foil` | Candidate, readiness, review and context transforms |
| `extras/mounts/cooperate/main.grove` | Roles, norms, action declarations, reusable views and installable graph templates |
| `extras/mounts/cooperate/worker.foil` | Registered host protocol and effect receipts |
| `extras/mounts/cooperate/host.py` | Initial provider adapter and process integration only |
| `extras/mounts/cooperate/tests.foil` | Transition laws and deterministic integration fixtures |
| `extras/mounts/nenex/document.foil` | Extracted document transition if shared admission requires it; no content relocation prerequisite |
| `extras/mounts/nenex/blocks.grove` | Minimal inline input, declaration, result and command presentations |
| Shared Goo runtime and host | Governed command binding and retained-operation interaction |
| Sovereign persistence module | Durable state and reachable-value restoration |

Implement reusable admission and persistence at the appropriate shared boundary.
Do not make core runtime files depend on the cooperation application. Avoid
refactoring unrelated modules while extracting the smallest required seam.

## Phases and tickets

Ticket IDs below identify implementation work and test evidence. They do not
prescribe separate user-visible issues or a new project-management store.

### P0 Document loop proof

Build one vertical slice before generalizing lifecycle machinery. Existing
tests and fixtures establish the starting baseline; all exit evidence below
is work to produce, not a claim about the current implementation.

| Ticket | Depends on | Work | Exit evidence |
| --- | --- | --- | --- |
| F0 | Existing Nenex, cells and MCP | Seed the workspace-choice subtree and deterministic listings; define candidate, criteria and result contracts | Explicit collection roots, bounded fixtures, canonical identity and source baseline recorded |
| F1 | F0 | Qualify Nenex's existing numeric-content/named-work ownership boundary | Saving, deleting and reordering prose preserves named inputs, cells, proposals and decisions; existing URLs stay unchanged |
| F2 | F0 | Add bounded atomic capture, immutable contribution submission, guarded input revision and atomic acceptance through shared admission | UI/MCP commands use one declaration; raw lifecycle writes refused; stale read-sets, duplicate operation IDs and partial commits tested |
| F3 | F0 | Publish the typed comparison transform and parameterized cell recipe | Cedar, no-match and Harbor cases pass; missing facts diagnose; secondary criteria dependencies and stable identities verified |
| F4 | F1, F2, F3 | Bind inline criteria, comparison, proposal review and decision views using retained Grove/Goo controls | Human and two external MCP sessions complete the story; late stale acceptance fails; prose refresh preserves drafts; historical views are read-only |
| F5 | F4 | Bind an accepted result into the budget document and apply the recipe to a second dataset | Typed headroom is 50; independent inputs share pinned logic; removing an occurrence preserves its subject; repeatable demo instructions |

F5 is the **first end-to-end milestone**. Use scripted client submissions for
deterministic failure tests and real external MCP sessions to demonstrate the
interaction. No model-provider adapter, scheduler, durable restore or new editor
is required. These tickets establish the narrow shared seams that later D and
U tickets extend; do not build duplicate command or presentation paths.

### P1 Runtime contracts and qualification

| Ticket | Work | Exit evidence |
| --- | --- | --- |
| C0 | Extend F0/F2 contracts with managed application, attempt and effect lifecycles | Concrete fixtures and native primitive mapping; no general taxonomy or duplicated workflow engine |
| C1 | Record performance and source baselines | Existing MCP/cell tests, timing report and reproducible fixture |
| C2 | Prove overlay composition and bounded evaluation | Nested `/o`, typed `/x`, pinned context, input-limit refusal and unsupported-code rejection tests |
| C3 | Qualify native persistence mechanism | Restore typed continuation state, exact compiled behavior, reachable pins, history identities and receipts |

C0 and C2 establish the managed-worker interface after the document proof.
C3 is the largest durable-release feasibility risk; qualify it before building
the real provider adapter. It can be investigated alongside the proof without
blocking that proof. If native restore cannot preserve required identities,
stop the durable-release track and
resolve that substrate issue before promising recovery.

### P2 Managed cooperation contracts

| Ticket | Depends on | Work | Exit evidence |
| --- | --- | --- | --- |
| D0 | C0 | Implement typed Foil command/step laws, native behavior adapters and immutable manifests | Legal/illegal transitions, facet preservation and deterministic step replay |
| D1 | C0, F1 | Extend the extracted document transition to managed document proposals | Source/record round trips, deletion and facet-preservation laws |
| D2 | C2 | Implement candidate, validation, readiness and context projections | Direct and nested composition agree; diagnostics survive |
| D3 | D0, C2, F2 | Extend atomic context capture with managed manifests and budget reservation | Concurrent edit cannot produce a mixed manifest |
| D4 | D0, D1, D2, F2 | Extend contribution submission and acceptance to managed attempts and document proposals | Source/read-set races, stale bases, conflicting proposals, duplicate commands and atomic content/decision/receipt tested |

At this phase, fake effects may be injected as recorded inputs. No real
provider access is needed.

### P3 Scheduler and recovery

| Ticket | Depends on | Work | Exit evidence |
| --- | --- | --- | --- |
| R0 | D0, D3 | Build bounded ready/lease indexes and claims on native crew/hive notifications | One owner per generation; indexes rebuild; no duplicate subscription engine |
| R1 | R0, D4 | Add typed effect intent/dispatch/receipt protocol, fake worker, cancellation, retries and joins | Runtime proof includes claim/cancel dispatch races and unknown outcomes |
| R2 | C3, D0 | Add durable acknowledgment and recovery | Crash matrix passes without losing admitted work |
| R3 | R1, R2 | Add one real model adapter behind durable effect admission | Captured request, response, usage and errors survive restart; capability checks precede dispatch |
| R4 | R2, R3 | Qualify bounded substrate tools and effect recovery | Duplicate and unknown-outcome tests; capabilities remain host-bound; no unrestricted tool discovery |

R1 is the managed runtime proof, extending the already working F5 document
loop. R2 and the extended UI work can proceed independently once contracts are
stable. The durable cooperative MVP requires R2; F5 does not satisfy recovery.

### P4 Extend Nenex and Grove integration

| Ticket | Depends on | Work | Exit evidence |
| --- | --- | --- | --- |
| U0 | C0, D0, F2 | Extend shared command admission and action/codec reflection to all managed commands | Identical declarations, commands, receipts and refusal reasons; no independently maintained tool schema |
| U5 | D1, D2, U0, F4 | Generalize stable inline occurrences and retained presentations across work roles | Duplicate placements, reorder, drafts, stale controls and historical read-only bindings pass |
| U1 | D1, D2, U0, U5, F5 | Extend input and logic bindings to reviewed procedure revisions | A user can apply logic inline and feed its result into another block; no new workspace required |
| U2 | D4, R1, U1 | Add inline contribution acceptance, progress, retained drafts and concise inspection | Browser tests for stale views, retries, cancellation, recovery and control provenance |
| U3 | Shared Unicode text infrastructure, D1, U0 | Optional: align source editing with the shared text component | Multiline/IME tests and removal of custom editor lifecycle |
| U4 | U1, U2, U3 | Optional: align remaining Nenex composition and qualify compatibility routes | Old links and history work; no unrelated metadata enters Semidoc; relocation only if required |

U5, U1 and U2 provide the cooperative MVP surface. Keep the existing source
editor reachable. U3 and U4 are optional alignment work, outside the cooperative
MVP critical path. Do not create another editor or workspace framework.
Arbitrary inline source authoring is a later extension after its compiler,
evaluation and shared editing boundaries are qualified.

### P5 Procedure improvement and durable qualification

| Ticket | Depends on | Work | Exit evidence |
| --- | --- | --- | --- |
| Q0 | D4, R3, U2, F5 | Improve and publish a reviewed definition referencing pinned Foil behavior and a parameterized Grove graph template | Successor review uses the same contribution protocol; two installations share pinned code, retain independent state and pass native-composition acceptance |
| Q1 | R4, U2, Q0 | Run correctness, crash and performance qualification | Reproducible reports and all required gates pass |
| Q2 | Q1 | Package example workflow and operational instructions | Clean boot, restart, export and restore walkthrough |

The first delivery is F0 → F1/F2/F3 → F4 → F5: document ownership,
calculation and shared review converge in a visible, reusable document.
The subsequent runtime lane is C0/C2 → D0/D3 → R0/R1. Document and projection work
D1/D2/D4 joins at R1. Persistence C3/R2 runs alongside it; both lanes must pass
before R3/R4. The UI lane U0/U5/U1/U2 joins runtime and reuse Q0 at qualification
Q1. These dependencies define the cooperative MVP; C1 supplies its performance
baseline and Q2 supplies release instructions. Full editor completion U3/U4
follows its shared infrastructure dependencies without delaying either proof.

Use one integration owner for shared command and persistence boundaries.
Other implementation lanes can own projections, Nenex ownership tests, worker
adapter, and evaluation fixtures. Merge small contract-backed increments;
do not split mutually dependent schema changes across incompatible branches.

## Verification matrix

F0–F5 require the document-loop acceptance checks below, including the relevant
document, projection, capture, admission, acceptance, inline and reuse laws.
The full matrix additionally qualifies managed execution and the durable MVP;
its crash, lease and effect requirements are not claims made by the first proof.

| Area | Required properties |
| --- | --- |
| Roles | Updating one facet preserves all unrelated fields; required fields and types remain valid |
| Native reuse | Shared published code, explicit template rebasing, preserved source pins, same action contracts through UI/MCP; fresh links never mutate manifests |
| Functional outputs | Delivered artifact accepts a second input and composes with another declared operation without prose reconstruction; behavior survives producer completion and restart |
| Inline bindings | Occurrence and namespace identity remain separate; source edits/reorder preserve work and drafts; duplicate presentations coexist; historical bindings cannot act on live state |
| Documents | Source and records converge; deleted nodes disappear; metadata survives; failed edits commit nothing |
| Projections | Reads produce no events; nested composition agrees with direct evaluation; excessive input and unsupported code reject before blocking admission; caches can be discarded |
| Capture | Primary/secondary/code revisions are pinned; pagination is complete; adaptive observations have explicit snapshots; source changes do not alter recorded request bytes |
| Admission | Same operation ID is idempotent; changed payload is refused; UI and MCP cannot bypass checks |
| Ownership | Duplicate claims fail; stale lease generations cannot complete work; shared dependencies survive one consumer's cancellation |
| Acceptance | Contract failure retains evidence; stale bases and changed live input read-sets reject even before invalidation; multi-record acceptance commits atomically |
| Effects | Durable intent and current dispatch authorization precede I/O; logical keys cannot change payload; receipts deduplicate; unknown outcomes retain budget; replay never repeats completed I/O |
| Recovery | Process crash restores identities, attempts and receipts; whole cascades commit or disappear; indexes rebuild; missing worker state does not lose queued work |
| UI | Shared selection, canonical targets, retained drafts, busy/error states, keyboard access and stale publication handling |
| Performance | Existing MCP thresholds plus the proposed control-path budgets and load staircase |

The crash matrix covers: before intent commit; after commit before dispatch;
after dispatch before response; after response before receipt commit; after
receipt commit before attempt completion; and after acceptance commit before
the client receives acknowledgment. Include cancellation and lease replacement
at each relevant boundary. Inject crashes between entries of one admitted
reaction cascade and around its durable batch marker; no recovered state may
contain only part of that admission.
Also crash between durable commit, worker notification and acknowledgement.
No worker may observe an intent from an uncommitted candidate.

Explicitly race cancellation against child creation and dispatch admission,
and lease replacement against dispatch authorization. Delay dependency-index
processing after an evidence edit, then attempt acceptance: the direct read-set
check must still reject stale input. Oversized inputs and expensive unsupported
transformations must fail before blocking or partially committing admission.

Use deterministic fake workers and replay fixtures for semantic tests.
Real-provider checks validate integration and usability; they do not make
correctness depend on model prose. Compare the same task with one worker and
with cooperation, recording accepted-result quality, cost, elapsed time,
duplicate work, stale proposals, and recovery success.

## End to end acceptance scenarios

### Gate A: document loop proof

Run the workspace-choice story in one sovereign lifetime. Record the exact
fixture, command receipts and assertions so another developer can repeat it.

1. Nenex and MCP resolve the same criteria, candidate and cell names. A change
   admitted through either interface appears in the other's next read; there
   is no second authoritative agent-side document.
2. An MCP contribution carries a bounded atomic capture and source references.
   Acceptance populates canonical facts and preserves its immutable proposal.
   Calculation and review reads create no model requests or namespace writes.
3. With the initial fixture, comparison returns Cedar at 360. Capture a fit
   proposal, lower the budget to 350, and observe a typed no-match result.
   Attempt to accept the old proposal before delivering any invalidation
   notification: the direct read-set check still refuses it.
4. The cost extraction remains valid because its declared inputs did not change.
   The fit proposal is retained as stale evidence. An explicit new assessment
   may suggest a tradeoff; it cannot silently change the human's criteria.
5. Relax quiet only through an explicit human revision. The live result becomes
   Harbor at 300. Accept a proposal captured against that state. Decision,
   accepted-result reference, canonical changes and receipt commit atomically.
   Repeating the operation ID returns the original result; changing its payload
   is refused. Raw writes cannot forge an accepted lifecycle state.
6. The budget document follows the accepted decision by a pinned binding and
   calculates 350 minus 300 as 50. Changing the live comparison later preserves
   that decision and budget value until an explicit binding update. Show current
   validity separately from historical acceptance.
7. Bind the same pinned recipe to a second fixture containing Annex (rent 250,
   fees 25, commute 10, quiet true) with budget 300, commute limit 30 and quiet
   required. It returns Annex at 275. The first comparison remains independent. No model call or
   prose reconstruction is required for this reuse.
8. Edit, reorder and delete prose; remove one of two occurrences of the same
   result. Inputs, cells, work and decisions survive. Retained controls preserve
   drafts; old document revisions expose captured read-only bindings or a clear
   unavailable state. A legacy document URL still resolves.
9. Reject malformed facts and oversized captures with diagnostics and no partial
   state changes. Exercise concurrent UI/MCP commands and an interrupted client
   response. Retrying within the running sovereign cannot duplicate acceptance.

Passing these checks and the real external-client walkthrough completes F5.
A CLI-only fixture is useful development evidence but does not satisfy the
Nenex user story. A screenshot of a report does not satisfy computation, stale
refusal or reuse. Restart recovery is explicitly outside this gate.

### Gate B: managed and durable cooperation

Extend Gate A with two Shrine-managed investigations and a synthesis. The
scheduler supplies captured manifests, joins accepted dependencies, enforces
budgets and cancellation, and preserves unaffected accepted work after edits.
Qualify the fake-worker runtime before introducing a real provider adapter.

Crash after dispatch and recover according to the effect's declared policy.
Retain a late worker's output without allowing it to overwrite a newer generation.
Restart the sovereign: accepted decisions, frozen inputs, history, pending work
and usable comparison behavior survive; completed effects are not repeated.
Review a proposed improvement to the reusable definition through the same
contribution protocol, publish its successor, and apply it to fresh inputs while
existing pinned applications retain their original behavior.

Passing this extension, the full verification matrix and performance gates
defines the durable cooperative MVP. Broader editor alignment remains separate.

## Operational limits and deferred work

Expose pending work, active claims, budget use, stale dependencies, unknown
effects, and durable journal health through typed inspection views. Supply
bounded logs and operation IDs that connect browser actions to decisions and
effects. Preserve the distinction between user correction, worker failure,
invalid proposal, provider failure, and infrastructure failure.

Retain pinned evidence needed by accepted decisions and active attempts.
Garbage collection must trace these references before deleting artifacts.
Keep immutable checkpoints and an export/restore path before introducing
retention policies. Treat externally referenced files as artifacts with
content identity; a filesystem path alone does not preserve their bytes.

Defer general distributed coordination, autonomous permission expansion,
arbitrary bidirectional overlays, unrestricted recursive spawning, global
semantic memory, a skill marketplace, and full graphical workflow authoring.
None is necessary to prove reusable, inspectable cooperation.

## Design references

- [Native behavior contracts](../../src/foil/sys/hand.foil),
  [Grove tree publication](../../src/foil/grove_backend.foil), and
  [template installation](../../src/foil/grove_install.foil) ground the native
  implementation contract.
- [Semidoc reference rendering](../../src/foil/semidoc.foil),
  [Goo subject presentation](../../extras/mounts/explorer/goo_browser.foil), and
  [registered draft compilation](../../src/foil/grove_draft.foil) ground the
  inline binding proposal; legacy fragments still require lifecycle adaptation.
- [PLAN effects model](effects.md) and
  [supervisor state abstraction](../../src/foil/helm.foil) ground the pure
  execution and host persistence boundary.
- [MCP operating contract](../../extras/mounts/mcp/skills/shrine-mcp/knobs.md)
  provides bounded references, history and cell conventions.
- [Chat reference](../../extras/mounts/chat/main.foil) provides request/response
  state patterns; its live ancestry and label-based adoption require replacement
  at the execution boundary.
- [Goo reference](../../src/grove/GOO.md) and
  [Hello Grove](../../extras/mounts/hello-grove/main.grove) define current view,
  pane, selection and action composition.
- [Hermes delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)
  supports explicit worker context and output contracts.
  [Hermes Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
  distinguishes logical work from attempts and documents recovery limits.
- [Hermes procedure revision tracking](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator#audit-ledger-and-single-edit-rollback)
  motivates recorded evidence for learned definition changes.
- [LangGraph functional execution](https://docs.langchain.com/oss/python/langgraph/functional-api#determinism)
  illustrates replay using retained task results.
- [AWS effect recovery](https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/)
  distinguishes retry policy from exactly-once external execution.
- [Anthropic cooperation experience](https://www.anthropic.com/research/multi-agent-research-system)
  motivates precise delegation contracts and evaluation of coordination cost.
- [Agent scaling study version 3](https://arxiv.org/abs/2512.08296v3)
  supports measuring task-dependent cooperation against a single-worker baseline.

External references inform contracts and tests. Shrine remains the execution
and state substrate; these systems are not runtime dependencies.
