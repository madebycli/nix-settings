{
  description = "Nix Sound — native adaptive Noctalia overlay";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      each = nixpkgs.lib.genAttrs systems;
    in {
      packages = each (system:
        let pkgs = import nixpkgs { inherit system; }; in {
          nix-settings = pkgs.callPackage ./nix/package.nix {};
          default = self.packages.${system}.nix-settings;
          noctalia-plugin = pkgs.runCommand "nix-sound-plugin" {} ''
            mkdir -p "$out/share/noctalia/plugins/nix-sound"
            cp -r ${./plugins/nix-sound}/. "$out/share/noctalia/plugins/nix-sound/"
          '';
        });
      apps = each (system: rec {
        nix-settings = { type = "app"; program = "${self.packages.${system}.nix-settings}/bin/nix-settings"; };
        default = nix-settings;
      });
      checks = each (system:
        let pkgs = import nixpkgs { inherit system; }; in {
          package = self.packages.${system}.nix-settings;
          cli = pkgs.runCommand "nix-sound-cli" { nativeBuildInputs = [self.packages.${system}.nix-settings]; } ''
            nix-settings --version
            nix-settings --help | grep -q doctor
            touch "$out"
          '';
          plugin = pkgs.runCommand "nix-sound-native-plugin" { nativeBuildInputs = [pkgs.noctalia pkgs.python3 pkgs.luau]; } ''
            export XDG_CONFIG_HOME="$TMPDIR/config" XDG_DATA_HOME="$TMPDIR/data"
            noctalia plugins lint ${./plugins/nix-sound} > "$out"
            python3 ${./tools/plugin_contract.py} --plugin ${./plugins/nix-sound} --noctalia-source ${pkgs.noctalia.src}
          '';
      });
      devShells = each (system:
        let pkgs = import nixpkgs { inherit system; }; in {
          default = pkgs.mkShell { packages = with pkgs; [ cargo rustc rustfmt clippy pulseaudio ]; };
        });
      overlays.default = final: _: { nix-settings = final.callPackage ./nix/package.nix {}; };
      nixosModules = {
        nix-settings = args@{pkgs,...}: import ./nix/module.nix (args // {defaultPackage = self.packages.${pkgs.stdenv.hostPlatform.system}.nix-settings;});
        default = self.nixosModules.nix-settings;
      };
      homeManagerModules = {
        nix-settings = args@{pkgs,...}: import ./nix/home-manager-module.nix (args // {defaultPackage = self.packages.${pkgs.stdenv.hostPlatform.system}.nix-settings;});
        default = self.homeManagerModules.nix-settings;
      };
    };
}
