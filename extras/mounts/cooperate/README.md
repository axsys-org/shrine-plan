# Document-local agent harness

This backend keeps work, captured inputs, branching traces and typed results in
Shrine records. External agents use the existing MCP tools. Foil implements the
commands; namespace admission validates and commits each operation as one
batch. The shared `native_work` module owns activity state, captured values, frozen
cells and the provider request/outcome contract. Flows use those same records.
The Codex mount supplies a native provider hand; model transport stays in its
existing bridge.

Attempt dispatch and settlement now use the same `native_work` transitions as
answering and document revision. The attempt's retained request is its dispatch
receipt; provider completion freezes its outcome once. Domain admission checks
that outcome against the captured guard and applies its own result policy.
Native activity phases gate hand reactions while dependencies hydrate, so
controller-local sent/settled booleans do not own another execution lifecycle.
Investigations remain open across delegated workers until explicit guarded
completion; a provider result alone does not complete its investigation.

From the repository root:

```sh
x/eden --mount cooperate --compiler none --port 8131
```

Add `--mount nenex` to work against wiki pages. The backend also works against
ordinary existing records. Eden restores its existing native world, including
journal/history, captures and compiled definitions. Use `--world PATH` for an
explicit world or `--ephemeral` for a disposable test.

## Operations

Call `mcp/apply` with `path` set to the target and `operation` set to
`/<node>/gov/cooperate/open`, `append`, or `finish`. `inputs` uses the plain keys
below. A reference is a typed MCP value, for example:

```json
{"type":"reference","path":"/0x11/user/data","care":"y","case":0}
```

`case: 0` follows live state. Use `{ "type": "reference", "value": "/h/..." }`
for an exact historical reference returned by a read.

| Operation | Target | Inputs | Result |
| --- | --- | --- | --- |
| `open` | Existing document record | `id`, `content`; optional `context/<label>` references, `parent`, `procedure` | Creates `<document>/work/<id>` with captured inputs and optional pinned parent edge |
| `append` | Open work record | `id`, `kind`, `content`; optional `context/<label>`, `reply_to`, `artifact` | Appends `<run>/trace/<id>`, links the previous head and captures any new observations/artifact |
| `delegate` | Open work record | `id`, `prompt`, JSON `schema`, `provider` reference, `guard` reference | Installs one native provider activity under `workers/<id>` |
| `finish` | Open work record | `id`, `content`; optional `artifact` | Rechecks initial and observation inputs, then commits result, receipt and completed state together |
| `ask` | Subject record | `id`, question in `content`, result `shape`, live `context` reference, `resume` activity path | Retains `<subject>/holes/<id>`; its native hand marks it ready and pokes the activity when that context changes |
| `resolve_hole` | Hole record | Current `attempt` path, `expected` context generation, explanation in `content` | Marks the demand resolved without deleting it; later changed context can reopen it |

Trace kinds are `message`, `observation`, `tool-result`, and `output`. Parent and
reply edges pin existing records; opening a branch does not implicitly copy all
its parent's context. A procedure is automatically captured as `context/procedure`.
An artifact may reference a record, subtree or derived cell output.

IDs are retry keys scoped to their operation's destination. Repeating the same
ID and identical inputs succeeds without rewriting the original records; reusing
an ID with changed inputs refuses. Completion does not require human review.
A refused stale completion leaves the run open and its trace available. Open a
new branch with fresh inputs to record work based on updated evidence.

## Reading work and reusing results

Stored lifecycle slots are published under `/<node>/gov/cooperate/`; readable
text uses `/sys/content`. Use ordinary `mcp/read` and `mcp/history`:

```text
<document>/work/<id>
  context/<label>               captured input cell
  checks/<label>                live equality check cell
  trace/<entry>                 linked message/observation/output
    context/<label>             captured observation input cell
    checks/<label>              observation equality check cell
    artifact                   captured tool/output artifact cell, when supplied
  result                       final captured artifact cell, when supplied
  commands/<id>                finish retry receipt
```

Read `/x` followed by a captured cell's path to obtain its frozen typed value;
read `/c/x` followed by its path for cell context. Snapshot metadata exposes
`/source`, `/source_case`, `/source_care` and `/observed_case` where available.
Reads do not launch agents or change lifecycle state.

Each investigation also has a live `/x/<run>/lens`: the subject and the named
context references selected at opening. Editing a reference on that cell changes
the next reading; the existing `context/<label>` cells remain frozen. Flows use
the same `native_work/lens_view` to expose their draft, brief, prior document,
captured evidence and live demand. A lens is selected context, not a transcript.

Persistent holes keep their question, expected shape, subject, owner activity,
latest attempt, observed context and reason in native records. `ask` is
idempotent and rejects direct context/resume cycles. `resolve_hole` checks the
current attempt and context generation so a late answer cannot close newer work. A context change
includes removal of the last evidence record. Missing evidence reopens the hole
as waiting, clears the current answer, and still allows in-flight attempts to
settle as superseded. Historical answers remain on their attempts. Restored
evidence wakes the same hand. A completed flow revision explicitly withdraws
its demand watch; staging another revision reattaches it. A context change
wakes the existing activity once for that changed reading; the activity's hand
decides what work to perform. An ordinary investigation records the resume
notification, while a flow's maintenance hand stages and dispatches its next
attempt. There is no timer or separate queue runner. These records and their
journal survive restart through Eden's native world continuation. Process I/O
is reconnected; uncertain external turns are retained as interrupted attempts,
not replayed. Date/backoff scheduling remains outside this contract.

`/x/<run>/checks/<label>` reports `/unchanged`, comparing current values with
captured values. Completion additionally checks the revision of directly stored
live inputs, so an edit followed by a revert still makes those captures stale.
Pinned historical inputs intentionally retain their historical interpretation.
Derived inputs are compared against their captured values; include underlying
records or a procedure reference when their exact revision is part of the work.

A final artifact is frozen at `/x/<run>/result`. The run's published `artifact`
slot retains the source reference: direct stored sources are pinned when possible;
derived sources retain their original reference as provenance. The frozen result
is the record of what was delivered. A cell definition that references published
behavior can be read and rebound to different inputs; a captured numerical output can be consumed
by another cell without interpreting its explanatory prose.

## Client helper

`client.py` uses only Python's standard library and the four existing MCP tools.
Paths passed to `--context` are live subtree references; pass a historical `/h/…`
reference to pin one. The target document and referenced inputs must already exist.

```sh
python3 extras/mounts/cooperate/client.py open /0x11/user/my_document \
  --id first --content 'Inspect these inputs.' \
  --context evidence=/0x11/user/my_data

python3 extras/mounts/cooperate/client.py context /0x11/user/my_document/work/first

python3 extras/mounts/cooperate/client.py append /0x11/user/my_document/work/first \
  --id observation --kind observation --content 'What the captured data shows.'

python3 extras/mounts/cooperate/client.py finish /0x11/user/my_document/work/first \
  --id done --content 'Completed calculation.' --artifact /x/0x11/user/my_cell
```

Put `--base http://127.0.0.1:PORT` before the subcommand to select another server.
`context --event ID` reads inputs captured by a trace entry. Context retrieval
counts pages against explicit node and byte limits and refuses an incomplete
result instead of silently truncating it. It is not a prompt generator or model
provider adapter.

The native proof bounds context capture to 16 aliases, 64 records and 64 KiB of
accounted data per command. An optional artifact has its own 64-record/64-KiB
budget, so an append with context and an artifact may retain up to 128 records
and 128 KiB. Command content is limited to 16 KiB, and a run to 128 trace entries.
Oversized operations refuse before committing. Opaque native values are accounted
as references; these limits do not bound arbitrary compiler execution.

## Scope and checks

This is a local trusted-client harness. Existing MCP access can write namespace
records; these commands provide a consistent protocol, not isolation against a
caller deliberately replacing its records with raw writes. Delegated model
requests run through native provider hands. Other external tool calls appear in
the trace when their caller explicitly records them; cost accounting and retry
policy are not supplied by these commands. Reads and
completion do not prove that an external model used only the captured context.

Native command and ownership checks:

```sh
WISP=/path/to/wisp python3 extras/x/check --mount cooperate
WISP=/path/to/wisp python3 extras/x/check --mount nenex
```

Real MCP transport check against a disposable running world with `cooperate`:

```sh
python3 extras/mounts/cooperate/tests/http.py http://127.0.0.1:8131 0x11
```

The test creates a uniquely named fixture subtree. It covers coherent captures,
branch and reply links, idempotent retries, stale observation and input handling,
atomic refused completion, frozen typed results and cell-definition reuse.
`x/eden --mount cooperate --compiler none --check --port 8132` runs it through
the mount's test hook alongside the MCP checks in a fresh world.

## Native providers

`delegate` binds a published `native_work/provider` to an open investigation.
The Codex mount publishes one at `/<node>/io/codex/work_provider`. It uses the
same request/outcome contract that Semidoc flows use. The guard is a record or
subtree reference captured before dispatch. Worker state, context and frozen
result remain below `workers/<id>`; no Python scheduler is needed.

A provider result is evidence, not permission to mutate a domain document.
The caller's completion operation checks its relevant captures and applies the
domain's rules. Flow revisions additionally compare current brief/evidence and
the captured physical draft revision before accepting generated source.

## Answering a retained question

The native `answer` operation takes a subject record and `id`, question in
`content`, a live `context` reference and a `provider` reference. It creates
`<subject>/work/questions/<id>` and retains the shaped hole at
`<subject>/holes/questions/<id>`. The shared answering hand captures context,
starts the ordinary native provider, and admits a bounded `{answer, note}`
result. An empty answer retains the note as missing evidence. No model call is
repeated for the same context, including failed or unresolved answers.

Attempts at `attempts/a_N` retain their frozen `context` and `answer` cells.
The controller's `answer` cell exposes the most recently admitted result.
Changed context waits for an in-flight result, rejects that stale result, then
starts a new capture. `answer_enabled` pauses/resumes the same activity;
completed provider results wait while paused. Results do not mutate the subject.
Nenex supplies one UI and context projection for these same operations. Other
applications can bind their own context cells and use this answering hand.
