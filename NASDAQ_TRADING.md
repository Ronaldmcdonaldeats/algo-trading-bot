# NASDAQ Trading Feature

## Overview

You can now trade the top NASDAQ stocks automatically without manually specifying symbols. This is perfect for diversified backtesting and paper trading across a large universe of stocks.

## New CLI Flags

Two new flags have been added to `backtest`, `paper`, and `live` commands:

### `--nasdaq-top-500`
Trade the top 500 NASDAQ stocks by market capitalization.

```bash
# Paper trading with top 500 NASDAQ stocks
python -m trading_bot paper --nasdaq-top-500 --period 6mo --iterations 5

# Backtesting with top 500 NASDAQ stocks
python -m trading_bot backtest --nasdaq-top-500 --period 1y

# Live paper trading with top 500 NASDAQ stocks
python -m trading_bot live paper --nasdaq-top-500 --period 6mo
```

### `--nasdaq-top-100`
Trade the top 100 NASDAQ stocks by market capitalization.

```bash
# Paper trading with top 100 NASDAQ stocks
python -m trading_bot paper --nasdaq-top-100 --period 6mo --iterations 5

# Backtesting with top 100 NASDAQ stocks
python -m trading_bot backtest --nasdaq-top-100 --period 1y

# Live paper trading with top 100 NASDAQ stocks
python -m trading_bot live paper --nasdaq-top-100 --period 6mo
```

## Top NASDAQ Stocks Included

The top stocks in the list (by market cap) are:
- AAPL, MSFT, NVDA, GOOGL, GOOG, AMZN, META, TSLA, BRK.B, AVGO
- NFLX, QCOM, AMD, INTC, ADBE, CSCO, CMCSA, PEP, COST, INTU
- ISRG, AEP, ABNB, MELI, SNPS, CHTR, PYPL, LRCX, KLAC, ASML
- And 470-470 more stocks for the top 500/100 selection...

## How It Works

1. When you use `--nasdaq-top-500` or `--nasdaq-top-100`, the CLI automatically loads the corresponding symbols
2. The symbol list is loaded from `src/trading_bot/data/nasdaq_symbols.py`
3. These symbols are then used for backtesting, paper trading, or live trading
4. The feature respects all other CLI options (period, interval, capital, etc.)

## Implementation Details

### NASDAQ Symbols Module
Location: `src/trading_bot/data/nasdaq_symbols.py`

Key function:
```python
def get_nasdaq_symbols(top_n: int = 500) -> list[str]:
    """Get top N NASDAQ stocks by market cap."""
```

Returns a list of stock symbols like `['AAPL', 'MSFT', ...]`

### CLI Integration
Modified in: `src/trading_bot/cli.py`

Functions updated:
- `_run_paper()` - Added NASDAQ flag handling
- `_run_backtest()` - Added NASDAQ flag handling
- `_run_live()` - Added NASDAQ flag handling for both paper and live trading

Logic:
```python
if getattr(args, 'nasdaq_top_500', False):
    symbols = _get_nasdaq_symbols(top_n=500)
elif getattr(args, 'nasdaq_top_100', False):
    symbols = _get_nasdaq_symbols(top_n=100)
else:
    symbols = _parse_symbols(args.symbols)
```

## Examples

### Backtest top 100 NASDAQ stocks over 1 year
```bash
python -m trading_bot backtest --nasdaq-top-100 --period 1y --interval 1d
```

### Paper trade top 500 NASDAQ stocks
```bash
python -m trading_bot paper --nasdaq-top-500 \
  --period 6mo \
  --interval 1h \
  --start-cash 100000 \
  --iterations 5
```

### Live paper trade top 100 NASDAQ stocks
```bash
python -m trading_bot live paper --nasdaq-top-100 \
  --period 3mo \
  --interval 1h \
  --start-cash 50000
```

## Notes

- **Symbol Count**: Top 500 returns up to 500 symbols, top 100 returns up to 100 symbols
- **Data Source**: Symbols are from a curated list of most liquid NASDAQ stocks
- **Priority**: NASDAQ flags override the `--symbols` parameter. If both are provided, NASDAQ flags take precedence
- **Memory**: Trading with 500 symbols requires sufficient RAM. Use `--memory-mode` flag if needed
- **Market Hours**: Works with US equities market hours by default

## Docker Usage

When using Docker Compose:

```bash
# Paper trade top 500 NASDAQ stocks
docker-compose exec app python -m trading_bot paper --nasdaq-top-500 --period 6mo --iterations 5

# Backtest top 100 NASDAQ stocks
docker-compose exec app python -m trading_bot backtest --nasdaq-top-100 --period 1y
```

## Troubleshooting

**Issue**: Symbol loading fails
- **Solution**: Ensure `src/trading_bot/data/nasdaq_symbols.py` exists
- **Check**: Run `python -c "from trading_bot.data.nasdaq_symbols import get_nasdaq_symbols; print(len(get_nasdaq_symbols(500)))"`

**Issue**: Memory issues with 500 symbols
- **Solution**: Use `--nasdaq-top-100` instead or add `--memory-mode` flag
- **Alternative**: Use `--max-symbols` to limit

## Contributing

To add or update the NASDAQ symbol list:
1. Edit `src/trading_bot/data/nasdaq_symbols.py`
2. Update the `symbols` list in `get_fallback_nasdaq_symbols()`
3. Test with: `python -m trading_bot backtest --nasdaq-top-100 --period 1mo`

---

**Created**: Feature implemented for large-scale NASDAQ trading
**Last Updated**: 2024
