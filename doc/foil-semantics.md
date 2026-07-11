Foil:

A foil module is parsed from a file, then refined by later passes
(e.g. docstring association from preceding SLUGs). This reference
covers only the structural AST.

MODULE := (DECL | IMPORT)[]
DECL := (+ NAME VALUE? (DECL | IMPORT)[])
IMPORT := (- NAME[])
' merge the named modules' compiled subjects into this one.  Imports
' resolve before any declaration elaborates, wherever the rune sits.
' Inside a + the imported entries are additionally *mounted* under that
' declaration's path (navigation only): types written through a mount
' normalize to the canonical name, so `app/vec` and `vec` are the same
' nominal type.  Identical entries arriving twice (diamond imports)
' dedupe; a differing entry at an occupied path — including one of this
' module's own declarations — is a collision diagnostic, and cyclic
' imports are a diagnostic naming the module.

Files are bags of declarations, not namespaces.  A `+ name` opens the
absolute `/name` namespace; the same namespace may be reopened in any
file, under any imported namespace, under a builtin namespace, or with
no prior definition.  A bodiless declaration is therefore a pure
namespace: it emits no root entry by itself, but its child declarations
still land at their absolute paths.  This is how files add members to
existing namespaces without redefining the original root.

Reopening merges member additions by path.  Redefining an imported root
with a body, redefining an imported member, or declaring the same path
twice in one file is a collision diagnostic; adding a fresh child under
an imported or builtin root is allowed.  Nested reopening is just nested
paths:

```
+  quip
  +  inner
    +  frob
      \  q=quip
      ^  nat
      1
```

`@@` declarations are local to the reopening site.  Method-call
dispatch matches a receiver's type arguments to an extension member's
declared parameters by name, in the parent namespace's order.  Extension
members intended for UFCS on a generic namespace should therefore reuse
the original `@@` names; explicit specializations such as
`map/has[nat lt]` are positional and work either way.

' The following runes are available to define values.
' Throughout, JUXT is written infix: (X JUXT Y) is the adjacency node
' for X placed immediately to the left of Y.

FISH := (> type=TYPE VALUE)
' associate a type with a value -> used for pattern matching, and variable binding

CONDITIONAL_FALLTHROUGH := ((? scrutinee=VALUE FISH[]) JUXT VALUE)
' conditional with fallthrough (FISH[] are the cases, trailing VALUE is the default)
CONDITIONAL_EXACT := (? scrutinee=VALUE FISH[])
' conditional without fallthrough
CONDITIONAL := CONDITIONAL_FALLTHROUGH | CONDITIONAL_EXACT

TYPE_VAR_DECL := ((@ vars=(WORD | CONST)[]) JUXT body=VALUE)
CONST := (= name=WORD type=TYPE)
' introduce type variables (bare words) and compile-time-constant
' parameters (faced, typed: lt={k; k; nat}) into `body`.  A variable
' the elaborated type never mentions is dropped (no quantifier).
' Constants are supplied at instantiation alongside type arguments
' (map[nat lt]) as declared names or nat literals; the reference is
' baked at compile time — nothing is passed at runtime.

SCOPED_VAR_DECL := (@@ vars=(WORD | CONST)[])
' identical to @, but directly inside a + it scopes over that
' declaration AND every descendant declaration, each of which drops
' the variables it does not use.

LAMBDA := ((\ TYPE[]) JUXT VALUE)
' declare a lambda

LETREC := ((= FISH[]) JUXT VALUE)
' declare a letrec (if variables are not truly recursive, then just let)

LOOP := ((| ARM[]) JUXT VALUE)
' `|  > foo=nat 3` — an immediately-applied lambda: each > arm declares
' one loop parameter (faced type) with its initial value, the heir is
' the body, and (_ ...) re-enters the loop (innermost | or \ wins).
' Inits elaborate in the outer scope (parallel binding — one call).
' No ^ cast needed: the self-call types as TBOT and joins away, so the
' loop's type is the join of its non-recursive exits; write ^ as the
' body's first form when the recursive result is consumed non-tail
' (or when passing the bare self value (_) as a gate).  Arms chain on
' one line (`|  > a=nat 1  > b=nat 2`) or stack on separate lines.

CALL := (PAREN VALUE[])
' (foo bar baz) -> lisp style fn application

APPL := (WORD JUXT CALL)
' foo(bar baz) segment of a UFCS method call
WING := WORD | APPL
' segment of UFCS syntax
UFCS_GET := (. var=WORD WING)
' get inside i.e. foo.bar
UFCS_PUT := (.# var=WORD APPL)
' put inside i.e. foo.#bar(baz)
UFCS_OVER := (.% var=WORD APPL)
' set i.e. foo.%bar(baz)
UFCS := UFCS_GET | UFCS_OVER | UFCS_PUT

FACE := (= WORD TYPE)
SPECIALISE := (WORD JUXT (BRACK TYPE[]))
' explicitly instantiate a polymorphic value or nominal type
STRUCT_FUNC := (CURLY % TYPE[])
' last type is the return, all others arguments
STRUCT_ROW := (BRACK TYPE[])
' anonymous structural row: constructor head 0 (the PLAN row rep),
' exact arity, faces transparent for nesting; OUTSIDE UFCS — no face
' accessors, no set_/over_ — consumed by binding + bare-face lookup,
' match arms (key (0, arity)), or host-side Ix.  Named and anonymous
' rows never cross-flow.  (Plain-curly rows are retired: curly is
' function types only.)
DECL_ROW := (: FACE[])
' a NAMED row (record) declaration body; a lone : is the empty row.
' The cstr is branded with the declaration path at insert; named rows
' get constructors, UFCS face access, and set_/over_ methods.
'
' TYPE ALIASES: only : and & mint nominal identity.  A + declaration
' whose body is a type expression (+ path row[quip], + myn nat) is a
' transparent ALIAS: the entry stores the target type, references
' resolve through it structurally (values flow both directions, no
' wrapper, no brand), and generic instantiations at the alias and at
' the target interoperate.  UFCS on an alias-typed receiver checks the
' alias's own declared methods first (an alias namespace is reopenable
' like any other), then unfolds to the target's method set — so an
' alias of row[quip] keeps .size/.drop/.weld and an alias of a named
' row keeps its face accessors.
'
' COMPILATION ROOTS: every compilation has a namespace root; the boot
' process (the compiler's builtins and everything compiled against
' them) is fiat /boot.  Declared entries key and brand under the root
' (/boot/uon/node), so a nominal value's runtime head is a real
' namespace path.  Source references and tooling names stay relative
' and resolve rooted-first (a local declaration shadows a substrate
' builtin of the same name); the primitives themselves (nat, uint,
' unit, quip, row, list, either, pail) are substrate — unrooted.
'
' PAIL: the builtin type `pail` is the open union of every nominal
' row type in the namespace — the path in the head constructor IS the
' tag.  Any declared row value flows into a pail position (sums do
' not: their heads are option tags, not brands; anonymous rows do
' not: head 0).  A match on a pail dispatches by branded head and
' always requires a fallthrough — the universe is open.  pail joins
' absorb members and meets refine to the member.
TYPE := WORD | FACE | STRUCT_FUNC | STRUCT_ROW | SPECIALISE
' a bare WORD is a type constructor or type-variable reference

LITERAL := TRAD | QUIP | UGLY
NAME := WORD
COMMENT := REX_COMMENT | SLUG
' COMMENT is consumed by a separate pass (docstring association); it does
' not appear in the structural value/decl tree.

VALUE := CONDITIONAL | LAMBDA | LETREC | LOOP | TYPE_VAR_DECL
       | CALL | UFCS | LITERAL | NAME

## Spec vs implementation

Everything above describes the *surface language*; the parser
(`foil-sast.rvr`) accepts all of it.  The elaborator implements a
subset.  As of this writing:

**Implemented end-to-end** (parse → elaborate → lower → run):
lambdas (`\`), casts (`^`), conditionals (`?`, both match and truthy-if
forms; matches without a fallthrough must be exhaustive),
self-recursion (`(_ ...)`), rows, variants, unions (`&`), nominal types and
constructor calls, UFCS *get* (`.`), explicit specialization
(`name[ty]`), type variables (`@`), local bindings (`=`, sequential —
each binding sees the previous ones; recursive local bindings are not
supported), `'`-prefixed **quip literals** (typed by the builtin
`quip` aura sum from `quip.rvr`; the runtime value is the tagged pair
from `parse-quip`, matchable with `?` arms like `($ta t=nat)`),
**named row declarations** (`:  foo=bar baz=qux`; the old `$  [..]`
spelling is a located parse error pointing at the migration), and
**anonymous structural rows** (`[..]` in type-use positions — casts,
parameters, spec arguments like `row[[p=row[quip] q=v]]`, and match
arms — `> [a=nat b=nat]` binds the pattern's own faces for the arm
body, `> r=[a=nat b=nat]` additionally names the whole row; bare faces
resolve through a local bound to an anonymous row, first match wins),
and **loops** (`|` — the LOOP form above; lowering lambda-lifts the
loop over any enclosing locals its body captures, and the self slot
re-supplies the captured values on `(_ ...)` re-entry), **compilation
roots** (/boot; see DECL_ROW notes), the **pail universe**
(`pail`; open union of nominal rows, branded-head dispatch, mandatory
fallthrough), and **type aliases** (a `+` decl with a type-expression
body; see DECL_ROW notes).

**Functional record update** uses plain `.` UFCS: for every face `x` of
a named row type, elaboration generates `v.x` (get), `v.set_x(new)`
(replace), and `v.over_x(fun)` (apply a function to the field).

**Parsed but rejected by the elaborator** (reported per-declaration with
source locations by the pre-elaboration scan in `foil-elab.rvr`):

- UFCS_PUT (`.#`) and UFCS_OVER (`.%`) — superseded by the generated
  `.set_<face>(val)` / `.over_<face>(fun)` methods
- tape, span, and page literal shapes (quip and cord literals are implemented)

`src/foil/bst.foil` and `src/foil/demo.foil` stay within the
implemented subset and are compiled and executed by the test suite.
`src/foil/axal.foil` is **aspirational**: it uses `.%`/`idx!`,
per-declaration type variables `!`, and other planned syntax, and does
not elaborate yet.

## Implementation map

Foil source is parsed as Rex, then immediately normalized to the three Rex
forms consumed by the Foil parser:

1. `rex:ParseRexNorm` produces normalized `leaf`, `nest`, and `juxt` nodes.
2. `foil-rex.rvr` provides the normalized Rex predicates and small accessors
   used by the parser.
3. `foil-sast.rvr` maps normalized Rex into the stable Foil SAST tags defined
   in `foil-surface.rvr`.
4. `foil-elab.rvr` elaborates SAST values and modules into typed Foil TC
   entries over the subject environment from `foil-builtins.rvr`.
5. `foil-lower.rvr` lowers typed Foil TC entries into executable PLAN values.

The public compatibility modules remain `foil-sast.rvr` for surface parsing
and `foil.rvr` for parsing, elaboration, default builtins, compilation, and
REPL helpers.
