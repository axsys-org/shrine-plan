# Shrine extras

Start with [Harness, documents, and applications](HARNESS.md) for the ownership
map: native work, flows, providers, Nenex, their integration, examples and fixtures.
The harness shares one native world; the handbook is an authored flow.
The optional [graph library](mounts/graph/README.md) publishes Foil/Grove evidence
projections using the existing overlay contracts; it has no service or scheduler.

For a worked example, read [Making a Grove and Goo mount](tutorials/grove-goo-mount.md).
Its runnable `hello-grove` mount includes a notes list, reader, and editor.

Optional applications shipped in the core repository. Each directory under
`extras/mounts/` is a flat source bag. From the repository root, `x/eden` reads
these live sources by default:

```sh
x/eden --mount explorer
x/eden --mount inspector --ephemeral
x/eden --mount debugger --mount srs --mount codex --check
x/eden --extras-root /path/to/other/extras --mount explorer
```

Eden keeps one native world per node in `$XDG_DATA_HOME/shrine/worlds/` (default
`~/.local/share/shrine/worlds/`). `--world PATH` selects an explicit directory;
subsequent launches remember its mount selection. Namespace state, history and
reachable compiled definitions share the runtime's snapshot root. Commits precede
write acknowledgments. Restart recreates I/O connections with fresh host
arguments, without reinstalling application seeds or replaying completed work.
`--ephemeral` and `--check` use disposable worlds. A world lock prevents two
launchers from serving the same store concurrently.

`web` owns shared browser routes, page composition and stylesheet.
`openrouter` supplies the generated client used by Chat; regenerate it with
`extras/x/generate-openrouter`. `explorer` adds `/ns` and the shared Goo document
host. The optional [read-only inspector](mounts/inspector/README.md) adds `/live`
and depends on `explorer` and `mcp`. It inspects native records, cells, overlays
and history; it does not run agents, write cursor records or create workspace
bindings. Direct MCP read/write/history/apply remain available by selecting the
`mcp` mount, independently of either browser surface.
`debugger` depends on `web` and `codecs`, publishes `/gov/debug`, installs
`/app/debug`, and owns `/debug` and `/debug-read`. `srs` publishes `/gov/srs` as
an installable template and automatically installs `/app/srs`. Additional SRS
instances can still be installed from that template. `codex` registers its driver
and owns the bridge's lifetime; set `CODEX_BIN` for a real server (`--check` uses
the fake server).
Chat, demo, Life, Loom, Nenex and Watch publish their modules and activate their
manifests. Hyp retains its standalone runner. Board and tic-tac-toe retain their
legacy declarative source bags; they had no Eden startup entrypoint.

## Descriptor version 1

`mount.json` declares:

- `name`, `version`, `dependencies`: identity and ordered prerequisite names.
- `modules`: logical Foil name to flat filename. File relocation does not rename
  definitions; `apps/life/main` remains `apps/life/main`.
- `pinned_modules`: owned modules whose exact predecessor artifacts are retained
  when behavior is republished. Persistent contracts and executable helpers have
  separate modules; source similarity never establishes type identity.
- `pinned_imports`: core-source modules whose retention this mount explicitly
  owns. They use the same predecessor-artifact selection and publication roots,
  including first compilation. `web` retains `semidoc` this way, so downstream
  Nenex and flow publications share the same authored-node and attribute types.
  No unrelated mount is searched for a replacement artifact.
  Retention selects the whole artifact, including its executable helpers. Thus
  `semidoc` itself stays captured; newly published Nenex/editor adapters consume
  that exact library. Pinning is not selective type matching or an automatic
  upgrade of that library's parser.
- `grove`: ordered units with `root` segments, ordered `files`, and optional
  compiler `prelude` module.
- `roots`: complete publication ownership, matching modules, retained core imports
  and Grove units.
- `assets`: HTTP asset name to required flat filename.
- `activate`: `{module, entry}`; namespace to `either[pail namespace]`.
- `http`: `{module, entry}`; captured `[filename, bytes]` rows and namespace to
  `http_foot/config`. `routes` declares claims; duplicate claims are rejected.
- `start`: `{module, entry}`; supervisor handle and host argument strings to
  registration result. Used for post-start driver registration.
- `host`: Python file with optional `prepare(root, work, check, cleanup, context)`
  returning a scan bag and string arguments, `scan(root, bag)` for preparation on
  explicit scans, and `check(url, node, timeout)` for integration checks. Register
  companion cleanup on the supplied `ExitStack`.
- `inspection`: selects the bounded inspection and journal response renderer.
- `tests` and `files`: test module mappings and original-path migration inventory.
  These are not overlaid into core at runtime.

Mount records and captured sources live under `/<node>/io/fs/<name>`. Definitions
remain under `/lib` and `/gov`; installed instances remain separate. Rescans
publish valid candidate outputs atomically and retain the last successful output
on failure. Application activation runs only when creating the world. Existing instances, HTTP handlers,
assets and registered drivers remain pinned until explicitly installed or started
again. Filesystem source watches are explicitly attached and reconciled by the
existing foot; a source scan is not an automatic service or world migration.

The debugger's host entrypoint builds through `extras/flake.nix`, whose Mash
input is pinned separately from core's tools. Source rescans refresh current
checkout contents; changed browser inputs rebuild their captured assets. Core's
bare shell does not need Node, pnpm or Mash, and bare Eden does not read these
application sources. There is no external extras repository input or pin.

## Validation

From the repository root, enter core's Nix shell (or set `WISP`) for Foil checks:

```sh
extras/x/check
extras/x/check --contracts-only
extras/x/check --mount life --mount codex
extras/x/check-goo
extras/x/check-rescan
extras/x/hyp --check
python3 extras/mounts/codex/codex_bridge_tests.py
nix develop path:./extras#debugger --command python3 extras/mounts/debugger/check-debugger.py
```

`extras/x/check-goo` is the production compatibility suite, also run by CI.
It builds the locked Mash Nix artifact and validates native contracts, prepared
geometry, and a disposable real Eden instance in Chromium. The application gate
uses production asset hooks and a test-only panes fixture. `goo-inspector`
provides the declared Goo namespace view at `/goo-inspector`; it is distinct
from the optional read-only `/live` inspector. SRS and Grove-dev retain their
domain/development behavior. See the
[application integration guide](mounts/explorer/APPLICATION-INTEGRATION.md).

The extras test runner assembles a disposable test fixture tree from core and the
flat descriptors. That compatibility layout exists only inside the test worker.
The production bootstrap reads namespace source snapshots through mount mappings.

Mounted checks share `extras/x/fixture_sources.py` for staging. To run one suite and its
mount contracts, use `extras/x/check --mount flow-authoring --suite tests/flows` from the
repository root. The execution-only mount is checked with `extras/x/check --mount flows`.
Native work/source/retry integration belongs to `tests/flows`;
`flow_ui_tests` checks native document adapters; the reflected authoring gate compiles the production Grove controls and compares browser/headless invocation. Nenex question
tests use Nenex and cooperative work directly, without a flows test dependency.
Core Goo runtime checks run in the core gate; mounted Goo text, style and view
checks run in explorer's `test_goo_v2` suite. The test-only `tests/fixtures/block-document` covers its
small document operations rather than re-registering those shared Goo cases; it
is not Nenex's document model or a production mount.
The component browser check owns rich formatting, undo and draft retention;
the block-document browser check owns structural editing and exact typed
save/reload. The filesystem actor check owns cancellation acknowledgements;
the flow watcher integration covers real file changes, dynamic bindings, late
read rejection and retained history without repeating flow publication.

The optional `/live` inspector has native route checks in
`extras/x/check --mount inspector --suite tests/inspector` and read-only adapter
checks in `node --test extras/mounts/inspector/tests/goo-live.test.cjs`. Its own
host check verifies packaged page and asset hashes.

Mounted workers stage under core’s `.check/`, avoiding large arenas on `/tmp`
tmpfs. Successful native workers discard their disposable arenas while retaining
frozen sources, inputs, logs and results. Failed workers retain their arenas for
diagnosis;
the compiler template remains cached. This does not clean existing run directories
or touch persistent user worlds.

Runners default to core in the parent of `extras/`; `--core-root` or
`SHRINE_CORE_ROOT` can select another core checkout. `migration.json` records
the original core paths and their destinations relative to this directory.
