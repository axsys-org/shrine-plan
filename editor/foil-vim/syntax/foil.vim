" Vim syntax file
" Language:    foil
" Filenames:   *.foil
"
" foil is a rex-based surface language built on the PLAN combinator
" calculus. Source is organized around runes: sigils that introduce
" syntactic forms with a stem and a leaf.
"
" Tall form:  rune at start of a stem, followed by 2+ spaces, content
"             starts on the same line, body continues on subsequent
"             lines at the same indent.
" Wide form:  rune followed immediately by `(...)`.

if exists("b:current_syntax")
  finish
endif

syn case match

" -------------------------------------------------------------------
" Comments
" -------------------------------------------------------------------
" The ' rune followed by whitespace introduces a comment line.
" Anchored at start-of-stem (^ or whitespace).
syn match foilComment "\(^\|\s\)\zs'\s.*$"

" -------------------------------------------------------------------
" Tags / hashed atoms
" -------------------------------------------------------------------
" #foo, %foo, 'foo  (the 'foo case must follow the comment rule, since
" 'foo without a trailing space is *not* a comment).
syn match foilTag "#[A-Za-z_][A-Za-z0-9_-]*"
syn match foilTag "%[A-Za-z_][A-Za-z0-9_-]*"
syn match foilTag "'[A-Za-z_][A-Za-z0-9_-]*"

" -------------------------------------------------------------------
" Numbers
" -------------------------------------------------------------------
syn match foilNumber "\<\d\+\>"

" -------------------------------------------------------------------
" Runes
" -------------------------------------------------------------------
" Runes recognised:  +  |  ^  ?  $  =  @  ;  :  &  %
"
" The general rule: a rune sits at start-of-stem (^ or whitespace before)
" and is followed by 2+ spaces, by `(`, or by end-of-line.
syn match foilRune "\(^\|\s\)\zs[+|^?$=@;:&]\ze\(\s\|(\|$\)"

" `%` overlaps with %tag, so disambiguate: `%` is a rune only when followed
" by whitespace or `(`; otherwise it's part of a tag (handled above).
syn match foilRune "\(^\|\s\)\zs%\ze\(\s\|(\)"

" Definition name: the herb after `+` is the binding name.
syn match foilDefName "\(^\s*+\s\+\)\@<=\<[A-Za-z_][A-Za-z0-9_-]*\>"

" -------------------------------------------------------------------
" Arm / clause marker (>)
" -------------------------------------------------------------------
" Used in `?` pattern arms and `=` let bindings.
syn match foilArm "\(^\|\s\)\zs>\ze\s"

" -------------------------------------------------------------------
" Binder equals
" -------------------------------------------------------------------
" `name=type` in function arguments and row fields.
" No surrounding whitespace, distinguishing from the `=` (let) rune.
syn match foilBinderEq "[A-Za-z0-9_-]\@<==\ze[A-Za-z_(]"

" -------------------------------------------------------------------
" Member access and qualified names
" -------------------------------------------------------------------
" foo.bar  -- member access (only on nominal types)
syn match foilMember "\.\<[A-Za-z_][A-Za-z0-9_-]*\>"
" foo:bar  -- qualified name (child of a declaration's namespace)
syn match foilQualifier "[A-Za-z0-9_-]\@<=:\ze[A-Za-z_]"

" -------------------------------------------------------------------
" Brackets
" -------------------------------------------------------------------
syn match foilBracket "[(){}\[\]]"

" -------------------------------------------------------------------
" Built-in types and common functions
" -------------------------------------------------------------------
" These aren't really "keywords" in the parser sense -- they're just the
" names you'll see most often in foil code. Adjust to taste.
"syn keyword foilBuiltinType nat
"syn keyword foilBuiltin     if add inc dec mul eq

" -------------------------------------------------------------------
" Highlight links
" -------------------------------------------------------------------
hi def link foilComment      Comment
hi def link foilTag          Constant
hi def link foilNumber       Number
hi def link foilRune         Statement
hi def link foilDefName      Function
hi def link foilArm          Special
hi def link foilBinderEq     Operator
"hi def link foilMember       Identifier
"hi def link foilQualifier    Operator
hi def link foilBracket      Delimiter
hi def link foilBuiltinType  Type
hi def link foilBuiltin      Keyword

let b:current_syntax = "foil"
