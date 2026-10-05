# Grove Canvas

This mount implements the evolving workspace in `doc/grove-canvas.md`.
Its default surface discovers native Grove/Goo presentations. The ordinary
`canvas.grove` template creates editable concept subjects; the browser renders
native frames and invokes their declared actions without per-domain handlers.
Subjects occupy an infinite canvas. Native editors open in place; local
experiments sit alongside their subjects. The separate equipment workspace
retains the first availability instrument.
Availability, comparison, retained demonstrations, candidate assessment and
publication run in native Foil. Browser code draws the experiment and retains
local drafts. The Python host authenticates and transports requests only.

Start a dedicated native world, outside iCloud:

```sh
python3 x/eden --runtime /absolute/path/to/wisp --protocol canvas/1 \
  --world /absolute/local/path/to/canvas-world --mount canvas --port 8140
```

The browser surface listens on loopback port 8141 (`CANVAS_PORT` overrides it).
Set `CANVAS_EPHEMERAL=1` for disposable acceptance runs; they keep their own
connection files without replacing the current workspace link.
On macOS, open **Grove Canvas** from `~/Applications`. The launcher reads the
current private connection and opens it in your default browser. Once connected,
bookmark the ordinary `/canvas` page. No Codex browser or credential-file editing
is needed. The launch credential is exchanged for an HttpOnly, SameSite cookie
and removed from the address bar. Browser access lasts 90 days and survives host
restarts; reopen the launcher if another browser needs connecting.

`browser-session.json` is host-only, mode 0600, outside the native source closure.
Each world uses its own cookie name: browser cookies are not isolated by TCP port,
so test worlds must not overwrite the development world's login. The backend has
a separate per-session credential, and agents retain separate restricted access.
Never expose either listener externally. Run the same command to resume the
pinned native world; source changes do not automatically replace its behavior.
`canvas-admin.json` remains available for automated acceptance and recovery.

The agent connection is deliberately narrower:

```sh
python3 extras/mounts/canvas/mcp.py \
  --connection /absolute/local/path/to/canvas-world/canvas-agent.json
```

MCP protocol `2025-06-18` provides `read`, `source`, `eval` and `continue_candidate`. `read`
accepts an exact subject reference to return its native presentations, fields,
occurrences and control routes. `source` accepts the presentation's exact
reference and revision. Begin a
candidate in Canvas; an agent can inspect and continue it. Native and host
checks both deny agent publication. The MCP adapter uses the same native
endpoint as the browser. `eval` compiles an ephemeral Grove presentation edit
against an exact subject, view revision and publication. It does not install
source or dispatch actions. `read` and `eval` accept a bounded native rendering
width. These are application-level principal boundaries,
not an OS sandbox for arbitrary code already running as the same macOS user.

## The interaction to exercise

In the default Canvas, double-click empty space or use **New concept** (`N`).
Native creation opens the subject's editor and focuses its input. Save with its
declared action or Command-Enter when there is exactly one action. Drag handles
or use arrow keys (Shift for larger moves); drag the background, hold Space, or
use two fingers to pan. Pinch to zoom around the pointer. **Fit** (`Command-0`)
brings subjects and open experiments into view. Geometry survives reload without
rewriting native records.

Inspect a native presentation and choose **Try a presentation change**. Its exact
Grove source and native comparison live in an attached canvas instrument.
Command-Enter previews an edit; Escape or **Back to subject** returns focus.
Reopening keeps the draft. This preview requires a world installed with the new
native compiler exports; historical pinned worlds do not acquire them from a
frontend reload.

The separate equipment workspace exercises the retained behavior lifecycle:

1. Inspect Camera A's existing 10:00–11:00 booking through its situations.
2. Try a 15-minute handover. Compare Alex and Sam starting at 11:00.
3. Enable the same-person exception and keep the candidate.
4. Use **Keep** next to Alex's situation to retain the demonstrated outcome.
5. Publish the exact candidate. Make a real reservation with the installed rule.
6. Propose removing the exception: the retained example must block publication.
7. Continue the same candidate through MCP, then return to Canvas.
8. Restart the native owner. Confirm state, examples and the candidate survive.

Hold Option and hover a rendered record, relation, outcome or rule control to
inspect it. Command-I toggles persistent inspection; keyboard focus also moves
the context. Enter pins it, Escape exits. Inspection never also invokes the
underlying application action. The panel does not reflow the canvas.

The equipment surfaces and experiment timeline use current native records.
Select any existing reservation to anchor the timeline. The six comparison
situations under Rule checks are declared boundary cases evaluated
against the current reservations. Retained commitments instead preserve their
original input records. They are not universal proof. Ordinary use never silently
becomes a must-hold requirement. Only an explicitly retained demonstration is
promoted with publication.

## Current boundaries

This remains an incomplete visual Grove editor. Generic presentation discovery,
source inspection, native source preview and declared actions are connected; the equipment
instrument still needs conversion, and localized agent source authoring is not
yet connected. General source candidate persistence/publication is also open.
The UI does not claim that saving an intention generates code.
The current Goo renderer also retains its explicit ASCII measurement limit.
Unsupported rendering produces a diagnostic. No generated response or mocked
frame counts as native acceptance.

Frontend assets are dependency-free ES modules and CSS. There is no separate
npm install or build cache. Transient browser state does not create native
history. Native events carry exact subjects, expected cases and event IDs.

Transport tests: `python3 -m unittest discover -s extras/mounts/canvas -p test_transport.py`.
Native tests: `WISP=/path/to/wisp python3 x/test_runner.py --jobs 1 mount:canvas:tests/canvas`.
See `doc/grove-canvas-status.md` for actual results and outstanding release gates.

Generic native surface / actual MCP acceptance (creates one test concept):
`python3 x/check_canvas_surfaces.py --world /absolute/development/world
--output /absolute/receipt.json`.
Add `--refine` to require bounded rendering, native source compilation and actual
MCP comparison parity. Browser state regressions:
`node --test extras/mounts/canvas/test_canvas_space.mjs
extras/mounts/canvas/test_inspection.mjs extras/mounts/canvas/test_surface_state.mjs`.

Live read/restart evidence: `python3 x/check_canvas_live.py --world /absolute/world
--reads 10000 --owner-pid OWNER_PID --max-p95-ms 300 --output /absolute/receipt.json`.
The receipt records failures as well as successes. `--journey` performs the native
fixture lifecycle and should only be used on a disposable fresh workspace.
The browser journey leaves a candidate open for actual MCP continuation:
`python3 x/check_canvas_mcp.py --connection /absolute/world/canvas-agent.json
--output /absolute/mcp-receipt.json`.

The current runtime patch set includes collection of terminated Spawn actors by
capability reachability. C-created actors remain embedder roots; live actors,
open handles and queued capabilities retain their targets. This avoids keeping a
minimum pair of heaps for every finished HTTP connection. Resource acceptance
still requires a passing whole-application endurance run; unit tests alone are
not a stability claim.
