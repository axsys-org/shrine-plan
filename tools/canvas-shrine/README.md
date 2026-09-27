# Coursebook — a Canvas app in Shrine + Foil

Coursebook keeps observed coursework, local notes and planning state in Shrine.
Real Foil forms maintain deadline phases, freshness and focused notices. Python
fetches Canvas's official iCalendar feed, decodes it, advances the clock and
serves the local UI. Canvas remains authoritative for coursework and submissions.

The demo supports class filtering, assignment search, upcoming/past dates,
local completion, notes and the next seven days of calendar events. The feed
refreshes every 15 minutes while the process runs. The separate namespace
inspector shows the actual records and forms.

**Private feed addresses, coursework snapshots, browser observations and native
worlds are not included in this repository.**

## Run

1. Start a [Shrine v5 world and bridge](../shrine-mcp/README.md). The app reuses
   that owner; it does not start another Wisp.
2. In your Python environment, install both dependency files:

   ```sh
   python -m pip install -r tools/shrine-mcp/requirements.txt -r tools/canvas-shrine/requirements.txt
   ```

3. Obtain your own feed through Canvas → Calendar → Calendar Feed. Configure it
   locally with a hidden prompt; the address is a private bearer link:

   ```sh
   python - <<'PY'
   from pathlib import Path
   from getpass import getpass
   import json
   directory = Path.home() / '.local/share/shrine/canvas'
   directory.mkdir(parents=True, exist_ok=True, mode=0o700)
   path = directory / 'connection.json'
   path.touch(mode=0o600, exist_ok=True)
   path.chmod(0o600)
   path.write_text(json.dumps({'feed_url': getpass('Canvas calendar feed URL: ')}))
   PY
   ```

   This adapter is currently scoped to `sit.instructure.com` and Eastern Time.
   It does not use browser cookies or bypass institutional API restrictions.

4. Point to your world's connection file, install the actual Foil, and run:

   ```sh
   export SHRINE_CONNECTION=/absolute/path/to/world/connection.json
   cd tools/canvas-shrine
   python install.py
   python app.py sync
   python app.py serve
   ```

5. Open [Coursebook](http://127.0.0.1:8784/). Keep the process running for timed
   refreshes; this version does not install an OS login service or remote alerts.

The private feed configuration is separate from `SHRINE_CONNECTION`, which
authenticates to your local Shrine bridge. `SHRINE_BRIDGE` can override the bridge
module directory; the default is the sibling `tools/shrine-mcp` directory.

## Optional browser observations

The feed supplies course titles but may omit course codes and exact due times.
Copy `browser-seed.example.json` to
`~/.local/share/shrine/canvas/browser-seed.json`, or set `CANVAS_BROWSER_SEED` to
a private file. Populate it only with facts actually checked in Canvas:

- `observed_at`: ISO 8601 time of the browser observation.
- `courses`: entries with `id`, `code`, and `name`.
- `deadlines`: pairs of assignment ID and exact ISO 8601 due time.

The empty template is valid. Without an inventory, the app discovers course IDs
and names from the feed. Browser-only exact times retain their own evidence age;
an unchanged feed date does not reverify the precise time.

## What the data can establish

- The calendar feed contains dated work and events, not every file,
  announcement, undated assignment, submission receipt or grade.
- Marking work done here updates only the native local plan. It does not submit
  work, mark Canvas's planner or change a grade.
- Submission is unknown until independently observed. Past dates therefore say
  “verify submission,” not “you missed this.”
- Date-only entries retain that precision. Next midnight is only a date-passed
  boundary, never an invented exact deadline.
- Assignment overrides retain their distinct feed identities.
- Missing items are retained as unobserved in the latest feed, not deleted.
- Unsupported recurrence, bad input and unavailable feeds preserve previous
  state. Staleness remains visible even when a last-known date still looks valid.

## Files and native surface

| File | Responsibility |
|---|---|
| `campus.foil` | Native forms: deadlines, freshness, cancellation, local completion and notices. |
| `install.py` | Compile/pin exports, install forms, attach crews and retain unresolved work. |
| `bridge.py` | Thin shared client for existing native operations. |
| `canvas.py` | HTTPS and iCalendar I/O, identities, precision and local artifacts. |
| `app.py` | Observation loop, local HTTP routes and guarded planning edits. |
| `index.html`, `style.css`, `app.js` | Responsive interface over native state. |
| `test_coursebook.py` | Parser cases and actual native cascade checks. |

```text
/campus
  /forms/{assignment,source}  actual compiled Foil
  /schema                    native bindings and immutable module reference
  /clock                     observed wall clock
  /settings                  deadline/freshness/refresh parameters
  /source                    availability, coverage and evidence
  /courses/<id>              observed course identities
  /assignments/<feed-uid>    observations + local plan + maintained phase
  /events/<feed-uid>         calendar events
  /notices/...               native notices and history
  /work/build                originating work
  /questions/...             unfinished understanding
  /tests/<run-id>/...        separate test fixtures
```

The native engine initializes a new form before its crew is hydrated. The form
therefore publishes `unknown` until the clock is known, and import settles it
with an ordinary empty poke after attachment. Notifications arm only after the
initial basis is available. Later meaningful transitions can emit notices;
unchanged clock ticks do not repeatedly emit the same notice.

Edit `campus.foil` and run `install.py` to install a new pinned version. Failed
compilation leaves installed forms intact. The compiler module is referenced by
its immutable pin rather than duplicated into application state.

## Verification

```sh
python test_coursebook.py
```

This uses your configured native world and retains fixtures under `/campus/tests`.
The real-feed parser check skips when the optional private `first.ics` snapshot
is absent. No personal fixture is shipped. The original development run passed
eight checks plus live refresh and local note persistence across an app restart.

All state changes use native case guards. The HTTP app binds to loopback, rejects
cross-origin writes and keeps the private feed address out of its API response.
The existing authenticated browser remains useful for checking facts the feed
cannot establish.
