" Vim filetype plugin file
" Language: Foil

if exists("b:did_ftplugin")
  finish
endif
let b:did_ftplugin = 1

" -- Indentation -----------------------------------------------------
setlocal expandtab
setlocal shiftwidth=2
setlocal tabstop=2
setlocal softtabstop=2
setlocal autoindent

" -- Comments --------------------------------------------------------
" The ' rune followed by whitespace introduces a comment line in tall form.
let &l:commentstring = "'  %s"
setlocal comments=b:'

" -- Misc ------------------------------------------------------------
" Treat -, _ as part of identifiers for *, gd, etc.
setlocal iskeyword+=-

let b:undo_ftplugin =
  \ "setlocal expandtab< shiftwidth< tabstop< softtabstop< autoindent<" .
  \ " commentstring< comments< iskeyword<"
