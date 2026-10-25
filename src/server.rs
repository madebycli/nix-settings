use crate::audio::{self, Request, Snapshot};
use anyhow::{Context, Result, ensure};
use serde_json::{Value, json};
use std::{
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Read, Write},
    os::{
        fd::AsRawFd,
        unix::{
            fs::{DirBuilderExt, MetadataExt, OpenOptionsExt, PermissionsExt},
            net::{UnixListener, UnixStream},
        },
    },
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, SyncSender},
    },
    thread,
    time::{Duration, Instant},
};

static STOP: AtomicBool = AtomicBool::new(false);
extern "C" fn stop(_: libc::c_int) {
    STOP.store(true, Ordering::Relaxed);
}
pub fn directory() -> Result<PathBuf> {
    let base = PathBuf::from(
        std::env::var_os("XDG_RUNTIME_DIR")
            .context("XDG_RUNTIME_DIR is missing; run inside your desktop session")?,
    );
    let path = base.join("nix-sound");
    fs::DirBuilder::new()
        .mode(0o700)
        .create(&path)
        .or_else(|e| {
            if e.kind() == std::io::ErrorKind::AlreadyExists {
                Ok(())
            } else {
                Err(e)
            }
        })?;
    let metadata = fs::symlink_metadata(&path)?;
    ensure!(
        metadata.is_dir()
            && metadata.uid() == unsafe { libc::geteuid() }
            && metadata.mode() & 0o077 == 0,
        "Unsafe nix-sound runtime directory"
    );
    Ok(path)
}
fn read_request(stream: &UnixStream) -> Result<Request> {
    let mut payload = String::new();
    BufReader::new(stream).take(16385).read_line(&mut payload)?;
    ensure!(
        payload.len() <= 16384 && payload.ends_with('\n'),
        "Invalid or oversized request"
    );
    Ok(serde_json::from_str(&payload)?)
}
pub fn request(value: &str) -> Result<Value> {
    let mut stream =
        UnixStream::connect(directory()?.join("audio.sock")).context("Open Nix Sound first")?;
    stream.set_read_timeout(Some(Duration::from_secs(5)))?;
    stream.set_write_timeout(Some(Duration::from_secs(2)))?;
    ensure!(
        value.len() <= 16384 && !value.contains('\n'),
        "Invalid request"
    );
    writeln!(stream, "{value}")?;
    let mut output = String::new();
    BufReader::new(stream)
        .take(2 * 1024 * 1024)
        .read_line(&mut output)?;
    Ok(serde_json::from_str(&output)?)
}
enum Event {
    Changed,
    Disconnected(String),
    Request(Request, SyncSender<Value>),
}
struct Subscription(Arc<Mutex<Option<Child>>>);
impl Drop for Subscription {
    fn drop(&mut self) {
        if let Some(mut child) = self.0.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
fn subscribe(tx: SyncSender<Event>) -> Subscription {
    let process = Arc::new(Mutex::new(None));
    let shared = process.clone();
    thread::spawn(move || {
        let mut delay = 250;
        while !STOP.load(Ordering::Relaxed) {
            let child = Command::new("pactl")
                .arg("subscribe")
                .env("LC_ALL", "C")
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn();
            match child {
                Ok(mut child) => {
                    let stdout = child.stdout.take().unwrap();
                    *shared.lock().unwrap() = Some(child);
                    let _ = tx.send(Event::Changed);
                    for line in BufReader::new(stdout).lines() {
                        let Ok(line) = line else {
                            break;
                        };
                        delay = 250;
                        if [
                            " on sink #",
                            " on source #",
                            " on sink-input #",
                            " on source-output #",
                            " on server #",
                            " on card #",
                        ]
                        .iter()
                        .any(|s| line.contains(s))
                        {
                            let _ = tx.try_send(Event::Changed);
                        }
                    }
                    if let Some(mut child) = shared.lock().unwrap().take() {
                        let _ = child.wait();
                    }
                    let _ = tx.send(Event::Disconnected(
                        "Audio server disconnected; reconnecting…".into(),
                    ));
                }
                Err(e) => {
                    let _ = tx.send(Event::Disconnected(e.to_string()));
                }
            }
            for _ in 0..delay / 50 {
                if STOP.load(Ordering::Relaxed) {
                    return;
                }
                thread::sleep(Duration::from_millis(50));
            }
            delay = (delay * 2).min(4000);
        }
    });
    Subscription(process)
}
fn emit(value: &Value) -> Result<()> {
    let mut out = std::io::stdout().lock();
    serde_json::to_writer(&mut out, value)?;
    writeln!(out)?;
    out.flush()?;
    Ok(())
}

pub fn watch() -> Result<()> {
    unsafe {
        libc::signal(libc::SIGTERM, stop as *const () as libc::sighandler_t);
        libc::signal(libc::SIGINT, stop as *const () as libc::sighandler_t);
    }
    let directory = directory()?;
    let mut lock: File = OpenOptions::new()
        .create(true)
        .truncate(false)
        .write(true)
        .mode(0o600)
        .open(directory.join("backend.lock"))?;
    ensure!(
        unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } == 0,
        "Nix Sound backend is already running"
    );
    lock.set_len(0)?;
    writeln!(lock, "{}", std::process::id())?;
    let path = directory.join("audio.sock");
    let _ = fs::remove_file(&path);
    let listener = UnixListener::bind(&path)?;
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600))?;
    let (tx, rx) = mpsc::sync_channel(64);
    let requests = tx.clone();
    thread::spawn(move || {
        while !STOP.load(Ordering::Relaxed) {
            let (mut stream, _) = match listener.accept() {
                Ok(v) => v,
                Err(_) => {
                    thread::sleep(Duration::from_millis(20));
                    continue;
                }
            };
            let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
            let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
            let response = match read_request(&stream) {
                Ok(request) => {
                    let (tx, rx) = mpsc::sync_channel(1);
                    if requests.send(Event::Request(request, tx)).is_err() {
                        break;
                    }
                    rx.recv_timeout(Duration::from_secs(4))
                        .unwrap_or(json!({"ok":false,"error":"Audio command timed out"}))
                }
                Err(error) => json!({"ok":false,"error":error.to_string()}),
            };
            let _ = writeln!(stream, "{response}");
        }
    });
    let _subscription = subscribe(tx);
    let mut state = Snapshot::default();
    let mut last = Value::Null;
    let mut dirty = true;
    let mut refreshed = Instant::now() - Duration::from_secs(1);
    let result = (|| -> Result<()> {
        while !STOP.load(Ordering::Relaxed) {
            if dirty && refreshed.elapsed() >= Duration::from_millis(60) {
                let value = match audio::snapshot() {
                    Ok(next) => {
                        state = next;
                        json!({"ok":true,"snapshot":state})
                    }
                    Err(e) => json!({"ok":false,"error":e.to_string()}),
                };
                if value != last {
                    emit(&value)?;
                    last = value;
                }
                refreshed = Instant::now();
                dirty = false;
            }
            match rx.recv_timeout(if dirty {
                Duration::from_millis(60)
            } else {
                Duration::from_secs(1)
            }) {
                Ok(Event::Changed) => dirty = true,
                Ok(Event::Disconnected(error)) => {
                    state = Snapshot::default();
                    emit(&json!({"ok":false,"error":error}))?;
                }
                Ok(Event::Request(request, reply)) => {
                    let result = if request.action == "refresh" {
                        Ok(())
                    } else {
                        audio::arguments(&request, &state)
                            .and_then(|args| audio::run(&args).map(|_| ()))
                    };
                    let value = match result {
                        Ok(()) => {
                            dirty = true;
                            json!({"ok":true})
                        }
                        Err(e) => json!({"ok":false,"error":e.to_string()}),
                    };
                    let _ = reply.send(value);
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => break,
                Err(_) => {}
            }
        }
        Ok(())
    })();
    STOP.store(true, Ordering::Relaxed);
    let _ = fs::remove_file(path);
    result
}
