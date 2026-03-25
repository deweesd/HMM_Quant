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
