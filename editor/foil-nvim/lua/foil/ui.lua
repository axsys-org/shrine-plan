-- Small UI helpers: a self-closing float and a notifier.

local M = {}

function M.notify(msg, level)
  vim.notify(msg, level or vim.log.levels.INFO, { title = "foil" })
end

--- Show lines in a float anchored at the cursor; closes on movement.
function M.float(lines, opts)
  opts = opts or {}
  if type(lines) == "string" then lines = vim.split(lines, "\n", { plain = true }) end
  if #lines == 0 then lines = { "(nothing)" } end
  local width = 0
  for _, l in ipairs(lines) do width = math.max(width, vim.fn.strdisplaywidth(l)) end
  width = math.min(math.max(width, 10), math.floor(vim.o.columns * 0.8))
  local height = math.min(#lines, math.floor(vim.o.lines * 0.6))
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.bo[buf].modifiable = false
  vim.bo[buf].bufhidden = "wipe"
  if opts.filetype then vim.bo[buf].filetype = opts.filetype end
  local win = vim.api.nvim_open_win(buf, false, {
    relative = "cursor", row = 1, col = 0,
    width = width, height = height,
    style = "minimal", border = "rounded",
  })
  local group = vim.api.nvim_create_augroup("FoilFloat" .. win, { clear = true })
  vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI", "BufLeave", "InsertEnter" }, {
    group = group, once = true,
    callback = function()
      if vim.api.nvim_win_is_valid(win) then vim.api.nvim_win_close(win, true) end
    end,
  })
  return win
end

return M
