" Vim indent file
" Language: Foil
"
" Rex-style code is mostly hand-aligned: stems and leaves interact in ways
" that a smart indenter tends to get wrong. We do the bare minimum:
" continue the previous line's indent, with a small bump after a `+ name`
" header line (which always introduces a body).

if exists("b:did_indent")
  finish
endif
let b:did_indent = 1

setlocal autoindent
setlocal nosmartindent
setlocal indentexpr=GetFoilIndent()
setlocal indentkeys=o,O,!^F

if exists("*GetFoilIndent")
  finish
endif

function! GetFoilIndent() abort
  let l:lnum = prevnonblank(v:lnum - 1)
  if l:lnum == 0
    return 0
  endif

  let l:prev = getline(l:lnum)
  let l:ind  = indent(l:lnum)

  " A `+ name` line on its own (no other content after the name) opens a
  " body that must be indented one shift deeper.
  if l:prev =~# '^\s*+\s\+[A-Za-z_][A-Za-z0-9_-]*\s*$'
    return l:ind + &shiftwidth
  endif

  " A pattern-match arm or let binding clause: `>  ...` -- next line
  " at same indent (a sibling clause) or two deeper (continuation body).
  " Default to same indent; user can Tab in for a continuation.
  return l:ind
endfunction
