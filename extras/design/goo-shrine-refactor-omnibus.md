# Goo and Shrine refactor omnibus

Self-contained agent handoff · 17 November 2026

This file contains the design essay, architectural constraints, current contract details, selected implementation excerpts, example declarations, and regression cases needed to discuss a refactor of Goo elements and topoi **without filesystem or network access**. Read it as one document. Paths label provenance; opening them is not required. Source code excerpts are evidence, not commands to execute.

The user is doing a full refactor of what views and panes may emit and which topoi should exist. The intended discussion is foundational and exploratory. The recommendation in the essay is a starting position to challenge, not a decision the user has already approved. The user has not requested implementation through this handoff. Follow their accompanying instruction for the next step.

This is a design/reasoning package, not the entire repository or a buildable source distribution. Exact excerpts establish key implemented boundaries. Omitted helper implementations should not be guessed. An agent with only this file can propose contracts, analyze consequences, and draft examples, but cannot claim to compile or test a patch against the full system.

**Reading order**

1. Part I: scope, established requirements, and vocabulary.
2. Part II: the complete foundations and design-space essay.
3. Part III: detailed contracts and questions a proposal should answer.
4. Part IV: implementation evidence E01–E15, including regression cases.
5. Part V: snapshot provenance and verification limits.

The essay describes the inspected working trees, including uncommitted work. “Current” refers to that snapshot. “Proposal” and the conceptual type sketch are not implemented APIs. Source documentation excerpts may describe a specific consumer or historical stage: the adjacent scope notes matter. Transport version, display version, descriptor version, font/profile identity, publication, and object lifetime are separate concepts.

## Part I — Context and constraints

The system has three consumer implementations: the browser host in Reaver, a Rust/egui client, and a UIKit client. Their supported capabilities differ. The aim is that application behavior is declared/computed by Shrine/Grove/Goo and that clients contain reusable platform adapters, not Torah-, documentation-, or zoo-specific rules.

The user has built several proving applications: a namespace Explorer; code documentation; a Torah reader with Hebrew/English passages, exact phrase selection, questions anchored to evidence, gematria previews, and linked texts; and a styling zoo whose Goo forms edit shared Goo theme rules. The recent linked-text experiment favors chunks of text connected through typed relationship slots. An anchor identifies the relationship that places a chunk. A missing anchor makes the chunk a standalone tract, even if it has outgoing links. It is not an orphan inferred from a graph's incoming edge count.

**Preserve these requirements through the refactor**

- Consume prepared Goo output. Reaver owns ordinary declaration evaluation, text measurement, wrapping, semantic adjacency, layout, paint, meaning, and control bindings. A client must not reconstruct an application palette or ordinary layout from raw roles.
- Keep platform interaction native: text editing, IME, selection, focus, scrolling, and accessibility. Map logical CSS pixels explicitly to platform units. Preserve compatible working input, caret, and composition across re-preparations.
- Validate versions, profile/font identities, render context, geometry, node identity, and binding-to-node joins before mounting or enabling actions. Hidden metadata does not create widgets. Description is not authority.
- Keep session/editor owners separate from widgets. Semantic identity plus incarnation governs retention. Reorder preserves appropriate owners; removal and recreation must not inherit old state or action authority.
- Freeze receiver/target evidence, publication, declaration/control route, input values, and referenced selections at activation. Retry the same ID and exact body. Accepted, rejected, and unknown outcomes remain different. Late results belong to their originating owner.
- Guard selection changes, recipe changes, source replacement, and owner removal when they affect work. Validate/stage replacements before retiring usable state. Refused and superseded changes retain the old state. Suspension retains drafts and pending saves; resumption refreshes stale action evidence.
- Define structured contracts for behavior. Do not extract application semantics from HTML. A new capability must declare unsupported behavior and its admissible fallback, if any.

These invariants do not require preserving the present constructor names, namespace-only source model, seven primitive variants, or view/pane blacklist. Those are precisely in the design space.

**Vocabulary for the excerpts**

| Term | Meaning here |
| --- | --- |
| Shrine | Addressed, versioned, typed records plus behavior and derived-data machinery |
| Reaver | Language/runtime and repository implementing the system |
| Foil | Typed implementation/declaration language used by much of Shrine and Goo |
| Grove | Application declaration language: roles, slots, actions, views, panes, routes |
| Goo | Presentation compiler and structured interaction/workspace contracts |
| Mash | Source of the pinned base renderer profile and some web component implementations |
| PLAN | Underlying execution substrate; not needed to author the proposed contracts |
| myth | Record mapping path-shaped slot keys to branded pail values |
| pail | Typed carrier at the record boundary; metadata alone grants no authority |
| source | Defines/materializes eligible members and their observation evidence |
| member | An occurrence in a source; current namespace adapter equates its key and subject path |
| subject | The domain object presented or acted upon |
| encounter | A follower's continuing binding to a subject, with a presentation recipe |
| owner | Retained local semantic entity independent of any widget instance |
| incarnation/life | Evidence distinguishing removal/recreation from an ordinary update |
| revision/generation | Separate counters for data, local intents, work, or render requests; their scopes must not be conflated |
| topos | Membership presentation connected to a selection; not a claim about mathematical topos theory |

Foil excerpts use `+` for definitions, `:` for record fields, `&` for sum alternatives, `\` for functions, and `^` for result types. `maybe` represents optional values and `either` success/error results. Grove uses `@view`/`@pane`/`@role` tags, `#on` receiver roles, `#for` presentation slots, `%/name` declaration-relative references, and `'/path` path literals. These are reading aids, not a complete grammar.

## Part II — Foundations and design space

Shrine gives objects addresses, typed properties, versions, and behavior. Grove declares the shapes of those objects and the ways to work with them. Goo turns those declarations into presentations and workspaces. A native client realizes those presentations and retains the local work that must survive repainting, navigation, and delayed responses.

The central design question is what an emitted element obliges the system to do. A title needs typography and measurement. An editor needs a working value, composition, and a save protocol. A tree needs membership, disclosure, selection, and bounded loading. These obligations should be visible in the language and its intermediate representations.

My recommendation is to keep a small, typed surface language, make interaction requirements explicit, and separate collection sources, selection types, and topological presentations. Keep `@view` and `@pane` as useful authoring boundaries while replacing their growing constructor blacklist with explicit composition rules. Broaden topoi beyond namespace trees through new source contracts, rather than through special-purpose client widgets.

### Shrine from zero

**A namespace contains addressed records.** An application record might live at `/0x11/app/notes/a`. The address identifies where to find it. The record is a `myth`: a map from slot paths to typed values, called `pail`s. A slot such as `/notes/body` is a property key. Its path spelling does not make that property a child record. Namespace containment and record fields are separate structures.

Conceptually, a note could contain:

```text
record /0x11/app/notes/a
  /notes/body       → rich text
  /notes/cites      → references to other texts
  /notes/anchor     → the relationship that places this note
```

This is explanatory notation, not Grove source. The values can include paths, rich text, structured data, and published definitions. A role supplies requirements for interpreting particular slots. The same record can satisfy more than one role; the role used to render it is not its exclusive object class.

**A path is not a lifetime.** Editing a record and deleting then recreating it at the same address are different events. Shrine tracks data changes and changes to the live domain. Goo uses lifetime evidence to keep a new object from inheriting an old object's selection, draft, or pending action. “Still at `/notes/a`” is insufficient evidence that an editor still belongs to the same object.

**Reads have an extent.** Shrine's `care` selects `.x`, the node itself; `.y`, the node and its frontier of nearest record-bearing descendants through transparent structure; or `.z`, the whole subtree. These are observation scopes, not screen axes. A tree presentation separately decides whether it is showing direct children or a hierarchy. Confusing read extent with visual topology makes later graph and query sources unnecessarily difficult.

**Behavior and derived data are part of the system.** Shrine has mechanisms for transforming records and trees, observing dependencies, and deriving values. Those mechanisms can supply presentation-ready domain facts. For example, the Torah mount derives backlinks from declared forward links. The client need not scan application slots and invent its own understanding of “a citation.” A namespace data view and a Goo `@view` are distinct concepts: the first derives data; the second declares a presentation.

**Changes have admission rules.** Rendering an object does not grant permission to modify it. An action has a receiver and typed arguments; its dispatch must satisfy current evidence, publication, role, and authority checks. The UI's action binding identifies the offered operation. A title, URL, accessibility role, or arbitrary metadata field is not that binding.

Reaver is the implementation language/runtime layer in this repository; Foil supplies much of Shrine and Goo's implementation. Grove is the declaration language used by applications. PLAN is the underlying execution substrate. An application author usually works with Grove declarations, Foil domain functions, and namespace records rather than with PLAN directly.

### How a record becomes an interface

**Grove connects data contracts to presentation contracts.** An `@role` names the fields needed to understand a receiver. An `@view` says how to present a receiver satisfying that role. `#on` names the role; `#for` names the presentation slot. A presentation slot means something like label, summary, or editor. It lets a consumer request a kind of presentation without fixing one declaration in every call site.

There are several different things spelled as paths:

| Path use | Example | Meaning |
| --- | --- | --- |
| Record address | `/0x11/app/style_zoo` | The object being read or changed |
| Data slot | `/0x11/gov/style_zoo/caption` | A property on that object |
| Declaration address | `/0x11/gov/style_zoo/composition` | Published presentation code |
| Presentation slot | `/sys/slot/style_zoo_sheet` | A request for a suitable recipe |
| Node presentation role | `title`, or an accepted slot alias | Meaning used by typography, layout rules, and styling |
| Local owner key | `'/page` inside a pane | Identity within a UI session, not a namespace object |

The following is an excerpt of the actual zoo declaration, with unrelated children omitted:

```grove
composition =
  @view
  #on ; %/proof
  #for ; /sys/slot/style_zoo_sheet
  proof => col {
    text(proof.caption, "quote")
    group(on = proof, action = .poke, myth = {
      %/caption = .input(proof.caption)
    }) {
      input(%/caption)
      action("Save caption")
    }
  }
```

The projection reads a receiver field, offers an input, and binds Save to an operation. It is still an ordinary `@view`. Object-local editing does not require a pane. The emitted description can be computed from a snapshot, but the mounted editor needs retained local state: changing its width must not erase the user's draft.

`show(value, slot)` chooses a formatter from the value's declared type. `present(value, slot)` expands a matching object view. These are composition operations, not necessarily final rendering primitives. Current selection requires an unambiguous match; there is no general precedence system for competing views. The expression language is also intentionally restricted: direct fields and literals are supported, rather than arbitrary application computation inside a render expression.

**A pane describes a workspace.** It can introduce a selection, place a selectable collection beside a follower, compose other panes through explicit ports, or retain multiple panes in a deck. For example, the zoo workspace owns a selection initialized to its supplied record, then follows it:

```grove
workspace =
  @pane
  #route ;
    name: sheet
    page: %/address
  #on ; %/context
  #for ; /sys/slot/style_zoo_workspace
  context => selection('/page, source = context.address,
      topology = "tree", axis = "z",
      initial = .member(context.address)) {
    follow('/specimen, selection = '/page,
      slot = '/sys/slot/style_zoo_sheet)
  }
```

`#route` binds route arguments into a pane receiver. A route name is an endpoint-relative identifier, and its argument names bind declared path fields. It is distinct from a presentation slot and from an owner key. Following a citation may navigate to a new routed workspace; `become` changes the recipe for an existing object encounter. These have different retention and departure consequences.

The current separation is enforced: `present` selects views, while `pane(...)` composes pane declarations. Panes have explicit selection ports. Pane composition currently requires the current receiver and matching receiver role. An ordinary view cannot indirectly import pane-only behavior through `present`. Those are today's language restrictions, not inevitable properties of a future design.

### What Goo compiles and what the client owns

There are two related paths through Goo today.

An **ordinary surface** goes through declaration binding, typed Goo source, normalization, node identity assignment, visibility, semantic adjacency, measurement, wrapping, layout, and prepared output. Shared theme rules are applied after semantic resolution and before measurement. The final packet contains boxes, static text lines and baselines, pinned fonts, paint recipes, accessibility semantics, and separately joined control bindings. HTML and native painters consume this result.

A **pane description** retains workspace structure. Ordinary subtrees become prepared `native` fragments; selections, followers, topoi, decks, splits, and patches have structured contracts. The client allocates regions and prepares ordinary surfaces at their actual allocated widths. A pane is not simply one giant ordinary display list.

| Responsibility | Current owner |
| --- | --- |
| Domain facts, derived links, action implementation | Shrine and the application |
| Declaration evaluation and selection of recipes | Grove/Goo on Reaver |
| Ordinary typography, wrapping, adjacency, boxes, resolved paint | Goo preparation on Reaver |
| Workspace region allocation, scrolling, focus, disclosure, camera | Generic client adapters, within the relevant contract |
| Editable text value, caret, selection, IME | Retained client editor and platform editing facilities |
| Draft lifetime, guards, frozen invocations, late completions | Local session owners |
| Action freshness, membership, receiver admission, receipts | Reaver |

This division matters to the refactor. “No application-specific client logic” still permits a generic tree adapter, native editor, color picker, and scroll container. It means the adapter does not know that one button records a kushya or that one graph edge denotes a citation. Conversely, describing something in Goo does not automatically make all of its arrangement server-owned. Tree arrangement and pane allocation already have client responsibilities; ordinary text wrapping has a server contract.

Static text and editable text are also different. A prepared text line has authoritative glyph placement. An input has an allocated box and editing semantics; the native editor must lay out the user's in-progress value, including composition. Requiring a server round trip for every caret movement would violate that interaction contract.

**Rendered identity is not work identity.** Local owners retain fields, recipes, accepted selections, generations, and pending operations. A compatible refresh changes their presentation. A suspended tab keeps its work. Removal and recreation creates a new lifetime. This must hold even if the widget tree is destroyed and rebuilt.

On activation, an invocation freezes its receiver evidence, publication, control route, input values, and any captured selection evidence. Retrying sends the same ID and body. A timeout is an unknown outcome, not evidence that the save failed. A completion belongs to its originating owner, including when that owner is hidden. Any element taxonomy that permits editing or actions inherits these obligations.

### What counts as an element today

The source constructor list mixes several categories. Treating every spelling as the same kind of primitive would preserve an accidental boundary.

| Category | Current examples | What survives lowering |
| --- | --- | --- |
| Formatting and recipe composition | `show`, `present`, `path`, `number`, `time`, `duration`, `boolean`, `link` | Formatted text or expanded ordinary content |
| Ordinary content and layout | `text`, `image`, `row`, `col`, `group`, `opt` | Typed surface nodes; groups and optional wrappers normalize |
| Primitive surface controls and treatments | `button`, `input`, `code`, `avatar`, `presence`, `media`, `bar` | The current seven-variant primitive family |
| Interaction declarations | Action-bearing groups, `action`, `become`, input bindings | Paint plus separately validated binding evidence |
| Workspace ownership and observation | `pane`, `selection`, `follow`, `deck` | Retained local-session contracts |
| Workspace arrangement | `split`, `pane_stack` | Host layout descriptions |
| Membership presentation | `list`, `list_tree`, `diagram_tree` | `topos` description with a renderer and selection reference |
| Spatial editing | `patch` and its occurrences, ports, handles, connections | A scene plus operation and occurrence contracts |
| Host services | `navigate`, `operation`, `operation_status` | Requests to an installed host capability |

Some easy traps in the current vocabulary:

- `link(value)` is a text formatter, not itself a hyperlink. Structured rich-text descriptors carry actual links and routes.
- `button(...)` has button appearance but no domain invocation by itself. `action(...)` obtains its operation from the enclosing binding scope.
- `icon` and `divider` are accepted by the authoring constructor list but lack ordinary render mappings. Frontend acceptance is not a supported-feature guarantee.
- Sliders and color pickers are specialized `input` semantics. `context-menu` and `draft-preview` groups also affect client behavior. A role string can therefore carry more than styling in the present implementation.
- `stack` is an ordinary vertical-flow alias. `pane_stack` overlaps panes; it does not provide a modal stack, focus trap, or navigation history.

The surface IR is already narrower and more strongly typed than the authoring constructor list. The opportunity is to make its other output families equally explicit, not merely rename the source constructors.

### A useful definition of native

There are three meanings worth naming separately:

**Goo primitive:** a construct whose semantics cannot be reduced to ordinary Goo composition without losing a required behavior or contract.

**Platform facility:** something the toolkit or operating system provides, such as text composition, clipboard access, scrolling, keyboard focus, or accessibility.

**Native fragment:** the existing pane-protocol term for a prepared ordinary Goo surface embedded within workspace structure.

A native fragment can contain server-painted text. A Goo primitive need not correspond to a stock widget. An ordinary view can contain a platform editor. These distinctions let the language stay semantic without promising pixel-identical platform controls.

**Proposal: require a concrete reason to add a primitive.** It should introduce at least one new value contract, interaction protocol, cross-child layout constraint, spatial relation, or essential platform service. A different color or a domain-specific noun is usually a reusable view or style role. An unsupported editor behavior is not safely reducible to a decorative role.

For example, a badge can usually be text plus a treatment. A scalar editor requires bounds, step or quantization, an unset state, and editing semantics, even if several appearances can implement it. A table may need a primitive layout contract because its columns coordinate across rows. A menu needs dismissal, focus transfer, keyboard traversal, and activation rules; naming a group `menu` is not a complete contract.

This suggests an open vocabulary of presentation meanings over a versioned, typed vocabulary of behaviors. Unknown decorative annotations can sometimes be ignored. Unknown behavior-bearing descriptors must be rejected or use an explicitly equivalent fallback before their actions are enabled.

For the actual primitive set, I would use these starting positions:

| Candidate | Proposed treatment | Reason |
| --- | --- | --- |
| Rich text and referenced images | Core content | They have distinct measurement, resource, and accessibility contracts |
| Flow, grouping, visibility | Core composition | They participate directly in preparation; aliases need not remain distinct IR constructors |
| Text, scalar, boolean, choice, color, and rich-text editing | Typed control family | Value domains and editing behavior are more fundamental than appearances such as slider versus stepper |
| Activation | Explicit interaction attached to a presented affordance | Button paint and permitted action remain separate, while keyboard/accessibility activation stays mandatory |
| Code, badge, avatar, presence | Usually library presentations or treatments | Keep a primitive only where it supplies a distinct contract, such as a resource policy or essential semantics |
| Progress | Typed range/value semantics with a presentation | Its accessible value must survive even if its bar, ring, or text appearance changes |
| Menu, popover, dialog | Generic interaction scopes with declared content | They need focus, dismissal, anchoring, and sometimes modality, not application-specific implementations |

This would be a semantic redesign, not just a reduction of the seven existing primitive tags. A composed progress bar is inadequate if it loses its value semantics. A composed button is inadequate if it loses keyboard activation. Demoting a visual treatment is safe only when its nonvisual obligations have another explicit home.

Likewise, native editor values should eventually be typed at the control boundary, with a declared codec into action arguments. The current zoo's numeric/color settings use string fields, including the empty string for inheritance. That is workable compatibility behavior; it should not force every future slider, optional scalar, or color model into the same wire convention. Codec changes must preserve frozen invocation bodies and reject incompatible drafts deliberately.

### What topoi mean in the current system

Here, a *topos* is a presentation of source membership connected to a local selection. The implementation does not supply the category-theoretic structures associated with the mathematical word. Its practical meaning is a place in which members can be encountered and chosen.

Three responsibilities are already separable:

1. A **source** materializes members and evidence about them.
2. A **selection owner** retains the accepted choice and governs attempts to change it.
3. A **topos adapter** arranges members, exposes navigation and focus, and proposes choices.

A follower observes accepted selection and chooses an ordinary presentation for its subject. It does not maintain a competing selected object. A selection can exist without a visible topos, as in the zoo's single-record follower.

The three current renderers are `list`, `list_tree`, and `diagram_tree`. The outline and diagram show a parent relation; the list shows membership sequentially. They share source/member evidence and selection semantics. Changing arrangement should not create a fresh choice authority or discard member work.

The source implementation is more specific than that abstract design. Members are namespace records, with `key` currently equal to `subject` and both spelled as paths. Source and member lifetimes, expected data versions, availability, and read axis travel with membership. Tree projections add parent relations. Structural branches may be focusable and expandable without being available record subjects.

Outline materialization uses bounded child pages, continuation evidence, and a consistent epoch. An unloaded branch is not an empty branch, and a filtered or unloaded member is not a deleted record. The browser adapter allows other topoi sharing that selection to use the materialized source. The egui workspace validator currently admits tree selections and the outline/diagram renderers; the compiler's broader vocabulary should not be mistaken for every consumer's supported set. UIKit's broader renderer specification likewise contains proposals alongside implementation descriptions.

### The design space for topoi

The most useful expansion is to specify **what relation a presentation preserves**, not to accumulate widget names.

| Candidate | Semantic requirement | Arrangement choices | Recommendation |
| --- | --- | --- | --- |
| Collection | Stable membership, order if meaningful, item evidence | List, cards, gallery, wrapping grid | One source family with several arrangements |
| Hierarchy | Parent/child relation, disclosure, partial loading | Outline, tidy tree, breadcrumbs into a rooted hierarchy | First-class topology; retain the existing adapters |
| Table | Row membership and column definitions, typed cells, shared column constraints | Read-only table, editable data grid | Add a table contract; row selection and cell selection must be distinguished |
| Relation graph | Typed edges, edge identity, cycles, repeated targets, bounded traversal | Node-link diagram, adjacency list, relation table | High priority for the linked-text model; do not force it into a tree |
| Text/document extent | Versioned addressable ranges and anchoring | Reader, parallel text, annotated passage | First-class selection/evidence family; it need not start as a collection topos |
| Timeline/calendar | Instants or intervals, ordering, overlap, timezone policy | Timeline, agenda, calendar | Add when temporal placement is domain meaning, not just a date label |
| Spatial scene | Occurrences, geometry, ports, constraints, declared manipulation operations | Patch board, map, diagram editor | Preserve as a distinct scene contract, sharing selection machinery where compatible |
| Grouped board | Membership plus explicit grouping and ordering relations | Kanban, lanes, grouped gallery | Build on collections; moving between groups requires a declared operation |

A tab deck is primarily a set of owned workspaces with suspension and retirement behavior. A modal is an interaction/focus scope. A context menu presents actions. None needs to become a topos merely because it contains multiple visible things.

Search is principally a source operation. Its results can use a list, table, or graph arrangement. Pagination and virtualization are materialization policies. Treating them as source capabilities lets multiple arrangements share them without creating several definitions of “the search results.”

**The hard new distinction is subject versus occurrence.** Suppose one text is cited by two different notes. A graph can show it once with two incoming edges, or a tree projection can show it under both notes. There is one text object but multiple presentation occurrences and relationships. Selecting the text to edit, selecting one citation to remove, and focusing one visible occurrence require different identities.

The current equality `member.key == member.subject` works for a namespace-tree adapter. It should not be baked into a generalized source protocol. A future member might carry a source-local membership key, a subject reference, an occurrence key, and an edge reference. Its capture must say which of those it denotes. Otherwise “remove this citation” can accidentally become “delete this text.”

The same issue appears in tables: a selected cell needs row and column identity, while its editor may write to a slot on the row's subject. An aggregate query row might have no editable subject at all. A source must specify that mapping rather than allowing the client to infer it from labels or position.

### The Torah reader as a test case

The linked-text model already has a useful separation: each chunk has a body; typed relationship slots connect chunks; an anchor identifies the relationship that places a chunk. An unanchored chunk is a standalone tract. Namespace storage location need not be its reading position.

That model calls for several projections of the same facts:

- A library lists unanchored tracts.
- A reader presents a chunk's prepared rich text and accepts exact range selections.
- A margin shows notes anchored to a selected range.
- A backlinks presentation shows incoming citations by relation type.
- A comparison workspace opens two independent readers.
- A relation graph exposes the network across chunks, including incompatible readings.

The margin could use a collection arrangement. The citation network requires graph membership or a declared graph-to-tree projection. The reader's range is neither a record path nor an index into that collection. It needs a document/revision, an offset convention, boundaries, and quotation evidence. The current phrase-selection contract uses versioned documents, half-open UTF-8 ranges, and exact quoted text. A future edit-aware anchoring scheme must explicitly decide how stale ranges relocate; it must not silently reattach a comment to similar words.

“Open a kushya” should remain a domain-declared action or navigation intent on that evidence. Gematria belongs in the selection provider's domain computation. The client should know how to select a text extent, display a prepared overlay, and activate an offered action. It should not know what a kushya or gematria is.

**Proposal:** make range, member, edge, and cell selections typed variants sharing lifecycle machinery. Share intent ordering, guards, capture, and history rules. Keep validation specific to each evidence type. Do not manufacture namespace records for every transient gesture solely to fit a path-only selection API.

### Four possible language architectures

| Architecture | What it makes easy | Main cost |
| --- | --- | --- |
| Expand the current view/pane split | Incremental changes; object views remain usable in labels, rows, and followers | More ad hoc pane-only constructors and behavioral role strings unless output types improve |
| One universal retained element graph | Uniform nesting; any component can introduce state and children | A small summary can secretly allocate a workspace; ownership, recursion, and guards become implicit |
| Server emits a complete scene and all geometry | Consistent whole-screen layout and straightforward replay | Scrolling, virtualization, camera feedback, and platform editing demand local protocols anyway; input latency becomes central |
| Typed output families with explicit interaction requirements | Clear composition boundaries; reusable generic hosts; new topoi without application-specific clients | More work to define interfaces and deliberate bridges between families |

The first is reasonable if the immediate priority is compatibility. The second fits a component-oriented authoring model, but requires an effect or ownership discipline to prevent hidden state from proliferating. The third is attractive for fixed scenes and inspector replay; it is costly as the only model for large interactive workspaces. The fourth is my preferred target, with gradual migration from the first.

Uniform authoring syntax and uniform runtime semantics are separate choices. A single component syntax can still return different typed contracts. Conversely, keeping `@view` and `@pane` does not require maintaining parallel expression evaluators or action systems.

### A proposed boundary for views and panes

The following is a conceptual type sketch, not a proposed parser patch:

```text
View(receiver, presentation context)
  → Surface + interaction requirements

Pane(receiver, explicit ports)
  → Workspace plan

Source(query, revision, cursor)
  → Membership page + relations + completeness evidence

Topos(source reference, selection port, item recipe, arrangement)
  → Collection presentation

Scene(objects, occurrences, geometry, operation bindings)
  → Spatial presentation
```

**Views should emit content, composition, and explicitly described interactions.** Text, images, bounded layout, formatted values, controls, and reusable object projections belong here. Object-local editing remains legal. Links can emit navigation intents for an enclosing host; the view need not own that host's history. A menu or range-selection overlay can be ordinary declared content inside an explicit interaction scope.

**Panes should allocate and connect owners.** Selections, source subscriptions, followers, editor encounters, child panes, decks, route entry points, and host-service bindings belong here. A pane's identity should survive rearrangement. Visual containers such as rows and splits should not accidentally become state owners.

**Separate descriptions from bindings.** A control specifies a value/editing contract and accessible meaning. A binding supplies its permitted invocation or local transition. The same visual button can activate a domain operation, change recipe, or request navigation, but the packet should distinguish those cases. Do not hide authority inside the ordinary paint tree or derive it from a component's name.

**Make composition requirements checkable.** A component that requires `Edit`, `SelectRange`, `Navigate`, or an explicitly supplied selection port should declare those requirements. A parent either supplies the required scope or compilation/admission rejects the composition. This is more precise than saying “views are stateless,” which is false for mounted object editors, or saying “panes may contain everything,” which conceals platform and lifecycle requirements.

There is a real unresolved choice about a topos inside an ordinary view. A small related-items list is attractive inline. But it can introduce source loading, selection, editable member work, and guards. My default would be:

- Permit pure repeated content once the language has a bounded repetition construct.
- Permit an interactive inline topos only through an explicit host/owner attachment with declared ports and scope.
- Reject implicit creation of an independent workspace from a summary or table cell.

This allows reusable “related items” components without making every invocation of `present` an unbounded session constructor.

### Tensions the refactor needs to resolve

**Semantic freedom versus a portable contract.** Application authors should invent roles such as premise, citation, warning, or editorial gloss. Renderers should not need code for each one. However, new behaviors such as editing a matrix or dragging a connection cannot be arbitrary role names. Keep open meanings and styles above typed, versioned interaction capabilities.

**Native feel versus deterministic preparation.** Font metrics, static wrapping, and paint can be shared exactly. Platform editing and focus cannot be reduced to frozen glyphs. Menus, tables, and trees need a declared split between prepared content, allocated regions, and native behavior. A fallback that preserves content but loses keyboard or editing semantics is not full capability support.

**Immediate feedback versus server authority.** A slider should move immediately. Its authoritative Goo preview can follow asynchronously; stale previews must not replace newer state. A graph drag can show a transient local transform, then commit a declared move operation. This is generic speculative feedback, with a defined reconciliation rule. It must not become a second application model in the client.

**Visual hierarchy versus semantic ownership.** Moving a pane into another split should ordinarily preserve its draft. Cloning it should create independent work. The ownership graph should therefore be explicit and separate from the layout tree. Reparenting across an ownership boundary needs a declared transfer policy, not an assumption that an equal key preserves everything.

**Shared objects versus independent editing occurrences.** Two panes displaying the same note might intentionally have separate drafts. Two arrangements of one collection might intentionally share accepted selection. The object address alone cannot decide either policy. Source identity, occurrence identity, editor ownership, and selection ports must each have a purpose.

**Virtualization versus retirement.** A row leaving the viewport must not look like deletion. An unknown save outcome cannot be garbage-collected because its widget was recycled. Large sources need explicit retain/suspend/retire rules and resource bounds; otherwise virtualization exchanges rendering cost for silent loss of work.

**Universal sources versus meaningful capture.** Query results, graph walks, namespace children, and text extents can share pagination machinery, but they cannot share an unqualified “path selected” capture. A query result needs query/revision evidence; an edge needs edge identity; a range needs text revision and boundaries. Generalization should expose these differences rather than erase them.

**Global styling versus behavioral metadata.** The theme editor changes geometry as well as color, so style resolution belongs before measurement. But a style rule must not turn passive text into a slider or grant an invocation. A refactor should distinguish semantic role, style selector, input type, and action binding even if the authoring syntax keeps convenient shorthand.

**Semantic layout versus explicit arrangement.** Goo's ordinary layout derives adjacency from meanings and ordered rules. This gives a common visual grammar across applications, but can make a small role change alter surrounding geometry. Tables, aligned parallel passages, and spatial annotations need relationships that a sequence of sibling affinities may not express. Add explicit constraint-bearing containers where needed, and expose their decisions in the inspector. Do not make authors simulate shared columns with padding or make clients guess the intended relationships from the resulting boxes.

**Extensibility versus reviewable admission.** A new component protocol needs a producer, validator, consumer implementation, unsupported-capability behavior, and fixtures. Arbitrary client plugins would change the trust and distribution model. A smaller generic protocol library is easier to support across egui and UIKit, provided it is expressive enough for actual applications.

### A practical refactor sequence

1. **Classify the existing constructors by output and behavior.** Record which are syntax sugar, surface nodes, binding declarations, owners, arrangement policies, and host capabilities. Reject unsupported mappings during compilation rather than after mounting.
2. **Type the output families.** Keep authoring aliases initially. Introduce explicit surface, workspace, collection, scene, and interaction descriptions, with checked bridges and required capabilities. Preserve current prepared display admission and action evidence.
3. **Extract source and selection contracts.** Keep namespace sources as one implementation. Make subject, membership, occurrence, lifetime, and revision distinct. Keep “not loaded,” “unavailable,” and “deleted” distinguishable.
4. **Move existing topoi onto those contracts.** Demonstrate that outline and diagram can share selection and member work while changing arrangement. Treat current client support as a capability matrix, not an assumption of parity.
5. **Add one relation source and typed text-range selection.** Use the Torah library, reader, anchored margin, and backlinks as the proving application. A graph view should consume declared relationships without any Torah-specific client code.
6. **Add a table only with its full contract.** Define columns, row/cell selection, sorting, virtualization, and editing bindings before choosing the visual widget. Calendar and board variants can follow actual application needs.

The acceptance cases should exercise semantics, not only screenshots: the same subject in two occurrences; changing arrangement with a dirty member editor; a hidden editor receiving a save completion; a removed and recreated subject; a stale range; query pages from different revisions; a refused or superseded transition; and an exact retry after a timeout. Include actual platform keyboard, IME, scrolling, and accessibility behavior for every newly claimed interactive capability.

The criterion for a successful refactor is that a new domain can declare its data, relationships, presentations, and offered operations without adding domain rules to egui or UIKit. A small primitive vocabulary helps only if its contracts can express those distinctions and preserve the user's work.

## Part III — Contract detail and design questions

### Evidence and admission

The following is a compact account of the implementation, not a substitute schema for manufacturing packets.

| Evidence | What it establishes |
| --- | --- |
| Profile revision and font hashes | Which measurement/paint assets a prepared surface used |
| Context: width, text scale, direction | The allocation and environment for which boxes and static lines were prepared |
| Node ID | Identity within a particular prepared surface, used to join paint, semantics, controls, and geometry |
| Declaration control route | Where the offered control lives in the published declaration; distinct from its final painted node ID |
| Receiver/displayed evidence | What was shown and which concrete writable object it refers to |
| Expected data case | Object version required by action admission |
| Publication | Published definitions/catalog basis, distinct from object version and renderer profile |
| Source/member life | Source or object incarnation, independent of normal data edits |
| Selection owner/revision | Accepted local choice at activation, not pending focus or a candidate choice |
| Render ticket | Admission of asynchronous output to a particular generation of work |
| Invocation ID and frozen request | Identity of one attempted operation and exact retry semantics |

An ordinary render and its evidence come from one captured namespace state. A control must join an actually presented node. A stale view may remain visible while its actions are disabled. A replacement is staged when incompatible with dirty work. Accepting a save does not imply that its old submitted value should overwrite edits typed after activation: those newer edits remain dirty against the accepted seed.

A missing receipt means unknown, not rejected. The current development receipt journal records accepted invocations, rejects changed requests reusing an ID, and is bounded. This is not a general promise of forever-retained distributed exactly-once delivery. Current local pending-operation retention is not durable restoration after process death.

### Four different structures

Keep these distinguishable even if the authoring language presents one composition syntax:

1. The namespace structure where records live.
2. The relation structure an application declares, such as citations or anchors.
3. The visual structure arranging content and controls.
4. The ownership/observation structure retaining work and coordinating guards.

A graph-to-tree projection changes structure 3, not necessarily 2. Reordering tabs changes structure 3 without necessarily changing 4. Recreating a record changes its lifetime even when its address in 1 is unchanged. An anchor can place a note in a reader independently of its storage parent.

### Current boundaries easily mistaken for general facilities

- The language's seven primitive variants are not the complete source constructor list. Formatting, composition, action scopes, and workspace nodes have different lowering paths.
- Namespace-record members currently require `key == subject`. General query rows, edges, and repeated occurrences need a new contract; renaming a renderer does not supply it.
- Different clients validate different workspace shapes. The egui Explorer's tree host and its simpler note-deck session are separate paths. The UIKit note-deck validator is not the whole routed-reader implementation.
- Rich-text editing is a display-v3 extension. It does not imply that every renderer implements rich editing. Supported Hebrew is specifically bounded; arbitrary Unicode shaping, niqqud/cantillation, and arbitrary styled bidi paragraphs are not promised.
- Wire protobuf v2 is independent of display v1/v2/v3. Requests remain URL-encoded. Some response families still use JSON. Do not turn the refactor into a generic JSON-inside-protobuf envelope.
- A reusable surface can be interactive without owning a navigation workspace. Input owners are real state even in an ordinary `@view`.
- Menu and preview behavior presently depend partly on specially interpreted roles. This is implementation evidence for making behavior explicit, not an endorsement of treating arbitrary role strings as new capabilities.
- Shared themes apply before ordinary measurement. The zoo edits padding, stroke, fill, and corners by kind/text role. It does not edit arbitrary fonts, native host chrome, or every container constraint.
- The generalization of selection to member/edge/range/cell variants in Part II is a proposal. Existing exact word-range selection uses its own prepared-text evidence and preview protocol.

### What the next agent should resolve

For any proposed architecture, answer these questions concretely. Alternative answers to the essay's recommendation are welcome.

1. What are the output types of views and panes? Which composition edges are legal? What happens when a summary tries to introduce an interactive source or nested owner?
2. Which names are syntax sugar, semantic roles, behavior capabilities, ownership constructs, or layout primitives? Show where `button`, `action`, `input`, `menu`, `table`, `deck`, and `patch` land.
3. What makes a source authoritative about membership? How do paging, filtering, ordering, completeness, and source revision work for a query or graph?
4. What identities represent a subject, source membership, visual occurrence, relation edge, and editor? Which can be shared, cloned, suspended, or retired?
5. How do a selected record, graph edge, cell, and text range differ in their capture and server validation? What does a generic follower consume?
6. Who owns geometry for ordinary text, table columns, graph arrangement, patch manipulation, and overlays? What may respond locally without inventing application semantics?
7. How do declared ports or capability requirements compose? Is `@view` versus `@pane` a useful type boundary, authoring shorthand, or something to remove?
8. How does a domain add a new relation or item view without shipping domain-specific client code? Conversely, what requires a new client capability and version?
9. How do native focus, IME, menus, scrolling, and accessibility work under the proposal? Which semantics must remain available if the visual presentation changes?
10. How do styles affect preparation without changing action authority or input type? What distinguishes a type role, visual role, and style selector?
11. What is retained during refresh, route departure, tab suspension, renderer changes, and materialization changes? Which transitions require a guard?
12. How would the existing Torah and zoo declarations migrate? Mark any new syntax as proposed. Identify compatibility adapters and diagnostics rather than assuming old packets are accepted.

A useful response supplies a minimal type algebra, several concrete declarations, a lifecycle/capture protocol, a capability matrix, and tradeoffs. It should distinguish a design argument from a verified implementation claim.

### Scenarios any replacement must explain

| Scenario | Required outcome |
| --- | --- |
| Same text appears under two citations | Editing text and removing one citation target different identities/operations |
| Dirty record appears in outline and graph | Switching arrangement follows the declared sharing policy and does not accidentally discard work |
| Dirty tab is reordered | Its semantic owner survives |
| Dirty tab is removed and guard refuses | Old usable tree and draft remain |
| A newer navigation intent supersedes a guard | Old guard completion cannot commit the earlier destination |
| A record is deleted and recreated at the same path | Old selection, draft, and authority do not attach to the new incarnation |
| A pending save finishes in a hidden editor | Its originating owner receives the result |
| A save times out after the server commits | Exact retry/status can recover acceptance; no new capture or duplicate semantic action |
| User types more while saving | Acceptance advances the submitted seed without overwriting later edits |
| A tree branch is unloaded | It is not treated as confirmed deletion |
| Query continuation arrives for an old revision | It cannot be merged with a new result set |
| A citation quote occurs twice | Offset/revision evidence selects the correct occurrence; substring search does not |
| An annotation's source text changes | Show unresolved evidence or apply an explicitly defined reattachment operation |
| Input encoding or supported formatting changes | Dirty work is staged behind a guard, not flattened silently |
| An unknown behavior-bearing descriptor arrives | Diagnose or use a declared equivalent fallback before enabling interaction |
| A theme changes padding | Reprepare authoritative geometry; do not merely repaint old boxes |
| A new route is declared in an application | Generic clients consume it without application-specific routing branches |

The following excerpts supply the concrete basis for these questions.

## Part IV — Embedded implementation evidence

### E01 — Records, care scopes, derived data, and role contracts

The record keys are paths used as opaque slots. The same underlying `myth` representation also holds text-run metadata; that does not turn the run descriptor into an action receiver. Care describes observation extent, not screen direction.

Source: `reaver/src/foil/sys/shrine.foil`, lines 1–98. Verbatim snapshot excerpt.

````foil
- sys/types
+  twig
  '  One slot-value pair: the unit a myth is built from.
  :  slot=path =pail
+  myth
  '  The record at a node: slots (paths, used as opaque keys) to
  '  pails.  The unit of state the namespace versions and a behavior
  '  manipulates.  A myth holds a handful of slots, so it is an
  '  ordered map (/mop), not a tree — and a type alias, so the whole
  '  mop method set (get/put/size/uni) applies directly.
  mop[path pail lt_pith]
  +  new
    '  The empty myth.
    ^  myth
    (mop/empty)
  +  sing
    '  The one-slot myth.
    \  slot=path v=pail
    ^  myth
    |  mop/sing[path pail lt_pith] slot v
  +  meld
    '  Union; the add side wins collisions (the default talk law).
    \  add=myth cur=myth
    ^  myth
    cur.uni(add)
  ' TODO: needs wet namespace-modules
  '  +  gett
  '    (@ v)
  '    \ slot=path mit=myth
  '    ^ maybe[v]
  '    mit.get(slot).map(v/try_from_pail)
  +  add
    '  Chain one twig onto a myth: mit.add(twig).
    \  =twig mit=myth
    ^  myth
    mit.put(twig.slot twig.pail)
+  lock
  '  One care's two independent local counters.  Data advances for
  '  every changed version of the care; shape advances only when the
  '  care's live domain changes.  Shape implies data, but is not a
  '  position in the data timeline.
  :  data=nat shape=nat
+  yuga
  '  A node's versioning information: one lock per care, plus the
  '  apollo time and the PKI blockheight at mint.
  :  x=lock
     y=lock
     z=lock
     now=nat
     block=nat
+  oath
  '  Unsigned security scaffolding. Both fields are zero in this port.
  '  Neither authentication nor predecessor-hash semantics are implemented;
  '  this layout is not a network verification contract.
  :  sig=nat prev_hash=nat
+  aeon
  '  Versioning plus security: everything about a committed version
  '  except the record itself.
  :  =yuga =oath
+  saga
  '  The committed version of a node: the aeon and the record.
  '  /sov/step adjusts the yuga as it applies diffs, so historical
  '  case queries are floor lookups, not subtree scans.
  '  The record rides behind a pin: each committed myth is one
  '  content-addressed unit, so snapshotting the sovereign
  '  re-serializes spines, never stored records (global.plan's
  '  small-pins discipline).  Version-only re-mints (ass/next over
  '  the held record) share the old pin verbatim.
  :  =aeon myth=pin[myth]
+  note
  '  One diff: replace the record, merge into it, or retract the
  '  node.  Versioning is the namespace's job — a diff carries none.
  +  make
    :  =myth
  +  poke
    :  =myth
  +  cull
    :
  &  note/make
     note/poke
     note/cull
+  care
  '  Read restriction: the node only (.x), the node plus its frontier
  '  — the nearest record-bearing descendants, transparent paths passing
  '  through (.y) — or the whole subtree (.z).
  &  care/x
     care/y
     care/z

  +  x
    :

  +  y
    :

  +  z
    :
````

Source: `reaver/src/foil/sys/view.foil`, lines 1–40. Verbatim snapshot excerpt.

````foil
- sys/types
- sys/shrine

'  A system module: a kernel upgrade keeps the old compiled sys/* so the
'  brands of the types stored records carry (woven, its stages, the
'  cell protocol below) stay what they were.  Add a type here only when
'  records will store it; a type built only at read time belongs in
'  lain_types, which an upgrade compiles afresh.
+  knit
  ' build structure
  :  get={\ myth}axal[myth] patch=maybe[{\ myth}axal[myth]]
+  felt
  ' delete structure. inverse of +knit
  :  get={\ axal[myth]}myth patch=maybe[{\ axal[myth]}myth]
+  dyed
  ' transform content
  :  get={\ myth}myth patch=maybe[{\ myth}myth]
+  sewn
  ' transform structure
  :  get={\ axal[myth]}axal[myth] patch=maybe[{\ axal[myth]}axal[myth]]
+  spun
  ' transform structure with the view node's own record as the args
  ' channel: the /x lens ctor.  get receives the node's record (its
  ' slots ARE the view's constant args) and the tack target's tree
  ' pinned at y care, and returns the derived tree. /sys/weft holds
  ' this ctor inline or an x-care safe to a ctor record. /sys/tack
  ' holds a y-care safe. The defining datum owns the result case.
  :  get={\ myth axal[myth]}axal[myth]
     patch=maybe[{\ myth axal[myth]}axal[myth]]
+  cell
  ' The cell ctor: get receives the context (the cell's own slots,
  ' secondary inputs as views at ['views <slot>]) and the input tree
  ' the tack names, and returns context' and the data tree.  /x reads
  ' the tree, /c/x the context'; neither is retained.
  :  get={\ myth axal[myth]}[myth axal[myth]]
+  cell_view
  ' A secondary input handed to a spun ctor: the tree a reference slot
  ' of the cell named, pinned, placed at ['views <slot>] in the record
  ' the ctor receives.
  :  tree=pin[axal[myth]]
````

Source: `reaver/src/foil/grove_role_runtime.foil`, lines 1–32. Verbatim snapshot excerpt.

````foil
- system_vocabulary
- lain_types
'  Stored, source-independent role shape. Codecs live in module exports.
+ grove_role_field
  : name=str slot=path optional=bool
+ grove_role_schema
  : fields=row[grove_role_field] need=row[row[path]]
+ grove_role_runtime
  + present
    \ need=row[row[path]] card=myth
    ^ bool
    | need.all
    \ group
    | group.any (\ slot card.has(slot))
  + spec
    \ fields=row[[path curb]] need=row[row[path]]
    ^ lash
    = types=curbs
        | fields.fold (mop/empty)
        \ out [slot type]
        | out.put slot type
    | lash types types need 0 0

+ grove_view_constants
  : values=myth

+ grove_action_handler
  : apply={\ myth myth}maybe[myth]

+ grove_action_schema
  : receiver=path arguments=grove_role_schema
````

### E02 — Authoring selection and constructor admission

This is the actual frontend boundary. The `topos` predicate has three renderer spellings. `scope_validate` forbids the listed constructs in ordinary views. The broader constructor allowlist is followed by later preparation mappings; acceptance here alone does not establish runtime support.

Source: `reaver/src/foil/grove_views.foil`, lines 231–240. Verbatim snapshot excerpt.

````foil
  + select
    \ context=grove_views/context role=path slot=path span=rex/source_span
    ^ either[grove/error goo/view]
    = matches
        | context.views.keep (\ view (and !(view.is_pane) (and (equal view.role role) (equal view.slot slot))))
    ? (eq matches.len 0)
      | goo/fail[goo/view] span "Missing view for role and slot; reflection fallback is not implemented."
    ? !(eq matches.len 1)
      | goo/fail[goo/view] span "Competing views for role and slot; precedence is not defined."
    | ./ok matches.at(0)
````

Source: `reaver/src/foil/grove_views.foil`, lines 274–324. Verbatim snapshot excerpt.

````foil
  + topos
    \ kind=str
    ^ bool
    | ((eq kind "list") || (eq kind "diagram_tree") || (eq kind "list_tree"))
  + local_validate
    \ context=grove_views/context view=goo/view node=goo/node
    ^ either[grove/error unit]
    = keyed=row[str] ["patch" "patch_node" "patch_port" "patch_connection" "patch_label" "patch_handle" "patch_operation" "pane" "selection" "list" "diagram_tree" "list_tree" "follow" "deck" "navigate" "operation" "operation_status"]
      leaf=row[str] ["list" "diagram_tree" "list_tree" "follow" "navigate" "operation" "operation_status"]
    ? !(keyed.has(node.constructor)) (./ok [])
    ? (eq node.arguments.len 0) (goo/fail[unit] node.span "Local declarations require a stable literal key.")
    ? !(grove_views/local_key node.arguments.head) (goo/fail[unit] node.span "Local keys must be path or text literals.")
    ? (and (leaf.has(node.constructor)) (gt node.children.len 0))
      | goo/fail[unit] node.span "list/follow use a slot-selected presentation; explicit bodies are not supported."
    ? (eq node.constructor "patch")
      ?> (./some scene) (grove_views/local_named "scene" node) (goo/fail[unit] node.span "patch requires a server-resolved scene field.")
      < type (grove_views/expression_type context view scene)
      ? !(context.renderers.any((\ renderer (and (equal renderer.type type) (eq renderer.constructor "text")))))
        | goo/fail[unit] node.span "patch scene must contain JSON text."
      | ./ok []
    ? (eq node.constructor "patch_operation")
      ?> (./some slot) (grove_views/local_named "slot" node) (goo/fail[unit] node.span "patch_operation requires its declared input slot.")
      < resolved (grove_views/reference context.root context.document context.lookup slot)
      | ./ok []
    ? (eq node.constructor "navigate")
      ?> (./some value) (grove_views/local_named "source" node) (goo/fail[unit] node.span "navigate requires a path source.")
      | grove_views/source_validate context view value
    ? ((eq node.constructor "operation") || (eq node.constructor "operation_status"))
      ?> (./some value) (grove_views/local_named "operation" node) (goo/fail[unit] node.span "Host controls require an operation key.")
      ? !(grove_views/local_key value) (goo/fail[unit] node.span "Operation keys must be literals.")
      | ./ok []
    = source=bool ((eq node.constructor "selection") || (grove_views/topos node.constructor))
    ? source
      ?> (./some value) (grove_views/local_named "source" node) (goo/fail[unit] node.span "selection/list require source = namespace path.")
      < valid (grove_views/source_validate context view value)
      ? (eq node.constructor "selection")
        = axis (grove_views/local_named "axis" node).fall((rex/cord "z"))
        ? !((eq axis.print (rex/cord "x").print) || ((eq axis.print (rex/cord "y").print) || (eq axis.print (rex/cord "z").print)))
          | goo/fail[unit] node.span "Selection axis must be x, y, or z."
        ?> (./some topology) (grove_views/local_named "topology" node) (./ok [])
        ? !((eq topology.print (rex/cord "tree").print) || (eq topology.print (rex/cord "children").print))
          | goo/fail[unit] node.span "Selection topology must be tree or children."
        | ./ok []
      ?> (./some port) (grove_views/local_named "selection" node) (goo/fail[unit] node.span "list requires a selection port.")
      ? !(grove_views/local_key port) (goo/fail[unit] node.span "Selection port must name a local key.")
      (./ok [])
    ? (eq node.constructor "follow")
      ?> (./some port) (grove_views/local_named "selection" node) (goo/fail[unit] node.span "follow requires a selection observation.")
      ? !(grove_views/local_key port) (goo/fail[unit] node.span "Selection observation must name a local key.")
      (./ok [])
    | ./ok []
````

Source: `reaver/src/foil/grove_views.foil`, lines 355–423. Verbatim snapshot excerpt.

````foil
  + scope_validate
    \ view=goo/view node=goo/node
    ^ either[grove/error unit]
    ? view.is_pane (./ok [])
    = exclusive=row[str] ["patch" "patch_node" "patch_port" "patch_connection" "patch_label" "patch_handle" "patch_operation" "pane" "_pane_instance" "selection" "list" "diagram_tree" "list_tree" "follow" "split" "deck" "pane_stack" "navigate" "operation" "operation_status"]
    ? (exclusive.has(node.constructor))
      | goo/fail[unit] node.span "Pane controls require @pane; @view is an object projection."
    ? (node.arguments.any(grove_views/captures))
      | goo/fail[unit] node.span "Selection capture requires @pane."
    | ./ok []
  + lower_nodes
    \ context=grove_views/context stack=list[path] view=goo/view nodes=list[goo/node]
    ^ either[grove/error list[goo/node]]
    ? (eq nodes.len 0) (./ok .nil)
    < head (grove_views/lower_node context stack view nodes.at(0))
    < tail (grove_views/lower_nodes context stack view nodes.drop(1))
    | ./ok tail.cons(head)
  + lower_node
    \ context=grove_views/context stack=list[path] view=goo/view node=goo/node
    ^ either[grove/error goo/node]
    < scope (grove_views/scope_validate view node)
    ? (eq node.constructor "_pane_instance") (./ok node.set_constructor("pane"))
    ? (eq node.constructor "pane")
      | goo/fail[goo/node] node.span "Use pane(declaration); inline pane bodies are not supported."
    ? (eq node.constructor "path")
      ? ((eq node.arguments.len 0) || (gt node.arguments.len 2) || (gt node.children.len 0))
        | goo/fail[goo/node] node.span "path requires a receiver or path value, an optional slot, and no children."
      = args (node.arguments.map((grove_views/interaction_reference context)))
        value args.head
        receiver=bool
          ?> (./leaf _ _ name) value .false
          | (and (equal value.leaf_kind (maybe/some[str] "word")) (eq name view.binding))
      ? !receiver
        < renderer (grove_views/renderer context view value)
        ? !(eq renderer "link")
          | goo/fail[goo/node] value.span "path requires a receiver or path-typed value."
        ? (eq args.len 2)
          < slot (grove_views/reference context.root context.document context.lookup args.at(1))
          | ./ok node.set_arguments(args)
        | ./ok node.set_arguments(args)
      ? (eq args.len 2)
        < slot (grove_views/reference context.root context.document context.lookup args.at(1))
        | ./ok node.set_arguments(args)
      | ./ok node.set_arguments(args)
    ? ((eq node.constructor "show") || (eq node.constructor "present"))
      ? !(and (eq node.arguments.len 2) (eq node.children.len 0))
        | goo/fail[goo/node] node.span "show/present require a value and slot, with no explicit children."
      = value node.arguments.at(0)
      < slot (grove_views/reference context.root context.document context.lookup node.arguments.at(1))
      ? (eq node.constructor "show")
        < constructor (grove_views/renderer context view value)
        | ./ok node.set_constructor(constructor)
      < role (grove_views/expression_type context view value)
      < target (grove_views/select context role slot node.span)
      ? stack.has(target.name)
        | goo/fail[goo/node] node.span "Cyclic view presentation."
      < children (grove_views/lower_nodes context stack.snoc(target.name) target target.children)
      | ./ok node.set_children(children.map((goo/bind_node target.binding value)))
    = constructors=row[str]
        ["group" "or" "action" "input" "text" "link" "number"
         "time" "duration" "boolean" "image" "icon" "divider"
         "patch" "patch_node" "patch_port" "patch_connection" "patch_label" "patch_handle" "patch_operation" "pane" "selection" "list" "diagram_tree" "list_tree" "follow" "split" "deck" "pane_stack" "navigate" "operation" "operation_status"
         "row" "col" "flow" "stack" "opt" "button" "code" "avatar" "presence" "media" "bar"]
    ? !(constructors.has(node.constructor))
      | goo/fail[goo/node] node.span "Unknown Goo constructor."
    < creation (grove_views/make_validate context view node)
    < valid (grove_views/local_validate context view node)
    < children (grove_views/lower_nodes context stack view node.children)
    | ./ok node.set_children(children).set_arguments(node.arguments.map((grove_views/interaction_reference context)))
````

Source: `reaver/src/foil/grove_views.foil`, lines 564–637. Verbatim snapshot excerpt.

````foil
  + pane_instance
    \ context=grove_views/context stack=list[path] view=goo/view env=list[[path path]] key=path prefix=path
    ^ either[grove/error goo/node]
    < composed (grove_views/compose_nodes context stack view env prefix view.children)
    < children (grove_views/lower_nodes context stack view composed)
    = keys (grove_views/pane_children_keys children)
    ? (keys.any((\ key (gt (keys.keep((\ other (equal key other)))).len 1))))
      | goo/fail[goo/node] view.span "Repeated pane declaration requires distinct instance keys."
    | ./ok (goo/node view.span "_pane_instance" (list/one (grove_views/path_literal key)) children)
  + compose_nodes
    \ context=grove_views/context stack=list[path] view=goo/view env=list[[path path]] prefix=path nodes=list[goo/node]
    ^ either[grove/error list[goo/node]]
    ? nodes.is_nil (./ok .nil)
    < head (grove_views/compose_node context stack view env prefix nodes.head)
    < tail (grove_views/compose_nodes context stack view env prefix nodes.tail)
    | ./ok tail.cons(head)
  + compose_node
    \ context=grove_views/context stack=list[path] view=goo/view env=list[[path path]] prefix=path node=goo/node
    ^ either[grove/error goo/node]
    ? (eq node.constructor "_pane_instance")
      | goo/fail[goo/node] node.span "Reserved pane constructor."
    ? (eq node.constructor "pane")
      ? ((eq node.arguments.len 0) || (gt node.children.len 0))
        | goo/fail[goo/node] node.span "Use pane(declaration); inline pane bodies are not supported."
      < _ (grove_views/pane_arguments node)
      < name (grove_views/reference context.root context.document context.lookup node.arguments.head)
      = matches (context.views.keep((\ pane (and pane.is_pane (equal pane.name name)))))
      ? !(eq matches.len 1)
        | goo/fail[goo/node] node.span "pane requires an @pane declaration."
      = target matches.head
      ? stack.has(name) (goo/fail[goo/node] node.span "Cyclic pane composition.")
      = receiver (grove_views/local_named "on" node).fall((rex/word view.binding))
      ? !(eq receiver.print view.binding)
        | goo/fail[goo/node] node.span "Pane composition currently requires the current receiver."
      ? !(equal target.role view.role)
        | goo/fail[goo/node] node.span "Pane receiver role must match its declaration."
      < bindings (grove_views/port_bindings context target env node)
      = explicit (grove_views/local_named "key" node)
      = key=either[grove/error path]
          ? explicit
           > (./some value)
            < local (grove_views/local_path value)
            | ./ok name.snoc('instance).weld(local)
          | ./ok name
      < key key
      < pane (grove_views/pane_instance context stack.snoc(name) target bindings key prefix.snoc(($x key.len)).weld(key))
      | ./ok (goo/bind_node target.binding receiver pane)
    = nested=either[grove/error list[[path path]]]
        ? !(eq node.constructor "selection") (./ok env)
        ? (eq node.arguments.len 0) (goo/fail[list[[path path]]] node.span "Selection requires a local key.")
        < local (grove_views/local_path node.arguments.head)
        | ./ok env.cons([local prefix.snoc('selection).weld(local)])
    < nested nested
    < arguments (grove_views/port_expressions nested node.arguments)
    = mapped=either[grove/error list[rex]]
        ? (eq node.constructor "selection")
          < local (grove_views/local_path node.arguments.head)
          < actual (grove_views/port_lookup nested local node.span)
          | ./ok arguments.tail.cons((grove_views/path_literal actual))
        ? ((grove_views/topos node.constructor) || (eq node.constructor "follow"))
          ?> (./some port) (grove_views/local_named "selection" node) (goo/fail[list[rex]] node.span "list/follow require a selection port.")
          < local (grove_views/local_path port)
          < actual (grove_views/port_lookup env local node.span)
          = rewrite
              \ argument=rex
              ^ rex
              ? (maybe/is_some (grove_views/local_named "selection" node.set_arguments((list/one argument))))
                | rex/rune "=" [(rex/word "selection") (grove_views/path_literal actual)]
              argument
          | ./ok arguments.map(rewrite)
        | ./ok arguments
    < arguments mapped
    < children (grove_views/compose_nodes context stack view nested prefix node.children)
    | ./ok node.set_arguments(arguments).set_children(children)
````

### E03 — Narrow surface types and rich text

These excerpts show the closed primitive family, source/semantic phase distinction, optional style fields, and the run descriptor. The source/core/normalized/visible/semantic phases are distinct nominal types; the omitted intervening phases are not aliases or permission to cast across phases. `goo/lang/en` is the current carrier variant; its name does not imply broad multilingual rendering support.

Source: `reaver/extras/mounts/goo/types.foil`, lines 115–201. Verbatim snapshot excerpt.

````foil
  + primitive_kind
    & goo/primitive_kind/button goo/primitive_kind/input goo/primitive_kind/code goo/primitive_kind/avatar goo/primitive_kind/presence goo/primitive_kind/media goo/primitive_kind/bar
    + button
      :
    + input
      :
    + code
      :
    + avatar
      :
    + presence
      :
    + media
      :
    + bar
      :
    + name
      \ value=goo/primitive_kind
      ^ str
      ? value
       > ./button "button"
       > ./input "input"
       > ./code "code"
       > ./avatar "avatar"
       > ./presence "presence"
       > ./media "media"
       > ./bar "bar"
    + parse
      \ text=str
      ^ maybe[goo/primitive_kind]
      ? (eq text "button") (./some (goo/primitive_kind/button))
      ? (eq text "input") (./some (goo/primitive_kind/input))
      ? (eq text "code") (./some (goo/primitive_kind/code))
      ? (eq text "avatar") (./some (goo/primitive_kind/avatar))
      ? (eq text "presence") (./some (goo/primitive_kind/presence))
      ? (eq text "media") (./some (goo/primitive_kind/media))
      ? (eq text "bar") (./some (goo/primitive_kind/bar))
      .none
  + primitive
    & goo/primitive/button goo/primitive/input goo/primitive/code goo/primitive/avatar goo/primitive/presence goo/primitive/media goo/primitive/bar
    + button
      : text=goo/text
    + input
      : text=goo/text
    + code
      : text=goo/text
    + avatar
      : text=goo/text
    + presence
      : text=goo/text
    + media
      : text=goo/text
    + bar
      : text=goo/text
    + kind
      \ value=goo/primitive
      ^ goo/primitive_kind
      ? value
       > (./button _) (goo/primitive_kind/button)
       > (./input _) (goo/primitive_kind/input)
       > (./code _) (goo/primitive_kind/code)
       > (./avatar _) (goo/primitive_kind/avatar)
       > (./presence _) (goo/primitive_kind/presence)
       > (./media _) (goo/primitive_kind/media)
       > (./bar _) (goo/primitive_kind/bar)
    + payload
      \ value=goo/primitive
      ^ goo/text
      ? value
       > (./button text) text
       > (./input text) text
       > (./code text) text
       > (./avatar text) text
       > (./presence text) text
       > (./media text) text
       > (./bar text) text
    + make
      \ kind=goo/primitive_kind text=goo/text
      ^ goo/primitive
      ? kind
       > ./button (goo/primitive/button text)
       > ./input (goo/primitive/input text)
       > ./code (goo/primitive/code text)
       > ./avatar (goo/primitive/avatar text)
       > ./presence (goo/primitive/presence text)
       > ./media (goo/primitive/media text)
       > ./bar (goo/primitive/bar text)
````

Source: `reaver/extras/mounts/goo/types.foil`, lines 202–277. Verbatim snapshot excerpt.

````foil
  + design
    ' Optional logical CSS pixels per side and opaque sRGB colors.
    : pad_x=maybe[nat] pad_y=maybe[nat] stroke=maybe[nat] edge=maybe[str] fill=maybe[str] radius=maybe[nat]
    + empty
      ^ goo/design
      | goo/design .none .none .none .none .none .none
    + color
      \ s=str
      ^ bool
      ? !(and (eq s.len 7) (eq s.at(0) 35)) .false
      | (list/range 1 7).all
        \ i=nat
        = c s.at(i)
        | ((and (ge c 48) (le c 57)) || (and (ge c 65) (le c 70)) || (and (ge c 97) (le c 102)))
    + valid
      \ d=goo/design
      ^ bool
      | and (and (le d.pad_x.fall(0) 96) (le d.pad_y.fall(0) 96))
          (and (and (le d.stroke.fall(0) 12) (le d.radius.fall(0) 48))
            (and (goo/design/color d.fill.fall("#000000")) (goo/design/color d.edge.fall("#000000"))))
  + config
    : grow=maybe[bool] max_ideal=maybe[goo/scalar]
      primary=maybe[bool] toggle=maybe[bool]
      label=maybe[str] option_label=maybe[str]
      value=maybe[goo/scalar] max=maybe[goo/scalar]
      design=goo/design
    + empty
      ^ goo/config
      | goo/config .none .none .none .none .none .none .none .none goo/design/empty
  + common
    : slot=goo/slot optional=goo/rank config=goo/config origin=maybe[goo/loc]
  + edge
    : left=goo/slot right=goo/slot left_id=goo/node_id right_id=goo/node_id
      bind=goo/affinity rule=maybe[nat] source=goo/edge_source
      parent=goo/node_id parent_slot=goo/slot
  + compile_context
    : view_path=goo/path
  + render_options
    : optional_budget=goo/rank hidden_ids=list[goo/node_id]
      hidden_paths=list[list[nat]] uniform_edges=bool
  + compile_request
    : context=goo/compile_context options=goo/render_options
  + source_attrs
    : common=goo/common
  + source
    & goo/source/text goo/source/image goo/source/jet goo/source/flow goo/source/group goo/source/opt
    + text
      : attrs=goo/source_attrs value=goo/text
    + image
      : attrs=goo/source_attrs value=str
    + jet
      : attrs=goo/source_attrs primitive=goo/primitive
    + flow
      : attrs=goo/source_attrs direction=goo/direction kids=list[goo/source]
    + group
      : attrs=goo/source_attrs kids=list[goo/source]
    + opt
      : attrs=goo/source_attrs rank=goo/rank kids=list[goo/source]
    + attrs
      \ tree=goo/source
      ^ goo/source_attrs
      ? tree
       > (./text a _) a
       > (./image a _) a
       > (./jet a _) a
       > (./flow a _ _) a
       > (./group a _) a
       > (./opt a _ _) a
    + children
      \ tree=goo/source
      ^ list[goo/source]
      ? tree
       > (./flow _ _ kids) kids
       > (./group _ kids) kids
       > (./opt _ _ kids) kids
      .nil
````

Source: `reaver/extras/mounts/goo/types.foil`, lines 364–397. Verbatim snapshot excerpt.

````foil
  + semantic_attrs
    : common=goo/common node_id=goo/node_id after=maybe[goo/edge]
  + semantic
    & goo/semantic/text goo/semantic/image goo/semantic/jet goo/semantic/flow
    + text
      : attrs=goo/semantic_attrs value=goo/text
    + image
      : attrs=goo/semantic_attrs value=str
    + jet
      : attrs=goo/semantic_attrs primitive=goo/primitive
    + flow
      : attrs=goo/semantic_attrs direction=goo/direction kids=list[goo/semantic]
    + attrs
      \ tree=goo/semantic
      ^ goo/semantic_attrs
      ? tree
       > (./text a _) a
       > (./image a _) a
       > (./jet a _) a
       > (./flow a _ _) a
    + children
      \ tree=goo/semantic
      ^ list[goo/semantic]
      ? tree
       > (./flow _ _ kids) kids
      .nil
    + node_id
      \ tree=goo/semantic
      ^ goo/node_id
      tree.attrs.node_id
    + after
      \ tree=goo/semantic
      ^ maybe[goo/edge]
      tree.attrs.after
````

Source: `reaver/extras/mounts/goo/text.foil`, lines 1–61. Verbatim snapshot excerpt.

````foil
- json
- sys/shrine

+ modifiers
  & modifiers/italic modifiers/bold modifiers/underline
  + italic
    :
  + bold
    :
  + underline
    :
+ pails
  + modifiers
    : values=list[modifiers]
+ weblink
  : href=str

' The run myth contains metadata; carrying it grants no action authority.
+ goo
  + lang
    & goo/lang/en
    + en
      : txt=str
    + txt
      \ value=goo/lang
      ^ str
      | goo/lang/en/txt value
  + runt
    : =myth lang=goo/lang
  + text
    row[goo/runt]
    + pail
      : value=goo/text
    + en
      \ txt=str
      ^ goo/text
      [(goo/runt myth/new (goo/lang/en txt))]
    + plain
      \ value=goo/text
      ^ str
      | str/cat_all value.map((\ run=goo/runt run.lang.txt))
    + slice
      ' Byte ranges; the current ASCII measurer supplies valid boundaries.
      ' Preserve descriptors and run order, including when cutting within a run.
      \ start=nat length=nat value=goo/text
      ^ goo/text
      % i=nat 0 offset=nat 0 out=list[goo/runt] .nil
      ? (eq i value.len) out.reverse.row
      = run value.at(i)
        txt run.lang.txt
        left (? (gt start offset) start offset)
        end (add start length)
        boundary (add offset txt.len)
        right (? (lt end boundary) end boundary)
        next (? (lt left right) out.cons((goo/runt run.myth (goo/lang/en txt.slice((sub left offset) (sub right left))))) out)
      | _ i.inc (add offset txt.len) next
    + supported
      \ value=goo/text
      ^ bool
      | row/all[goo/runt] (\ run (goo_text/descriptor_valid run.myth)) value
````

### E04 — Ordinary lowering and the compiler passes

`node` binds values and reduces formatting spellings to ordinary content. Action authority is discovered separately from the visual primitive. `compile_source` applies the theme before measurement; the captured stages are the ones used by that preparation.

Source: `reaver/extras/mounts/explorer/goo_bridge.foil`, lines 231–351. Verbatim snapshot excerpt.

````foil
  + node
    \ published=goo/published card=myth node=goo/node
    ^ either[str list[goo/source]]
    = kind node.constructor
      args node.arguments.map(goo_bridge/surface)
      style (goo_runtime/named "style" args)
      args (args.keep((\ arg (maybe/is_none (goo_runtime/named "style" (list/one arg))))))
      ' A bound input keeps its slot first for control discovery and activation.
      args=list[rex]
        ? !(and (eq kind "input") (eq args.len 3)) args
        ? !(goo_read/record args.at(2)) args
        | args.take(2).cons(args.at(2))
      has_config=bool (? args.len (goo_read/record args.at(0)) .false)
      config=either[str goo/config]
        ? !has_config (./ok goo/config/empty)
        ?> (./ok fields) (goo_read/config args.at(0))
          | ./err "Invalid Goo v2 configuration record."
        ?> (./some config) (goo_codec/config fields)
          | ./err "Invalid Goo v2 configuration values."
        | ./ok config
      args=list[rex] (? has_config args.drop(1) args)
    < config config
    = styled=either[str goo/config]
        ?> (./some expr) style (./ok config)
        ? !((eq kind "text") || (eq kind "code") || (eq kind "button"))
          | ./err "style requires a text, code, or button specimen."
        ?> (./some value) (goo_bridge/value published card expr) (./err "Missing style field.")
        ?> design=goo/design value (./err "Expected a Goo design value.")
        ? !(goo/design/valid design) (./err "Style dimensions or colors are out of range.")
        | ./ok config.set_design(design)
    < config styled
    ? (eq kind "or")
      % rest=list[goo/node] node.children
      ^ either[str list[goo/source]]
      ? (eq rest.len 0) (./ok .nil)
      < child (goo_bridge/node published card rest.at(0))
      ? child.len (./ok child)
      | _ rest.drop(1)
    ? (eq kind "present")
      < children (goo_bridge/nodes published card node.children)
      < slot (goo_bridge/slot published card args.at(1))
      | ./ok (list/one (goo/source/group (goo_bridge/attrs node.span slot config) children))
    = containers=row[str] ["group" "row" "col" "flow" "stack" "opt"]
    ? containers.has(kind)
      = children=list[goo/node]
          ? (maybe/is_none (goo_runtime/named "make" node.arguments)) node.children
          = fields (goo_runtime/named "myth" node.arguments).run(goo_runtime/fields).fall(.nil)
          | goo_bridge/creation_inputs fields node.children
      < children (goo_bridge/nodes published card children)
      = slot=either[str str]
          ? ((eq kind "opt") || (eq args.len 0)) (./ok kind)
          ? (and (eq kind "group") (goo_bridge/named args.at(0))) (./ok kind)
          | goo_bridge/slot published card args.at(0)
      < slot slot
      = attrs (goo_bridge/attrs node.span slot config)
      ? (eq kind "opt")
        = rank=maybe[goo/rank]
            ? (eq args.len 0) (./some (goo/rank/compact))
            ?> (./ok number) (goo_read/scalar args.at(0)) .none
            | goo_codec/rank number
        ?> (./some rank) rank (./err "opt requires rank 1 or 2.")
        ? (eq rank.to_nat 0) (./err "opt requires rank 1 or 2.")
        | ./ok (list/one (goo/source/opt attrs rank children))
      ? (eq kind "group") (./ok (list/one (goo/source/group attrs children)))
      = direction=goo/direction
          ? ((eq kind "col") || (eq kind "stack")) (goo/direction/col)
          (goo/direction/row)
      | ./ok (list/one (goo/source/flow attrs direction children))
    ? (eq kind "input")
      ? ((eq args.len 0) || (gt args.len 2)) (./err "input requires a value or slot path, with an optional role.")
      ?> (./some held) (goo_bridge/value published card args.at(0))
        | ./err "input requires a literal value or absolute slot path."
      = content=either[str goo/text]
          ? held
           > slot=pails/p
            ? card.get(slot.p)
             > (./some value) (goo_bridge/formatted_runs "text" value)
             > ./none (./ok (goo/text/en ""))
           > value=pails/t (./ok (goo/text/en value.t))
          | ./err "input requires a literal value or absolute slot path."
        role=either[str str]
          ? (eq args.len 1) (./ok "input")
          | goo_bridge/slot published card args.at(1)
      < content content
      < role role
      = rich=bool
          ?> slot=pails/p held .false
          ?> (./some value) card.get(slot.p) .false
          ?> value=goo/text/pail value .false
          .true
      ? (and rich ((eq role "slider") || (eq role "colorwell"))) (./err "A native value input requires a plain string slot.")
      | ./ok (list/one (goo/source/jet (goo_bridge/attrs node.span (? rich "rich-input" role) config) (goo/primitive/input content)))
    ? (eq kind "path")
      ? (has_config || (eq args.len 0) || (gt args.len 2) || (gt node.children.len 0))
        | ./err "path requires a receiver or path value, an optional slot, and no children."
      < value (goo_bridge/evaluate published card args.head)
      ?> (./some value) value (./ok .nil)
      ?> value=pails/p value (./err "path requires a path-typed value.")
      = slot=either[str str]
          ? (eq args.len 1) (./ok "body")
          | goo_bridge/slot published card args.at(1)
      < slot slot
      | ./ok (list/one (goo_bridge/path_source node.span slot config value.p))
    = scalars=row[str] ["text" "link" "number" "time" "duration" "boolean"]
      primitive (goo/primitive_kind/parse (? (eq kind "action") "button" kind))
    ? !((scalars.has(kind)) || ((eq kind "image") || (maybe/is_some primitive)))
      | ./err (str/cat_all ["No Goo v2 constructor mapping for " kind "."])
    ? (eq args.len 0) (./err "Goo leaf requires a value.")
    < evaluated (goo_bridge/evaluate published card args.at(0))
    ?> (./some value) evaluated (./ok .nil)
    < text (goo_bridge/formatted_runs kind value)
    = slot=either[str str]
        ? ((eq kind "action") || (eq args.len 1))
          | ./ok (? (maybe/is_some primitive) (? (eq kind "action") "action" kind) "body")
        | goo_bridge/slot published card args.at(1)
    < slot slot
    = attrs (goo_bridge/attrs node.span slot config)
    ? (eq kind "image") (./ok (list/one (goo/source/image attrs text.plain)))
    ? primitive
     > (./some primitive) (./ok (list/one (goo/source/jet attrs (goo/primitive/make primitive text))))
     > ./none (./ok (list/one (goo/source/text attrs text)))
````

Source: `reaver/extras/mounts/explorer/goo_bridge.foil`, lines 381–410. Verbatim snapshot excerpt.

````foil
  + compile_source
    ' Capture the same pass values used by this preparation, only when requested.
    \ context=goo_bridge/render_context source=goo/source prefix=str slot=path
    ^ either[str goo_bridge/compilation]
    ?> (./ok core) (goo_pass/normalize source)
      | ./err "Unable to normalize Goo v2 source."
    = ids (list/range 0 (goo_pass/count core)).map((\ i (goo/node_id
        (str/cat_all [prefix ":" (nat/show i)]))))
      normalized (goo_pass/assign core ids 0).tree
      options (goo_pass/options (goo_bridge/context slot))
      visible (goo_pass/visibility options normalized)
      semantic (goo_compile/semantic .false visible)
      semantic=maybe[goo/semantic]
        ? (eq context.theme.size 0) semantic
        | semantic.run((goo_theme/apply context.theme))
    < prepared (goo_html/prepare semantic context.width context.scale context.rtl)
    = stages=row[json]
        ? !(context.pipeline) []
        [(goo_inspect/stage "parse" "skipped" jnull [])
         (goo_inspect/stage "read" "skipped" jnull [])
         (goo_inspect/stage "source" "ok" (goo_inspect/source source) [])
         (goo_inspect/stage "core" "ok" (goo_inspect/core core) [])
         (goo_inspect/stage "normalized" "ok" (goo_inspect/normalized normalized) [])
         (goo_inspect/stage "visible" "ok" (goo_codec/optional_json[goo/visible] goo_inspect/visible visible) [])
         (goo_measure/stage prepared.measurement.value "semantic")
         (goo_measure/stage prepared.measurement.value "metrics")
         (goo_measure/stage prepared.measurement.value "layout")
         (goo_measure/stage prepared.measurement.value "trace")
         (goo_inspect/stage "prepared" "ok" (goo_html/inspect prepared) [])]
    | ./ok (goo_bridge/compilation prepared stages)
````

Source: `reaver/extras/mounts/explorer/goo_theme.foil`, lines 1–72. Verbatim snapshot excerpt.

````foil
- goo_runtime
- goo_app/ascii

' World-owned defaults layered over the immutable Mash font and geometry profile.
+ goo_theme
  + rules
    mop[path goo/design lt_pith]
  + root
    \ self=iota
    ^ path
    [self 'app 'goo_theme]
  + binding
    ^ path
    ['sys 'goo 'theme_design_slot]
  + design
    \ card=myth
    ^ maybe[goo/design]
    < held card.get(goo_theme/binding)
    ?> ref=pails/p held .none
    < held card.get(ref.p)
    ?> d=goo/design held .none
    ? !(goo/design/valid d) .none
    | ./some d
  + published
    \ state=namespace
    ^ goo_theme/rules
    = tree (sovereign_care .y (goo_theme/root state.self) state)
    | tree.kid_tap.fold (mop/empty)
      \ rules=goo_theme/rules [key child]
      ?> (./some card) child.fil rules
      ?> (./some d) (goo_theme/design card) rules
      ? (equal[goo/design] d goo/design/empty) rules
      | rules.put([key] d)
  + projected
    ' Only a direct child of the reserved theme root may preview a rule.
    \ rules=goo_theme/rules self=iota target=path card=myth
    ^ goo_theme/rules
    = root (goo_theme/root self)
    ? !(and (eq target.len root.len.inc) (equal[path] target.take(root.len) root)) rules
    ?> (./some d) (goo_theme/design card) rules
    | rules.put([target.at(root.len)] d)
  + inherit
    \ base=goo/design own=goo/design
    ^ goo/design
    | goo/design
      (? own.pad_x.is_some own.pad_x base.pad_x)
      (? own.pad_y.is_some own.pad_y base.pad_y)
      (? own.stroke.is_some own.stroke base.stroke)
      (? own.edge.is_some own.edge base.edge)
      (? own.fill.is_some own.fill base.fill)
      (? own.radius.is_some own.radius base.radius)
  + apply
    \ rules=goo_theme/rules node=goo/semantic
    ^ goo/semantic
    ? node
     > (./flow a dir kids) (goo/semantic/flow a dir kids.map((goo_theme/apply rules)))
    = kind (goo_ascii/kind node)
    ? !((eq kind "text") || (eq kind "button") || (eq kind "code") || (eq kind "input")) node
    = base rules.get([($ts kind)]).fall(goo/design/empty)
      role (goo_ascii/role node)
      base=goo/design
        ? !(eq kind "text") base
        ?> (./some d) rules.get([($ts (str/cat_all ["text_" role]))]) base
        | goo_theme/inherit base d
    ? (equal[goo/design] base goo/design/empty) node
    = attrs node.attrs config attrs.common.config
      design (goo_theme/inherit base config.design)
      attrs attrs.set_common(attrs.common.set_config(config.set_design(design)))
    ? node
     > (./text _ text) (goo/semantic/text attrs text)
     > (./jet _ jet) (goo/semantic/jet attrs jet)
    node
````

### E05 — Prepared output and transport

Quoted documentation sections below define ordinary preparation and current transport boundaries. The geometry contract remains applicable across later display extensions. The standalone renderer documentation elsewhere contains historical ASCII-only scope; E12 supplies the later rich-text/Hebrew limits. Protocol documentation links inside the quote are provenance, not dependencies of this handoff.

Source: `reaver/extras/mounts/goo/HTML.md`, lines 9–58. Verbatim snapshot excerpt.

````markdown
## Public prepared contract

`goo_prepared/prepare` accepts a semantic tree and one render context: available
width, text scale and direction. It computes a validated native plan, joins each
plan ID to its semantic payload, and stores explicit lines for static text. Empty semantic output
is supported. The HTML entry point `goo_html/prepare` delegates to this shared
module; preparation has no HTML or browser dependency. The standalone development
JSON action defaults to width 752, scale 1, LTR and view path `/full`. Live Explorer
requests require an explicit context.

`goo_prepared/encode` validates a prepared value and returns `maybe[json]`. Its
version-1 display list contains:

- `profile`: the profile `id`, `version` and content-addressed `revision`.
- `context`: the requested `width`, `textScale` and `direction` (`ltr`/`rtl`).
- `coordinates: "absolute-css-px"`, resolved root `width`/`height`, and preorder
  `nodes`. The root width includes Goo's normal layout quantization.
- Each node's `id`, `parentId`, `kind`, semantic `role`, full `slot`, `config`,
  original `payload`, absolute `box`, `textStyle` and explicit `lines`. Images
  additionally retain their `src`. Each node also carries versioned `paint` and
  `semantics` descriptors; see [the portable contract](PORTABLE.md).
- Each text style's pinned font ID/hash, family, weight, style, font size,
  line height, letter spacing and insets. Kerning and ligatures are disabled
  for this profile's deterministic glyph-advance model.
- Each line's `text`, absolute `box`, `textX`, absolute `baseline` and
  `prefixAdvance`. The prefix reserves the first status marker. Baselines come
  from the pinned font's vertical metrics; painters need not infer CSS line-box
  behavior.

Editable `input` nodes have an empty `lines` array. Their original value remains
in `payload`, alongside `config`, the allocated `box` and resolved `textStyle`.
The renderer's native control owns editing and painting that value inside the
server-allocated box, including tabs, caret, selection and composition. The
prepared display does not claim static glyph positions for an editable value.
Static button and avatar labels still carry explicit lines.

Coordinates are physical positions from the surface's top-left, including RTL
placement and the resolved gaps/alignment. Renderers paint those boxes and lines
using the identified fonts. They do not need to interpret flow direction,
adjacency rules, wrapping or the browser DOM. A new width, text scale, direction
or profile revision requires a new preparation; reflowing an existing display
list under a different context is outside the contract.

The legacy record namespace `goo_html_internal` remains for source compatibility.
Its name does not imply that preparation belongs to HTML. Foil record constructors
are not compiler-private, so guarded consumer entry points revalidate the
measurement, dimensions, ID joins, measured summaries, aggregate geometry,
leaf heights, lines and rebuilt render tree. Forged prepared records cannot
bypass those guards. Public painting takes no independent width or scale.
````

Source: `reaver/extras/mounts/goo/protocol/README.md`, lines 1–42. Verbatim snapshot excerpt.

````markdown
# Goo domain protobuf v2

`goo.proto` is the wire contract. `wire=protobuf-v2` selects it; omission selects
legacy JSON. The generic v1 Value/Object protocol is rejected. Requests remain
URL-encoded and invocation retry bodies remain frozen.

The response oneof carries Presentation, LayoutBundle, Source, Snapshot,
OperationReceipt, or Failure. Nested messages describe the actual prepared
contracts: display nodes and boxes, text lines/runs, resolved fonts and paint,
editing palettes, accessibility semantics, bindings and pane identities.
Geometry uses finite IEEE754 binary64 (`double`) in logical CSS pixels.
Version/lifetime/publication strings retain their domain's unbounded identity
representation. Myth entries carry an explicit branded pail union. Neither
metadata nor unknown fields grant action authority.

`generate.py` produces typed Foil records and BAT encoders in `wire.foil`, plus
Rust schema descriptors. It also generates adapters for existing JSON-returning
domain APIs. The main ordinary/native preparation path in `wire_prepared.foil`
reads actual preparation objects and scalar bits, with no intermediate JSON
display, decimal geometry, or HTML. Paint table and binding descriptor APIs are
still small JSON adapters. Pane and tree adapters currently use their existing
domain APIs before encoding named messages. BAT chunks are flattened only when
writing the HTTP response. `http_foot` preserves explicit lengths and final zero
bytes.

Rust visits borrowed protobuf fields directly into application models through
Serde. Presence, wire types, duplicate singular fields/oneof cases, UTF-8,
finite doubles, integer bounds, required fields, message depth and size are
checked before mounting. Semantic validators remain mandatory. Raw protobuf is
retained for inspection; an ordinary presentation's diagnostic JSON projection
is generated only when requested.

Compiler pipeline captures, patch packets, inspection captures and all-views
catalogs are not yet v2 messages. They retain their JSON endpoints; binary
pipeline/patch/inspection requests are explicitly rejected. Workspace bootstrap
uses JSON because it can contain patch contracts. There is no JSON blob or
generic Value escape hatch in this schema. Add their actual domain messages
before migrating those endpoints. A `/goo/render` read resolving to a patch
returns a typed HTTP 415 Failure with `code=json-contract`. The egui client may
repeat only that explicitly identified read in JSON. It does not downgrade
actions, receipts, unknown selectors or failed network requests.
````

Source: `reaver/extras/mounts/goo/protocol/README.md`, lines 55–59. Verbatim snapshot excerpt.

````markdown
Unknown protobuf fields are skipped; unsupported known contract versions are
rejected by model validation. Required-field additions need a wire-version
change. Never reuse field numbers. Failure on a successful action response is
an unknown outcome, not evidence that the action was rejected. Receipt storage
and exact invocation retries remain unchanged.
````

### E06 — Pane descriptions and portable bindings

A subtree without host constructs is prepared as a native fragment. Otherwise the host structure is preserved and recursively described. A patch has its own preparation path. Control descriptors are joined after declaration routes/occurrence identities are finalized; descriptive fields do not grant actions.

Source: `reaver/extras/mounts/explorer/goo_panes.foil`, lines 11–20. Verbatim snapshot excerpt.

````foil
  + local
    \ kind=str
    ^ bool
    = kinds=row[str] ["patch" "pane" "selection" "list" "diagram_tree" "list_tree" "follow" "split" "deck" "pane_stack" "navigate" "operation" "operation_status"]
    | kinds.has(kind)
  + contains
    \ node=goo/node
    ^ bool
    ? (goo_panes/local node.constructor) .true
    | node.children.any goo_panes/contains
````

Source: `reaver/extras/mounts/explorer/goo_panes.foil`, lines 107–144. Verbatim snapshot excerpt.

````foil
  + node_with
    \ context=goo_bridge/render_context published=goo/published card=myth route=row[nat] node=goo/node
    ^ either[str json]
    ? (eq node.constructor "patch") (goo_patch/prepare context published card node route (goo_panes/controls published card))
    ? !(goo_panes/contains node)
      < fields (goo_bridge/prepared_fields context published card published.view.set_children((list/one node))
          (goo_panes/controls published card node route))
      | ./ok (json/obj fields.snoc((jkv "kind" (json/str "native"))).snoc((jkv "node" (json/str (str/join "." route.map(nat/show))))))
    < children (goo_panes/nodes_with context published card route node.children)
    = key=str (? node.arguments.len (goo_panes/text node.arguments.head) "")
      slot (goo_panes/property "slot" node)
      seed (goo_runtime/named "initial" node.arguments)
      initial=maybe[path]
        ?> (./some expression) seed .none
        ? !(goo_runtime/mentions "member" expression) .none
        | goo_panes/initial_path published card expression
      properties=row[jkv]
        [(jkv "kind" (json/str (? (grove_views/topos node.constructor) "topos" node.constructor)))
         (jkv "renderer" (json/str (? (grove_views/topos node.constructor) node.constructor "")))
         (jkv "topology" (json/str (goo_panes/property "topology" node)))
         (jkv "axis" (json/str (goo_panes/property "axis" node)))
         (jkv "key" (json/str key))
         (jkv "source" (json/str (goo_panes/property "source" node)))
         (jkv "selection" (json/str (goo_panes/property "selection" node)))
         (jkv "label" (json/str (goo_panes/property "label" node)))
         (jkv "mode" (json/str (goo_panes/property "mode" node)))
         (jkv "browse" (json/str (goo_panes/property "browse" node)))
         (jkv "operation" (json/str (goo_panes/property "operation" node)))
         (jkv "slot" (json/str (? slot.len slot "/sys/slot/content")))
         (jkv "initial" (initial.run((\ path (json/str (path_show path)))).fall(jnull)))
         (jkv "children" (json/arr children))]
    ? (and (maybe/is_some seed) (maybe/is_none initial))
      | ./err "initial requires .member(path), naming a source membership rather than a subject or ordinal."
    = value (json/obj properties)
    ? ((eq node.constructor "navigate") || (eq node.constructor "operation") || (eq node.constructor "operation_status"))
      | ./ok (json/obj properties.snoc((jkv "html" (json/str (str/from_atom
          (weft/render (weft/el "div" [] (goo_panes/host_control value))))))))
    | ./ok value
````

Source: `reaver/extras/mounts/goo/PORTABLE.md`, lines 150–181. Verbatim snapshot excerpt.

````markdown
## Explorer control bindings

Ordinary surfaces and patch body controls retain their existing flat fields.
`captures` is always present, including `[]`. Each control also has:

```json
{
  "binding": {
    "version": 1,
    "kind": "invoke-and-become",
    "nodeId": "/example/view:3",
    "route": "0.1.2",
    "slot": "/example/next",
    "captures": [{"slot": "/example/about", "selection": "/example/current"}],
    "presented": true
  }
}
```

`kind` is `input`, `invoke`, `become`, `invoke-and-become`, or `none`. `nodeId`
joins the **local display**, while `route` addresses the original declaration
for admission. `slot` keeps its existing meaning: input argument slot or become
destination. An absent slot remains the legacy empty string. Capture references
identify the lexically resolved selection; they are not captured live values.
The client freezes input and selection evidence when it creates an invocation.

Bindings are produced after pane route and patch occurrence ID rewriting.
`presented:false` means source metadata survived but its node is absent from this
prepared display; do not manufacture a widget for it. Width-dependent visibility
can change that flag. Legacy flat fields and the nested binding describe the same
control. Existing `/goo` action checks still decide whether a request is valid.
````

Source: `reaver/extras/mounts/goo/PORTABLE.md`, lines 182–230. Verbatim snapshot excerpt.

````markdown
## Portable patch occurrence content

A patch description adds `contentVersion:1`. Its existing `scene`, `contents`,
`controlsHTML`, and `offerBindings` remain. Each `contents[]` occurrence adds an
ordered `content[]` sequence:

| `kind` | Fields and interpretation |
|---|---|
| `body` | `key` (declaration route), `profile`, `context`, `display`, `controls`; an ordinary prepared body |
| `port` | Scene-local `key`, accessible `label`, `moves:[]` |
| `handle` | Scene-local `key`, accessible `label`, `moves:[{direction,dx,dy,label},…]` |
| `select` | Scene-local `key`, accessible `label`, `moves:[]`; selection only |
| `presentation` | `key`, `label`, absolute `target` and `slot`, `units:"css-px"`, `rect:{x,y,width,height}`; an embedded ordinary presentation reference |
| `label` | Scene-local `key`, recursive `children[]` content |

Static declarations and typed dynamic populations both carry `content[]`. Dynamic
populations remain passive: portable content does not grant domain action authority.
An embedded `presentation` supplies the same validated subject, slot and rectangle
as the browser frame. A supporting client requests and validates that ordinary
presentation separately, in its own owner; it must not parse the HTML or treat the
reference as action authority. Selection affordances never acquire movement deltas.
Unknown content kinds must be diagnosed rather than silently omitted.

Bodies are encoded from the **same checked preparation** used for their HTML.
A patch-node body uses its scene rectangle width when available, matching the
existing HTML path. Body display coordinates are local to that body. Scene
occurrence geometry supplies placement; renderers must not interpret the body
coordinates as scene coordinates. Sibling bodies keep declaration order. Port
and label keys refer to the enclosing occurrence, not globally unique objects.
A handle is a logical move affordance; the host can choose native controls or
accessible actions instead of copying the HTML corner placement.

The four movement descriptors currently carry +/-10 scene-unit X/Y deltas.
HTML movement buttons are generated from those same descriptors. Top-level
`connectionControls` contains `{key,controls:[…]}` groups. Controls are
`{kind:"disconnect",connection,label}` or
`{kind:"reconnect",connection,endpoint,label}`. These also generate the legacy
connection-control HTML.

These affordances do **not** introduce new operations. The scene's offered
operations, occurrence lifetimes, endpoints, candidate constraints and existing
`offerBindings` determine availability and admission. An offer binding's
`control` is the same finalized control emitted for its ordinary operation body;
its `argumentSlot` identifies the ordinary input used for the operation payload.
The client still owns gestures, candidate choice, camera state, previews,
acknowledgement coverage, and reconciliation. Hosted workspace session receivers are
forbidden from exposing domain invocation through patch occurrences just as
through ordinary surfaces.
````

### E07 — Namespace membership, paging, and selection capture

The source implementation makes key and subject the same path. This is an implemented namespace-adapter restriction, not a general graph source. Pages carry a namespace epoch, and continuation checks prevent cross-source/parent mixing. Captures are checked against the published lexical source and current membership, lifetime, and data evidence.

Source: `reaver/src/foil/goo_runtime.foil`, lines 113–136. Verbatim snapshot excerpt.

````foil
  + lifetime
    ' x.shape changes on removal/recreation, never on an ordinary live edit.
    \ target=path state=namespace
    ^ nat
    ?> (./some history) state.history(target) 0
    | (history.ever_at(target)).x.lock.shape
  + member
    \ source=path target=path state=namespace
    ^ json
    | goo_runtime/member_status (maybe/is_some (goo_runtime/record .x target state)) source target state
  + member_status
    \ available=bool source=path target=path state=namespace
    ^ json
    = face (sovereign_peek target state).fil.fall(myth/new).path_at(system_vocabulary/face)
    | json/obj
      [(jkv "face" (json/str (face.run(path_show).fall(""))))
       (jkv "key" (json/str (path_show target)))
       (jkv "subject" (json/str (path_show target)))
       (jkv "source" (json/str (path_show source)))
       (jkv "sourceLife" (json/str (nat/show (goo_runtime/lifetime source state))))
       (jkv "life" (json/str (nat/show (goo_runtime/lifetime target state))))
       (jkv "type" (json/str "namespace-record"))
       (jkv "expected" (json/str (nat/show (state.case(.x target)).fall(state.local.top))))
       (jkv "status" (json/str (? available "available" "unavailable")))]
````

Source: `reaver/src/foil/goo_runtime.foil`, lines 217–269. Verbatim snapshot excerpt.

````foil
  + tree_page_value
    ' Page only immediate children. Continuations are tied to one namespace epoch.
    \ query=goo_runtime/request state=namespace
    ^ either[str json]
    = source query.target axis (goo_runtime/axis query)
      parent_text (goo_runtime/input_text "$parent" query)
      after_text (goo_runtime/input_text "$after" query)
      epoch (nat/show state.local.rec.len)
      expected (goo_runtime/input_text "$epoch" query)
    ?> (./some parent) (path_parse (? parent_text.len parent_text (path_show source))) (./err "Invalid tree parent.")
    ? !(pith_prefix source parent) (./err "Tree parent is outside its source.")
    ? (and expected.len !(eq expected epoch)) (./err "Tree changed; refresh its children.")
    ? (and after_text.len !(expected.len)) (./err "Tree continuation requires its epoch.")
    = projected (goo_runtime/projection axis source state)
      subtree projected.dip(parent.drop(source.len))
      after=maybe[path]
        ? !(after_text.len) .none
        ? (path_parse after_text)
         > (./some path) (./some path)
        | physical_key/decode after_text
    ? (and after_text.len (maybe/is_none after)) (./err "Invalid tree cursor.")
    ? (after.run((\ path !(and (eq path.len parent.len.inc) (pith_prefix parent path)))).fall(.false))
      | ./err "Tree cursor is outside its parent."
    ? !(subtree.wyt) (./err "Tree parent is unavailable.")
    = selected subtree.kid.range_after(after.run((\ path path.at(parent.len))) 65)
      count (? (gt selected.len 64) 64 selected.len)
      visible (selected.take(count).keep((\ entry (goo_runtime/printable_path parent.snoc(entry.key)))))
      continuation=either[str json]
        ? !(gt selected.len 64) (./ok jnull)
        ? (physical_key/encode parent.snoc(selected.at(count.dec).key))
         > (./ok cursor) (./ok (json/str cursor))
        | ./err "Tree cursor exceeds its key budget; use the physical debugger for this branch."
    < next continuation
    =
      describe
        \ path=path node=axal[myth]
        ^ json
        = member (goo_runtime/member_status (maybe/is_some node.fil) source path state)
        ?> (json/obj fields) member member
        | json/obj fields.weld([(jkv "axis" (json/str axis)) (jkv "topology" (json/str "tree"))
            (jkv "parent" (? (equal path source) jnull (json/str (path_show path.take(path.len.dec)))))
            (jkv "hasChildren" (json/boo (gt node.kid.size 0)))])
      members (visible.map((\ entry (describe parent.snoc(entry.key) (unpin entry.val.held)))))
      members (? (and !(parent_text.len) !(after_text.len)) members.cons((describe source projected)) members)
    | ./ok (json/obj [(jkv "id" (json/str (path_show source)))
        (jkv "life" (json/str (nat/show (goo_runtime/lifetime source state))))
        (jkv "type" (json/str "namespace-record")) (jkv "axis" (json/str axis))
        (jkv "topology" (json/str "tree")) (jkv "incremental" (json/boo .true))
        (jkv "bounded" (json/boo .true)) (jkv "epoch" (json/str epoch))
        (jkv "omitted" (json/num .false (sub count visible.len)))
        (jkv "parent" (json/str (path_show parent))) (jkv "next" next)
        (jkv "members" (json/arr members))])
````

Source: `reaver/src/foil/goo_runtime.foil`, lines 397–453. Verbatim snapshot excerpt.

````foil
  + bound_captures
    \ nodes=list[goo/node] route=row[nat] fields=list[rex] input=row[[str str]]
    ^ either[str unit]
    ? fields.is_nil (./ok [])
    ?> (./nest _ _ rune kids) fields.head (goo_runtime/bound_captures nodes route fields.tail input)
    ? !(and (eq rune "=") (eq kids.len 2)) (goo_runtime/bound_captures nodes route fields.tail input)
    ? !(goo_runtime/mentions "capture" kids.at(1)) (goo_runtime/bound_captures nodes route fields.tail input)
    ?> (./some key) (goo_runtime/operand_path kids.at(1)) (./err "Capture must name a lexical selection.")
    ?> (./some source) (goo_runtime/selection_source key nodes route .none) (./err "Capture selection is not in scope.")
    ?> (./some slot) (goo_runtime/read_path kids.at(0)) (./err "Invalid capture slot.")
    < member (goo_runtime/capture_value input slot)
    ? !(eq (path_show source) (goo_runtime/json_text (goo_runtime/json_field "source" member)))
      | ./err "Capture source does not match the published selection declaration."
    ?> (./some subject) (path_parse (goo_runtime/json_text (goo_runtime/json_field "subject" member))) (./err "Invalid capture subject.")
    = axis (goo_runtime/json_text (goo_runtime/json_field "axis" member))
    ? !(eq (goo_runtime/selection_axis key nodes route "z") (? axis.len axis "z"))
      | ./err "Capture axis does not match the published selection declaration."
    = tree (goo_runtime/selection_tree key nodes route .false)
    ? !(eq tree (eq (goo_runtime/json_text (goo_runtime/json_field "topology" member)) "tree"))
      | ./err "Capture topology does not match the published selection declaration."
    ? !(and (pith_prefix source subject) (tree || (eq subject.len source.len.inc)))
      | ./err "Capture is outside the declared source topology."
    | goo_runtime/bound_captures nodes route fields.tail input
  + validate_captures
    \ input=row[[str str]] fields=list[rex] state=namespace
    ^ either[str unit]
    ? fields.is_nil (./ok [])
    = field fields.head
    ?> (./nest _ _ rune kids) field (goo_runtime/validate_captures input fields.tail state)
    ? !(and (eq rune "=") (eq kids.len 2)) (goo_runtime/validate_captures input fields.tail state)
    ? !(goo_runtime/mentions "capture" kids.at(1)) (goo_runtime/validate_captures input fields.tail state)
    ?> (./some slot) (goo_runtime/read_path kids.at(0)) (./err "Invalid capture argument slot.")
    < value (goo_runtime/capture_value input slot)
    = text (\ key=str (goo_runtime/json_text (goo_runtime/json_field key value)))
    ?> (./some source) (path_parse (text "source")) (./err "Invalid capture source.")
    ?> (./some subject) (path_parse (text "subject")) (./err "Invalid capture subject.")
    ? !(and (eq (text "type") "namespace-record") (eq (text "key") (path_show subject)))
      | ./err "Incompatible capture membership."
    = tree (eq (text "topology") "tree")
      axis_text=str (text "axis")
      axis=str (? (gt axis_text.len 0) axis_text "z")
      projected (goo_runtime/projection axis source state)
      belongs=bool
        ? !tree (and (and (eq subject.len source.len.inc) (pith_prefix source subject)) (maybe/is_some projected.dip(subject.drop(source.len)).fil))
        | and (pith_prefix source subject) (maybe/is_some projected.dip(subject.drop(source.len)).fil)
    ? !belongs
      | ./err "Capture is not a member of its finite source."
    ? !(and (state.permitted(subject)) (pith_prefix [state.self 'app] subject))
      | ./err "Captured subject is outside application authority."
    ? !(and (eq (text "life") (nat/show (goo_runtime/lifetime subject state)))
         (eq (text "sourceLife") (nat/show (goo_runtime/lifetime source state))))
      | ./err "Captured membership was removed or replaced."
    ? !(eq (text "expected") (nat/show (state.case(.x subject)).fall(0)))
      | ./err "Captured subject changed before admission."
    ? (maybe/is_none (goo_runtime/record .x subject state)) (./err "Captured subject is unavailable.")
    ? !(projected.wyt) (./err "Captured source is unavailable.")
    | goo_runtime/validate_captures input fields.tail state
````

### E08 — A topos is an adapter over membership

The web adapter validates tree structure, materializes bounded branches, retains disclosure by lifetime, and distinguishes focus from accepted choice. The excerpts stop before widget construction. The containing session owns selection; the tree component does not authorize application writes.

Source: `reaver/extras/mounts/explorer/goo-topoi.js`, lines 1–93. Verbatim snapshot excerpt.

````javascript
/* A topos presents membership; the selection port remains the choice authority. */
(function(root) {
  'use strict';
  const renderers = new Set(['list', 'diagram_tree', 'list_tree']);
  const hasOutline = (nodes, selection) => nodes.some(node => node.kind!=='selection' &&
    ((node.renderer==='list_tree' && node.selection===selection) || hasOutline(node.children||[],selection)));
  function topology(members, renderer) {
    if (!renderers.has(renderer)) throw new Error('Unknown topos renderer');
    const byKey = new Map();
    for (const member of members) {
      if (byKey.has(member.key)) throw new Error('Duplicate topos member');
      byKey.set(member.key, member);
    }
    if (renderer === 'list' || !members.length) return byKey;
    if (members.filter(m => m.parent == null).length !== 1) throw new Error('Tree topoi require one root; use selection topology = "tree".');
    for (const member of members) {
      const seen = new Set([member.key]); let parent = member.parent;
      while (parent != null) {
        if (!byKey.has(parent)) throw new Error('Missing topos parent');
        if (seen.has(parent)) throw new Error('Cyclic topos parent relation');
        seen.add(parent); parent = byKey.get(parent).parent;
      }
    }
    return byKey;
  }
  // Materialization requests only; semantic membership remains in GooSession.
  class TreeSource {
    constructor(path, axis, fetchPage) {
      this.path=path;this.axis=axis;this.fetchPage=fetchPage;this.requested=new Map();
    }
    request(member, more=false) {
      const previous=this.requested.get(member.key);
      const pages=previous?.life===member.life ? previous.pages : 0;
      this.requested.set(member.key,{life:member.life,pages:more?Math.max(1,pages)+1:Math.max(1,pages)});
    }
    commit(source) {
      const live=new Map(source.members.map(member=>[member.key,member.life]));
      for(const [key,plan] of this.requested)if(live.get(key)!==plan.life)this.requested.delete(key);
    }
    async read(signal, fetchPage=this.fetchPage) {
      const wanted=new Map(this.requested), records=new Map(), presentations=[];
      let omitted=0;
      const first=await fetchPage({},signal);
      const check=(page,parent)=> {
        if(page.id!==this.path || page.axis!==this.axis || page.topology!=='tree' || !page.incremental ||
           page.life!==first.life || page.epoch!==first.epoch || page.parent!==parent || !Array.isArray(page.members))
          throw new Error('Tree page changed; refresh before continuing.');
      };
      const add=(page,parent,initial=false)=> {
        check(page,parent);
        if(page.omitted!==undefined && (!Number.isSafeInteger(page.omitted)||page.omitted<0||page.omitted>64))throw new Error('Invalid omitted tree count.');
        omitted+=page.omitted||0;
        if(page.presentations)presentations.push(...page.presentations);
        if(page.members.length>(initial?65:64))throw new Error('Tree child page exceeds its bound.');
        for(const member of page.members) {
          const isRoot=initial && member.key===this.path && member.parent===null;
          if(!isRoot && member.parent!==parent)throw new Error('Invalid tree child parent.');
          if(records.has(member.key))throw new Error('Duplicate tree child.');
          records.set(member.key,{...member,childrenLoaded:!member.hasChildren});
        }
        if(records.size>4096)throw new Error('Loaded tree exceeds 4096 nodes; inspect a smaller subtree.');
      };
      add(first,this.path,true);
      if(!records.has(this.path))throw new Error('Missing tree root.');
      const queue=[{parent:this.path,page:first}];
      for(let index=0;index<queue.length;index++) {
        const {parent,page}=queue[index], member=records.get(parent);
        const plan=wanted.get(parent);
        const desired=plan?.life===member.life?plan.pages:1;
        let next=page.next, pages=1;
        const cursors=new Set();
        while(next && pages<desired) {
          if(cursors.has(next))throw new Error('Repeated tree cursor.');cursors.add(next);
          const continuation=await fetchPage({parent,after:next,epoch:first.epoch},signal);
          add(continuation,parent);next=continuation.next;pages++;
        }
        member.childrenLoaded=true;member.moreChildren=!!next;
        // Only explicitly expanded branches are requested; never recursively walk
        // an unopened subtree. Parent order also drops requests for removed nodes.
        for(const child of records.values()) {
          if(child.parent!==parent || !child.hasChildren || wanted.get(child.key)?.life!==child.life)continue;
          const page=await fetchPage({parent:child.key,epoch:first.epoch},signal);
          add(page,child.key);queue.push({parent:child.key,page});
        }
      }
      topology([...records.values()],'list_tree');
      return {...first,omitted,members:[...records.values()],...(first.presentations?{presentations}:{})};
    }
  }
  const sameMember = (a, b) => !!a && !!b && ['key','life','source','sourceLife'].every(key => a[key] === b[key]) && (a.axis || 'z') === (b.axis || 'z');
  const focusable = member => member && (member.status === 'available' || member.hasChildren);
  const focusMember = (members, focused) => members.find(member => focusable(member) && sameMember(member, focused)) || members.find(focusable) || null;
  const interactive = event => !!event.target.closest('button,a,input,select,textarea,summary,[contenteditable],[data-goo-tree-interactive]');
````

### E09 — Immutable activation and server receipt semantics

The client freezes an invocation in private fields. It sends the same body when retrying. The server compares the normalized request associated with an invocation ID and returns the prior accepted result. Server `now` is excluded from request equality; clients do not recapture providers or input on retry. Receipt and candidate state are committed together. Only accepted invocations are journaled by this implementation; absence remains unknown.

Source: `shrine-egui/src/transport.rs`, lines 1–117. Verbatim snapshot excerpt.

````rust
use crate::model::*;
use anyhow::{Result, ensure};
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, io::Read, time::Duration};
use uuid::Uuid;
#[derive(Clone, Debug)]
pub struct Connection {
    pub server: String,
    pub target: String,
    pub slot: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SelectionCapture {
    pub selection: String,
    pub incarnation: u32,
    pub revision: u64,
    pub member: Member,
}
/// Created once at activation; private fields prevent retry-time recapture.
#[derive(Clone, Debug)]
pub struct Invocation {
    id: String,
    body: String,
    inputs: BTreeMap<String, String>,
    target: String,
    become_slot: Option<String>,
}
impl Invocation {
    pub fn become_slot(&self) -> Option<&str> {
        self.become_slot.as_deref()
    }
    pub fn id(&self) -> &str {
        &self.id
    }
    pub fn body(&self) -> &str {
        &self.body
    }
    pub fn inputs(&self) -> &BTreeMap<String, String> {
        &self.inputs
    }
    pub fn target(&self) -> &str {
        &self.target
    }
    pub fn capture(
        p: &Presentation,
        c: &Control,
        inputs: BTreeMap<String, String>,
        selections: &BTreeMap<String, SelectionCapture>,
    ) -> Result<Self> {
        p.validate(&p.context, &p.snapshot.subject)?;
        ensure!(
            p.controls.contains(c)
                && c.binding.presented
                && ["invoke", "invoke-and-become"].contains(&c.binding.kind.as_str()),
            "Action not bound to this display"
        );
        ensure!(
            inputs.keys().eq(p.seeds().keys()) && inputs.values().all(|v| portable_text(v)),
            "Input slots mismatch or unsupported text character; draft retained"
        );
        for (slot, value) in &inputs {
            let n = p
                .input_node(slot)
                .ok_or_else(|| anyhow::anyhow!("Missing bound input"))?;
            ensure!(
                n.semantics.accepts_input(value),
                "Value outside the prepared input contract; draft retained"
            );
            if let Some(edit) = &n.editing {
                edit.decode(value)?;
            }
        }
        let id = Uuid::new_v4().to_string();
        let s = &p.snapshot;
        let mut fields = vec![
            ("wire".into(), "protobuf-v2".into()),
            ("target".into(), s.subject.clone()),
            ("subject".into(), s.target.clone()),
            ("view".into(), p.view.clone()),
            ("control".into(), c.binding.route.clone()),
            ("expected".into(), s.expected.clone()),
            ("displayed".into(), s.displayed.clone()),
            ("publication".into(), s.publication.clone()),
            ("invocation".into(), id.clone()),
        ];
        fields.extend(
            inputs
                .iter()
                .map(|(k, v)| (format!("input:{k}"), v.clone())),
        );
        for r in &c.binding.captures {
            let v = selections
                .get(&r.selection)
                .ok_or_else(|| anyhow::anyhow!("Missing selection {}", r.selection))?;
            ensure!(v.member.status == "available", "Unavailable selection");
            fields.push((format!("input:{}", r.slot), serde_json::to_string(v)?));
        }
        Ok(Self {
            id,
            body: form(fields),
            inputs,
            target: s.subject.clone(),
            become_slot: c.r#become.then(|| c.slot.clone()),
        })
    }
}
pub fn form(fields: impl IntoIterator<Item = (String, String)>) -> String {
    url::form_urlencoded::Serializer::new(String::new())
        .extend_pairs(fields)
        .finish()
}
#[derive(Clone, Debug, PartialEq)]
pub enum Outcome {
    Accepted,
    Rejected(String),
    Unknown(String),
}
````

Source: `reaver/src/foil/goo_runtime.foil`, lines 577–659. Verbatim snapshot excerpt.

````foil
  + apply
    \ query=goo_runtime/request state=namespace
    ^ either[str namespace]
    ? !(eq query.publication (goo_runtime/publication state)) (./err "Views changed; refresh before submitting.")
    ? !(eq query.displayed (state.case(.y query.target)).fall(0)) (./err "Object changed; refresh before submitting.")
    ?> (./some target) (goo_runtime/target query.target state) (./err "This presentation has no writable source object.")
    ? !(equal[path] target query.subject) (./err "The presentation now refers to a different object; refresh before submitting.")
    ? !(state.permitted(target)) (./err "Object is outside this namespace's authority.")
    ? !(pith_prefix [state.self 'app] target) (./err "Only application objects are writable here.")
    ? !(eq query.expected (state.case(.x target)).fall(0)) (./err "Object changed; refresh before submitting.")
    ?> (./some current) (goo_runtime/record .x target state) (./err "Object no longer exists.")
    ?> (./some published) (goo_runtime/record .x query.view state) (./err "View no longer exists.")
    < view (goo_runtime/published published)
    < found (goo_runtime/control query view current)
    = [node scope] found
    ? (maybe/is_some scope.make) (goo_runtime/create query published current state scope)
    < next (goo_runtime/updated query published current state)
    ? (grove_install/change target (writ/make next) state)
     > (./ok next) (./ok next)
     > (./err why) (./err (str/from_atom (iota_show why)))
  + receipt
    : identity=str request=goo_runtime/request body=str
  + receipts
    : entries=list[goo_runtime/receipt]
  + receipt_slot
    ^ path
    system_vocabulary/goo/receipts
  + journal
    \ state=namespace
    ^ list[goo_runtime/receipt]
    = record (goo_runtime/record .x [state.self 'weft 'goo_receipts] state).fall(myth/new)
    ?> (./some held) record.get(goo_runtime/receipt_slot) .nil
    ?> receipts=goo_runtime/receipts held .nil
    receipts.entries
  + operation_status
    \ query=goo_runtime/request state=namespace
    ^ str
    | show (goo_runtime/operation_status_value query state)

  + operation_status_value
    \ query=goo_runtime/request state=namespace
    ^ json
    = ids (query.inputs.keep((\ [key value] (eq key "$invocation"))))
      identity=str
        ? !(eq ids.len 1) ""
        = [key value] ids.at(0)
        value
      matches ((goo_runtime/journal state).keep((\ entry (and (eq entry.identity identity) (equal entry.request.target query.target)))))
    | json/obj [(jkv "operationId" (json/str identity))
        (jkv "outcome" (json/str (? matches.is_nil "unknown" "accepted")))]

  + act
    \ query=goo_runtime/request state=namespace
    ^ [namespace nat str]
    = identities (query.inputs.keep((\ [key value] (eq key "$invocation"))))
      identity=str
        ? (eq identities.len 1)
          = [key value] identities.at(0)
          value
        ""
      home=path [state.self 'weft 'goo_receipts]
      journal (goo_runtime/record .x home state).fall(myth/new)
      entries=list[goo_runtime/receipt]
        ?> (./some held) journal.get(goo_runtime/receipt_slot) .nil
        ?> receipts=goo_runtime/receipts held .nil
        receipts.entries
      prior (entries.keep((\ entry (eq entry.identity identity))))
      request query.set_now(0)
    ? (and (gt identity.len 0) (gt prior.len 0))
      ? (equal request prior.head.request) [state 200 prior.head.body]
      [state 409 (show (json/obj [(jkv "error" (json/str "Invocation identity was reused with changed arguments."))]))]
    ? (and (gt identity.len 0) (ge entries.len 1024))
      [state 409 (show (json/obj [(jkv "error" (json/str "Development invocation journal is full; restart the namespace."))]))]
    ? (goo_runtime/apply query state)
     > (./ok next)
      = body (goo_runtime/status query next)
      ? (eq identity.len 0) [next 200 body]
      = record (journal.put(goo_runtime/receipt_slot
          (goo_runtime/receipts entries.snoc((goo_runtime/receipt identity request body)))))
      ? (grove_install/change home (writ/make record) next)
       > (./ok committed) [committed 200 body]
       > (./err _) [state 409 (show (json/obj [(jkv "error" (json/str "Unable to retain invocation receipt."))]))]
     > (./err why) [state 409 (show (json/obj [(jkv "error" (json/str why))]))]
````

### E10 — Editor owners and staged structural changes

These are the egui reusable editor and note-deck session, not a claim that every Explorer adapter uses exactly the same tree shape. The fields and transition code illustrate retained work, generation admission, unknown outcomes, and atomic replacement. `can_leave` alone is not the dirty-work policy: callers additionally check `dirty` and the guard decision. A pending operation blocks retirement but not suspension/tab switching where supported.

Source: `shrine-egui/src/session.rs`, lines 1–190. Verbatim snapshot excerpt.

````rust
//! Session state is independent of widgets and worker threads. All completions carry incarnation/ticket.
use crate::{model::*, transport::*};
use anyhow::{Result, ensure};
use std::collections::BTreeMap;
use uuid::Uuid;
#[derive(Clone, Debug)]
pub struct Field {
    pub seed: String,
    pub value: String,
}
impl Field {
    pub fn dirty(&self) -> bool {
        self.seed != self.value
    }
}
#[derive(Clone, Debug)]
pub struct Editor {
    pub id: Uuid,
    pub target: String,
    pub slot: String,
    pub member: Option<Member>,
    pub publication: Option<String>,
    pub presentation: Option<Presentation>,
    pub fields: BTreeMap<String, Field>,
    pub rich_fields: BTreeMap<String, crate::rich_text::Draft>,
    pub design_preview: crate::design::Preview,
    pub preview_inspected: Option<String>,
    pub selection_preview: Option<crate::text_selection::Preview>,
    pub text_selection: Option<crate::text_selection::Selection>,
    pub pending: Option<Invocation>,
    pub sending: bool,
    pub suspended: bool,
    pub composing: bool,
    pub stale: bool,
    pub generation: u64,
    pub mounted_generation: u64,
    pub revision: u64,
    pub requested: Option<Context>,
    pub status: String,
    pub candidate: Option<Presentation>,
}
impl Editor {
    pub fn new(target: String, slot: String) -> Self {
        Self {
            id: Uuid::new_v4(),
            target,
            slot,
            member: None,
            publication: None,
            presentation: None,
            fields: BTreeMap::new(),
            rich_fields: BTreeMap::new(),
            text_selection: None,
            selection_preview: None,
            design_preview: Default::default(),
            preview_inspected: None,
            pending: None,
            sending: false,
            suspended: false,
            composing: false,
            stale: true,
            generation: 0,
            mounted_generation: 0,
            revision: 0,
            requested: None,
            status: "Waiting for prepared view".into(),
            candidate: None,
        }
    }
    pub fn dirty(&self) -> bool {
        self.fields.values().any(Field::dirty)
    }
    pub fn can_leave(&self) -> bool {
        self.pending.is_none() && !self.composing
    }
    pub fn can_act(&self) -> bool {
        !self.stale
            && !self.suspended
            && !self.composing
            && self.pending.is_none()
            && self.presentation.is_some()
    }
    pub fn values(&self) -> BTreeMap<String, String> {
        self.fields
            .iter()
            .map(|(k, f)| (k.clone(), f.value.clone()))
            .collect()
    }
    pub fn edit(&mut self, slot: &str, value: String) {
        if let Some(f) = self.fields.get_mut(slot) {
            f.value = value;
            self.revision += 1;
        }
    }
    pub fn request(&mut self, context: Context) -> Option<u64> {
        if self.suspended || self.pending.is_some() {
            return None;
        }
        self.generation += 1;
        self.requested = Some(context);
        self.stale = true;
        self.candidate = None;
        self.status = "Refreshing; actions paused".into();
        Some(self.generation)
    }
    pub fn receive(&mut self, ticket: u64, p: Presentation) -> Result<bool> {
        if ticket != self.generation || self.suspended {
            return Ok(false);
        }
        p.validate(self.requested.as_ref().unwrap(), &self.target)?;
        let replacing = self
            .presentation
            .as_ref()
            .is_some_and(|old| old.lifetime() != p.lifetime())
            || self
                .member
                .as_ref()
                .is_some_and(|m| m.life != p.snapshot.life)
            || self
                .publication
                .as_ref()
                .is_some_and(|v| *v != p.snapshot.publication);
        let seeds = p.seeds();
        let changes_encoding = self.presentation.as_ref().is_some_and(|old| {
            self.fields
                .iter()
                .filter(|(_, f)| f.dirty())
                .any(|(slot, f)| {
                    let (Some(previous), Some(next)) = (old.input_node(slot), p.input_node(slot))
                    else {
                        return true;
                    };
                    previous.editing.is_some() != next.editing.is_some()
                        || previous.semantics.role != next.semantics.role
                        || !next.semantics.accepts_input(&f.value)
                })
        });
        let incompatible_style = self.rich_fields.iter().any(|(slot, draft)| {
            p.controls
                .iter()
                .find(|c| &c.slot == slot && c.binding.presented)
                .and_then(|c| {
                    p.display
                        .as_ref()
                        .unwrap()
                        .nodes
                        .iter()
                        .find(|n| n.id == c.id)
                })
                .and_then(|n| n.editing.as_ref())
                .is_some_and(|edit| draft.runs().iter().any(|r| edit.style(&r.myth).is_none()))
        });
        let loses = self
            .fields
            .iter()
            .any(|(k, f)| f.dirty() && !seeds.contains_key(k));
        let loses_evidence = self
            .text_selection
            .as_ref()
            .is_some_and(|s| s.source(&p).is_none());
        if self.composing
            || ((replacing || loses || changes_encoding || incompatible_style || loses_evidence)
                && self.dirty())
        {
            self.candidate = Some(p);
            self.status = "Prepared replacement staged; draft retained".into();
            return Ok(false);
        }
        ensure!(
            !self
                .member
                .as_ref()
                .is_some_and(|m| m.life != p.snapshot.life),
            "Selected member replaced; reload declared tabs"
        );
        ensure!(
            !self
                .publication
                .as_ref()
                .is_some_and(|v| *v != p.snapshot.publication),
            "Publication replaced; reload declared tabs"
        );
        if replacing || changes_encoding {
            self.fields.clear();
            self.rich_fields.clear();
            self.id = Uuid::new_v4();
        }
        self.mount(p);
        Ok(true)
    }
````

Source: `shrine-egui/src/session.rs`, lines 289–366. Verbatim snapshot excerpt.

````rust
    pub fn activate(
        &mut self,
        c: &Control,
        selections: &BTreeMap<String, SelectionCapture>,
    ) -> Result<Invocation> {
        ensure!(self.can_act(), "Editor is not actionable");
        let p = self.presentation.as_ref().unwrap();
        for n in &p.display.as_ref().unwrap().nodes {
            if crate::text_selection::document(n).is_some() && self.fields.contains_key(&n.slot) {
                ensure!(
                    self.text_selection.as_ref().is_some_and(
                        |s| s.source(p).is_some() && self.fields[&n.slot].value == s.wire()
                    ),
                    "Select words from the current passage before saving"
                );
            }
        }
        let i = Invocation::capture(
            self.presentation.as_ref().unwrap(),
            c,
            self.values(),
            selections,
        )?;
        self.pending = Some(i.clone());
        self.sending = true;
        self.generation += 1;
        self.revision += 1;
        self.status = "Saving; edits and tab switching remain available".into();
        Ok(i)
    }
    pub fn complete(&mut self, id: &str, outcome: Outcome) -> bool {
        if self.pending.as_ref().is_none_or(|i| i.id() != id) {
            return false;
        }
        self.sending = false;
        self.revision += 1;
        match outcome {
            Outcome::Accepted => {
                let i = self.pending.take().unwrap();
                for (k, v) in i.inputs() {
                    if let Some(f) = self.fields.get_mut(k) {
                        f.seed = v.clone();
                    }
                }
                self.stale = true;
                self.status = "Save accepted; reread required".into();
                true
            }
            Outcome::Rejected(e) => {
                self.pending = None;
                self.stale = true;
                self.status = format!("Rejected; draft retained. Refresh before saving. {e}");
                false
            }
            Outcome::Unknown(e) => {
                self.status =
                    format!("Unknown save outcome. Check status or retry exact save. {e}");
                false
            }
        }
    }
    pub fn suspend(&mut self) -> bool {
        if self.composing {
            return false;
        }
        self.suspended = true;
        self.stale = true;
        self.generation += 1;
        self.candidate = None;
        true
    }
    pub fn resume(&mut self) {
        self.generation += 1;
        self.suspended = false;
        self.stale = true;
        self.requested = None;
    }
}
````

Source: `shrine-egui/src/session.rs`, lines 500–676. Verbatim snapshot excerpt.

````rust
    pub fn stage(&mut self, change: Change) -> Result<Plan> {
        self.intent += 1;
        let mut affected = vec![];
        match &change {
            Change::Deck {
                tabs,
                sources,
                basis,
                ..
            } => {
                let mut keys = std::collections::BTreeSet::new();
                ensure!(
                    tabs.len() <= 8 && tabs.iter().all(|t| keys.insert(&t.id)),
                    "Duplicate/excessive panes"
                );
                for t in tabs {
                    let s = sources
                        .get(&t.source)
                        .ok_or_else(|| anyhow::anyhow!("Missing source"))?;
                    s.validate(t)?;
                    if !self
                        .panes
                        .iter()
                        .any(|p| p.tab.id == t.id && self.retained(p, t, s, basis))
                    {
                        Pane::new(t.clone(), s.clone())?;
                    }
                }
                for p in &self.panes {
                    let keep = tabs.iter().find(|t| t.id == p.tab.id).is_some_and(|t| {
                        self.retained(p, t, &sources[&t.source], basis)
                            && p.selected.as_ref().is_none_or(|m| {
                                sources[&t.source].members.iter().any(|n| {
                                    n.identity() == m.identity() && n.status == "available"
                                })
                            })
                    });
                    if !keep {
                        affected.push(p.id)
                    }
                }
            }
            Change::Select { pane, member } => {
                let p = self
                    .panes
                    .iter()
                    .find(|p| p.id == *pane)
                    .ok_or_else(|| anyhow::anyhow!("Stale pane"))?;
                ensure!(
                    p.source
                        .members
                        .iter()
                        .any(|m| m.identity() == member.identity() && m.status == "available"),
                    "Unavailable selection"
                );
                if p.selected
                    .as_ref()
                    .is_none_or(|m| m.identity() != member.identity())
                {
                    affected.push(p.id)
                }
            }
            Change::Remove { pane } => {
                ensure!(self.panes.iter().any(|p| p.id == *pane), "Stale pane");
                affected.push(*pane)
            }
        }
        let affected = affected
            .into_iter()
            .map(|id| {
                let p = self.panes.iter().find(|p| p.id == id).unwrap();
                (id, p.editor.as_ref().map(|e| (e.id, e.revision)))
            })
            .collect();
        Ok(Plan {
            ticket: self.intent,
            change,
            affected,
        })
    }
    pub fn needs_guard(&self, p: &Plan) -> bool {
        p.affected.iter().any(|(id, _)| {
            self.panes
                .iter()
                .find(|p| p.id == *id)
                .and_then(|p| p.editor.as_ref())
                .is_some_and(|e| e.dirty() || !e.can_leave())
        })
    }
    pub fn commit(&mut self, plan: Plan, discard: bool) -> Result<()> {
        ensure!(plan.ticket == self.intent, "Transition superseded");
        for (id, stamp) in &plan.affected {
            let p = self
                .panes
                .iter()
                .find(|p| p.id == *id)
                .ok_or_else(|| anyhow::anyhow!("Owner removed"))?;
            ensure!(
                p.editor.as_ref().map(|e| (e.id, e.revision)) == *stamp,
                "Guard superseded by new work"
            );
            if let Some(e) = &p.editor {
                ensure!(
                    e.can_leave() && (!e.dirty() || discard),
                    "Work retained: finish composition or resolve save, then choose Stay/Discard"
                );
            }
        }
        match plan.change {
            Change::Deck {
                tabs,
                sources,
                basis,
                publication,
            } => {
                // Build every replacement before changing the usable registry.
                let mut next = vec![];
                for t in tabs {
                    let s = &sources[&t.source];
                    let mut p = if let Some(p) = self
                        .panes
                        .iter()
                        .find(|p| p.tab.id == t.id && self.retained(p, &t, s, &basis))
                    {
                        p.clone()
                    } else {
                        Pane::new(t.clone(), s.clone())?
                    };
                    if let Some(m) = &p.selected {
                        if let Some(n) = s
                            .members
                            .iter()
                            .find(|n| n.identity() == m.identity() && n.status == "available")
                        {
                            p.selected = Some(n.clone())
                        } else {
                            p.selected = None;
                            p.editor = None;
                            p.selection_revision += 1;
                        }
                    }
                    p.tab = t;
                    p.source = s.clone();
                    next.push(p);
                }
                self.panes = next;
                self.basis = basis;
                self.publication = publication;
            }
            Change::Select { pane, member } => {
                let p = self.panes.iter_mut().find(|p| p.id == pane).unwrap();
                if p.selected
                    .as_ref()
                    .is_none_or(|m| m.identity() != member.identity())
                {
                    p.selected = Some(member);
                    p.editor = None;
                    p.selection_revision += 1;
                }
            }
            Change::Remove { pane } => self.panes.retain(|p| p.id != pane),
        }
        if !self.panes.iter().any(|p| Some(p.id) == self.active) {
            self.active = self.panes.first().map(|p| p.id);
        }
        for p in &mut self.panes {
            p.mount_editor(&self.publication);
            if let Some(e) = &mut p.editor {
                if Some(p.id) == self.active {
                    e.resume()
                } else {
                    e.suspend();
                }
            }
        }
        Ok(())
    }
````

### E11 — Real consumer capability boundaries

The egui excerpt is from the Explorer workspace validator. It admits tree selections and two tree arrangements, plus supported structural/native controls; it is not the note-deck validator. The UIKit excerpt is specifically its note list/detail workspace adapter. UIKit also has a separately implemented routed Torah reader, so these restrictions must not be generalized to all UIKit screens. Neither excerpt is a roadmap promise.

Source: `shrine-egui/src/explorer.rs`, lines 433–515. Verbatim snapshot excerpt.

````rust
                match kind {
                    "pane" | "split" | "pane_stack" => {}
                    "or" => {
                        let alternatives = children(n);
                        ensure!(
                            alternatives.len() == 2
                                && text(&alternatives[0], "kind") == "follow"
                                && text(&alternatives[1], "kind") == "native",
                            "Unsupported pane fallback; expected follower and prepared fallback"
                        );
                    }
                    "selection" => {
                        ensure!(
                            !key.is_empty()
                                && path(text(n, "source"))
                                && text(n, "topology") == "tree"
                                && ["x", "y", "z", ""].contains(&text(n, "axis")),
                            "Unsupported selection"
                        );
                        scope.insert(
                            key.into(),
                            (
                                text(n, "source").into(),
                                if text(n, "axis").is_empty() {
                                    "z".into()
                                } else {
                                    text(n, "axis").into()
                                },
                            ),
                        );
                    }
                    "topos" => {
                        ensure!(
                            ["list_tree", "diagram_tree"].contains(&text(n, "renderer"))
                                && scope.contains_key(text(n, "selection"))
                                && path(text(n, "slot")),
                            "Unsupported/unscoped tree"
                        );
                        let (source, axis) = &scope[text(n, "selection")];
                        ensure!(
                            text(n, "source") == source
                                && (text(n, "axis").is_empty() || text(n, "axis") == axis)
                                && ["", "tree"].contains(&text(n, "topology")),
                            "Tree/selection source mismatch"
                        );
                    }
                    "follow" => {
                        ensure!(
                            scope.contains_key(text(n, "selection")) && path(text(n, "slot")),
                            "Unscoped follower"
                        );
                    }
                    "navigate" => {
                        ensure!(
                            ["input", "parent", ""].contains(&text(n, "mode"))
                                && path(text(n, "source")),
                            "Unsupported navigation"
                        );
                    }
                    "operation" | "operation_status" => {
                        ensure!(
                            host.operations
                                .iter()
                                .any(|o| o.key == text(n, "operation")),
                            "Undeclared host operation"
                        );
                    }
                    "native" => {
                        let route = text(n, "node");
                        ensure!(
                            !route.is_empty() && route.split('.').all(|s| s.parse::<u32>().is_ok()),
                            "Invalid native declaration route"
                        );
                        let surface = native(packet, n)?;
                        ensure!(
                            surface.view == packet.view
                                && surface.controls.iter().all(|c| !c.invoke && !c.r#become),
                            "Workspace native surface cannot grant domain authority"
                        );
                        surface.validate(&packet.context, &packet.snapshot.subject)?;
                    }
                    _ => bail!("Unsupported workspace component: {kind}"),
                }
````

Source: `shrine_ios/shrine_ios/Goo/GooWorkspaceModels.swift`, lines 1–102. Verbatim snapshot excerpt.

````swift
import Foundation

struct GooPaneNode: Decodable {
    let kind: String
    var mode: String? = nil
    let key: String?
    let label: String?
    let renderer: String?
    let source: String?
    let selection: String?
    let slot: String?
    let axis: String?
    let topology: String?
    let initial: String?
    let children: [GooPaneNode]?
}

struct GooWorkspaceDescription: Equatable {
    let selectionKey: String
    let listKey: String
    let followerKey: String
    let source: String
    let axis: String
    let listSlot: String
    let detailSlot: String
    let initial: String?

    init(nodes: [GooPaneNode]) throws {
        func flatten(_ nodes: [GooPaneNode]) -> [GooPaneNode] {
            nodes.flatMap { [$0] + flatten($0.children ?? []) }
        }
        let all = flatten(nodes)
        guard all.allSatisfy({ ["pane", "split", "selection", "topos", "follow"].contains($0.kind) }),
              all.filter({ $0.kind == "pane" }).count == 1,
              all.filter({ $0.kind == "split" }).count == 1,
              all.filter({ $0.kind == "selection" }).count == 1,
              all.filter({ $0.kind == "topos" }).count == 1,
              all.filter({ $0.kind == "follow" }).count == 1,
              let selection = all.first(where: { $0.kind == "selection" }),
              let key = selection.key, !key.isEmpty,
              let source = selection.source, source.hasPrefix("/") else {
            throw GooError.message("This consumer supports one selection, one list and one follower.")
        }
        let scoped = flatten(selection.children ?? [])
        guard let list = scoped.first(where: { $0.kind == "topos" }),
              let follow = scoped.first(where: { $0.kind == "follow" }),
              list.renderer == "list", list.selection == key, follow.selection == key,
              list.source == source, let listKey = list.key, let followerKey = follow.key,
              !listKey.isEmpty, !followerKey.isEmpty,
              [nil, "", "children"].contains(selection.topology),
              [nil, "", "children"].contains(list.topology),
              let listSlot = list.slot, let detailSlot = follow.slot else {
            throw GooError.message("The list and follower must share one finite child selection.")
        }
        let axis = selection.axis.flatMap { $0.isEmpty ? nil : $0 } ?? "z"
        let listAxis = list.axis.flatMap { $0.isEmpty ? nil : $0 } ?? "z"
        guard ["x", "y", "z"].contains(axis), axis == listAxis else { throw GooError.message("Incompatible selection axis.") }
        self.selectionKey = key; self.listKey = listKey; self.followerKey = followerKey
        self.source = source; self.axis = axis; self.listSlot = listSlot; self.detailSlot = detailSlot
        initial = selection.initial
    }
}

struct GooMember: Codable, Equatable {
    let key: String
    let subject: String
    let source: String
    let sourceLife: String
    let life: String
    let type: String
    let expected: String
    let status: String
    let axis: String
    var parent: String? = nil
    var topology: String? = nil
    var identity: String { [source, sourceLife, key, subject, life, axis].joined(separator: "\n") }
    var available: Bool { status == "available" }
}

struct GooSource: Codable {
    let id: String
    let life: String
    let type: String
    let axis: String
    let topology: String
    let bounded: Bool
    let members: [GooMember]

    func validate(description: GooWorkspaceDescription) throws {
        guard bounded, members.count <= 64, id == description.source, axis == description.axis,
              type == "namespace-record", topology == "children",
              Set(members.map(\.key)).count == members.count,
              members.allSatisfy({ member in
                let prefix = id.hasSuffix("/") ? id : id + "/"
                let child = member.subject.hasPrefix(prefix) ? String(member.subject.dropFirst(prefix.count)) : ""
                return !child.isEmpty && !child.contains("/") && member.key == member.subject &&
                    member.source == id && member.sourceLife == life && member.axis == axis &&
                    member.type == type && ["available", "unavailable"].contains(member.status)
              }) else { throw GooError.message("Invalid or unsupported Goo membership source.") }
    }
}
````

### E12 — Rich editing, Hebrew, and exact-range overlays

The rich editor, word selection, and provider-generated overlay are distinct extensions. Plain rich-text metadata is not authority. A selection preview may use only the currently supported local transition controls; it is not a general domain-action popup. These sections are reproduced together so the earlier generic text explanation cannot be read as claiming universal shaping or editor parity.

Source: `reaver/extras/mounts/goo/PORTABLE.md`, lines 509–613. Verbatim snapshot excerpt.

````markdown
## Rich-text editing (display v3)

A prepared input may supply `editing` with `version:1`, `encoding:"goo-text-v1"`,
`maxBytes:65536`, `styles:[{myth,resolved}]`, and `linkStyle`. Its `textRuns` is the
initial structured value, `semantics.value` is its plain projection, and
`semantics.multiline` is true. `lines` remains empty: editing, selection, caret,
scrolling and IME use the platform editor. The supplied input box is fixed by
Reaver. Styling options contain resolved pinned font/paint recipes; consumers
must not invent font choices or a parallel palette. Match a run's metadata to
an option after removing `/sys/link` and canonicalizing modifier order (an empty
modifier list is equivalent to no modifier slot). Use `linkStyle`'s foreground
and highlight for linked editing text; its placeholder target is descriptive
and grants no action authority.

Display v3 is required even for an empty rich value. Older native clients must
reject it rather than flatten it into a plain input. Browser output explicitly
diagnoses the unavailable editor; it does not expose a plain input pretending to
edit structured runs. Ordinary plain inputs and v1/v2 displays are unchanged.

The action input is a serialized Goo run array in the existing `input:<slot>`
form field. The declaration must use a typed action argument decoder; the mount's
`goo_edit/decode` accepts that JSON string or an existing `goo/text/pail`, checks
its shape, metadata, pinned fonts and ASCII repertoire, and returns a typed pail.
It never resolves code or dispatches from metadata. JSON strings are not
automatically promoted by `.poke`: use a declared typed action. Freeze the wire
string alongside the usual receiver, declaration, versions and invocation ID.
A retry must reuse the exact original body. Preserve edits made after activation.

Rich/plain encoding changes and removed formatting support are incompatible
re-preparations: retain dirty owners and stage the change behind the existing
loss-of-work guard. Compatible refresh/resize must retain run metadata, caret,
composition, selection, typing style, undo history and pending invocations.
Current scope includes ASCII and the unpointed Hebrew run-font extension, bundled fonts, inline modifiers and links;
clipboard interchange is plain text. No browser/HTML rich editor or UIKit rich
editor is included.

### Unpointed Hebrew run font

The optional `hebrew` run face covers ASCII and U+05D0–U+05EA. Its identity
and font hash are in `run-fonts/hebrew.json`. Plain source runs containing
Hebrew acquire the resolved `/sys/font/hebrew` fallback during preparation;
an incompatible explicit face is diagnosed. Logical UTF-8 text and run offsets
are preserved. Reaver measures a Hebrew scalar once and breaks lines only at
scalar boundaries, including for widths smaller than one glyph. Consumers
must validate the font identity before painting. The native folio uses one
logical run per mixed-direction paragraph and applies Unicode bidi ordering
after line breaking. This does not introduce support for niqqud, cantillation,
general complex-script shaping or arbitrary rich-text bidi across styled runs.

### Word-selection overlays

A static text node can declare a versioned passage by attaching a
`/sys/selection` path pail to its source run(s). In this edition the whole node
names one document; its payload is canonical LF-normalized logical text with
no tabs. Its ordinary prepared fragments supply hit geometry. Highlights track
half-open UTF-8 byte offsets in that payload, never screen coordinates, a
word number, or the first substring matching the quote. A selection retains the
receiver identity, incarnation, publication, source path and source text; it may
be projected again at another width, but never rebound to changed content.

A source may supply a separate local composer slot in a
`/sys/selection_composer` path pail. All source runs must agree on the
document and composer. When omitted, the document path is the composer slot.
The capture always retains the original document identity.

The range overlay can surface an independently declared, presented local
`become` button whose destination slot matches the composer slot. In the new
recipe, only an exact document/receiver match and a presented plain input whose
slot matches the annotated node's slot can receive the capture. The input wire
value is the JSON tuple `[documentPath,startByte,endByte,exactQuote]`. A save
is an ordinary, separately bound Goo invocation. A descriptor alone grants no
navigation or write capability. The Torah action validates the tuple against
the actual manuscript before storing it.

In the egui workspace, a prepared namespace link can request read-only
navigation with a `/sys/navigate` path matching the same run's `/sys/link`
path. Following it uses the workspace's declared address input and normal
editor transition guards. A descriptive link by itself remains hoverable.

Saved details are ordinary text runs carrying a `/sys/evidence` text pail with
the same tuple. A renderer can underline a saved span and list its details only
when the document, both offsets, and exact logical slice match. A historical
quote alone is never sufficient to move an annotation to a new occurrence.


A selectable source may additionally carry `/sys/selection_preview`, a path to
an ordinary published view. The receiver must contain a `goo_selection/provider`
pail at that same path. Its pure `project` function receives the validated range
wire and receiver myth and returns an ephemeral myth for that view. This is a
read-only projection, never a notebook mutation. Application calculations and
popup content belong in that provider and Goo view.

POST `/goo/render` with `selection`, `sourceNode`, source `view`, `target`,
`life`, `expected`, `displayed`, `publication`, `sourceWidth`, preview render context and
`wire=protobuf-v2` requests the projection. Reaver rereads the source, verifies
its identity and the exact whole-word range, resolves the source-declared
provider, and prepares its declared view. The result uses the ordinary typed
protobuf presentation contract. Only local `become` controls are supported in
this preview edition. Inputs and domain invocations are rejected.

Clients own placement, highlighting and request lifetimes. A preview completion
is usable only for its originating owner, exact range, source text, recipe and
snapshot. Compatible reflow can retain it. Suspended/stale owners cannot enable
its controls. Changing selection drops the old completion, including errors.
The provider metadata grants no write authority.
````

### E13 — Real application and route declarations

These declarations show the zoo as an ordinary editable view plus a workspace, and Torah as routed read/compare panes with independent selections. Imported role/slot definitions outside these excerpts are dependencies for actual compilation; the semantic roles are explained in the essay. No client-specific Torah route branch is implied.

Source: `reaver/extras/mounts/goo-style-zoo/main.grove`, lines 160–203. Verbatim snapshot excerpt.

````grove
workspace =
  @pane
  #route ;
    name: sheet
    page: %/address
  #on ; %/context
  #for ; /sys/slot/style_zoo_workspace
  context => selection('/page, source = context.address, topology = "tree", axis = "z", initial = .member(context.address)) {
    follow('/specimen, selection = '/page, slot = '/sys/slot/style_zoo_sheet)
  }

composition =
  @view
  #on ; %/proof
  #for ; /sys/slot/style_zoo_sheet
  proof => col {
    text(proof.navigation, '/sys/slot/label)
    group("context-menu") {
      text(proof.specimen, proof.treatment, style = proof.plate)
      action("Override this specimen", become = '/sys/slot/style_zoo_editor)
    }
    text("A print proof assembled from Goo components.", "subtitle")
    row {
      avatar("GS")
      col {
        text("Goo Studio", "author")
        text("Letterpress series", "metadata")
      }
      text("PROOF", "badge")
    }
    text(proof.caption, "quote")
    row {
      text("3", "value")
      text("of 4 plates inked", "unit")
    }
    bar({[value]: 3, [max]: 4, [label]: "Plates inked"}, "")
    text("Proof caption", '/sys/slot/label)
    group(on = proof, action = .poke, myth = { %/caption = .input(proof.caption) }) {
      input(%/caption)
      action("Save caption")
    }
    text("Save to see your words set in the quote face above.", "hint")
  }
````

Source: `reaver/extras/mounts/torah-study/chunks.grove`, lines 95–156. Verbatim snapshot excerpt.

````grove
workspace =
  @pane
  #route ;
    name: read
    chunk: %/address
    reveal: /sys/slot/chunk_read
  #meta ;
    lede: "Text library"
    "/sys/help": (pails/t "Open a tract or follow a link to a directly addressed chunk.")
  #on ; %/context
  #for ; /sys/slot/chunk_workspace
  context => {
    navigate('/address, source = context.address, mode = "input", label = "Open address")
    selection('/page, source = context.address, topology = "tree", axis = "z", initial = .member(context.address)) {
      follow('/reader, selection = '/page, slot = '/sys/slot/chunk_read)
    }
  }

left =
  @slot
  #meta ;
    lede: "Left text"

right =
  @slot
  #meta ;
    lede: "Right text"

pair =
  @role
  %/left: path_type
  %/right: path_type

comparison =
  @pane
  #on ; %/pair
  #for ; /sys/slot/chunk_compare
  #route ;
    name: compare
    left: %/left
    right: %/right
  pair => split {
    pane(%/Left)
    pane(%/Right)
  }

Left =
  @pane
  #on ; %/pair
  #for ; /sys/slot/chunk_compare_left
  pair => selection('/left, source = pair.left, topology = "tree", axis = "z", initial = .member(pair.left)) {
    follow('/reader, selection = '/left, slot = '/sys/slot/chunk_read)
  }

Right =
  @pane
  #on ; %/pair
  #for ; /sys/slot/chunk_compare_right
  pair => selection('/right, source = pair.right, topology = "tree", axis = "z", initial = .member(pair.right)) {
    follow('/reader, selection = '/right, slot = '/sys/slot/chunk_read)
  }
````

Source: `reaver/extras/mounts/goo/PORTABLE.md`, lines 272–323. Verbatim snapshot excerpt.

````markdown
### Pane routes

A Grove pane can publish a route alongside its receiver role. For example:

```grove
comparison =
  @pane
  #on ; %/pair
  #for ; /sys/slot/chunk_compare
  #route ;
    name: compare
    left: %/left
    right: %/right
  ...
```

Each argument binds a required query value to a path-typed receiver slot. All required
receiver fields must be bound. The first binding supplies the workspace entry's
`source`. An optional `reveal: /sys/slot/...` enables citation evidence for that
source. The workspace automatically exposes its entry pane's route. Its mount
manifest may also export additional declarations with `"panes": [[...], ...]`.
The host checks the published declarations and rejects duplicate route names.

Use `/<workspace>/<name>?left=…&right=…` for a shareable location. The native
session entry request adds `format=json`. Encode values once as query arguments.
The older `/<workspace>?route=<name>&...` form also resolves. Reaver checks the
argument names, paths, workspace root and each subject's admission before
allocating the pane receiver. Entry JSON echoes `destination` and `arguments`,
alongside the ordinary workspace fields. A reveal-enabled route also returns
`readSlot` and optionally `at`, the tuple
`[documentPath,startByte,endByte,exactQuote]` with exclusive UTF-8 offsets.

A routed text run carries a `/sys/link` path, matching `/sys/navigate` path,
`/sys/route` text naming the route, and one path pail per argument under
`/sys/route/<key>`. The link target must occur among the arguments. A citation
can also carry `/sys/navigate_at` text containing the evidence tuple. The reader
checks the revision, boundaries and quotation against its prepared text and
displays a stale quotation as unresolved. Route entry grants no action binding.

Native Back and Forward keep a local cursor and a scroll viewport per visit.
Opening, revisiting, and pasting stage an admitted session and a freshly
prepared workspace. The cursor moves after editor guards and installation
succeed. Copied locations can be opened in another egui session configured
with the same server and workspace endpoint.

The earlier `workspace-subject` descriptor described
the pre-main synthetic receiver and must not be emitted for stored sessions. Operations identify the supported host workflow, not an
arbitrary executable command or URL. `mount-rescan` retains the existing guarded
status/scan/publication workflow. Unknown kinds must remain unavailable. This is
host configuration transport, not renderer capability negotiation or an
authorization token.
````

The current zoo additionally declares `receiver.routeRoots` for its two registries: `app/goo_theme` and `app/style_zoo`. They constrain route-argument admission; they are not an action grant. When omitted, route admission uses the initial path as its prefix. Changing the initial record alone must not accidentally prevent navigation to the other registry.

### E14 — Deterministic regression cases

These are actual test definitions for atomic page admission, duplicate/member checks, foreign parents, guard supersession, composition, and installed host identity. They are evidence of encoded expectations. No test was executed to create this omnibus, and these excerpts do not assert that every future contract already has coverage.

Source: `shrine-egui/tests/explorer.rs`, lines 1–63. Verbatim snapshot excerpt.

````rust
use serde_json::json;
use shrine_egui::{explorer::*, model::*, session::Editor, transport::Client};
fn page(source: &str, parent: Option<&str>, epoch: &str) -> Page {
    serde_json::from_value(json!({"id":source,"life":"1","type":"namespace-record","axis":"z","topology":"tree","incremental":true,"bounded":true,"epoch":epoch,"omitted":0,"parent":parent.unwrap_or(source),"next":null,"members":if parent.is_none(){vec![json!({"key":source,"subject":source,"source":source,"sourceLife":"1","life":"1","type":"namespace-record","expected":"3","status":"unavailable","axis":"z","topology":"tree","parent":null,"hasChildren":true})]}else{vec![]},"presentations":[]})).unwrap()
}
#[test]
fn page_admission_is_atomic_and_epoch_bound() {
    let tree = Tree::new("/a".into(), "z".into(), "/summary".into());
    let tree = tree.with_page(page("/a", None, "9"), None, None).unwrap();
    let mut malformed = page("/a", Some("/a"), "10");
    assert!(tree.with_page(malformed.clone(), Some("/a"), None).is_err());
    assert_eq!(tree.epoch, "9");
    malformed.epoch = "9".into();
    malformed.life = "2".into();
    assert!(tree.with_page(malformed, Some("/a"), None).is_err());
    assert_eq!(tree.members.len(), 1);
}
#[test]
fn page_rejects_duplicate_members_and_missing_prepared_content() {
    let mut p = page("/a", None, "9");
    p.members.push(p.members[0].clone());
    assert!(p.validate("/a", "z", "/summary", None, None).is_err());
    p.members.pop();
    p.members[0].member.status = "available".into();
    assert!(p.validate("/a", "z", "/summary", None, None).is_err());
}
#[test]
fn page_rejects_foreign_parent_and_unbounded_sources() {
    let mut p = page("/a", None, "9");
    p.parent = "/elsewhere".into();
    assert!(p.validate("/a", "z", "/summary", None, None).is_err());
    p.parent = "/a".into();
    p.bounded = false;
    assert!(p.validate("/a", "z", "/summary", None, None).is_err());
}
#[test]
fn guard_refusal_supersession_and_identity_replacement() {
    let mut e = Editor::new("/a".into(), "/content".into());
    let guard = Guard::capture(4, [&e].into_iter());
    assert!(guard.check(5, [&e].into_iter(), true).is_err());
    e.revision += 1;
    assert!(guard.check(4, [&e].into_iter(), true).is_err());
    e.revision -= 1;
    e.id = uuid::Uuid::new_v4();
    assert!(guard.check(4, [&e].into_iter(), true).is_err());
}
#[test]
fn guard_cannot_discard_composition() {
    let mut e = Editor::new("/a".into(), "/content".into());
    e.composing = true;
    let guard = Guard::capture(1, [&e].into_iter());
    assert!(guard.check(1, [&e].into_iter(), true).is_err());
}
#[test]
fn entry_requires_installed_session_and_known_host() {
    let mut entry:Entry=serde_json::from_value(json!({"version":1,"target":"/0x11/goo/ses/1","source":"/a","view":"/v","host":{"version":1,"kind":"workspace","declaration":"/v","navigation":{"kind":"workspace-session","sourceSlot":"/s"},"operations":[]}})).unwrap();
    entry.validate("/a").unwrap();
    entry.target = "/a".into();
    assert!(entry.validate("/a").is_err());
    entry.target = "/0x11/goo/ses/1".into();
    entry.host.navigation.kind = "workspace-subject".into();
    assert!(entry.validate("/a").is_err());
}
````

### E15 — Shared-source topoi and lifecycle prose

These excerpts document the implemented web source adapter and interaction model. Some earlier sections of PANES.md describe the original finite-list slice; only the later Topoi section below should be used for the incremental-tree behavior. Read its limits as per-adapter behavior, not arbitrary-graph support.

Source: `reaver/extras/mounts/explorer/PANES.md`, lines 430–480. Verbatim snapshot excerpt.

````markdown
## Topoi

`list`, `diagram_tree`, and `list_tree` are presentations of one keyed topos.
They share selection ports, source evidence, member views, and capture semantics.
A renderer change does not replace the semantic owner. Tree sources opt in with
`selection(..., topology = "tree")`. Sources consumed by an outline (`list_tree`)
use immediate-child pages
of at most 64 members, materializes branches on disclosure, and offers a native
continuation button for wide branches. The root's first page also includes the
root itself. Each page carries parent, continuation, branch hints and a namespace
epoch; continuations cannot escape their source or mix epochs. Loaded material
is bounded at 4096 nodes per tree source and uses the existing selection owner,
input guards and refresh cancellation. Standalone diagram/flat presentations and
the legacy complete-source endpoint keep their complete, 64-member projection.
Views sharing an outline's selection see the same materialized source.
Disclosure and camera state never call domain actions.

Paging examines at most 64 raw keys plus one lookahead. Keys without a Goo path
spelling are omitted and counted in `omitted`; outlines display that count rather
than failing the whole branch. `next` is an opaque `physical_key` continuation, so
even an entirely omitted page can advance. Legacy path-shaped cursors remain
accepted, with the same parent/source and epoch checks. The physical debugger
remains the interface for inspecting those raw keys.

The outline adapter requests `presentations=pane-v1` on `/goo/source`, with
repeated `slot` parameters (at most eight), `textScale`, and `direction`. The
server prepares each available member's ordinary Goo view in `sm`/`md`/`lg`
from the same immutable namespace as that child page, reusing one catalog for
the page. The response adds `presentations: [{key, slot, bundle}]` alongside
membership; these packets never become selection or capture payloads.

The adapter validates all packets, their profile and contexts, subject/lifetime,
and page epoch before admitting the refreshed projection. Existing rows remain
visible during preparation or failure. New record rows mount prepared content
before attachment, avoiding a raw-path placeholder while hydration runs. The
variants seed the existing presentation owner's cache; narrower-than-sm panes
and later scale/direction changes still use the ordinary contextual render API.
Structural branches without a record retain their path labels. Preparation
failure rejects the page and reports the backend diagnostic without partially
replacing the tree.

`goo-topoi.js` adapts native lists, Mash `goo-tree`, and Mash `goo-tidy-tree`.
The explorer builds its own pinned component bundle, so selecting the debugger
mount is unnecessary. `extras/flake.nix` pins the profile- and patch-enabled Mash revision
`16b8a9079e8a45dc2681cf3210e1d186e5cbe622` without dependency overrides.
Production asset builds verify the vendored profile against that Nix artifact.

The application gate installs the test-only `panes` fixture; `topoi_demo` shows a
list, outline, and diagram sharing a detail view and a descendant capture action.
````

Source: `reaver/extras/mounts/explorer/PANES.md`, lines 131–186. Verbatim snapshot excerpt.

````markdown
## Continuity and guards

The accepted selection is the only choice authority. A follower derives its
binding from that selection; it has no writable navigation subject. Membership
changes can preserve the encounter when subject bindings are equal. Ordinary
live data revisions preserve encounter and recipe. `become` changes only that
encounter's recipe. Choosing the same member is a no-op.

Pointer activation selects. Arrow keys move list focus; Enter selects. Clear
uses the same local protocol. Nested buttons, inputs and links own their events.
Usable row references remain usable after another member is selected. Intent
sequence is allocated by the session; retrying an old intent cannot undo a later
choice. Handles from another session, retired incarnations and reflected JSON
snapshots cannot execute local operations.

The real Goo text inputs in following panes retain working values separately
from server seed values. A dirty departure shows an inline Stay / Discard and
leave decision. Accepted selection and its usable encounter remain unchanged
while a candidate is pending. All affected followers are guarded. A newer
candidate supersedes an older guard result. Checkpoint callbacks can succeed
without implying that a superseded presentation transition also succeeds.
This repository has no independent draft/checkpoint service; the built-in UI
provides discard/refusal, not a fabricated autosave service.

Native pane fragments and editable member rows use the same working-input and
departure guards as following panes. Retiring a row or native fragment removes
its guards and resources after admission. A guard for a suspended pane appears
in the visible workspace so its decision remains reachable.

Composition defers structural reevaluation and refuses destructive departure.
Retirement releases resources only after guards allow it. Full page reload has
no retained UI-session continuity. A refresh explicitly observes domain/source
changes; this slice does not add background watchers.

`split` uses equal flexible columns with a deterministic one-column narrow
fallback. `deck(key)` uses local keyed alternative selection. It seeds the first
child once, preserves an active child across reorder and picks the first
survivor after guarded removal. Empty decks have no active child. Inactive
panes are suspended and removed from keyboard navigation while keeping inputs
and encounters; their subject view is refreshed before reuse. `pane_stack`
overlaps panes in declaration order without history, modality or focus traps.

Asynchronous subject output carries owner incarnation, accepted selection
revision, encounter, recipe generation and member evidence. Stale output cannot
replace the current encounter. Old content is marked loading and made inert
while a newly accepted subject loads. Queue and adjacent pane owners survive
that detail update.

Filtering/unloading a known member is not deletion. Confirmed deletion leaves
an explicit unavailable selection. A recreated record at the same path does not
inherit the old choice. An incompatible source lifetime requires removing and
redeclaring the selection, rather than silent rebinding/reseeding.
When the displayed workspace root itself is replaced, the host guards and closes
the old controller, then creates a fresh session for that root lifetime. Ordinary
data edits and render-context changes continue within the existing session.
````

## Part V — Provenance and verification limits

The prose was prepared from the current local working trees on 17 November 2026. The package is a static snapshot. Commit IDs below identify repository bases; they do not identify all quoted content because the working trees contain uncommitted changes. Full source-file hashes and excerpt ranges identify the captured versions more precisely. Paths here are labels only.

The assembly check verifies that every quoted excerpt equals the indicated source lines, that the essay is included, and that the document has balanced code fences. It does not compile the system, rerun runtime tests, establish all-platform parity, or certify future refactor choices. The evidence consists of current source and authored contracts/tests. Do not infer the existence of omitted capabilities from a proposal or from a frontend's acceptance of a constructor.

An offline agent should say which conclusions follow from these excerpts, which are design recommendations, and which would require later repository inspection or live verification.

Base commit, `reaver`: `d0deab276e4e268941d5b61199c6c69538eb9f61`.

Base commit, `shrine-egui`: `3f21ac1c7d1fbf3cafef3ab789318cb2b2a45d9e`.

Base commit, `shrine_ios`: `e1dbdfde6dd5870d85b41cfdef0d67e615ecd721`.

### Excerpt inventory

Multiple ranges from one source share its full-file SHA-256. The inventory includes only embedded evidence, not an instruction to fetch other files.

| Source label | Included lines | Full source SHA-256 |
| --- | --- | --- |

| `reaver/src/foil/sys/shrine.foil` | 1–98 | `7fee06f1134b6a48d3541b2ae06ccf0b8e21c7a2df77706bd075510f925a4927` |

| `reaver/src/foil/sys/view.foil` | 1–40 | `55bc52975f737e608b4d02ef64061591105fc883b12f0d4129495cd1b3274a1b` |

| `reaver/src/foil/grove_role_runtime.foil` | 1–32 | `b18b295ccd0b655de65e6f53aca10d5f1203d644b6e400e367c59ada812eb26b` |

| `reaver/src/foil/grove_views.foil` | 231–240 | `7914e5f5986634299a46cafb6792e42282cf3e8df4d769667dc2e732b15a15a8` |

| `reaver/src/foil/grove_views.foil` | 274–324 | `7914e5f5986634299a46cafb6792e42282cf3e8df4d769667dc2e732b15a15a8` |

| `reaver/src/foil/grove_views.foil` | 355–423 | `7914e5f5986634299a46cafb6792e42282cf3e8df4d769667dc2e732b15a15a8` |

| `reaver/src/foil/grove_views.foil` | 564–637 | `7914e5f5986634299a46cafb6792e42282cf3e8df4d769667dc2e732b15a15a8` |

| `reaver/extras/mounts/goo/types.foil` | 115–201 | `b22c3ddcde81b83743e377b83be56de5c71cbbf431720e41c5caa127597408c8` |

| `reaver/extras/mounts/goo/types.foil` | 202–277 | `b22c3ddcde81b83743e377b83be56de5c71cbbf431720e41c5caa127597408c8` |

| `reaver/extras/mounts/goo/types.foil` | 364–397 | `b22c3ddcde81b83743e377b83be56de5c71cbbf431720e41c5caa127597408c8` |

| `reaver/extras/mounts/goo/text.foil` | 1–61 | `831ec9311220a141d21c3eb01fa40d5109954e6d2c2808493a812d60eaed07e8` |

| `reaver/extras/mounts/explorer/goo_bridge.foil` | 231–351 | `da19fabde902602f773d6fe08dae43d8b2b5c01420672e925de46887d8c041b4` |

| `reaver/extras/mounts/explorer/goo_bridge.foil` | 381–410 | `da19fabde902602f773d6fe08dae43d8b2b5c01420672e925de46887d8c041b4` |

| `reaver/extras/mounts/explorer/goo_theme.foil` | 1–72 | `a2c2b533de43b087fe92311e6683afe6215132c3ce7f8a3353218c8f925220d3` |

| `reaver/extras/mounts/goo/HTML.md` | 9–58 | `864b9e693678a6d5d320912b42ef81344e4c34575a91d8a4ea4106b0496f3946` |

| `reaver/extras/mounts/goo/protocol/README.md` | 1–42 | `8dd50a2dbee435f1c0cb3893cf5d732993446efe88777efe24a294b82b1210c2` |

| `reaver/extras/mounts/goo/protocol/README.md` | 55–59 | `8dd50a2dbee435f1c0cb3893cf5d732993446efe88777efe24a294b82b1210c2` |

| `reaver/extras/mounts/explorer/goo_panes.foil` | 11–20 | `884d43136e3ac6db913e408eddd81eb16c8c3739ee682a548abeb3307ac52f45` |

| `reaver/extras/mounts/explorer/goo_panes.foil` | 107–144 | `884d43136e3ac6db913e408eddd81eb16c8c3739ee682a548abeb3307ac52f45` |

| `reaver/extras/mounts/goo/PORTABLE.md` | 150–181 | `24771498e48dff32b35e4bd3374e08c8ffb5f89a9ad30eb04433b8ea83e2a3b9` |

| `reaver/extras/mounts/goo/PORTABLE.md` | 182–230 | `24771498e48dff32b35e4bd3374e08c8ffb5f89a9ad30eb04433b8ea83e2a3b9` |

| `reaver/src/foil/goo_runtime.foil` | 113–136 | `ebdf9c69a0106b34d5b51913361cfe03094af52d62cd628459a2c4abbf61a2f8` |

| `reaver/src/foil/goo_runtime.foil` | 217–269 | `ebdf9c69a0106b34d5b51913361cfe03094af52d62cd628459a2c4abbf61a2f8` |

| `reaver/src/foil/goo_runtime.foil` | 397–453 | `ebdf9c69a0106b34d5b51913361cfe03094af52d62cd628459a2c4abbf61a2f8` |

| `reaver/extras/mounts/explorer/goo-topoi.js` | 1–93 | `b0e5cfe5ffe64c818b746d042f6610a753f5bb5698bc7fd4bb93c04e188b619f` |

| `shrine-egui/src/transport.rs` | 1–117 | `7349b253e39af2b476715147f0ccb9206c747fae55c31f811ad1b1c1e8ce1fbe` |

| `reaver/src/foil/goo_runtime.foil` | 577–659 | `ebdf9c69a0106b34d5b51913361cfe03094af52d62cd628459a2c4abbf61a2f8` |

| `shrine-egui/src/session.rs` | 1–190 | `d48652dbc80bccd38a00039be18691c5d4945303383e868a5b82d052779eadab` |

| `shrine-egui/src/session.rs` | 289–366 | `d48652dbc80bccd38a00039be18691c5d4945303383e868a5b82d052779eadab` |

| `shrine-egui/src/session.rs` | 500–676 | `d48652dbc80bccd38a00039be18691c5d4945303383e868a5b82d052779eadab` |

| `shrine-egui/src/explorer.rs` | 433–515 | `f9f5b21ebcbe3733e59900486b5d1ceeaf298eafbe08cd02e918894068362bd3` |

| `shrine_ios/shrine_ios/Goo/GooWorkspaceModels.swift` | 1–102 | `0daf02448fba945b4c1857601ddf1f74439c8778df3f542b1c55b0c47e5d1f98` |

| `reaver/extras/mounts/goo/PORTABLE.md` | 509–613 | `24771498e48dff32b35e4bd3374e08c8ffb5f89a9ad30eb04433b8ea83e2a3b9` |

| `reaver/extras/mounts/goo-style-zoo/main.grove` | 160–203 | `748a34a4a081a7c25b57db948c042129a968ea1aba4e1408f3efcf202c9c0bb4` |

| `reaver/extras/mounts/torah-study/chunks.grove` | 95–156 | `df60ac61cbeba4dc40e5593ea80a80dd4a9867f087551125e82202b80305c4ff` |

| `reaver/extras/mounts/goo/PORTABLE.md` | 272–323 | `24771498e48dff32b35e4bd3374e08c8ffb5f89a9ad30eb04433b8ea83e2a3b9` |

| `shrine-egui/tests/explorer.rs` | 1–63 | `708423ea2c2c419eae155e03380dbbd8687531c4bac667c8ca6aa4422e626452` |

| `reaver/extras/mounts/explorer/PANES.md` | 430–480 | `491420212e25982ecc7e5c77908ed88e08432831ae568bd6d506bf3cd50ec61b` |

| `reaver/extras/mounts/explorer/PANES.md` | 131–186 | `491420212e25982ecc7e5c77908ed88e08432831ae568bd6d506bf3cd50ec61b` |

End of self-contained handoff.
