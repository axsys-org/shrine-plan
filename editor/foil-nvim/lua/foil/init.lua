-- foil-nvim: the buddy's wire port (doc/buddy-wire.md) as editor
-- features — compile-on-save diagnostics, eval, hover, inspect,
-- jump-to-definition, who-calls, completion, and a REPL buffer, all
-- against the one resident x/repl image.

local M = {}

M.config = {
  host = "127.0.0.1",
  port = 8679,
  compile_on_save = true, -- BufWritePost *.foil -> compile + diagnostics
  keymaps = true,         -- buffer-local maps in foil buffers
}

function M.setup(opts)
  M.config = vim.tbl_extend("force", M.config, opts or {})
  require("foil.wire").setup({ host = M.config.host, port = M.config.port })
end

function M.ping()
  require("foil.wire").request({ op = "ping" }, function(ok, res)
    local ui = require("foil.ui")
    if ok and res.ok then
      ui.notify(("connected: %s v%s"):format(res.server, res.v))
    else
      ui.notify(ok and "unexpected reply" or res, vim.log.levels.ERROR)
    end
  end)
end

return M
