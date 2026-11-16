"""Broker (Angel One SmartAPI) connection management.

Security model
  * Local only: requests must come from loopback and, if an Origin header is present, from a localhost origin.
    (The dev server may listen on 0.0.0.0 and the app has other open endpoints; credentials must never be
    settable from another machine or from a random website open in the user's browser.)
  * Secrets are write-only: they are never returned by any endpoint and never logged.
  * A failed attempt never replaces working credentials; only a successful login is committed.
  * Optionally persisted to the git-ignored .env file (plain text, mode 600).
"""
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from services import angelone_client, stock_service

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
_SAFE = re.compile(r"^[^\s'\"#\\$`]{3,128}$")   # no whitespace/quotes/#/\/$ so it is safe in an unquoted .env value
FRESH_SECONDS = 900


def local_only(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Broker settings can only be changed from this machine.")
    origin = request.headers.get("origin")
    if origin and urlparse(origin).hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Cross-site requests are not allowed.")


router = APIRouter(prefix="/broker", tags=["Broker Connection"], dependencies=[Depends(local_only)])


class ConnectRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=128)
    client_id: str = Field(..., min_length=1, max_length=64)
    pin: str = Field(..., min_length=1, max_length=64)
    totp_secret: str = Field(..., min_length=1, max_length=128)
    persist: bool = True


class DisconnectRequest(BaseModel):
    forget: bool = False


def _persist_env(values: Dict[str, Optional[str]]) -> None:
    """Sets/removes keys in .env, keeping every other line. Atomic write, owner-only permissions."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values:
            seen.add(key)
            if values[key] is not None:
                out.append(f"{key}={values[key]}")
        else:
            out.append(line)
    for key, val in values.items():
        if key not in seen and val is not None:
            out.append(f"{key}={val}")
    fd, tmp = tempfile.mkstemp(dir=str(ENV_PATH.parent), prefix=".env.")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_PATH)


def _status() -> Dict[str, Any]:
    st = angelone_client.STATE
    now = time.time()
    if not angelone_client.CREDENTIALS_CONFIGURED:
        state = "NOT_CONNECTED"
    elif st["last_ok"] and now - st["last_ok"] < FRESH_SECONDS:
        state = "CONNECTED"
    elif st["last_error"]:
        state = "ERROR"
    else:
        state = "CONNECTING"
    return {
        "state": state,
        "broker": "Angel One SmartAPI",
        "client": angelone_client.client_hint(),
        "last_ok_seconds_ago": round(now - st["last_ok"]) if st["last_ok"] else None,
        "last_error": st["last_error"] if state in ("ERROR", "CONNECTING") else None,
        "fallback": None if state == "CONNECTED" else "Yahoo Finance (delayed prices; no order-book depth, futures or option chain)",
    }


@router.get("/status", response_model=Dict[str, Any])
def status():
    return _status()


@router.post("/connect", response_model=Dict[str, Any])
def connect(req: ConnectRequest):
    api_key, client_id, pin, totp = (v.strip() for v in (req.api_key, req.client_id, req.pin, req.totp_secret))
    totp = totp.replace(" ", "").upper()
    for label, val in (("API key", api_key), ("Client code", client_id), ("PIN", pin), ("TOTP secret", totp)):
        if not _SAFE.match(val):
            raise HTTPException(status_code=422, detail=f"{label} looks invalid (no spaces, quotes or # allowed).")
    try:
        pyotp.TOTP(totp).now()
    except Exception:
        raise HTTPException(status_code=422, detail="TOTP secret is not valid base32. Use the text shown under the QR code, not a 6-digit code.")

    try:
        conn = angelone_client.test_login(api_key, client_id, pin, totp)   # nothing stored yet
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    angelone_client.set_credentials(api_key, client_id, pin, totp)
    angelone_client.adopt_session(conn)
    stock_service._angelone_warned = False
    threading.Thread(target=stock_service._refresh_cycle, daemon=True, name="post-connect-refresh").start()

    saved = False
    if req.persist:
        try:
            _persist_env({"SMARTAPI_KEY": api_key, "SMARTAPI_CLIENT_ID": client_id,
                          "SMARTAPI_PASSWORD": pin, "SMARTAPI_TOTP_SECRET": totp})
            saved = True
        except OSError:
            saved = False
    return {**_status(), "saved_to_env": saved, "message": "Connected. Live prices, depth, futures and options now use Angel One."}


@router.post("/disconnect", response_model=Dict[str, Any])
def disconnect(req: DisconnectRequest):
    angelone_client.clear_credentials()
    forgotten = False
    if req.forget:
        try:
            _persist_env({"SMARTAPI_KEY": None, "SMARTAPI_CLIENT_ID": None, "SMARTAPI_PASSWORD": None, "SMARTAPI_TOTP_SECRET": None})
            forgotten = True
        except OSError:
            forgotten = False
    return {**_status(), "forgotten": forgotten,
            "message": "Disconnected." + (" Saved credentials were removed from .env." if forgotten else " Saved credentials in .env were kept (they reload on restart).")}
