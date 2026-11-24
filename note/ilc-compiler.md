# Incremental Foil compiler experiment

`src/reaver/ilc-compiler.rvr` accepts text splices or normalized Rex subtree
replacements and incrementally compiles a Foil import graph to ordinary
artifacts. It calls the existing parser, elaborator, lowerer and PLAN code
generator. This is an optional experiment; it does not replace the production
compiler or its publication preparation.

The first reuse boundary is **a module and its dependency subgraph**. It is not
incremental parsing, nor incremental typechecking inside a module. A fresh edit
can still benefit: unchanged modules do not need to be recompiled, even when
the whole program has never appeared before.

## How it uses ILC, PE and content identity

Think of compilation as `C(config, source_forest) -> retained_compilation`.
`pe.rvr` specializes the compiler invocation against the static context.
`ilc.rvr` applies a custom derivative that transfers the previous compilation
cache across source changes. The expensive operation remains the real
`foil-new-env:compile-inner`, not a toy replacement compiler.

For each source module the key is:

```
Pin [compiler-scope, module-name, normalized-Rex-pin,
     [(import-name, dependency-artifact-pin), ...]]
```

Keys include imports in source order and preserve spans. Equal module source
alone is insufficient: a changed dependency must invalidate its importers.
Compiler scope includes the actual compiler/PE functions and the selected
publication context: compiler selection, public roots, nominal moments,
installed artifacts and runtime owner. Nominal revisions are caller-supplied;
hashing source does not authorize new public definition identities.

The ordinary driver's cache key contains a graph-wide source revision. Keeping
that token in every incremental key would invalidate everything on any edit.
This experiment replaces only that token with each module's source/dependency
key. It retains all the other context fields. Artifacts therefore carry
per-module provenance. Tests compare exact artifacts with a cold run of this
same protocol, and exported behavior and constructor identities with the
ordinary production driver, whose provenance tokens differ.

The ILC rule is explicit domain knowledge. This is **not** evidence that generic
differentiation automatically discovers compiler dependencies. PE binds static
context; the module dependency rule supplies the useful incremental work.

`src/reaver/ilc-compiler-demo.rvr` is an executable walkthrough: it produces a
unary `g(source-delta)`, edits a dependency, reuses an independent module, and
then undoes the edit entirely from retained history.

## API and edit contract

```scheme
(#bind inc (#module ilc-compiler))

;; context comes from the caller's selected publication assignments.
(define cfg (inc:config context ["main"] 1024))
(define forest (inc:from-texts [["lib" lib-text] ["main" main-text]]))
(define compiled (inc:specialize cfg forest))

;; Byte offsets refer to the document immediately before this edit.
(define dx (inc:change [(inc:text-diff "lib" 8 1 "4")]))
(define next (inc:update cfg compiled dx))
(inc:artifact next "main")
```

These are edit constructors, not algorithms for finding a minimal difference
between two complete files. A caller that already has editor splices need not
rediscover them. The normalized-Rex alternative is:

```scheme
(inc:change [(inc:rex-diff "lib" [0 1] replacement-node)])
```

Rex paths index children, not constructor fields; `[]` replaces the entire
tree. The caller supplies valid normalized Rex and spans for structural edits.
Rex edits preserve other nodes' spans and do not infer new text offsets.

A batch is a row of sequential operations:

- `["text" name byte-offset delete-byte-count inserted-text]`
- `["rex" name child-index-path replacement-node]`
- `["set-text" name complete-text]`
- `["set-rex" name complete-normalized-tree]`
- `["delete" name]`

Text splices to one document coalesce before parsing; only edited documents are
reparsed. A Rex edit bypasses the text parser and clears the retained text for
that document. A subsequent text splice then fails rather than applying offsets
to an obsolete buffer. `set-text` restores a synchronized text/tree pair.
Adding a module requires an existing resolver/publication assignment for its
name; imports cannot invent authority.

`stats` returns `[compiled-source-modules history-hits installed-artifacts]`
for the latest update. An unchanged module counts as a hit. The memo is explicit
in the returned cache, with no process-global memo. If its entry count exceeds
the configured soft limit, the next update drops history. A single build can
exceed the limit; it is not a byte-level memory bound. A generic ILC replacement
falls back to a cold specialization. Config is the static argument to the
specialized function: start a new specialization when changing configuration
without a source delta. A zero source delta means no change.

Compilation is pure and compiled artifacts are forced before the new cache is
returned. Retained source records follow PLAN's normal lazy evaluation rules. A
failed compilation throws without publishing a partial artifact cache; the caller can retain the old
cache and apply a corrected edit. The prototype does not retain an invalid
editor buffer or implement editor diagnostic state management.

## Scope and remaining work

- Every update still walks the reachable module graph to validate dependency
  keys. A reverse dependency index could avoid much of that walk.
- A changed module is fully reparsed for text edits, then fully elaborated and
  lowered. Rex edits remove only the text-parsing step.
- Changed artifact pins conservatively invalidate importers, even if their
  exported behavior happens to be equivalent. There is no interface-equivalence
  optimization.
- Declaration-level reuse needs exact dependency tracking for name resolution,
  imported and local types, prototypes, generated members and lowering groups.
  A syntax-subtree hash by itself is not a sound typechecking cache key.
- Publication/moment selection is fixed input to each compilation. This is not
  an incremental implementation of publication preparation.
- Structural edits rely on caller-maintained spans. Changing parser versions
  requires recreating the source forest from text; this is not a hot-migration
  protocol for persisted parser state.

## Reproducing the experiment

```sh
WISP=/path/to/wisp x/check pe-tests ilc-tests ilc-compiler-tests
WISP=/path/to/wisp x/bench-ilc-compiler --samples 5 --cycles 4
```

The benchmark uses 41 actual Foil modules: 32 leaves, eight groups of four
leaves, and one root. Every leaf defines a value and eight typed functions.
All edits introduce fresh values; no undo/history repetition is needed.
Eight clustered edits affect two groups, while eight scattered edits affect
all eight. Compiled module counts per update are 3 for one leaf, 11 for eight
clustered leaves, 17 for eight scattered leaves, and 41 for all leaves.

Three strategies receive the same source edit stream:

1. **Production:** ordinary `compile-with`, with an empty artifact cache.
2. **Cold:** the new module-key orchestration, with empty history each update.
3. **Incremental:** the retained cache, updated through ILC.

Timers include applying edits, changed-file parsing for text, dependency walks,
key construction, elaboration, lowering, linking and cache maintenance. All
strategies receive already parsed unchanged modules: the baseline is not
charged for reparsing the entire program. Initial compilation, source and edit
generation, publication selection and semantic validation are outside timers.
Every trial starts from the same initial retained cache; no prior sample's
history is supplied. Order reverses on alternating samples. Logs, frozen
sources, runtime identity, checksums and per-sample timings are kept in `.check`.

The pilot exposed the existing `codegen:ingest-global` rejection of some
zero-valued imported computed globals (`wack global`). The workload starts at
one and increases; the experiment does not modify that unrelated code path.

## Measurements

Five samples of four successive fresh edit batches, measured in the VM.
Medians in milliseconds per batch; initial compilation excluded.

| Edit batch | Modules rebuilt / 41 | Production | Cold key protocol | Incremental | Production / incremental |
| --- | ---: | ---: | ---: | ---: | ---: |
| text-clustered-1 | 3 | 1144.820 | 1274.050 | 175.202 | 6.53x |
| rex-clustered-1 | 3 | 1147.189 | 1258.521 | 175.788 | 6.53x |
| text-clustered-8 | 11 | 1192.825 | 1300.698 | 435.380 | 2.74x |
| text-scattered-8 | 17 | 1191.595 | 1271.475 | 604.529 | 1.97x |
| text-clustered-32 | 41 | 1260.601 | 1379.704 | 1386.062 | 0.91x |

The partial-edit cases beat production in all five paired samples. Full churn
lost all five: when all leaves change, every module rebuilds and the cache
adds overhead. Text and Rex single-leaf results are essentially equal on this
fixture; parsing is small compared with elaboration/lowering and key
maintenance. These are fresh changes, so the gains do not depend on undo or
revisiting an old whole program. This experiment does not establish a universal
edit-count threshold for other dependency graphs or module sizes.

The cold key protocol is slower than ordinary compilation; the speedup comes
from avoiding compiler work, not from replacing the compiler with a faster one.

Runtime: `/nix/store/y4y0hwcwg7d8g7rvksb9md05jwa1w2w8-enki-pgo-0.1.0/bin/wisp`. Host: `macOS-26.3-arm64-arm-64bit-Mach-O`.
Report, raw logs and frozen sources: `.check/ilc-compiler-z5pj8ce1/results.json`.
The measured implementation, fixture and benchmark were checked against the
working tree. Subsequent edits only expanded tests, the walkthrough and this
note.

Regression coverage includes text splices, coalescing sequential edits, Rex
replacement, independent and diamond dependencies, import retargeting, missing
modules, cycles, compiler errors and recovery, invalid edit bounds, undo hits,
history eviction, generic ILC fallback, cache transfer without evaluating old
source, compiler selection changes, installed artifact precedence, and nominal
constructor revision changes. Successful updates agree exactly with cold
artifacts using the same module-key protocol; exported values and constructor
identities also agree with the ordinary production driver.
