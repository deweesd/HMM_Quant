"""
////// app/dashboard.py \\\\\\
──────────────────────────────────────────────────────────────────────────────
Regime-Based Trading Dashboard — Streamlit App

Run with:
    streamlit run app/dashboard.py

Tabs
────
  📊 Dashboard   — Live ticker cards, current signal, candlestick with
                   regime background, backtest metrics
  📋 Backtest    — Equity curve vs Buy & Hold, trade log table
  📖 README      — Model guide, indicator reference, disclaimers
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import numpy  as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

from strategy.signals  import get_ticker_data, CONFIRM_COLS, CONFIRM_LABELS
from pipeline.download import TICKERS, TICKER_LABELS
from models.hmm        import N_STATES
from strategy.backtest import run_backtest
from strategy.exits   import build_exit_thresholds, RECOMMENDED_LADDER
from strategy.explain import get_scenario, get_historical_replay
from app.css import DASHBOARD_CSS, LIGHT_MODE_CSS

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title = "Regime Trading App",
    page_icon  = "📈",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

# ── Theme state ────────────────────────────────────────────────────────────────
if "light_mode" not in st.session_state:
    st.session_state.light_mode = False
if st.session_state.light_mode:
    st.markdown(LIGHT_MODE_CSS, unsafe_allow_html=True)

_topbar_logo, _topbar_btn = st.columns([14, 1])
with _topbar_logo:
    st.markdown("""
<div style="display:flex; align-items:center; padding:10px 0 14px;
            border-bottom:1px solid var(--border); margin-bottom:8px;">
  <div style="font-size:18px; font-weight:700; letter-spacing:-0.3px; color:var(--t1);">
    HMM <span style="color:var(--accent-lt);">Quant</span>
  </div>
</div>
""", unsafe_allow_html=True)
with _topbar_btn:
    _btn_icon = "☀️" if st.session_state.light_mode else "🌙"
    if st.button(_btn_icon, key="theme_btn", help="Toggle dark / light mode"):
        st.session_state.light_mode = not st.session_state.light_mode
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ Settings")

    selected_ticker = st.selectbox(
        "Focus Ticker",
        options = TICKERS,
        format_func = lambda t: TICKER_LABELS[t],
        index = 0,
    )

    period = st.selectbox(
        "Data Window",
        options = ["365d", "730d"],
        index   = 1,
        help    = "Max reliable hourly history via yfinance is ~730 days.",
    )

    n_states = st.slider(
        "HMM States",
        min_value = 4,
        max_value = 8,
        value     = N_STATES,
        help      = "Number of hidden market regimes to detect.",
    )

    chart_bars = st.slider(
        "Chart — bars to show",
        min_value = 168,
        max_value = 2000,
        value     = 500,
        step      = 100,
        help      = "Number of hourly bars displayed in the candlestick chart.",
    )

    st.subheader("Exit Strategy")

    position_mode = st.radio(
        "Position Mode",
        options=["recommended", "user_defined"],
        format_func=lambda x: "Recommended" if x == "recommended" else "User Defined",
        help="Recommended uses the built-in 5-tier profit-taking ladder.",
    )

    position_usd = st.number_input(
        "Position Size (USD)",
        min_value=100,
        value=1000,
        step=100,
        help="Hypothetical capital to allocate to one trade.",
    )

    user_exit_ladder = None
    if position_mode == "user_defined":
        with st.expander("Custom Exit Ladder", expanded=True):
            st.caption("Define 5 tiers. Last tier is always 'remainder' (50% of remaining).")
            default_gains = [15, 30, 45, 60, 100]
            default_fracs = [10, 15, 20, 30, 50]
            rows = []
            for k in range(5):
                c1, c2 = st.columns(2)
                gp = c1.number_input(
                    f"Tier {k+1} Gain %", min_value=1, max_value=1000,
                    value=default_gains[k], key=f"gp_{k}",
                )
                sf = c2.number_input(
                    f"Sell %", min_value=1, max_value=99,
                    value=default_fracs[k], key=f"sf_{k}",
                )
                rows.append({"gain_pct": gp, "sell_fraction": sf / 100.0})
            user_exit_ladder = rows

    st.caption("Data via yfinance · Model via hmmlearn")
    st.caption("For educational purposes only.")


# ══════════════════════════════════════════════════════════════════════════════
# CACHED DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_ticker(ticker: str, period: str, n_states: int) -> dict:
    """Load full pipeline for one ticker (cached 1 hour)."""
    return get_ticker_data(ticker=ticker, period=period, n_states=n_states)


@st.cache_data(ttl=3600, show_spinner=False)
def load_backtest(ticker: str, period: str, n_states: int,
                  position_mode: str = "recommended") -> tuple:
    """Run backtest for one ticker (cached 1 hour). position_mode defaults to 'recommended'."""
    result = load_ticker(ticker, period, n_states)
    return run_backtest(result["df"], position_mode=position_mode)


@st.cache_data(ttl=3600, show_spinner=False)
def load_scenario(ticker: str, period: str, n_states: int,
                  position_usd: float) -> dict:
    """Compute scenario for current signal bar (cached 1 hour)."""
    result = load_ticker(ticker, period, n_states)
    return get_scenario(
        result["df"], ticker, position_usd, RECOMMENDED_LADDER
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_replay(ticker: str, period: str, n_states: int) -> list:
    """Compute historical replay (cached 1 hour)."""
    result = load_ticker(ticker, period, n_states)
    return get_historical_replay(result["df"], n=5)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_circ_supply(ticker: str) -> str:
    """
    Fetch Market Cap (Price × Circulating Supply) from yfinance.
    Uses .info['marketCap'] which is reliably populated for crypto tickers.
    Falls back to fast_info.market_cap, then price × shares_outstanding.
    """
    try:
        info = yf.Ticker(ticker).info

        # Primary: marketCap field from full info dict
        mcap = info.get("marketCap") or info.get("market_cap")

        # Fallback: compute from current price × circulating supply
        if not mcap:
            price  = info.get("regularMarketPrice") or info.get("currentPrice")
            supply = info.get("circulatingSupply")
            if price and supply:
                mcap = price * supply

        if not mcap or mcap == 0:
            return "N/A"

        if mcap >= 1e12:
            return f"${mcap/1e12:.2f}T"
        elif mcap >= 1e9:
            return f"${mcap/1e9:.2f}B"
        elif mcap >= 1e6:
            return f"${mcap/1e6:.2f}M"
        else:
            return f"${mcap:,.0f}"
    except Exception:
        return "N/A"



# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Regime colour spans for candlestick background
# ══════════════════════════════════════════════════════════════════════════════

REGIME_FILL = {
    "Bull":    "rgba(0,201,106,0.10)",
    "Bear":    "rgba(224,53,53,0.13)",
    "Neutral": "rgba(150,150,150,0.06)",
}

def get_regime_spans(df: pd.DataFrame) -> list:
    """
    Consolidate consecutive same-regime bars into (start, end, regime) tuples.
    With 17k bars this produces ~500-2000 spans rather than 17k shapes,
    which keeps the plotly chart responsive.
    """
    if df.empty:
        return []
    spans  = []
    regime = df["Regime"].iloc[0]
    start  = df.index[0]
    for ts, r in zip(df.index[1:], df["Regime"].iloc[1:]):
        if r != regime:
            spans.append({"start": start, "end": ts, "regime": regime})
            regime = r
            start  = ts
    spans.append({"start": start, "end": df.index[-1], "regime": regime})
    return spans


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Main candlestick chart
# ══════════════════════════════════════════════════════════════════════════════

def build_candlestick(df_plot: pd.DataFrame, ticker: str) -> go.Figure:
    """
    2-row plotly chart:
      Row 1 (75%): Candlestick + EMA20 + EMA200 + regime background
      Row 2 (25%): Volume bars coloured by up/down candle

    NOTE: We use fig.add_shape(row=1) for regime bands rather than
    fig.add_vrect() because vrect ignores the row= parameter and
    bleeds onto the volume subplot.
    """
    spans = get_regime_spans(df_plot)

    fig = make_subplots(
        rows              = 2,
        cols              = 1,
        shared_xaxes      = True,
        row_heights       = [0.75, 0.25],
        vertical_spacing  = 0.02,
        subplot_titles    = ("", ""),
    )

    # ── Regime background (row 1 only) ────────────────────────────────────────
    for span in spans:
        fig.add_shape(
            type      = "rect",
            xref      = "x",
            yref      = "y domain",    # fraction of row-1 height
            x0        = span["start"],
            x1        = span["end"],
            y0        = 0,
            y1        = 1,
            fillcolor = REGIME_FILL.get(span["regime"], REGIME_FILL["Neutral"]),
            line_width = 0,
            layer     = "below",
            row = 1, col = 1,
        )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x      = df_plot.index,
        open   = df_plot["Open"],
        high   = df_plot["High"],
        low    = df_plot["Low"],
        close  = df_plot["Close"],
        name   = "Price",
        increasing_line_color  = "#26a69a",
        decreasing_line_color  = "#ef5350",
        whiskerwidth = 0.3,
    ), row=1, col=1)

    # ── EMA20 & EMA200 ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x    = df_plot.index,
        y    = df_plot["EMA20"],
        mode = "lines",
        name = "EMA 20",
        line = dict(color="#f5a623", width=1.2, dash="dot"),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x    = df_plot.index,
        y    = df_plot["EMA200"],
        mode = "lines",
        name = "EMA 200",
        line = dict(color="#7b68ee", width=1.5),
    ), row=1, col=1)

    # ── Volume bars ───────────────────────────────────────────────────────────
    vol_colors = [
        "#26a69a" if c >= o else "#ef5350"
        for o, c in zip(df_plot["Open"], df_plot["Close"])
    ]
    fig.add_trace(go.Bar(
        x          = df_plot.index,
        y          = df_plot["Volume"],
        name       = "Volume",
        marker_color = vol_colors,
        opacity    = 0.7,
        showlegend = False,
    ), row=2, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    label = TICKER_LABELS.get(ticker, ticker)
    fig.update_layout(
        title            = dict(
            text     = f"{label}/USD — Hourly Candlestick with Regime Overlay",
            font     = dict(size=14, color="#e0e0e0"),
            x        = 0.01,
        ),
        xaxis_rangeslider_visible = False,
        height      = 560,
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
        font          = dict(color="#e0e0e0"),
        legend        = dict(
            orientation = "h",
            yanchor     = "bottom",
            y           = 1.02,
            xanchor     = "left",
            x           = 0,
            font        = dict(size=10),
        ),
        margin = dict(l=10, r=10, t=50, b=10),
    )
    fig.update_xaxes(
        showgrid    = True,
        gridcolor   = "#222",
        gridwidth   = 0.5,
        showspikes  = True,
        spikecolor  = "#555",
        spikethickness = 1,
    )
    fig.update_yaxes(
        showgrid  = True,
        gridcolor = "#222",
        gridwidth = 0.5,
        row=1, col=1,
    )
    fig.update_yaxes(
        showgrid  = False,
        row=2, col=1,
    )

    # ── Regime legend annotation ──────────────────────────────────────────────
    for regime, color in [("Bull", "#00c96a"), ("Bear", "#e03535"), ("Neutral", "#888")]:
        fig.add_annotation(
            text      = f"■ {regime}",
            xref      = "paper",
            yref      = "paper",
            x         = {"Bull": 0.70, "Bear": 0.80, "Neutral": 0.90}[regime],
            y         = 1.04,
            showarrow = False,
            font      = dict(color=color, size=11),
        )

    return fig


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Equity curve chart
# ══════════════════════════════════════════════════════════════════════════════

def build_equity_chart(equity: pd.Series, bh: pd.Series, ticker: str) -> go.Figure:
    label = TICKER_LABELS.get(ticker, ticker)
    fig   = go.Figure()

    fig.add_trace(go.Scatter(
        x    = equity.index,
        y    = equity.values,
        mode = "lines",
        name = "Strategy",
        line = dict(color="#00c96a", width=2),
        fill = "tozeroy",
        fillcolor = "rgba(0,201,106,0.06)",
    ))
    fig.add_trace(go.Scatter(
        x    = bh.index,
        y    = bh.values,
        mode = "lines",
        name = f"Buy & Hold {label}",
        line = dict(color="#7b68ee", width=1.5, dash="dash"),
    ))
    fig.update_layout(
        title        = "Portfolio Equity vs Buy & Hold",
        height       = 380,
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
        font          = dict(color="#e0e0e0"),
        yaxis_title   = "Portfolio Value ($)",
        xaxis_title   = "Date",
        legend        = dict(x=0.01, y=0.99),
        margin        = dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#222")
    fig.update_yaxes(showgrid=True, gridcolor="#222")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Regime summary table styling
# ══════════════════════════════════════════════════════════════════════════════

def style_summary(df: pd.DataFrame):
    def row_color(row):
        base = "background-color:#141420; color:#e0e0e0;"
        if row["Label"] == "Bull":
            return [base + "color:#00c96a;"] + [base] * (len(row) - 1)
        if row["Label"] == "Bear":
            return [base + "color:#e03535;"] + [base] * (len(row) - 1)
        return [base] * len(row)

    return (
        df.style
        .apply(row_color, axis=1)
        .format({
            "Mean_Return": "{:.5f}",
            "Volatility":  "{:.5f}",
            "Avg_Range":   "{:.5f}",
        })
        .set_properties(**{"font-size": "12px"})
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Hero Signal Banner
# ══════════════════════════════════════════════════════════════════════════════

def render_hero_banner(df: pd.DataFrame, ticker: str, latest) -> None:
    """Render the hero signal banner for the selected ticker."""
    signal  = str(latest["Signal"])
    regime  = str(latest["Regime"])
    n_conf  = int(latest["Confirmations"])
    price   = float(df["Close"].iloc[-1])
    pct_24h = float((price / df["Close"].iloc[-25] - 1) * 100) if len(df) > 25 else 0.0
    label   = TICKER_LABELS.get(ticker, ticker)
    ts      = df.index[-1].strftime("%Y-%m-%d %H:%M UTC")
    hmm_st  = int(latest["HMM_State"])

    pill_cls   = {"LONG": "long", "SHORT": "short"}.get(signal, "neutral")
    regime_cls = {"Bull": "bull", "Bear": "bear"}.get(regime, "neut")
    regime_icon= {"Bull": "🟢", "Bear": "🔴"}.get(regime, "⚪")
    delta_cls  = "pos" if pct_24h >= 0 else "neg"
    delta_sign = "▲" if pct_24h >= 0 else "▼"

    pips_html = "".join(
        f'<div class="hmm-pip{"  filled" if i < n_conf else ""}"></div>'
        for i in range(10)
    )

    st.markdown(f"""
<div class="hmm-hero">
  <div>
    <div class="hmm-hero-ticker">{label}/USD — Current Signal</div>
    <div class="hmm-signal-pill {pill_cls}">
      <div class="hmm-pulse"></div>{signal}
    </div>
    <div style="font-size:11px;color:var(--t3);margin-top:6px;">
      {ts} &nbsp;·&nbsp; HMM State {hmm_st}
    </div>
  </div>
  <div class="hmm-hero-stats">
    <div class="hmm-hero-stat">
      <div class="hmm-stat-label">Regime</div>
      <div class="hmm-regime-badge {regime_cls}">{regime_icon} {regime}</div>
    </div>
    <div class="hmm-hero-stat">
      <div class="hmm-stat-label">Confirmations</div>
      <div class="hmm-stat-val">{n_conf}<span style="font-size:14px;color:var(--t3)">/10</span></div>
      <div class="hmm-conf-pips">{pips_html}</div>
    </div>
    <div class="hmm-hero-stat">
      <div class="hmm-stat-label">24h</div>
      <div class="hmm-stat-val {delta_cls}">{delta_sign} {abs(pct_24h):.2f}%</div>
    </div>
    <div class="hmm-hero-stat">
      <div class="hmm-stat-label">Price</div>
      <div class="hmm-stat-val acc">${price:,.2f}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Regime-Coloured Ticker Cards
# ══════════════════════════════════════════════════════════════════════════════

def render_ticker_cards(all_data: dict) -> None:
    """Render 4 regime-coloured ticker cards as HTML."""
    cards_html = ['<div class="hmm-cards">']

    for ticker in TICKERS:
        if ticker not in all_data:
            cards_html.append(
                f'<div class="hmm-card neut"><div class="hmm-card-name">'
                f'{TICKER_LABELS[ticker]}</div><div style="color:var(--t3)">No data</div></div>'
            )
            continue

        df_t  = all_data[ticker]["df"]
        label = TICKER_LABELS[ticker]
        price = float(df_t["Close"].iloc[-1])

        def _pct(n):
            if len(df_t) > n:
                old = float(df_t["Close"].iloc[-(n + 1)])
                return (price / old - 1) * 100 if old else 0.0
            return 0.0

        pct_24h = _pct(24)
        pct_7d  = _pct(168)
        mcap    = fetch_circ_supply(ticker)
        regime  = str(df_t["Regime"].iloc[-1])
        reg_cls = {"Bull": "bull", "Bear": "bear"}.get(regime, "neut")
        reg_icon= {"Bull": "●", "Bear": "●"}.get(regime, "●")
        d_cls   = "pos" if pct_24h >= 0 else "neg"
        d_sign  = "▲" if pct_24h >= 0 else "▼"
        w_color = "var(--bull)" if pct_7d >= 0 else "var(--bear)"

        cards_html.append(f"""
<div class="hmm-card {reg_cls}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div class="hmm-card-name">{label}</div>
      <div class="hmm-card-tick">{ticker}/USD</div>
    </div>
    <div class="hmm-regime-pill {reg_cls}">{reg_icon} {regime}</div>
  </div>
  <div class="hmm-card-price">${price:,.2f}</div>
  <div class="hmm-card-delta {d_cls}">{d_sign} {abs(pct_24h):.2f}% (24h)</div>
  <div class="hmm-card-stats">
    <div class="hmm-card-stat">
      <div class="hmm-card-stat-label">7d</div>
      <div class="hmm-card-stat-val" style="color:{w_color}">{pct_7d:+.1f}%</div>
    </div>
    <div class="hmm-card-stat">
      <div class="hmm-card-stat-label">Mkt Cap</div>
      <div class="hmm-card-stat-val">{mcap}</div>
    </div>
  </div>
</div>""")

    cards_html.append('</div>')
    st.markdown("\n".join(cards_html), unsafe_allow_html=True)


def render_sentiment_strip(all_data: dict) -> None:
    """Render the compact market sentiment strip (replaces Plotly gauge)."""
    scores = []
    for t in TICKERS:
        if t in all_data:
            r = all_data[t]["df"]["Regime"].iloc[-1]
            scores.append(1 if r == "Bull" else (-1 if r == "Bear" else 0))

    if not scores:
        return

    avg        = sum(scores) / len(scores)       # -1 to +1
    gauge_pct  = (avg + 1) / 2 * 100             # 0 to 100

    if gauge_pct >= 67:
        label, color = "Bullish",  "var(--bull)"
    elif gauge_pct <= 33:
        label, color = "Bearish",  "var(--bear)"
    else:
        label, color = "Neutral",  "var(--neut)"

    bull_n = scores.count(1)
    neut_n = scores.count(0)
    bear_n = scores.count(-1)

    st.markdown(f"""
<div class="hmm-sent-strip">
  <div class="hmm-sent-label">Market Sentiment</div>
  <div class="hmm-gauge-wrap">
    <div class="hmm-gauge-track">
      <div class="hmm-gauge-needle" style="left:{gauge_pct:.0f}%"></div>
    </div>
    <div class="hmm-gauge-ticks"><span>Bearish</span><span>Neutral</span><span>Bullish</span></div>
  </div>
  <div class="hmm-sent-val" style="color:{color}">{label}</div>
  <div class="hmm-sent-pills">
    <div class="hmm-sent-pill bull">● Bull ×{bull_n}</div>
    <div class="hmm-sent-pill neut">● Neutral ×{neut_n}</div>
    <div class="hmm-sent-pill bear">● Bear ×{bear_n}</div>
  </div>
</div>
""", unsafe_allow_html=True)


def render_conf_panel(latest) -> None:
    """Render confirmation checklist as an open-by-default collapsible panel."""
    n_conf = int(latest["Confirmations"])
    rows = []
    for col_name in CONFIRM_COLS:
        val     = bool(latest.get(col_name, False))
        cls     = "pass" if val else "fail"
        icon    = "✓" if val else "✗"
        desc    = CONFIRM_LABELS[col_name]
        rows.append(
            f'<div class="hmm-conf-item">'
            f'<div class="hmm-conf-icon {cls}">{icon}</div>{desc}</div>'
        )

    items_html = "\n".join(rows)
    panel_id   = "hmmConfBody"

    st.markdown(f"""
<div class="hmm-conf-card">
  <div class="hmm-conf-header" onclick="
    var b=document.getElementById('{panel_id}');
    b.classList.toggle('collapsed');
    this.querySelector('.hmm-conf-count').textContent =
      b.classList.contains('collapsed') ? '{n_conf}/10 met ▾' : '{n_conf}/10 met ▴';
  ">
    <div class="hmm-conf-title">🔍 Confirmation Detail — Current Bar</div>
    <div class="hmm-conf-count">{n_conf}/10 met ▴</div>
  </div>
  <div class="hmm-conf-body" id="{panel_id}">
    {items_html}
  </div>
</div>
""", unsafe_allow_html=True)


def render_metrics_snapshot(m: dict, ticker: str) -> None:
    """Render the 6-cell backtest metrics grid card."""
    label      = TICKER_LABELS.get(ticker, ticker)
    ret_cls    = "pos" if m["Total Return (%)"] >= 0 else "neg"
    alpha_cls  = "pos" if m["Alpha (pp)"] >= 0 else "neg"
    dd_cls     = "neg"

    st.markdown(f"""
<div class="hmm-metrics-card">
  <div class="hmm-metrics-head">
    <div class="hmm-metrics-title">Backtest Snapshot — {label}/USD</div>
    <div class="hmm-metrics-sub">$20,000 start · 1.5× leverage · 72-hr cooldown</div>
  </div>
  <div class="hmm-metrics-grid">
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Total Return</div>
      <div class="hmm-metric-val {ret_cls}">{m["Total Return (%)"]:+.1f}%</div>
      <div class="hmm-metric-ctx {alpha_cls}">α {m["Alpha (pp)"]:+.1f}pp vs B&H</div>
    </div>
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Buy &amp; Hold</div>
      <div class="hmm-metric-val">{m["Buy & Hold (%)"]:+.1f}%</div>
      <div class="hmm-metric-ctx">Benchmark</div>
    </div>
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Win Rate</div>
      <div class="hmm-metric-val acc">{m["Win Rate (%)"]:.0f}%</div>
      <div class="hmm-metric-ctx">of trades</div>
    </div>
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Max Drawdown</div>
      <div class="hmm-metric-val {dd_cls}">{m["Max Drawdown (%)"]:.1f}%</div>
      <div class="hmm-metric-ctx {dd_cls}">Peak-to-trough</div>
    </div>
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Sharpe Ratio</div>
      <div class="hmm-metric-val acc">{m["Sharpe Ratio"]:.2f}</div>
      <div class="hmm-metric-ctx">Risk-adjusted</div>
    </div>
    <div class="hmm-metric-cell">
      <div class="hmm-metric-lbl">Final Equity</div>
      <div class="hmm-metric-val pos">${m["Final Equity ($)"]:,.0f}</div>
      <div class="hmm-metric-ctx">{m["Total Trades"]} trades</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def _section_label(text: str) -> None:
    st.markdown(
        f'<div style="font-size:12px;font-weight:600;letter-spacing:.07em;'
        f'text-transform:uppercase;color:var(--t3);margin:4px 0 -4px;">{text}</div>',
        unsafe_allow_html=True,
    )


st.markdown("# HMM Quant Trades")

tab_dashboard, tab_backtest, tab_about = st.tabs(
    ["📊 Live", "📋 Backtest", "📖 About"]
)

# ── Load all tickers (outside tabs so all_data is accessible to every tab) ───
with st.spinner("Loading market data…"):
    all_data = {}
    for ticker in TICKERS:
        try:
            all_data[ticker] = load_ticker(ticker, period, n_states)
        except Exception as e:
            st.warning(f"Could not load {ticker}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:

    # ── Hero Banner ───────────────────────────────────────────────────────────
    if selected_ticker in all_data:
        res    = all_data[selected_ticker]
        df_sel = res["df"]
        latest = df_sel.iloc[-1]
        render_hero_banner(df_sel, selected_ticker, latest)

    # ── Market Overview ───────────────────────────────────────────────────────
    _section_label("Market Overview")
    render_ticker_cards(all_data)
    render_sentiment_strip(all_data)

    # ── Price Chart ───────────────────────────────────────────────────────────
    if selected_ticker in all_data:
        res    = all_data[selected_ticker]
        df_sel = res["df"]
        latest = df_sel.iloc[-1]
        _section_label("Price Chart")
        chart = build_candlestick(
            df_sel.iloc[-chart_bars:], selected_ticker
        )
        label = TICKER_LABELS.get(selected_ticker, selected_ticker)
        st.markdown(f"""
<div class="hmm-chart-card">
  <div class="hmm-chart-head">
    <div class="hmm-chart-title">{label}/USD — Hourly Chart with Regime Overlay</div>
    <div class="hmm-chart-badges">
      <span class="hmm-badge hmm-badge-ema20">EMA 20</span>
      <span class="hmm-badge hmm-badge-ema200">EMA 200</span>
      <span class="hmm-badge hmm-badge-vol">Volume</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        st.plotly_chart(chart, use_container_width=True, key="main_chart")
        render_conf_panel(latest)

    # ── Backtest Snapshot ─────────────────────────────────────────────────────
    _section_label("Backtest Snapshot")
    try:
        equity_curve, bh_curve, trades_df, metrics = load_backtest(
            selected_ticker, period, n_states
        )
        render_metrics_snapshot(metrics, selected_ticker)
    except Exception as e:
        st.error(f"Backtest error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BACKTEST DETAILS
# ─────────────────────────────────────────────────────────────────────────────
with tab_backtest:
    label = TICKER_LABELS.get(selected_ticker, selected_ticker)
    try:
        if position_mode == "user_defined" and user_exit_ladder:
            try:
                validated_ladder = build_exit_thresholds("user_defined", user_exit_ladder)
                result_data = load_ticker(selected_ticker, period, n_states)
                equity_curve, bh_curve, trades_df, metrics = run_backtest(
                    result_data["df"],
                    position_mode="user_defined",
                    user_exit_ladder=validated_ladder,
                )
            except ValueError as e:
                st.warning(f"Invalid custom ladder: {e} — using recommended.")
                equity_curve, bh_curve, trades_df, metrics = load_backtest(
                    selected_ticker, period, n_states
                )
        else:
            equity_curve, bh_curve, trades_df, metrics = load_backtest(
                selected_ticker, period, n_states
            )

        # ── Historical Signal Replay ───────────────────────────────────────────
        try:
            replay = load_replay(selected_ticker, period, n_states)
            if replay:
                _section_label("Last 5 Completed LONG Trades")
                for trade in replay:
                    ret_color   = "#00c96a" if trade["total_return_pct"] >= 0 else "#e03535"
                    pnl_sign    = "+" if trade["pnl_usd"] >= 0 else ""
                    partials_str = "  ".join(
                        f"`{p}`" for p in trade["partials_fired"]
                    ) if trade["partials_fired"] else "*no partial exits*"
                    st.markdown(
                        f"**Trade {trade['trade_num']}** &nbsp; "
                        f"{trade['entry_time'][:10]} → {trade['exit_time'][:10]} "
                        f"({trade['duration_h']}h)&nbsp; | &nbsp;"
                        f"<span style='color:{ret_color}'>"
                        f"**{trade['total_return_pct']:+.1f}%** / "
                        f"{pnl_sign}${trade['pnl_usd']:,.0f}</span> &nbsp; | &nbsp;"
                        f"Exit: *{trade['exit_reason']}* &nbsp; | &nbsp;"
                        f"Regime: {trade['regime_at_entry']} · "
                        f"{trade['confirmations_entry']}/10 conf &nbsp;",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Partials fired: {partials_str}  ·  Peak gain: {trade['peak_gain_pct']:+.1f}%")
        except Exception as e:
            st.warning(f"Replay unavailable: {e}")

        # Equity chart
        eq_fig = build_equity_chart(equity_curve, bh_curve, selected_ticker)
        st.markdown(f"""
<div class="hmm-chart-card">
  <div class="hmm-chart-head">
    <div class="hmm-chart-title">Portfolio Equity vs Buy &amp; Hold — {label}/USD</div>
    <div class="hmm-chart-badges">
      <span class="hmm-badge hmm-badge-strat">Strategy</span>
      <span class="hmm-badge hmm-badge-bh">Buy &amp; Hold</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        st.plotly_chart(eq_fig, use_container_width=True, key="eq_chart")

        # Trade log
        n_trades  = len(trades_df)
        avg_ret   = metrics.get("Avg Trade Return (%)", 0)
        caption   = f"{n_trades} trades · Avg {avg_ret:+.2f}% per trade"
        st.markdown(f"""
<div class="hmm-tradelog-card">
  <div class="hmm-tradelog-head">
    <div class="hmm-tradelog-title">Trade Log</div>
    <div class="hmm-tradelog-meta">{caption}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        if n_trades == 0:
            st.info("No completed trades in this period. Try a longer window or different ticker.")
        else:
            def color_ret(val):
                try:
                    return "color: #00c96a" if float(val) > 0 else "color: #e03535"
                except Exception:
                    return ""
            st.dataframe(
                trades_df.style.map(color_ret, subset=["Return %"]),
                use_container_width=True,
                hide_index=False,
            )
    except Exception as e:
        st.error(f"Could not run backtest: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — ABOUT
# ─────────────────────────────────────────────────────────────────────────────
with tab_about:
    left_html = """
<div class="hmm-about-card">
  <h3>What This App Does</h3>
  <p>Uses a <strong>Hidden Markov Model (HMM)</strong> to detect the current market regime
  (Bull, Bear, or Neutral) for BTC, ETH, SOL, and ADA. When the HMM identifies a
  <strong>Bull regime</strong> and at least <strong>8 of 10</strong> technical confirmations
  are met, the app generates a <strong>LONG</strong> signal.</p>
</div>
<div class="hmm-about-card">
  <h3>The 10-Point Confirmation System</h3>
  <ul>
    <li>RSI &lt; 80 — not yet overbought</li>
    <li>Momentum &gt; 1.5% — 24h upward thrust</li>
    <li>Volatility &lt; 6% — sustainable move</li>
    <li>MACD nearing positive — momentum turning</li>
    <li>Volume &gt; 20-bar SMA — conviction behind move</li>
    <li>ADX &gt; 30 — strong trend confirmed</li>
    <li>Price &gt; EMA 20 — short-term structure</li>
    <li>Price &gt; EMA 200 — long-term structure</li>
    <li>MACD &gt; Signal line — bullish cross</li>
    <li>RSI &gt; 20 — not in panic territory</li>
  </ul>
</div>
"""
    right_html = """
<div class="hmm-about-card">
  <h3>Model Parameters</h3>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Model</span><span class="hmm-stat-val">GaussianHMM</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Covariance</span><span class="hmm-stat-val">Full</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Iterations</span><span class="hmm-stat-val">1,000</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Scaler</span><span class="hmm-stat-val">StandardScaler</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Features</span><span class="hmm-stat-val">Returns, Range, Vol &#x394;</span></div>
</div>
<div class="hmm-about-card">
  <h3>Risk Management</h3>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Leverage</span><span class="hmm-stat-val">1.5&times;</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Start Capital</span><span class="hmm-stat-val">$20,000</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Cooldown</span><span class="hmm-stat-val">72 hrs post-exit</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Exit Trigger</span><span class="hmm-stat-val">Bear regime flip</span></div>
</div>
<div class="hmm-disclaimer">
  &#x26A0;&#xFE0F; <strong>Not financial advice.</strong> Educational use only.
  Past performance does not guarantee future results.
</div>
"""
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.markdown(left_html, unsafe_allow_html=True)
    with col_right:
        st.markdown(right_html, unsafe_allow_html=True)

    # ── Detailed model documentation ──────────────────────────────────────────
    st.markdown("""
---

## 2. The Hidden Markov Model (HMM)

### What is an HMM?
A **Hidden Markov Model** is a probabilistic model that assumes an observable
sequence (price data) is generated by an underlying sequence of *hidden states*
(market regimes) that we cannot observe directly.

At each hour, the market is in exactly one hidden state. The model learns:
- The **probability of transitioning** from one state to another
- The **emission distribution** — what feature values each state tends to produce

### Why use an HMM for regime detection?
Unlike simple rules (e.g. "RSI > 70 = overbought"), an HMM:
- Captures *regime persistence* — markets trend, they don't flip randomly
- Models *multi-dimensional structure* — considers returns, volatility, and volume simultaneously
- Is **unsupervised** — no labelled data or manual regime definitions needed

### Implementation
| Parameter | Value | Reason |
|---|---|---|
| Model | `hmmlearn.GaussianHMM` | Continuous emission distributions |
| States | 6 (adjustable) | Captures Bull, Bear, and Neutral sub-regimes |
| Covariance | `full` | Each state has its own 3×3 covariance matrix |
| Iterations | 1,000 | EM algorithm convergence |
| Scaler | `StandardScaler` | Required — prevents ill-conditioned covariances |

**State labelling** is automatic:
- 🟢 **Bull** — state with the highest mean hourly return
- 🔴 **Bear** — state with the lowest mean hourly return
- ⚪ **Neutral** — all remaining states

---

## 3. The Three HMM Training Features

| Feature | Formula | What It Captures |
|---|---|---|
| **Returns** | `Close.pct_change()` | Momentum and price direction |
| **Range** | `(High − Low) / Close` | Intrabar volatility |
| **Vol_Change** | `Volume.pct_change()` | Liquidity shifts — surges signal breakouts |

All three features are **IQR-clipped** before training to prevent extreme outliers
(e.g. flash crashes) from hijacking entire HMM states.

---

## 4. The 10-Point Confirmation System

The strategy requires a **Bull** regime AND at least **8 of 10** conditions below.
This double-filter reduces false signals.

| # | Condition | Rationale |
|---|---|---|
| 1 | RSI < 80 | Not yet overbought — room to run |
| 2 | Momentum > 1.5% | 24-hour price gain confirms upward thrust |
| 3 | Volatility < 6% | Low 24-hr realised vol = sustainable move |
| 4 | MACD nearing positive | MACD histogram > −0.1% of price |
| 5 | Volume > 20-bar SMA | Above-average volume = conviction |
| 6 | ADX > 30 | Strong trend confirmed |
| 7 | Price > EMA 20 | Short-term bullish structure |
| 8 | Price > EMA 200 | Long-term bullish structure |
| 9 | MACD > Signal line | Classic bullish MACD cross |
| 10 | RSI > 20 | Not in panic territory |

---

## 5. Risk Management Rules

| Rule | Detail |
|---|---|
| Exit trigger | Close position when regime flips to Bear |
| Cooldown | 72-hour ban on re-entry after any exit |
| Leverage | 1.5× simulated on PnL |
| Position size | 100% of current equity per trade |

---

## 6. Backtest Methodology

- **Data**: Yahoo Finance hourly OHLCV, up to 730 days
- **Starting capital**: $20,000 · No transaction costs or slippage
- **No look-ahead bias** — signals computed bar-by-bar in sequence
- **Compounding**: equity compounds across trades

| Metric | Definition |
|---|---|
| Total Return | `(final_equity / 20,000 − 1) × 100` |
| Buy & Hold | Passive hold over same period |
| Alpha | Total Return − Buy & Hold (pp) |
| Win Rate | % of completed trades that were profitable |
| Max Drawdown | Largest peak-to-trough equity decline |
| Sharpe Ratio | Annualised `mean(ret) / std(ret)` using `√8760` |

---

## 7. Sidebar Controls

| Control | Effect |
|---|---|
| Focus Ticker | Selects asset for signal, chart, and backtest |
| Data Window | 365d or 730d of hourly history |
| HMM States | Number of hidden regimes (4–8) |
| Chart Bars | Hourly bars displayed in candlestick chart |

---

## 8. Market Cap

> **Market Cap = Current Price × Circulating Supply**

Values sourced from `yfinance` and displayed as T / B / M.
Circulating supply figures can vary across data providers.

---

## 9. Data Sources

| Source | Purpose |
|---|---|
| yfinance | OHLCV price data from Yahoo Finance |
| hmmlearn | GaussianHMM implementation |
| scikit-learn | StandardScaler normalisation |
| Rabiner (1989) | *A Tutorial on HMMs* — foundational reference |
| Wilder (1978) | *New Concepts in Technical Trading Systems* — RSI, ADX |

---

## 10. Limitations

- **No transaction costs**: Real trading incurs fees, spread, and slippage
- **HMM instability**: State labels can shift between runs due to random initialisation
- **Hourly granularity**: Signals lag intraday moves; crypto can gap significantly
- **Leverage risk**: 1.5× amplifies losses during fast Bear regime flips
- **Survivorship bias**: Only currently-listed assets are analysed
""")

    # Regime State Profiles
    _section_label("Regime State Profiles")
    if selected_ticker in all_data:
        res = all_data[selected_ticker]
        st.dataframe(
            style_summary(res["state_summary"]),
            use_container_width=True,
            hide_index=True,
        )
