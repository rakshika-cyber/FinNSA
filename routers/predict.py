from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from ml.predictor import predict_stock_direction

router = APIRouter(tags=["Multi-Modal Stock Prediction"])

class PredictRequest(BaseModel):
    english_text: Optional[str] = Field(None, example="Company revenue grew 18% with positive margin expansion.")
    hinglish_text: Optional[str] = Field(None, example="Management commentary bullish hai, naye orders se profit badhega.")

@router.post("/predict/{ticker}", response_model=Dict[str, Any])
def predict_ticker_direction(ticker: str, request: Request, payload: Optional[PredictRequest] = None):
    """
    Combines technical indicators (VWAP, MACD, RSI) with PyTorch BCGF fused sentiment 
    to forecast stock direction (UP/DOWN) and confidence score.
    """
    eng_text = payload.english_text if payload else None
    hing_text = payload.hinglish_text if payload else None

    try:
        sentiment_engine = getattr(request.app.state, "sentiment_engine", None)
        if not sentiment_engine:
            raise HTTPException(status_code=500, detail="Sentiment Engine model is not initialized in app state.")
            
        prediction = predict_stock_direction(
            ticker=ticker,
            sentiment_engine=sentiment_engine,
            english_text=eng_text,
            hinglish_text=hing_text
        )
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed for ticker {ticker}: {str(e)}")
