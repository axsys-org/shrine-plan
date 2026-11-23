# Berakhot 2a fixture sources

This offline study is imported from Sefaria's text API. It includes the complete
14 base-text segments and 22 available Rashi/Tosafot glosses for those segments.
The original responses and exact SHA-256 hashes are kept beside this file in
`manifest.json`. No network access is required while reading or commenting.

| Text | Edition / attribution | License reported by Sefaria |
| --- | --- | --- |
| Base Hebrew/Aramaic | Wikisource Talmud Bavli, via Sefaria | CC-BY-SA |
| Base English | A. Cohen, *Tractate Berakot*, Cambridge University Press, 1921 | Public Domain |
| Rashi, Hebrew | Vilna Edition, via Sefaria | Public Domain |
| Rashi, English | Sefaria Community Translation | CC0 |
| Tosafot, Hebrew | Vilna Edition, via Sefaria | Public Domain |
| Tosafot, English | Jan Buckler, via Sefaria | CC-BY |

Source pages: [Berakhot 2a](https://www.sefaria.org/Berakhot.2a),
[Rashi](https://www.sefaria.org/Rashi_on_Berakhot.2a),
[Tosafot](https://www.sefaria.org/Tosafot_on_Berakhot.2a).
Consult the linked edition metadata for the applicable license terms; the
imported text retains those licenses. This is not an original translation.

`extras/shuin/generate-talmud.py` removes HTML markup, translator footnote markup,
and directional control characters, decodes HTML entities, and normalizes
whitespace. It preserves the imported wording. Offsets refer to these normalized
UTF-8 records. Imported glosses are anchored to their **source segment**, rather
than claiming reconstructed word-level catchwords. New personal glosses capture
the exact selected byte range. Some imported commentaries have no English
translation in the selected edition; their Hebrew remains available.

The UI abbreviates long glosses with an explicit “Read full gloss” control; full
text remains in the namespace. Generated `talmud.foil` is reproducible by running
`python3 extras/shuin/generate-talmud.py`.

Hebrew is rendered with the bundled OFL-licensed Frank Ruhl Libre font. Its license
and font manifest are maintained in the separate native client repository, at
`assets/fonts/frankruhllibre/OFL.txt` and the client font manifest.
