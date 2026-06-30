# Rex Examples

A collection of Rex examples illustrating the range of the notation.

Despite the surface variety, every example here collapses down to three
conceptual forms:

    leaf                      -- an atomic token: word, string, or quoted form
    NEST(rune form*)          -- a rune applied to zero or more children,
                              -- tagged with a bracket type: () [] {} or none
    form JUXT form            -- two forms placed immediately adjacent

The bracket type is part of the tree — `{x:3}`, `(x:3)`, and `[x:3}` all
produce different nodes. Downstream languages assign meaning to the difference:
perhaps `()` for grouping, `[]` for lists, `{}` for records. Rex preserves the
distinction but doesn't interpret it.

Tight infix, tight prefix, layout poems, blocks — all of it is just different
ways of encoding one of these three things. Keep that in mind while reading:
the tree underneath is always simple.


## Bracket Types

The normal nesting types are obvious. parens is `(x : 3)`, etc.  But what is the "clear" nesting type?

One example is with multiple layers of infix:  `{x : 3, y : 4}`.  The coma node has brackets, but
the colon nodes (`x : 3`) have no visible delimiters, so they are "clear" nesting.  Similarly,
with `(f x, g x)`.  The `f x` node has a "clear" nesting.

Two more cases are with using infix at the outermost layer, and with using infix in block items:

```rex
x = 3   ') clear infix
print x ') clear prefix

block
   x = 3   ') clear infix
   print x ') clear prefix
```

---

## The Core Subset

All Rex trees can be written in fully explicit prefix notation. This is the
foundation everything else builds on.

```rex
(+)
(+ a b)
(+ (* a a) (!! "error"))
[+ [* a a] [* b b]]
```

`()` and `[]` follow identical parsing rules — only the bracket type differs
in the output tree. Any Rex tree can always be written this way.

---

## Heirs

When two forms are written side-by-side with no whitespace, they form an
heir — a juxtaposition node:

```rex
foo(+ 3 4)
b"hello"
[+][-]
```

`foo(+ 3 4)` is the familiar function-call form. `b"hello"` is a typed
literal — a word juxtaposed with a string, useful for byte strings, raw
strings, etc. `[+][-]` is two bracket forms juxtaposed, which looks
unusual but is structurally identical to the others.

---

## The Same Tree, Many Forms

These two examples parse to the same tree. The first is written in explicit
prefix notation; the second uses layout, tight infix, and tight prefix:

```rex
(:= (/ x y)
 (| if (= y 0) (!! "Error: divide-by-zero")
  (| if (< x y) 0
   (# (+ 1 (/ (- x y) y))))))
```

```rex
:= x/y
 | if y=0 !!{Error: divide-by-zero}
 | if x<y 0
 | #(1 + (x-y / y))
```

In the second form: `:=` opens a layout poem. `x/y` is tight infix. `y=0`
and `x<y` are tight infix. `!!` is tight prefix applied to a curly-brace
quip. `x-y / y` is mixed tight/spaced infix. The choice of form is
purely aesthetic — both are valid Rex.

---

## Tight Infix

Runes between tokens with no spaces form tight infix:

```rex
a+b         ') => (+ a b)
a+b+c       ') => (+ a b c)
x:xs        ') cons
a.b.c       ') field access chain
foo/[bar]   ') tight infix with a bracket form on the right
```

Tight infix uses the same precedence ordering as spaced infix — determined
by the first character of each rune, from loosest (`,`) to tightest (`.`).
So mixing runes in tight infix works too:

```rex
a.b+c       ') => (+ (. a b) c)   -- . binds tighter than +
x:xs++ys    ') => (: x (++ xs ys)) -- : binds looser than ++
```

A tight infix expression always uses a single rune token — two adjacent rune
characters lex as one token, so `a+*b` would be the single rune `+*`, not
`+` and `*` separately.

---

## Spaced Infix and Precedence

Inside brackets or layout, runes separated by spaces create spaced infix.
Unlike tight infix, spaced infix can mix different runes freely. When multiple
rune types appear, they are sorted by precedence and grouped automatically.
Precedence is determined by the first character of each rune, using this fixed
ordering from loosest to tightest:

    , : # $ ` ~ @ ? \ | ^ & = ! < > + - * / % .

Lower in this list binds more tightly. The ordering was chosen so common
conventions work naturally: `,` separates items at the outermost level, `:` for
type annotations binds looser than `->`, arithmetic operators have their
conventional relative ordering, `.` for field access binds tightest of all.

```rex
(a + b)
(a + b + c)
(a + f x + d)   ') f x is grouped as one child: => (+ a (f x) d)
(a -> b -> c)
```

A type signature uses mixed runes — `:` is looser than `->`, so it splits
first:

```rex
map : (a -> b) -> [a] -> [b]
```

Parses as `(:  map  (-> (-> a b) ([] a) ([] b)))`. The `:` separates the
name from the type, and `->` chains within the type.

For arithmetic, tight infix handles high-precedence operations and spaced
infix handles low-precedence ones:

```rex
(4 + 5*n + x/4)
```

`5*n` and `x/4` are tight infix (no spaces); `+` is spaced infix. Precedence
is made explicit through spacing rather than declared separately.

A JSON-style record uses `,` as the loosest separator and `:` for key-value
pairs — and because `,` has lower precedence than `:`, they compose without
extra parentheses:

```rex
{
  name: "rex",
  version: "1.0.0",
  enabled: true,
}
```

Parses as a `,`-form where each child is a `:`-form. The precedence system
is what makes this work without any special parser support for records.

---

## Tight Prefix

A rune immediately preceding a token (no space) creates a tight prefix form:

```rex
+a          ') => (+ a)
+a.b        ') => (+ a.b)  -- tight prefix applied to tight infix
./foo/bar   ') => (./ foo/bar)
-x          ') negation
<h          ') operator section: (< h)
```

Tight prefix composes with tight infix: `+a.b` parses as `+` applied to
`a.b` (the whole tight infix chain), not as `(+a).b`.

---

## Mixing Tight and Spaced Infix

Tight and spaced infix compose naturally — tight infix always binds tighter
than any spaced infix, regardless of the runes involved. This means you can
write mixed expressions without extra parentheses:

```rex
(x:xs ++ ys)        ') => (++ (: x xs) ys)
(a.b + c.d)         ') => (+ (. a b) (. c d))
```

The tight forms are resolved first, then the spaced infix groups the results.

---

## Layout / Rune Poems

A free-floating rune (followed by a space) opens a layout context. Children
are gathered by indentation:

```rex
+ 3
  4
  5
```

Parses as `(+ 3 4 5)`. Poems nest naturally:

```rex
+ * 2 3
  * 4 5
```

The `*` forms are children of `+`.

Heirs appear when a sibling rune is at the same column as the opening rune:

```rex
~ a b c + foo bar
        + zaz
```

Parses as `(~ a b c (+ foo bar)(+ zaz))`. The two `+` forms are peers
at the same column, not children of `~`.

---

## Block Mode

A line ending with exactly one free rune opens a block. Indented lines
become items:

```rex
f x =
  a
  b
```

```rex
def foo(x, y):
    x += y
    return x
```

Any rune at end of line triggers this — not just `:` or `=`. Multi-line
infix works the same way:

```rex
result = 3 + 4
       + 5 + 6
       + 7 + 8
```

---

## Haskell-Like Style

Type signatures, function definitions, pattern matching:

```rex
map : (a -> b) -> [a] -> [b]
map f []     = []
map f (x:xs) = (f x : map f xs)

def quicksort xs:
    match xs:
        []     -> []
        (h:ts) ->
            less    = filter <h ts
            greater = filter >=h ts
            quicksort less ++ [h] ++ quicksort greater
```

Juxtaposition handles application. Tight infix handles `x:xs`.  Block
mode handles the indented match arms. Spaced infix handles `++`. None
of this required special design.

---

## Runic / Sire Style

The primary style of Sire, Rex's bootstrapping language. Rune poems build
computation vertically using `|` for application, `@` for let-binding,
`^` for loops, `?` for lambdas:

```rex
= exampleList
   ~   ? (sillyFn x y)
       | sz | weld [5 -4 3]
            | map add-x [1 #(x+4 * y)]
   ~   + user: %sol
       + repo: b"plunder"
       + path: /home/sol/r/plunder
```

The `~` rune opens a poem, `?` and `|` are nested poems within it.
`add-x` is a word (hyphens are part of the word here in old-style Sire —
in current Rex `-` is a rune so identifiers use `_`). `%sol` and the
path are quips.

---

## Nested Layout in Brackets

Layout and nesting compose freely:

```rex
= thunk
{ f:  ? (f x)
      ^ [_, _, _]
      | add @ fx (f x)
            | mul 3 fx
      | add x x

, x:  | add 3
      | add 3 4
}
```

A curly-brace record with `f:` and `x:` as keys, each followed by a
layout poem. The `@` inside the poem opens a nested let-binding. The `,`
separates record fields.

---

## String Types Side by Side

```rex
= examples
  # slugExample
      ' ## Introduction
      '
      ' Rex is to Plunder what s-expressions are to Lisp.
      '
      ' This is a multi-line slug string.

  + uglyExample
      ''
      ## Introduction

      Rex is to Plunder what s-expressions are to Lisp.

      This is an ugly string — arbitrary content, no escaping needed.
      ''
```

The slug version uses `'` on each line explicitly. The ugly string uses
`''` delimiters and contains the text verbatim including blank lines.
Both produce the same kind of string content; the choice depends on
aesthetics and whether the content contains tick characters.

---

## Configuration Formats

JSON-style:

```rex
{
  glossary: {
    title: "example glossary",
    glossDiv: {
      title: 'S,
      glossEntry: {
        id:        'SGML,
        sortAs:    'SGML,
        glossTerm: "Standard Generalized Markup Language",
      }
    }
  }
}
```

TOML-style (Rex can represent most TOML directly):

```rex
title = "TOML Example"

[owner]
name = "Tom Preston-Werner"
dob  = '1979-05-27T07:32:00-08:00

[database]
enabled = true
ports   = [8000, 8001, 8002]
```

---

## Domain-Specific Languages

A table schema DSL — entirely downstream convention, Rex just provides
the structure:

```rex
# deftable User []
- name/Text unique nullable=F
- age/Int  nullable initform=18
- description/Text
```

`#` invokes a macro, `-` introduces items, `/` is tight infix for type
annotation, `=` for default values. The Rex parser knows nothing about
what any of this means.

A macro definition written in Rex:

```rex
# defmacro if_let [[var cond] &body then else]
` @ $var $cond
  # if $var $then $else
```

The macro body itself is Rex notation — `@` for let, `#` for macro
invocation, `$` for splicing. This is what Lisp-style macros-as-library
look like in Rex.

---

## Comments

Comments use tick followed by a closing bracket:

```rex
') This is a line comment
'] This is also a line comment
'} And this too

f x = x + 1  ') inline comment
```

The three variants (`')`, `']`, `'}`) can carry different semantic
meaning by convention — regular comment, doc comment, pragma — though
that is for individual languages to define, not Rex itself.