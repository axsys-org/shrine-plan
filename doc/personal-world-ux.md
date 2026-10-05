Send Codex this as the **UI/UX north star**. This is the part it should keep in mind while dogfooding so it does not accidentally turn Shrine into a node editor, chat app, dashboard builder, or developer console.

> # SHRINE PERSONAL AGENT OS — UI PARADIGM
>
> The UI should communicate the actual thesis of Shrine:
>
> **the user is continuously growing one native computational world, and the agent continuously grows useful software around that world.**
>
> Do not make the user think in terms of:
>
> ```text
> create app
> open app
> configure workflow
> wire node
> switch mode
> inspect agent
> return to canvas
> ```
>
> The user should mostly:
>
> ```text
> point at something
> describe what they want
> watch relevant structure appear/change
> watch useful software form around it
> use that software
> continue from the result
> ```
>
> The system underneath can be sophisticated as hell. The experience should remain coherent.
>
> ---
>
> ## THE PERMANENT SHELL
>
> There should be very little permanent navigation.
>
> ```text
> ┌──────────────────────────────────────────────────────────────────────────────┐
> │  SHRINE                                                      Search / ⌘K    │
> ├──────────────────────┬───────────────────────────────────────────────────────┤
> │                      │                                                       │
> │      NS WORLD        │                    CURRENT WORLD                      │
> │                      │                                                       │
> │  ⌕ Search...         │                                                       │
> │                      │      ┌────────────────────────────────────────┐       │
> │  ▾ People            │      │                                        │       │
> │     Alice            │      │                                        │       │
> │     Bob              │      │        ACTUAL WORKING SOFTWARE         │       │
> │                      │      │                                        │       │
> │  ▾ Projects          │      │ spreadsheet / editor / timeline /      │       │
> │     Alpha            │      │ image surface / graph / document /     │       │
> │                      │      │ map / simulation / something new       │       │
> │  ▾ Tasks             │      │                                        │       │
> │                      │      │                                        │       │
> │  ▾ Artifacts         │      └────────────────────────────────────────┘       │
> │  ▾ Results           │                                                       │
> │  ▾ Machinery         │                                                       │
> │                      │                                                       │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │  > describe what you want...                            attach ▪ send        │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> That bottom prompt is the **one primary agent entry point**.
>
> It inherits current context automatically:
>
> ```text
> current selection
> current Thing/path
> current application
> current file
> current UI occurrence
> current result
> current surrounding structure
> ```
>
> Right click / shortcut can summon the same prompt locally.
>
> There is not a separate chat product.
>
> ---
>
> # THE EXPERIENCE SHOULD EVOLVE LIKE THIS
>
> Start with almost nothing:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │                                                       │
> │                      │                                                       │
> │  empty-ish           │                                                       │
> │                      │                                                       │
> │                      │                                                       │
> │                      │                                                       │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │ > I want to track projects, tasks, people and deadlines                     │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> The agent first figures out **what should exist natively**.
>
> Then the user should visibly see the relevant structure taking shape:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │            PROPOSED STRUCTURE                         │
> │                      │                                                       │
> │ + Project            │      Project                                          │
> │ + Task               │      ├── name : Text                                  │
> │ = Person             │      ├── people : Many<Ref<Person>>                   │
> │                      │      └── tasks : Many<Ref<Task>>                      │
> │                      │                                                       │
> │                      │      Task                                             │
> │                      │      ├── title : Text                                 │
> │                      │      ├── assignee : Ref<Person>?                      │
> │                      │      ├── deadline : Date?                             │
> │                      │      └── status : Status                              │
> │                      │                                                       │
> │                      │                         [Apply] [Change]               │
> └──────────────────────┴───────────────────────────────────────────────────────┘
> ```
>
> Not raw Foil.
>
> Not implementation details.
>
> **The meaningful native structure.**
>
> Once applied, the agent should immediately make it useful:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │                    PROJECTS                           │
> │                      │                                                       │
> │ ▾ Project Alpha      │      ┌────────────────────────────────────────────┐   │
> │   ▾ people           │      │ Alpha                                      │   │
> │      Alice           │      │                                            │   │
> │      Bob             │      │ TODO              PERSON        DEADLINE   │   │
> │   ▾ tasks            │      │ Build parser      Alice         Oct 8      │   │
> │      Build parser    │      │ Finish UI         Bob           Oct 12     │   │
> │      Finish UI       │      │                                            │   │
> │                      │      └────────────────────────────────────────────┘   │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │ > make this easier to schedule                                               │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> Now the agent is not “creating another app.”
>
> It is taking the existing world and finding a better expression of it.
>
> ```text
> selected:
> Project#Alpha.tasks[*]
>
> agent sees:
> Many<Task>
> Task.title
> Task.assignee
> Task.deadline
>
> agent searches existing machinery
> ```
>
> Then the user sees a **small meaningful fit preview**:
>
> ```text
> ┌────────────────────────── MAKING A TIMELINE ──────────────────────────┐
> │                                                                       │
> │ Existing structure                                                    │
> │                                                                       │
> │ ✓ tasks         <- Project#Alpha.tasks[*]                             │
> │ ✓ label         <- Task.title                                         │
> │ ✓ temporal pos  <- Task.deadline                                      │
> │ ✓ person        <- Task.assignee                                      │
> │                                                                       │
> │ Reusing                                                               │
> │ = Date presentation                                                    │
> │ = Task label presentation                                              │
> │ = draggable temporal-item behavior                                     │
> │                                                                       │
> │ Creating                                                              │
> │ + /Timeline#7/results/conflicts                                        │
> │                                                                       │
> │ Source structure changes: none                                         │
> │                                                        [Create]        │
> └───────────────────────────────────────────────────────────────────────┘
> ```
>
> Then the actual UI replaces the proposal:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │                     ALPHA                             │
> │                      │                                                       │
> │ ▾ Project Alpha      │  Oct 6      Oct 8      Oct 10     Oct 12             │
> │   ▾ tasks            │    │          │           │          │                │
> │      Build parser ───┼──────██████████                                    │
> │      Finish UI ──────┼────────────────████████████                          │
> │                      │                                                       │
> │ ▾ Results            │  ⚠ overlap                                            │
> │   Timeline#7         │                                                       │
> │     conflicts        │                                                       │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │ > show workload next to this                                                 │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> Notice the model:
>
> ```text
> did not create another universe
> did not copy the Tasks
> did not create a workflow node
> did not open another page
> ```
>
> It built another useful realization over the same refs.
>
> ---
>
> # THE NS PANEL AND THE UI ARE TWO DIRECTIONS INTO THE SAME THING
>
> Click:
>
> ```text
> Alice
> ```
>
> in NS:
>
> ```text
> NS:
> Person#17
> ```
>
> Every visible occurrence of Alice should subtly highlight:
>
> ```text
> spreadsheet row
> timeline assignment avatar
> org chart node
> contact panel
> ```
>
> Conversely:
>
> ```text
> click Alice in some UI
> ```
>
> NS reveals:
>
> ```text
> Person#17
> ```
>
> and the cared path associated with the clicked occurrence.
>
> The mental model should become:
>
> > “These aren't synchronized copies of Alice. They're all Alice.”
>
> ---
>
> # FILES ENTER THE SAME WORLD
>
> Drop:
>
> ```text
> employees.csv
> ```
>
> Do not navigate to an importer.
>
> It simply appears:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │ employees.csv                                         │
> │                      │                                                       │
> │ ▾ Artifacts          │ name        email             manager                 │
> │   employees.csv      │ Alice       alice@...         Bob                     │
> │                      │ Bob         bob@...           Carol                   │
> │                      │ ...                                                   │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │ > these are our employees, merge them into the organization                  │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> Agent responds with relevant structure:
>
> ```text
> employees.csv
> 
> REUSE
> 287 Person refs
>
> CREATE
> 25 Person refs
>
> MAP
> name       <-> Person.name
> email      <-> Person.email
> manager    <-> Person.manager
>
> UNMAPPED
> office_code
>
> Organization.people
> + 25 refs
>
> [Preview people] [Apply]
> ```
>
> After commit, those People simply exist.
>
> Then:
>
> ```text
> > show the reporting hierarchy
> ```
>
> and the current surface can become:
>
> ```text
>                         Carol
>                       /       \
>                     Bob       Eve
>                    /   \
>                 Alice   Liam
> ```
>
> Same refs.
>
> ---
>
> # APPLICATION UI SHOULD BE BUILT OVER RELEVANT STRUCTURE
>
> The agent internally deals with:
>
> ```text
> input bindings
> output bindings
> result paths
> typed behavior
> decomposed presentation
> ```
>
> But the human mostly sees:
>
> ```text
> what exists
> what is being added
> what is being changed
> and the actual resulting software
> ```
>
> If editing is allowed:
>
> ```text
> Person#17.salary
> ```
>
> then editing the salary cell in a table changes the real path.
>
> If something is a result:
>
> ```text
> /Workload#4/results/load[Person#17]
> ```
>
> then the UI presents it as a result without pretending to mutate `Person`.
>
> The distinction exists semantically even if visually they appear together.
>
> ---
>
> # FLOWS SHOULD EMERGE WITHOUT BECOMING A FLOW-BUILDER
>
> Example evolution:
>
> ```text
> Project.tasks
>      │
>      ▼
> Timeline
>      │
>      └── conflicts
>             │
>             ▼
>         Planner
>             │
>             └── dailyPlan
>                    │
>                    ▼
>                Calendar
> ```
>
> The user should mostly experience:
>
> ```text
> > use these conflicts to produce a daily plan
> ```
>
> not:
>
> ```text
> drag output connector
> connect node
> configure field map
> press save
> ```
>
> If the user asks to inspect how something is wired, then expose:
>
> ```text
> ┌────────────────────────────────────────────────────────┐
> │ Project.tasks                                          │
> │      ↓                                                 │
> │ Timeline.results.conflicts                             │
> │      ↓                                                 │
> │ Planner.results.dailyPlan                              │
> │      ↓                                                 │
> │ Calendar.items                                         │
> └────────────────────────────────────────────────────────┘
> ```
>
> Otherwise let the useful resulting software dominate.
>
> **Flow is an emergent dependency/composition graph, not a product mode.**
>
> ---
>
> # APPLICATIONS SHOULD EVOLVE IN PLACE
>
> Start:
>
> ```text
> simple task table
> ```
>
> Then:
>
> ```text
> > add workload
> ```
>
> It becomes:
>
> ```text
> task table
> + workload indicators
> ```
>
> Then:
>
> ```text
> > let me schedule by dragging
> ```
>
> It grows:
>
> ```text
> table
> + temporal UI
> + drag behavior
> ```
>
> Then:
>
> ```text
> > add budget impact
> ```
>
> It searches:
>
> ```text
> Money
> Person.salary
> Task.assignment
> existing currency presenter
> existing workload computation
> ```
>
> and expands the same working environment.
>
> The user should feel like **software is growing**, not like they're spawning a pile of apps.
>
> ---
>
> # PARTIAL REUSE SHOULD BE VISIBLE IN THE RESULTS
>
> Suppose an existing People surface has:
>
> ```text
> AvatarPresenter
> PersonName
> StatusBadge
> editable role field
> ```
>
> A new project planner needs:
>
> ```text
> PersonName
> AvatarPresenter
> workload result
> ```
>
> It should reuse those pieces.
>
> Do not make reuse itself a complex UI.
>
> But if inspecting the change:
>
> ```text
> REUSE
> = PersonName
> = AvatarPresenter
> = MoneyPresenter
>
> NEW
> + WorkloadBadge
> ```
>
> This communicates that Shrine is **accumulating vocabulary**.
>
> ---
>
> # IMAGE/MEDIA SHOULD FEEL LIKE THE SAME SYSTEM
>
> Drop:
>
> ```text
> inspection.jpg
> ```
>
> The native world gains:
>
> ```text
> Image#42
> ├── raw artifact
> └── pixels : Matrix<Pixel>
> ```
>
> Current surface:
>
> ```text
> ┌──────────────────────┬───────────────────────────────────────────────────────┐
> │ NS WORLD             │                                                       │
> │                      │                                                       │
> │ ▾ Image#42           │              [ actual image ]                         │
> │   pixels             │                                                       │
> │                      │                  ______                               │
> │ ▾ Building#7         │              ___/      \___                           │
> │   roof               │             /   selected   \                          │
> │                      │             \     roof      /                          │
> │                      │              \___________/                            │
> ├──────────────────────┴───────────────────────────────────────────────────────┤
> │ > that's Building 7's roof                                                   │
> └──────────────────────────────────────────────────────────────────────────────┘
> ```
>
> The proposal is:
>
> ```text
> CREATE ANCHOR
>
> Image#42 / mask#8
>        <->
> Building#7.roof
>
> provenance:
> image version 1
> exact mask retained
> ```
>
> Later attach a second image:
>
> ```text
> > compare this roof with the previous image
> ```
>
> The system may create:
>
> ```text
> RoofObservation#1
> ├── image -> Image#42
> └── mask  -> M0
>
> RoofObservation#2
> ├── image -> Image#43
> └── mask  -> M1
> ```
>
> The user sees the actual comparison:
>
> ```text
> ┌────────────────────────────────────────────────────┐
> │ ROOF CHANGE                                        │
> │                                                    │
> │ [ old ]                    [ new ]                 │
> │                                                    │
> │ unchanged     █████████                            │
> │ disappeared   ░░░                                  │
> │ appeared         ▒▒▒▒                              │
> │                                                    │
> │ changed area: 8.4%                                │
> └────────────────────────────────────────────────────┘
> ```
>
> Underneath, Shrine can use:
>
> ```text
> M0 ∩ M1
> M0 ∪ M1
> M1 - M0
> M0 - M1
> ```
>
> The user sees the useful visual result and relevant native observations.
>
> ---
>
> # WHEN THE WORLD BREAKS
>
> This is where Shrine should become obviously different from conventional software.
>
> Suppose `Task.deadline` disappears or changes type.
>
> Suddenly:
>
> ```text
> Timeline
> Calendar
> Planner
> ```
>
> depend on something that no longer works.
>
> Do not crash into a developer console.
>
> The affected UI should locally show:
>
> ```text
> ┌──────────────────────────── Timeline ────────────────────────────┐
> │                                                                  │
> │  ⚠ Temporal binding needs repair                                │
> │                                                                  │
> │  Previously                                                     │
> │      Task.deadline -> timeline position                         │
> │                                                                  │
> │  Available now                                                  │
> │      Task.targetDate                                            │
> │      Task.scheduleEstimate                                      │
> │                                                                  │
> │  Agent proposes                                                 │
> │      Task.targetDate                                            │
> │                                                                  │
> │  Also affects                                                   │
> │      Calendar                                                    │
> │      Planner                                                     │
> │                                                                  │
> │                                     [Apply repair] [Change]      │
> └──────────────────────────────────────────────────────────────────┘
> ```
>
> The user sees the **semantic broken relation and proposed repair**.
>
> Not Foil garbage.
>
> Not evaluator internals.
>
> Not “regenerate app.”
>
> Apply it:
>
> ```text
> Task.targetDate
>      ↓
> temporal projection
>      ↓
> Timeline ✓
> Calendar ✓
> Planner ✓
> ```
>
> Same applications recover.
>
> ---
>
> # USER CORRECTION IS PART OF THE LOOP
>
> Suppose agent proposes:
>
> ```text
> use targetDate
> ```
>
> User says:
>
> ```text
> no, use scheduleEstimate
> ```
>
> The system changes the relevant binding.
>
> Then dependent UI recomputes.
>
> The correction itself becomes part of the world's history.
>
> Next time another construction needs `Task -> Interval`, the system already has evidence about the preferred interpretation.
>
> ---
>
> # THE OS SHOULD GET SMARTER OVER TIME
>
> Early state:
>
> ```text
> USER REQUEST
>      ↓
> MODEL
>      ↓
> lots of invention
>      ↓
> software
> ```
>
> Later:
>
> ```text
> USER REQUEST
>      ↓
> MODEL SEARCHES WORLD
>      ↓
> finds:
>     types
>     projections
>     UI pieces
>     Foil machinery
>     previous corrections
>     file mappings
>     presentations
>      ↓
> mostly recomposes
>      ↓
> invents tiny missing piece
> ```
>
> Visually the user should feel that the OS increasingly **already knows how their world works**.
>
> ---
>
> # THE UI SHOULD NEVER MAKE THE USER FEEL LIKE THEY ARE “PROGRAMMING AN AGENT”
>
> Bad:
>
> ```text
> configure agent
> choose tool
> map inputs
> map outputs
> create workflow
> publish workflow
> ```
>
> Good:
>
> ```text
> select Tasks
> 
> > make these schedulable
> ```
>
> or:
>
> ```text
> select existing planner
> 
> > include budget impact
> ```
>
> or:
>
> ```text
> attach PDF
> 
> > merge the claims in here into this project
> ```
>
> or:
>
> ```text
> select image region
> 
> > that's the building we're tracking
> ```
>
> The intelligence should dissolve into the environment.
>
> ---
>
> # THE EXPERIENCE OVER MONTHS
>
> This is the actual evolution I want Shrine to imply:
>
> ```text
> DAY 1
> 
> small NS
> model invents structure
> model invents presentations
> model writes missing computation
> ```
>
> ```text
> DAY 10
>
> People already exist
> Tasks already exist
> Money presentation exists
> Date projection exists
> table editing exists
> timeline behavior exists
>
> new software reuses most of it
> ```
>
> ```text
> DAY 100
>
> massive world
> huge accumulated vocabulary
> years of provenance
> user corrections
> existing presentations
> existing behavior
> existing semantic adapters
> existing application fragments
>
> user:
>     "give me a way to understand what's going wrong
>      with this project"
>
> system:
>     largely composes capabilities it already has
> ```
>
> So:
>
> ```text
>            WORLD GROWS
>                │
>                ▼
>        SOFTWARE VOCABULARY GROWS
>                │
>                ▼
>          AGENT REUSES MORE
>                │
>                ▼
>         LESS MUST BE INVENTED
>                │
>                ▼
>       ENVIRONMENT GETS SMARTER
>                │
>                ▼
>            WORLD GROWS...
> ```
>
> ---
>
> # THE FULL PARADIGM
>
> ```text
>                         USER INTENT
>                              │
>                select / describe / attach
>                              │
>                              ▼
>                    ┌──────────────────┐
>                    │  FRONTIER AGENT  │
>                    └────────┬─────────┘
>                             │
>                  inspect current world
>                             │
>                             ▼
>              ┌─────────────────────────────┐
>              │      SHARED NS WORLD        │
>              │                             │
>              │ Things / refs / paths       │
>              │ files / media / provenance  │
>              │ results / machinery         │
>              └──────────────┬──────────────┘
>                             │
>                  identify desired change
>                             │
>             ┌───────────────┴────────────────┐
>             │                                │
>             ▼                                ▼
>       STRUCTURE CHANGE               SOFTWARE CHANGE
>       create/update NS               bind/reuse/extend
>             │                                │
>             └───────────────┬────────────────┘
>                             ▼
>                    MEANINGFUL PREVIEW
> 
>             relevant NS structure + actual UI
>                             │
>                             ▼
>                           COMMIT
>                             │
>                             ▼
>                    ┌───────────────────┐
>                    │   REAL SOFTWARE   │
>                    │                   │
>                    │ edit              │
>                    │ view              │
>                    │ calculate         │
>                    │ react             │
>                    │ mutate            │
>                    │ produce results   │
>                    └─────────┬─────────┘
>                              │
>                   outputs remain native
>                              │
>                              ▼
>                      MORE WORLD STATE
>                              │
>                  ┌───────────┴───────────┐
>                  │                       │
>                  ▼                       ▼
>             USER CONTINUES          CASCADE BREAKS
>                  │                       │
>                  │                       ▼
>                  │                exact failed relation
>                  │                       │
>                  │                       ▼
>                  │                  AGENT REPAIRS
>                  │                       │
>                  │                meaningful preview
>                  │                       │
>                  └──────────────┬────────┘
>                                 ▼
>                              CONTINUE
> ```
>
> **This is not a workspace around AI.**
>
> **This is not AI generating disposable apps.**
>
> **This is not a workflow builder.**
>
> **This is not an infinite draggable canvas full of boxes.**
>
> It is:
>
> > **one living native world whose structure and software continuously evolve together, with an agent making the world more useful while the human remains in direct contact with the actual things being created.**
>
> The UX succeeds when the user can watch:
>
> ```text
> structure become software
> software modify structure
> results become new material
> old software get reused
> failures expose exact broken assumptions
> the agent repair those assumptions
> the world become progressively more capable
> ```
>
> without needing to think about Foil, runtime internals, application registries, wiring tools, or how the model did the plumbing.
>
> **That is the expectation. Do not dumb this into cards + chat. Do not complicate it into Figma + Zapier. Make it feel like the computer itself is becoming programmable and intelligent around the user's world.**

## Latest interaction clarification

The main surface is a downward, persistent sequence of requests, optional files or
native selections, checked structural proposals, and working results. The adjacent
structure panel renders the same native records with readable labels and values;
raw addresses remain available through inspection. Selecting material and asking
to apply existing software continues this sequence. The model searches, binds,
repairs or authors a local missing piece, and asks only where meaning is ambiguous.
Do not make free canvas navigation, developer namespace traversal or a separate
source-approval workflow prerequisites for ordinary use.
