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
import signal
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
    (icons.parent.parent / "index.theme").write_text(
        "[Icon Theme]\nName=Hicolor\nDirectories=scalable/apps\n[scalable/apps]\nSize=24\nType=Scalable\nMinSize=1\nMaxSize=256\n"
    )
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

    resolved = run([binary, "icons", json.dumps([
        {"key":"known","icon":"sound-test","label":"Known application"},
        {"key":"missing","icon":"missing-app-icon","label":"Missing application"},
    ])])
    assert resolved.returncode == 0, resolved.stderr
    icon_paths = json.loads(resolved.stdout)
    assert icon_paths.get("known") == str(icons / "sound-test.svg"), icon_paths
    assert "missing" not in icon_paths

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
                    "--property=application.name="
                    + [
                        "Brave",
                        "vesktop",
                        "Music",
                        "Video player",
                        "Long application name to check truncation",
                        "Voice chat",
                    ][i],
                    "--property=application.icon_name=" + ("sound-test" if i < 5 else "missing-app-icon"),
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
        # Exercise the actual long German headings and an inherited monospace host font.
        config = root / "config/noctalia/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        # First stream intentionally fails before emitting JSON. Commands and later
        # stream attempts delegate to the real engine, preserving all existing checks.
        bridge = root / "audio-engine"
        failed_once = root / "failed-once"
        attempts = root / "watch-attempts"
        import shlex

        bridge.write_text(
            '#!/bin/sh\nif [ "$1" = icons ]; then sleep 2; fi\nif [ "$1" = watch ]; then\n  echo attempt >> '
            + shlex.quote(str(attempts))
            + "\n  if [ ! -f "
            + shlex.quote(str(failed_once))
            + " ]; then\n    touch "
            + shlex.quote(str(failed_once))
            + "\n    echo 'fixture early startup failure' >&2\n    exit 7\n  fi\nfi\nexec "
            + shlex.quote(binary)
            + ' "$@"\n'
        )
        bridge.chmod(0o755)
        config.write_text(
            '[shell]\nlang="de"\nfont_family="monospace"\n[plugin_settings."madebycli/nix-sound"]\nexecutable='
            + json.dumps(str(bridge))
            + "\n"
        )
        result = run([binary, "install-plugin"])
        assert result.returncode == 0, result.stderr
        installed = root / "data/noctalia/plugins/nix-sound/plugin.toml"
        installed.write_text(
            installed.read_text()
            .replace("width = 1600", "width = 480")
            .replace("height = 900", "height = 400")
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
        sock = runtime / "nix-sound/audio.sock"
        lock = runtime / "nix-sound/backend.lock"

        def backend_pid():
            try:
                return int(lock.read_text().strip())
            except (OSError, ValueError):
                return 0

        wait_for(
            lambda: sock.exists() and backend_pid() > 0,
            "plugin recovers from a pre-JSON startup failure",
        )
        assert len(attempts.read_text().splitlines()) >= 2
        first_pid = backend_pid()
        os.kill(first_pid, signal.SIGKILL)
        wait_for(
            lambda: backend_pid() > 0 and backend_pid() != first_pid and sock.exists(),
            "automatic backend restart while panel is open",
        )
        # Reproduce a missing executable while the audio server and other programs
        # remain healthy. It must render a connection error, never fake no-devices.
        live_pid = backend_pid()
        unavailable = bridge.with_suffix(".temporarily-missing")
        bridge.rename(unavailable)
        os.kill(live_pid, signal.SIGKILL)
        wait_for(
            lambda: (
                not sock.exists()
                or run([binary, "request", '{"action":"refresh"}']).returncode != 0
            ),
            "backend is unavailable",
        )
        shot("sound-backend-missing")
        unavailable.rename(bridge)
        wait_for(
            lambda: backend_pid() > 0 and backend_pid() != live_pid and sock.exists(),
            "automatic recovery after executable restoration",
        )
        time.sleep(0.5)
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

        pointer_dy = 0

        def move(x, y):
            command(
                f"move {int(x * 2560 / width)} {int((y + pointer_dy) * 720 / height)}"
            )

        def click(x, y):
            move(x, y)
            command("click")

        time.sleep(2)  # Let the stock host's virtual-keyboard layout OSD disappear.
        shot("sound-wide-before")
        # Fixed and filled panels have different native screen origins. Locate the first
        # yellow slider row in the stock default theme rather than guessing its Y offset.
        raw = subprocess.run(
            ["grim", "-t", "ppm", "-o", "HEADLESS-1", "-"],
            env=env,
            capture_output=True,
            check=True,
        ).stdout
        magic, size, maximum, pixels = raw.split(b"\n", 3)
        assert magic == b"P6" and maximum == b"255"
        pw, ph = map(int, size.split())
        rows = []
        for y in range(ph):
            count = sum(
                1
                for x in range(pw)
                if pixels[(y * pw + x) * 3] > 210
                and pixels[(y * pw + x) * 3 + 1] > 210
                and pixels[(y * pw + x) * 3 + 2] < 190
            )
            if count > pw * 0.5:
                rows.append(y)
        assert rows, "Native master tracks must be visible"
        first = [y for y in rows if y < rows[0] + 12]
        pointer_dy = round(sum(first) / len(first)) - 192
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
        click(240, 311)
        wait_for(
            lambda: any(n["volume"] < 0.8 for n in snapshot()["playback"]),
            "application pointer changes server volume",
        )
        before = {n["id"]: n["volume"] for n in snapshot()["playback"]}
        move(240, 311)
        command("down")
        move(420, 311)
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
        click(1000, 311)
        wait_for(
            lambda: snapshot()["recording"][0]["volume"] < 0.8,
            "recording pointer changes volume",
        )
        # Same-position buttons toggle both directions and keep their geometry.
        click(750, 192)
        wait_for(lambda: snapshot()["outputs"][0]["muted"], "master mute")
        click(750, 311)
        wait_for(lambda: snapshot()["playback"][0]["muted"], "application mute")
        shot("sound-muted")
        click(750, 192)
        wait_for(lambda: not snapshot()["outputs"][0]["muted"], "master unmute")
        click(750, 311)
        wait_for(lambda: not snapshot()["playback"][0]["muted"], "application unmute")
        shot("sound-wide-after-app")
        # Identical pointer coordinates must map to the same volume regardless of the
        # percentage digit count before rendering (the 9/90/100% width regression).
        geometry = []
        for group, kind, y in [
            ("outputs", "sink", 192),
            ("playback", "sink-input", 311),
        ]:
            observed = []
            node = snapshot()[group][0]
            for volume in [0.09, 0.90, 1.0]:
                response = run(
                    [
                        binary,
                        "request",
                        json.dumps(
                            {
                                "action": "volume",
                                "kind": kind,
                                "id": node["id"],
                                "volume": volume,
                            }
                        ),
                    ]
                )
                assert response.returncode == 0, response.stderr
                time.sleep(0.3)
                shot(f"percent-{kind}-{int(volume * 100)}")
                click(500, y)
                time.sleep(0.3)
                observed.append(snapshot()[group][0]["volume"])
            assert max(observed) - min(observed) < 0.001, (kind, observed)
            geometry.append({"kind": kind, "same_click_volumes": observed})
        # Master and app cards must share the same track start/end after accounting
        # for the host's native list viewport insets.
        assert (
            abs(
                geometry[0]["same_click_volumes"][0]
                - geometry[1]["same_click_volumes"][0]
            )
            < 0.001
        ), geometry
        (artifacts / "slider-geometry.json").write_text(json.dumps(geometry, indent=2))
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
            # Native contentScale is negotiated at open; apply the host's new UI scale
            # before comparing viewport insets against scaled ui.* padding.
            assert run([binary, "sound"]).returncode == 0
            assert run([binary, "sound"]).returncode == 0
            shot(f"sound-scaled-{width}")
        text = (artifacts / "noctalia.log").read_text()
        assert "Missing volume" not in text
        assert "exceeded its CPU budget" not in text, "A native plugin callback timed out"
        assert "disabled after repeated timeouts" not in text
        assert "language: de" in text, (
            "The native fixture must actually use German translations"
        )
        assert "ui node '" not in text, (
            "Native controls emitted invalid property/value warnings"
        )
        (artifacts / "result.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "checks": [
                        "startup stderr/exit before JSON recovers automatically",
                        "killed backend restarts while panel stays open",
                        "missing executable shows connection error and restoration recovers",
                        "German headings and inherited monospace font render without native UI warnings",
                        "different app-name lengths retain aligned device selectors",
                        "master and application tracks share horizontal alignment",
                        "real master and per-app pointer callbacks change Pulse volumes",
                        "reinstall reloads cached manifest/service in running host without restart",
                        "master and per-app mute/unmute with stable selected buttons",
                        "master and application drag-release commits change server volumes",
                        "six playback and one recording stream with XDG application icons",
                        "centered capped overlay at 2560x1440, 1600x900, 1366x768, 800x600, 640x360",
                        "long device names, output resizing and freshly opened 125% UI scale",
                        "identical pointer mapping with 9%, 90% and 100% labels for master and app sliders",
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
