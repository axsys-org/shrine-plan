# Hands

A hand is a process outside the world. It never runs inside the runtime and
never touches the store; it talks to the world only through the MCP surface
an agent gets: read, write, history and the stream. A pure world has four
ways for anything to cross its boundary, and the four hands are those four:

| direction | hand | the plug |
|---|---|---|
| in, from time | `clock` | the system clock: `today(now, timezone)` |
| out, on a change | `watch` | `post(url, payload)`: one JSON POST (Slack is a URL) |
| out, on a request | `export` | `write_file(path, format, rows)`: JSON or CSV |
| in, on a schedule | `import` | `read_csv(source)`, `read_json(source)`: rows as dicts |

`ask` is the fifth, the model: it answers `ask` cells.

## Two halves, one of them written once

`hand.py` is the world half: config as a record at `/agent/hands/<name>`
(a person changes it with a write, no restart), where it left off as a
record at `/agent/hands/<name>/seen`, the stream followed with the poll
fallback from `stream.py`, every write signed `who: <name>` and idempotent,
`update()` as write-if-unchanged (the case it read rides with the write),
a failure logged and retried on the next line, never a partial answer.
The base also owns the rule that keeps two hands from ping-ponging: a line
from any hand, or one whose touched paths all sit under `/agent/hands`,
never causes a write by itself, and seen is marked only after a write, or
on a tick once the hand is a hundred lines behind its mark. A mark is an
event, and on the live page it lands on top of what the hand just saw, so
an idle hand writes none.

A hand is a subclass with at most two methods, each returning how many
writes it made:

```python
class Clock(Hand):
    name = 'clock'
    every = 60.0                      # seconds between ticks
    def tick(self, now): ...          # on a tick
    def line(self, line): ...         # on a stream line (optional)
```

`segment_of(text)` in the base makes a valid name from an id, a field or
a path (`p-1` is `p_1`, `full name` is `full_name`, a path is its segments
after the node joined by underscores); every hand names records with it.

The outside half is the plug: one function. A second plug on any hand is a
function with the same shape (`post`, `write_file`, `read_csv`); for
`import`, the field-to-slot mapping is a record under the hand's config,
not code.

## Running one

```bash
python3 extras/mounts/mcp/hands/clock.py http://127.0.0.1:8300 --timezone Europe/Berlin
python3 extras/mounts/mcp/hands/watch.py http://127.0.0.1:8300 --cells "/user/views/total" --url https://hooks.slack.com/...
python3 extras/mounts/mcp/hands/export.py http://127.0.0.1:8300
python3 extras/mounts/mcp/hands/import_.py http://127.0.0.1:8300
```

`--once` makes one pass and exits. A world kept with `--world DIR` names
the hands it runs in `world.json` (`--hand "clock --timezone UTC"` on the
first boot); the launcher starts each after the foot listens, with its log
at `DIR/hands/<name>.log`, and stops it at teardown. A hand not listed is
not running.

## Config, by hand

- `clock`: `/agent/hands/clock {timezone}`; writes `/clock {day, timezone}` once a day.
- `watch`: `/agent/hands/watch {cells, url}`; keeps the last value at `/agent/hands/watch/<cell>`.
- `export`: a request record under `/agent/hands/export/`: `{folder, format, path}`; poked with `done, path, rows`.
- `import`: `/agent/hands/import/<source> {kind, source, folder, key, every}`, `/map {field: slot}`, `/refs/<slot> {table, match}`; writes `who: import:<source>`, the source id at `/source_id`, references at `/<slot>_ref` made once.
- `ask`: `/agent/hands/ask {model, endpoint}`.

A hand that is not running shows as an `ask` that never answers, a
`/clock` day that is behind, an export request without `done`, an import
config whose `ran` does not move. The launcher's `Eden:` line names the
hands it started.

## Waking an agent

An agent is a name that owns paths (`/agent/<name>`, and whatever else it
keeps) and depends on paths (what its cells and plans point at). A wake is
a stream line touching one of those; the paths are the address, and there
is no field to fill. How an agent listens is its own plumbing, outside the
world, which never learns the vendor: an app that can watch a command
watches the stream itself; the rest run `wake.py`:

```bash
python3 hands/wake.py <base> --name codex --run '<the command that opens your app on a note>'
```

It follows the stream, reads what the cells under your folders point at,
and runs the command, one at a time, when a line not signed by you touches
something you own or depend on (`WAKE_PATHS`, `WAKE_FROM`, `WAKE_EPOCH` in
the environment, the line as JSON on stdin). Without `--run` it prints the
wakes. It never writes. The setup page has the commands for the apps we
know.
