{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.rex = {
    url = "github:liam-fitzgerald/rex/lf/remove-quip-poems";
    flake = false;
  };
  inputs.enki = {
    url = "github:axsys-org/enki/lf/ice-opcode";
  };
  inputs.mash = {
    # Use Git's credential helper for the private repository.
    type = "git";
    url = "https://github.com/axsys-org/mash.git";
    rev = "12e5f9345d9745cb75cab4f58e39aa33da83e14e";
    allRefs = true;
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, rex, enki, mash }:
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
          mashPackages = mash.packages.${system};
          debuggerTools = [
            enkiPkg
            mashPackages.nodejs
            mashPackages.pnpm
            pkgs.python3
            pkgs.lsof
          ];

          hsPkgs = pkgs.haskellPackages.override {
            overrides = hfinal: hprev: {
              rex = hfinal.callCabal2nix "rex" rex {};
              plan-assembler = hfinal.callCabal2nix "plan-assembler" ./. {};
              # if rex.cabal is in a subdir, use:
              # rex = hfinal.callCabal2nix "rex" (rex + "/subdir") {};
            };
          };
        in {
          debugger = pkgs.mkShell {
            packages = debuggerTools;
            MASH_NIX_ROOT = "${mashPackages.workspace}";
          };
          default = hsPkgs.shellFor {
            packages = hp: [ hp.plan-assembler ];
            MASH_NIX_ROOT = "${mashPackages.workspace}";
            nativeBuildInputs = [
              hsPkgs.ghcid
              hsPkgs.stylish-haskell
              hsPkgs.cabal-install
              pkgs.rlwrap
              pkgs.samply
            ] ++ debuggerTools;
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
        in {
          default = pkgs.runCommand "reaver-tests" {
            nativeBuildInputs = [ enkiPkg pkgs.python3 ];
          } ''
            cp -R ${self} repo
            chmod -R u+w repo
            cd repo
            x/check > test.log 2>&1 || {
              cat test.log
              exit 1
            }
            mkdir -p $out
            cp test.log $out/
            for run in .check/run-*; do
              report="$out/$(basename "$run")"
              mkdir -p "$report"
              cp "$run/results.json" "$report/"
              for group in "$run"/*/; do
                dest="$report/$(basename "$group")"
                mkdir -p "$dest"
                cp "$group/input" "$group/out.log" "$group/result.json" "$dest/"
              done
            done
          '';
        });
    };
}
