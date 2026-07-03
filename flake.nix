{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.rex = {
    url = "github:liam-fitzgerald/rex/lf/remove-quip-poems";
    flake = false;
  };
  inputs.enki = {
    url = "github:axsys-org/enki/main";
  };

  outputs = { self, nixpkgs, rex, enki }:
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
          enkiPkg = enki.packages.${system}.default;


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
              pkgs.samply
              enkiPkg
            ];
            # buildInputs = with hsPkgs; [
            #   text primitive pretty-show containers deepseq
            #   optics ghc-prim mtl transformers cryptohash-sha256
            #   base58-bytestring vector network rex
            # ];
          };
        });
      checks = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          enkiPkg = enki.packages.${system}.default;
          runReaverTest = module: pkgs.runCommand "reaver-${module}" {
            nativeBuildInputs = [ enkiPkg ];
          } ''
            cp -R ${self} repo
            chmod -R u+w repo
            cd repo
            x/test ${module} 2>&1 | tee test.log

            if grep -q '"ERROR"' test.log; then
              echo "bar"
              tail -200 test.log
              exit 1
            fi
            echo "baz"
            touch $out
          '';
        in {
          foil-bst-tests = runReaverTest "foil-bst-tests";
          foil-exec-tests = runReaverTest "foil-exec-tests";
          forge-tests = runReaverTest "forge-tests";
        });
    };
}
