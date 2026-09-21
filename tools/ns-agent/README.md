# Shrine observation lab

A fixed OpenRouter model uses `read`, `make`, `poke`, and `cull` against a real,
isolated Shrine sovereign. Each actual result is returned to the model, and the
complete conversation is kept. No training or crystallization is involved.
The native `/sys/crew` slot also lets the model leave notes that return when
their dependencies change.
The `goal` tool is a convenience that installs or updates the same native goal
records through those operations. It does not evaluate conditions in Python.

The page is rendered by `src/foil/apps/rl-agent/main.foil`, using `weft`.
Python serves that rendered page and its local CSS/JS. This is a separate local
app process; it does not mount into or modify an existing live helm instance.

## Run

Requires Python 3.10+ (standard library only) and the project's built Wisp binary.

```sh
export WISP=/absolute/path/to/wisp
export OPENROUTER_API_KEY=... # or use a private --key-file outside the repository
python3 tools/ns-agent/app.py --port 8765 --budget 2
```

Open http://127.0.0.1:8765. The first launch stages the Reaver snapshot and
compiles the Foil app. `--seed-snapshot /path/to/staged/snap` can reuse an already
staged snapshot; `--runtime /private/work/directory` chooses runtime storage.
Use a separate runtime directory for tests and for every concurrently running app.

The fixed model is `anthropic/claude-sonnet-5`, routed only to Anthropic, with
fallback disabled. The process budget persists across UI session resets. Actual
reported costs, model/provider IDs, input/output tokens, request sizes and latency
are recorded. Uncertain network calls reserve their conservative cost envelope;
there are no automatic retries. Pricing in the guard was verified September 20,
2026 ($2/M input, $10/M output); update it when changing the model/provider.

## The implementation boundary

```text
page / prompt → runner.py → OpenRouter tool call
                              ↓
                       runtime.py (validate + transport)
                              ↓
                       agent-crud.rvr (JSON line protocol)
                              ↓
                       agent_crud.foil → Shrine cycle
                              ↓
                  real ACK/error + native change signs
                              ↓
                     observation → next model call
```

- `agent_crud.foil`: JSON/native field conversion, existing reads and transactions,
  before/after values at paths with real native change signs, and one native hear
  form that forwards dependency notes as addressed host messages.
- `agent-crud.rvr`: holds the sovereign and runs the line protocol. It does not
  implement namespace semantics or an expression evaluator.
- `runtime.py`: subprocess lifetime, path/value validation and operation journal.
- `runner.py`: model protocol, growing conversation, causal event links and costs.
- `app.py` and `web/`: local server and the live observation/namespace interface.

The model can emit up to 16 tool operations in one response. They execute in
order, with individual acknowledgements, changes and dependency notifications.
This is not atomic: on failure, earlier successes remain and remaining calls
receive explicit not-executed results. The model then sees all results together.
It is instructed to wait when choosing another operation requires feedback.
The `why` argument is a brief operation purpose, not a transcript of hidden reasoning.

Application paths are ordinary absolute addresses such as `/users/ian`.
The model cannot write root, `/agent`, `/log`, `/boot`, `/h`, or `/io`.
Fields use single-segment slot names, except native `/sys/crew` and app `/app/goal`; nested JSON is a value, not an implicit
namespace subtree. Strings/natural numbers become standard `pails/t` and `pails/n`;
other JSON becomes `crud/value`. Arbitrary native forms, refs and types
are not exposed through this initial transport. Make replaces one record while
preserving descendants; Poke merges fields; Cull recursively removes descendants.

Observation events are also real records at `/agent/events/eNNNNN`, with a
causal parent, event kind, and payload. The runtime's own `/log` is kept as well.
The model receives tool result references to its observation records. Root reads
show application data; explicit `/agent` and `/log` reads inspect internal records.
Unknown native payloads (such as the native journal's event card) are visibly marked,
not silently decoded as ordinary JSON.

This baseline records **operation-level causality**, plus dependency notifications,
not every internal kernel dispatch. No ACK is fabricated for a rejected
operation; an accepted no-op has an ACK and an empty changes array.

## Leave a future note

The model can use the same Make/Poke operations with these fields, for example
on a record at `/notes/user-count`:

```json
{
  "note": "When users change, check whether the summary count needs updating.",
  "/sys/crew": {
    "users": {"path": "/users", "care": "z"}
  }
}
```

This converts to an actual `cpail(crew)` at the native `['sys', 'crew']` slot.
The adapter also attaches its small forwarding form through `/sys/limb`; that
managed slot is omitted from the JSON view. Shrine discovers the dependency and
dispatches `hear`. The form emits a typed message addressed to `/agent/probe`,
carrying the saved note, its record, changed dependencies and native hydrated
views. It leaves the watcher unchanged, so forwarding does not trigger itself.
The host accepts those messages into causal observation records and feeds them
to the model. Python does not scan for matching dependencies or run a scheduler.

- `x`: exact record; `y`: record plus nearest record-bearing descendant frontier;
  `z`: whole subtree. These are Shrine's semantics, not a hand-written path matcher.
- For `y`/`z`, the watched root must be an actual record. An implicit directory
  has no native change sign. Read first and Make `{}` at that root if needed;
  existing children are preserved. Exact `x` watches can wait for an absent record.
- The adapter checks that prerequisite against a native read before installing or
  rewiring note/goal dependencies. A missing root rejects the entire operation with
  a `Make /path {}` diagnostic; nothing is written. Historical replay preserves
  previously accepted commands, so existing inactive watches need an explicit repair.
- Poke the note text to change the reminder. Poke `/sys/crew` with a replacement
  map to rewire it; `{}` unwires it. Cull the note record to remove it entirely.
- Several named dependencies can share a note. Notes stay wired after firing.
- Root and runtime bookkeeping paths cannot be watched through this adapter.
- The external-change control now only wakes the model when Shrine emits a
  matching notification. Other external changes are recorded for its next turn.
  Model-issued tool operations continue their existing request/response loop.

## Native goals

A goal is now an app record with a small default Foil behavior. Through normal
Make/Poke, the model writes a note and the special `/app/goal` field:

```json
{
  "note": "Keep the release ready",
  "/app/goal": {
    "conditions": {
      "tests": {"path": "/release/tests", "care": "x", "note": "All tests pass", "met": false},
      "approval": {"path": "/release/approval", "care": "x", "note": "Release is approved", "met": false}
    }
  }
}
```

The adapter creates a typed `crud/goal` payload and attaches the goal form through
`/sys/limb`. Its native `init` and `talk` arms derive `/sys/crew` from the conditions
and compute `fulfilled = all conditions met`. Reads include this computed boolean;
it is not accepted in writes. The model updates individual assessments by Poking
`/app/goal` with the complete conditions map, preserving unchanged entries.

On native `hear`, only conditions whose cared dependencies changed reset to false.
Foil recomputes fulfillment and sends the revised goal, condition notes, changed
dependencies and current views back to the model. Fulfilled goals remain installed
and reopen on relevant changes. Assessment updates do not wake the same goal.
False means not established, including failed, unknown or invalidated; the model
still reasons about semantic truth. The native rule verifies the conjunction of
assessments, not whether the model's interpretation is correct.

The goal must have 1–64 named conditions; dependencies may repeat. Ordinary care
semantics apply. Self-watches and subtree watches containing the goal are rejected
to prevent self-invalidation. `/sys/crew` is managed on goals: edit conditions to
rewire them, or Cull to remove the goal. Cross-goal cycles remain subject to the
runtime's cascade limit. A watch waits for changes, so it does not replace doing
available work now. The app has no canned goal/demo runner or goal scoring panel.

There are two entry points. **+ New goal** immediately creates a native pending
goal from the submitted description and records the request in the conversation.
That UI-only creation may temporarily have zero conditions; native fulfillment
remains false. The model then uses `goal(path, note, conditions, why)` to define the
conditions and confirms the result in chat. If the provider fails or clarification
is needed, the requested goal remains saved. Ordinary chat can also imply ongoing
work; the model is instructed to use the same goal tool when appropriate. Both paths
use the same native `crud/goal` payload and Foil behavior. The tool preserves unrelated
fields when updating a goal and refuses to overwrite an ordinary record.

The UI's context metric is serialized request KB, not a claim about token count.
Actual API token counts are in the exported transcript. The runner stops before
its configured context limit instead of silently summarizing/truncating history.

## Persistence and reset

The sovereign and its native version history live in the running Wisp process.
Every mutation and response is also appended to `operations.jsonl`. Sessions,
complete model messages, metrics and checks are saved under `sessions/`.
**New chat** saves the current chat's operation tape, then starts a separate real
Shrine namespace. The chat picker restores that chat's conversation and executes
its recorded operations through Shrine to rebuild its namespace, cases and native
watches. Other chats' goals are paused until reopened. Switching never calls the
model or redelivers historical probes, and never resets cumulative API spending.
If final native records differ from the saved verification snapshot, the switch
fails and the previous chat is restored. No saved JSON namespace is installed into
an emulated runtime; JSON records are used only for verification and display.

Older chat files from the original reset UI are also listed. On first reopening,
their exact last observation is located in the original operation journal to recover
the corresponding tape. If that original history is missing, restoration fails
explicitly; the app does not synthesize operations from the saved record snapshot.

By default, restarting opens a fresh chat. Pass `--resume` to reopen the active chat
with current system instructions. Interrupted active turns require explicit recovery.
This is deterministic replay of the CRUD app, not general crash recovery for arbitrary
external services. The UI has no destructive namespace-reset control.

## Tests

```sh
cd tools/ns-agent
python3 -m unittest test_native -v  # validation tests; native tests skip without WISP
WISP=/path/to/wisp AGENT_RUNTIME=/private/fresh-test-directory \
  AGENT_SEED=/path/to/staged/snap python3 -m unittest test_native -v
```

Native tests check CRUD semantics, dependency delivery, ordered operation batches,
partial failure, causal links and session replay. Scripted clients in protocol
tests exercise transport behavior; they do not measure model capability.

`test_live_dependencies.py` is a separate, explicitly invoked paid test (a $0.35
cap). It asks the real model to create a note, changes its dependency, checks its
response, and verifies that no-op, unrelated, and unwired changes make no model
calls. Run it with `--wisp`, an isolated `--runtime`, `--seed-snapshot`, and a private
`--key-file`. Its transcript and independent checks remain in that runtime directory.

`test_live_goals.py` uses the same arguments and a $0.50 cap. A real model installs
and assesses a goal over two external facts; subsequent changes exercise native
completion, reopening, reassessment and no-op silence. The test also checks that
the model does not change those external facts to manufacture fulfillment.
