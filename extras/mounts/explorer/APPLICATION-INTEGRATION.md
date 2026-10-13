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

## Prepared child-page regression (2026-10-05)

`check-tree-browser.mjs` now delays a real prepared child-page response, checks
that existing rows remain visible, and observes DOM mutations to reject any
available row attached without its Goo presentation. It also exercises the
64-child continuation, deferred grandchildren, retained row identities and
cached size variants with no individual child-summary render requests.
Structural branches still display their namespace path.

Verified against the compiled `tree-pages` and `panes` fixture on port 8097:

- Node adapter/session/transport tests: 74 passed.
- Native mount checks: 649 passed (Explorer 484, web 135, debugger 28,
  mount contracts 1, Grove debugger 1).
- Tree hydration and layout browser gates: Chromium 151.0.7922.34,
  Firefox 153.0, WebKit 26.5, all passed. The tree gate also runs nine
  shared topology cases in each engine.

- Full Chromium application gate: 10 scenarios passed, 95 real render responses
  and one deliberate domain action, including saved input, stale responses,
  instance replacement and native input identity/composition preservation.

The prepared-page tests cover missing/duplicate packets, profile mismatch,
subject/lifetime/epoch mismatch, multiple slots, snapshot consistency and a
failed refresh retaining the installed tree. Action versions remain those of
the resolved writable receiver; they are not replaced by projection versions.

## Path constructor regression (2026-10-05)

The compiled `tree-pages` fixture includes a record with no lede. The tree gate
checks that its canonical namespace path is present in the initial SSR HTML and
remains its Goo presentation after hydration. Selecting it loads the real
synthetic follower, whose slot heading uses the shared path formatter.

Verified against the compiled application on port 8098:

- Node adapter/session/transport tests: 74 passed.
- Native checks: 664 passed (Explorer 499, web 135, debugger 28, mount contracts
  1, Grove debugger 1), including all 15 new path cases. The final Explorer
  suite was rerun after correcting the generated test document and testing the
  root through a typed field; the other mount suites passed unchanged.
- Tree/path and layout browser gates: Chromium 151.0.7922.34, Firefox 153.0,
  WebKit 26.5, all passed; nine shared topology cases per engine.
- Full Chromium application gate: 10 scenarios passed, 95 real render responses
  and one deliberate save action.

The native path cases cover receiver fallback, lede precedence, typed fields,
path literals, a typed root path, missing optional fields, nested `present`, live and
SSR identity binding, synthetic slot labels, and invalid arguments.

Known upstream boundary: authored root-only `'/` literals currently fail Grove
compilation. Typed root paths still render `/`; the constructor does not add a
second literal parser.


## Presentation inspection regression (2026-10-05)

`check-inspection-browser.mjs` exercises the actual `/goo/inspect` formatter and
installed render packets. It delays an actual response for ordering coverage;
it supplies no mocked domain decisions. Each engine captures a tree summary,
recaptures it, inspects the inspector's generated presentation, supersedes a
pending capture, and inspects an editable view during composition.

Verified on the compiled `goo-inspector`, `tree-pages` and `panes` application at
port 8100; served inspection JavaScript matched the checkout:

- 80 Node tests passed, including six capture identity/privacy/lifetime tests.
- 679 native checks passed: Explorer 514, web 135, debugger 28, mount contracts
  1, Grove debugger 1. Explorer was rerun with the final observation schema.
  Fifteen new native cases include actual HTTP JSON byte framing, typed path
  rendering, provenance, no domain controls, and malformed/duplicate fields.
- Chromium 151.0.7922.34, Firefox 153.0 and WebKit 26.5 each passed six real
  inspection captures. Checks cover unchanged namespace/selection, source links,
  late response rejection, bounded self-inspection, excluded draft contents, and
  retained input identity, caret and composition. No domain action was sent.
- Full Chromium application gate: ten scenarios passed, 102 real render
  responses and one deliberate save action in the disposable fixture.

The inspection records are browser observations rendered through Goo's existing
synthetic pipeline. They are not persisted namespace assertions or execution
traces; no historical replay or per-branch explanation is claimed.
