# Real Goo application integration gate

Run the required compatibility suite from Reaver's locked runtime shell:

```sh
nix develop .#eden --command python3 extras/x/check-goo
```

The suite builds `path:./extras#mash-workspace` at the immutable revision in
`extras/flake.lock`. It checks native contracts, browser adapters, font/geometry
conformance and the live application. Install that build's Playwright Chromium
once in the Extras debugger shell (`pnpm --dir "$MASH_NIX_ROOT" --filter
@mash/visual-tests exec playwright install chromium`). CI installs the browser
and runs the complete suite on every pull request. The check is named
**Production Goo compatibility**; repository branch rules must require that name
where merge protection is desired.

For just the application gate:

```sh
WISP=/path/to/the/locked/wisp python3 extras/mounts/explorer/scripts/check-integration.py
```

No local Mash checkout or asset preparation override is accepted. The gate
records the clean build's revision and Nix store path, verifies the vendored
profile against it, and uses the unchanged production Explorer/debugger build
hooks. Production topoi builds also verify profile identity and bytes.

`goo-inspector` is the only production Goo view consumer. The gate adds
`extras/tests/fixtures/panes` to a disposable mount catalogue for interaction
regressions. That specimen is unavailable in the production catalogue. The
shared Explorer rendering and namespace infrastructure remains in production.

The browser scenarios cover:

- Compiled `/goo/render` responses with profile identity, render context and the
  portable display list; hydration and local selection invoke no domain actions.
- Independent selection owners and following presentations.
- Container resizing, RTL and text scale reaching server preparation.
- Native input identity and draft retention during composition and resizing;
  Stay/Discard departure guards.
- A delayed real server response arriving after another selection was accepted.
- A real Save action followed by a persisted reread and refreshed list projection.
- Replacing the actual test installation through `/grove/dev`, which changes
  source/member lifetimes and retires the old accepted encounter.
- Registered Goo inspector workspace receivers, child selection,
  structured synthetic followers and contextual rendering after resizing.
- Actual Mash list, tree and diagram components through the shared topology
  browser cases: focus projection, renderer changes, unavailable/deleted members,
  reused keys, retained native controls and inert hydration.

Response interception only delays an actual `/goo/render` response to exercise
stale-result handling. The topology browser cases create their own temporary
browser fixture using the loaded production classes; the selection/edit/save
and replacement cases use the real compiled application. Browser constructor
instrumentation exposes the real `GooPanes` instances for assertions without
changing their behavior.

Use `--output DIR` to retain startup logs, screenshots and JSON scenario results
at a chosen location. Startup compiles real mounts and may take several minutes;
`--startup-timeout` defaults to 900 seconds. The runner terminates its process
group when the gate finishes or fails.

`--panes-only` runs the application scenarios without Goo inspector
for diagnosis. Its output is marked as a subset; it does not pass the full gate.

`--url http://127.0.0.1:PORT` instead targets an already running **disposable**
Eden server with the test-only `panes` fixture and `goo-inspector`. This mode edits Card B and replaces that
server's `/0x11/app/panes` installation. It is for isolated test instances.

This gate complements the renderer-only
[`goo/scripts/check-profile.py`](../goo/scripts/check-profile.py) and the fast
Node session/adapter tests. It does not replace font/geometry conformance or
claim hardware IME coverage; composition events are dispatched in Chromium.
