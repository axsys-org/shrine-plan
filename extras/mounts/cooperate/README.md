# Document-local agent harness

This backend keeps work, captured inputs, branching traces and typed results in
Shrine records. External agents use the existing MCP tools. Foil implements the
three commands; namespace admission validates and commits each operation as one
batch. There is no model transport or scheduler in this mount.

From the repository root:

```sh
x/eden --mount cooperate --compiler none --port 8131
```

Add `--mount nenex` to work against wiki pages. The backend also works against
ordinary existing records. Starting Eden creates a fresh namespace; this proof
retains journal/history within that process, without restart recovery.

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
| `finish` | Open work record | `id`, `content`; optional `artifact` | Rechecks initial and observation inputs, then commits result, receipt and completed state together |

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
caller deliberately replacing its records with raw writes. External tool calls,
model requests, cost accounting and retries belong to the external client and
are represented by trace entries only when that client records them. Reads and
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
