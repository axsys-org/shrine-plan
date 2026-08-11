-- Omni-completion over the module's own entries (the mirror's
-- ['entries] slot via the wire's complete op).

local wire = require("foil.wire")
local module = require("foil.module")

local M = {}

function M.omnifunc(findstart, base)
  if findstart == 1 then
    local line = vim.api.nvim_get_current_line()
    local col = vim.fn.col(".") - 1
    local start = col
    while start > 0 and line:sub(start, start):match("[%w_/]") do
      start = start - 1
    end
    return start
  end
  local ok, res = wire.request_sync(
    { op = "complete", module = module.of(0), prefix = base }, 5000)
  if not ok or not res.ok then return {} end
  local items = {}
  for _, name in ipairs(wire.field(res, "names") or {}) do
    items[#items + 1] = { word = name, menu = "[foil]" }
  end
  return items
end

return M
