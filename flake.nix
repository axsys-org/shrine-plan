{
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  inputs.rex = {
    url = "github:liam-fitzgerald/rex/lf/remove-quip-poems";
    flake = false;
  };
  # Liam's wormholes branch (enki PR #59): actor and Mesa handles are host capabilities, and
  # libmesa is in the runtime as opset-83 operations.
  inputs.enki = {
    url = "github:axsys-org/enki/lf/wormholes";
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
      # the world runtime: enki as pinned, with the fix for stale thunk update targets kept as GC roots
      # (enki PR #50, rebased on main), which made long-lived worlds grow without bound under reads;
      # halted actors freed (each kept its thread and heap until exit; ported to the wormholes branch,
      # where a handle is a capability and not a table index); the store collected while an actor waits
      # in a syscall (a world always waits in Accept, so its store was never collected again); and
      # SeqHost, the demand that sequences on a host capability, which Seq rejects (codegen.rvr lowers
      # every demanded let to it, so a spawn that must happen now can be demanded); and the store's
      # address space reserved without commit, as on main: the wormholes branch dropped MAP_NORESERVE, so
      # on Linux with the default overcommit rule the 256 GiB reservation is refused and nothing starts;
      # and what the kernel's networking needs of the runtime (nix/enki-pin-ops.patch): pins as values
      # (PinHash, PinBytes, PinFrom, PinNames, PinParts), so a value leaves one store and arrives in
      # another as the same pin under the same hash, and a stream holding a law is refused; sockets that
      # answer instead of raising (ReadAll, SendTo), since a raise from Connect ends the process; and
      # the key two worlds share and seal with (BoxKey, SecretSeal, SecretOpen, over libsodium)
      # and what a machine's own world may execute (nix/enki-host-ops.patch): entropy, usage, and a host
      # handle, given once to a process started with a worlds root, that makes a world's directory as a
      # copy of a staged one, starts this same runtime there, stops it and asks whether it is alive
      runtimeFor = system: enki.packages.${system}.default.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ [
          ./nix/enki-update-targets.patch
          ./nix/enki-free-halted-actors.patch
          ./nix/enki-collect-while-parked.patch
          ./nix/enki-seq-host.patch
          ./nix/enki-reserve-without-commit.patch
          ./nix/enki-pin-ops.patch
          ./nix/enki-host-ops.patch
        ];
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
