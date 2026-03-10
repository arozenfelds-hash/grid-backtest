# Grid Bot Backtester

## Project Overview
Standalone grid/ping-pong bot backtester with Streamlit dashboard.
Data source: **Binance USDM Perpetual Futures** via CCXT (`binanceusdm`).
Supports **557+ coins** — any active USDT-margined perp on Binance.

## Architecture

```
grid-backtest/
├── app.py           # Streamlit dashboard (UI, charts, KPIs)
├── backtester.py    # Grid backtest engine (run_grid_backtest)
├── data_loader.py   # CCXT binanceusdm data fetcher + coin registry
└── requirements.txt # Python dependencies
```

## Key Concepts

### Trading Modes
- **Perps** (`mode="perps"`): USDT-margined futures. Can go short. Only USDT balance needed. Both buy and sell sides always active.
- **Spot** (`mode="spot"`): Spot trading. Cannot go short. Requires initial USDT + token balance. Sells require sufficient token balance; buys require sufficient cash. Orders that can't fill due to balance are skipped and counted.

### Canonical Grid
All orders snap to a single grid: `min_price + n × price_step` (integer n).
This prevents misaligned grids from two different calculation paths.

- `gp(level)` → grid price for integer level
- `gl(price)` → nearest grid level for a price
- `factor_levels = max(1, round(profit_pct / 100 × first_close / price_step))`

### Order Mechanics
On each fill, two orders are spawned:
1. **Profit order** at ±`factor_levels` distance (with `origin` set for RT tracking)
2. **Maintenance order** at ±1 level (keeps both sides populated; `origin=None`)

Profit orders overwrite maintenance orders but not other profit orders.

### Round Trips
A round trip completes when a profit order (one with `origin != None`) fills.
RT profit = price difference × size - 2 × fee.

## Data Loader Details
- Exchange: `ccxt.binanceusdm` (Binance USDM Perpetual Futures)
- Pagination: `limit=1000` per request (Binance max), loop with `since_ms = last_ts + 1`
- Ticker format: `"BTC-USD"` → `"BTC/USDT:USDT"` (app ticker → CCXT symbol)
- Auto-discovery: `_load_markets()` fetches all active USDT linear swaps
- `POPULAR_TICKERS` dict has 25 preset coins with friendly names
- `GRID_DEFAULTS` dict has per-coin `(min_price, price_step)` defaults

## Streamlit App
- Port: `8503` (default)
- Caching: `@st.cache_data(ttl=1800)` on backtest runner
- Sidebar: mode selector (Perps/Spot), coin selector (Popular/All), timeframe, grid params, capital
- Charts: Plotly — price+fills+pending, net tokens, equity, drawdown, RT distribution
- Dark theme with custom CSS

## Common Tasks

### Run the app
```bash
cd ~/grid-backtest && streamlit run app.py --server.port 8503
```

### Add a new popular coin
1. Add to `POPULAR_TICKERS` in `data_loader.py`
2. Add to `GRID_DEFAULTS` with sensible `(min_price, price_step)`
3. Verify the ticker exists: `python3 -c "from data_loader import get_available_tickers; print('COIN-USD' in get_available_tickers())"`

### Important: Binance perps ticker quirks
- MATIC → now `POL-USD` (rebranded)
- PEPE → `1000PEPE-USD` (1000x multiplier on futures)
- Always verify with `get_available_tickers()` before adding

## Dependencies
- `ccxt` (Binance USDM futures)
- `pandas`, `numpy` (data + computation)
- `streamlit` (dashboard)
- `plotly` (charts)

## Style Preferences
- Use `width="stretch"` not `use_container_width=True` (Streamlit deprecation)
- All values in dataframes should be `str` type to avoid Arrow serialization errors
- Guard against division by zero: `if price <= 0: continue/break`
