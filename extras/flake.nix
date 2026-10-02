{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.mash = {
    type = "git";
    url = "https://github.com/axsys-org/mash.git";
    rev = "e6b81238d81242f9f053e21d9b498d84f5129383";
    allRefs = true;
    inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = { self, nixpkgs, mash }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      each = nixpkgs.lib.genAttrs systems;
    in {
      packages = each (system: {
        mash-workspace = mash.packages.${system}.workspace;
      });
      devShells = each (system: {
        debugger = nixpkgs.legacyPackages.${system}.mkShell {
          packages = [ mash.packages.${system}.nodejs mash.packages.${system}.pnpm
            nixpkgs.legacyPackages.${system}.python3 ];
          MASH_NIX_ROOT = "${mash.packages.${system}.workspace}";
        };
      });
      lib.mounts = builtins.attrNames (builtins.readDir ./mounts);
    };
}
