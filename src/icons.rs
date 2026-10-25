//! Icon filesystem work runs in a separate, bounded host subprocess, never in a
//! Noctalia render callback or on the audio event loop.
use anyhow::{Result, ensure};
use serde::Deserialize;
use std::{collections::BTreeMap, env, fs, path::PathBuf, process::Command};

#[derive(Deserialize)]
struct Request {
    key: String,
    icon: String,
    label: String,
}

fn data_dirs() -> Vec<PathBuf> {
    let home = env::var_os("HOME").map(PathBuf::from).unwrap_or_default();
    let mut dirs = vec![
        env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local/share")),
    ];
    dirs.extend(env::split_paths(
        &env::var_os("XDG_DATA_DIRS").unwrap_or_else(|| "/usr/local/share:/usr/share".into()),
    ));
    dirs
}

fn desktop_icons() -> BTreeMap<String, String> {
    let mut icons = BTreeMap::new();
    for dir in data_dirs() {
        let Ok(entries) = fs::read_dir(dir.join("applications")) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().is_none_or(|e| e != "desktop") {
                continue;
            }
            let Ok(text) = fs::read_to_string(&path) else {
                continue;
            };
            let mut fields = BTreeMap::new();
            let mut desktop = false;
            for line in text.lines().map(str::trim) {
                if line.starts_with('[') {
                    desktop = line == "[Desktop Entry]";
                    continue;
                }
                if let Some((key, value)) = line.split_once('=').filter(|_| desktop) {
                    fields.insert(key.trim(), value.trim());
                }
            }
            let Some(icon) = fields.get("Icon").filter(|v| !v.is_empty()) else {
                continue;
            };
            let id = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
            for name in [
                id,
                fields.get("Name").copied().unwrap_or(""),
                fields.get("StartupWMClass").copied().unwrap_or(""),
            ] {
                if !name.is_empty() {
                    icons
                        .entry(name.to_lowercase())
                        .or_insert_with(|| (*icon).to_owned());
                }
            }
        }
    }
    icons
}

fn themes() -> Vec<String> {
    let mut themes = Vec::new();
    if let Some(output) = Command::new("gsettings")
        .args(["get", "org.gnome.desktop.interface", "icon-theme"])
        .output()
        .ok()
        .filter(|output| output.status.success())
    {
        themes.push(
            String::from_utf8_lossy(&output.stdout)
                .trim()
                .trim_matches('\'')
                .to_owned(),
        );
    }
    let config = env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env::var_os("HOME").unwrap_or_default()).join(".config"));
    for gtk in ["gtk-3.0", "gtk-4.0"] {
        if let Ok(text) = fs::read_to_string(config.join(gtk).join("settings.ini")) {
            for line in text.lines() {
                if let Some((_, value)) = line
                    .split_once('=')
                    .filter(|(key, _)| key.trim() == "gtk-icon-theme-name")
                {
                    themes.push(value.trim().trim_matches('"').to_owned());
                }
            }
        }
    }
    themes.push("hicolor".into());
    themes
}

pub fn resolve(json: &str) -> Result<BTreeMap<String, String>> {
    ensure!(json.len() <= 128 * 1024, "Icon request too large");
    let requests: Vec<Request> = serde_json::from_str(json)?;
    ensure!(requests.len() <= 256, "Too many icons");
    let entries = desktop_icons();
    let themes = themes();
    let mut result = BTreeMap::new();
    for request in requests {
        for name in [&request.icon, &request.label]
            .into_iter()
            .filter(|n| !n.is_empty())
        {
            let icon = entries
                .get(&name.to_lowercase())
                .map(String::as_str)
                .unwrap_or(name);
            let path = if icon.starts_with('/') {
                let path = PathBuf::from(icon);
                path.is_file().then_some(path)
            } else {
                themes.iter().find_map(|theme| {
                    freedesktop_icons::lookup(icon)
                        .with_size(24)
                        .with_theme(theme)
                        .find()
                })
            };
            if let Some(path) = path {
                result.insert(request.key.clone(), path.to_string_lossy().into_owned());
                break;
            }
        }
    }
    Ok(result)
}
