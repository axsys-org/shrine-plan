' Proposed namespace seed format; the loader/writer is not implemented yet.
' Rex syntax, with Foil data values. Load under a caller-supplied root, normally
' [state.self]. This file describes current records, without namespace history.
'
' - module: import constructors/types into the value-reading environment.
' + path: declare a record relative to the enclosing record, or the load root.
' = slot value: assign a literal slot path in that record; require a pail value.
' Slot keys never inherit the enclosing record path: theme is ['theme], while
' /sys/lede is ['sys 'lede]. Multi-segment slot keys remain single slot keys.
' + . denotes the enclosing/root record itself. Empty records are significant.
' ~/ inside a quoted path is a proposed extension: expand against the load root,
' even inside nested records. Ordinary quoted absolute paths stay absolute.
'
' Values use Foil literals, rows, and typed data constructors. The initial
' subset excludes function calls other than data constructors, live reads,
' lambdas, and evaluation against records being loaded. Resolve constructors
' against this build's definitions; do not write case suffixes into the file.

- lain_types

+ config/shuin
  = /sys/lede (pails/t "Shuin configuration")
  = theme (pails/t "light")
  = text_scale (pails/n 100)
  = start (pails/p '~/app/chat/general)

+ app/chat
  = /sys/lede (pails/t "Team chat")

  + general
    = /sys/lede (pails/t "General")
    = /sys/content (pails/t "A place for everyone.")

  + random
    = /sys/lede (pails/t "Random")

+ app/scratch

' Load contract:
' Parse the whole file with Rex, retaining spans for diagnostics. Expand record
' paths and root-relative path values, then validate every value before writes.
' Reject duplicate record declarations and duplicate slots within one file.
' An undeclared intermediate path is structural; it does not acquire a record.
' Forward path references are allowed because a path value does not read its
' target. Any target-existence requirement belongs to a separate schema check.
'
' The build supplies an ordered list of files. Later files override individual
' slots from earlier files. Omitted slots and records are retained; an empty
' record declaration ensures existence and does not clear an earlier record.
' Compose all files first, then install the resulting records atomically into
' the fresh build namespace after their types are published, before activation.
' A live loader should default to filling absent slots; overriding existing
' values is an explicit caller option. Reapplying equal values is a no-op.
' Namespace admission rules still apply; publish no candidate on any failure.
'
' Save contract:
' Export current live records under an explicitly selected root. Preserve
' empty records, slot keys, value types, and contents. Sort paths and slots by
' the namespace's canonical path ordering for stable output. Emit flattened
' record paths; nesting above is optional authoring sugar. Emit + . for the root.
' Use root-relative spelling for typed path values within the exported root;
' preserve external paths. Never rewrite strings just because they look like
' paths. Fully qualify constructor names in canonical output, without cases.
' Preserve constructor distinctions and generic arguments needed to read values.
' Pins need an explicit supported representation; never silently unwrap them.
' Fail with record/slot diagnostics for unsupported values, including code and
' closures. Do not use show/value: it clips text and hides runtime structure.
' Histories, tombstones, journal entries, and compiler artifacts are outside
' the intended configuration/data export. Select data roots explicitly.
' The round-trip promise is the same records and typed data under compatible
' definitions, with paths rebased to the destination root and fresh history.
