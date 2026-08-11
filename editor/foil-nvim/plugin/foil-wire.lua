-- foil-nvim entry: commands + autocmds.  Everything else lazy-loads.

if vim.g.loaded_foil_wire then return end
vim.g.loaded_foil_wire = 1

local function cfg()
  return require("foil").config
end

vim.api.nvim_create_user_command("FoilConnect", function()
  require("foil").ping()
end, { desc = "ping the buddy wire port" })

vim.api.nvim_create_user_command("FoilCompile", function()
  require("foil.diag").compile()
end, { desc = "recompile the buffer's module (resync + diagnostics)" })

vim.api.nvim_create_user_command("FoilDoctest", function()
  require("foil.diag").doctest()
end, { desc = "run the buffer module's doctests" })

vim.api.nvim_create_user_command("FoilEval", function(a)
  if a.range > 0 then
    require("foil.eval").eval_selection()
  else
    require("foil.eval").eval_arg(a.args)
  end
end, { nargs = "*", range = true, desc = "evaluate an expression against the buffer's module" })

vim.api.nvim_create_user_command("FoilInspect", function(a)
  require("foil.inspect").inspect(a.args)
end, { nargs = "?", desc = "inspect a mirror entry (default: name under cursor)" })

vim.api.nvim_create_user_command("FoilCalls", function(a)
  require("foil.inspect").xref("calls", a.args)
end, { nargs = "?", desc = "what the entry under the cursor calls" })

vim.api.nvim_create_user_command("FoilCalledBy", function(a)
  require("foil.inspect").xref("called_by", a.args)
end, { nargs = "?", desc = "who calls the entry under the cursor" })

vim.api.nvim_create_user_command("FoilRepl", function()
  require("foil.repl").open()
end, { desc = "open the wire REPL buffer" })

local group = vim.api.nvim_create_augroup("FoilWire", { clear = true })

vim.api.nvim_create_autocmd("BufWritePost", {
  group = group,
  pattern = "*.foil",
  callback = function(ev)
    if cfg().compile_on_save then
      require("foil.diag").compile(ev.buf)
    end
  end,
})
