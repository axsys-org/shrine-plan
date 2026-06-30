Foil:

A foil module is parsed from a file, then refined by later passes
(e.g. docstring association from preceding SLUGs). This reference
covers only the structural AST.

MODULE := DECL[]
DECL := (+ NAME VALUE DECL[])

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

TYPE_VAR_DECL := ((@ vars=WORD[]) JUXT body=VALUE)
' introduce type variables `vars` into `body`

LAMBDA := ((\ TYPE[]) JUXT VALUE)
' declare a lambda

LETREC := ((= FISH[]) JUXT VALUE)
' declare a letrec (if variables are not truly recursive, then just let)

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
STRUCT_ROW := (CURLY TYPE[])
' anonymous product type
TYPE := WORD | FACE | STRUCT_FUNC | STRUCT_ROW | SPECIALISE
' a bare WORD is a type constructor or type-variable reference

LITERAL := TRAD | QUIP | UGLY
NAME := WORD
COMMENT := REX_COMMENT | SLUG
' COMMENT is consumed by a separate pass (docstring association); it does
' not appear in the structural value/decl tree.

VALUE := CONDITIONAL | LAMBDA | LETREC | TYPE_VAR_DECL
       | CALL | UFCS | LITERAL | NAME

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
