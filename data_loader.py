"""
data_loader.py
==============
Fetches OHLCV data from Binance USDM Perpetual Futures via CCXT.

Using perps (binanceusdm) gives extensive trading history for all coins
listed on Binance Futures.  Symbols are auto-discovered so any active
USDT-margined perp can be backtested.
"""

from __future__ import annotations

from datetime import datetime, timezone

import ccxt
import pandas as pd


# ── Binance USDM Futures client ──────────────────────────────────────────────

_exchange = ccxt.binanceusdm({"enableRateLimit": True})

# Cache of available symbols — populated on first call
_available_symbols: dict[str, str] | None = None


def _load_markets() -> dict[str, str]:
    """Return {app_ticker: exchange_symbol} for every active USDT perp."""
    global _available_symbols
    if _available_symbols is not None:
        return _available_symbols

    _exchange.load_markets()
    result: dict[str, str] = {}
    for sym, info in _exchange.markets.items():
        if (
            info.get("swap")
            and info.get("linear")
            and info.get("active")
            and info.get("quote") == "USDT"
        ):
            base = info["base"]
            app_ticker = f"{base}-USD"
            result[app_ticker] = sym  # e.g. "BTC-USD" → "BTC/USDT:USDT"
    _available_symbols = result
    return result


def get_available_tickers() -> list[str]:
    """Return sorted list of all available app tickers (e.g. ['BTC-USD', ...])."""
    return sorted(_load_markets().keys())


def ticker_to_symbol(ticker: str) -> str:
    """Convert app ticker 'BTC-USD' to Binance perp symbol 'BTC/USDT:USDT'."""
    markets = _load_markets()
    if ticker not in markets:
        raise ValueError(
            f"Ticker {ticker} not found on Binance USDM Futures. "
            f"Available: {get_available_tickers()[:20]}..."
        )
    return markets[ticker]


# ── Popular coins with friendly names (for UI defaults) ──────────────────────

POPULAR_TICKERS = {
    "BTC-USD":  "Bitcoin (BTC)",
    "ETH-USD":  "Ethereum (ETH)",
    "SOL-USD":  "Solana (SOL)",
    "BNB-USD":  "BNB (BNB)",
    "TAO-USD":  "Bittensor (TAO)",
    "ARB-USD":  "Arbitrum (ARB)",
    "SUI-USD":  "Sui (SUI)",
    "DOGE-USD": "Dogecoin (DOGE)",
    "XRP-USD":  "XRP (XRP)",
    "ADA-USD":  "Cardano (ADA)",
    "AVAX-USD": "Avalanche (AVAX)",
    "LINK-USD": "Chainlink (LINK)",
    "DOT-USD":  "Polkadot (DOT)",
    "POL-USD":  "Polygon (POL)",
    "OP-USD":   "Optimism (OP)",
    "APT-USD":  "Aptos (APT)",
    "NEAR-USD": "NEAR (NEAR)",
    "FIL-USD":  "Filecoin (FIL)",
    "ATOM-USD": "Cosmos (ATOM)",
    "UNI-USD":  "Uniswap (UNI)",
    "1000PEPE-USD": "Pepe (1000PEPE)",
    "WIF-USD":  "Dogwifhat (WIF)",
    "RENDER-USD":"Render (RENDER)",
    "FET-USD":  "Fetch.ai (FET)",
    "INJ-USD":  "Injective (INJ)",
}

# Default grid params per coin: (min_price, price_step)
GRID_DEFAULTS = {
    "BTC-USD":  (75_000.0, 500.0),
    "ETH-USD":  (1_500.0,  10.0),
    "SOL-USD":  (100.0,    1.0),
    "BNB-USD":  (500.0,    5.0),
    "TAO-USD":  (200.0,    2.0),
    "ARB-USD":  (0.20,     0.005),
    "SUI-USD":  (1.0,      0.05),
    "DOGE-USD": (0.10,     0.005),
    "XRP-USD":  (1.0,      0.02),
    "ADA-USD":  (0.30,     0.01),
    "AVAX-USD": (15.0,     0.5),
    "LINK-USD": (10.0,     0.2),
    "DOT-USD":  (3.0,      0.1),
    "POL-USD":  (0.20,     0.005),
    "OP-USD":   (0.50,     0.02),
    "APT-USD":  (5.0,      0.2),
    "NEAR-USD": (2.0,      0.1),
    "FIL-USD":  (2.0,      0.1),
    "ATOM-USD": (5.0,      0.2),
    "UNI-USD":  (5.0,      0.2),
    "1000PEPE-USD": (0.005, 0.0002),
    "WIF-USD":  (0.30,     0.01),
    "RENDER-USD":(2.0,     0.1),
    "FET-USD":  (0.30,     0.01),
    "INJ-USD":  (5.0,      0.2),
}


def get_display_name(ticker: str) -> str:
    """Friendly name for ticker, fallback to ticker itself."""
    return POPULAR_TICKERS.get(ticker, ticker)


# ── OHLCV fetch ──────────────────────────────────────────────────────────────

def fetch_ohlcv(
    ticker: str = "BTC-USD",
    timeframe: str = "1h",
    days: int = 365,
) -> pd.DataFrame:
    """
    Paginated OHLCV fetch from Binance USDM Futures.

    Parameters
    ----------
    ticker    : app-style ticker, e.g. 'BTC-USD'
    timeframe : CCXT timeframe string, e.g. '1h', '4h', '1d', '15m'
    days      : how many calendar days of history to fetch

    Returns
    -------
    DataFrame with columns: Open, High, Low, Close, Volume
    DatetimeIndex in UTC.
    """
    symbol = ticker_to_symbol(ticker)
    since_ms = int(
        (datetime.now(timezone.utc) - pd.Timedelta(days=days)).timestamp() * 1000
    )

    all_bars: list = []
    while True:
        bars = _exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=1000)
        if not bars:
            break
        all_bars.extend(bars)
        last_ts = bars[-1][0]
        if len(bars) < 1000:
            break
        since_ms = last_ts + 1

    if not all_bars:
        raise RuntimeError(
            f"Binance Futures returned no {timeframe} data for {ticker} ({symbol}). "
            "Check ticker name or try again later."
        )

    df = pd.DataFrame(all_bars, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop(columns=["ts"])
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    df = df.dropna()

    if df.empty:
        raise RuntimeError(f"All rows were NaN/empty after cleaning for {ticker}.")

    return df
