# Tick Backtester Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tick-by-tick grid trading backtester for Binance perpetual futures with historical data download, live WebSocket collection, martingale grid strategy, leverage/liquidation tracking, and Streamlit dashboard.

**Architecture:** Three components — (1) Data collector daemon for downloading historical aggTrade data and streaming live ticks via WebSocket, (2) Pure Python backtest engine with pluggable strategies and margin simulation, (3) Streamlit dashboard with Cicada MM branding. Components communicate only through Parquet files on disk.

**Tech Stack:** Python 3.11+, ccxt, websockets, pandas, pyarrow, numpy, httpx, streamlit, plotly

**Spec:** `docs/superpowers/specs/2026-03-15-tick-backtester-design.md`

---

## Chunk 1: Project Scaffold + Data Loader + Collector

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `~/tick-backtester/requirements.txt`
- Create: `~/tick-backtester/.gitignore`
- Create: `~/tick-backtester/CLAUDE.md`
- Create: `~/tick-backtester/assets/cicada_logo_blue.svg`
- Create: `~/tick-backtester/assets/cicada_logo_white.svg`

- [ ] **Step 1: Create repo and initial files**

```bash
mkdir -p ~/tick-backtester && cd ~/tick-backtester && git init
```

- [ ] **Step 2: Create requirements.txt**

```
ccxt>=4.0
websockets>=12.0
pandas>=2.0
pyarrow>=14.0
numpy>=1.24
httpx>=0.27
streamlit>=1.30
plotly>=5.18
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
data/
venv/
.superpowers/
```

- [ ] **Step 4: Create CLAUDE.md**

Write project documentation covering architecture, file roles, key concepts (martingale grid, margin model, collector), common commands, and style preferences (same as grid-backtest: `width="stretch"`, str values in DataFrames, guard against div-by-zero).

- [ ] **Step 5: Copy logo assets from grid-backtest**

```bash
cp ~/grid-backtest/assets/cicada_logo_blue.svg ~/tick-backtester/assets/
cp ~/grid-backtest/assets/cicada_logo_white.svg ~/tick-backtester/assets/
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: project scaffold with deps, gitignore, docs, assets"
```

- [ ] **Step 7: Create GitHub repo and push**

```bash
cd ~/tick-backtester
gh repo create arozenfelds-hash/tick-backtester --private --source=. --push
```

---

### Task 2: Data loader — read Parquet tick data

**Files:**
- Create: `~/tick-backtester/data_loader.py`
- Create: `~/tick-backtester/tests/test_data_loader.py`

The data loader reads Parquet files from `data/ticks/{SYMBOL}/{aggTrades|bookTicker}/YYYY-MM-DD.parquet` and returns DataFrames for specified symbol and date range.

- [ ] **Step 1: Write failing tests for data_loader**

```python
# tests/test_data_loader.py
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def tick_dir():
    """Create a temp dir with sample Parquet tick files."""
    d = tempfile.mkdtemp()
    base = Path(d) / "ticks" / "BTCUSDT" / "aggTrades"
    base.mkdir(parents=True)

    # Day 1: 3 trades
    df1 = pd.DataFrame({
        "agg_trade_id": [1, 2, 3],
        "price": [50000.0, 50010.0, 49990.0],
        "quantity": [0.1, 0.2, 0.15],
        "first_trade_id": [100, 101, 102],
        "last_trade_id": [100, 101, 102],
        "timestamp": [1709251200000, 1709251260000, 1709251320000],  # 2024-03-01 00:00, 00:01, 00:02 UTC
        "is_buyer_maker": [False, True, False],
    })
    pq.write_table(pa.Table.from_pandas(df1), base / "2024-03-01.parquet", compression="zstd")

    # Day 2: 2 trades
    df2 = pd.DataFrame({
        "agg_trade_id": [4, 5],
        "price": [50050.0, 50100.0],
        "quantity": [0.3, 0.05],
        "first_trade_id": [103, 104],
        "last_trade_id": [103, 104],
        "timestamp": [1709337600000, 1709337660000],  # 2024-03-02
        "is_buyer_maker": [True, False],
    })
    pq.write_table(pa.Table.from_pandas(df2), base / "2024-03-02.parquet", compression="zstd")

    yield d
    shutil.rmtree(d)


def test_load_agg_trades_full_range(tick_dir):
    from data_loader import load_ticks
    df = load_ticks(tick_dir, "BTCUSDT", "aggTrades", "2024-03-01", "2024-03-02")
    assert len(df) == 5
    assert list(df.columns) == ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "timestamp", "is_buyer_maker"]


def test_load_agg_trades_single_day(tick_dir):
    from data_loader import load_ticks
    df = load_ticks(tick_dir, "BTCUSDT", "aggTrades", "2024-03-01", "2024-03-01")
    assert len(df) == 3


def test_load_missing_symbol(tick_dir):
    from data_loader import load_ticks
    df = load_ticks(tick_dir, "ETHUSDT", "aggTrades", "2024-03-01", "2024-03-02")
    assert len(df) == 0


def test_available_symbols(tick_dir):
    from data_loader import get_available_symbols
    syms = get_available_symbols(tick_dir)
    assert "BTCUSDT" in syms


def test_available_date_range(tick_dir):
    from data_loader import get_date_range
    start, end = get_date_range(tick_dir, "BTCUSDT", "aggTrades")
    assert start == "2024-03-01"
    assert end == "2024-03-02"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/tick-backtester && python -m pytest tests/test_data_loader.py -v
```

Expected: FAIL — `data_loader` module not found.

- [ ] **Step 3: Implement data_loader.py**

```python
# data_loader.py
"""Load Parquet tick data from disk for backtesting."""

from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import pyarrow.parquet as pq


def load_ticks(
    data_dir: str,
    symbol: str,
    data_type: str,  # "aggTrades" or "bookTicker"
    start_date: str,  # "YYYY-MM-DD"
    end_date: str,
) -> pd.DataFrame:
    """Load tick data for symbol in date range. Returns empty DataFrame if no data."""
    base = Path(data_dir) / "ticks" / symbol / data_type
    if not base.exists():
        return pd.DataFrame()

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    frames = []
    d = start
    while d <= end:
        f = base / f"{d.isoformat()}.parquet"
        if f.exists():
            frames.append(pq.read_table(f).to_pandas())
        d += timedelta(days=1)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def get_available_symbols(data_dir: str) -> list[str]:
    """List symbols that have tick data."""
    ticks = Path(data_dir) / "ticks"
    if not ticks.exists():
        return []
    return sorted([d.name for d in ticks.iterdir() if d.is_dir()])


def get_date_range(data_dir: str, symbol: str, data_type: str) -> tuple[str, str] | None:
    """Return (start_date, end_date) for a symbol's data. None if no data."""
    base = Path(data_dir) / "ticks" / symbol / data_type
    if not base.exists():
        return None
    files = sorted(base.glob("*.parquet"))
    if not files:
        return None
    start = files[0].stem
    end = files[-1].stem
    return start, end
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/tick-backtester && python -m pytest tests/test_data_loader.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data_loader.py tests/test_data_loader.py && git commit -m "feat: data loader for Parquet tick files"
```

---

### Task 3: Collector — historical aggTrade download

**Files:**
- Create: `~/tick-backtester/collector.py`
- Create: `~/tick-backtester/tests/test_collector.py`

Downloads daily aggTrade CSVs from Binance public data archive, converts to Parquet with zstd compression. CLI: `python collector.py download --symbol BTCUSDT --start 2026-03-01 --end 2026-03-15`

- [ ] **Step 1: Write failing test for download logic**

```python
# tests/test_collector.py
import pandas as pd
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch


def test_csv_to_parquet_conversion():
    """Test that raw CSV data gets correctly converted to Parquet."""
    from collector import _csv_bytes_to_parquet

    # Binance aggTrade CSV format (no header):
    # agg_trade_id, price, quantity, first_trade_id, last_trade_id, timestamp, is_buyer_maker
    csv_data = b"1,50000.00,0.100,100,100,1709251200000,false\n2,50010.00,0.200,101,101,1709251260000,true\n"

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "2024-03-01.parquet"
        _csv_bytes_to_parquet(csv_data, out)

        df = pd.read_parquet(out)
        assert len(df) == 2
        assert df["price"].iloc[0] == 50000.0
        assert df["is_buyer_maker"].iloc[1] == True
        assert df["agg_trade_id"].dtype == "int64"


def test_build_download_url():
    from collector import _build_download_url
    url = _build_download_url("BTCUSDT", "2024-03-01")
    assert "data.binance.vision" in url
    assert "BTCUSDT" in url
    assert "2024-03-01" in url
    assert url.endswith(".zip")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/tick-backtester && python -m pytest tests/test_collector.py -v
```

- [ ] **Step 3: Implement download functions in collector.py**

```python
# collector.py
"""Tick data collector: historical download + live WebSocket streaming."""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import zipfile
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

AGG_TRADE_COLUMNS = [
    "agg_trade_id", "price", "quantity", "first_trade_id",
    "last_trade_id", "timestamp", "is_buyer_maker",
]
AGG_TRADE_DTYPES = {
    "agg_trade_id": "int64", "price": "float64", "quantity": "float64",
    "first_trade_id": "int64", "last_trade_id": "int64",
    "timestamp": "int64", "is_buyer_maker": "bool",
}


def _build_download_url(symbol: str, date_str: str) -> str:
    return (
        f"https://data.binance.vision/data/futures/um/daily/aggTrades/"
        f"{symbol}/{symbol}-aggTrades-{date_str}.zip"
    )


def _csv_bytes_to_parquet(csv_bytes: bytes, out_path: Path) -> None:
    """Convert raw Binance aggTrade CSV bytes to a zstd Parquet file."""
    df = pd.read_csv(
        io.BytesIO(csv_bytes),
        header=None,
        names=AGG_TRADE_COLUMNS,
        dtype=AGG_TRADE_DTYPES,
    )
    # Binance CSVs sometimes have a header row — drop if first row is non-numeric
    if df.iloc[0]["agg_trade_id"] == 0 or not str(df.iloc[0]["price"]).replace(".", "").isdigit():
        df = df.iloc[1:]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path, compression="zstd")


async def download_day(client: httpx.AsyncClient, symbol: str, day: str, data_dir: Path) -> bool:
    """Download one day of aggTrade data. Returns True if successful."""
    out_path = data_dir / "ticks" / symbol / "aggTrades" / f"{day}.parquet"
    if out_path.exists():
        log.info(f"  {day}: already exists, skipping")
        return True

    url = _build_download_url(symbol, day)
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 404:
            log.warning(f"  {day}: not available on archive (404)")
            return False
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.error(f"  {day}: download failed: {e}")
        return False

    # Binance serves a .zip containing one .csv
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = zf.namelist()[0]
        csv_bytes = zf.read(csv_name)

    _csv_bytes_to_parquet(csv_bytes, out_path)
    log.info(f"  {day}: saved ({out_path.stat().st_size / 1024:.0f} KB)")
    return True


async def download_range(symbol: str, start: str, end: str, data_dir: Path | None = None) -> None:
    """Download aggTrade data for a symbol over a date range."""
    if data_dir is None:
        data_dir = DATA_DIR

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    days = []
    d = start_d
    while d <= end_d:
        days.append(d.isoformat())
        d += timedelta(days=1)

    log.info(f"Downloading {symbol} aggTrades: {start} to {end} ({len(days)} days)")

    async with httpx.AsyncClient(timeout=60) as client:
        for day in days:
            await download_day(client, symbol, day, data_dir)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tick data collector")
    sub = parser.add_subparsers(dest="command")

    dl = sub.add_parser("download", help="Download historical aggTrade data")
    dl.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    dl.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    dl.add_argument("--end", required=True, help="End date YYYY-MM-DD")

    st = sub.add_parser("status", help="Show data status")

    args = parser.parse_args()

    if args.command == "download":
        asyncio.run(download_range(args.symbol, args.start, args.end))
    elif args.command == "status":
        from data_loader import get_available_symbols, get_date_range
        for sym in get_available_symbols(str(DATA_DIR)):
            rng = get_date_range(str(DATA_DIR), sym, "aggTrades")
            if rng:
                print(f"  {sym}: {rng[0]} → {rng[1]}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/tick-backtester && python -m pytest tests/test_collector.py -v
```

- [ ] **Step 5: Integration test — download 1 day of real data**

```bash
cd ~/tick-backtester && python collector.py download --symbol BTCUSDT --start 2024-03-01 --end 2024-03-01
python collector.py status
```

Expected: downloads, converts, shows `BTCUSDT: 2024-03-01 → 2024-03-01`

- [ ] **Step 6: Commit**

```bash
git add collector.py tests/test_collector.py && git commit -m "feat: collector with historical aggTrade download from Binance archive"
```

---

### Task 4: Collector — live WebSocket streaming

**Files:**
- Modify: `~/tick-backtester/collector.py`

Add WebSocket streaming for aggTrade + bookTicker. Buffer in memory, flush to Parquet every 60s, daily rotation, auto-reconnect.

- [ ] **Step 1: Add websocket streaming to collector.py**

Add to collector.py after the download functions:

```python
import json
import time
import websockets
from collections import defaultdict

BOOK_TICKER_COLUMNS = ["timestamp", "best_bid", "best_bid_qty", "best_ask", "best_ask_qty"]

class TickBuffer:
    """Buffer ticks in memory, flush to Parquet periodically."""

    def __init__(self, data_dir: Path, flush_interval: int = 60):
        self.data_dir = data_dir
        self.flush_interval = flush_interval
        self.buffers: dict[str, list[dict]] = defaultdict(list)  # key = "SYMBOL/TYPE"
        self.last_flush = time.time()
        self.tick_counts: dict[str, int] = defaultdict(int)
        self.last_tick_time: dict[str, float] = {}

    def add_agg_trade(self, symbol: str, data: dict) -> None:
        key = f"{symbol}/aggTrades"
        self.buffers[key].append({
            "agg_trade_id": int(data["a"]),
            "price": float(data["p"]),
            "quantity": float(data["q"]),
            "first_trade_id": int(data["f"]),
            "last_trade_id": int(data["l"]),
            "timestamp": int(data["T"]),
            "is_buyer_maker": data["m"],
        })
        self.tick_counts[key] += 1
        self.last_tick_time[key] = time.time()

    def add_book_ticker(self, symbol: str, data: dict) -> None:
        key = f"{symbol}/bookTicker"
        self.buffers[key].append({
            "timestamp": int(data["T"]) if "T" in data else int(time.time() * 1000),
            "best_bid": float(data["b"]),
            "best_bid_qty": float(data["B"]),
            "best_ask": float(data["a"]),
            "best_ask_qty": float(data["A"]),
        })
        self.tick_counts[key] += 1
        self.last_tick_time[key] = time.time()

    def should_flush(self) -> bool:
        return time.time() - self.last_flush >= self.flush_interval

    def flush(self) -> None:
        """Write buffered data to Parquet files (atomic rename)."""
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for key, rows in self.buffers.items():
            if not rows:
                continue
            symbol, dtype = key.split("/")
            out_dir = self.data_dir / "ticks" / symbol / dtype
            out_dir.mkdir(parents=True, exist_ok=True)

            out_path = out_dir / f"{today}.parquet"
            tmp_path = out_dir / f".{today}.tmp.parquet"

            df_new = pd.DataFrame(rows)

            # Append to existing file if present
            if out_path.exists():
                df_existing = pd.read_parquet(out_path)
                df_new = pd.concat([df_existing, df_new], ignore_index=True)

            table = pa.Table.from_pandas(df_new, preserve_index=False)
            pq.write_table(table, tmp_path, compression="zstd")
            tmp_path.rename(out_path)  # atomic rename

        # Log heartbeat
        for key, count in self.tick_counts.items():
            log.info(f"  Heartbeat: {key} — {count} ticks total")

        self.buffers.clear()
        self.last_flush = time.time()


async def _stream_symbol(symbol: str, buffer: TickBuffer) -> None:
    """Connect to Binance WebSocket for one symbol (aggTrade + bookTicker)."""
    streams = f"{symbol.lower()}@aggTrade/{symbol.lower()}@bookTicker"
    url = f"wss://fstream.binance.com/stream?streams={streams}"
    backoff = 1

    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info(f"Connected: {symbol}")
                backoff = 1
                async for msg in ws:
                    data = json.loads(msg)
                    stream = data.get("stream", "")
                    payload = data.get("data", {})

                    if "aggTrade" in stream:
                        buffer.add_agg_trade(symbol, payload)
                    elif "bookTicker" in stream:
                        buffer.add_book_ticker(symbol, payload)

                    if buffer.should_flush():
                        buffer.flush()

        except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
            log.warning(f"{symbol} disconnected: {e}. Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def stream_symbols(symbols: list[str], data_dir: Path | None = None) -> None:
    """Stream tick data for multiple symbols concurrently."""
    if data_dir is None:
        data_dir = DATA_DIR

    buffer = TickBuffer(data_dir)
    tasks = [_stream_symbol(sym, buffer) for sym in symbols]
    await asyncio.gather(*tasks)
```

- [ ] **Step 2: Add `stream` CLI command**

Update the `main()` function's subparser:

```python
    sm = sub.add_parser("stream", help="Stream live tick data via WebSocket")
    sm.add_argument("--symbols", required=True, help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT")
```

And in the command handler:

```python
    elif args.command == "stream":
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
        log.info(f"Starting live stream for: {symbols}")
        asyncio.run(stream_symbols(symbols))
```

- [ ] **Step 3: Add gap detection to collector**

Before starting live stream, scan existing Parquet files for missing or partial days. Download missing days from archive. Add to `stream_symbols()`:

```python
async def _fill_gaps(symbols: list[str], data_dir: Path) -> None:
    """Detect and fill gaps in historical data before starting live stream."""
    from data_loader import get_date_range
    from datetime import date, timedelta

    today = date.today()
    async with httpx.AsyncClient(timeout=60) as client:
        for sym in symbols:
            rng = get_date_range(str(data_dir), sym, "aggTrades")
            if rng is None:
                # No data at all — download last 7 days
                start = today - timedelta(days=7)
                await download_range(sym, start.isoformat(), (today - timedelta(days=1)).isoformat(), data_dir)
                continue

            # Check for missing days in range
            start_d = date.fromisoformat(rng[0])
            end_d = today - timedelta(days=1)
            d = start_d
            while d <= end_d:
                f = data_dir / "ticks" / sym / "aggTrades" / f"{d.isoformat()}.parquet"
                if not f.exists():
                    log.info(f"Gap detected: {sym} {d} — downloading")
                    await download_day(client, sym, d.isoformat(), data_dir)
                else:
                    # Check for partial day (first/last timestamp)
                    df = pd.read_parquet(f)
                    if len(df) > 0:
                        first_ts = int(df["timestamp"].iloc[0])
                        last_ts = int(df["timestamp"].iloc[-1])
                        day_start = int(pd.Timestamp(d).timestamp() * 1000)
                        day_end = day_start + 86400000 - 1
                        # If data covers less than 20 hours, consider partial
                        if (last_ts - first_ts) < 72000000:
                            log.info(f"Partial day detected: {sym} {d} — re-downloading")
                            f.unlink()
                            await download_day(client, sym, d.isoformat(), data_dir)
                d += timedelta(days=1)
```

- [ ] **Step 4: Add data retention and disk monitoring to TickBuffer**

Add to `TickBuffer.flush()`:

```python
def _prune_old_files(self, retention_days: int = 90) -> None:
    """Delete Parquet files older than retention period."""
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    ticks_dir = self.data_dir / "ticks"
    if not ticks_dir.exists():
        return
    for sym_dir in ticks_dir.iterdir():
        for dtype_dir in sym_dir.iterdir():
            for f in dtype_dir.glob("*.parquet"):
                if f.stem < cutoff:
                    f.unlink()
                    log.info(f"Pruned old file: {f}")

def _check_disk_usage(self) -> None:
    """Warn if disk usage exceeds 80%."""
    import shutil
    usage = shutil.disk_usage(self.data_dir)
    pct = usage.used / usage.total * 100
    log.info(f"Disk usage: {pct:.1f}%")
    if pct > 80:
        log.warning(f"⚠️ Disk usage at {pct:.1f}% — consider increasing retention pruning")
```

Call `_prune_old_files()` once per day (on daily rotation) and `_check_disk_usage()` on each flush.

- [ ] **Step 5: Add staleness detection to TickBuffer**

```python
def check_stale_symbols(self) -> None:
    """Warn if no ticks received for a symbol in 5 minutes."""
    now = time.time()
    for key, last in self.last_tick_time.items():
        if now - last > 300:  # 5 minutes
            log.warning(f"⚠️ No ticks for {key} in {int(now - last)}s")
```

Call from `flush()` on each heartbeat cycle.

- [ ] **Step 6: Manual test — stream for 2 minutes**

```bash
cd ~/tick-backtester && timeout 120 python collector.py stream --symbols BTCUSDT 2>&1 | tail -20
```

Expected: gap detection logs, connection message, heartbeat logs every 60s with tick counts + disk usage. Check `data/ticks/BTCUSDT/aggTrades/` and `bookTicker/` for today's Parquet file.

- [ ] **Step 7: Commit**

```bash
git add collector.py && git commit -m "feat: live WebSocket streaming with gap detection, retention, health monitoring"
```

---

## Chunk 2: Margin Engine + Martingale Strategy

### Task 5: Margin engine — leverage & liquidation tracking

**Files:**
- Create: `~/tick-backtester/margin.py`
- Create: `~/tick-backtester/tests/test_margin.py`

Pure calculation module. Tracks wallet balance, position, margin ratio, and detects liquidation.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_margin.py
import pytest


def test_initial_state():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=10000, leverage=10)
    assert mt.wallet_balance == 10000
    assert mt.position_qty == 0
    assert mt.is_liquidated == False


def test_open_long_position():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=10000, leverage=10)
    mt.add_fill("buy", price=50000, qty=0.1, fee=1.0)
    assert mt.position_qty == pytest.approx(0.1)
    assert mt.avg_entry == pytest.approx(50000)
    assert mt.wallet_balance == pytest.approx(9999.0)  # minus fee


def test_margin_ratio():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=10000, leverage=10)
    mt.add_fill("buy", price=50000, qty=0.1, fee=1.0)
    ratio = mt.margin_ratio(mark_price=50000)
    # margin_balance = 9999 + 0 unrealized = 9999
    # maint_margin = 5000 * 0.004 = 20 (0.40% for <50k bracket)
    # ratio = 9999 / 20 = ~499
    assert ratio > 100  # healthy


def test_liquidation_detection():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=100, leverage=50)
    mt.add_fill("buy", price=50000, qty=0.1, fee=0.0)
    # position notional = 5000, margin_used = 100 (= all capital)
    # Price drops: unrealized = 0.1 * (48000 - 50000) = -200
    # margin_balance = 100 + (-200) = -100 < maint_margin
    assert mt.check_liquidation(mark_price=48000) == True


def test_close_position_pnl():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=10000, leverage=10)
    mt.add_fill("buy", price=50000, qty=0.1, fee=1.0)
    mt.add_fill("sell", price=51000, qty=0.1, fee=1.02)
    # Realized PnL = 0.1 * (51000 - 50000) = 100, minus 2.02 fees = 97.98
    assert mt.position_qty == pytest.approx(0)
    assert mt.wallet_balance == pytest.approx(10000 - 1.0 - 1.02 + 100)  # 10097.98


def test_short_position():
    from margin import MarginTracker
    mt = MarginTracker(initial_capital=10000, leverage=10)
    mt.add_fill("sell", price=50000, qty=0.1, fee=1.0)
    assert mt.position_qty == pytest.approx(-0.1)
    assert mt.avg_entry == pytest.approx(50000)
    # Price goes up = loss for short
    unrealized = mt.unrealized_pnl(mark_price=51000)
    assert unrealized == pytest.approx(-100)  # -0.1 * (51000 - 50000)


def test_tiered_maint_rate():
    from margin import get_maint_margin
    # < 50k: 0.4%
    assert get_maint_margin(10000) == pytest.approx(40)
    # 50k-250k: first 50k at 0.4% + remainder at 0.5%
    assert get_maint_margin(100000) == pytest.approx(50000 * 0.004 + 50000 * 0.005)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/tick-backtester && python -m pytest tests/test_margin.py -v
```

- [ ] **Step 3: Implement margin.py**

```python
# margin.py
"""Leverage & liquidation tracking for perpetual futures backtesting."""

from __future__ import annotations
from dataclasses import dataclass, field

# Default Binance BTCUSDT maintenance margin brackets
# (max_notional, maint_rate)
DEFAULT_BRACKETS = [
    (50_000, 0.004),
    (250_000, 0.005),
    (1_000_000, 0.01),
    (5_000_000, 0.025),
    (float("inf"), 0.05),
]

LIQUIDATION_FEE_RATE = 0.005  # 0.5% of notional


def get_maint_margin(position_notional: float, brackets: list | None = None) -> float:
    """Calculate maintenance margin using tiered brackets."""
    if brackets is None:
        brackets = DEFAULT_BRACKETS

    remaining = abs(position_notional)
    maint = 0.0
    prev_cap = 0.0

    for cap, rate in brackets:
        tier_size = min(remaining, cap - prev_cap)
        if tier_size <= 0:
            break
        maint += tier_size * rate
        remaining -= tier_size
        prev_cap = cap

    return maint


@dataclass
class MarginTracker:
    """Track margin state for a single direction (long or short)."""

    initial_capital: float
    leverage: int
    brackets: list = field(default_factory=lambda: list(DEFAULT_BRACKETS))

    # State
    wallet_balance: float = 0.0
    position_qty: float = 0.0  # positive = long, negative = short
    avg_entry: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    is_liquidated: bool = False
    liquidation_price: float | None = None
    liquidation_time: int | None = None
    min_margin_ratio: float = float("inf")

    def __post_init__(self):
        self.wallet_balance = self.initial_capital

    def add_fill(self, side: str, price: float, qty: float, fee: float) -> None:
        """Process a fill. side = 'buy' or 'sell'."""
        self.wallet_balance -= fee
        self.total_fees += fee

        if side == "buy":
            if self.position_qty >= 0:
                # Adding to long / opening long
                total_cost = self.avg_entry * self.position_qty + price * qty
                self.position_qty += qty
                self.avg_entry = total_cost / self.position_qty if self.position_qty > 0 else 0
            else:
                # Closing short
                close_qty = min(qty, abs(self.position_qty))
                pnl = close_qty * (self.avg_entry - price)  # short profit = entry - exit
                self.realized_pnl += pnl
                self.wallet_balance += pnl
                self.position_qty += qty
                if self.position_qty > 0:
                    # Flipped to long
                    self.avg_entry = price
                elif self.position_qty == 0:
                    self.avg_entry = 0
        else:  # sell
            if self.position_qty <= 0:
                # Adding to short / opening short
                total_cost = self.avg_entry * abs(self.position_qty) + price * qty
                self.position_qty -= qty
                self.avg_entry = total_cost / abs(self.position_qty) if self.position_qty != 0 else 0
            else:
                # Closing long
                close_qty = min(qty, self.position_qty)
                pnl = close_qty * (price - self.avg_entry)  # long profit = exit - entry
                self.realized_pnl += pnl
                self.wallet_balance += pnl
                self.position_qty -= qty
                if self.position_qty < 0:
                    # Flipped to short
                    self.avg_entry = price
                elif self.position_qty == 0:
                    self.avg_entry = 0

    def unrealized_pnl(self, mark_price: float) -> float:
        if self.position_qty == 0:
            return 0.0
        return self.position_qty * (mark_price - self.avg_entry)

    def position_notional(self, mark_price: float) -> float:
        return abs(self.position_qty) * mark_price

    def margin_balance(self, mark_price: float) -> float:
        return self.wallet_balance + self.unrealized_pnl(mark_price)

    def margin_ratio(self, mark_price: float) -> float:
        """Margin balance / maintenance margin. <1.0 = liquidation."""
        notional = self.position_notional(mark_price)
        if notional == 0:
            return float("inf")
        maint = get_maint_margin(notional, self.brackets)
        if maint == 0:
            return float("inf")
        ratio = self.margin_balance(mark_price) / maint
        self.min_margin_ratio = min(self.min_margin_ratio, ratio)
        return ratio

    def check_liquidation(self, mark_price: float, timestamp: int = 0) -> bool:
        """Check if position should be liquidated at this price."""
        if self.position_qty == 0:
            return False
        ratio = self.margin_ratio(mark_price)
        if ratio <= 1.0:
            self.is_liquidated = True
            self.liquidation_price = mark_price
            self.liquidation_time = timestamp
            # Apply liquidation fee
            liq_fee = self.position_notional(mark_price) * LIQUIDATION_FEE_RATE
            self.wallet_balance -= liq_fee
            self.total_fees += liq_fee
            # Close position at mark price
            self.position_qty = 0
            self.avg_entry = 0
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/tick-backtester && python -m pytest tests/test_margin.py -v
```

- [ ] **Step 5: Commit**

```bash
git add margin.py tests/test_margin.py && git commit -m "feat: margin engine with tiered maintenance rates and liquidation"
```

---

### Task 6: Martingale grid strategy

**Files:**
- Create: `~/tick-backtester/strategies/__init__.py`
- Create: `~/tick-backtester/strategies/martingale.py`
- Create: `~/tick-backtester/tests/test_martingale.py`

Implements the cycle-based martingale strategy with dynamic TP.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_martingale.py
import pytest


def test_grid_order_placement():
    """Test initial grid orders are placed with martingale scaling."""
    from strategies.martingale import MartingaleGrid

    mg = MartingaleGrid(
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=3,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
    )
    orders = mg.place_grid(current_price=50000)

    assert len(orders) == 3
    # Level 1: $100 @ 49950
    assert orders[0]["price"] == pytest.approx(49950)
    assert orders[0]["size_usd"] == pytest.approx(100)
    assert orders[0]["side"] == "buy"
    # Level 2: $150 @ 49900
    assert orders[1]["price"] == pytest.approx(49900)
    assert orders[1]["size_usd"] == pytest.approx(150)
    # Level 3: $225 @ 49850
    assert orders[2]["price"] == pytest.approx(49850)
    assert orders[2]["size_usd"] == pytest.approx(225)


def test_tp_after_first_fill():
    """After first fill, TP should be placed."""
    from strategies.martingale import MartingaleGrid

    mg = MartingaleGrid(
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=3,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
    )
    mg.place_grid(current_price=50000)
    tp = mg.on_fill(level=0, fill_price=49950)

    assert tp is not None
    assert tp["side"] == "sell"
    assert tp["size_usd"] == pytest.approx(100)
    # TP price = avg_entry * (1 + 0.5/100)
    assert tp["price"] == pytest.approx(49950 * 1.005)


def test_tp_accumulates_on_second_fill():
    """After second fill, TP size should include both fills."""
    from strategies.martingale import MartingaleGrid

    mg = MartingaleGrid(
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=3,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
    )
    mg.place_grid(current_price=50000)
    mg.on_fill(level=0, fill_price=49950)
    tp = mg.on_fill(level=1, fill_price=49900)

    assert tp["size_usd"] == pytest.approx(250)  # 100 + 150
    # Weighted avg entry: (100*49950 + 150*49900) / 250 = 49920
    avg = (100 * 49950 + 150 * 49900) / 250
    assert tp["price"] == pytest.approx(avg * 1.005)


def test_cycle_complete_on_tp_fill():
    """TP fill should complete the cycle."""
    from strategies.martingale import MartingaleGrid

    mg = MartingaleGrid(
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=3,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
    )
    mg.place_grid(current_price=50000)
    mg.on_fill(level=0, fill_price=49950)
    result = mg.on_tp_fill()

    assert result["cycle_complete"] == True
    assert result["profit_usd"] > 0
    assert mg.cycle_count == 1
    assert len(mg.pending_orders) == 0  # all cancelled


def test_short_direction():
    """Short grid should place sell orders above price."""
    from strategies.martingale import MartingaleGrid

    mg = MartingaleGrid(
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=3,
        price_step=50,
        tp_profit_pct=0.5,
        direction="short",
    )
    orders = mg.place_grid(current_price=50000)

    assert orders[0]["side"] == "sell"
    assert orders[0]["price"] == pytest.approx(50050)
    assert orders[1]["price"] == pytest.approx(50100)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/tick-backtester && python -m pytest tests/test_martingale.py -v
```

- [ ] **Step 3: Implement strategies/martingale.py**

```python
# strategies/martingale.py
"""Martingale Grid strategy with dynamic take-profit."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class MartingaleGrid:
    """Martingale grid with accumulating dynamic TP."""

    initial_order_size: float  # USDT
    martingale_factor: float   # e.g. 1.5
    num_levels: int
    price_step: float          # absolute USDT
    tp_profit_pct: float       # e.g. 0.5 for 0.5%
    direction: str             # "long", "short", or "hedge"

    # State
    pending_orders: dict = field(default_factory=dict)  # {level: order_dict}
    filled_levels: list = field(default_factory=list)    # [(level, price, size_usd)]
    tp_order: dict | None = None
    cycle_count: int = 0
    total_filled_usd: float = 0.0
    weighted_entry_sum: float = 0.0  # Σ(size_usd * fill_price)

    def _order_size(self, level: int) -> float:
        """Calculate order size for a given level (0-indexed)."""
        return self.initial_order_size * (self.martingale_factor ** level)

    def _is_long_side(self) -> bool:
        return self.direction in ("long", "hedge")

    def _is_short_side(self) -> bool:
        return self.direction in ("short", "hedge")

    def place_grid(self, current_price: float) -> list[dict]:
        """Place initial grid orders for a new cycle. Returns list of orders."""
        self.pending_orders.clear()
        self.filled_levels.clear()
        self.tp_order = None
        self.total_filled_usd = 0.0
        self.weighted_entry_sum = 0.0

        orders = []

        if self._is_long_side():
            for i in range(self.num_levels):
                price = current_price - (i + 1) * self.price_step
                if price <= 0:
                    break
                size = self._order_size(i)
                # In hedge mode, use negative keys for long side to avoid collision
                key = i if self.direction != "hedge" else ("long", i)
                order = {"level": i, "side": "buy", "price": price, "size_usd": size, "grid_side": "long"}
                self.pending_orders[key] = order
                orders.append(order)

        if self._is_short_side():
            for i in range(self.num_levels):
                price = current_price + (i + 1) * self.price_step
                size = self._order_size(i)
                key = i if self.direction != "hedge" else ("short", i)
                order = {"level": i, "side": "sell", "price": price, "size_usd": size, "grid_side": "short"}
                self.pending_orders[key] = order
                orders.append(order)

        return orders

    def on_fill(self, level: int, fill_price: float) -> dict | None:
        """Handle a grid order fill. Returns updated TP order or None."""
        if level not in self.pending_orders:
            return None

        order = self.pending_orders.pop(level)
        size_usd = order["size_usd"]

        self.filled_levels.append((level, fill_price, size_usd))
        self.total_filled_usd += size_usd
        self.weighted_entry_sum += size_usd * fill_price

        # Calculate weighted average entry
        avg_entry = self.weighted_entry_sum / self.total_filled_usd

        # Calculate TP price
        if self.direction in ("long", "hedge"):
            tp_price = avg_entry * (1 + self.tp_profit_pct / 100)
            tp_side = "sell"
        else:
            tp_price = avg_entry * (1 - self.tp_profit_pct / 100)
            tp_side = "buy"

        self.tp_order = {
            "side": tp_side,
            "price": tp_price,
            "size_usd": self.total_filled_usd,
            "avg_entry": avg_entry,
        }

        return self.tp_order

    def on_tp_fill(self) -> dict:
        """Handle TP fill. Returns cycle result."""
        if not self.tp_order or not self.filled_levels:
            return {"cycle_complete": False}

        avg_entry = self.tp_order["avg_entry"]
        tp_price = self.tp_order["price"]
        size_usd = self.tp_order["size_usd"]

        if self.direction in ("long", "hedge"):
            profit = size_usd * (tp_price - avg_entry) / avg_entry
        else:
            profit = size_usd * (avg_entry - tp_price) / avg_entry

        self.cycle_count += 1
        levels_filled = len(self.filled_levels)

        # Cancel remaining pending orders
        self.pending_orders.clear()
        self.tp_order = None
        self.filled_levels.clear()
        self.total_filled_usd = 0.0
        self.weighted_entry_sum = 0.0

        return {
            "cycle_complete": True,
            "profit_usd": profit,
            "levels_filled": levels_filled,
            "avg_entry": avg_entry,
            "tp_price": tp_price,
            "cycle_number": self.cycle_count,
        }
```

Also create `strategies/__init__.py`:

```python
# strategies/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/tick-backtester && python -m pytest tests/test_martingale.py -v
```

- [ ] **Step 5: Commit**

```bash
git add strategies/ tests/test_martingale.py && git commit -m "feat: martingale grid strategy with dynamic TP"
```

---

### Task 6b: Classic Grid strategy

**Files:**
- Create: `~/tick-backtester/strategies/classic_grid.py`
- Create: `~/tick-backtester/tests/test_classic_grid.py`

Port the existing grid-backtest logic to work as a strategy plugin with the same interface as MartingaleGrid. Reference `~/grid-backtest/backtester.py` for the canonical grid, profit/maintenance order mechanics, and round-trip tracking.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_classic_grid.py
import pytest

def test_initial_grid_placement():
    from strategies.classic_grid import ClassicGrid
    cg = ClassicGrid(
        min_price=40000, price_step=100, order_size_usd=50,
        profit_pct=1.0, n_init_above=3,
    )
    orders = cg.place_grid(current_price=50000)
    buys = [o for o in orders if o["side"] == "buy"]
    sells = [o for o in orders if o["side"] == "sell"]
    assert len(sells) == 3
    assert len(buys) > 0
    # Sells should be above current price
    assert all(o["price"] > 50000 for o in sells)

def test_fill_spawns_profit_and_maintenance():
    from strategies.classic_grid import ClassicGrid
    cg = ClassicGrid(
        min_price=40000, price_step=100, order_size_usd=50,
        profit_pct=1.0, n_init_above=3,
    )
    cg.place_grid(current_price=50000)
    initial_count = len(cg.pending_orders)
    # Simulate a buy fill
    buy_prices = sorted([p for p, o in cg.pending_orders.items() if o["side"] == "buy"], reverse=True)
    fill_price = buy_prices[0]
    new_orders = cg.on_fill(fill_price)
    # Should spawn a profit sell and possibly a maintenance buy
    assert any(o["side"] == "sell" for o in new_orders)
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement classic_grid.py**

Adapt the logic from `~/grid-backtest/backtester.py` into a class with `place_grid()`, `on_fill()`, and `pending_orders` dict matching the interface the engine expects. Use the canonical grid helpers (`gp`, `gl`, `factor_levels`).

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add strategies/classic_grid.py tests/test_classic_grid.py && git commit -m "feat: classic grid strategy ported from grid-backtest"
```

---

## Chunk 3: Backtest Engine

### Task 7: Backtest engine — orchestrate strategy + margin on tick data

**Files:**
- Create: `~/tick-backtester/engine.py`
- Create: `~/tick-backtester/tests/test_engine.py`

The engine reads tick data via data_loader, runs a strategy tick-by-tick, tracks margin via MarginTracker, and produces trades_df, cycles_df, equity_series, margin_series, and metrics_dict.

- [ ] **Step 1: Write failing test**

```python
# tests/test_engine.py
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_tick_dir():
    """Create tick data that simulates a price drop and recovery (martingale cycle)."""
    d = tempfile.mkdtemp()
    base = Path(d) / "ticks" / "BTCUSDT" / "aggTrades"
    base.mkdir(parents=True)

    # Price: 50000 → drops to 49900 (fills 2 levels) → recovers to TP
    prices = [50000, 49980, 49950, 49920, 49900, 49920, 49950, 49980, 50000, 50020, 50050]
    ts_base = 1709251200000  # 2024-03-01 00:00 UTC

    df = pd.DataFrame({
        "agg_trade_id": list(range(len(prices))),
        "price": [float(p) for p in prices],
        "quantity": [0.1] * len(prices),
        "first_trade_id": list(range(len(prices))),
        "last_trade_id": list(range(len(prices))),
        "timestamp": [ts_base + i * 60000 for i in range(len(prices))],
        "is_buyer_maker": [i % 2 == 0 for i in range(len(prices))],
    })
    pq.write_table(pa.Table.from_pandas(df), base / "2024-03-01.parquet", compression="zstd")

    yield d
    import shutil
    shutil.rmtree(d)


def test_engine_basic_run(sample_tick_dir):
    from engine import run_backtest

    result = run_backtest(
        data_dir=sample_tick_dir,
        symbol="BTCUSDT",
        start_date="2024-03-01",
        end_date="2024-03-01",
        strategy="martingale",
        initial_capital=10000,
        leverage=10,
        initial_order_size=100,
        martingale_factor=1.5,
        num_levels=5,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
        maker_fee=0.0002,
    )

    assert "trades_df" in result
    assert "cycles_df" in result
    assert "metrics" in result
    assert "equity_series" in result
    assert "margin_series" in result
    assert result["metrics"]["initial_capital"] == 10000


def test_engine_liquidation(sample_tick_dir):
    """With tiny capital and high leverage, should get liquidated."""
    from engine import run_backtest

    result = run_backtest(
        data_dir=sample_tick_dir,
        symbol="BTCUSDT",
        start_date="2024-03-01",
        end_date="2024-03-01",
        strategy="martingale",
        initial_capital=50,  # very small
        leverage=100,
        initial_order_size=100,
        martingale_factor=2.0,
        num_levels=5,
        price_step=50,
        tp_profit_pct=0.5,
        direction="long",
        maker_fee=0.0002,
    )

    assert result["metrics"]["was_liquidated"] == True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/tick-backtester && python -m pytest tests/test_engine.py -v
```

- [ ] **Step 3: Implement engine.py**

```python
# engine.py
"""Backtest engine — orchestrates strategy + margin on tick data."""

from __future__ import annotations

import pandas as pd
import numpy as np
from data_loader import load_ticks
from margin import MarginTracker
from strategies.martingale import MartingaleGrid


_bracket_cache: dict[str, list] = {}

def _fetch_brackets(symbol: str) -> list:
    """Fetch leverage brackets via CCXT. Cached locally."""
    if symbol in _bracket_cache:
        return _bracket_cache[symbol]
    try:
        import ccxt
        exchange = ccxt.binanceusdm()
        exchange.load_markets()
        ccxt_symbol = symbol.replace("USDT", "/USDT:USDT")
        brackets_raw = exchange.fetch_leverage_brackets([ccxt_symbol])
        if ccxt_symbol in brackets_raw:
            brackets = [
                (b["notionalCap"], b["maintenanceMarginRate"])
                for b in brackets_raw[ccxt_symbol]
            ]
            _bracket_cache[symbol] = brackets
            return brackets
    except Exception:
        pass
    from margin import DEFAULT_BRACKETS
    _bracket_cache[symbol] = DEFAULT_BRACKETS
    return DEFAULT_BRACKETS


def run_backtest(
    data_dir: str,
    symbol: str,
    start_date: str,
    end_date: str,
    strategy: str = "martingale",
    initial_capital: float = 10_000,
    leverage: int = 10,
    initial_order_size: float = 100,
    martingale_factor: float = 1.5,
    num_levels: int = 5,
    price_step: float = 50,
    tp_profit_pct: float = 0.5,
    direction: str = "long",
    maker_fee: float = 0.0002,
    spread_aware: bool = False,
    progress_callback=None,  # callable(current, total) for UI progress bar
) -> dict:
    """Run a tick-by-tick backtest. Returns dict with trades_df, cycles_df, metrics, etc."""

    # Load tick data
    ticks = load_ticks(data_dir, symbol, "aggTrades", start_date, end_date)
    if ticks.empty:
        raise ValueError(f"No tick data for {symbol} from {start_date} to {end_date}")

    book = None
    book_idx = 0  # pointer into bookTicker DataFrame
    if spread_aware:
        book = load_ticks(data_dir, symbol, "bookTicker", start_date, end_date)
        if book.empty:
            book = None  # Fall back to aggTrade matching
        else:
            book = book.sort_values("timestamp").reset_index(drop=True)

    # Fetch leverage brackets per symbol via CCXT (cached)
    brackets = _fetch_brackets(symbol)

    # Initialize components
    margin = MarginTracker(initial_capital=initial_capital, leverage=leverage, brackets=brackets)

    grid = MartingaleGrid(
        initial_order_size=initial_order_size,
        martingale_factor=martingale_factor,
        num_levels=num_levels,
        price_step=price_step,
        tp_profit_pct=tp_profit_pct,
        direction=direction,
    )

    # Place initial grid
    first_price = float(ticks.iloc[0]["price"])
    grid.place_grid(current_price=first_price)

    # Simulation state
    trades = []
    cycles = []
    equity_points = []
    margin_points = []
    total_ticks = len(ticks)

    # Performance: use itertuples() instead of iterrows() for ~10-50x speedup
    # on large tick datasets (millions of rows per day)
    prices = ticks["price"].values
    timestamps = ticks["timestamp"].values

    for idx in range(total_ticks):
        price = float(prices[idx])
        ts = int(timestamps[idx])

        # Progress callback
        if progress_callback and idx % 10000 == 0:
            progress_callback(idx, total_ticks)

        # Check liquidation
        if margin.check_liquidation(mark_price=price, timestamp=ts):
            trades.append({
                "timestamp": ts, "side": "LIQUIDATION", "price": price,
                "qty": 0, "notional": 0, "fee": 0,
                "wallet_balance": margin.wallet_balance,
                "margin_ratio": 0,
            })
            break

        # Get current best bid/ask for spread-aware execution
        best_bid, best_ask = price, price  # default: use aggTrade price
        if book is not None:
            # Advance bookTicker pointer to current timestamp
            while book_idx < len(book) - 1 and book.iloc[book_idx]["timestamp"] <= ts:
                book_idx += 1
            if book_idx > 0:
                row = book.iloc[book_idx - 1]
                best_bid, best_ask = float(row["best_bid"]), float(row["best_ask"])

        # Check if any grid orders are triggered
        for level, order in list(grid.pending_orders.items()):
            triggered = False
            if order["side"] == "buy" and best_ask <= order["price"]:
                triggered = True
            elif order["side"] == "sell" and best_bid >= order["price"]:
                triggered = True

            if triggered:
                fill_price = order["price"]
                size_usd = order["size_usd"]
                qty = size_usd / fill_price
                fee = size_usd * maker_fee

                # Check if we have enough margin
                new_notional = margin.position_notional(fill_price) + size_usd
                margin_needed = new_notional / leverage
                if margin_needed > margin.wallet_balance:
                    continue  # Skip — not enough margin

                # Process fill
                margin.add_fill(order["side"], fill_price, qty, fee)
                tp = grid.on_fill(level, fill_price)

                mr = margin.margin_ratio(fill_price)
                trades.append({
                    "timestamp": ts, "side": order["side"].upper(),
                    "price": fill_price, "qty": qty,
                    "notional": size_usd, "fee": fee,
                    "wallet_balance": margin.wallet_balance,
                    "margin_ratio": mr,
                })

        # Check if TP is triggered
        if grid.tp_order:
            tp = grid.tp_order
            tp_triggered = False
            if tp["side"] == "sell" and price >= tp["price"]:
                tp_triggered = True
            elif tp["side"] == "buy" and price <= tp["price"]:
                tp_triggered = True

            if tp_triggered:
                tp_price = tp["price"]
                tp_usd = tp["size_usd"]
                tp_qty = tp_usd / tp_price
                tp_fee = tp_usd * maker_fee

                margin.add_fill(tp["side"], tp_price, tp_qty, tp_fee)
                result = grid.on_tp_fill()

                mr = margin.margin_ratio(tp_price)
                trades.append({
                    "timestamp": ts, "side": f"TP_{tp['side'].upper()}",
                    "price": tp_price, "qty": tp_qty,
                    "notional": tp_usd, "fee": tp_fee,
                    "wallet_balance": margin.wallet_balance,
                    "margin_ratio": mr,
                })

                if result["cycle_complete"]:
                    cycles.append({
                        "cycle": result["cycle_number"],
                        "levels_filled": result["levels_filled"],
                        "avg_entry": result["avg_entry"],
                        "tp_price": result["tp_price"],
                        "profit_usd": result["profit_usd"],
                        "timestamp_end": ts,
                    })

                    # Start new cycle
                    grid.place_grid(current_price=price)

        # Record equity and margin at intervals (every 1000 ticks to save memory)
        if idx % 1000 == 0 or idx == total_ticks - 1:
            equity_points.append({
                "timestamp": ts,
                "equity": margin.margin_balance(price),
            })
            margin_points.append({
                "timestamp": ts,
                "margin_ratio": margin.margin_ratio(price),
                "position_notional": margin.position_notional(price),
            })

    # Build output DataFrames
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=["timestamp", "side", "price", "qty", "notional", "fee", "wallet_balance", "margin_ratio"]
    )
    cycles_df = pd.DataFrame(cycles) if cycles else pd.DataFrame(
        columns=["cycle", "levels_filled", "avg_entry", "tp_price", "profit_usd", "timestamp_end"]
    )
    equity_series = pd.DataFrame(equity_points) if equity_points else pd.DataFrame(columns=["timestamp", "equity"])
    margin_series = pd.DataFrame(margin_points) if margin_points else pd.DataFrame(columns=["timestamp", "margin_ratio", "position_notional"])

    # Compute metrics
    final_price = float(ticks.iloc[-1]["price"]) if not margin.is_liquidated else margin.liquidation_price or 0
    final_equity = margin.margin_balance(final_price) if not margin.is_liquidated else margin.wallet_balance
    total_return = (final_equity - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0

    # Max drawdown
    if len(equity_series) > 1:
        eq = equity_series["equity"].values
        running_max = np.maximum.accumulate(eq)
        drawdowns = (eq - running_max) / running_max * 100
        max_dd = float(np.min(drawdowns))
    else:
        max_dd = 0.0

    winning_cycles = len([c for c in cycles if c["profit_usd"] > 0])
    total_cycles = len(cycles)

    metrics = {
        "initial_capital": initial_capital,
        "final_equity": final_equity,
        "total_return_pct": total_return,
        "realized_pnl": margin.realized_pnl,
        "unrealized_pnl": margin.unrealized_pnl(final_price) if not margin.is_liquidated else 0,
        "total_fees": margin.total_fees,
        "total_trades": len(trades_df),
        "cycles_completed": total_cycles,
        "win_rate": winning_cycles / total_cycles * 100 if total_cycles > 0 else 0,
        "avg_cycle_profit": sum(c["profit_usd"] for c in cycles) / total_cycles if total_cycles > 0 else 0,
        "max_drawdown": max_dd,
        "was_liquidated": margin.is_liquidated,
        "liquidation_price": margin.liquidation_price,
        "liquidation_time": margin.liquidation_time,
        "min_margin_ratio": margin.min_margin_ratio if margin.min_margin_ratio != float("inf") else None,
        "cycles_before_liquidation": total_cycles if margin.is_liquidated else None,
        "total_volume": float(trades_df["notional"].sum()) if not trades_df.empty else 0,
        "leverage": leverage,
        "direction": direction,
        "strategy": strategy,
    }

    return {
        "trades_df": trades_df,
        "cycles_df": cycles_df,
        "equity_series": equity_series,
        "margin_series": margin_series,
        "metrics": metrics,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/tick-backtester && python -m pytest tests/test_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add engine.py tests/test_engine.py && git commit -m "feat: backtest engine orchestrating strategy + margin on tick data"
```

---

## Chunk 4: Streamlit UI + Deployment

### Task 8: Streamlit dashboard

**Files:**
- Create: `~/tick-backtester/app.py`

Reuses Cicada MM design from grid-backtest. Copy the CSS/theme approach from `~/grid-backtest/app.py`.

- [ ] **Step 1: Create app.py with Cicada design, sidebar, and all tabs**

Build the full Streamlit app with:
- Cicada MM CSS (copy theme system from grid-backtest/app.py)
- Sidebar: logo, "For internal use only", strategy selector, direction, symbol, date range, leverage, grid params, martingale params, spread-aware toggle, run button, theme toggle
- Overview tab: KPI cards (Total P&L, Return %, Cycles, Win Rate, Max Drawdown, Avg Cycle Profit, Liquidated warning, Min Margin Ratio, Volume, Fees)
- Price & Fills tab: Plotly candlestick-style tick chart with buy/sell markers, grid levels, TP line
- Margin & Risk tab: margin ratio over time, liquidation line, position notional chart
- Cycles tab: DataTable of all cycles
- Trade Log tab: DataTable of all fills
- Data availability indicator in sidebar
- Progress bar during backtest

Reference `~/grid-backtest/app.py` for the exact CSS patterns, KPI card HTML, chart configurations, and Cicada branding approach. Adapt for tick-backtester specifics (different metrics, different charts).

Additional UI requirements:
- Show warning banner: "Funding rates not included. Actual results may differ for long-held positions."
- When spread-aware is enabled but bookTicker data missing for the date range, show notice: "bookTicker data not available for this period. Using aggTrade price matching."
- Configurable fee rate input in sidebar (default 0.02% maker)
- If liquidation occurred, show prominent red KPI card with liquidation price, time, and cycles_before_liquidation
- Classic Grid / Martingale Grid selector in sidebar — Classic Grid hides martingale-specific params (factor, num_levels)
- Hedge mode selector shows both long and short cycle stats separately

- [ ] **Step 2: Test locally**

```bash
cd ~/tick-backtester && streamlit run app.py --server.port 8504
```

Verify: page loads, sidebar renders, Cicada logo shows, theme toggle works. If no tick data available yet, UI should show a helpful message.

- [ ] **Step 3: Commit**

```bash
git add app.py && git commit -m "feat: Streamlit dashboard with Cicada MM branding and all tabs"
```

---

### Task 9: Deploy script and server setup

**Files:**
- Create: `~/tick-backtester/deploy.sh`

- [ ] **Step 1: Create deploy.sh**

```bash
#!/bin/bash
set -e

echo "=== Tick Backtester — Deploy ==="

REPO_URL="git@github.com:arozenfelds-hash/tick-backtester.git"
REPO_DIR="/opt/tick-backtester"
DATA_DIR="/opt/tick-backtester/data"

# Clone or pull
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    echo "Pulling latest..."
    git pull
else
    echo "Cloning..."
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

# Create data dir
mkdir -p "$DATA_DIR/ticks"

# Install deps
echo "Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || \
pip3 install -r requirements.txt -q

# Collector service
cat > /etc/systemd/system/tick-collector.service <<'UNIT'
[Unit]
Description=Tick Data Collector
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tick-backtester
ExecStart=/usr/bin/python3 collector.py stream --symbols BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

# Streamlit service
cat > /etc/systemd/system/tick-backtester.service <<'UNIT'
[Unit]
Description=Tick Backtester Streamlit App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tick-backtester
ExecStart=/usr/bin/python3 -m streamlit run app.py --server.port 8504 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable tick-collector tick-backtester
systemctl restart tick-collector tick-backtester

echo ""
echo "=== Deployed! ==="
echo "Collector: systemctl {start|stop|restart|status} tick-collector"
echo "App:       http://$(hostname -I | awk '{print $1}'):8504"
echo "Manage:    systemctl {start|stop|restart|status} tick-backtester"
echo "Logs:      journalctl -u tick-collector -f"
echo "           journalctl -u tick-backtester -f"
```

- [ ] **Step 2: Commit and push**

```bash
git add deploy.sh && chmod +x deploy.sh && git commit -m "feat: deploy script with systemd services for collector + app"
git push
```

- [ ] **Step 3: Deploy to server**

```bash
ssh root@154.83.140.69 "cd /opt && git clone git@github.com:arozenfelds-hash/tick-backtester.git 2>/dev/null; cd /opt/tick-backtester && git pull && bash deploy.sh"
```

- [ ] **Step 4: Download initial historical data on server**

```bash
ssh root@154.83.140.69 "cd /opt/tick-backtester && python3 collector.py download --symbol BTCUSDT --start 2026-03-01 --end 2026-03-14"
```

- [ ] **Step 5: Verify app is running**

Open http://154.83.140.69:8504 — should see the Cicada-branded tick backtester.

Verify collector is running:
```bash
ssh root@154.83.140.69 "systemctl status tick-collector"
```

- [ ] **Step 6: Final commit with any fixes**

```bash
git add -A && git commit -m "fix: post-deployment adjustments" && git push
```
