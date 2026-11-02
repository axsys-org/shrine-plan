local M = {}

function M.setup()
  if vim.b.did_foil_wire_ftplugin then return end
  vim.b.did_foil_wire_ftplugin = true
  vim.bo.omnifunc = "v:lua.require'foil.complete'.omnifunc"
  local undo = { "setlocal omnifunc<", "unlet! b:did_foil_wire_ftplugin" }
  local function map(mode, lhs, rhs, desc)
    vim.keymap.set(mode, lhs, rhs, { buffer = true, silent = true, desc = desc })
    -- Expand <leader> now so cleanup still works if the user changes it.
    local key = lhs:gsub('<leader>', vim.g.mapleader or '\\')
    undo[#undo + 1] = 'silent! execute ' .. vim.fn.string(mode .. 'unmap <buffer> ' .. key)
  end
  if require('foil').config.keymaps then
    map('n', 'K', function() require('foil.inspect').hover() end, 'Foil/Grove: declaration')
    map('n', 'gd', function() require('foil.inspect').goto_definition() end, 'Foil/Grove: definition')
    map('n', '<leader>fi', function() require('foil.inspect').inspect('') end, 'Foil/Grove: inspect')
    if require('foil').uses_wire() then
      map('n', '<leader>fe', function() require('foil.eval').eval_line() end, 'Foil: eval line')
      map('x', '<leader>fe', "<Esc><Cmd>lua require('foil.eval').eval_selection()<CR>", 'Foil: eval selection')
      map('n', '<leader>fc', function() require('foil.diag').compile() end, 'Foil: compile')
      map('n', '<leader>ft', function() require('foil.diag').doctest() end, 'Foil: doctests')
      map('n', '<leader>fr', function() require('foil.repl').open() end, 'Foil: REPL')
      map('n', '<leader>fu', function() require('foil.inspect').xref('called_by', '') end, 'Foil: callers')
    end
  end
  local old = vim.b.undo_ftplugin
  vim.b.undo_ftplugin = (old and (old .. ' | ') or '') .. table.concat(undo, ' | ')
end

return M
