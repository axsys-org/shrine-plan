# Shrine extras

Optional applications shipped in the core repository. Each directory under
`extras/mounts/` is a flat source bag. From the repository root, `x/eden` reads
these live sources by default:

```sh
x/eden --mount explorer
x/eden --mount debugger --mount srs --mount codex --check
x/eden --extras-root /path/to/other/extras --mount explorer
```

`web` owns shared browser routes, page composition and stylesheet.
`openrouter` supplies the generated client used by Chat; regenerate it with
`extras/x/generate-openrouter`. `explorer` adds `/ns`.
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
- `grove`: ordered units with `root` segments, ordered `files`, and optional
  compiler `prelude` module.
- `roots`: complete publication ownership, matching modules and Grove units.
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
on failure. Activation runs only at startup. Existing instances, HTTP handlers,
assets and registered drivers remain pinned until explicitly installed or started
again. No watcher or automatic migration runs.

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
extras/x/check-rescan
extras/x/hyp --check
python3 extras/mounts/codex/codex_bridge_tests.py
nix develop path:./extras#debugger --command python3 extras/mounts/debugger/check-debugger.py
```

The extras test runner assembles a disposable test fixture tree from core and the
flat descriptors. That compatibility layout exists only inside the test worker.
The production bootstrap reads namespace source snapshots through mount mappings.
Runners default to core in the parent of `extras/`; `--core-root` or
`SHRINE_CORE_ROOT` can select another core checkout. `migration.json` records
the original core paths and their destinations relative to this directory.
