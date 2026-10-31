# DSE Market Signal - Implementation Roadmap

Rule: Implement -> Test -> Verify -> Check -> Next Phase

Historical data: Maximum 6 months for initial testing.
Fetch historical data in small batches, not one bulk request.
Scheduler: Daily incremental collection after initial backfill.

## Phase 1 - Foundation

- [x] Project folders
- [x] Python environment
- [x] FastAPI
- [x] Database
- [x] Unit tests
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 2 - Data Engine

- [x] DSE source access
- [x] Manual collection
- [x] 6-month batch backfill (all configured symbols)
- [x] Daily scheduler (all configured symbols)
- [x] Duplicate prevention
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 3 - Trading Calendar

- [x] Sunday-Thursday active days
- [x] Friday-Saturday weekend skip
- [x] DSE holiday calendar
- [x] Gap auditor (calendar verification strict)
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 4 - Indicators

- [x] Moving averages (EMA 9, 21, 50, 200)
- [x] Momentum (RSI 14)
- [x] Trend (MACD 12, 26, 9)
- [x] Volatility (ATR 14, Bollinger Bands)
- [x] Support & Resistance (Classic Pivots, S1-S3, R1-R3)
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 5 - Market Rules Engine

- [x] Circuit breaker limits (dynamic price bands)
- [x] Minimum tick size (0.10 BDT)
- [x] Settlement cycles (A/B/N = T+2, Z = T+3)
- [x] Category and side strict validation
- [x] Trading session hours tracking
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 6 - Position Sizing

- [x] Risk per trade calculation (1-3% equity)
- [x] Single-stock allocation cap (25%)
- [x] Portfolio sizing recommendations
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 7 - Risk Management Engine

- [x] Drawdown circuit breaker calculated from peak equity
- [x] Max concurrent positions limit
- [x] Single-stock allocation concentration check
- [x] Strict Risk/Reward ratio validation (min 1.5:1 required for approval)
- [x] Ratcheting trailing stop calculation
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 8 - Paper Trading Engine

- [x] Virtual order execution with DSE rules enforcement
- [x] Virtual order execution with risk limits enforcement
- [x] Non-marketable LIMIT orders placed as PENDING
- [x] Mark-to-market portfolio snapshot and P&L
- [x] Peak equity tracking in virtual accounts
- [x] Trade history and account reset
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 9 - Algorithmic Signals

- [x] Multi-factor confluence scoring
- [x] Confidence score calculation
- [x] Target and stop loss generation
- [x] Telegram alert delivery
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 10 - AI Engine

- [x] Multi-model provider abstraction (Gemini / Anthropic / Groq / Ollama)
- [x] Comprehensive stock analysis
- [x] Signal review & risk assessment
- [x] Market outlook generation
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 11 - Frontend Dashboard

- [x] Three-column TradingView layout
- [x] Interactive candlestick chart canvas
- [x] Neutral initial placeholder states (no mock data leakage)
- [x] Watchlist, signals & paper trading UI
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 12 - Automation & Operations

- [x] Active Manual/Auto mode scheduler control
- [x] Exponential backoff retry handling
- [x] Multi-symbol gap audit & recovery check
- [x] Recovery failure propagation to cycle status
- [x] Runtime safe JSON log endpoint
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 13 - Technical Charts

- [x] Multi-panel candlestick chart payload
- [x] Overlay indicators (EMA 9, 21, 50)
- [x] Separate volume, RSI & MACD panels
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 14 - Stock Screener

- [x] Multi-factor technical screener
- [x] Persistent JSON watchlist management
- [x] AI signal review integration
- [x] Phase tests passed
- [x] Evidence reviewed and phase approved

## Phase 15 - Final Testing & Production Deployment

- [x] Walk-forward backtesting engine
- [x] Integration testing across all components
- [x] Production Dockerfile and docker-compose.yml
- [x] Systemd service definition and GitHub Actions CI/CD workflow
- [x] Automated deployment verification (`scripts/verify_deployment.py`)
- [x] Phase tests passed (93 automated tests)
- [x] Evidence reviewed and phase approved

## Audit Remediation Status
All Critical, High, and Additional audit findings have been resolved and verified with automated regression tests:
1. Paper orders strictly enforce DSE market rules and portfolio risk limits.
2. Low Risk/Reward (< 1.5) orders are rejected (`is_approved = False`).
3. Automation mode (MANUAL/AUTO) actively pauses/resumes the daily collection scheduler.
4. Multi-symbol daily collection and backfill for all 5 configured symbols (`GP`, `BATBC`, `SQURPHARMA`, `BEXIMCO`, `ROBI`).
5. Drawdown is computed from historical peak equity.
6. Automation logs endpoint handles JSON parsing safely without NameError.
7. Automation cycle status marks FAILED if recovery fails across any symbol.
8. Complete production deployment infrastructure provided (Docker, Compose, Systemd, CI/CD, deployment verification).

## Progress
- Current: Complete, Verified & Audit Remediated (Phases 1-15)
- Blocker: None
- Test Suite: 93 passed, 0 failed
- Deployment Readiness: 100% verified via `scripts/verify_deployment.py`
