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
  --accent:      #CF142B;
  --accent-lt:   #e8374a;
  --accent-glow: rgba(207,20,43,0.18);
  --gold:        #FCDD09;
  --blue-cat:    #0032A0;
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
  --bg0:         #f7f7f7;
  --bg1:         #efefef;
  --bg2:         #ffffff;
  --bg3:         #f4f4f4;
  --border:      rgba(207,20,43,0.10);
  --border2:     rgba(207,20,43,0.20);
  --t1:          #111111;
  --t2:          #444444;
  --t3:          #888888;
  --accent:      #b01225;
  --accent-lt:   #CF142B;
  --accent-glow: rgba(207,20,43,0.12);
  --gold:        #d4b800;
  --blue-cat:    #0032A0;
  --bull:        #059669;
  --bull-bg:     rgba(5,150,105,0.08);
  --bear:        #dc2626;
  --bear-bg:     rgba(220,38,38,0.08);
  --shadow:      0 2px 8px rgba(79,70,229,0.08), 0 0 1px rgba(79,70,229,0.12);
}

/* ── Streamlit internals ─────────────────────────────────────────── */

/* Hide Streamlit's default header/toolbar — replaced by custom btg-navbar */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"]      { display: none !important; }
[data-testid="stDeployButton"] { display: none !important; }

/* Main content area — reduced top padding since Streamlit header is hidden */
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

/* Tabs: underline style matching BTG navbar */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: transparent !important;
  gap: 0 !important;
  border-bottom: 1px solid var(--border) !important;
  padding-bottom: 0 !important;
  justify-content: flex-start !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: 0 !important;
  color: var(--t2) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 10px 20px !important;
  border-bottom: 2px solid transparent !important;
  margin-bottom: -1px !important;
  transition: var(--transition) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
  color: var(--t1) !important;
  background: transparent !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background: transparent !important;
  color: var(--accent) !important;
  font-weight: 600 !important;
  border-bottom: 2px solid var(--accent) !important;
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

/* ── Ticker Cards ────────────────────────────────────────────────── */
.hmm-cards { display:grid; grid-template-columns:repeat(2,1fr); gap:14px; margin:4px 0; }
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

/* ── About Tab ───────────────────────────────────────────────────── */
.hmm-about-card {
  background:var(--bg2); border:1px solid var(--border);
  border-radius:var(--radius); padding:18px 20px; box-shadow:var(--shadow);
  margin-bottom:18px;
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

/* ── Section divider (Live tab spacing) ──────────────────────────── */
.hmm-section-gap {
  height: 28px;
  border-top: 1px solid var(--border);
  margin: 8px 0 4px;
}
.hmm-section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--t3);
  margin: 0 0 10px;
}

/* ── Responsive ──────────────────────────────────────────────────── */
html, body { overflow-x: hidden; max-width: 100vw; }
section[data-testid="stMain"] { overflow-x: hidden; }
.block-container { overflow-x: hidden; }

/* Tablet ≤ 900px */
@media (max-width: 900px) {
  .hmm-cards        { grid-template-columns: repeat(2,1fr) !important; }
  .hmm-metrics-grid { grid-template-columns: repeat(3,1fr) !important; }
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
  .block-container  { padding: 0.75rem 0.75rem 2rem !important; }
}

/* Very small ≤ 380px */
@media (max-width: 380px) {
  .hmm-cards { grid-template-columns: 1fr !important; }
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
  letter-spacing: 0.09em; text-transform: uppercase; color: var(--t3);
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
.hmm-tip {
  font-size: 10px; color: var(--t3); cursor: help;
  margin-left: 3px; vertical-align: middle;
}
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

/* ── About tab cards ─────────────────────────────────────────────── */
.hmm-about-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
  margin-bottom: 14px;
  box-shadow: var(--shadow);
}
.hmm-about-card h3 {
  font-size: 14px; font-weight: 700;
  color: var(--accent-lt);
  margin: 0 0 12px;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.hmm-about-card p, .hmm-about-card li {
  font-size: 13px; color: var(--t2); line-height: 1.65;
}
.hmm-about-card ul { padding-left: 18px; margin: 0; }
.hmm-about-card li { margin-bottom: 4px; }
.hmm-stat-row {
  display: flex; justify-content: space-between;
  padding: 7px 0; border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.hmm-stat-row:last-child { border-bottom: none; }
.hmm-stat-key { color: var(--t3); font-weight: 500; }
.hmm-stat-val { color: var(--t1); font-weight: 600; }
.hmm-disclaimer {
  background: var(--bear-bg);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  font-size: 12.5px; color: var(--bear);
  margin-top: 10px;
}

/* ── Trade log card ──────────────────────────────────────────────── */
.hmm-tradelog-card {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow);
}
.hmm-tradelog-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid var(--border);
}
.hmm-tradelog-title { font-size: 13px; font-weight: 700; color: var(--t1); }
.hmm-tradelog-meta  { font-size: 11px; color: var(--t3); }

/* ── BTG Traders Navbar ──────────────────────────────────────────── */
.btg-navbar {
  display: flex;
  align-items: center;
  height: 60px;
  margin: -1rem -1.5rem 1.5rem -1.5rem;
  padding: 0 28px;
  background: #0c0c14;
  border-bottom: 1px solid rgba(207,20,43,0.3);
  position: relative;
  z-index: 100;
}
/* Reset browser default link styles inside navbar */
.btg-navbar a, .btg-navbar a:visited, .btg-navbar a:hover {
  text-decoration: none !important;
  color: inherit !important;
}
.btg-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none !important;
  flex-shrink: 0;
}
.btg-brand-mark {
  width: 30px; height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, #CF142B 0%, #0032A0 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 900; color: #FCDD09;
}
.btg-brand-name {
  font-size: 16px; font-weight: 700;
  color: #eeeef5; letter-spacing: -0.3px;
}
.btg-brand-red { color: #CF142B; }
.btg-nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
  position: absolute;
  left: 50%; transform: translateX(-50%);
}
.btg-nav-link {
  padding: 7px 15px;
  border-radius: 8px;
  font-size: 13px; font-weight: 500;
  color: #9090aa;
  cursor: pointer;
  border: 1px solid transparent;
  background: none;
  text-decoration: none;
  transition: all 0.15s;
  user-select: none;
}
.btg-nav-link:hover { color: #eeeef5; background: rgba(255,255,255,0.05); }
.btg-nav-active {
  color: #eeeef5 !important;
  background: rgba(207,20,43,0.12) !important;
  border-color: rgba(207,20,43,0.25) !important;
}
.btg-nav-disabled { color: #444 !important; cursor: default !important; }
.btg-nav-disabled:hover { background: none !important; }
.btg-nav-actions {
  margin-left: auto;
  display: flex; align-items: center; gap: 8px;
}
.btg-icon-btn {
  width: 32px; height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  background: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; color: #9090aa;
  text-decoration: none;
  transition: all 0.15s;
}
.btg-icon-btn:hover { border-color: rgba(255,255,255,0.2); color: #eeeef5; }
.btg-btn-ghost {
  padding: 7px 14px; border-radius: 8px;
  font-size: 13px; font-weight: 500;
  color: #9090aa;
  border: 1px solid rgba(255,255,255,0.12);
  background: none; cursor: pointer;
  transition: all 0.15s;
}
.btg-btn-ghost:hover { color: #eeeef5; border-color: rgba(255,255,255,0.25); }
.btg-btn-primary {
  padding: 7px 16px; border-radius: 8px;
  font-size: 13px; font-weight: 600;
  color: #fff; background: #CF142B;
  border: none; cursor: pointer;
  transition: all 0.15s;
}
.btg-btn-primary:hover { background: #b01225; }
body.hmm-light .btg-navbar { background: #ffffff; border-bottom-color: rgba(207,20,43,0.2); }
body.hmm-light .btg-brand-name { color: #111111; }
body.hmm-light .btg-nav-link { color: #666; }
body.hmm-light .btg-nav-link:hover { color: #111; background: rgba(0,0,0,0.04); }
body.hmm-light .btg-btn-ghost { color: #666; border-color: rgba(0,0,0,0.15); }
body.hmm-light .btg-btn-ghost:hover { color: #111; }
body.hmm-light .btg-icon-btn { color: #666; border-color: rgba(0,0,0,0.12); }

/* ── Alpha Build Banner ──────────────────────────────────────────── */
.btg-alpha-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin: 0 -1.5rem 1.5rem -1.5rem;
  padding: 12px 28px;
  background: rgba(252,221,9,0.06);
  border-bottom: 1px solid rgba(252,221,9,0.2);
}
.btg-alpha-badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 4px;
  background: rgba(252,221,9,0.15);
  border: 1px solid rgba(252,221,9,0.35);
  color: #FCDD09;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-top: 1px;
}
.btg-alpha-text {
  font-size: 12px;
  color: #9090aa;
  line-height: 1.5;
  flex: 1;
}
.btg-alpha-text a {
  color: #FCDD09 !important;
  text-decoration: underline !important;
}
.btg-alpha-close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: #55556a;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  margin-top: -1px;
}
.btg-alpha-close:hover { color: #9090aa; }
body.hmm-light .btg-alpha-banner { background: rgba(212,184,0,0.06); border-bottom-color: rgba(212,184,0,0.25); }
body.hmm-light .btg-alpha-text { color: #555; }
</style>

<script>
function toggleHmmTheme() {
  document.body.classList.toggle('hmm-light');
  var btn = document.getElementById('hmmThemeBtn');
  if (btn) {
    btn.textContent = document.body.classList.contains('hmm-light') ? '☀️' : '🌙';
  }
}
</script>
"""

SIDEBAR_HIDDEN_CSS = """
<style>
/* ── Sidebar hidden — injected when st.session_state.sidebar_visible is False ── */
[data-testid="stSidebar"]  { display: none !important; }
section[data-testid="stMain"] { margin-left: 0 !important; }
/* NOTE: stSidebarCollapsedControl is intentionally NOT hidden so the native
   Streamlit toggle always works as a fallback. */
</style>
"""

LIGHT_MODE_CSS = """
<style>
/* ── Light mode override — injected when st.session_state.light_mode is True ── */
body {
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

/* ── Streamlit native element overrides for light mode ─────────── */
[data-testid="stAppViewContainer"],
section[data-testid="stMain"],
.block-container {
  background: var(--bg0) !important;
}

/* Markdown headings and body text */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
  color: var(--t1) !important;
}
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th {
  color: var(--t2) !important;
}

/* Streamlit generic text / caption / label */
.stText, .stCaption, [data-testid="stCaptionContainer"] {
  color: var(--t3) !important;
}
label, .stWidgetLabel { color: var(--t2) !important; }

/* Tab labels */
[data-testid="stTabs"] [data-baseweb="tab"] {
  color: var(--t2) !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: var(--accent) !important;
  background: var(--accent-glow) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--bg1) !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stWidgetLabel {
  color: var(--t3) !important;
}

/* Metric */
[data-testid="stMetric"] { background: var(--bg2) !important; }
[data-testid="stMetricValue"] { color: var(--t1) !important; }
[data-testid="stMetricLabel"] { color: var(--t3) !important; }

/* DataFrames */
[data-testid="stDataFrame"] { background: var(--bg2) !important; }

/* Expander */
[data-testid="stExpander"] {
  background: var(--bg2) !important;
  border-color: var(--border) !important;
}
</style>
"""
