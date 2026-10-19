#!/usr/bin/env python3
"""Download a bounded, public Manifold sample with raw-response receipts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
IDS = ["OqEUCA9tCN", "PUu5UdNR6E", "AqZzEnIysE", "U55gtI0lnE",
       "9LPpAtIQEn", "8hyIALhpqN", "RL8CuzNAhd"]


def main():
    data = ROOT / "data"
    raw = data / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    markets, receipts = [], []
    for market_id in IDS:
        url = "https://api.manifold.markets/v0/market/" + market_id
        with urlopen(url, timeout=30) as response:
            body = response.read()
            status = response.status
        fetched = datetime.now(timezone.utc).isoformat()
        market = json.loads(body)
        assert market["id"] == market_id
        name = market_id + ".json"
        (raw / name).write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        receipts.append({"market_id": market_id, "url": url, "http_status": status,
                         "fetched_at": fetched, "sha256": digest,
                         "bytes": len(body), "file": "raw/" + name})
        markets.append({"source": "manifold", "source_api": url,
                        "fetched_at": fetched, "raw_sha256": digest,
                        "market": market})
    (data / "sample.json").write_text(json.dumps(markets, indent=2, ensure_ascii=False) + "\n")
    (data / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps({"markets": len(markets), "binary": sum(x["market"]["outcomeType"] == "BINARY" for x in markets),
                      "multiple_choice": sum(x["market"]["outcomeType"] == "MULTIPLE_CHOICE" for x in markets),
                      "path": str(data / "sample.json")}))


if __name__ == "__main__":
    main()
