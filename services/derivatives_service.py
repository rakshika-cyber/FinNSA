"""Option chain, futures and market depth for Nifty 50 stocks.

Data sources
  * Prices, open interest, volume, bid/ask depth: Angel One SmartAPI (NSE/NFO exchange feed).
  * Contract list: Angel One public instrument master (OpenAPIScripMaster.json).
  * Greeks and implied volatility: COMPUTED here (Black-Scholes, European exercise - NSE stock
    options are European-style). IV is solved from the real option LTP. Rate and dividend
    yield are assumptions and are returned with every response so the UI can display them.
"""
import json
import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from services import angelone_client
from services.stock_service import ALL_NIFTY_50_STOCKS, _get_cached, _ensure_cache_ready

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FNO_PATH = _DATA_DIR / "angelone_fno.json"
_TOKENS = json.loads((_DATA_DIR / "angelone_tokens.json").read_text()) if (_DATA_DIR / "angelone_tokens.json").exists() else {}

# Assumptions (shown in the UI). Override via env; 91-day T-bill / short G-sec yield is the usual choice.
RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.065"))
DIVIDEND_YIELD = 0.0
IST = timezone(timedelta(hours=5, minutes=30))
CHAIN_TTL = 30
STRIKES_EACH_SIDE = 12

_lock = threading.Lock()
_fno: Optional[Dict[str, Any]] = None
_cache: Dict[str, tuple] = {}


# ---------------------------------------------------------------- instruments
def _base(symbol: str) -> str:
    return symbol.upper().replace(".NS", "")


def _load_fno() -> Dict[str, Any]:
    """{base_symbol: {"options": [...], "futures": [...]}} filtered to Nifty 50 names, refreshed daily."""
    global _fno
    with _lock:
        if _fno is not None:
            return _fno
        if _FNO_PATH.exists():
            age = time.time() - _FNO_PATH.stat().st_mtime
            if age < 12 * 3600:
                _fno = json.loads(_FNO_PATH.read_text())
                return _fno
        resp = requests.get(SCRIP_MASTER_URL, timeout=90)
        resp.raise_for_status()
        wanted = {_base(s["symbol"]) for s in ALL_NIFTY_50_STOCKS}
        out: Dict[str, Any] = {n: {"options": [], "futures": []} for n in wanted}
        for i in resp.json():
            if i.get("exch_seg") != "NFO" or i.get("name") not in wanted:
                continue
            kind = i.get("instrumenttype")
            if kind not in ("OPTSTK", "FUTSTK"):
                continue
            row = {"token": i["token"], "symbol": i["symbol"], "expiry": i["expiry"],
                   "lot": int(float(i["lotsize"])), "strike": float(i["strike"]) / 100.0}
            out[i["name"]]["options" if kind == "OPTSTK" else "futures"].append(row)
        _DATA_DIR.mkdir(exist_ok=True)
        _FNO_PATH.write_text(json.dumps(out))
        _fno = out
        return _fno


def _expiry_dt(expiry: str) -> datetime:
    return datetime.strptime(expiry, "%d%b%Y").replace(hour=15, minute=30, tzinfo=IST)


def list_expiries(symbol: str) -> List[str]:
    data = _load_fno().get(_base(symbol), {"options": []})
    now = datetime.now(IST)
    exps = {o["expiry"] for o in data["options"] if _expiry_dt(o["expiry"]) > now}
    return sorted(exps, key=_expiry_dt)


# ---------------------------------------------------------------- Black-Scholes
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_price(S: float, K: float, T: float, r: float, q: float, sigma: float, is_call: bool) -> float:
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if is_call:
        return S * math.exp(-q * T) * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * math.exp(-q * T) * _ncdf(-d1)


def implied_vol(price: float, S: float, K: float, T: float, r: float, q: float, is_call: bool) -> Optional[float]:
    """Bisection IV. Returns None when the price is outside no-arbitrage bounds (stale/zero quotes)."""
    if price <= 0 or T <= 0:
        return None
    disc_k, disc_s = K * math.exp(-r * T), S * math.exp(-q * T)
    intrinsic = max(0.0, disc_s - disc_k) if is_call else max(0.0, disc_k - disc_s)
    upper = disc_s if is_call else disc_k
    if price < intrinsic - 1e-9 or price > upper:
        return None
    lo, hi = 1e-4, 5.0
    if bs_price(S, K, T, r, q, hi, is_call) < price:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if bs_price(S, K, T, r, q, mid, is_call) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def greeks(S: float, K: float, T: float, r: float, q: float, sigma: float, is_call: bool) -> Dict[str, float]:
    """delta; gamma per 1 INR; theta per calendar day; vega per 1 vol point (1%)."""
    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    eq, er = math.exp(-q * T), math.exp(-r * T)
    pdf = _npdf(d1)
    if is_call:
        delta = eq * _ncdf(d1)
        theta = -S * eq * pdf * sigma / (2 * sqrt_t) - r * K * er * _ncdf(d2) + q * S * eq * _ncdf(d1)
    else:
        delta = -eq * _ncdf(-d1)
        theta = -S * eq * pdf * sigma / (2 * sqrt_t) + r * K * er * _ncdf(-d2) - q * S * eq * _ncdf(-d1)
    return {
        "delta": round(delta, 4),
        "gamma": round(eq * pdf / (S * sigma * sqrt_t), 6),
        "theta": round(theta / 365.0, 3),
        "vega": round(S * eq * pdf * sqrt_t / 100.0, 3),
    }


# ---------------------------------------------------------------- quotes
def _depth_level(side: List[dict]) -> Dict[str, Any]:
    best = side[0] if side else {}
    p = best.get("price") or 0
    return {"price": p if p else None, "qty": best.get("quantity") or 0}


def _spot(symbol: str) -> Optional[float]:
    _ensure_cache_ready()
    c = _get_cached(f"{_base(symbol)}.NS")
    return c["price"] if c else None


def _cached(key: str, ttl: int, loader):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = loader()
    _cache[key] = (time.time(), val)
    return val


def _max_pain(rows: List[Dict[str, Any]]) -> Optional[float]:
    strikes = sorted({r["strike"] for r in rows})
    if not strikes:
        return None
    by = {(r["strike"], r["type"]): r["oi"] for r in rows}
    best, best_pain = None, None
    for s in strikes:
        pain = sum(by.get((k, "CE"), 0) * max(0.0, s - k) + by.get((k, "PE"), 0) * max(0.0, k - s) for k in strikes)
        if best_pain is None or pain < best_pain:
            best, best_pain = s, pain
    return best


def _load_chain(symbol: str, expiry: str) -> Dict[str, Any]:
    base = _base(symbol)
    fno = _load_fno().get(base)
    contracts = [o for o in (fno or {}).get("options", []) if o["expiry"] == expiry]
    if not contracts:
        raise ValueError(f"No option contracts for {base} expiring {expiry}")

    spot = _spot(base)
    if not spot:
        raise ValueError(f"No live spot price for {base}")

    # Only fetch strikes near the money (+ enough for PCR/max pain accuracy is NOT guaranteed
    # outside this window, so summary stats below say which window they cover).
    strikes = sorted({c["strike"] for c in contracts})
    atm = min(strikes, key=lambda k: abs(k - spot))
    idx = strikes.index(atm)
    window = set(strikes[max(0, idx - STRIKES_EACH_SIDE): idx + STRIKES_EACH_SIDE + 1])
    wanted = [c for c in contracts if c["strike"] in window]
    by_token = {c["token"]: c for c in wanted}

    quotes = angelone_client.get_full_quotes("NFO", list(by_token))
    T = max((_expiry_dt(expiry) - datetime.now(IST)).total_seconds(), 0) / (365.0 * 86400)

    rows, feed_time = [], None
    for q in quotes:
        c = by_token.get(q.get("symbolToken"))
        if not c:
            continue
        is_call = c["symbol"].endswith("CE")
        ltp = q.get("ltp") or 0.0
        depth = q.get("depth") or {}
        bid, ask = _depth_level(depth.get("buy", [])), _depth_level(depth.get("sell", []))
        # A contract with no volume and no open interest has a stale last price; IV from it is noise.
        traded = bool(q.get("tradeVolume")) and bool(q.get("opnInterest"))
        iv = implied_vol(ltp, spot, c["strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, is_call) if (T > 0 and traded) else None
        g = greeks(spot, c["strike"], T, RISK_FREE_RATE, DIVIDEND_YIELD, iv, is_call) if iv else None
        feed_time = feed_time or q.get("exchFeedTime")
        rows.append({
            "strike": c["strike"], "type": "CE" if is_call else "PE", "symbol": c["symbol"], "lot": c["lot"],
            "ltp": ltp or None, "change_pct": q.get("percentChange"),
            "bid": bid["price"], "bid_qty": bid["qty"], "ask": ask["price"], "ask_qty": ask["qty"],
            "oi": q.get("opnInterest") or 0, "volume": q.get("tradeVolume") or 0,
            "iv": round(iv * 100, 2) if iv else None, "greeks": g,
        })

    calls = [r for r in rows if r["type"] == "CE"]
    puts = [r for r in rows if r["type"] == "PE"]
    coi, poi = sum(r["oi"] for r in calls), sum(r["oi"] for r in puts)
    cvol, pvol = sum(r["volume"] for r in calls), sum(r["volume"] for r in puts)
    atm_iv = [r["iv"] for r in rows if r["strike"] == atm and r["iv"]]

    strikes_out: Dict[float, Dict[str, Any]] = {}
    for r in rows:
        strikes_out.setdefault(r["strike"], {"strike": r["strike"]})[r["type"]] = r

    return {
        "symbol": base, "expiry": expiry, "spot": spot, "atm_strike": atm,
        "days_to_expiry": round(T * 365, 2),
        "chain": [strikes_out[k] for k in sorted(strikes_out)],
        "summary": {
            "window": f"ATM ±{STRIKES_EACH_SIDE} strikes",
            "call_oi": coi, "put_oi": poi, "pcr_oi": round(poi / coi, 3) if coi else None,
            "call_volume": cvol, "put_volume": pvol, "pcr_volume": round(pvol / cvol, 3) if cvol else None,
            "max_pain": _max_pain(rows), "atm_iv": round(sum(atm_iv) / len(atm_iv), 2) if atm_iv else None,
            "lot_size": contracts[0]["lot"],
        },
        "assumptions": {"model": "Black-Scholes (European)", "risk_free_rate": RISK_FREE_RATE,
                        "dividend_yield": DIVIDEND_YIELD,
                        "note": "Prices/OI/volume/bid-ask are exchange data via Angel One SmartAPI. "
                                "IV and Greeks are computed from those prices, not exchange-published."},
        "exchange_feed_time": feed_time,
    }


def get_option_chain(symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
    expiries = list_expiries(symbol)
    if not expiries:
        raise ValueError(f"{_base(symbol)} has no listed stock options")
    expiry = expiry or expiries[0]
    if expiry not in expiries:
        raise ValueError(f"Invalid expiry {expiry}; available: {expiries}")
    data = _cached(f"chain:{_base(symbol)}:{expiry}", CHAIN_TTL, lambda: _load_chain(symbol, expiry))
    return {**data, "expiries": expiries}


def get_futures(symbol: str) -> List[Dict[str, Any]]:
    base = _base(symbol)
    futs = sorted((_load_fno().get(base) or {}).get("futures", []), key=lambda f: _expiry_dt(f["expiry"]))
    futs = [f for f in futs if _expiry_dt(f["expiry"]) > datetime.now(IST)]
    if not futs:
        return []

    def load():
        by = {f["token"]: f for f in futs}
        spot = _spot(base)
        out = []
        for q in angelone_client.get_full_quotes("NFO", list(by)):
            f = by[q["symbolToken"]]
            ltp = q.get("ltp")
            out.append({"expiry": f["expiry"], "symbol": f["symbol"], "lot": f["lot"], "ltp": ltp,
                        "change_pct": q.get("percentChange"), "oi": q.get("opnInterest"),
                        "volume": q.get("tradeVolume"),
                        "basis": round(ltp - spot, 2) if ltp and spot else None})
        return sorted(out, key=lambda x: _expiry_dt(x["expiry"]))
    return _cached(f"fut:{base}", CHAIN_TTL, load)


def get_depth(symbol: str) -> Dict[str, Any]:
    """Real 5-level order book for the equity (NSE)."""
    key = f"{_base(symbol)}.NS"
    tok = (_TOKENS.get(key) or {}).get("token")
    if not tok:
        raise ValueError(f"No Angel One token for {key}")

    def load():
        rows = angelone_client.get_full_quotes("NSE", [tok])
        if not rows:
            raise ValueError("No depth returned")
        q = rows[0]
        d = q.get("depth") or {}
        return {
            "symbol": _base(symbol), "ltp": q.get("ltp"),
            "buy": [{"price": l["price"], "qty": l["quantity"], "orders": l["orders"]} for l in d.get("buy", [])],
            "sell": [{"price": l["price"], "qty": l["quantity"], "orders": l["orders"]} for l in d.get("sell", [])],
            "total_buy_qty": q.get("totBuyQuan"), "total_sell_qty": q.get("totSellQuan"),
            "upper_circuit": q.get("upperCircuit"), "lower_circuit": q.get("lowerCircuit"),
            "avg_price": q.get("avgPrice"), "exchange_feed_time": q.get("exchFeedTime"),
        }
    return _cached(f"depth:{_base(symbol)}", 5, load)
