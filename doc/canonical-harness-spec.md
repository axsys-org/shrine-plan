Use this as the **canonical harness / personal-OS spec**. I’d give Codex the whole thing and tell it not to reinterpret this as a request for another framework.

> # SHRINE / CANVAS — CANONICAL HARNESS SPEC
>
> Treat this as the standing product and architecture contract.
>
> **Do not build a giant framework implementing every behavior described below.** The bet is that most of this behavior should emerge naturally from a small set of general native primitives plus a capable OpenRouter agent with broad namespace context.
>
> Your job is to expose enough of the real Shrine world to the agent, give it generic actions over that world, keep the environment usable and legible, and then **use the system for a long time**.
>
> Only add new machinery when actual use proves a missing primitive.
>
> The system should not become:
>
> ```text
> SpreadsheetFramework
> TimelineFramework
> PDFFramework
> AgentRepairFramework
> FlowFramework
> UIReuseFramework
> ```
>
> If those concepts can be expressed through the existing substrate, let the agent express them.
>
> The thesis we are testing is:
>
> ```text
> typed persistent NS
> + stable refs
> + care-scoped path bindings
> + Grove structure/templates
> + Foil computation/dependencies/events
> + decomposed Goo presentation
> + transactions/diffs/history/provenance
> + a model that can inspect and manipulate all of that
>
> =
>
> a personal computational environment
> whose software can be continuously composed,
> extended, repaired and reused from the world itself
> ```
>
> ---
>
> ## 1. ROLES
>
> For this phase:
>
> ```text
> CODEX
> = operator / developer / aggressive dogfooder
>
> OPENROUTER MODEL
> = actual in-system agent
>
> SHRINE
> = authoritative persistent computational world
>
> GROVE
> = native structure / templates / reusable shape
>
> FOIL
> = typed behavior / dependency / execution / reaction
>
> GOO
> = decomposed presentation
>
> CANVAS
> = human/agent construction and use surface
>
> BROWSER/HOST
> = minimal physical boundary
> ```
>
> Do not fake the model's intelligence in browser-side heuristics.
>
> The OpenRouter model should receive enough context/tools to inspect the namespace, definitions, types, available machinery, bindings, failures and proposed diffs and make the actual reasoning decisions.
>
> The host should provide irreducible physical capabilities such as rendering, pointer/keyboard input, files, perhaps media decoding/tracking helpers, etc. Application semantics should remain native.
>
> ---
>
> ## 2. THE WORLD IS NS, NOT APPS
>
> There is no privileged universal `App` ontology.
>
> These can all be native material:
>
> ```text
> Person
> Task
> Image
> Matrix
> Spreadsheet-like construction
> Compiler
> Editor
> IDE-like construction
> Timeline
> Calendar
> Game
> Simulation
> Document
> Parser
> UI presenter
> Foil function
> application result
> workflow
> Canvas itself
> ```
>
> “Application” is human shorthand for a recurring arrangement of native structure, bindings, behavior and presentation.
>
> The central rule is:
>
> ```text
> Thing + Thing -> Thing
> ```
>
> A successful construction remains native material and can be selected, reused, decomposed, extended and composed again.
>
> Software is material, not a terminal artifact.
>
> ---
>
> ## 3. NS SHAPE
>
> Keep the ontology simple.
>
> A Thing may have:
>
> ```text
> stable identity / REF
> name
> description
> typed fields
> nested Things
> refs
> collections
> maps
> sequences
> matrices
> tensors
> trees
> graphs
> derived values
> behavior
> presentation associations
> history/provenance
> ```
>
> Do not explode dense values into millions of namespace records.
>
> This is valid:
>
> ```text
> Image#7
> └── pixels : Matrix<Pixel>
> ```
>
> and:
>
> ```text
> Image#7.pixels[x,y]
> ```
>
> is already an exact native focus.
>
> More generally:
>
> ```text
> Spreadsheet  (row,col)      -> Value / Ref
> Image        (x,y)          -> Pixel
> Tensor       (i,j,k,...)    -> T
> Text         range          -> Span
> AST          path/node      -> ASTNode
> Timeline     track/item     -> Event
> Game board   (x,y)          -> Tile
> Graph        node/edge      -> Thing
> ```
>
> This general idea of **typed addressable shape** is fundamental.
>
> ---
>
> ## 4. SELECTION IS A FIRST-CLASS OPERATION
>
> Clean up the NS side panel and make it a serious selection/navigation surface.
>
> It should not look like a raw AST debugger.
>
> I should be able to select:
>
> ```text
> one Thing
> one field
> one result path
> several unrelated paths
> a collection
> a subtree
> a recursive subtree
> an image region/mask
> an artifact range
> an existing application construction
> reusable machinery
> ```
>
> Selection should expose enough information to the agent and user to understand:
>
> ```text
> identity
> path
> type
> cardinality
> care scope
> writability / authority
> dependencies
> provenance where relevant
> ```
>
> The user should not have to manually specify every binding. Selection + description should often be enough for the model to infer reasonable structure.
>
> ---
>
> ## 5. CARE
>
> Bindings are not simply “this app uses this Thing.”
>
> Bindings operate at a **care scope** over paths.
>
> An application may care about:
>
> ```text
> Project#4
> ```
>
> or:
>
> ```text
> Project#4.tasks
> ```
>
> or:
>
> ```text
> Project#4.tasks[*].deadline
> ```
>
> or recursively:
>
> ```text
> Project#4.tasks[*].subtasks[*...]
> ```
>
> The selected/cared path exposes a typed shape.
>
> Different machinery can care about different portions of the same Thing.
>
> Care should naturally constrain:
>
> ```text
> dependencies
> invalidation
> binding compatibility
> presentation
> write scope
> repeated/recursive template instantiation
> ```
>
> Do not build a giant speculative care framework if existing path/dependency semantics already express enough. Use the minimum representation needed.
>
> ---
>
> ## 6. WHAT AN “APPLICATION” REALLY IS
>
> Conceptually, an application-like construction consists of:
>
> ```text
> INPUT BINDINGS
>     native path(s)
>     typed shape
>     care
>     cardinality
>     recursion/template rules
>
> OUTPUT BINDINGS
>     real writable native path(s)
>     typed shape
>     care
>     cardinality
>
> RESULT PATHS
>     app-owned native results/state
>     NOT pretending to be source mutation
>
> EVENT BINDINGS
>     keyboard
>     pointer
>     user actions
>     time
>     external observations
>     NS changes
>     actor/message events
>
> FOIL
>     typed computation over bindings
>     dependencies
>     reactions
>     transformations
>     actions
>     state transitions
>
> GOO
>     decomposed care-scoped UI
>     over exact bound/result paths
> ```
>
> Do not force an application into “read-only” or “mutating” categories.
>
> A single construction may:
>
> ```text
> read some paths
> mutate some paths
> derive results elsewhere
> maintain local result state
> present overlays
> react to events
> produce new Things
> ```
>
> simultaneously.
>
> ---
>
> ## 7. INPUT/OUTPUT BINDINGS ARE TYPED
>
> Foil works over typed bindings.
>
> Application commitments should therefore be matchable against selected native path shapes.
>
> Example:
>
> ```text
> Timeline expects:
>
> Many<T>
> T -> Label
> T -> Interval
> ```
>
> Selected:
>
> ```text
> Project.tasks : Many<Task>
>
> Task.title    : Text
> Task.deadline : Date
> ```
>
> The model should reason:
>
> ```text
> Many<Task> matches Many<T>
> Task.title can satisfy Label
> Task -> Interval is missing
> ```
>
> Then search for existing machinery.
>
> Maybe:
>
> ```text
> TaskScheduleEstimate(Task) -> Interval
> ```
>
> already exists.
>
> If not, perhaps `Task.deadline` can be adapted.
>
> If several choices are semantically valid and the intended meaning matters, ask the user.
>
> If it is merely computational, solve it.
>
> Preference order:
>
> ```text
> exact fit
> -> existing reusable projection
> -> partial reuse/composition
> -> small adaptation
> -> minimum new machinery
> -> ask user only for real semantic ambiguity
> ```
>
> ---
>
> ## 8. RECURSIVE AND MULTI-CARDINALITY BINDINGS
>
> Do not manually create thousands of repetitive bindings.
>
> Templates should be generative.
>
> Example:
>
> ```text
> for each Person p in Organization.people:
>
>     PersonRow(p)      <-> p
>     NameCell(p)       <-> p.name
>     SalaryCell(p)     <-> p.salary
>     Avatar(p)         <-> p.avatar
> ```
>
> Same idea:
>
> ```text
> for each Matrix coordinate (x,y):
>     PixelOccurrence(x,y) <-> Matrix[x,y]
> ```
>
> or:
>
> ```text
> recursively for each AST node n:
>     NodeOccurrence(n) <-> AST.nodes[n]
> ```
>
> Repeated correspondence should be generated from structure/cardinality, not stored as endless one-off host records.
>
> ---
>
> ## 9. UI IS DECOMPOSED
>
> This is non-negotiable.
>
> Do not make:
>
> ```text
> SpreadsheetWidget <-> Spreadsheet
> TimelineWidget    <-> Timeline
> IDEWidget         <-> IDE
> ```
>
> Rich UI can be visually fused while remaining semantically decomposed.
>
> Spreadsheet:
>
> ```text
> Row(p)            <-> Person#p
> NameCell(p)       <-> Person#p.name
> SalaryCell(p)     <-> Person#p.salary
> Avatar(p)         <-> Person#p.avatar
> WorkloadBadge(p)  <-> /results/workload[p]
> ```
>
> IDE:
>
> ```text
> source editor text   <-> Source.text
> AST outline node     <-> AST.nodes[n]
> diagnostic underline <-> Diagnostic.sourceLocation
> run action           <-> Foil action
> output pane          <-> /results/execution
> ```
>
> Image:
>
> ```text
> pixel(x,y)           <-> Image.pixels[x,y]
> selection mask       <-> /editor/results/selectionMask
> crop handle          <-> exact geometry/result path
> ```
>
> The model should be able to reuse:
>
> ```text
> one presenter
> one interaction behavior
> one repeated template
> half an existing surface
> one diagnostic treatment
> one editor component
> one graph presentation
> ```
>
> without importing an entire opaque application.
>
> UI itself is reusable computational vocabulary.
>
> ---
>
> ## 10. CANVAS IS YOUR FRIEND
>
> Do not punish yourself with enormous DOM hierarchies when a Canvas/SVG/raster surface is more appropriate.
>
> Use DOM/native controls where text editing, accessibility, forms, IME and focus benefit.
>
> Use Canvas/SVG/raster aggressively for:
>
> ```text
> grids
> image editors
> graphs
> timelines
> node systems
> games
> simulations
> geospatial views
> masks
> annotations
> handles
> arbitrary generated interfaces
> ```
>
> Canvas is a rendering escape hatch, not an ontology.
>
> Every meaningful occurrence must still resolve to exact native correspondence:
>
> ```text
> screen point
> -> rendered occurrence
> -> exact NS path / typed selection
> -> Foil action
> ```
>
> **Canvas for visual freedom; NS for truth.**
>
> ---
>
> ## 11. MAKE THE UI ACTUALLY GOOD
>
> Stop using generic debug cards as the default proof.
>
> The environment should increasingly resemble real software.
>
> Build actual usable surfaces such as:
>
> ```text
> spreadsheet
> table
> graph/org chart
> timeline
> calendar
> document reader
> image editor
> source editor
> IDE-like environment
> project planner
> map/geospatial view
> simulation
> game
> ```
>
> These are expressiveness tests, not privileged types.
>
> The Canvas should feel like a place where regions can actually become the software being constructed.
>
> ---
>
> ## 12. REAL BEHAVIOR, NOT STATIC MOCKUPS
>
> Applications should actually work.
>
> Exercise:
>
> ```text
> keyboard
> pointer
> drag/drop
> selection
> text editing
> painting
> resizing
> time
> reactions
> dependency updates
> state transitions
> undo/redo
> subscriptions
> computation
> ```
>
> Meaning belongs in native event/Foil bindings, not random browser-side app logic.
>
> Example:
>
> ```text
> Key("Enter")
> -> current native focus
> -> applicable native action
> -> Foil
> ```
>
> ---
>
> ## 13. FLOWS
>
> A flow is **not** opaque Zapier-style app boxes passing blobs.
>
> It is native constructions connected by exact paths/results/events in the same world.
>
> Example:
>
> ```text
>                        Organization.people
>                               │
>               ┌───────────────┼───────────────┐
>               ▼               ▼               ▼
>          Spreadsheet       Org Graph      Workload
>               │                               │
>               │                        /results/load
>               │                               │
>               └─────────────┬─────────────────┘
>                             ▼
>                           Planner
>                             │
>                    /results/conflicts
>                             │
>                             ▼
>                          Timeline
> ```
>
> Flows may branch and merge.
>
> Any intermediate path/result can be:
>
> ```text
> selected
> viewed
> edited if writable
> bound elsewhere
> used to make a new application
> composed with another construction
> ```
>
> `app -> app -> app` is human shorthand.
>
> Underneath:
>
> ```text
> paths
> -> native machinery
> -> paths
> -> native machinery
> -> paths
> ```
>
> ---
>
> ## 14. PARTIAL REUSE IS MORE IMPORTANT THAN “APP REUSE”
>
> Do not think only in terms of reusing complete applications.
>
> Reuse can happen at any scale:
>
> ```text
> type fragments
> path projections
> Foil transforms
> UI presenters
> event behavior
> ingestion mappings
> formatting rules
> recursive templates
> result computations
> entire applications
> ```
>
> A new spreadsheet-like thing might reuse:
>
> ```text
> repeated row machinery
> Money presenter
> writable scalar editor
> filtering
> sorting
> formula dependency behavior
> ```
>
> without importing some monolithic Spreadsheet object.
>
> A new IDE-like thing may reuse:
>
> ```text
> Source editor
> diagnostics
> compiler action
> AST tree
> ```
>
> individually.
>
> Application boundaries should become increasingly irrelevant.
>
> ---
>
> ## 15. THE AGENT'S JOB
>
> The OpenRouter model should act as the intelligence layer over the accumulated native world.
>
> Its default loop:
>
> ```text
> inspect
> search
> recognize
> match
> reuse
> compose
> adapt
> repair
> invent only what is missing
> ```
>
> Not:
>
> ```text
> prompt
> -> regenerate whole app
> ```
>
> Given a new problem:
>
> ```text
> inspect selected/native subjects
> inspect their cared typed shapes
> inspect requested application commitments
> search existing machinery
> reuse compatible pieces
> identify precise holes
> fill only those holes
> Pure-test speculative computation where appropriate
> preview native diff
> commit
> retain useful new machinery
> ```
>
> Over time the model should need to invent less.
>
> Desired trajectory:
>
> ```text
> early:
> lots of invention
>
> later:
> mostly search/reuse/composition/repair
> ```
>
> Every successful construction increases the world's future vocabulary.
>
> ---
>
> ## 16. PROPOSED DIFFS MUST BE VISIBLE
>
> Do not let the agent silently modify the world.
>
> Before meaningful commits, expose the actual proposed native change.
>
> Show:
>
> ```text
> what was inspected
> what bindings matched
> what machinery was reused
> what failed to fit
> what is being created
> what is being mutated
> result paths
> affected dependents
> required write scope
> unresolved ambiguity
> ```
>
> Example:
>
> ```text
> APPLY Timeline
>
> ✓ /Project#4/tasks[*] : Many<Task>
> ✓ Task.title -> Label
> ! Task -> Interval missing
>
> REUSE:
>   Task.deadline : Date
>
> ADAPT:
>   DeadlineInterval(Task) -> Interval
>
> CREATE:
>   /Timeline#8/results/conflicts
>
> SOURCE MUTATIONS:
>   none
> ```
>
> If mutating:
>
> ```text
> ~ Person#17.salary
>     92,000 -> 98,000
>
> affected:
>     PayrollTable
>     BudgetSummary
>     TeamCostChart
> ```
>
> The fit/repair process should be legible UI, not merely:
>
> ```text
> Thinking...
> ```
>
> ---
>
> ## 17. CONSISTENCY AND CASCADES
>
> Shrine's dependency/reference graph should make breakage precise.
>
> Later changes may invalidate previously valid constructions.
>
> Examples:
>
> ```text
> field removed
> type changed
> cardinality changed
> reference changed
> source artifact updated
> result no longer matches downstream commitment
> permission changed
> Foil dependency becomes invalid
> UI binding no longer resolves
> ```
>
> Failure can propagate downstream or reveal that something upstream needs refinement.
>
> Desired loop:
>
> ```text
> change
>   ↓
> dependency cascade
>   ↓
> exact broken commitment
>   ↓
> agent receives failure + context
>   ↓
> search existing repairs/machinery
>   ↓
> surgical proposal
>   ↓
> visible diff
>   ↓
> commit
>   ↓
> cascade stabilizes
> ```
>
> Do not regenerate the whole application if one binding is wrong.
>
> Repair the smallest responsible structure.
>
> Ask the user only when the repair requires an actual semantic/preference decision.
>
> ---
>
> ## 18. SELF-HEALING, BUT DON'T TURN IT INTO A FRAMEWORK
>
> Do not implement a giant “self-healing subsystem.”
>
> Self-healing should mostly emerge because:
>
> ```text
> failures are precise
> dependencies are explicit
> refs are stable
> types are visible
> the agent can inspect the world
> the agent can author native repairs
> transactions are previewable
> ```
>
> If a runtime/shared invariant fails:
>
> ```text
> reproduce
> fix shared primitive
> add one focused regression
> return immediately to using Shrine
> ```
>
> Do not spend the next six hours creating hypothetical regression matrices.
>
> ---
>
> ## 19. FILES: GENERAL PRINCIPLE
>
> User should be able to attach arbitrary files to the model.
>
> Immediate proving formats:
>
> ```text
> CSV
> XLSX
> JSON
> XML
> text
> Markdown
> PDF
> image
> ```
>
> Later:
>
> ```text
> GIF
> video
> audio
> geospatial
> weird binary formats
> whatever the model can reasonably mediate
> ```
>
> Always keep the original raw artifact.
>
> Also expose a useful native representation even if no semantic interpretation is requested.
>
> ---
>
> ## 20. FILE FORMAT DOES NOT DICTATE NS ONTOLOGY
>
> CSV does not imply:
>
> ```text
> CsvDocument
> -> rows
> -> columns
> ```
>
> forever.
>
> It might become:
>
> ```text
> Many<Person>
> ```
>
> or:
>
> ```text
> Organization.people
> ```
>
> or:
>
> ```text
> List<Money>
> ```
>
> or one native scalar.
>
> Or the file may remain mostly external with only some anchored/projected paths.
>
> Serialization is evidence/addressing, not semantic destiny.
>
> ---
>
> ## 21. RAW NATIVE REPRESENTATION
>
> Even with no description:
>
> ```text
> image
> -> Image
>    └── pixels : Matrix<Pixel>
>
> text
> -> native text/spans
>
> Markdown
> -> native document/block hierarchy
>
> JSON
> -> native tree/maps/values
>
> XML
> -> native structured tree
>
> PDF
> -> pages/text/layout/images/tables where recoverable
> ```
>
> Preserve:
>
> ```text
> raw artifact
> +
> useful native representation
> ```
>
> Interpretation beyond that is optional.
>
> ---
>
> ## 22. INSPECT / SELECT / DESCRIBE
>
> File interpretation should be reachable through:
>
> ```text
> INSPECT
> SELECT
> DESCRIBE
> ```
>
> independently or together.
>
> Examples:
>
> ```text
> inspect this file
> select this table
> these rows are employees
> that's Alice
> extract these totals
> track this car
> ```
>
> No description should be mandatory.
>
> ---
>
> ## 23. ANCHORS
>
> Anchors connect exact external/artifact loci to exact native identity/path.
>
> Conceptually:
>
> ```text
> Anchor
> ├── artifactRef
> ├── selector
> │   ├── path
> │   ├── cell/range
> │   ├── text span
> │   ├── bbox
> │   ├── polygon
> │   ├── mask
> │   ├── timestamp interval
> │   └── object track
> ├── nativeRef/nativePath
> └── provenance/history
> ```
>
> Examples:
>
> ```text
> Sheet1!D42
>     <-> Invoice#9.total
>
> PDF page 3 bbox(...)
>     <-> Policy#4.limit
>
> image mask(...)
>     <-> Building#31.roof
>
> video track(...)
>     <-> Vehicle#9
> ```
>
> The same native Thing may be anchored across many artifacts.
>
> ---
>
> ## 24. MEDIA
>
> Media is where stable anchoring gets especially interesting.
>
> First observation:
>
> ```text
> user selection OR VLM/OCR/segmentation
>          ↓
> native region/mask
>          ↓
> anchor
>          ↓
> exact NS Thing/path
> ```
>
> Example:
>
> ```text
> Image#8.mask#4
>       <-> Building#31.roof
> ```
>
> Do not continuously call the LLM for every frame or update.
>
> Once correspondence exists, use cheap conventional perception where needed to maintain it.
>
> Host helper may use:
>
> ```text
> OpenCV
> segmentation
> registration
> optical flow
> feature matching
> tracking
> OCR
> whatever appropriate library exists
> ```
>
> The LLM can write a small Python helper if necessary.
>
> That helper's job is simply:
>
> ```text
> old media state
> + new media state
> -> corresponding new mask/region/observation
> ```
>
> It does not own semantic identity.
>
> Shrine does.
>
> ---
>
> ## 25. MASKS/REGIONS SHOULD BE NATIVE
>
> If corresponding regions are available:
>
> ```text
> M0 = old native mask
> M1 = new native mask
> ```
>
> then much of the interesting comparison can be ordinary native region algebra:
>
> ```text
> M0 ∩ M1      stayed
> M0 ∪ M1      total extent
> M1 - M0      appeared
> M0 - M1      disappeared
> IoU          continuity
> contains
> overlaps
> intersects
> distance
> area
> centroid
> trajectory
> existence
> ```
>
> Foil can express semantic behavior over those relationships.
>
> Example:
>
> ```text
> if VehicleMask was outside Gate
> and is now inside Gate
> -> Entered(Vehicle, Gate)
> ```
>
> or:
>
> ```text
> changedArea =
>     area(M1 - M0) / area(M0)
> ```
>
> The host does perception.
>
> Shrine/Foil interpret relationships.
>
> ---
>
> ## 26. MEDIA PROVENANCE
>
> Retain provenance across media versions:
>
> ```text
> Building#31.roof
> └── observations
>     ├── version 1 -> mask M1
>     ├── version 2 -> mask M2
>     ├── version 3 -> mask M3
>     └── ...
> ```
>
> A derived conclusion can then trace:
>
> ```text
> semantic state
> <- Foil rule
> <- region relationship
> <- masks
> <- artifact versions
> <- original raw media
> ```
>
> User corrections should attach to this exact provenance.
>
> Example:
>
> ```text
> "that's shadow, not roof damage"
> ```
>
> should be a correction to the precise anchor/observation/rule, not merely conversational text.
>
> ---
>
> ## 27. CRYSTALLIZATION
>
> The model may initially rely on expensive reasoning.
>
> Over time:
>
> ```text
> LLM semantic interpretation
>        ↓
> cheap feature/tracking helper
>        ↓
> native observation history
>        ↓
> corrections/provenance
>        ↓
> stable pattern discovered
>        ↓
> crystallize into Foil
> ```
>
> Example:
>
> ```text
> RoofObservation
> -> DamageState
> ```
>
> becomes ordinary reusable native computation.
>
> General principle:
>
> **expensive inference should collapse into durable software whenever possible.**
>
> ---
>
> ## 28. APPLICATIONS SHOULD GROW FROM FILE/NS MATERIAL
>
> File ingest is not the endpoint.
>
> Example:
>
> ```text
> CSV
> -> native People
> -> spreadsheet
> -> same refs in org graph
> -> workload result
> -> planner
> ```
>
> Image:
>
> ```text
> Image
> -> Matrix<Pixel>
> -> selected/anchored region
> -> image editing
> -> region changes
> -> temporal comparison
> -> geospatial/map surface
> ```
>
> Source:
>
> ```text
> SourceTree
> -> compiler
> -> AST + diagnostics
> -> editor
> -> IDE-ish environment
> ```
>
> PDF:
>
> ```text
> raw PDF
> -> native document representation
> -> selected exact ranges/regions
> -> anchored Things
> -> table/search/reader/analysis
> ```
>
> ---
>
> ## 29. AGENT SHOULD SEE AND REUSE EXISTING MACHINERY
>
> This is especially important with giant model context.
>
> If the agent can see most or all of the namespace, give it enough representation of:
>
> ```text
> types
> refs
> Grove definitions
> Foil definitions
> UI presenters
> app constructions
> result paths
> provenance
> available actions
> dependency failures
> ```
>
> so it can reason globally.
>
> Do not unnecessarily hide the world behind tiny hand-written retrieval schemas if giant context makes direct inspection practical.
>
> We are explicitly testing whether a frontier model over a huge coherent namespace can approximate the behavior we originally wanted from persistent namespace attention.
>
> ---
>
> ## 30. DO NOT OVERFIT THE DEMO
>
> Do not build five handcrafted mini applications whose success depends on recognizing:
>
> ```text
> if spreadsheet
> if timeline
> if image editor
> if IDE
> ```
>
> in host code.
>
> The test is that the **same generic primitives** can produce all of them.
>
> If you find yourself writing app-specific browser/runtime logic, treat that as a warning sign.
>
> ---
>
> ## 31. DOGFOOD FOR A LONG TIME
>
> Stop treating every small result as the end of a checkpoint.
>
> Keep the environment live.
>
> Spend a long time:
>
> ```text
> creating Things
> importing files
> selecting paths
> asking the agent to apply machinery
> creating new applications
> extending existing ones
> composing application pieces
> creating flows
> editing things
> triggering dependencies
> intentionally changing upstream structure
> observing downstream breakage
> letting the agent repair it
> correcting the agent
> reusing the corrected machinery elsewhere
> ```
>
> The primary activity should be **using Shrine**.
>
> ---
>
> ## 32. TESTING POLICY
>
> Minimize speculative regression work.
>
> Default:
>
> ```text
> use
> -> use
> -> compose
> -> use
> -> real bug appears
> -> isolate bug
> -> fix shared cause
> -> add one focused regression if warranted
> -> immediately return to using Shrine
> ```
>
> Do not:
>
> ```text
> feature works
> -> invent 40 edge cases
> -> refactor runtime
> -> benchmark everything
> -> build framework
> -> never return to product
> ```
>
> Things that justify low-level work include:
>
> ```text
> crash
> corruption
> memory leak
> identity violation
> wrong dependency behavior
> stale correspondence accepted
> permission/authority violation
> actual expressiveness ceiling
> unusable performance
> ```
>
> “This could be cleaner” does not.
>
> “183 ms instead of 150 ms” currently does not.
>
> ---
>
> ## 33. DO NOT SECRETLY REPLAN THE ARCHITECTURE
>
> Do not take this spec and disappear for hours designing a new architecture intended to support it.
>
> **Use what exists first.**
>
> When a requested behavior appears possible with current Shrine/Grove/Foil/Goo/harness primitives, implement it using those primitives.
>
> If something genuinely cannot be expressed, identify the smallest missing primitive and add only that.
>
> We are testing whether the system already has enough closure.
>
> ---
>
> ## 34. WHAT I WANT TO SEE VISUALLY
>
> Improve the live Canvas/NS environment so I can actually understand what is happening.
>
> Roughly:
>
> ```text
> ┌─────────────────────────────────────────────────────────────────────┐
> │ Shrine                              search / prompt / attach file   │
> ├────────────────┬────────────────────────────────────────────────────┤
> │ NS WORLD       │                    CANVAS                          │
> │                │                                                    │
> │ ▾ Organization │      ┌──────────────────────────────┐              │
> │   ▾ people     │      │ usable application surface  │              │
> │     Alice      │      │                              │              │
> │     Bob        │      └──────────────────────────────┘              │
> │   ▾ tasks      │                                                    │
> │                │           ┌────────────────────────┐               │
> │ ▾ Files        │           │ second projection     │               │
> │ ▾ Results      │           └────────────────────────┘               │
> │ ▾ Machinery    │                                                    │
> │                │                                                    │
> ├────────────────┴────────────────────────────────────────────────────┤
> │ selected paths / binding fit / proposed diff / agent activity      │
> └─────────────────────────────────────────────────────────────────────┘
> ```
>
> I want to see:
>
> ```text
> current selection
> current native identities
> agent binding attempts
> reused machinery
> missing commitments
> proposed changes
> affected dependents
> failures/cascades
> repair attempts
> ```
>
> without turning the whole product into a developer console.
>
> ---
>
> ## 35. SUCCESSFUL DEMONSTRATION
>
> Do not report success because:
>
> ```text
> spreadsheet demo works
> image demo works
> 100 tests pass
> ```
>
> The real proof is something like:
>
> ```text
> start with a world
>      ↓
> manually create some Things
>      ↓
> ingest heterogeneous real/synthetic files
>      ↓
> same identities reused across sources
>      ↓
> select arbitrary paths
>      ↓
> agent matches application commitments
>      ↓
> existing machinery partially reused
>      ↓
> one missing piece invented
>      ↓
> native diff shown
>      ↓
> beautiful functional UI appears
>      ↓
> same refs appear in another application
>      ↓
> edit through one surface
>      ↓
> all dependent surfaces update
>      ↓
> use an application result in another construction
>      ↓
> build a flow
>      ↓
> change something upstream
>      ↓
> downstream commitment breaks
>      ↓
> exact break is surfaced to the agent
>      ↓
> agent repairs it surgically
>      ↓
> repair diff shown
>      ↓
> corrected machinery retained
>      ↓
> reuse it somewhere unrelated
>      ↓
> continue
> ```
>
> That is the actual experiment.
>
> ---
>
> ## 36. NORTH STAR
>
> The system should eventually feel like:
>
> ```text
> USER GROWS WORLD
>          ↓
> AGENT SEARCHES EXISTING COMPUTATIONAL VOCABULARY
>          ↓
> SOFTWARE GROWS AROUND WORLD
>          ↓
> USER USES SOFTWARE
>          ↓
> SOFTWARE PRODUCES/MUTATES MORE NATIVE MATERIAL
>          ↓
> THAT SOFTWARE ITSELF BECOMES MATERIAL
>          ↓
> AGENT REUSES PIECES OF IT
>          ↓
> MORE SOFTWARE
>          ↓
> FAILURES REVEAL PRECISE BROKEN COMMITMENTS
>          ↓
> AGENT REPAIRS THEM
>          ↓
> REPAIRS BECOME KNOWLEDGE
>          ↓
> WORLD GETS MORE CAPABLE OVER TIME
> ```
>
> This is the Factorio/Excel property:
>
> **outputs become future machinery, and using the computer increasingly becomes the same activity as programming the computer.**
>
> The goal is not an AI assistant sitting beside applications.
>
> The goal is:
>
> **one persistent computational world, many synchronized projections over exact shared identity, and agents continuously composing, extending and maintaining the software around that world.**
>
> If you can get that behavior mostly from the existing harness and native substrate, that is the win.
>
> **Do not overbuild it. Do not overfit it. Do not make a toy. Keep the system alive and force the thesis to prove itself through use.**