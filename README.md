# DSE Market Signal App

An autonomous, full-stack algorithmic market analysis, signal generation, paper trading, and automated scraping engine tailored specifically for the **Dhaka Stock Exchange (DSE)**.

---

## 🌟 Key Features

1. **DSE Market Data Engine**:
   - Automated sequential historical backfilling (6 months, 7-day batches) using legacy DSE scraping without requiring an API key.
   - Sunday–Thursday Bangladeshi trading calendar with full market holiday recognition.
   - Automated daily data collection scheduled for **16:30 Asia/Dhaka** with duplicate prevention.
   - Controlled missing-data recovery and strict HTTP 403 handling (never bypasses or hammers).

2. **Technical Analysis & Indicators**:
   - Wilder's 14-period RSI, MACD (12, 26, 9), EMA (9, 21, 50), SMA (9, 20, 50).
   - Bollinger Bands (20, 2σ), Average True Range (ATR), and Average Directional Index (ADX).
   - Volume Surge detection (1.5x 20-day MA) and Classic Pivot Support/Resistance levels (P, S1, S2, R1, R2).

3. **Multi-Factor Signal Engine**:
   - Buy/Sell/Hold signals with confidence score (0–100%) and clear confluence rationale.
   - ATR-based dynamic stop-loss and take-profit targets.
   - Telegram notification integration with graceful fallback simulation mode.

4. **Virtual Paper Trading & Position Sizing**:
   - Virtual order execution (MARKET / LIMIT) with cash balance and position tracking.
   - Real-time mark-to-market portfolio equity, realized & unrealized P&L.
   - Dynamic position sizing implementing the 2% capital risk rule and maximum portfolio concentration limits.

5. **Risk Management & DSE Regulatory Rules**:
   - Portfolio drawdown circuit breaker (freezes new buys upon exceeding maximum drawdown limit).
   - Trailing stop-loss calculation that ratchets upward with price highs and never decreases.
   - Official DSE regulatory circuit breaker bands (+/- 10% down to +/- 3.75% based on price bracket).
   - 0.10 BDT tick size enforcement and T+2 / T+3 settlement category handling.

6. **TradingView-Style Frontend Dashboard**:
   - Responsive multi-pane layout: Watchlist & Screener (left), Candlestick & Technical Canvas Chart (center), Signal & Order Panel (right).
   - Interactive sidebar toggle controls (Hide/Show Left & Right).
   - Real-time system health and DSE trading session indicators.

7. **Optional Gemini AI Integration**:
   - AI-driven stock technical commentary and signal second opinion.
   - Automatic fallback to an expert rule-based engine when `GEMINI_API_KEY` is not present.

8. **Stock Screener & Strategy Backtesting**:
   - Quantitative multi-factor screener filtering by trend, RSI, volume surge, and signal.
   - User watchlist with live price updates and AI consensus.
   - Bar-by-bar historical backtesting engine reporting total return, win rate, profit factor, max drawdown, and trade logs.

---

## 🚀 Quick Start Guide

### 1. Requirements & Setup

Ensure Python 3.10+ (or 3.14) is installed.

```bash
# Clone or navigate to project directory
cd D:\DSE-Market-Signal

# Create and activate virtual environment (if not already created)
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running Automated Tests

Run the complete regression test suite:

```bash
pytest
```

All unit, integration, and end-to-end acceptance tests should pass cleanly.

### 3. Running the Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- **TradingView Dashboard**: Open your browser at [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger API Docs**: Navigate to [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📁 Project Structure

```
D:\DSE-Market-Signal/
├── backend/
│   ├── calendar.py          # DSE Sunday-Thursday trading calendar & holidays
│   ├── collector.py         # Legacy DSE scraping & daily collection
│   ├── db.py                # SQLite database connection & prices table
│   ├── indicators.py        # Technical indicator formulas (RSI, MACD, EMA, BB, ATR)
│   ├── analysis.py          # Stock technical analysis & support/resistance
│   ├── market_summary.py    # Market breadth & gainers/losers
│   ├── signals.py           # Confluence signal engine (Buy/Sell/Hold)
│   ├── telegram.py          # Telegram alert dispatcher with simulation fallback
│   ├── paper_trading.py     # Virtual orders, positions, trade history, P&L
│   ├── position_sizing.py   # Capital allocation & 2% risk calculator
│   ├── risk_management.py   # Stop loss, trailing stop, drawdown circuit breaker
│   ├── dse_rules.py         # Circuit breaker bands, tick size, settlement rules
│   ├── ai_engine.py         # Gemini AI analysis with expert fallback
│   ├── automation.py        # Automation state, retry, recovery & monitoring
│   ├── chart_service.py     # Multi-panel candlestick, RSI & MACD chart payload
│   ├── screener.py          # Stock screener & watchlist manager
│   ├── backtesting.py       # Algorithmic strategy backtester
│   └── main.py              # FastAPI application & API endpoints
├── config/
│   └── settings.json        # Centralized engine configuration
├── engine/
│   ├── config.py            # Configuration loader
│   ├── pipeline.py          # Modular execution pipeline
│   └── skills/              # Agent skills (trend, breakout, mean reversion)
├── frontend/
│   ├── index.html           # TradingView-style main dashboard
│   ├── styles.css           # Modern dark-mode TradingView styling
│   └── app.js               # Interactive chart canvas & UI logic
├── scripts/
│   ├── backfill.py          # 6-month historical backfill utility
│   ├── gap_audit.py         # Trading calendar gap and holiday auditor
│   └── recovery.py          # Controlled missing-data recovery runner
└── tests/                   # 80+ comprehensive automated tests
```

---

## 🛡️ Production Deployment Readiness & Operational Guide

The platform is fully configured for containerized or systemd-managed production deployment:

### 1. Docker Deployment
```bash
# Build and run using Docker Compose
docker compose up -d --build

# Verify container health
docker compose ps
curl http://localhost:8000/health
```

### 2. Linux Systemd Service Deployment
```bash
# Copy systemd unit file
sudo cp dse-market-signal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dse-market-signal
sudo systemctl status dse-market-signal
```

### 3. Automated Deployment Verification
Validate that all deployment configurations, container requirements, database schema, multi-symbol data, and API endpoints are verified:
```bash
python scripts/verify_deployment.py
```

### 4. Risk & Compliance Architecture
- **DSE Market Compliance**: Enforces ±3.75% to ±10% daily circuit bands, 0.10 BDT tick size, category-specific settlement cycles (A/B/N = T+2, Z = T+3), and market hours.
- **Order Execution Safety**: Paper orders strictly enforce DSE market policies and risk parameters (drawdown breaker from peak equity, maximum 25% single-stock allocation, and 1.5:1 minimum Risk/Reward ratio).
- **LIMIT Order Engine**: Non-marketable limit orders remain `PENDING` until target execution prices are reached.
- **Automation Control**: Toggling `MANUAL` mode actively pauses scheduler background execution, while `AUTO` mode resumes daily capture across all configured symbols (`GP`, `BATBC`, `SQURPHARMA`, `BEXIMCO`, `ROBI`).

