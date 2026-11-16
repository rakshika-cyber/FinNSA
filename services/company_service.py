"""Per-company data: fundamentals (yfinance) and recent news headlines (Google News RSS).

No API keys are required for either source.
"""
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
import yfinance as yf

from services.stock_service import ALL_NIFTY_50_STOCKS

_BY_SYMBOL = {s["symbol"]: s for s in ALL_NIFTY_50_STOCKS}

_CACHE: Dict[str, tuple] = {}
_CACHE_LOCK = threading.Lock()
FUNDAMENTALS_TTL = 6 * 3600   # fundamentals move slowly
NEWS_TTL = 10 * 60


def normalize_ticker(ticker: str) -> Optional[Dict[str, str]]:
    """Returns the Nifty 50 entry for a ticker, or None. Restricting to the known
    list keeps this endpoint from being used to query arbitrary symbols."""
    sym = ticker.upper()
    if not sym.endswith(".NS"):
        sym += ".NS"
    return _BY_SYMBOL.get(sym)


def _cached(key: str, ttl: int, loader):
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = loader()
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # drop NaN
    except (TypeError, ValueError):
        return None


def _statement_series(df, row_names: List[str]) -> List[Dict[str, Any]]:
    """Pulls the first matching row from a yfinance statement as [{period, value}] oldest-first."""
    if df is None or getattr(df, "empty", True):
        return []
    for name in row_names:
        if name in df.index:
            series = df.loc[name].dropna()
            out = [{"period": c.strftime("%Y-%m-%d"), "value": _num(v)} for c, v in series.items()]
            return sorted(out, key=lambda r: r["period"])
    return []


def _load_fundamentals(symbol: str) -> Dict[str, Any]:
    t = yf.Ticker(symbol)
    info = t.info or {}
    try:
        annual = t.income_stmt
    except Exception:
        annual = None
    try:
        quarterly = t.quarterly_income_stmt
    except Exception:
        quarterly = None

    rev_names = ["Total Revenue", "Operating Revenue"]
    ni_names = ["Net Income", "Net Income Common Stockholders"]

    return {
        "ticker": symbol,
        "source": "Yahoo Finance via yfinance (aggregated from company filings)",
        "profile": {
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "summary": info.get("longBusinessSummary"),
        },
        "valuation": {
            "market_cap": _num(info.get("marketCap")),
            "pe_trailing": _num(info.get("trailingPE")),
            "pe_forward": _num(info.get("forwardPE")),
            "price_to_book": _num(info.get("priceToBook")),
            "dividend_yield_pct": _num(info.get("dividendYield")),
            "eps_trailing": _num(info.get("trailingEps")),
            "beta": _num(info.get("beta")),
            "week52_high": _num(info.get("fiftyTwoWeekHigh")),
            "week52_low": _num(info.get("fiftyTwoWeekLow")),
        },
        "financials": {
            "total_revenue_ttm": _num(info.get("totalRevenue")),
            "revenue_growth": _num(info.get("revenueGrowth")),
            "earnings_growth": _num(info.get("earningsGrowth")),
            "profit_margin": _num(info.get("profitMargins")),
            "operating_margin": _num(info.get("operatingMargins")),
            "return_on_equity": _num(info.get("returnOnEquity")),
            "debt_to_equity": _num(info.get("debtToEquity")),
            "revenue_annual": _statement_series(annual, rev_names),
            "net_income_annual": _statement_series(annual, ni_names),
            "revenue_quarterly": _statement_series(quarterly, rev_names),
            "net_income_quarterly": _statement_series(quarterly, ni_names),
        },
        "currency": info.get("financialCurrency") or "INR",
    }


def get_fundamentals(symbol: str) -> Dict[str, Any]:
    return _cached(f"fund:{symbol}", FUNDAMENTALS_TTL, lambda: _load_fundamentals(symbol))


def _load_news(company_name: str, limit: int) -> List[Dict[str, Any]]:
    q = quote_plus(f'"{company_name}" stock when:14d')
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items, seen = [], set()
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        source_el = it.find("source")
        source = source_el.text if source_el is not None else None
        # Google appends " - Publisher" to the headline; strip it for cleaner scoring.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        try:
            published = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            published = datetime.now(timezone.utc)
        items.append({
            "title": title,
            "link": it.findtext("link"),
            "source": source,
            "published": published.isoformat(),
        })
        if len(items) >= limit:
            break
    return items


def get_news(company_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    return _cached(f"news:{company_name}:{limit}", NEWS_TTL, lambda: _load_news(company_name, limit))


# ---------------------------------------------------------------- governance / people
def _load_governance(symbol: str) -> Dict[str, Any]:
    t = yf.Ticker(symbol)
    info = t.info or {}
    officers = []
    for o in info.get("companyOfficers") or []:
        officers.append({
            "name": o.get("name"), "title": o.get("title"), "age": o.get("age"),
            "year_born": o.get("yearBorn"), "total_pay_inr": _num(o.get("totalPay")),
            "fiscal_year": o.get("fiscalYear"),
        })
    base = symbol.replace(".NS", "")
    return {
        "ticker": symbol,
        "source": "Yahoo Finance via yfinance (executive officers & holder summary)",
        "scope_note": "Lists key executive officers only. Independent/non-executive directors and the full "
                      "board are NOT included; use the official NSE/BSE links for the complete board and "
                      "shareholding pattern.",
        "officers": officers,
        "holders": {
            "insiders_pct": _num(info.get("heldPercentInsiders")),
            "institutions_pct": _num(info.get("heldPercentInstitutions")),
        },
        "analysts": {
            "recommendation": info.get("recommendationKey"),
            "count": info.get("numberOfAnalystOpinions"),
            "target_mean": _num(info.get("targetMeanPrice")),
            "target_high": _num(info.get("targetHighPrice")),
            "target_low": _num(info.get("targetLowPrice")),
        },
        "official_links": {
            "nse_company": f"https://www.nseindia.com/get-quotes/equity?symbol={quote_plus(base)}",
            "bse_search": "https://www.bseindia.com/corporates/List_Scrips.html",
        },
    }


def get_governance(symbol: str) -> Dict[str, Any]:
    return _cached(f"gov:{symbol}", FUNDAMENTALS_TTL, lambda: _load_governance(symbol))


# ---------------------------------------------------------------- price statistics
def _load_statistics(symbol: str) -> Dict[str, Any]:
    import math
    hist = yf.Ticker(symbol).history(period="2y", interval="1d")
    close = hist["Close"].dropna() if hist is not None and not hist.empty else None
    if close is None or len(close) < 60:
        raise ValueError("Not enough price history")
    last = float(close.iloc[-1])

    def ret(days: int) -> Optional[float]:
        return round((last / float(close.iloc[-1 - days]) - 1) * 100, 2) if len(close) > days else None

    daily = close.pct_change().dropna()
    year = close.iloc[-252:]
    run_max = year.cummax()
    drawdown = float(((year - run_max) / run_max).min()) * 100
    vol_20 = float(daily.iloc[-20:].std()) * math.sqrt(252) * 100
    vol_252 = float(daily.iloc[-252:].std()) * math.sqrt(252) * 100
    vol = hist["Volume"].dropna()
    return {
        "ticker": symbol,
        "source": "Computed from Yahoo Finance daily closes (dividend/split adjusted)",
        "returns_pct": {"1M": ret(21), "3M": ret(63), "6M": ret(126), "1Y": ret(252)},
        "volatility_annualised_pct": {"20D": round(vol_20, 2), "1Y": round(vol_252, 2)},
        "max_drawdown_1y_pct": round(drawdown, 2),
        "sma_50": round(float(close.iloc[-50:].mean()), 2),
        "sma_200": round(float(close.iloc[-200:].mean()), 2) if len(close) >= 200 else None,
        "week52_high": round(float(year.max()), 2),
        "week52_low": round(float(year.min()), 2),
        "avg_volume_20d": int(vol.iloc[-20:].mean()) if len(vol) >= 20 else None,
        "last_close": round(last, 2),
    }


def get_statistics(symbol: str) -> Dict[str, Any]:
    return _cached(f"stats:{symbol}", 3600, lambda: _load_statistics(symbol))
