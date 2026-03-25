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
from app.css import DASHBOARD_CSS

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

st.markdown("""
<div style="display:flex; align-items:center; justify-content:space-between;
            padding:10px 0 14px; border-bottom:1px solid var(--border);
            margin-bottom:8px;">
  <div style="font-size:18px; font-weight:700; letter-spacing:-0.3px; color:var(--t1);">
    HMM <span style="color:var(--accent-lt);">Quant</span>
  </div>
  <button id="hmmThemeBtn"
    onclick="toggleHmmTheme()"
    style="width:36px; height:36px; border-radius:50%; border:1px solid var(--border2);
           background:var(--bg2); color:var(--t2); cursor:pointer; font-size:16px;
           display:flex; align-items:center; justify-content:center; transition:var(--transition);">
    🌙
  </button>
</div>
""", unsafe_allow_html=True)


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
# HELPER: Sparkline figure
# ══════════════════════════════════════════════════════════════════════════════

def make_sparkline(prices: pd.Series, positive: bool) -> go.Figure:
    """Tiny borderless single line chart for ticker cards (7-day price trend)."""
    color = "#00c96a" if positive else "#e03535"
    fig = go.Figure(go.Scatter(
        x = prices.index,
        y = prices.values,
        mode      = "lines",
        line      = dict(color=color, width=1.2),
        showlegend = False,
        hovertemplate = "%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height      = 35,
        margin      = dict(l=0, r=0, t=0, b=0),
        xaxis       = dict(visible=False),
        yaxis       = dict(visible=False),
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
    )
    return fig


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
        base = "background-color:#1a1a2e; color:#e0e0e0;"
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

tab_dashboard, tab_backtest, tab_readme = st.tabs(
    ["📊 Dashboard", "📋 Backtest", "📖 README"]
)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:

    # ── Load all tickers ──────────────────────────────────────────────────────
    with st.spinner("Loading market data…"):
        all_data = {}
        for ticker in TICKERS:
            try:
                all_data[ticker] = load_ticker(ticker, period, n_states)
            except Exception as e:
                st.warning(f"Could not load {ticker}: {e}")

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
                st.subheader("Last 5 Completed LONG Trades")
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
                    st.markdown("---")
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
# TAB 3 — README / GUIDE
# ─────────────────────────────────────────────────────────────────────────────
with tab_readme:

    st.title("📖 README — Regime-Based Trading App")
    st.caption("A guide to how this app works, what each indicator means, "
               "and important limitations to understand before use.")

    st.markdown("""
---

## 1. What This App Does

This app uses a **Hidden Markov Model (HMM)** to automatically detect the current
*market regime* (Bull, Bear, or Neutral) for four major cryptocurrencies:
**BTC, ETH, SOL, and ADA**.

When the HMM identifies a **Bull regime** AND at least **8 of 10 technical
confirmations** are met, the app generates a **LONG** signal.
When the HMM flips to **Bear**, it signals an **EXIT** immediately.

A simulated backtest runs on 730 days of hourly data, starting with **$20,000**,
using **1.5× leverage**, and enforcing a **72-hour cooldown** after every exit.

---

## 2. The Hidden Markov Model (HMM)

### What is an HMM?
A **Hidden Markov Model** is a probabilistic model that assumes an observable
sequence (price data) is generated by an underlying sequence of *hidden states*
(market regimes) that we cannot observe directly.

At each hour, the market is in exactly one hidden state.
The model learns:
- The **probability of transitioning** from one state to another
- The **emission distribution** — what feature values each state tends to produce

### Why use an HMM for regime detection?
Unlike simple rules (e.g. "RSI > 70 = overbought"), an HMM:
- Captures *regime persistence* — markets trend, they don't flip randomly
- Models *multi-dimensional structure* — it considers returns, volatility, and
  volume simultaneously
- Is **unsupervised** — no labelled data or manual regime definitions needed

### Implementation
| Parameter | Value | Reason |
|---|---|---|
| Model | `hmmlearn.GaussianHMM` | Continuous emission distributions |
| States | 6 (adjustable) | Captures Bull, Bear, and 4 Neutral sub-regimes |
| Covariance | `full` | Each state has its own 3×3 covariance matrix |
| Iterations | 1,000 | EM algorithm convergence |
| Scaler | `StandardScaler` | Required — prevents ill-conditioned covariances |

**State labelling** is automatic:
- 🟢 **Bull Run** — the state with the highest mean hourly return
- 🔴 **Bear / Blood in the Streets** — the state with the lowest mean hourly return
- ⚪ **Neutral** — all remaining states

---

## 3. The Three HMM Training Features

| Feature | Formula | What It Captures |
|---|---|---|
| **Returns** | `Close.pct_change()` | Momentum and price direction |
| **Range** | `(High − Low) / Close` | Intrabar volatility — how wide each candle is |
| **Vol_Change** | `Volume.pct_change()` | Liquidity shifts — surges signal breakouts |

All three features are **IQR-clipped** before training to prevent extreme
outliers (e.g. flash crashes, exchange reconnections) from hijacking entire
HMM states.

---

## 4. The 10-Point Confirmation System

The strategy requires the HMM to identify a **Bull** regime AND at least
**8 out of 10** of the following technical conditions to be true.
This double-filter reduces false signals.

| # | Condition | Rationale |
|---|---|---|
| 1 | **RSI < 80** | Not yet overbought — room to run |
| 2 | **Momentum > 1.5%** | 24-hour price gain confirms upward thrust |
| 3 | **Volatility < 6%** | Low 24-hr realised vol = calmer, more sustainable move |
| 4 | **MACD nearing positive** | MACD histogram > −0.1% of price — momentum turning |
| 5 | **Volume > 20-bar SMA** | Above-average volume = conviction behind the move |
| 6 | **ADX > 30** | Wilder ADX confirms a *strong* trend is in place |
| 7 | **Price > EMA 20** | Short-term bullish structure |
| 8 | **Price > EMA 200** | Long-term bullish structure |
| 9 | **MACD > Signal line** | Classic bullish MACD cross |
| 10 | **RSI > 20** | Not in panic / deeply oversold territory |

---

## 5. Risk Management Rules

| Rule | Detail |
|---|---|
| **Exit trigger** | Immediately close position when regime → Bear |
| **Cooldown** | Hard 72-hour ban on re-entry after any exit |
| **Leverage** | 1.5× simulated on PnL (gains and losses both amplified) |
| **Position size** | 100% of current equity per trade (no fractional sizing) |

The 72-hour cooldown prevents *choppy re-entry* when the regime is oscillating
around the Bull/Bear boundary.

---

## 6. Backtest Methodology

- **Data**: Yahoo Finance hourly OHLCV, up to 730 days
- **Starting capital**: $20,000
- **No transaction costs or slippage** (simulated idealised execution)
- **No look-ahead bias** — signals are computed bar-by-bar in sequence
- **Mark-to-market**: portfolio value includes unrealised PnL every bar
- **Compounding**: equity compounds across trades

### Metrics Explained

| Metric | Definition |
|---|---|
| **Total Return** | `(final_equity / 20,000 − 1) × 100` |
| **Buy & Hold** | Passive hold from first to last bar (same period) |
| **Alpha** | Total Return − Buy & Hold (in percentage points) |
| **Win Rate** | % of completed trades that were profitable |
| **Max Drawdown** | Largest peak-to-trough equity decline (%) |
| **Sharpe Ratio** | Annualised `mean(ret) / std(ret)` using `√8760` (24/7 crypto) |

---

## 7. Sidebar Controls

| Control | Effect |
|---|---|
| **Focus Ticker** | Selects the asset for the signal, chart, and backtest |
| **Data Window** | 365d or 730d of hourly history |
| **HMM States** | Number of hidden regimes (4–8). More states = finer granularity |
| **Chart Bars** | How many hourly bars the candlestick chart displays |
| **Exit Strategy: Position Mode** | Select "Recommended" (built-in 5-tier ladder) or "User Defined" (custom tiers). Default: Recommended. |
| **Exit Strategy: Position Size (USD)** | Hypothetical capital to size the Scenario Calculator. Default: $1,000. |
| **Exit Strategy: Custom Exit Ladder** | (User Defined only) Define 5 custom profit-taking tiers: gain % threshold and fraction to sell. |

Changing any control triggers a full re-run with 1-hour cache.

---

## 8. Market Cap — What It Shows

The **Market Cap** figure displayed on each ticker card is calculated as:

> **Market Cap = Current Price × Circulating Supply**

This is the total market value of all coins currently in circulation — analogous
to *free-float market capitalisation* in equity markets.

| Term | Definition |
|---|---|
| **Circulating Supply** | Coins that are publicly available and actively traded (excludes locked, reserved, or not-yet-minted coins) |
| **Current Price** | Latest hourly close price from Yahoo Finance |
| **Market Cap** | Price × Circulating Supply — a measure of the asset's total economic weight |

Values are sourced from `yfinance` (`Ticker.info['marketCap']`) and displayed
in abbreviated form: **T** = trillion, **B** = billion, **M** = million.

> Note: crypto circulating supply figures can vary across data providers
> due to differing definitions of "locked" vs "available" coins.

---

## 9. Data Sources & References

| Source | Purpose |
|---|---|
| [yfinance](https://github.com/ranaroussi/yfinance) | OHLCV price data from Yahoo Finance |
| [hmmlearn](https://hmmlearn.readthedocs.io/) | GaussianHMM implementation |
| [scikit-learn](https://scikit-learn.org/) | StandardScaler normalisation |
| Rabiner, L.R. (1989) | *A Tutorial on HMMs and Selected Applications in Speech Recognition*, Proc. IEEE |
| Wilder, J.W. (1978) | *New Concepts in Technical Trading Systems* — RSI, ADX |

---

## 10. Limitations & Disclaimer

> ⚠️ **This app is for educational and research purposes only.
> It does not constitute financial advice. Past backtest performance
> is not indicative of future results.**

**Known limitations:**
- **Survivorship bias**: Only currently-listed assets are analysed
- **No transaction costs**: Real trading incurs fees, spread, and slippage
- **HMM instability**: State labels can shift between runs due to random initialisation
- **Hourly granularity**: Signals lag intraday moves; crypto can gap significantly
- **Look-forward risk**: Indicator warm-up periods reduce usable history
- **Leverage risk**: 1.5× amplifies losses — a Bear regime exit can crystallise
  significant losses during fast moves

Always perform your own due diligence before making any investment decision.
""")

    st.subheader("How the Strategy Protects Your Position")
    st.markdown("""
**5-Tier Profit-Taking Ladder**

Rather than holding 100% of a position until a Bear regime exit, the strategy incrementally
realises gains as price advances:

| Tier | Gain from Entry | Fraction Sold |
|---|---|---|
| 1 | +15% | 10% of original position |
| 2 | +30% | 15% of original position |
| 3 | +45% | 20% of original position |
| 4 | +60% | 30% of original position |
| 5 | +100% | 50% of *remaining* position |

By +60%, approximately 75% of your original position has been de-risked into realised gains.
Anything above +100% is held until a Bear regime exit or trailing stop — no further automatic sells.

**Trailing Stop**

Once you are in a position, a moving floor protects against giving back large gains.
If price falls 5% below its peak since entry, the remaining position closes immediately —
regardless of regime. This fires before checking for a Bear regime exit on the same bar.

**3-Bar Regime Filter**

The HMM model requires 3 consecutive hourly bars in a new regime before that regime is
confirmed. A single-candle regime spike is reverted to the prior confirmed regime.
This prevents false signals from transient noise.

**Bear Regime Exit**

When the HMM detects a confirmed Bear regime (3+ consecutive Bear bars), any open
remaining position closes immediately, regardless of current gain or loss.
""")

    st.subheader("Understanding Bull, Bear, and Neutral Regimes")
    st.markdown("""
The HMM groups all hourly bars into hidden states based on three features: **Returns**
(hourly price change), **Range** (high−low spread), and **Vol_Change** (hourly volume shift).

**Bull** — the state with the highest average hourly return. Typically characterised by
positive price momentum and controlled volatility.

**Bear** — the state with the lowest average hourly return. Associated with negative price
movement or sharp drawdowns.

**Neutral** — all remaining states. Neither strongly bullish nor bearish. A Neutral regime
is **not a sell signal** — open positions remain open during Neutral periods.

**Regime vs Signal:** A regime describes the current market character. A *Signal* is
generated only when the regime is Bull AND at least 8 of 10 technical confirmations pass.
You can be in a Bull regime without a LONG signal if confirmations are weak.

Regime changes take effect only after the 3-bar minimum duration filter confirms them.
""")

    st.subheader("Model & Strategy Parameters")
    params = {
        "Initial Capital":     "$20,000",
        "Leverage":            "1.5×",
        "Cooldown After Exit": "72 bars (hours)",
        "Min Confirmations":   "8 / 10",
        "HMM States":          str(n_states),
        "MIN_REGIME_BARS":     "3",
        "TRAILING_STOP_PCT":   "5%",
        "Exit Tier 1":         "+15% → sell 10% of position",
        "Exit Tier 2":         "+30% → sell 15% of position",
        "Exit Tier 3":         "+45% → sell 20% of position",
        "Exit Tier 4":         "+60% → sell 30% of position",
        "Exit Tier 5":         "+100% → sell 50% of remaining",
    }
    params_df = pd.DataFrame(params.items(), columns=["Parameter", "Value"])
    st.dataframe(params_df, use_container_width=True, hide_index=True)

    st.caption("Built with Streamlit · Plotly · hmmlearn · yfinance · Python 3.12+")
