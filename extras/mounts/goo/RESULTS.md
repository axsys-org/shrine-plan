# Item 05: diagnostics and results

`src/results.foil` adds typed diagnostics and result bookkeeping. Semantic passes,
wire codecs for Goo trees, and the complete compiler API remain items 06–13.
The existing source adapter still stops after Rex parsing and reports incomplete.

`goo_result/diagnostic` follows `Goo.Diag`: Error or Warning, optional one-based
`goo/loc`, and message text. Stage identity belongs to the surrounding pass entry.
Diagnostic order is preserved. Missing locations render as `-`; present ones as
`line:column`. Rex error leaves now produce these typed diagnostics before the
source adapter projects them to its existing JSON schema. The retained Rex
transport and its separate legacy diagnostic representation are unchanged.

`goo_result/pass[v]` distinguishes:

- `succeeded`: a typed value and diagnostics (warnings are allowed).
- `rejected`: optional typed partial output and diagnostics.
- `crashed`: a synchronous exception message, separate from language diagnostics.

`classify` retains the supplied value as partial output when any diagnostic is an
error. Warnings alone succeed. An explicit rejection remains a rejection even
with an empty diagnostic list; it cannot accidentally become successful empty
output. Low-level constructors are trusted interfaces, like the item-04 IR.

`goo_result/output` holds phase-specific parse, read, core, normalized, visible,
and semantic outputs. Visible and Semantic explicitly permit an absent tree.
A progress checkpoint stores the compile context and ordered pass entries. The
small `control/step` recorder appends a delivered pass, preserving earlier values,
summary text and diagnostics, then stops on rejection or crash. It neither
selects nor implements semantic passes. A terminal state never evaluates a later
callback. The tests use a throwing callback with a positive control to prove this.

`control/finish` distinguishes a successful absent semantic tree from a present
one. Active/incomplete, rejected, crashed, successful empty and successful
nonempty are distinct states. Finishing an already failed or cancelled state
cannot mask its outcome.

Cancellation is separate: `attempt/cancelled` produces `control/cancelled` with
the last checkpoint, without creating a failed pass or ordinary compile result.
The recorder does not catch arbitrary exceptions. An executor must force a pass's
output and classify synchronous exceptions before delivering a `pass/crashed`;
the full executor belongs to item 13. This preserves the Haskell pipeline's rule
that asynchronous exceptions propagate rather than becoming compilation errors.

At the actual process boundary, Ctrl-C/SIGINT exits 130 and SIGTERM exits 143.
Cancellation during a Rex or Foil call stops its child process group, including
descendants, reaps the direct child, and emits no normal JSON failure response. Child processes
terminated by SIGINT/SIGTERM also propagate cancellation. Ordinary synchronous
process errors continue to produce structured adapter failures. Tests exercise
both signals while blocked at both boundaries, with locked files proving that
parent and descendant processes were running before cancellation and stopped
before the check finishes.

The Haskell production pipeline stores its crash separately from its pass list;
the full-stage oracle exposes a crashed stage. The Foil recorder retains an
explicit crashed entry plus stage/message in the terminal result, preserving the
information needed for both views. Partial rejected outputs match the oracle's
recoverable-parse behavior. There is no new semantic result JSON codec here.

Run `extras/mounts/goo/bin/goo build`, `extras/mounts/goo/bin/goo fmt --check`, and
`extras/mounts/goo/bin/goo test`. The package test command includes result behavior,
compiler rejection, actual cancellation, and frozen parse comparisons.
