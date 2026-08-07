{ config, lib, pkgs, defaultPackage, ... }:
let
  cfg = config.programs.nix-settings;
in
{
  options.programs.nix-settings = {
    enable = lib.mkEnableOption "Nix Settings";
    package = lib.mkOption {
      type = lib.types.package;
      default = defaultPackage;
      defaultText = lib.literalExpression "inputs.nix-settings.packages.${pkgs.system}.default";
      description = "The Nix Settings package to install.";
    };
    enablePolkitHelper = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Install the restricted Nix Settings Polkit action.";
    };
  };

  config = lib.mkIf cfg.enable (lib.mkMerge [
    {
      environment.systemPackages = [ cfg.package ];
    }
    (lib.mkIf cfg.enablePolkitHelper {
      security.polkit.enable = true;
      environment.etc."polkit-1/actions/com.madebycli.NixSettings.policy".source =
        "${cfg.package}/share/polkit-1/actions/com.madebycli.NixSettings.policy";
    })
  ]);
}
