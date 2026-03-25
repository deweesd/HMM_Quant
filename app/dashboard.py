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

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title = "Regime Trading App",
    page_icon  = "📈",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Minimal custom CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
  .signal-long    { background:#0d6b3a; color:#fff; padding:6px 18px;
                    border-radius:8px; font-size:1.4rem; font-weight:700; }
  .signal-short   { background:#8b1a1a; color:#fff; padding:6px 18px;
                    border-radius:8px; font-size:1.4rem; font-weight:700; }
  .signal-neutral { background:#444;    color:#ccc; padding:6px 18px;
                    border-radius:8px; font-size:1.4rem; font-weight:700; }
  .regime-bull    { color:#00c96a; font-weight:700; font-size:1.1rem; }
  .regime-bear    { color:#e03535; font-weight:700; font-size:1.1rem; }
  .regime-neutral { color:#aaa;    font-weight:700; font-size:1.1rem; }
  .card-label     { font-size:0.75rem; color:#aaa; text-transform:uppercase;
                    letter-spacing:0.08em; }
  .divider        { border-top: 1px solid #333; margin: 16px 0; }
</style>
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

    st.divider()
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

    st.divider()
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
        paper_bgcolor = "#0f1117",
        plot_bgcolor  = "#0f1117",
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
        paper_bgcolor = "#0f1117",
        plot_bgcolor  = "#0f1117",
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
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("# HMM Quant Trades")

tab_dashboard, tab_backtest, tab_readme = st.tabs(
    ["📊 Dashboard", "📋 Backtest", "📖 README"]
)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:

    # ── Load all 4 tickers for top cards ──────────────────────────────────────
    with st.spinner("Loading market data and training HMM models…"):
        all_data = {}
        for t in TICKERS:
            try:
                all_data[t] = load_ticker(t, period, n_states)
            except Exception as e:
                st.error(f"Failed to load {t}: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 1 — TICKER OVERVIEW CARDS
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Market Overview")
    cols = st.columns(4)

    for col, ticker in zip(cols, TICKERS):
        if ticker not in all_data:
            col.warning(f"{TICKER_LABELS[ticker]}: no data")
            continue

        df_t   = all_data[ticker]["df"]
        label  = TICKER_LABELS[ticker]
        price  = float(df_t["Close"].iloc[-1])

        # Price changes (guard against index being too short)
        def safe_pct(bars_back: int) -> float:
            if len(df_t) > bars_back:
                old = float(df_t["Close"].iloc[-(bars_back + 1)])
                return (price / old - 1) * 100 if old != 0 else 0.0
            return 0.0

        pct_24h = safe_pct(24)
        pct_7d  = safe_pct(168)
        mcap    = fetch_circ_supply(ticker)

        # 7-day sparkline (last 168 hourly bars)
        spark_prices = df_t["Close"].iloc[-168:]
        spark_fig    = make_sparkline(spark_prices, positive=(pct_7d >= 0))

        with col:
            st.markdown(f"### {label}/USD")
            st.metric(
                label = "Price",
                value = f"${price:,.2f}",
                delta = f"{pct_24h:+.2f}% (24h)",
                delta_color = "normal",
            )
            st.metric("7d Change",  f"{pct_7d:+.2f}%")
            st.metric("Market Cap", mcap)
            st.plotly_chart(spark_fig, use_container_width=True, key=f"spark_{ticker}")

    # ══════════════════════════════════════════════════════════════════════════
    # OVERALL MARKET SENTIMENT GAUGE
    # Scores each asset: Bull = +1, Neutral = 0, Bear = -1
    # Averages across all 4 tickers → maps to 0–100 for the gauge needle.
    # Green zone (67–100) = broadly bullish market
    # Grey  zone (33–67)  = mixed / neutral
    # Red   zone (0–33)   = broadly bearish market
    # ══════════════════════════════════════════════════════════════════════════
    regime_scores = []
    for t in TICKERS:
        if t in all_data:
            reg = all_data[t]["df"]["Regime"].iloc[-1]
            if reg == "Bull":
                regime_scores.append(1)
            elif reg == "Bear":
                regime_scores.append(-1)
            else:
                regime_scores.append(0)

    if regime_scores:
        avg_score   = sum(regime_scores) / len(regime_scores)   # -1 to +1
        gauge_value = (avg_score + 1) / 2 * 100                 # 0 to 100

        if gauge_value >= 67:
            sentiment_label = "Bullish"
            needle_color    = "#00c96a"
        elif gauge_value <= 33:
            sentiment_label = "Bearish"
            needle_color    = "#e03535"
        else:
            sentiment_label = "Neutral"
            needle_color    = "#888888"

        gauge_fig = go.Figure(go.Indicator(
            mode  = "gauge+number+delta",
            value = gauge_value,
            title = {"text": f"Overall Market Sentiment — <b>{sentiment_label}</b>",
                     "font": {"size": 15}},
            delta = {"reference": 50, "increasing": {"color": "#00c96a"},
                     "decreasing": {"color": "#e03535"}},
            number= {"suffix": "", "font": {"size": 28}, "valueformat": ".0f"},
            gauge = {
                "axis": {"range": [0, 100], "tickwidth": 1,
                         "tickcolor": "#555", "tickvals": [0, 33, 50, 67, 100],
                         "ticktext": ["Bear", "", "Neutral", "", "Bull"]},
                "bar":  {"color": needle_color, "thickness": 0.25},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  33], "color": "rgba(224,53,53,0.18)"},
                    {"range": [33, 67], "color": "rgba(100,100,100,0.12)"},
                    {"range": [67,100], "color": "rgba(0,201,106,0.18)"},
                ],
                "threshold": {
                    "line":  {"color": "#ffffff", "width": 2},
                    "thickness": 0.75,
                    "value": 50,
                },
            },
        ))
        gauge_fig.update_layout(
            height        = 220,
            margin        = dict(l=30, r=30, t=40, b=10),
            paper_bgcolor = "rgba(0,0,0,0)",
            font          = {"color": "#e0e0e0"},
        )

        bull_count = regime_scores.count(1)
        bear_count = regime_scores.count(-1)
        neut_count = regime_scores.count(0)

        g_left, g_mid, g_right = st.columns([1, 2, 1])
        with g_mid:
            st.plotly_chart(gauge_fig, use_container_width=True, key="market_gauge")
            st.caption(
                f"Based on HMM regime across all 4 assets  ·  "
                f"🟢 Bull: {bull_count}  ⚪ Neutral: {neut_count}  🔴 Bear: {bear_count}"
            )

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 2 — CURRENT SIGNAL + REGIME SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader(f"Signal & Regime — {TICKER_LABELS[selected_ticker]}/USD")

    if selected_ticker in all_data:
        res    = all_data[selected_ticker]
        df_sel = res["df"]
        latest = df_sel.iloc[-1]

        signal  = str(latest["Signal"])
        regime  = str(latest["Regime"])
        n_conf  = int(latest["Confirmations"])

        sig_col, reg_col, conf_col, summary_col = st.columns([1, 1, 1, 3])

        # Signal badge
        with sig_col:
            st.markdown('<p class="card-label">Current Signal</p>',
                        unsafe_allow_html=True)
            badge_cls = {
                "LONG":    "signal-long",
                "SHORT":   "signal-short",
                "NEUTRAL": "signal-neutral",
            }.get(signal, "signal-neutral")
            st.markdown(f'<span class="{badge_cls}">{signal}</span>',
                        unsafe_allow_html=True)
            st.caption(f"As of {df_sel.index[-1].strftime('%Y-%m-%d %H:%M UTC')}")

        # Regime
        with reg_col:
            st.markdown('<p class="card-label">Detected Regime</p>',
                        unsafe_allow_html=True)
            reg_cls = {"Bull": "regime-bull", "Bear": "regime-bear"}.get(
                regime, "regime-neutral"
            )
            icon = {"Bull": "🟢", "Bear": "🔴", "Neutral": "⚪"}.get(regime, "⚪")
            st.markdown(f'<span class="{reg_cls}">{icon} {regime}</span>',
                        unsafe_allow_html=True)
            st.caption(f"HMM State {int(latest['HMM_State'])}")

        # Confirmation count
        with conf_col:
            st.markdown('<p class="card-label">Confirmations</p>',
                        unsafe_allow_html=True)
            st.markdown(
                f"<h2 style='margin:0;color:{'#00c96a' if n_conf>=8 else '#e0e0e0'}'>"
                f"{n_conf}/10</h2>",
                unsafe_allow_html=True,
            )
            st.caption("Minimum 8/10 required for LONG")

        # Regime summary table
        with summary_col:
            st.markdown('<p class="card-label">Regime Summary (all states)</p>',
                        unsafe_allow_html=True)
            st.dataframe(
                style_summary(res["state_summary"]),
                use_container_width = True,
                hide_index          = True,
            )

        # ── Scenario Calculator (only shown when signal is LONG) ───────────────
        if signal == "LONG":
            try:
                if position_mode == "user_defined" and user_exit_ladder:
                    try:
                        validated_ladder = build_exit_thresholds("user_defined", user_exit_ladder)
                        scenario = get_scenario(
                            df_sel, selected_ticker, position_usd, validated_ladder
                        )
                    except ValueError as e:
                        st.warning(f"Invalid custom ladder: {e} — showing recommended.")
                        scenario = load_scenario(selected_ticker, period, n_states, position_usd)
                else:
                    scenario = load_scenario(selected_ticker, period, n_states, position_usd)

                st.markdown("#### Scenario Calculator")
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("Entry Price",    f"${scenario['entry_price']:,.2f}")
                sc2.metric("HMM Confidence", f"{scenario['hmm_confidence']:.0%}")
                sc3.metric("Regime Bars",    f"{scenario['regime_bars']}h confirmed")
                sc4.metric("Trailing Stop",  f"${scenario['trailing_stop_price']:,.2f}",
                           delta=f"${scenario['trailing_stop_loss']:,.0f} max loss",
                           delta_color="inverse")

                # Exit schedule table
                sched_df = pd.DataFrame(scenario["exit_schedule"])
                sched_df.columns = ["Tier", "Trigger Price ($)", "USD Realised", "USD Remaining"]
                st.dataframe(sched_df, use_container_width=True, hide_index=True)
                st.caption(
                    f"Risk/Reward: {scenario['risk_reward_ratio']:.1f}×  ·  "
                    f"Avg trade duration: {scenario['avg_trade_duration_h']:.0f}h"
                )
            except Exception as e:
                st.warning(f"Scenario unavailable: {e}")

        st.divider()

        # ── Confirmation checklist ─────────────────────────────────────────────
        with st.expander("🔍 Confirmation Detail (current bar)", expanded=False):
            chk_cols = st.columns(2)
            for i, col_name in enumerate(CONFIRM_COLS):
                val  = bool(latest.get(col_name, False))
                icon = "✅" if val else "❌"
                chk_cols[i % 2].write(f"{icon}  {CONFIRM_LABELS[col_name]}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 3 — CANDLESTICK CHART
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader(f"Price Chart — {TICKER_LABELS[selected_ticker]}/USD")

    if selected_ticker in all_data:
        df_plot = all_data[selected_ticker]["df"].tail(chart_bars)
        chart   = build_candlestick(df_plot, selected_ticker)
        st.plotly_chart(chart, use_container_width=True, key="main_chart")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 4 — BACKTEST METRICS
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader(f"Backtest Metrics — {TICKER_LABELS[selected_ticker]}/USD")
    st.caption("$20,000 starting capital · 1.5× leverage · 72-hr cooldown after exit")

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

        m = metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Total Return",
            f"{m['Total Return (%)']:+.1f}%",
            delta = f"α {m['Alpha (pp)']:+.1f}pp vs B&H",
            delta_color = "normal",
        )
        c2.metric("Win Rate",     f"{m['Win Rate (%)']:.0f}%")
        c3.metric("Max Drawdown", f"{m['Max Drawdown (%)']:.1f}%")
        c4.metric("Sharpe Ratio", f"{m['Sharpe Ratio']:.2f}")

        sub1, sub2, sub3 = st.columns(3)
        sub1.metric("Buy & Hold",    f"{m['Buy & Hold (%)']:+.1f}%")
        sub2.metric("Total Trades",  m["Total Trades"])
        sub3.metric("Final Equity",  f"${m['Final Equity ($)']:,.0f}")

    except Exception as e:
        st.error(f"Backtest error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BACKTEST DETAILS
# ─────────────────────────────────────────────────────────────────────────────
with tab_backtest:
    st.subheader(f"Backtest — {TICKER_LABELS[selected_ticker]}/USD")

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

        # Equity curve chart
        eq_fig = build_equity_chart(equity_curve, bh_curve, selected_ticker)
        st.plotly_chart(eq_fig, use_container_width=True, key="eq_chart")

        st.divider()

        # ── Trade log ──────────────────────────────────────────────────────────
        st.subheader("Trade Log")
        if len(trades_df) == 0:
            st.info("No completed trades in this period. "
                    "Try a longer window or different ticker.")
        else:
            # Colour PnL column
            def color_ret(val):
                try:
                    v = float(val)
                    return "color: #00c96a" if v > 0 else "color: #e03535"
                except Exception:
                    return ""

            st.dataframe(
                trades_df.style.map(color_ret, subset=["Return %"]),
                use_container_width = True,
                hide_index          = False,
            )
            n_full = len(trades_df[trades_df["Is Partial"] == False]) if "Is Partial" in trades_df.columns else len(trades_df)
            st.caption(
                f"{n_full} completed trades (+ {len(trades_df) - n_full} partial exits shown) "
                f"· Avg return {metrics['Avg Trade Return (%)']:+.2f}% per trade"
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

    st.divider()

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

    st.divider()

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

    st.divider()

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

    st.divider()
    st.caption("Built with Streamlit · Plotly · hmmlearn · yfinance · Python 3.12+")
