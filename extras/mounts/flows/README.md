# Semidoc flow harness

Flows package reusable work in an authored Semidoc document. The handbook flow
uses editorial briefs and source dependencies to author and maintain **concept
documents**. It synthesizes explanations, examples and guidance; it does not turn
each README heading into a handbook chapter.

## Run the shared world

```sh
WISP=/path/to/wisp x/eden --mount flows --mount codex --compiler none --port 8300
```

Open `/nenex?path=/0x11/app/nenex/w/handbook_flow`. Eden captures the repository
inventory through its existing filesystem mount and installs the authored Semidoc
page, published definition and live evidence cell. Click **Attach maintenance**
to use the installed Codex hand. The source binding and destination are filled in.
No Python client, observer or worker command is needed.

The handbook reader and `/live` Cells surface share this world's namespace,
provider, hands and overlays. **Cells** on the handbook displays the actual native
maintenance work. Each concept row links its draft, context, evidence and hole.
Other authored flows get the same work cell and output embedding.

Repository files are external I/O. `host.py` only captures and hashes the declared
inventory when the filesystem foot asks; it has no queue, model or document policy.
The ordinary `/io/fs/flow_sources` capture instance shares the native filesystem foot.
It is separate from the program publication at `/io/fs/flows`, so evidence changes
do not compile the harness. The foot checks every 15 seconds and requests the normal source
scan after two matching changed captures. Unchanged bytes produce no namespace
write. **Capture repository changes** requests an immediate scan from Nenex.
Invalid/missing evidence blocks publication while retaining the last good documents.
Namespace evidence producers need no filesystem adapter. Source changes wake the
same maintenance hand; reads never dispatch a model.

The Codex mount uses the installed CLI's authentication and configured model.
The provider requests structured prose in a read-only thread. It never answers
approval requests, and credentials are not part of the flow. Leave the provider
empty for manual authoring, or bind another published native provider.

The source file seeds a missing authoring page. Edit its saved Semidoc and publish
to revise the procedure. Export namespace edits before stopping this development
world: restart recovery is not implemented by this launcher.

## Authoring contract

With the `flows` mount installed, Nenex's **Page tools → Flows** provides the
authoring lifecycle in the reader:

1. **Author a new flow** creates `NAME_flow` as an ordinary editable Nenex
   document. Supply evidence keys and an editorial brief for the initial
   `inventory → revise → evidence` composition.
2. Use **Edit source** and **Save page** to compose additional steps and briefs.
   Existing pages containing marked definitions receive the same controls.
3. **Publish flow** invokes the published native `publish` operation against the
   saved source. An obsolete form refuses rather than publishing another edit.
4. Bind the published definition's inputs to namespace paths, choose an output
   document and a provider, then **Attach maintenance**. `/x/...` binds a cell or
   overlay result; `sources` needs captured source envelopes. The existing live
   handbook feed is `/x/0x11/user/flow_sources/handbook_live` in the shared world.
   Leave the provider empty for manual completion, or use the installed Codex
   provider at `/0x11/io/codex/work_provider`.
5. The attached hand exposes status, output, work/drafts and its working overlay.
   **Pause maintenance** and **Resume maintenance** use native `set_enabled`.
   Republish after editing the procedure; source changes wake its dependencies.

These forms use `namespace_command/plan` and supervisor admission over the same
published `author`, `publish`, `follow`, `set_enabled` and `detach` operations as
other clients. They require no Python command or worker. Nenex accepts typed
page-tool contributions under `/gov/nenex_ui/tools`; the flows mount supplies
its own renderer and HTTP adapter without making Nenex depend on flows.

A section marked `/flow/definition NAME` contains an executable composition.
Ordinary prose and literal examples are inert. The standard Semidoc parser and
Nenex document model are reused.

| Attribute | Meaning |
| --- | --- |
| `/flow/input NAME` | Named namespace-tree input. |
| `/flow/step NAME ;/operation/path` | Invoke a published native operation. |
| `/flow/bind PORT VALUE` | Bind a port to an input or preceding step. Repeat for each port. |
| `/flow/result NAME` | Select the returned value. Exactly one. |
| `/flow/page RELATIVE_PATH` | Declare a page or editorial brief; `/` names the root. |
| `/flow/uses SOURCE...` | Declare the source dependencies for that page. |

The reserved `document` binding contains the authored pages. When passed to
`revise`, their bodies are instructions for authoring concept documents. When
passed to the deterministic `documents` operation, they are final page templates.
A different guide or synthesis reuses the same operations with different briefs,
source dependencies and destination. There is no handbook-specific prose in the
native runtime or provider.

Names are canonical symbols (letter followed by letters, digits or underscores,
up to 64 characters). Pages must avoid reserved `flows`, `work`, `inputs`,
`cells` and `reference` paths. Compilation rejects duplicates, unknown attributes,
invalid paths, missing/extra ports and forward references. Limits are 16 inputs,
16 steps and 32 authored pages. Use **Edit source** for executable definitions:
the block editor does not guarantee round-tripping repeated binding attributes.

A `flow/operation` is a published Foil law with named ports and a pure tree-to-tree
interface. Compilation captures the law and its publication moment. Native
reflection can inspect the typed definitions; there is no second evaluator.
The implemented control structure is ordered and acyclic. A judgment-producing
step can suspend and resume; general branches and extraction remain future work.

## Concept revision lifecycle

The shipped composition is `inventory → revise → evidence`:

1. `inventory` checks complete captured source envelopes.
2. `revise` forms a typed task for each page from its brief and declared sources.
3. The maintenance hand creates requests for tasks without a matching resolution.
4. A person or worker authors the draft against those captured materials.
5. `submit_revision` checks source/brief freshness, draft version, native content
   structure and controller state. It stores the resolution and rationale.
6. The spun proposal resumes the composition. `evidence` adds a compact source
   provenance index. Once all required concepts are ready, the hand publishes
   the complete tree through the existing Nenex writer.

Changing a source invalidates only briefs that declare it. Editing a brief also
invalidates its result. A completed resolution for an unchanged task is reused;
reading a cell never launches a model. Each step's result remains inspectable,
including the resolutions and their exact evidence. A response must name its
source evidence in its explanation; syntax/freshness checks do not establish
factual correctness. No generated example is represented as a passing test.

Each request lives beneath `<controller>/work/revision_N`:

| Child | Meaning |
| --- | --- |
| `instructions` | Native Semidoc brief and captured source material. |
| `draft` | The actual editable Nenex document being proposed. |
| `evidence` | Frozen evidence cell; read through `/x`. |
| `prior` | Frozen destination snapshot cell; read through `/x`. |
| `view` | Spun working overlay composing document, brief, evidence and prior state. |
| `guard` | Derived capture of the physical draft, including its revision. |
| `worker` | Shared native work activity, captured context and provider outcome. |
| `result` | Frozen accepted concept resolution. |

The default controller is under the authoring page's `work` child, so draft and
instruction documents can be opened in Nenex. The overlay binds to the physical
draft that editor operations change. It supplies a coherent working view; it is
not a universal write-through namespace or a new editor data model. Writes to a
synthesized `/x` result still require the corresponding explicit source operation.

To complete a draft manually, export or author a Semidoc section and submit it:

```sh
python3 extras/mounts/flows/client.py submit-revision REQUEST_PATH \
  --source concept.semidoc --note 'What changed and which evidence supports it' \
  --expected DRAFT_VERSION
```

The version is the physical draft version captured before editing. Omitting it
captures the current version at submission; native providers retain the
version from before generation. Generated content may contain native prose,
sections, items, quotations, literals and valid rich text. Executable attributes
and arbitrary reference blocks are refused. The writer supplies source and child
links. Identical response retries are no-ops; conflicting retries refuse.

## Cells, hands and admission

`follow` installs a reusable hand and a spun at `<controller>/view`. Its tack is
the published definition. Named source bindings and completed resolutions are
secondary inputs. Crew subscriptions wake it on changed dependencies. Pending
work is exposed by the frozen queue cell at `/x/<controller>/queue`.

`cooperate` and flows share `native_work`: one activity record, captured-value
representation, frozen-cell implementation, freshness check and provider request/
outcome contract. Flow captures add a port name; their evidence is the same
`native_work/captured` value used by investigations. A flow's attempt retains its
own compiled definition and destination plan, while shared activity state owns
completion. Existing cooperation commands remain usable.

The maintenance hand creates requests and admits results. The Codex provider hand
creates an ordinary bridge command once, subscribes to its acknowledgment and
then its stable per-turn completion record. It freezes the original draft guard
alongside the result. No Python process polls work queues or advances a flow.
Model work is serial per controller. Failed or uncertain results remain recorded;
the same evidence does not replay the model call. Independent remaining concepts
can proceed. A provider can explicitly return an empty `source` and a `note`
describing missing evidence instead of fabricating a completed concept.
Manual and automatic admission share the task-freshness and content checks.

Each pending concept retains a hole at
`<concept>/holes/<author-page>/<step>`. This is the subject's unresolved work,
not a transient queue item. It retains its question, expected result shape,
failure/missing-evidence reason and current attempt. Its `context` spun selects
the current task for that concept from the published flow's evaluation. Unrelated
source changes do not count as changed evidence for that demand. The shared
native hole hand observes the lens and sends a resume notification to the
existing maintenance activity when its reading changes. Maintenance stages a
fresh captured attempt and uses the same configured provider and admission path.
Completed holes stay attached as resolved records and can reopen on later
evidence. No Python scheduling is involved.

The request's `/x/<request>/view` is the shared live lens over `document`,
`brief`, `prior`, frozen `evidence`, and the demand's `live` context. The provider
receives the current task's captured brief/evidence and prior draft; attempts
retain their original task and guard after the lens changes. This implements
Ian's live context/retained demand pattern without importing his agent loop,
web crawler, date scheduler or model-directed arbitrary-write protocol. Paused
and detached controllers retain holes but do not dispatch or admit new work.

[`examples/evidence_resume.semidoc`](examples/evidence_resume.semidoc) is a small
authored example of this cycle. Bind a `readiness` source that initially lacks
`GATE_OPEN`; the provider leaves a reasoned hole. Publish a new source envelope
and update the existing observed feed with evidence containing that marker. The
native hand resumes and publishes the concept. Reads, elapsed time and identical
evidence do not retry it.

Publication uses the same pure Nenex materializer as deterministic flows. It
protects edited generated prose, rejects collisions and page removals needing
migration, and preserves named notes/cells/work. A destination claim prevents
competing maintainers. Source failures retain the last good handbook. Pauses
stop acceptance/publication; resuming catches up. Detach releases the claim and
retains historical work.

```sh
python3 extras/mounts/flows/client.py pause CONTROLLER
python3 extras/mounts/flows/client.py resume CONTROLLER
python3 extras/mounts/flows/client.py detach CONTROLLER
python3 extras/mounts/flows/client.py publish AUTHOR_PATH handbook
python3 extras/mounts/flows/client.py export AUTHOR_PATH handbook.semidoc
```

Successful generations retain the pinned definition, inputs, trace and result
under `<controller>/work/N`. `<destination>/flows/latest` links to that run.
Old attempts keep their meaning after a source or definition changes. Trusted
clients with unrestricted raw namespace writes can bypass the protocol; this
is not an isolation boundary against those clients.

## Deterministic flows and format import

The existing `identity`, `decompose` and `documents` operations remain available.
`decompose` is a bounded Markdown-to-Semidoc importer, useful at an external-format
boundary. `documents` can combine fixed authored templates with imported source
guides. Neither is involved in editing an existing Nenex document. The concept
handbook uses `revise` and `evidence` instead.

Pure flows support `preview` followed by `commit`. A preview freezes its inputs,
definition, step values and destination revision. Commit checks those captures and
is idempotent. Judgment-bearing flows currently use `follow`; manual preview
refuses with `flow_revision_requires_follow` rather than pretending a brief is a
finished result.

Native operations under `/<node>/gov/flows/` include `author`, `publish`,
`import_source`, `observe`, `source_failed`, `preview`, `commit`, `follow`,
`submit_revision`, `set_enabled` and `detach`. They use ordinary namespace
admission; native callers do not require MCP. The filesystem/CLI helper uses the
existing generic transport. It does not own the work lifecycle.

## Source capture and checks

`prepare` reads the complete declared inventory, bounds it and hashes exact UTF-8
bytes. `--from-bundle` verifies saved hashes for replay. The native filesystem foot requires two
equal changed captures before requesting a fresh mount scan. Missing/invalid files block
maintenance. Recovery works even when restored content is unchanged. This is
stable capture, not a filesystem transaction. Native import retains the supplied
SHA-256; the filesystem client independently calculates it.

```sh
WISP=/path/to/wisp python3 extras/x/check --mount flows
python3 -m unittest discover -s extras/mounts/flows/tests -p 'test_*.py'
python3 extras/mounts/flows/tests/revisions_transport.py http://127.0.0.1:8138 --codex
python3 extras/mounts/flows/tests/maintenance_transport.py http://127.0.0.1:8138
```

Transport tests use disposable fixture paths. The earlier address-book/Austin
application, Python import scripts and Nenex domain declarations have been removed.
Address/OSM remains a proposed representation example in the handbook; it does
not claim an installed importer.
