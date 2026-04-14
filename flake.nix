{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.rex = {
    url = "github:liam-fitzgerald/rex/lf/remove-quip-poems";
    flake = false;
  };

  outputs = { self, nixpkgs, rex }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems f;
    in {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          hsPkgs = pkgs.haskellPackages.override {
            overrides = hfinal: hprev: {
              rex = hfinal.callCabal2nix "rex" rex {};
              plan-assembler = hfinal.callCabal2nix "plan-assembler" ./. {};
              # if rex.cabal is in a subdir, use:
              # rex = hfinal.callCabal2nix "rex" (rex + "/subdir") {};
            };
          };
        in {
          default = hsPkgs.shellFor {
            packages = hp: [ hp.plan-assembler ];
            nativeBuildInputs = [
              hsPkgs.ghcid
              hsPkgs.stylish-haskell
              hsPkgs.cabal-install
              pkgs.rlwrap
            ];
            # buildInputs = with hsPkgs; [
            #   text primitive pretty-show containers deepseq
            #   optics ghc-prim mtl transformers cryptohash-sha256
            #   base58-bytestring vector network rex
            # ];
          };
        });
    };
}
