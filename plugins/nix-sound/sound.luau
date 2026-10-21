--!nonstrict
local host = require("./host.luau")
local opened = false
local nonce = 0
local lastGeometry = ""
local pending = {}
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
    local key=node.kind..tostring(node.id)
    return ui.row({gap=6, align="center"}, {
        ui.slider({key=key, flexGrow=1, min=0, max=1, step=0.01, value=node.volume, controlSize="sm",
            -- Native onChange receives the value; onDragEnd has no arguments (also for keyboard/scroll).
            onChange=function(value)
                local number=tonumber(value)
                if number then pending[key]=math.clamp(number,0,1) end
            end,
            onDragEnd=function()
                local value=pending[key]
                if value~=nil then
                    pending[key]=nil
                    send({action="volume",kind=node.kind,id=node.id,volume=value})
                end
            end}),
        -- Label width is not a fixed layout constraint in the host. Reserve the entire
        -- percentage column so 9%, 90% and 100% never change the slider's track length.
        ui.row({width=48,justify="end",align="center"},{
            ui.label({text=tostring(math.floor(node.volume*100+0.5)).."%",textAlign="right",color="primary"}),
        }),
        ui.button({text=tr("mute"),width=80,controlSize="sm",selected=node.muted,
            tooltip=tr(node.muted and "unmute" or "mute"),onClick=function()
                send({action="mute",kind=node.kind,id=node.id,muted=not node.muted})
            end}),
    })
end
local function selector(devices, selected, callback)
    local labels = {}; local index = 0
    for i,device in ipairs(devices) do labels[i]=device.label; if device.id == selected then index=i-1 end end
    return ui.select({options=labels, selectedIndex=index, flexGrow=1, enabled=#devices>0, controlSize="sm",
        onChange=function(i) local device=devices[(tonumber(i) or 0)+1]; if device then callback(device) end end})
end
local function master(devices, title, glyph)
    local current=devices[1]
    for _,device in ipairs(devices) do if device.is_default then current=device;break end end
    local nodes={ui.row({gap=6,align="center"},{ui.glyph({name=glyph,size=22,color="primary"}),ui.label({text=tr(title),fontSize=20,fontWeight="bold",maxLines=1})})}
    if current then
        table.insert(nodes,ui.row({align="stretch"},{selector(devices,current.id,function(device)send({action="default",kind=device.kind,id=device.id})end)}))
        table.insert(nodes,volume(current))
    else table.insert(nodes,ui.label({text=tr("no_devices"),color="on_surface_variant"})) end
    return ui.column(host.card({gap=6,padding=8}),nodes)
end
local function appIcon(stream)
    local path=noctalia.appIconPath(stream.icon~="" and stream.icon or stream.label,24)
    if not path then path=noctalia.appIconPath(stream.label,24) end
    if path then return ui.image({path=path,width=24,height=24,fit="contain"}) end
    return ui.glyph({name=stream.kind=="source-output" and "microphone" or "apps",size=24,color="primary"})
end
local function streams(list, devices, title, compact)
    local nodes={}
    for _,stream in ipairs(list) do
        local content={ui.row({gap=6,align="center"},{appIcon(stream),
            ui.label({text=stream.label,maxWidth=compact and 90 or 120,maxLines=1,fontSize=16,fontWeight="medium"}),
            selector(devices,stream.device,function(device)send({action="route",kind=stream.kind,id=stream.id,device=device.id})end)}),volume(stream)}
        table.insert(nodes,ui.column(host.card({key=stream.kind..tostring(stream.id),gap=4,padding=8}),content))
    end
    if #nodes==0 then table.insert(nodes,ui.label({text=tr("no_streams"),color="on_surface_variant",maxLines=2})) end
    local heading=ui.label({text=tr(title),fontSize=16,fontWeight="medium",color="on_surface_variant"})
    if compact then
        table.insert(nodes,1,heading)
        return ui.column({align="stretch",gap=6},nodes)
    end
    return ui.column({flexGrow=1,align="stretch",gap=6}, {
        heading,ui.scroll({key=title,flexGrow=1,align="stretch",gap=6},nodes),
    })
end
render=function()
    if not opened then return end
    local width,height=host.dimensions(1600,900)
    local narrow=width<760
    local error=noctalia.state.get("command-error") or ""
    if error=="" then error=noctalia.state.get("error") or "" end
    local nodes={ui.row({gap=6,align="center"},{
        ui.label({text=tr("title"),fontSize=20,fontWeight="bold",flexGrow=1}),
        button("","refresh",function()send({action="refresh"})end),
        ui.button({text="",glyph="x",onClick=function()panel.close()end,visible=(host.style()).show_close_buttons,controlSize="sm"}),
    })}
    if error~="" then table.insert(nodes,ui.label({text=error,color="error",maxLines=2})) end
    if narrow then
        local body={master(snapshot.outputs,"output","volume"),master(snapshot.inputs,"input","microphone"),
            streams(snapshot.playback,snapshot.outputs,"playback",true),streams(snapshot.recording,snapshot.inputs,"recording",true)}
        table.insert(nodes,ui.scroll({key="compact-body",flexGrow=1,align="stretch",gap=8},body))
    else
        -- Let native flex allocate the actual compositor viewport, including bars and panel padding.
        -- Fixed monitor-derived child widths can exceed it and clip the left/right fields.
        table.insert(nodes,ui.row({key="wide-body",flexGrow=1,gap=8,align="stretch"},{
            ui.column({flexGrow=1,align="stretch",gap=8},{master(snapshot.outputs,"output","volume"),streams(snapshot.playback,snapshot.outputs,"playback",false)}),
            ui.column({flexGrow=1,align="stretch",gap=8},{master(snapshot.inputs,"input","microphone"),streams(snapshot.recording,snapshot.inputs,"recording",false)}),
        }))
    end
    lastGeometry=tostring(width)..":"..tostring(height)..noctalia.json.encode(host.appearance())
    panel.render(ui.column({align="stretch",flexGrow=1,gap=8},nodes))
end
noctalia.state.watch("snapshot",function(value) snapshot=value or snapshot;render()end)
noctalia.state.watch("error",render)
noctalia.state.watch("command-error",render)
function onOpen()
    host.openViewport();opened=true;noctalia.state.set("open",true);panel.setWantsSecondTicks(true);render()
end
function onClose() opened=false;noctalia.state.set("open",false);panel.setWantsSecondTicks(false) end
function update()
    local w,h=host.dimensions(1600,900)
    if tostring(w)..":"..tostring(h)..noctalia.json.encode(host.appearance())~=lastGeometry then render() end
end
