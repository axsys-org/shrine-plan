# The PR into main: what goes in, what stays out, what to fix first

Branch `ic-bare-loop`, 55 commits and 112 files ahead of main, 19 commits behind it, no merge conflicts (merge-tree
dry run). This file is the plan for making that reviewable by Liam; it does not itself go in.

## Fix before anyone reads it

1. **One reverse-reference read path.** Done (ae73407): both the direct `/r` read and a view's read end in
   `store_references`, and a live read takes the index's current edges instead of unpinning the top snapshot.
   Measured after: `/r` of a thing with 172 incoming edges, 0.18 s through MCP at care z; 0.04 s for a page of five.
2. **`graph_world/nodes` and `cap` as cell parameters.** Done: `cap`, `deeper`, `nodes` are read from the cell's
   slots with the constants as documented defaults and ceilings (`graph_world/bounds_of`).
3. **`read_fuel`**: done both ways: 32768 is the ceiling, said so in its comment, and a cell declares a smaller
   budget of its own at `/sys/view/fuel`, applied in `woven_evaluate_select` (a nesting cell's remaining fuel caps it).
4. **Type placement constraint written next to the types.** Done: the rule is at the head of `sys/view.foil` and
   above the protocol types in `lain_types.foil`.
5. **`weft_std` (1,400 lines) placement**: self-contained, in the kernel tree because records cannot hold closures.
   Offer the mount alternative in the PR text; don't move it without his word.
6. **The error scan in the pipeline** counts module self-test output as failure (`newtype`); out of the PR's scope but
   note it so the retained stage's mtime trick is not mistaken for correctness.

## What goes in

Kernel (`src/foil`), each with a one-paragraph doc comment at the top of the module saying what it is for and why it
is in the kernel:
- `reference_index.foil`: the reverse-reference index in `sov`, maintained in `apply`, rebuildable from the journal,
  bounded snapshots (`span`). `r_spell`: `/r/<len>/<path>`, the `/h` convention.
- `shrine.foil`: `sov/apply` computes before/after once for the index and the signs; `reindex_references`.
- `lain_peek.foil`: `/r` and `/o` reads, the woven evaluator with observations, `read_fuel`, the cycle trail,
  `store_references` with its epoch rule. The largest diff; the PR text walks it.
- `lain_types.foil`: the view protocol types, `is_r`, `sorge`, `view_project` (see fix 4).
- `view_cache.foil`, `view_ops.foil`, `view_walk.foil`, `weft_graph.foil`, `graph_views.foil`, `graph_world.foil`,
  `graph_union.foil`, `graph_beneath.foil`, `graph_workspace.foil`: the views. Pure, named, registered at
  `/weft/graph`; each file's head says what the view answers and what it never asserts.
- `helm.foil`, `http_foot.foil`: the supervisor `look` card (several view reads in one call).
- `eden.foil`: seeds `weft_graph`.
- `namespace.foil` (`system_at`), `lain_poke.foil` (`is_r`, `r_parse` in triggers), `sys/slots.foil` and the
  regenerated catalogue: Codex's, kept after review; the PR text names them as such.
- `src/reaver`: `eden.rvr`'s `mounted-with` (the upgrade boot entry) and the bootstrap test fixtures. Codex's; needed
  by the upgrade path; say so.
- Tests in Foil (`src/foil/tests/*`): in. Liam wants tests in Foil, and these are the proof of the views. The
  Python proof scripts under `extras/mounts/mcp/tests/strangers` and `tests/registries`: in, they are small and
  they are the acceptance record.
- Mounts: `extras/mounts/mcp` (the four tools, `look`), `extras/mounts/explorer` (the page), `extras/mounts/hyp`
  (one line, the cache pass-through).
- `x/eden`, `x/eden_hands.py`, `x/setup`, `SETUP.md`, `.gitignore`: the kept-world and hands launcher; in.

## What stays out (move to a notes branch or leave untracked)

- `extras/mounts/mcp/hands/*.md` except `VISION.md`: `ASSEMBLY.md`, `COMPOSABLE_NAMESPACE.md`,
  `REVIEW-2026-10-25.md`, `HANDOFF.md`, `REGISTRIES.md`, `PR-PLAN.md`. They are the thinking, not the change.
- `extras/mounts/mcp/hands/registries.py`, `web.py`, `digest.py`, `links.py`, `agent.py`, `sync.py`: the Python hands.
  Liam's line is Foil in the kernel, Python only for what can't be Foil; the hands qualify, but they are a product
  layer. Propose them as a second PR so the kernel PR is read on its own.
- `extras/mounts/mcp/skills/*`: the agent skills; second PR with the hands.
- Anything under `.check/`, `work/`, scratch runners, `.DS_Store`.

## Doc comments the kernel changes need (the picky list)

- Every new top-level `+ name` gets a `'` line saying what it is; every type gets its fields explained where a
  name is not obvious (`strength`, `soft`, `trail`, `span`).
- No file carries a comment that explains the conversation ("Codex did", "tonight"); only what the code is for.
- Numbers get a reason: `span` 64, `cap` 24, `deeper` 6, `nodes` 150, `read_fuel` 32768, `graph_workspace/nodes`
  120, view cache 256 entries.
- `?` arms over `care` and `res` stay exhaustive; the `unreachable` trap is the compiler's, not a comment.
- Names: no `query_*` leftovers (done: `woven_*`); no `_native` suffixes in Foil; no "neuralese".

## Liam's rules, checked

- version 0 never means live for a pinned read: `/h/<care>/0/...` is a live reference by construction, and a
  `woven_origin` pins it at the reader's epoch when the view is frozen (`e<n>` epochs). Say this in the PR.
- Dispatch through the namespace: `/r`, `/o`, `/x`, `/c/x`, `/h` are all reads; the MCP tools stay four.
- Pagination: `look` exists so a page is one call; the z reads page at 500 nodes with `next`.
- Tests in Foil: 16 suites, 362 checks green on 2026-10-26 (run-14), plus 189 graph checks (run-15).

## Order of work

1. Merge main into the branch. Done on `ic-bare-loop-main` (worktree `../shrine-cells-main`): three additive
   conflicts (the `look` card beside main's `snapshot_bat`/`interact_bat`; the launcher copies `arena.dat`), and the
   test inventory brought up to date (main's three new reaver suites classified, entries for files that no longer
   exist dropped). Main runs a newer enki (single-file `arena.dat` snapshots, bat primops); the merged branch's
   Foil runs on it. Full suite on the new runtime, 2026-10-26 05:30: pristine main 1,277 pass, 0 fail, 4 suite
   errors of its own (`lain_store`, `lain_fixture`, `grove_publication` need-fail at suite completion; `fs_sync`
   fails to compile under the new elaborator), 39 suites in 845 s. The merged branch: 851 pass, 0 fail, the same
   four errors, 33 of 56 suites before the runner's 900 s limit, still progressing when cut (the extra 17 suites are
   ours); the rest run in a second batch. Main's own `x/check` also trips its inventory gate before any suite runs;
   the inventory fix on `ic-bare-loop-main` is what lets it run. The saved-world upgrade pipeline is
   LMDB-shaped and has not been tried on the new runtime; the PR does not depend on it.
2. Fixes 1-4 above, with their doc comments; commit each as its own.
3. Move the notes and the hands to `ic-bare-loop-notes` / a second branch; the kernel branch keeps `VISION.md`.
4. PR text: one section per commit group, in reading order: index and reads; evaluator and cache; views;
   supervisor look and mounts; page; launcher. Each kernel edit with its reason, each number with its rule.
5. Open only on Ian's word.
