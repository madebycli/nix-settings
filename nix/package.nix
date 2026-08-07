{
  lib,
  stdenvNoCC,
  closureInfo,
  python3,
  gtk3,
  gtk-layer-shell,
  glib,
  gdk-pixbuf,
  pango,
  at-spi2-core,
  fontconfig,
  gsettings-desktop-schemas,
  shared-mime-info,
  hicolor-icon-theme,
  gobject-introspection,
  pipewire,
  wireplumber,
}:

let
  versionLines = lib.splitString "\n" (builtins.readFile ../src/nix_settings/version.py);
  versionLine = lib.findFirst (
    line: builtins.match "__version__ = \"([^\"]+)\"" line != null
  ) null versionLines;
  versionMatch =
    if versionLine == null then
      throw "Unable to read Nix Settings version from src/nix_settings/version.py"
    else
      builtins.match "__version__ = \"([^\"]+)\"" versionLine;
  packageVersion = builtins.elemAt versionMatch 0;
  python = python3.withPackages (
    pythonPackages: with pythonPackages; [
      pygobject3
      pycairo
    ]
  );
  typelibSourceClosure = closureInfo {
    rootPaths = [
      python
      glib
      gdk-pixbuf
      pango
      at-spi2-core
      gtk3
      gtk-layer-shell
      gobject-introspection
    ];
  };
  runtimeTypelibs = stdenvNoCC.mkDerivation {
    pname = "nix-settings-runtime-typelibs";
    version = "1";
    dontUnpack = true;
    installPhase = ''
      destination="$out/lib/girepository-1.0"
      mkdir -p "$destination"
      while IFS= read -r source; do
        [ -e "$source" ] || continue
        while IFS= read -r typelib; do
          install -m644 "$typelib" "$destination/$(basename "$typelib")"
        done < <(find -L "$source" -type f -name '*.typelib' -print)
      done < ${typelibSourceClosure}/store-paths
      for required in Gtk-3.0 Gdk-3.0 GLib-2.0 Gio-2.0 GtkLayerShell-0.1; do
        test -f "$destination/$required.typelib" || {
          echo "missing runtime typelib: $required" >&2
          exit 1
        }
      done
    '';
  };
  typelibPath = lib.makeSearchPath "lib/girepository-1.0" [
    runtimeTypelibs
    glib
    gtk3
    gtk-layer-shell
    gdk-pixbuf
    pango
    at-spi2-core
  ];
  dataPath = lib.makeSearchPath "share" [
    glib
    gtk3
    gsettings-desktop-schemas
    shared-mime-info
    hicolor-icon-theme
  ];
  runtimePath = lib.makeBinPath [ pipewire wireplumber ];
  pixbufLoaders = "${gdk-pixbuf}/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache";
  fontconfigFile = "${fontconfig.out}/etc/fonts/fonts.conf";
in
stdenvNoCC.mkDerivation {
  pname = "nix-settings";
  version = packageVersion;
  src = lib.cleanSource ../.;
  strictDeps = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    libexec="$out/libexec/nix-settings"
    mkdir -p "$libexec" "$out/bin" "$out/share/applications" \
      "$out/share/icons/hicolor/scalable/apps" "$out/share/doc/nix-settings"
    cp -r src/nix_settings "$libexec/"

    cat > "$out/bin/nix-settings" <<PY
#!${python.interpreter}
import os
import runpy
import sys

sys.dont_write_bytecode = True


def prepend(name: str, value: str) -> None:
    current = os.environ.get(name)
    os.environ[name] = value if not current else f"{value}:{current}"


prepend("GI_TYPELIB_PATH", "${typelibPath}")
prepend("XDG_DATA_DIRS", "${dataPath}")
prepend("PATH", "${runtimePath}")
os.environ.setdefault("GDK_PIXBUF_MODULE_FILE", "${pixbufLoaders}")
os.environ.setdefault("FONTCONFIG_FILE", "${fontconfigFile}")
sys.path.insert(0, "$libexec")
runpy.run_module("nix_settings", run_name="__main__")
PY
    chmod +x "$out/bin/nix-settings"

    install -m644 data/com.madebycli.NixSettings.desktop "$out/share/applications/"
    install -m644 data/icons/hicolor/scalable/apps/com.madebycli.NixSettings.svg \
      "$out/share/icons/hicolor/scalable/apps/"
    install -m644 README.md LICENSE "$out/share/doc/nix-settings/"
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    export HOME="$TMPDIR/home"
    export XDG_RUNTIME_DIR="$TMPDIR/runtime"
    mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"

    test "$("$out/bin/nix-settings" --version)" = "nix-settings ${packageVersion}"
    "$out/bin/nix-settings" --help | grep -q doctor
    set +e
    "$out/bin/nix-settings" doctor > doctor.txt
    result=$?
    set -e
    test "$result" -ne 0
    grep -q 'GTK 3' doctor.txt
    grep -q 'GTK Layer Shell' doctor.txt

    if grep -R -E '/usr/bin/python|/usr/bin/env|Gtk4LayerShell|Gtk-4.0' \
      "$out/bin" "$out/libexec/nix-settings"; then
      echo "non-hermetic path or GTK4 reference found in Nix Settings output" >&2
      exit 1
    fi
    runHook postInstallCheck
  '';

  meta = {
    description = "GTK3 layer-shell sound center for NixOS";
    homepage = "https://github.com/madebycli/nix-settings";
    license = lib.licenses.mit;
    mainProgram = "nix-settings";
    platforms = lib.platforms.linux;
  };
}
