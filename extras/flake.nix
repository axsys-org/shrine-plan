{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.mash = {
    type = "git";
    url = "https://github.com/axsys-org/mash.git";
    rev = "12e5f9345d9745cb75cab4f58e39aa33da83e14e";
    allRefs = true;
    inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = { self, nixpkgs, mash }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      each = nixpkgs.lib.genAttrs systems;
    in {
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
