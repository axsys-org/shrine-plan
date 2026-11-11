"""Once per world: the mesa hand into its hands.foil, compiled by the hands mount; taken up on the world's next boot.
   python3 install_mesa.py 0x58 [0x53 ...]   (the hand text beside this script as mesa_hand.foil)
   WHO=owner for a world with no agent token (its owner token is used instead)."""
import http.client, json, os, re, sys, time
from pathlib import Path
NODES = sys.argv[1:]
reg = json.load(open("/opt/shrine/v13/pilot/state/registry.json"))
hand = open(Path(__file__).with_name("mesa_hand.foil")).read()
KOOK = "(kook/decl 'mesa hands/mesa/form (lore/line \"Keeps /net/mesa: what this world publishes to each peer and wants from each.\"))"
SEED = "[['mesa] (kooked [(pact/rel ['kook 'mesa])])]"
def add(text, head, item):
    at = text.index(head) + len(head)
    rest = text[at:]
    return text[:at] + ("[" + item + "]" + rest[2:] if rest.startswith("[]") else "[" + item + " " + rest[1:])
NODE = {"n": ""}
def call(name, **a):
    node = NODE["n"]
    tok = open(f"/opt/shrine/v13/pilot/state/{node}.{os.environ.get("WHO", "agent")}.token").read().strip()
    c = http.client.HTTPConnection("127.0.0.1", 18400, timeout=600)
    c.request("POST", f"/w/{node}/mcp", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": a}}), {"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    r = json.loads(c.getresponse().read())["result"]
    return r.get("structuredContent") or r
for node in NODES:
    w = next(x for x in reg["worlds"] if x["node"] == node)
    NODE["n"] = node
    f = Path(w["dir"]) / "hands" / "hands.foil"
    text = f.read_text()
    if "\n  +  mesa\n" in text:
        a = text.index("  +  mesa\n"); b = text.index("  +  app\n")
        text = text[:a] + hand.lstrip("\n") + text[b:]
    else:
        text = text.replace("  +  app\n", hand.lstrip("\n") + "  +  app\n", 1)
        text = add(text, "kooks=row[kook/decl] ", KOOK)
        text = add(text, "seeds=row[[p=path t=myth]] ", SEED)
    if os.environ.get("MERGE_TO"):
        # check only: the merged module written where x/foil-check reads it; the world untouched
        Path(os.environ["MERGE_TO"]).write_text(text); print(f"{node}: merged to {os.environ['MERGE_TO']}"); continue
    c = http.client.HTTPConnection("127.0.0.1", 18400, timeout=30); c.request("GET", f"/w/{node}/drive"); c.getresponse().read()
    t0 = time.time()
    while True:
        try:
            call("mcp/read", path=f"/{node}", care="x"); break
        except Exception:
            if time.time() - t0 > 300: raise
            time.sleep(1)
    f.write_text(text)
    home = f"/{node}/io/fs/hands"
    p0 = int(call("mcp/read", path=home, care="x").get("properties", {}).get("/sys/fs/source/publication", 0))
    t0 = time.time()
    call("mcp/apply", path=home, operation=f"{home}/op/rescan", inputs={})
    while True:
        p = call("mcp/read", path=home, care="x").get("properties", {})
        if int(p.get("/sys/fs/source/publication", 0)) > p0 and p.get("/sys/fs/source/message") == "Published":
            print(f"{node}: compiled in {time.time() - t0:.1f} s; taken up on its next boot", flush=True); break
        if p.get("/sys/fs/source/diagnostic_text") and time.time() - t0 > 20:
            print(f"{node}: failed: {p['/sys/fs/source/diagnostic_text'][:1500]}", flush=True); sys.exit(1)
        if time.time() - t0 > 600:
            print(f"{node}: no result in 600 s: {json.dumps(p)[:600]}", flush=True); sys.exit(1)
        time.sleep(2)
