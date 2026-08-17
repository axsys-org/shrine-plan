# Nenex-Authored Foundry Roadmap

- **Status:** Proposed; implementation in progress
- **Primary mode:** Foundations and primitive governance
- **Implementation home:** `shrine-plan`
- **Conceptual authority:** the Shrine five-concept product schema: Node, Space,
Flow, Plate, and Block

## 1. Outcome

Nenex becomes the authoring environment for one durable Foundry corpus.
Semidoc source and normalized namespace records remain synchronized by the
existing Nenex machinery. Foundry interprets the admitted records directly;
there is no second Foundry source corpus, import daemon, or permanent compiler
bridge between two authorities.

The corpus describes:

- semantic values and contextual layers;
- reusable Block and Slot contracts;
- Plate and Scene compositions;
- Zoo recipes, explicit fallbacks, and catalogs;
- renderer and provider pronunciations assembled from Layers, Recipes, Catalogs,
  and `felt` targets rather than a fifth authored object family;
- deterministic runtime projection and source-code generation targets; and
- provenance sufficient to reproduce every generated or projected result.

The same resolved semantic graph can be delivered as a live addressed
projection DAG or pronounced into replaceable artifacts such as HTML, CSS,
TypeScript, SwiftUI, SVG maps, documentation, and conformance tests.

Nenex source is authored truth. Projection packets and generated code are
replaceable materializations.

### 1.1 Current implementation checkpoint — 2026-08-15

- Normalized Nenex records can enter the Foundry corpus without a second source
  language or source-text adapter. A read-only `nenex_foundry_face` now owns the
  corpus index presentation, so the Nenex app supplies the expanded `/nenex/w`
  record tree and receives ordinary `weft/node` output without importing the
  corpus compiler vocabulary into the app unit.
- The renderer-neutral `projection_dag` now carries its ordered
  `projection_resolution_context` table, and each contextual placement carries
  its exact context reference. Begin frames carry the same table and
  progressive updates preserve it. Validation rejects duplicate context
  identities, missing parents, cycles, invalid scopes, partial placement
  context adoption, invalid root ancestry, and orphaned contexts.
- Resolution Context records carry ordered local Layer pins, resolved deltas,
  winning-layer provenance, and an all-or-nothing guarded policy/witness arm.
  This freezes the structural boundary; it does not fabricate trusted guard
  evidence for the current Chat contrast and motion values. Those values remain
  outside the strict context cutover until a trusted guard-policy admission
  path supplies exact policy and witness pins.
- Source-owned Action declarations, independently addressed
  `projection_interaction` entries, `projection_action_mount` and
  `projection_destination_mount` records, and the pure occurrence admission
  pass exist. Admission is exact-occurrence and explicit: it never infers an
  Action from role, kind, source, route, kook, form, or terminal operation.
- The typed `terminal_plan` builder consumes one completed DAG and its exact
  canonical pronunciation, retaining per-occurrence Resolution Context and
  interaction evidence. A generic Web terminal lowers closed non-interactive
  operations into `weft/node`; a sibling text terminal lowers the same plan and
  preserves Action evidence without invoking it. The Web terminal refuses
  Actions until a trusted host supplies witness-bound endpoint, method, and
  input-field mechanics.
- The generic Foundry core has bounded pinned-Wisp compiler proof for the
  interaction, Web terminal, text terminal, corpus, code-generation, Zoo,
  Lense, and Fragment cones. This is compiler evidence for those cones, not a
  complete repository suite, app compile, live HTTP route, or browser proof.
- The stage template now uses a serial cached roster fold, with equivalence,
  failure-order, and failure-continuation assertions in the Reaver test source.
  This removes parallel stage fanout, but does not solve the aggregate
  cumulative-cache size: the complete stage still exceeded its practical
  memory budget and was stopped. An artifact-native stage remains separate
  compiler work because current stage and suite APIs require the legacy cache
  rows and lore.
- The oversized Chat compiler unit is being split, without changing semantic
  identities, into projection, compatibility pronunciation, and frame/watcher
  modules. `apps/chat/main.foil` delegates through compatibility wrappers, but
  the extracted modules and slimmed app do not yet have post-split compiler or
  live-route proof. The legacy `plan_policy`/`web_any` policy remains reachable
  outside the generic terminal proof, so Phase 7 and the Chat cutover are not
  complete.
- Live Chat send is not yet an admitted Action. The current HTTP request has no
  authenticated semantic actor or explicit grant; the old `/post/chat/log`
  path is legacy behavior and MUST NOT be treated as proof of Action admission.
- No earlier phase is retroactively complete merely because Phase 6.5 core
  slices exist. Post-change app compilation, focused suites, complete repository
  gates, repeated live HTTP responses, and browser behavior remain distinct
  evidence and are still required by their named exit gates.

## 2. Product model

The Foundry does not introduce a parallel component ontology. It specializes
the five product concepts and their existing refinements.

| Product concept | Foundry responsibility |
| --- | --- |
| Node | Durable layers, templates, recipes, catalogs, pronunciation source, and application source |
| Space | Selects and constrains applicable Foundries without becoming component ancestry |
| Flow | Carries live work and resumable arrangements, including Chat and Stage Flow |
| Plate | Establishes a bounded projection, local selection, interaction region, and ceiling |
| Block | Supplies inspectable compositional structure, state roles, behavior roles, and named Slots |

Scene, Scene Route, Slot, Text, and Glyph refine these concepts:

- a Scene is a coherent Plate arrangement under a contextual render root;
- a Scene Route traverses semantic placement edges, not namespace paths or DOM
  indices;
- a Slot is a named attachment and participation contract;
- Text is an ordered Block composition rather than an opaque renderer string;
- a Glyph is a terminal pronunciation with no children or authority; and
- a Stage Flow is a Flow whose state remembers an arrangement. Its visual
  realization can be a root Scene, but Stage is not a sixth durable primitive.

The current compiler-level `stage` kind may remain temporarily as a ceiling or
realization role. Durable product state MUST use Stage Flow semantics.

## 3. Architectural invariants

### 3.1 One authored corpus

There MUST be one authored source of Foundry meaning:

```text
Nenex Semidoc source
    <-> normalized namespace records
        -> Foundry corpus interpretation
        -> resolved semantic graph
        -> addressed projection DAG
        -> runtime or source pronunciation
```

The existing `foundry_doc` implementation is a donor and executable reference.
Its useful data types, validation rules, and diagnostics should move behind a
record-oriented `foundry_corpus` interpretation. Its build-time `.sd` corpus
should disappear after the equivalent admitted Nenex pages pass the same tests.

### 3.2 Page identity is not semantic identity

A Nenex page is an editorial and revision boundary. Its page name or URL MUST
NOT silently become Foundry identity.

For example:

```text
editorial page:       /nenex/w/block-plate-header
declared identity:    /foundry/system/blocks/plate-header
page revision pin:    the admitted page moment
projection identity:  source pin-ref plus occurrence axis
```

Renaming the editorial page must not rename the declared Block. Reusing one
declared Block in several placements must not copy its definition or conflate
its occurrences.

### 3.3 Definitions and placements remain separate

A semantic definition is shared. Context belongs to an ordered placement edge.
The addressed projection graph therefore remains a tree of occurrences within a
DAG of shared definitions.

The same Plate Header Block may be defined once and placed in Chat, Life, a
Lense, and a generated documentation specimen. Each placement receives its own
occurrence axis and Scene Route.

### 3.4 Forward references compose; backlinks explain

Typed forward references determine dependencies, composition, fallbacks, and
catalog closure. Backlinks are a derived reverse index used for:

- navigation;
- impact analysis;
- invalidation planning;
- refactoring previews; and
- diagnostics such as unused or unexpectedly shared definitions.

Backlink order MUST NOT change semantic resolution. A backlink MUST NOT grant
authority or cause a definition to be included in a projection.

### 3.5 Meaning and materialization remain separate

Foundry owns realization policy. It does not own source identity, disclose
unadmitted structure, or grant actions.

- semantic roles precede HTML tags, SwiftUI types, CSS selectors, SVG paths,
  font names, and native handles;
- a pronunciation may reflect admitted actions but cannot create them;
- presentation cascade and capability attenuation remain different operations;
- renderer terminals are replaceable and non-authoritative; and
- generated code never becomes the unrecorded source of the design system.

### 3.6 Unknown structure survives partial interpretation

An older interpreter MUST preserve unknown admitted records and slots when it
can do so safely. It may fall back or refuse to pronounce them, but it must not
silently erase or reinterpret them.

### 3.7 One canonical semantic IR

Foundry has several representations because authoring, compilation, delivery,
and terminal materialization have different jobs. They MUST NOT become
competing semantic authorities:

| Representation | Role | Lifetime and authority |
| --- | --- | --- |
| `foundry_doc/surface` | Authored graph of definitions and ordered placement edges interpreted from corpus records | Durable authored meaning while the `.sd` donor remains; eventually supplied by admitted Nenex records |
| `surface_tree` | Renderer-neutral tree-shaped working form used by `knit` and `sewn` | Transient compiler IR only; no independent revision, durable identity, or delivery authority |
| `projection_dag` | Addressed graph of shared semantic definitions, contextual placements, Holes, actions, parameters, roots, and revision evidence | **Canonical resolved semantic IR** and the only semantic input shared by terminals |
| `projection_pronunciation` | Deterministic ordered occurrence view over one complete `projection_dag` revision | Disposable traversal view, not a second semantic graph and not a pronunciation program |
| `terminal_plan` | Typed, per-occurrence selection of admitted terminal Recipes and bindings | Disposable internal planning evidence for one backend request; schedules `felt` execution but is not a new primitive shape |
| `weft/node` | Existing typed Web terminal AST | Web-specific output after the semantic-to-terminal cut, not a universal component IR |
| Terminal Fragment | Versioned envelope pairing terminal material with an existing semantic address | Replaceable delivery product, never semantic identity or authority |

`foundry_doc/surface` and `surface_tree` MUST have one explicit deterministic
relationship. Either the authored graph compiles through `knit`/`sewn` into the
addressed DAG, or `surface_tree` remains an optional working view used by
particular Recipes. It must not remain a second permanent structural graph with
unspecified equality. In either case, compilation records enough source and
Recipe provenance to reproduce the canonical `projection_dag`.

No terminal may reconstruct semantic policy by inspecting roles after this
boundary. Any representation added later must state whether it is authored,
canonical semantic IR, a disposable derived view, backend-specific terminal
IR, or a delivery envelope.

## 4. Corpus records

The first release recognizes the four established Foundry document families.
They are interpretations of ordinary namespace records, not special storage
objects.

### 4.1 Layer

A Layer supplies semantic token assignments and provenance.

```text
Layer
  identity
  guarded
  token assignments
  declared applicability
  source page and revision
```

Broad layers resolve before near layers. Guarded client-owned layers, initially
accessibility and mandatory privacy presentation, resolve after ordinary layers
and cannot be undone by a nearer cosmetic layer.

### 4.2 Surface

A Surface is a renderer-neutral, tree-shaped DAG template composed from Stage
ceiling, Scene, Plate, Block, Slot, Text, and Glyph roles. It contains unique
definitions and ordered placement edges.

Surface records MAY declare:

- semantic kind and role;
- stable definition identity;
- named placement Slot;
- source reference;
- reference to a source-owned Action declaration;
- semantic navigation destination;
- live Hole reference;
- semantic fallback reference;
- external template reference;
- invariant Text content; and
- projection parameters that remain semantic.

Renderer classes, DOM event handlers, CSS layout declarations, and native
widget handles MUST NOT enter a Surface.

### 4.3 Recipe

A Recipe maps a semantic input role and context to a realization step.

```text
Recipe
  identity
  input role and shape
  output role and kind
  primitive: dyed | knit | sewn | felt
  ceiling
  backend and pronunciation family
  required features
  ordered fallbacks
  template or native operation reference
  optional lawful amendment contract
```

Native operation references remain inert until the selected interpreter invokes
them. The recipe does not name a privileged runtime callback or acquire
authority by being selected.

### 4.4 Catalog

A Catalog declares an entry projection and its ordered closure of recipes and
layers.

```text
Catalog
  identity
  optional source constraint
  source role
  target role
  ceiling
  ordered recipe references
  ordered layer references
  optional terminal role
```

Catalog selection is semantic. HTTP routes and renderer-local component names
must not select catalogs by accident.

### 4.5 Provider bindings and generators

“Provider pack” is not a Foundry object. Provider bindings and generators are
represented as coordinated Layers, Recipes, Catalogs, and `felt`
pronunciations, not a fifth storage kind. A new record kind is justified only
if repeated use demonstrates state or laws that cannot be expressed by those
four families.

Examples include:

- Web semantic variables and HTML/CSS pronunciation;
- Apple dynamic colors, typography roles, materials, and symbol choices;
- text-terminal emphasis and navigation pronunciation;
- SVG symbol and sprite maps;
- TypeScript and Swift type generation; and
- documentation and conformance-test generation.

## 5. Nenex and Semidoc extensions

### 5.1 Stable named records

Nenex currently expands document structure as ordered child records. Foundry
authoring also needs stable explicitly declared identities that do not move when
prose or sibling order changes.

The expansion law MUST support both:

- ordered anonymous document children for prose; and
- named semantic definitions mounted through explicit stable identities.

Named definitions still retain source spans and page provenance. A collision
between two live pages declaring the same identity must produce a stable
diagnostic and no admitted Foundry revision.

### 5.2 Source-record synchronization

The existing bidirectional Nenex law remains:

- editing source deterministically updates normalized records;
- lawful direct record changes regenerate canonical source;
- a change commits atomically; and
- source and records never remain divergent.

Foundry-specific interpretation MUST NOT create a second editable mirror.

### 5.3 Typed relation vocabulary

Semidoc path-valued attributes already form typed relations. The Foundry
interpretation should consume those relations directly.

The initial vocabulary includes:

```text
/foundry/name
/foundry/kind
/foundry/guarded
/token/...
/surface/root
/surface/kind
/surface/role
/surface/place
/surface/slot
/surface/source
/surface/action
/surface/destination
/surface/hole
/surface/fallback
/surface/template
/recipe/...
/catalog/...
```

Slot contracts require a small extension:

```text
/slot/accepts
/slot/cardinality
/slot/required
/slot/fallback
/slot/participation
```

These fields describe compatibility and narrowing. They never grant action
authority.

### 5.4 Corpus index

Nenex should expose an interpreted Foundry index grouped by declared kind and
identity. The index is observational and MUST NOT instantiate every recipe or
open live Holes merely to display the corpus.

Each entry should show:

- editorial page;
- declared semantic identity;
- current revision pin;
- kind;
- forward dependencies;
- backlinks;
- validation state;
- generated/projection consumers; and
- most recent accepted or refused interpretation.

## 6. Semantic foundations

### 6.1 Page granularity

Token paths should be granular. Pages should be cohesive.

Do not create one page per scalar. A page should normally represent one
versioned Layer, provider-pronunciation grouping, component contract, Recipe,
Surface, or Catalog. A provider grouping still expands into the four ordinary
record families; it does not create a fifth kind. Splitting is warranted when
parts need independent ownership, revision, fallback, or reuse.

### 6.2 Token domains

Tokens MUST be named by semantic purpose rather than apparent value.

Initial domains:

```text
/token/color/text/...
/token/color/fill/...
/token/color/surface/...
/token/color/border/...
/token/color/action/...
/token/color/status/...
/token/type/...
/token/space/...
/token/radius/...
/token/elevation/...
/token/material/...
/token/motion/...
/token/density/...
/token/layout/...
```

`primary` and `secondary` are valid only beneath a semantic domain, for example
`/token/color/text/secondary`. A global `/token/color/primary` is too ambiguous
for a durable system.

### 6.3 Scales and aliases

Foundational scales and semantic aliases are distinct:

```text
foundation value or provider symbol
    <- semantic token
        <- Block- or Plate-local refinement
```

For example, `/token/color/text/secondary` can resolve to an Apple dynamic
system role, a Web CSS variable, or a text-terminal emphasis policy. The core
semantic token must not be named after any one provider API.

Exact CSS pixels, media queries, SwiftUI modifiers, and raw platform color
values remain terminal pronunciation material. Typed cross-provider measures
may be added only after their unit and scaling laws are explicit.

### 6.4 Initial system packet

The first shared system should define only enough vocabulary for the Chat
vertical:

- primary, secondary, tertiary, and disabled text;
- base, raised, sunken, overlay, selected, and destructive surfaces/fills;
- accent, positive, warning, and destructive actions/status;
- body, caption, label, header, and code typography roles;
- compact, regular, and spacious density;
- related, grouped, section, and Plate spacing roles;
- small, regular, Plate, and window radii/elevation roles;
- visible focus, increased contrast, and reduced-motion guarded policy; and
- stable layout roles required by Plate Header, Message, Composer, Sidebar,
  Window, and Scene.

`header` in the type vocabulary means a semantic **Header Text Style**, not a
component. Its cohesive definition supplies text attributes such as family,
size, weight, line height, tracking, and their fallbacks under
`/token/type/header/...`. Text color remains a separate semantic token so the
same Header Text Style can appear on ordinary, secondary, selected, or
destructive surfaces without being redefined.

Structural headers must be qualified by their actual anatomy and owner. The
initial component is `Plate Header Block`; `Section Header Block` may be added
later if it proves to be a distinct reusable contract. `Title Bar Block` is
chrome and remains separate from both. Bare `Header Block` is not a canonical
name.

The first packet is not a promise that these exact names are forever complete.
It is a bounded vocabulary that must prove its usefulness across multiple
surfaces before expanding.

## 7. Block and Slot governance

### 7.1 Component boundary

Every candidate must be classified before it is promoted:

- shared Block contract;
- composite pattern;
- product-local Block;
- headless behavior/source layer; or
- renderer pronunciation.

If a definition combines more than one of these roles, split the boundary.

### 7.2 Promotion rule

A product-local Block should become shared only when:

- it already recurs in at least two independent compositions, or a second
  consumer is imminent and concrete;
- its semantic role and Slot anatomy are stable;
- product-specific copy, analytics, source paths, and workflow policy can stay
  outside it;
- its fallbacks and accessibility obligations are known; and
- sharing removes real duplicated maintenance.

Plate Header, Action Button, Text Input, Title Bar, and Window Control Group are
likely shared. Chat Message, Conversation Item, and Chat Composer begin
product-local.

### 7.3 Slot anatomy

A Slot is a semantic attachment contract, not an empty rectangle. A reusable
Plate Header may declare:

```text
Plate Header Block
  leading:  optional Glyph or bounded Block
  title:    required Text
  subtitle: optional Text
  status:   optional Block
  trailing: optional Block
  content:  optional bounded projection
```

Layout changes may move these Slots without renaming them. A renderer may
pronounce the same Plate Header as a row, stacked block, spoken sequence, or
compact summary. Text placed in its `title` Slot may request Header Text Style;
that style does not create or imply the surrounding Block.

### 7.4 Behavior ownership

Blocks expose semantic Action roles and state requirements, not arbitrary
callbacks. The source Node, Flow, or subject remains responsible for behavior.
The active context separately determines whether an Action is admitted.

A Composer Block can expose `send`, but its presence does not grant permission
to append to a Chat Flow.

### 7.5 Action and navigation admission

A Surface Block may reference a source-owned Action declaration. The declaration
owns the semantic intent, target subject or Flow operation, input contract,
capability requirements, and result, refusal, and receipt policy. The Surface
owns none of those facts: it only names the Action it can expose. In particular,
the Chat Composer Action is not `/chat/log`; `/chat/log` is the stateful subject
used by the source-owned send declaration after admission. The Action is also
not a `kind=action` Surface node, a direct kook or form reference, or a
capability declaration attached to the Composer.

Action and navigation admission are contextual and occurrence-scoped. The
canonical DAG therefore carries independently addressed interaction entries,
not additional Surface kinds or authority hidden in generic terminal bindings:

```text
projection_interaction
  address
  owner occurrence address
  action_mounts
  optional destination_mount

action_mount
  source-owned Action declaration identity and pin
  typed input-contract reference
  admission and attenuation witness

destination_mount
  semantic destination declaration
  admitted target occurrence address
```

The admission witness is produced by a trusted authority resolver over the
authenticated actor, target Action horizon, effective capability intersection,
and every enclosing attenuation contract. A digest-shaped byte string supplied
by a Surface, terminal, client, or declaration is not such a witness. The pure
Action admission function may validate and narrow verified context and derive a
mount-bound witness from it; it MUST NOT authenticate an opaque digest or mint
the upstream grant itself.

`projection_interaction` is a derived `projection_object` / `projection_entry`
variant in the canonical DAG. It is not a fifth corpus family and not a visible
child. Its independent address lets progressive Upsert, Resolve, Withdraw, and
revision completion apply without inventing a second delivery protocol. The
`owner` is the exact Block or Slot occurrence governed by the entry. A shared
Composer definition placed under two contexts remains one definition but may
have two interaction entries with different admitted Action sets.

An authored `/surface/action` or `/surface/destination` path may travel through
the compiler as an unresolved semantic reference, but that parameter is not an
admission result. Before terminal planning, Foundry must resolve it into the
typed occurrence binding above or emit an addressed refusal. A semantic
destination resolves to a Scene Route or other addressed projection target;
the browser URL is terminal material. If navigation also changes durable Flow
selection, the destination relation and the mutating Action remain two separate
bindings.

## 8. Cascade, fallbacks, and refusal

Fallback behavior must be fixed before Space- or Locus-specific presentation is
implemented.

### 8.1 Semantic scope cascade

The target contextual order is:

```text
client baseline
personal accessibility and privacy guards
Personal Web Foundry
Space Foundry
Scene Foundry
Plate Foundry
Block Foundry
projection-local fork
```

Ordinary values resolve broad-to-near. Guarded client-owned accessibility and
privacy presentation resolves after ordinary layers. Every selected value
carries exact winning-layer provenance.

This is the **semantic scope cascade**: progressively narrower scopes refine a
shared field of semantic presentation policy. It is independent from how much
terminal material a client chooses to realize. Visibility, distance, focus, or
device pressure MUST NOT change semantic identity, admitted actions, privacy,
or accessibility obligations.

### 8.2 Resolution Context DAG

The compiler does not copy a fully flattened token record into every
occurrence. It derives a content-addressed `ResolutionContext` DAG. Each
context contains at least:

```text
ResolutionContext
  digest
  parent context digest?
  scope occurrence address
  ordered local Layer pins
  resolved-value delta
  winning-layer provenance
  guarded accessibility and privacy evidence
```

Every contextual placement occurrence in the canonical `projection_dag`
references exactly one Resolution Context. A reused definition can therefore
retain one semantic identity while its placements resolve under distinct
contexts. Equal parent context, local Layer pins, guards, and deltas produce an
equal digest and may share one context node.

Resolution Contexts are content-addressed derived data attached to a completed
projection revision, not authored Nodes and not another semantic authority.
They may be cached and recomputed independently. A consumer requests only the
resolved fields its selected Recipe needs, but the context still records the
complete winner and guard evidence required to reproduce those values.

Inheritance of presentation values does not imply inheritance of authority.
Actions, observations, Sights, capabilities, and disclosure still follow their
own admission and attenuation laws.

### 8.3 Fallback classes

The implementation MUST keep these distinct:

1. **Semantic fallback** — a simpler compatible meaning-preserving recipe.
2. **Structural fallback** — an explicitly permitted lower-ceiling composition.
3. **Renderer fallback** — another terminal representation for the same role.
4. **Progressive Hole fallback** — cached, placeholder, empty, or compact
   content while a live source remains unresolved.
5. **Refusal** — stable evidence that no compatible realization is available.

Accessibility is a guarded override, not a fallback class.

### 8.4 Fallback laws

Every fallback edge must be explicitly authored. A fallback may reduce
richness, composition depth, interaction, animation, or provider specificity.
It MUST NOT:

- invent source semantics;
- disclose additional structure;
- widen effective actions or capabilities;
- exceed the current projection ceiling;
- override a guarded accessibility requirement;
- style or mutate an ancestor; or
- change the referenced source occurrence.

Resolution order is deterministic:

```text
exact applicable recipe
  -> ordered explicit fallback recipes
  -> ordered explicit terminal alternatives
  -> refusal
```

Cycle, ambiguity, kind mismatch, missing required Slot, over-ceiling output, and
provider incompatibility all produce diagnostics or refusal rather than an
invented default.

### 8.5 Terminal fidelity

Terminal fidelity is a request axis separate from the semantic scope cascade:

```text
latent -> coarse -> normal -> refined
```

It belongs beside backend, features, mode, and ceiling in a pronunciation
request. Fidelity may postpone work or choose an explicitly authored
compatible terminal Recipe. It MUST NOT rename an occurrence, change its
Resolution Context, disclose more semantic structure, add or remove an
admitted action, or skip guarded accessibility and privacy resolution.

A coarse result is valid only when the Catalog admits it as a compatible
meaning-preserving fallback for that role and request. The absence of a finer
Recipe is not permission to treat a parent context or partial semantic result
as final. Latent content may retain its semantic address and dependency state
without producing a Fragment.

### 8.6 Progressive laws

- Completed addressed definitions may be retained by address without being
  resent.
- A Hole names its expected kind, semantic role, source, parameters, and
  semantic fallback.
- Resolving a Hole replaces only that address or mounted live branch.
- An unchanged source pin and dependency closure must produce byte-identical
  semantic definitions.
- A terminal may preserve the last complete compatible realization while a new
  revision is pending.
- The last complete compatible Fragment remains mounted until its replacement
  is complete; terminals do not expose a partially resolved cascade between
  fidelity levels.
- A fidelity transition changes terminal material only. It does not change the
  completed semantic DAG revision, occurrence address, Resolution Context, or
  admitted behavior.
- Values are interpolated across a refinement boundary only when a Recipe
  declares a lawful interpolation. Otherwise replacement is atomic.
- A browser or renderer cache is non-authoritative and may always be rebuilt.
- Only a complete admitted revision becomes the committed packet graph.

## 9. Pronunciation and code generation

### 9.1 Zoo primitive algebra

Foundry Recipes use the existing Zoo overlay constructors according to their
input and output shapes:

| Primitive | Shape | Foundry responsibility |
| --- | --- | --- |
| `dyed` | record -> record | Resolve or refine semantic values while preserving record structure. |
| `knit` | record -> subtree | Lift one admitted source occurrence into an initial SurfaceTree. |
| `sewn` | subtree -> subtree | Normalize, compose, graft, cascade, and otherwise transform renderer-neutral structure. |
| `felt` | subtree -> record | Collapse an admitted SurfaceTree into one terminal pronunciation or generated-artifact record. |

Their canonical composition is branched rather than a claim that every
compiler carrier is a new Zoo shape:

```text
source occurrence record
  -> dyed*                     semantic record refinement
  -> knit                      initial renderer-neutral SurfaceTree
  -> sewn*                     structural projection and composition
       |
       +-> compile and address
             -> projection_dag             canonical addressed semantic IR
             -> projection_pronunciation   deterministic occurrence traversal
             -> validated addressed subtree views
             -> Zoo select admitted felt Recipes
             -> terminal_plan              internal scheduling evidence
             -> felt:<target>*              each call remains subtree -> record
             -> typed terminal AST or generated artifact
             -> Terminal Fragment?         only for installed runtime material
```

The signatures are the law; the names do not create new authority. A Recipe
cannot label a record-to-record operation `sewn`, nor treat a terminal payload
as an input subtree. `felt` is the semantic-to-terminal cut. A Fragment is a
delivery envelope after that cut, not a fifth Zoo primitive and not the inverse
of a semantic projection.

The Zoo `subtree` is a validated renderer-neutral shape class, not a promise
that its only carrier is the transient `surface_tree` record. A completed
`projection_dag` may carry that same validated structure with addresses,
sharing, placements, and Resolution Context references. `felt` receives an
addressed subtree view of that carrier; it does not rebuild a semantic tree.

The expanded pipeline therefore does not change the four primitive shapes.
Addressing, Resolution Context derivation, traversal, and plan construction are
compiler bookkeeping around admitted Recipes. The interpreter uses the
`terminal_plan` to schedule each selected `felt` call with its corresponding
subtree view and context; the plan is not itself the primitive input. Neither
`surface_tree` nor `terminal_plan` becomes a second delivered semantic graph or
authored ground.

### 9.2 Typed terminal lowering plan

The late-pronunciation registry is a derived index over admitted,
Catalog-visible `felt` Recipes. It is not an imperative registration API and
not a fifth corpus family. Its key includes semantic kind and role, backend,
pronunciation family, features, mode, ceiling, and fidelity. Its entries retain
the exact Recipe identity, revision pin, input contract, terminal operation,
fallback edges, and provider dependencies.

For one completed `projection_dag` and one pronunciation request, Zoo selects
exactly one admitted Recipe for every required occurrence or emits an addressed
ambiguity/refusal. The selections and their validated inputs form an ephemeral
typed `terminal_plan` used to execute those Recipes:

```text
terminal_plan
  schema and terminal-operation version
  completed semantic DAG revision
  backend, pronunciation, features, mode, ceiling, fidelity
  roots
  ordered terminal steps
  complete Recipe, Layer, Catalog, and fallback provenance

terminal_step
  semantic and placement occurrence address
  selected Recipe identity and pin
  Resolution Context digest
  closed terminal-operation reference and typed bindings
  ordered child-step references
  admitted Hole, Action, and destination mount bindings copied from the DAG
  fallback or refusal evidence
```

Terminal operations form a small, versioned, closed algebra for the target
family. They are terminal opcodes, not new Block roles or product concepts. A
Web interpreter may dispatch on those opcodes to construct the existing
`weft/node` AST; it MUST NOT dispatch on Chat roles, source routes, visible
product copy, or application-specific paths. A text interpreter lowers its own
plan from the same semantic DAG and occurrence addresses.

An `action` terminal opcode, if a selected `felt` Recipe uses one, is only a
mechanical pronunciation instruction. It does not make Action a Surface kind
and it is invalid without the exact admitted Action mount copied into that
occurrence's terminal step. A Composer may instead remain a container operation
whose admitted mount supplies submission semantics. In either case, the adapter
must not infer an Action or destination from a semantic role, `/surface/source`,
`kind`, route, or application default.

Product copy, navigation destinations, actions, observation sources, and Hole
identity must already be admitted semantic inputs. A plan may contain a
selected target-operation reference, but concrete tags, escaping, classes, CSS
spellings, target-local handles, and payload bytes appear only in the terminal
record emitted across the `felt` cut. Provider values come from selected Layers
and Recipes, never from an application switch.

The decisive non-displacement test is that erasing diagnostic semantic role
names from a completed plan does not change terminal bytes. Unknown or
ambiguous semantic roles refuse while building the plan; the adapter never
rediscovers Foundry policy.

### 9.3 One resolved input, several outputs

Both runtime rendering and code generation consume the same resolved addressed
semantic graph.

```text
completed projection_dag revision plus Resolution Contexts
  -> felt:web-runtime
  -> felt:web-source
  -> felt:css
  -> felt:typescript
  -> felt:swiftui-source
  -> felt:svg-pack
  -> felt:text
  -> felt:docs
  -> felt:tests
```

A runtime pronunciation serves a live surface. A source pronunciation emits a
reproducible artifact. Neither changes authored identity.

### 9.4 Generated artifact provenance

Every generated artifact must record or be accompanied by:

- source semantic identities;
- source revision pins;
- complete dependency pins;
- selected catalog and layer chain;
- target backend, features, and projection ceiling;
- generator/pronunciation identity and version;
- output digest; and
- any fallback or refusal evidence used during generation.

Two runs over equal inputs must produce byte-identical outputs, except for
explicitly declared non-semantic packaging metadata.

### 9.5 Generated-code ownership

Generated files follow one of three explicit policies:

1. wholly generated and overwritten;
2. generated with named extension Slots/files outside the generated artifact;
3. bidirectional only through an exact complement with Get-Put, Put-Get,
   validation, and refusal laws.

Unmarked manual edits to generated files are unsupported. Generated code must
not gradually become the real undocumented design system.

### 9.6 Generator boundaries

Generators may emit target syntax and target-specific accessibility metadata.
They must not:

- derive new semantic roles from CSS classes or pixels;
- use a route, DOM path, Figma layer name, or generated symbol as durable
  identity;
- introduce an action not present in the semantic graph;
- hide an unresolved required Slot; or
- make a provider-specific value canonical across all renderers.

## 10. Terminal Fragments and the handler boundary

`felt` and Frag are adjacent, but they are not synonyms.

- `felt` executes a selected terminal pronunciation over validated addressed
  subtree views carried by one completed `projection_dag`; the internal plan
  schedules those calls without changing their `subtree -> record` shape.
- A **Terminal Fragment** carries one replaceable result of that pronunciation
  to a target-local handler.

The boundary is:

```text
completed addressed semantic graph
  -> typed terminal_plan
  -> felt:<terminal pronunciation>
  -> target AST or payload (`weft/node` for Web)
  -> Terminal Fragment offer
  -> target-local codec handler
  -> local materialization
```

A Fragment is therefore not a Block, Plate, Scene, authored Nenex definition,
Recipe, durable identity, or authority-bearing callback. It is terminal
material associated with an existing semantic occurrence. Semantic frames stay
canonical; terminal Fragments remain replaceable siblings that a consumer may
discard and reproduce.

For Web, `weft/node` is already the typed terminal AST. Generalization MUST use
it rather than inventing a second renderer-neutral HTML/component graph. The
Web `felt` interpreter executes only the closed terminal operations selected in
the plan and constructs the Weft AST. The codec adapter only serializes and
packages that AST. Semantic selection has already finished before either
terminal stage runs.

### 10.1 Terminal Fragment contract

The target contract generalizes the current
`projection_terminal_pronunciation` record and contains:

- the exact semantic address being pronounced;
- codec/pronunciation identity and version;
- terminal-plan digest, selected Recipe pins, Resolution Context digest, and
  requested fidelity;
- a target-local destination or handle, never durable semantic identity;
- media kind and payload/body;
- cache and retention policy;
- resolved graph revision plus source and dependency provenance; and
- fallback, refusal, or compatibility evidence relevant to the payload.

Equal completed inputs under the same pronunciation must produce an equal
Fragment payload. A Fragment cannot add structure, roles, actions, or
capabilities absent from its addressed semantic input.

Generated source is not automatically a Fragment. It becomes terminal runtime
material only if a host installs it under a declared codec and offers it to a
handler. `felt:web-source`, `felt:css`, and `felt:swiftui-source` otherwise
remain reproducible build artifacts with the ownership laws above.

### 10.2 Current Web compatibility surface

The existing Web implementation is the first concrete Fragment codec:

- `frag/html` stores terminal markup;
- `/frag` serves one bare HTML pronunciation;
- `frag/mount_report` mounts an already-composed report and is the current
  live-Hole replacement boundary; and
- `/w.js` is a fixed declarative Weft handler for fetch, observation, form,
  replacement, revision, retry, scrolling, and retention behavior.

This does not make inline scripts, DOM paths, routes, or browser object handles
part of Foundry meaning. The current wire key `"html"` is a compatibility
spelling for the Web payload, not the general Fragment ontology. Generalization
must preserve existing Web clients until a versioned media/body envelope is
available.

### 10.3 Handler law

Every terminal handler follows the same authority split:

```text
Offer    addressed semantic occurrence under pinned codec law
Handle   decode and materialize locally
Propose  return a structured claim tied to that offer
Resolve  admit the next state, witness, or refusal in Shrine
```

Handlers may cache, render, observe, and mediate explicitly scoped local
effects. They do not admit revisions, mint semantic identity, or obtain ambient
authority. Browser retention is consequently useful and disposable, never the
source of truth.

## 11. Reference vertical

The first complete vertical is Chat.

```text
Chat Flow occurrence
  -> Chat Plate
       -> Plate Header Block
       -> Message Log Block
            -> live messages Hole
       -> Composer Block
            -> identity selector Slot
            -> text-input Slot
            -> admitted send Action

Chat Scene
  -> Conversations/sidebar Plate
  -> Chat Plate

Stage Flow
  -> root Scene realization
       -> Life Scene Plate
       -> Chat Scene Plate

Locus personal overlay plane
  -> command surface
  -> Flow switcher
  -> Lense Plates
  -> personal hard-pinned Plates
```

### 11.1 Window chrome boundary

A projected web-demo Window Chrome Block may display a traffic-light group. An
actual operating-system close, minimize, or zoom control belongs to trusted
host chrome.

Foundry may request the semantic role. Only the trusted host may pronounce it
as a host-fixed control. An ordinary Scene must not impersonate that authority.
A decorative Glyph remains noninteractive; an actionable projected control
requires a separately admitted Action.

### 11.2 Locus boundary

Locus is a Personal-Web-owned projection context, not a child component of the
active Scene. Its visible surfaces occupy a separate protected overlay plane.
They may inspect or propose actions against a Scene only through separately
admitted Sights and capabilities.

Locus work begins only after the fallback, Slot, and addressed progressive laws
are green in the Chat and Stage Flow verticals.

## 12. Phased implementation

Each phase has an independent exit gate. Later phases must not use prose or
screenshots as evidence that an earlier semantic gate passed.

### Phase 0 — Freeze boundaries and capture the prototype

**Work**

- Record the five-concept mapping and the Stage Flow correction in tests/docs.
- Inventory the current `.sd` corpus, Chat-specific HTML policy, CSS literals,
  recipes, catalogs, addressed frames, terminal Fragment envelope, `/frag`
  compatibility surface, and browser packet cache.
- Capture golden semantic DAG, placement order, terminal output, and live-Hole
  behavior for all current Chat surfaces.
- Mark which current behaviors are source-confirmed, focused-test-confirmed,
  and live-runtime-confirmed.

**Exit gate**

- Existing Chat Plate, Chat Scene, Shrine Scene, desktop specimen, contrast
  specimen, and frames route have reproducible baselines.
- No new semantic feature is introduced during the capture.

### Phase 1 — Add stable semantic identities to Nenex

**Work**

- Extend Semidoc/Nenex expansion for explicitly named semantic definitions.
- Preserve ordered anonymous prose children alongside named definitions.
- Store source page, source range, declared identity, and revision provenance.
- Diagnose duplicate definitions and illegal identity movement.
- Preserve the existing source-record round trip.

**Exit gate**

- Editing prose above a definition does not change its semantic identity.
- Renaming a Nenex page does not rename its declaration.
- Source -> records -> canonical source is stable.
- Duplicate live declarations refuse atomically.

### Phase 2 — Establish the Foundry corpus interpretation

**Work**

- Extract the useful `foundry_doc` Layer, Surface, Recipe, Catalog, and
  diagnostic contracts into a record-oriented `foundry_corpus` module.
- Decode ordinary normalized namespace records instead of reparsing a parallel
  `.sd` corpus.
- Keep unknown fields where safe and diagnose ill-typed required fields.
- Expose an observation-free corpus index.

**Exit gate**

- Equivalent `.sd` and Nenex records decode to equal typed documents during the
  migration window.
- Invalid documents produce stable diagnostics and no runnable partial value.
- Opening the index does not instantiate recipes or live Holes.

### Phase 3 — Build dependency closure and backlink invalidation

**Work**

- Interpret typed forward references as the canonical dependency graph.
- Compute deterministic transitive closure for a selected catalog.
- Detect cycles, missing definitions, kind mismatches, and ambiguous roots.
- Use Nenex backlinks as a reverse dependency/impact view.
- Key compiled definitions by source and dependency pins.

**Exit gate**

- Editing one leaf invalidates exactly its transitive consumers.
- Unrelated definitions retain their addresses and cached artifacts.
- Reordering backlinks changes no compiled output.
- Cycle diagnostics identify the complete relevant reference path.

### Phase 4 — Define semantic foundations

**Work**

- Author the initial cohesive baseline, contrast, motion, type, spacing,
  material, and density Layers in Nenex.
- Establish semantic token naming and page-granularity linting.
- Add Web, Apple, and text provider mappings for the small Chat vocabulary.
- Preserve exact value provenance through cascade resolution.

**Exit gate**

- No Chat Surface contains literal color names used as semantic meaning.
- High contrast and reduced motion survive nearer cosmetic layers.
- Every resolved token identifies its winning layer.
- Missing provider mappings fall back or refuse explicitly.

### Phase 5 — Complete Block and Slot contracts

**Work**

- Add Slot accepts, cardinality, required, fallback, and participation fields.
- Validate attachment kinds and ceiling compatibility.
- Author Plate Header, Title Bar, Window Controls, Message, Message Log,
  Composer, and Conversation Item contracts.
- Keep Chat-specific sources, copy, and workflow behavior outside shared
  Blocks.

**Exit gate**

- Missing required Slots refuse with stable diagnostics.
- Optional Slots disappear or fall back without changing sibling identity.
- Responsive or alternate pronunciation does not rename Slots.
- The same shared Block can be placed twice with one definition and distinct
  occurrence axes.

### Phase 6 — Lock fallback and refusal semantics

**Work**

- Implement the four fallback classes as distinct types or validated roles,
  with refusal as a separate terminal outcome.
- Enforce deterministic ordered traversal, cycle rejection, and ceiling
  monotonicity.
- Define Chat message, Message Log Hole, composer, Window Chrome, provider
  symbol, compact, and text fallbacks. Keep accessibility as guarded policy,
  never a fallback class.
- Emit refusal evidence into projection diagnostics and generated-artifact
  provenance.

**Exit gate**

- Get the same result for equal inputs regardless of map iteration order while
  preserving declared catalog and fallback order.
- A fallback cannot widen structure, observation, or actions.
- Every missing required realization ends in a declared fallback or refusal.
- Guarded accessibility tests pass across all ordinary layer orders.

### Phase 6.5 — Freeze the compiler IR and cascade boundary

**Work**

- Freeze the representation table in Section 3.7 in code and module-level
  contracts: authored `foundry_doc/surface`, transient `surface_tree`, canonical
  `projection_dag`, traversal-only `projection_pronunciation`, disposable
  `terminal_plan`, Web-specific `weft/node`, and Terminal Fragment envelope.
- Choose and test the exact deterministic relationship between
  `foundry_doc/surface` and `surface_tree`; do not maintain two permanent
  structural graphs.
- Make `projection_dag` the only canonical resolved semantic IR consumed by all
  pronunciation targets.
- Add the content-addressed Resolution Context table and one context reference
  per placement occurrence, including parent, local Layer pins, resolved
  deltas, winner provenance, and guarded-policy evidence.
- Add independently addressed `projection_interaction` entries carrying
  occurrence-scoped `action_mount` and `destination_mount` bindings. Resolve
  Surface references against source-owned declarations, perform interaction
  attenuation before terminal planning, and retain the declaration pin plus
  admission witness in the canonical DAG.
- Define the trusted authority-resolver boundary that authenticates actor and
  target, computes Action/capability/attenuation intersections, and issues the
  upstream admission evidence. Digest shape alone is never authority.
- Version the typed `terminal_plan` schema and terminal-operation algebra.
- Add terminal fidelity as a request axis independent of semantic scope,
  identity, and admission.

**Exit gate**

- Equal authored inputs, dependencies, and Recipes produce byte-identical
  addressed DAGs and Resolution Context digests.
- One shared definition placed under two scopes remains one definition with two
  occurrence axes and the appropriate context references.
- One shared Action-exposing Block placed under two interaction contexts remains
  one definition with two independently addressed interaction entries. Each
  entry contains only the Actions admitted in its own context; neither can
  widen, overwrite, or lend authority to the other.
- Removing an admitted Action mount changes no shared definition identity and
  leaves no terminal-visible substitute from role, source, kind, or default.
- No valid Surface or canonical DAG uses `kind=action`, and no Surface record
  owns a subject path, kook/form reference, or capability grant merely because
  it references an Action declaration.
- No declaration, Surface, terminal binding, browser input, or arbitrary
  digest-shaped value can construct an admitted Action mount without verified
  upstream authority evidence.
- Web and text begin from the exact same completed `projection_dag` revision;
  no renderer syntax, route, DOM handle, or native handle appears in it.
- `projection_pronunciation` can be discarded and rebuilt without changing the
  semantic DAG, and no consumer treats it as authored ground.
- Changing only terminal fidelity changes no semantic address, Resolution
  Context, admitted action, or completed DAG revision.
- The existing golden Chat DAG remains equal across the boundary change.

### Phase 7 — Prove Chat Plate through typed terminal lowering

**Work**

- Seed the minimally complete Chat Plate foundations, Blocks, Slots, visible
  copy, semantic navigation destinations, Message Log Hole, and source-owned
  Composer send declaration before removing their legacy renderer branches.
  The Composer Block references that declaration; it does not call `/chat/log`
  directly or declare its own subject, capability, or behavior form.
- Derive a Zoo pronunciation index solely from the selected Catalog's admitted
  `felt` Recipes. Key it by semantic kind/role, backend, pronunciation family,
  features, mode, ceiling, and fidelity; do not expose arbitrary imperative
  registration as authority.
- Compile every required occurrence into a typed `terminal_step` with exact
  Recipe pin, Resolution Context digest, ordered children, typed bindings,
  admitted Hole/Action/destination mounts copied from canonical interaction
  entries, and fallback/refusal evidence.
- Interpret the resulting plan through a generic Web terminal that constructs
  the existing `weft/node` AST and a generic text terminal that consumes the
  same completed semantic DAG.
- Move concrete Web structure and provider spellings into admitted Recipes and
  Layers. Do not move the Chat role switch into a provider, adapter, registry,
  or another application module.
- Separate Web runtime pronunciation from reusable CSS/token output.
- Route the actual Chat Plate exclusively through this path. Legacy Scene and
  Stage branches may remain quarantined until their later migration, but they
  MUST NOT be reachable from the Chat Plate proof.

**Exit gate**

- The same admitted Chat Plate `projection_dag` revision and occurrence
  addresses produce both Web and text output without rebuilding semantic
  structure.
- Neither terminal interpreter contains Chat-role, `/chat`-path, visible-copy,
  or application-source dispatch. Erasing diagnostic role names from a
  completed terminal plan leaves emitted bytes unchanged.
- `apps/chat/main.foil` contains no reachable role-by-role HTML policy for the
  Chat Plate; changing a Recipe changes its terminal output without editing the
  application or interpreter.
- Changing authored copy changes output without editing a Recipe. Removing the
  admitted Composer Action makes form emission impossible.
- The Action-free Composer occurrence cannot regain submission behavior from
  `/surface/source`, `/chat/log`, `kind`, role, a terminal opcode, or an adapter
  default. An `action` opcode without exactly one compatible admitted mount
  refuses before terminal material is emitted.
- A shared Composer definition placed once where send is admitted and once where
  it is refused produces two occurrence-scoped interaction entries and two
  correspondingly different terminal plans without duplicating or renaming the
  shared Block definition.
- Chat navigation reaches the terminal as admitted destination mounts over
  semantic occurrence addresses. Concrete `/chat/...` URLs appear only after
  the `felt` cut and are never recovered from labels or roles.
- Unknown and ambiguous roles refuse while compiling the terminal plan with
  the exact occurrence address; the terminal never supplies a Chat default.
- Coarse Chat output is produced only through an explicitly admitted compatible
  fallback, and the last complete Fragment remains mounted until replacement.

### Phase 8 — Add deterministic code generation

**Work**

- Add `felt` generator targets for CSS, TypeScript token/Slot types, HTML/Weft
  source, documentation, and conformance tests.
- Add SwiftUI and SVG/symbol packs after the core generator contract is green.
- Define artifact manifests, digests, output ownership, and extension points.
- Make generators consume only completed resolved semantic graphs.

**Exit gate**

- Equal pins, features, generator version, and target produce byte-identical
  output.
- Generated artifacts carry complete provenance.
- Manual extension code survives regeneration only through declared extension
  boundaries.
- No generator can introduce semantic roles or actions.

### Phase 9 — Establish the Terminal Fragment boundary

**Work**

- Generalize `projection_terminal_pronunciation` into the versioned Terminal
  Fragment contract without changing semantic packet identity.
- Bind `felt:web-runtime` to the existing `frag/html`, `/frag`,
  `frag/mount_report`, and fixed `/w.js` handler as the first codec.
- Keep the current `"html"` wire spelling as an explicitly versioned
  compatibility form while adding generic media/body semantics.
- Tie every Fragment to one exact semantic address and completed graph
  revision, with pronunciation, dependency, cache, fallback, and refusal
  provenance.
- Specify Offer-Handle-Propose-Resolve for Web first, with the same authority
  boundary available to later native, GPU, audio, file, or agent handlers.
- Keep generated source outside the Fragment lifecycle unless deliberately
  installed as runtime material under a declared codec.

**Exit gate**

- The same semantic frame can be paired with Web and text Fragments without
  changing its address or definition.
- A stale, corrupt, incompatible, or evicted Fragment can be discarded and
  reproduced without loss of semantic state.
- Resolving a live Hole replaces only its addressed mounted Fragment.
- A handler cannot invent a semantic role, action, revision, or capability.
- Existing `/frag` and Weft behavior remains compatible through focused and
  live HTTP/browser proof.

### Phase 10 — Complete the live Chat Plate cutover

**Work**

- Replace the remaining `.sd` donor definitions for Chat Plate, Message Log,
  Plate Header, and Composer with their Phase 7 admitted Nenex records.
- Bind live conversations, messages, and action availability to the addressed
  Hole and Action inputs already proven by the generic plan.
- Delete the quarantined Chat Plate branches from both late HTML policy paths;
  do not leave a compatibility fallback that can rediscover role policy.
- Preserve live message scrolling and message-send behavior.

**Exit gate**

- Editing Header Text Style attributes updates title text without changing
  Plate Header anatomy; editing the Plate Header page updates its composition
  without editing Chat Foil/CSS.
- Sending a message changes only the live log branch; the stable outer semantic
  graph retains its revision and addresses when its inputs are unchanged.
- The focused Chat Foundry suite and live HTTP proof remain green.

### Phase 11 — Migrate Scene and Stage Flow realization

**Work**

- Author the Chat Scene and nested Scene-as-Plate recipes in Nenex.
- Replace the durable desktop-stage concept with Stage Flow state interpreted
  as a root Scene arrangement.
- Keep placement geometry and focus in the Stage Flow subject/kook.
- Use the existing lawful overlay complement for backward geometry amendments.
- Separate projected window chrome from trusted host-fixed controls.
- Migrate every remaining Scene and Stage terminal role to admitted Recipes and
  remove the legacy `plan_policy`/`web_any` semantic role switches entirely.

**Exit gate**

- One Chat source can appear as a Chat Plate, Chat Scene, and nested Scene Plate
  without identity duplication.
- Moving or resizing a window changes Stage Flow arrangement state, not source
  Scene identity.
- Get-Put and Put-Get tests cover geometry amendments and stale complements.
- No application or terminal adapter contains a role-by-role general Foundry
  HTML switch.

### Phase 12 — Complete progressive retention and invalidation

**Work**

- Integrate Nenex dependency pins with addressed frame retention.
- Retain completed semantic definitions and only resend changed entries.
- Cache and reuse equal Resolution Context nodes independently from definitions
  and terminal products.
- Keep live branches as explicit Holes or mounted observations.
- Schedule latent, coarse, normal, and refined terminal work from explicit
  fidelity requests without changing semantic revisions or admission.
- Define cache quotas, eviction, schema-version migration, and refusal recovery
  for the non-authoritative browser store.
- Add instrumentation for retained, upserted, resolved, withdrawn, and refused
  addresses.

**Exit gate**

- A token edit does not refetch an unchanged message log.
- A message append does not rebuild or resend the stable Scene shell.
- Two equal cascade ancestries share one Resolution Context digest; a local
  Layer edit invalidates only the descendant contexts and terminal steps that
  consume its changed fields.
- Refining a visible Plate retains the last complete compatible Fragment until
  the replacement is complete and changes no semantic address or action.
- Corrupt or obsolete browser state can be discarded and rebuilt.
- Multiple open Chat pages converge on admitted revisions without polling
  unchanged state.

### Phase 13 — Introduce Locus, hardening, and governance

**Work**

- Serve command, Flow-switcher, Lense, and personal pinned Plates from the
  Personal Web Foundry in a separate protected overlay plane.
- Keep Stage Flow, active Scene, Personal Web overlay, and trusted host roots
  distinct for occlusion and input routing.
- Add hardening from selected Trace material or projection arrangements into
  new Nenex-authored Nodes with provenance.
- Add corpus review, promotion, deprecation, and compatibility workflows.
- Generate reference documentation and corpus impact reports from the same
  graph.

**Exit gate**

- Locus chrome cannot be occluded or impersonated by Scene content.
- Visible Locus chrome cannot act against a Scene without separate authority.
- Hardening creates new durable ground with source provenance rather than
  mutating an ephemeral projection into authority.
- Deprecated definitions remain resolvable for declared compatibility windows
  or refuse explicitly.

## 13. Current implementation migration map

| Current implementation | Target |
| --- | --- |
| `src/foil/foundry/chat/*.sd` | Seed and test fixtures, then admitted Nenex pages |
| `foundry_doc.foil` source compiler | Donor for `foundry_corpus` record types, validation, and diagnostics |
| `foundry_doc/surface` | Authored graph compiled deterministically into the canonical addressed DAG |
| `surface_tree` | Transient `knit`/`sewn` working IR with no durable revision or delivery identity |
| `chat_css` literal string | Admitted provider Layers/Recipes plus generated semantic variables and Web-terminal spellings |
| Chat `plan_policy` and `web_any` role switches | Authored semantics -> derived Recipe index -> typed `terminal_plan` -> generic Web/text interpreters; then deletion |
| Hardcoded General/Foundry/Random labels | Admitted conversation/source occurrences or explicit fallback Text |
| Literal traffic-light colors | Window Controls role plus Web/Apple provider pronunciation |
| `desktop_stage` semantic root | Stage Flow state served as a root Scene realization |
| Browser IndexedDB packet cache | Non-authoritative addressed retention with schema/version policy |
| `foundry_delivery` DAG and frames | Canonical renderer-neutral semantic IR and addressed delivery boundary |
| `foundry_pronounce` occurrence plan | Rebuildable deterministic traversal view over one completed DAG revision |
| Aggregate Recipe evidence on bridged nodes | Per-occurrence selected Recipe pin, Resolution Context, typed operation, and fallback evidence in `terminal_plan` |
| Web role-to-HTML lowering | Closed terminal operations interpreted into the existing `weft/node` AST |
| `projection_terminal_pronunciation` | Versioned Terminal Fragment envelope paired with, but separate from, semantic frames |
| `frag/html`, `/frag`, and `frag/mount_report` | Web runtime Fragment codec and exact live-Hole mount boundary |
| Fixed `/w.js` runtime | Web codec handler; local effects and retention without semantic admission authority |
| Terminal wire key `"html"` | Compatibility spelling migrated to generic versioned media/body fields |

The old path is deleted family by family only after equality tests, live proof,
and fallback tests pass. A second permanent representation is not an acceptable
migration strategy.

## 14. Verification matrix

### Authoring

- Semidoc parse/unparse and Nenex source-record round trip.
- Stable declared identity across prose edits and page renames.
- Atomic duplicate, ill-typed, missing-reference, and cycle refusal.
- Exact source page, range, and revision provenance.

### Corpus

- Deterministic forward closure and reverse backlink index.
- Unknown-record preservation.
- Layer order and guarded override laws.
- Definition/placement separation and repeated occurrences.

### Surface and fallback

- Kind, Slot cardinality, compatibility, ceiling, and required-child checks.
- Exact, semantic, structural, renderer, Hole, and refusal cases.
- Accessibility and reduced-motion guards.
- No capability widening through ancestry, Slot attachment, or fallback.

### Projection addresses and frames

- Stable address generation from source pin and occurrence axis.
- Begin/Upsert/Resolve/Withdraw/Complete/Refuse lifecycle.
- No partial-revision promotion.
- Minimal invalidation after token, template, source, and provider changes.
- Content-addressed Resolution Context sharing, winner provenance, guarded
  evidence, and descendant-only invalidation.

### Pronunciation and generation

- Runtime Web and text parity over one semantic DAG.
- Exactly one admitted Recipe selection per required occurrence or an addressed
  ambiguity/refusal.
- Terminal-plan determinism, per-occurrence Recipe pins, typed binding checks,
  and stable output after diagnostic role-name erasure.
- No Chat role, application route, visible product copy, or provider-default
  decision in a terminal interpreter.
- Byte-reproducible generated artifacts.
- Complete generator provenance and output digests.
- Negative tests preventing invented roles, actions, and hidden required Slots.
- Golden Chat, Stage Flow, accessibility, and refusal specimens.

### Terminal Fragments and handlers

- Exact pairing between each Fragment and its semantic address and completed
  revision.
- Codec/version/media compatibility, terminal fallback, and explicit refusal.
- Equal payloads for equal inputs under one pronunciation.
- No route, DOM handle, native handle, or generated symbol used as semantic
  identity.
- No inline script or arbitrary callback authority in Web payloads.
- Handler proposals remain tied to their offers and require Shrine admission.

### Progressive Fragment delivery

- Resolving a Hole replaces only its exact addressed mount.
- Retained Fragments survive unchanged revisions and withdraw cleanly.
- Latent/coarse/normal/refined requests preserve semantic identity, Resolution
  Context, guarded policy, actions, and observation authority.
- Coarse output requires an explicit compatible Recipe; incomplete semantic
  resolution is never committed as a lower-fidelity result.
- Last-complete retention and atomic replacement across fidelity refinement.
- Multiple consumers, multiple open pages, and cold-cache recovery converge on
  the same completed admitted revision.
- Corrupt or incompatible local retention can be dropped and rebuilt.

### Runtime proof discipline

Source compilation, focused tests, complete repository gates, mounted Lain
behavior, browser behavior, native provider behavior, and generated-code build
results are separate claims. A roadmap phase is complete only when its named
gate has the required evidence.

## 15. Performance and cache policy

- Corpus interpretation should be incremental by page revision and dependency
  pin.
- Catalog closure should reuse unchanged typed definitions.
- Projection compilation should reuse unchanged definitions and placements by
  address.
- Resolution Contexts should cache by parent digest, ordered local Layer pins,
  resolved delta, guard evidence, and compiler schema version.
- Terminal generation should cache by resolved graph revision, backend,
  features, mode, ceiling, fidelity, selected Recipe pins, consumed Resolution
  Context fields, generator version, and output options.
- Terminal Fragments should cache by semantic address, completed revision,
  Resolution Context and terminal-plan digests, fidelity, codec/pronunciation
  identity and version, media kind, and payload digest.
- A live Hole update should not invalidate a stable ancestor definition.
- Backlinks may plan invalidation but do not determine semantic inclusion.
- Cache limits and eviction are host policy. Cache loss must not alter meaning.
- Diagnostic and generated artifacts must not enter durable namespace ground
  unless deliberately hardened with provenance.

## 16. Governance

### Adding tokens

A new shared token requires:

- a semantic role not already expressible;
- at least two concrete consumers or one unavoidable cross-surface contract;
- fallback and accessibility behavior;
- provider treatment for supported baseline targets; and
- a migration/deprecation note if it replaces another token.

### Adding shared Blocks

A new shared Block requires:

- stable Slot anatomy;
- evidence of reuse;
- product-local behavior removed or explicitly wrapped;
- documented states and fallbacks;
- projection ceiling and action-contract review; and
- Web/text specimens plus relevant accessibility follow-up.

### Breaking changes

Renaming semantic identities, changing required Slots, changing kind, narrowing
accepted attachment types, or changing fallback meaning is breaking. Such a
change requires an explicit replacement relationship, dependent impact report,
and compatibility or refusal plan.

### Ownership

- design-system governance owns token domains, naming, promotion, and shared
  visual-language rules;
- component/Block governance owns reusable Slot anatomy and shared/local
  boundaries;
- Foundry owns cascade, fallback, projection, and pronunciation contracts;
- source Nodes and kooks own semantic state and behavior;
- accessibility review owns remediation and manual verification beyond the
  guarded baseline;
- renderer/provider owners maintain terminal packs; and
- codec-handler owners maintain local materialization, retention, and scoped
  effect mediation without semantic admission authority; and
- hosts own cache, process, device, and trusted-control mechanics.

## 17. Non-goals

This roadmap does not:

- import React, Tailwind, Radix, shadcn, Figma runtime, or another component
  framework into Shrine;
- make Nenex page titles, URLs, Figma layer names, CSS selectors, or DOM paths
  durable identity;
- store every scalar value on its own page;
- place raw CSS, SwiftUI modifiers, native handles, or JavaScript callbacks in
  renderer-neutral Surfaces;
- make Fragments, routes, DOM/native handles, or generated files durable
  semantic identities;
- treat the Web Fragment codec as arbitrary JavaScript execution or as the
  ontology for later terminal handlers;
- make backlinks an inheritance or composition mechanism;
- make generated code authoritative;
- treat presentation cascade as capability inheritance;
- let a projected control impersonate trusted host chrome;
- require every Flow, Stage Flow, or Locus operation to have a visual surface;
  or
- begin Space/Locus styling before fallback and Slot laws pass.

## 18. First executable slice

The smallest credible landing is Phases 0 through 3 for one narrow definition:

1. Create a Nenex page declaring `/foundry/system/blocks/plate-header`.
2. Expand it into stable named namespace records.
3. Interpret it through the extracted Foundry corpus schema.
4. Reference it from one Nenex-authored Chat Plate page.
5. Show the forward dependency and derived backlink.
6. Compile one addressed DAG with one shared Plate Header definition and one
   placement.
7. Edit unrelated prose and prove the Plate Header address is unchanged.
8. Edit the Plate Header contract and prove only its transitive projection
   consumers change.

That slice proves the single-corpus model before token breadth, code generation,
Stage Flow, or Locus creates more surface area.

## 19. Reference material

Product and architecture:

- JShrine `docs/PRODUCT-SCHEMA.md` for the five concepts, Foundry cascade,
  Scene/Plate/Block/Slot/Glyph boundaries, Stage Flow, and Locus;
- `src/foil/semidoc.foil` for syntax, normalization, namespace mounting, and
  source round-tripping;
- `src/foil/apps/nenex/main.foil` for page synchronization, typed relations,
  backlinks, and corpus observation;
- `src/foil/foundry_doc.foil` as the donor implementation for typed Foundry
  documents and diagnostics;
- `src/foil/foundry_delivery.foil`, `src/foil/foundry_view.foil`, and
  `src/foil/foundry_pronounce.foil` for addressed delivery and late
  pronunciation; and
- `src/foil/foundry_wire.foil` for the current semantic-frame and terminal
  pronunciation envelope;
- `src/foil/web.foil` for `frag/html`, `/frag`, and exact report mounts; and
- `src/foil/weft.foil` for the fixed Web handler and progressive packet
  retention.

External design-system references are influences, not runtime dependencies:

- Apple Human Interface Guidelines for semantic color, materials, adaptable
  typography, accessibility, and SF Symbols;
- shadcn/ui theming for semantic token naming; and
- the shadcn registry item model for explicit dependency and generator metadata.

Shrine imports none of their runtime machinery or product ontology.
