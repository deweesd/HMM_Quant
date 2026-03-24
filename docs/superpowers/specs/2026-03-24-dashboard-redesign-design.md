# Dashboard Redesign — Design Spec
**Date:** 2026-03-24
**Status:** Approved
**Scope:** `app/dashboard.py` — visual redesign. Chart builder functions (`build_candlestick`, `build_equity_chart`) receive minimal colour-only changes for light mode support. No changes to pipeline, models, or strategy logic.

---

## 1. Goals

- Replace the generic Streamlit default aesthetic with a polished Fintech Pro / Robinhood-inspired design
- Eliminate visual clutter: remove all `st.divider()` calls, compress whitespace via custom CSS
- Establish clear visual hierarchy so users immediately know whether to buy, hold, or sell
- Support dark mode (default) and light mode with a runtime toggle
- Be fully responsive: desktop, tablet (2-col), and mobile (1–2 col, vertical scroll only, no horizontal scroll)
- Lay groundwork for future traffic growth: signal prominence, performance headline above the fold

---

## 2. Visual Identity

| Token | Dark Mode | Light Mode |
|---|---|---|
| Background primary | `#07070d` | `#f0f0f8` |
| Background card | `#141420` | `#ffffff` |
| Accent (indigo) | `#6366f1` / `#818cf8` | `#4f46e5` / `#6366f1` |
| Bull green | `#00c96a` | `#059669` |
| Bear red | `#ef4444` | `#dc2626` |
| Neutral grey | `#6b7280` | `#6b7280` |
| Body font | system-ui / Inter | same |

The accent shifts from bright indigo (dark) to deeper violet (light) to maintain contrast in each mode.

---

## 3. Streamlit Integration Architecture

### 3.1 Native widgets kept, CSS-overridden

The design works **within** Streamlit's native widget model — `st.sidebar`, `st.tabs()`, `st.columns()`, `st.metric()`, etc. are all kept. The visual transformation is achieved entirely through CSS overrides injected via `st.markdown(..., unsafe_allow_html=True)`.

Streamlit's native sidebar, header bar, and tab widget are **restyled**, not replaced with raw HTML. This avoids fragile DOM injection and remains compatible with Streamlit updates.

Target selectors for Streamlit internals:
- `[data-testid="stSidebar"]` — sidebar background, border, padding
- `[data-testid="stSidebarContent"]` — inner content padding
- `[data-testid="stHeader"]` — top header bar (hidden entirely; custom logo/tabs rendered via `st.markdown` at top of main content)
- `[data-testid="stTabs"] [data-baseweb="tab-list"]` — tab bar styling
- `[data-testid="stTabs"] [data-baseweb="tab"]` — individual tab pill styling
- `[data-testid="stTabs"] [data-baseweb="tab-highlight"]` — active tab underline (hidden; replaced by pill background)
- `.block-container` — reduce top/bottom padding (set to `1rem 1.5rem`)
- `.stVerticalBlock` — reduce gap between stacked elements
- `.element-container` — reduce bottom margin
- `[data-testid="stMetric"]` — restyle metric value/label/delta

All `st.divider()` calls are removed. Card visual boundaries provide separation instead.

### 3.2 Dark / Light toggle

Streamlit owns `data-theme` on `document.documentElement` — do **not** write to that attribute.

**Mechanism:** the toggle adds/removes the class `hmm-light` on `document.body`. All custom CSS variables are defined on `body` (dark defaults) and `body.hmm-light` (light overrides). This is entirely separate from Streamlit's own theming and will not conflict.

```css
body           { --bg0: #07070d; --accent: #6366f1; /* dark defaults */ }
body.hmm-light { --bg0: #f0f0f8; --accent: #4f46e5; /* light overrides */ }
```

Toggle JavaScript (injected in the CSS `st.markdown` block):

```js
function toggleHmmTheme() {
  document.body.classList.toggle('hmm-light');
  const btn = document.getElementById('hmmThemeBtn');
  btn.textContent = document.body.classList.contains('hmm-light') ? '☀️' : '🌙';
}
```

> **Note on the reference mockup:** The mockup file (`mockups/dashboard-redesign.html`) uses `html[data-theme="light"]` and `document.documentElement.setAttribute('data-theme', ...)` for its toggle — this was the mockup's standalone HTML approach and is **not** the implementation mechanism. In `dashboard.py`, use `body.hmm-light` as specified above. The mockup's visual design (colours, layout, spacing) remains the authoritative reference; only its theme-switching JS and CSS selectors differ from the implementation.

### 3.3 Plotly chart theming for light mode

`build_candlestick` and `build_equity_chart` currently hardcode `paper_bgcolor = "#0f1117"`. These two properties are **in scope for this redesign**:

- Change both functions to accept a `bg_color: str` parameter (default `"#0f1117"`)
- The dashboard passes the correct value based on a session-state theme flag
- Alternatively: pass `paper_bgcolor = "rgba(0,0,0,0)"` and control background entirely via the card wrapper's CSS `background` — this is the preferred approach as it removes the coupling entirely

---

## 4. Navigation & Layout

### Topbar
Streamlit's native header (`[data-testid="stHeader"]`) is hidden via `display: none`. A custom logo + theme toggle is rendered as the first element in the main content area using `st.markdown`:

```html
<div class="hmm-topbar">
  <div class="hmm-logo">HMM <span>Quant</span></div>
  <button class="hmm-theme-toggle" onclick="toggleHmmTheme()">🌙</button>
</div>
```

Streamlit's own `st.tabs()` provides the Live / Backtest / About navigation — restyled to pill tabs via CSS overrides on `[data-baseweb="tab"]`.

### Sidebar (desktop)
`st.sidebar` is kept. Styled via `[data-testid="stSidebar"]` CSS to match the design tokens (background `--bg1`, border-right `--border`, no box-shadow). Width stays at Streamlit's default (≈245px on wide layout).

Contents (in order):
1. Focus Asset — `st.selectbox`
2. Data Window — `st.selectbox`
3. HMM States — `st.slider`
4. Chart Bars — `st.slider`
5. `st.caption` footer (data sources + disclaimer)

### Mobile sidebar behaviour
Streamlit's sidebar collapses to its native hamburger drawer on mobile. CSS overrides ensure the drawer background and content match design tokens. No custom mobile drawer is implemented — Streamlit's native collapse is sufficient.

### Responsive breakpoints
| Width | Cards grid | Metrics grid | Sidebar |
|---|---|---|---|
| > 900px | 4 col | 6 col | Fixed left (Streamlit native) |
| 600–900px | 2 col | 3 col | Fixed left |
| ≤ 600px | 2 col | 2 col | Streamlit native hamburger |
| ≤ 380px | 1 col | 2 col | Streamlit native hamburger |

`overflow-x: hidden` is set on `.block-container` and `section[data-testid="stMain"]` to prevent horizontal scroll. All grids use `width: 100%` and `min-width: 0` to prevent flex/grid overflow.

---

## 5. Tab Structure

### Tab 1 — Live
1. Hero Signal Banner
2. Market Overview (4 ticker cards)
3. Market Sentiment Strip
4. Price Chart
5. Confirmation Detail Panel
6. Backtest Snapshot (6-metric grid)

> **Note:** The Regime Summary table (all HMM states) from the current dashboard is **removed from the Live tab**. It is relocated to the **About tab** (Section 5, after model parameters), where it fits the "trust/methodology" context better.

### Tab 2 — Backtest
1. Equity curve vs Buy & Hold
2. Trade log table

### Tab 3 — About
1. What the app does
2. The 10-point confirmation system
3. Model parameters table
4. **Regime State Summary** (relocated from Live tab)
5. Risk management rules
6. Disclaimer

---

## 6. Component Specifications

### 6.1 Hero Signal Banner
Full-width card. Two regions, side-by-side on desktop, stacked vertically on mobile (≤600px):

**Left region** (`.hero-left`):
- Asset label: `"{TICKER_LABEL}/USD — Current Signal"` (13px, uppercase, muted)
- Signal pill: `LONG` / `SHORT` / `NEUTRAL` (22px bold, glow shadow, pulsing dot, coloured border)
- Timestamp caption below pill

**Right region** (`.hero-stats` — horizontal flex row of 4 stat columns):
1. Regime badge (Bull / Bear / Neutral pill)
2. Confirmations count (`9/10`) with 10-pip bar below (filled pips = passed confirmations)
3. 24h change percentage
4. Current price

On mobile (≤600px): `.hero` switches to `flex-direction: column`. `.hero-stats` remains a wrapping flex row but each stat shrinks to fit. Reference: mockup `.hero-stats` / `.hero-stat` CSS structure.

### 6.2 Ticker Cards (×4)
- `st.columns(4)` on desktop, CSS grid override on mobile (see breakpoints)
- Each card rendered as `st.markdown(html, unsafe_allow_html=True)`
- 4px left accent bar (`::before` pseudo-element) coloured by current regime
- Gradient background tint from regime colour at 8% opacity, fading to card colour
- Content: asset name, `TICKER/USD`, regime badge, price, 24h delta, 7d change, market cap, sparkline (Plotly, height=36px)

### 6.3 Market Sentiment Strip
Single `st.markdown` card replacing the Plotly `go.Indicator` gauge entirely:
- Left: "Market Sentiment" label
- Centre: CSS gradient track (`bear → neutral → bull`) with a positioned needle at the computed score
- Right: sentiment label ("Bullish" / "Neutral" / "Bearish") + three coloured asset-count pills

Computed the same way as current code (average regime score → 0–100 scale).

### 6.4 Confirmation Detail Panel
- Rendered via `st.markdown` as a card with a header row: `"🔍 Confirmation Detail — Current Bar"` on left, `"N / 10 met ▾"` on right
- **Open by default, collapsible** — the `▾` chevron indicates it can be collapsed. JavaScript toggles a `.collapsed` class on the panel body. This replaces the current `st.expander`
- Body: 2-column CSS grid of 10 items, each with circular pass (✓ green) or fail (✗ red) icon
- On mobile (≤600px): grid drops to 1 column

### 6.5 Backtest Metrics Snapshot (Live tab)
Single card with a 6-cell CSS grid divided by 1px border lines.

Cells (in order): Total Return, Buy & Hold, Win Rate, Max Drawdown, Sharpe Ratio, Final Equity.

> **Total Trades is intentionally omitted** from this 6-cell grid. The count appears as a caption in the trade log header on the Backtest tab instead.

Each cell: uppercase label (10.5px) → value (22px bold) → context line (11.5px).
Colour: positive = bull green, negative = bear red, ratios = accent.

### 6.6 Candlestick Chart
`build_candlestick` is kept. **One permitted change:** `paper_bgcolor` and `plot_bgcolor` are changed from the hardcoded `"#0f1117"` to `"rgba(0,0,0,0)"` (transparent). The chart card wrapper's CSS `background` property provides the visible background colour, which automatically adapts to dark/light mode via CSS variables.

### 6.7 Equity Chart
Same treatment as 6.6 — `paper_bgcolor` and `plot_bgcolor` set to `"rgba(0,0,0,0)"`.

### 6.8 Regime State Summary (About tab)

The `state_summary` dataframe (produced by `get_ticker_data`) is relocated from the Live tab to the About tab. It is rendered using `st.dataframe` with the existing `style_summary()` function, but `style_summary()` must be updated to use CSS variable colours instead of hardcoded hex values (`#1a1a2e`, `#e0e0e0`) so it renders correctly in both dark and light mode. Specifically:
- Row background: replace `background-color:#1a1a2e` with `background-color:var(--bg2, #1a1a2e)`
- Row text: replace `color:#e0e0e0` with `color:var(--t1, #e0e0e0)`
- Bull/Bear label colours remain `#00c96a` / `#e03535` (acceptable in both modes)

It is placed in the About tab between the Model Parameters and Risk Management sections, under a heading "Regime State Profiles".

### 6.9 Trade Log Table
`st.dataframe` kept as-is. Card wrapper adds a header row (title left, trade count + avg return right) rendered via `st.markdown`.

---

## 7. Custom CSS Injection

Single `st.markdown` block injected **immediately after `st.set_page_config`**, before any other content calls. (`st.set_page_config` must always be the very first Streamlit call — placing `st.markdown` before it raises a `StreamlitAPIException`.) Contains:

1. CSS custom properties on `body` (dark defaults) and `body.hmm-light` (light overrides)
2. Streamlit internal overrides (all selectors listed in Section 3.1)
3. Custom component classes (`.hmm-topbar`, `.hero`, `.ticker-card`, `.signal-pill`, `.conf-pip`, `.sentiment-strip`, `.metrics-grid`, etc.)
4. Responsive `@media` rules
5. JavaScript: `toggleHmmTheme()` function

Streamlit `st.divider()` calls: **all removed**.

---

## 8. Out of Scope

- No changes to `pipeline/`, `models/`, or `strategy/` modules
- No changes to data fetching, caching TTL, or backtest logic
- No backend alerting, webhooks, or email features
- No shareable snapshot/export feature
- No authentication or public/private view split
- No changes to `TICKERS`, `TICKER_LABELS`, `N_STATES`, or any constants

---

## 9. Files Changed

| File | Change |
|---|---|
| `app/dashboard.py` | Full visual redesign — CSS block, layout restructure, component rewrites, remove `st.divider()` calls, `paper_bgcolor` → transparent in chart builders |
| `mockups/dashboard-redesign.html` | Reference mockup (design approved 2026-03-24) |
