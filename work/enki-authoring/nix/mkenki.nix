{
  lib,
  stdenv,
  src,
  gnumake,
  curl,
  gmp,
  lmdb,
  openssl,
  libsodium,
  libblake3,
  compiler,
  cc,
  extraNativeBuildInputs ? [],
}: {
  pname,
  buildType,
  makeTarget ? "all",
  makeArgs ? "",
  installPackage ? true,
}:
stdenv.mkDerivation {
  inherit pname src;
  version = "0.1.0";

  nativeBuildInputs =
    [
      gnumake
    ]
    ++ extraNativeBuildInputs;

  buildInputs = [
    curl
    gmp
    lmdb
    openssl
    libsodium
    libblake3
  ];

  dontConfigure = true;
  strictDeps = true;
  enableParallelBuilding = true;
  hardeningDisable = ["fortify" "fortify3"];

  buildPhase = ''
    runHook preBuild
    make ${makeTarget} BUILD_TYPE=${buildType} CC=${compiler}/bin/${cc} ${makeArgs}
    runHook postBuild
  '';

  installPhase =
    if installPackage
    then ''
      runHook preInstall
      make install BUILD_TYPE=${buildType} PREFIX=$out
      runHook postInstall
    ''
    else ''
      runHook preInstall
      mkdir -p $out
      printf '%s\n' '${pname} passed' > $out/result.txt
      runHook postInstall
    '';

  meta = {
    description = "PLAN runtime and C libraries";
    homepage = "https://github.com/axsys-org/enki";
    license = lib.licenses.mit;
    mainProgram = "wisp";
    platforms = lib.platforms.unix;
  };
}
