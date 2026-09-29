{
  description = "Standalone Foil Goo: retained Rex parser/printer toolchain";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    rex = { url = "github:sol-plunder/rex"; flake = false; };
  };
  outputs = { self, nixpkgs, rex }:
    let systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
    in { devShells = nixpkgs.lib.genAttrs systems (system:
      let pkgs = nixpkgs.legacyPackages.${system};
          hp = pkgs.haskellPackages.extend (final: previous: {
            rex = pkgs.haskell.lib.dontCheck (final.callCabal2nix "rex" rex {});
          });
      in { default = pkgs.mkShell { packages = [
        (hp.ghcWithPackages (p: [ p.rex p.aeson p.bytestring p.vector p.text ]))
      ]; }; }); };
}
