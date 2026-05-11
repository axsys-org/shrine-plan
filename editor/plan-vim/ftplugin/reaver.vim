if exists("b:did_ftplugin")
  finish
endif
let b:did_ftplugin = 1

setlocal commentstring=;\ %s
setlocal comments=:;
setlocal lisp
setlocal autoindent
setlocal shiftwidth=2
setlocal softtabstop=2
setlocal expandtab
setlocal iskeyword+=#,-
setlocal define=^\s*(define\>\|^\s*(define-syntax\>

" optional: make [% jump between define forms
nnoremap <buffer> ]] /^\s*(define\\|^\s*(define-syntax<CR>
nnoremap <buffer> [[ ?^\s*(define\\|^\s*(define-syntax<CR>
