-- Local declaration completion, or module entries through the optional wire.

local wire = require("foil.wire")
local module = require("foil.module")

local M = {}

function M.omnifunc(findstart, base)
  if findstart == 1 then
    local line = vim.api.nvim_get_current_line()
    local col = vim.fn.col(".") - 1
    return require("foil.source").start(line, col)
  end
  local source = require("foil.source")
  if not require("foil").uses_wire() then return source.complete(base) end
  local prefix = source.resolve(base)
  local ok, res = wire.request_sync(
    { op = "complete", module = module.of(0), prefix = prefix })
  if not ok or not res.ok then return {} end
  local items = {}
  for _, name in ipairs(wire.field(res, "names") or {}) do
    if name:sub(1, #prefix) == prefix then
      items[#items + 1] = { word = base .. name:sub(#prefix + 1), menu = "[foil]" }
    end
  end
  return items
end

return M
