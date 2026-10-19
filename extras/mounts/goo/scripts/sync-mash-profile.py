#!/usr/bin/env python3
"""Vendor a verified Mash renderer profile and generate Goo's native constants.

An update requires --mash-root explicitly. --check is entirely repository-local;
it checks the complete vendored bundle, the Foil constants derived from it, and
the browser-facing profile links that serve that bundle over HTTP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENDOR = ROOT / "profile"


def canonical(value):
    """The bundle's sorted-key JSON encoding, including ECMAScript numbers."""
    if isinstance(value, dict):
        return "{" + ",".join(canonical(k) + ":" + canonical(value[k]) for k in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(canonical, value)) + "]"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite profile number")
        if value == 0:
            return "0"
        if 1e-6 <= abs(value) < 1e21:
            number = format(Decimal(str(value)), "f")
            return number.rstrip("0").rstrip(".") if "." in number else number
        mantissa, exponent = repr(value).lower().split("e")
        return mantissa.removesuffix(".0") + "e" + ("+" if int(exponent) >= 0 else "-") + str(abs(int(exponent)))
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset_path(folder, name):
    path = pathlib.PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name:
        raise ValueError(f"invalid profile asset path: {name}")
    candidate = folder / path
    if not candidate.resolve().is_relative_to(folder.resolve()):
        raise ValueError(f"profile asset escapes bundle: {name}")
    return candidate


def verify_bundle(folder):
    manifest = json.loads((folder / "assets.json").read_text())
    profile = json.loads((folder / "profile.json").read_text())
    if manifest["formatVersion"] != 1 or profile["id"] != "mash-goo" or profile["version"] != 1:
        raise ValueError("unsupported Mash Goo renderer profile")
    for key in ("id", "version", "revision"):
        if manifest[key] != profile[key]:
            raise ValueError(f"manifest/profile {key} mismatch")
    names = [entry["path"] for entry in manifest["files"]]
    if names != sorted(set(names)) or "profile.json" not in names or "assets.json" in names:
        raise ValueError("invalid profile asset inventory")
    actual = sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    if actual != sorted(["assets.json", *names]):
        raise ValueError("profile asset inventory does not match bundle files")
    for entry in manifest["files"]:
        data = asset_path(folder, entry["path"]).read_bytes()
        if len(data) != entry["bytes"] or digest(data) != entry["sha256"]:
            raise ValueError(f"profile asset failed verification: {entry['path']}")
    source = {key: value for key, value in profile.items() if key != "revision"}
    files = [entry for entry in manifest["files"] if entry["path"] != "profile.json"]
    revision = "sha256:" + digest(canonical({"profile": source, "files": files}).encode())
    if revision != profile["revision"]:
        raise ValueError("profile revision does not match its content")
    if profile["measurement"]["authority"] != "server" or profile["measurement"]["arithmetic"] != "binary64":
        raise ValueError("profile does not describe server binary64 measurement")
    if profile["text"]["encoding"] != "ascii" or profile["text"]["printableRange"] != [32, 126] or profile["text"]["controls"] != [9, 10, 13]:
        raise ValueError("unsupported profile glyph coverage")
    metrics = json.loads((folder / "metrics.json").read_text())
    for face in profile["fonts"].values():
        metric = metrics[face["metricsKey"]]
        if digest(asset_path(folder, face["file"]).read_bytes()) != metric["fontSHA256"]:
            raise ValueError(f"font/metric mismatch: {face['file']}")
        if metric["weight"] != face["weight"] or len(metric["advances"]) != 95 or metric["unitsPerEm"] <= 0:
            raise ValueError(f"invalid font metrics: {face['file']}")
    return profile


def scalar(value):
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return f"(goo/scalar {bits})"


def quote(value):
    return json.dumps(value, ensure_ascii=False)



PAINT_MARKER = "/* Paint only. Typography, control padding and measured geometry are generated. */"


def paint_rules(css):
    """Bounded build-time lowering of the pinned profile, never a client CSS API.

    Fail closed when Mash introduces a selector/property this lowering cannot
    represent. Geometry continues to come from the verified JSON profile.
    """
    if css.count(PAINT_MARKER) != 1:
        raise ValueError("portable paint requires the pinned paint section")
    source = css.split(PAINT_MARKER, 1)[1]
    rules = []
    ignored = {"display", "grid-template-columns", "grid-template-rows", "place-items", "white-space", "cursor"}
    supported = {"color", "background", "border-color", "border-radius", "overflow", "outline", "outline-offset"}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", source):
        properties = dict(part.strip().split(":", 1) for part in body.split(";") if part.strip())
        properties = {k.strip(): v.strip() for k, v in properties.items()}
        unknown = properties.keys() - supported - ignored
        if unknown:
            raise ValueError(f"unsupported portable paint properties: {sorted(unknown)}")
        for selector in selectors.split(","):
            selector = selector.strip()
            if not re.fullmatch(r"\.goo-surface(?: \.goo-[a-z-]+(?::not\(\.goo-text\))?(?:\.[a-z-]+)?(?::focus-visible)?)?", selector):
                raise ValueError(f"unsupported portable paint selector: {selector}")
            if (":focus-visible" in selector or ".highlight" in selector) and properties.keys() - {"outline", "outline-offset"}:
                raise ValueError(f"unsupported portable state paint: {selector}")
            if properties.get("overflow", "visible") not in ("hidden", "visible"):
                raise ValueError("unsupported portable overflow")
            rules.append((selector, properties))
    if re.sub(r"[^{}]+\{[^{}]*\}", "", source).strip():
        raise ValueError("unsupported portable paint syntax")
    return rules


def paint_recipe(profile, rules, kind, role="", primary=False, destructive=False, state="normal"):
    classes = {"goo-surface", "goo-node", "goo-" + kind}
    if kind == "text":
        classes.add("goo-" + role)
    if primary: classes.add("primary")
    if destructive: classes.add("destructive")
    if state == "highlight": classes.add("highlight")
    # Native HTML buttons have UA ButtonText, which prevents inherited surface
    # color. Pin the existing light-profile baseline instead of delegating it to
    # another toolkit's button defaults. Explicit primary/destructive rules win.
    resolved = {"color": "#000000"} if kind == "button" else {}
    applicable = []
    for order, (selector, properties) in enumerate(rules):
        if kind == "button" and selector == ".goo-surface": continue
        if ":focus-visible" in selector and state != "focus": continue
        if ":not(.goo-text)" in selector and kind == "text": continue
        positive = selector.replace(":not(.goo-text)", "").replace(":focus-visible", "")
        if set(re.findall(r"\.([a-z-]+)", positive)) <= classes:
            applicable.append((selector.count(".") + selector.count(":focus-visible"), order, properties))
    for _, _, properties in sorted(applicable): resolved.update(properties)
    def color(value):
        if not re.fullmatch(r"#[0-9a-f]{6}", value):
            raise ValueError(f"unsupported portable color: {value}")
        return value
    background = resolved.get("background", "transparent")
    if background == "transparent":
        fill = {"kind": "none"}
    elif background.startswith("#"):
        fill = {"kind": "solid", "color": color(background)}
    else:
        match = re.fullmatch(r"linear-gradient\((138deg|to right), (#[0-9a-f]{6})( 73%)?, (#[0-9a-f]{6})( 73%)?\)", background)
        if not match: raise ValueError(f"unsupported portable background: {background}")
        angle, first, stop1, last, stop2 = match.groups()
        fill = {"kind": "linear-gradient", "angleDegrees": 90 if angle == "to right" else 138,
                "stops": [{"offset": .73 if stop1 else 0, "color": first}, {"offset": .73 if stop2 else 1, "color": last}]}
    radius = resolved.get("border-radius", "0px")
    if radius == "50%": corners = {"kind": "ellipse"}
    elif re.fullmatch(r"[0-9]+px", radius): corners = {"kind": "radius", "radius": int(radius[:-2])}
    else: raise ValueError(f"unsupported portable radius: {radius}")
    border = kind in ("input", "button", "code") or (kind == "text" and role == "badge")
    recipe = {"version": 1, "units": "css-px", "colorSpace": "srgb", "foreground": color(resolved["color"]),
              "background": fill, "border": {"width": profile["geometry"]["controlBorder"] if border else 0,
              "color": color(resolved.get("border-color", resolved["color"]))}, "corners": corners,
              "clip": resolved.get("overflow") == "hidden"}
    if "outline" in resolved:
        match = re.fullmatch(r"([0-9]+)px solid (#[0-9a-f]{6})", resolved["outline"])
        offset = resolved.get("outline-offset", "0px")
        if not match or not re.fullmatch(r"[0-9]+px", offset): raise ValueError("unsupported portable outline")
        recipe["outline"] = {"width": int(match[1]), "color": match[2], "offset": int(offset[:-2])}
    return recipe


def foil_json(value):
    if isinstance(value, dict): return "(json/obj [" + " ".join(f"(jkv {quote(k)} {foil_json(v)})" for k, v in value.items()) + "])"
    if isinstance(value, list): return "(json/arr [" + " ".join(map(foil_json, value)) + "])"
    if isinstance(value, bool): return "(json/boo ." + ("true" if value else "false") + ")"
    if isinstance(value, str): return "(json/str " + quote(value) + ")"
    if isinstance(value, int): return f"(json/num .{'true' if value < 0 else 'false'} {abs(value)})"
    return "(json/real " + quote(canonical(value)) + ")"


def generate_paint(profile, css):
    rules = paint_rules(css)
    out = ["  + paint_style", "    \\ kind=str role=str primary=bool destructive=bool", "    ^ json"]
    constants = []
    cases = []
    for primary, destructive in ((True, True), (True, False), (False, True), (False, False)):
        condition = '(eq kind "button")'
        if primary: condition = f"(and {condition} primary)"
        if destructive: condition = f"(and {condition} destructive)"
        cases.append((condition, "button", "", primary, destructive))
    for role in profile["textStyles"]["roles"]:
        cases.append((f'(and (eq kind "text") (eq role {quote(role)}))', "text", role, False, False))
    for kind in ("input", "code", "avatar", "presence", "media", "bar"):
        cases.append((f'(eq kind {quote(kind)})', kind, "", False, False))
    for index, (condition, kind, role, primary, destructive) in enumerate(cases):
        recipe = paint_recipe(profile, rules, kind, role, primary, destructive)
        # State recipes describe local presentation, not remotely-owned focus.
        recipe["states"] = {state: paint_recipe(profile, rules, kind, role, primary, destructive, state).get("outline")
                            for state in ("highlight", "focus")
                            if "outline" in paint_recipe(profile, rules, kind, role, primary, destructive, state)}
        name = f"paint_recipe_{index}"
        constants.extend([f"  + {name}", "    ^ json", "    " + foil_json(recipe)])
        out.append(f"    ? {condition} goo_profile/{name}")
    recipe = paint_recipe(profile, rules, "group")
    recipe["states"] = {"highlight": paint_recipe(profile, rules, "group", state="highlight")["outline"]}
    constants.extend(["  + paint_default", "    ^ json", "    " + foil_json(recipe)])
    out.append("    goo_profile/paint_default")
    return constants + out


def generate(profile, css=None):
    out = ["- goo_app/fonts", "", "' Generated by scripts/sync-mash-profile.py from the verified Mash bundle.", "+ goo_profile"]

    def constant(name, kind, value):
        out.extend([f"  + {name}", f"    ^ {kind}", f"    {value}"])

    constant("id", "str", quote(profile["id"]))
    constant("version", "nat", str(profile["version"]))
    constant("revision", "str", quote(profile["revision"]))
    out.extend(["  + metadata", "    \\ ignored=unit", "    ^ json", '    | json/obj [(jkv "id" (json/str goo_profile/id)) (jkv "version" (json/num .false goo_profile/version)) (jkv "revision" (json/str goo_profile/revision))]'])
    for name, kind, key in (("font_id", "str", None), ("font_family", "str", "family"), ("font_weight", "nat", "weight"), ("font_style", "str", "style")):
        out.extend([f"  + {name}", "    \\ face=goo_fonts/face", f"    ^ {kind}", "    ? face"])
        for face, spec in profile["fonts"].items():
            value = face if key is None else spec[key]
            out.append(f"     > ./{face} " + (quote(value) if kind == "str" else str(value)))
    for name, key in (("font_ascent", "ascent"), ("font_descent", "descent"), ("font_units", "unitsPerEm")):
        out.extend([f"  + {name}", "    \\ face=goo_fonts/face", "    ^ nat", "    ? face"])
        for face, spec in profile["fonts"].items():
            out.append(f"     > ./{face} {spec['verticalMetrics'][key]}")
    out.extend(["  + style", "    : face=goo_fonts/face pixels=goo/scalar leading=goo/scalar tracking=goo/scalar inset_x=goo/scalar inset_y=goo/scalar", "  + text_style", "    \\ scale=goo/scalar kind=str role=str", "    ^ goo_profile/style"])

    def style(spec):
        pixels = scalar(spec["pixels"])
        # Preserve the original binary64 operation order: (ratio * pixels) * scale.
        values = [f"(goo_fonts/face/{spec['face']})", f"(goo_fp/times {pixels} scale)", f"(goo_fp/times (goo_fp/times {scalar(spec['lineHeight'])} {pixels}) scale)", *[scalar(spec[k]) for k in ("tracking", "insetX", "insetY")]]
        return "(goo_profile/style " + " ".join(values) + ")"

    for table, variable in (("kinds", "kind"), ("roles", "role")):
        for name, spec in profile["textStyles"][table].items():
            out.append(f"    ? (eq {variable} {quote(name)}) {style(spec)}")
    out.append("    " + style(profile["textStyles"]["default"]))
    geometry = profile["geometry"]
    for name, values in (("natural_width", geometry["naturalWidths"]), ("fixed_height", {key: value for key, value in geometry["heights"].items() if key != "media"})):
        out.extend([f"  + {name}", "    \\ kind=str", "    ^ maybe[goo/scalar]"])
        for kind, value in values.items():
            out.append(f"    ? (eq kind {quote(kind)}) (./some {scalar(value)})")
        out.append("    .none")
    for name, key in (("preferred_cap", "preferredCaps"), ("minimum_width", "minimumWidths")):
        out.extend([f"  + {name}", "    \\ slot=str", "    ^ goo/scalar"])
        for slot, value in geometry[key]["slots"].items():
            out.append(f"    ? (eq slot {quote(slot)}) {scalar(value)}")
        out.append("    " + scalar(geometry[key]["default"]))
    conditions = [f"(eq {variable} {quote(value)})" for key, variable in (("fixedKinds", "kind"), ("fixedSlots", "slot")) for value in geometry[key]]
    out.extend(["  + fixed", "    \\ kind=str slot=str", "    ^ bool", "    (" + " || ".join(conditions) + ")"])
    for name, value in (("media_minimum", geometry["heights"]["media"]["minimum"]), ("media_aspect_ratio", geometry["heights"]["media"]["aspectRatio"]), ("status_marker", geometry["status"]["markerPixels"]), ("status_gap", geometry["status"]["gap"]), ("fit_tolerance", geometry["fitTolerance"])):
        constant(name, "goo/scalar", scalar(value))
    constant("tab_text", "str", quote(" " * profile["text"]["tabSpaces"]))
    constant("error_prefix", "str", quote(profile["text"]["errorPrefix"]))
    out.extend(generate_paint(profile, css if css is not None else (VENDOR / "profile.css").read_text()))
    return "\n".join(out) + "\n"


def browser_profile_links():
    """The paths browsers fetch to get the profile over HTTP.

    These are symlinks into the single vendored profile directory (the Goo
    static tree and the Explorer consumer both serve them). Keeping them as
    symlinks is what guarantees the served contract can never diverge from the
    verified bundle that produced the server-side preparation.
    """
    explorer = ROOT.parents[1] / "mounts" / "explorer"
    return [
        ROOT / "static" / "goo-profile.css",
        ROOT / "static" / "goo-profile.json",
        explorer / "goo-profile.css",
        explorer / "goo-profile.json",
    ]


def check_browser_profile_links(profile=VENDOR):
    """Guard the browser-facing profile against a missing or re-pointed link.

    A profile bump or a partial checkout can leave one of these links broken or
    pointing elsewhere; that would let the browser serve a stale or absent
    profile while preparation uses the current bundle. Each link must remain a
    symlink that resolves to the corresponding vendored profile file.
    """
    for link in browser_profile_links():
        if not link.is_symlink():
            raise ValueError(f"browser profile must be a symlink into the vendored profile: {link}")
        source = profile / ("profile.css" if link.name.endswith(".css") else "profile.json")
        if not source.is_file() or link.resolve() != source.resolve():
            raise ValueError(f"browser profile link does not resolve to the vendored profile: {link} -> {link.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mash-root", type=pathlib.Path, help="explicit Mash checkout containing packages/goo-profile/dist")
    parser.add_argument("--check", action="store_true", help="check committed assets and generated Foil without a Mash checkout")
    args = parser.parse_args()
    if not args.check and args.mash_root is None:
        parser.error("updates require --mash-root; use --check to verify locally")
    try:
        if args.mash_root is not None:
            source = args.mash_root.resolve() / "packages/goo-profile/dist"
            verify_bundle(source)
            if args.check:
                for path in source.rglob("*"):
                    if path.is_file() and (not (VENDOR / path.relative_to(source)).is_file() or path.read_bytes() != (VENDOR / path.relative_to(source)).read_bytes()):
                        raise ValueError(f"vendored profile is stale: {path.relative_to(source)}")
            else:
                # Prepare and verify before replacing the generated bundle. An
                # explicit update can also repair a damaged previous import.
                with tempfile.TemporaryDirectory(prefix=".profile-import-", dir=ROOT) as temp:
                    incoming = pathlib.Path(temp) / "incoming"
                    previous = pathlib.Path(temp) / "previous"
                    shutil.copytree(source, incoming)
                    verify_bundle(incoming)
                    if VENDOR.exists():
                        VENDOR.rename(previous)
                    try:
                        incoming.rename(VENDOR)
                    except OSError:
                        if previous.exists():
                            previous.rename(VENDOR)
                        raise
        profile = verify_bundle(VENDOR)
        generated = generate(profile)
        target = ROOT / "profile.foil"
        if args.check:
            if not target.is_file() or target.read_text() != generated:
                raise ValueError("generated profile.foil is stale")
        else:
            target.write_text(generated)
        subprocess.run([sys.executable, str(ROOT / "scripts/generate-fonts.py"), *(["--check"] if args.check else [])], check=True)
        if args.check:
            check_browser_profile_links()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Mash Goo profile: {error}\n")
    print(f"Mash Goo profile verified: {profile['id']} v{profile['version']} {profile['revision']}")


if __name__ == "__main__":
    main()
