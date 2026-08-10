-- Interrogation: hover (K), full inspection, jump-to-definition, and
-- who-calls — all reads of the mirror's entry records via describe.

local wire = require("foil.wire")
local module = require("foil.module")
local ui = require("foil.ui")

local M = {}

--- The entry name under the cursor, dotted for the wire ("cord/eof"
--- and "cord.eof" both -> "cord.eof").
function M.name_at_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1
  local s, e = col, col - 1
  local function tok(c) return c:match("[%w_%./]") ~= nil end
  while s > 1 and tok(line:sub(s - 1, s - 1)) do s = s - 1 end
  while e < #line and tok(line:sub(e + 1, e + 1)) do e = e + 1 end
  local word = line:sub(s, e):gsub("^[%./]+", ""):gsub("[%./]+$", "")
  if word == "" then return nil end
  return (word:gsub("/", "."))
end

function M.describe(name, cb)
  name = name or M.name_at_cursor()
  if not name then return ui.notify("no name under cursor", vim.log.levels.WARN) end
  wire.request({ op = "describe", module = module.of(0), name = name }, function(ok, res)
    if not ok then return ui.notify(res, vim.log.levels.WARN) end
    cb(name, res)
  end)
end

--- K: kind, type, first lore line.
function M.hover()
  M.describe(nil, function(name, res)
    if not res.ok then
      return ui.notify(wire.field(res, "error") or "unknown entry", vim.log.levels.WARN)
    end
    local lines = {}
    local kind = wire.field(res, "kind")
    lines[1] = name .. (kind and ("  [" .. kind .. "]") or "")
    local ty = wire.field(res, "type")
    if ty then lines[#lines + 1] = "type: " .. ty end
    local lede = wire.field(res, "lede")
    if lede then
      lines[#lines + 1] = ""
      lines[#lines + 1] = lede
    end
    ui.float(lines)
  end)
end

--- :FoilInspect — the whole entry record, source included.
function M.inspect(name)
  M.describe(name ~= "" and name or nil, function(nm, res)
    if not res.ok then
      return ui.notify(wire.field(res, "error") or "unknown entry", vim.log.levels.WARN)
    end
    local lines = { nm .. (wire.field(res, "kind") and ("  [" .. res.kind .. "]") or "") }
    if wire.field(res, "type") then lines[#lines + 1] = "type: " .. res.type end
    if wire.field(res, "line") then lines[#lines + 1] = "line: " .. res.line end
    if wire.field(res, "lede") then
      lines[#lines + 1] = ""
      lines[#lines + 1] = res.lede
    end
    local function paths(label, key)
      local ps = wire.field(res, key)
      if ps and #ps > 0 then
        lines[#lines + 1] = ""
        lines[#lines + 1] = label
        for _, p in ipairs(ps) do lines[#lines + 1] = "  " .. p end
      end
    end
    paths("calls:", "calls")
    paths("referenced by:", "called_by")
    local src = wire.field(res, "src")
    if src then
      lines[#lines + 1] = ""
      for _, l in ipairs(vim.split(src, "\n", { plain = true })) do
        lines[#lines + 1] = l
      end
    end
    ui.float(lines, { filetype = "foil" })
  end)
end

--- gd: the ['defline] mirror slot.
function M.goto_definition()
  local name = M.name_at_cursor()
  if not name then return ui.notify("no name under cursor", vim.log.levels.WARN) end
  local ok, res = wire.request_sync({ op = "describe", module = module.of(0), name = name }, 8000)
  if not ok then return ui.notify(res, vim.log.levels.WARN) end
  local line = res.ok and wire.field(res, "line")
  if type(line) ~= "number" or line < 1 then
    return ui.notify("no definition line for " .. name, vim.log.levels.WARN)
  end
  vim.cmd("normal! m'") -- jumplist
  vim.api.nvim_win_set_cursor(0, { line, 0 })
end

--- Who-calls / called-by into the quickfix list, each entry resolved
--- to its file and defline.
function M.xref(key, name)
  M.describe(name ~= "" and name or nil, function(nm, res)
    if not res.ok then
      return ui.notify(wire.field(res, "error") or "unknown entry", vim.log.levels.WARN)
    end
    local nodes = wire.field(res, key) or {}
    if #nodes == 0 then
      return ui.notify(("no %s for %s"):format(key, nm))
    end
    local items = {}
    for _, node in ipairs(nodes) do
      local mod, entry = module.parse_node(node)
      local item = { text = node }
      if mod and entry then
        item.text = mod .. ":" .. entry
        item.filename = module.file_of(mod, 0)
        local dok, dres = wire.request_sync(
          { op = "describe", module = mod, name = (entry:gsub("/", ".")) }, 8000)
        if dok and dres.ok and type(wire.field(dres, "line")) == "number" then
          item.lnum = dres.line
        end
      end
      items[#items + 1] = item
    end
    vim.fn.setqflist({}, " ", { title = "foil " .. key .. " " .. nm, items = items })
    vim.cmd("copen")
  end)
end

return M
