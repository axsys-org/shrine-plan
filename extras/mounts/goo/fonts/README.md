# Pinned fonts

Source font files were retrieved from the Google Fonts repository on 2026-09-24:

- https://github.com/google/fonts/tree/main/ofl/inter
- https://github.com/google/fonts/tree/main/ofl/robotomono

The exact source SHA-256 hashes and generated font hashes are recorded in
`metrics.json`. Both families are licensed under SIL OFL 1.1; the original
copyright notices and full licenses are included alongside the source files.

`scripts/generate-fonts.py` (fonttools 4.66.0) instantiates fixed weights and
Inter optical size 14, removes layout features, and subsets to U+0020–U+007E.
It generates the bundled TTFs, @font-face declarations, and Haskell advances.
No installed system font or network service participates at runtime.

The web-facing families are `Goo Sans` and `Goo Mono`; quotes use Goo Sans italic.
The inspector can fall back for its own Unicode UI symbols; measured Goo content
accepts printable ASCII plus CR/LF/tab only. These controls normalize to explicit
lines and four-space tabs before painting. Browser kerning, ligatures, optical
size and synthetic faces are disabled for measured content.
