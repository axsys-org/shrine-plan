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
      runtimeFor = system: enki.packages.${system}.default.overrideAttrs (old: {
        patches = (old.patches or []) ++ [ ./nix/native-sharing.patch ./nix/native-compaction.patch ];
        postInstall = (old.postInstall or "") + ''
          $CC -std=c23 -D_GNU_SOURCE -O2 -I$out/include ${./x/eden-native-upgrade.c} \
            -L$out/lib -lplan -laxsys -llmdb -lcrypto -lgmp -lsodium -lblake3 \
            -lpthread -lm -o $out/bin/eden-native-upgrade
          $CC -std=c23 -D_GNU_SOURCE -O2 -Itests/support -I$out/include \
            tests/unit/test_plan_native.c -L$out/lib -lenki -lplan -laxsys \
            -llmdb -lcrypto -lgmp -lsodium -lblake3 -lcurl -lpthread -lm \
            -o native-check
          ./native-check
        '';
      });
    in {
      packages = forAllSystems (system: { runtime = runtimeFor system; });
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          enkiPkg = runtimeFor system;
          edenTools = [ enkiPkg pkgs.python3 pkgs.lsof ];

          hsPkgs = pkgs.haskellPackages.override {
            overrides = hfinal: hprev: {
              rex = hfinal.callCabal2nix "rex" rex {};
              plan-assembler = hfinal.callCabal2nix "plan-assembler" ./. {};
              # if rex.cabal is in a subdir, use:
              # rex = hfinal.callCabal2nix "rex" (rex + "/subdir") {};
            };
          };
        in {
          eden = pkgs.mkShell { packages = edenTools; };
          default = hsPkgs.shellFor {
            packages = hp: [ hp.plan-assembler ];
            nativeBuildInputs = [
              hsPkgs.ghcid
              hsPkgs.stylish-haskell
              hsPkgs.cabal-install
              pkgs.rlwrap
              pkgs.samply
            ] ++ edenTools;
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
          enkiPkg = runtimeFor system;
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
