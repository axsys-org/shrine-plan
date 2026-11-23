# Reaver import verification — 2026-11-23

The application was booted from this repository's canonical `extras/mounts`
using `extras/shuin/run-chat-server.py --test-fixtures`. The provider was a local
deterministic mock; no paid provider or user world was used. The disposable
server and mock were stopped after acceptance completed.

## Passing checks

- System slot catalog: 132 documented slots verified; five catalog tests pass.
- Mount/launcher contracts: 15 pass; the optional native-descriptor check is
  skipped when this Python-only suite is run without `WISP` in its environment.
  Live Eden startup additionally exercised the actual mount descriptors.
- Namespace text: 35 lossless round trips and unsupported executable-value rejection.
- Agent loop: codec round trips, read/write grants, protected controls, provider
  failures, retained inboxes, arrivals during HTTP and pending-grant boundaries.
- Creation stencils: typed interface, care authority, atomic rejection, visible
  messages, stale versions, trusted timestamps and exact-turn retry without duplicates.
- Workbench: all 37 checks pass, including isolated candidates, stale sources,
  dependencies and fixtures, exact multi-record publication, agent admission,
  registration of another target, and an HTTP-held agent crossing publication.
- Search oracle: all 45 checks pass, including prefix semantics, pagination,
  structural contributions, Unicode, rename/delete, app-only scope, edition
  upgrades, replay and system-publication exclusion.
- All 186 focused kernel checks pass: record copies, reverse-reference
  reactivity, source mounts, supervisor, text ordering, bounded previews, value
  reads, view publication, publication and physical projection. The broad run
  additionally passed all 22 idx conformance checks and the Goo suites.
- Grove frontend, backend, actions and stencils pass; reflected-data tests pass.
- Bootstrap/publication documentation passes after updating two assertions for
  the intended fallback titles. Authored documentation still wins; removing it
  restores a readable title and removes stale help.
- The separate native launcher's production, fixture and control-world staging
  were checked against these in-tree mounts. No native Rust changes were required.

## Known baseline failures

The broad kernel gate is not green. The following failures were reproduced with
this same runtime against a clean archive of the pre-import commit `66ff9f52`:

| Suite | Existing failure |
| --- | --- |
| `foil:tests/fs_sync` | Unfinished fixture does not compile. |
| `foil:tests/grove_publication` | `need-fail` in the fixture runner. |
| `foil:tests/lain_fixture` | `need-fail` in the fixture runner. |
| `foil:tests/lain_store` | `need-fail` in the fixture runner. |
| `foil-grove-context-tests` | `need-fail`. |
| `foil-publication-tests` | Bare nullary-brand presentation assertion. |

The broad `native` group also reached its 900-second timeout before completing.
The focused 186-check run completed separately; the timeout is not classified as
a reproduced baseline failure. The full native gate remains unverified.

These fixtures remain enabled and their failures have not been suppressed.
The original documentation-publication failure introduced by fallback titles
was corrected in the assertions and rerun successfully; it is not classified as
an existing failure.

## Reproduction and limits

From the Reaver root, with a supported `WISP` executable:

```sh
x/check native namespace-publication-tests foil-grove-tests \
  foil-grove-backend-tests foil-grove-action-tests foil-grove-stencil-tests \
  reflected-data-tests --jobs 2 --timeout 900
WISP=/path/to/wisp python3 x/test_runner.py foil-bootstrap-tests
python3 x/eden-mounts-test.py
python3 extras/shuin/check-search-index.py --wisp /path/to/wisp \
  --output /tmp/shuin-search.json
```

See [README.md](README.md#disposable-verification) for the live acceptance commands.
The fresh import checks used the previously tested PGO/SLJIT runtime with the
separate Enki GC headroom patch. That runtime change and its binary are not in
this PR, and these results do not claim a fresh run on Reaver's stock runtime.
Runtime SHA-256: `7ee6e2190e01f8cb62880535480bd7243ef0dd3bf43b83e0bddc1b18b8d1c1cd`.

No native widget/IME tests or 10,000-path latency benchmark were rerun for this
source relocation. The consensus setup remains operator-supervised; this import
does not introduce a persistent consensus coordinator or saved-world migration.
