if exists('b:current_syntax')
  finish
endif
" Embedded Foil and Goo share Rex strings, quips, paths and anchors.
runtime! syntax/foil.vim
unlet! b:current_syntax
syn match groveKind "@\%(type\|slot\|role\|action\|norm\|sewn\|tree\|view\|pane\)\>"
syn match groveDirective "#\%(import\|with\|on\|here\|from\|to\|like\|for\|port\|meta\|or\|opt\|get\)\>"
syn match groveLanguage "!\s\+\%(foil\|goo\)\>"
syn match groveDefName '^\s*\zs[A-Za-z_][A-Za-z0-9_/-]*\ze\s*='
syn match groveDefName '^\s*\zs"\%([^"]\|""\)*"\ze\s*='
syn match groveArrow "=>"
syn match groveGet "^\s*\zsget\ze\s*:"
hi def link groveKind Type
hi def link groveDirective PreProc
hi def link groveLanguage Include
hi def link groveDefName Function
hi def link groveArrow Operator
hi def link groveGet Keyword
let b:current_syntax = 'grove'
