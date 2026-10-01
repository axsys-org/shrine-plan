{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.mash = {
    type = "git";
    url = "https://github.com/axsys-org/mash.git";
    rev = "93954c6ef57629839b88762bc486babb5c348813";
    allRefs = true;
    inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = { self, nixpkgs, mash }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      each = nixpkgs.lib.genAttrs systems;
    in {
      devShells = each (system:
        let
          # This Mash revision added WA but retained the previous pnpm cache hash.
          workspace = mash.packages.${system}.workspace.overrideAttrs (_: {
            pnpmDeps = nixpkgs.legacyPackages.${system}.fetchPnpmDeps {
              pname = "mash-workspace";
              version = "0.0.0";
              src = mash;
              pnpm = mash.packages.${system}.pnpm;
              fetcherVersion = 3;
              hash = "sha256-v6Nf3KTB/1JkdPcI4A8FqQvcfxYMtw9351j9l3Vlw58=";
            };
          });
        in {
        debugger = nixpkgs.legacyPackages.${system}.mkShell {
          packages = [ mash.packages.${system}.nodejs mash.packages.${system}.pnpm
            nixpkgs.legacyPackages.${system}.python3 ];
          MASH_NIX_ROOT = "${workspace}";
        };
      });
      lib.mounts = builtins.attrNames (builtins.readDir ./mounts);
    };
}
