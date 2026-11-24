# Goo and Shrine from records to interfaces

Design note, 17 November 2026. **Current** describes the inspected Reaver and egui implementation. **Proposal** describes a possible refactor, not syntax or capabilities already available. The source map at the end points to the contracts behind the explanation.

Shrine gives objects addresses, typed properties, versions, and behavior. Grove declares the shapes of those objects and the ways to work with them. Goo turns those declarations into presentations and workspaces. A native client realizes those presentations and retains the local work that must survive repainting, navigation, and delayed responses.

The central design question is what an emitted element obliges the system to do. A title needs typography and measurement. An editor needs a working value, composition, and a save protocol. A tree needs membership, disclosure, selection, and bounded loading. These obligations should be visible in the language and its intermediate representations.

My recommendation is to keep a small, typed surface language, make interaction requirements explicit, and separate collection sources, selection types, and topological presentations. Keep `@view` and `@pane` as useful authoring boundaries while replacing their growing constructor blacklist with explicit composition rules. Broaden topoi beyond namespace trees through new source contracts, rather than through special-purpose client widgets.

## Shrine from zero

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

Reaver is the implementation language/runtime layer in this repository; Foil supplies much of Shrine and Goo's implementation. Grove is the declaration language used by applications. PLAN is the underlying execution substrate. An application author usually works with Grove declarations, Foil domain functions, and namespace records rather than with PLAN directly. [1–3]

## How a record becomes an interface

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

`show(value, slot)` chooses a formatter from the value's declared type. `present(value, slot)` expands a matching object view. These are composition operations, not necessarily final rendering primitives. Current selection requires an unambiguous match; there is no general precedence system for competing views. The expression language is also intentionally restricted: direct fields and literals are supported, rather than arbitrary application computation inside a render expression. [3, 4]

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

The current separation is enforced: `present` selects views, while `pane(...)` composes pane declarations. Panes have explicit selection ports. Pane composition currently requires the current receiver and matching receiver role. An ordinary view cannot indirectly import pane-only behavior through `present`. Those are today's language restrictions, not inevitable properties of a future design. [4, 5]

## What Goo compiles and what the client owns

There are two related paths through Goo today.

An **ordinary surface** goes through declaration binding, typed Goo source, normalization, node identity assignment, visibility, semantic adjacency, measurement, wrapping, layout, and prepared output. Shared theme rules are applied after semantic resolution and before measurement. The final packet contains boxes, static text lines and baselines, pinned fonts, paint recipes, accessibility semantics, and separately joined control bindings. HTML and native painters consume this result.

A **pane description** retains workspace structure. Ordinary subtrees become prepared `native` fragments; selections, followers, topoi, decks, splits, and patches have structured contracts. The client allocates regions and prepares ordinary surfaces at their actual allocated widths. A pane is not simply one giant ordinary display list. [5–7]

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

On activation, an invocation freezes its receiver evidence, publication, control route, input values, and any captured selection evidence. Retrying sends the same ID and body. A timeout is an unknown outcome, not evidence that the save failed. A completion belongs to its originating owner, including when that owner is hidden. Any element taxonomy that permits editing or actions inherits these obligations. [8]

## What counts as an element today

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

The surface IR is already narrower and more strongly typed than the authoring constructor list. The opportunity is to make its other output families equally explicit, not merely rename the source constructors. [4, 6, 7]

## A useful definition of native

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

## What topoi mean in the current system

Here, a *topos* is a presentation of source membership connected to a local selection. The implementation does not supply the category-theoretic structures associated with the mathematical word. Its practical meaning is a place in which members can be encountered and chosen.

Three responsibilities are already separable:

1. A **source** materializes members and evidence about them.
2. A **selection owner** retains the accepted choice and governs attempts to change it.
3. A **topos adapter** arranges members, exposes navigation and focus, and proposes choices.

A follower observes accepted selection and chooses an ordinary presentation for its subject. It does not maintain a competing selected object. A selection can exist without a visible topos, as in the zoo's single-record follower.

The three current renderers are `list`, `list_tree`, and `diagram_tree`. The outline and diagram show a parent relation; the list shows membership sequentially. They share source/member evidence and selection semantics. Changing arrangement should not create a fresh choice authority or discard member work.

The source implementation is more specific than that abstract design. Members are namespace records, with `key` currently equal to `subject` and both spelled as paths. Source and member lifetimes, expected data versions, availability, and read axis travel with membership. Tree projections add parent relations. Structural branches may be focusable and expandable without being available record subjects.

Outline materialization uses bounded child pages, continuation evidence, and a consistent epoch. An unloaded branch is not an empty branch, and a filtered or unloaded member is not a deleted record. The browser adapter allows other topoi sharing that selection to use the materialized source. The egui workspace validator currently admits tree selections and the outline/diagram renderers; the compiler's broader vocabulary should not be mistaken for every consumer's supported set. UIKit's broader renderer specification likewise contains proposals alongside implementation descriptions. [9–11]

## The design space for topoi

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

## The Torah reader as a test case

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

**Proposal:** make range, member, edge, and cell selections typed variants sharing lifecycle machinery. Share intent ordering, guards, capture, and history rules. Keep validation specific to each evidence type. Do not manufacture namespace records for every transient gesture solely to fit a path-only selection API. [12]

## Four possible language architectures

| Architecture | What it makes easy | Main cost |
| --- | --- | --- |
| Expand the current view/pane split | Incremental changes; object views remain usable in labels, rows, and followers | More ad hoc pane-only constructors and behavioral role strings unless output types improve |
| One universal retained element graph | Uniform nesting; any component can introduce state and children | A small summary can secretly allocate a workspace; ownership, recursion, and guards become implicit |
| Server emits a complete scene and all geometry | Consistent whole-screen layout and straightforward replay | Scrolling, virtualization, camera feedback, and platform editing demand local protocols anyway; input latency becomes central |
| Typed output families with explicit interaction requirements | Clear composition boundaries; reusable generic hosts; new topoi without application-specific clients | More work to define interfaces and deliberate bridges between families |

The first is reasonable if the immediate priority is compatibility. The second fits a component-oriented authoring model, but requires an effect or ownership discipline to prevent hidden state from proliferating. The third is attractive for fixed scenes and inspector replay; it is costly as the only model for large interactive workspaces. The fourth is my preferred target, with gradual migration from the first.

Uniform authoring syntax and uniform runtime semantics are separate choices. A single component syntax can still return different typed contracts. Conversely, keeping `@view` and `@pane` does not require maintaining parallel expression evaluators or action systems.

## A proposed boundary for views and panes

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

## Tensions the refactor needs to resolve

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

## A practical refactor sequence

1. **Classify the existing constructors by output and behavior.** Record which are syntax sugar, surface nodes, binding declarations, owners, arrangement policies, and host capabilities. Reject unsupported mappings during compilation rather than after mounting.
2. **Type the output families.** Keep authoring aliases initially. Introduce explicit surface, workspace, collection, scene, and interaction descriptions, with checked bridges and required capabilities. Preserve current prepared display admission and action evidence.
3. **Extract source and selection contracts.** Keep namespace sources as one implementation. Make subject, membership, occurrence, lifetime, and revision distinct. Keep “not loaded,” “unavailable,” and “deleted” distinguishable.
4. **Move existing topoi onto those contracts.** Demonstrate that outline and diagram can share selection and member work while changing arrangement. Treat current client support as a capability matrix, not an assumption of parity.
5. **Add one relation source and typed text-range selection.** Use the Torah library, reader, anchored margin, and backlinks as the proving application. A graph view should consume declared relationships without any Torah-specific client code.
6. **Add a table only with its full contract.** Define columns, row/cell selection, sorting, virtualization, and editing bindings before choosing the visual widget. Calendar and board variants can follow actual application needs.

The acceptance cases should exercise semantics, not only screenshots: the same subject in two occurrences; changing arrangement with a dirty member editor; a hidden editor receiving a save completion; a removed and recreated subject; a stale range; query pages from different revisions; a refused or superseded transition; and an exact retry after a timeout. Include actual platform keyboard, IME, scrolling, and accessibility behavior for every newly claimed interactive capability.

The criterion for a successful refactor is that a new domain can declare its data, relationships, presentations, and offered operations without adding domain rules to egui or UIKit. A small primitive vocabulary helps only if its contracts can express those distinctions and preserve the user's work.

## Source map

These references describe the inspected checkout, including uncommitted work. This note does not claim a new runtime verification run. Earlier architecture documents contain historical limits and proposals; executable validators take precedence when those differ.

1. [Shrine records, care scopes, and lifetimes](../../src/foil/sys/shrine.foil); [namespace publications and history](../../src/foil/namespace.foil).
2. [Derived record and tree constructors](../../src/foil/sys/shrine.foil); [slot vocabulary](../../slots/README.md).
3. [Grove role and action contracts](../../src/foil/grove_role_runtime.foil); [action compilation](../../src/foil/grove_actions.foil).
4. [Goo authoring reference](../../src/grove/GOO.md); [constructor validation, view selection, and pane composition](../../src/foil/grove_views.foil).
5. [Pane contracts and lifecycle](../mounts/explorer/PANES.md); [pane description production](../mounts/explorer/goo_panes.foil); [route host](../mounts/explorer/goo_workspace_mount.foil).
6. [Binding and ordinary surface lowering](../mounts/explorer/goo_bridge.foil); [typed surface IR](../mounts/goo/types.foil); [shared theme resolution](../mounts/explorer/goo_theme.foil).
7. [Prepared rendering boundary](../mounts/goo/HTML.md); [portable paint, editing, range, and binding contracts](../mounts/goo/PORTABLE.md).
8. [Server action admission and invocation receipts](../../src/foil/goo_runtime.foil); [egui editor owners](/Users/test/dev/shrine-egui/src/session.rs); [frozen client invocations](/Users/test/dev/shrine-egui/src/transport.rs).
9. [Server membership and paging](../../src/foil/goo_runtime.foil); [web topos adapter](../mounts/explorer/goo-topoi.js); [selection/session implementation](../mounts/explorer/goo-session.js).
10. [egui workspace admission](/Users/test/dev/shrine-egui/src/explorer.rs); [egui workspace realization](/Users/test/dev/shrine-egui/src/explorer_app.rs).
11. [UIKit renderer specification](/Users/test/dev/shrine_ios/GOO_RENDERER_SPEC.md); [UIKit current scope](/Users/test/dev/shrine_ios/README.md). The specification explicitly labels some boundaries as proposals.
12. [Linked-text model and reader](../mounts/torah-study/README.md); [routed reader and comparison declarations](../mounts/torah-study/chunks.grove); [actual zoo views and workspace](../mounts/goo-style-zoo/main.grove).
13. [Real pane fixture](../tests/fixtures/panes/README.md); [incremental source fixture](../tests/fixtures/tree-pages/README.md); [egui page and guard tests](/Users/test/dev/shrine-egui/tests/explorer.rs).
