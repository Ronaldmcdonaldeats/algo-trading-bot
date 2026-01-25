"""Symbol validator - tests which NASDAQ symbols have valid Alpaca data."""

import logging
from datetime import datetime, timezone, timedelta
import concurrent.futures
import os

logger = logging.getLogger(__name__)


class SymbolValidator:
    """Validate which symbols have real data on Alpaca."""
    
    # Mega cap tech - 100% verified working
    VERIFIED_CORE = {
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "GOOG",
        "AVGO", "QCOM", "AMD", "INTC", "CSCO", "NFLX", "PYPL", "ADBE", "CRM",
        "INTU", "SNPS", "CDNS", "MU", "LRCX", "KLAC", "AMAT", "MRVL", "ON",
        "BA", "CAT", "HON", "RTX", "JPM", "BAC", "WFC", "GS", "MS", "BLK",
    }
    
    # Top NASDAQ tickers to test (expanded list for validation)
    NASDAQ_CANDIDATES = {
        # Large cap tech
        "ASML", "NXPI", "MCHP", "SLAB", "PSTG", "SHOP", "ABNB", "ZOOM", "TEAM",
        "WDAY", "OKTA", "SPLK", "DDOG", "CRWD", "HUBS", "MSTR", "ORCL",
        # Semiconductors
        "QRVO", "MPWR", "RMBS", "CACI", "SSNC", "APH",
        # Communications
        "TMUS", "CMCSA", "CHTR", "FOXA", "MTCH", "YELP", "TRIP", "EXPE",
        # E-commerce & Platforms
        "UBER", "LYFT", "EBAY", "DKNG", "PENN",
        # Cloud & Security
        "CLOUD", "DOCU", "ESTC", "NET", "PANW", "ZS",
        # Energy & Utilities
        "CVX", "XOM", "COP", "MPC", "PSX", "VLO", "NEE", "DUK", "EXC", "SO",
        "OKE", "KMI", "EPD", "WEC", "AEP",
        # Healthcare & Biotech
        "JNJ", "PFE", "UNH", "AMGN", "GILD", "BIIB", "VRTX", "MRNA",
        "REGN", "CTLT", "ILMN", "DXCM", "ISRG",
        # Financial Services
        "ICE", "CME", "SCHW", "LPL",
        # Airlines
        "AAL", "DAL", "UAL",
        # Consumer
        "PG", "KO", "PEP", "MDLZ", "MNST", "KMB", "CL", "ULTA",
        # Real Estate
        "DLR", "EQIX", "PSA", "CUBE", "ARE",
        # Growth
        "RBLX", "DASH", "SNOW", "COIN", "SOFI", "SQ", "UPST",
        # Diversified
        "DELL", "HPQ", "KEYS", "CHKP", "ZM", "VEEV", "BLKB",
        "NOW", "SMAR", "AZO", "ANSS", "SNAP", "PIN", "PLTR", "CRSR",
        # Additional
        "MSCI", "VRSK", "RELX", "FTNT", "SHW", "ECL", "LYB", "APD",
        "TMO", "LLY", "MRK", "ABBV", "SYK", "MDT", "DGX", "ANTM", "HUM",
        "AIG", "MET", "PRU", "SAVE", "ALK", "PEG",
        "DCPH", "ENSG", "FUTU", "IGLD", "IMAX",
        "ARPT", "ARRO", "ASAI", "ASBC", "ISKN",
        "ISLE", "ITIC", "ITOR", "ITRI", "ITRM",
    }
    
    def __init__(self):
        """Initialize validator."""
        pass
    
    @staticmethod
    def test_symbol(symbol: str, provider) -> bool:
        """Test if a symbol has valid data on Alpaca.
        
        Args:
            symbol: Ticker symbol
            provider: AlpacaProvider instance
            
        Returns:
            True if symbol has valid data, False otherwise
        """
        try:
            # Try to download 1 day of data for the symbol
            # Use cache to speed up repeated tests
            df = provider.download_bars(
                symbols=[symbol],
                period="1d",
                interval="1d",
                use_cache=True,
                cache_ttl_minutes=1440  # Cache for 24 hours
            )
            
            # Check if we got valid data
            if df is None or df.empty:
                return False
            
            if df.shape[0] == 0:
                return False
            
            # Check if we have OHLC data
            if df.shape[1] == 0:
                return False
            
            logger.info(f"✓ {symbol}: Valid data")
            return True
            
        except Exception as e:
            logger.debug(f"✗ {symbol}: {str(e)[:40]}")
            return False
    
    @staticmethod
    def validate_symbols(provider, symbols: set = None, max_workers: int = 5) -> set:
        """Validate multiple symbols in parallel.
        
        Args:
            provider: AlpacaProvider instance
            symbols: Set of symbols to test (defaults to core + candidates)
            max_workers: Number of parallel validation threads
            
        Returns:
            Set of validated symbols
        """
        if symbols is None:
            symbols = SymbolValidator.VERIFIED_CORE | SymbolValidator.NASDAQ_CANDIDATES
        
        validated = set()
        failed = set()
        
        logger.info(f"[VALIDATE] Testing {len(symbols)} symbols for Alpaca data availability...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(SymbolValidator.test_symbol, sym, provider): sym
                for sym in symbols
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(futures, timeout=90):
                sym = futures[future]
                completed += 1
                
                try:
                    if future.result(timeout=5):
                        validated.add(sym)
                    else:
                        failed.add(sym)
                except Exception as e:
                    logger.debug(f"✗ {sym}: Exception - {str(e)[:40]}")
                    failed.add(sym)
                
                # Progress every 5 symbols
                if completed % 5 == 0:
                    logger.info(f"[VALIDATE] Progress: {completed}/{len(symbols)} ({len(validated)} valid)")
        
        logger.info(f"[VALIDATE] ✓ Results: {len(validated)} valid, {len(failed)} failed")
        logger.info(f"[VALIDATE] Valid symbols: {', '.join(sorted(validated)[:15])}...")
        
        return validated
    
    @staticmethod
    def get_optimal_symbols(provider, target_count: int = 100) -> set:
        """Get validated symbols up to target count.
        
        Strategy:
        1. Start with verified core symbols (always included)
        2. Test candidates to find valid ones
        3. Return up to target_count symbols
        
        Args:
            provider: AlpacaProvider instance
            target_count: Target number of symbols (default 100)
            
        Returns:
            Set of validated symbols
        """
        # Core symbols are always included
        result = SymbolValidator.VERIFIED_CORE.copy()
        
        if len(result) >= target_count:
            return result
        
        # Validate candidates to fill up to target
        remaining_needed = target_count - len(result)
        logger.info(f"[SYMBOLS] Core: {len(result)} symbols. Need {remaining_needed} more.")
        
        candidates = list(SymbolValidator.NASDAQ_CANDIDATES)
        
        # Validate in batches to find valid ones
        validated = SymbolValidator.validate_symbols(
            provider,
            symbols=set(candidates[:remaining_needed * 2]),  # Test 2x what we need
            max_workers=5
        )
        
        result.update(validated)
        
        return result


def main():
    """Test symbol validation (run standalone for discovery)."""
    from trading_bot.broker.alpaca import AlpacaConfig, AlpacaProvider
    
    # Setup
    try:
        config = AlpacaConfig.from_env(paper_mode=True)
        provider = AlpacaProvider(config=config)
        
        # Get optimal symbols
        symbols = SymbolValidator.get_optimal_symbols(provider, target_count=100)
        
        print(f"\n[RESULT] Found {len(symbols)} valid symbols:")
        print(f"Symbols: {', '.join(sorted(symbols))}")
        
        # Save to file for reference
        with open("validated_symbols.txt", "w") as f:
            for sym in sorted(symbols):
                f.write(f"{sym}\n")
        
        print(f"\n[SAVE] Saved to validated_symbols.txt")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
