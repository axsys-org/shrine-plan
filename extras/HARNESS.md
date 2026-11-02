# Harness, documents, and applications

The harness is the shared native work protocol plus the procedures and provider
adapters that use it. It is not a second world, a Python runner, or a replacement
for Nenex. Nenex is a document application in that world. The handbook is an
authored procedure and its maintained documents, not another application runtime.

## Ownership

| Location | Owns | Does not own |
| --- | --- | --- |
| `src/foil` and `src/reaver` | Namespace reads/writes, admission, reactions, cells/views, filesystem I/O, publication, Semidoc and native persistence | Application-specific work policies and handbook recipes |
| `mounts/cooperate/work*.foil` (`native_work`, `native_work_ops`) | Captures, activities, events, provider dispatch receipts/outcomes, context lenses and persistent holes | Document structure, source polling, provider transport |
| `mounts/cooperate/main*.foil`, `answer*.foil` | Investigation and question-answering policies over native work | Another attempt lifecycle or private work store |
| `mounts/flows/flow*.foil`, `runtime*.foil` | Semidoc procedure compilation, pinned operation selection, evaluation, preview and guarded commit | Browser state or provider processes |
| `mounts/flows/maintenance*.foil`, `request_ops.foil` | Reactive procedure maintenance and generic suspended requests using native work | Polling, a work queue, or a second retry receipt |
| `mounts/flows/work*.foil`, document operations in `operations.foil` | Document-revision policy: briefs, drafts, accepted revisions and evidence | A second provider lifecycle; arbitrary executable content generation |
| `mounts/flows/sources*.foil` | Evidence adapters and live source bindings using existing filesystem ownership | Filesystem actors, Nenex pages, example installation |
| `mounts/flows/web*.foil` | Explicit HTTP request/result adapter and native transport foot | Automatic research, polling or application-specific crawling policy |
| `mounts/codex` | Native provider hand and app-server transport/process lifetime | Deciding when a flow runs or when a domain result is acceptable |
| `mounts/nenex` | Semidoc page ownership, source/Goo editing, reader, question/block context and page-tool contributions | The work lifecycle or a flow evaluator |
| `mounts/flows/nenex*.foil`, `interface.foil` | Flow/Nenex integration: source authoring, page evidence, guarded writer and forms | The generic command catalogue or filesystem-source lifecycle |
| `mounts/flows/install.foil` | Native flow command/law registration and retained-contract checks | Nenex routes or example catalogue |
| `mounts/flows/examples.foil`, `examples/`, `examples.json` | Optional authored recipes and their setup data | Runtime policy for all flows |
| `tests/fixtures/block-document` | Goo regression fixture with its own small bounded block model | Nenex's document representation |

`install.foil` can assemble native commands without importing Nenex. The shipped
`flows` **mount still bundles** that backend with the Nenex integration and declares
Nenex as a dependency. Module separation is not a claim that there is already an
independently installable headless flow mount. Existing pinned module ownership,
logical names, public commands and retained contract definitions are unchanged by
this cleanup. We do not move contracts between publishers to tidy directories.

The flat source bags are a deliberate Eden publication boundary. Keep logical
responsibilities clear inside them instead of adding a new directory loader,
umbrella service, or compatibility mount. Runtime modules stay flat; examples and
test assets can live in subdirectories and are staged by the existing host/gate.
The flow native suites and transport fixtures are grouped under `flows/tests/`;
`mount.json` retains their existing logical suite names.

## How the pieces meet

An authored Semidoc definition selects operations or published child flows and binds
named inputs. Publishing captures those laws and selected child definitions.
Cells read evidence and expose the computation. The maintenance
hand reacts to dependency changes. A suspended step opens native work and a hole;
a provider returns a retained outcome. Domain acceptance checks freshness and shape.
The chosen writer admits changes through the same namespace admission as other tools.
The policy that permits adopting an unwritten document containing only its owned
holes lives with that Nenex writer, not in the shared native work module.
Nenex exposes those records, drafts and commands to a person.

A Nenex page can select a published flow into an ordinary captured cell and embed
an independently bound occurrence. The occurrence is the existing maintenance
controller under the page's named `work` child. A Semidoc `doc/embed` reference
projects that controller's work, cells and controls; it does not own the activity.
Removing the reference leaves the activity and history intact. Explicit detach
releases its claim and subscriptions. Selected occurrences retain the exact
definition publication while their input bindings remain live; existing live
maintenance attachments continue to follow publication.

Nenex's page/block question interface uses the shared answering policy directly;
it does not need to manufacture a flow. Cooperate investigations use the same
captures and provider protocol without requiring a document editor. A document
revision flow adds editorial and publication rules to that protocol.

Overlays and cells are views, not writable branches or ambient process namespaces.
Reads do not dispatch providers. An attempt's frozen evidence and definition remain
separate from its live context lens. An authored `/flow/invoke` evaluates the captured
child in the same invocation, with explicit inputs and scoped step identities.
Suspended child work uses the parent's native requests, holes and resolutions.
The parent's selected writer owns final publication. Captures, child step results
and final call results remain distinct events in the ordinary trace.

## Python and source adapters

Keep Python at host/process/transport and test boundaries:

- Eden's mount launcher and scan bridge stage files for the native filesystem foot.
- Codex's bridge owns app-server bytes and process cleanup. Native hands own work.
- `cooperate/client.py` is an optional thin MCP client for external callers.
- `flows/tests/client.py` is a transport helper for disposable regressions. The old
  production `flows/client.py` handbook workflow has been removed; use Nenex's
  author/publish/attach operations.
- `flows/host.py` stages the exact bytes of repository files declared in
  `examples.json`. Each file uses an ordinary native source hand; the existing
  merge cell combines their named evidence. Missing files disappear from the
  current scan while native captures and history remain. There is no bundle
  adapter, aggregate evidence format or compatibility decoder.

A source adapter may decode an input or perform an explicitly requested external
operation. It must not privately decide retries, watch ownership, or completion.
Those decisions belong to existing native records and reactions.

## Examples, fixtures, and remaining boundaries

`mounts/` contains optional application and capability mounts. Demonstrations such
as `hello-grove`, `goo-moodboard`, `life` and `patch-demo` are optional examples,
not dependencies of the harness. Browser/native conformance specimens belong in
`tests/fixtures/`; block-document is now there alongside panes and tree-pages.
Do not delete a regression merely because its fixture resembles an application.

The revision policy in `work_ops.foil` constructs Semidoc draft records. The selected
writer may declare an existing native `kook` in `flow/document`; attachment captures
that declaration from the writer's exact retained record, and each revision request
keeps it for completion. The Nenex writer opts into its document form there. Without
the declaration, drafts carry source only. Form paths retain ordinary native form
resolution semantics; this is not a new behavior publication mechanism.

`flow/definition` still carries optional document pages in its pinned contract.
Ordinary compositions leave that payload empty. The contract remains unchanged;
this work does not rebrand retained values or claim to remove that historical field.

Composition reuses native dispatch and holes, captures child definitions and bindings,
and gives effects an admitted writer. Evaluation is bounded to eight nested calls
and 128 executed steps across the whole invocation. Child publication takes effect
for live-path callers only when they are explicitly republished; explicit native
historical references remain pinned. Nenex composition controls author these
references and repeated bindings in Semidoc itself. Selected executed steps from
retained runs can become new Semidoc procedures with external dependencies exposed
as inputs. Arbitrary exploratory traces, ambient inherited bindings and independently
scheduled child controllers remain outside this implementation.

Declared Goo actions reuse the existing request interpreter and receipt journal.
A flow requests native work; its hand emits a native namespace command. Shared
admission checks current work and evidence before planning the declared Goo
action and its receipt together. The hand observes that receipt before accepting
the result. Existing emitted moves carry these commands; no action foot, polling
loop or second interpreter is added. Nenex reflects compiled controls into
captured cells and exposes their bindings for deliberate selection. Source authoring and extraction belong to the Nenex flow adapter;
the action work provider belongs to the shared harness.

## Validation and saved worlds

Use `extras/x/check --mount flows` for native suites and mounted entrypoint checks;
`flow_install_tests` exercises native installation and a Semidoc composition without
importing the Nenex integration. The flow suites cover suspension, freshness,
retries, source ownership and document publication. Nenex's suites own source/Goo
fidelity and question context. Codex's suites own provider transport and dispatch.
The fixture catalogue can be supplied to both Eden and `extras/x/check` with
`--extras-root`, following `tests/fixtures/tree-pages/README.md`.

Validate refactors in disposable worlds. Captured implementations, attempts and
x/y/z history belong to the saved world, not the source checkout. This cleanup does
not activate modules, patch a bootstrap, migrate a world or clean its storage.
The earlier reverse-reference integration changes the core `sov` contract and is
still not an upgrade path for a world running an older retained kernel.
