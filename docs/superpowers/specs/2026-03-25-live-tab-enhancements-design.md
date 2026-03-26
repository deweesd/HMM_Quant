# Live Tab Enhancements — Design Spec
**Date:** 2026-03-25
**Status:** Approved
**Scope:** `app/dashboard.py`, `app/css.py`, `strategy/signals.py`, `strategy/backtest.py`

---

## 1. Goals

- Restore the Settings sidebar so it is always accessible (collapse/expand)
- Add BUY / SELL limit-order markers to the candlestick chart with hoverable price levels
- Default the chart to the last 90 days with a rangeslider for pan/zoom
- Introduce a dedicated Risk Panel (below Hero Banner) showing σ, Sharpe, SR ranking, and t-stat significance
- Gate the LONG signal when σ > 8% (volatility too high for reliable regime detection)
- Ensure the layout is fully responsive: no header/chart overlap on desktop or mobile

---

## 2. Architecture

```
app/dashboard.py   ← MOD — Risk Panel, chart markers, rangeslider, sidebar CSS fix
app/css.py         ← MOD — sidebar collapse control CSS, Risk Panel styles,
                            marker tooltip styles, rangeslider styles,
                            responsive breakpoints for mobile
strategy/signals.py ← MOD — σ gate: suppress LONG when Volatility > 8%
```

No changes to `pipeline/`, `models/`, or `strategy/backtest.py`.
All new σ and Sharpe computations read from columns already present on `df`
(`Volatility`, `Returns`) — no new pipeline steps required.

---

## 3. Item 1 — Settings Sidebar Fix

### Root Cause
`[data-testid="stHeader"]` is hidden via CSS (for the clean custom topbar). Streamlit's
native hamburger button for expanding a collapsed sidebar lives inside that header element.
Once the user collapses the sidebar, there is no visible control to re-expand it.

### Fix
Streamlit renders a `[data-testid="stSidebarCollapsedControl"]` element at the left edge of
the viewport when the sidebar is collapsed. This element is present in the DOM but may be
invisible or mispositioned when the header is hidden. Add the following to `app/css.py`:

```css
/* Ensure sidebar collapse/expand chevron is always reachable */
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  z-index: 999 !important;
  top: 60px !important;   /* clear the custom topbar height */
}
```

No changes to `dashboard.py` or the topbar layout.

---

## 4. Item 2 — BUY / SELL Markers on Candlestick Chart

### Signal Definitions
Derived from `df["Signal"]` and `df["Regime"]` columns already on the dataframe.

| Marker | Condition | Visual |
|--------|-----------|--------|
| BUY    | `Signal` transitions from non-`LONG` → `LONG` (first bar of a new LONG run) | Green ▲ at candle low − 0.5% |
| SELL   | `Regime` transitions to `Bear` while prior bar was in a LONG run | Red ▼ at candle high + 0.5% |

HOLD state is communicated by the existing Bull regime background shading — no additional
marker is needed.

### Hover Tooltip Content
Each marker shows on hover (via Plotly `customdata` + `hovertemplate`):

**BUY marker:**
```
🟢 BUY SIGNAL
Entry price: $X,XXX.XX
Exit targets:
  +15%  → $X,XXX  (sell 10%)
  +30%  → $X,XXX  (sell 15%)
  +45%  → $X,XXX  (sell 20%)
  +60%  → $X,XXX  (sell 30%)
  +100% → $X,XXX  (sell 50% remaining)
Stop loss: $X,XXX (-5% trailing)
```

**SELL marker:**
```
🔴 EXIT — Bear Regime
Exit price: $X,XXX.XX
```

### Implementation in `build_candlestick()`
Add two `go.Scatter` traces to row 1 after the EMA traces:

```python
# BUY markers
buy_mask  = (df_plot["Signal"] == "LONG") & (df_plot["Signal"].shift(1) != "LONG")
# SELL markers
sell_mask = (df_plot["Regime"] == "Bear") & (df_plot["Regime"].shift(1) != "Bear") \
            & (df_plot["Signal"].shift(1) == "LONG")
```

Marker sizes: 10px. Z-order: above candlesticks (add traces after candlestick trace).
Do not show markers in the legend (set `showlegend=False` on marker traces, add them to
the regime annotation row at top of chart instead).

---

## 5. Item 3 — Chart Default Range + Rangeslider

### Default View
Set `xaxis.range` on layout to the last 90 calendar days of available data:

```python
range_end   = df_plot.index[-1]
range_start = range_end - pd.Timedelta(days=90)
fig.update_layout(xaxis=dict(range=[range_start, range_end]))
```

All data is still loaded into the chart; the user can drag the rangeslider left to see
older history.

### Rangeslider
Re-enable Plotly's x-axis rangeslider (currently disabled):

```python
xaxis_rangeslider_visible = True
xaxis_rangeslider_thickness = 0.04   # thin bar at bottom
```

Style overrides in `css.py` to match the dark theme:
```css
.rangeslider-mask { fill: rgba(255,255,255,0.04) !important; }
.rangeslider-grabber-min, .rangeslider-grabber-max {
  fill: var(--accent) !important;
}
```

Remove the `chart_bars` slider from the sidebar — it is superseded by the rangeslider.

---

## 6. Item 4 — Volatility σ Gate

### Formula
The existing `Volatility` column in `df` (computed in `pipeline/indicators.py`):

```
σ = rolling_24bar_std(Returns) × √24 × 100   (percentage)
```

This is the 24-hour realised volatility of hourly returns, annualised to a daily figure.

### Gate Logic — `strategy/signals.py`
Add one condition to `score_signals()`. After the existing `conditions` list:

```python
vol_gate = df_out["Volatility"] <= 8.0   # suppress LONG when σ > 8%

conditions = [
    (df_out["Regime"] == "Bull") & (df_out["Confirmations"] >= 8) & vol_gate,
    df_out["Regime"] == "Bear",
]
df_out["Signal"] = np.select(conditions, ["LONG", "SHORT"], default="NEUTRAL")
df_out["Vol_Gated"] = (~vol_gate) & (df_out["Regime"] == "Bull") \
                      & (df_out["Confirmations"] >= 8)
```

`Vol_Gated` (bool) is a new column: `True` when a LONG signal was suppressed by the
volatility gate. Used by the Risk Panel to show a "🔴 High Vol — Signal Gated" warning.

### Threshold
Default: 8%. This is stricter than the existing `C3_Vol_lt_6` confirmation check (6%).
The gate is a hard block on entry; C3 remains a soft confirmation within the 10-point
scoring system.

---

## 7. Item 5 + 6 + 7 — Risk Panel

### Position
Rendered in `tab_dashboard`, immediately after `render_hero_banner()` and before
`render_ticker_cards()`. Only rendered when `selected_ticker in all_data`.

### σ and Sharpe Computation (in `app/dashboard.py`)

```python
def compute_risk_metrics(df: pd.DataFrame) -> dict:
    """Compute σ, Sharpe, t-stat, and risk rating for the Risk Panel."""
    sigma   = float(df["Volatility"].iloc[-1])          # current bar σ (%)
    returns = df["Returns"].dropna()
    n       = len(returns)
    sharpe  = float(returns.mean() / returns.std() * np.sqrt(8760)) if returns.std() > 0 else 0.0
    t_stat  = sharpe * np.sqrt(n)
    sig     = t_stat > 1.96                             # p < 0.05, two-tailed

    if sigma <= 4 and sharpe >= 1.5:
        rating, rating_cls = "Low Risk", "bull"
    elif sigma <= 8 and sharpe >= 0.5:
        rating, rating_cls = "Moderate", "neut"
    else:
        rating, rating_cls = "High Risk", "bear"

    return dict(sigma=sigma, sharpe=sharpe, t_stat=t_stat,
                sig=sig, rating=rating, rating_cls=rating_cls, n=n)
```

### SR Asset Ranking (computed across all loaded tickers)

```python
def compute_sr_ranking(all_data: dict) -> list:
    """Return list of (ticker, sharpe, sigma, signal) dicts sorted by sharpe desc."""
    rows = []
    for t, res in all_data.items():
        d  = res["df"]
        rm = compute_risk_metrics(d)
        sig = str(d["Signal"].iloc[-1])
        gated = bool(d["Vol_Gated"].iloc[-1]) if "Vol_Gated" in d.columns else False
        rows.append(dict(ticker=t, label=TICKER_LABELS[t],
                         sharpe=rm["sharpe"], sigma=rm["sigma"],
                         signal=sig, gated=gated))
    return sorted(rows, key=lambda r: r["sharpe"], reverse=True)
```

### t-stat Annotation
Displayed below the Sharpe number:

> `t = SR × √N = 3.24`  ✓ returns differ from zero (p < 0.05)

If t < 1.96:

> `t = SR × √N = 1.12`  ⚠ insufficient evidence (p > 0.05)

### Risk Panel HTML Structure
New `render_risk_panel(df, all_data, selected_ticker)` function in `dashboard.py`:

```
┌─────────────────────────────────────────────────────────┐
│  RISK OVERVIEW                          ● Low Risk      │
│  σ (Volatility)   Sharpe Ratio   t-stat                 │
│  3.2%             2.31           t=3.24 ✓ p<0.05        │
│                                                         │
│  ASSET RANKING BY SHARPE                                │
│  #1 Bitcoin    SR 2.31  σ 3.2%  ● LONG                 │
│  #2 Ethereum   SR 1.87  σ 4.1%  ● LONG                 │
│  #3 Solana     SR 0.92  σ 6.8%  ● NEUTRAL              │
│  #4 Cardano    SR 0.44  σ 9.1%  🔴 Gated               │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Responsive Layout

### Desktop (> 768px)
- Sidebar: 260px fixed width, always visible
- Main content: fluid, max-width 100%
- Risk Panel: 3-column grid (σ | Sharpe | t-stat), ranking as 4-row table

### Mobile (≤ 768px)
- Sidebar: hidden by default (`initial_sidebar_state="collapsed"` via CSS override), accessible via `[data-testid="stSidebarCollapsedControl"]`
- Hero Banner: single column, stacked stats
- Risk Panel: 1-column stack (σ → Sharpe → t-stat → ranking)
- Chart: full width, height reduced to 400px
- Ticker Cards: 2-column grid (currently 4-column)
- No horizontal overflow: `overflow-x: hidden` on main container

### CSS additions to `app/css.py`
```css
@media (max-width: 768px) {
  .hmm-hero            { flex-direction: column !important; }
  .hmm-hero-stats      { flex-wrap: wrap !important; }
  .hmm-risk-metrics    { grid-template-columns: 1fr !important; }
  .hmm-cards           { grid-template-columns: 1fr 1fr !important; }
  .hmm-ranking-table   { font-size: 11px !important; }
}
```

---

## 9. Sidebar — Remove `chart_bars` Slider

The "Chart — bars to show" slider (currently `min=168, max=2000`) is removed from the
sidebar. It is superseded by the chart's rangeslider. The `chart_bars` variable is removed
from `build_candlestick()` call sites; the full `df_sel` is passed instead of `df_sel.iloc[-chart_bars:]`.

---

## 10. Files Changed

| File | Action | Key change |
|---|---|---|
| `app/css.py` | Modify | Sidebar collapsed control CSS, Risk Panel styles, rangeslider theme, mobile breakpoints |
| `app/dashboard.py` | Modify | Risk Panel render, `compute_risk_metrics`, `compute_sr_ranking`, chart markers, rangeslider, 90-day default range, remove `chart_bars` |
| `strategy/signals.py` | Modify | σ gate condition + `Vol_Gated` column |

---

## 11. Out of Scope

- Daily vs hourly Sharpe toggle (deferred — requires HMM refit on daily bars)
- Live order execution or brokerage API integration
- Persistent user position tracking across sessions
- Additional tickers beyond the current 4
