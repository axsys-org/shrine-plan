if exists("b:did_indent")
  finish
endif
let b:did_indent = 1

setlocal indentexpr=GetReaverIndent()
setlocal indentkeys=o,O,),],0=end

function! GetReaverIndent()
  let lnum = prevnonblank(v:lnum - 1)
  if lnum <= 0
    return 0
  endif

  let prev = getline(lnum)
  let curr = getline(v:lnum)

  let ind = indent(lnum)

  " decrease indent for closing delimiters
  if curr =~ '^\s*[\)\]]'
    return ind - &shiftwidth
  endif

  " increase after lines ending in an open form
  if prev =~ '[([]\s*$'
    return ind + &shiftwidth
  endif

  " increase after lines with more opens than closes
  let opens  = len(split(substitute(prev, '[^(\[]', '', 'g'), '\zs'))
  let closes = len(split(substitute(prev, '[^)\]]', '', 'g'), '\zs'))
  if opens > closes
    return ind + &shiftwidth
  endif

  return ind
endfunction