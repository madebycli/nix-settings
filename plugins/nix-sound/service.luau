--!nonstrict
local exe = noctalia.getConfig("executable")
local queue = {}
local busy = false
local started = false
local function quote(s) return "'" .. tostring(s):gsub("'", "'\\''") .. "'" end
local pump
pump = function()
    if busy or #queue == 0 then return end
    busy = true
    local command = table.remove(queue, 1)
    local accepted = noctalia.runAsync({exe, "request", noctalia.json.encode(command)}, function(result)
        busy = false
        local data = result and noctalia.json.decode(result.stdout or "")
        noctalia.state.set("command-error", data and data.ok and "" or data and data.error or result and result.stderr or "Audio command failed")
        pump()
    end, 6000)
    if not accepted then busy = false; noctalia.state.set("command-error", "Cannot send audio command") end
end
noctalia.state.watch("command", function(message)
    if type(message) ~= "table" then return end
    local command = message.command
    if type(command) ~= "table" then return end
    if command.action == "volume" then
        for i = #queue, 1, -1 do
            local old = queue[i]
            if old.action == "volume" and old.kind == command.kind and old.id == command.id then queue[i] = command; pump(); return end
        end
    end
    table.insert(queue, command); pump()
end)
noctalia.state.watch("open", function(value)
    if value ~= true then return end
    if started then return end
    started = noctalia.runStream(quote(exe) .. " watch", function(line)
        local data = noctalia.json.decode(line)
        if type(data) ~= "table" then return end
        noctalia.state.set("connected", data.ok == true)
        noctalia.state.set("error", data.error or "")
        noctalia.state.set("snapshot", data.ok and data.snapshot or {outputs={}, inputs={}, playback={}, recording={}})
    end)
    if not started then noctalia.state.set("error", "Cannot start Nix Sound; check the executable setting") end
end)
