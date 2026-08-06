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
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ];
  };
}
