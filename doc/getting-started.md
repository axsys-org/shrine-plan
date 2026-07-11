# Getting started with Foil

Foil is a typed language that compiles to PLAN. Modules live in
`src/foil/<name>.foil`; the compiler, REPL, and test harness you'll
actually sit in front of is **buddy** — a resident terminal session
meant to live next to your editor:

```
x/buddy
```

Save a `.foil` file and press enter in buddy: it recompiles what
changed (including anything that imports what changed), runs the
module's doctests, and prints located diagnostics when it doesn't
compile. `:h` lists the commands; `name = expr` binds REPL variables;
bare expressions evaluate against the focused module.

## A module

```
-  vec                          ;; import: merge vec.foil's subject
+  maybe_nat
  &  ($some nat)                ;; a sum of variants
     $none
+  point
  '  A point.  Doc lines start with ' and attach to the decl.
  :  x=nat y=nat                ;; a named row (record): fields are faces
+  norm
  '  ?=  ((norm (point 3 4)) 25)
  \  p=point                    ;; lambda: typed parameters
  ^  nat                        ;; return-type cast
  (add (mul p.x p.x) (mul p.y p.y))
```

- `+ name` declares; nesting `+` inside a `+` declares children —
  `+ bst + insert` is `/bst/insert`, referenced as `bst/insert`.
  Files are bags of declarations: they may contribute to many roots,
  and any `+` namespace can be reopened later in another file.  A
  bodiless `+ name` is a pure namespace and only its children add
  entries.
- `- name` imports: the named module's compiled entries merge into
  yours at their own paths. Inside a `+` the import is additionally
  *mounted* — `+ app  - vec` also makes `app/vec` a name for `vec`,
  and types written either way are the same nominal type. Imports
  resolve before any declaration elaborates, wherever the rune sits;
  colliding declarations and import cycles are compile errors.
- Reopening adds fresh members under an existing root, including
  builtins.  Redefining the root itself with a body, redefining an
  imported member, or declaring the same path twice in one file is a
  compile error.  Nested reopenings spell the path directly:
  `+ quip  + inner  + frob`.
- Doc lines (`'`) attach to the declaration. A doc line of the form
  `?=  ((expr) expected)` is a **doctest**: buddy runs it on every
  resync.

## Values and types

- `nat` is the number type; literals are `nat`s. `[1 2 3]` is a row;
  `row[nat]` its type. `{nat nat; nat}` is a two-argument function
  type. `=` inside a bracket faces a field: `[x=nat y=nat]`.
- `:` declares a **named row** (record): `:  x=nat y=nat` as a decl
  body. A lone `:` is the empty row. Named rows get constructors,
  UFCS face access (`p.x`), and generated `set_x`/`over_x` methods;
  their runtime head is the declaration path.
- `[x=nat y=nat]` in a **type-use position** (a `^` cast, a parameter,
  a spec argument like `row[[p=row[quip] q=v]]`, a match-arm pattern)
  is an **anonymous structural row**: constructor head literally `0`
  (the PLAN row rep), exact arity, faces transparent for nesting.
  Anonymous rows are **outside UFCS** — no `.face`, no `set_`/`over_`
  — consume one by binding it and using the bare face names
  (`=  > r (fit pax fat)` then `rem`/`fil`), by matching
  (`> [x=nat y=nat] ...` binds the pattern's faces; a binder
  `> r=[x=nat y=nat]` also names the whole row), or from the host via
  `Ix`. Construct
  them with row literals: `[pax fat.fil]`. Named and anonymous rows
  never cross-flow (their runtime heads differ). Bare-face lookup is
  first-match; an anonymous field can shadow an outer local.
- `&` declares a sum of options; `($tag payload...)` constructs a
  variant; options must differ in constructor or arity (colliding
  options are a compile error — matches dispatch on head+arity).
  Sums stay nominal: there are no anonymous unions — name them.
- Every compilation has a **namespace root** — the boot process is
  `/boot` — so a named row's runtime head is a real namespace path
  (`/boot/point`). Source names stay relative; a local declaration
  shadows a builtin of the same name. The builtin **`pail`** type is
  the open union of every named row in the namespace — the head IS
  the tag. Any declared row value flows into a `pail` position;
  matching a pail dispatches by branded head and always needs a
  fallthrough (the universe is open). Sums and anonymous rows do not
  inhabit `pail` — wrap them in a record.
- Constructors are the type name applied: `(point 3 4)`.
- Only `:` and `&` mint a new nominal type. A `+` declaration whose
  body is a type expression is a **transparent alias** — `+ path`
  with body `row[quip]` makes `path` interchangeable with `row[quip]`
  everywhere: same runtime rep, values flow both ways, row methods
  (`p.size`) and face accessors unfold through it. An alias namespace
  is reopenable, and its own declared methods win before the target's
  (`p.depth` then `p.size`). See `path` in `src/foil/sept.foil`.
- Generics declare variables with `(@ v)` — or `(@@ v)` directly in a
  `+` to scope the variable over the declaration and every descendant
  (each member drops the variables it doesn't use). Apply with
  brackets:

```
+  box
  (@ v)
  :  val=v
+  use
  \  b=box[nat]
  ^  nat
  b.val
```

  At call sites you can specialize explicitly — `(bst/insert[nat] k v t)`
  — but method-position calls usually infer: `xs.map(bump)`,
  `xs.filter(even)`, `xs.fold(addf 0)` need no annotations.
- Literals know their values: `5 : 5` (a singleton nat that nests
  under `nat`); `'$foo` is the constant symbol type, inhabited by the
  cord `"foo"`, and usable as a const-generic argument
  (`labeled['$foo]`). Inference widens constants, so `(if x 1 2)` is
  still a `nat`.
- The autonamer names a face after its type: `=point` is
  `point=point`, `=foo/bar` is `foo=foo/bar` — handy in rows and
  parameter lists.
- A faced entry in the variable list declares a **compile-time
  constant**: `(@@ k lt={k; k; nat})` gives every member an ordering
  function `lt` without it being passed at runtime. Instantiate with
  the constant alongside the type arguments — `map[nat lt]` — using a
  declared name or a nat literal; each distinct constant compiles its
  own specialized members. See `src/foil/map.foil`.
  If another file reopens a generic namespace and wants method-call
  dispatch on its extension members, repeat the same `@@` names used by
  the original namespace; explicit calls like `map/has[nat lt]` are
  positional and do not depend on those names.

## Control

- `?` matches on a scrutinee; `>` arms bind a narrowed pattern; a
  trailing value is the fallthrough. Without a fallthrough the match
  must be exhaustive (checked).

```
  ?  m
   > ($some v=nat)  v
   > $none          0
```

- `= > name expr` binds locals (letrec) above a body.
- `(_ args...)` is self-recursion — the enclosing function calls
  itself. It needs a `^` return cast on the function.
- `|` opens a loop: each `>` arm declares a typed loop parameter with
  its initial value, the body follows, and `(_ ...)` re-enters the
  loop (the innermost `|` or `\`) with new parameter values. No `^`
  needed — the loop's type is the join of its non-recursive exits:

```
+  countdown
  \  n=nat
  ^  nat
  |  > foo=nat n
  ?  (eq 0 foo)
     foo
  (_ (dec foo))
```

  Arms chain on one line (`|  > i=nat n  > acc=nat 0`) or stack on
  separate lines. The loop body may use enclosing locals freely (they
  are captured), and a `^` as the loop's first body form types the
  self-call when its result is consumed non-tail (e.g. factorial's
  `(mul i (_ (dec i)))`).

## Methods (UFCS)

`recv.meth(args)` looks up `meth` under the receiver's type path with
the receiver as the last argument: `t.insert(k v)` on a `bst[v]` is
`bst/insert`. Rows and nats have method sets too: `xs.size`,
`xs.drop(1)`, `xs.rev`, `n.add(1)`, `n.lt(m)`. Zero-argument methods
chain bare: `n.l.size`. Reopened namespaces participate in the same
lookup, so an extension member such as `map/has` can be called as
`m.has(k)` once its file is imported. (Receivers must currently be
names — bind a `= > tmp (...)` to chain off a call.)

## Reading diagnostics

Errors are located and collected — a compile reports every failed
declaration, not just the first:

```
in module app:
  the module does not elaborate
    in /app/norm:
      unbound reference /poimt
        at line 12, col 3
```

`want:`/`got:` lines show types in source syntax. Parse errors point
at the offending form; wf errors name the offending path.

## Running tests

```
cp snap/root-pristine.plan snap/root.plan   # always: snapshots go stale
nix develop -c x/test foil-tests
```

Exit codes lie; grep the log for `"ERROR"`. The full chain is
`foil-tests`, `forge-tests`, `buddy-tests`, `foil-async-tests`.
`x/forge` serves the same live environment over HTTP.

## Sharp edges (known, alpha)

See [PAPERCUTS.md](../PAPERCUTS.md) for the current onboarding guide to
workflow traps, unsupported forms, type-system constraints, and tooling
limitations. It is the single maintained list; historical limitations are
not kept there after they are fixed.

The corpus under `src/foil/` (bst, demo, vec, vecapp) is the best
reference for idiomatic shape; `doc/foil-semantics.md` is the structural
grammar.
