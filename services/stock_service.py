import json
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

import yfinance as yf

from services import angelone_client

# All 50 Nifty 50 Tickers mapped by Sector
ALL_NIFTY_50_STOCKS = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Financials"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Financials"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG"},
    {"symbol": "ITC.NS", "name": "ITC Limited", "sector": "FMCG"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Financials"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Financials"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "sector": "Construction"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank", "sector": "Financials"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Automobile"},
    {"symbol": "TITAN.NS", "name": "Titan Company", "sector": "Consumer Goods"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Healthcare"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Materials"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "Financials"},
    {"symbol": "WIPRO.NS", "name": "Wipro", "sector": "IT"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Metals"},
    {"symbol": "NTPC.NS", "name": "NTPC Limited", "sector": "Power"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corp", "sector": "Power"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Automobile"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT"},
    {"symbol": "ONGC.NS", "name": "ONGC", "sector": "Energy"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Metals"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports", "sector": "Construction"},
    {"symbol": "COALINDIA.NS", "name": "Coal India", "sector": "Energy"},
    {"symbol": "BPCL.NS", "name": "Bharat Petroleum", "sector": "Energy"},
    {"symbol": "CIPLA.NS", "name": "Cipla", "sector": "Healthcare"},
    {"symbol": "EICHERMOT.NS", "name": "Eicher Motors", "sector": "Automobile"},
    {"symbol": "HEROMOTOCO.NS", "name": "Hero MotoCorp", "sector": "Automobile"},
    {"symbol": "HINDALCO.NS", "name": "Hindalco Industries", "sector": "Metals"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Metals"},
    {"symbol": "LTIM.NS", "name": "LTIMindtree", "sector": "IT"},
    {"symbol": "NESTLEIND.NS", "name": "Nestle India", "sector": "FMCG"},
    {"symbol": "TECHM.NS", "name": "Tech Mahindra", "sector": "IT"},
    {"symbol": "TORNTPHARM.NS", "name": "Torrent Pharma", "sector": "Healthcare"},
    {"symbol": "UPL.NS", "name": "UPL Limited", "sector": "Materials"},
    {"symbol": "BAJAJ-AUTO.NS", "name": "Bajaj Auto", "sector": "Automobile"},
    {"symbol": "BAJAJFINSV.NS", "name": "Bajaj Finserv", "sector": "Financials"},
    {"symbol": "BEL.NS", "name": "Bharat Electronics", "sector": "Construction"},
    {"symbol": "BRITANNIA.NS", "name": "Britannia Industries", "sector": "FMCG"},
    {"symbol": "DIVISLAB.NS", "name": "Divi's Laboratories", "sector": "Healthcare"},
    {"symbol": "DRREDDY.NS", "name": "Dr. Reddy's Lab", "sector": "Healthcare"},
    {"symbol": "GRASIM.NS", "name": "Grasim Industries", "sector": "Materials"},
    {"symbol": "INDUSINDBK.NS", "name": "IndusInd Bank", "sector": "Financials"},
    {"symbol": "IOC.NS", "name": "Indian Oil Corp", "sector": "Energy"},
    {"symbol": "SHRIRAMFIN.NS", "name": "Shriram Finance", "sector": "Financials"},
    {"symbol": "TATACONSUM.NS", "name": "Tata Consumer Products", "sector": "FMCG"},
    {"symbol": "TRENT.NS", "name": "Trent Limited", "sector": "Consumer Goods"}
]

# India feed: key benchmark indices (replaces the old global US/crypto feed).
INDIA_INDEX_ITEMS = [
    {"symbol": "NIFTY50", "name": "Nifty 50", "category": "INDEX"},
    {"symbol": "NIFTYBANK", "name": "Nifty Bank", "category": "INDEX"},
    {"symbol": "SENSEX", "name": "BSE Sensex", "category": "INDEX"}
]

# yFinance fallback tickers for the indices above, used only if Angel One is unavailable.
_INDEX_YF_FALLBACK = {
    "NIFTY50": "^NSEI",
    "NIFTYBANK": "^NSEBANK",
    "SENSEX": "^BSESN",
}

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_ANGEL_TOKEN_MAP: Dict[str, Dict[str, str]] = _load_json(_DATA_DIR / "angelone_tokens.json")
_TOKEN_TO_SYMBOL = {v["token"]: k for k, v in _ANGEL_TOKEN_MAP.items()}

_ANGEL_INDEX_MAP: Dict[str, Dict[str, str]] = _load_json(_DATA_DIR / "angelone_indices.json")
_INDEX_TOKEN_TO_SYMBOL = {v["token"]: k for k, v in _ANGEL_INDEX_MAP.items()}

REFRESH_INTERVAL_SECONDS = 5
CLOSED_REFRESH_SECONDS = 60

# Real-price cache, refreshed on a background thread so requests never block
# on a live network round-trip.
_price_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()
_last_refresh: datetime = datetime.min.replace(tzinfo=timezone.utc)

_refresh_thread_started = False
_refresh_thread_lock = threading.Lock()

_angelone_warned = False


def check_indian_market_open() -> Dict[str, Any]:
    """
    Checks if Indian Stock Exchanges (NSE / BSE) are currently open.
    NSE/BSE Trading Hours: Monday - Friday, 09:15 AM to 03:30 PM IST (UTC+5:30).
    """
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_offset)

    weekday = now_ist.weekday()  # 0 = Monday, 6 = Sunday
    is_weekend = weekday in [5, 6]

    current_time_minutes = now_ist.hour * 60 + now_ist.minute
    market_start_minutes = 9 * 60 + 15  # 09:15 AM
    market_end_minutes = 15 * 60 + 30   # 03:30 PM

    is_trading_hours = market_start_minutes <= current_time_minutes <= market_end_minutes
    is_open = (not is_weekend) and is_trading_hours

    status_str = "LIVE // MARKET OPEN" if is_open else "OFF-HOURS // MARKET CLOSED (Last Close Prices)"

    return {
        "is_open": is_open,
        "ist_time": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "status_text": status_str
    }


def _refresh_nse_via_angelone() -> bool:
    """Returns True if Angel One quotes were fetched and applied to the cache."""
    global _angelone_warned
    if not angelone_client.CREDENTIALS_CONFIGURED or not _ANGEL_TOKEN_MAP:
        if not _angelone_warned:
            print("[stock_service] Angel One SmartAPI not configured (missing credentials or "
                  "data/angelone_tokens.json) - falling back to yFinance for NSE prices.")
            _angelone_warned = True
        return False

    tokens = [v["token"] for v in _ANGEL_TOKEN_MAP.values()]
    try:
        quotes = angelone_client.get_quotes(tokens)
    except Exception as e:
        print(f"[stock_service] Angel One SmartAPI fetch failed ({e}); "
              f"keeping last known prices this cycle.")
        return False

    updated = {}
    for token, row in quotes.items():
        sym = _TOKEN_TO_SYMBOL.get(token)
        if not sym or row.get("ltp") is None:
            continue
        price = float(row["ltp"])
        prev_close = float(row.get("close") or price)
        change_percent = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
        updated[sym] = {
            "price": round(price, 2),
            "previous_close": round(prev_close, 2),
            "day_high": round(float(row.get("high") or price), 2),
            "day_low": round(float(row.get("low") or price), 2),
            "volume": int(row.get("volume") or 0),
            "change_percent": change_percent,
            "bid": row.get("bid"),   # real best bid/ask from the exchange order book (None when no resting orders)
            "ask": row.get("ask"),
        }

    if not updated:
        return False

    with _cache_lock:
        _price_cache.update(updated)
    return True


def _fetch_one_yf(symbol: str) -> Dict[str, Any]:
    info = yf.Ticker(symbol).fast_info
    price = float(info["lastPrice"])
    prev_close = float(info["previousClose"])
    day_high = float(info.get("dayHigh", price) or price)
    day_low = float(info.get("dayLow", price) or price)
    volume = int(info.get("lastVolume", 0) or 0)
    change_percent = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

    return {
        "price": round(price, 2),
        "previous_close": round(prev_close, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "volume": volume,
        "change_percent": change_percent,
    }


def _refresh_nse_via_yfinance() -> None:
    """Fallback path used when Angel One isn't configured or a cycle fails outright."""
    for item in ALL_NIFTY_50_STOCKS:
        sym = item["symbol"]
        try:
            data = _fetch_one_yf(sym)
        except Exception:
            continue
        with _cache_lock:
            _price_cache[sym] = data


def _refresh_indices_via_angelone() -> bool:
    """Returns True if Angel One index quotes were fetched and applied to the cache."""
    if not angelone_client.CREDENTIALS_CONFIGURED or not _ANGEL_INDEX_MAP:
        return False

    exchange_tokens: Dict[str, List[str]] = {}
    for entry in _ANGEL_INDEX_MAP.values():
        exchange_tokens.setdefault(entry["exch_seg"], []).append(entry["token"])

    try:
        quotes = angelone_client.get_quotes_multi(exchange_tokens)
    except Exception as e:
        print(f"[stock_service] Angel One index fetch failed ({e}); "
              f"keeping last known prices this cycle.")
        return False

    updated = {}
    for token, row in quotes.items():
        sym = _INDEX_TOKEN_TO_SYMBOL.get(token)
        if not sym or row.get("ltp") is None:
            continue
        price = float(row["ltp"])
        prev_close = float(row.get("close") or price)
        change_percent = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
        updated[sym] = {
            "price": round(price, 2),
            "change_percent": change_percent,
        }

    if not updated:
        return False

    with _cache_lock:
        _price_cache.update(updated)
    return True


def _refresh_indices_via_yfinance() -> None:
    for symbol, yf_ticker in _INDEX_YF_FALLBACK.items():
        try:
            data = _fetch_one_yf(yf_ticker)
        except Exception:
            continue
        with _cache_lock:
            _price_cache[symbol] = data


def _refresh_cycle() -> None:
    global _last_refresh
    if not _refresh_nse_via_angelone():
        _refresh_nse_via_yfinance()
    if not _refresh_indices_via_angelone():
        _refresh_indices_via_yfinance()
    _last_refresh = datetime.now(timezone.utc)


def _refresh_loop() -> None:
    while True:
        try:
            _refresh_cycle()
        except Exception as e:
            print(f"[stock_service] price refresh cycle failed: {e}")
        # Prices can't change while the market is closed; poll slowly so we stay well inside the API rate limit.
        time.sleep(REFRESH_INTERVAL_SECONDS if check_indian_market_open()["is_open"] else CLOSED_REFRESH_SECONDS)


def start_price_refresh_thread() -> None:
    """Starts the background 5s price-refresh loop exactly once per process."""
    global _refresh_thread_started
    with _refresh_thread_lock:
        if _refresh_thread_started:
            return
        # Populate the cache synchronously once so the first request isn't empty.
        try:
            _refresh_cycle()
        except Exception as e:
            print(f"[stock_service] initial price fetch failed: {e}")
        t = threading.Thread(target=_refresh_loop, daemon=True, name="price-refresh")
        t.start()
        _refresh_thread_started = True


def _ensure_cache_ready() -> None:
    # Safety net for callers (or tests) that hit these functions before the
    # FastAPI lifespan has started the background thread.
    if not _price_cache:
        start_price_refresh_thread()


def _get_cached(symbol: str) -> Dict[str, Any]:
    with _cache_lock:
        data = _price_cache.get(symbol)
        return dict(data) if data else None


def get_nifty50_stocks() -> List[Dict[str, Any]]:
    """
    Returns list of all Nifty 50 stocks with real prices sourced from Angel One
    SmartAPI (refreshed every 5s), falling back to yFinance if SmartAPI is
    unavailable.
    """
    _ensure_cache_ready()
    mkt_info = check_indian_market_open()

    results = []
    for item in ALL_NIFTY_50_STOCKS:
        sym = item["symbol"]
        cached = _get_cached(sym)
        if not cached:
            continue  # no data for this symbol; skip rather than fabricate a price

        price = cached["price"]
        change_percent = cached["change_percent"]
        volume = cached["volume"]
        day_high = cached["day_high"]
        day_low = cached["day_low"]

        bid, ask = cached.get("bid"), cached.get("ask")  # real order-book values or None; never estimated

        results.append({
            "ticker": sym,
            "name": item["name"],
            "sector": item["sector"],
            "price": price,
            "change_percent": change_percent,
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "day_high": day_high,
            "day_low": day_low,
            "market_open": mkt_info["is_open"]
        })

    return results


def get_global_markets() -> List[Dict[str, Any]]:
    """
    Returns the India feed: Nifty 50, Nifty Bank, and BSE Sensex, sourced from
    Angel One SmartAPI (refreshed every 5s), falling back to yFinance if
    SmartAPI is unavailable.
    """
    _ensure_cache_ready()
    mkt_info = check_indian_market_open()

    results = []
    for idx in INDIA_INDEX_ITEMS:
        sym = idx["symbol"]
        cached = _get_cached(sym)
        if not cached:
            continue

        price = cached["price"]
        change_percent = cached["change_percent"]

        results.append({
            "symbol": sym,
            "name": idx["name"],
            "category": idx["category"],
            "price": price,
            "change_percent": change_percent
        })
    return results


_TECH_CACHE: Dict[str, Any] = {}
_TECH_TTL = 60


def _rsi_wilder(close, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1])


def _macd(close, fast=12, slow=26, signal=9):
    macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(hist.iloc[-1]), float(hist.iloc[-2])


def _session_vwap(symbol: str):
    """VWAP of the most recent trading session from 5-minute bars. None if unavailable."""
    bars = yf.Ticker(symbol).history(period="5d", interval="5m")
    if bars is None or bars.empty:
        return None
    last_day = bars.index[-1].date()
    day = bars[bars.index.date == last_day]
    vol = day["Volume"].sum()
    if not vol:
        return None
    typical = (day["High"] + day["Low"] + day["Close"]) / 3
    return float((typical * day["Volume"]).sum() / vol)


def compute_detectors(ticker: str) -> Dict[str, Any]:
    """Real RSI(14, Wilder), MACD(12,26,9) from daily closes and session VWAP from 5m bars (yfinance)."""
    formatted_ticker = ticker.upper()
    if not formatted_ticker.endswith(".NS") and not formatted_ticker.startswith("^"):
        formatted_ticker += ".NS"

    hit = _TECH_CACHE.get(formatted_ticker)
    if hit and time.time() - hit[0] < _TECH_TTL:
        return hit[1]

    daily = yf.Ticker(formatted_ticker).history(period="1y", interval="1d")
    close = daily["Close"].dropna() if daily is not None and not daily.empty else None
    if close is None or len(close) < 35:
        raise ValueError(f"Not enough price history to compute indicators for {formatted_ticker}")

    _ensure_cache_ready()
    cached = _get_cached(formatted_ticker)
    price = cached["price"] if cached else float(close.iloc[-1])

    rsi_val = round(_rsi_wilder(close), 1)
    macd_line, signal_line, hist, prev_hist = _macd(close)
    try:
        vwap = _session_vwap(formatted_ticker)
    except Exception:
        vwap = None

    rsi_signal = "OVERSOLD (BULLISH)" if rsi_val < 30 else ("OVERBOUGHT (BEARISH)" if rsi_val > 70 else "NEUTRAL")
    if vwap is None:
        vwap_val, vwap_signal = 0.0, "UNAVAILABLE"
    else:
        vwap_val = round(vwap, 2)
        vwap_signal = "ABOVE VWAP (BULLISH)" if price >= vwap_val else "BELOW VWAP (BEARISH)"
    if hist >= 0:
        macd_trend = "BULLISH CROSSOVER" if prev_hist < 0 else "BULLISH"
    else:
        macd_trend = "BEARISH CROSSOVER" if prev_hist >= 0 else "BEARISH"

    result = {
        "ticker": formatted_ticker,
        "current_price": price,
        "vwap": vwap_val,
        "vwap_signal": vwap_signal,
        "rsi": rsi_val,
        "rsi_signal": rsi_signal,
        "macd": {
            "macd_line": round(macd_line, 2),
            "signal_line": round(signal_line, 2),
            "histogram": round(hist, 2),
            "histogram_pct": round(hist / price * 100, 3) if price else 0.0,
            "trend": macd_trend,
        },
        "source": "Computed from yfinance daily closes (RSI/MACD) and 5m bars (VWAP)",
    }
    _TECH_CACHE[formatted_ticker] = (time.time(), result)
    return result
