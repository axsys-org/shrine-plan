# Care-aware path inputs

Server commands below run from the Reaver root. Cargo commands and native
render artifacts refer to the separate `shrine-goo-native` checkout. Historical
validation counts are not a substitute for the current branch’s PR checks.

Goo declares the control; Shrine discovers targets and admits grants. The native
renderer only edits a draft and displays the returned metadata.

```text
input(%/read_dependencies, kind = .path, many = 1,
      care = .choose, access = .read, label = "Read dependencies")
input(%/write_dependencies, kind = .path, many = 1,
      care = .choose, access = .write, label = "Write dependencies")
```

The corresponding slots hold `goo_paths/hunts`, whose `items` are Shrine's existing
`hunt` values (`c=care`, `p=path`). A shared type adapter is shown in `agents.grove`.
Text inputs retain their existing contract. Path inputs add a `pathInput` descriptor
(version 1) to the bound node. Clients that do not support it reject the descriptor;
the older Mash adapter explicitly reports an unsupported capability.

Views containing path inputs also declare which input slots each action consumes.
The native editor clears only those accepted drafts: saving dependencies retains
an unsent task, and sending a task retains unsaved dependency selections. The full
captured invocation remains unchanged for exact retries.

The form transport carries a versioned JSON envelope in each input value:
`{"version":1,"hunts":[{"key":"v1/…","care":"y"}]}`. This is an encoding of typed
hunts, not a list of textual paths. Shrine decodes it against the *published input*
and the caller's namespace authority. Display paths, titles, and descriptions
travel separately and never identify a grant. Re-selecting a canonical key changes
its care. Selecting a path does not commit permissions.

Search uses `/shuin/paths`, bound to the receiver, view publication, and input slot.
It indexes titles (`/sys/lede`) and displayed paths; `/sys/help` supplies tooltips.
Record bodies are not searched or returned. Exact matches precede title/path
prefixes, with canonical path ordering within each tier. ASCII case is folded;
other Unicode characters retain their spelling. `ber` finds “Berakhot”; `festival`
does not find “Autumn festival”. Empty queries list eligible paths. Ordinary
pages contain at most 20 entries; there is no substring or fuzzy fallback.

Search edition 5 uses commit-maintained `idx` postings under
`/<self>/idx/path_search`. Title prefixes up to eight Unicode characters have direct ordered posting
lists; longer title queries verify their full prefix against candidate metadata.
Path postings use the displayed parent plus the first eight characters of the
final name; full-prefix verification retains complete matches, including names
longer than eight characters and queries ending in a slash. There are no
query-time metadata scans or journal catch-up. Structural folders are maintained
through descendant contributions, stopping at `/<node>/app`. The declaration's
Subtree hunt is relative `app`: construction and maintenance visit application
records only. System publications, node roots, journals, governance and index
records are excluded. No system-publication search projection is built. Edition
5 rebuilds older indexes and removes their out-of-scope postings. Existing typed
selections and grants are unchanged; Explorer still browses the full namespace.

Protocol 2 returns an opaque continuation and revision token, bound to the
query, caller, published view and input. Changed revisions reject continuation.
Missing or incompatible indexes produce a readiness error and require rebuilding;
they never fall back to a scan. The compatibility `limited` field is always false.
Published declarations and trusted `/sys/goo/path_policy` restrict eligibility.
Unsupported data can appear in search; save preflight reports the exact record
and slot whose value cannot be exported.

Native interaction uses a 150 ms debounce. IME composition invalidates in-flight
searches and suppresses new ones until commit/cancel. Generation IDs discard late
replies. Up/Down select results, Enter adds, Escape dismisses, and Tab follows normal
form navigation. F2 changes care for the next pick. With an empty query, Left selects
a chip; Left/Right move among chips, Space or Enter changes care, and Delete removes.
Care and removal are also pointer targets and accessibility custom actions. Structural
paths require an explicit Folder or Subtree choice. The dropdown has loading, empty,
and error states and combobox/listbox accessibility metadata.

## Agent authority

Read and write grants are separate typed sets. Write grants also permit reading and
include their records in the context bundle. Grants use the namespace's actual care:

- File (`.x`): the selected record only.
- Folder (`.y`): that record and the nearest record-bearing descendants, passing
  through transparent paths and stopping at each intervening record.
- Subtree (`.z`): all descendant records.

The same reach check governs reads, writes, creation, and Grove action receivers.
`namespace_read` accepts `care: "x" | "y" | "z"`, defaulting to File. A requested
projection is rejected if any returned record falls outside the union of read and
write grants. Context export deduplicates overlapping records. Only hunts and their
container were added to the lossless namespace-text codecs.

Agents still read their own subtree and write their own workspace. Runner records,
grant-control records, `/gov`, `/io`, `/weft`, `/log`, and foreign authorities cannot
be written through agent tools. An explicit Folder write grant may create a record
through transparent paths, but cannot write below an intervening record.

The creation form and existing-agent dependency editor use the same two controls.
Saving existing dependencies does not submit a task. A trusted receiver commit
continuation (`/sys/goo/commit`) preflights the resulting context before admitting
an action, then applies idle-agent edits immediately. Running-agent edits stay in a
queue keyed by agent ID. Turns capture their grants before HTTP starts. Pending
changes apply at success or failure boundaries, before another turn; errors stay
errors until explicitly resumed. Exact-retry receipts include the continuation.
Legacy `dependencies: pails/ps` remain read-only Subtree grants and migrate on save.

## Verification

`extras/mounts/shuin-chat-test/paths.foil` checks real namespace frontiers, transparent
paths, creation boundaries, write-implies-read, protected records, default read care,
legacy interpretation, and unsupported-value diagnostics. The native `paths` test
covers search pages and revisions, structural results, rejected typed saves, creation,
editing, and migration. The agent mock suite exercises real HTTP holds and queued
edits at success and failure boundaries. Widget tests cover keyboard selection,
chips, IME, debounce, and stale replies. Native snapshots are emitted to `artifacts`
when `SHUIN_ARTIFACTS` is set.

The shared hunt types, typed admission, commit continuation and idx kernel
support are part of this checkout; no integration patch is needed.

Verified on 2026-11-19 against a freshly booted disposable Shrine and local mock
OpenRouter:

- `cargo test --offline --workspace`: 101 passed; live integration tests are
  opt-in and were run separately below.
- `shuin-widgets --test paths`: search/care/admission/migration and native draft
  retention passed; the live dropdown/accessibility test passed and confirmed
  picking does not save permissions.
- `extras/shuin/test-agents.py`: tools, Grove invocation, guards, inbox arrival,
  pending edits for separate agents, and success/failure boundaries passed.
- `shuin-widgets --test agents`: creation, task submission and exact retry passed.
- `shuin-widgets --test reflection`: retained editors and drafts across publication
  changes passed.
- Full and incremental Reaver patches passed reverse-application checks.

Native renders: `artifacts/Agents-create-native.png`,
`artifacts/Agents-dependencies-native.png`, and `artifacts/Agents-chooser-native.png`.
Keyboard and simulated IME composition tests passed. Live Japanese input-source
testing remains the user's separate manual check.
