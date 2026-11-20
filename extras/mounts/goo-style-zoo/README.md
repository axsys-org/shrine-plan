# Goo style zoo

The Theme page edits shared rules. Four linked specimen sheets show the shared Goo profile in the browser workspace, egui, and UIKit. The Composition sheet combines an avatar, badge, quote, numeric value, progress bar and bound caption editor. Save a new caption to see the server reread it in the quote face. Type sets one phrase in six slots. Runs sets the same attributed text in two base roles, with a working link to Paint. Paint shows the profile’s media, status, button and progress treatments.

From the Reaver checkout, boot a disposable world:

```sh
python3 x/eden --mount goo-style-zoo --port 18480
```

Open [the zoo](http://127.0.0.1:18480/style-zoo). To use the egui inspector, run the following from the shrine-egui checkout:

```sh
GOO_SERVER=http://127.0.0.1:18480 GOO_ENDPOINT=/style-zoo GOO_PATH=/0x11/app/goo_theme/button \
  ./scripts/cargo-macos.sh run -- --explorer
```

Open **Theme** and choose **Button**, **All text**, a text role, **Code**, or **Input**. Dragging edits a private draft of that rule. The Reading room and Print desk previews are separate Goo views; the controls in the editor also inherit matching rules. **Publish theme** writes the selected rule to the world. Refresh another open view to see the result. For example, Button changes both the Composition sheet’s Save caption action and the Paint sheet’s button samples. Use **Default** and publish to remove a property from the rule.

For an override on just one sheet, right-click the Composition title, the title specimen on Type, the body sample on Runs, or the default button on Paint. Choose **Override this specimen**. The adjacent button opens the same workbench from the keyboard. Inside the workbench, right-click **Style workbench** and choose **Edit workbench heading** to edit the editor itself.

Drag the sliders for horizontal and vertical padding (0–96 CSS pixels per side), stroke width (0–12), and corner radius (0–48). Click the stroke or fill swatch to open the opaque RGB picker. Editing a value turns off **Default**; check it again to inherit the profile. Reaver remeasures and paints the private draft before you save. **Save design** writes the current sheet record. **Discard draft** restores the last read values. Use `--world DIR` on the Eden command to retain records across backend restarts.

Grove binds a typed style with `style = page.plate`. A `context-menu` group offers its presented local recipe buttons on secondary click. The workbench is an ordinary published view with six inputs, a bound save action, and a `draft-preview` group. Its receiver record registers which six slots can project a style for that declaration. A preview reads the snapshot, applies the validated values to an in-memory copy, and runs the same preparation as a saved render. Each sheet has independent style values for its specimen and its workbench heading.

Other components still open **Inspect Goo**. The inspector shows the received protobuf preview when inspecting an active draft. Save and refresh with pipeline capture enabled to see the stored override in the source and semantic stages. Enable **Capture pipeline** and refresh the workspace to compare the compilation stages with the painted result. UIKit accepts the same server, endpoint and initial location under **Open routed workspace**.

The Grove views are in [main.grove](main.grove). The seed records, typed run descriptors and route links are in [specimens.foil](specimens.foil). The `sheet(page)` route accepts records under the two `receiver.routeRoots` in [mount.json](mount.json): `app/goo_theme` and `app/style_zoo`. For example the native reader can navigate to `/style-zoo/sheet?page=/0x11/app/style_zoo/runs`. A workspace that omits `routeRoots` keeps its initial record as the sole route prefix.

With the zoo running, `python3 extras/mounts/goo-style-zoo/check-prepared.py` checks the effective type roles, link highlights, button treatments and progress values at 350 and 900 CSS pixels. In Grove, use a native slot literal such as `"quote"` for profile roles without a registered namespace alias.

Theme rules are records under `/<world>/app/goo_theme`. They override the pinned Mash profile at preparation time; publishing does not rewrite profile assets or change the font identity. Each property resolves independently: base profile → shared kind → shared text role → explicit node style. The shared editor supports per-side horizontal and vertical padding, solid fill, stroke width/color, and corner radius. Fonts, foreground ink, container layout, and native host chrome are outside this editor. No broadcast is needed for new preparations; already painted views keep their snapshot until a refresh.
