"""News-sentiment signal using FinBERT (ProsusAI/finbert, open source).

Each headline is classified positive/negative/neutral, scored as P(pos) - P(neg),
then averaged with a recency weight (half-life 3 days) into one signal.
This is a sentiment indicator over headlines, not investment advice.
"""
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

import torch

MODEL_NAME = "ProsusAI/finbert"
HALF_LIFE_DAYS = 3.0
BULLISH_THRESHOLD = 0.15
BEARISH_THRESHOLD = -0.15

_lock = threading.Lock()
_tokenizer = None
_model = None


def _load():
    global _tokenizer, _model
    with _lock:
        if _model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
            _model.eval()
    return _tokenizer, _model


def score_headlines(news: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not news:
        return {"signal": "NO_DATA", "score": 0.0, "confidence": 0.0, "count": 0, "headlines": []}

    tokenizer, model = _load()
    id2label = {int(i): l.lower() for i, l in model.config.id2label.items()}
    titles = [n["title"] for n in news]

    with torch.no_grad():
        enc = tokenizer(titles, return_tensors="pt", truncation=True, max_length=96, padding=True)
        probs = torch.softmax(model(**enc).logits, dim=-1)

    now = datetime.now(timezone.utc)
    scored, weighted_sum, weight_total = [], 0.0, 0.0
    for n, p in zip(news, probs):
        by_label = {id2label[i]: float(p[i]) for i in range(p.shape[0])}
        score = by_label.get("positive", 0.0) - by_label.get("negative", 0.0)
        label = max(by_label, key=by_label.get)
        age_days = max(0.0, (now - datetime.fromisoformat(n["published"])).total_seconds() / 86400)
        weight = 0.5 ** (age_days / HALF_LIFE_DAYS)
        weighted_sum += score * weight
        weight_total += weight
        scored.append({**n, "label": label, "score": round(score, 3)})

    agg = weighted_sum / weight_total if weight_total else 0.0
    if agg >= BULLISH_THRESHOLD:
        signal = "BULLISH"
    elif agg <= BEARISH_THRESHOLD:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for s in scored:
        counts[s["label"]] = counts.get(s["label"], 0) + 1

    return {
        "signal": signal,
        "score": round(agg, 3),
        "confidence": round(min(1.0, abs(agg) / 0.6), 2),
        "count": len(scored),
        "breakdown": counts,
        "model": MODEL_NAME,
        "headlines": scored,
    }
