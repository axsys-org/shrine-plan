if exists('b:did_indent')
  finish
endif
runtime! indent/foil.vim
setlocal indentexpr=GetGroveIndent()

function! GetGroveIndent() abort
  let l:lnum = prevnonblank(v:lnum - 1)
  let l:prev = getline(l:lnum)
  " Bare declaration headers open a level; @role and ! foil do not.
  if l:prev =~# '^\s*\%([A-Za-z_][A-Za-z0-9_/-]*\|"[^"]*"\)\s*=\s*\%(''\s.*\)\?$'
    return indent(l:lnum) + shiftwidth()
  endif
  return GetFoilIndent()
endfunction
