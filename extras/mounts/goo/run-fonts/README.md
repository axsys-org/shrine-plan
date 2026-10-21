# Run-style font extension

These fixed ASCII faces extend the pinned base profile without changing its
existing assets or revision. `fonts.json` records source/output SHA-256 hashes,
metrics, weights and styles. Sources are the vendored Inter Italic and Roboto
Mono variable fonts in `../fonts/`, under their included SIL OFL licenses.

Regenerate using Python with `fonttools==4.66.0`:

```sh
python extras/mounts/goo/scripts/generate-run-fonts.py
```

The generator verifies source hashes against the base profile's source metadata.
The same generated TTFs are copied into explorer static assets and egui assets;
consumers pin their hashes. Styled displays require display version 2.
