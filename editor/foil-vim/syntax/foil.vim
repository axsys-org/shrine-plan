" Foil's Rex surface syntax: anchors, generics and compact constructors.
if exists('b:current_syntax')
  finish
endif
syn case match
syn match foilNumber "\<\d\+\>"
syn match foilRune "[+|^?$=@;:&<>!\\]"
syn match foilRune "%\ze\s"
syn match foilGeneric "@@\?"
syn match foilBracket "[][(){}]"
syn match foilPath "\<[A-Za-z_][A-Za-z0-9_-]*\%(/[A-Za-z_][A-Za-z0-9_-]*\)\+"
syn match foilMember "\.[A-Za-z_][A-Za-z0-9_-]*"
syn match foilAnchor "[;#]/\ze[A-Za-z_]"
syn match foilAnchor "\./\ze[A-Za-z_]"
syn match foilDefName "\%(^\s*+\s\+\)\@<=[A-Za-z_][A-Za-z0-9_/-]*"
" Quips include quoted paths and tack/hunt data; they have no closing quote.
syn match foilQuip "'[^[:space:](){}\[\]\"']\+"
" Rex escapes a quote by doubling it, not with a backslash.
syn region foilString start=+"+ skip=+""+ end=+"+ oneline
syn match foilComment "\%(^\|\s\)\zs'\%($\|\s.*$\)" contains=foilTodo
syn keyword foilTodo TODO FIXME NOTE contained
hi def link foilNumber Number
hi def link foilRune Statement
hi def link foilGeneric Type
hi def link foilBracket Delimiter
hi def link foilPath Identifier
hi def link foilMember Function
hi def link foilAnchor Special
hi def link foilDefName Function
hi def link foilQuip Constant
hi def link foilString String
hi def link foilComment Comment
hi def link foilTodo Todo
let b:current_syntax = 'foil'
