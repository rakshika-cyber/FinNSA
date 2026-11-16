import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import database
from ml.sentiment_engine import SentimentEngine
from routers import stocks, sentiment, predict, upload, company, compare, orders, broker
from services import stock_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager:
    Initializes SQLite database and loads FinBERT / Hinglish PyTorch models ONCE into app state.
    """
    print("[FinNSA] Initializing SQLite database cache...")
    database.init_db()

    print("[FinNSA] Loading Hugging Face transformer models into memory (FinBERT & MuRIL/HingBERT)...")
    sentiment_engine = SentimentEngine()
    # Attempt loading full HF transformer model weights (uses fallback feature extractor if offline)
    sentiment_engine.load(load_transformer_weights=True)
    app.state.sentiment_engine = sentiment_engine

    print("[FinNSA] Starting live market price refresh (Angel One SmartAPI, 5s interval)...")
    stock_service.start_price_refresh_thread()

    print("[FinNSA] FinNSA Backend Application is Ready!")
    yield
    print("[FinNSA] Shutting down FinNSA application...")

app = FastAPI(
    title="FinNSA API - Nifty 50 Sentiment & Technical Fusion Engine",
    description="Predicts Nifty 50 stock direction from English + Hinglish financial news sentiment fused with technical indicators (VWAP, MACD, RSI) using PyTorch Bilinear Co-Attentive Gated Fusion (BCGF).",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    # Local-only: a wildcard origin would let any website in the user's browser call this API (incl. /broker, /orders).
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(stocks.router)
app.include_router(sentiment.router)
app.include_router(predict.router)
app.include_router(upload.router)
app.include_router(company.router)
app.include_router(compare.router)
app.include_router(orders.router)
app.include_router(broker.router)

# Mount Static Files directory for frontend UI
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/stock", include_in_schema=False)
async def serve_stock_page():
    """Serves the per-stock detail page (ticker passed as ?ticker=RELIANCE)."""
    return FileResponse(os.path.join(STATIC_DIR, "stock.html"))

@app.get("/compare-view", include_in_schema=False)
async def serve_compare_page():
    """Multi-stock and sector comparison page."""
    return FileResponse(os.path.join(STATIC_DIR, "compare.html"))

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serves the FinNSA static dashboard at root URL."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "FinNSA Backend API is running. Access API docs at /docs"}
