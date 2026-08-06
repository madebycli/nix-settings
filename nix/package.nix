{
  lib,
  python3Packages,
  gtk4,
  gtk4-layer-shell,
  glib,
  gobject-introspection,
  wrapGAppsHook4,
  pipewire,
  wireplumber,
  hicolor-icon-theme,
  shared-mime-info,
}:

python3Packages.buildPythonApplication {
  pname = "nix-settings";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ../.;

  build-system = with python3Packages; [
    setuptools
    wheel
  ];

  dependencies = with python3Packages; [
    pygobject3
    pycairo
  ];

  nativeBuildInputs = [
    gobject-introspection
    wrapGAppsHook4
  ];

  buildInputs = [
    gtk4
    gtk4-layer-shell
    glib
    hicolor-icon-theme
    shared-mime-info
  ];

  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    pytest
  ];

  preFixup = ''
    gappsWrapperArgs+=(
      --prefix PATH : ${lib.makeBinPath [ pipewire wireplumber ]}
    )
  '';

  postInstall = ''
    install -Dm644 data/com.madebycli.NixSettings.desktop \
      "$out/share/applications/com.madebycli.NixSettings.desktop"
    install -Dm644 data/icons/hicolor/scalable/apps/com.madebycli.NixSettings.svg \
      "$out/share/icons/hicolor/scalable/apps/com.madebycli.NixSettings.svg"
  '';

  pythonImportsCheck = [ "nix_settings" ];

  meta = {
    description = "Native GTK4 settings application for NixOS";
    homepage = "https://github.com/madebycli/nix-settings";
    license = lib.licenses.mit;
    mainProgram = "nix-settings";
    platforms = lib.platforms.linux;
  };
}
