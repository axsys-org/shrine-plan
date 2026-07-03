# Foil Roadmap (Fable review pass)

A second roadmap for the Foil compiler (`src/reaver/foil*.rvr`, `codegen.rvr`,
`reef.rvr`), written after a close read of the full pipeline on branch
`lf/foil-fix`. It complements `ROADMAP.md`: items already listed there are only
repeated where the priority changes or the item is affected by newer findings.
Tags: **[correctness]**, **[tests]**, **[design]**, **[cleanliness]**,
**[completeness]**, **[ux]**, **[perf]**.

Guiding observation: the compiler has good bones (clean pass layering, small
seams, decent TC-level tests) but **no feedback loop that executes compiled
output**. Every high-severity item below survived because the suite asserts
on IR shape, never on results. Fix the feedback loop first; everything else
gets cheaper.

---

## P0 — Establish ground truth (do before any further lowering work)

- [x] **[tests] Execute compiled Foil, not just shape-check it.**
      *(done — `foil-exec-tests.rvr`; see `doc/aar/p0-1-execution-tests.md`)*
      Add a test that compiles and *runs* an argument-order-sensitive function,
      e.g. `+ sub2 \ a=nat b=nat ^ nat (sub a b)`, asserting `(sub2 5 1) == 4`,
      plus a recursive `~` function and a `?`-match function (use `bst.foil` as
      the canary). Wire it into `foil-tests.rvr` / `x/test`.
      **Expected to fail today** — that failure is the point; it pins P0.2.

- [x] **[correctness] Fix the elab/codegen calling-convention mismatch.**
      *(done — see `doc/aar/p0-2-calling-convention.md`; also uncovered two latent codegen bugs, `doc/aar/found-refcount-cond.md` and `doc/aar/found-ingest-let-snoc.md`)*
      The elaborator numbers locals self=0, arg_i=i (frame `Weld [self] argty`,
      `foil-elab.rvr:179-184`; pinned by integration tests). But:
      - `lower-lam` passes `tc-lam-arity` = frame size = **nargs+1**
        (`foil-lower.rvr:36`), so `ingest-lambda` (`codegen.rvr:339`) allocates
        one phantom argument key on top of its own separate `selfkey`;
      - the body scope is built `lrev(argkeys) ++ [selfkey]`, so `V i`
        resolves to key `nargs+1-i`.
      Net effect against the PLAN law spec (`doc/plan-spec.txt`, R rule:
      0=self, 1..arity=args in application order):
      - argument references are **reversed** (only 1-arg functions come out
        right by accident);
      - `~` self-reference lands on position nargs+1 — the first let slot if
        one exists (e.g. the match scrutinee), otherwise a literal;
      - under a match's `L`, arm references to function args are off by one.
      Decide on one convention (suggest: keep elab's self=0/args-in-order,
      make `lower-lam` pass the real arg count, and build the ingest scope as
      self-then-args without `lrev`), then fix `lower-lam` + `ingest-lambda` +
      `codegen` together.

- [x] **[correctness/tests] Re-derive the codegen asserts from the PLAN spec.**
      *(done — see `doc/aar/p0-3-codegen-asserts.md`)*
      Several existing asserts pin *wrong* laws, e.g. `codegen.rvr:191-194`
      asserts identity compiles to `(Law 1 "id" 2)` — per the spec a 1-arity,
      0-let law with body `2` returns the constant 2. These asserts will fight
      the P0.2 fix; rewrite them with hand-derived expected laws, and add a
      few that *evaluate* the produced law.

**Exit:** `(sub2 5 1)` returns 4 from compiled PLAN; a recursive function and a
match-heavy function execute correctly end-to-end.

---

## P1 — Correctness of the implemented core

Type-system and lowering defects confirmed in source, ordered by blast radius.

- [x] **[correctness] `subst-type` fallthrough corrupts types.**
      *(done — `doc/aar/p1-subst-type-fallthrough.md`)*
      `foil-types.rvr:120` returns `(right 0)` (an Either, copy-pasted from
      `check-type-wf`) for any unhandled tag — `TANY`, `TTYP`, `TSELF`, `TBOT`
      get *replaced* by `("right" 0)` during specialization. Should return
      `ty` unchanged (and probably error on genuinely unknown tags).

- [x] **[correctness] `cmp-total-in` compares the wrong operand.**
      *(done — `doc/aar/p1-cmp-total-operand.md`)*
      `reef.rvr:181`: `btype` is `(Type a)`, should be `(Type b)`. Cross-type
      comparisons dispatch into the wrong case. This feeds `TSUM`
      canonicalization (`sort cmp-total`).

- [x] **[correctness] `sort` drops pivot-equal elements.**
      *(done — duplicates kept, sum dedup made explicit; `doc/aar/p1-sort-drops-duplicates.md`)*
      `reef.rvr:214-223` partitions strictly-less/strictly-greater; duplicates
      vanish. Accidentally dedups sums (decide whether sum dedup is *wanted*
      and make it explicit), but it is a data-loss bug for every other caller.

- [x] **[correctness] Span inversion**
      *(done — `doc/aar/p1-span-inversion.md`)* (`foil-rex.rvr:46-51`) — `span-first`/
      `span-last` return the wrong operand; `span-join` yields negative spans.
      (Also in ROADMAP.md Stage 1; must land before spans reach diagnostics.)

- [x] **[correctness] `s_tfun` not wrapped in `TTYP`**
      *(done — `doc/aar/p1-tfun-ttyp.md`)* (`foil-elab.rvr:87`),
      so a named function type stores its *arity* as its type via the
      `(_2 (tc-typ-inner …))` extraction at `foil-elab.rvr:380`. Normalize all
      type-valued elaborations to `TTYP` + regression test.

- [x] **[correctness] Subject shape vs tvar API**
      *(done — `doc/aar/p1-subject-shape.md`)* — `make-subject` builds two
      slots, `sut-tvar` addresses slot 3 (`foil-subject.rvr:66-71`). Reconcile
      before enabling `check-type-wf` (currently dead code, see P4).

- [x] **[correctness] `TNAT` meet is wrong.**
      *(done — `doc/aar/p1-tnat-meet.md`)* `type-meet-span` returns `TBOT`
      for `meet(TNAT 0, TNAT 7)` (`foil-types.rvr:421`) although `TNAT 7`
      nests in `TNAT 0`; the meet should be the constant. A test currently
      *asserts the wrong behavior* (`foil-types-tests.rvr:138`) — fix both.
      More generally: add lattice property tests (meet is glb / join is lub
      w.r.t. `type-nests?`, commutativity up to sum ordering).

- [x] **[correctness] Match-arm test weakening (new `lower-arm-test`).**
      *(done — invariant enforced at elaboration; `doc/aar/p1-arm-test-invariant.md`)*
      The uncommitted rewrite checks constructor head + arity only, weaker
      than the old deep `type-fits`. Two sum options sharing tag+arity but
      differing payloads now silently take the first arm. Either document the
      invariant and enforce it at elaboration time (reject sums whose options
      are indistinguishable by head+arity), or deepen the generated test.

- [x] **[correctness] `lower-tc-mod` re-lowers builtins and duplicates order.**
      *(done — `doc/aar/p1-lower-mod-relowering.md`)*
      It walks the entire subject order including builtin FFI entries, and
      inserting into `out` (seeded with the same subject) re-pushes keys onto
      `subject-order`. Skip already-lowered/FFI entries; keep order a set.

**Exit:** lattice ops obey their laws under test; no known wrong-value paths in
elab → lower → codegen for the implemented subset.

---

## P2 — An honest boundary and legible failures

(Substantially = ROADMAP.md Stage 2; kept here because P0/P1 change the order.)
All P2 items done — see `doc/aar/p2-*.md`.

- [x] **[ux]** Located "not implemented" diagnostics for `s_letrec`,
      `s_ufcs_put`, `s_ufcs_over`, `s_literal` (`foil-elab.rvr:357-360`)
      instead of raw AST dumps.
- [x] **[ux]** Wire spans into elaboration errors (depends on span fix, P1) and
      start actually accumulating into `env-diags` instead of failing fast.
- [x] **[ux]** A legible failure for "recursive function without `^` return
      cast" — today `peek-ret-cast` yields `TBAD` (`foil-elab.rvr:111-114`)
      and the user sees `("bad apply" …)`. Detect and say what's missing.
- [x] **[correctness/ux]** `uncurry-call` else-branch (`foil-sast.rvr:111-116`)
      passes a single SAST node where `s_app` expects an argument row — the
      `%`-with-heir path `axal.foil` relies on. Fix or reject with a message.
- [x] **[docs]** Mark spec-vs-implementation in `doc/foil-semantics.md`;
      label `axal.foil` aspirational.

---

## P3 — Completeness for real programs

Same list and rationale as ROADMAP.md Stage 3, dependency-ordered.
All four landed (see `doc/aar/p3-*.md`), with two design changes:

1. ~~Local bindings / `letrec`~~ **done** — `=` bindings elaborate as
   sequential lets (`doc/aar/p3-local-bindings.md`); truly recursive
   local bindings remain future work.
2. ~~Functional record update `.%` / `.#`~~ **done, redesigned** —
   plain `.` UFCS instead of new runes: every generated accessor now
   comes with `set_<face>` / `over_<face>` methods
   (`doc/aar/p3-record-update.md`).  `.%`/`.#` stay rejected.
3. ~~Text literals + a string type~~ **done** — `'`-prefixed rex quips
   typed by the `quip` aura sum from `quip.rvr`
   (`doc/aar/p3-quip-literals.md`).
4. ~~Match exhaustiveness checking~~ **done** — fall-less matches must
   cover every option of the scrutinee sum
   (`doc/aar/p3-exhaustiveness.md`).

---

## P4 — Design debt to decide (not just clean)

Each of these is a *decision* item — keep-and-finish or delete — because the
half-state is what breeds P0/P1-class bugs.

- [x] **[design] `TANY` is both top and bottom**
      *(decided: it is the gradual/dynamic type — named, fenced, and given
      deliberate meet/join behavior; `doc/aar/p4-tany-dynamic.md`)* (`foil-types.rvr:158-159`),
      a deliberate soundness escape hatch that also backs `empty-env`'s goal.
      Name it, comment it, and decide where it is allowed to appear.
- [x] **[design] No `TFUN` variance**
      *(implemented: args contravariant, returns covariant; unface-fun
      hack deleted; `doc/aar/p4-tfun-variance.md`)* — functions nest only via `Equal`, with
      the `unface-fun` equality hack in `type-apply-span`. Either implement
      co/contravariance or document the restriction.
- [x] **[design] Globals are inlined by value**
      *(decided: function refs are by-name TC_GLOBALs linked via pins at
      lowering; other entries stay inline; `doc/aar/p4-tc-global-linking.md`)* (`elab-ref` embeds the whole
      referee TC, `foil-elab.rvr:253`): no linking, no by-name recursion,
      copies everywhere. Fine for now — but it should be a stated decision,
      and it interacts with any future incremental-compilation story (perf:
      it also bloats every compiled law that references a big function).
- [x] **[design] Vestigial bidirectional checking**
      *(removed; source comment marks where checking-mode belongs;
      `doc/aar/p4-tany-dynamic.md`)* — `env-goal`
      push/peek/pop exists, `elab-cast` writes it, nothing reads it. Commit to
      checking-mode elaboration or remove the machinery.
- [x] **[cleanliness] Dead/broken lattice code**
      *(deleted, except `check-type-wf` — fixed and enabled as an
      elab-mod post-pass, and `TC_GLOBAL` — now load-bearing;
      `doc/aar/p4-wf-checks.md`, `doc/aar/p4-booleans-and-dead-code.md`)*: `check-type-wf` (never
      called), `resolve-type` (legacy tags), `either-seq` (missing else
      branch), `tc-global`/`TC_GLOBAL` (never constructed; its lowering at
      `foil-lower.rvr:97` calls `got-const` missing the `sut` arg),
      `TUNI`/`TBOX`/`TEXI` (exported, never built).
- [x] **[cleanliness] Footgun globals in reef**
      *(yes/no with no=0; fixing it activated print.rvr line-wrapping
      for the first time; `doc/aar/p4-booleans-and-dead-code.md`)*: `(define y 1)` *and*
      `(define n 1)` — `n` is a truthy "no". Replace `y`/`n` with named
      booleans (or fix `n` to 0 and grep every use); stop passing `y y y`
      as flags (`foil-lower.rvr:36`).
- [x] **[cleanliness] Duplication**
      *(deduped, except the foil.rvr façade — kept deliberately as the
      stable public surface; `doc/aar/p4-booleans-and-dead-code.md`)*: `fold-app` (codegen + foil-lower), double
      `f-pinned` (`codegen.rvr:17-18`), double `pipe` macro (`reef.rvr:28-32`),
      `surf-ref-val`/`surf-ref-path` aliases, the ~50-line re-export façade in
      `foil.rvr`.

---

## P5 — Performance (after correctness locks)

All four items resolved — measurements and the rejected-experiment
writeup in `doc/aar/p5-perf-measurements.md`:

- [x] **[perf]** Index `span-to-mold`'s reverse lookup — *implemented,
      measured ~5% net regression at current module sizes, dropped.*
      The premise didn't hold: wall clock is dominated by wisp module
      compilation, not foil elaboration. Revisit with measurements when
      subjects grow.
- [x] **[perf]** Memoize `mold-to-span` — *same experiment, same
      verdict.*
- [x] **[perf]** Skip re-lowering builtin entries in `lower-tc-mod` —
      *done in P1.*
- [x] **[perf]** Revisit global-by-value inlining (P4) once a linking story
      exists — *done: TC_GLOBAL by-name references (P4).*

---

## Status notes vs ROADMAP.md (as of `lf/foil-fix` working tree)

Already addressed on this branch (verify via P0 execution tests before
checking off):

- Match lowering P1 trio (ROADMAP.md Stage 0): `L_` now dispatches to
  `ingest-let`, `ingest-let` destructures the tag slot, and `lower-match`
  lowers the scrutinee. The `pe.rvr` residualized arm test was replaced by
  the direct `lower-arm-test` — good direction; see P1 weakening note.
- Debug prints stripped from `reef.rvr` sort/cmp paths and the `TSUM`
  mismatch print.
- `type-fits-span` learned a `TNOM` case.

Sequencing traps carried over: fix spans before surfacing them; reconcile the
subject shape before enabling WF checks; don't start P4 cleanup until P0–P2
land.
