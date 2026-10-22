#!/bin/sh
set -eu
MOUNT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$MOUNT/../../.." && pwd)
CLIENT=${GOO_EGUI_ROOT:-"$REPO/../goo-egui"}
if [ ! -f "$CLIENT/Cargo.toml" ]; then
  echo 'Set GOO_EGUI_ROOT to the goo-egui checkout (needed when Shrine is in a worktree).' >&2
  exit 1
fi
cd "$CLIENT"
export GOO_SERVER=${GOO_SERVER:-http://127.0.0.1:8190}
export GOO_TARGET=/0x11/app/branchmap/exchange
exec ./scripts/cargo-macos.sh run --locked -- --single
