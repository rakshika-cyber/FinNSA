from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from services.stock_service import get_nifty50_stocks, get_global_markets, compute_detectors, check_indian_market_open

router = APIRouter(tags=["Stocks & Market Feeds"])

@router.get("/stocks/status", response_model=Dict[str, Any])
def get_market_status():
    """
    Returns real-time status of Indian Stock Exchanges (NSE / BSE) and IST timestamp.
    """
    return check_indian_market_open()

@router.get("/stocks", response_model=List[Dict[str, Any]])
def list_stocks():
    """
    List all 50 Nifty 50 stocks. Returns the latest real quotes (refreshed every 5s from Angel One, yFinance fallback).
    """
    try:
        return get_nifty50_stocks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stock data: {str(e)}")

@router.get("/stocks/global", response_model=List[Dict[str, Any]])
def list_global_markets():
    """
    Returns top global markets (NASDAQ, NYSE, Bitcoin, Ethereum).
    Returns the latest real index quotes.
    """
    try:
        return get_global_markets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching global markets: {str(e)}")

@router.get("/detectors/{ticker}", response_model=Dict[str, Any])
def get_detectors(ticker: str):
    """
    Returns technical detectors (VWAP, MACD, RSI) for a specific Nifty 50 ticker.
    """
    try:
        return compute_detectors(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating technical indicators for {ticker}: {str(e)}")
