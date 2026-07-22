{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.rex = {
    url = "github:liam-fitzgerald/rex/lf/remove-quip-poems";
    flake = false;
  };
  inputs.enki = {
    url = "github:axsys-org/enki/lf/silo";
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
          enkiWriteClosePatch = pkgs.writeText "enki-op82-write-close.patch" ''
            diff --git a/pkg/plan/src/rplan.c b/pkg/plan/src/rplan.c
            index 54c6afb..60bd4ce 100644
            --- a/pkg/plan/src/rplan.c
            +++ b/pkg/plan/src/rplan.c
            @@ -661,8 +661,11 @@ pl_val pl_op82_write(pl_thread* t, size_t ab) {
               uint8_t* b = rp_nat_bytes(ARG(1), true, &n);
               int rc = rp_write_all(fd, b, n);
               free(b);
            -  if (rc < 0)
            +  if (rc < 0) {
            +    /* The caller cannot run CloseFd after this primop raises. */
            +    ax_fd_close((size_t)h);
                 pl_raise_msg(t, "Write: write failed");
            +  }
               return 0;
             }
          '';
          enkiPkg = enki.packages.${system}.default.overrideAttrs (old: {
            patches = (old.patches or []) ++ [ enkiWriteClosePatch ];
          });


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
          enkiWriteClosePatch = pkgs.writeText "enki-op82-write-close.patch" ''
            diff --git a/pkg/plan/src/rplan.c b/pkg/plan/src/rplan.c
            index 54c6afb..60bd4ce 100644
            --- a/pkg/plan/src/rplan.c
            +++ b/pkg/plan/src/rplan.c
            @@ -661,8 +661,11 @@ pl_val pl_op82_write(pl_thread* t, size_t ab) {
               uint8_t* b = rp_nat_bytes(ARG(1), true, &n);
               int rc = rp_write_all(fd, b, n);
               free(b);
            -  if (rc < 0)
            +  if (rc < 0) {
            +    /* The caller cannot run CloseFd after this primop raises. */
            +    ax_fd_close((size_t)h);
                 pl_raise_msg(t, "Write: write failed");
            +  }
               return 0;
             }
          '';
          enkiPkg = enki.packages.${system}.default.overrideAttrs (old: {
            patches = (old.patches or []) ++ [ enkiWriteClosePatch ];
          });
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
          foil-async-tests = runReaverTest "foil-async-tests";
          buddy-tests = runReaverTest "buddy-tests";
          forge-tests = runReaverTest "forge-tests";
        });
    };
}
