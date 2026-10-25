--!nonstrict
local exe = noctalia.getConfig("executable")
local queue = {}
local busy = false
local started = false
local generation = 0
local retryAt = 0
local retryDelay = 1000
local lastFailure = ""
local function quote(s) return "'" .. tostring(s):gsub("'", "'\\''") .. "'" end
local function decode(text)
    local ok,value=pcall(noctalia.json.decode,text or "")
    return ok and type(value)=="table" and value or nil
end
local function nonempty(text) return type(text)=="string" and text~="" and text or nil end
local icons, iconSeen, iconBusy = {}, {}, false
local resolveIcons
resolveIcons=function(snapshot)
    if iconBusy then return end
    local requests={}
    for _,list in ipairs({snapshot.playback or {},snapshot.recording or {}}) do
        for _,stream in ipairs(list) do
            local key=(stream.icon or "").."\31"..stream.label
            if not iconSeen[key] and #requests<256 then
                iconSeen[key]=true
                table.insert(requests,{key=key,icon=stream.icon or "",label=stream.label})
            end
        end
    end
    if #requests==0 then return end
    iconBusy=true
    local accepted=noctalia.runAsync({exe,"icons",noctalia.json.encode(requests)},function(result)
        iconBusy=false
        local paths=result and result.exitCode==0 and decode(result.stdout)
        if paths then
            for key,path in pairs(paths) do if type(path)=="string" then icons[key]=path end end
            noctalia.state.set("icons",icons)
        end
        resolveIcons(noctalia.state.get("snapshot") or {})
    end,6000)
    if not accepted then iconBusy=false end
end
local function failed(reason)
    started=false
    queue={}
    lastFailure=reason
    noctalia.state.set("connected",false)
    noctalia.state.set("error",reason)
    retryAt=noctalia.nowMs()+retryDelay
    retryDelay=math.min(8000,retryDelay*2)
end
local pump
pump = function()
    if busy or #queue == 0 or noctalia.state.get("connected")~=true then return end
    busy = true
    local command = table.remove(queue, 1)
    local accepted = noctalia.runAsync({exe, "request", noctalia.json.encode(command)}, function(result)
        busy = false
        local data = result and decode(result.stdout)
        local ok=result and result.exitCode==0 and data and data.ok==true
        noctalia.state.set("command-error", ok and "" or data and nonempty(data.error) or result and nonempty(result.stderr) or noctalia.tr("command_failed"))
        pump()
    end, 6000)
    if not accepted then busy = false; noctalia.state.set("command-error", noctalia.tr("command_failed")) end
end
local function start()
    if started or noctalia.state.get("open")~=true then return end
    if not noctalia.commandExists(exe) then
        failed(noctalia.tr("backend_missing").." "..tostring(exe))
        return
    end
    generation+=1
    local current=generation
    lastFailure=""
    noctalia.state.set("connected",false)
    -- runStream has no exit callback and discards stderr. Forward diagnostics and a
    -- final marker explicitly; the host owns/terminates the whole process group.
    local command=quote(exe)..[[ watch 2>&1; code=$?; printf '\n{"event":"nix-sound-exited","code":%d}\n' "$code"]]
    started=true
    local accepted=noctalia.runStream(command,function(line)
        if current~=generation then return end
        local data=decode(line)
        if data and data.event=="nix-sound-exited" then
            failed(noctalia.tr("backend_stopped").." ("..tostring(data.code)..")"..(lastFailure~="" and ("\n"..lastFailure) or ""))
        elseif data and type(data.ok)=="boolean" then
            local wasConnected=noctalia.state.get("connected")==true
            local connected=data.ok==true and type(data.snapshot)=="table"
            noctalia.state.set("connected",connected)
            if connected then
                retryDelay=1000
                lastFailure=""
                noctalia.state.set("error","")
                if not wasConnected then noctalia.state.set("command-error","") end
                noctalia.state.set("snapshot",data.snapshot)
                resolveIcons(data.snapshot)
                pump()
            else
                lastFailure=nonempty(data.error) or noctalia.tr("backend_stopped")
                noctalia.state.set("error",lastFailure)
            end
        else
            lastFailure=string.sub(line,1,1500)
            noctalia.state.set("connected",false)
            noctalia.state.set("error",lastFailure)
        end
    end)
    if not accepted then failed(noctalia.tr("backend_stopped")) end
end
function update()
    if not started and noctalia.state.get("open")==true and noctalia.nowMs()>=retryAt then start() end
end
noctalia.state.watch("command", function(message)
    if type(message) ~= "table" then return end
    local command = message.command
    if type(command) ~= "table" then return end
    if command.action=="refresh" and not iconBusy then
        iconSeen={};resolveIcons(noctalia.state.get("snapshot") or {})
    end
    if command.action=="refresh" and not started then
        retryAt=0;retryDelay=1000;noctalia.state.set("command-error","");start();return
    end
    if noctalia.state.get("connected")~=true then
        noctalia.state.set("command-error",noctalia.tr("connecting"));return
    end
    if command.action == "volume" then
        for i = #queue, 1, -1 do
            local old = queue[i]
            if old.action == "volume" and old.kind == command.kind and old.id == command.id then queue[i] = command; pump(); return end
        end
    end
    table.insert(queue, command); pump()
end)
noctalia.state.watch("open", function(value)
    if value==true then retryAt=0;update() end
end)
noctalia.state.set("connected",false)
noctalia.state.set("error","")
noctalia.setUpdateInterval(1000)
-- State watches only report future changes. Pick up panels opened before service load.
update()
