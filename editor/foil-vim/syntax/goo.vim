if exists('b:current_syntax')
  finish
endif
runtime! syntax/foil.vim
unlet! b:current_syntax
" Standalone literal Goo uses %slot references.
syn match gooSlot "%[A-Za-z_][A-Za-z0-9_/-]*"
syn match gooArrow "=>"
hi def link gooSlot Identifier
hi def link gooArrow Operator
let b:current_syntax = 'goo'
