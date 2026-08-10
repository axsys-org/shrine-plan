-- Eval: an expression against the buffer's module, result in a float
-- ("value : type", the law for law-like values) — C-x C-e for the
-- namespace.

local wire = require("foil.wire")
local module = require("foil.module")
local ui = require("foil.ui")

local M = {}

local function render(res)
  local lines = {}
  if res.ok then
    local value = wire.field(res, "value") or ""
    local ty = wire.field(res, "type")
    lines[1] = ty and (value .. " : " .. ty) or value
    local law = wire.field(res, "law")
    if law then
      lines[#lines + 1] = ""
      for _, l in ipairs(vim.split(law, "\n", { plain = true })) do
        lines[#lines + 1] = l
      end
    end
  else
    lines[1] = "error: " .. (wire.field(res, "error") or "?"):gsub("\n.*", " …")
    for _, d in ipairs(res.diags or {}) do
      lines[#lines + 1] = ("  %s:%s  %s"):format(d.line or "?", d.col or "?", d.msg or "")
    end
  end
  return lines
end

--- Evaluate text (with an optional prelude of repl vars).
function M.eval_text(text, prelude, cb)
  local mod = module.of(0)
  local full = (prelude and prelude ~= "") and (prelude .. text) or text
  wire.request({ op = "eval", module = mod, text = full }, function(ok, res)
    if not ok then return ui.notify(res, vim.log.levels.WARN) end
    if cb then return cb(res) end
    ui.float(render(res))
  end)
end

function M.eval_line()
  M.eval_text(vim.trim(vim.api.nvim_get_current_line()))
end

--- Evaluate the last visual selection.
function M.eval_selection()
  local s = vim.fn.getpos("'<")
  local e = vim.fn.getpos("'>")
  local last = vim.api.nvim_buf_get_lines(0, e[2] - 1, e[2], false)[1] or ""
  local endcol = math.min(e[3], #last) -- linewise '> reports v:maxcol
  local lines = vim.api.nvim_buf_get_text(0, s[2] - 1, s[3] - 1, e[2] - 1, endcol, {})
  M.eval_text(vim.trim(table.concat(lines, "\n")))
end

--- :FoilEval {expr}
function M.eval_arg(text)
  if text and text ~= "" then M.eval_text(text) else M.eval_line() end
end

M.render = render

return M
