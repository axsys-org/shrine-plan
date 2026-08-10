-- The wire client: one JSON request per TCP connection, one JSON
-- reply, server closes (doc/buddy-wire.md).  Async with a callback,
-- plus a vim.wait sync wrapper for omnifunc/gd.

local uv = vim.uv or vim.loop

local M = {}

M.config = {
  host = "127.0.0.1",
  port = 8679,
  timeout = 30000, -- compiles can be slow; evals are not
}

function M.setup(opts)
  M.config = vim.tbl_extend("force", M.config, opts or {})
end

--- Send one request table; cb(ok, result) on the main loop.
--- ok=false => result is an error string.  ok=true => result is the
--- decoded response object (which itself carries .ok).
function M.request(req, cb)
  local tcp = uv.new_tcp()
  local chunks = {}
  local done = false
  local function finish(ok, res)
    if done then return end
    done = true
    if not tcp:is_closing() then tcp:close() end
    vim.schedule(function() cb(ok, res) end)
  end
  local timer = uv.new_timer()
  timer:start(M.config.timeout, 0, function()
    timer:stop(); timer:close()
    finish(false, "wire timeout")
  end)
  tcp:connect(M.config.host, M.config.port, function(err)
    if err then
      return finish(false, ("connect to %s:%d failed (%s) — is x/repl running?")
        :format(M.config.host, M.config.port, err))
    end
    tcp:read_start(function(rerr, chunk)
      if rerr then return finish(false, rerr) end
      if chunk then
        chunks[#chunks + 1] = chunk
      else -- EOF: the server wrote its line and closed
        local body = table.concat(chunks)
        local ok, decoded = pcall(vim.json.decode, body)
        if ok then finish(true, decoded)
        else finish(false, "undecodable response: " .. body:sub(1, 200)) end
      end
    end)
    tcp:write(vim.json.encode(req) .. "\n")
  end)
end

--- Blocking variant (for completion and gd, which need a value now).
function M.request_sync(req, timeout)
  local result
  M.request(req, function(ok, res) result = { ok = ok, res = res } end)
  vim.wait(timeout or M.config.timeout, function() return result ~= nil end, 20)
  if not result then return false, "wire timeout" end
  return result.ok, result.res
end

--- nil out vim.NIL so callers can use `or` defaults.
function M.field(res, key)
  local v = res[key]
  if v == vim.NIL then return nil end
  return v
end

return M
