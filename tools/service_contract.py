#!/usr/bin/env python3
"""Run the actual service lifecycle with ordered native callback/state semantics."""

import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument("--plugin", default="plugins/nix-sound")
p.add_argument("--luau", default="luau")
a = p.parse_args()
source = Path(a.plugin, "service.luau").read_text()
harness = r"""
local clock=0
local values={open=true}
local watchers={}
local streams={}
local commands={}
local available=true
local accepting=true
local native={}
noctalia={
    getConfig=function()return "/engine"end,
    tr=function(k)return k end,
    nowMs=function()return clock end,
    commandExists=function()return available end,
    setUpdateInterval=function()end,
    state={get=function(k)return values[k]end,set=function(k,v)values[k]=v;if watchers[k]then watchers[k](v)end end,
        watch=function(k,fn)watchers[k]=fn end},
    json={decode=function(s)if native[s]then return native[s]end;error("Malformed JSON")end,
        encode=function(value)return value end},
    runStream=function(command,callback)table.insert(streams,{command=command,callback=callback});return accepting end,
    runAsync=function(args,callback)table.insert(commands,{args=args,callback=callback});return true end,
}
"""
checks = r"""
assert(#streams==1,"A panel opened before service load must start without a new watch event")
assert(not values.connected,"No fake ready state before a snapshot")
assert(string.find(streams[1].command,"2>&1",1,true),"Startup diagnostics must reach the callback")
assert(string.find(streams[1].command,"nix-sound-exited",1,true),"Native runStream lacks its own exit callback")
native.ready={ok=true,snapshot={outputs={{id=1}},inputs={},playback={},recording={}}}
streams[1].callback("ready")
assert(values.connected and values.error=="")
update();update();assert(#streams==1,"Healthy connections must not spawn polling commands/duplicate streams")
assert(#commands==0)
streams[1].callback("engine failed before startup")
assert(not values.connected and string.find(values.error,"engine failed",1,true))
native.exit={event="nix-sound-exited",code=7}
streams[1].callback("exit")
clock=999;update();assert(#streams==1,"Restart must use bounded backoff")
clock=1000;update();assert(#streams==2,"An exited stream must restart automatically")
streams[2].callback("ready");assert(values.connected and values.error=="")
streams[1].callback("exit");assert(values.connected,"Stale callbacks must not poison the new connection")
noctalia.state.set("command",{command={action="volume",kind="sink",id=1,volume=.5}})
assert(#commands==1)
commands[1].callback({exitCode=1,stdout="",stderr=""})
assert(values["command-error"]~="","Empty stderr must not hide command failures")
streams[2].callback("exit")
available=false
clock=2000;update()
assert(not values.connected and string.find(values.error,"backend_missing",1,true),"Missing engines must be visible")
assert(#streams==2)
available=true
noctalia.state.set("command",{command={action="refresh"}})
assert(#streams==3,"Reconnect must bypass backoff and re-check the engine")
streams[3].callback("ready");assert(values.connected and values["command-error"]=="")
noctalia.state.set("open",false)
streams[3].callback("exit")
clock=99999;update();assert(#streams==3,"Closed panels must not spin failed startup attempts")
noctalia.state.set("open",true)
assert(#streams==4,"Reopening after an exit must recover")
streams[4].callback("ready")
assert(values.connected)
print("Service startup race, exit/retry, stderr, missing-engine and reopen contracts passed")
"""
with tempfile.TemporaryDirectory(prefix="sound-service-") as directory:
    script = Path(directory, "service.luau")
    script.write_text(harness + "\n" + source + "\n" + checks)
    subprocess.run([a.luau, str(script)], check=True)
