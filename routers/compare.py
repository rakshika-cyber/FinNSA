from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from services import company_service, market_service

router = APIRouter(tags=["Charts & Comparison"])


def _guard(fn, *args):
    try:
        return fn(*args)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data source failed: {e}")


@router.get("/company/{ticker}/chart", response_model=Dict[str, Any])
def chart(ticker: str, range: str = Query("1y")):
    entry = company_service.normalize_ticker(ticker)
    if not entry:
        raise HTTPException(status_code=404, detail=f"{ticker} is not a Nifty 50 ticker.")
    return _guard(market_service.get_chart, entry["symbol"], range)


@router.get("/compare", response_model=Dict[str, Any])
def compare(tickers: str = Query(..., description="Comma-separated Nifty 50 tickers, 2-8"), range: str = Query("6mo")):
    symbols = []
    for t in tickers.split(","):
        entry = company_service.normalize_ticker(t.strip())
        if not entry:
            raise HTTPException(status_code=404, detail=f"{t} is not a Nifty 50 ticker.")
        if entry["symbol"] not in symbols:
            symbols.append(entry["symbol"])
    return _guard(market_service.compare, symbols, range)


@router.get("/compare/sectors", response_model=Dict[str, Any])
def sectors():
    return _guard(market_service.sector_overview)
