# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common commands (Windows PowerShell)

### Setup (editable install)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional (Alpaca integration extras):
```powershell
python -m pip install -e ".[dev,live]"
```

### Lint
```powershell
ruff check .
```

### Tests
Run all tests:
```powershell
pytest
```

Run a single test file:
```powershell
pytest tests/test_risk.py
```

Run a single test:
```powershell
pytest tests/test_risk.py::test_position_size_shares_basic
```

Note: `pyproject.toml` sets `pytest` to run quietly by default (`addopts = "-q"`).

### Run the CLI
After installing (editable or normal), the CLI entrypoints are:

Module form:
```powershell
python -m trading_bot --help
```

Console script form (from `pyproject.toml`):
```powershell
trading-bot --help
```

Current subcommands exist but are stubs:
```powershell
python -m trading_bot backtest --config configs/default.yaml
python -m trading_bot paper --config configs/default.yaml
```

### Environment/bootstrap
Create a local `.env` from `.env.example`:
```powershell
.\scripts\bootstrap.ps1
```

### Docker (optional)
`docker-compose.yml` defines:
- `app`: builds from `Dockerfile` and runs `python -m trading_bot --help`
- `postgres`: Postgres 16 with default credentials `trading/trading`

Common workflow:
```powershell
docker compose up --build
```

## Codebase architecture (big picture)

### Entry points
- `src/trading_bot/__main__.py` runs `trading_bot.cli:main` (module entrypoint: `python -m trading_bot ...`).
- `src/trading_bot/cli.py` defines the top-level `argparse` CLI (`backtest` and `paper` subcommands). The CLI currently prints “not implemented yet”.

### Configuration
- `configs/default.yaml` is the default config file used by the CLI.
- `src/trading_bot/config.py` loads YAML and maps:
  - `risk` -> `RiskConfig` (max risk per trade, stop-loss %, take-profit %)
  - `portfolio` -> `PortfolioConfig`
  - `strategy` -> `StrategyConfig(raw=...)` (kept as an untyped mapping for now)

When wiring new features, expect to extend `AppConfig` (or parse `StrategyConfig.raw`) rather than scattering config reads.

### Data → indicators → strategy signals
- `src/trading_bot/data/providers.py` defines a `MarketDataProvider` protocol and a concrete `YFinanceProvider` (historical price data via `yfinance.download`). `AlpacaProvider` is a stub.
- `src/trading_bot/indicators.py` adds technical indicators (RSI, MACD, fast/slow SMAs) using the `ta` library.
- `src/trading_bot/strategy/mean_reversion_momentum.py` defines `generate_signals(df, ...)` which:
  - computes indicators
  - computes a rolling z-score over price
  - outputs a `signal` column (0/1 currently; short is reserved)

This is the main “strategy logic” currently implemented.

### Risk sizing
- `src/trading_bot/risk.py` contains pure functions for:
  - stop-loss / take-profit price calculations
  - fixed-fractional position sizing (`position_size_shares`)

### Execution/backtesting/brokers (mostly scaffolding)
- `src/trading_bot/backtest/engine.py` is a placeholder for wiring `generate_signals` into an actual backtest engine (notes mention backtrader + analyzers).
- `src/trading_bot/broker/paper.py` is a placeholder for a paper broker (fills/slippage/limits not implemented).

### Persistence
- `src/trading_bot/db/trade_log.py` defines a minimal SQLAlchemy model (`Trade`) and a `SqliteTradeLogger` used to log trades to a local SQLite DB (`trades.sqlite`).
- `.env.example` also includes a `POSTGRES_DSN` intended for future Postgres-backed storage (used in `docker-compose.yml`).
