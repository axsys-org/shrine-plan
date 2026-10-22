# Combined-branch validation, 2026-10-22

The application and quote graph ran on `ic-hands` rebased onto `lf/goo-contracts`. The manifest pins the source revisions and hashes the tested probe and harness sources. No core fixes were applied.

| Check | Observed result | Receipt |
| --- | --- | --- |
| MCP product suite | 150 checks; 443 round trips; event budget held | `product-tests.log` |
| Native Foil domain suite | 42 passed | `native-checks.json` |
| Real Goo actions | Buy/sell, exact retry, stale/refused operations, nested split/settlement, account creation and projections passed | `live-check.json` |
| goo-egui library | Prepared view accepted at widths 480/900/1200 | `egui-tests.log` |
| Hand integration | 23 checks; zero events in 60 idle seconds | `hands-tests.log` |
| Quote graph | 24 assertions passed, including repeated checks after restoration | `quotes/checks.json`, `quotes/calls.jsonl` |
| Graceful stop/resume | Eight quote checks plus four state/history comparisons passed after restart | `lifecycle/after/checks.json`, before/after snapshots |
| Stock ask suite | Failed: expected one answer, received zero on an accumulated world | `ask-tests.log` |
| Isolated fake ask probe | Initial answer/update passed; catch-up and restart rediscovery failed; manual rediscovery restored answering | `ask-probe.json` |

Two additional compatibility checks passed before the runtime checks: Explorer's `goo-live.test.cjs` ran 30 tests; `x/eden-mounts-test.py` ran 17 tests with one skip. Their output is in the task transcript, not these receipt files. Browser inspection showed the live quote cell list and event history. The goo-egui check exercised the actual Rust consumer but did not perform a new desktop click-through.

The hand integration test instantiates the hand classes directly, uses a localhost notification sink, and exercises file import/export. The model probe uses a fake responder. Managed-process supervision, external notification delivery, and real inference were not tested.

The initial quote attempt calculated the correct amounts but stopped when the Python driver treated an expected conditional-write refusal as an unexpected MCP error. `initial-quote-attempt.jsonl` preserves that attempt and its cold timings. The driver was corrected to admit an explicitly expected refusal. A later test-only cleanup also hit `tombstoned_ancestor` when recreating children under a culled QA root; the final seeder explicitly creates that root. The final full replay passed. These were probe corrections, not core harness fixes.

The fake-hand probe initially saved a mutable discovery dictionary that its later manual-repair step changed. The final probe copies that dictionary before repair and was rerun; `ask-probe.json` therefore records the empty registry at the actual failure point.

The first quote read took 29.248 seconds. Warm corrected-probe calls were all below 0.5 seconds. A five-second unrelated health request timed out during the first evaluation. These observations came from a mixed workload and do not establish a performance benchmark or root cause.

The same kept world was stopped with SIGTERM to the Eden launcher and resumed through `start.sh`; no world files were restored or reseeded between the lifecycle snapshots. This tests normal shutdown/restart, not an interrupted write, power failure, snapshot migration, or recovery after source replacement.

The retry skill passed its validator. Its preparation script exported a new application-free directory, checked all ten input hashes, and rejected an occupied destination and a revision containing a previous application. No new Astra construction run was launched.
