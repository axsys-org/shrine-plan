-- Saved-source compiler and style diagnostics from the persistent wire service.
local wire = require("foil.wire")
local module = require("foil.module")
local ui = require("foil.ui")
local M = {}
M.ns = vim.api.nvim_create_namespace("foil-wire")
M.lint_ns = vim.api.nvim_create_namespace("foil-lint")
local pending = {}

local function to_diagnostics(rows, mod, source)
  local out, foreign = {}, {}
  for _, d in ipairs(rows) do
    local severity = d.level == "warning" and vim.diagnostic.severity.WARN
      or vim.diagnostic.severity.ERROR
    if d.module ~= nil and d.module ~= vim.NIL and d.module ~= mod then
      foreign[#foreign + 1] = ("%s:%s  %s"):format(d.module, d.line or "?", d.msg or "")
    else
      out[#out + 1] = {
        lnum = math.max(0, (tonumber(d.line) or 1) - 1),
        col = math.max(0, (tonumber(d.col) or 1) - 1),
        message = d.msg or "error", severity = severity, source = source,
        code = wire.field(d, "rule"),
      }
    end
  end
  if #foreign > 0 then
    out[#out + 1] = {
      lnum = 0, col = 0, message = "In other modules:\n" .. table.concat(foreign, "\n"),
      severity = vim.diagnostic.severity.ERROR, source = source,
    }
  end
  return out
end

local function diagnose(op, bufnr)
  bufnr = bufnr or vim.api.nvim_get_current_buf()
  if bufnr == 0 then bufnr = vim.api.nvim_get_current_buf() end
  local mod = module.of(bufnr)
  local tick = vim.api.nvim_buf_get_changedtick(bufnr)
  local name = vim.api.nvim_buf_get_name(bufnr)
  local token = {}
  pending[bufnr] = token
  wire.request({ op = op, module = mod }, function(ok, res)
    if pending[bufnr] ~= token or not vim.api.nvim_buf_is_valid(bufnr)
      or vim.api.nvim_buf_get_changedtick(bufnr) ~= tick
      or vim.api.nvim_buf_get_name(bufnr) ~= name then return end
    pending[bufnr] = nil
    if not ok then return ui.notify(res, vim.log.levels.WARN) end
    local compiler, lint = {}, {}
    for _, d in ipairs(res.diags or {}) do
      local rows = (op == "lint" or d.source == "foil-lint") and lint or compiler
      rows[#rows + 1] = d
    end
    if not res.ok and #compiler == 0 and (op ~= "lint" or #lint == 0) then
      local rows = op == "lint" and lint or compiler
      rows[#rows + 1] = { msg = wire.field(res, "error") or (op .. " failed") }
    end
    if op == "compile" then
      vim.diagnostic.set(M.ns, bufnr, to_diagnostics(compiler, mod, "foil"))
    end
    vim.diagnostic.set(M.lint_ns, bufnr, to_diagnostics(lint, mod, "foil-lint"))
    if res.ok then
      local report = wire.field(res, "report") or (op == "lint" and "Linted " .. mod or "compiled")
      ui.notify((report:gsub("\n", " · ")) .. (" · %d lint findings"):format(#lint))
    else
      local first = (res.diags or {})[1]
      ui.notify(first and first.msg or wire.field(res, "error") or (op .. " failed"), vim.log.levels.ERROR)
    end
  end)
end

function M.compile(bufnr) diagnose("compile", bufnr) end
function M.lint(bufnr) diagnose("lint", bufnr) end

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
