use anyhow::{Context, Result, ensure};
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    time::{SystemTime, UNIX_EPOCH},
};
use toml_edit::{DocumentMut, value};

const FILES: &[(&str, &str)] = &[
    (
        "plugin.toml",
        include_str!("../plugins/nix-sound/plugin.toml"),
    ),
    (
        "service.luau",
        include_str!("../plugins/nix-sound/service.luau"),
    ),
    (
        "sound.luau",
        include_str!("../plugins/nix-sound/sound.luau"),
    ),
    ("host.luau", include_str!("../plugins/nix-sound/host.luau")),
    (
        "translations/en.json",
        include_str!("../plugins/nix-sound/translations/en.json"),
    ),
    (
        "translations/de.json",
        include_str!("../plugins/nix-sound/translations/de.json"),
    ),
];
pub fn xdg(variable: &str, fallback: &str) -> Result<PathBuf> {
    Ok(std::env::var_os(variable)
        .map(PathBuf::from)
        .unwrap_or(PathBuf::from(std::env::var_os("HOME").context("HOME missing")?).join(fallback)))
}
fn stamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos()
}
fn store_output(executable: &Path) -> Option<&Path> {
    executable
        .ancestors()
        .find(|path| path.parent() == Some(Path::new("/nix/store")))
}
fn managed_executable(path: &str) -> bool {
    let path = Path::new(path);
    store_output(path).is_some()
        && matches!(
            path.file_name().and_then(|name| name.to_str()),
            Some("nix-settings" | ".nix-settings-wrapped")
        )
}
fn retain_engine(executable: &Path) -> Result<()> {
    let Some(output) = store_output(executable) else {
        return Ok(());
    };
    let root = xdg("XDG_STATE_HOME", ".local/state")?.join("nix-sound/engine");
    fs::create_dir_all(root.parent().unwrap())?;
    let result = Command::new("nix-store")
        .arg("--add-root")
        .arg(&root)
        .arg("--indirect")
        .arg("--realise")
        .arg(output)
        .output()
        .context("Cannot retain the installed Nix Sound engine; nix-store is required")?;
    ensure!(
        result.status.success(),
        "Cannot protect the installed Nix Sound engine from garbage collection: {}",
        String::from_utf8_lossy(&result.stderr).trim()
    );
    Ok(())
}
struct Staging(PathBuf);
impl Drop for Staging {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
pub fn install() -> Result<()> {
    let parent = xdg("XDG_DATA_HOME", ".local/share")?.join("noctalia/plugins");
    fs::create_dir_all(&parent)?;
    let destination = parent.join("nix-sound");
    // Keep incomplete payloads outside the host's scanned plugin directory.
    let staging = parent
        .parent()
        .unwrap()
        .join(format!(".nix-sound-install-{}", stamp()));
    fs::create_dir(&staging)?;
    let _staging = Staging(staging.clone());
    for (name, content) in FILES {
        let path = staging.join(name);
        fs::create_dir_all(path.parent().unwrap())?;
        fs::write(&path, content)?;
    }
    // Resolve the engine independently of the shell's PATH (e.g. after a Nix profile update).
    let executable = std::env::current_exe()?;
    // Nix makeWrapper launches a hidden binary; retain the wrapper that supplies pactl's PATH.
    let executable = executable
        .file_name()
        .and_then(|name| name.to_str())
        .and_then(|name| name.strip_prefix('.'))
        .and_then(|name| name.strip_suffix("-wrapped"))
        .map(|name| executable.with_file_name(name))
        .filter(|path| path.is_file())
        .unwrap_or(executable);
    let mut manifest: DocumentMut = fs::read_to_string(staging.join("plugin.toml"))?.parse()?;
    manifest["setting"][0]["default"] = value(executable.to_string_lossy().as_ref());
    fs::write(staging.join("plugin.toml"), manifest.to_string())?;
    let directory = xdg("XDG_STATE_HOME", ".local/state")?.join("noctalia");
    fs::create_dir_all(&directory)?;
    let path = directory.join("settings.toml");
    let original = match fs::read_to_string(&path) {
        Ok(v) => v,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(e) => return Err(e.into()),
    };
    let mut state: DocumentMut = original
        .parse()
        .context("Invalid Noctalia settings; left unchanged")?;
    let merged = Command::new("noctalia")
        .args(["config", "export", "full"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .and_then(|s| s.parse::<DocumentMut>().ok());
    let base = match merged {
        Some(v) => v,
        None => {
            let config = xdg("XDG_CONFIG_HOME", ".config")?.join("noctalia/config.toml");
            let mut base: DocumentMut = if config.exists() {
                fs::read_to_string(config)?
                    .parse()
                    .context("Invalid Noctalia config; left unchanged")?
            } else {
                DocumentMut::new()
            };
            if let Some(plugins) = state.get("plugins") {
                base["plugins"] = plugins.clone();
            }
            base
        }
    };
    let mut enabled = base
        .get("plugins")
        .and_then(|p| p.get("enabled"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if !enabled
        .iter()
        .any(|v| v.as_str() == Some("madebycli/nix-sound"))
    {
        enabled.push("madebycli/nix-sound");
    }
    state["plugins"]["enabled"] = value(enabled);
    // A previous host settings save can preserve an old generated store path even
    // after the manifest default is updated. Repair only our managed engine paths.
    let configured = [&state, &base].into_iter().find_map(|doc| {
        doc.get("plugin_settings")
            .and_then(|p| p.get("madebycli/nix-sound"))
            .and_then(|p| p.get("executable"))
            .and_then(|v| v.as_str())
    });
    if configured.is_some_and(managed_executable) {
        state["plugin_settings"]["madebycli/nix-sound"]["executable"] =
            value(executable.to_string_lossy().as_ref());
    }
    let updated = state.to_string();
    // `nix run` outputs are otherwise collectible after this command exits.
    retain_engine(&executable)?;
    if destination.exists() {
        // Keep backups outside the scanned plugins directory to avoid duplicate plugin IDs.
        let backups = parent.parent().unwrap().join("plugin-backups");
        fs::create_dir_all(&backups)?;
        fs::rename(&destination, backups.join(format!("nix-sound-{}", stamp())))?;
    }
    fs::rename(staging, &destination)?;
    if updated != original {
        if path.exists() {
            fs::copy(
                &path,
                directory.join(format!("settings.toml.nix-sound-backup-{}", stamp())),
            )?;
        }
        let temp = directory.join(format!(".nix-sound-{}.toml", stamp()));
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;
        let mut file = fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .mode(0o600)
            .open(&temp)?;
        file.write_all(updated.as_bytes())?;
        file.sync_all()?;
        fs::rename(temp, path)?;
    }
    println!("Installed and enabled Nix Sound: {}", destination.display());
    // The host caches manifest dimensions and service scripts across unchanged config
    // reloads. Re-enable this plugin through its supported IPC so upgrades take effect.
    let disabled = Command::new("noctalia")
        .args(["msg", "plugins", "disable", "madebycli/nix-sound"])
        .output();
    if disabled
        .ok()
        .is_some_and(|output| output.status.success() && output.stdout.starts_with(b"ok"))
    {
        let enabled = Command::new("noctalia")
            .args(["msg", "plugins", "enable", "madebycli/nix-sound"])
            .output()
            .context("Installed Sound, but could not re-enable it in the running host")?;
        ensure!(
            enabled.status.success() && enabled.stdout.starts_with(b"ok"),
            "Installed Sound, but Noctalia could not re-enable it: {}",
            String::from_utf8_lossy(&enabled.stdout)
        );
        println!("Reloaded Nix Sound in the running Noctalia instance.");
    }
    Ok(())
}
pub fn open() -> Result<()> {
    let status = Command::new("noctalia")
        .args(["msg", "panel-toggle", "madebycli/nix-sound:sound"])
        .status()
        .context("Noctalia 5 is required; start it in your desktop session")?;
    ensure!(
        status.success(),
        "Cannot open Sound. Run `nix-settings install-plugin` and enable Nix Sound in Noctalia."
    );
    Ok(())
}

/// Describe the installed payload as well as the currently invoked package.
pub fn diagnose() -> Result<()> {
    let manifest =
        xdg("XDG_DATA_HOME", ".local/share")?.join("noctalia/plugins/nix-sound/plugin.toml");
    if !manifest.exists() {
        println!("Plugin: not installed (run install-plugin)");
        return Ok(());
    }
    let doc: DocumentMut = fs::read_to_string(&manifest)?.parse()?;
    let executable = doc
        .get("setting")
        .and_then(|v| v.as_array_of_tables())
        .and_then(|v| v.get(0))
        .and_then(|v| v.get("default"))
        .and_then(|v| v.as_str())
        .unwrap_or("nix-settings");
    println!("Installed engine: {executable}");
    if executable.starts_with('/') && !Path::new(executable).is_file() {
        println!("Installed engine is missing; run install-plugin again.");
    }
    let root = xdg("XDG_STATE_HOME", ".local/state")?.join("nix-sound/engine");
    if let Ok(target) = fs::read_link(root) {
        println!("Retained Nix engine: {}", target.display());
    }
    Ok(())
}
