-- foil-nvim entry: commands + autocmds.  Everything else lazy-loads.

if vim.g.loaded_foil_wire then return end
vim.g.loaded_foil_wire = 1

local function cfg()
  return require("foil").config
end

local function connected(fn, any_buffer)
  return function(...)
    if not cfg().wire_enabled or (not any_buffer and vim.bo.filetype ~= "foil") then
      return require("foil.ui").notify(
        "This command requires an enabled Foil wire server; Grove uses local navigation.",
        vim.log.levels.WARN)
    end
    return fn(...)
  end
end

vim.api.nvim_create_user_command("FoilConnect", connected(function()
  require("foil").ping()
end, true), { desc = "ping the compiler wire port" })

vim.api.nvim_create_user_command("FoilCompile", connected(function()
  require("foil.diag").compile()
end), { desc = "recompile the buffer's module (resync + diagnostics)" })

vim.api.nvim_create_user_command("FoilLint", connected(function()
  require("foil.diag").lint()
end), { desc = "lint the saved buffer without typechecking it" })

vim.api.nvim_create_user_command("FoilDoctest", connected(function()
  require("foil.diag").doctest()
end), { desc = "run the buffer module's doctests" })

vim.api.nvim_create_user_command("FoilEval", connected(function(a)
  if a.range > 0 then
    require("foil.eval").eval_selection()
  else
    require("foil.eval").eval_arg(a.args)
  end
end), { nargs = "*", range = true, desc = "evaluate an expression against the buffer's module" })

vim.api.nvim_create_user_command("FoilInspect", function(a)
  require("foil.inspect").inspect(a.args)
end, { nargs = "?", desc = "inspect a mirror entry (default: name under cursor)" })

vim.api.nvim_create_user_command("FoilCalls", connected(function(a)
  require("foil.inspect").xref("calls", a.args)
end), { nargs = "?", desc = "what the entry under the cursor calls" })

vim.api.nvim_create_user_command("FoilCalledBy", connected(function(a)
  require("foil.inspect").xref("called_by", a.args)
end), { nargs = "?", desc = "who calls the entry under the cursor" })

vim.api.nvim_create_user_command("FoilRepl", connected(function()
  require("foil.repl").open()
end), { desc = "open the wire REPL buffer" })

local group = vim.api.nvim_create_augroup("FoilWire", { clear = true })

vim.api.nvim_create_autocmd("BufWritePost", {
  group = group,
  pattern = "*.foil",
  callback = function(ev)
    if cfg().compile_on_save and require("foil").uses_wire(ev.buf) then
      require("foil.diag").compile(ev.buf)
    end
  end,
})
