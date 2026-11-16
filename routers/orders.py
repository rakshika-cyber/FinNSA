"""Order tickets.

IMPORTANT: nothing here is sent to a broker. Orders are validated against the live price and recorded in the
local `order_intents` table as RECORDED_NOT_SENT. Routing to Angel One's order API is deliberately not wired up;
it moves real money and needs an explicit decision (static-IP whitelisting, risk limits, SEBI/exchange rules).
"""
import sqlite3
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import database
from services import company_service
from services.stock_service import _ensure_cache_ready, _get_cached

router = APIRouter(prefix="/orders", tags=["Order Tickets (not sent to broker)"])
MAX_QTY = 100000


class OrderRequest(BaseModel):
    ticker: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    quantity: int = Field(..., ge=1, le=MAX_QTY)
    limit_price: Optional[float] = Field(None, gt=0)


@router.post("", response_model=Dict[str, Any])
def create_order_intent(order: OrderRequest):
    entry = company_service.normalize_ticker(order.ticker)
    if not entry:
        raise HTTPException(status_code=404, detail=f"{order.ticker} is not a Nifty 50 ticker.")
    _ensure_cache_ready()
    quote = _get_cached(entry["symbol"])
    if not quote:
        raise HTTPException(status_code=503, detail="No live price available; cannot validate the order.")
    ref = quote["price"]

    if order.order_type == "LIMIT":
        if order.limit_price is None:
            raise HTTPException(status_code=422, detail="Limit orders need a limit price.")
        if abs(order.limit_price / ref - 1) > 0.20:
            raise HTTPException(status_code=422, detail=f"Limit price ₹{order.limit_price} is more than 20% away from last price ₹{ref}.")

    conn = sqlite3.connect(database.DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO order_intents (ticker, side, order_type, quantity, limit_price, reference_price, status) VALUES (?,?,?,?,?,?,?)",
            (entry["symbol"], order.side, order.order_type, order.quantity, order.limit_price, ref, "RECORDED_NOT_SENT"))
        conn.commit()
        oid = cur.lastrowid
    finally:
        conn.close()

    price = order.limit_price if order.order_type == "LIMIT" else ref
    return {
        "id": oid, "status": "RECORDED_NOT_SENT", "sent_to_broker": False,
        "ticker": entry["symbol"], "side": order.side, "order_type": order.order_type, "quantity": order.quantity,
        "reference_price": ref, "estimated_value": round(price * order.quantity, 2),
        "message": "Order validated and recorded locally. It was NOT sent to any broker or exchange.",
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_order_intents(limit: int = 50):
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM order_intents ORDER BY id DESC LIMIT ?", (min(limit, 200),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
