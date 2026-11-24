# Foil style guide

`TODO` blocks mark decisions and examples still to be filled in. They are not
style requirements until resolved.

## Scope

> TODO: Which code does this guide cover? When editing existing code, should
> contributors preserve the surrounding style or apply this guide? Should
> unrelated formatting changes be kept separate?

## Example

```foil
+ is_txt
  '  Whether v is a nonempty cord of printable ASCII bytes.
  '  ?=  ((tyshow/is_txt "abc") 1)
  '  ?=  ((tyshow/is_txt 3) 0)
  \ v=nat
  ^ bool
  ? (eq v 0)
    .false
  % rest=nat v
  ? (eq rest 0)
    .true
  = byte | mod rest 256
  ? (lt byte 32)
    .false
  ? (lt 126 byte)
    .false
  | _ | div rest 256
```

## An aside on rex poems

### What Is a Rune Poem?

A rune poem is Rex's primary mechanism for vertical structure. A
free-floating rune (followed by a space) opens a poem, and children
are gathered by indentation — everything indented more than the
rune's column belongs to the poem:

    + a
      b
      c

This parses as `(+ a b c)`. The rune `+` is at column 0. Its
children `a`, `b`, `c` are at column 2 (after `+ `). Everything
to the right and below belongs to the poem until something appears
at the poem's column or to its left.

### The Parsing Box

This is the critical concept for understanding poem printing. A rune
poem claims a rectangular region: from its starting column, extending
rightward to infinity and downward until a token appears at a column
less than the poem's starting position. We call this the poem's
"parsing box."

The parsing box check is strict less-than: `col tok < cxPos ctx`.
Content at the same column as the poem does NOT break out — it stays
inside the poem.

### Flat vs Vertical

A poem with only closed children (words, strings, brackets) can be
rendered flat:

    + a b c

Or vertical:

    + a
      b
      c

The printer offers a `PChoice` between these when the poem is
"inlineable." PDoc's layout engine picks flat when it fits within
the page width, vertical otherwise.

A poem is inlineable when all children except possibly the last are
closed, and the last is either closed or itself inlineable. This
recursive check allows chains of nested poems to go flat:

    + a * b c       (poem + with children: a, poem * with children: b c)

### The Staircase Problem

When a poem has multiple children that are themselves poems (open
children), flat rendering is not possible and vertical rendering
requires special care.

Consider a poem `+` with three child poems `| a b`, `| c d`,
`| e f`. A naive vertical layout puts all children at the same
column:

    + | a b
      | c d
      | e f

This is WRONG. The first `|` poem starts at column 2 and its
parsing box captures everything at column > 2. The second `|` at
column 2 is NOT less than 2, so it does not break out — the first
poem consumes it. The tree would re-parse as the first `|` having
children `a`, `b`, `| c d`, `| e f` — completely different from
the original.

## The Staircase Solution

Each earlier sibling must be indented further right than later
siblings, forming a descending staircase:

    + | a b
     | c d
    | e f

Now the first `|` is at column 10. Its parsing box captures
everything at column > 10. The second `|` at column 6 is less
than 10, so it breaks out. The third `|` at column 2 is less
than 6, so it breaks out of the second. All three remain within
`+`'s box (column > 0).

The staircase pattern: each open sibling is 1 column further
right than the one below it.

## Why Only Open Children Need Staircases

Closed children (words, strings, bracket forms) have no vertical
extent. A word like `a` sits on one line and cannot capture
anything below it. So closed siblings can safely share a column:

    + a
      b
      c

`a` at column 2 doesn't create a parsing box. `b` at column 2 is
fine. Only rune poems (and blocks, which have their own printing
rules) create parsing boxes that could capture siblings.

This means the staircase is only needed between open siblings.
Mixed sequences work naturally — closed children use `PLine` at
the same column, open children use the staircase:

    + a
       | x y
      | z w

Here `a` is closed (no box). The first open child `| x y` is at
column 6, the second `| z w` at column 2 — a descending staircase
among just the open children.

## PStaircase: The Mechanism

PDoc provides `PStaircase` for rendering consecutive open children
in a descending staircase pattern. Given a list of documents:

    pdocStaircase [doc1, doc2, doc3]

It renders them with doc1 at the deepest indent, doc2 less indented,
and doc3 at the base indent:

      doc1
     doc2
    doc3

The key properties:

1. **Inside-out rendering**: Later items are rendered first to
   determine the overall shape, then earlier items are positioned.

2. **Backstep isolation**: The staircase returns `backstep=0` so
   its internal indentation doesn't leak to surrounding context.
   Multiple staircases compose cleanly without interference.

3. **Step size**: Each level is 1 column less indented than the
   previous one.

## The Rune's Line

When all children are open, the first child starts on a new line
(from PStaircase's `PLine`), leaving the rune alone:

    +
        | a b
       | c d
      | e f

The rune `+` is on line 1 by itself. This is valid Rex — the poem
still captures everything below at column > 0. When a poem has a
mix of closed and open children, the closed children appear on the
rune's line before the staircase begins:

    + a b
       | x y
      | z w

Here `a` and `b` are closed, rendered inline after `+ `. Then the
open children form a staircase below.

## Inlineability Revisited

A poem is inlineable only when the staircase is unnecessary: all
children except possibly the last are closed. If the last child is
an open poem, it's inlineable only if ITS children are also
inlineable (recursively). This ensures that flat rendering is only
offered when it produces output that re-parses correctly:

    + a * b c       OK: * b c is the last child, inlineable
    + * a b * c d   NOT inlineable: first child is open

When not inlineable, only the vertical form (with staircase) is
produced — no `PChoice`, no chance of incorrect flat output.
## Whitespace Layout

At the module level the `+` rune induces a two space margin for its children.
Inside a declaration, bodies sit two columns past their parent rune.
Operand lists may instead align under the first operand. Use one space after
`+`, just as for other runes; declaration bodies retain their two-space margin.

Here are the columns in the opening example. Each `·` represents one space;
the column numbers and notes are not part of the code.

```text
0123456789                  column (zero-based)
+·is_txt                   module rune: column 0
··\·v=nat                   declaration rune: column 2, value column 4
··^·bool
··?·(eq·v·0)                parent rune: column 2
····.false                  branch: column 4 (+2 from parent)
··%·rest=nat·v              back to declaration gutter

0 → 2   two-space margin from the module rune to its children
2 → 4   two-space margin from the parent rune to its branch
2 → n   n-space margin for dealing with backstepping
```


```foil
0123456789                  column (zero-based)
+·is_txt                   module rune: column 0
··+·help                   module rune inside module rune: column 2
····|·add·2·3               nested declaration rune: column 4, value colum 6
··\·v=nat                   declaration rune: column 2, value column 4

```

Line width has a hard cap at 80. Line width above 72 is suspect (a lint
warning), but may be called for. Width above 80 is a lint error. Tabs are forbidden.

## Rune layout

Always prefer tall-form `| f x y z` over `(f x y z)`. The only reasons to use the
parenthesis call syntax are to avoid having to break small arguments on new lines.

Do not ever use wide form `(| f x y z)`.
```
| foo (bar baz) qux ' acceptable
| foo               ' too simple for its height
 | bar baz
qux
```
or to use dot syntax compactly
```foil
(unpin p).meld(m) ' good, compact
. | unpin p ' bad, too simple for height
 meld(m)
```

If an argument to a UFCS call is overly long, consider lifting it out into a
separate let binding (single-use lets are eliminated by the compiler).
```foil
' bad
| _ j.inc out.snoc((explorer/dt_row1 src want (explorer/dt_chip verdict curx j)))
' better
=   nex
  | explorer/dt_row1 src want | explorer/dt_chip verdict curx j
| _ j.inc out.snoc(nex)
```




> TODO: Define “small,” “compact,” and “overly long” using the line width above
> or a nesting/readability rule. When a call no longer fits, which argument
> should move onto a new line first? When should it become a separate binding?
> Add a borderline example showing the preferred choice.

### UFCS versus prefix calls

UFCS vs free fns is a judgement call, you should use whichever maximises the
aesthetic of the code

### Path literals

Always write literal paths with slash syntax: `'/foo/bar`, not
`['foo 'bar]`. This includes single-segment paths (`'/foo`), numeric
segments (`'/foo/3`), and the empty/root path (`'/`). Parenthesize the
empty path as `('/)` in argument positions so Rex does not absorb the
following text into the literal. A bare `'foo` is one symbol, not a path.

Use row construction only when path segments are computed, such as
`[authority 'app name]`, or append computed segments to a literal prefix
with `.snoc`. Ordinary rows that are not paths retain row syntax.

### Rune layout `=`

`=` layout can be either kingside e.g.
```foil
+ foo
  = bar 3
    baz 4
  | add bar baz
```
or queenside for a multiline value:
```foil
  =   result
    | transform source
      | choose mode
        fallback
  | finish result
```
Queenside patterns sit four columns past `=`, and their values sit two
columns past it. A multiline value must remain one expression. Keep
parentheses when they group multiple statements into that expression.

Group adjacent short bindings in an aligned kingside stanza. Give complex
values separate queenside bindings. Use `'` comments for explanations, not
empty separators between bindings. An inner `^` can supply type information
that does not flow through a parenthesized body; avoid repeating that same
type on the binding name.

Kingside values should be aligned on the first rune of the value
```foil
' bad
= names | helm/scan after.sov
  crew | helm/crew_of names after.sov
  dead | before.crew.keys.keep (\ n (!(names.has(n)) || restarted.has(n)))
  born | names.keep (\ n (!(before.crew.has(n)) || restarted.has(n)))
  watches | helm/watches_of names after.sov
  tells | helm/notifications names born watches signs before after
  births | helm/births_for born after.sov

' bad
= names   | helm/scan after.sov
  crew    | helm/crew_of names after.sov
  dead    | before.crew.keys.keep (\ n (!(names.has(n)) || restarted.has(n)))
  born    | names.keep (\ n (!(before.crew.has(n)) || restarted.has(n)))
  watches | helm/watches_of names after.sov
  tells   | helm/notifications names born watches signs before after
  births  | helm/births_for born after.sov

```


## Naming convention

### Lapidary style

In smaller functions (<40 LOC), prefer lapidary style. Lapidary style uses 3-5 char names.
Naming algorithm:

- is there a 3-5 char word that describes the variable accurately? if so use
  that
- if no, then use a 3 char CVC construction that is a pun on the type name
  e.g. pax=path. 4 char constructions are only permissible if a pluralised
  version of CVC i.e. paxs=row[path]

> TODO: Does lapidary style apply only to local variables, or also to parameters,
> function names, and public fields? Is 40 LOC a guideline or a hard cutoff,
> and do comments and blank lines count?

> TODO: Define CVC (consonant-vowel-consonant) and give a few canonical type/name
> pairs. How should two values of the same type be distinguished? When are
> role-based names or longer names preferable to type puns? Are 1-2 character
> names such as `v` and `j` in the examples allowed, and in which contexts?

### Regular style

More typical of regular programming - choose longer, more descriptive names (but
don't descend into abstract_enterprise_factory_slop)

> TODO: When should regular style be chosen? Is it required for larger functions
> or public APIs, and may it be mixed with lapidary style within one function?
> Add an example of a useful descriptive name and one that is unnecessarily long.

### Shared naming conventions

Always use snake_case


