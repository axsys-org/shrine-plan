# Validation receipt: 2026-10-22

The application runs on Shrine base `1c3e3e6c` and goo-egui
`c7054a5ae94f2747e050fe4e7679a3bd12e6da30`. The native tests execute the real
Foil compiler and runtime. The live tests use a fresh disposable Eden world and
an unmodified Shrine core.

- `native-checks.json`: 42 passing native checks and hashes of tested modules.
- `live-check.json`: real action responses, five refreshed namespace collections,
  and the final prepared view after trading and settlement.
- `egui-check.txt`: the actual goo-egui library accepts the view at three widths.
- `source-sha256.json`: application source identities for this run.

A desktop check entered `buy`, `alice`, market `0`, outcome `0`, and quantity
`10`, then clicked Submit transaction. The client reread 98.600000 TOY for Alice,
10 shares of `0:0`, and an accepted transaction receipt. No external money or
venue order was involved. Presentation was also inspected after fixing newline
separators and ASCII display labels.

## Framework limitations reproduced

The collection request `GET /goo/source?target=/x/0x11/app/branchmap/accounts&axis=z`
returns three initial members. A prepared render request for the listed child
`/x/0x11/app/branchmap/accounts/1` returns `Object is unavailable.` The resolver
treats that entire child path as a defining datum instead of dipping into its
parent's generated tree.

Live source replacement fails separately. Starting from a working world:

1. Read `/grove/dev/status` for source `/0x11/gov/branchmap` and root
   `/0x11/app/branchmap`.
2. POST `/grove/dev/rescan` with that source, root, and the returned requested
   scan number. Wait until requested and completed match.
3. POST `/grove/dev/replace` with source, root, the new template version,
   the root's expected version, and the completed scan number.
4. Read the accounts collection again.

The replacement reports installed version 2, but the collection read logs
`sewn_norm_failed` and times out. Temporary diagnostic instrumentation narrowed
this to the sewn input-role check; that instrumentation is excluded from the
branch. The exact compiler/publication identity defect remains unisolated.
The supported path is a fresh startup after source changes. Replacing the
instance from the *same* publication, without a rescan, resets the disposable
world and leaves its projections working.

Fresh startup, normal account mutations, and the full action regression pass.
These results do not establish authentication, durable restart, AMM behavior,
external oracle correctness, or safe concurrent raw namespace editing.
