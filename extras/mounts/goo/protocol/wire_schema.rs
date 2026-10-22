// Generated from goo.proto by protocol/generate.py.
use super::{Field, Kind, Mode, Schema};
pub static RESPONSE: Schema = Schema { name: "Response", fields: &[
    Field { name: "wire_version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "presentation", tag: 2, kind: Kind::Message(&PRESENTATION), mode: Mode::Optional },
    Field { name: "bundle", tag: 3, kind: Kind::Message(&LAYOUTBUNDLE), mode: Mode::Optional },
    Field { name: "source", tag: 4, kind: Kind::Message(&SOURCE), mode: Mode::Optional },
    Field { name: "snapshot", tag: 5, kind: Kind::Message(&SNAPSHOT), mode: Mode::Optional },
    Field { name: "receipt", tag: 6, kind: Kind::Message(&OPERATIONRECEIPT), mode: Mode::Optional },
    Field { name: "failure", tag: 7, kind: Kind::Message(&FAILURE), mode: Mode::Optional },
] };
pub static PROFILE: Schema = Schema { name: "Profile", fields: &[
    Field { name: "id", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "version", tag: 2, kind: Kind::U32, mode: Mode::Required },
    Field { name: "revision", tag: 3, kind: Kind::String, mode: Mode::Required },
] };
pub static CONTEXT: Schema = Schema { name: "Context", fields: &[
    Field { name: "width", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "textScale", tag: 2, kind: Kind::Double, mode: Mode::Required },
    Field { name: "direction", tag: 3, kind: Kind::String, mode: Mode::Required },
] };
pub static BOX: Schema = Schema { name: "Box", fields: &[
    Field { name: "x", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "y", tag: 2, kind: Kind::Double, mode: Mode::Required },
    Field { name: "width", tag: 3, kind: Kind::Double, mode: Mode::Required },
    Field { name: "height", tag: 4, kind: Kind::Double, mode: Mode::Required },
] };
pub static ORIGIN: Schema = Schema { name: "Origin", fields: &[
    Field { name: "line", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "column", tag: 2, kind: Kind::U32, mode: Mode::Required },
] };
pub static TEXTSTYLE: Schema = Schema { name: "TextStyle", fields: &[
    Field { name: "fontId", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "fontSHA256", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "family", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "weight", tag: 4, kind: Kind::U32, mode: Mode::Required },
    Field { name: "style", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "fontSize", tag: 6, kind: Kind::Double, mode: Mode::Required },
    Field { name: "lineHeight", tag: 7, kind: Kind::Double, mode: Mode::Required },
    Field { name: "letterSpacing", tag: 8, kind: Kind::Double, mode: Mode::Required },
    Field { name: "insetX", tag: 9, kind: Kind::Double, mode: Mode::Required },
    Field { name: "insetY", tag: 10, kind: Kind::Double, mode: Mode::Required },
    Field { name: "kerning", tag: 11, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "ligatures", tag: 12, kind: Kind::Bool, mode: Mode::Required },
] };
pub static MYTH: Schema = Schema { name: "Myth", fields: &[
    Field { name: "entries", tag: 1, kind: Kind::Message(&MYTHENTRY), mode: Mode::Repeated },
] };
pub static MYTHENTRY: Schema = Schema { name: "MythEntry", fields: &[
    Field { name: "path", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "pail", tag: 2, kind: Kind::Message(&PAIL), mode: Mode::Required },
] };
pub static PAIL: Schema = Schema { name: "Pail", fields: &[
    Field { name: "nat", tag: 1, kind: Kind::String, mode: Mode::Optional },
    Field { name: "boolean", tag: 2, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "text", tag: 3, kind: Kind::String, mode: Mode::Optional },
    Field { name: "path", tag: 4, kind: Kind::String, mode: Mode::Optional },
    Field { name: "modifiers", tag: 5, kind: Kind::Message(&MODIFIERS), mode: Mode::Optional },
    Field { name: "weblink", tag: 6, kind: Kind::String, mode: Mode::Optional },
    Field { name: "unsupportedBrand", tag: 7, kind: Kind::String, mode: Mode::Optional },
] };
pub static MODIFIERS: Schema = Schema { name: "Modifiers", fields: &[
    Field { name: "values", tag: 1, kind: Kind::String, mode: Mode::Repeated },
] };
pub static ENGLISH: Schema = Schema { name: "English", fields: &[
    Field { name: "txt", tag: 1, kind: Kind::String, mode: Mode::Required },
] };
pub static LANGUAGE: Schema = Schema { name: "Language", fields: &[
    Field { name: "en", tag: 1, kind: Kind::Message(&ENGLISH), mode: Mode::Required },
] };
pub static TEXTRUN: Schema = Schema { name: "TextRun", fields: &[
    Field { name: "myth", tag: 1, kind: Kind::Message(&MYTH), mode: Mode::Required },
    Field { name: "lang", tag: 2, kind: Kind::Message(&LANGUAGE), mode: Mode::Required },
] };
pub static TEXTRUNS: Schema = Schema { name: "TextRuns", fields: &[
    Field { name: "values", tag: 1, kind: Kind::Message(&TEXTRUN), mode: Mode::Repeated },
] };
pub static LINK: Schema = Schema { name: "Link", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "path", tag: 2, kind: Kind::String, mode: Mode::Optional },
    Field { name: "href", tag: 3, kind: Kind::String, mode: Mode::Optional },
] };
pub static RUNSEMANTICS: Schema = Schema { name: "RunSemantics", fields: &[
    Field { name: "role", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "target", tag: 2, kind: Kind::Message(&LINK), mode: Mode::Optional },
] };
pub static HIGHLIGHT: Schema = Schema { name: "Highlight", fields: &[
    Field { name: "fill", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "stroke", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "width", tag: 3, kind: Kind::Double, mode: Mode::Required },
    Field { name: "radius", tag: 4, kind: Kind::Double, mode: Mode::Required },
] };
pub static UNDERLINE: Schema = Schema { name: "Underline", fields: &[
    Field { name: "color", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "width", tag: 2, kind: Kind::Double, mode: Mode::Required },
    Field { name: "y", tag: 3, kind: Kind::Double, mode: Mode::Required },
] };
pub static RESOLVEDRUN: Schema = Schema { name: "ResolvedRun", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "textStyle", tag: 2, kind: Kind::Message(&TEXTSTYLE), mode: Mode::Required },
    Field { name: "foreground", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "highlight", tag: 4, kind: Kind::Message(&HIGHLIGHT), mode: Mode::Optional },
    Field { name: "underline", tag: 5, kind: Kind::Message(&UNDERLINE), mode: Mode::Optional },
    Field { name: "semantics", tag: 6, kind: Kind::Message(&RUNSEMANTICS), mode: Mode::Required },
] };
pub static RUNFRAGMENT: Schema = Schema { name: "RunFragment", fields: &[
    Field { name: "myth", tag: 1, kind: Kind::Message(&MYTH), mode: Mode::Required },
    Field { name: "lang", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "text", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "box", tag: 4, kind: Kind::Message(&BOX), mode: Mode::Required },
    Field { name: "textX", tag: 5, kind: Kind::Double, mode: Mode::Required },
    Field { name: "baseline", tag: 6, kind: Kind::Double, mode: Mode::Required },
    Field { name: "resolved", tag: 7, kind: Kind::Message(&RESOLVEDRUN), mode: Mode::Optional },
] };
pub static RUNFRAGMENTS: Schema = Schema { name: "RunFragments", fields: &[
    Field { name: "values", tag: 1, kind: Kind::Message(&RUNFRAGMENT), mode: Mode::Repeated },
] };
pub static LINE: Schema = Schema { name: "Line", fields: &[
    Field { name: "text", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "box", tag: 2, kind: Kind::Message(&BOX), mode: Mode::Required },
    Field { name: "textX", tag: 3, kind: Kind::Double, mode: Mode::Required },
    Field { name: "baseline", tag: 4, kind: Kind::Double, mode: Mode::Required },
    Field { name: "prefixAdvance", tag: 5, kind: Kind::Double, mode: Mode::Required },
    Field { name: "runs", tag: 6, kind: Kind::Message(&RUNFRAGMENTS), mode: Mode::Optional },
] };
pub static EDITSTYLE: Schema = Schema { name: "EditStyle", fields: &[
    Field { name: "myth", tag: 1, kind: Kind::Message(&MYTH), mode: Mode::Required },
    Field { name: "resolved", tag: 2, kind: Kind::Message(&RESOLVEDRUN), mode: Mode::Required },
] };
pub static EDITING: Schema = Schema { name: "Editing", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "encoding", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "maxBytes", tag: 3, kind: Kind::U32, mode: Mode::Required },
    Field { name: "styles", tag: 4, kind: Kind::Message(&EDITSTYLE), mode: Mode::Repeated },
    Field { name: "linkStyle", tag: 5, kind: Kind::Message(&RESOLVEDRUN), mode: Mode::Required },
] };
pub static GRADIENTSTOP: Schema = Schema { name: "GradientStop", fields: &[
    Field { name: "offset", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "color", tag: 2, kind: Kind::String, mode: Mode::Required },
] };
pub static BACKGROUND: Schema = Schema { name: "Background", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "color", tag: 2, kind: Kind::String, mode: Mode::Optional },
    Field { name: "angleDegrees", tag: 3, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "stops", tag: 4, kind: Kind::Message(&GRADIENTSTOP), mode: Mode::Repeated },
] };
pub static BORDER: Schema = Schema { name: "Border", fields: &[
    Field { name: "width", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "color", tag: 2, kind: Kind::String, mode: Mode::Required },
] };
pub static CORNERS: Schema = Schema { name: "Corners", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "radius", tag: 2, kind: Kind::Double, mode: Mode::Optional },
] };
pub static OUTLINE: Schema = Schema { name: "Outline", fields: &[
    Field { name: "width", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "color", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "offset", tag: 3, kind: Kind::Double, mode: Mode::Required },
] };
pub static STATES: Schema = Schema { name: "States", fields: &[
    Field { name: "highlight", tag: 1, kind: Kind::Message(&OUTLINE), mode: Mode::Optional },
    Field { name: "focus", tag: 2, kind: Kind::Message(&OUTLINE), mode: Mode::Optional },
] };
pub static MARKER: Schema = Schema { name: "Marker", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "color", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "diameter", tag: 3, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "insetX", tag: 4, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "insetY", tag: 5, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "size", tag: 6, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "gap", tag: 7, kind: Kind::Double, mode: Mode::Optional },
] };
pub static IMAGEPAINT: Schema = Schema { name: "ImagePaint", fields: &[
    Field { name: "fit", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "rendering", tag: 2, kind: Kind::String, mode: Mode::Optional },
    Field { name: "clipToCorners", tag: 3, kind: Kind::Bool, mode: Mode::Optional },
] };
pub static PAINT: Schema = Schema { name: "Paint", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "units", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "colorSpace", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "foreground", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "background", tag: 5, kind: Kind::Message(&BACKGROUND), mode: Mode::Required },
    Field { name: "border", tag: 6, kind: Kind::Message(&BORDER), mode: Mode::Required },
    Field { name: "corners", tag: 7, kind: Kind::Message(&CORNERS), mode: Mode::Required },
    Field { name: "clip", tag: 8, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "states", tag: 9, kind: Kind::Message(&STATES), mode: Mode::Required },
    Field { name: "marker", tag: 10, kind: Kind::Message(&MARKER), mode: Mode::Optional },
    Field { name: "image", tag: 11, kind: Kind::Message(&IMAGEPAINT), mode: Mode::Optional },
] };
pub static RANGE: Schema = Schema { name: "Range", fields: &[
    Field { name: "minimum", tag: 1, kind: Kind::Double, mode: Mode::Required },
    Field { name: "maximum", tag: 2, kind: Kind::Double, mode: Mode::Required },
    Field { name: "value", tag: 3, kind: Kind::Double, mode: Mode::Required },
] };
pub static SEMANTICS: Schema = Schema { name: "Semantics", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "role", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "label", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "value", tag: 4, kind: Kind::String, mode: Mode::Optional },
    Field { name: "editable", tag: 5, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "multiline", tag: 6, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "range", tag: 7, kind: Kind::Message(&RANGE), mode: Mode::Optional },
] };
pub static CONFIG: Schema = Schema { name: "Config", fields: &[
    Field { name: "grow", tag: 1, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "maxIdeal", tag: 2, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "primary", tag: 3, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "toggle", tag: 4, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "label", tag: 5, kind: Kind::String, mode: Mode::Optional },
    Field { name: "optionLabel", tag: 6, kind: Kind::String, mode: Mode::Optional },
    Field { name: "value", tag: 7, kind: Kind::Double, mode: Mode::Optional },
    Field { name: "max", tag: 8, kind: Kind::Double, mode: Mode::Optional },
] };
pub static NODE: Schema = Schema { name: "Node", fields: &[
    Field { name: "id", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "parentId", tag: 2, kind: Kind::String, mode: Mode::Optional },
    Field { name: "kind", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "role", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "slot", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "payload", tag: 6, kind: Kind::String, mode: Mode::Required },
    Field { name: "box", tag: 7, kind: Kind::Message(&BOX), mode: Mode::Required },
    Field { name: "textStyle", tag: 8, kind: Kind::Message(&TEXTSTYLE), mode: Mode::Required },
    Field { name: "lines", tag: 9, kind: Kind::Message(&LINE), mode: Mode::Repeated },
    Field { name: "paint", tag: 10, kind: Kind::Message(&PAINT), mode: Mode::Required },
    Field { name: "semantics", tag: 11, kind: Kind::Message(&SEMANTICS), mode: Mode::Required },
    Field { name: "config", tag: 12, kind: Kind::Message(&CONFIG), mode: Mode::Required },
    Field { name: "textRuns", tag: 13, kind: Kind::Message(&TEXTRUNS), mode: Mode::Optional },
    Field { name: "editing", tag: 14, kind: Kind::Message(&EDITING), mode: Mode::Optional },
    Field { name: "src", tag: 15, kind: Kind::String, mode: Mode::Optional },
] };
pub static DISPLAY: Schema = Schema { name: "Display", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "profile", tag: 2, kind: Kind::Message(&PROFILE), mode: Mode::Required },
    Field { name: "context", tag: 3, kind: Kind::Message(&CONTEXT), mode: Mode::Required },
    Field { name: "coordinates", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "width", tag: 5, kind: Kind::Double, mode: Mode::Required },
    Field { name: "height", tag: 6, kind: Kind::Double, mode: Mode::Required },
    Field { name: "nodes", tag: 7, kind: Kind::Message(&NODE), mode: Mode::Repeated },
] };
pub static SNAPSHOT: Schema = Schema { name: "Snapshot", fields: &[
    Field { name: "life", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "subject", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "target", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "expected", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "displayed", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "publication", tag: 6, kind: Kind::String, mode: Mode::Required },
    Field { name: "projectionSeq", tag: 7, kind: Kind::U64, mode: Mode::Optional },
    Field { name: "coveredOperationIds", tag: 8, kind: Kind::String, mode: Mode::Repeated },
    Field { name: "recipePublication", tag: 9, kind: Kind::String, mode: Mode::Optional },
] };
pub static CAPTURE: Schema = Schema { name: "Capture", fields: &[
    Field { name: "slot", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "selection", tag: 2, kind: Kind::String, mode: Mode::Required },
] };
pub static BINDING: Schema = Schema { name: "Binding", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "kind", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "nodeId", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "route", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "slot", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "captures", tag: 6, kind: Kind::Message(&CAPTURE), mode: Mode::Repeated },
    Field { name: "presented", tag: 7, kind: Kind::Bool, mode: Mode::Required },
] };
pub static CONTROL: Schema = Schema { name: "Control", fields: &[
    Field { name: "id", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "kind", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "control", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "slot", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "invoke", tag: 5, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "become", tag: 6, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "captures", tag: 7, kind: Kind::Message(&CAPTURE), mode: Mode::Repeated },
    Field { name: "binding", tag: 8, kind: Kind::Message(&BINDING), mode: Mode::Required },
] };
pub static NAVIGATION: Schema = Schema { name: "Navigation", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "sourceSlot", tag: 2, kind: Kind::String, mode: Mode::Required },
] };
pub static OPERATION: Schema = Schema { name: "Operation", fields: &[
    Field { name: "key", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "kind", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "source", tag: 3, kind: Kind::String, mode: Mode::Required },
] };
pub static HOST: Schema = Schema { name: "Host", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "kind", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "declaration", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "navigation", tag: 4, kind: Kind::Message(&NAVIGATION), mode: Mode::Required },
    Field { name: "operations", tag: 5, kind: Kind::Message(&OPERATION), mode: Mode::Repeated },
] };
pub static PANE: Schema = Schema { name: "Pane", fields: &[
    Field { name: "kind", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "renderer", tag: 2, kind: Kind::String, mode: Mode::Optional },
    Field { name: "topology", tag: 3, kind: Kind::String, mode: Mode::Optional },
    Field { name: "axis", tag: 4, kind: Kind::String, mode: Mode::Optional },
    Field { name: "key", tag: 5, kind: Kind::String, mode: Mode::Optional },
    Field { name: "source", tag: 6, kind: Kind::String, mode: Mode::Optional },
    Field { name: "selection", tag: 7, kind: Kind::String, mode: Mode::Optional },
    Field { name: "label", tag: 8, kind: Kind::String, mode: Mode::Optional },
    Field { name: "mode", tag: 9, kind: Kind::String, mode: Mode::Optional },
    Field { name: "browse", tag: 10, kind: Kind::String, mode: Mode::Optional },
    Field { name: "operation", tag: 11, kind: Kind::String, mode: Mode::Optional },
    Field { name: "slot", tag: 12, kind: Kind::String, mode: Mode::Optional },
    Field { name: "initial", tag: 13, kind: Kind::String, mode: Mode::Optional },
    Field { name: "children", tag: 14, kind: Kind::Message(&PANE), mode: Mode::Repeated },
    Field { name: "node", tag: 15, kind: Kind::String, mode: Mode::Optional },
    Field { name: "profile", tag: 16, kind: Kind::Message(&PROFILE), mode: Mode::Optional },
    Field { name: "context", tag: 17, kind: Kind::Message(&CONTEXT), mode: Mode::Optional },
    Field { name: "display", tag: 18, kind: Kind::Message(&DISPLAY), mode: Mode::Optional },
    Field { name: "controls", tag: 19, kind: Kind::Message(&CONTROL), mode: Mode::Repeated },
    Field { name: "html", tag: 20, kind: Kind::String, mode: Mode::Optional },
] };
pub static DESCRIPTION: Schema = Schema { name: "Description", fields: &[
    Field { name: "values", tag: 1, kind: Kind::Message(&PANE), mode: Mode::Repeated },
] };
pub static PRESENTATION: Schema = Schema { name: "Presentation", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "ok", tag: 2, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "profile", tag: 3, kind: Kind::Message(&PROFILE), mode: Mode::Required },
    Field { name: "context", tag: 4, kind: Kind::Message(&CONTEXT), mode: Mode::Required },
    Field { name: "snapshot", tag: 5, kind: Kind::Message(&SNAPSHOT), mode: Mode::Optional },
    Field { name: "view", tag: 6, kind: Kind::String, mode: Mode::Optional },
    Field { name: "kind", tag: 7, kind: Kind::String, mode: Mode::Required },
    Field { name: "display", tag: 8, kind: Kind::Message(&DISPLAY), mode: Mode::Optional },
    Field { name: "controls", tag: 9, kind: Kind::Message(&CONTROL), mode: Mode::Repeated },
    Field { name: "description", tag: 10, kind: Kind::Message(&DESCRIPTION), mode: Mode::Optional },
    Field { name: "host", tag: 11, kind: Kind::Message(&HOST), mode: Mode::Optional },
    Field { name: "slot", tag: 12, kind: Kind::String, mode: Mode::Optional },
    Field { name: "role", tag: 13, kind: Kind::String, mode: Mode::Optional },
    Field { name: "origin", tag: 14, kind: Kind::Message(&ORIGIN), mode: Mode::Optional },
    Field { name: "html", tag: 15, kind: Kind::String, mode: Mode::Optional },
    Field { name: "node", tag: 16, kind: Kind::String, mode: Mode::Optional },
    Field { name: "readOnlyDisplay", tag: 17, kind: Kind::Message(&DISPLAY), mode: Mode::Optional },
] };
pub static LAYOUT: Schema = Schema { name: "Layout", fields: &[
    Field { name: "size", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "render", tag: 2, kind: Kind::Message(&PRESENTATION), mode: Mode::Required },
] };
pub static LAYOUTBUNDLE: Schema = Schema { name: "LayoutBundle", fields: &[
    Field { name: "version", tag: 1, kind: Kind::U32, mode: Mode::Required },
    Field { name: "ok", tag: 2, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "layoutPolicy", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "context", tag: 4, kind: Kind::Message(&CONTEXT), mode: Mode::Required },
    Field { name: "layouts", tag: 5, kind: Kind::Message(&LAYOUT), mode: Mode::Repeated },
] };
pub static MEMBER: Schema = Schema { name: "Member", fields: &[
    Field { name: "key", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "subject", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "source", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "sourceLife", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "life", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "type", tag: 6, kind: Kind::String, mode: Mode::Required },
    Field { name: "expected", tag: 7, kind: Kind::String, mode: Mode::Required },
    Field { name: "status", tag: 8, kind: Kind::String, mode: Mode::Required },
    Field { name: "axis", tag: 9, kind: Kind::String, mode: Mode::Required },
    Field { name: "face", tag: 10, kind: Kind::String, mode: Mode::Optional },
    Field { name: "topology", tag: 11, kind: Kind::String, mode: Mode::Optional },
    Field { name: "parent", tag: 12, kind: Kind::String, mode: Mode::Optional },
    Field { name: "hasChildren", tag: 13, kind: Kind::Bool, mode: Mode::Optional },
] };
pub static PREPAREDMEMBER: Schema = Schema { name: "PreparedMember", fields: &[
    Field { name: "key", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "slot", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "bundle", tag: 3, kind: Kind::Message(&LAYOUTBUNDLE), mode: Mode::Required },
] };
pub static SOURCE: Schema = Schema { name: "Source", fields: &[
    Field { name: "id", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "life", tag: 2, kind: Kind::String, mode: Mode::Required },
    Field { name: "type", tag: 3, kind: Kind::String, mode: Mode::Required },
    Field { name: "axis", tag: 4, kind: Kind::String, mode: Mode::Required },
    Field { name: "topology", tag: 5, kind: Kind::String, mode: Mode::Required },
    Field { name: "bounded", tag: 6, kind: Kind::Bool, mode: Mode::Required },
    Field { name: "members", tag: 7, kind: Kind::Message(&MEMBER), mode: Mode::Repeated },
    Field { name: "incremental", tag: 8, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "epoch", tag: 9, kind: Kind::String, mode: Mode::Optional },
    Field { name: "parent", tag: 10, kind: Kind::String, mode: Mode::Optional },
    Field { name: "next", tag: 11, kind: Kind::String, mode: Mode::Optional },
    Field { name: "omitted", tag: 12, kind: Kind::U64, mode: Mode::Optional },
    Field { name: "presentations", tag: 13, kind: Kind::Message(&PREPAREDMEMBER), mode: Mode::Repeated },
] };
pub static OPERATIONRECEIPT: Schema = Schema { name: "OperationReceipt", fields: &[
    Field { name: "operationId", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "outcome", tag: 2, kind: Kind::String, mode: Mode::Required },
] };
pub static FAILURE: Schema = Schema { name: "Failure", fields: &[
    Field { name: "error", tag: 1, kind: Kind::String, mode: Mode::Required },
    Field { name: "ok", tag: 2, kind: Kind::Bool, mode: Mode::Optional },
    Field { name: "version", tag: 3, kind: Kind::U32, mode: Mode::Optional },
    Field { name: "code", tag: 4, kind: Kind::String, mode: Mode::Optional },
] };
