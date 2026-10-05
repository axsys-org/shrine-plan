{
  description = "enki C library project with Nix, Make, Greatest, theft, and libFuzzer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    reaver = {
      url = "github:axsys-org/shrine-plan/lf/fix-silo";
      flake = false;
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    treefmt-nix,
    reaver,
  }:
    flake-utils.lib.eachSystem [
      "x86_64-linux"
      "aarch64-linux"
      "aarch64-darwin"
    ] (
      system: let
        pkgs = import nixpkgs {inherit system;};
        lib = pkgs.lib;
        stdenv = pkgs.stdenv;
        src = lib.fileset.toSource {
          root = ./.;
          fileset = lib.fileset.unions [
            ./.clang-format
            ./.clang-tidy
            ./Makefile
            ./pkg
            ./tests
          ];
        };

        treefmtEval = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs.clang-format.enable = true;
          programs.alejandra.enable = true;
          programs.mdformat.enable = true;
          settings.formatter.clang-format.includes = [
            "*.c"
            "*.h"
          ];
          settings.formatter.mdformat.includes = [
            "*.md"
          ];
          settings.formatter.alejandra.includes = [
            "*.nix"
          ];
        };

        compilerFor = buildType:
          if buildType == "coverage"
          then {
            stdenv = pkgs.gccStdenv;
            compiler = pkgs.gccStdenv.cc;
            cc = "gcc";
          }
          else if stdenv.isDarwin
          then {
            stdenv = pkgs.llvmPackages.stdenv;
            compiler = pkgs.llvmPackages.stdenv.cc;
            cc = "clang";
          }
          else if lib.elem buildType ["debug" "release"]
          then {
            stdenv = pkgs.gccStdenv;
            compiler = pkgs.gccStdenv.cc;
            cc = "gcc";
          }
          else {
            stdenv = pkgs.llvmPackages.stdenv;
            compiler = pkgs.llvmPackages.stdenv.cc;
            cc = "clang";
          };

        mkWithCompiler = buildType: let
          selected = compilerFor buildType;
        in
          import ./nix/mkenki.nix {
            inherit lib src;
            inherit (pkgs) gnumake curl gmp lmdb openssl libsodium libblake3;
            inherit (selected) stdenv compiler cc;
          };

        mkenki = buildType: let
          selected = compilerFor buildType;
          pgoMakeArgs =
            lib.optionalString (buildType == "pgo")
            (lib.concatStringsSep " " [
              "PGO_REAVER_SRC=${reaver}/src"
              "PGO_CC=${selected.compiler}/bin/${selected.cc}"
              "LLVM_PROFDATA=${pkgs.llvmPackages.llvm}/bin/llvm-profdata"
            ]);
        in
          (mkWithCompiler buildType {
            pname = "enki${lib.optionalString (buildType != "release") "-${buildType}"}";
            inherit buildType;
            makeArgs = pgoMakeArgs;
          }).overrideAttrs (_old: {
            installPhase = ''
              runHook preInstall
              make install BUILD_TYPE=${buildType} PREFIX=$out ${pgoMakeArgs}
              runHook postInstall
            '';
          });

        enkiRelease = mkenki "pgo";
        enkiReleaseNoPGO = mkenki "release";

        mkBinPackage = name: extraInstall:
          pkgs.runCommand "enki-${name}-0.1.0" {
            meta = {
              description = "${name} binary from enki";
              homepage = "https://github.com/axsys-org/enki";
              license = lib.licenses.mit;
              mainProgram = name;
              platforms = lib.platforms.unix;
            };
          } ''
            mkdir -p $out/bin
            ln -s ${enkiRelease}/bin/${name} $out/bin/${name}
            ${extraInstall}
          '';
        wispPackage = mkBinPackage "wisp" ''
          mkdir -p $out/share/enki/reaver
          cp -R ${reaver}/src $out/share/enki/reaver/src
        '';
        assemblerPackage = mkBinPackage "assembler" "";

        mkCheckArgs = buildType: suffix: makeArgs:
          (mkWithCompiler buildType {
            pname = "enki-tests-${buildType}${suffix}";
            inherit buildType makeArgs;
            makeTarget = "test";
            installPackage = false;
          }).overrideAttrs (_old: {
            ENKI_REAVER_SRC_DIR = "${reaver}/src";
            ENKI_REAVER_PLAN_DIR = "${reaver}/src/plan";
            # The HTTP tests talk to a loopback mock server; the Darwin
            # sandbox blocks even localhost without this.
            __darwinAllowLocalNetworking = true;
          });

        mkCheck = buildType: mkCheckArgs buildType "" "";
        /*
        no TSAN for macOS - causes occasional (nondeterministic) crashes in CI
        ASAN should be disabled until we fix bytecode lifecycles
        */
        # release: the only leg that runs the -O3 -DNDEBUG codegen that ships
        # (assert() and the PL_GC_FORBID accounting compile out there).
        testBuildTypes = ["debug" "ubsan" "release"];
        linuxTestBuildTypes = ["tsan"];
        testChecks =
          lib.listToAttrs
          (map
            (buildType: {
              name = "tests-${buildType}";
              value = mkCheck buildType;
            })
            testBuildTypes)
          // (lib.optionalAttrs (stdenv.isLinux) (lib.listToAttrs (map
            (buildType: {
              name = "tests-${buildType}";
              value = mkCheck buildType;
            })
            linuxTestBuildTypes)))
          // {
            # YIELD_STRESS (spec §10.1): every depth-0 safepoint suspends
            tests-debug-yield-stress =
              mkCheckArgs "debug" "-yield-stress" "YIELD_STRESS=1";
            # GC_STRESS (DEVELOP.md): every pl_gc_reserve collects, so a
            # missing root fails deterministically instead of by luck
            tests-debug-gc-stress =
              mkCheckArgs "debug" "-gc-stress" "GC_STRESS=1";
          };

        coverageReport = (compilerFor "coverage").stdenv.mkDerivation {
          pname = "enki-coverage-report";
          version = "0.1.0";
          inherit src;

          nativeBuildInputs = [
            pkgs.gnumake
            pkgs.lcov
          ];

          ENKI_REAVER_SRC_DIR = "${reaver}/src";
          ENKI_REAVER_PLAN_DIR = "${reaver}/src/plan";
          buildInputs = [
            pkgs.curl
            pkgs.gmp
            pkgs.lmdb
            pkgs.openssl
            pkgs.libsodium
            pkgs.libblake3
          ];
          __darwinAllowLocalNetworking = true;

          dontConfigure = true;
          strictDeps = true;
          enableParallelBuilding = true;
          buildPhase = ''
            runHook preBuild
            make coverage BUILD_TYPE=coverage CC=${(compilerFor "coverage").compiler}/bin/${(compilerFor "coverage").cc}
            runHook postBuild
          '';

          installPhase = ''
            runHook preInstall
            mkdir -p $out
            cp -R build/coverage/html $out/html
            sed "s#^SF:$PWD/#SF:#" \
              build/coverage/coverage/enki.filtered.info > $out/enki.info
            runHook postInstall
          '';
        };

        coverageApp = pkgs.writeShellApplication {
          name = "enki-coverage-report";
          text = ''
            report="${coverageReport}/html/index.html"
            if command -v xdg-open >/dev/null 2>&1 && [ -n "''${DISPLAY:-}" ]; then
              xdg-open "$report" >/dev/null 2>&1 || true
            elif command -v open >/dev/null 2>&1; then
              open "$report" >/dev/null 2>&1 || true
            fi
            printf '%s\n' "$report"
          '';
        };
      in {
        packages = {
          default = enkiRelease;
          enki = enkiRelease;
          enki-release = enkiReleaseNoPGO;
          wisp = wispPackage;
          assembler = assemblerPackage;
          enki-debug = mkenki "debug";
          enki-asan = mkenki "asan";
          enki-ubsan = mkenki "ubsan";
          enki-tsan = mkenki "tsan";
          enki-coverage = mkenki "coverage";
          coverage = coverageReport;
        };

        checks =
          testChecks
          // {
            format = treefmtEval.config.build.check self;
          };

        apps = {
          wisp = flake-utils.lib.mkApp {
            drv = wispPackage;
            name = "wisp";
          };
          assembler = flake-utils.lib.mkApp {
            drv = assemblerPackage;
            name = "assembler";
          };
          coverage-report = flake-utils.lib.mkApp {drv = coverageApp;};
        };

        formatter = treefmtEval.config.build.wrapper;

        devShells.default = pkgs.mkShell {
          ENKI_REAVER_SRC_DIR = "${reaver}/src";
          ENKI_REAVER_PLAN_DIR = "${reaver}/src/plan";

          packages =
            [
              pkgs.gcc
              pkgs.clang
              pkgs.clang-tools
              pkgs.bear
              pkgs.gnumake
              pkgs.curl
              pkgs.gmp
              pkgs.lmdb
              pkgs.openssl
              pkgs.libsodium
              pkgs.libblake3
              pkgs.lcov
              pkgs.gcovr
              pkgs.compiledb
              pkgs.alejandra
              pkgs.mdformat
              pkgs.samply
              treefmtEval.config.build.wrapper
            ]
            ++ lib.optionals stdenv.isLinux [
              pkgs.valgrind
              pkgs.binutils
            ];

          shellHook = ''
            cat <<'BANNER'
            enki development shell

            Common targets:
              make
              make test
              make BUILD_TYPE=asan test
              make BUILD_TYPE=ubsan test
              make BUILD_TYPE=tsan test
              make coverage
              make compile-commands
              make tidy
              make format-check
              # make CC=clang BUILD_TYPE=asan fuzz FUZZ_ARGS="-max_total_time=60"
            BANNER
          '';
        };
      }
    );
}
