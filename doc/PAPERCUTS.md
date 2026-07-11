# Foil sharp edges

Foil is an alpha typed language that compiles to PLAN. This is a
present-tense guide to the parts most likely to surprise a new user. It is
not a history of fixed bugs.

For the happy path, start with `doc/getting-started.md`, keep
`doc/foil-semantics.md` nearby as the grammar reference, and use the modules
under `src/foil/` as executable examples.

## Start here

Run the compile buddy next to your editor:

```sh
x/buddy
```

Foil modules live at `src/foil/<module>.foil`. In buddy, select a module with
`:m <module>`, press enter to resync after edits, and use `:h` for commands.
Buddy recompiles changed modules and their importers, runs doctests, and
keeps REPL bindings between resyncs.

The most useful working examples are:

- `src/foil/demo.foil` for records, sums, matches, and methods;
- `src/foil/bst.foil` for recursive generics and doctests;
- `src/foil/map.foil` for compile-time constant parameters;
- `src/foil/sept.foil` for aliases, anonymous rows, higher-order functions,
  and larger recursive data structures.

Do not use `src/foil/axal.foil` as an implementation example. It is an
aspirational syntax fixture and intentionally does not elaborate.

## Testing and snapshots

The test snapshot can silently contain stale compiled modules. Restore the
pristine snapshot before every Foil test run:

```sh
cp snap/root-pristine.plan snap/root.plan
nix develop -c x/test foil-tests
```

Two details matter:

- The process exit code is not a reliable verdict. Search the output for
  `ERROR`.
- `x/test` deliberately loads parts of the module graph in separate wisp
  sessions. Do not collapse those stages into one session; the boundary
  avoids deterministic, order-dependent interpreter corruption.

The broader test chain is `foil-tests`, `forge-tests`, `buddy-tests`, and
`foil-async-tests`. Use the flake-provided runtime. Older wisp/enki binaries
can abort when actor operations used by parallel compilation are invoked.

## Source syntax that looks more conventional than it is

### Paths and function types

Paths use `/`, not `:` or `.`:

```foil
bst/insert
map/has[nat lt]
```

Function types list arguments followed by the result, separated with `;`:

```foil
{nat; nat}
{nat; nat; nat}
```

The first is `nat -> nat`; the second is `(nat, nat) -> nat`.

### Method receivers must be names

UFCS is receiver-last: `x.f(a)` resolves like `(f a x)`. The receiver must
currently be a word, not an arbitrary expression. Bind an intermediate
before continuing a chain:

```foil
=  > tmp (make_point 1 2)
tmp.x
```

`(make_point 1 2).x` is a parse error. Parenthesized rune expressions are
valid as arguments—`f(x.y)` is fine—the restriction is specifically on the
receiver at the start of a method chain.

### Record update uses generated methods

The `.#` and `.%` forms parse but are rejected. Every field `x` of a named
row gets ordinary methods instead:

```foil
p.x
p.set_x(7)
p.over_x(inc)
```

Updates are functional; they return a new row. Avoid field sets that make a
real field collide with a generated name—for example fields `x` and `set_x`
in the same record—because accessor generation does not diagnose that name
collision yet.

### Locals are sequential, not recursive

`=` local bindings are sequential lets. Each binding sees earlier bindings,
but not itself or later bindings:

```foil
=  > a 3
   > b (add a 1)
(mul a b)
```

For recursion, use `(_ ...)` to call the innermost enclosing function or
loop. A recursively called function needs an explicit `^` return type. A
`|` loop usually infers its result from non-recursive exits and needs `^`
only when the recursive result is consumed non-tail or the bare self value
is passed as a function.

### Literal families are different types

- `5` is a nat literal with singleton type `5` (`0` remains the general nat
  type).
- `"foo"` is a cord: a packed nat, also typed by its constant value.
- `'foo`, `'%hello`, and `'0x1f` are quips: tagged aura values inhabiting the
  builtin `quip` sum.
- `'$foo` in type position is a constant symbol type. In a faced position,
  rex currently needs parentheses: write `x=('$foo)`, not `x='$foo`.

Tape, span, and page literal shapes are not elaborated. Cord literal syntax
also cannot embed a double-quote byte; code that needs arbitrary bytes must
construct or transform the packed nat explicitly.

## Rows, sums, and matches

### Named and anonymous rows do not cross-flow

A declaration body beginning with `:` creates a named row:

```foil
+  point
  :  x=nat y=nat
```

Named rows have a branded runtime head, a constructor, UFCS field access,
and generated update methods.

`[x=nat y=nat]` in a type-use position is an anonymous structural row. Its
runtime head is `0`. It has no field methods and is not interchangeable with
a named row that happens to have the same fields. Bind or match it and use
bare faces:

```foil
=  > r (fit path tree)
(add x y)                 ' x and y come from r's anonymous row type
```

Generic row operations such as `.size`, `.drop`, and `.weld` still work on
anonymous rows because they operate on the array representation; `.x`,
`.set_x`, and `.over_x` do not.

Bare-face lookup is first-match, so a face from an anonymous-row local can
shadow an outer local with the same name.

### Match arms are row-shaped

Foil lowers matches by runtime constructor and arity. Arm patterns must
narrow to row-shaped values: named rows, anonymous rows, or variant rows.
You cannot currently match directly on singleton nat or symbol constants.

Fall-less matches over closed sums must be exhaustive. A match on `pail`
always needs a fallthrough because `pail` is the open universe of named rows
in the namespace.

Sum options must differ by constructor or arity. Two options with the same
tag and arity but different payload types are rejected because runtime match
dispatch cannot distinguish them.

### `pail` is not an anonymous union

Any named row can flow into `pail`; its branded path is the tag. Sum variants
and anonymous rows cannot. Wrap those values in a named row when they need to
cross a `pail` boundary.

## Generics and specialization

### Explicit and inferred specialization coexist

Prefix calls can be specialized explicitly:

```foil
(bst/insert[nat] key val tree)
```

Method calls usually infer from the receiver and arguments:

```foil
xs.map(bump)
```

If a direct generic call reports that explicit specialization is required,
add the bracketed arguments. Inference is deliberately narrower than a
general constraint solver.

### Recursive generics need path-shaped type arguments

Nominal type applications are encoded as paths. Recursive generics such as
`list` and `bst` therefore require arguments that have a path representation:
named types, type variables, constants, or applications of those. Function
types and anonymous structural rows can specialize non-recursive generics
structurally, but cannot be substituted into a recursive self path.

### Const generics are more restrictive

A declaration such as:

```foil
(@@ k lt={k; k; nat})
```

has a type parameter `k` and a compile-time constant `lt`. Instantiate it as
`map[nat lt]`. Const arguments must be declared names, in-scope const
parameters, constant symbols, or nat literals; arbitrary expressions are not
hoisted automatically. Type arguments to a const-parameter generic must also
be path-shaped.

Members with const parameters require explicit specialization unless the
receiver's type already carries the constants. Thus `m.insert(k v)` can infer
from `m : map[nat lt]`, while a prefix reference generally needs
`map/insert[nat lt]`.

### Reopened generic namespaces correlate parameters by name

When another module reopens a generic namespace and adds a member intended
for method dispatch, repeat the original `@@` parameter names and order.
Explicit calls are positional, but receiver-driven UFCS correlates the
receiver's arguments with the extension member by parameter name.

### Only rows and sums mint nominal identity

`:` and `&` declarations create new nominal types. A `+` declaration whose
body is another type expression is a transparent alias: values flow both
ways, and method lookup falls through to the target after checking methods
declared on the alias itself.

## Equality and failure

The builtin `eq` is PLAN's shallow equality. It is safe for atoms, but on
structured values it can report equal merely because the outer heads match.
For example, two quips with the same aura but different payloads are not a
safe use of `eq`. Use a domain comparator such as `eq_iota`/`eq_pith`, or
write structural equality for the type.

Foil has no general crash/abort primitive for user code. Libraries normally
represent partiality with an option/result sum or accept an explicit default.
Do not design an API around an invariant-violation escape hatch that the
language cannot express.

## Modules, imports, and tooling discovery

Files are bags of declarations, not namespace boundaries. A module can reopen
multiple roots, and another module can add members beneath an imported or
builtin root. Collision checking happens within a compilation/import graph;
two unrelated modules that extend the same root are not globally reconciled
until something imports them together.

Imports are resolved by the file-backed compiler. The in-memory
`compile-inline` helper used by tests cannot import modules; write a real
fixture under `src/foil/` when import behavior matters.

Source names are relative, but compiled declarations live under a namespace
root (`/boot` for the normal compiler image). If you inspect raw runtime row
heads or internal paths, expect rooted names even though source code spells
`point`, not `/boot/point`.

Buddy and Forge do not discover every `.foil` file from the directory. Their
initial module set is seeded by the hardcoded `forge-mods` roster, then
expanded through transitive imports. A module outside that graph can compile
when imported but will not automatically appear in browsing or doctest
reports. Add it to the roster when it should be a first-class tool module.

## Reading diagnostics

A module compile recovers at declaration granularity. It reports every failed
declaration, but only the first error inside each declaration. Declarations
that depend on a failed declaration can then report collateral errors. Fix
the earliest/root declaration first and recompile before investigating every
downstream message.

Most user-triggerable failures have located, structured diagnostics. A raw
tuple or internal tag is still a compiler-quality bug rather than intended
user-facing behavior; preserve the source snippet and add it to the crash
corpus when reporting it.

## Current unsupported forms at a glance

- recursive local `=` bindings;
- arbitrary expressions as method receivers;
- `.#` and `.%` updates (use generated `set_`/`over_` methods);
- constant/literal match arms that are not row-shaped;
- tape, span, and page literals;
- structural arguments to recursive or const-parameter generics;
- arbitrary expression values as const-generic arguments;
- a general user-level crash/abort primitive;
- automatic directory-wide discovery in Buddy and Forge.
