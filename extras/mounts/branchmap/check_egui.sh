#!/bin/sh
set -eu
MOUNT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$MOUNT/../../.." && pwd)
CLIENT=${GOO_EGUI_ROOT:-"$REPO/../goo-egui"}
(cd "$CLIENT" && ./scripts/cargo-macos.sh build --locked --lib)
mkdir -p "$MOUNT/run"
rustc --edition=2024 "$MOUNT/check_egui.rs" \
  -L "dependency=$CLIENT/target/debug/deps" \
  --extern "shrine_egui=$CLIENT/target/debug/libshrine_egui.rlib" \
  -o "$MOUNT/run/check-egui"
exec "$MOUNT/run/check-egui"
