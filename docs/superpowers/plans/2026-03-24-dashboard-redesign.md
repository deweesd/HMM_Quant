# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `app/dashboard.py` with a Fintech Pro aesthetic — indigo/violet accent, dark/light toggle, hero signal banner, regime-coloured ticker cards, and a 3-tab layout (Live / Backtest / About) — using CSS overrides on Streamlit's native widgets.

**Architecture:** All visual changes are CSS/HTML injected via a single `st.markdown` block immediately after `st.set_page_config`. Streamlit's native `st.sidebar`, `st.tabs()`, `st.columns()`, and `st.metric()` are kept and restyled. No new Python modules are created. The dark/light toggle uses `body.hmm-light` class toggling — not Streamlit's own `data-theme` attribute.

**Tech Stack:** Python 3.9, Streamlit, Plotly, custom HTML/CSS/JS injected via `st.markdown`

**Reference mockup:** `mockups/dashboard-redesign.html` — authoritative for visual design; its theme-toggle JS (`html[data-theme]`) differs from the implementation which uses `body.hmm-light`.

**Design spec:** `docs/superpowers/specs/2026-03-24-dashboard-redesign-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/dashboard.py` | Modify | All visual changes live here |
| `app/css.py` | Create | CSS/JS string constant extracted from dashboard for readability |
| `tests/test_dashboard_helpers.py` | Create | Unit tests for the two testable Python changes (`build_candlestick` transparent bg, `style_summary` CSS vars) |

> `app/css.py` is a simple module containing one string constant `DASHBOARD_CSS`. Extracting it keeps `dashboard.py` readable and makes the CSS independently auditable. It has zero logic.

---

## Task 1: Create `app/css.py` with CSS token foundation and theme toggle

**Files:**
- Create: `app/css.py`

This task builds the full CSS string: design tokens, `body.hmm-light` overrides, and the `toggleHmmTheme()` JavaScript function. No Streamlit internals yet — just the token layer.

- [ ] **Step 1: Create `app/css.py` with the base CSS block**

```python
# app/css.py
"""
DASHBOARD_CSS — injected via st.markdown immediately after st.set_page_config.
Contains: design tokens, body.hmm-light overrides, toggleHmmTheme() JS.
All component and Streamlit-override CSS is appended in subsequent tasks.
"""

DASHBOARD_CSS = """
<style>
/* ── Design tokens: dark mode (default) ─────────────────────────── */
body {
  --bg0:         #07070d;
  --bg1:         #0e0e18;
  --bg2:         #141420;
  --bg3:         #1c1c2c;
  --border:      rgba(255,255,255,0.06);
  --border2:     rgba(255,255,255,0.11);
  --t1:          #eeeef5;
  --t2:          #9090aa;
  --t3:          #55556a;
  --accent:      #6366f1;
  --accent-lt:   #818cf8;
  --accent-glow: rgba(99,102,241,0.22);
  --bull:        #00c96a;
  --bull-bg:     rgba(0,201,106,0.08);
  --bear:        #ef4444;
  --bear-bg:     rgba(239,68,68,0.08);
  --neut:        #6b7280;
  --neut-bg:     rgba(107,114,128,0.07);
  --radius:      12px;
  --radius-sm:   8px;
  --shadow:      0 2px 8px rgba(0,0,0,0.5), 0 0 1px rgba(0,0,0,0.8);
  --transition:  all 0.22s ease;
}

/* ── Light mode overrides ────────────────────────────────────────── */
body.hmm-light {
  --bg0:         #f0f0f8;
  --bg1:         #e8e8f4;
  --bg2:         #ffffff;
  --bg3:         #f4f4fc;
  --border:      rgba(79,70,229,0.10);
  --border2:     rgba(79,70,229,0.20);
  --t1:          #111128;
  --t2:          #4a4a68;
  --t3:          #9090aa;
  --accent:      #4f46e5;
  --accent-lt:   #6366f1;
  --accent-glow: rgba(79,70,229,0.14);
  --bull:        #059669;
  --bull-bg:     rgba(5,150,105,0.08);
  --bear:        #dc2626;
  --bear-bg:     rgba(220,38,38,0.08);
  --shadow:      0 2px 8px rgba(79,70,229,0.08), 0 0 1px rgba(79,70,229,0.12);
}
</style>

<script>
function toggleHmmTheme() {
  document.body.classList.toggle('hmm-light');
  var btn = document.getElementById('hmmThemeBtn');
  if (btn) {
    btn.textContent = document.body.classList.contains('hmm-light') ? '\u2600\ufe0f' : '\ud83c\udf19';
  }
}
</script>
"""
```

- [ ] **Step 2: Verify Python syntax**

```bash
cd /Users/dmd/Desktop/HMM_Quant/HMM_Quant && .venv/bin/python -c "from app.css import DASHBOARD_CSS; print('OK', len(DASHBOARD_CSS), 'chars')"
```

Expected: `OK <number> chars` with no errors.

- [ ] **Step 3: Commit**

```bash
git add app/css.py
git commit -m "feat(dashboard): add CSS token foundation and theme toggle JS"
```

---

## Task 2: Streamlit internal CSS overrides

**Files:**
- Modify: `app/css.py` — append Streamlit selector overrides to `DASHBOARD_CSS`

These overrides restyle Streamlit's native widgets to match the design tokens without replacing them.

- [ ] **Step 1: Append Streamlit overrides to the `<style>` block in `app/css.py`**

Add the following inside the `<style>` tag in `DASHBOARD_CSS`, after the token blocks:

```css
/* ── Streamlit internals ─────────────────────────────────────────── */

/* Hide native header; custom topbar is rendered via st.markdown */
[data-testid="stHeader"] { display: none !important; }

/* Main content area */
.block-container {
  padding: 1rem 1.5rem 2rem !important;
  max-width: 100% !important;
}
section[data-testid="stMain"] {
  background: var(--bg0);
  overflow-x: hidden;
}

/* Tighten vertical spacing between stacked elements */
.stVerticalBlock { gap: 0.6rem !important; }
.element-container { margin-bottom: 0 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--bg1) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebarContent"] { padding: 1.25rem 1rem !important; }

/* Sidebar widget labels */
[data-testid="stSidebar"] label {
  font-size: 10.5px !important;
  font-weight: 600 !important;
  letter-spacing: 0.07em !important;
  text-transform: uppercase !important;
  color: var(--t3) !important;
}

/* Selectbox and slider inputs in sidebar */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] .stSlider {
  background: var(--bg2) !important;
  border-color: var(--border2) !important;
  border-radius: var(--radius-sm) !important;
}

/* Tabs: pill style */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: transparent !important;
  gap: 4px !important;
  border-bottom: 1px solid var(--border) !important;
  padding-bottom: 0 !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: 20px 20px 0 0 !important;
  color: var(--t2) !important;
  font-size: 13.5px !important;
  font-weight: 500 !important;
  padding: 8px 20px !important;
  transition: var(--transition) !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background: var(--accent-glow) !important;
  color: var(--accent-lt) !important;
  font-weight: 600 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"]    { display: none !important; }

/* st.metric */
[data-testid="stMetric"] {
  background: var(--bg2) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 12px 14px !important;
}
[data-testid="stMetricLabel"] {
  font-size: 10.5px !important;
  font-weight: 600 !important;
  letter-spacing: 0.07em !important;
  text-transform: uppercase !important;
  color: var(--t3) !important;
}
[data-testid="stMetricValue"] {
  font-size: 22px !important;
  font-weight: 700 !important;
  color: var(--t1) !important;
}
[data-testid="stMetricDelta"] { font-size: 11.5px !important; }

/* Remove dividers (they are deleted from code, but guard any that remain) */
hr { display: none !important; }
```

- [ ] **Step 2: Verify import still works**

```bash
.venv/bin/python -c "from app.css import DASHBOARD_CSS; assert 'stHeader' in DASHBOARD_CSS; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/css.py
git commit -m "feat(dashboard): add Streamlit internal CSS overrides"
```

---

## Task 3: Custom topbar and inject CSS into dashboard

**Files:**
- Modify: `app/dashboard.py` — inject CSS, add topbar, remove `st.divider()` calls

- [ ] **Step 1: Add the import at the top of `dashboard.py` with the other imports**

In the existing import block (lines 17–33), add:
```python
from app.css import DASHBOARD_CSS
```

Then find the existing CSS `st.markdown` block (lines 47–62):
```python
st.markdown("""<style> ... </style>""", unsafe_allow_html=True)
```

Replace **only that `st.markdown` call** (not the import) with:
```python
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
```

This call stays immediately after `st.set_page_config(...)`. The import goes at the top of the file with all other imports.

- [ ] **Step 2: Add custom topbar immediately after the CSS injection**

```python
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
```

- [ ] **Step 3: Remove all `st.divider()` calls from `dashboard.py`**

First confirm the exact count and lines:
```bash
grep -n "st.divider()" app/dashboard.py
```

Delete every found line (there are approximately 7 — the grep output is authoritative, not any hardcoded number).

- [ ] **Step 4: Smoke test — app launches without error**

```bash
.venv/bin/python -c "
import ast, sys
with open('app/dashboard.py') as f:
    src = f.read()
ast.parse(src)
print('Syntax OK')
"
```

Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): inject CSS, add topbar, remove dividers"
```

---

## Task 4: Hero Signal Banner

**Files:**
- Modify: `app/dashboard.py` — replace the Signal & Regime row with the hero banner
- Modify: `app/css.py` — add hero component CSS

- [ ] **Step 1: Add hero CSS to `app/css.py`**

Append inside the `<style>` block:

```css
/* ── Hero Signal Banner ──────────────────────────────────────────── */
.hmm-hero {
  border-radius: var(--radius);
  border: 1px solid var(--border2);
  background: linear-gradient(135deg, var(--bg2) 0%, var(--bg3) 100%);
  padding: 22px 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow);
  margin-bottom: 4px;
}
.hmm-hero::before {
  content: '';
  position: absolute;
  top: -40px; left: -40px;
  width: 200px; height: 200px;
  background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
  pointer-events: none;
}
.hmm-hero-ticker {
  font-size: 12px; font-weight: 600; letter-spacing: 0.05em;
  text-transform: uppercase; color: var(--t2); margin-bottom: 8px;
}
.hmm-signal-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 22px; border-radius: 40px;
  font-size: 22px; font-weight: 800; letter-spacing: 0.04em;
}
.hmm-signal-pill.long {
  background: var(--bull-bg); color: var(--bull);
  border: 1.5px solid rgba(0,201,106,0.3);
  box-shadow: 0 0 28px rgba(0,201,106,0.15);
}
.hmm-signal-pill.short {
  background: var(--bear-bg); color: var(--bear);
  border: 1.5px solid rgba(239,68,68,0.3);
  box-shadow: 0 0 28px rgba(239,68,68,0.15);
}
.hmm-signal-pill.neutral {
  background: var(--neut-bg); color: var(--neut);
  border: 1.5px solid rgba(107,114,128,0.3);
}
.hmm-pulse { width:9px; height:9px; border-radius:50%; animation: hmm-pulse 2s ease-in-out infinite; }
.hmm-signal-pill.long  .hmm-pulse { background: var(--bull); }
.hmm-signal-pill.short .hmm-pulse { background: var(--bear); }
.hmm-signal-pill.neutral .hmm-pulse { background: var(--neut); }
@keyframes hmm-pulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:0.45; transform:scale(0.8); }
}
.hmm-regime-badge {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:20px;
  font-size:13px; font-weight:600;
}
.hmm-regime-badge.bull { background:var(--bull-bg); color:var(--bull); border:1px solid rgba(0,201,106,0.2); }
.hmm-regime-badge.bear { background:var(--bear-bg); color:var(--bear); border:1px solid rgba(239,68,68,0.2); }
.hmm-regime-badge.neut { background:var(--neut-bg); color:var(--neut); border:1px solid rgba(107,114,128,0.2); }
.hmm-conf-pips { display:flex; gap:4px; align-items:center; margin-top:5px; }
.hmm-pip {
  width:13px; height:5px; border-radius:3px;
  background:var(--bg3); border:1px solid var(--border2);
}
.hmm-pip.filled { background:var(--bull); border-color:var(--bull); }
.hmm-hero-stats { display:flex; gap:24px; align-items:flex-start; flex-shrink:0; }
.hmm-hero-stat { display:flex; flex-direction:column; align-items:center; gap:4px; }
.hmm-stat-label {
  font-size:10px; font-weight:600; letter-spacing:0.07em;
  text-transform:uppercase; color:var(--t3);
}
.hmm-stat-val { font-size:22px; font-weight:700; color:var(--t1); line-height:1; }
.hmm-stat-val.pos { color:var(--bull); }
.hmm-stat-val.neg { color:var(--bear); }
.hmm-stat-val.acc { color:var(--accent-lt); }
```

- [ ] **Step 2: Add a `render_hero_banner()` helper function in `dashboard.py`**

Add after the existing helper functions (after `style_summary`, before the `# MAIN APP` section):

```python
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
```

- [ ] **Step 3: In `tab_dashboard`, replace the current Signal & Regime row block with a `render_hero_banner()` call**

Find the block starting with:
```python
st.subheader(f"Signal & Regime — {TICKER_LABELS[selected_ticker]}/USD")
```
and ending at the `st.divider()` after the expander. Replace the entire block with:

```python
if selected_ticker in all_data:
    res    = all_data[selected_ticker]
    df_sel = res["df"]
    latest = df_sel.iloc[-1]
    render_hero_banner(df_sel, selected_ticker, latest)
```

- [ ] **Step 4: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): add hero signal banner component"
```

---

## Task 5: Regime-coloured ticker cards

**Files:**
- Modify: `app/dashboard.py` — replace the `st.metric` ticker card loop
- Modify: `app/css.py` — add ticker card CSS

- [ ] **Step 1: Add ticker card CSS to `app/css.py`**

```css
/* ── Ticker Cards ────────────────────────────────────────────────── */
.hmm-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:4px 0; }
.hmm-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 14px 12px;
  position: relative; overflow: hidden;
  box-shadow: var(--shadow);
  transition: var(--transition);
  cursor: default;
}
.hmm-card:hover { border-color:var(--border2); transform:translateY(-1px); }
/* Left accent bar via pseudo-element */
.hmm-card::before {
  content:''; position:absolute;
  top:0; left:0; width:4px; height:100%;
  border-radius:var(--radius) 0 0 var(--radius);
}
.hmm-card.bull::before { background:var(--bull); }
.hmm-card.bear::before { background:var(--bear); }
.hmm-card.neut::before { background:var(--neut); }
.hmm-card.bull { background: linear-gradient(135deg, var(--bull-bg) 0%, var(--bg2) 45%); }
.hmm-card.bear { background: linear-gradient(135deg, var(--bear-bg) 0%, var(--bg2) 45%); }
.hmm-card-name  { font-size:14px; font-weight:700; color:var(--t1); }
.hmm-card-tick  { font-size:11px; color:var(--t3); margin-top:1px; }
.hmm-card-price { font-size:19px; font-weight:700; color:var(--t1); margin:8px 0 2px; }
.hmm-card-delta { font-size:12px; font-weight:600; }
.hmm-card-delta.pos { color:var(--bull); }
.hmm-card-delta.neg { color:var(--bear); }
.hmm-card-stats { display:flex; gap:14px; margin-top:8px; }
.hmm-card-stat-label { font-size:10px; color:var(--t3); text-transform:uppercase; letter-spacing:.06em; }
.hmm-card-stat-val   { font-size:12px; font-weight:600; color:var(--t2); }
.hmm-regime-pill {
  font-size:11px; font-weight:600; padding:3px 8px; border-radius:10px;
}
.hmm-regime-pill.bull { background:var(--bull-bg); color:var(--bull); }
.hmm-regime-pill.bear { background:var(--bear-bg); color:var(--bear); }
.hmm-regime-pill.neut { background:var(--neut-bg); color:var(--neut); }
```

- [ ] **Step 2: Add `render_ticker_cards()` helper in `dashboard.py`**

```python
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
```

- [ ] **Step 3: Replace the existing ticker cards loop in `tab_dashboard`**

Find the block from `st.subheader("Market Overview")` through the loop that calls `st.plotly_chart(spark_fig, ...)`. Replace with:

```python
st.markdown('<div style="font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--t3);margin-bottom:2px;">Market Overview</div>', unsafe_allow_html=True)
render_ticker_cards(all_data)
```

> **Note on `make_sparkline`:** Sparklines are dropped entirely in this redesign — `render_ticker_cards` does not include them. Do not attempt to add inline SVG sparklines; that is outside scope. `make_sparkline()` will be deleted in Task 14.

- [ ] **Step 4: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): add regime-coloured ticker cards"
```

---

## Task 6: Market Sentiment Strip (replace Plotly gauge)

**Files:**
- Modify: `app/dashboard.py` — replace `go.Indicator` gauge with HTML strip
- Modify: `app/css.py` — add sentiment strip CSS

- [ ] **Step 1: Add sentiment strip CSS to `app/css.py`**

```css
/* ── Sentiment Strip ─────────────────────────────────────────────── */
.hmm-sent-strip {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); padding:14px 20px;
  display:flex; align-items:center; gap:18px;
  box-shadow:var(--shadow);
}
.hmm-sent-label { font-size:12px; font-weight:600; color:var(--t3);
                  text-transform:uppercase; letter-spacing:.07em; white-space:nowrap; }
.hmm-gauge-wrap { flex:1; display:flex; flex-direction:column; gap:5px; }
.hmm-gauge-track {
  height:7px; border-radius:4px;
  background: linear-gradient(90deg, var(--bear) 0%, var(--neut) 50%, var(--bull) 100%);
  opacity:0.35; position:relative;
}
.hmm-gauge-needle {
  position:absolute; top:-4px; transform:translateX(-50%);
  width:3px; height:15px; border-radius:2px;
  background:var(--t1); opacity:0.9;
}
.hmm-gauge-ticks { display:flex; justify-content:space-between;
                   font-size:10.5px; color:var(--t3); }
.hmm-sent-val { font-size:18px; font-weight:700; white-space:nowrap; }
.hmm-sent-pills { display:flex; gap:7px; flex-shrink:0; flex-wrap:wrap; }
.hmm-sent-pill { display:flex; align-items:center; gap:4px;
                 padding:4px 10px; border-radius:12px; font-size:11.5px; font-weight:600; }
.hmm-sent-pill.bull { background:var(--bull-bg); color:var(--bull); }
.hmm-sent-pill.neut { background:var(--neut-bg); color:var(--neut); }
.hmm-sent-pill.bear { background:var(--bear-bg); color:var(--bear); }
```

- [ ] **Step 2: Add `render_sentiment_strip()` helper in `dashboard.py`**

```python
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
```

- [ ] **Step 3: Replace the gauge block in `tab_dashboard`**

Find the block from `regime_scores = []` through `st.caption(f"Based on HMM regime...")`. Replace with:

```python
render_sentiment_strip(all_data)
```

Remove the `gauge_fig`, `gauge_value`, `g_left/g_mid/g_right` columns, and `st.caption` for the gauge — all replaced by the strip.

- [ ] **Step 4: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): replace Plotly gauge with CSS sentiment strip"
```

---

## Task 7: Confirmation Detail Panel

**Files:**
- Modify: `app/dashboard.py` — replace `st.expander` with inline collapsible panel
- Modify: `app/css.py` — add confirmation panel CSS

- [ ] **Step 1: Add confirmation panel CSS to `app/css.py`**

```css
/* ── Confirmation Panel ──────────────────────────────────────────── */
.hmm-conf-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow);
}
.hmm-conf-header {
  padding:12px 16px; border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
  cursor:pointer; user-select:none;
}
.hmm-conf-header:hover { background:var(--bg3); }
.hmm-conf-title { font-size:13px; font-weight:600; color:var(--t2); }
.hmm-conf-count { font-size:12px; color:var(--t3); }
.hmm-conf-body {
  padding:12px 16px;
  display:grid; grid-template-columns:1fr 1fr; gap:7px 20px;
}
.hmm-conf-body.collapsed { display:none; }
.hmm-conf-item { display:flex; align-items:center; gap:9px; font-size:12.5px; color:var(--t2); }
.hmm-conf-icon {
  width:18px; height:18px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:10px; flex-shrink:0; font-weight:700;
}
.hmm-conf-icon.pass { background:var(--bull-bg); color:var(--bull); }
.hmm-conf-icon.fail { background:var(--bear-bg); color:var(--bear); }
```

- [ ] **Step 2: Add `render_conf_panel()` helper in `dashboard.py`**

```python
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
```

- [ ] **Step 3: Replace the `st.expander` block in `tab_dashboard`**

Find:
```python
with st.expander("🔍 Confirmation Detail (current bar)", expanded=False):
    chk_cols = st.columns(2)
    for i, col_name in enumerate(CONFIRM_COLS):
        ...
```

Replace with (inside the `if selected_ticker in all_data:` block, after the chart):

```python
render_conf_panel(latest)
```

- [ ] **Step 4: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): add collapsible confirmation detail panel"
```

---

## Task 8: Backtest Metrics Snapshot (6-cell grid)

**Files:**
- Modify: `app/dashboard.py` — replace `st.metric` rows with HTML grid
- Modify: `app/css.py` — add metrics grid CSS

- [ ] **Step 1: Add metrics grid CSS to `app/css.py`**

```css
/* ── Backtest Metrics Grid ───────────────────────────────────────── */
.hmm-metrics-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow);
}
.hmm-metrics-head {
  padding:12px 16px; border-bottom:1px solid var(--border);
  display:flex; justify-content:space-between; align-items:center;
}
.hmm-metrics-title { font-size:13.5px; font-weight:600; color:var(--t1); }
.hmm-metrics-sub   { font-size:11.5px; color:var(--t3); }
.hmm-metrics-grid  {
  display:grid; grid-template-columns:repeat(6,1fr);
  gap:1px; background:var(--border);
}
.hmm-metric-cell {
  background:var(--bg2); padding:12px 14px;
  display:flex; flex-direction:column; gap:4px;
  transition:var(--transition);
}
.hmm-metric-cell:hover { background:var(--bg3); }
.hmm-metric-lbl {
  font-size:10px; font-weight:600; letter-spacing:.07em;
  text-transform:uppercase; color:var(--t3);
}
.hmm-metric-val { font-size:21px; font-weight:700; line-height:1; color:var(--t1); }
.hmm-metric-val.pos { color:var(--bull); }
.hmm-metric-val.neg { color:var(--bear); }
.hmm-metric-val.acc { color:var(--accent-lt); }
.hmm-metric-ctx { font-size:11px; color:var(--t3); }
.hmm-metric-ctx.pos { color:var(--bull); }
.hmm-metric-ctx.neg { color:var(--bear); }
```

- [ ] **Step 2: Add `render_metrics_snapshot()` helper in `dashboard.py`**

```python
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
```

- [ ] **Step 3: Replace the existing metrics block in `tab_dashboard`**

Find the block from `st.subheader(f"Backtest Metrics —...")` through `sub3.metric("Final Equity", ...)`. Replace with:

```python
st.markdown(f'<div style="font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--t3);margin-bottom:2px;">Backtest Snapshot</div>', unsafe_allow_html=True)
try:
    equity_curve, bh_curve, trades_df, metrics = load_backtest(
        selected_ticker, period, n_states
    )
    render_metrics_snapshot(metrics, selected_ticker)
except Exception as e:
    st.error(f"Backtest error: {e}")
```

- [ ] **Step 4: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): add 6-cell backtest metrics snapshot grid"
```

---

## Task 9: Make chart builders theme-aware (transparent backgrounds)

**Files:**
- Modify: `app/dashboard.py` — `build_candlestick` and `build_equity_chart`
- Create: `tests/test_dashboard_helpers.py`

This is the only task with unit-testable Python changes.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dashboard_helpers.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy  as np

def _make_df(n=50):
    idx   = pd.date_range("2025-01-01", periods=n, freq="h")
    close = np.random.uniform(95, 105, n)
    df    = pd.DataFrame({
        "Open":   close * np.random.uniform(0.995, 1.005, n),
        "High":   close * np.random.uniform(1.005, 1.015, n),  # always above close
        "Low":    close * np.random.uniform(0.985, 0.995, n),  # always below close
        "Close":  close,
        "Volume": np.random.randint(1000, 5000, n),
        "EMA20":  close * np.random.uniform(0.99, 1.01, n),
        "EMA200": close * np.random.uniform(0.97, 1.03, n),
        "Regime": np.random.choice(["Bull", "Bear", "Neutral"], n),
    }, index=idx)
    return df


def test_candlestick_transparent_background():
    """build_candlestick must use transparent chart backgrounds."""
    from app.dashboard import build_candlestick
    fig = build_candlestick(_make_df(), "BTC-USD")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)", \
        f"Expected transparent paper_bgcolor, got {fig.layout.paper_bgcolor}"
    assert fig.layout.plot_bgcolor  == "rgba(0,0,0,0)", \
        f"Expected transparent plot_bgcolor, got {fig.layout.plot_bgcolor}"


def test_equity_chart_transparent_background():
    """build_equity_chart must use transparent chart backgrounds."""
    from app.dashboard import build_equity_chart
    idx    = pd.date_range("2025-01-01", periods=50, freq="h")
    equity = pd.Series(np.linspace(20000, 28000, 50), index=idx)
    bh     = pd.Series(np.linspace(20000, 24000, 50), index=idx)
    fig    = build_equity_chart(equity, bh, "BTC-USD")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor  == "rgba(0,0,0,0)"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_dashboard_helpers.py -v 2>&1 | tail -20
```

Expected: both tests FAIL with assertion errors about `#0f1117`.

- [ ] **Step 3: Update `build_candlestick` in `dashboard.py`**

Find `paper_bgcolor = "#0f1117"` and `plot_bgcolor = "#0f1117"` inside `build_candlestick`. Change both to `"rgba(0,0,0,0)"`.

- [ ] **Step 4: Update `build_equity_chart` in `dashboard.py`**

Find `paper_bgcolor = "#0f1117"` and `plot_bgcolor = "#0f1117"` inside `build_equity_chart`. Change both to `"rgba(0,0,0,0)"`.

- [ ] **Step 5: Add chart card wrapper CSS to `app/css.py`**

```css
/* ── Chart Card Wrapper ──────────────────────────────────────────── */
.hmm-chart-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow);
}
.hmm-chart-head {
  padding:12px 16px; border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
}
.hmm-chart-title { font-size:13.5px; font-weight:600; color:var(--t1); }
.hmm-chart-badges { display:flex; gap:7px; }
.hmm-badge {
  font-size:11px; padding:3px 8px; border-radius:6px;
  font-weight:500;
}
.hmm-badge-ema20  { background:rgba(245,166,35,.12); color:#f5a623; }
.hmm-badge-ema200 { background:rgba(123,104,238,.12); color:#7b68ee; }
.hmm-badge-vol    { background:var(--bg3); color:var(--t3); }
.hmm-badge-strat  { background:rgba(0,201,106,.12); color:var(--bull); }
.hmm-badge-bh     { background:rgba(123,104,238,.12); color:#7b68ee; }
```

In `tab_dashboard`, wrap the `st.plotly_chart(chart, ...)` call with a chart card header:

```python
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
```

Do the same for the equity chart in `tab_backtest`:
```python
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
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_dashboard_helpers.py -v
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/dashboard.py app/css.py tests/test_dashboard_helpers.py
git commit -m "feat(dashboard): transparent chart backgrounds, add chart card wrappers"
```

---

## Task 10: Restructure Live tab layout and section headers

**Files:**
- Modify: `app/dashboard.py` — reorder Live tab sections, add section label helper

This task assembles the final Live tab order: Hero → Cards → Sentiment → Chart → Conf Panel → Metrics.

- [ ] **Step 1: Add section label helper**

Add near the top of the `# MAIN APP` section:

```python
def _section_label(text: str) -> None:
    st.markdown(
        f'<div style="font-size:12px;font-weight:600;letter-spacing:.07em;'
        f'text-transform:uppercase;color:var(--t3);margin:4px 0 -4px;">{text}</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: Reorder `tab_dashboard` to match spec order**

The `with tab_dashboard:` block should read in this order:

```
1. Load all tickers (existing spinner block)
2. render_hero_banner()               ← hero first
3. _section_label("Market Overview")
4. render_ticker_cards()
5. render_sentiment_strip()
6. _section_label("Price Chart")
7. chart card header + st.plotly_chart (main chart)
8. render_conf_panel()
9. _section_label("Backtest Snapshot")
10. render_metrics_snapshot()
```

Remove the old `st.subheader()` calls for "Market Overview", "Signal & Regime", "Price Chart", "Backtest Metrics" — replaced by `_section_label`.

- [ ] **Step 3: Syntax + smoke test**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: syntax OK, all tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/dashboard.py
git commit -m "feat(dashboard): assemble final Live tab layout order"
```

---

## Task 11: Restructure Backtest tab

**Files:**
- Modify: `app/dashboard.py` — restyle `tab_backtest`, add trade log card header

- [ ] **Step 1: Add trade log card CSS to `app/css.py`**

```css
/* ── Trade Log Card ──────────────────────────────────────────────── */
.hmm-tradelog-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow);
}
.hmm-tradelog-head {
  padding:11px 16px; border-bottom:1px solid var(--border);
  display:flex; justify-content:space-between; align-items:center;
}
.hmm-tradelog-title { font-size:13.5px; font-weight:600; color:var(--t1); }
.hmm-tradelog-meta  { font-size:11.5px; color:var(--t3); }
```

- [ ] **Step 2: Update `tab_backtest` block**

```python
with tab_backtest:
    label = TICKER_LABELS.get(selected_ticker, selected_ticker)
    try:
        equity_curve, bh_curve, trades_df, metrics = load_backtest(
            selected_ticker, period, n_states
        )
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
```

- [ ] **Step 3: Syntax check**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): restyle Backtest tab with card wrappers"
```

---

## Task 12: Restructure About tab and relocate Regime Summary

**Files:**
- Modify: `app/dashboard.py` — rewrite `tab_readme` → `tab_about`
- Modify: `app/css.py` — add about tab CSS
- Modify: `app/dashboard.py` — update `style_summary()` to use CSS variables

- [ ] **Step 1: Update `style_summary()` to use CSS variables**

Find `style_summary()` (around line 402). Replace hardcoded hex colours:

```python
# Before
base = "background-color:#1a1a2e; color:#e0e0e0;"

# After
base = "background-color:var(--bg2, #1a1a2e); color:var(--t1, #e0e0e0);"
```

- [ ] **Step 2: Add about tab CSS to `app/css.py`**

```css
/* ── About Tab ───────────────────────────────────────────────────── */
.hmm-about-grid { display:grid; grid-template-columns:2fr 1fr; gap:18px; }
.hmm-about-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow);
}
.hmm-about-card h3 {
  font-size:14px; font-weight:700; color:var(--t1);
  padding-bottom:10px; border-bottom:1px solid var(--border); margin-bottom:12px;
}
.hmm-about-card p, .hmm-about-card li {
  font-size:13px; color:var(--t2); line-height:1.65;
}
.hmm-about-card ul { padding-left:16px; display:flex; flex-direction:column; gap:4px; }
.hmm-stat-row {
  display:flex; justify-content:space-between; align-items:center;
  padding:8px 0; border-bottom:1px solid var(--border); font-size:13px;
}
.hmm-stat-row:last-child { border-bottom:none; }
.hmm-stat-key { color:var(--t3); font-weight:500; }
.hmm-stat-val { color:var(--t1); font-weight:600; }
.hmm-disclaimer {
  background:var(--bear-bg); border:1px solid rgba(239,68,68,.15);
  border-radius:var(--radius-sm); padding:11px 14px;
  font-size:12px; color:var(--t2); line-height:1.6;
}
```

- [ ] **Step 3: Rewrite the `tab_readme` block as `tab_about`**

Rename `tab_readme` to `tab_about` in both the `st.tabs()` call and the `with` block. The tab label changes from `"📖 README"` to `"📖 About"`.

Replace the entire `with tab_readme:` content with:

```python
with tab_about:
    # Left column content
    left_html = """
<div class="hmm-about-card" style="margin-bottom:18px;">
  <h3>What This App Does</h3>
  <p>Uses a <strong>Hidden Markov Model (HMM)</strong> to detect the current market regime
  (Bull, Bear, or Neutral) for BTC, ETH, SOL, and ADA. When the HMM identifies a
  <strong>Bull regime</strong> and at least <strong>8 of 10</strong> technical confirmations
  are met, the app generates a <strong>LONG</strong> signal.</p>
</div>
<div class="hmm-about-card" style="margin-bottom:18px;">
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
<div class="hmm-about-card" style="margin-bottom:18px;">
  <h3>Model Parameters</h3>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Model</span><span class="hmm-stat-val">GaussianHMM</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Covariance</span><span class="hmm-stat-val">Full</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Iterations</span><span class="hmm-stat-val">1,000</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Scaler</span><span class="hmm-stat-val">StandardScaler</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Features</span><span class="hmm-stat-val">Returns, Range, Vol Δ</span></div>
</div>
<div class="hmm-about-card" style="margin-bottom:18px;">
  <h3>Risk Management</h3>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Leverage</span><span class="hmm-stat-val">1.5×</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Start Capital</span><span class="hmm-stat-val">$20,000</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Cooldown</span><span class="hmm-stat-val">72 hrs post-exit</span></div>
  <div class="hmm-stat-row"><span class="hmm-stat-key">Exit Trigger</span><span class="hmm-stat-val">Bear regime flip</span></div>
</div>
<div class="hmm-disclaimer">
  ⚠️ <strong>Not financial advice.</strong> Educational use only.
  Past performance does not guarantee future results.
</div>
"""
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.markdown(left_html, unsafe_allow_html=True)
    with col_right:
        st.markdown(right_html, unsafe_allow_html=True)

    # Regime State Summary (relocated from Live tab)
    st.markdown(
        '<div style="font-size:12px;font-weight:600;letter-spacing:.07em;'
        'text-transform:uppercase;color:var(--t3);margin:12px 0 4px;">'
        'Regime State Profiles</div>',
        unsafe_allow_html=True
    )
    # all_data is populated in tab_dashboard above; tabs execute in order so it is in scope here
    if selected_ticker in all_data:
        res = all_data[selected_ticker]
        st.dataframe(
            style_summary(res["state_summary"]),
            use_container_width=True,
            hide_index=True,
        )
```

- [ ] **Step 4: Update the `st.tabs()` call**

```python
tab_dashboard, tab_backtest, tab_about = st.tabs(
    ["📊 Live", "📋 Backtest", "📖 About"]
)
```

- [ ] **Step 5: Syntax check + tests**

```bash
.venv/bin/python -c "import ast; ast.parse(open('app/dashboard.py').read()); print('OK')"
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -15
```

- [ ] **Step 6: Commit**

```bash
git add app/dashboard.py app/css.py
git commit -m "feat(dashboard): restructure About tab, relocate Regime Summary"
```

---

## Task 13: Responsive CSS

**Files:**
- Modify: `app/css.py` — append responsive `@media` rules

- [ ] **Step 1: Append responsive CSS to `app/css.py`**

```css
/* ── Responsive ──────────────────────────────────────────────────── */
html, body { overflow-x: hidden; max-width: 100vw; }
section[data-testid="stMain"] { overflow-x: hidden; }
.block-container { overflow-x: hidden; }

/* Tablet ≤ 900px */
@media (max-width: 900px) {
  .hmm-cards        { grid-template-columns: repeat(2,1fr) !important; }
  .hmm-metrics-grid { grid-template-columns: repeat(3,1fr) !important; }
  .hmm-about-grid   { grid-template-columns: 1fr !important; }
  .hmm-hero         { flex-direction: column !important; gap: 14px !important; }
  .hmm-hero-stats   { flex-wrap: wrap !important; gap: 14px !important; }
}

/* Mobile ≤ 600px */
@media (max-width: 600px) {
  .hmm-cards        { grid-template-columns: repeat(2,1fr) !important; gap:10px !important; }
  .hmm-metrics-grid { grid-template-columns: repeat(2,1fr) !important; }
  .hmm-hero         { padding: 14px !important; }
  .hmm-hero-stats   { flex-wrap: wrap !important; width: 100% !important; }
  .hmm-signal-pill  { font-size: 18px !important; padding: 8px 16px !important; }
  .hmm-conf-body    { grid-template-columns: 1fr !important; }
  .hmm-about-grid   { grid-template-columns: 1fr !important; }
  .block-container  { padding: 0.75rem 0.75rem 2rem !important; }
}

/* Very small ≤ 380px */
@media (max-width: 380px) {
  .hmm-cards { grid-template-columns: 1fr !important; }
}
```

- [ ] **Step 2: Verify CSS renders without browser errors**

Open the app in Chrome DevTools → Console. No CSS parse errors should appear.

- [ ] **Step 3: Test mobile breakpoint**

In Chrome DevTools, switch to iPhone 14 (390px wide). Verify:
- Cards show 2 per row
- Hero banner stacks vertically
- No horizontal scrollbar visible

- [ ] **Step 4: Commit**

```bash
git add app/css.py
git commit -m "feat(dashboard): add responsive CSS for tablet and mobile"
```

---

## Task 14: Full integration test and cleanup

**Files:**
- Modify: `app/dashboard.py` — remove any remaining dead code (`make_sparkline`, old signal/regime row refs)
- Run: full test suite + live smoke test

- [ ] **Step 1: Remove dead code from `dashboard.py`**

Delete `make_sparkline()` — sparklines were dropped in Task 5 (not replaced with SVG; they are simply removed from the design). Verify no callers remain before deleting:

```bash
grep -n "make_sparkline" app/dashboard.py
```

Expected: only the function definition line. Delete the full function.

- [ ] **Step 2: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests pass including `test_imports.py` and `test_dashboard_helpers.py`.

- [ ] **Step 3: Smoke test — launch app headlessly**

```bash
timeout 15 .venv/bin/streamlit run app/dashboard.py \
  --server.headless true \
  --server.port 8502 2>&1 | head -20
```

Expected output contains `You can now view your Streamlit app in your browser` with no Python tracebacks.

- [ ] **Step 4: Visual check — launch app and compare against mockup**

```bash
.venv/bin/streamlit run app/dashboard.py
```

Open `mockups/dashboard-redesign.html` alongside. Verify:
- [ ] Dark mode matches mockup colour palette
- [ ] Light mode toggle works (🌙/☀️ button)
- [ ] Hero signal banner is the first visible element on Live tab
- [ ] 4 ticker cards show with correct regime colour bars
- [ ] Sentiment strip is compact horizontal bar (no large gauge)
- [ ] Chart card has header with EMA/Volume badges
- [ ] Confirmation panel is open by default and collapses on click
- [ ] 6-cell metrics grid is a single unified card
- [ ] Backtest tab has equity chart + trade log with card headers
- [ ] About tab has 2-column layout + Regime State Profiles table
- [ ] No horizontal scrolling at any window size
- [ ] No `st.divider()` visual lines anywhere

- [ ] **Step 5: Final commit**

```bash
git add app/dashboard.py app/css.py tests/test_dashboard_helpers.py
git commit -m "feat(dashboard): complete Fintech Pro redesign

- Hero signal banner replaces buried signal/regime row
- Regime-coloured ticker cards with left accent bar
- CSS sentiment strip replaces oversized Plotly gauge
- Collapsible confirmation panel (open by default)
- 6-cell backtest metrics grid
- Transparent Plotly chart backgrounds for light mode
- body.hmm-light dark/light toggle
- About tab with relocated Regime State Profiles
- Responsive layout: desktop 4-col, tablet 2-col, mobile 1-2 col

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
