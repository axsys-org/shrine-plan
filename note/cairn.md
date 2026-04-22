
# cairn reference

## overview

cairn is a rex-based language whose surface syntax is organized around **runes**. each rune introduces a syntactic form with a **stem** and a **leaf**; some runes also treat the first item of a stem specially, calling it the **herb**.

the language is designed around the following ideas:

* declarations are tree-shaped rather than purely flat
* named types are nominal
* unnamed composite values are structural
* casting is the boundary between structural and nominal representations
* member syntax is resolved statically through nominal types
* closure-like objects are represented through a door-like construct

this document is a reference for the current surface design. unresolved parts of the language are marked with **TODO**.

---

## rex structure

a rune has a stem and a leaf. visually:

```rex
|  stem
   stem
leaf
```

in rex terms:

* the **leaf** is the sequence of adjacent AST nodes composed by heir
* the **stem** is the contents of the `OPEN` node introduced by the rune
* the first node of a stem may be treated specially; this is called the **herb**

---

## core semantic model

### declarations

declarations are not purely flat bindings. a declaration may have both:

* a value
* child declarations beneath that value

this gives declarations a namespace-like shape. This shape only exists at
compile time, which is to say that the names are recursive, but their referents
are not. They are parsed top to bottom.


### structural and nominal values

cairn distinguishes between **structural** and **nominal** types.

* unnamed composite types are structural
* named types are nominal
* structural code may operate on nominal values so long as it relies only on structural shape
* nominality is introduced explicitly through casting

### member lookup

member syntax is available only on values with nominal types.

member access is resolved statically through the nominal type of the receiver. it is ordinary function application, not dynamic dispatch.

### representation strategy

PLAN represents rows as applications of a number.

examples:

* `(0 3)` represents the one-tuple `[3]`
* `((0 3) 4)` represents the two-tuple `[3 4]`

cairn uses the head of this application spine to distinguish structural from nominal values:

* structural rows use `0` as head
* nominal values use an arithmetized constructor identity as head

ordinary cairn code does not directly inspect or rewrite these heads.

**TODO:** specify this invariant precisely.

---

## runes

## `+` — declare constant

`+` introduces a named constant.

### shape

Tall `+` takes an herb and a leaf.

* the stem gives the name being introduced
* the leaf gives the value being bound and child declarations. The value must
  come first

Wide `+` takes two stems - name and value, no recursive children definitions.

### examples

```rex
+  point
  [3 4]
```

```rex
+  point
  [3 4]
  +  magnitude
    ...
```

in the second example, `point` has both a value and a child declaration `magnitude`.

### notes

this makes constant declarations tree-shaped rather than purely flat.

---

## `|` — function

`|` introduces a function.

### shape

`|` takes any number of stems and a leaf.

* the stems are the argument binders
* the leaf is the function body

### example

```rex
|  x=nat  y=nat
(add x y)
```

because functions are curried, this is directly equivalent (will produce the
same PLAN) to:

```rex
|  x=nat
|  y=nat
(add x y)
```

### notes

multi-argument function syntax is shorthand for nested unary functions.
Binders are of the form `name=type`. No patterns are allowed in type position.
type variables are allowed in type position, assuming that they are in scope
(introduced with @)

### TODO

* are faceless binders useful?

---

## `^` — cast

`^` casts the value of its leaf to the type referred to by its stem.

### shape

`^` takes a single stem and a leaf, or in wide form two stems.

### example

```rex
^  nat
   x
' wide
`^(foo bar)`
```

### nominal construction

casting is the point where nominal values are constructed.

given:

```rex
+  point
  $  [x=nat y=nat]
```

`point` is a named type and therefore nominal.

if `[3 4]` is represented structurally as:

```text
(0 3 4)
```

then casting it to `point` changes its representation to:

```text
(<magic-num> 3 4)
```

where `<magic-num>` is an arithmetization of the constructor identity of `point`.

### notes

this allows structural values to be converted into nominal values without exposing raw representation heads to ordinary user code.

structural functions may consume nominal values so long as the underlying
structural types nest.

Nominal types can be searched to produce their underlying structural type. This
means that from the typechecking perspective, all four items of the 2x2 casting
matrix are identical.

In all cases, assert that the underlying structural casted-to type nests inside
the underlying structural casting-from type. Then emit code that rewrites
the constructor tag accordingly.

The type system will not let you manually do (0 3). The only other way to
produce an arbitrary nat head row is with Coup, which is not exposed to the
programmer.

---

## `%` — call

`%` is the explicit multiline function application form.

### shape

`%` takes any number of stems and a leaf.

* the first stem is the function being called
* the remaining stems and the leaf are its arguments

### examples

```rex
%  (if (eq a 0) b)
   c
```

equivalent to:

```rex
%  if (eq a 0) b
   c
```

and to ordinary application syntax:

```rex
(if (eq a 0) b c)
```


---

## `?` — pattern match

`?` performs pattern matching.

### shape

* the first stem is the scrutinee
* each subsequent stem begins with `>`
* `>` markers must align vertically

### example

```rex
?  a
   > [#some x=nat] x
   > #none         x
```

### notes

pattern matches must always declare the type being matched.

### TODO
- properly specify pattern syntax
-
---

## `$` — type parsing context

`$` switches into type parsing context.

### shape

`$` takes a rex form and causes it to be parsed as a type expression rather than a value expression.

### example

```rex
$  [x=nat y=nat]
```

this means a row type with fields `x` and `y`, not construction of a runtime row value.

### TODO

* specify the grammar of type expressions under `$`
* specify whether type expressions form a distinct AST category or elaborate into ordinary terms

---

## `=` — let / letrec

`=` introduces a block of bindings before evaluating a body.

### shape

`=` is followed by a sequence of `>` clauses and then a body.

### example

```rex
=  > a (do-some-call b)
   > b (depends-on c)
   > c 3
   ...body
```

all bindings introduced by the `>` clauses are in scope for the body.

the intended meaning is recursive binding.


---

## `@` — introduce type variable

`@` introduces universal quantification over type variables.

### shape

`@` takes a list of names in its stems and quantifies over them in its leaf.

### example

```rex
@  x y
   body
```

this means: for all type variables `x` and `y`, `body`.

@ binds type variables only. There is no higher-kinding (pure system F).

---

## `;` — close over data

`;` closes over data to produce a door-like nominal object.

### shape

`;` introduces a closed-over environment and nested declarations which may refer to that environment.

### example

```rex
+  door
  ;  foo=nat
  +  func
    |  a=nat
    ^  nat
    (add a foo)
  +  try
    (door (add 2 foo))
```

this produces a function from a `nat` to a row of functions closed over that value.

the intent is that member syntax such as:

```rex
(door 3).func(5)
```

typechecks because `;` synthesizes a nominal type associated with the closed-over environment.

---

## names

## bare and qualified names

a bare name refers directly to a binding:

```rex
foo
```

a qualified name refers to a child binding:

```rex
foo:bar
```

## member syntax

member syntax is available only for nominally typed values.

if `foo` has nominal type `fud`, then:

```rex
foo.bar
```

desugars to:

```rex
(fud:bar foo)
```

if the member takes additional arguments:

```rex
foo.baz(qux)
```

it desugars to:

```rex
(fud:baz qux foo)
```

the receiver is passed last.

this is ordinary function application, not dynamic dispatch.

if the type of the receiver is not nominal, member syntax is a compilation error.



