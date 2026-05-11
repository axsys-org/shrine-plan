if exists("b:current_syntax")
  finish
endif

syn case match

syn match   reaverComment /;.*/ contains=@Spell
syn region  reaverString start=/"/ skip=/\\"/ end=/"/ contains=reaverEscape
syn match   reaverEscape /\\./ contained
syn match   reaverNumber /\<\d\+\>/
syn match   reaverParen /[()]/
syn match   reaverBracket /[\[\]]/

syn match   reaverSharpForm /#\%(bind\|import\|module\)\>/
syn keyword reaverSpecial define define-syntax lambda If Ifz Seq assert
syn keyword reaverBuiltin Eq Or Dec Inc Sz Ix Up foldl foldr drop print strWeld
syn match   reaverBuiltin /\<_\d\+\>/

syn match   reaverHead /(\s*\zs[#A-Za-z_][#A-Za-z0-9_-]*/ contains=reaverSharpForm,reaverSpecial,reaverBuiltin
syn match   reaverSymbol /\<[A-Za-z_][A-Za-z0-9_-]*\>/

hi def link reaverComment   Comment
hi def link reaverString    String
hi def link reaverEscape    SpecialChar
hi def link reaverNumber    Number
hi def link reaverParen     Delimiter
hi def link reaverBracket   Delimiter
hi def link reaverSharpForm PreProc
hi def link reaverSpecial   Keyword
hi def link reaverBuiltin   Function
hi def link reaverHead      Statement
hi def link reaverSymbol    Identifier

let b:current_syntax = "reaver"
