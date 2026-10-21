#!/usr/bin/env python3
"""Check real installer writes in isolated XDG directories, including repeat installs."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib

p=argparse.ArgumentParser()
p.add_argument("--binary", default="target/debug/nix-settings")
args=p.parse_args()
binary=str(Path(args.binary).resolve())
with tempfile.TemporaryDirectory(prefix="nix-sound-install-") as temp:
    root=Path(temp)
    (root/"run").mkdir(mode=0o700)
    env=os.environ | {"XDG_RUNTIME_DIR":str(root/"run"),"XDG_CONFIG_HOME":str(root/"config"),"XDG_STATE_HOME":str(root/"state"),"XDG_DATA_HOME":str(root/"data")}
    config=root/"config/noctalia/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[plugins]\nenabled=["other/example"]\n[bar.main]\nend=["music"]\n')
    settings=root/"state/noctalia/settings.toml"
    settings.parent.mkdir(parents=True)
    original='[shell]\ncorner_radius_scale=1.5\n[widget.music]\ntype="media"\n'
    settings.write_text(original)
    def run(*args,ok=True):
        result=subprocess.run([binary,*args],env=env,capture_output=True,text=True)
        assert (result.returncode==0)==ok,result.stderr
        return result
    run("install-plugin","--help")
    assert settings.read_text()==original
    assert not (root/"data").exists()
    run("install-plugin")
    data=tomllib.loads(settings.read_text())
    assert data["plugins"]["enabled"]==["other/example","madebycli/nix-sound"]
    assert data["shell"]["corner_radius_scale"]==1.5
    assert data["widget"]["music"]["type"]=="media"
    assert "bar" not in data
    backups=list(settings.parent.glob("settings.toml.nix-sound-backup-*"))
    assert len(backups)==1 and backups[0].read_text()==original
    installed=root/"data/noctalia/plugins/nix-sound"
    manifest=tomllib.loads((installed/"plugin.toml").read_text())
    assert manifest["setting"][0]["default"]==binary
    before=settings.read_bytes()
    run("install-plugin")
    assert settings.read_bytes()==before
    assert len(list(settings.parent.glob("settings.toml.nix-sound-backup-*")))==1
    assert len(list((root/"data/noctalia/plugins").iterdir()))==1
    assert len(list((root/"data/noctalia/plugin-backups").iterdir()))==1
    settings.write_text("invalid = [")
    run("install-plugin",ok=False)
    assert settings.read_text()=="invalid = ["
    print("Installer preservation, backups, repeat install, no bar widget, help and malformed-settings checks passed")
