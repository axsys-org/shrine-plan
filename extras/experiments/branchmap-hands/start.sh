#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$HERE/../../.." && pwd)
export BRANCHMAP_PORT=${BRANCHMAP_PORT:-8192}
WORLD=${BRANCHMAP_WORLD:-"$HERE/run/world"}
if [ "${_HANDS_GOO_SHELL:-}" != "$REPO" ]; then
  exec nix --extra-experimental-features 'nix-command flakes' develop \
    --no-update-lock-file "path:$REPO#eden" --command env _HANDS_GOO_SHELL="$REPO" TMPDIR="${TMPDIR:-/tmp}" sh "$HERE/start.sh"
fi
if lsof -nP -iTCP:"$BRANCHMAP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $BRANCHMAP_PORT is occupied; choose another BRANCHMAP_PORT." >&2
  exit 1
fi
mkdir -p "$HERE/run"
if [ "$(uname -s)" != Darwin ]; then
  echo 'This launcher uses the macOS loopback bind adapter.' >&2
  exit 1
fi
clang -dynamiclib -o "$HERE/run/loopback_bind.dylib" "$REPO/extras/mounts/branchmap/loopback_bind.c"
exec env _EDEN_NIX_ROOT="$REPO" DYLD_INSERT_LIBRARIES="$HERE/run/loopback_bind.dylib" \
  python3 "$REPO/x/eden" --mount mcp --mount probe --mount branchmap --mount explorer \
    --port "$BRANCHMAP_PORT" --world "$WORLD"
