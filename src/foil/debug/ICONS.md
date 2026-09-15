# Debugger icons

The debugger uses **Mash's existing semantic icon registry only**.

`icons.js` maps application actions to stock names such as `object.document`,
`action.search`, `action.play`, `navigation.back`, and
`status.information`. Every icon is a normal `ui-icon` component. The Mash
bundle owns its source, sizing, theming, and license notices.

No JShrine assets, custom SVG paths, application icon registrations, external
fonts, or additional icon packs are imported. Unknown action aliases fail
explicitly rather than rendering a substitute.

`x/debug-icons-test.mjs` checks every alias against Mash's actual generated
semantic registry and verifies the shared component/accessibility contract.
