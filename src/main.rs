mod audio;
mod install;
mod server;
use anyhow::{Result, bail, ensure};
fn main() {
    if let Err(e) = run() {
        eprintln!("Nix Sound: {e:#}");
        std::process::exit(1);
    }
}
fn run() -> Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "Nix Sound — native Noctalia sound overlay\n\nUsage: nix-settings [sound | install-plugin | doctor | snapshot | watch | request JSON]\n\n  sound           Open the centered overlay (default)\n  install-plugin  Install/enable the local Noctalia plugin; preserve backups\n  doctor          Check Noctalia and the audio server\n  snapshot        Print the audio graph as JSON\n  watch           Event-driven plugin backend (one per session)\n  request JSON    Send a validated audio operation\n\nRequires Noctalia 5.2+ (API 31) and PipeWire-Pulse (pactl). No GTK/Qt runtime."
        );
        return Ok(());
    }
    if args == ["--version"] {
        println!("nix-settings {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    match args.first().map(String::as_str).unwrap_or("sound") {
        "sound" => {
            ensure!(args.len() <= 1, "Unexpected argument");
            install::open()
        }
        "install-plugin" => {
            ensure!(args.len() == 1, "Unexpected argument");
            install::install()
        }
        "snapshot" => {
            ensure!(args.len() == 1, "Unexpected argument");
            println!("{}", serde_json::to_string(&audio::snapshot()?)?);
            Ok(())
        }
        "watch" => {
            ensure!(args.len() == 1, "Unexpected argument");
            server::watch()
        }
        "request" => {
            ensure!(args.len() == 2, "Pass one JSON object");
            let value = server::request(&args[1])?;
            println!("{value}");
            ensure!(
                value["ok"] == true,
                "{}",
                value["error"].as_str().unwrap_or("Request failed")
            );
            Ok(())
        }
        "doctor" => {
            ensure!(args.len() == 1, "Unexpected argument");
            let host = std::process::Command::new("noctalia")
                .arg("--version")
                .output()?;
            ensure!(host.status.success(), "Noctalia unavailable");
            println!("Noctalia: {}", String::from_utf8_lossy(&host.stdout).trim());
            let s = audio::snapshot()?;
            println!(
                "Audio: {} outputs, {} inputs, {} application streams",
                s.outputs.len(),
                s.inputs.len(),
                s.playback.len() + s.recording.len()
            );
            install::diagnose()
        }
        _ => bail!("Unknown command; use --help"),
    }
}
