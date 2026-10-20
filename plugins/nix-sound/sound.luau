--!nonstrict
local host = require("./host.luau")
local opened = false
local nonce = 0
local lastGeometry = ""
local snapshot = noctalia.state.get("snapshot") or {outputs={}, inputs={}, playback={}, recording={}}
local render
local function tr(key) return noctalia.tr(key) end
local function send(command)
    nonce += 1
    noctalia.state.set("command", {nonce=nonce, command=command})
end
local function button(text, glyph, click)
    return ui.button({text=text, glyph=glyph, onClick=click, controlSize="sm"})
end
local function volume(node)
    return ui.column({gap=6, align="stretch"}, {
        ui.row({align="center", gap=8}, {
            ui.label({text=tr("volume"), color="on_surface_variant", flexGrow=1}),
            ui.label({text=tostring(math.floor(node.volume*100+0.5)).."%", color="primary"}),
            button(tr(node.muted and "unmute" or "mute"), node.muted and "volume-off" or "volume", function()
                send({action="mute", kind=node.kind, id=node.id, muted=not node.muted})
            end),
        }),
        ui.slider({key=node.kind..tostring(node.id), min=0, max=1, step=0.01, value=node.volume,
            onDragEnd=function(value) send({action="volume", kind=node.kind, id=node.id, volume=tonumber(value)}) end}),
    })
end
local function selector(devices, selected, callback)
    local labels = {}; local index = 0
    for i,device in ipairs(devices) do labels[i]=device.label; if device.id == selected then index=i-1 end end
    return ui.select({options=labels, selectedIndex=index, flexGrow=1, enabled=#devices>0,
        onChange=function(i) local device=devices[(tonumber(i) or 0)+1]; if device then callback(device) end end})
end
local function master(devices, title, glyph)
    local current=devices[1]
    for _,device in ipairs(devices) do if device.is_default then current=device;break end end
    local nodes={ui.row({gap=8,align="center"},{ui.glyph({name=glyph,size=22,color="primary"}),ui.label({text=tr(title),fontSize=20,fontWeight="bold"})})}
    if current then
        table.insert(nodes,selector(devices,current.id,function(device)send({action="default",kind=device.kind,id=device.id})end))
        table.insert(nodes,volume(current))
    else table.insert(nodes,ui.label({text=tr("no_devices"),color="on_surface_variant"})) end
    return ui.column(host.card({flexGrow=1}),nodes)
end
local function streams(list, devices, title, width, height)
    local nodes={}
    for _,stream in ipairs(list) do
        local content={ui.label({text=stream.label,maxLines=1,fontSize=16,fontWeight="medium"}),
            selector(devices,stream.device,function(device)send({action="route",kind=stream.kind,id=stream.id,device=device.id})end),volume(stream)}
        table.insert(nodes,ui.column(host.card({key=stream.kind..tostring(stream.id)}),content))
    end
    if #nodes==0 then table.insert(nodes,ui.label({text=tr("no_streams"),color="on_surface_variant",maxLines=2})) end
    return ui.column({width=width,height=height+32,align="stretch",gap=12}, {
        ui.label({text=tr(title),fontSize=16,fontWeight="medium",color="on_surface_variant"}),
        ui.scroll({key=title,flexGrow=1,align="stretch",gap=10},nodes),
    })
end
render=function()
    if not opened then return end
    local width,height=host.dimensions(1120,720)
    local narrow=width<760
    local error=noctalia.state.get("command-error") or ""
    if error=="" then error=noctalia.state.get("error") or "" end
    local nodes={ui.row({gap=8,align="center"},{
        ui.label({text=tr("title"),fontSize=20,fontWeight="bold",flexGrow=1}),
        button("","refresh",function()send({action="refresh"})end),
        ui.button({text="",glyph="x",onClick=function()panel.close()end,visible=(host.style()).show_close_buttons,controlSize="sm"}),
    })}
    if error~="" then table.insert(nodes,ui.label({text=error,color="error",maxLines=2})) end
    if narrow then
        -- One outer scroll keeps every control reachable even on short/high-DPI screens.
        local body={master(snapshot.outputs,"output","volume"),master(snapshot.inputs,"input","microphone"),
            streams(snapshot.playback,snapshot.outputs,"playback",width,200),streams(snapshot.recording,snapshot.inputs,"recording",width,200)}
        table.insert(nodes,ui.scroll({key="compact-body",flexGrow=1,align="stretch",gap=14},body))
    else
        local column=(width-16)/2
        table.insert(nodes,ui.scroll({key="wide-body",flexGrow=1,align="stretch"},{ui.row({gap=16,align="stretch"},{
            ui.column({width=column,align="stretch",gap=16},{master(snapshot.outputs,"output","volume"),streams(snapshot.playback,snapshot.outputs,"playback",column,math.max(60,height-340))}),
            ui.column({width=column,align="stretch",gap=16},{master(snapshot.inputs,"input","microphone"),streams(snapshot.recording,snapshot.inputs,"recording",column,math.max(60,height-340))}),
        })}))
    end
    lastGeometry=tostring(width)..":"..tostring(height)..noctalia.json.encode(host.appearance())
    panel.render(ui.column({align="stretch",flexGrow=1,gap=16},nodes))
end
noctalia.state.watch("snapshot",function(value) snapshot=value or snapshot;render()end)
noctalia.state.watch("error",render)
noctalia.state.watch("command-error",render)
function onOpen()
    host.openViewport();opened=true;noctalia.state.set("open",true);panel.setWantsSecondTicks(true);render()
end
function onClose() opened=false;noctalia.state.set("open",false);panel.setWantsSecondTicks(false) end
function update()
    local w,h=host.dimensions(1120,720)
    if tostring(w)..":"..tostring(h)..noctalia.json.encode(host.appearance())~=lastGeometry then render() end
end
