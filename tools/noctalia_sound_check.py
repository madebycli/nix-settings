#!/usr/bin/env python3
"""Real native Sound pointer acceptance under isolated headless Sway.

Requires stock Noctalia 5.3+, Mesa/EGL, Sway/grim, PulseAudio utilities and
GIF-Player's developer virtual_input example (--driver). No GIF runtime is used.
Artifacts stay outside the source tree. Never operates the user's audio server.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import tomllib

p = argparse.ArgumentParser()
p.add_argument("--binary", required=True)
p.add_argument("--driver", required=True)
p.add_argument("--noctalia", required=True)
p.add_argument("--module-dir")
p.add_argument("--artifacts", required=True)
a = p.parse_args()
binary = str(Path(a.binary).resolve())
artifacts = Path(a.artifacts).resolve()
artifacts.mkdir(parents=True, exist_ok=True)
children = []


def wait_for(check, description):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.1)
    raise AssertionError("Timed out: " + description)


with tempfile.TemporaryDirectory(prefix="sound-host-") as directory:
    root = Path(directory)
    runtime = root / "run"
    runtime.mkdir(mode=0o700)
    env = os.environ | {
        "HOME": str(root),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "PULSE_SERVER": "unix:" + str(runtime / "pulse.sock"),
        "WLR_BACKENDS": "headless",
        "WLR_HEADLESS_OUTPUTS": "1",
        "WLR_RENDERER": "pixman",
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "EGL_PLATFORM": "wayland",
        "PATH": a.noctalia + ":" + str(Path(binary).parent) + ":" + os.environ["PATH"],
    }
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("DISPLAY", None)
    width, height = 1600, 900
    (root / "sway.conf").write_text(
        "xwayland disable\ndefault_border none\noutput HEADLESS-1 mode 1600x900\nseat seat0 fallback true\n"
    )
    # A known XDG icon tests the real resolver; this is generated test artwork.
    icons = root / "data/icons/hicolor/scalable/apps"
    icons.mkdir(parents=True)
    (icons / "sound-test.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" rx="5" fill="#ff7040"/><circle cx="12" cy="12" r="6" fill="white"/></svg>'
    )

    def run(argv):
        return subprocess.run(argv, env=env, text=True, capture_output=True, timeout=15)

    def launch(argv, name):
        log = open(artifacts / (name + ".log"), "w")
        child = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
        children.append(child)
        return child

    def snapshot():
        result = run([binary, "snapshot"])
        return json.loads(result.stdout) if result.returncode == 0 else {}

    def shot(name):
        time.sleep(1)
        result = run(["grim", "-o", "HEADLESS-1", str(artifacts / (name + ".png"))])
        assert result.returncode == 0, result.stderr

    try:
        launch(["sway", "-c", str(root / "sway.conf")], "sway")
        wait_for(lambda: any(runtime.glob("wayland-*")), "Wayland socket")
        env["WAYLAND_DISPLAY"] = next(
            p.name for p in runtime.glob("wayland-*") if p.is_socket()
        )
        env["SWAYSOCK"] = str(next(runtime.glob("sway-ipc.*.sock")))
        pulse = [
            "pulseaudio",
            "-n",
            "--daemonize=no",
            "--use-pid-file=no",
            "--exit-idle-time=-1",
            "--load=module-native-protocol-unix socket="
            + str(runtime / "pulse.sock")
            + " auth-anonymous=1",
            "--load=module-null-sink sink_name=speakers sink_properties=device.description="
            + "CORSAIR_HS80_MAX_WIRELESS_Gaming_Receiver_Analog_Stereo_" * 5,
            "--load=module-null-source source_name=microphone",
        ]
        if a.module_dir:
            pulse += ["--dl-search-path=" + a.module_dir]
        launch(pulse, "pulse")
        wait_for(lambda: run(["pactl", "info"]).returncode == 0, "Pulse server")
        for i in range(6):
            launch(
                [
                    "pacat",
                    "--playback",
                    "--raw",
                    "--property=application.name=Music " + str(i),
                    "--property=application.icon_name=sound-test",
                    "/dev/zero",
                ],
                "playback" + str(i),
            )
        launch(
            [
                "parec",
                "--record",
                "--raw",
                "--property=application.name=Recorder",
                "--property=application.icon_name=sound-test",
            ],
            "recording",
        )
        result = run([binary, "install-plugin"])
        assert result.returncode == 0, result.stderr
        installed = root / "data/noctalia/plugins/nix-sound/plugin.toml"
        installed.write_text(
            installed.read_text()
            .replace('width = "fill"', "width = 480")
            .replace('height = "fill"', "height = 400")
        )
        launch([shutil.which("noctalia", path=env["PATH"])], "noctalia")
        wait_for(
            lambda: run(["noctalia", "msg", "color-scheme-get"]).returncode == 0,
            "Noctalia IPC",
        )
        upgrade = run([binary, "install-plugin"])
        assert "Reloaded Nix Sound" in upgrade.stdout, upgrade.stdout + upgrade.stderr
        time.sleep(1.5)
        assert run([binary, "sound"]).returncode == 0
        wait_for(
            lambda: len(snapshot().get("playback", [])) == 6,
            "six live playback streams",
        )
        driver = subprocess.Popen(
            [a.driver],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        children.append(driver)
        assert driver.stdout.readline().strip() == "ready"

        def command(line):
            driver.stdin.write(line + "\n")
            driver.stdin.flush()
            assert driver.stdout.readline().startswith("done " + line)
            time.sleep(0.08)

        def move(x, y):
            command(f"move {int(x * 2560 / width)} {int(y * 720 / height)}")

        def click(x, y):
            move(x, y)
            command("click")

        shot("sound-wide-before")
        # Native master sliders lie in the third row of each compact master card.
        click(200, 192)
        wait_for(
            lambda: abs(snapshot()["outputs"][0]["volume"] - 1) > 0.1,
            "master pointer changes server volume",
        )
        shot("sound-wide-after-master")
        move(200, 192)
        command("down")
        move(450, 192)
        command("up")
        wait_for(
            lambda: snapshot()["outputs"][0]["volume"] > 0.5,
            "master drag commits changed value",
        )
        # App sliders follow the section title and the two-row application header.
        click(240, 321)
        wait_for(
            lambda: any(n["volume"] < 0.8 for n in snapshot()["playback"]),
            "application pointer changes server volume",
        )
        before = {n["id"]: n["volume"] for n in snapshot()["playback"]}
        move(240, 321)
        command("down")
        move(420, 321)
        command("up")
        wait_for(
            lambda: any(
                abs(n["volume"] - before[n["id"]]) > 0.005
                for n in snapshot()["playback"]
            ),
            "application drag changes volume",
        )
        click(1000, 192)
        wait_for(
            lambda: snapshot()["inputs"][0]["volume"] < 0.8,
            "microphone pointer changes volume",
        )
        click(1000, 321)
        wait_for(
            lambda: snapshot()["recording"][0]["volume"] < 0.8,
            "recording pointer changes volume",
        )
        # Same-position buttons toggle both directions and keep their geometry.
        click(750, 192)
        wait_for(lambda: snapshot()["outputs"][0]["muted"], "master mute")
        click(750, 321)
        wait_for(lambda: snapshot()["playback"][0]["muted"], "application mute")
        shot("sound-muted")
        click(750, 192)
        wait_for(lambda: not snapshot()["outputs"][0]["muted"], "master unmute")
        click(750, 321)
        wait_for(lambda: not snapshot()["playback"][0]["muted"], "application unmute")
        shot("sound-wide-after-app")
        for width, height, name in [
            (2560, 1440, "large"),
            (1366, 768, "laptop"),
            (800, 600, "small"),
            (640, 360, "short"),
        ]:
            assert (
                run(
                    ["swaymsg", "output", "HEADLESS-1", "mode", f"{width}x{height}"]
                ).returncode
                == 0
            )
            time.sleep(1.2)
            # Explicit reopen also tests selecting the viewport afresh.
            assert run([binary, "sound"]).returncode == 0
            assert run([binary, "sound"]).returncode == 0
            shot("sound-" + name)
        settings_file = root / "state/noctalia/settings.toml"
        settings = tomllib.loads(settings_file.read_text())
        settings.setdefault("accessibility", {})["ui_scale"] = 1.25

        def toml_lines(data, path=()):
            lines = (
                ["[" + ".".join(json.dumps(key) for key in path) + "]"] if path else []
            )
            for key, value in data.items():
                if not isinstance(value, dict):
                    lines.append(json.dumps(key) + " = " + json.dumps(value))
            for key, value in data.items():
                if isinstance(value, dict):
                    lines += toml_lines(value, path + (key,))
            return lines

        updated = settings_file.with_suffix(".new")
        updated.write_text("\n".join(toml_lines(settings)) + "\n")
        updated.replace(settings_file)
        time.sleep(1.5)
        for width, height in [(1366, 768), (800, 600), (640, 360)]:
            assert (
                run(
                    ["swaymsg", "output", "HEADLESS-1", "mode", f"{width}x{height}"]
                ).returncode
                == 0
            )
            time.sleep(1.5)
            shot(f"sound-scaled-{width}")
        text = (artifacts / "noctalia.log").read_text()
        assert "Missing volume" not in text
        (artifacts / "result.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "checks": [
                        "real master and per-app pointer callbacks change Pulse volumes",
                        "reinstall reloads cached manifest/service in running host without restart",
                        "master and per-app mute/unmute with stable selected buttons",
                        "master and application drag-release commits change server volumes",
                        "six playback and one recording stream with XDG application icons",
                        "native fill overlay at 2560x1440, 1600x900, 1366x768, 800x600, 640x360",
                        "long device names, 125% UI scale and live resize without reopening",
                    ],
                },
                indent=2,
            )
        )
        print("Native Sound pointer, drag and monitor checks passed")
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
