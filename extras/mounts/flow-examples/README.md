# Authored flow examples

This optional mount selects `flow-authoring`, `flow-web`, `conversation` and
`grove-authoring`. The procedures use the shared
`flows` execution mount. It owns recipes and domain policy, not a
second harness. `x/eden --mount flow-examples --ephemeral` creates a disposable
world for trying them; add `--mount codex` for a real interactive provider.
Existing world mounts, captured handlers and history are never upgraded by moving
these files. Deliberate publication and activation remain separate operations.

`examples/` contains authored Semidoc procedures and sample evidence.
`examples.json` selects evidence and recipes. `examples.foil` installs native
instantiate operations and supplies pure example adapters; `cartography.foil`
contains the cited-assertion policy. `query_sources.foil` selects explicitly bound named endpoints and arguments. The only Python stages declared bytes for
the existing filesystem foot. It does not poll, schedule, execute flows or save
application state. The shared `flow-web/host.py` only supplies its native HTTP foot
address.

The **Flow examples** Goo tool lists the catalogue once. Enter a recipe name to
create its `<name>_flow` page, then open that page, publish the authored definition,
bind its explicit inputs and attach through **Author flows**. Creation never
publishes a flow or overwrites an existing source document automatically.
Authored default-node references are rebound through Semidoc's parsed reference
values at creation. Prose and literal examples are left intact. Child dependencies
can be prepared together through the inspected publication procedure below,
or created and published individually.

`conversation_response` is the initial conversation procedure. Create its page,
publish `respond`, then choose that definition and an interactive provider at
`/conversation`. The supplied policy authors Semidoc; its response is projected
Nenex, with shared native requests, cells, holes and guarded publication. See the
[conversation boundary](../conversation/README.md) for context selection and limits.

## Independently invokable stages

The library separates proposals, native effects, observations and document
projection. A stage returns ordinary native records through the existing result
cells. A downstream flow binds those values directly; it does not parse a report.
The authored stages and compositions live in `examples/*.semidoc`. The pure
adapters in `stages.foil` construct existing judgments or inspect supplied
records. They introduce no persistent types, provider, queue or work lifecycle.

| Composition | Separately invokable components | Native result |
| --- | --- | --- |
| `orient_here` | `inspect_subject` | Summary, questions, next action proposal; exact context and source captures |
| `surface_investigation` | `inspect_subject` over supplied source context | The same structured read-only assessment |
| `investigation_handoff` | `assess_work` then `plan_continuation` | Original owner/status/capture and a continuation proposal |
| `resume_work` | `assess_work`, selected original-work action, `prepare_action`, `invoke_action`, `verify_action` | Receipts and exact postcondition observations |
| `invoke_and_verify` | `prepare_action` then `invoke_action` then `verify_action` | Verified captures with their check and receipt evidence |
| `grove_app_authoring` | `grove_source`, native draft argument preparation, `invoke_action`, `inspect_grove_draft` | Actual compiled draft record, source, revision and capture |
| `save_grove_draft` | Revision-checked source preparation, `invoke_action`, `inspect_grove_draft` | Observed compiled revision of an existing draft |
| `publish_grove_draft` | Revision-checked preparation, `invoke_action`, native publication observation | Observed published revision; independent of authoring |
| `procedure_extraction` | `extract_procedure` then `inspect_procedure` | Actual authored Nenex record/source and native receipts |
| `task_learning` | `extract_lessons`, `propose_instruction`, `propose_procedure` | Three independently consumable proposal records |
| Guide's `author_publish` | `create_document`, receipt dependency, `publish_flow` | Native publication receipts |

`author_document` separately proposes Semidoc source. `create_document` writes
that proposal through a selected creation control. `publish_flow` publishes its
named definition through an explicitly selected publication control.
`project_result` is an optional final document projection for any of these
results. Source fields are literal text, not executable document attributes.
The handbook, atlas and authored wiki retain their document-producing contracts;
chapters are not artificially turned into separate procedures.

### Publication and binding

In **Flow examples**, enter the parent recipe name and a fresh inspection name,
then choose **Inspect publication dependencies**. The optional definition name
defaults to the recipe name; use `respond` for `conversation_response`.
The native inspection reads
the selected Semidoc definition's actual invocation references. It lists missing
children before their consumers, deduplicates shared children, checks live
cycles, and shows each existing publication's captured references alongside the
currently selected ones. Exact historical references remain pinned and are not
recursively upgraded. The existing compiler supplies validation and diagnostics.

The inspection is a frozen cell at
`/<node>/app/flow_examples/catalogue/cells/<inspection>`. Its computed value
contains the ordered records, source/publication captures, dependency captures,
and full authored/shipped source comparison. Inspection creates no authored
page, publication or running flow. The Goo panel shows the summary and both
versions of the selected root's source; inspect child entries through that cell.

**Publish inspected authored sources** checks those captures, creates missing
catalogue recipes and publishes dependencies before consumers in one existing
native admission using deferred commands. A changed source, dependency,
publication, recipe or publisher refuses the stale inspection. A later command
failure rejects the entire admission. This is not an install queue or another
work lifecycle. It does not bind inputs, invoke a provider or attach occurrences.
Current recipe bytes come from the existing filesystem snapshot report. A
missing file may remain in namespace history, but cannot be offered or created
as a current template. Deletion also invalidates an outstanding inspection;
restoration permits a fresh review using the same native source records.

Existing source documents always win over shipped templates. A difference is a
review prompt, not permission to overwrite or merge. Use the existing Nenex
source/Goo editor to apply the desired changes, then inspect again. Older pages
need no baseline marker or migration: the comparison does not pretend to know
whether a difference is a local edit or an upstream template change. Existing
external publications without available source are kept rather than rebuilt.

Individual creation/publication remains available. A parent captures exact child
definitions; later edits do not retarget old attempts or pinned occurrences.
Deliberate occurrence adoption stays separate. Live-publication maintenance
attachments retain their existing behavior when a definition is republished.

For native-result flows, explicitly select
`/0x11/gov/flows/retain_result` as the writer. This uses the existing
work result cell and receipt without writing a document or another result store.
For `project_result`, bind `value` to the producer's result and select the
Nenex writer. Invoke a child with `/flow/invoke` to recompute together, or bind
an explicitly retained generation result when it should stay fixed.
After a standalone invocation publishes, its receipt identifies the retained run
at `<controller>/work/<generation>`. The computed result is at
`/x/<controller>/work/<generation>/result`. For example, bind `lessons` in
`propose_instruction` to an `extract_lessons` run's result, or bind `value` in
`project_result` to that same result. Use the actual generation named by the
receipt. The raw `result` record is the cell definition, not its output.

Judgment stages bind `provider` to the raw native provider record, commonly
`/0x11/io/codex/surface_provider`. Their default instructions are in Semidoc.
A per-invocation assignment can be a Nenex page bound as source evidence using
**Bind Nenex evidence**. This replaces the default source collection; choose the
binding before attachment. Default changes do not retarget an existing controller.
The task captures the actual supplied source and prior-stage records.

The structured schema is specific to the stage: for example `grove_source`
returns `name`, `source`, `note`; `extract_lessons` returns `observation`,
`interpretation`, `rule`, `counterexample`, `note`. Required empty fields
produce `flow_revision_unresolved` and retain the existing request hole.
Evidence edits or **Retry failed request** resume through the same native hand.
Duplicate/unknown fields, non-text values and oversized results are refused.
A validated proposal is still a proposal; it is not proof that a tool ran.

These stages instruct the interactive provider to avoid mutations. This is task
policy, not a new capability sandbox. Native request/owner/definition/evidence
and hole-head checks still authorize every tool call, including after pause or
detach. No separate MCP loop or browser-specific action implementation is added.

### Actions and verification

`prepare_action` accepts a captured declared control as `selection` and one
native record of text argument slots as `arguments`. It uses the existing Goo
input metadata to encode rich text. It keeps the selected control, receiver and
publication guards. A newly discovered selection is an explicit new input.
`invoke_action` delegates to the existing `request_actions` operation and
native action provider. The provider supplies guarded admission and a retained
invocation identity. The result retains the actual outcome, result reference,
request and receipt identity. An agent's report cannot substitute for that result.

`verify_action` has three inputs: `receipts`, `checks`, `observations`.
Each named check record contains:

- `target`: native path of the record to observe.
- `after`: optional exclusive lower bound for its x version.
- `expect/<slot path>`: one or more expected native values, compared by pail equality.

The correspondingly named observation contains an existing native own-record
capture, retaining the exact value and version. For a frozen inspection, bind
the raw cell record. To follow changes, use **Create observation cell** in the
Flow examples tool: choose an owning Nenex page, unused cell name and source
record path. This installs the existing native watching cell. Bind its computed
output at `/x/<page>/cells/<name>`, not its raw definition. It can be created
before the source exists. Deletion makes the current observation unavailable;
restoration updates it through ordinary cell dependencies. Earlier captures
remain retained in attempts and history. A frozen inspection is deliberately an
as-of reading and does not establish current availability.
Missing, stale, wrong-target or mismatching observations refuse verification.
They can be corrected by changing that binding, without repeating the action.
Verification inputs are deliberately excluded from the action task's evidence.
The checks establish only the declared postcondition at the captured version.

`assess_work` exposes the original typed work, owner and as-of status. Handoff
and continuation consume this same value. `resume_work` requires an explicitly
selected action on the original work, its owner or its recorded hole. It refuses
to dispatch active or completed work again. A waiting/failed attempt can still
have unresolved work on its original hole. The selected control decides whether
the requested continuation is admissible. This flow does not choose authority, copy a
controller, patch status fields or adopt a new definition. Use
`plan_continuation` independently when the missing input or next action needs
judgment; its result does not itself resume work.
For `resume_work`, keep `capture` fixed to the inspection used to select the
continuation action. Bind the resulting state separately through `observations`;
otherwise the action's own progress would change the requested continuation.

### Grove authoring and procedure extraction

`grove_source` authors source only. Bind task requirements and existing Grove
contracts through `sources`; the proposal is available for editing/reuse before
any effect. `grove_app_authoring` additionally binds `selection` to the native
**Create and compile draft** control on `/0x11/app/grove_authoring`, and
`capture` to an own-record capture of `/0x11/app/grove_authoring/drafts/<name>`.
Create the observation cell before invoking when the draft does not yet exist.
The same hand reevaluates
when its observation changes. There is no polling loop in the example.

`inspect_grove_draft` checks that source equals the proposal and that the native
job's `revision`, `attempted` and `ready` agree. An old successful preview
does not certify a newer source. Exercise preview controls separately with
`invoke_and_verify`. Compilation is not a claim about arbitrary app behavior.
`save_grove_draft` revises an existing draft. Its `before` input is the frozen
capture used to select the save control; `capture` separately follows the
compiled result. A changed result cannot silently change the revision being saved.
`publish_grove_draft` requires a publication control selected for the exact
verified draft version, then observes `published == revision`. It replaces the
sample published instance; it does not migrate existing business data.

`extract_procedure` takes an explicitly selected existing extraction control
and its argument record. Native extraction retains laws and omitted input
bindings for executed flow steps. Investigation extraction creates an editable
proposal and an authoring hole. `inspect_procedure` returns the actual observed
Nenex source/record with receipts; inspect its existing provenance/input children
for further review. Neither stage publishes or resolves the authoring hole.

The authored wiki remains a separate document flow: 24 concept pages plus
compact provenance. Its examples are inert, and source changes refresh evidence
without silently rewriting or certifying prose. It uses the same native
`grove_draft/job`, compiler, records, hands, overlays and publication boundary.

### Validation boundaries

`flow_stage_tests` covers component publication, structured results, receipt
validation, explicit observation checks, Grove revision checks, original-work
selection, composed invocation without replay, and composed learning.
`flow_agent_qol_tests` covers actual composed orientation with controlled
responses: missing input, refusal, retry, changed evidence, pause/detach, result
cells, overlays and retained x/y/z history. Existing action and Grove suites
retain their admission/compiler tests. These fixtures do not establish that a
live model will produce valid Grove code or a correct assessment for every task.

### Learning, technical atlas and format ingestion

All three are available under **Flow examples**. Creating an example
authors its shipped Semidoc and binds its declared repository files through the
existing filesystem source hands. It does not publish, attach, dispatch a model
or overwrite an existing example page. Publish its named definition, bind any
remaining inputs, select the result-appropriate writer and a separate destination, then attach
maintenance or embed a selected occurrence using the ordinary controls.
The three examples reuse the handbook catalogue's `/0x11/io/fs/flow_sources`
capture. Atlas sources reuse the same file entries as the handbook, rather than
staging duplicate copies under new names. Native source-feed dependencies keep
that capture watched while any consumer still needs it.
Source keys also name generated reference documents. Use `cell_examples` for
the Cells source: `cells`, `work`, `inputs`, `flows` and `holes` are reserved
by the native document writer, including beneath `reference`.

| Example | Definition / author page | Remaining input | Result |
| --- | --- | --- | --- |
| Task learning | `task_learning` / `task_learning_flow` | `capture`: settled native work; `provider`: selected native provider | Structured lesson, instruction proposal and procedure proposal |
| Technical atlas | `technical_atlas` / `technical_atlas_flow` | `capture`: a selected native definition or compiler mirror entry | Concept tree relating language/runtime, interfaces and computation |
| Format ingestion | `format_ingestion` / `format_ingestion_flow` | None for the bundled JSON sample | Deterministic source document projection; decoded values retained in the step trace |

For either `capture` input, open **Author flows → Inspect callable
definitions**, name the inspection, enter the source record path and set
**Inspection care** to `x`. Bind the flow input to the **raw**
`<author>/cells/<inspection>` path, without `/x`. This supplies the existing
`native_work/captured` record. The adapter refuses collection care, absent
versions and empty readings instead of treating a collection's epoch as its
root record's identity. The exact typed capture remains beside a bounded display
produced by the existing native value renderer. Source text and type descriptors
are inspectable evidence; a decompiled law is not evidence that it ran.

The inspection is frozen. Later source publication does not retarget it; inspect
and rebind deliberately to adopt another definition or task outcome. Ordinary
manual/document sources remain live bindings and wake the existing maintenance
hand on change. An attempt retains both readings. The raw cell path and its
`/x/...` computed projection have different meanings here; the adapter requires
the former, not a new kind of flow input.

**Task learning** uses native settled-work semantics: an open/running activity
refuses; a completed, failed or otherwise settled attempt can supply evidence,
including an attempt whose subject-owned hole still needs work. Its `sources`
collection contains `task` and `instructions`. The catalogue binds clearly
labelled sample documents. Replace these with the actual goal and current
instructions before adopting a real lesson. Three separately invokable stages produce native proposals through the shared
request hand. The instruction and procedure proposals each depend on the
structured lesson, rather than independently reinterpreting the original task. The flow does not mutate instruction
files, infer a runnable procedure from opaque results, or install a global
after-task hook. Use existing trace extraction and callable composition to turn
an accepted proposal into a separately reviewed and published procedure.
For a completed flow, select its retained `work/<generation>` record. The adapter
walks its existing typed evaluation trace explicitly, including each step's
named results, instead of relying on a truncated rendering of the enclosing
run. Other native work contributes the fields actually present in its selected
record; this does not follow arbitrary investigation links or infer missing
actions. Every display remains a view of the original retained capture.

**Technical atlas** binds the existing Shrine, Grove, Goo, Nenex, flow-harness,
reflection, cell, hand and view sources. Its `example` step actually runs the
existing inventory operation; that captured input/result is inspectable in the
trace. Concept drafts also use the explicitly selected native definition. The
result is authored explanation with provenance, not README replication. It is
not a full Enki manual, nor a claim that arbitrary code examples were executed.
Other callable examples can be deliberately composed or embedded through the
existing Nenex controls.

**Format ingestion** requires no provider. The sample binds one JSON source as
`data`; rebinding another format uses the explicit format field in the declared
Goo action. `library/decode_sources` validates the existing
source envelopes, selects JSON/Markdown/literal-text handling, and returns source
cards. A JSON card adds one `data` slot containing its existing native JSON
variant record (`json/obj`, `json/arr`, and so on). `flow_library/json_value`
reads it back as the parser's sum; neither a new wrapper nor a code carrier is used.
The source remains beside it. Another operation or child flow can consume this
decoded tree; no per-key namespace records, schema registry or entity merge are
created. `library/project_sources` uses the existing `documents` operation for
readable reference pages and retains the JSON value and original source on each
JSON reference record in the returned tree. Another flow can consume that complete
result. The Nenex writer writes those pages; typed decoded values remain in the
retained step/result cells, not as editable data slots on generated prose documents.

This example stops at decoding and document projection. Selecting useful domain
structures, derived cells and Grove/Goo views remains authoring work. An explicit
mapping can supply that next step before other flows consume the structured data.

The native JSON decoder retains ordered object members (including duplicates),
nulls, exact signed integers and real-number source lexemes. It has a permissive
numeric dialect, including malformed real lexemes described in `src/foil/json.foil`;
this adapter is **not** strict RFC validation or domain validation. Original bytes
remain authoritative evidence. Parse failures, trailing content, unsupported
formats and unavailable sources refuse before publication. CSV, OSM and domain
schema adapters are still separate authoring work. No parser is copied into the
flow library.

These optional pure operations live under `/0x11/gov/flows/operations/library`
and are registered by the existing example catalogue. They reuse native
captures, JSON values and `flow/page`; there is no new persistent contract,
work interpreter, provider, watcher or scheduling layer.
The example mount publishes `flow_examples` and `flow_stages` as ordinary modules.
Adding the stage module requires normal mount publication; this does not replace
a saved service or silently activate anything in an existing world.
The added input choices belong to the published Goo declarations. Existing worlds retain their captured HTTP handlers. Updating published actions
does not replace those handlers or install this new page host in a running
world. This consolidation is validated in disposable worlds.

The focused native check is `extras/x/check --mount flow-examples --suite flow_library_tests`.
`--suite flow-authoring-only-tests` compiles the production authoring Grove and
checks its browser/headless actions, including JSON format and own-record care,
without loading the Codex surface fixture. The existing
`--suite flow-reflected-authoring-tests` retains the combined authoring and
Codex surface coverage; its provider fixture is an explicit test dependency.

**Bind web source** writes an ordinary named URL input and fills `urls`.
`web_fetch` declares a native work request, `web_sources` converts an accepted
response to a source envelope, and `decompose`/`documents` prepare the output.
The HTTP foot performs bounded native `Fetch` calls. It owns transport only;
the shared hand owns attempts, guarded completion and retry. Requests already
pending at restart are marked interrupted rather than silently replayed.
Changing a URL input's `revision` slot explicitly requests another capture.
There is no HTTP polling scheduler. HTTP errors remain failed attempts and do
not become current evidence.

The first HTTP flow supports named GET requests and Markdown decomposition.
HTML and other supported text remain literal evidence. Search-engine choice,
registry-specific interpretation, PDF/CSV adapters and source-file write-back
are not implemented by these examples; they require explicit operations and
authored procedures, not an implicit research daemon.

### Cartography as an authored chain

The example catalogue also supplies **Web evidence**, **Cited assertions**, and
**Cartography**. These are Semidoc procedures using the existing work lifecycle.
The parent captures two child definitions, then uses the ordinary document
revision operation and guarded Nenex writer. `cartography.foil` supplies their
domain operations through the optional example catalogue; native `flow_install`
does not depend on it or on the optional graph mount.

From Nenex:

1. Create Capture sources and publish `capture_sources`, then create Web evidence
   and publish `web_evidence`. Create Cited assertions and
   publish `cited_assertions`. Their pages are `web_evidence_flow` and
   `cited_assertions_flow`. Create Cartography and publish `cartography` last.
2. On `cartography_flow`, use **Bind web source** for each named URL. Reserve the
   name `review`. The control supplies the `urls` binding. Each bound URL has an
   **Update web source** control. It checks the previously displayed URL before
   changing that same record, preserves its other metadata, and wakes the
   existing maintenance hand. An obsolete update form is refused.
3. Supply the explicit subject and question as a native record. This can be an
   ordinary Semidoc heading with a path attribute, authored in Nenex:

   ```text
   ;. /research_subject
     ;@ /subject ;/0x11/user/company
     ;= When was this company founded?
       Investigate the selected sources without merging identities by name.
   ```

   Bind `subject` to that heading's raw namespace record, whose address is
   available from the block tools. A typed native `subject` reference plus
   `question` text is also accepted. A path attribute explicitly selects live
   x-care identity; the heading supplies the question when no `question` slot
   is present.
4. With the optional graph library published, bind `projection` to the raw
   `/0x11/gov/graph/report` record. Its ordinary compiled `spun` constructor is
   the selected policy. To retain the selection, use **Inspect native
   definitions** on that raw record and bind the resulting frozen cell's
   `/x/...` view. A live raw binding deliberately follows later publication.
5. Attach maintenance with a new destination, the existing Nenex writer, and
   the existing native Codex work provider. Inspect its shared work cell,
   request evidence, validated value cells, revision overlays and holes.

Web evidence captures explicit HTTP URLs and reuses the existing Markdown
importer. Cartography accepts Markdown/plain-text sources; HTML, binary media,
search and registry interpretation need selected adapters. A changed URL record
or `revision` requests a fresh capture; no network polling scheduler is installed.

Cited assertions bounds extraction, checks exact nonempty quotations against
captured source bytes, and fixes subject/source identities outside the model's
response. Acceptance and its reason are explicit provider judgments, not proven
facts. Collected claims have one stable, source-qualified symbol key each, as
required by the existing Grove claims norm; their source and proposal references
remain on the records. The selected projection may select and annotate but cannot rewrite claim
values or qualifiers. A conflicting selected report or an empty report refuses
review completion even if the provider claims success. Changed evidence resumes
the same demand through the native hand; unchanged failures use **Retry work**.

The parent authors a concept from reviewed assertions and adds compact source
provenance children. Exact captures, rejected proposals, accepted claims and
judgments remain in work history. The claims are native values in addressable
work cells; publishing them as independent sovereign assertions requires an
explicit writer policy. `/r` continues to reflect ordinary typed references,
including work references; selecting assertion holders requires an explicit
scope. This procedure does not discover all relationships or infer identity groups.

After explicitly rescanning and publishing changed mount sources, use
**Author flows → Refresh installed flow operations** to install
that publication's flow registrations. This published action reuses the existing
registration planner and pinned contract checks. It does not replace the saved
HTTP service or compiler. Already captured flow definitions and attempts stay
captured. Republish the selected child and parent to update a live maintenance
attachment. A retained occurrence instead keeps its selected moment: capture
the new publication, then deliberately adopt it when desired. Adoption controls
are only offered for retained occurrences.

## Validation

Run from the repository root in disposable fixtures:

```sh
extras/x/check --mount flow-examples --suite flow_library_tests
extras/x/check --mount flow-examples --suite flow_cartography_tests --suite flow_cartography_lifecycle_tests
extras/x/check --mount flow-examples --suite cartography-publication-tests
extras/x/check --mount flow-examples --mount codex --suite flow-reflected-authoring-tests
node --test extras/mounts/explorer/tests/goo-document.test.cjs
python3 extras/mounts/flows/tests/test_sources.py
python3 extras/mounts/flow-examples/tests/test_sources.py
```

The native suites exercise the shipped Semidoc, evidence changes, retained
captures, holes, retries and document publication. The publication and reflected
authoring gates compile the actual Grove controls. Cold compilation can take
several minutes and substantial memory. Native provider fixtures use controlled
responses; these checks do not establish a fresh browser-to-Codex run or the
quality of generated prose. Live experiments require their own explicit world,
provider selection and verification of retained history.

## Handbook example

First enter `evidence_sources` in **Flow examples → Create example document**,
then open the created page and publish its `evidence_sources` definition. The handbook and Source outline
both invoke this published procedure.

Enter `handbook` in the same **Create example document** control to create
the authoring page and repository capture feed. Publish the definition,
then bind sources and attach maintenance. An existing handbook is opened without
replacing its authored source or history. Its declared input defaults and capture
control live in the page's named `flows/defaults` child, preserving its Semidoc source.

`examples/handbook.semidoc` holds its briefs and dependency declarations.
`examples.json` declares its repository files, source page, input defaults and
optional capture setup. The optional `flow-examples` mount registers these
example actions without instantiating them. The shared `flows` mount does not
read the catalogue.

Repository capture is host I/O. This mount’s `host.py` stages each declared file's exact bytes.
Native source hands expose each file beneath the authoring page's `inputs/sources`;
the existing merge cell at `cells/sources` combines their named evidence. The
handbook's declared source dependencies prevent publishing concepts whose required
evidence is missing.
Missing files are omitted from the current scan; they do not prevent installing
or recompiling the harness in another workspace. Each source hand retains its last
good capture. A feed requires its live file to appear in the configured mount's
current scan report and not in its missing-file list. Retained bytes and an old
successful report are not current evidence. Returning identical bytes restores
the feed without deleting its prior captures. Reading a cell never launches a model.
Other flows can bind namespace evidence directly or use native `watch_sources`
to connect one live file under a filesystem mount's destination to a feed.

The filesystem foot reconciles its owned watcher actors whenever its native
binding changes. A capture configuration has one polling actor, shared by all
source feeds bound to it. `watch_sources` attaches a feed or, with its current
native `expected` case, rebinds it. `unwatch_sources` takes that same case guard
and removes the live dependency while retaining the feed, last good capture and
history. Ownership is derived from the existing native dependencies, not stored
in a second owner table. Rebinding releases the old configuration only when no
other source feed still refers to it. Pausing a maintenance controller does not
remove its authored source binding.

The existing configuration retains its interval (`fs/watch_seconds`, default
15 seconds for a newly attached source); `fs/watch_active` records whether its
source bindings still require polling. Removing or changing a configuration
cancels its old actor. Every read needs permission from the foot, with at most
one second between idle cancellation points. An in-flight I/O call may finish,
but its obsolete generation cannot publish. A completion also checks the exact
native configuration assertion inside ordinary supervisor admission, then lets
the existing filesystem hand apply the request and result in one atomic batch.
Two matching captures stabilize changes; unchanged captures produce no event.
No work queue or scheduler is added. Captured records and all x/y/z cases remain.

The disposable-world gate is `../flows/tests/check-watch-lifecycle.py` (run with `WISP`
set, or from the core development shell). It uses real file deletion/restoration,
two authored flows sharing a capture, rebind/detach/reattach, read counters after
cancellation, and a deliberately blocked read released after detach. The Python
test driver only changes fixture files; the native supervisor, filesystem foot,
source hands and cells perform the lifecycle. The core `tests/fs_reconcile` suite
also checks the worker's termination acknowledgement and rejection of late
results after an ABA detach/reattach. These tests never open a retained live world.

The small `examples/evidence_resume.semidoc` demonstrates a persistent demand:
missing `GATE_OPEN` evidence leaves a hole; changed relevant evidence resumes it
through the same hand. No wall-clock work scheduler is involved.

## Working with Shrine

Create `working_with_shrine` through **Flow examples**. The source page contains
**two separately publishable definitions** using existing operations:

- `working_with_shrine` checks captured sources and publishes the authored guide
  to a destination such as `/0x11/app/nenex/w/working_with_shrine`. Select the Nenex
  writer and the example's default `sources`; no provider is needed. Its children
  cover discovery, contracts/context, preparation, an author/publish exercise and
  receipt inspection. This is authored guidance, not generated README prose.
- `author_publish` consumes `proposal`, `author_selection` and
  `publication_selection`. It calls `create_document`, then `publish_flow`.
  Source-writing receipts establish the dependency; select the publication
  control after creation and update only that binding. Its result is native
  receipts. Use `author_document`
  for source proposals, and `project_result` for optional document presentation.

Publish each definition by its name on the source page. Attach or embed the chosen
publication using the existing controls. Creation and publication do not attach
it automatically. The guide's example produces a reusable evidence-checking flow;
its result is source data, not input for the Nenex document writer.

Guide pages can participate in scoped action contexts through **Set action
relationship**. The guide explains which native action declarations to reference
and how to connect a catalogue selection, receiver and optional cell bindings.
These explicit native attachments are separate from navigable Semidoc links;
installing the recipe does not silently add typed relationships or context cells.

This is an authored procedure over shared hands, cells, overlays and receipts.
The guide flow and selected-action composition are deterministic; source proposal
stages may use an agent.
Native guards validate action admission. A brief does not reduce the provider's
namespace authority, and validating a report does not prove its claims. Interactive
calls may have effects before the final report is accepted. Inspect the retained
receipts and resulting records, including on failed/retried attempts. Rediscover
publication after creating or editing the receiver instead of reusing stale guards.

## Live structured data

`live_data` reuses HTTP capture, native source envelopes, the JSON decoder and
the Nenex projection. Its step cells retain cohesive decoded values for further
composition. Bind explicit URLs and revisions; it does not poll a SQL database.
The optional [`sql-source`](../sql-source/README.md) companion exposes configured
parameterized reads. The [WWI profile](examples/wwi/README.md) supplies order and
schema queries for a real local business case study. No SQL credentials belong
in the namespace. Different captures are not a single multi-query SQL snapshot.

## Compose incoming-data flows

These are independently authored and published Semidoc procedures. The same
native definition records expose their input names and retained implementations
through **Author flows → Inspect callables / Select published flow**. Each
catalogue operation links its captured source under `example/source` and its
publication collection under `example/publications`; its children exist only
after publication. A recipe may declare differently named or multiple definitions. Discovery does not silently instantiate a whole business app.

| Procedure | Inputs | Result |
| --- | --- | --- |
| `select_queries` | `catalogue`, `selection` | Named URL records with explicit arguments and revisions |
| `capture_sources` | `urls` | Successful source captures with native provenance; shared holes/retries on failure |
| `decode_sources` | `sources` | Cohesive decoded values alongside original evidence |
| `project_sources` | `pages`, `sources` | Authored document projections retaining decoded data |

Create and publish each component through the existing example and authoring
controls. Then publish a parent using `/flow/invoke` and explicit `/flow/bind`
relationships. The parent captures exact child publications. Updating a child
does not silently change a retained parent or an existing occurrence.

`business_workspace` is one editable composition of all four. It supplies generic
overview, model, records, investigations and procedures briefs. It binds no
business names, SQL queries or paging defaults. `live_data` is the smaller
capture → decode → project composition for already selected URLs. Filesystem
captures can enter at `decode_sources`; projection can be omitted entirely.
The existing `format_ingestion` example remains a direct decoding/projection
example with a small local JSON fixture.

Current decoding supports JSON, Markdown and text. This is not CSV/Parquet
support, automatic entity mapping, database change capture or a scale claim.
An LLM can author a domain-specific mapping or validation flow and compose it
between decoding and projection; that mapping must explicitly preserve keys,
relationships, nulls, dates and business rules. Similar-looking customer or order
fields across datasets are not evidence of a shared identity.

### Invoke components independently

**Flow examples → Publish and invoke example** accepts name, destination, bindings
(JSON input names to namespace paths) and an optional writer path. Blank writer
selects the existing Nenex writer. For a data-only component use
`/0x11/gov/flows/retain_result` and an unused destination such as
`/0x11/user/outputs/selected_queries`. This writer contributes no document writes;
the existing lifecycle retains results, traces, captures, receipts and ordinary
maintenance cells. It introduces no result store or alternate executor.

The source page's occurrence is `<name>_flow/work/<destination-last-segment>`.
Its retained successful run has a normal `result` cell. Bind another invocation
to that projected result path (the `/x/.../work/<generation>/result` view) to use
its values. A selected generation is stable; use a parent `/flow/invoke` chain
when dependencies should recompute together from changing evidence. Different
components can be invoked, inspected and composed independently.

The invocation shortcut selects the definition matching the example name. For
recipes with differently named or multiple definitions, use the existing
authoring controls to select one explicitly. Native deferred commands keep
creation, publication and attachment in one admission. A later refusal exposes none of the earlier source/publication edits.
Repeating the same invocation keeps its exact retained request and definition,
even after source edits. Different bindings/writers require a deliberate new
occurrence; explicit adoption remains the existing operation. Occupied unclaimed
destinations and colliding controller names are refused. No existing world is
updated merely by changing these files.

### Bind a business profile

For `select_queries`, bind `catalogue` to the captured `endpoint.json` record from
a configured source transport. Bind `selection` to a tree with one record per
chosen output name. Each selection record has:

- `query`: text naming an entry in the catalogue.
- `argument/<name>`: optional text arguments, encoded as URL query parameters.
- `revision`: optional numeric revision for deliberate recapture.

The catalogue record's revision also invalidates selections. Unknown queries,
duplicate catalogue entries, malformed selections and invalid URLs refuse. The
transport validates its own named-query parameters and bounds. This selector
performs no I/O, creates no credentials and starts no polling service.

For the WWI example, selection records can be `model` with query `catalog`, and
`orders` with query `orders`, argument/after `"0"`, argument/limit `"10"`.
Those are profile data, not defaults in the procedure. Bind `business_workspace`
with `catalogue` and `selection`, choose a fresh Nenex destination and leave its
writer blank. Publish the four components first. The original WWI SQL profile
remains under [examples/wwi](examples/wwi/README.md).

For a CRM source, selection might instead be `accounts` → `accounts_page` with
an explicit region argument, and `opportunities` → `pipeline_page` with a bounded
page size. The disposable tests invoke all four components separately with
those names and connect the retained result cells, as well as exercising the
composed workspace with the WWI-shaped selection.

### Dataset examples and actual boundaries

- [Northwind's linked sample](https://learn.microsoft.com/en-us/power-apps/maker/canvas-apps/northwind-install)
  uses Dataverse. It needs a Dataverse transport or an explicitly chosen export;
  our SQL Server adapter is not a Dataverse connector.
- [AdventureWorks](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure)
  can use the SQL Server transport with its own declared queries and bounds.
  WWI SQL files are not an AdventureWorks import profile.
- [Contoso's generator](https://github.com/sql-bi/Contoso-Data-Generator-V2),
  [Maven CRM](https://mavenanalytics.io/data-playground/crm-sales-opportunities)
  and [dunnhumby](https://www.dunnhumby.com/source-files/) are candidate inputs,
  not integrated datasets. File formats need explicit decoders and large imports
  need measured bounded ingestion. No automatic pagination or whole-business
  import is supplied by these example flows.
