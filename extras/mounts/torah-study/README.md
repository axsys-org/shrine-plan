# Beit Midrash — Bava Metzia 21b

A single-sugya Goo mount for a three-minute chavruta. Open the Torah study page in a browser. The Gemara sits between two attributed readings; a student’s interpretations accumulate in a separate gilyon (margin). There is no runtime dependency on Sefaria or an external font.

```sh
cd /Users/test/dev/reaver
python3 x/eden --mount torah-study --port 8253
```

Open <http://127.0.0.1:8253/torah-study>. By default Eden boots a disposable world. For a notebook that resumes after restart, pass `--world /path/to/a/dedicated/world` on every boot.

## At the study table

1. **Read (0:00).** Click **יאוש שלא מדעת** in the central text. Open the kushya in the evidence slip. The question singles out those three words; the links to 21b:2 and 21b:4 let the pair test it against marked and unmarked finds.
2. **Distinguish (0:35).** Choose **Introduce a distinction**. Try “Knowing now / being certain later.” For the practical consequence, enter “An unmarked coin found before its owner notices”; for the boundary, “A marked vessel whose owner expects it back.” Record it. The margin assigns an ID such as D1.
3. **Compare (1:25).** Read A and B against the same lemma. Abaye requires actual awareness; Rava considers the predictable response to an unmarked loss. Neither premise is overwritten when the student chooses a side.
4. **Fork (2:00).** Enter the distinction ID and choose **Fork Rava**. The draft records its parent, premise, source reference, lemma, and distinction. Reload and choose **Resume a fork** to return to the same draft.
5. **Publish (2:30).** Write a thesis of your own, for example “Certainty is evidence of the owner’s likely response, but is not itself knowledge.” Choose **Publish alternative**. The margin now contains a numbered alternative, with links back to the distinction and the phrase. Reload to see the publication reread from Reaver. The same distinction can be used to fork Abaye next.

The Hebrew/Aramaic excerpt is from [Bava Metzia 21b:1](https://www.sefaria.org/Bava_Metzia.21b.1). The English is a fresh gloss. The dispute over the unmarked object is developed at [21b:4](https://www.sefaria.org/Bava_Metzia.21b.4); the marked-object boundary is at [21b:2](https://www.sefaria.org/Bava_Metzia.21b.2). The kushya, descriptions of assumptions, and student examples are editorial, not quotations from named commentators.

## Mount boundaries

- `main.grove` defines the notebook as a Goo selection/follower, ordinary views, recipe changes, native form controls, and bound actions. The browser folio is a Weft shell: native bidirectional text and selection for the passage, source links and a read-only projection of saved leaves. The shell neither authors invocations nor treats displayed links as write authority.
- `model.foil` owns stable lemma and reading IDs, append-only distinctions and editions, and one resumable fork per folio. Publishing adds a reading to this Reaver world, not an external service. Earlier leaves and the two source readings remain unchanged.
- One curated passage, two source readings. The browser offers the traditional evidence span; the native reader also supports arbitrary contiguous word ranges. There is no corpus importer, concurrent private notebook, or fork-of-a-fork editor. A created fork survives reload; text typed into an unsubmitted form is not a saved draft. The browser folio uses browser shaping. The native folio uses the pinned Hebrew Goo run font and prepared text geometry.

## Native egui

Boot this mount on port 8258, then run `GOO_SERVER=http://127.0.0.1:8258 GOO_ENDPOINT=/beit-midrash GOO_PATH=/0x11/app/torah_study/folio ./scripts/cargo-macos.sh run -- --explorer`
in the shrine-egui checkout. The native entry is `/beit-midrash`; its three
Goo followers are Study, Gemara and Gilyon. Drag over any words in the central Hebrew or English source and choose **Open a
kushya** on the selection overlay. The mount’s pure selection provider computes
standard gematria, per-word letter values and exact-range related questions.
`selection_menu` declares the popup as an ordinary Goo view. The composer freezes the quote; **Record
kushya** saves its versioned source path, half-open UTF-8 offsets, exact text
and question through Goo. Reaver checks the quote and both word boundaries
against the notebook manuscript. A cross-line range retains its logical newline,
and identical words at different positions remain distinct. Saved spans are
underlined; clicking a mark lists only the questions attached to that exact
range. The traditional
question, comparison and fork workflow are still available. Reading
evidence performs no domain write. The highlighted phrase, readings and margin
are prepared Goo views; the client does not read the HTML shell or the
browser’s JSON ledger. Supported Hebrew in this edition is unpointed.
The linked online source editions remain accessible from the browser folio.

## Linked-text experiment

The same mount also serves a native Goo workspace at `/torah-chunks`. Boot a fresh world as above, then run this from the shrine-egui checkout (use the port printed by Eden):

```sh
GOO_SERVER=http://127.0.0.1:8253 GOO_ENDPOINT=/torah-chunks GOO_PATH=/0x11/app/torah_chunks ./scripts/cargo-macos.sh run -- --explorer
```

Open **Bava Metzia 21b:1**. Drag across **יאוש שלא מדעת**. The popup lists the question anchored on those words and the independent essay citing them. Follow the question to its note, or choose **Write on these words** and save your own. Click **Library** to return to the two standalone tracts. Each chunk can also be opened directly by address.

To follow an exact citation, open **On later knowledge** and click the **Cites**
link under **Links from this text**. The reader reveals **יאוש שלא מדעת**.
**Back** returns to the essay at its previous scroll position. Use **Copy location**
and paste it into **Open address** in another egui session on the same server
and endpoint, or supply the copied URL as `GOO_PATH` at launch. A stale
citation displays its saved words as unresolved.

The source of truth is one namespace record per chunk. `/chunk/body` holds rich text and `/chunk/revision` identifies its edition. Relationship slots such as `/study/asks_about`, `/study/comments_on`, and `/study/cites` hold ordered destinations. A destination records a target address and revision, optionally with a half-open UTF-8 range and exact quotation. `/chunk/anchor` names the slot whose first destination places this chunk. Omitting the anchor makes it a tract, regardless of how many citations it has.

The library watches its subtree and derives incoming links from those forward declarations. The phrase preview filters by the complete destination. A missing or stale destination is shown as unresolved on the referring chunk, with its saved quotation. New notes get independent addresses under the library. Their addresses survive deletion of the text they annotate.

This experiment supports browsing and writing anchored notes in egui. Standalone tracts and other link semantics are seeded or authored as records. There is no interactive source editor or reattachment form.

## Verification

On a disposable world, the browser check creates a distinction containing Hebrew, forks Rava, reloads before publication, publishes, reloads again and compares the saved record to the captured draft. It expects exactly three Goo mutations. Run from Reaver with Mash's Playwright dependencies and Chromium installed:

```sh
node extras/mounts/torah-study/check-browser.mjs http://127.0.0.1:8253 /Users/test/dev/mash /tmp/torah-study-check
WISP=/path/to/wisp python3 extras/x/check --mount torah-study --jobs 4
```

For the native round trip, use a disposable notebook and run in shrine-egui:

```sh
GOO_SERVER=http://127.0.0.1:8258 GOO_DISPOSABLE=1 ./scripts/cargo-macos.sh test --test torah -- --ignored --test-threads=1
```


The chunk workspace exposes two native routes. Open
`/torah-chunks/read?chunk=/0x11/app/torah_chunks/essay` and click **Compare these texts**
beneath its citation. The comparison places the citing chunk on the left and its
source on the right. The same view opens directly at
`/torah-chunks/compare?left=/0x11/app/torah_chunks/essay&right=/0x11/app/torah_chunks/sugya`.
Both are declared in `chunks.grove`.
