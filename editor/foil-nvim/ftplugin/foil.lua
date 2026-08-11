-- Buffer-local wiring for foil buffers (the syntax/indent side lives
-- in editor/foil-vim; install both).

if vim.b.did_foil_wire_ftplugin then return end
vim.b.did_foil_wire_ftplugin = 1

vim.bo.omnifunc = "v:lua.require'foil.complete'.omnifunc"

if require("foil").config.keymaps then
  local function map(mode, lhs, rhs, desc)
    vim.keymap.set(mode, lhs, rhs, { buffer = true, desc = desc })
  end
  map("n", "K", function() require("foil.inspect").hover() end, "foil: describe (hover)")
  map("n", "gd", function() require("foil.inspect").goto_definition() end, "foil: go to definition")
  map("n", "<leader>fe", function() require("foil.eval").eval_line() end, "foil: eval line")
  map("x", "<leader>fe", "<Esc><Cmd>lua require('foil.eval').eval_selection()<CR>", "foil: eval selection")
  map("n", "<leader>fc", function() require("foil.diag").compile() end, "foil: compile module")
  map("n", "<leader>ft", function() require("foil.diag").doctest() end, "foil: doctest module")
  map("n", "<leader>fi", function() require("foil.inspect").inspect("") end, "foil: inspect entry")
  map("n", "<leader>fr", function() require("foil.repl").open() end, "foil: repl")
  map("n", "<leader>fu", function() require("foil.inspect").xref("called_by", "") end, "foil: who calls")
end
