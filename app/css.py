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
