# Goo components

A small component library implemented with the current Grove/Goo contracts.
The components are published typed roles and views. Goo prepares their geometry,
text, and paint; the existing browser host owns drafts and admitted interactions.

## Run the gallery

From the repository root:

```sh
python3 x/eden --mount goo-components --compiler none --ephemeral --port 8144
```

Open [the component gallery](http://127.0.0.1:8144/goo-components). The gallery's
editing examples save to its sample records. `--ephemeral` gives this invocation
a disposable world. Omit it or choose `--world PATH` when persistence is wanted.

The gallery stylesheet controls its navigation and surrounding page only.
Component appearance comes from the existing pinned Mash/Goo profile. Resize
the window to request a new prepared layout. There is no component JavaScript
or second client layout engine in this mount.

## Components

All public presentation slots below begin `/sys/slot/components/`.
Roles and data fields are published under `/<node>/gov/goo_components/`.

| Slot | Required role | Meaning |
| --- | --- | --- |
| `heading` | `copy` | Title text |
| `paragraph` | `copy` | Wrapping body text |
| `caption` | `copy` | Supporting text |
| `code` | `copy` | Monospaced source display |
| `badge` | `copy` | Compact descriptive label |
| `status` | `copy` | Descriptive status and marker |
| `metadata` | `labelled` | Label and value |
| `identity` | `person` | Initials, name, caption |
| `card` | `article` | Shared header and body |
| `compact_card` | `article` | Smaller projection of the same record |
| `empty_state` | `article` | Title and explanatory body |
| `rich_text` | `rich_copy` | Structured text runs and label |
| `text_field` | `labelled` | Plain input with an ordinary Save action |
| `rich_editor` | `rich_copy` | Rich input with a typed Save action |
| `image` | `figure_content` | Namespace-backed image with contextual alt text |
| `figure` | `figure_content` | Image and caption from the same record |

`card_header` is also published for composing article views. Rich editors expose
the standard `text_toolbar` and `text_commands` slots for the browser adapter.
The toolbar changes local formatting; only Save invokes a domain action.

## Use the library

Add `goo-components` to a mount's dependencies. Supply records using the
library's published field slots. For example, at node `0x11`:

```text
#import component_title="/0x11/gov/goo_components/title"
#import component_body="/0x11/gov/goo_components/body"
#import component_caption="/0x11/gov/goo_components/caption"

"/welcome" =
  @tree
  component_title: "Welcome"
  component_body: "A shared article component presenting application content."
  component_caption: "Getting started"
```

Request that record through `/goo/render` with
`slot=/sys/slot/components/card`, or use that slot in a list/follower. Supply the
usual target and render context. The standard role matching and admission checks
still apply. `compact_card` uses the same record and field identities.

Within this publication, composition uses the existing `present` constructor:

```text
item => col('/sys/containers/card) {
  present(item, '/sys/slot/components/card_header)
  text(item.body, '/sys/slot/content)
}
```

Current `present` expansion searches the current Grove compilation unit; adding
a dependency does not enable cross-publication inline expansion. Other mounts
can select the published recipes through ordinary Goo presentation boundaries.
No new import syntax or arbitrary child callback mechanism is introduced here.

The role contracts are:

| Role | Fields |
| --- | --- |
| `copy` | `value: text` |
| `labelled` | `label: text`, `value: text` |
| `article` | `title: text`, `body: text`, `caption: text` |
| `person` | `initials: text`, `title: text`, `caption: text` |
| `rich_copy` | `label: text`, `rich_value: rich_type` |
| `figure_content` | `image_source: text`, `image_width: image_dimension`, `image_height: image_dimension`, `alt_text: text`, `caption: text` |

`rich_type` decodes the current `goo/text` contract. Font, modifier, and link
metadata remain structured through rich saves. Plain text fields edit only
`value`; rich editors edit only `rich_value`. The component does not manufacture
an action receiver or bypass the published action contract.

## Images

The supplied sculpture photo is included as `sculpture.jpg`, unchanged at
382 by 382 pixels. Its SHA-256 is
`c9980a80f65c430e1f305c455bef4c2408b4727d8dfb60d7e1e84b01ae3b2910`.
Mount publication captures its bytes in `/<node>/io/fs/$goo-components`, in the
`/sys/fs/source/assets` bundle. The declared `/goo-components/sculpture.jpg`
asset URL serves those published namespace bytes with `image/jpeg`.

`/<node>/app/goo_components/photo` holds the occurrence's `image_source` URL,
`image_width`, `image_height`, `alt_text`, and `caption`. Image and Figure reuse
that record. This photo's dimensions are 382 by 382. Alt text is bound
at render time and supplied to both Goo's image semantics and the HTML `alt`:

```text
item => image(item.image_source, "media", label = item.alt_text, width = item.image_width, height = item.image_height)
```

Named image options follow the source and slot, in any order. `label` must be
text. `width` and `height` must be supplied together as positive integers, either
literals or receiver fields. Missing, invalid, duplicate, and unknown options
are rejected. Existing one- and two-argument image recipes remain supported.

The dimensions describe the original image, not a fixed display size. Goo
prepares the media height as allocated width divided by source aspect ratio,
so the full image keeps its proportions at desktop and narrow widths. The
prepared geometry is shared by HTML and native consumers. The optional
`aspectRatio` config is also available to literal Goo recipes; images without
it retain the existing profile sizing, and avatars retain their fixed shape.
The gallery's **Open full image** link still opens the original asset.

This first slice uses a published asset URL and supplied dimension metadata.
General image upload, automatic dimension discovery, and arbitrary namespace
image-path resolution are not implemented by this mount.

## Boundaries

This library uses ASCII text and the existing pinned font repertoire. Rich
editing supports the current inline styles and references; it is not a nested
document editor. Links are descriptive metadata. Card headers are named
presentations, not a new general Slot compatibility system. There is no Foundry
cascade, arbitrary inline object support, dynamic progress-value recipe, or
new semantic identity protocol in this change.

These recipes use the portable Goo preparation contract. The gallery and save
flows have been verified in Chromium; the separate egui application's gallery
integration has not been exercised.

## Verification

```sh
WISP=/path/to/wisp python3 extras/x/check --mount goo-components --contracts-only
WISP=/path/to/wisp python3 extras/mounts/goo-components/check-views.py
python3 extras/mounts/goo-components/host.py http://127.0.0.1:8144
node extras/mounts/goo-components/check-browser.mjs \
  http://127.0.0.1:8144 /path/to/mash /tmp/goo-components-browser
```

`check-views.py` parses the actual Grove sources and compiles every component and
supporting view, including nested `present` composition, in a disposable fixture.
`host.py` is also registered as the mount's `x/eden --check` hook. It checks all
16 components at three width/scale/direction contexts, controls, rich metadata,
image semantics and proportions, exact original image bytes, and rejected catalog requests.
The browser check exercises image decoding, alt text, preserved aspect ratio, both save flows,
rejection of unsupported plain text before mutation, selection formatting and
undo, reload, draft retention on resize, reference preservation, and a narrow
layout.
