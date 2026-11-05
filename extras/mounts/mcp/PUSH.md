# The commit push: subscribing to a world instead of tailing its history

A world tells its subscribers about every commit as it commits. Nothing outside a world (the host, a gateway, a hand,
an orchestrator) needs to read `mcp/history after <epoch>` in a loop to learn what changed: hold one stream per world
and act on its events.

## The stream

`GET /mcp/stream` on the world's URL (the same port as `/mcp`, local only, no credential) answers
`200 text/event-stream` and stays open. Each commit, from any writer (an MCP write or apply, a page, the probe, the net
mount, the filesystem foot, a reaction round), is one event:

```
id: 1742
data: {"epoch":1742,"who":"gateway","touched":["/0x11/relationships/0x22/inquiry", ...],"touched_count":4,"woke":["/0x11/judgments/0x22"],"woke_count":1}

```

- `epoch`: the commit's epoch, also the event id. Epochs only grow; each appears once.
- `who`: the writer's tag (`who` on `mcp/write`; `world` for an untagged write under /user or /agent from another
  mount, `system` for boot and system folders), the same as `mcp/history` reports.
- `touched`: the paths the commit's diff touched (the records written, the kernel's ancestor bumps, the writer's
  journal tag), the first hundred; `touched_count` is all of them. When `touched_count` is larger, read that one epoch
  with `mcp/history` (`after: epoch - 1, limit: 1`).
- `woke`: the cells (records with a `/sys/weft`) this commit woke: every cell it wrote, every cell holding a reference
  that reads a name it changed (care x: the record; y: the record and its children; z: anything beneath; a cull reaches
  every reference beneath it), and the cells reading those cells' `/x`, to the end of the chain. Found through the
  reverse index (`reference_index/readers`, `cell_wakes` in `lain_peek`), never by scanning. First hundred, and
  `woke_count`.
- A presented read (`mcp/read` with `present: true`) is a `data: {"shown": {path, care, case}}` event with no id; it
  journals nothing.

Comments (lines starting `:`) carry no event: `: open` after the head, and `: at <epoch>` once on a live open.

## Subscribing without missing anything

- **First connect** (nothing seen yet): `GET /mcp/stream`. The first thing after the head is `: at <top>`: the epoch the
  stream starts after. Persist it as your resume point before you act on anything else.
- **Every event**: act on it, then persist its `epoch` as your resume point.
- **Reconnect** (socket closed, world restarted, host restarted): `GET /mcp/stream?after=<resume point>`. The world first
  replays every commit after that epoch from its journal, 64 epochs per read, then continues live. No gap, no repeat:
  each connection renders from its own last-sent epoch, so a live commit during the replay is sent after it, once.
- A subscriber that is slow never falls behind or gets dropped for lag: commits that arrive while it is busy coalesce
  into one catch-up from the journal. Only a closed socket drops a stream.
- Retrying the connection while a world is down is the only wait; between commits the socket is silent. There is no
  heartbeat (that would be a timer); set TCP keepalive on the client socket if a middlebox needs traffic.

`hands/stream.py` is a complete client (`Stream(base, after)`, `Stream.opened_at()`, `follow(base, seen)`), about
eighty lines with no dependencies.

## What the host does with it (replacing the history tail)

Today the host calls `mcp/history after <epoch>` per world on a timer to find approvals, wakes, new requests and
changed `on` paths, and the wake bridge re-checks cell contexts once per poll. Instead:

1. Per world, one thread or task: `follow(base, seen=<persisted resume point>)` (or the same logic in Rust: one
   socket, parse `id:`/`data:` blocks, reconnect with `?after=`).
2. For each event, match `touched` against the paths the host watches (approvals, `/outreach`, `/answers`, requests,
   the `on` paths of a relationship). A match is the moment to read that record (one `mcp/read`), exactly as the
   history tail did with the paths it found. `who` lets the host skip its own writes.
3. For the wake bridge: `woke` names the cells whose inputs changed. Check the context (`/c/x<cell>`) of those cells
   only, and only when the commit woke them; a commit elsewhere costs nothing. A cell a commit wrote is in `woke` too
   (its prompt, input or model may have moved).
4. Persist the epoch after handling each event; on restart, resume with `?after=`.

Measured on the box (one light world, mcp and probe, `extras/mounts/mcp/tests/push.py`, two runs):

| what | time |
|---|---|
| a write's HTTP ack to its event at the subscriber | median 2.2-2.3 ms, max 4.8-29.5 ms |
| sending a write to its event (the write itself is most of it) | median 27.6-28.6 ms, p95 36.9-52.6 ms |
| a probe-mount write (not MCP) to its event | 20-21 ms |
| reconnect with `?after=` to its first replayed event, sixty writes running | 25-27 ms; 70 epochs replayed in order, once each |
| a write under an ask's input to the ask hand's answer written (fake model) | 109-115 ms |
| world restart, then `?after=` | 3.2 s to serve; the epochs before the kill replay |

`woke` was exact in the test: a write under `a` woke the count over `a` and the pick over that count, never the count
over `b`; a write nobody reads woke nothing; a write two levels under `a` woke the y-reader of `a` (the kernel bumps
each ancestor, so the depth-1 bump is in the diff); a cull of `a` woke its readers.

## The ask hand

`hands/ask.py` runs this way now: it finds every ask cell through the reverse index (the holders of a `/sys/weft`
reference to the stdlib ask, at `/r/<len>/<node>/weft/stdlib/ask`), answers the ones asking, then follows the stream and
reads a context only for the cells an event woke. It keeps no place in the log; on restart it finds what is asking
again.

## Where it lives

- `src/foil/helm.foil`: a foot registered with `hears` is told `feet/task/committed top` by the supervisor after every
  commit (after the bindings, before the reply). Eden registers the HTTP foot so.
- `src/foil/http_foot.foil`: the stream action (`after`, a per-epoch `line`), the coalescing fan-out, the per-connection
  catch-up (`page`, `catch_up`, `streaming`).
- `extras/mounts/mcp/mcp_mount.foil`: `GET /mcp/stream?after=`, `mcp_mount/notice` (the event for one epoch).
- `src/foil/reference_index.foil` `readers`, `src/foil/lain_peek.foil` `cell_wakes`: what a commit woke.

## Limits

- The journal records no wall time for a commit (`now` is 0 on card writes), so events carry no time; stamp receipt.
- Worlds booted from an older kernel (the pilot's `ic-base` worlds) have no `?after=` and push only MCP writes; they
  need the new kernel before the host can drop the tail.
- The filesystem foot still samples the source tree on a one-second timer (that is outside the world; inotify would
  replace it).
