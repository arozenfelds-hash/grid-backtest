"""
backtester.py
=============
Grid / Ping-Pong bot backtester.

Supports two modes:
  - "perps"  : USDT-margined perpetual futures. Can go short. Only USDT balance needed.
  - "spot"   : Spot trading. Cannot go short. Needs initial USDT + token balance.
               Sells require token balance, buys require cash balance.

Canonical grid: all orders snap to  min_price + n × price_step.
Each fill spawns:
  1. A profit order at ±factor_levels distance
  2. A maintenance order ±1 level to keep both sides populated (perps always;
     spot only if balance allows)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def run_grid_backtest(
    df: pd.DataFrame,
    min_price: float,
    price_step: float,
    order_size_usd: float = 50.0,
    profit_pct: float = 1.0,
    start_cap: float = 10_000.0,
    start_date: str | None = None,
    n_init_above: int = 10,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    mode: str = "perps",
    initial_tokens: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Grid bot backtest on OHLCV data.

    Parameters
    ----------
    df              : OHLCV DataFrame (Open, High, Low, Close, Volume)
    min_price       : floor price — no buy orders below this
    price_step      : $ distance between adjacent grid levels
    order_size_usd  : order size in USDT per fill
    profit_pct      : spread % between paired buy/sell (converted to grid levels)
    start_cap       : starting capital in USDT
    start_date      : optional ISO date string to trim data
    n_init_above    : how many initial sell levels above current price
    maker_fee       : maker fee rate (limit orders)
    taker_fee       : taker fee rate (not used — all orders are limits)
    mode            : "perps" or "spot"
    initial_tokens  : starting token balance (spot mode only)

    Returns
    -------
    (df_with_equity, trades_df, metrics_dict)
    """
    df = df.copy()
    is_spot = mode == "spot"

    # ── Filter to start_date ─────────────────────────────────────────────────
    if start_date is not None:
        ts = pd.Timestamp(start_date)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        df = df[df.index >= ts]
    if df.empty:
        raise RuntimeError("No data found after the selected start date.")

    avg_usd = order_size_usd
    fee_rate = maker_fee

    # ── Canonical grid helpers ───────────────────────────────────────────────
    first_close = float(df["Close"].iloc[0])

    def gp(level: int) -> float:
        """Grid price for integer level (level 0 = min_price)."""
        return round(min_price + level * price_step, 8)

    def gl(price: float) -> int:
        """Nearest grid level for a price."""
        return round((price - min_price) / price_step)

    # profit_pct → integer number of grid levels
    factor_levels = max(1, round(profit_pct / 100.0 * first_close / price_step))

    first_level = gl(first_close)

    # ── Simulation state ─────────────────────────────────────────────────────
    cash = float(start_cap)
    tokens = float(initial_tokens) if is_spot else 0.0
    realized_pnl = 0.0
    round_trips = 0
    rt_profits: list[float] = []
    total_fees = 0.0
    total_buy_val = 0.0
    total_buy_qty = 0.0
    total_sell_val = 0.0
    total_sell_qty = 0.0
    skipped_no_balance = 0

    # Initial equity for return calculation
    initial_equity = cash + tokens * first_close

    # pending[price] = {"side", "size_tokens", "usd_value", "origin"}
    pending: dict[float, dict] = {}

    # ── Initial grid placement ───────────────────────────────────────────────
    # Sell orders: from first_level UP for n_init_above levels
    for i in range(n_init_above):
        sp = gp(first_level + i)
        if sp <= 0:
            continue
        size_tok = avg_usd / sp
        # Spot: only place sell if we have tokens (checked at fill time)
        pending[sp] = {
            "side": "sell", "size_tokens": size_tok,
            "usd_value": avg_usd, "origin": None,
        }

    # Buy orders: from (first_level - factor_levels) DOWN to level 0
    buy_start_level = first_level - factor_levels
    for lv in range(buy_start_level, -1, -1):
        bp = gp(lv)
        if bp <= 0:
            break
        pending[bp] = {
            "side": "buy", "size_tokens": avg_usd / bp,
            "usd_value": avg_usd, "origin": None,
        }

    # ── Main simulation loop ─────────────────────────────────────────────────
    trades: list[dict] = []
    equity_curve: list[float] = []
    rows = list(df.itertuples(index=True))

    for row in rows:
        lo = float(row.Low)
        hi = float(row.High)
        cl = float(row.Close)
        idx = row.Index

        # Snapshot triggered orders before any fills this bar
        triggered: list[tuple[float, dict]] = []
        for price, order in pending.items():
            if order["side"] == "buy" and lo <= price:
                triggered.append((price, dict(order)))
            elif order["side"] == "sell" and hi >= price:
                triggered.append((price, dict(order)))

        if triggered:
            # Sells low→high, buys high→low (realistic fill order)
            triggered.sort(key=lambda x: x[0] if x[1]["side"] == "sell" else -x[0])

            for price, order in triggered:
                if price not in pending:
                    continue

                side = order["side"]
                size = order["size_tokens"]
                fill_value = price * size
                fee = fill_value * fee_rate

                # ── Spot balance checks ──────────────────────────────────
                if is_spot:
                    if side == "sell" and tokens < size * 0.999:
                        # Not enough tokens to sell — skip this fill
                        skipped_no_balance += 1
                        del pending[price]
                        continue
                    if side == "buy" and cash < (fill_value + fee) * 0.999:
                        # Not enough cash to buy — skip this fill
                        skipped_no_balance += 1
                        del pending[price]
                        continue

                del pending[price]

                usd_val = order["usd_value"]
                origin = order["origin"]
                rt_profit = 0.0

                total_fees += fee

                lv = gl(price)

                if side == "sell":
                    cash += fill_value - fee
                    tokens -= size
                    total_sell_val += fill_value
                    total_sell_qty += size

                    # Profit BUY: factor_levels below
                    buy_lv = lv - factor_levels
                    buy_price = gp(buy_lv)
                    if buy_price >= min_price and buy_price > 0:
                        pending[buy_price] = {
                            "side": "buy", "size_tokens": avg_usd / buy_price,
                            "usd_value": avg_usd, "origin": price,
                        }

                    # Maintenance SELL: one level higher
                    next_sell = gp(lv + 1)
                    if next_sell > 0 and next_sell not in pending:
                        pending[next_sell] = {
                            "side": "sell", "size_tokens": avg_usd / next_sell,
                            "usd_value": avg_usd, "origin": None,
                        }

                    # Round trip check
                    if origin is not None:
                        rt_profit = (price - origin) * size - 2 * fee
                        realized_pnl += rt_profit
                        round_trips += 1
                        rt_profits.append(rt_profit)

                else:  # buy
                    cash -= fill_value + fee
                    tokens += size
                    total_buy_val += fill_value
                    total_buy_qty += size

                    # Profit SELL: factor_levels above
                    sell_lv = lv + factor_levels
                    sell_price = gp(sell_lv)
                    if sell_price > 0:
                        existing = pending.get(sell_price)
                        if existing is None or existing["origin"] is None:
                            pending[sell_price] = {
                                "side": "sell", "size_tokens": avg_usd / sell_price,
                                "usd_value": avg_usd, "origin": price,
                            }

                    # Maintenance BUY: one level lower
                    prev_buy = gp(lv - 1)
                    if prev_buy > 0 and prev_buy >= min_price and prev_buy not in pending:
                        pending[prev_buy] = {
                            "side": "buy", "size_tokens": avg_usd / prev_buy,
                            "usd_value": avg_usd, "origin": None,
                        }

                    # Round trip check
                    if origin is not None:
                        rt_profit = (origin - price) * size - 2 * fee
                        realized_pnl += rt_profit
                        round_trips += 1
                        rt_profits.append(rt_profit)

                trades.append({
                    "time": idx,
                    "side": "SELL" if side == "sell" else "BUY",
                    "price": price,
                    "size_tokens": size,
                    "usd_value": fill_value,
                    "fee": fee,
                    "rt_profit": rt_profit,
                    "realized_pnl": realized_pnl,
                    "tokens": tokens,
                    "cash": cash,
                })

        equity_curve.append(cash + tokens * cl)

    df["equity"] = equity_curve

    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=["time", "side", "price", "size_tokens", "usd_value",
                 "fee", "rt_profit", "realized_pnl", "tokens", "cash"]
    )

    final_price = float(df["Close"].iloc[-1])
    final_equity = cash + tokens * final_price
    total_return = (final_equity - initial_equity) / initial_equity * 100.0

    avg_buy_price = total_buy_val / total_buy_qty if total_buy_qty > 0 else 0.0
    avg_sell_price = total_sell_val / total_sell_qty if total_sell_qty > 0 else 0.0

    if tokens > 0:
        unrealized_pnl = tokens * (final_price - avg_buy_price)
    elif tokens < 0:
        unrealized_pnl = tokens * (final_price - avg_sell_price)
    else:
        unrealized_pnl = 0.0

    n_pb = sum(1 for o in pending.values() if o["side"] == "buy")
    n_ps = sum(1 for o in pending.values() if o["side"] == "sell")

    # Max drawdown
    eq_arr = np.array(equity_curve)
    running_max = np.maximum.accumulate(eq_arr)
    drawdowns = (eq_arr - running_max) / running_max * 100.0
    max_dd = float(drawdowns.min())

    return df, trades_df, {
        "total_return": total_return,
        "final_equity": final_equity,
        "initial_equity": initial_equity,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_fees": total_fees,
        "round_trips": round_trips,
        "n_trades": len(trades_df),
        "avg_rt_profit": float(np.mean(rt_profits)) if rt_profits else 0.0,
        "min_rt_profit": float(np.min(rt_profits)) if rt_profits else 0.0,
        "max_rt_profit": float(np.max(rt_profits)) if rt_profits else 0.0,
        "rt_profits": rt_profits,
        "tokens": tokens,
        "avg_buy_price": avg_buy_price,
        "avg_sell_price": avg_sell_price,
        "cash": cash,
        "n_pending_buys": n_pb,
        "n_pending_sells": n_ps,
        "start_cap": start_cap,
        "initial_tokens": initial_tokens if is_spot else 0.0,
        "avg_usd": avg_usd,
        "pending_orders": pending,
        "total_buy_val": total_buy_val,
        "total_buy_qty": total_buy_qty,
        "total_sell_val": total_sell_val,
        "total_sell_qty": total_sell_qty,
        "max_drawdown": max_dd,
        "factor_levels": factor_levels,
        "mode": mode,
        "skipped_no_balance": skipped_no_balance,
    }
