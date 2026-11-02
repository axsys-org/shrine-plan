-- A buffer-local declaration index, not a type checker. In particular, member
-- dispatch, imported names and compiler-generated declarations need the server.
local M = {}
local cache = {}

local function index(buf)
  if buf == nil or buf == 0 then buf = vim.api.nvim_get_current_buf() end
  local tick = vim.api.nvim_buf_get_changedtick(buf)
  local ft = vim.bo[buf].filetype
  if cache[buf] and cache[buf].tick == tick and cache[buf].ft == ft then return cache[buf].entries end
  local entries, stack = {}, {}
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local grove = vim.bo[buf].filetype == 'grove'
  for row, line in ipairs(lines) do
    local indent = vim.fn.strdisplaywidth(line:match('^%s*'))
    if line:match('%S') and not line:match("^%s*'%s") and not line:match("^%s*'%s*$") then
      while #stack > 0 and stack[#stack].indent >= indent do
        stack[#stack].last = row - 1
        table.remove(stack)
      end
    end
    local name = line:match('^%s*%+%s+([%w_/-]+)')
    if not name and grove then
      name = line:match('^%s*([%w_/-]+)%s*=%s*$')
      if not name then name = line:match('^%s*"([^"]+)"%s*=%s*$') end
    end
    if name then
      local parent = stack[#stack]
      local entry = { name = parent and (parent.name .. '/' .. name) or name,
        label = name, line = row, last = #lines, indent = indent, parent = parent }
      entries[#entries + 1] = entry
      stack[#stack + 1] = entry
    end
  end
  cache[buf] = { tick = tick, ft = ft, entries = entries }
  return entries
end

function M.scope(buf, row)
  local scope
  for _, entry in ipairs(index(buf or 0)) do
    if entry.line <= row and row <= entry.last then scope = entry end
  end
  return scope
end

function M.resolve(word, buf, row)
  if not word then return nil end
  local anchor = word:sub(1, 2)
  if anchor == ';/' or anchor == '#/' then
    local scope = M.scope(buf or 0, row or vim.fn.line('.'))
    if anchor == ';/' and scope then scope = scope.parent end
    return (scope and (scope.name .. '/') or '') .. word:sub(3)
  end
  return word
end

local function token_char(c) return c:match('[%w_./;#%-]') ~= nil end

function M.start(line, col)
  -- col is the zero-based insertion column, as expected by omnifunc.
  while col > 0 and token_char(line:sub(col, col)) do col = col - 1 end
  return col
end

function M.word()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1
  local group = vim.fn.synIDattr(vim.fn.synID(vim.fn.line('.'), col, 1), 'name')
  if group:match('Comment') or group:match('String') or group:match('Quip') then return nil end
  if not token_char(line:sub(col, col)) then return nil end
  local start = M.start(line, col)
  local last = col
  while last < #line and token_char(line:sub(last + 1, last + 1)) do last = last + 1 end
  if line:sub(start, start) == "'" then return nil end -- quoted data
  return line:sub(start + 1, last)
end

function M.find(word)
  if not word then
    local scope = M.scope(0, vim.fn.line('.'))
    if scope and scope.line == vim.fn.line('.') and M.word() == scope.label then return scope end
  end
  local name = M.resolve(word or M.word())
  if not name then return nil end
  for _, entry in ipairs(index(0)) do
    if entry.name == name then return entry end
  end
end

function M.complete(base)
  local prefix = M.resolve(base)
  local items, seen = {}, {}
  for _, entry in ipairs(index(0)) do
    if entry.name:sub(1, #prefix) == prefix and not seen[entry.name] then
      seen[entry.name] = true
      items[#items + 1] = { word = base .. entry.name:sub(#prefix + 1), menu = '[local]' }
    end
  end
  return items
end

function M.goto_definition()
  local entry = M.find()
  if not entry then
    return require('foil.ui').notify('no local declaration under cursor', vim.log.levels.INFO)
  end
  vim.cmd("normal! m'")
  vim.api.nvim_win_set_cursor(0, { entry.line, entry.indent })
end

function M.inspect(name)
  local entry = M.find(name ~= '' and name or nil)
  if not entry then
    return require('foil.ui').notify('no local declaration under cursor', vim.log.levels.INFO)
  end
  local lines = vim.api.nvim_buf_get_lines(0, entry.line - 1, math.min(entry.last, entry.line + 24), false)
  if entry.last > entry.line + 24 then lines[#lines + 1] = '…' end
  require('foil.ui').float(lines, { filetype = vim.bo.filetype })
end

vim.api.nvim_create_autocmd('BufWipeout', {
  callback = function(ev) cache[ev.buf] = nil end,
})

return M
