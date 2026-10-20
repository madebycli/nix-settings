{ lib, rustPlatform, makeWrapper, pulseaudio }:
rustPlatform.buildRustPackage {
  pname = "nix-settings";
  version = (builtins.fromTOML (builtins.readFile ../Cargo.toml)).package.version;
  src = lib.cleanSource ../.;
  cargoLock.lockFile = ../Cargo.lock;
  nativeBuildInputs = [ makeWrapper ];
  postInstall = ''
    wrapProgram "$out/bin/nix-settings" --prefix PATH : ${lib.makeBinPath [ pulseaudio ]}
    mkdir -p "$out/share/noctalia/plugins/nix-sound" "$out/share/applications" "$out/share/icons/hicolor/scalable/apps"
    cp -r plugins/nix-sound/. "$out/share/noctalia/plugins/nix-sound/"
    cp data/com.madebycli.NixSettings.desktop "$out/share/applications/"
    cp data/icons/hicolor/scalable/apps/com.madebycli.NixSettings.svg "$out/share/icons/hicolor/scalable/apps/"
  '';
  meta = {
    description = "Native Noctalia sound overlay with an event-driven Rust backend";
    homepage = "https://github.com/madebycli/nix-settings";
    license = lib.licenses.mit;
    mainProgram = "nix-settings";
    platforms = lib.platforms.linux;
  };
}
