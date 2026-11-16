import math
from typing import Dict, Any, Optional
from services.stock_service import compute_detectors
from ml.sentiment_engine import SentimentEngine

# Sample financial news snippets per ticker for quick prediction demonstration
DEFAULT_TICKER_NEWS = {
    "RELIANCE.NS": {
        "eng": "Reliance Industries reports 12% revenue growth driven by retail and digital services expansion.",
        "hing": "Reliance ka quarterly profit kafi strong aaya hai, retail segment me badiya badhat mili hai."
    },
    "TCS.NS": {
        "eng": "TCS signs multi-billion deal with European bank, outlook remains optimistic for cloud services.",
        "hing": "TCS ko naya bada European contract mila, IT sector me bullish momentum dekha gaya."
    },
    "HDFCBANK.NS": {
        "eng": "HDFC Bank deposit growth accelerates to 16% YoY, asset quality remains stable.",
        "hing": "HDFC Bank ke margins stable hai aur deposit badh raha hai."
    },
    "INFY.NS": {
        "eng": "Infosys raises full-year revenue growth guidance after robust Q3 deal wins.",
        "hing": "Infosys ne guidance badha diya hai, stock me achhi tezi aane ki ummeed hai."
    }
}

def predict_stock_direction(
    ticker: str, 
    sentiment_engine: SentimentEngine, 
    english_text: Optional[str] = None, 
    hinglish_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fuses technical indicators (VWAP, MACD, RSI) with PyTorch BCGF sentiment score 
    to forecast stock direction (UP/DOWN) and confidence score.
    """
    formatted_ticker = ticker.upper()
    if not formatted_ticker.endswith(".NS") and not formatted_ticker.startswith("^"):
        formatted_ticker += ".NS"

    # 1. Fetch Technical Indicators
    indicators = compute_detectors(formatted_ticker)
    
    # 2. Extract news text (user-provided or ticker default)
    if not english_text or not english_text.strip():
        english_text = DEFAULT_TICKER_NEWS.get(formatted_ticker, {}).get(
            "eng", f"Analysts remain positive on {formatted_ticker} performance after earnings update."
        )
    if not hinglish_text or not hinglish_text.strip():
        hinglish_text = DEFAULT_TICKER_NEWS.get(formatted_ticker, {}).get(
            "hing", f"{formatted_ticker} me strong buying interest hai, chart par breakout structure hai."
        )

    # 3. Compute Sentiment via PyTorch BCGF Head
    sentiment_res = sentiment_engine.analyze(english_text, hinglish_text)
    bcgf_score = sentiment_res["fused"]["bcgf_score"] # Range [-1.0, 1.0]

    # 4. Normalize Technical Indicator Signals to [-1.0, 1.0]
    # RSI Signal
    rsi = indicators["rsi"]
    if rsi < 30:
        rsi_score = 0.8  # Oversold -> Bullish bounce
    elif rsi > 70:
        rsi_score = -0.8 # Overbought -> Bearish pull-back
    else:
        rsi_score = (rsi - 50.0) / 30.0 # Linear mapping around 50

    # MACD Signal
    macd_hist = indicators["macd"]["histogram"]
    # Histogram scales with share price, so score it as a % of price (0.5% of price ~= full signal).
    macd_score = max(-1.0, min(1.0, indicators["macd"]["histogram_pct"] / 0.5))

    # VWAP Signal
    price = indicators["current_price"]
    vwap = indicators["vwap"]
    if vwap > 0:
        vwap_diff_pct = (price - vwap) / vwap
        vwap_score = max(-1.0, min(1.0, vwap_diff_pct * 20.0))
    else:
        vwap_score = 0.0

    # 5. Weighted Multi-modal Fusion
    # Weights: BCGF Sentiment (40%), MACD (25%), RSI (20%), VWAP (15%)
    w_bcgf, w_macd, w_rsi, w_vwap = 0.40, 0.25, 0.20, 0.15
    fused_signal = (
        w_bcgf * bcgf_score +
        w_macd * macd_score +
        w_rsi * rsi_score +
        w_vwap * vwap_score
    )

    # 6. Direction & Confidence Calculation
    direction = "UP" if fused_signal >= 0.0 else "DOWN"
    
    # Confidence mapped using Sigmoid of absolute signal strength
    raw_conf = 1.0 / (1.0 + math.exp(-abs(fused_signal) * 2.8))
    confidence_percent = round(min(98.5, max(52.0, raw_conf * 100)), 1)

    # 7. Generate Natural Language Rationale
    rationale = []
    rationale.append(f"BCGF Fused Sentiment Score: {bcgf_score:+.2f} ({sentiment_res['fused']['direction']} bias from English & Hinglish news).")
    rationale.append(f"MACD Histogram: {macd_hist:+.2f} ({indicators['macd']['trend']}).")
    rationale.append(f"RSI (14): {rsi:.1f} ({indicators['rsi_signal']}).")
    rationale.append(f"VWAP: ₹{vwap:.2f} (Current price ₹{price:.2f} is {indicators['vwap_signal']}).")

    return {
        "ticker": formatted_ticker,
        "direction": direction,
        "confidence": confidence_percent,
        "fusion_signal_score": round(fused_signal, 4),
        "news_evaluated": {
            "english": english_text,
            "hinglish": hinglish_text
        },
        "sentiment_analysis": sentiment_res,
        "technical_indicators": indicators,
        "reasoning": rationale
    }
