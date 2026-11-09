# Native checks and namespace reports

Python launches isolated runtimes, freezes inputs, stages the compiler, handles
process deadlines and retains launch diagnostics. Reaver/Foil execute checks,
contain execution exceptions and determine the native verdict. Eden's launcher
remains Python. Application work is exercised through the real native operations.

## Ownership and commands

| Boundary | Definition / owner | Entry point |
| --- | --- | --- |
| Core language and namespace | `test-inventory.json`, `src/foil/tests`, Reaver suites | `x/check --list`; `x/check SUITE` |
| Mounted application behavior | Mount `tests`, `test_files`, and `test_suites` declarations | `extras/x/check --mount NAME --suite SUITE` |
| Independent publication | Explicit Reaver publication fixtures | `x/check foil-semidoc-publication-tests foil-demand-publication-tests` |
| Filesystem lifecycle | Native watch fixture and external file mutations | `x/check flow-watch-lifecycle` (explicit selection) |
| Native crash/restart | External process driver, disposable native snapshots | `x/eden-persistence-test.py` |
| Actual Goo/browser interaction | Explorer application gate and fixture mounts | `extras/x/check-goo` |

Commands that execute native code require `WISP` or the repository's Nix shell.
`x/check` first runs its host failure-path checks. `extras/x/check-goo` includes
the conversation adapter checks for draft retention, refresh and Goo submission.
`x/check --fast` selects the existing fast inventory; it does not establish
mounted-world, browser or provider integration. The root Nix check runs `x/check`.
Live Codex demonstrations and cost measurements are separate, explicitly chosen
checks. Controlled provider responses do not establish model reliability.

`extras/x/check` reuses the core worker launcher. Its combined fixture is useful
for application behavior, but cannot establish separately published mounts'
contract identity. Keep explicit publication tests alongside those native cases.
Each mount declares executable native modules in `tests`, fixture-only sources
in `test_files`, and additional Reaver entrypoints in `test_suites`. Shared test
imports belong in `test_dependencies`; a specialist suite can declare its own
`dependencies`. These extend the disposable source tree, never runtime mount
dependencies. `manual: true` keeps cost probes out of the default run while
allowing explicit `--suite` selection. External transport, restart and browser
gates retain their separate launchers.
Command gates run frozen copies of their drivers, mount descriptors and extras
sources alongside the frozen core tree; queued execution never rereads the checkout.

The shared staging recipe installs the existing `plangrm:compileP6` before
loading the Foil compiler closure, and each worker selects it again because
`Install` is process-local. Its template key includes both compilers' source
dependencies. This only prepares disposable test snapshots; it does not
patch a running application or upgrade a retained world. Mounted checks use the
same staged template, without a temporary runtime wrapper.

Reproduce the flow library checks with the normal entrypoints:

```sh
extras/x/check --mount flows --suite flow_install_tests --jobs 1
extras/x/check --mount flow-examples --suite flow_library_publication_tests \
  --suite flow_stage_tests --suite flow_agent_qol_tests \
  --suite flow_cartography_lifecycle_tests --suite flow_library_tests \
  --suite flow_workspace_tests --jobs 2
extras/x/check --mount flow-examples --suite flow-reflected-authoring-tests --jobs 2
x/check flow-web-transport --jobs 1
```

The stage fixture reads the shipped catalogue and uses the native library
inspection/publication operations to publish only each case's requested recipes
and their dependencies. Its compiled Goo fixtures select graph through the
flow-examples test descriptor, including when run individually.
The HTTP command uses a local fixture server; fetch, lifecycle assertions and
report verdicts execute natively. These checks need no model account.

## Reports are namespace records

Each native worker retains its own disposable namespace at `/0x11/tests/run`:

- The root records selected-suite count, status, completion count, and pinned
  executable captures.
- `sources/<index>` retains the selected suite kind, module name and source text
  read from the worker's frozen source tree.
- `checks/<index>` records status, module, check name, expected and actual values.

`src/foil/testing_report.foil` admits these ordinary records through
`namespace_command`. The transition from `running` to `passed` or `failed` uses
the existing x/y/z journal. Completion cannot replace an already completed run.
Foil captures retain the compiled artifacts and their publication contexts;
Reaver captures retain the execution closure, including shared fixture helpers.
Suite source records are not a recursive text snapshot of every dependency.
Boolean Reaver entrypoints contribute one result per entrypoint; assertions
inside those functions are not automatically expanded into individual records.

`src/reaver/testing-report.rvr` binds the report into the disposable Reaver
session. The runtime's normal native Save preserves it; there is no JSON import,
report database or second save format. Successful arenas now contain reports and
are retained. Each worker has an independent namespace; a combined review surface
has not been implemented. This retention uses disk space and does not introduce
automatic reclamation or compact report exports.

The launch receipt in `result.json` points to the arena and namespace path. It
contains process status/timing and selected suite names, not individual results.
`results.json` collects those launch receipts. `out.log` remains necessary for a
runtime that crashes or cannot compile the report writer. A timed-out worker can
leave a saved `running` report: consult the receipt for process completion.

## Inspect a retained report

Use the worker's frozen source tree and arena, without starting an application:

```sh
printf '(test_report:read test_report_completed [])\n' |
  "$WISP" --file-root "$RUN/src" "$RUN/native/snap" root _
```

The worker directory is its group name (`native` above). Native bindings
`test_report_started` and `test_report_completed` retain the two states.
`test_report:versions` returns the report root's x/y/z versions;
`test_report:read-at` reads a historical x version. These are ordinary namespace
reads through the report's retained artifact. No new HTTP report viewer is added.

## Failure boundaries

Native cases, empty suites, missing selected results, failed compilation and
explicit Reaver entrypoints produce native failure records. An entrypoint failure
does not prevent later independent entrypoints from running. The launcher requires
the native summary, completion marker and successful process completion.

Older Reaver suites execute assertions during module import. Those failures still
require the launcher's uncaught-error guard; their module completion record alone
is not sufficient evidence of a successful process. An invalid or incomplete
worker must never be accepted solely because its report contains passing checks.
Migration is incremental; the guard remains required for the unmigrated suites
and for failures while loading dependencies.

## Scope of the explicit suite integration

This integration targets the behavior changed by the shared harness branch:

- `foil-publication-tests`: exact pinned contracts, captured implementations,
  publication guards and the existing native restart/history fixture.
- `foil-demand-publication-tests`: new graph policies using retained contracts.
- `foil-semidoc-publication-tests`: repeated bindings through publication and
  source/Goo edits.
- `foil-semidoc-layout-tests`: native Semidoc record tags and attribute occurrences.
- `foil-grove-context-tests`: Grove publication and slot presentation.
- The mounted `nenex-document-tests`: the actual source and block editors.

These checks execute through explicit entrypoints. The Semidoc and demand suites
prepare their system artifacts inside their invocation through ordinary native
publication operations. They do not import the eager, shared compiler-test
fixture. Grove context reuses the existing `foil-grove-fixture:create` entrypoint;
its other six consumers retain their existing registrations and test bodies.
The publication suite's `checkpoint-test` constructs the same checked fixture
explicitly for the separate restart driver.

Select the branch checks directly:

```sh
x/check foil-publication-tests foil-demand-publication-tests \
  foil-semidoc-publication-tests foil-semidoc-layout-tests foil-grove-context-tests --jobs 1
extras/x/check --mount nenex --suite nenex-document-tests --jobs 1
```

The publication and Grove-context suites have separate workers so unrelated
legacy import-time checks do not execute when these suites are selected.
The existing native Foil cases for admission, persistence, filesystem lifecycle,
Semidoc and the mounted harness continue through the shared native runner.

The launcher's disposable failure probe breaks an early publication assertion
and the final Semidoc layout assertion. It verifies that imports stay inert,
the later demand-publication check still runs, and reopening the saved namespace
retains all three outcomes and report history. Assertions and history comparisons
are native; Python only prepares disposable inputs and launches processes.

General compiler, bootstrap, context, brand and wire-codec suites keep their
original execution style. Their aggregate `foil-tests.rvr` and PLAN launcher
remain intact. Migrating those suites is separate repository work, not a
requirement for the shared harness. The uncaught-import-error guard remains
necessary for those tests and their shared setup.
