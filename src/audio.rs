use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    io::Read,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

/// One server graph read, never one subprocess per node. Pulse's native volumes are perceptual.
pub fn run(args: &[String]) -> Result<String> {
    let mut child = Command::new("pactl")
        .args(args)
        .env("LC_ALL", "C")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("pactl unavailable; install PulseAudio utilities and enable PipeWire-Pulse")?;
    let mut out = child.stdout.take().unwrap();
    let mut err = child.stderr.take().unwrap();
    let output = thread::spawn(move || {
        let mut s = String::new();
        out.read_to_string(&mut s).map(|_| s)
    });
    let error = thread::spawn(move || {
        let mut s = String::new();
        err.read_to_string(&mut s).map(|_| s)
    });
    let start = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if start.elapsed() > Duration::from_secs(3) {
            let _ = child.kill();
            let _ = child.wait();
            let _ = output.join();
            let _ = error.join();
            bail!("Audio server did not respond within 3 seconds");
        }
        thread::sleep(Duration::from_millis(5));
    };
    let out = output
        .join()
        .map_err(|_| anyhow::anyhow!("Audio reader stopped"))??;
    let err = error
        .join()
        .map_err(|_| anyhow::anyhow!("Audio reader stopped"))??;
    ensure!(status.success(), "Audio command failed: {}", err.trim());
    Ok(out)
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Node {
    pub id: u32,
    pub kind: String,
    pub name: String,
    pub label: String,
    pub icon: String,
    pub volume: f64,
    pub muted: bool,
    pub device: Option<u32>,
    pub is_default: bool,
}
#[derive(Clone, Debug, Default, PartialEq, Serialize)]
pub struct Snapshot {
    pub outputs: Vec<Node>,
    pub inputs: Vec<Node>,
    pub playback: Vec<Node>,
    pub recording: Vec<Node>,
}
fn text<'a>(v: &'a Value, key: &str) -> &'a str {
    v[key].as_str().unwrap_or("")
}
fn node(v: &Value, kind: &str, default: &str) -> Option<Node> {
    let id = u32::try_from(v["index"].as_u64()?).ok()?;
    let name = text(v, "name");
    let props = &v["properties"];
    let stream = kind == "sink-input" || kind == "source-output";
    let label = if stream {
        [
            text(props, "application.name"),
            text(props, "application.process.binary"),
            text(props, "media.name"),
        ]
        .into_iter()
        .find(|s| !s.is_empty())
        .unwrap_or("Application")
    } else {
        [
            text(v, "description"),
            text(props, "device.description"),
            name,
        ]
        .into_iter()
        .find(|s| !s.is_empty())
        .unwrap_or("Audio")
    };
    let volumes: Vec<f64> = v["volume"]
        .as_object()
        .into_iter()
        .flat_map(|m| m.values())
        .filter_map(|v| v["value"].as_f64())
        .collect();
    let volume = if volumes.is_empty() {
        1.0
    } else {
        volumes.iter().sum::<f64>() / volumes.len() as f64 / 65536.0
    };
    Some(Node {
        id,
        kind: kind.into(),
        name: name.into(),
        label: label.into(),
        icon: text(props, "application.icon_name").into(),
        volume: volume.clamp(0.0, 1.0),
        muted: v["mute"].as_bool().unwrap_or(false),
        device: v[if kind == "sink-input" {
            "sink"
        } else {
            "source"
        }]
        .as_u64()
        .and_then(|v| u32::try_from(v).ok()),
        is_default: !stream && name == default,
    })
}
pub fn parse(graph: &Value, info: &Value) -> Result<Snapshot> {
    ensure!(
        graph.is_object() && graph["sinks"].is_array() && graph["sources"].is_array(),
        "Invalid audio server graph"
    );
    let collect = |key: &str, kind: &str, default: &str| -> Vec<Node> {
        let mut nodes: Vec<_> = graph[key]
            .as_array()
            .into_iter()
            .flatten()
            .filter(|v| {
                kind != "source"
                    || match &v["monitor_of_sink"] {
                        Value::Number(n) => n.as_u64() == Some(u32::MAX as u64),
                        Value::String(s) => s == "n/a" || s == "4294967295",
                        _ => {
                            text(&v["properties"], "device.class") != "monitor"
                                && !text(v, "name").ends_with(".monitor")
                        }
                    }
            })
            .filter_map(|v| node(v, kind, default))
            .collect();
        nodes.sort_by_key(|n| (!n.is_default, n.label.to_lowercase(), n.id));
        nodes
    };
    Ok(Snapshot {
        outputs: collect("sinks", "sink", text(info, "default_sink_name")),
        inputs: collect("sources", "source", text(info, "default_source_name")),
        playback: collect("sink_inputs", "sink-input", ""),
        recording: collect("source_outputs", "source-output", ""),
    })
}
pub fn snapshot() -> Result<Snapshot> {
    let graph: Value = serde_json::from_str(&run(&["--format=json".into(), "list".into()])?)?;
    let info: Value = serde_json::from_str(&run(&["--format=json".into(), "info".into()])?)?;
    parse(&graph, &info)
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub action: String,
    pub kind: Option<String>,
    pub id: Option<u32>,
    pub volume: Option<f64>,
    pub muted: Option<bool>,
    pub device: Option<u32>,
}
pub fn arguments(request: &Request, state: &Snapshot) -> Result<Vec<String>> {
    let kind = request.kind.as_deref().context("Missing node kind")?;
    let list = match kind {
        "sink" => &state.outputs,
        "source" => &state.inputs,
        "sink-input" => &state.playback,
        "source-output" => &state.recording,
        _ => bail!("Unknown node kind"),
    };
    let id = request.id.context("Missing audio node")?;
    let node = list
        .iter()
        .find(|n| n.id == id)
        .context("Audio node disconnected; refresh and try again")?;
    Ok(match request.action.as_str() {
        "volume" => {
            let volume = request.volume.context("Missing volume")?;
            ensure!(
                volume.is_finite() && (0.0..=1.0).contains(&volume),
                "Volume must be between 0 and 1"
            );
            vec![
                format!("set-{kind}-volume"),
                id.to_string(),
                format!("{:.2}%", volume * 100.0),
            ]
        }
        "mute" => vec![
            format!("set-{kind}-mute"),
            id.to_string(),
            if request.muted.context("Missing mute value")? {
                "1"
            } else {
                "0"
            }
            .into(),
        ],
        "default" => {
            ensure!(
                kind == "sink" || kind == "source",
                "Select an output or input device"
            );
            vec![format!("set-default-{kind}"), node.name.clone()]
        }
        "route" => {
            let devices = match kind {
                "sink-input" => &state.outputs,
                "source-output" => &state.inputs,
                _ => bail!("Only application streams can be routed"),
            };
            let device = request.device.context("Missing target device")?;
            ensure!(
                devices.iter().any(|n| n.id == device),
                "Target device disconnected"
            );
            vec![format!("move-{kind}"), id.to_string(), device.to_string()]
        }
        _ => bail!("Unknown audio action"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    fn fixture() -> Snapshot {
        parse(&json!({"sinks":[{"index":1,"name":"speaker","description":"Headset","volume":{"left":{"value":32768},"right":{"value":32768}},"mute":true}],
            "sources":[{"index":2,"name":"mic","monitor_of_sink":null},{"index":3,"name":"monitor","monitor_of_sink":1}],
            "sink_inputs":[{"index":8,"sink":1,"properties":{"application.name":"Music"}}],
            "source_outputs":[{"index":9,"source":2,"properties":{"application.name":"Chat"}},{"index":10,"source":2,"properties":{"application.name":"Chat"}}]}),
            &json!({"default_sink_name":"speaker","default_source_name":"mic"})).unwrap()
    }
    #[test]
    fn graph_volumes_defaults_monitors_and_duplicate_streams() {
        let s = fixture();
        assert_eq!(s.outputs[0].volume, 0.5);
        assert!(s.outputs[0].muted && s.outputs[0].is_default);
        assert_eq!(s.inputs.len(), 1);
        assert_eq!(s.playback[0].device, Some(1));
        assert_eq!(s.recording.len(), 2);
    }
    #[test]
    fn routes_use_supported_server_commands_and_validate_direction() {
        let s = fixture();
        let mut r: Request =
            serde_json::from_value(json!({"action":"route","kind":"sink-input","id":8,"device":1}))
                .unwrap();
        assert_eq!(arguments(&r, &s).unwrap(), ["move-sink-input", "8", "1"]);
        r.device = Some(2);
        assert!(arguments(&r, &s).is_err());
    }
    #[test]
    fn stale_nodes_and_invalid_volume_cannot_be_sent() {
        let s = fixture();
        let mut r: Request =
            serde_json::from_value(json!({"action":"volume","kind":"sink","id":1,"volume":0.32}))
                .unwrap();
        assert_eq!(
            arguments(&r, &s).unwrap(),
            ["set-sink-volume", "1", "32.00%"]
        );
        r.volume = Some(f64::NAN);
        assert!(arguments(&r, &s).is_err());
        r.volume = Some(0.2);
        r.id = Some(404);
        assert!(arguments(&r, &s).is_err());
    }
}
