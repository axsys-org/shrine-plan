"""Check the effective styles of a running Goo zoo using its prepared output."""
import argparse
import json
from urllib.parse import urlencode
from urllib.request import urlopen


def sheet(server, root, name, width):
    fields = {"target": f"{root}/{name}", "slot": "/sys/slot/style_zoo_sheet",
              "width": width, "textScale": 1, "direction": "ltr"}
    with urlopen(server.rstrip("/") + "/goo/render", urlencode(fields).encode(), timeout=90) as response:
        return json.load(response)["display"]["nodes"]


def check(server, root, width):
    # Unknown slot paths survive preparation with the default face. Checking only
    # whether the view rendered would miss visually identical type specimens.
    nodes = sheet(server, root, "type", width)
    styles = {n["role"]: n["textStyle"] for n in nodes if n["payload"] == "The quick brown fox"}
    assert set(styles) == {"title", "body", "quote", "label", "credit", "badge"}, styles.keys()
    assert styles["quote"]["style"] == "italic"
    assert styles["title"]["fontSize"] > styles["body"]["fontSize"] > styles["label"]["fontSize"]

    nodes = sheet(server, root, "runs", width)
    samples = [n for n in nodes if n["payload"].startswith("Plain, ")]
    assert len(samples) == 2 and samples[0]["textRuns"] == samples[1]["textRuns"]
    for sample in samples:
        fragments = [f for line in sample["lines"] for f in line["runs"]]
        linked = [f for f in fragments if f["myth"].get("/sys/link")]
        assert linked and all(f["resolved"]["highlight"] for f in linked)
        assert all(f["resolved"]["semantics"]["target"]["path"] == root + "/paint" for f in linked)

    nodes = sheet(server, root, "paint", width)
    buttons = [n["paint"] for n in nodes if n["kind"] == "button"]
    assert len({json.dumps(paint, sort_keys=True) for paint in buttons}) == 3
    assert [n["semantics"]["range"]["value"] for n in nodes if n["kind"] == "bar"] == [1, 3]
    print(f"Verified typography, run highlights, button treatments and progress at {width} CSS px.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:18480")
    parser.add_argument("--root", default="/0x11/app/style_zoo")
    args = parser.parse_args()
    for width in (350, 900):
        check(args.server, args.root, width)
