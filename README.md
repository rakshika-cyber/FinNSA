# FinNSA: Nifty 50 terminal

A local web terminal for the Nifty 50 with a 1990s trading-screen look. FastAPI backend, plain-JS frontend.

**What it shows**
- Live board of all 50 stocks (price, change, best bid/ask, volume, day range) with sector filters and search.
- Per-stock page: price/RSI/MACD/return-distribution/drawdown charts, buy/sell order book (5 levels), futures, full
  **option chain with IV and Greeks**, open-interest and IV-smile charts, fundamentals, officers, holdings, analyst targets.
- **News signal**: recent headlines (Google News RSS) scored by FinBERT (open source).
- Compare page: multi-stock relative performance, risk/return, correlation, and sector-wise news-vs-return comparison.
- On-screen guided tour (`T`), keyboard shortcuts (`?`), live refresh while the market is open.

> Information only, **not investment advice**. The BUY/SELL ticket checks an order against the live price and records it
> locally; it **does not send orders to any broker**.

## Quick start

Requires Python 3.10+ and about 3 GB of disk (PyTorch + models). First run downloads two Hugging Face models (~600 MB).

```bash
git clone <repo-url> finnsa && cd finnsa
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000. Use `127.0.0.1` (not `0.0.0.0`) so the app is reachable only from your own machine.

## Live data: connect your own Angel One SmartAPI account

Without a broker connection the app still runs, using Yahoo Finance (delayed prices; no order book, futures or options).
For live exchange data, click the red **BROKER** chip in the header (or press `G`) and enter:

| Field | What it is | Where to get it |
|---|---|---|
| API key | identifies your app | https://smartapi.angelone.in -> My Apps -> Create App |
| Client code | your Angel One login ID | your Angel One account |
| PIN | your 4-digit Angel One MPIN | your Angel One account |
| TOTP secret | base32 text under the TOTP QR code (not the 6-digit code) | https://smartapi.angelone.in/enable-totp |

The app logs in once to test them and only then stores them. "Remember" writes them to a local `.env` (plain text,
owner-only permissions, git-ignored). Or create `.env` yourself from `.env.example`.
**Everyone uses their own credentials. Never share or commit your `.env` or `logs/`.**

## Keyboard
`?` help · `T` tour · `H` board · `C` compare · `D` datasets · `G` broker · `/` search · `J/K` move · `O` open ·
`B/S` buy/sell ticket · `1-5` chart range · `[ ]` expiry/sector · `N/P` next/previous stock · `Q` close/back.

## Data sources & caveats
- **Exchange data** (prices, order book, futures, options OI/volume): Angel One SmartAPI, polled about every 5s while the market is open.
- **IV and Greeks**: *computed* here (Black-Scholes, risk-free rate 6.5% by default, set `RISK_FREE_RATE` in `.env`), not exchange-published.
- **Charts, indicators, fundamentals, officers, holdings, analyst targets**: Yahoo Finance via `yfinance`. A third-party aggregate that can lag;
  verify against NSE/BSE filings. The officer list is executives only, not the full board.
- **News**: Google News RSS scored by ProsusAI/finbert. Describes the tone of headlines; it does not predict prices.
- The market-open check knows weekends and trading hours, not exchange holidays.
- `main.py`'s BCGF fusion head (`/predict`) has **no trained weights**; treat its UP/DOWN output as a demo.

## Layout
```
main.py            app entry; routers/  API endpoints;  services/  data + business logic
ml/                sentiment engine, fusion head;  static/  frontend (HTML/JS/CSS)
data/              Angel One instrument token maps;  scripts/  token-map builder
```
