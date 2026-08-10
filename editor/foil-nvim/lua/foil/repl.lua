-- The in-editor REPL: a prompt buffer sharing the buddy's image over
-- the wire.  Repl variables live CLIENT-side and ride each eval as a
-- textual prelude (the terminal repl's own trick — vars survive
-- resyncs by construction).
--
--   <expr>        evaluate against the focus module
--   name = expr   bind a repl variable
--   :m <mod>      switch focus     :vars  list vars
--   :c [mod]      recompile        :t [mod]  doctests
--   :q            close

local wire = require("foil.wire")
local module = require("foil.module")

local M = {}

local state = { buf = nil, focus = "sept", vars = {} } -- vars: {name, expr} pairs

local function append(lines)
  if not (state.buf and vim.api.nvim_buf_is_valid(state.buf)) then return end
  local last = vim.api.nvim_buf_line_count(state.buf)
  vim.api.nvim_buf_set_lines(state.buf, last, last, false, lines)
  for _, win in ipairs(vim.fn.win_findbuf(state.buf)) do
    vim.api.nvim_win_set_cursor(win, { vim.api.nvim_buf_line_count(state.buf), 0 })
  end
end

local function prelude()
  local parts = {}
  for _, v in ipairs(state.vars) do
    parts[#parts + 1] = "=  " .. v[1] .. "  " .. v[2] .. "\n"
  end
  return table.concat(parts)
end

local function set_var(name, expr)
  for i, v in ipairs(state.vars) do
    if v[1] == name then table.remove(state.vars, i); break end
  end
  state.vars[#state.vars + 1] = { name, expr }
end

local function render_eval(res)
  if res.ok then
    local out = { "value: " .. (wire.field(res, "value") or "") }
    if wire.field(res, "type") then out[#out + 1] = "type:  " .. res.type end
    if wire.field(res, "law") then
      out[#out + 1] = ""
      vim.list_extend(out, vim.split(res.law, "\n", { plain = true }))
    end
    return out
  end
  local out = { "error: " .. (wire.field(res, "error") or "?") }
  return vim.split(table.concat(out, "\n"), "\n", { plain = true })
end

local function dispatch(text)
  text = vim.trim(text)
  if text == "" then text = ":c" end
  if text == ":q" then
    vim.api.nvim_buf_delete(state.buf, { force = true })
    state.buf = nil
    return
  end
  if text == ":vars" then
    if #state.vars == 0 then return append({ "no vars" }) end
    local out = {}
    for _, v in ipairs(state.vars) do out[#out + 1] = "  " .. v[1] .. " = " .. v[2] end
    return append(out)
  end
  local mod = text:match("^:m%s+(%S+)$")
  if mod then
    state.focus = mod
    return append({ "focus: " .. mod })
  end
  local cmod = text:match("^:c%s*(%S*)$")
  if cmod then
    local target = cmod ~= "" and cmod or state.focus
    return wire.request({ op = "compile", module = target }, function(ok, res)
      if not ok then return append({ res }) end
      if res.ok then
        append(vim.split(wire.field(res, "report") or "compiled", "\n", { plain = true }))
      else
        local out = { "error: " .. (wire.field(res, "error") or "?") }
        for _, d in ipairs(res.diags or {}) do
          out[#out + 1] = ("  %s:%s  %s"):format(d.line or "?", d.col or "?", d.msg or "")
        end
        append(out)
      end
    end)
  end
  local tmod = text:match("^:t%s*(%S*)$")
  if tmod then
    local target = tmod ~= "" and tmod or state.focus
    return wire.request({ op = "doctest", module = target }, function(ok, res)
      if not ok then return append({ res }) end
      append({ res.ok and ("done: " .. res.passed .. " passed, " .. res.failed .. " failed")
        or ("error: " .. (wire.field(res, "error") or "?")) })
    end)
  end
  if text:match("^:") then
    return append({ "unknown command " .. text })
  end
  local name, expr = text:match("^([%l%d_]+)%s+=%s+(.+)$")
  if not name then name, expr = text:match("^([%l%d_]+) = (.+)$") end
  if name and expr then set_var(name, expr) end
  local body = expr or text
  wire.request(
    { op = "eval", module = state.focus, text = prelude() .. body },
    function(ok, res)
      if not ok then return append({ res }) end
      append(render_eval(res))
    end)
end

function M.open()
  if state.buf and vim.api.nvim_buf_is_valid(state.buf) then
    for _, win in ipairs(vim.fn.win_findbuf(state.buf)) do
      return vim.api.nvim_set_current_win(win)
    end
    vim.cmd("botright 12split")
    return vim.api.nvim_win_set_buf(0, state.buf)
  end
  local frommod = module.of(0)
  if vim.bo.filetype == "foil" and frommod ~= "" then state.focus = frommod end
  vim.cmd("botright 12split")
  local buf = vim.api.nvim_create_buf(false, true)
  state.buf = buf
  vim.api.nvim_win_set_buf(0, buf)
  vim.api.nvim_buf_set_name(buf, "foil://repl")
  vim.bo[buf].buftype = "prompt"
  vim.bo[buf].bufhidden = "hide"
  vim.bo[buf].swapfile = false
  vim.fn.prompt_setprompt(buf, state.focus .. "> ")
  vim.fn.prompt_setcallback(buf, function(text)
    dispatch(text)
    if state.buf then vim.fn.prompt_setprompt(state.buf, state.focus .. "> ") end
  end)
  append({ "the namespace repl (wire) — :m :c :t :vars :q" })
  vim.cmd("startinsert")
end

return M
