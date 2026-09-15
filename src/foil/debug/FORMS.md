# Authored debugger forms

`enhanceForms` sews server-rendered operation and Grove forms into Mash. It is
presentation-only; the native form, original controls and navigation module
retain validation, values, authorization checks, submission and commit handling.

- Preserve every input, label, form and hidden operation/source/version node.
  Do not clone values into replacement controls or introduce a proxy `ui-form`.
- Existing authored control sizes and form size contexts win. Otherwise the
  form supplies Mash's small context; controls opt into real coarse targets.
- A standalone `ui-input` with an authored nonempty `label` can acquire the
  existing `ui-field` wrapper. Configure the wrapper's required state before
  connecting it, because the field propagates required state to its control.
- Existing fields, groups, visible labels, slots and ARIA description/label
  associations are not reconstructed. A currently focused control is not
  structurally reparented; a later explicit enhancement can complete that work.
- Native single-line Grove inputs use `ui-input-group typography="code"`
  inside their existing label. Their native label and form ownership remain
  intact. Do not put a native-only group into `ui-field`: the current field
  protocol does not forward focus to a native descendant of a group.
- The application owns only form grouping, placement and authored lede layout.
  Mash owns the input surface, sizing, focus, invalid and disabled presentation.
  Native controls outside the supported group composition keep their fallback.

The safe browser contract lives in `x/debug-operation-ui-test.mjs`. It requires
a saved real shell, intercepts every request at an inert origin and fulfills
deliberate submissions as rejected fixtures. It does not exercise or mutate the
user's live namespace. Tests cover authored identity, required/disabled/readonly
states, labels, exact FormData, busy guards, draft/focus recovery and responsive
geometry. A green UI fixture test is not proof of a real backend commit.
