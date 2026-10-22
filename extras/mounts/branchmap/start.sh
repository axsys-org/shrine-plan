#!/bin/sh
set -eu
MOUNT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$MOUNT/../../.." && pwd)
export BRANCHMAP_PORT=${BRANCHMAP_PORT:-8190}
if [ "$(uname -s)" != Darwin ]; then
  echo 'This launcher requires macOS for its loopback bind adapter.' >&2
  exit 1
fi
if [ "${_BRANCHMAP_SHELL:-}" != "$REPO" ]; then
  exec nix --extra-experimental-features 'nix-command flakes' develop \
    --no-update-lock-file "$REPO#eden" --command env _BRANCHMAP_SHELL="$REPO" TMPDIR="${TMPDIR:-/tmp}" sh "$MOUNT/start.sh"
fi
if lsof -nP -iTCP:"$BRANCHMAP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $BRANCHMAP_PORT is occupied; inspect its owner first." >&2
  exit 1
fi
mkdir -p "$MOUNT/run"
clang -dynamiclib -o "$MOUNT/run/loopback_bind.dylib" "$MOUNT/loopback_bind.c"
exec env _EDEN_NIX_ROOT="$REPO" DYLD_INSERT_LIBRARIES="$MOUNT/run/loopback_bind.dylib" \
  python3 "$REPO/x/eden" --mount branchmap --mount goo-inspector --port "$BRANCHMAP_PORT"
