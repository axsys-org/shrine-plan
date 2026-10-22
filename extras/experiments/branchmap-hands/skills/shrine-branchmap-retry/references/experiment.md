# Branchmap reconstruction experiment

Implement a runnable nested prediction-market namespace in Shrine from `inputs/branchmap.pdf` and the seven frozen market observations in `inputs/data/`. Use the paper's semantics where practical and explain departures. Build with the supplied harness and the adjacent `goo-egui` repository. Choose the internal representation yourself.

## Milestone A: namespace and live computation

Represent source markets, outcomes, provenance, and nested claims. Demonstrate that reversing the order of compatible conditions reaches the same canonical claim. Reject incompatible assignments to the same market. Preserve the distinction between marginal observations and an executable joint quote: an unsupported joint price stays unknown.

Make useful market queries and a quote calculation using cells/formulas where they fit. Reference shared facts rather than copying them. Demonstrate live propagation after changing an input, restoration, pinned input behavior, missing-input behavior, and a deliberate formula fault. Record the expectations before running the checks. Explain what the standard formulas support and where new native code is needed.

## Milestone B: participants and interaction

Add local toy-money accounts and positions. Let the user buy and sell supported claims, split a parent into a complete mutually exclusive family, merge the complete family back, and resolve a market. Show balances, positions, and transaction results through Goo using goo-egui. Preserve total money plus backed collateral. Reject overspending, unsupported quotes, invalid quantities, stale actions, and incomplete merges. An exact retry must not execute twice. Treat local participant selection as a simulation identity unless you implement an authority boundary.

Keep market rules, canonicalization, quote calculation, ledger transitions, and presentation inside Shrine. Python may fetch and normalize observations, bootstrap facts, and drive tests. It must not become the live exchange controller. Identify every piece of domain behavior that remains outside Shrine and justify it.

Verify actual frontend action transport, a prepared-view render, and stop/resume of the same kept world. Explain whether derived child paths can be read independently. Separate observed failures from suspected causes and untested behavior. Do not treat a successful graceful restart as proof of crash durability.

## Deliverables and comparison record

Produce source, replay instructions, a runnable inspection path, and a short report of architecture choices and harness feedback. Keep generated runtime state separate from source. Include:

- Harness and goo-egui commit IDs; dirty status; frozen-input SHA-256 hashes.
- Model identifier, reasoning setting, prior exposure, start/end times, and tool-call counts where available.
- Results for each milestone, with concrete expected and observed values and machine-readable receipts.
- External domain-code boundary, formula/cell use, custom native code, and framework modifications.
- Failed attempts and time spent recovering; test assertions grouped by behavior rather than a single inflated count.
- Remaining gaps ranked by their effect on this application.

Assess the run before reading earlier solutions. Compare milestone A to the original namespace experiment and milestone B to the native exchange experiment. The later task is broader; total checks or elapsed time across different scopes do not establish a harness improvement. Fresh live market data can be a separate extension after the frozen-input comparison.
