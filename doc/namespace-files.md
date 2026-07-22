# Namespace files: first storage slice

File semantics live in Foil namespace values, not in the Reaver HTTP or native
host. This first slice uses two distinct branded pails:

- `file_format(media_type)` is a format definition with an explicit MIME type.
  A namespace can expose it in a record's `['format]` slot.
- `file_occurrence(format, content)` is one file occurrence. A namespace record
  exposes it in `['file]`; `format` is the branded `file_format` value and
  `content` is an inline byte atom.

`GET /api/file/<namespace-path>` asks the Foil responder to project the target
record. A valid occurrence returns its bytes with the format's MIME type. A
missing record returns 404; a present record without a valid `file_occurrence`
returns 422. The Reaver layer only maps the URL to a namespace path and carries
the status, content type, and body selected by Foil.

## Deliberate limitation and next slice

Inline atoms are sufficient for small files and preserve non-text bytes, but
they are not the long-term large-object store. The follow-up should add a
content-addressed blob reference as another branded namespace value, backed by
an explicitly authorized blob provider. That provider must verify the digest
and return bytes mechanically; namespace records must continue to own format,
occurrence, and reference semantics. This slice does not treat a host path as a
blob identity and does not grant the HTTP/native host ambient filesystem
authority.
