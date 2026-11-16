from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any

router = APIRouter(tags=["News Sentiment Analysis"])

class SentimentRequest(BaseModel):
    english_text: str = Field(..., example="Reliance Industries quarterly net profit jumps 15% exceeding estimates.")
    hinglish_text: str = Field(..., example="Reliance ka result shandar aaya hai, stock me aaj achhi tezi dekhne ko mil sakti hai.")

@router.post("/sentiment", response_model=Dict[str, Any])
def analyze_sentiment(payload: SentimentRequest, request: Request):
    """
    Takes English + Hinglish financial news text, runs FinBERT (English) and MuRIL/HingBERT (Hinglish)
    branches, and fuses them via PyTorch Bilinear Co-Attentive Gated Fusion (BCGF) head.
    """
    if not payload.english_text.strip() and not payload.hinglish_text.strip():
        raise HTTPException(status_code=400, detail="At least one of English or Hinglish news text must be provided.")

    try:
        sentiment_engine = getattr(request.app.state, "sentiment_engine", None)
        if not sentiment_engine:
            raise HTTPException(status_code=500, detail="Sentiment Engine model is not initialized in app state.")
            
        result = sentiment_engine.analyze(payload.english_text, payload.hinglish_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment processing failed: {str(e)}")
