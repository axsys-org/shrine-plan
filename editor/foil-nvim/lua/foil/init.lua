-- Local Foil/Grove editing, with optional compiler wire integration.

local M = {}

M.config = {
  wire_enabled = false, -- opt in after starting x/repl or x/eden --wire-port
  host = "127.0.0.1",
  port = 8679,
  timeout = 120000,       -- milliseconds; first compilation can be slow
  compile_on_save = true, -- BufWritePost *.foil -> compile + diagnostics
  keymaps = true,         -- buffer-local maps in Foil and Grove buffers
}

function M.uses_wire(bufnr)
  return M.config.wire_enabled and vim.bo[bufnr or 0].filetype == "foil"
end

function M.setup(opts)
  M.config = vim.tbl_extend("force", M.config, opts or {})
  require("foil.wire").setup({ host = M.config.host, port = M.config.port, timeout = M.config.timeout })
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
