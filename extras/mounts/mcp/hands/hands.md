# Hands

A hand is a process outside the world. It never runs inside the runtime and
never touches the store; it talks to the world only through the MCP surface
an agent gets: read, write, history and the stream. Two hands:

| hand | what it is | the plug |
|---|---|---|
| `clock` | the smallest source: the day, once a day at `/clock` | the system clock: `today(now, timezone)` |
| `source` | one runner for every source an agent promoted to a hand | a script per kind in `sources/`: `marker`, `skeleton`, `regions` |

Everything that used to be an import, a watch or an export is a source or a
view: a csv is a source bound by `rows`; a change is what the runner does
when a marker moves (and `url` on its config is told); a file wanted out of
the world is a cell read by whatever writes files.

## Two halves, one of them written once

`hand.py` is the world half: config as a record at `/agent/hands/<name>`
(a person changes it with a write, no restart), where it left off as a
record at `/agent/hands/<name>/seen`, the stream followed with the poll
fallback from `stream.py`, every write signed `who: <name>` (the source
hand signs `source_<artifact>`) and idempotent, `update()` as
write-if-unchanged (the case it read rides with the write), a failure
logged and retried on the next line, never a partial answer. The base also
owns the rule that keeps two hands from ping-ponging: a line from any hand,
or one whose touched paths all sit under `/agent/hands`, never causes a
write by itself, and seen is marked only after a write, or on a tick once
the hand is a hundred lines behind its mark. A mark is an event, and on the
live page it lands on top of what the hand just saw, so an idle hand writes
none.

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

## The source runner

The agent writes the source: a record at `/user/<scope>/sources/<artifact>`
with `where` (a path or a URL), `script` (a module in `hands/sources/`),
`key` when the script wants one, `every` (seconds between passes) for a
source that changes on its own. The hand's config names the folders it
binds: `/agent/hands/source {folders: "/user/finance/sources", url}`. A
pass over an artifact:

1. The script's `marker(source)` against the `marker` slot on the record:
   moved or not.
2. The regions that exist under the artifact, with their `digest` and case.
3. The requests: `read path=<scope> referencing=<artifact>` lists the cells
   waiting at a path under the artifact (`hole: true`); each is a region to
   extract.
4. The skeleton: `skeleton(source)` is every locator the source has, in
   its order, the paths something may point at; `contents(source)`, when
   the script has it, is the part of that written eagerly (the table of
   contents: parts, sections, sheets), each with only `source`; without
   it the whole skeleton is written. A leaf (a paragraph, a footnote) is
   written when something points at it.
5. The content: `regions(source, paths)` for the requested paths, and for
   every existing region when the marker moved (an `eager` script, like
   `rows`, gives every region on first contact). A region whose digest is
   unchanged is skipped; a changed one is rewritten with `if_case`; a path
   the skeleton no longer has is culled.
6. One write of all of it, signed `source_<artifact>`, plus the new marker
   on the record; a pass with nothing to write writes nothing. With `url`
   set, a change is one JSON POST `{artifact, marker, written, culled,
   epoch}`.

A region is the script's slots (the source's own facts at that locator,
in its types, plus the position slots: `row`, `line`, `page`) and the
hand's two: `source`, a reference to the artifact record, and `digest`.
Never prose: a paragraph's region is its position and a digest of its
words (`body`), and what the paragraph states is decomposed beneath it
by whoever reads it; a row's region is its columns, which are facts. No
status, no kind, no interpretation; what is thought about a region is a
view over it. Write-back goes the other way: a `text` slot an agent puts
on a heading's region is written into the file under that heading and
then leaves the world again, so prose lives in the file.

A script is a module in `sources/<name>.py`:

```python
eager = False                         # True: every region's content on first contact
def marker(source): ...               # the version read: mtime and size, a digest, a commit, an etag
def skeleton(source): ...             # [relative path, ...] every locator, in the source's order
def contents(source): ...             # optional: the locators written eagerly (default: all of skeleton)
def regions(source, paths): ...       # {path: slots} for those paths; a path the source lacks maps to None
def write(source, path, slots): ...   # optional: put slots back at that locator, touching nothing else
```

`source` is the artifact record's slots. The script is deterministic: the
same source at the same marker gives the same paths and the same slots,
and a path alone names its region (a request's parameters are its path).
Three ship: `rows` (csv, or a json array of objects; eager; the key
column names the row, `row` is the line), `headings` (markdown or text;
lazy; a heading is a path under the headings above it, `title`, `level`,
`line`, `words` and `body`, the digest of what is under it) and
`numbered_pleading` (a complaint by its sections and numbered paragraphs;
lazy; the sections are the contents, a paragraph is `page`, `words`,
`body`). The skill's
`sources.md` says what the hierarchy, locator and position are for every
other kind; a new kind is a module with those three functions.

## Running one

```bash
python3 extras/mounts/mcp/hands/clock.py http://127.0.0.1:8300 --timezone Europe/Berlin
python3 extras/mounts/mcp/hands/source.py http://127.0.0.1:8300 --folders "/user/finance/sources"
```

`--once` makes one pass and exits. A world kept with `--world DIR` names
the hands it runs in `world.json` (`--hand "clock --timezone UTC"` on the
first boot); the launcher starts each after the foot listens, with its log
at `DIR/hands/<name>.log`, and stops it at teardown. A hand not listed is
not running.

## Config, by hand

- `clock`: `/agent/hands/clock {timezone}`; writes `/clock {day, timezone}` once a day.
- `source`: `/agent/hands/source {folders, url}`; the sources themselves are the agent's records under each folder; writes `who: source_<artifact>`.

A hand that is not running shows as a `/clock` day that is behind, or a
source whose `marker` does not move when the file does. The launcher's `Eden:` line names the hands it started.
