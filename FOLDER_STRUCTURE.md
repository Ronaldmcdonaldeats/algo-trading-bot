# Folder Structure Overview

## Root Directory
Clean, minimal structure with only essential files and directories visible:

```
algo-trading-bot/
├── configs/              # Configuration files (default.yaml)
├── data/                 # Runtime data (NEW - databases, logs)
├── docs/                 # Documentation (NEW - optimizations, guides)
├── notebooks/            # Jupyter notebooks for analysis
├── scripts/              # Utility scripts (bootstrap.ps1)
├── src/                  # Source code
├── tests/                # Unit tests
├── .env                  # Environment variables
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker image definition
├── pyproject.toml        # Python project configuration
└── README.md             # Project overview
```

## Key Directories

### `/configs/`
Configuration YAML files for trading strategies and parameters:
- `default.yaml` - Default trading configuration

### `/data/` (NEW)
Runtime files including databases and logs:
- `trades.sqlite` - Trade history database (moved from root)
- `test.db` - Test database
- `bot_debug.log` - Debug logs

### `/docs/` (NEW)
Documentation files for reference:
- `OPTIMIZATION_SUMMARY.md` - All optimizations applied
- `MEMORY_OPTIMIZATION_GUIDE.md` - Memory optimization details
- `QUICK_START.md` - Getting started guide
- `FOLDER_STRUCTURE.md` - This file structure reference
- Additional guides and agent notes

### `/src/trading_bot/`
Main application code:

**Core Modules:**
- `__init__.py` - Package initialization
- `__main__.py` - Entry point
- `cli.py` - Command-line interface (11 subcommands)
- `config.py` - Configuration loading & validation
- `indicators.py` - Technical indicators (RSI, MACD, ATR, etc.)
- `risk.py` - Risk management calculations

**Subpackages:**
- `analytics/` - DuckDB analytics pipeline
- `backtest/` - Backtesting engine
- `broker/` - Broker integrations (Alpaca, Paper)
- `core/` - Core data models
- `data/` - Data providers (Alpaca, Mock)
- `db/` - Database models and repository
- `engine/` - Paper trading engine
- `learn/` - Ensemble learning and tuning
- `paper/` - Paper trading runner
- `schedule/` - Market schedule (US equities)
- `strategy/` - Trading strategies (RSI, MACD, ATR)
- `tui/` - Terminal UI (Rich)
- `ui/` - Dashboard UI

### `/tests/`
Unit tests:
- `test_config.py` - Config validation tests
- `test_duckdb_analytics.py` - Analytics tests
- `test_paper_broker.py` - Paper broker tests
- `test_risk.py` - Risk management tests
- `test_schedule.py` - Market schedule tests

## Default Paths
All database operations now use `data/trades.sqlite`:
- CLI: All 11 subcommands default to `data/trades.sqlite`
- Python APIs: All runners and libraries default to `data/trades.sqlite`
- This keeps runtime data organized separately from code

## Cleanup Summary
**Before:** Root directory had 28+ files (10+ markdown docs, 3 databases scattered)
**After:** Root directory has only 7 dirs + 7 essential files

**Moved to `/docs/`:**
- OPTIMIZATION_SUMMARY.md
- MEMORY_OPTIMIZATION_GUIDE.md
- QUICK_START.md
- AGENTS.md
- DOCUMENTATION.md
- FOLDER_STRUCTURE.md
- And 5+ other optimization documents

**Moved to `/data/`:**
- trades.sqlite (trade history)
- test.db (test database)
- bot_debug.log (debug logs)
