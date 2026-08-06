{
  description = "Nix Settings - native GTK4 settings for NixOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ self.overlays.default ];
          };
        in
        {
          inherit (pkgs) nix-settings;
          default = pkgs.nix-settings;
        });

      apps = forAllSystems (system: rec {
        nix-settings = {
          type = "app";
          program = "${self.packages.${system}.nix-settings}/bin/nix-settings";
        };
        default = nix-settings;
      });

      checks = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          source = nixpkgs.lib.cleanSource ./.;
          python = pkgs.python312.withPackages (ps: with ps; [ pytest mypy pygobject3 pycairo ]);
          package = self.packages.${system}.nix-settings;
          closure = pkgs.closureInfo { rootPaths = [ package ]; };
        in
        {
          inherit package;

          python-tests = pkgs.runCommand "nix-settings-python-tests" {
            nativeBuildInputs = [ python pkgs.ruff ];
          } ''
            cp -r ${source} source
            chmod -R u+w source
            cd source
            export PYTHONPATH="$PWD/src"
            python -m compileall -q src
            pytest -q
            ruff check .
            mypy src
            touch "$out"
          '';

          cli-smoke = pkgs.runCommand "nix-settings-cli-smoke" {
            nativeBuildInputs = [ package ];
          } ''
            export HOME="$TMPDIR/home"
            export XDG_RUNTIME_DIR="$TMPDIR/runtime"
            mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
            chmod 700 "$XDG_RUNTIME_DIR"
            nix-settings --help | grep -q doctor
            nix-settings --version | grep -q 'nix-settings 0.1.0'
            set +e
            nix-settings doctor > doctor.txt
            result=$?
            set -e
            test "$result" -ne 0
            grep -q 'Nix Settings doctor' doctor.txt
            touch "$out"
          '';

          runtime-closure-policy = pkgs.runCommand "nix-settings-runtime-closure-policy" { } ''
            if grep -E '/[^/]*(setuptools|wheel|linux-headers|gcc-wrapper|binutils-wrapper)-' \
              ${closure}/store-paths; then
              echo "forbidden build dependency in Nix Settings runtime closure" >&2
              exit 1
            fi
            if grep -R -E '/usr/bin/python|/usr/bin/env' ${package}/bin; then
              echo "non-hermetic interpreter path found" >&2
              exit 1
            fi
            touch "$out"
          '';
        });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python312.withPackages (ps: with ps; [ pytest mypy pygobject3 pycairo ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.ruff
              pkgs.nixfmt-rfc-style
              pkgs.gtk4
              pkgs.gtk4-layer-shell
              pkgs.gobject-introspection
              pkgs.pipewire
              pkgs.wireplumber
            ];
            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              echo "Nix Settings development shell"
            '';
          };
        });

      overlays.default = final: _prev: {
        nix-settings = final.callPackage ./nix/package.nix { };
      };

      nixosModules = {
        nix-settings = args@{ pkgs, ... }:
          import ./nix/module.nix (args // {
            defaultPackage = self.packages.${pkgs.system}.nix-settings;
          });
        default = self.nixosModules.nix-settings;
      };

      homeManagerModules = {
        nix-settings = args@{ pkgs, ... }:
          import ./nix/home-manager-module.nix (args // {
            defaultPackage = self.packages.${pkgs.system}.nix-settings;
          });
        default = self.homeManagerModules.nix-settings;
      };
    };
}
