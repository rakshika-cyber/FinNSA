"""Chart series, multi-stock comparison and sector-wise aggregates (price statistics + news signal).

All price history comes from Yahoo Finance via yfinance (adjusted daily closes). News signals use the same
Google News RSS + FinBERT pipeline as the single-stock page, and share its cache, so a stock shows the same
signal everywhere.
"""
import math
import threading
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from services import company_service, news_signal
from services.stock_service import ALL_NIFTY_50_STOCKS, _get_cached, _ensure_cache_ready

_BY_SYMBOL = {s["symbol"]: s for s in ALL_NIFTY_50_STOCKS}
RANGES = {"1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504}

_cache: Dict[str, tuple] = {}
_lock = threading.Lock()


def _cached(key: str, ttl: int, loader):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    val = loader()
    with _lock:
        _cache[key] = (time.time(), val)
    return val


def _clean(x: float, nd: int = 2) -> Optional[float]:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _series(s: pd.Series, nd: int = 2) -> List[Optional[float]]:
    return [_clean(v, nd) for v in s.tolist()]


# ---------------------------------------------------------------- single stock chart
def _load_chart(symbol: str, rng: str) -> Dict[str, Any]:
    hist = yf.Ticker(symbol).history(period="3y", interval="1d")
    hist = hist.dropna(subset=["Close"]) if hist is not None else None
    if hist is None or len(hist) < 60:
        raise ValueError("Not enough price history")
    close = hist["Close"]

    # Indicators are computed on the full history first so SMA200/MACD are warmed up, then trimmed.
    sma20, sma50, sma200 = (close.rolling(n).mean() for n in (20, 50, 200))
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    std20 = close.rolling(20).std()
    daily = close.pct_change()

    n = RANGES[rng]
    sl = slice(-n, None)
    view = close.iloc[sl]
    run_max = view.cummax()
    drawdown = (view - run_max) / run_max * 100

    rets = (daily.iloc[sl].dropna() * 100)
    lo, hi = float(rets.min()), float(rets.max())
    bins = 20
    width = (hi - lo) / bins or 1.0
    counts = [0] * bins
    for r in rets:
        counts[min(bins - 1, int((r - lo) / width))] += 1
    hist_bins = [{"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2), "count": c} for i, c in enumerate(counts)]

    return {
        "ticker": symbol, "range": rng, "source": "Yahoo Finance daily bars (adjusted); indicators computed",
        "dates": [d.strftime("%Y-%m-%d") for d in view.index],
        "open": _series(hist["Open"].iloc[sl]), "high": _series(hist["High"].iloc[sl]),
        "low": _series(hist["Low"].iloc[sl]), "close": _series(view), "volume": [int(v) for v in hist["Volume"].iloc[sl]],
        "sma20": _series(sma20.iloc[sl]), "sma50": _series(sma50.iloc[sl]), "sma200": _series(sma200.iloc[sl]),
        "bb_upper": _series((sma20 + 2 * std20).iloc[sl]), "bb_lower": _series((sma20 - 2 * std20).iloc[sl]),
        "rsi": _series(rsi.iloc[sl], 1), "macd": _series(macd.iloc[sl], 3), "macd_signal": _series(macd_sig.iloc[sl], 3),
        "macd_hist": _series((macd - macd_sig).iloc[sl], 3), "drawdown": _series(drawdown),
        "returns_histogram": {"bins": hist_bins, "mean": round(float(rets.mean()), 3), "std": round(float(rets.std()), 3),
                              "skew": round(float(rets.skew()), 3), "kurtosis": round(float(rets.kurt()), 3), "n": int(len(rets))},
    }


def get_chart(symbol: str, rng: str = "1y") -> Dict[str, Any]:
    if rng not in RANGES:
        raise ValueError(f"range must be one of {list(RANGES)}")
    return _cached(f"chart:{symbol}:{rng}", 600, lambda: _load_chart(symbol, rng))


# ---------------------------------------------------------------- multi-stock comparison
def _closes(symbols: List[str], period: str = "2y") -> pd.DataFrame:
    key = f"closes:{','.join(sorted(symbols))}:{period}"

    def load():
        df = yf.download(symbols, period=period, interval="1d", auto_adjust=True, progress=False, threads=True)["Close"]
        if isinstance(df, pd.Series):
            df = df.to_frame(symbols[0])
        return df.dropna(how="all")
    return _cached(key, 900, load)


def compare(symbols: List[str], rng: str = "6mo") -> Dict[str, Any]:
    if rng not in RANGES:
        raise ValueError(f"range must be one of {list(RANGES)}")
    if not 2 <= len(symbols) <= 8:
        raise ValueError("Pick between 2 and 8 stocks")
    df = _closes(symbols).iloc[-RANGES[rng]:].dropna(axis=1, how="all")
    df = df.dropna()  # common dates only, so every line starts together
    if len(df) < 20:
        raise ValueError("Not enough overlapping price history")
    norm = df / df.iloc[0] * 100
    rets = df.pct_change().dropna()
    corr = rets.corr()
    rows = []
    for s in df.columns:
        r = rets[s]
        dd = ((df[s] - df[s].cummax()) / df[s].cummax()).min() * 100
        ann_ret = (df[s].iloc[-1] / df[s].iloc[0]) ** (252 / len(df)) - 1
        vol = r.std() * math.sqrt(252)
        rows.append({"ticker": s, "name": _BY_SYMBOL.get(s, {}).get("name"), "sector": _BY_SYMBOL.get(s, {}).get("sector"),
                     "return_pct": _clean((df[s].iloc[-1] / df[s].iloc[0] - 1) * 100),
                     "volatility_pct": _clean(vol * 100), "max_drawdown_pct": _clean(dd),
                     "return_over_vol": _clean(ann_ret / vol if vol else None, 2)})
    return {
        "range": rng, "source": "Yahoo Finance adjusted daily closes; metrics computed",
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "series": {s: _series(norm[s]) for s in norm.columns},
        "stats": rows,
        "correlation": {"tickers": list(corr.columns), "matrix": [[_clean(v, 3) for v in row] for row in corr.values.tolist()]},
        "note": "Series rebased to 100 at the first common date. return_over_vol = annualised return / annualised volatility (not a Sharpe ratio; no risk-free rate).",
    }


# ---------------------------------------------------------------- sectors + news
_news_state = {"running": False, "done": 0, "total": 0}
_news_scores: Dict[str, Dict[str, Any]] = {}
_news_ts: Dict[str, float] = {}
NEWS_TTL = 600


def scored_news(symbol: str) -> Dict[str, Any]:
    """Single source of truth for a stock's news signal (shared by stock page and sector view)."""
    entry = _BY_SYMBOL[symbol]
    news = company_service.get_news(entry["name"])
    return {"ticker": symbol, "name": entry["name"], **news_signal.score_headlines(news)}


def _news_worker(symbols: List[str]) -> None:
    for s in symbols:
        try:
            r = scored_news(s)
            _news_scores[s] = {"signal": r["signal"], "score": r["score"], "count": r["count"]}
            _news_ts[s] = time.time()
        except Exception:
            _news_scores[s] = {"signal": "ERROR", "score": None, "count": 0}
            _news_ts[s] = time.time()
        _news_state["done"] += 1
    _news_state["running"] = False


def _ensure_news() -> None:
    stale = [s["symbol"] for s in ALL_NIFTY_50_STOCKS if time.time() - _news_ts.get(s["symbol"], 0) > NEWS_TTL]
    with _lock:
        if _news_state["running"] or not stale:
            return
        _news_state.update(running=True, done=0, total=len(stale))
    threading.Thread(target=_news_worker, args=(stale,), daemon=True, name="sector-news").start()


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 5:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 3) if sx and sy else None


def sector_overview() -> Dict[str, Any]:
    _ensure_news()
    _ensure_cache_ready()
    symbols = [s["symbol"] for s in ALL_NIFTY_50_STOCKS]
    closes = _closes(symbols, "1y")

    def ret(sym: str, days: int) -> Optional[float]:
        if sym not in closes.columns:
            return None
        c = closes[sym].dropna()
        return _clean((c.iloc[-1] / c.iloc[-1 - days] - 1) * 100) if len(c) > days else None

    stocks = []
    for it in ALL_NIFTY_50_STOCKS:
        sym = it["symbol"]
        px = _get_cached(sym) or {}
        news = _news_scores.get(sym)
        stocks.append({"ticker": sym.replace(".NS", ""), "name": it["name"], "sector": it["sector"],
                       "day_pct": px.get("change_percent"), "ret_1m": ret(sym, 21), "ret_3m": ret(sym, 63),
                       "news_score": news["score"] if news else None, "news_signal": news["signal"] if news else None})

    def avg(vals):
        v = [x for x in vals if x is not None]
        return round(sum(v) / len(v), 3) if v else None

    sectors = []
    for sec in sorted({s["sector"] for s in stocks}):
        g = [s for s in stocks if s["sector"] == sec]
        scored = [s for s in g if s["news_score"] is not None]
        sectors.append({
            "sector": sec, "count": len(g), "avg_day_pct": avg([s["day_pct"] for s in g]),
            "avg_ret_1m": avg([s["ret_1m"] for s in g]), "avg_ret_3m": avg([s["ret_3m"] for s in g]),
            "avg_news_score": avg([s["news_score"] for s in scored]), "news_covered": len(scored),
            "bullish": sum(1 for s in scored if s["news_signal"] == "BULLISH"),
            "neutral": sum(1 for s in scored if s["news_signal"] == "NEUTRAL"),
            "bearish": sum(1 for s in scored if s["news_signal"] == "BEARISH"),
        })
    pairs = [(s["news_score"], s["ret_1m"]) for s in stocks if s["news_score"] is not None and s["ret_1m"] is not None]
    return {
        "sectors": sectors, "stocks": stocks,
        "news_progress": dict(_news_state),
        "correlation_news_vs_1m_return": {"r": _pearson([p[0] for p in pairs], [p[1] for p in pairs]), "n": len(pairs)},
        "note": "News score = recency-weighted FinBERT sentiment of recent headlines (-1..+1). Returns are trailing price returns, "
                "so the correlation shows whether sentiment and past performance agree, not that news predicts future moves. "
                "Sector tags are this app's own groupings.",
        "source": "Prices: Yahoo Finance / Angel One. News: Google News RSS scored by FinBERT.",
    }
