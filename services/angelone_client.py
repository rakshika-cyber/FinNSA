"""
Thin wrapper around Angel One's SmartAPI for fetching NSE equity quotes.

Auth model: SmartAPI login (clientCode + password/PIN + TOTP) returns a JWT
that expires; we re-login transparently whenever a call fails with an auth
error. Quotes are fetched in batches via getMarketData so refreshing ~49
tickers costs one HTTP call instead of 49.
"""
import os
import re
import threading
import time
from typing import Dict, List, Optional

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect

load_dotenv()

SMARTAPI_KEY = os.getenv("SMARTAPI_KEY")
SMARTAPI_CLIENT_ID = os.getenv("SMARTAPI_CLIENT_ID")
SMARTAPI_PASSWORD = os.getenv("SMARTAPI_PASSWORD")
SMARTAPI_TOTP_SECRET = os.getenv("SMARTAPI_TOTP_SECRET")

CREDENTIALS_CONFIGURED = all(
    [SMARTAPI_KEY, SMARTAPI_CLIENT_ID, SMARTAPI_PASSWORD, SMARTAPI_TOTP_SECRET]
)

class NotConnected(RuntimeError):
    """No SmartAPI credentials configured (distinct from an upstream failure)."""


_lock = threading.Lock()
_client: Optional[SmartConnect] = None

# Connection health, surfaced in the UI header via /broker/status. Never holds secrets.
STATE = {"last_ok": None, "last_error": None}


def _mark_ok() -> None:
    STATE.update(last_ok=time.time(), last_error=None)


def _safe(e: Exception) -> str:
    """Short error text safe to show in the UI (SmartAPI errors can echo request headers incl. the API key)."""
    msg = re.sub(r"(?i)(x-privatekey|api[_-]?key|password|totp)['\"]?\s*[:=]\s*['\"]?[^,'\"}\s]+", r"\1=<hidden>", str(e))
    return f"{type(e).__name__}: {msg}"[:160]


def _mark_fail(e: Exception) -> None:
    STATE["last_error"] = _safe(e)


def set_credentials(api_key: str, client_id: str, pin: str, totp_secret: str) -> None:
    global SMARTAPI_KEY, SMARTAPI_CLIENT_ID, SMARTAPI_PASSWORD, SMARTAPI_TOTP_SECRET, CREDENTIALS_CONFIGURED
    SMARTAPI_KEY, SMARTAPI_CLIENT_ID, SMARTAPI_PASSWORD, SMARTAPI_TOTP_SECRET = api_key, client_id, pin, totp_secret
    CREDENTIALS_CONFIGURED = True


def clear_credentials() -> None:
    global SMARTAPI_KEY, SMARTAPI_CLIENT_ID, SMARTAPI_PASSWORD, SMARTAPI_TOTP_SECRET, CREDENTIALS_CONFIGURED, _client
    SMARTAPI_KEY = SMARTAPI_CLIENT_ID = SMARTAPI_PASSWORD = SMARTAPI_TOTP_SECRET = None
    CREDENTIALS_CONFIGURED = False
    with _lock:
        _client = None
    STATE.update(last_ok=None, last_error=None)


def adopt_session(conn: SmartConnect) -> None:
    global _client
    with _lock:
        _client = conn
    _mark_ok()


def test_login(api_key: str, client_id: str, pin: str, totp_secret: str) -> SmartConnect:
    """Logs in with the given credentials WITHOUT touching the stored ones. Raises ValueError(message) on failure."""
    try:
        conn = SmartConnect(api_key=api_key)
        session = conn.generateSession(client_id, pin, pyotp.TOTP(totp_secret).now())
    except Exception as e:
        raise ValueError(f"Could not reach Angel One: {_safe(e)}")
    if not session or not session.get("status"):
        raise ValueError(f"Angel One rejected the login: {(session or {}).get('message') or 'unknown error'}")
    return conn


def client_hint() -> Optional[str]:
    """Masked client code for display, e.g. 'A***56'."""
    c = SMARTAPI_CLIENT_ID
    if not c:
        return None
    return c[0] + "***" + c[-2:] if len(c) > 4 else "***"

# SmartAPI rejects bursts ("exceeding access rate"). All market-data calls go through
# this throttle so the 5s price refresher and on-demand option-chain requests share one budget.
_MIN_CALL_INTERVAL = 1.1
_throttle_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    with _throttle_lock:
        wait = _MIN_CALL_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _login() -> SmartConnect:
    conn = SmartConnect(api_key=SMARTAPI_KEY)
    totp = pyotp.TOTP(SMARTAPI_TOTP_SECRET).now()
    session = conn.generateSession(SMARTAPI_CLIENT_ID, SMARTAPI_PASSWORD, totp)
    if not session or not session.get("status"):
        raise RuntimeError(f"Angel One SmartAPI login failed: {(session or {}).get('message')}")
    return conn


def _get_client(force_relogin: bool = False) -> SmartConnect:
    global _client
    with _lock:
        if _client is None or force_relogin:
            _client = _login()
        return _client


def get_quotes(tokens: List[str], exchange: str = "NSE") -> Dict[str, dict]:
    """
    Fetch LTP/OHLC/volume for a batch of symbol tokens on a single exchange.
    Returns {token: {ltp, open, high, low, close, volume}}.
    Raises on total failure (caller decides whether to fall back).
    """
    return get_quotes_multi({exchange: tokens})


def get_quotes_multi(exchange_tokens: Dict[str, List[str]]) -> Dict[str, dict]:
    """
    Fetch LTP/OHLC/volume for a batch of symbol tokens, grouped by exchange
    segment (e.g. {"NSE": [...], "BSE": [...]}).
    Returns {token: {ltp, open, high, low, close, volume}}.
    Raises on total failure (caller decides whether to fall back).
    """
    if not CREDENTIALS_CONFIGURED:
        raise NotConnected("Angel One is not connected - press G (or click the BROKER button) to connect your SmartAPI account")

    def _fetch(conn: SmartConnect) -> dict:
        out: Dict[str, dict] = {}
        # SmartAPI caps symbols per request; chunk defensively.
        chunk_size = 50
        for exchange, tokens in exchange_tokens.items():
            if not tokens:
                continue
            for i in range(0, len(tokens), chunk_size):
                chunk = tokens[i:i + chunk_size]
                _throttle()
                resp = conn.getMarketData(mode="FULL", exchangeTokens={exchange: chunk})
                if not resp or not resp.get("status"):
                    raise RuntimeError(f"Angel One getMarketData failed: {resp}")
                for row in resp.get("data", {}).get("fetched", []):
                    token = row.get("symbolToken")
                    if not token:
                        continue
                    depth = row.get("depth") or {}
                    best = lambda side: next((l["price"] for l in depth.get(side, []) if l.get("price")), None)
                    out[token] = {
                        "bid": best("buy"), "ask": best("sell"),
                        "ltp": row.get("ltp"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("tradeVolume", 0),
                    }
        return out

    try:
        out = _fetch(_get_client())
        _mark_ok()
        return out
    except Exception:
        # Session likely expired - force a fresh login once and retry.
        try:
            out = _fetch(_get_client(force_relogin=True))
            _mark_ok()
            return out
        except Exception as e:
            _mark_fail(e)
            raise


def get_full_quotes(exchange: str, tokens: List[str]) -> List[dict]:
    """Raw FULL-mode rows (LTP, OI, volume, 5-level depth, exchange timestamps) for one exchange."""
    if not CREDENTIALS_CONFIGURED:
        raise NotConnected("Angel One is not connected - press G (or click the BROKER button) to connect your SmartAPI account")

    def _fetch(conn: SmartConnect) -> List[dict]:
        rows: List[dict] = []
        for i in range(0, len(tokens), 50):
            _throttle()
            resp = conn.getMarketData(mode="FULL", exchangeTokens={exchange: tokens[i:i + 50]})
            if not resp or not resp.get("status"):
                raise RuntimeError(f"Angel One getMarketData failed: {resp}")
            rows.extend(resp.get("data", {}).get("fetched", []))
        return rows

    try:
        out = _fetch(_get_client())
        _mark_ok()
        return out
    except Exception:
        try:
            out = _fetch(_get_client(force_relogin=True))
            _mark_ok()
            return out
        except Exception as e:
            _mark_fail(e)
            raise
