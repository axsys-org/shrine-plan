#!/bin/sh
# Start a fresh, loopback-only MCP world using this checkout's pinned runtime.
set -eu
EXPERIMENT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$EXPERIMENT/../../.." && pwd)

if [ "$(uname -s)" != Darwin ]; then
  echo 'This launcher requires macOS for its process-local bind adapter.' >&2
  exit 1
fi
if [ "${_BRANCHMAP_ENV:-}" != "$REPO" ]; then
  if ! command -v nix >/dev/null 2>&1; then
    echo 'Put Nix on PATH before starting this experiment.' >&2
    exit 1
  fi
  exec nix --extra-experimental-features 'nix-command flakes' develop \
    --no-update-lock-file "$REPO#eden" --command \
    env _BRANCHMAP_ENV="$REPO" sh "$EXPERIMENT/start_world.sh"
fi
if lsof -nP -iTCP:8148 -sTCP:LISTEN >/dev/null 2>&1; then
  echo 'Port 8148 already has a listener. Inspect it before starting another world.' >&2
  exit 1
fi
RUNTIME=${WISP:-$(command -v wisp)}
if [ ! -x "$RUNTIME" ]; then
  echo 'WISP must name an executable runtime.' >&2
  exit 1
fi
mkdir -p "$EXPERIMENT/run"
clang -dynamiclib -o "$EXPERIMENT/run/loopback_bind.dylib" "$EXPERIMENT/loopback_bind.c"
# Listen takes only a port. Confine this process's port 8148 to loopback.
exec env _EDEN_NIX_ROOT="$REPO" WISP="$RUNTIME" \
  DYLD_INSERT_LIBRARIES="$EXPERIMENT/run/loopback_bind.dylib" \
  python3 "$REPO/x/eden" --mount mcp --port 8148
