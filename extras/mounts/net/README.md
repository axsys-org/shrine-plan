# net: networked names

The generic substrate for one world observing another's published names. It knows
publishers, names, revisions and whether a judgment has fallen behind a revision.
It knows nothing about any business.

## Records

```
/<self>/net/names/<publisher>/<name>/current   written only by the shrine-mesa sidecar: the viewed slots of
                                                the acquired revision, plus remote_case, publisher, source (name@case)
/<self>/net/names/<publisher>/<name>/seen      written by whoever judged against a revision: remote_case is the
                                                revision the judgment relied on
/<self>/net/stale                               a cell over the whole names subtree (z care); never stored
```

`<publisher>` is the publisher's node id (a hex segment such as `0x11`); `<name>` is one path
segment the publisher chose. The acquired revision is source-attributed, not verified: the
remote epoch and case are recorded, and until Mesa and Groundwire the signature is the
sidecar's to check.

## Publications (phase 1)

What a world exposes is a record under its own root, written by the owner or an agent on the
owner's behalf, never by the sidecar:

```
/<self>/net/publications/<name>   one name this world exposes; <name> is one lowercase segment
   path    required, text         the local path whose revisions are exposed, e.g. /0x11/pub/aluminum
   to      required, text         "public", or the node id of one peer such as 0x12
   slots   optional, text         the slot names to expose, space-separated; absent means every slot
   note    optional, text
```

The sidecar lists `/<self>/net/publications` (care `y`), reads each child, and watches the record
at `path`: every new case is bound under the Mesa name `<name>@<case>` and announced to the peers
`to` names (every configured peer for `public`). Nothing not listed here is ever bound. Visibility
at this libmesa commit is traffic policy, not authentication: every bind is `Access::Public`, and
`to` decides only who is told.

The role's contract is judged on every update: a poke or remake that leaves a publication without
`path` or `to`, or with either not text, is refused (`curb_need`, `curb_type`). The first write of a
record under the tree is not judged: the tree stamps the contract onto the record in that same write,
and the kernel treats a new contract as adopted over the record it arrives with (`guard_diffs` in
`lain_poke.foil`). The sidecar therefore skips a publication that lacks `path` or `to` and says so in
its log; the next complete poke makes it a publication.

On the acquiring side `/net/names/<publisher>/<name>/current` is written once per acquired
revision: a sidecar that restarts, or a notice delivered twice, compares `remote_case` with what
the world already holds and writes nothing for a revision already acquired.

## Reading the overlay

Over MCP, with the node spelled: `mcp/read path=/x/<self>/net/stale care=y`. Each child is
`/<publisher>/<name>` with `current` (the acquired revision), `seen` (the judged one),
`publisher` and `name`. A name with no `seen` was never judged and is not listed; a name
whose `seen` equals `current` is not listed. `/c/x/<self>/net/stale` shows the cell's context,
including `/sys/tack/case`, the input subtree's current case.

## Why the cell is written from activation

A Grove `@tree` seed accepts only a y-care tack, and the names subtree is three deep. The
`@sewn` declaration `stale` is published with the Grove template at `/<self>/gov/net/stale`;
`activation.foil` instantiates the template at `/<self>/net` and then writes the cell record
`{sys/weft: (safe 1 .x /gov/net/stale), sys/tack: (safe 0 .z /net/names)}` through
`grove_install/change`.

## Running it

```
python3 x/eden --node 0x12 --mount net --mount mcp --mount probe --port 8302 --world <dir>
```

`mount.json` depends on `codecs` for the Grove `text` type.

## Phase 0, measured (2026-11-02)

`demo/phase0.py` boots two worlds from this checkout (A `0x11` with `mcp probe`, B `0x12` with
`net mcp probe`), starts the shrine-mesa publisher beside A and the reader beside B
(`/Users/ianchanner/shrine-mesa`, commit 462745f, libmesa 2e94a13), and asserts the loop:

| what | measured |
|---|---|
| A's revision acquired in B (flow notice, signed named read, world write) | 0.16 s (revision 1), 0.11 s (revision 2) |
| `/x/0x12/net/stale` listing the name after A's next revision | 0.14 s after the write in A |
| `kill -9` of B's runtime, restart, overlay unchanged | 2.6 s |
| re-judging at the new case | the overlay empties |
| runtime footprint after the run | A 69 MB, B 197 MB |

What is real: the acquisition is a publisher-signed Mesa read verified by the reader's engine, the
notice a durable flow with receipts, the overlay a kernel lens over records, persistence the
world's own. What is not yet: the bind is `Access::Public` (libmesa's signed-public profile refuses
any other access at this commit), there is no requester authentication or encryption, the sockets
are loopback, and the publisher keys are local seed files.

## Phase 1, measured (2026-11-03)

`demo/phase1.py` boots A (`0x11`) and B (`0x12`), both with `net mcp probe`, writes A's publication
`{path: /0x11/pub/aluminum, to: 0x12}`, starts one `shrine-mesa serve` beside each world
(`/Users/ianchanner/shrine-mesa` eb7918e, libmesa 2e94a13), writes 500 revisions at about twenty a
second while killing with `-9`, at random, each world's runtime and each service five times (a service
stays down for three revisions and restarts from its state directory; a world is rebooted at once), and
compares B's acquired history with A's through pinned reads of both records.

| what | measured |
|---|---|
| A's 500 cases in B | 500, none lost, none duplicated, in order, every slot matching |
| the run, first write to last, with the twenty kills | 48.5 s; 5.8 s more to drain after the last write |
| revision 1 in B, counted from the services' start | 0.22 s |
| named reads on B, signature and every LSS leaf verified (502 reads across 6 lives) | 12.6 ms on average, 5.0 ms at best |
| stalled announcements or reads, across 6 lives of each service | 0 |
| notices delivered again after a kill between the world write and the delivery commit | 4, each recognised and not written |
| world restart after `kill -9` | 1.6 to 3.6 s |
| first boot; footprint after the run | 41 s and 88 s; 100 MB and 240 MB RSS |

The first run against the service's first commit (609c14a) did not pass: the publisher bound every
case in order but announced about four at a time, waited for them to settle, and slept a second on
every stalled announcement, so B lagged hundreds of cases behind. eb7918e moved the world calls off
the service loop, widened the flow window to 32 with look-ahead binds, and rearms a stall after 50 ms;
the run above is the fixed service. What the service holds after 500 revisions is one binding and one
fence per publication (`RetireBefore` after the peer settles), and a store rotated to a new flow
generation every 40 rows, since `mesa-store` frees nothing below its 16,384-row cap.
