# Goo domain protobuf v2

`goo.proto` is the wire contract. `wire=protobuf-v2` selects it; omission selects
legacy JSON. The generic v1 Value/Object protocol is rejected. Requests remain
URL-encoded and invocation retry bodies remain frozen.

The response oneof carries Presentation, LayoutBundle, Source, Snapshot,
OperationReceipt, or Failure. Nested messages describe the actual prepared
contracts: display nodes and boxes, text lines/runs, resolved fonts and paint,
editing palettes, accessibility semantics, bindings and pane identities.
Geometry uses finite IEEE754 binary64 (`double`) in logical CSS pixels.
Version/lifetime/publication strings retain their domain's unbounded identity
representation. Myth entries carry an explicit branded pail union. Neither
metadata nor unknown fields grant action authority.

`generate.py` produces typed Foil records and BAT encoders in `wire.foil`, plus
Rust schema descriptors. It also generates adapters for existing JSON-returning
domain APIs. The main ordinary/native preparation path in `wire_prepared.foil`
reads actual preparation objects and scalar bits, with no intermediate JSON
display, decimal geometry, or HTML. Paint table and binding descriptor APIs are
still small JSON adapters. Pane and tree adapters currently use their existing
domain APIs before encoding named messages. BAT chunks are flattened only when
writing the HTTP response. `http_foot` preserves explicit lengths and final zero
bytes.

Rust visits borrowed protobuf fields directly into application models through
Serde. Presence, wire types, duplicate singular fields/oneof cases, UTF-8,
finite doubles, integer bounds, required fields, message depth and size are
checked before mounting. Semantic validators remain mandatory. Raw protobuf is
retained for inspection; an ordinary presentation's diagnostic JSON projection
is generated only when requested.

Compiler pipeline captures, patch packets, inspection captures and all-views
catalogs are not yet v2 messages. They retain their JSON endpoints; binary
pipeline/patch/inspection requests are explicitly rejected. Workspace bootstrap
uses JSON because it can contain patch contracts. There is no JSON blob or
generic Value escape hatch in this schema. Add their actual domain messages
before migrating those endpoints. A `/goo/render` read resolving to a patch
returns a typed HTTP 415 Failure with `code=json-contract`. The egui client may
repeat only that explicitly identified read in JSON. It does not downgrade
actions, receipts, unknown selectors or failed network requests.

Generate and verify:

```sh
python3 extras/mounts/goo/protocol/generate.py
protoc -I extras/mounts/goo/protocol --descriptor_set_out=/tmp/goo.pb \
  extras/mounts/goo/protocol/goo.proto
# Consumer goldens use the independent protoc encoder:
cd ../shrine-egui
python3 scripts/generate-protobuf-fixtures.py
./scripts/cargo-macos.sh test --test protobuf
```

Unknown protobuf fields are skipped; unsupported known contract versions are
rejected by model validation. Required-field additions need a wire-version
change. Never reuse field numbers. Failure on a successful action response is
an unknown outcome, not evidence that the action was rejected. Receipt storage
and exact invocation retries remain unchanged.
