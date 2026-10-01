# Panes verification and rehearsal

Verified September 30, 2026. API, implementation map, source spellings and limits
are in [PANES.md](PANES.md). The runnable fixture is
[`../panes/panes.grove`](../panes/panes.grove).

## Automated results

Commands executed from the repository root:

```sh
node --test extras/mounts/explorer/tests/*.test.cjs
WISP=/nix/store/x42s38g8973a3lzjk3qw7dyyd2hlnca1-enki-pgo-0.1.0/bin/wisp \
  python3 extras/x/check --mount panes --jobs 2
git diff --check
```

- JavaScript: **19 passed, zero failures/skips**, 52.7 ms on the final run.
- Foil/mount regressions: **428 passing checks**: web 135 (53.5 s), mount
  contracts 1 (60.9 s), explorer 292 (71.1 s). Group timings overlap with two jobs.
- Whitespace validation: clean.

The Foil run covers the final compiler/runtime code, including invalid creation
seed diagnostics and server validation of the published lexical capture source.
The fixture was also republished and reinstalled through the real development
panel after separating its study record from the installer. The final JavaScript run
includes batched retirement notifications and retained keyed deck controls.

| Acceptance cases | Evidence |
| --- | --- |
| S01, S13 | Real Grove parse/lower, retained constructors, missing keys and invalid seed; source/member compatibility in runtime and Foil tests. |
| S02, S03, S05, S07, S14 | Actual row listeners plus browser selection/clear, independent workspaces, keyboard focus and reusable row controls. Local gestures showed zero action activations/dispatches. |
| S04, S06, S08–S11 | Deterministic session tests: creation-only seed, consumer-independent ownership, duplicate memberships/reorder, missing projection versus deletion, fresh incarnations and encounter continuity. |
| S12, S15 | Browser recipe changes and retained editor; deferred adapter tests reject obsolete subject/recipe output and late recipe guards. |
| S16–S19 | Real text-input departure prompt in browser; deterministic guard failures, supersession, multiple followers and old-intent retry tests. |
| S20–S22 | Keyed composition/lifetime and deck resource tests; actual deck adapter preserves tab nodes across reorder. Browser rehearsed deck suspension. Overlap layering is the CSS declaration-order contract, not a browser-tested modal/history system. |
| S23, S24 | Frozen accepted-selection capture and retry tests; Foil validates lifetime, data version, lexical source and invocation payload identity; browser action stores the captured path through normal dispatch. |
| S25, S26 | Existing action/provider/receiver/admission tests plus real SRS Good button inside an unselected row. Read-only planning and zero action counters for local selection. |
| S27, S28 | Native input/composition listener tests, guards/resources/retirement tests; browser draft retention and inspection of actual accepted choices, ports, followers and captures. |

The adapter suite uses a small DOM test port and deterministic deferred promises;
it does not substitute for the browser rehearsal below. Hardware IME composition,
browser stack layering, and every owner-removal permutation were not manually
rehearsed. Their narrower automated coverage should not be read as a claim that
all 28 cases passed end-to-end in a browser.

## Browser rehearsal

The real explorer, HTTP adapter and namespace were exercised on a separate local
instance. Observed results:

1. First workspace started empty; second independently seeded Card A. Selecting
   B updated only the first detail. ArrowDown focused C without selecting it;
   Enter selected C. The inspector showed zero domain action dispatches.
2. Changed C to its editor, typed a draft, switched to the inspection deck tab
   and back: recipe and text survived. Refresh views also retained them.
3. Selecting B with dirty input left C accepted and B pending. Selecting A
   superseded that prompt. Stay preserved C and its draft.
4. Remember selected card captured B and updated the study's stored path to
   `/0x11/app/panes/cards/b`, visible in ordinary and synthetic rendering.
5. Good inside the SRS row updated the card while the collection remained
   unselected. Selecting that row and using Show changed its following recipe
   to the answer without changing the selection.
6. Edited B and saved through its ordinary action. Both queues refreshed their
   summary text, the editor recipe survived, and the second workspace stayed A.
7. Clear returned the first detail to Choose a card. Existing controls continued
   to select B, C, then B without resetting the adjacent workspace.

### Fixture correction found during final rehearsal

Saving a card and then acting on the Grove installation root replayed its pact
seed records, restoring the card seed. `grove_install/mount` installs a manifest
on that root; it is not an ordinary study record. The specimen now places the
action receiver at `/0x11/app/panes/study`, alongside `/cards`, so study actions
do not reactivate the installer. The final browser pass saved “Card B retained after capture”, then captured B
on the study; both queues retained the saved text, the editor remained active,
and the second workspace remained on A. This does not change the existing pact lifecycle
for actions authored directly on an installation root.

## Run the specimen

```sh
WISP=/path/to/wisp python3 x/eden --mount panes --port 8172
```

Open `http://127.0.0.1:8172/views/0x11/app/panes/study`. The mount includes explorer,
codecs and SRS. Use the default node `0x11`; the fixture's finite source paths
are explicit. For a short demonstration, repeat steps 1–5 above and expand
Inspect local runtime to distinguish focus, accepted/pending choice and capture.

This is page-local single selection over at most 64 physical namespace children.
It uses explicit refresh, not reload persistence or a general query subscription
system. Dynamic member recipes containing another local session are diagnosed;
custom repeated bodies, cross-owner atomic capture, independent external draft
storage and general navigation history remain outside this slice. The capture
fixture has local application authority and stores a validated subject path; it
does not imply external Shrine integration.
