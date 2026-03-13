"""
app.py
======
Grid Bot Backtester — Streamlit Dashboard.
Cicada corporate design with light/dark themes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import base64
from pathlib import Path

from backtester import run_grid_backtest
from data_loader import (
    GRID_DEFAULTS,
    POPULAR_TICKERS,
    fetch_ohlcv,
    get_available_tickers,
    get_display_name,
)

# ── Logo ─────────────────────────────────────────────────────────────────────
_LOGO_PATH = Path(__file__).parent / "assets" / "cicada_logo.png"
_LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode() if _LOGO_PATH.exists() else ""

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="cicada. Grid Backtester",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme toggle ─────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
IS_DARK = st.session_state.theme == "dark"

# ── Color system — Cicada MM brand ───────────────────────────────────────────
C_PRIMARY  = "#2D5BFF"  # Cicada accent blue

if IS_DARK:
    C_BG       = "#0A0A0A"
    C_SURFACE  = "#1A1A1A"
    C_BORDER   = "rgba(255,255,255,0.08)"
    C_BORDER2  = "rgba(255,255,255,0.12)"
    C_TEXT     = "#FFFFFF"
    C_MUTED    = "#6B6B6B"
    C_GREEN    = "#00CC88"
    C_RED      = "#EF4444"
    C_CYAN     = C_PRIMARY
    C_PURPLE   = "#7c3aed"
    C_AMBER    = "#f59e0b"
    C_BLUE     = C_PRIMARY
    _PLOT_BG     = "rgba(10,10,10,0.6)"
    _LEGEND_BG   = "rgba(26,26,26,0.95)"
    _GRID_CLR    = "rgba(255,255,255,0.05)"
    _SIDEBAR_BG  = "linear-gradient(180deg, #0A0F1A 0%, #0D1117 50%, #0A0A0A 100%)"
    _INPUT_BG    = "rgba(26,26,26,0.9)"
    _KPI_BG      = "#1A1A1A"
    _KPI_BORDER  = "1px solid rgba(255,255,255,0.06)"
    _HEADER_BG   = "linear-gradient(135deg, #0A0F1A 0%, #111833 40%, #0D1117 100%)"
    _STAT_BG     = "#1A1A1A"
    _GLOW_A      = "radial-gradient(ellipse 80% 50% at 20% 0%, rgba(45,91,255,0.08) 0%, transparent 60%)"
    _GLOW_B      = "radial-gradient(ellipse 60% 40% at 80% 100%, rgba(45,91,255,0.05) 0%, transparent 60%)"
    _HEAD_CLR    = "#FFFFFF"
    _SEC_CLR     = "#FFFFFF"
    _BODY_CLR    = "rgba(255,255,255,0.65)"
    _ROW_BORDER  = "rgba(255,255,255,0.08)"
else:
    C_BG       = "#F5F5F5"
    C_SURFACE  = "#FFFFFF"
    C_BORDER   = "#E5E5E5"
    C_BORDER2  = "#D4D4D4"
    C_TEXT     = "#000000"
    C_MUTED    = "#6B6B6B"
    C_GREEN    = "#059669"
    C_RED      = "#DC2626"
    C_CYAN     = C_PRIMARY
    C_PURPLE   = "#7c3aed"
    C_AMBER    = "#D97706"
    C_BLUE     = C_PRIMARY
    _PLOT_BG     = "rgba(255,255,255,0.6)"
    _LEGEND_BG   = "rgba(255,255,255,0.95)"
    _GRID_CLR    = "rgba(0,0,0,0.06)"
    _SIDEBAR_BG  = "linear-gradient(180deg, #F5F5F5 0%, #FFFFFF 50%, #F5F5F5 100%)"
    _INPUT_BG    = "rgba(255,255,255,0.9)"
    _KPI_BG      = "#FFFFFF"
    _KPI_BORDER  = "1px solid #E5E5E5"
    _HEADER_BG   = "linear-gradient(135deg, #FFFFFF 0%, #F0F4FF 60%, #FFFFFF 100%)"
    _STAT_BG     = "#FFFFFF"
    _GLOW_A      = "radial-gradient(ellipse 80% 50% at 20% 0%, rgba(45,91,255,0.03) 0%, transparent 60%)"
    _GLOW_B      = "none"
    _HEAD_CLR    = "#000000"
    _SEC_CLR     = "#000000"
    _BODY_CLR    = "#6B6B6B"
    _ROW_BORDER  = "#EEEEEE"

# ── Chart theme ──────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=_PLOT_BG,
    font=dict(family="'JetBrains Mono', 'SF Mono', monospace", color=C_MUTED, size=10),
    margin=dict(l=0, r=12, t=28, b=0),
    legend=dict(
        bgcolor=_LEGEND_BG, bordercolor=C_BORDER, borderwidth=1,
        orientation="h", x=0, y=1.02, font=dict(size=9, color=C_MUTED),
    ),
)
GRID_STYLE = dict(showgrid=True, gridcolor=_GRID_CLR, gridwidth=1,
                   zeroline=False)

# ── Global CSS — Cicada MM design system ──────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {{
    --bg: {C_BG}; --surface: {C_SURFACE}; --border: {C_BORDER};
    --text: {C_TEXT}; --muted: {C_MUTED};
    --green: {C_GREEN}; --red: {C_RED}; --cyan: {C_CYAN};
    --purple: {C_PURPLE}; --amber: {C_AMBER}; --blue: {C_BLUE};
    --primary: {C_PRIMARY};
}}

html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], .main .block-container {{
    background-color: var(--bg) !important;
    color: {_BODY_CLR};
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 15px; line-height: 1.6;
}}

[data-testid="stAppViewContainer"]::before {{
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: {_GLOW_A}, {_GLOW_B};
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: {_SIDEBAR_BG} !important;
    border-right: 1px solid {'rgba(45,91,255,0.15)' if IS_DARK else 'rgba(45,91,255,0.12)'} !important;
}}
[data-testid="stSidebar"]::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--primary), #00A3FF);
    z-index: 10;
}}
[data-testid="stSidebar"] [data-testid="stMarkdown"] h1 {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 800 !important; letter-spacing: -0.02em;
    color: var(--text) !important;
    font-size: 1.4rem !important; margin-bottom: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdown"] h3 {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important; letter-spacing: 0.15em;
    text-transform: uppercase; font-size: 0.65rem !important;
    color: var(--muted) !important; margin-bottom: 4px !important;
}}
[data-testid="stSidebar"] hr {{ border-color: var(--border) !important; opacity: 0.5; }}
[data-testid="stSidebar"] label {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.8rem !important; color: var(--muted) !important;
    font-weight: 500;
}}
[data-testid="stSidebar"] .stRadio > div {{
    gap: 0.5rem !important;
}}
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stDateInput input {{
    background: {_INPUT_BG} !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    border-radius: 8px !important;
}}

/* Main content headings */
.main h2, .main h3 {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: -0.015em;
    color: var(--text) !important;
}}

/* Section divider */
hr.noir {{ border: none; border-top: 1px solid var(--border); margin: 28px 0; }}

/* Dataframes */
[data-testid="stDataFrame"] {{
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    overflow: hidden;
}}

/* KPI Cards */
.kpi {{
    background: {_KPI_BG};
    border: {_KPI_BORDER};
    border-radius: 16px;
    padding: 20px 16px 18px;
    text-align: center;
    position: relative;
    overflow: hidden;
    min-height: 96px;
    display: flex; flex-direction: column; justify-content: center;
    {'box-shadow: 0 1px 3px rgba(0,0,0,0.04);' if not IS_DARK else ''}
    transition: transform 300ms cubic-bezier(0.16,1,0.3,1), box-shadow 300ms cubic-bezier(0.16,1,0.3,1);
}}
.kpi:hover {{
    transform: translateY(-2px);
    {'box-shadow: 0 4px 12px rgba(0,0,0,0.08);' if not IS_DARK else 'box-shadow: 0 4px 16px rgba(0,0,0,0.3);'}
}}
.kpi::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent-color, var(--primary));
    opacity: 0.8;
}}
.kpi-val {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.3rem; font-weight: 700;
    line-height: 1.1; letter-spacing: -0.02em;
    color: var(--accent-color, var(--primary));
}}
.kpi-lbl {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.6rem; font-weight: 500;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 6px;
}}

/* Header banner */
.hdr-banner {{
    background: {_HEADER_BG};
    border: 1px solid {'rgba(45,91,255,0.15)' if IS_DARK else 'rgba(45,91,255,0.12)'};
    border-radius: 16px;
    padding: 24px 28px 20px;
    margin-bottom: 12px;
    position: relative;
    overflow: hidden;
    {'box-shadow: 0 2px 16px rgba(45,91,255,0.06);' if IS_DARK else 'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'}
}}
.hdr-banner::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--primary), #00A3FF);
}}
.hdr-title {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 1.8rem; font-weight: 800;
    letter-spacing: -0.02em;
    color: {_HEAD_CLR};
    margin: 0; line-height: 1.1;
}}
.hdr-badge {{
    display: inline-block;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.6rem; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 100px;
    margin-left: 12px;
    position: relative; top: -2px;
}}
.hdr-badge.perps {{
    background: rgba(45,91,255,0.12); color: var(--primary);
    border: 1px solid rgba(45,91,255,0.25);
}}
.hdr-badge.spot {{
    background: rgba(245,158,11,0.12); color: var(--amber);
    border: 1px solid rgba(245,158,11,0.25);
}}
.hdr-meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; color: var(--muted);
    margin-top: 10px; line-height: 1.6;
}}
.hdr-meta span {{ color: var(--text); font-weight: 500; }}

/* Section headers */
.sec-hdr {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 700; font-size: 1.1rem;
    letter-spacing: -0.01em;
    color: {_SEC_CLR};
    display: flex; align-items: center; gap: 10px;
    margin: 0 0 14px 0;
}}
.sec-hdr::after {{
    content: '';
    flex: 1; height: 1px;
    background: linear-gradient(90deg, {'rgba(45,91,255,0.2)' if IS_DARK else 'rgba(45,91,255,0.15)'}, transparent);
}}
.sec-dot {{
    display: inline-block; width: 6px; height: 6px;
    border-radius: 50%; margin-right: 2px;
}}
/* Section badge pill */
.sec-pill {{
    display: inline-block;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 11px; font-weight: 500;
    letter-spacing: 0.1em; text-transform: uppercase;
    padding: 6px 16px; border-radius: 100px;
    border: 1px solid {'rgba(255,255,255,0.2)' if IS_DARK else 'rgba(0,0,0,0.15)'};
    color: {'rgba(255,255,255,0.7)' if IS_DARK else '#333'};
    margin-bottom: 8px;
}}

/* Stat rows */
.stat-panel {{
    background: {_STAT_BG};
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px 18px;
    {'box-shadow: 0 1px 3px rgba(0,0,0,0.04);' if not IS_DARK else ''}
}}
.stat-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid {_ROW_BORDER};
    font-size: 0.8rem;
}}
.stat-row:last-child {{ border-bottom: none; }}
.stat-k {{ font-family: 'Plus Jakarta Sans', sans-serif; color: var(--muted); font-weight: 400; }}
.stat-v {{ font-family: 'JetBrains Mono', monospace; color: var(--text); font-weight: 500; text-align: right; }}

/* Warning bar */
.warn-bar {{
    background: {'rgba(245,158,11,0.08)' if IS_DARK else 'rgba(245,158,11,0.06)'};
    border: 1px solid {'rgba(245,158,11,0.2)' if IS_DARK else 'rgba(245,158,11,0.3)'};
    border-left: 3px solid var(--amber);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.8rem; color: var(--amber);
    margin: 8px 0;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0; background: transparent;
    border-bottom: 1px solid var(--border);
}}
.stTabs [data-baseweb="tab"] {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.72rem !important;
    text-transform: uppercase; letter-spacing: 0.06em;
    font-weight: 500;
    color: var(--muted) !important;
    border-bottom: 2px solid transparent;
    padding: 8px 16px !important;
    transition: all 300ms cubic-bezier(0.16,1,0.3,1);
}}
.stTabs [aria-selected="true"] {{
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
    font-weight: 600;
    background: {'rgba(45,91,255,0.04)' if IS_DARK else 'rgba(45,91,255,0.06)'} !important;
}}

/* Buttons */
.stButton > button[kind="primary"] {{
    background-color: #2D5BFF !important;
    color: #FFFFFF !important;
    border-radius: 100px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 500 !important; font-size: 14px !important;
    padding: 10px 24px !important;
    border: none !important;
    transition: transform 300ms cubic-bezier(0.16,1,0.3,1);
}}
.stButton > button[kind="primary"]:hover {{
    transform: scale(1.02);
}}

/* Footer */
.footer {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.7rem; color: var(--muted);
    text-align: center;
    padding: 24px 0 8px;
    border-top: 1px solid {'rgba(45,91,255,0.15)' if IS_DARK else 'rgba(45,91,255,0.1)'};
    margin-top: 32px;
}}
.conf-notice {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 11px; font-weight: 400;
    letter-spacing: 0.08em;
    color: var(--muted); opacity: 0.7;
    margin-top: 8px;
}}

/* Hide streamlit defaults */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 0 !important; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, color: str = C_CYAN) -> str:
    return (
        f'<div class="kpi" style="--accent-color:{color}">'
        f'<div class="kpi-val">{value}</div>'
        f'<div class="kpi-lbl">{label}</div></div>'
    )

def _pnl_color(v: float) -> str:
    return C_GREEN if v >= 0 else C_RED

def _stat_panel(rows: list[tuple[str, str, str]]) -> str:
    """Build a stat panel. Each row = (key, value, color)."""
    inner = ""
    for k, v, c in rows:
        inner += f'<div class="stat-row"><span class="stat-k">{k}</span><span class="stat-v" style="color:{c}">{v}</span></div>'
    return f'<div class="stat-panel">{inner}</div>'

def _section(title: str, dot_color: str = C_CYAN) -> str:
    return f'<div class="sec-hdr"><span class="sec-dot" style="background:{dot_color}"></span>{title}</div>'


# ── Cached backtest runner ────────────────────────────────────────────────────

@st.cache_data(ttl=1_800, show_spinner="Fetching data & running backtest...")
def run_cached_backtest(
    ticker, timeframe, days, start_cap, start_date_str,
    min_price, price_step, order_size_usd, profit_pct,
    n_init_above, maker_fee, mode="perps", initial_tokens=0.0,
):
    raw = fetch_ohlcv(ticker, timeframe=timeframe, days=days)
    return run_grid_backtest(
        raw, min_price=min_price, price_step=price_step,
        order_size_usd=order_size_usd, profit_pct=profit_pct,
        start_cap=start_cap, start_date=start_date_str,
        n_init_above=n_init_above, maker_fee=maker_fee,
        mode=mode, initial_tokens=initial_tokens,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 8px 0 4px;">
        <img src="data:image/png;base64,{_LOGO_B64}" style="width:160px; margin-bottom:6px;" alt="Cicada">
        <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:0.65rem; font-weight:600;
                    letter-spacing:0.15em; text-transform:uppercase; color:{C_MUTED};">
            Grid Backtester
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Binance USDM Perpetual Futures")

    # Theme toggle
    _theme_label = "Dark" if IS_DARK else "Light"
    if st.toggle(f"{_theme_label} Mode", value=IS_DARK, key="theme_toggle"):
        if st.session_state.theme != "dark":
            st.session_state.theme = "dark"
            st.rerun()
    else:
        if st.session_state.theme != "light":
            st.session_state.theme = "light"
            st.rerun()

    st.markdown("---")

    st.markdown("### Trading Mode")
    p_mode = st.radio("Mode", ["Perps", "Spot"], horizontal=True,
                       help="Perps: futures (can short). Spot: need tokens to sell.")
    p_mode_val = p_mode.lower()
    st.markdown("---")

    st.markdown("### Coin")
    coin_mode = st.radio("Source", ["Popular", "All Perps"], horizontal=True,
                          label_visibility="collapsed")
    if coin_mode == "Popular":
        p_ticker = st.selectbox("Coin", list(POPULAR_TICKERS.keys()),
                                 format_func=lambda k: POPULAR_TICKERS.get(k, k))
    else:
        all_tickers = get_available_tickers()
        p_ticker = st.selectbox("Coin (search)", all_tickers,
                                 format_func=lambda k: f"{k}  {get_display_name(k)}")

    st.markdown("---")
    st.markdown("### Data")
    p_timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d", "15m", "5m"], index=0)
    p_days = st.number_input("History (days)", 30, 1500, 180)
    p_start_date = st.date_input("Start Date",
        value=(pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90)).date())

    st.markdown("---")
    st.markdown("### Grid")
    _def_min, _def_step = GRID_DEFAULTS.get(p_ticker, (100.0, 1.0))
    col1, col2 = st.columns(2)
    p_min_price = col1.number_input("Min Price", 0.0000001, 1_000_000.0, _def_min, format="%g")
    p_step = col2.number_input("Step ($)", 0.0000001, 100_000.0, _def_step, format="%g")
    p_order_size = st.number_input("Order Size (USDT)", 5.0, 1_000_000.0, 50.0, format="%.2f")
    p_profit = st.slider("Profit %", 0.05, 10.0, 1.0, step=0.05, format="%.2f%%")
    p_n_init = st.slider("Init Sell Levels", 1, 50, 10)
    p_maker_fee = st.number_input("Maker Fee %", 0.0, 1.0, 0.02, format="%.3f") / 100.0

    st.markdown("---")
    st.markdown("### Capital")
    p_start_cap = st.number_input("Starting USDT", 100.0, 10_000_000.0, 10_000.0, format="%.2f")
    if p_mode_val == "spot":
        _coin_sym = p_ticker.split("-")[0]
        p_initial_tokens = st.number_input(f"Initial {_coin_sym}",
            0.0, 1_000_000.0, 0.0, format="%g",
            help=f"Starting {_coin_sym} balance. Sells require tokens on spot.")
    else:
        p_initial_tokens = 0.0

    _fl = max(1, round(p_profit / 100.0 * _def_min / p_step))
    st.caption(f"profit ~ {_fl} lvl = ${_fl * p_step:,.4g}/RT")

    st.markdown("---")
    if st.button("Refresh Data", width="stretch", type="primary"):
        st.cache_data.clear()


# ── Run backtest ──────────────────────────────────────────────────────────────

sd_str = p_start_date.isoformat() if p_start_date else None

try:
    grid_df, grid_trades, gm = run_cached_backtest(
        p_ticker, p_timeframe, int(p_days), float(p_start_cap), sd_str,
        float(p_min_price), float(p_step), float(p_order_size),
        float(p_profit), int(p_n_init), float(p_maker_fee),
        mode=p_mode_val, initial_tokens=float(p_initial_tokens),
    )
except Exception as e:
    st.error(f"Backtest failed: {e}")
    st.stop()


# ── Derived metrics ──────────────────────────────────────────────────────────

coin_sym    = p_ticker.split("-")[0]
total_pnl   = gm["realized_pnl"] + gm["unrealized_pnl"]
tokens_now  = gm["tokens"]
final_price = float(grid_df["Close"].iloc[-1])
rt_profits  = gm.get("rt_profits", [])
po          = gm["pending_orders"]

if abs(tokens_now) < 1e-12:
    pos_label, pos_color = "FLAT", C_MUTED
elif tokens_now > 0:
    pos_label, pos_color = f"+{tokens_now:.6f}", C_GREEN
else:
    pos_label, pos_color = f"{tokens_now:.6f}", C_RED


# ── Header Banner ────────────────────────────────────────────────────────────

_badge_cls = "perps" if p_mode_val == "perps" else "spot"
_badge_txt = "PERPETUAL" if p_mode_val == "perps" else "SPOT"

_cap_info = f"<span>${p_start_cap:,.0f}</span> USDT"
if p_mode_val == "spot" and p_initial_tokens > 0:
    _cap_info += f" + <span>{p_initial_tokens:g}</span> {coin_sym}"

st.markdown(f"""
<div class="hdr-banner">
    <div class="hdr-title">
        {get_display_name(p_ticker)}
        <span class="hdr-badge {_badge_cls}">{_badge_txt}</span>
    </div>
    <div class="hdr-meta">
        {_cap_info}
        &nbsp;&middot;&nbsp; min <span>${p_min_price:g}</span>
        &nbsp;&middot;&nbsp; step <span>${p_step:g}</span>
        &nbsp;&middot;&nbsp; order <span>${p_order_size:,.2f}</span>
        &nbsp;&middot;&nbsp; profit <span>{p_profit:.2f}%</span> ({gm['factor_levels']} lvl)
        &nbsp;&middot;&nbsp; tf <span>{p_timeframe}</span>
        &nbsp;&middot;&nbsp; fee <span>{p_maker_fee*100:.3f}%</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── KPI Cards ────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5, c6 = st.columns(6, gap="small")
c1.markdown(_kpi("Total P&L",     f"${total_pnl:+,.2f}",                 _pnl_color(total_pnl)),       unsafe_allow_html=True)
c2.markdown(_kpi("Realized",      f"${gm['realized_pnl']:+,.2f}",        _pnl_color(gm["realized_pnl"])), unsafe_allow_html=True)
c3.markdown(_kpi("Unrealized",    f"${gm['unrealized_pnl']:+,.2f}",      _pnl_color(gm["unrealized_pnl"])), unsafe_allow_html=True)
c4.markdown(_kpi("Round Trips",   str(gm["round_trips"]),                C_PURPLE),                    unsafe_allow_html=True)
c5.markdown(_kpi("Fills",         str(gm["n_trades"]),                   C_CYAN),                      unsafe_allow_html=True)
c6.markdown(_kpi("Position",      pos_label,                             pos_color),                   unsafe_allow_html=True)

st.markdown("")
d1, d2, d3, d4, d5, d6 = st.columns(6, gap="small")
d1.markdown(_kpi("Equity",        f"${gm['final_equity']:,.2f}",         C_CYAN),    unsafe_allow_html=True)
d2.markdown(_kpi("Return",        f"{gm['total_return']:+.2f}%",         _pnl_color(gm["total_return"])), unsafe_allow_html=True)
d3.markdown(_kpi("Max Drawdown",  f"{gm['max_drawdown']:.2f}%",          C_RED),     unsafe_allow_html=True)
d4.markdown(_kpi("Fees Paid",     f"${gm['total_fees']:,.2f}",           C_AMBER),   unsafe_allow_html=True)
d5.markdown(_kpi("Avg RT Profit", f"${gm['avg_rt_profit']:,.4f}",        C_GREEN),   unsafe_allow_html=True)
d6.markdown(_kpi("Cash",          f"${gm['cash']:,.2f}",                 C_MUTED),   unsafe_allow_html=True)

if gm.get("skipped_no_balance", 0) > 0:
    st.markdown(
        f'<div class="warn-bar">{gm["skipped_no_balance"]} orders skipped — '
        f'insufficient {"token" if p_mode_val == "spot" else ""} balance</div>',
        unsafe_allow_html=True,
    )


# ── Working Range ────────────────────────────────────────────────────────

# Buy side: how many levels down from starting price the USDT can cover
_buy_levels = int(p_start_cap // p_order_size) if p_order_size > 0 else 0
_buy_price_low = max(p_min_price, final_price - _buy_levels * p_step)
_buy_range_pct = (final_price - _buy_price_low) / final_price * 100 if final_price > 0 else 0

# Sell side: perps use USDT, spot uses token balance
if p_mode_val == "spot":
    # Each sell level needs order_size_usd / level_price tokens (approximate with current price)
    _sell_levels = int(p_initial_tokens * final_price // p_order_size) if p_order_size > 0 and final_price > 0 else 0
else:
    _sell_levels = _buy_levels  # perps: symmetric, same USDT funds both sides

_sell_price_hi = final_price + _sell_levels * p_step
_sell_range_pct = (_sell_price_hi - final_price) / final_price * 100 if final_price > 0 else 0
_total_range_pct = _buy_range_pct + _sell_range_pct

st.markdown('<hr class="noir">', unsafe_allow_html=True)
st.markdown(f'{_section("Working Range", C_BLUE)}', unsafe_allow_html=True)
r1, r2, r3, r4, r5, r6 = st.columns(6, gap="small")
r1.markdown(_kpi("Buy Levels",   str(_buy_levels),                C_GREEN),  unsafe_allow_html=True)
r2.markdown(_kpi("Buy Floor",    f"${_buy_price_low:,.4g}",       C_GREEN),  unsafe_allow_html=True)
r3.markdown(_kpi("Buy Coverage", f"{_buy_range_pct:.1f}%",        C_GREEN),  unsafe_allow_html=True)
r4.markdown(_kpi("Sell Levels",  str(_sell_levels),                C_RED),    unsafe_allow_html=True)
r5.markdown(_kpi("Sell Ceiling", f"${_sell_price_hi:,.4g}",        C_RED),    unsafe_allow_html=True)
r6.markdown(_kpi("Total Range",  f"{_total_range_pct:.1f}%",      C_BLUE),   unsafe_allow_html=True)

if p_mode_val == "spot":
    st.markdown(
        f'<div class="stat-panel" style="margin-top:6px;font-size:0.75rem">'
        f'<div class="stat-row"><span class="stat-k">USDT funds buy side</span>'
        f'<span class="stat-v" style="color:{C_GREEN}">${p_start_cap:,.2f} → {_buy_levels} levels</span></div>'
        f'<div class="stat-row"><span class="stat-k">{coin_sym} funds sell side</span>'
        f'<span class="stat-v" style="color:{C_RED}">{p_initial_tokens:g} {coin_sym} → {_sell_levels} levels</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Price Chart ──────────────────────────────────────────────────────────────

st.markdown('<hr class="noir">', unsafe_allow_html=True)
st.markdown(f'{_section("Price · Fills · Grid", C_CYAN)}', unsafe_allow_html=True)

# Full backtest range — no tail slicing
chart_df = grid_df

# All trades across the full range
trades_window = grid_trades if not grid_trades.empty else grid_trades
buys_w  = trades_window[trades_window["side"] == "BUY"]  if not trades_window.empty else trades_window
sells_w = trades_window[trades_window["side"] == "SELL"] if not trades_window.empty else trades_window

# Compute y-axis range from actual price data (with padding), NOT from pending orders
_price_lo = float(chart_df["Low"].min())
_price_hi = float(chart_df["High"].max())
# Include fill prices in range
if not buys_w.empty:
    _price_lo = min(_price_lo, float(buys_w["price"].min()))
if not sells_w.empty:
    _price_hi = max(_price_hi, float(sells_w["price"].max()))
_price_pad = (_price_hi - _price_lo) * 0.06
_y_min = _price_lo - _price_pad
_y_max = _price_hi + _price_pad

fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
    row_heights=[0.55, 0.22, 0.23], vertical_spacing=0.04,
    subplot_titles=("", "", ""))

# Price line — use OHLC candlestick for richer view on full range
fig.add_trace(go.Candlestick(
    x=chart_df.index,
    open=chart_df["Open"], high=chart_df["High"],
    low=chart_df["Low"], close=chart_df["Close"],
    name="Price",
    increasing=dict(line=dict(color=C_PRIMARY, width=1), fillcolor="rgba(45,91,255,0.15)"),
    decreasing=dict(line=dict(color="#555" if IS_DARK else "#94a3b8", width=1), fillcolor="rgba(85,85,85,0.1)" if IS_DARK else "rgba(148,163,184,0.1)"),
), row=1, col=1)

# Fill markers
if not buys_w.empty:
    fig.add_trace(go.Scatter(
        x=buys_w["time"], y=buys_w["price"],
        mode="markers", name="Buy",
        marker=dict(symbol="triangle-up", color=C_GREEN, size=7,
                    line=dict(width=1, color=f"rgba(0,204,136,0.4)")),
    ), row=1, col=1)
if not sells_w.empty:
    fig.add_trace(go.Scatter(
        x=sells_w["time"], y=sells_w["price"],
        mode="markers", name="Sell",
        marker=dict(symbol="triangle-down", color=C_RED, size=7,
                    line=dict(width=1, color="rgba(255,59,92,0.4)")),
    ), row=1, col=1)

# Pending order lines — only show those within the visible y-range
if po:
    buy_prices  = sorted([p for p, o in po.items()
                          if o["side"] == "buy" and p >= _y_min], reverse=True)[:10]
    sell_prices = sorted([p for p, o in po.items()
                          if o["side"] == "sell" and p <= _y_max])[:10]
    for i, px in enumerate(buy_prices):
        fig.add_hline(y=px, line=dict(color="rgba(0,230,138,0.2)", width=0.5, dash="dot"),
            annotation_text=f"B {px:,.2f}" if i < 5 else None,
            annotation_font=dict(size=7, color="rgba(0,230,138,0.5)"),
            annotation_position="right", row=1, col=1)
    for i, px in enumerate(sell_prices):
        fig.add_hline(y=px, line=dict(color="rgba(255,59,92,0.2)", width=0.5, dash="dot"),
            annotation_text=f"S {px:,.2f}" if i < 5 else None,
            annotation_font=dict(size=7, color="rgba(255,59,92,0.5)"),
            annotation_position="right", row=1, col=1)

# Net tokens
if not grid_trades.empty:
    fig.add_trace(go.Scatter(
        x=trades_window["time"], y=trades_window["tokens"],
        mode="lines", name="Tokens", line=dict(color=C_AMBER, width=1.2),
        fill="tozeroy", fillcolor="rgba(245,158,11,0.05)",
    ), row=2, col=1)

# Equity
fig.add_trace(go.Scatter(
    x=chart_df.index, y=chart_df["equity"],
    name="Equity", line=dict(color=C_PURPLE, width=1.5),
    fill="tozeroy", fillcolor="rgba(168,85,247,0.05)",
), row=3, col=1)

fig.update_layout(**CHART_LAYOUT, height=750, xaxis_rangeslider_visible=False)
# Lock price y-axis to actual price range — prevents pending hlines from stretching it
fig.update_yaxes(**GRID_STYLE, title_font=dict(size=9), range=[_y_min, _y_max], row=1, col=1)
fig.update_yaxes(**GRID_STYLE, title_font=dict(size=9), row=2, col=1)
fig.update_yaxes(**GRID_STYLE, title_font=dict(size=9), row=3, col=1)
for i in range(1, 4):
    fig.update_xaxes(**GRID_STYLE, row=i, col=1)
st.plotly_chart(fig, width="stretch")


# ── Statistics (tabbed) ──────────────────────────────────────────────────────

st.markdown('<hr class="noir">', unsafe_allow_html=True)
st.markdown(f'{_section("Analytics", C_PURPLE)}', unsafe_allow_html=True)

tab_pos, tab_rt, tab_orders = st.tabs(["Position & Fills", "Round Trips", "Pending Orders"])

with tab_pos:
    col_a, col_b = st.columns(2, gap="medium")

    with col_a:
        _n_buys  = int((grid_trades["side"] == "BUY").sum())  if not grid_trades.empty else 0
        _n_sells = int((grid_trades["side"] == "SELL").sum()) if not grid_trades.empty else 0
        _buy_usd  = float(grid_trades.loc[grid_trades["side"]=="BUY",  "usd_value"].sum()) if _n_buys  > 0 else 0.0
        _sell_usd = float(grid_trades.loc[grid_trades["side"]=="SELL", "usd_value"].sum()) if _n_sells > 0 else 0.0
        _buy_tok  = float(grid_trades.loc[grid_trades["side"]=="BUY",  "size_tokens"].sum()) if _n_buys  > 0 else 0.0
        _sell_tok = float(grid_trades.loc[grid_trades["side"]=="SELL", "size_tokens"].sum()) if _n_sells > 0 else 0.0
        _buy_fees = float(grid_trades.loc[grid_trades["side"]=="BUY",  "fee"].sum()) if _n_buys  > 0 else 0.0
        _sell_fees= float(grid_trades.loc[grid_trades["side"]=="SELL", "fee"].sum()) if _n_sells > 0 else 0.0

        st.markdown(_stat_panel([
            ("BUY Fills",    str(_n_buys),              C_GREEN),
            ("BUY Volume",   f"${_buy_usd:,.2f}",       C_TEXT),
            ("BUY Tokens",   f"{_buy_tok:.6f}",          C_TEXT),
            ("BUY Fees",     f"${_buy_fees:,.2f}",       C_AMBER),
            ("", "", C_BORDER),
            ("SELL Fills",   str(_n_sells),              C_RED),
            ("SELL Volume",  f"${_sell_usd:,.2f}",       C_TEXT),
            ("SELL Tokens",  f"{_sell_tok:.6f}",         C_TEXT),
            ("SELL Fees",    f"${_sell_fees:,.2f}",      C_AMBER),
        ]), unsafe_allow_html=True)

    with col_b:
        _pos_rows = []
        if p_mode_val == "spot":
            _pos_rows.append(("Initial Tokens", f"{gm.get('initial_tokens',0.0):g} {coin_sym}", C_MUTED))
        _pos_rows.extend([
            ("Net Tokens",     f"{tokens_now:+.6f} {coin_sym}", pos_color),
            ("Avg Buy Price",  f"${gm['avg_buy_price']:,.2f}" if gm["avg_buy_price"] > 0 else "\u2014", C_GREEN),
            ("Avg Sell Price", f"${gm['avg_sell_price']:,.2f}" if gm["avg_sell_price"] > 0 else "\u2014", C_RED),
            ("Current Price",  f"${final_price:,.2f}", C_CYAN),
            ("Unrealized P&L", f"${gm['unrealized_pnl']:+,.2f}", _pnl_color(gm["unrealized_pnl"])),
            ("Cash Balance",   f"${gm['cash']:,.2f}", C_TEXT),
        ])
        if p_mode_val == "spot":
            _pos_rows.append(("Skipped Orders", str(gm.get("skipped_no_balance", 0)), C_AMBER))
        _pos_rows.append(("Pending Buys / Sells", f"{gm['n_pending_buys']} / {gm['n_pending_sells']}", C_MUTED))
        st.markdown(_stat_panel(_pos_rows), unsafe_allow_html=True)


with tab_rt:
    col_c, col_d = st.columns([1, 2], gap="medium")

    with col_c:
        if rt_profits:
            rt_arr = np.array(rt_profits)
            st.markdown(_stat_panel([
                ("Count",  str(len(rt_arr)),                C_PURPLE),
                ("Total",  f"${rt_arr.sum():,.4f}",         _pnl_color(rt_arr.sum())),
                ("Min",    f"${rt_arr.min():,.4f}",         C_RED),
                ("Avg",    f"${rt_arr.mean():,.4f}",        C_TEXT),
                ("Median", f"${float(np.median(rt_arr)):,.4f}", C_TEXT),
                ("Max",    f"${rt_arr.max():,.4f}",         C_GREEN),
                ("Std",    f"${rt_arr.std():,.4f}",         C_MUTED),
            ]), unsafe_allow_html=True)
        else:
            st.info("No round trips completed yet.")

    with col_d:
        if rt_profits:
            fig_rt = make_subplots(rows=2, cols=1, shared_xaxes=False,
                row_heights=[0.55, 0.45], vertical_spacing=0.12,
                subplot_titles=("Cumulative RT Profit", "Profit Distribution"))

            fig_rt.add_trace(go.Scatter(
                x=list(range(1, len(rt_profits) + 1)),
                y=list(np.cumsum(rt_profits)),
                mode="lines", name="Cum Profit",
                line=dict(color=C_GREEN, width=1.5),
                fill="tozeroy", fillcolor="rgba(0,204,136,0.05)",
            ), row=1, col=1)

            fig_rt.add_trace(go.Histogram(
                x=rt_profits, nbinsx=40, name="Distribution",
                marker_color=C_PURPLE, opacity=0.85,
            ), row=2, col=1)

            fig_rt.update_layout(**CHART_LAYOUT, height=420, showlegend=False)
            fig_rt.update_yaxes(**GRID_STYLE, row=1, col=1)
            fig_rt.update_yaxes(**GRID_STYLE, row=2, col=1)
            fig_rt.update_xaxes(**GRID_STYLE, row=1, col=1)
            fig_rt.update_xaxes(**GRID_STYLE, row=2, col=1)
            st.plotly_chart(fig_rt, width="stretch")


with tab_orders:
    if po:
        col_ob, col_os = st.columns(2, gap="medium")
        buy_orders = sorted(
            [(px, o) for px, o in po.items() if o["side"] == "buy"],
            key=lambda x: x[0], reverse=True)[:30]
        sell_orders = sorted(
            [(px, o) for px, o in po.items() if o["side"] == "sell"],
            key=lambda x: x[0])[:30]

        with col_ob:
            st.markdown(f'<div style="font-size:0.75rem;color:{C_GREEN};font-weight:500;'
                        f'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">'
                        f'Buy Orders ({len(buy_orders)})</div>', unsafe_allow_html=True)
            if buy_orders:
                bo_rows = [{"Price": f"${px:,.4f}", "Size": f"${o['usd_value']:,.2f}",
                            "Origin": f"${o['origin']:,.4f}" if o["origin"] else "Grid"}
                           for px, o in buy_orders]
                st.dataframe(pd.DataFrame(bo_rows), width="stretch", hide_index=True,
                             height=min(36 * len(bo_rows) + 40, 400))

        with col_os:
            st.markdown(f'<div style="font-size:0.75rem;color:{C_RED};font-weight:500;'
                        f'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">'
                        f'Sell Orders ({len(sell_orders)})</div>', unsafe_allow_html=True)
            if sell_orders:
                so_rows = [{"Price": f"${px:,.4f}", "Size": f"${o['usd_value']:,.2f}",
                            "Origin": f"${o['origin']:,.4f}" if o["origin"] else "Grid"}
                           for px, o in sell_orders]
                st.dataframe(pd.DataFrame(so_rows), width="stretch", hide_index=True,
                             height=min(36 * len(so_rows) + 40, 400))
    else:
        st.info("No pending orders.")


# ── Equity & Drawdown ────────────────────────────────────────────────────────

st.markdown('<hr class="noir">', unsafe_allow_html=True)
st.markdown(f'{_section("Equity & Drawdown", C_PURPLE)}', unsafe_allow_html=True)

eq_arr = np.array(grid_df["equity"].values)
running_max = np.maximum.accumulate(eq_arr)
dd_pct = (eq_arr - running_max) / running_max * 100.0

fig_dd = make_subplots(rows=2, cols=1, shared_xaxes=True,
    row_heights=[0.6, 0.4], vertical_spacing=0.06, subplot_titles=("", ""))

fig_dd.add_trace(go.Scatter(
    x=grid_df.index, y=grid_df["equity"],
    name="Equity", line=dict(color=C_PURPLE, width=1.8),
    fill="tozeroy", fillcolor="rgba(168,85,247,0.04)",
), row=1, col=1)

fig_dd.add_trace(go.Scatter(
    x=grid_df.index, y=dd_pct,
    name="Drawdown", line=dict(color=C_RED, width=1),
    fill="tozeroy", fillcolor="rgba(255,59,92,0.08)",
), row=2, col=1)

fig_dd.update_layout(**CHART_LAYOUT, height=380)
for i in range(1, 3):
    fig_dd.update_yaxes(**GRID_STYLE, row=i, col=1)
    fig_dd.update_xaxes(**GRID_STYLE, row=i, col=1)
st.plotly_chart(fig_dd, width="stretch")


# ── Trade Log ────────────────────────────────────────────────────────────────

st.markdown('<hr class="noir">', unsafe_allow_html=True)
st.markdown(f'{_section("Trade Log", C_AMBER)}', unsafe_allow_html=True)

if not grid_trades.empty:
    disp = grid_trades.tail(500).copy()
    disp["time"]         = pd.to_datetime(disp["time"]).dt.strftime("%Y-%m-%d %H:%M")
    disp["price"]        = disp["price"].map("${:,.4f}".format)
    disp["size_tokens"]  = disp["size_tokens"].map("{:.6f}".format)
    disp["usd_value"]    = disp["usd_value"].map("${:,.2f}".format)
    disp["fee"]          = disp["fee"].map("${:,.4f}".format)
    disp["rt_profit"]    = disp["rt_profit"].map(lambda v: f"${v:+,.4f}" if v != 0 else "\u2014")
    disp["realized_pnl"] = disp["realized_pnl"].map("${:+,.4f}".format)
    disp["tokens"]       = disp["tokens"].map("{:+.6f}".format)
    disp["cash"]         = disp["cash"].map("${:,.2f}".format)
    st.dataframe(
        disp.rename(columns={
            "time": "Time", "side": "Side", "price": "Price",
            "size_tokens": "Tokens", "usd_value": "USD", "fee": "Fee",
            "rt_profit": "RT Profit", "realized_pnl": "Cum P&L",
            "tokens": "Net Pos", "cash": "Cash",
        }),
        width="stretch", hide_index=True,
        height=min(36 * (len(disp) + 1) + 10, 560),
    )
    if len(grid_trades) > 500:
        st.caption(f"Showing last 500 of {len(grid_trades):,} total fills.")
else:
    st.info("No fills executed \u2014 adjust grid parameters or start date.")


# ── Footer ───────────────────────────────────────────────────────────────────

st.markdown(
    f'<div class="footer">'
    f'<img src="data:image/png;base64,{_LOGO_B64}" style="width:80px; opacity:0.5; margin-bottom:6px;" alt="Cicada"><br>'
    f'<div>GRID BACKTESTER &middot; '
    f'Binance USDM Futures via CCXT &middot; Not financial advice</div>'
    f'<div class="conf-notice">Confidential. For internal demonstration purposes.</div>'
    f'</div>',
    unsafe_allow_html=True,
)
