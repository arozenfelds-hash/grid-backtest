# Tick Backtester — Design Spec

**Date:** 2026-03-15
**Project:** tick-backtester (new repo)
**Server:** root@154.83.140.69, deployed at /opt/tick-backtester
**Related:** grid-backtest (existing OHLCV-based backtester)

## Overview

A tick-by-tick grid trading backtester for Binance USDM perpetual futures. Unlike the existing grid-backtest (which uses OHLCV candles), this project uses actual trade-level (aggTrade) and order book (bookTicker) data for precise fill simulation. Designed for simulation first, architected so live trading can be plugged in later.

## Architecture

Three separate components with clean boundaries:

### 1. Collector Service (24/7 daemon)

Runs as a systemd service. Collects and stores tick data independently of backtesting.

**Historical download:**
- Source: Binance public data archive (`data.binance.vision/data/futures/um/daily/aggTrades/{SYMBOL}/`)
- Downloads daily aggTrade CSVs, converts to Parquet
- CLI: `python collector.py download --symbol BTCUSDT --start 2026-03-01 --end 2026-03-15`

**Live WebSocket streaming:**
- Connects to `wss://fstream.binance.com/ws/{symbol}@aggTrade` and `{symbol}@bookTicker`
- Buffers in memory, flushes to Parquet every 60 seconds
- Daily file rotation at midnight UTC
- Auto-reconnect with exponential backoff
- CLI: `python collector.py stream --symbols BTCUSDT,ETHUSDT`

**Smart gap detection:**
- On startup, scans existing Parquet files for missing days
- Auto-downloads gaps from archive before starting live stream

**Storage layout:**
```
data/ticks/
  BTCUSDT/
    aggTrades/
      2026-03-01.parquet
      2026-03-02.parquet
    bookTicker/
      2026-03-01.parquet
  ETHUSDT/
    ...
```

**aggTrade Parquet schema:**

| Column | Type |
|--------|------|
| agg_trade_id | int64 |
| price | float64 |
| quantity | float64 |
| first_trade_id | int64 |
| last_trade_id | int64 |
| timestamp | int64 (ms) |
| is_buyer_maker | bool |

**bookTicker Parquet schema:**

| Column | Type |
|--------|------|
| timestamp | int64 (ms) |
| best_bid | float64 |
| best_bid_qty | float64 |
| best_ask | float64 |
| best_ask_qty | float64 |

**Estimated storage:** ~3MB/day/symbol compressed. 25 symbols × 30 days ≈ 2.3GB.

### 2. Backtest Engine (pure Python library)

Framework-agnostic library — no web dependencies. Can be imported by Streamlit, FastAPI, or a future live trading bot.

#### Strategy Modes

**Mode 1: Classic Grid**
Same logic as existing grid-backtest but running on tick data. Fixed-size orders at each level, profit + maintenance orders on fill. Serves as a baseline comparison.

**Mode 2: Martingale Grid + Dynamic TP** (primary strategy)

Cycle-based strategy:
1. Place N limit orders (buy or sell or both in hedge mode) spaced by `price_step`
2. Each subsequent order is multiplied by martingale factor (e.g., L1=$100, L2=$150, L3=$225 at 1.5x)
3. Single take-profit order that accumulates — when L1 fills ($100), TP=$100. When L2 fills ($150), TP becomes $250
4. TP price = weighted average entry ± profit target %
5. When TP fills → cycle complete, cancel remaining limit orders, start new cycle immediately
6. Supports long-only, short-only, or both sides simultaneously (Binance hedge mode)

**Parameters:**
- `initial_order_size` — first level order in USDT
- `martingale_factor` — multiplier per level (1.0 = no scaling)
- `num_levels` — number of limit orders per cycle
- `price_step` — distance between levels
- `tp_profit_pct` — take-profit target as % from weighted avg entry
- `direction` — "long", "short", or "hedge"
- `leverage` — 1x to 125x

#### Spread-Aware Execution

Uses bookTicker data for realistic fill simulation:
- Buy limit fills when best ask ≤ order price
- Sell limit fills when best bid ≥ order price
- Toggleable — run with or without for comparison

#### Leverage & Liquidation Engine

**Margin tracking (per tick):**
```
wallet_balance    = initial_capital + realized_pnl
position_size     = Σ filled orders (notional)
margin_used       = position_size / leverage
unrealized_pnl    = position × (mark_price - avg_entry)
margin_balance    = wallet + unrealized_pnl
maint_margin      = position_size × maint_rate
```

**Binance tiered maintenance margin rates:**

| Position (USDT) | Maint Rate |
|------------------|-----------|
| 0 – 50,000 | 0.40% |
| 50,000 – 250,000 | 0.50% |
| 250,000 – 1,000,000 | 1.00% |
| 1,000,000 – 5,000,000 | 2.50% |
| 5,000,000+ | 5.00% |

**Liquidation condition:** `margin_balance ≤ maint_margin`

When liquidation is detected:
- Simulation stops (or records and continues if configured)
- All positions and orders are cancelled
- Liquidation fee applied (based on Binance's liquidation fee schedule)

**Liquidation output metrics:**
- `was_liquidated` (bool)
- `liquidation_price` (float)
- `liquidation_time` (timestamp)
- `min_margin_ratio` (float — closest the account got to liquidation)
- `cycles_before_liquidation` (int)
- `margin_ratio_series` (for charting over time)

#### Engine Output

The engine returns:
- `trades_df` — every fill with timestamp, side, price, qty, notional, margin state
- `cycles_df` — completed cycles with start/end time, levels filled, avg entry, TP price, profit, duration
- `equity_series` — equity over time (per tick where state changes)
- `margin_series` — margin ratio over time
- `metrics_dict` — summary metrics (P&L, return %, win rate, drawdown, fees, liquidation info, etc.)

### 3. Streamlit UI

Reuses Cicada MM corporate design from grid-backtest. Same fonts, colors, theme toggle, logo.

**Sidebar:**
- Cicada logo + "Tick Backtester" + "For internal use only"
- Strategy: Classic Grid / Martingale Grid
- Direction: Long / Short / Hedge
- Symbol selector (popular presets + all Binance perps)
- Date range (based on available tick data)
- Leverage slider (1x–125x)
- Grid params: price_step, num_levels, initial_order_size
- Martingale params: factor, TP profit %
- Spread-aware execution toggle
- Run Backtest button
- Dark/Light theme toggle

**Main area tabs:**

| Tab | Content |
|-----|---------|
| Overview | KPI cards: Total P&L, Return %, Cycles Completed, Win Rate, Max Drawdown, Avg Cycle Profit, Liquidated (yes/no + red warning), Min Margin Ratio, Total Volume, Fees |
| Price & Fills | Tick price chart with buy/sell markers, grid levels overlay, TP level line, cycle boundaries |
| Margin & Risk | Margin ratio over time, liquidation price line, position size over time |
| Cycles | Table of all cycles: start/end time, levels filled, entry avg, TP price, profit, duration |
| Trade Log | Every fill: timestamp, side, price, qty, notional, margin impact |

**Data availability indicator** in sidebar showing which symbols have data, date ranges, and gaps.

## Deployment

**Server:** root@154.83.140.69
**Repo path:** /opt/tick-backtester
**Port:** 8504 (Streamlit app)

**Two systemd services:**
1. `tick-collector` — runs 24/7, collects tick data
2. `tick-backtester` — Streamlit app on port 8504

**Deploy script:** `deploy.sh` — pulls latest, installs deps, builds, restarts services

## File Structure

```
tick-backtester/
├── collector.py          # Data collector (download + websocket)
├── engine.py             # Backtest engine (strategies + margin)
├── strategies/
│   ├── __init__.py
│   ├── classic_grid.py   # Classic grid strategy
│   └── martingale.py     # Martingale grid + dynamic TP
├── margin.py             # Leverage & liquidation tracking
├── data_loader.py        # Read Parquet tick data for engine
├── app.py                # Streamlit dashboard
├── deploy.sh             # Server deployment script
├── requirements.txt      # Dependencies
├── CLAUDE.md             # Project documentation
├── data/                 # Tick data storage (gitignored)
│   └── ticks/
└── assets/               # Cicada logos
    ├── cicada_logo_blue.svg
    └── cicada_logo_white.svg
```

## Dependencies

- ccxt (market info, symbol discovery)
- websockets (live data streaming)
- pandas + pyarrow (Parquet read/write)
- numpy (calculations)
- streamlit (UI)
- plotly (charts)
- aiohttp or httpx (historical data download)

## Future Extensions (out of scope for now)

- Live trading execution via CCXT
- React + FastAPI real-time dashboard
- Multi-exchange support
- Funding rate simulation
