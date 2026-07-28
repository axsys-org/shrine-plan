# Ripping text-sensitivity out of rex → sast

STATUS 2026-07-28: LANDED.  The zero-span property holds (a normalized
tree with every span zeroed compiles and behaves identically — the
permanent test lives in foil-schemagen-tests) and the whole corpus
parses with item-col / truthy-split / the one-liner line filter
deleted.  What shipped differs from the plan below in one spelling:
the vertical group normalizes to the EMPTY-RUNE CLEAR NEST (the block
form sast always consumed), not to Juxt — a group and a same-line
juxtaposition (`f(x)` method segment) can occupy the same position,
so they need distinct constructors.  Everything else is as planned,
with one correction after checking the rex reference: the poem
ANCHOR is the head rune's LAST character (§8.3-8.4), peers are lines
STARTING at or left of it, children strictly right — the original
bug was demanding free-pos EQUALITY for peers, not the anchor choice
itself.  Poem ctxs carry the anchor; a peer starting inside a
multi-char rune's width pops and regroups by column in the parent.
Body items group relative to the FIRST OPERAND's
column (deeper runs = one sub-block kid, equal-column lines = the
poem's own items, same-line followers join as a juxt), `=` pairs
positionally (group in value position = block value; in head
position = spliced continuation pairs; head juxts splice), bool-`?`
is cond + rest-as-then, and bracket absorption skips empty-rune kids
(a block's statements must not become call args).

Goal (2026-07-28, Liam): past the tokenizer, nobody consults columns,
lines, or offsets for *structure*.  Spans ride as diagnostics only.
The normal form stays Leaf/Nest/Juxt; sast never distinguishes
Juxt-vs-Heir or Bloc/Open/Pref/Tyte; sast rules are positional:

- `=`  — kid count satisfies n mod 2 == 0, consumed pairwise.
- `\`, `|` — same-line kids are binders/params; the body is a
  mandatory trailing Juxt (one-liners canonicalize to a singleton).
- `?`  — forwards row[child] plus a trailing Juxt as maybe[rex]
  through the sast; elab interprets.  No arity knowledge in sast.

## Where the disease actually lives (probe-verified)

1. **rex-split-heir (rex.rvr:1387) keys sibling-vs-child on FREE-POS.**
   A rune node's span col is its free-pos (col + len - 1,
   rex-free-node), and the heir split compares that against the poem
   head's free-pos.  Equal-indentation lines whose rune is WIDER have
   a deeper free-pos and get swallowed as children.  This is the
   origin of: the equal-rune-width heir gotcha, the wide-rune (?>,
   |>) "swallowed into the poem" repairs in parse-body-go, and
   truthy-split's shallow/deep column scan.

2. **rex-convert-poem attaches deeper lines as FLAT kids**, mixing a
   statement's same-line operands with its subordinate body lines in
   one kid list.  sast re-splits them by line number (\ one-liner,
   foil-sast:629) and column (parse-letrec grab, :449).

3. **rex-normalize-juxt splices nested Juxts flat** (rex.rvr:1506) and
   **rex-normalize-bloc merges head+items** (:1523), erasing the
   vertical grouping the tree layer did resolve.

## The fix, at the origin

a. **rex-split-heir compares START columns.**  For a rune node, start
   = span-col - (len - 1) — the normalization item-col does today,
   moved to the one layer allowed to think about columns, then
   deleted from sast.  Equal start col ⇒ sibling regardless of rune
   width: wide-rune swallowing vanishes, and with it every downstream
   repair.

b. **rex-convert-poem groups subsequent lines.**  Same-line nodes stay
   operand kids; deeper LINES (line > head line) become ONE trailing
   Heir kid (statements at the same inner col splice together;
   the group itself is a single kid).  This gives \/| their mandatory
   trailing group and ? its forwardable body without any rune-specific
   knowledge at the rex layer.

c. **Normalize keeps structure**: Heir → Juxt as a single kid (no
   splice into the parent), Bloc → head kids + trailing Juxt(items).
   Juxt-in-Juxt is unambiguous: outer = vertical group, inner =
   same-line juxtaposition.

d. **foil-sast goes positional** and these die: item-col, synth-body
   column logic, parse-letrec's grab/bcol, the \ one-liner line
   filter, truthy-split, the wide-rune cut repairs in parse-body-go,
   the ? fallthrough column comment, on-dec-list's offset capping
   (diagnostic spans can then be computed correctly at parse time).

## Shape changes sast consumers will see

- bool-?: kids [cond juxt(then...)] (2 kids always; multi-line then no
  longer produces >2 kids needing truthy-split); else stays the heir
  sibling / continuation.
- match-?: kids [scrut juxt(arm... fallthrough...)]; arms are the
  `>`-runed items of the group; groupmates without `>` are the
  fallthrough.  Arms' own bodies arrive as each arm's trailing group.
- `=`: [name value] or [name juxt(value-block)] — always even.
- `\` decl-slot vs inline unifies: params = same-line kids, body =
  trailing juxt when present, else (one-liner) last kid.
- `|`: binder arms same-line / sibling `>` lines; body = the decl
  heir as today.

## Risks / corners

- Sources indented 1..(runewidth-1) past a statement's start column
  change meaning (previously sibling by free-pos, now child).  Corpus
  is the oracle; expect zero such lines in-tree.
- foil-lore (capture-lore) and doctest.rvr walk normalized rex — they
  must tolerate nested juxts.
- rex-tests assert printed forms; printer must print groups
  (indent = depth) — this refactor is also what makes
  parse ∘ print = id reachable.

## Acceptance

1. Full corpus parses to behaviorally identical modules (x/check all
   groups + driver suites green).
2. Zero-span property: compile-rex of a span-zapped parsed tree of
   json.foil (and sept) compiles and round-trips — the exact probe
   that fails today.  Lands in foil-schemagen-tests.
3. item-col and every rx-span read in foil-sast outside rex-blurb
   (diagnostics) is deleted.

## Order

1. rex tree layer: split-heir start-col + poem line-grouping (a, b).
2. Normalize: no-splice + bloc grouping (c).
3. foil-sast port (d), iterating per-module: sept → json → shrine →
   lain → helm, template-copy probes, then full gate.
4. foil-lore / doctest adjustments.
5. Zero-span test + delete dead repairs + gate + commit.
6. (Later) schemagen emits trees directly; printer layout from
   structure.
