# Branchmap: a native Shrine exchange

Branchmap runs its market rules, accounts, positions, collateral, settlement,
and presentation inside Shrine. Grove declares the application and Goo prepares
its interface for the `goo-egui` desktop client. Python imports the public
snapshot and drives tests; no Python process executes trades.

This mount was first built on `lf/goo-contracts` at `1c3e3e6c`. It now also runs on
the combined `ic-hands` and updated `lf/goo-contracts` branch. Use the
[combined launcher and feedback](../../experiments/branchmap-hands/README.md)
for MCP cells and kept-world restart. The first MCP experiment is archived under
[extras/experiments/branchmap](../../experiments/branchmap/README.md).
That experiment's Python controller and MCP cell library are not dependencies of
this application. Combining the branches adds the MCP authoring surface without
changing the native ledger representation.

## Run

Prerequisites: macOS, Nix on PATH, Xcode Command Line Tools, and the adjacent
[goo-egui repository](https://github.com/axsys-org/goo-egui). The frontend was
integrated against `c7054a5ae94f2747e050fe4e7679a3bd12e6da30`. Mash is fetched from
the public repository at the exact revision pinned by `extras/flake.lock`.

From the Shrine repository root:

```sh
extras/mounts/branchmap/start.sh
```

Wait for Eden's readiness message. The default port is 8190; set
`BRANCHMAP_PORT` to use another free port. The process-local macOS bind adapter
restricts that listener to loopback. Confirm with `lsof -nP -iTCP:8190 -sTCP:LISTEN`.
The launcher does not change firewall settings or existing worlds.

In another terminal:

```sh
extras/mounts/branchmap/client.sh
```

When Shrine is in a Git worktree, set `GOO_EGUI_ROOT` to the actual goo-egui
checkout. Set `GOO_SERVER` if using another port. The script launches the client's
ordinary prepared-view mode at `/0x11/app/branchmap/exchange`.

For the native namespace inspector, run from goo-egui:

```sh
GOO_SERVER=http://127.0.0.1:8190 GOO_PATH=/0x11/app/branchmap \
  ./scripts/cargo-macos.sh run -- --explorer
```

The server also exposes its existing browser Explorer. No application-specific
JavaScript handles transactions.

**This mount's original launcher creates a fresh world each time.** Transactions
remain in that running namespace and journal. The
[combined launcher](../../experiments/branchmap-hands/start.sh) uses Eden's new
kept-world mode to preserve them across stop/resume. These launchers have
different lifecycle behavior; neither establishes production wallet durability.

## Try a transaction

Alice and Bob start with 100 TOY each. The house starts with 10,000 TOY, then locks
700 as collateral for 100 complete outcome sets in each of the seven markets.
Cash uses integer millionths; quantities use whole shares. Every winning share
redeems for 1 TOY.

The transaction form has six fields. Market and outcome numbers start at zero.
The market list shows outcomes and their fixed local prices in the same order.

| Operation | Participant | Market | Outcome | Quantity | Parent conditions |
| --- | --- | --- | --- | --- | --- |
| Buy ten YES shares | alice | 0 | 0 | 10 | empty |
| Sell those shares | alice | 0 | 0 | 10 | empty |
| Split ten TOY into a complete family | alice | 0 | 0 | 10 | empty |
| Split the YES parent again on Bitcoin | alice | 2 | 0 | 10 | `0:0` |
| Merge the Bitcoin siblings back | alice | 2 | 0 | 10 | `0:0` |
| Merge the original family back to cash | alice | 0 | 0 | 10 | empty |
| Create Carol with a house-funded grant | carol | 0 | 0 | 0 | empty |
| Resolve market 0 to YES | operator | 0 | 0 | 0 | empty |

Enter operation names `buy`, `sell`, `split`, `merge`, `open-account`, or `resolve`.
The Outcome field is used only by buy, sell, and resolve. Split and merge always
use every outcome of the chosen market. Quantity is ignored for open-account and
resolve. The form rereads accepted state through Goo; rejected actions keep the
previous state. Prices do not move with trades. A purchase consumes the house's
backed inventory and transfers cash; it cannot mint an unbacked claim.

All seven markets are explicitly reopened as **local simulation scenarios** from
the October 16 observation snapshot. Local resolution is independent of venue
resolution or current dates. Full source specifications, URLs, fetch times, and
hashes remain in each market's provenance. A source observation is not an
executable venue quote. No funds or orders leave the local world.

The account selector is a local participant identity, not authentication.
`operator` marks a simulated resolution action, not a privileged credential.
Any local client with access to the world can operate it.

## Native architecture

| File | Responsibility |
| --- | --- |
| [domain.foil](domain.foil) | Typed book, canonical assignments, asset identity, ledger transitions, projections and display text |
| [main.grove](main.grove) | Book type, exchange role, domain action, prepared view, sewn projections, installed records |
| [sample.foil](sample.foil) | Generated public observation literals; native initial-book constructor |
| [import_snapshot.py](import_snapshot.py) | Verify raw hashes and generate observation literals; no trading logic |
| [mount.foil](mount.foil) | Install the Grove template |
| [test_branchmap.foil](test_branchmap.foil) | Executable Foil domain regressions |
| [check.py](check.py) | Run those regressions through the real compiler/runtime |

`/0x11/app/branchmap/exchange` owns a typed `branchmap/book`. The book contains
accounts, markets, positions, collateral and append-only accepted-operation
receipts. One Grove domain action computes the complete next book and its display
fields. Goo's expected-version admission protects that replacement. Two requests
based on one old book cannot both spend its cash. Exact invocation retries use
the Goo operation receipt rather than executing the transition again.

The book deliberately uses one aggregate transaction boundary. Ordinary Grove
actions transform one receiver; treating independently edited account records as
a transaction would require additional coordination. This choice serializes the
whole exchange, including unrelated participants. It is suitable for a bounded
local experiment, not a high-volume exchange.

Five `@sewn` declarations project the book into namespace collection reads:

- `/x/0x11/app/branchmap/accounts`: names and integer cash balances.
- `/x/0x11/app/branchmap/positions`: owners, quantities, canonical conditions and asset identities.
- `/x/0x11/app/branchmap/markets`: source IDs, full provenance and local resolution.
- `/x/0x11/app/branchmap/verses`: canonical held conditions, TOP and explicit pricing status.
- `/x/0x11/app/branchmap/receipts`: accepted operations and their sequence numbers.

These trees are derived read models, not a second ledger. Their numeric child
paths are row ordinals and can change after a transaction. On this base, `/x`
returns the collection tree but does not resolve its child paths as standalone
objects. Use the collection read for structure and the exchange view for balances
and positions; clicking a derived child in the inspector returns unavailable.
The source ID,
participant name and asset ID carry identity. Use the exchange action to write.

A verse is a sorted, deduplicated assignment set. Each assignment identifies a
market in this fixed snapshot and one of its outcomes. Opposite outcomes for one
market are refused. Asset identities serialize the canonical set with the stable
source market IDs and the fixed root currency `TOY`; they are not hashes or EVM
identifiers. Outcome ordinals are pinned to this snapshot. Replacing the snapshot
under existing holdings requires a migration, not rerunning the importer.

Splitting TOP locks cash; splitting a conditional parent consumes that position.
Both operations issue every mutually exclusive child. Merging consumes equal
quantities from the complete family and restores the parent. Resolution consumes
losers, removes satisfied assignments, combines identical residual holdings, and
redeems unconditional winners from collateral. It checks that total cash plus
locked collateral still equals the fixed supply. New-account grants transfer
cash from the house rather than increasing that supply.

Joint claims have no executable quote. The application never multiplies marginal
prices to price a conjunction. Split and merge remain available without a quote.
This implements conjunction claims; it does not define a conditional-bet contract
that refunds when its conditioning event fails.

## Boundaries found on the original base

These findings describe the first native implementation. The
[combined-branch report](../../experiments/branchmap-hands/FEEDBACK.md) records
current checks and distinguishes resolved gaps from findings not retested.

- The original base did not contain the MCP standard-cell mount. Native Grove
  `@sewn` projections replace those demonstration queries.
- A single-receiver Grove action provides a clear atomic boundary. A normalized,
  independently writable multi-record ledger needs a broader domain transaction
  mechanism and explicit dependency/version admission.
- The generic local namespace/editor interface is not an ownership boundary.
  Application actions enforce these rules, but a privileged raw record edit can
  replace the book or its cached display fields. There is no wallet authority.
- The namespace stores typed structures directly. Canonical structural identity
  removes the need for an external SHA-256 controller; matching the paper's
  Keccak/ABI IDs would be a separate compatibility task.
- The egui contract supports prepared ordinary inputs and actions. This interface
  uses that common subset: six labeled fields and one submit action. Dropdown
  market selection, a live quote preview and a participant-specific portfolio
  layout remain interface work, not external domain logic.
- The `/x` resolver treats the entire path after `/x` as the defining datum.
  It lists generated children but cannot read those child paths individually.
  This limits ordinary inspector navigation of sewn output trees.
- Live Grove rescan followed by instance replacement reproduces
  `sewn_norm_failed`: the new projection rejects its input role, even when the
  source is unchanged. The source request times out and subsequent requests
  stop responding in that world. Fresh startup passes the full lifecycle.
  Treat live replacement as unsupported for this mount pending a framework
  fix; restart the disposable world after source changes. No core workaround
  or diagnostic compiler changes are included in this branch.
- Text preparation is bounded to ASCII by the current frontend contract. The
  importer transliterates display labels to ASCII, escapes provenance text, and
  retains the exact original snapshot.
- Wisp's listener takes a port without a bind address. A process-local macOS
  adapter supplies loopback confinement; it does not implement domain logic.
- The original launcher used disposable Eden startup. The combined launcher
  exercises the new kept-world mode; crash recovery remains untested.
- Fixed quotes and finite house inventory are a toy execution policy. There is
  no order book, AMM, external oracle, fee model, or arbitrary cross-market
  consistency proof. The receipt row grows with the session; no compaction exists.

## Validation

Run native domain checks from the repository root:

```sh
nix --extra-experimental-features 'nix-command flakes' develop \
  --no-update-lock-file .#eden --command python3 extras/mounts/branchmap/check.py
```

The tests execute Foil, not a Python reimplementation. They cover canonicalization,
account funding, inventory/cash transfers, complete-family splitting/merging,
nested normalization, four-outcome markets, winner/loser redemption, conservation,
closed markets, invalid conditions and quantities, and namespace projections.

The original controller and evidence remain historical references. Their passing
results do not stand in for native domain tests or Goo action integration tests.

After starting a fresh disposable world, exercise the actual Goo transport:

```sh
python3 extras/mounts/branchmap/check_live.py --disposable
GOO_EGUI_ROOT=/path/to/goo-egui extras/mounts/branchmap/check_egui.sh
```

The first command changes that world's accounts and resolves two markets. It
checks exact retries, stale submissions, refused transactions, nested settlement,
and derived collection refresh. The second compiles a small read-only harness
against the actual goo-egui library and validates the prepared view at three
widths. Test outputs and local binaries go into ignored `run/`.

Measured results and action responses are in [the validation receipt](evidence/2026-10-22/README.md). The desktop purchase check showed Alice holding ten shares after paying 1.4 TOY.
