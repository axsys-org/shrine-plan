# Foil context for language models

Use this file as operational context when reading, writing, or editing Foil in
this repository. It describes the currently implemented language and favors
the modern style exercised end-to-end by `src/foil/shrine.foil`.

Foil is an alpha, statically typed, expression-oriented language that compiles
to PLAN. Its surface syntax is Rex: indentation, alignment, parentheses, and
runic prefixes are syntax. Do not translate it mechanically into Haskell,
Rust, Scheme, or conventional brace-and-semicolon syntax.

When repository examples disagree, prefer, in order:

1. compiling code and tests;
2. `src/foil/shrine.foil` for the modern dot dialect;
3. `src/foil/demo.foil`, `bst.foil`, and `sept.foil` for established idioms;
4. `doc/getting-started.md`, `doc/foil-semantics.md`, and
   `doc/PAPERCUTS.md` for broader explanations.

The intentionally broken diagnostic fixtures live in `src/foil-bad/`. Do not
imitate forms from them.

## A complete small module

This example establishes the visual grammar and several preferred idioms:

```foil
+  outcome
  (@@ v)
  &  outcome/ok[v]
     outcome/err

  +  ok
    :  value=v

  +  err
    :  reason=quip

+  point
  :  x=nat y=nat

+  sum_to
  \  n=nat
  ^  nat
  %  i=nat n  acc=nat 0
  ?  (eq i 0)
     acc
  (_ (dec i) (add acc i))

+  unwrap_or
  \  fallback=nat r=outcome[nat]
  ^  nat
  ?>  (./ok n) r
      fallback
  n

+  demo
  '  Construct and functionally update a point.
  '  ?=  ((demo 4) 15)
  \  n=nat
  ^  nat
  =  p  (point n 1)
     q  p.set_x(n.inc)
  (add q.x (sum_to n))
```

There are no commas between arguments or fields. A declaration begins with
`+`; a function begins with `\`; `^` ascribes its result; the last expression
is the result.

## Layout and lexical habits

- Preserve the indentation already used by the surrounding file. Two spaces
  per nesting level is the dominant style.
- A rune such as `+`, `\`, `^`, `?`, `?>`, `=`, `|`, `|>`, `&`, or `:` opens
  a form. Its aligned and indented children determine that form's extent.
- Parenthesized values use prefix application: `(f a b)`, not `f(a, b)`.
- Square brackets construct rows: `[a b c]`.
- `/` separates namespace path segments: `bst/insert`, not `bst.insert`.
- `.` is field access and UFCS method syntax: `p.x`, `xs.fold(...)`.
- Names conventionally use `snake_case`. Hyphen is a rune, so do not invent
  kebab-case identifiers.
- A leading `'` line is a slug/doc comment. Prefer it over importing comment
  syntax from another language.

Foil is expression-oriented. Conditionals, matches, local bindings, loops,
casts, calls, and row literals all produce values.

## Modules, declarations, and namespaces

### Imports

The new `foil-new-env` driver uses nearest-definition precedence, then
later source-order ties, with transitive unprefixed visibility. It rejects
`[order=...]`. Prefixes change spelling, not defining-module identity.
See `doc/foil-new-env-imports.md` for the exact rules. `foil-new-env` is
the sole compiler. File callers use `foil-source`, which normalizes the
shared sources’ historical order annotations before invoking the driver.

```foil
-  sept
-  shrine_types
```

`- module` imports the named `.foil` module and merges its compiled entries.
Imports are resolved before declarations elaborate, wherever they appear.

An import nested beneath a declaration is also mounted at that namespace:

```foil
+  app
  -  vec
```

The canonical `vec` entries are then navigable through `app/vec` as well.
Mounted and canonical nominal types are the same type.

### Declarations

```foil
+  name
  BODY
```

Files are bags of declarations, not namespaces tied to the filename. Nested
declarations extend the path:

```foil
+  tree
  +  size
    \  t=tree
    ^  nat
    ...
```

The member is referenced as `tree/size`. A bodiless `+ name` is a pure
namespace. Existing namespaces, including imported and builtin namespaces,
may be reopened to add fresh members. Redefining an occupied entry is an
error.

### Functions and constants

```foil
+  max
  \  a=nat b=nat
  ^  nat
  ?  (lt a b)
     b
  a
```

Parameters are faced types: `name=type`. Public functions should normally
have an explicit result cast, especially when recursive or when returning a
relative variant.

A declaration may be a value instead of a function:

```foil
+  ten
  ^  nat
  (add 3 7)
```

Reference this as `ten`, not `(ten)`. In `shrine.foil`, `sov/new` is such a
nullary constant.

## Types and data

### Common type spellings

| Foil | Meaning |
| --- | --- |
| `nat` | natural number |
| `bool` | truthy `nat`, conventionally `0` or `1` |
| `quip` | tagged aura literal such as `'reason` |
| `row[nat]` | homogeneous builtin row |
| `box[v]` | generic application |
| `[x=nat y=nat]` | fixed anonymous structural row |
| `{\ nat}nat` | one `nat` argument returning `nat` |
| `{\ a b}c` | arguments `a`, `b`, returning `c` |
| `{\}unit` | no arguments, returning `unit` |
| `pail` | open union of all named row types in the namespace |

Specialization uses square brackets and is positional:

```foil
res[myth]
axal[uon[ass]]
row[[p=path q=axal[uon[ass]]]]
bst/insert[nat]
```

`=type` is an autonamed face. For example, `: =lock epochs=uon[nat]`
means `: lock=lock epochs=uon[nat]`.

`and : {\ bool bool}bool` is the named conjunction operation. Like `&&`,
it does not evaluate its right operand when the left operand is false.

### Sibling references

`%/name` resolves relative to the parent of the current declaration.
Inside `fs_foot/on_fact`, `%/on_bind` names `fs_foot/on_bind`.
At module top level, `%/name` names a module-level declaration.
Nested namespaces establish their own sibling scope; resolution does not
search ancestors if that exact sibling is missing. The syntax also works
in type annotations and with suffixes such as `%/helpers/read`.

### Named rows

`:` declares a nominal record:

```foil
+  lock
  :  data=nat shape=nat
```

Construct it in field order:

```foil
(lock 3 2)
```

Every named-row field gets generated methods:

```foil
l.data
l.set_data(4)
l.over_data(inc)
```

Named records also get `T/try_from_pail : {\ pail}maybe[T]`.
It returns `.some` for the record's exact nominal brand and arity, or
`.none` otherwise, preserving the complete record as the payload.
For a generic record use `box/try_from_pail[nat]`. Like `pail/as[T]`,
this checks nominal identity and arity; generic arguments are erased.
The helper name is reserved within a record declaration.

Updates are functional and return a new row. `.#` and `.%` parse but are not
implemented; always use `set_<field>` and `over_<field>`.

Only `:` and `&` mint nominal identity. A declaration whose body is merely a
type expression is a transparent alias:

```foil
+  path
  row[quip]
```

Alias values flow directly to and from the target type and inherit its method
set, after methods declared on the alias itself are considered.

### Anonymous structural rows

A bracketed value is a positional row:

```foil
[x y]
[]
```

In a type or pattern position, brackets describe a fixed anonymous row:

```foil
[state=sov signs=axal[sign]]
```

Anonymous rows have runtime head `0`. They are not interchangeable with a
named row having the same fields. They have no `.field`, `.set_field`, or
`.over_field` methods. Consume them through positional binding, pattern
matching, or bare-face lookup:

```foil
+  pair_sum
  \  pair=[x=nat y=nat]
  ^  nat
  (add x y)

+  destructure
  \  pair=[x=nat y=nat]
  ^  nat
  =  [a b]  pair
  (add a b)
```

Generic row methods such as `.size`, `.at`, `.fold`, `.weld`, and `.snoc`
operate on the array representation and remain available where their types
fit.

### Sums and variants

The modern `shrine.foil` style defines a sum from named member rows:

```foil
+  res
  (@@ v)
  &  res/known[v]
     res/null
     res/unknown

  +  known
    :  value=v

  +  null
    :

  +  unknown
    :
```

The older ad-hoc payload style (`& ($some v) $none`) still parses, but the
tree has migrated off it entirely. Do not write new code with it; declare
member rows and list them in the sum as above.

Prefer relative variants when the context determines the sum type:

```foil
(./known value)
.null
```

The parenthesized form carries a payload; the bare form is nullary.

`./tag` means “the member named `tag` of the expected sum.” It is resolved
from a function result cast, a call argument type, a row field type, or the
scrutinee type of a pattern. Without such an expected type, elaboration fails;
add a `^` cast/annotation or use a qualified constructor.

Relative patterns bind fields positionally and `_` ignores a field:

```foil
?  r
 > (./known value)  value
 > .null             0
 > .unknown          0
```

Nested patterns are valid, including rows of variants:

```foil
> [(./known x) (./known y)]  (equal x y)
```

Options in one sum must differ by constructor and arity. Runtime dispatch
cannot distinguish two same-tag, same-arity options by payload type alone.

### `pail`

Any named row can flow into `pail`; its nominal path is the runtime tag.
Payload-style variants and anonymous rows cannot. A `pail` match always needs
a fallthrough because its universe is open.

## Calls, fields, and methods

### Prefix calls

Calls are Lisp-style:

```foil
(add a b)
(saga (aeon yg (oath 0 0)) myth)
(bst/insert[nat] key value tree)
```

No commas or named argument syntax are used. A parenthesized call with fewer
arguments may be a partial application when its expected function type makes
that valid, as in `(add 3)`.

### The call rune `|`

`|` is a call written as a rune instead of parentheses: its children and
its heir become one application.

```foil
|  f
   x
   y
z
```

means `(f x y z)`. The first child is the function; every later child,
then the heir, is an argument. Children may also sit on the rune's own
line, so `|  f x y` with heir `z` is the same call.

This is what a call spread over lines looks like when an argument is
long enough that a parenthesized call would wrap badly, and — because
the heir is the rest of the body — it is also how a call takes
everything that follows as its final argument:

```foil
|  (if (eq a 0) b)
(_ (dec a) (inc b))
```

means `(if (eq a 0) b (_ (dec a) (inc b)))`. A head that is already a
call flattens into one application rather than nesting.

In a position with no heir, the children alone make the call: `(| f x y)`
is `(f x y)`. `|` with a single child and nothing to apply is that child.

A dotted head folds the operands into its last method segment:
`|  recv.method a b` is `recv.method(a b)` — the same UFCS call with the
receiver passed last, spread over lines.

`#` on a call head reverses the arguments: `(#str/cat a b)` is
`(str/cat b a)`, so a receiver-last builtin reads left to right without
UFCS. It is an involution (`##f` is `f`), it prefixes only a saturated
call (a partial `(#f a)` or a bare `#f` is a diagnostic), and it has no
tall form — `#f`, `#str/cat`, `#(expr)`, or as a `|` head.

Operand lines are siblings, one operand each, with one exception: a
`\` operand line followed by sibling lines takes them as its body
chain, the way a lambda line does at the top of a body, and closes the
operand list. The heir is still the call's last argument:

```foil
|  l.kid.uno
   \ k2 aw bw
   | axal/k[v] | pin | me k2 (unpin aw.held) | unpin bw.held
r.kid
```

is `l.kid.uno((\ k2 aw bw (axal/k[v] ...)) r.kid)`. Only `\` chains this
way; a `|` or `?` operand followed by a sibling line stays two operands.

### UFCS methods

Method calls are receiver-last. If `tree/insert` has parameters
`key value tree`, then:

```foil
tree.insert(key value)
```

means the equivalent of:

```foil
(tree/insert key value tree)
```

Method segments chain left to right:

```foil
s.ever_at(pax).x
pax.unders.any(predicate)
```

A bare name or a parenthesized expression may be the initial receiver:

```foil
(tailof xs).len
(xs.take(2)).cons(5)
```

Parenthesize a call result before using it as a receiver. Within method
arguments, ordinary expressions such as `f(x.y)` are fine.

Generic methods usually infer type arguments from the receiver and arguments.
Use explicit specialization on prefix calls when inference cannot determine
them.

## Control flow and pattern forms

### Truthy conditionals

`?` without `>` arms is an if/else expression:

```foil
?  condition
   when_true
when_false
```

The final expression is the fallthrough. Chaining gives an if/else-if shape:

```foil
?  first_condition
   first_value
?  second_condition
   second_value
default_value
```

Truth is numeric: zero is false and nonzero is true.

### Matches

`?` followed by `>` arms is a match:

```foil
?  value
 > (./ker saga)  (./some saga.myth)
 > (./nul _)     .none
```

Without a fallthrough, a closed sum match must be exhaustive. Add a trailing
expression for a non-exhaustive or open match:

```foil
?  [a b]
 > [.null .null]        .true
 > [.unknown .unknown]  .true
.false
```

Arm patterns must be row-shaped: named rows, anonymous rows, or variants.
Literal singleton matches are not implemented.

### Bind-or-else guards

`?>` matches a pattern and exposes its binders to the rest of the body. On
failure it returns the indented else value:

```foil
?>  (./some value) maybe_value
    default_value
body_using_value
```

Operationally:

- match succeeds: evaluate the following body with `value` in scope;
- match fails: evaluate `default_value` and skip the following body.

Guards can be chained and can appear after a cast, inside a loop, before local
bindings, or inside an arm body. `shrine.foil` uses them for option/result
unwrapping and early fallback.

### Pattern predicates and booleans

`?=(PATTERN VALUE)` returns `1` when the pattern matches and `0` otherwise.
`!?=` negates the test:

```foil
?=((./known _) result)
!?=(.null result)
```

Patterns may be nested. Predicate binders are not available outside the test;
use `?>` when the body needs a bound payload.

The boolean conveniences are:

```foil
.true
.false
!(condition)
(left || right)
```

They normalize to `1` or `0`. Do not invent `&&`; express conjunction with a
conditional, a helper, or a logically equivalent supported form.

### Pipelines

`|>` threads the accumulated value as the **first** argument of each stage:

```foil
|> raw
  prune_culls
  expand_culls(top idx)
```

This expands conceptually to:

```foil
(expand_culls (prune_culls raw) top idx)
```

A bare stage `f` means `(f accumulator)`. A call-shaped stage `g(a b)` means
`(g accumulator a b)`.

### Loops

`%` creates an immediately applied loop from `name=type init` pairs — each
is a typed parameter with its initial value (no `>` arms: `>` is match and
guard only):

```foil
%  i=nat n  acc=nat 0
?  (eq i 0)
   acc
(_ (dec i) (add acc i))
```

`(_ ...)` re-enters the innermost loop. Loop initializers are evaluated in the
outer scope, like parallel arguments. A loop normally infers its result from
non-recursive exits. Put `^ result_type` at the start of the loop body when a
recursive result is consumed non-tail or the bare self gate is used.

## Local bindings, lambdas, and recursion

### Sequential local bindings

Modern Foil accepts bare name/value pairs:

```foil
=  first   expression
   second  expression_using_first
body_using_both
```

Typed bindings use an annotated pattern:

```foil
=  item=nat expression
body
```

Positional destructuring uses a bracket pattern:

```foil
=  [state signs]  result
body
```

Bindings are sequential, not recursive: each value sees earlier bindings but
not itself or later bindings. The rune is historically named letrec in the
compiler, but source-level recursive local names are not supported.

A binding value may be a multiline function or control-flow expression:

```foil
=  walk
     \  todo=row[nat] acc=nat
     ^  nat
     ...
body_using_walk
```

### Inline lambdas

Inline lambdas are commonly inferred from the callee's function parameter:

```foil
items.any((\ item (gt item 0)))
```

Destructuring parameters is supported:

```foil
pairs.fold(0 (\ acc [key value] (add acc value)))
```

For a multiline lambda in a method call, `;` opens Rex block layout for the
argument; it is not a C-style statement terminator:

```foil
items.fold(0 ;
  \  acc item
  (add acc item))
```

Use explicit faced parameter types when there is no strong contextual type.

### Self recursion

`(_ args...)` calls the innermost enclosing `\` function or `|` loop. A
recursive function needs an explicit result cast:

```foil
+  count
  \  n=nat
  ^  nat
  ?  (eq n 0)
     0
  (inc (_ (dec n)))
```

`(_)` denotes the bare self function. This matters when recursion crosses an
inline lambda: inside that lambda, `_` would refer to the lambda itself. Capture
the outer self before entering it, as `shrine.foil` does:

```foil
=  me  (_)

children.fold(seed ;
  \  acc child
  (me child acc))
```

Do not recursively call a local helper by its binding name; use `_`, or
capture the outer self as shown.

## Generics

`(@@ ...)` directly within a declaration scopes variables over that
declaration and all descendants:

```foil
+  box
  (@@ v)
  :  value=v
```

`(@ ...)` introduces variables only for the following value body:

```foil
+  transform
  (@ v w)
  \  f={\ v}w x=v
  ^  w
  (f x)
```

Apply generic types and values with brackets:

```foil
box[nat]
(bst/insert[nat] key value tree)
```

UFCS normally infers generics from the receiver. Recursive generic types need
path-shaped arguments (named types, type variables, constants, or
applications of those); arbitrary function or structural types cannot always
be substituted into a recursive self path.

Compile-time constant parameters are faced entries in a generic variable
list:

```foil
(@@ k lt={\ k k}nat)
```

Instantiate both the type and constant: `map[nat lt]`. Constant arguments are
declared names, in-scope constant parameters, constant symbols, or nat
literals—not arbitrary expressions. When reopening a generic namespace for a
UFCS extension, repeat the original `@@` parameter names and order.

## Literals, equality, and documentation

### Literals

- `42` is a nat literal. Nonzero literals initially have singleton types;
  inference widens them where needed. `0` is the general nat case. A bare
  nat never flows into `str`/`sym` on its own; the explicit cast `^ str 3`
  claims the aura (and changes nothing at runtime).
- `"text"` is a packed-nat cord literal.
- `'reason`, `'%symbol`, and `'0x1f` are tagged quip literals.
- `'$name` in a type position is a constant symbol type.
- `.true` and `.false` are `1` and `0`.

Tape, span, and page literal families are not implemented. Cord literals
cannot directly contain a double-quote byte.

### Equality

`eq` is shallow PLAN equality. Use it for atoms and constructor-level tests.
For structured values, use `equal` for deep comparison or a domain-specific
comparator. `shrine.foil` uses `equal` to compare live `myth` payloads while
matching result constructors separately.

### Doc comments and doctests

Slug lines immediately inside a declaration attach documentation to it:

```foil
+  square
  '  Multiply a number by itself.
  '  ?=  ((square 4) 16)
  \  n=nat
  ^  nat
  (mul n n)
```

A slug beginning `?=` is a doctest consumed by the tooling. It is comment
content, distinct from the executable `?=(PATTERN VALUE)` predicate.

## Common failure modes

Before emitting Foil, check for these mistakes:

- Do not add commas, braces, `return`, `let`, `match`, `if ... then`, `=>`, or
  other syntax from a different language. Use `?` for idiomatic control flow;
  `(if condition yes no)` exists only as an ordinary builtin call.
- Do not use `.` for namespace qualification; use `/`.
- Do not use `.#` or `.%`; use generated `set_` and `over_` methods.
- Do not treat named and anonymous rows as structurally interchangeable.
- Do not assume a relative variant has enough type context. Add a result cast
  or explicit qualification when needed.
- Do not call a method receiver-first when translating it to prefix form;
  Foil UFCS passes the receiver last.
- Do not use shallow `eq` as deep structural equality.
- Do not make local `=` names self-recursive; use `(_ ...)`.
- Do not omit `^` from a self-recursive function.
- Do not match raw nat or symbol singleton values as arms; use truthy
  conditionals or row/variant wrappers.
- Do not invent a fallthrough-free `pail` match; `pail` is open.
- Do not assume all generics infer. Add explicit `[type ...]` arguments to a
  prefix call when diagnostics request them.
- Do not “simplify” aligned indentation casually. Layout changes can alter the
  Rex tree and therefore the program.

## Generation protocol for LLMs

When asked to create or change Foil:

1. Read the whole target declaration plus the declarations of every local type
   and method it uses. Search imported modules for exact names and signatures.
2. Decide the data identity deliberately: `:` for a nominal record, `&` for a
   nominal sum, `[... ]` for an anonymous positional product, or a bare type
   body for a transparent alias.
3. Write the public signature first. Add explicit parameter faces and a `^`
   result cast before writing the body.
4. Reuse the surrounding dialect. In modern code prefer `.tag`, `(./tag ...)`,
   `?>`, `?=`, bare `=` bindings, inline lambdas, and `|>` where they make the
   data flow clearer.
5. Keep relative variants inside a clear expected-type boundary. Qualify or
   annotate ambiguous constructions.
6. Use prefix calls for ordinary functions and UFCS for real receiver-oriented
   operations. Verify the receiver-last parameter order.
7. Model recoverable failure with an option/result sum. `error` has type
   `{\ pail}nat` and raises its named-row payload when evaluated. It never
   returns; `nat` is the declared result without a divergence type.
8. Add or update a slug doctest for small public behavior when practical.
9. Compile the real module. Import behavior cannot be validated by the
   in-memory `compile-inline` test helper.
10. Fix the earliest declaration error first; later diagnostics are often
    collateral failures.

## Compact syntax reference

```text
-  module                         import
+  name BODY                      declaration
:  x=type y=type                  named row declaration
&  option-a option-b              sum declaration
\  x=type y=type BODY             function/lambda
^  type BODY                      type/result ascription
(f a b)                           prefix call
|  f / a / b                      call rune: children + heir = (f a b ..)
(#f a b)                          the same call with the arguments reversed (## = id)
|  recv.m a / b                   call rune, dotted head: recv.m(a b)
f[type const]                     explicit specialization
[a b c]                           row value
[x=type y=type]                   anonymous row type/pattern
recv.field                        named-row field access
recv.method(a b)                  UFCS; receiver passed last
?  cond YES / NO                  truthy conditional
?  value / > PAT BODY ...         pattern match
?> PAT value / ELSE / REST        bind-or-else guard
<  PAT value / MAPPER? / REST     bind-or-propagate (either err/ok, maybe some/none)
?=(PAT value)                     pattern predicate
!?=(PAT value)                    negated pattern predicate
!value                            truthy negation
(a || b)                          truthy disjunction
=  name VALUE / BODY              sequential local binding
=  name=type VALUE / BODY         typed local binding
=  [a b] VALUE / BODY             positional destructuring
%  x=type init / BODY             loop (pairs; no > arms)
(_ args...)                       recurse/re-enter
(_)                               bare self function
|> seed / f / g(a b)              first-argument pipeline
.tag                              relative nullary variant
(./tag args...)                   relative payload variant
'  text                           doc/slug comment
```


### Native actor and snapshot operations

The raw builtins retain their runtime spellings:

- `Save : (@ a) {\ pin[a]}nat` writes a pinned snapshot root.
- `Spawn : (@ a) {\ {\ nat}a}nat` starts a compiled function with
  self handle `0` and returns a handle local to the spawning actor.
- `Send : {\ nat any}nat` sends a message without capabilities.
- `SendCaps : {\ nat any row[nat]}nat` transfers the listed actor
  capabilities with the message.
- `Recv : (@ message) {\ nat}[message=message caps=row[nat]]` receives
  from the current actor's mailbox; use `(Recv[my_message] 0)` and
  destructure the returned row.
- `CloseHandle : {\ nat}nat` drops a local actor handle; it does not
  stop the target actor.

Use explicit demand to sequence these operations. A handle number inside
the message is just data: transfer capabilities through `SendCaps` and use
the recipient-local handles returned by `Recv`. The chosen message type
is trusted, not checked by the transport; it must match the foot's protocol.
`Save` changes
the runtime snapshot root, so save the intended continuation, not an
arbitrary intermediate value. Adding these operations does not enable
automatic application persistence.

### Explicit demand (`;`)

Foil remains lazy by default. `= ;x=nat expr` and `= x ;expr` demand
one shared initializer before continuing; `(f ;expr)` demands the operand
at its call boundary even if `f` ignores it. `\ ;x=nat y=nat` demands `x`
when the original function body is entered, not when partially applied.
A tall `; expr` sequences that demand before the following body, and a
final `;expr` demands and returns the result. Branches and unused lazy
initializers keep their own evaluation boundaries. Demand uses runtime
`Seq`, so a row's fields remain lazy. Existing block-mode argument
separators retain their meaning.

The final codegen let is `L now value body` (0 lazy, 1 strict). `TC_DEMAND`
and `TC_BEFORE` are temporary typed nodes consumed by lowering. `F` and
`A` have no strictness metadata. IR_ENTRY version 2 rejects old persisted
IR caches; clear and rebuild them. `x/strict-let-check` verifies exact
traces against a memoizing interpreter and through the Foil compiler.


### Foil supervisor and feet

`helm.foil` owns the supervisor and the `feet/task` / `feet/gift`
protocol. `supervisor/handle` executes pure namespace transitions;
`supervisor/run` sequences registration, binding updates, and replies.
Bootstrap code sends `helm/card` or `supervisor/register` with a reply
capability. Each foot receives a dedicated endpoint that resolves relative
paths and delivers replies to that foot. It is not a write-permission policy.
Changed `%y` bindings arrive before the write acknowledgment.

`src/reaver/eden.rvr` compiles Eden and invokes it. `eden/main` boots the
namespace and registers `http_foot/run`. There are no Reaver Helm adapters,
`driver_in` / `driver_out` records, or duties. Registration is explicit and
in memory. Persistence, actor discovery/restarts, crew subscriptions, and
outbound move routing are not implemented. Incomplete cascades and kernel
outbound moves reject atomically.

Run `x/check foil:tests/supervisor foil:tests/http_foot` and
`x/eden --check` for the actual HTTP path. See `doc/helm-foil.md` and
`doc/foil-feet.md`.

### Shared builtin type core

`foil-type-core.rvr` owns the new builtin type declarations. Its single
TypeEntry table supplies both `default-type-world` and a type-only
`core-subject` containing new Scheme-backed TC_TYP entries. It is independent
of the elaborator, FFI implementations, and the old solver. `foil-new-elab`
uses this world and shares its aura vocabulary and builtin maybe brands.
Typed Reaver and every production builtin FFI signature now use this core
and the new kernel. `typed-reaver-types.rvr` adapts generic application and
shallow runtime shape checks without importing the old solver or compiler.
Typed metadata is `typed-reaver/v2`; stale v1 and old-algebra payloads are
rejected. Production still installs raw FFI values after static checking;
checked manifest wrappers remain available. Subject-to-world replay lives
in the shared core so those wrappers can resolve local declarations.
The elaborator, lowering, renderer, relocation, and inspection consumers
now accept the new representation. Inspection distinguishes sum/row/type
entries and walks semantic TC/type positions for reference edges; literal,
FFI, and const payloads remain opaque. The unused old `got-type` API is
removed; type consumers use the kernel or the explicit TC_TYP payload.
Subject span lookup reads TC/IR_ENTRY source spans.
`foil-types.rvr`, `foil-core-types.rvr`, and `foil-types-tests.rvr` have
been deleted. Guards reject their return to source modules, imports,
test inventory, or source-browser listings. Old type tags remain only in
stale-payload rejection tests. `newtype.rvr` remains the shared descriptor
and record-construction foundation, not a second Foil solver.
See `doc/foil-type-system-retirement.md`.

## Shared text and record utilities

Prefer Sept's `str/cat_all`, `str/join`, and `nat/show` to local string
accumulators. `str/split_byte` retains empty segments (including empty
input); `str/split_nonempty` drops zero-length spans. Both scan bytes.
`str/find` returns the first byte offset, `str/trim_ascii` trims boundary
bytes <= 32, `str/ascii_lower` folds A..Z, and `str/repeat` repeats a chunk.
Legacy nat-cord callers can use `cord/join`, `cord/split_byte`, and
`cord/split_nonempty`. Do not replace permissive app number parsers with
strict `nat/parse` without explicitly changing their contract.

`myth/path_at slot record` returns `maybe[path]`: use `.fall([])` only when
missing and root should mean the same thing. `myth/crew_at slot record`
returns an empty crew for absent or foreign pails. `myth/copy_slot slot src
dst` copies any present pail and leaves the destination untouched on absence.
These live in `lain_types`, not Sept. `mop/filter` takes a key/value predicate;
`mop/del` removes a comparator-equal key. Both currently rebuild in key order
(O(n log n)); neither changes the map's nominal representation.

## Rex bindings

Import `rex` for native-compatible surface and normalized syntax trees.
`rex/parse` parses a whole file into `either[any rex]`; `parse_block` keeps
the native single-block convention and `parse_normalized` explicitly applies
normalization. The builtin `rex` sum has all nine native variants and a
zero-headed `rex/source_span`; do not redeclare their constructor brands.
`rex/parse_blocks` returns `either[any row[rex]]` using reference block
boundaries; use it for documents such as Grove. Empty documents yield an empty
row. The existing `rex/parse` keeps compiler-style whole-file layout.

`rex/word`, `cord`, `rune`, `paren`, `path`, and `dot` build zero-span trees.
`children`, `map_children`, `walk`, and `rex/fold[value]` support inspection
and transformation. Walk is bottom-up and never revisits replacement trees.

Use surface `rex/open` nodes when printing prefix declarations. The native
printer renders normalized clear rune Nests in infix form; printing is not a
universal inverse of normalization. Feed normalized generated trees directly
to the compiler when possible. See `doc/foil-rex.md` and the executable
`test_fixtures/rex_example` for a parse/rewrite/generate/print example.

## Grove v2 syntax AST

`src/foil/grove.foil` parses Grove v2 with `grove/parse` or
`grove/from_blocks`, returning `either[grove/error grove/document]`.
It uses reference-style Rex blocks and preserves expressions, types,
and embedded Foil as surface Rex. It performs no resolution or lowering.
`! foil` consumes the rest of its enclosing body; do not put blank lines
inside that code. See `doc/grove-v2.md` and `src/grove/srs.grove`.
The Reaver Grove implementation is a separate, older design.

### Grove declaration backend

`grove_backend/compile root document ports` returns a located diagnostic or
canonical `[path myth]` publication records. The host adapter requires a
compiled publication in `prepare`, then `compile prepared previous lookup root
ast`. The predecessor reader participates in assigning every generated and
nested definition before elaboration. Imported artifacts retain their defining
moments, independently of source mount spelling.

Every nominal definition has a navigable `/sys/mold` record. Compiler bundles
and source-free exports live at the canonical publisher-owned paths returned by
`publisher_vocabulary/grove/*`. Native compiler artifacts preserve the prepared
plan and expected cases. `publish` checks and commits the complete batch through
the namespace journal. Compiler artifacts, Grove bundles and templates are
version three; stale products require rebuilding.

### Grove roles and system vocabulary

System slots are defined by `src/foil/sys/slots.foil` in the pinned system
publication. Grove resolves their records as namespace aliases with no code
exports. It does not republish a second `/sys` vocabulary.
`src/grove/value_codecs.grove` supplies publisher-owned wrappers around system
value carriers. SRS mounts its `sys/types/*` source imports onto those published
codecs; this does not relocate their identities. Time and duration retain their
existing scalar erasure and pails/n codecs.

`grove_roles.foil` preprocesses roles before backend indexing: required
properties, inherited `#with`, inclusive `#or`, and `#opt` become nominal
records, checked `from_myth`/`to_myth`, and a lash. Curbs contain exact definition
references, including each admitted constructor of a sum. Optional/OR fields
are `maybe` payloads. `extra` preserves unrelated slots. Publisher-owned role
schemas and exported codecs support source-free inheritance. Definitions and
instance creation are separate; SRS definitions publish under `/<self>/gov/srs`.

### Grove actions

`grove_actions.foil` runs before role generation. `@action` requires one
`#on` role, ordered required argument properties, and explicit Foil code.
Generated `run` checks the argument/receiver/result types. `apply` accepts
an argument myth and receiver myth, decodes through type and role codecs,
and returns `maybe[myth]`; invalid input or output is `.none`. Metadata at
`publisher_vocabulary/grove/action` stores the receiver path and argument schema. Nothing
is installed in the live namespace or `/sys/op`. Stored bundles support
source-free action imports. SRS now compiles through `finish` (six decls);
full compilation includes the tree declarations. Run
`x/check foil-grove-action-tests`. Tight annotations such as
`value=%/grade` are rewritten structurally by the backend.

### Grove norms

`grove_norms.foil` runs before actions and roles. Each `@norm` has one
`#here` quoted path pattern, `#with` roles, and inline role constraints.
It exports an `axal[myth]` alias, an `item` role module, `check`, `validate`,
and a descriptive `soma` spec. `publisher_vocabulary/grove/norm` stores segment and item
schemas. Literal path segments use the native path codec; captures use
`[name=@aura]`, with `@tas` mapped to `ts`. Validation checks every occupied
record, permitting empty myths only at matching strict prefixes. Empty
collections are valid. `validate` returns the first invalid relative path;
`check` returns the unchanged tree on success. No live installation.
Run `x/check foil-grove-norm-tests`. The first eight SRS declarations now
compile under `/gov/srs`. Sewn synthesis adds `queue` as the ninth.


### Grove sewn transformations

Use `@sewn`, not the former typo `@dyed`. `grove_sewn.foil` lowers an
explicit `get` body with one `#from` and one `#to` norm. Its module exports
unchecked `get`/`run` and checked `apply : axal[myth] -> maybe[axal[myth]]`.
`apply` validates the input, invokes the implementation, and validates the
output. `publisher_vocabulary/grove/sewn` stores both norm paths and their
compiled schemas (`source_schema`/`target_schema`), from the same norm modules
used by `apply`. Request-local adapters project through that pinned metadata,
not the latest norm declaration at an endpoint path. Older compiled sewn
metadata requires recompilation; missing or incompatible metadata fails closed.
External norms and sewn modules import through stored compiler bundles. Run
`x/check foil-grove-sewn-tests`.


### Grove templates and instance installation

`grove_trees.foil` lowers cord-named `@tree` declarations into relative
seeds in a versioned `grove_template`, stored at `publisher_vocabulary/grove/template` on
the published source root. Named declarations remain individual records
under that source root. Definition names and instance paths are separate
namespaces. The compiler validates all seed norms before publication.

Slot keys, `#like` source paths, and sewn code references are absolute
references to shared definitions. `tack: '@/y/%/cards` becomes a typed
`grove_instance_ref`; only these explicit local references rebase when
instantiating. Opaque user values and definition paths are never rewritten
by prefix matching. Templates retain contracts and existing ward/fresh
behavior. Live instance records carry no module bundles.

`grove_install/instantiate source version target state` resolves the
published template, checks its version and the previewed source x case,
and mounts at the target atomically through Pact. `publisher_vocabulary/grove/source`
on the instance root records the source version. Existing targets and
missing referenced code/input reject. The source template stays unchanged
and can be instantiated repeatedly. `grove_install/mount` is the lower
level publication/mount helper; the state supplies Pact, ward, and fresh.
Run `x/check foil-grove-tree-tests` for compilation, shared definitions,
independent instances, queue isolation, and contract validation.

### Eden with SRS

`x/eden --srs` compiles and publishes system vocabulary and SRS definitions
before serving HTTP. `eden_srs/compile` builds publication records without
live state; `eden_srs/publish` publishes them and `eden_srs/boot` combines
Eden boot with publication. No instance data is installed at `/gov/srs`.
Open `/ns/gov/srs`, enter an instance root, and click **Install instance**.
The UI can create multiple instances using the same published template.
`x/eden --srs --check` verifies definition publication, two HTTP installs,
stale/conflicting rejection, and the instance card and queue.
The default launcher remains base Eden. See `doc/eden-boot.md`.
