Yes — this is the missing correction. **The system should evolve sequentially, not ask the agent to hallucinate an entire app + schema + behavior graph + Foil program in one shot.**

Give Codex this:

> # CRITICAL CORRECTION — BUILD THE WORLD/APPLICATION SEQUENTIALLY
>
> Do **not** ask the model to construct an entire application, all Foil, all bindings, all UI, and every anticipated dependency in one generation.
>
> That is exactly how it keeps producing brittle garbage.
>
> The Personal OS should grow through a repeating sequence:
>
> ```text
> USER INTENT
>     ↓
> what needs to exist?
>     ↓
> CREATE / REFINE RELEVANT NS STRUCTURE
>     ↓
> show structure diff
>     ↓
> commit
>     ↓
> what useful software can exist over this structure?
>     ↓
> establish app bindings
>     ↓
> BUILD THE UI FIRST / SURFACE THE THING
>     ↓
> add LOCAL behavior only where the live UI now requires it
>     ↓
> run/use it
>     ↓
> next need appears
>     ↓
> extend structure / bindings / UI / local behavior
>     ↓
> repeat
> ```
>
> **This is an evolutionary system.**
>
> ---
>
> ## 1. THE USER DESCRIBES OUTCOMES, NOT ARCHITECTURE
>
> The permanent interaction should remain:
>
> ```text
> select something if relevant
> attach files if relevant
> describe what I want
> ```
>
> Examples:
>
> ```text
> "I want to track projects and deadlines."
>
> "Add these employees to this organization."
>
> "Make this useful for scheduling."
>
> "I want to compare these images."
>
> "Turn this into something I can use to manage an investigation."
>
> "Add budgeting to this."
> ```
>
> The agent decides whether that requires:
>
> ```text
> new NS structure
> changes to existing NS
> more data
> a new application surface
> extension of an existing surface
> new result paths
> a few new localized behaviors
> ```
>
> The user should not have to classify the request.
>
> ---
>
> # 2. STRUCTURE FIRST WHEN STRUCTURE IS MISSING
>
> Suppose I say:
>
> ```text
> "I want to track projects, tasks and deadlines."
> ```
>
> Do **not** immediately generate a giant planner.
>
> First make the required world coherent:
>
> ```text
> Project
> ├── name : Text
> ├── people : Many<Ref<Person>>
> └── tasks : Many<Ref<Task>>
>
> Task
> ├── title : Text
> ├── assignee : Ref<Person>?
> ├── deadline : Date?
> └── status : Status
> ```
>
> Show me that meaningful structural proposal:
>
> ```text
> REUSE
> = Person
> = Date
>
> CREATE
> + Project
> + Task
>
> ADD
> + Project.tasks
> + Task.deadline
> ```
>
> Let me apply/correct it.
>
> Now that world exists.
>
> ---
>
> # 3. THEN BUILD THE APPLICATION OVER THE REAL STRUCTURE
>
> After the structure exists, establish the application commitments:
>
> ```text
> ProjectSurface
>
> INPUT
>     Project
>     Project.tasks[*]
>     Project.people[*]
>
> WRITABLE
>     Task.title
>     Task.status
>     Task.deadline
>     Task.assignee
>
> RESULTS
>     filteredTasks
> ```
>
> Then make a **good actual UI** immediately:
>
> ```text
> ┌───────────────────────────────────────────────────────────────┐
> │ PROJECT ALPHA                                  + Task         │
> ├───────────────────────────────────────────────────────────────┤
> │ Task                    Person      Deadline      Status      │
> │                                                               │
> │ Build parser            Alice       Oct 8         Doing      │
> │ Canvas polish           Bob         Oct 12        Todo       │
> │ Integration test        Liam        Oct 15        Todo       │
> └───────────────────────────────────────────────────────────────┘
> ```
>
> The UI is decomposed against the real paths.
>
> At this stage, do not try to implement every possible behavior this application could ever need.
>
> ---
>
> # 4. ADD BEHAVIOR LOCALLY AS THE APPLICATION REQUIRES IT
>
> Now I say:
>
> ```text
> "let me change status inline"
> ```
>
> That produces one small localized behavior:
>
> ```text
> occurrence:
>     StatusCell(task)
>
> reads:
>     Task.status
>
> event:
>     user selects status
>
> writes:
>     Task.status
> ```
>
> Compile that local typed behavior into Foil.
>
> Done.
>
> Then:
>
> ```text
> "let me schedule by dragging"
> ```
>
> Add:
>
> ```text
> TimelineItem(task)
>
> reads:
>     Task.deadline
>
> event:
>     drag
>
> writes:
>     Task.deadline
> ```
>
> Again: **local behavior associated with the relevant cared paths/UI occurrence.**
>
> Do not generate one giant Foil subsystem called `ProjectPlanner`.
>
> ---
>
> # 5. FOIL SHOULD ACCUMULATE LOCALLY
>
> Think:
>
> ```text
> UI occurrence
>      ↕
> exact cared paths
>      ↕
> small typed behavior
>      ↓
> compiled localized Foil
> ```
>
> So a complex application eventually has substantial behavior, but it arrived incrementally:
>
> ```text
> ProjectPlanner
>
> UI
> ├── TaskRow
> │    ├── TitleEditor
> │    ├── AssigneePicker
> │    ├── StatusControl
> │    └── DeadlineEditor
> │
> ├── Timeline
> │    └── TaskOccurrence[*]
> │
> ├── WorkloadPanel
> │    └── PersonWorkload[*]
> │
> └── BudgetPanel
>
> behavior
> ├── title edit behavior
> ├── assignment behavior
> ├── status behavior
> ├── timeline drag behavior
> ├── workload dependency computation
> └── budget dependency computation
> ```
>
> Those are **small typed local behaviors**, not one model-authored blob.
>
> ---
>
> # 6. CRAZY APPLICATIONS ARE STILL THE GOAL
>
> Do not interpret locality as reducing expressive power.
>
> I should eventually be able to say:
>
> ```text
> "Make me an environment for coordinating a construction project:
> combine the schedule, people, satellite imagery, budget, documents,
> inspections and weather observations."
> ```
>
> That can become:
>
> ```text
> ConstructionProject#8
> ├── people
> ├── tasks
> ├── budget
> ├── site
> ├── documents
> ├── inspections
> └── media
>
>                       ↓
>
> ┌─────────────────────────────────────────────────────────────┐
> │ CONSTRUCTION PROJECT                                      │
> ├──────────────────┬──────────────────────────────────────────┤
> │                  │                                          │
> │ timeline         │             site / image                 │
> │                  │             inspection                   │
> │ █████ Task A     │                                          │
> │    ███ Task B    │           [ aerial imagery ]             │
> │                  │                                          │
> ├──────────────────┼──────────────────────────────────────────┤
> │ PEOPLE/WORKLOAD  │ DOCUMENTS / ISSUES / COST               │
> │                  │                                          │
> │ Alice █████      │ Permit.pdf                              │
> │ Bob   ██         │ Inspection #4 ⚠                         │
> │                  │ Budget variance +4.2%                    │
> └──────────────────┴──────────────────────────────────────────┘
> ```
>
> Full-power application.
>
> But it was built as:
>
> ```text
> structure
> → surface
> → local behaviors
> → use
> → extension
> → more local behaviors
> → more structure
> → more surface
> ```
>
> rather than one giant generation.
>
> ---
>
> # 7. APPLICATION NEEDS CAN REQUIRE MORE NS STRUCTURE
>
> This is crucial.
>
> Suppose I already have:
>
> ```text
> Task
> ├── title
> └── status
> ```
>
> Then ask:
>
> ```text
> "give me a timeline"
> ```
>
> The application requires temporal structure that does not exist.
>
> The agent should say, in useful product terms:
>
> ```text
> Timeline needs a time position for each Task.
>
> Current Task:
> ✓ title
> ✕ time/date
>
> Possible extensions:
> + deadline : Date
> + interval : Interval
>
> Do you want tasks positioned by a single deadline
> or with start/end durations?
> ```
>
> That is a legitimate user question because it changes the meaning of the world.
>
> If I choose interval:
>
> ```text
> Task
> + start : DateTime?
> + end   : DateTime?
> ```
>
> Then the timeline can bind cleanly.
>
> **Applications are allowed to expose missing structure requirements.**
>
> That is not failure.
>
> That is how the world grows.
>
> ---
>
> # 8. SOMETIMES THE APPLICATION NEEDS MORE DATA, NOT MORE TYPES
>
> Distinguish:
>
> ```text
> missing STRUCTURE
> ```
>
> from:
>
> ```text
> structure exists but DATA is missing
> ```
>
> Example:
>
> ```text
> Task already has:
> start
> end
>
> but 12 Tasks have no values.
> ```
>
> Timeline should not invent dates.
>
> It can surface:
>
> ```text
> Timeline can render 28 / 40 tasks.
>
> 12 tasks are missing schedule data.
>
> [show unscheduled]
> [let agent estimate]
> [leave unscheduled]
> ```
>
> If model-derived estimates are acceptable:
>
> ```text
> /ScheduleEstimate/results[Task#17]
> ```
>
> can exist as results/derived data without lying that they were user-entered dates.
>
> ---
>
> # 9. STRUCTURAL CHANGES CAN BREAK EXISTING APPLICATIONS
>
> This is expected and important.
>
> Suppose later:
>
> ```text
> Task.deadline : Date
> ```
>
> gets replaced by:
>
> ```text
> Task.schedule : Interval
> ```
>
> Existing applications may have commitments to `Task.deadline`.
>
> Immediately:
>
> ```text
> Task schema changes
>      ↓
> typed dependency invalidation
>      ↓
> Timeline deadline binding fails
> Calendar deadline binding fails
> Reminder deadline binding fails
> ```
>
> The user should see a semantic repair:
>
> ```text
> 3 existing surfaces need attention.
>
> Task.deadline no longer exists.
>
> Existing replacement:
> Task.schedule : Interval
>
> Proposed:
> Timeline  -> use Task.schedule
> Calendar  -> use Task.schedule.start
> Reminder  -> use Task.schedule.start
>
> [Apply repairs]
> ```
>
> Not:
>
> ```text
> foil compilation error blah blah
> ```
>
> ---
>
> # 10. EXISTING APPLICATIONS SHOULD EVOLVE, NOT BE REGENERATED
>
> If the Task structure changes, preserve:
>
> ```text
> existing UI
> existing user arrangement
> existing useful presenters
> existing unaffected behavior
> existing results
> ```
>
> Repair only the broken commitments.
>
> ```text
> before
>
> Task.deadline
>      ↓
> Timeline temporal geometry
>
> after
>
> Task.schedule
>      ↓
> Timeline temporal geometry
> ```
>
> Timeline does not disappear and regenerate.
>
> ---
>
> # 11. APPLICATION BUILD-UP SHOULD FEEL CONTINUOUS
>
> This is the desired UX:
>
> ```text
>                  WORLD
>                    │
>                    ▼
>         ┌────────────────────┐
>         │ simple useful UI   │
>         └─────────┬──────────┘
>                   │
>          "add scheduling"
>                   │
>                   ▼
>       requires temporal structure?
>          │                  │
>         yes                already exists
>          │                  │
>          ▼                  │
>     propose NS extension    │
>          │                  │
>          └────────┬─────────┘
>                   ▼
>            extend same UI
>                   │
>          add local behaviors
>                   │
>                   ▼
>         ┌────────────────────┐
>         │ richer useful UI   │
>         └─────────┬──────────┘
>                   │
>            "add budgeting"
>                   │
>                   ▼
>          inspect current NS
>                   │
>          reuse Money/People/etc.
>                   │
>            missing structure?
>                   │
>                   ▼
>              extend world
>                   │
>                   ▼
>              extend UI
>                   │
>                   ▼
>               continue
> ```
>
> **The application grows with the world.**
>
> ---
>
> # 12. SHOW THE RELEVANT NS EVOLUTION ALONGSIDE THE REAL UI
>
> The user should be able to see:
>
> ```text
> BEFORE
>
> Task
> ├── title
> └── status
> ```
>
> request:
>
> ```text
> "add scheduling"
> ```
>
> proposal:
>
> ```text
> Task
> ├── title
> ├── status
> ├── + start : DateTime?
> └── + end   : DateTime?
> ```
>
> and simultaneously:
>
> ```text
> CURRENT UI                         PROPOSED UI
>
> ┌──────────────┐                  ┌───────────────────────┐
> │ Task list    │                  │ Task list + timeline  │
> │              │        ->        │                       │
> │ A       Todo │                  │ A █████               │
> │ B       Doing│                  │      █████ B          │
> └──────────────┘                  └───────────────────────┘
> ```
>
> That is a **10/10 experience**:
>
> > I understand what changed in my world and immediately see what new capability that change enables.
>
> ---
>
> # 13. AGENT SHOULD MAKE SMALL COMMITMENTS
>
> Do not give the agent one giant request like:
>
> ```text
> produce the complete final application implementation
> ```
>
> Internally walk it through:
>
> ```text
> 1. resolve relevant world/context
> 2. determine necessary structure changes
> 3. commit/check structure
> 4. establish input/output/result paths
> 5. render initial decomposed UI
> 6. identify immediate behavior needed by that UI
> 7. define/compile small localized typed behavior
> 8. run it
> 9. observe real result
> 10. continue with next missing capability
> ```
>
> This should dramatically reduce stupid failures because each step gets grounded in what actually exists after the prior step.
>
> ---
>
> # 14. UI FIRST IS A VERY USEFUL GROUNDING MECHANISM
>
> Once the bindings exist, **make the UI concrete early**.
>
> Because then behavior questions become specific.
>
> Instead of:
>
> ```text
> "write behavior for project manager"
> ```
>
> you get:
>
> ```text
> this dropdown
> -> changes Task.status
>
> this timeline occurrence
> -> reads Task.schedule
>
> this drag
> -> writes Task.schedule
>
> this workload badge
> -> derives from assignments
> ```
>
> The UI itself localizes the behavioral problem.
>
> That is much easier for the model to reason about.
>
> ---
>
> # 15. LOCAL FOIL SHOULD BE HIDDEN BUT INSPECTABLE
>
> The model/harness can produce:
>
> ```text
> typed behavior contract
>      ↓
> localized Foil
> ```
>
> The user sees:
>
> ```text
> Dragging a task changes its schedule.
> Workload updates when assignments change.
> ```
>
> Internals remain available under deep inspection if somebody actually wants them.
>
> They are not product UI.
>
> ---
>
> # 16. ONE REPEATING CONSTRUCTION CYCLE
>
> Everything — apps, file integration, extensions, repairs — should reuse one conceptual cycle:
>
> ```text
>                  REQUEST
>                     │
>                     ▼
>           inspect existing world
>                     │
>                     ▼
>          what structure is needed?
>                     │
>             ┌───────┴────────┐
>             │                │
>          already            missing
>          exists               │
>             │                 ▼
>             │          propose NS diff
>             │                 │
>             └───────┬─────────┘
>                     ▼
>                  STRUCTURE
>                     │
>                     ▼
>          establish app bindings
>                     │
>                     ▼
>             REAL UI APPEARS
>                     │
>                     ▼
>        add immediate local behavior
>                     │
>                     ▼
>                   USE
>                     │
>             ┌───────┴──────────┐
>             │                  │
>         new desire         something breaks
>             │                  │
>             ▼                  ▼
>         REQUEST             REPAIR
>             │                  │
>             └────────┬─────────┘
>                      ▼
>                    REPEAT
> ```
>
> That loop **is the OS**.
>
> ---
>
> # 17. DO NOT REDUCE THE AMBITION
>
> Sequential construction does not mean simplistic applications.
>
> It is specifically how we eventually get much more complicated applications reliably.
>
> ```text
> tiny native structure
>     ↓
> simple surface
>     ↓
> local behavior
>     ↓
> structure extension
>     ↓
> richer surface
>     ↓
> more local behavior
>     ↓
> reused external machinery
>     ↓
> result paths
>     ↓
> other native structures
>     ↓
> composition
>     ↓
> sophisticated environment
> ```
>
> You should eventually be able to construct things comparable in complexity to:
>
> ```text
> IDE
> Photoshop-like editor
> spreadsheet
> project management suite
> GIS surface
> analytics workstation
> simulation environment
> game
> document research environment
> ```
>
> without introducing privileged application types.
>
> ---
>
> # 18. THE UX TARGET
>
> The user experience should feel like:
>
> ```text
> I say what I want.
>
> Shrine shows me the meaningful world structure required.
>
> I see the actual software taking shape immediately.
>
> I use it.
>
> I ask for more.
>
> The existing thing grows instead of being replaced.
>
> If it needs more structure, Shrine explains the meaningful missing concept.
>
> If it needs more data, Shrine shows me exactly what's missing.
>
> If my world changes and something breaks, Shrine shows the broken assumption
> and repairs that assumption instead of destroying the application.
>
> Over time my world and my software become richer together.
> ```
>
> **That is the Personal OS.**
>
> The implementation trick is not to have the model generate more.
>
> It is to have the model make **smaller, typed, locally grounded commitments in sequence**, while the live UI and actual NS state continually constrain what it does next.
>
> Build it that way.