"""
One-off / occasionally-rerun script: downloads Angel One's public instrument
master and builds a {nifty50_symbol: {token, angel_symbol}} map for NSE
equities, saved to data/angelone_tokens.json.

No SmartAPI credentials needed for this step - the scrip master is a public
file. Rerun this if Angel One adds/renames an instrument and a ticker goes
missing from the app.
"""
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.stock_service import ALL_NIFTY_50_STOCKS  # noqa: E402

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "angelone_tokens.json"
INDICES_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "angelone_indices.json"


def main() -> None:
    print(f"Downloading scrip master from {SCRIP_MASTER_URL} ...")
    resp = requests.get(SCRIP_MASTER_URL, timeout=60)
    resp.raise_for_status()
    instruments = resp.json()
    print(f"Loaded {len(instruments)} instruments")

    nse_eq_by_name = {
        d["name"]: {"token": d["token"], "angel_symbol": d["symbol"]}
        for d in instruments
        if d.get("exch_seg") == "NSE" and d.get("symbol", "").endswith("-EQ")
    }

    mapping = {}
    missing = []
    for stock in ALL_NIFTY_50_STOCKS:
        # our tickers are like "RELIANCE.NS" -> Angel One's instrument "name" is "RELIANCE"
        base_name = stock["symbol"].replace(".NS", "")
        entry = nse_eq_by_name.get(base_name)
        if entry:
            mapping[stock["symbol"]] = entry
        else:
            missing.append(stock["symbol"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(mapping, indent=2))
    print(f"Wrote {len(mapping)} tokens to {OUTPUT_PATH}")
    if missing:
        print(f"WARNING: no Angel One instrument found for: {missing}")

    index_by_symbol = {
        d["symbol"]: {"token": d["token"], "exch_seg": d["exch_seg"]}
        for d in instruments
        if d.get("instrumenttype") == "AMXIDX"
        and d.get("symbol") in ("Nifty 50", "Nifty Bank", "SENSEX")
    }
    indices = {
        "NIFTY50": index_by_symbol.get("Nifty 50"),
        "NIFTYBANK": index_by_symbol.get("Nifty Bank"),
        "SENSEX": index_by_symbol.get("SENSEX"),
    }
    missing_idx = [k for k, v in indices.items() if not v]
    indices = {k: v for k, v in indices.items() if v}
    INDICES_OUTPUT_PATH.write_text(json.dumps(indices, indent=2))
    print(f"Wrote {len(indices)} index tokens to {INDICES_OUTPUT_PATH}")
    if missing_idx:
        print(f"WARNING: no Angel One instrument found for indices: {missing_idx}")


if __name__ == "__main__":
    main()
