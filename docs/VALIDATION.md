# Validation (2026-10-21)

Verified locally in the managed Linux environment:

- Rust unit tests, rustfmt and Clippy with warnings denied.
- Real isolated PulseAudio 17: graph parsing, exclusion of monitor sources, master volume/mute/default, real playback and recording stream routing, recording volume, server restart/reconnect, signal shutdown/socket removal.
- Real installer in temporary XDG directories: preservation of existing config and enabled plugins, original settings backup, repeat installs, no bar widget, help without mutation and malformed-settings preservation.
- Native Luau callback execution/property checks against unmodified Noctalia 5.3.0 sources (`e37d7145b95a51b801db9bb20d1c600f35111e0b`), including 1366×768, 1280×720, 800×600, 640×360 and 3840×2160 logical outputs, UI scaling, square/round corners and glass/soft cards. Luau scripts compile.

The isolated null-device audio run produced its first snapshot in about 25 ms with a debug binary; this is one test observation, not a hardware/startup performance guarantee.

The x86_64 Nix package build, packaged CLI and complete `nix flake check` (including official Noctalia plugin lint) passed locally. Both native plugins also loaded in unmodified Noctalia 5.3.0 under software-rendered Sway. The combined host runner exercised live palette/shape/border/transparency/UI-scale changes, native Sound backend startup and audio control, and native overlays at 800×600 and 1366×768 with 125% UI scaling. Screenshots remain in the execution workspace, outside the source repositories.

## 1.0.5 sound backend recovery

The native Sound panel test forced the first backend launch to fail, verified a visible connection error and automatic retry, killed a running backend and verified recovery while the panel stayed open, then hid the engine executable and verified the error state and recovery after restoring it. Audio controls, mute, routing and responsive layout checks still passed. An installer acceptance test ran the packaged Nix wrapper twice and confirmed its executable path, registered indirect GC root and repeat-install behavior. The plugin callback contract also verifies bounded retry timing and that a failed backend is not shown as “no devices.” On the user's machine, `nix-settings doctor` reported 3 outputs, 2 inputs and 3 application streams; this confirms the backend sees the audio graph but does not by itself identify the installed plugin's original launch failure.

Sound now prefers a centered 1600 × 900 logical-pixel surface before Noctalia UI scaling, clamped by the host on smaller monitors. Scroll viewports receive exact remaining height through native flex layout, so content stays within the panel.

PipeWire-Pulse on the user's machine, physical device hotplug, a physical 15-inch monitor and GPU-backed MangoWM remain unverified. The Sway/Noctalia tests do not establish target-hardware acceptance. Runtime prerequisites and installation commands are in README.md.

## 1.0.1 regression checks

The 1.0.0 native callback incorrectly expected a value from onDragEnd, causing the user's “Missing volume” report. The Luau contract now invokes every master/application slider with the real native onChange(value), onDragEnd() signature. `tools/noctalia_sound_check.py` runs stock Noctalia against an isolated Pulse server with six playback streams, one recorder and an XDG icon fixture; genuine virtual pointer clicks and drag/release input must change actual server volume for output, microphone, playback and recording. Large and small monitor screenshots, 125% UI scaling, long device names and live resizing are covered. Screenshots cover full-work-area sizing and dense cards at large and small logical outputs. It needs the developer virtual_input executable from GIF-Player; Sound has no GIF runtime dependency.

The upgrade acceptance starts a running host with an old 480×400 manifest, reinstalls Sound and verifies that the running host uses the new filled panel without restarting Noctalia. The native run also tests master/application mute and unmute in place; selected buttons inherit the host's active palette. Installer-only acceptance uses a private runtime directory to avoid touching a desktop IPC session.

## 1.0.2 sizing and percentage regression

The user found 1.0.1's full-work-area overlay too large and explicitly chose a smaller overall overlay while retaining current control sizes. The centered surface now prefers 1600 × 900 logical pixels before Noctalia UI scaling, with native clamping on smaller monitors. A fixed percentage column prevents the 9%/90%/100% digit-count transition from changing slider track length.

The real native host test renders each of those three percentages and clicks identical coordinates on master and application tracks. All three initial values map to exactly the same resulting volume per track (76% master, 77% application in the default fixture), verifying stable geometry through real pointer input. Screenshots also cover the capped surface on a 2560×1440 output and clamping on laptop/smaller displays.

## 1.0.3 typography and alignment

The native fixture now explicitly uses shell.lang=de and the host's monospace font, with different-length application names. Screenshots exercise “Systemlautstärke”, “Mikrofon”, section titles and aligned routing selectors at wide/narrow sizes. Header glyphs use fixed square slots and labels use the native textFixedHeight baseline. Native warnings about unsupported UI values fail the host check; the percentage label alignment uses the supported end token. Existing volume, mute, pointer mapping, installer upgrade, monitor sizing and scaling acceptance is retained.

## 1.0.4 spacing correction (2026-10-23)

The user's close-up showed accumulated gaps around the section title and first application, plus master/application card edges offset by native list padding. Wide master cards now match the native ScrollView inset, section captions align with inner card content, and duplicate column/heading gaps are removed. The native fixture checks identical pointer mapping on master and app tracks as well as the existing 9%/90%/100% stability checks. At the default fixture both tracks now map the same coordinate to 76%. Scaled captures reopen the panel to apply Noctalia's negotiated 125% content scale before inspecting the matched insets.
