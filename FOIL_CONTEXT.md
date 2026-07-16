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
  |  > i=nat n  > acc=nat 0
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
| `{nat; nat}` | one `nat` argument returning `nat` |
| `{a; b; c}` | arguments `a`, `b`, returning `c` |
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

`|` creates an immediately applied loop with typed parameters and initial
values:

```foil
|  > i=nat n  > acc=nat 0
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

Typed bindings use `>` arms:

```foil
=  > item=nat expression
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
  \  f={v; w} x=v
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
(@@ k lt={k; k; nat})
```

Instantiate both the type and constant: `map[nat lt]`. Constant arguments are
declared names, in-scope constant parameters, constant symbols, or nat
literals—not arbitrary expressions. When reopening a generic namespace for a
UFCS extension, repeat the original `@@` parameter names and order.

## Literals, equality, and documentation

### Literals

- `42` is a nat literal. Nonzero literals initially have singleton types;
  inference widens them where needed. `0` is the general nat case.
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
7. Model failure with an option/result sum. Foil has no general user-level
   crash/abort primitive.
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
f[type const]                     explicit specialization
[a b c]                           row value
[x=type y=type]                   anonymous row type/pattern
recv.field                        named-row field access
recv.method(a b)                  UFCS; receiver passed last
?  cond YES / NO                  truthy conditional
?  value / > PAT BODY ...         pattern match
?> PAT value / ELSE / REST        bind-or-else guard
?=(PAT value)                     pattern predicate
!?=(PAT value)                    negated pattern predicate
!value                            truthy negation
(a || b)                          truthy disjunction
=  name VALUE / BODY              sequential local binding
=  > name=type VALUE / BODY       typed local binding
=  [a b] VALUE / BODY             positional destructuring
|  > x=type init / BODY           loop
(_ args...)                       recurse/re-enter
(_)                               bare self function
|> seed / f / g(a b)              first-argument pipeline
.tag                              relative nullary variant
(./tag args...)                   relative payload variant
'  text                           doc/slug comment
```
