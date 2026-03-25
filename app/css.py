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
