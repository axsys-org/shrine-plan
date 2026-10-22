# Branchmap on ic-hands and goo-contracts

This branch combines the latest fetched harness and Goo work, retains the native exchange, and adds a formula-only quote experiment plus a repeatable fresh-run skill. No core harness patch is included.

| Layer | Revision |
| --- | --- |
| Fetched `ic-hands` | `7c5f96aff558dde2cf7a7219cc7ec40ff487e195` |
| Fetched `lf/goo-contracts` | `b192de7418da44a6d66e0f97db2f8f652c931d6d` |
| Harness after rebasing its 35 commits | `aae7cfa49ada19d066905d9e9e88347bc4064bde` |
| Original experiment copied onto combined base | `91b82572` |
| Native exchange copied onto combined base | `82bf21bd` |
| goo-egui used for validation | `c7054a5ae94f2747e050fe4e7679a3bd12e6da30` |

The working branch is `codex/ic-hands-goo`. The rebase applied cleanly. The shared `ic-hands` and `lf/goo-contracts` branches were not rewritten. The existing `cyc/cell-experiments` checkout and its untracked editor files were preserved.

## Run and inspect

On macOS with Nix and Xcode Command Line Tools, run from the repository root:

```sh
extras/experiments/branchmap-hands/start.sh
```

This starts MCP, probe, Branchmap, and Explorer at `http://127.0.0.1:8192`. It keeps the world at `extras/experiments/branchmap-hands/run/world`. Stop with Ctrl-C and invoke the same command to resume. `BRANCHMAP_PORT` and `BRANCHMAP_WORLD` select a different port and new world directory; a kept world's saved configuration must match. The launcher uses the existing macOS loopback adapter and starts no background hands.

In another terminal, seed and check the quotes once:

```sh
python3 extras/experiments/branchmap-hands/quotes.py
```

The script refuses an existing quote namespace. For later checks, including after restart, use `--verify`. Open [the live quote graph](http://127.0.0.1:8192/live?views=/0x11/user/branchmap_quotes/views). The live page shows twelve view cells, their row counts, and the author-tagged change history. The native exchange remains available through the ordinary goo-egui prepared view:

```sh
GOO_SERVER=http://127.0.0.1:8192 GOO_EGUI_ROOT=/path/to/goo-egui \
  extras/mounts/branchmap/client.sh
```

Follow the [native exchange instructions](../../mounts/branchmap/README.md) for toy trades. The combined launcher replaces that document's original disposable-launcher limitation.

## What the quote graph computes

The experiment imports one frozen observation, prices ten shares at 140,000 millionths each, and derives a cost of 1,400,000 and remaining cash of 98,600,000. Python supplies facts, configuration and assertions. The live computation runs in Shrine.

Requests reference offers and accounts. Two `follow` cells bring those records into each request; four `rename` cells expose their nested slots to the expression parser. Two `each` cells calculate cost and remaining cash. `where` selects eligible requests, `validate` returns failures, and `select` exposes the amounts. A separate `diff` cell compares the eligible amounts with expectations written before evaluation. A twelfth view cell tests a pinned secondary input.

Six request cases cover a valid quote, insufficient inventory, insufficient cash, zero quantity, fractional quantity, and a conjunction with no observed price. Only the valid request qualifies. The conjunction produces a diagnostic hole and no invented cost. An offer update changes the cost to 2,000,000; restoring its prior source version restores the quote. A stale `if_case` refuses an entire two-record batch. An explicitly pinned offer table keeps its old price. Division by zero returns a formula fault without making the world unavailable.

These accounts and offers are an isolated quote-design fixture. They are not a mirror of the native exchange ledger, and this graph does not execute orders or appear in the exchange's transaction form. Connecting a displayed quote to trade admission still requires a native action to revalidate the quote's dependencies before committing the ledger transition. The native exchange already revalidates its own aggregate book through Goo.

## Validation and feedback

[FEEDBACK.md](FEEDBACK.md) distinguishes improvements, reproduced failures, and proposed work. [evidence/2026-10-22](evidence/2026-10-22/README.md) contains the measured results. `ask_probe.py` reproduces the hand backlog/restart findings with a local fake model; its JSON records failed properties even though the reproducer completes successfully. No real inference or external notification was sent.

To repeat the native checks and real action transport on a fresh test world:

```sh
nix --extra-experimental-features 'nix-command flakes' develop \
  --no-update-lock-file path:.#eden --command python3 extras/mounts/branchmap/check.py
python3 extras/mounts/branchmap/check_live.py --server http://127.0.0.1:8192 --disposable
GOO_SERVER=http://127.0.0.1:8192 GOO_EGUI_ROOT=/path/to/goo-egui \
  extras/mounts/branchmap/check_egui.sh
```

The live action test changes balances and resolves markets. Run it only on a fresh test world. For stop/resume evidence, run `lifecycle.py before`, stop and resume the same world, then run `lifecycle.py after`. That checker expects the quote fixture and the live action test's Carol account.

## Retry from scratch

[RETRY.md](RETRY.md) contains the copyable new-chat prompt. The reusable [skill](skills/shrine-branchmap-retry/SKILL.md) is also installed locally as `$shrine-branchmap-retry`. Its preparation script exports the harness-only revision, the paper, and ten frozen input files into a new directory. It excludes both previous applications and their reports. The brief separates namespace/query construction from the broader accounts/trading/UI task so comparisons preserve scope.
