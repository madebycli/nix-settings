#!/usr/bin/env python3
"""Verify that installing from a real Nix output registers a persistent engine root."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib

p = argparse.ArgumentParser()
p.add_argument("--binary", required=True)
p.add_argument("--nix-store", default="nix-store")
a = p.parse_args()
binary = Path(a.binary).resolve()
assert str(binary).startswith("/nix/store/"), "Pass the packaged public Nix wrapper"
output = next(path for path in binary.parents if path.parent == Path("/nix/store"))
with tempfile.TemporaryDirectory(prefix="sound-retained-") as directory:
    root = Path(directory)
    (root / "run").mkdir(mode=0o700)
    env = os.environ | {
        "XDG_RUNTIME_DIR": str(root / "run"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CONFIG_HOME": str(root / "config"),
    }
    for _ in range(2):
        result = subprocess.run(
            [str(binary), "install-plugin"],
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        gcroot = root / "state/nix-sound/engine"
        assert gcroot.is_symlink() and gcroot.resolve() == output, (gcroot, output)
        manifest = tomllib.loads(
            (root / "data/noctalia/plugins/nix-sound/plugin.toml").read_text()
        )
        assert manifest["setting"][0]["default"] == str(binary), (
            "Keep the public wrapper and its pactl PATH"
        )
        registered = subprocess.run(
            [a.nix_store, "--query", "--roots", str(output)],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        assert registered.returncode == 0, registered.stderr
        assert str(gcroot) in registered.stdout, (
            "The symlink must be a registered GC root, not merely a link"
        )
    print("Packaged engine GC root, wrapper path and repeat-install retention passed")
