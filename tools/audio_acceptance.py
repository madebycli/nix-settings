#!/usr/bin/env python3
"""Exercise the real backend against an isolated Pulse server; no desktop/hardware claims."""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time

p = argparse.ArgumentParser()
p.add_argument("--binary", default="target/debug/nix-settings")
p.add_argument("--module-dir")
p.add_argument("--result")
args = p.parse_args()
binary = str(Path(args.binary).resolve())
children = []
checks = []
with tempfile.TemporaryDirectory(prefix="nix-sound-audio-") as temp:
    root = Path(temp)
    runtime = root / "run"
    runtime.mkdir(mode=0o700)
    env = os.environ | {"XDG_RUNTIME_DIR": str(runtime), "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_STATE_HOME": str(root / "state"), "XDG_DATA_HOME": str(root / "data"),
        "PULSE_SERVER": "unix:" + str(runtime / "pulse.sock"), "PULSE_COOKIE": str(root / "cookie")}
    log = open(root / "pulse.log", "w")
    def start_audio():
        command = [shutil.which("pulseaudio"), "-n", "--daemonize=no", "--use-pid-file=no", "--exit-idle-time=-1",
            "--load=module-native-protocol-unix socket=" + str(runtime / "pulse.sock") + " auth-anonymous=1",
            "--load=module-null-sink sink_name=speakers", "--load=module-null-sink sink_name=headphones",
            "--load=module-null-source source_name=microphone", "--load=module-null-source source_name=headset_mic"]
        if args.module_dir:
            command += ["--dl-search-path=" + args.module_dir]
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
        children.append(process)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            connection = subprocess.run(["pactl", "info"], env=env, capture_output=True, text=True)
            if connection.returncode == 0:
                return process
            if process.poll() is not None:
                raise AssertionError((root / "pulse.log").read_text())
            time.sleep(0.05)
        raise AssertionError("Audio server not ready: " + connection.stderr + "\n" + (root / "pulse.log").read_text())
    def cli(*command):
        result = subprocess.run([binary, *command], env=env, capture_output=True, text=True, timeout=8)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    events = queue.Queue()
    def read_events(process):
        for line in process.stdout:
            events.put(json.loads(line))
    def wait_for(predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                event = events.get(timeout=0.2)
            except queue.Empty:
                continue
            if predicate(event):
                return event
        raise AssertionError("Timed out waiting for audio state")
    def request(**value):
        return cli("request", json.dumps(value))
    try:
        audio = start_audio()
        started = time.monotonic()
        watch = subprocess.Popen([binary, "watch"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        children.append(watch)
        threading.Thread(target=read_events, args=(watch,), daemon=True).start()
        first = wait_for(lambda e: e.get("ok") and len(e["snapshot"]["outputs"]) == 2)
        startup = (time.monotonic() - started) * 1000
        state = first["snapshot"]
        assert len(state["inputs"]) == 2, state
        checks.append("real server graph and monitor-source exclusion")
        speakers = next(n for n in state["outputs"] if n["name"] == "speakers")
        headphones = next(n for n in state["outputs"] if n["name"] == "headphones")
        request(action="volume", kind="sink", id=speakers["id"], volume=0.32)
        wait_for(lambda e: e.get("ok") and any(n["id"] == speakers["id"] and abs(n["volume"] - .32) < .001 for n in e["snapshot"]["outputs"]))
        request(action="mute", kind="sink", id=speakers["id"], muted=True)
        wait_for(lambda e: e.get("ok") and any(n["id"] == speakers["id"] and n["muted"] for n in e["snapshot"]["outputs"]))
        request(action="default", kind="sink", id=headphones["id"])
        wait_for(lambda e: e.get("ok") and any(n["id"] == headphones["id"] and n["is_default"] for n in e["snapshot"]["outputs"]))
        checks.append("master volume, mute and default output")
        player = subprocess.Popen(["pacat", "--playback", "--device=speakers", "--raw", "/dev/zero"], env=env, stdout=subprocess.DEVNULL, stderr=log)
        recorder = subprocess.Popen(["parec", "--record", "--device=microphone", "--raw"], env=env, stdout=subprocess.DEVNULL, stderr=log)
        children += [player, recorder]
        state = wait_for(lambda e: e.get("ok") and e["snapshot"]["playback"] and e["snapshot"]["recording"])["snapshot"]
        playback = state["playback"][0]
        request(action="route", kind="sink-input", id=playback["id"], device=headphones["id"])
        wait_for(lambda e: e.get("ok") and any(n["id"] == playback["id"] and n["device"] == headphones["id"] for n in e["snapshot"]["playback"]))
        recording = state["recording"][0]
        target = next(n for n in state["inputs"] if n["name"] == "headset_mic")
        request(action="route", kind="source-output", id=recording["id"], device=target["id"])
        wait_for(lambda e: e.get("ok") and any(n["id"] == recording["id"] and n["device"] == target["id"] for n in e["snapshot"]["recording"]))
        request(action="volume", kind="source-output", id=recording["id"], volume=.54)
        wait_for(lambda e: e.get("ok") and any(n["id"] == recording["id"] and abs(n["volume"]-.54)<.001 for n in e["snapshot"]["recording"]))
        checks.append("real playback and recording streams, routing in both directions, recording volume")
        audio.terminate(); audio.wait(timeout=5)
        wait_for(lambda e: not e.get("ok"))
        audio = start_audio()
        wait_for(lambda e: e.get("ok") and len(e["snapshot"]["outputs"]) == 2)
        checks.append("server disconnect and automatic reconnect")
        watch.terminate(); assert watch.wait(timeout=5) == 0
        assert not (runtime / "nix-sound/audio.sock").exists()
        checks.append("clean signal shutdown and socket removal")
        result = {"ok": True, "checks": checks, "first_snapshot_ms": round(startup, 2), "server": "isolated PulseAudio 17 null devices"}
        if args.result:
            Path(args.result).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
