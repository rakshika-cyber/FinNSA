from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from typing import Optional

from services import angelone_client, company_service, derivatives_service, market_service

router = APIRouter(prefix="/company", tags=["Company Detail"])


def _resolve(ticker: str) -> Dict[str, str]:
    entry = company_service.normalize_ticker(ticker)
    if not entry:
        raise HTTPException(status_code=404, detail=f"{ticker} is not a Nifty 50 ticker.")
    return entry


@router.get("/{ticker}/fundamentals", response_model=Dict[str, Any])
def fundamentals(ticker: str):
    entry = _resolve(ticker)
    try:
        return company_service.get_fundamentals(entry["symbol"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fundamentals source failed: {e}")


@router.get("/{ticker}/news-signal", response_model=Dict[str, Any])
def news_sentiment_signal(ticker: str):
    entry = _resolve(ticker)
    try:
        return market_service.scored_news(entry["symbol"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"News signal failed: {e}")


def _guard(fn, *args):
    try:
        return fn(*args)
    except angelone_client.NotConnected as e:
        raise HTTPException(status_code=503, detail=str(e), headers={"X-Broker": "not-connected"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream data source failed: {e}")


@router.get("/{ticker}/governance", response_model=Dict[str, Any])
def governance(ticker: str):
    return _guard(company_service.get_governance, _resolve(ticker)["symbol"])


@router.get("/{ticker}/statistics", response_model=Dict[str, Any])
def statistics(ticker: str):
    return _guard(company_service.get_statistics, _resolve(ticker)["symbol"])


@router.get("/{ticker}/option-chain", response_model=Dict[str, Any])
def option_chain(ticker: str, expiry: Optional[str] = None):
    return _guard(derivatives_service.get_option_chain, _resolve(ticker)["symbol"], expiry)


@router.get("/{ticker}/futures", response_model=list)
def futures(ticker: str):
    return _guard(derivatives_service.get_futures, _resolve(ticker)["symbol"])


@router.get("/{ticker}/depth", response_model=Dict[str, Any])
def depth(ticker: str):
    return _guard(derivatives_service.get_depth, _resolve(ticker)["symbol"])
