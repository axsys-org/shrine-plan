-- Run from the repository root:
-- nvim --headless -u NONE -i NONE -n -l editor/foil-nvim/tests/run.lua
local root = vim.fn.getcwd()
vim.opt.runtimepath:prepend(root .. '/editor/foil-nvim')
vim.opt.runtimepath:prepend(root .. '/editor/foil-vim')
vim.cmd('filetype plugin indent on')
vim.cmd('syntax on')
vim.cmd('runtime plugin/foil-wire.lua')
local count = 0
local function eq(actual, expected, label)
  count = count + 1
  assert(vim.deep_equal(actual, expected), (label or '') .. '\nexpected ' .. vim.inspect(expected) .. '\ngot ' .. vim.inspect(actual))
end
local seq = 0
local function buffer(ext, lines)
  vim.cmd('enew!')
  seq = seq + 1
  vim.cmd('file /tmp/foil-editor-test-' .. seq .. '.' .. ext)
  vim.api.nvim_buf_set_lines(0, 0, -1, false, lines)
  vim.cmd('doautocmd BufRead')
  vim.cmd('syntax sync fromstart')
end
local function group(row, text)
  local line = vim.api.nvim_buf_get_lines(0, row - 1, row, false)[1]
  local col = assert(line:find(text, 1, true))
  return vim.fn.synIDattr(vim.fn.synID(row, col, 1), 'name')
end
local function cursor(row, text)
  local line = vim.api.nvim_buf_get_lines(0, row - 1, row, false)[1]
  vim.api.nvim_win_set_cursor(0, {row, assert(line:find(text, 1, true)) - 1})
end
local function test()
  buffer('foil', {
    '+ color', '  + red :', '  + blue :', '  & #/red #/blue',
    '+ parse-color', '  \\ text=str', '  (color/read_str text).ok_or("Unknown ""color"".")',
    '  ;/color', '  (@ t) (@@ scope)', "  '@/y/%/cards", "' TODO #/red", '  > .none ./some',
    '  %/old',
  })
  eq(vim.bo.filetype, 'foil', 'Foil detection')
  eq(group(2, 'red'), 'foilDefName')
  eq(group(4, '#/'), 'foilAnchor')
  eq(group(6, '\\'), 'foilRune')
  eq(group(7, 'color/read_str'), 'foilPath')
  eq(group(7, '.ok_or'), 'foilMember')
  eq(group(7, 'color""'), 'foilString', 'doubled quotes stay inside string')
  eq(group(8, ';/'), 'foilAnchor')
  eq(group(9, '@@'), 'foilGeneric')
  eq(group(10, '%/'), 'foilQuip', 'quoted tack data is not an anchor')
  eq(group(11, '#/'), 'foilComment')
  eq(group(12, '>'), 'foilRune')
  eq(group(12, './'), 'foilAnchor')
  assert(group(13, '%/') ~= 'foilAnchor', 'old sibling spelling must not be highlighted as an anchor')
  eq(vim.bo.shiftwidth, 2)
  eq(vim.bo.commentstring, "'  %s")
  eq(vim.fn.maparg('gd', 'n', false, true).buffer, 1)
  eq(vim.fn.maparg('<leader>fc', 'n'), '', 'wire compile is opt-in')

  local source = require('foil.source')
  local inspect = require('foil.inspect')
  cursor(11, '#/red')
  eq(source.word(), nil, 'comments are not references')
  cursor(7, 'Unknown')
  eq(source.word(), nil, 'strings are not references')
  cursor(10, 'cards')
  eq(source.word(), nil, 'quoted data is not a reference')
  buffer('foil', {
    '+ grove', '  + tag-kind', '    + slot :', '    + role :', '    & #/slot #/role',
    '  + read-tag-kind', '    \\ text=str', '    ;/tag-kind/read_str text',
    '+ other', '  + inner', '    #/child', '    + child :',
    '+ grove', '  + extra', '    ;/tag-kind',
  })
  cursor(5, '#/slot')
  eq(inspect.name_at_cursor(), 'grove.tag-kind.slot')
  eq(source.find().line, 3)
  cursor(3, 'slot')
  eq(source.find().name, 'grove/tag-kind/slot', 'inspect nested declaration header')
  cursor(5, '#/slot')
  eq(source.complete('#/s')[1].word, '#/slot', 'child completion retains anchor')
  cursor(8, ';/tag-kind')
  eq(inspect.name_at_cursor(), 'grove.tag-kind.read_str', 'sibling anchor drops current declaration')
  eq(source.complete(';/tag-')[1].word, ';/tag-kind')
  eq(source.start('    ;/tag-kind', 13), 4)
  cursor(11, '#/child')
  eq(source.find().line, 12, 'forward child reference')
  cursor(15, ';/tag-kind')
  inspect.goto_definition()
  eq(vim.fn.line('.'), 2, 'additive namespace resolves earlier declaration')
  vim.api.nvim_buf_set_lines(0, 1, 2, false, {'  + renamed'})
  eq(source.find('grove/tag-kind'), nil, 'index refreshes after editing')
  buffer('foil', {'+ original :', '+ alias original'})
  cursor(2, 'original')
  eq(source.find().line, 1, 'reference on a compact declaration line')

  buffer('grove', {
    '#import text=lib/grove/types/text', 'note =', '  @role', '  title: text',
    'summary =', '  @view', '  #on ; ;/note', '  ! goo', '  note => {',
    '    show(note.title, \'/sys/slot/label)', '  }',
    '"/notes" =', '  @tree', '  title: "#on @role"',
    'status =', '  @type', '  ! foil', '  + ready :', '  + pending :',
    '  & #/ready #/pending',
  })
  eq(vim.bo.filetype, 'grove')
  eq(group(1, '#import'), 'groveDirective')
  eq(group(2, 'note'), 'groveDefName')
  eq(group(3, '@role'), 'groveKind')
  eq(group(7, '#on'), 'groveDirective')
  eq(group(7, ';/'), 'foilAnchor')
  eq(group(8, '! goo'), 'groveLanguage')
  eq(group(9, '=>'), 'groveArrow')
  eq(group(12, '"/notes"'), 'groveDefName')
  eq(group(14, '#on'), 'foilString')
  eq(group(18, 'ready'), 'foilDefName')
  cursor(7, ';/note')
  eq(source.find().line, 2, 'Grove sibling navigation')
  eq(source.complete(';/n')[1].word, ';/note')
  cursor(20, '#/ready')
  eq(source.find().line, 18, 'embedded Foil child')

  -- No requests on save by default, nor for Grove even with wire enabled.
  local requests = {}
  local wire = require('foil.wire')
  wire.request = function(req) requests[#requests + 1] = req end
  wire.request_sync = function(req)
    requests[#requests + 1] = req
    return true, {ok = true, names = {'grove/tag-kind'}}
  end
  vim.cmd('doautocmd BufWritePost')
  vim.cmd('FoilCompile')
  eq(#requests, 0)
  require('foil').setup({wire_enabled = true})
  vim.cmd('doautocmd BufWritePost')
  vim.cmd('FoilCompile')
  eq(#requests, 0, 'Grove never goes to Foil compiler')
  buffer('foil', {'+ grove', '  + read', '    ;/tag-'})
  cursor(3, ';/tag-')
  eq(require('foil.complete').omnifunc(0, ';/tag-')[1].word, ';/tag-kind')
  eq(requests[1].prefix, 'grove/tag-')
  vim.cmd('doautocmd BufWritePost')
  eq(requests[2].op, 'compile')

  -- Successful compilation keeps lint findings, including their severity and
  -- rule ids. Replies for an older request or edited buffer cannot overwrite it.
  local callbacks = {}
  wire.request = function(req, cb)
    requests[#requests + 1] = req
    callbacks[#callbacks + 1] = cb
  end
  local diag = require('foil.diag')
  local mod = require('foil.module').of()
  local finding = {module=mod, source='foil-lint', line=3, col=5,
    level='warning', rule='gutter', msg='align the gutter'}
  diag.compile()
  callbacks[#callbacks](true, {ok=true, diags={finding}})
  local got = vim.diagnostic.get(0, {namespace=diag.lint_ns})
  eq(#got, 1, 'lint survives successful compilation')
  eq({got[1].lnum, got[1].col, got[1].severity, got[1].code},
    {2, 4, vim.diagnostic.severity.WARN, 'gutter'})
  eq(#vim.diagnostic.get(0, {namespace=diag.ns}), 0)
  diag.compile()
  local stale = callbacks[#callbacks]
  diag.compile()
  callbacks[#callbacks](true, {ok=true, diags={}})
  stale(true, {ok=false, error='old error'})
  eq(#vim.diagnostic.get(0, {namespace=diag.lint_ns}), 0, 'fixed lint is cleared')
  eq(#vim.diagnostic.get(0, {namespace=diag.ns}), 0, 'stale error ignored')
  diag.compile()
  local edited = callbacks[#callbacks]
  vim.api.nvim_buf_set_lines(0, 2, 3, false, {'    42'})
  edited(true, {ok=false, error='error in previous text'})
  eq(#vim.diagnostic.get(0, {namespace=diag.ns}), 0, 'edited buffer ignores saved-source reply')
  diag.compile()
  callbacks[#callbacks](true, {ok=false, diags={
    {module=mod, line=2, col=1, msg='unknown name'}, finding}})
  eq(#vim.diagnostic.get(0, {namespace=diag.ns}), 1, 'compiler error retained alongside lint')
  vim.cmd('FoilLint')
  eq(requests[#requests].op, 'lint')
  callbacks[#callbacks](true, {ok=true, diags={}})
  eq(#vim.diagnostic.get(0, {namespace=diag.ns}), 1, 'lint-only preserves compiler errors')
  eq(#vim.diagnostic.get(0, {namespace=diag.lint_ns}), 0)
  diag.compile()
  callbacks[#callbacks](true, {ok=false, diags={{module='dependency', line=7, msg='bad import'}}})
  got = vim.diagnostic.get(0, {namespace=diag.ns})
  eq(got[1].lnum, 0, 'dependency error is summarized, not misplaced')
  eq(got[1].severity, vim.diagnostic.severity.ERROR)
  diag.compile()
  callbacks[#callbacks](true, {ok=true, diags={{module=mod, line=1, col=1,
    source='foil-lint', rule='snake-case', level='error', msg='use snake_case'}}})
  eq(vim.diagnostic.get(0, {namespace=diag.lint_ns})[1].severity, vim.diagnostic.severity.ERROR)
  require('foil').setup({wire_enabled = false})

  -- Filetype switches must clean up Lua mappings and buffer-local options.
  vim.bo.filetype = 'text'
  eq(vim.fn.maparg('gd', 'n'), '', 'mapping cleanup')
  eq(vim.bo.omnifunc, '', 'omnifunc cleanup')
  eq(vim.b.did_foil_wire_ftplugin, nil)
  vim.bo.filetype = 'foil'
  eq(vim.fn.maparg('gd', 'n', false, true).buffer, 1, 'ftplugin can be reloaded')

  for _, case in ipairs({
    {'foil', '+ name', 2}, {'foil', '+ name :', 0},
    {'foil', '+ name \' comment', 2}, {'grove', 'note =', 2},
    {'grove', '"/notes" =', 2}, {'grove', '  @role', 2},
    {'grove', '  ! foil', 2}, {'grove', '  + ready :', 2},
  }) do
    buffer(case[1], {case[2], 'body'})
    vim.cmd('normal! G==')
    eq(vim.fn.indent(2), case[3], 'indent after ' .. case[2])
  end
  buffer('goo', {'group { text("Hi", %title) }'})
  eq(vim.bo.filetype, 'goo')
  eq(group(1, '%title'), 'gooSlot')

  local module = require('foil.module')
  buffer('foil', {''})
  vim.api.nvim_buf_set_name(0, root .. '/src/foil/stdlib/runtime.foil')
  eq(module.of(), 'stdlib/runtime')
  eq(module.file_of('types'), root .. '/src/foil/types.foil')
  vim.api.nvim_buf_set_name(0, root .. '/extras/mounts/chat/main.foil')
  eq(module.of(), 'apps/chat/main', 'mount module alias')
  eq(module.file_of('chat_mount'), root .. '/extras/mounts/chat/activation.foil')
  vim.api.nvim_buf_set_name(0, root .. '/extras/mounts/chat/tests.foil')
  eq(module.of(), 'apps/chat/tests', 'mount test alias')
  vim.b.foil_module = 'override'
  eq(module.of(), 'override')
  eq({module.parse_node('/boot/stdlib/runtime/42/grove/tag_kind')}, {'stdlib/runtime', 'grove/tag_kind'})
end
local ok, err = xpcall(test, debug.traceback)
if not ok then
  io.stderr:write(err .. '\n')
  vim.cmd('cquit 1')
else
  print(('Foil editor: %d checks passed'):format(count))
  vim.cmd('qa!')
end
