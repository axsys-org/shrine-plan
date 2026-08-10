-- Compile-on-save: the wire's compile op is the resync (report,
-- changeset, mirror remount); its diags land in vim.diagnostic, its
-- report in the echo area — save, and the verdict is under your eyes
-- before they move (the buddy promise, in-editor).

local wire = require("foil.wire")
local module = require("foil.module")
local ui = require("foil.ui")

local M = {}

M.ns = vim.api.nvim_create_namespace("foil-wire")

local function to_diagnostics(res)
  local out = {}
  for _, d in ipairs(res.diags or {}) do
    if type(d.line) == "number" and d.line > 0 then
      out[#out + 1] = {
        lnum = d.line - 1,
        col = math.max(0, (tonumber(d.col) or 1) - 1),
        message = d.msg or "error",
        severity = vim.diagnostic.severity.ERROR,
        source = "foil",
      }
    end
  end
  if #out == 0 then
    out[1] = {
      lnum = 0, col = 0,
      message = wire.field(res, "error") or "compile failed",
      severity = vim.diagnostic.severity.ERROR,
      source = "foil",
    }
  end
  return out
end

function M.compile(bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  local mod = module.of(bufnr)
  wire.request({ op = "compile", module = mod }, function(ok, res)
    if not ok then return ui.notify(res, vim.log.levels.WARN) end
    if not vim.api.nvim_buf_is_valid(bufnr) then return end
    if res.ok then
      vim.diagnostic.set(M.ns, bufnr, {})
      ui.notify((wire.field(res, "report") or "compiled"):gsub("\n", " · "))
    else
      vim.diagnostic.set(M.ns, bufnr, to_diagnostics(res))
      local first = (res.diags or {})[1]
      ui.notify(first and first.msg or wire.field(res, "error") or "compile failed",
        vim.log.levels.ERROR)
    end
  end)
end

function M.doctest(bufnr)
  local mod = module.of(bufnr or 0)
  wire.request({ op = "doctest", module = mod }, function(ok, res)
    if not ok then return ui.notify(res, vim.log.levels.WARN) end
    if res.ok then
      local failed = tonumber(res.failed) or 0
      ui.notify(("doctests %s: %s passed, %s failed"):format(mod, res.passed, res.failed),
        failed > 0 and vim.log.levels.ERROR or vim.log.levels.INFO)
    else
      ui.notify(wire.field(res, "error") or "doctest failed", vim.log.levels.ERROR)
    end
  end)
end

return M
