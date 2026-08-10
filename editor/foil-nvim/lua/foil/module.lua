-- Buffer -> module name.  Module m lives at <root>/foil/<m>.foil
-- (helm-build's save writes "foil/" .. mod .. ".foil"), so the name is
-- everything after the LAST "/foil/" component, extension stripped —
-- nested names (apps/chat) fall out naturally.  b:foil_module
-- overrides.

local M = {}

function M.of(bufnr)
  bufnr = bufnr or 0
  local override = vim.b[bufnr].foil_module
  if override and override ~= "" then return override end
  local path = vim.api.nvim_buf_get_name(bufnr)
  local mod = path:match(".*/foil/(.+)%.foil$")
  if mod then return mod end
  return vim.fn.fnamemodify(path, ":t:r")
end

--- The source root holding foil/: for mapping mirror paths back to
--- files.  nil when the buffer is not under a foil/ tree.
function M.root(bufnr)
  local path = vim.api.nvim_buf_get_name(bufnr or 0)
  return path:match("(.*/foil/)") and path:gsub("/foil/.*$", "/foil/") or nil
end

--- A mirror node path "/boot/<mod..>/<n>/<name..>" -> module, name
--- (both "/"-joined), or nil.
function M.parse_node(node)
  local rest = node:match("^/boot/(.+)$")
  if not rest then return nil end
  local segs = vim.split(rest, "/", { plain = true })
  for i, s in ipairs(segs) do
    if s:match("^%d+$") then
      local mod = table.concat(vim.list_slice(segs, 1, i - 1), "/")
      local name = table.concat(vim.list_slice(segs, i + 1), "/")
      if mod ~= "" and name ~= "" then return mod, name end
      return nil
    end
  end
  -- no count marker: the whole thing is a module node
  return rest, nil
end

--- The file for a module, resolved against the current buffer's root.
function M.file_of(mod, bufnr)
  local root = M.root(bufnr)
  if not root then return nil end
  return root .. mod .. ".foil"
end

return M
