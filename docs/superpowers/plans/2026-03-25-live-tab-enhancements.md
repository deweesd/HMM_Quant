# Live Tab Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 7 Live Tab enhancements from the approved spec: sidebar fix, BUY/SELL chart markers, 90-day default + rangeslider, σ volatility gate, Sharpe Risk Panel, SR asset ranking, and SR↔t-stat annotation. Also remove emoji from tab labels.

**Architecture:** Three files touched in order — `strategy/signals.py` (σ gate logic), `app/css.py` (new component styles appended to DASHBOARD_CSS), `app/dashboard.py` (new render functions + chart updates + Live tab wiring). No new files created. No pipeline or model changes.

**Tech Stack:** Python, Streamlit, Plotly `go.Scatter` for markers, CSS custom properties, numpy for Sharpe/t-stat math.

---

## File Map

| File | Change |
|---|---|
| `strategy/signals.py` | Add `vol_gate` condition + `Vol_Gated` boolean column |
| `app/css.py` | Append Risk Panel CSS, sidebar collapsed control, marker badges, rangeslider, updated mobile breakpoints |
| `app/dashboard.py` | Remove `chart_bars` slider, add `compute_risk_metrics`, `compute_sr_ranking`, `render_risk_panel`, update `build_candlestick`, update Live tab wiring, strip emoji from tabs |

---

## Task 1 — σ Volatility Gate (`strategy/signals.py`)

**Files:** Modify `strategy/signals.py:74-79`

- [ ] In `score_signals()`, replace the existing `conditions` block with the gate-aware version:

```python
vol_gate = df_out["Volatility"] <= 8.0

conditions = [
    (df_out["Regime"] == "Bull") & (df_out["Confirmations"] >= 8) & vol_gate,
    df_out["Regime"] == "Bear",
]
df_out["Signal"]    = np.select(conditions, ["LONG", "SHORT"], default="NEUTRAL")
df_out["Vol_Gated"] = (
    (~vol_gate) & (df_out["Regime"] == "Bull") & (df_out["Confirmations"] >= 8)
)
```

- [ ] Verify `Vol_Gated` is a bool column — `np.select` already returns `NEUTRAL` for the gated case; `Vol_Gated` is an independent boolean flag for display only.

- [ ] Commit: `git commit -m "feat(signals): add σ volatility gate — suppress LONG when σ > 8%"`

---

## Task 2 — CSS: Risk Panel + Sidebar Fix + Marker Badges + Rangeslider + Mobile (`app/css.py`)

**Files:** Modify `app/css.py` — append new block inside the `DASHBOARD_CSS` string, just before `</style>` on line 534.

- [ ] Add the following CSS block (insert before the `</style>` tag that closes `DASHBOARD_CSS`):

```css
/* ── Sidebar collapsed control — always reachable ───────────────── */
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  z-index: 999 !important;
  top: 60px !important;
}

/* ── Chart marker badges ─────────────────────────────────────────── */
.hmm-badge-buy  { background: rgba(0,201,106,0.12); color: var(--bull);
                  border: 1px solid rgba(0,201,106,0.3); }
.hmm-badge-sell { background: rgba(239,68,68,0.12);  color: var(--bear);
                  border: 1px solid rgba(239,68,68,0.3); }

/* ── Rangeslider theme ───────────────────────────────────────────── */
.rangeslider-mask          { fill: rgba(255,255,255,0.04) !important; }
.rangeslider-grabber-min,
.rangeslider-grabber-max   { fill: var(--accent) !important; }

/* ── Risk Panel ──────────────────────────────────────────────────── */
.hmm-risk-panel {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  padding: 18px 20px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hmm-risk-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hmm-risk-panel-title {
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--t3);
}
.hmm-risk-badge {
  padding: 4px 12px; border-radius: 20px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
}
.hmm-risk-badge.bull { background: var(--bull-bg); color: var(--bull);
                       border: 1px solid rgba(0,201,106,0.25); }
.hmm-risk-badge.neut { background: var(--neut-bg); color: #e0a020;
                       border: 1px solid rgba(224,160,32,0.25); }
.hmm-risk-badge.bear { background: var(--bear-bg); color: var(--bear);
                       border: 1px solid rgba(239,68,68,0.25); }
.hmm-risk-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
.hmm-risk-metric {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  display: flex; flex-direction: column; gap: 4px;
}
.hmm-risk-metric-lbl {
  font-size: 10px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--t3);
}
.hmm-risk-metric-val {
  font-size: 22px; font-weight: 700; color: var(--t1);
}
.hmm-risk-metric-val.bull { color: var(--bull); }
.hmm-risk-metric-val.bear { color: var(--bear); }
.hmm-risk-metric-val.acc  { color: var(--accent-lt); }
.hmm-risk-metric-sub {
  font-size: 10.5px; color: var(--t3); line-height: 1.45;
}
.hmm-risk-metric-sub .sig  { color: var(--bull);  font-weight: 700; }
.hmm-risk-metric-sub .warn { color: #e0a020;       font-weight: 700; }
.hmm-risk-metric-sub .gate { color: var(--bear);   font-weight: 700; }

.hmm-vol-gate-warning {
  display: flex; align-items: center; gap: 8px;
  background: var(--bear-bg);
  border: 1px solid rgba(239,68,68,0.25);
  border-radius: var(--radius-sm);
  padding: 9px 14px;
  font-size: 11.5px; color: var(--bear); font-weight: 600;
}

.hmm-ranking-head {
  font-size: 10px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--t3); margin-bottom: 8px;
}
.hmm-ranking-table { width: 100%; border-collapse: collapse; }
.hmm-ranking-table th {
  text-align: left;
  font-size: 9.5px; font-weight: 700;
  letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--t3); padding: 0 10px 7px 0;
  border-bottom: 1px solid var(--border2);
}
.hmm-ranking-table td {
  padding: 7px 10px 7px 0;
  border-bottom: 1px solid var(--border);
  font-size: 12px; color: var(--t2); vertical-align: middle;
}
.hmm-ranking-table tr:last-child td { border-bottom: none; }
.hmm-rank-num  { font-size: 11px; font-weight: 700; color: var(--t3); }
.hmm-rank-asset{ font-weight: 600; color: var(--t1); }
.hmm-rank-tick { font-size: 10px; color: var(--t3); }
.hmm-rank-sr   { font-weight: 700; color: var(--accent-lt); font-size: 13px; }
.hmm-rank-sig  {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 700; white-space: nowrap;
}
.hmm-rank-sig.long    { background: var(--bull-bg); color: var(--bull); }
.hmm-rank-sig.neutral { background: var(--neut-bg); color: var(--neut); }
.hmm-rank-sig.short   { background: var(--bear-bg); color: var(--bear); }
.hmm-rank-sig.gated   { background: var(--bear-bg); color: var(--bear); }

/* ── Responsive additions for Risk Panel ─────────────────────────── */
@media (max-width: 900px) {
  .hmm-risk-metrics { grid-template-columns: 1fr 1fr !important; }
  .hmm-ranking-table th,
  .hmm-ranking-table td { font-size: 11px !important; }
}
@media (max-width: 600px) {
  .hmm-risk-metrics { grid-template-columns: 1fr !important; }
  .hmm-ranking-table th,
  .hmm-ranking-table td { font-size: 10px !important; padding: 5px 6px 5px 0 !important; }
  .hmm-risk-panel   { padding: 14px !important; }
}
```

- [ ] Commit: `git commit -m "feat(css): Risk Panel styles, sidebar fix, marker badges, rangeslider, mobile breakpoints"`

---

## Task 3 — Remove `chart_bars` Sidebar Slider (`app/dashboard.py`)

**Files:** Modify `app/dashboard.py:122-129`

- [ ] Delete the `chart_bars` slider block entirely (lines 122–129):

```python
# DELETE this block:
chart_bars = st.slider(
    "Chart — bars to show",
    min_value = 168,
    max_value = 2000,
    value     = 500,
    step      = 100,
    help      = "Number of hourly bars displayed in the candlestick chart.",
)
```

---

## Task 4 — Update `build_candlestick()` (`app/dashboard.py`)

**Files:** Modify `app/dashboard.py:277-412`

Changes:
1. Add BUY/SELL marker traces (after EMA200 trace, before volume bars)
2. Enable rangeslider with 90-day default range
3. Add BUY/SELL badge CSS classes to the header badges

- [ ] Replace the `build_candlestick` function with the updated version below. Key differences marked with `# NEW`:

```python
def build_candlestick(df_plot: pd.DataFrame, ticker: str) -> go.Figure:
    """
    2-row plotly chart:
      Row 1 (75%): Candlestick + EMA20 + EMA200 + BUY/SELL markers + regime background
      Row 2 (25%): Volume bars coloured by up/down candle

    Default view: last 90 calendar days. Full history available via rangeslider.
    BUY  markers: green ▲ at signal transition to LONG
    SELL markers: red   ▼ at Bear regime flip while previously in LONG
    """
    spans = get_regime_spans(df_plot)

    fig = make_subplots(
        rows             = 2,
        cols             = 1,
        shared_xaxes     = True,
        row_heights      = [0.75, 0.25],
        vertical_spacing = 0.02,
        subplot_titles   = ("", ""),
    )

    # ── Regime background (row 1 only) ────────────────────────────────────────
    for span in spans:
        fig.add_shape(
            type      = "rect",
            xref      = "x",
            yref      = "y domain",
            x0        = span["start"],
            x1        = span["end"],
            y0        = 0,
            y1        = 1,
            fillcolor = REGIME_FILL.get(span["regime"], REGIME_FILL["Neutral"]),
            line_width = 0,
            layer     = "below",
            row=1, col=1,
        )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x      = df_plot.index,
        open   = df_plot["Open"],
        high   = df_plot["High"],
        low    = df_plot["Low"],
        close  = df_plot["Close"],
        name   = "Price",
        increasing_line_color = "#26a69a",
        decreasing_line_color = "#ef5350",
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

    # ── BUY markers — NEW ─────────────────────────────────────────────────────
    if "Signal" in df_plot.columns:
        buy_mask = (df_plot["Signal"] == "LONG") & (df_plot["Signal"].shift(1) != "LONG")
        df_buy   = df_plot[buy_mask]
        if not df_buy.empty:
            # Build hover lines: entry price + 5 exit targets + stop
            custom = []
            for _, row in df_buy.iterrows():
                ep = row["Close"]
                targets = "<br>".join(
                    f"  +{t['gain_pct']}% → ${ep*(1+t['gain_pct']/100):,.0f} "
                    f"(sell {int(t['sell_fraction']*100)}%)"
                    for t in RECOMMENDED_LADDER
                )
                stop = ep * 0.95
                custom.append(
                    f"Entry: ${ep:,.2f}<br>Exit targets:<br>{targets}"
                    f"<br>Stop loss: ${stop:,.2f} (−5% trailing)"
                )
            fig.add_trace(go.Scatter(
                x          = df_buy.index,
                y          = df_buy["Low"] * 0.995,
                mode       = "markers",
                name       = "BUY",
                marker     = dict(
                    symbol = "triangle-up",
                    size   = 10,
                    color  = "#00c96a",
                    line   = dict(color="#00c96a", width=1),
                ),
                customdata = custom,
                hovertemplate = (
                    "<b>🟢 BUY SIGNAL</b><br>%{customdata}<extra></extra>"
                ),
                showlegend = False,
            ), row=1, col=1)

    # ── SELL markers — NEW ────────────────────────────────────────────────────
    if "Regime" in df_plot.columns and "Signal" in df_plot.columns:
        sell_mask = (
            (df_plot["Regime"] == "Bear") &
            (df_plot["Regime"].shift(1) != "Bear") &
            (df_plot["Signal"].shift(1) == "LONG")
        )
        df_sell = df_plot[sell_mask]
        if not df_sell.empty:
            custom_sell = [
                f"Exit price: ${row['Close']:,.2f}"
                for _, row in df_sell.iterrows()
            ]
            fig.add_trace(go.Scatter(
                x          = df_sell.index,
                y          = df_sell["High"] * 1.005,
                mode       = "markers",
                name       = "SELL",
                marker     = dict(
                    symbol = "triangle-down",
                    size   = 10,
                    color  = "#ef4444",
                    line   = dict(color="#ef4444", width=1),
                ),
                customdata = custom_sell,
                hovertemplate = (
                    "<b>🔴 EXIT — Bear Regime</b><br>%{customdata}<extra></extra>"
                ),
                showlegend = False,
            ), row=1, col=1)

    # ── Volume bars ───────────────────────────────────────────────────────────
    vol_colors = [
        "#26a69a" if c >= o else "#ef5350"
        for o, c in zip(df_plot["Open"], df_plot["Close"])
    ]
    fig.add_trace(go.Bar(
        x            = df_plot.index,
        y            = df_plot["Volume"],
        name         = "Volume",
        marker_color = vol_colors,
        opacity      = 0.7,
        showlegend   = False,
    ), row=2, col=1)

    # ── 90-day default range — NEW ────────────────────────────────────────────
    range_end   = df_plot.index[-1]
    range_start = range_end - pd.Timedelta(days=90)

    # ── Layout ────────────────────────────────────────────────────────────────
    label = TICKER_LABELS.get(ticker, ticker)
    fig.update_layout(
        title = dict(
            text  = f"{label}/USD — Hourly Chart with Regime Overlay",
            font  = dict(size=14, color="#e0e0e0"),
            x     = 0.01,
        ),
        xaxis_rangeslider_visible   = True,          # NEW — was False
        xaxis_rangeslider_thickness = 0.04,          # NEW — thin bar
        height        = 580,                         # slightly taller for rangeslider
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
        xaxis  = dict(range=[range_start, range_end]),  # NEW — 90-day default
    )
    fig.update_xaxes(
        showgrid       = True,
        gridcolor      = "#222",
        gridwidth      = 0.5,
        showspikes     = True,
        spikecolor     = "#555",
        spikethickness = 1,
    )
    fig.update_yaxes(showgrid=True, gridcolor="#222", gridwidth=0.5, row=1, col=1)
    fig.update_yaxes(showgrid=False, row=2, col=1)

    # ── Regime legend annotations ─────────────────────────────────────────────
    for regime, color in [("Bull","#00c96a"), ("Bear","#e03535"), ("Neutral","#888")]:
        fig.add_annotation(
            text      = f"■ {regime}",
            xref      = "paper", yref = "paper",
            x         = {"Bull": 0.70, "Bear": 0.80, "Neutral": 0.90}[regime],
            y         = 1.04,
            showarrow = False,
            font      = dict(color=color, size=11),
        )

    return fig
```

- [ ] Add `RECOMMENDED_LADDER` to the imports at the top of `dashboard.py` (it is already imported via `strategy.exits`; verify it is included in the existing import line):

```python
from strategy.exits import build_exit_thresholds, RECOMMENDED_LADDER
```

---

## Task 5 — Add Risk Metric Functions (`app/dashboard.py`)

**Files:** Modify `app/dashboard.py` — add three functions before the `# MAIN APP` section.

- [ ] Add `compute_risk_metrics()`:

```python
def compute_risk_metrics(df: pd.DataFrame) -> dict:
    """Compute σ, Sharpe, t-stat, and risk rating for the Risk Panel."""
    sigma   = float(df["Volatility"].iloc[-1])
    returns = df["Returns"].dropna()
    n       = len(returns)
    sharpe  = (
        float(returns.mean() / returns.std() * np.sqrt(8760))
        if returns.std() > 0 else 0.0
    )
    t_stat = sharpe * np.sqrt(n)
    sig    = t_stat > 1.96

    if sigma <= 4 and sharpe >= 1.5:
        rating, rating_cls = "Low Risk", "bull"
    elif sigma <= 8 and sharpe >= 0.5:
        rating, rating_cls = "Moderate", "neut"
    else:
        rating, rating_cls = "High Risk", "bear"

    return dict(
        sigma=sigma, sharpe=sharpe, t_stat=t_stat,
        sig=sig, rating=rating, rating_cls=rating_cls, n=n,
    )
```

- [ ] Add `compute_sr_ranking()`:

```python
def compute_sr_ranking(all_data: dict) -> list:
    """Return list of ticker dicts sorted by Sharpe descending."""
    rows = []
    for t, res in all_data.items():
        d      = res["df"]
        rm     = compute_risk_metrics(d)
        signal = str(d["Signal"].iloc[-1])
        gated  = bool(d["Vol_Gated"].iloc[-1]) if "Vol_Gated" in d.columns else False
        rows.append(dict(
            ticker=t, label=TICKER_LABELS[t],
            sharpe=rm["sharpe"], sigma=rm["sigma"],
            signal=signal, gated=gated,
        ))
    return sorted(rows, key=lambda r: r["sharpe"], reverse=True)
```

- [ ] Add `render_risk_panel()`:

```python
def render_risk_panel(df: pd.DataFrame, all_data: dict, ticker: str) -> None:
    """Render the Risk Overview panel: σ, Sharpe, t-stat, vol-gate warning, SR ranking."""
    rm      = compute_risk_metrics(df)
    ranking = compute_sr_ranking(all_data)

    sigma_cls  = "bull" if rm["sigma"] <= 4 else ("neut" if rm["sigma"] <= 8 else "bear")
    sharpe_cls = "bull" if rm["sharpe"] >= 1.5 else ("acc" if rm["sharpe"] >= 0.5 else "bear")
    tstat_cls  = "bull" if rm["sig"] else "warn"
    sig_text   = (
        f'<span class="{tstat_cls}">✓ p &lt; 0.05 — returns ≠ 0</span>'
        if rm["sig"] else
        '<span class="warn">⚠ p &gt; 0.05 — insufficient evidence</span>'
    )

    # Vol gate warning (only shown when a LONG was gated)
    gate_html = ""
    if "Vol_Gated" in df.columns and bool(df["Vol_Gated"].iloc[-1]):
        gate_html = f"""
<div class="hmm-vol-gate-warning">
  🔴 σ = {rm["sigma"]:.1f}% exceeds 8% threshold — LONG signal suppressed.
  High volatility reduces regime reliability.
</div>"""

    # Build ranking rows
    rank_rows = []
    for i, row in enumerate(ranking, 1):
        sr_color = (
            "var(--bull)"      if row["sharpe"] >= 1.5 else
            "var(--accent-lt)" if row["sharpe"] >= 0.5 else
            "var(--bear)"
        )
        sig_cls  = "gated" if row["gated"] else row["signal"].lower()
        sig_lbl  = "🔴 Gated" if row["gated"] else (
            "▲ LONG" if row["signal"] == "LONG" else
            "▼ SHORT" if row["signal"] == "SHORT" else "● NEUTRAL"
        )
        sigma_color = (
            "var(--bull)" if row["sigma"] <= 4 else
            "#e0a020"     if row["sigma"] <= 8 else
            "var(--bear)"
        )
        selected = " style='background:var(--bg1);'" if row["ticker"] == ticker else ""
        rank_rows.append(f"""
<tr{selected}>
  <td class="hmm-rank-num">{i}</td>
  <td>
    <div class="hmm-rank-asset">{row["label"]}</div>
    <div class="hmm-rank-tick">{row["ticker"]}/USD</div>
  </td>
  <td class="hmm-rank-sr" style="color:{sr_color}">{row["sharpe"]:.2f}</td>
  <td style="color:{sigma_color};font-size:12px;font-weight:600">{row["sigma"]:.1f}%</td>
  <td><span class="hmm-rank-sig {sig_cls}">{sig_lbl}</span></td>
</tr>""")

    st.markdown(f"""
<div class="hmm-risk-panel">
  <div class="hmm-risk-panel-head">
    <div class="hmm-risk-panel-title">Risk-Adjusted Performance — {TICKER_LABELS.get(ticker, ticker)}/USD</div>
    <div class="hmm-risk-badge {rm['rating_cls']}">● {rm['rating']}</div>
  </div>

  <div class="hmm-risk-metrics">
    <div class="hmm-risk-metric">
      <div class="hmm-risk-metric-lbl">σ Volatility (24h)</div>
      <div class="hmm-risk-metric-val {sigma_cls}">{rm["sigma"]:.1f}%</div>
      <div class="hmm-risk-metric-sub">
        Gate threshold: 8%<br>
        {'<span class="sig">✓ Below gate — signal active</span>' if rm["sigma"] <= 8 else '<span class="gate">✗ Above gate — signal suppressed</span>'}
      </div>
    </div>
    <div class="hmm-risk-metric">
      <div class="hmm-risk-metric-lbl">Sharpe Ratio</div>
      <div class="hmm-risk-metric-val {sharpe_cls}">{rm["sharpe"]:.2f}</div>
      <div class="hmm-risk-metric-sub">
        (Avg hourly return / σ) × √8760<br>
        {'<span class="sig">Strong risk-adjusted return</span>' if rm["sharpe"] >= 1.5 else ('<span class="warn">Moderate return</span>' if rm["sharpe"] >= 0.5 else '<span class="gate">Weak return</span>')}
      </div>
    </div>
    <div class="hmm-risk-metric">
      <div class="hmm-risk-metric-lbl">t-statistic</div>
      <div class="hmm-risk-metric-val acc">{rm["t_stat"]:.2f}</div>
      <div class="hmm-risk-metric-sub">
        SR × √N = SR × √{rm["n"]}<br>
        {sig_text}
      </div>
    </div>
  </div>

  {gate_html}

  <div>
    <div class="hmm-ranking-head">Asset Ranking by Sharpe Ratio</div>
    <table class="hmm-ranking-table">
      <thead>
        <tr>
          <th>#</th><th>Asset</th><th>Sharpe</th><th>σ</th><th>Signal</th>
        </tr>
      </thead>
      <tbody>{''.join(rank_rows)}</tbody>
    </table>
  </div>
</div>
""", unsafe_allow_html=True)
```

---

## Task 6 — Strip Emoji from Tab Labels + Wire Live Tab (`app/dashboard.py`)

**Files:** Modify `app/dashboard.py:752-754` and `app/dashboard.py:760-797`

- [ ] Change tab labels:

```python
# FROM:
tab_dashboard, tab_backtest, tab_about = st.tabs(
    ["📊 Live", "📋 Backtest", "📖 About"]
)
# TO:
tab_dashboard, tab_backtest, tab_about = st.tabs(
    ["Live", "Backtest", "About"]
)
```

- [ ] In the Live tab section, add `render_risk_panel()` call after `render_hero_banner()`, and update the chart call to pass full `df_sel` instead of `df_sel.iloc[-chart_bars:]`:

```python
with tab_dashboard:

    if selected_ticker in all_data:
        res    = all_data[selected_ticker]
        df_sel = res["df"]
        latest = df_sel.iloc[-1]
        render_hero_banner(df_sel, selected_ticker, latest)
        render_risk_panel(df_sel, all_data, selected_ticker)   # NEW

    _section_label("Market Overview")
    render_ticker_cards(all_data)
    render_sentiment_strip(all_data)

    if selected_ticker in all_data:
        res    = all_data[selected_ticker]
        df_sel = res["df"]
        latest = df_sel.iloc[-1]
        _section_label("Price Chart")
        chart = build_candlestick(df_sel, selected_ticker)     # full df — no slice
        label = TICKER_LABELS.get(selected_ticker, selected_ticker)
        st.markdown(f"""
<div class="hmm-chart-card">
  <div class="hmm-chart-head">
    <div class="hmm-chart-title">{label}/USD — Hourly Chart with Regime Overlay</div>
    <div class="hmm-chart-badges">
      <span class="hmm-badge hmm-badge-buy">▲ BUY</span>
      <span class="hmm-badge hmm-badge-sell">▼ SELL</span>
      <span class="hmm-badge hmm-badge-ema20">EMA 20</span>
      <span class="hmm-badge hmm-badge-ema200">EMA 200</span>
      <span class="hmm-badge hmm-badge-vol">Volume</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        st.plotly_chart(chart, use_container_width=True, key="main_chart")
        render_conf_panel(latest)

    _section_label("Backtest Snapshot")
    try:
        equity_curve, bh_curve, trades_df, metrics = load_backtest(
            selected_ticker, period, n_states
        )
        render_metrics_snapshot(metrics, selected_ticker)
    except Exception as e:
        st.error(f"Backtest error: {e}")
```

- [ ] Commit everything: `git commit -m "feat(dashboard): Risk Panel, BUY/SELL markers, 90-day range, rangeslider, SR ranking, t-stat, clean tab labels"`

---

## Task 7 — Smoke Test

- [ ] Run the app: `streamlit run app/dashboard.py`
- [ ] Verify: sidebar visible + collapse/expand chevron works
- [ ] Verify: Live tab shows "Live" (no emoji) in the tab
- [ ] Verify: Risk Panel appears below Hero Banner with σ, Sharpe, t-stat, ranking
- [ ] Verify: ADA shows "🔴 Gated" when σ > 8% (or test by temporarily lowering threshold to 2% in signals.py)
- [ ] Verify: Chart defaults to last 90 days, rangeslider at bottom, BUY/SELL triangles visible
- [ ] Verify: Hover on BUY marker shows entry price + 5 exit targets + stop loss
