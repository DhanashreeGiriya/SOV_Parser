"""
Intelligent SOV Parser — Streamlit entry point.

Run with:
    streamlit run app.py

(this file bootstraps sys.path so the sov_app package is importable
whether you launch it from inside or outside the package directory)
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parent.parent
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import streamlit as st

st.set_page_config(page_title="Intelligent SOV Parser", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
:root {
    --bg:#ffffff; --surface:#f8f9fa; --card:#ffffff; --border:#dee2e6;
    --teal:#1565c0; --teal-d:#0d47a1; --amber:#f59e0b; --green:#10b981;
    --red:#ef4444; --blue:#1976d2; --purple:#8b5cf6;
    --text:#1a1a2e; --muted:#6c757d;
    --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
}
html,body,.stApp{background:#f0f4f8!important;color:var(--text)!important;font-family:var(--sans)!important}

header[data-testid="stHeader"]{display:none!important}
#MainMenu{display:none!important}
[data-testid="stToolbar"]{display:none!important}
footer{display:none!important}

[data-testid="stSidebar"]{background:#ffffff!important;border-right:1px solid #dee2e6!important}
[data-testid="stSidebar"] *{color:#1a1a2e!important}

.block-container{padding:2.5rem 2.2rem 1.8rem!important;max-width:1440px}

h1{font-family:var(--mono)!important;font-size:1.8rem!important;font-weight:600!important;color:#1565c0!important;letter-spacing:-.03em!important;margin-bottom:0!important}
h2{font-family:var(--sans)!important;font-weight:600!important;color:#1a1a2e!important;font-size:1.05rem!important}
h3{font-family:var(--sans)!important;font-weight:500!important;color:#6c757d!important;font-size:.9rem!important;text-transform:uppercase!important;letter-spacing:.06em!important}
.stButton>button{background:#1565c0!important;color:#ffffff!important;font-family:var(--mono)!important;font-weight:600!important;border:none!important;border-radius:4px!important;padding:.5rem 1.2rem!important;font-size:.85rem!important;transition:all .15s!important}
.stButton>button:hover{background:#0d47a1!important;transform:translateY(-1px)!important}
[data-testid="stDownloadButton"]>button{background:#ffffff!important;color:#1565c0!important;font-family:var(--mono)!important;font-weight:600!important;border:1px solid #1565c0!important;border-radius:4px!important;padding:.5rem 1.2rem!important;font-size:.85rem!important;transition:all .15s!important;width:100%!important}
[data-testid="stDownloadButton"]>button:hover{background:#e8f0fe!important;transform:translateY(-1px)!important}
[data-testid="stFileUploader"]{background:var(--card)!important;border:1px dashed var(--border)!important;border-radius:6px!important}
.stSelectbox>div>div,.stNumberInput>div>div>input,.stTextInput>div>div>input{background:#ffffff!important;color:#1a1a2e!important;border:1px solid #ced4da!important;border-radius:4px!important;font-family:var(--mono)!important;font-size:.85rem!important}
.stTextInput label,.stNumberInput label,.stSelectbox label,.stCheckbox label,.stSlider label{color:#6c757d!important;font-size:.8rem!important}
input::placeholder{color:#adb5bd!important}
[data-testid="stMetric"]{background:#ffffff!important;border:1px solid #dee2e6!important;border-radius:6px!important;padding:.9rem 1.1rem!important}
[data-testid="stMetricLabel"]{color:#6c757d!important;font-size:.72rem!important;text-transform:uppercase;letter-spacing:.05em}
[data-testid="stMetricValue"]{color:#1565c0!important;font-size:1.7rem!important;font-weight:700!important;font-family:var(--mono)!important}
.streamlit-expanderHeader{background:var(--card)!important;border-radius:4px!important;color:var(--text)!important;font-family:var(--sans)!important;font-size:.88rem!important}
.stTabs [data-baseweb="tab-list"]{background:#f0f4f8!important;border-radius:4px 4px 0 0!important;gap:2px}
.stTabs [data-baseweb="tab"]{color:#6c757d!important;font-family:var(--mono)!important;font-size:.82rem!important;font-weight:500!important;padding:.5rem 1rem!important}
.stTabs [aria-selected="true"]{color:#1565c0!important;background:#ffffff!important;border-bottom:2px solid #1565c0!important}
.stTabs [data-baseweb="tab-panel"]{background:#ffffff!important;border-radius:0 0 6px 6px!important;padding:1.2rem!important;border:1px solid #dee2e6!important;border-top:none!important}
.stDataFrame{border-radius:4px!important}
.stAlert{border-radius:4px!important;font-family:var(--sans)!important;font-size:.88rem!important}
hr{border-color:var(--border)!important;margin:1rem 0!important}
.stProgress>div>div{background:var(--teal)!important}
code{font-family:var(--mono)!important;background:#e8f0fe!important;color:#1565c0!important;border-radius:3px!important;padding:.1rem .4rem!important;font-size:.82rem!important}
.stCheckbox>label>div{color:var(--text)!important}

[data-testid="stSidebar"]            { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="collapsedControl"]     { display: none !important; }
section[data-testid="stSidebarContent"] { display: none !important; }
button[kind="header"]                { display: none !important; }

.method-badge{display:inline-block;font-family:var(--mono);font-size:.7rem;font-weight:600;padding:.15rem .5rem;border-radius:3px;text-transform:uppercase;letter-spacing:.05em}
.m-ref    {background:rgba(21,101,192,.1);color:#1565c0;border:1px solid rgba(21,101,192,.3)}
.m-sem    {background:rgba(245,158,11,.1);color:#b45309;border:1px solid rgba(245,158,11,.3)}
.m-ai     {background:rgba(139,92,246,.1);color:#6d28d9;border:1px solid rgba(139,92,246,.3)}
.m-absent {background:rgba(108,117,125,.1);color:#495057;border:1px solid rgba(108,117,125,.2)}
.m-miss   {background:rgba(239,68,68,.1);color:#dc2626;border:1px solid rgba(239,68,68,.3)}
.m-human  {background:rgba(245,158,11,.1);color:#92400e;border:1px solid rgba(245,158,11,.3)}
.m-fb {background:rgba(16,185,129,.1);color:#065f46;border:1px solid rgba(16,185,129,.3)}
.legend-row{display:flex;gap:.6rem;flex-wrap:wrap;margin:.8rem 0;align-items:center}
.conf-bar-wrap{width:80px;height:6px;background:rgba(0,0,0,.08);border-radius:3px;display:inline-block;vertical-align:middle;margin-left:6px}
.conf-bar{height:100%;border-radius:3px}

/* Journey cards */
.j-card{background:#ffffff;border:1px solid #dee2e6;border-radius:8px;padding:1rem 1.2rem;margin-bottom:.8rem}
.j-title{font-family:var(--mono);font-size:.95rem;font-weight:600;color:#1565c0;margin-bottom:.8rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.j-steps-row{display:flex;align-items:stretch;gap:0;margin-bottom:.6rem;overflow-x:auto}
.j-step{flex:1;min-width:130px;padding:.6rem .8rem;background:#f8f9fa;border:1px solid #dee2e6;border-radius:0}
.j-step:first-child{border-radius:6px 0 0 6px}
.j-step:last-child{border-radius:0 6px 6px 0}
.j-step-lbl{font-size:.62rem;color:#6c757d;text-transform:uppercase;letter-spacing:.08em;font-weight:600;margin-bottom:.25rem}
.j-step-val{font-family:var(--mono);font-size:.78rem;color:#1a1a2e;word-break:break-word;font-weight:500}
.j-step-note{font-size:.64rem;color:#6c757d;margin-top:.2rem;font-style:italic}
.j-arrow{display:flex;align-items:center;padding:0 4px;color:#adb5bd;font-size:1rem;flex-shrink:0;align-self:center}
.j-final{border-color:#1565c0!important;background:rgba(21,101,192,.06)!important}
.j-final .j-step-val{color:#1565c0!important}
.j-card.j-agreed{border-left:3px solid #10b981!important}
.j-card.j-override{border-left:3px solid #8b5cf6!important}
.j-card.j-removed{border-left:3px solid #ef4444!important}
.j-basis{font-size:.78rem;color:#374151;margin-top:.5rem;padding:.35rem .6rem;background:#f0f4f8;border-left:3px solid #1565c0;border-radius:0 4px 4px 0}

/* Schema summary grid */
.schema-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.5rem;margin:.8rem 0}
.schema-cell{padding:.5rem .8rem;border-radius:5px;border:1px solid #dee2e6;font-family:var(--mono);font-size:.75rem}
.sc-ref   {background:rgba(21,101,192,.07);border-color:rgba(21,101,192,.3);color:#1565c0}
.sc-sem   {background:rgba(245,158,11,.07);border-color:rgba(245,158,11,.3);color:#b45309}
.sc-ai    {background:rgba(139,92,246,.07);border-color:rgba(139,92,246,.3);color:#6d28d9}
.sc-miss  {background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.3);color:#dc2626}
.sc-null  {background:rgba(108,117,125,.07);border-color:rgba(108,117,125,.2);color:#6c757d}
.sc-human {background:rgba(245,158,11,.07);border-color:rgba(245,158,11,.3);color:#92400e}

/* ── Sticky header + tab bar ─────────────────────────────────────────────── */

/* 1. Fix the very top app container so it doesn't scroll with content */
.stApp > div:first-child {
    position: sticky !important;
    top: 0 !important;
    z-index: 999 !important;
}

/* 2. Our custom title div (the blue "Intelligent SOV Parser" bar) */
div[data-testid="stVerticalBlock"] > div:first-child > div:first-child {
    position: sticky !important;
    top: 0 !important;
    z-index: 998 !important;
    background: #f0f4f8 !important;
    padding-bottom: .5rem !important;
}

/* 3. Streamlit tab list — stick below the title */
.stTabs [data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0 !important;
    z-index: 997 !important;
    background: #f0f4f8 !important;
    padding-top: .3rem !important;
    padding-bottom: 0 !important;
    border-bottom: 1px solid #dee2e6 !important;
}

/* 4. Make the main block-container scrollable independently */
section.main > div.block-container {
    overflow-y: auto !important;
    height: 100vh !important;
    padding-top: 1rem !important;
}

/* 5. Ensure the tab panel content (below the sticky tabs) scrolls */
.stTabs [data-baseweb="tab-panel"] {
    overflow-y: auto !important;
    max-height: calc(100vh - 130px) !important;
}
</style>
""", unsafe_allow_html=True)

from ui.accuracy_tab import render_accuracy_tab
from ui.common import load_pipeline, render_sidebar
from ui.feedback_tab import render_feedback_tab
from ui.phase1_mapping import render_phase1
from ui.phase2_review import render_phase2
from ui.phase3_transform import render_phase3
from ui.row_feedback_tab import render_row_feedback_tab

def main():
    system, auto_threshold, _ = render_sidebar()

    try:
        import base64
        with open("logo 1 (1).jpg", "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        logo_html = (
            f'<img src="data:image/jpeg;base64,{logo_b64}" '
            f'style="height:48px;width:auto;object-fit:contain;display:block">'
        )
    except Exception:
        logo_html = ""

    st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            margin-bottom:1rem;padding-bottom:.75rem;border-bottom:2px solid #dee2e6">
  <div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.7rem;font-weight:700;
                color:#1565c0;letter-spacing:-.03em;line-height:1.1">Intelligent SOV Parser</div>
    <div style="font-size:.6rem;color:#6c757d;font-family:'IBM Plex Mono',monospace;margin-top:.3rem;letter-spacing:.01em">
      For Faster SOV Verifications
    </div>
  </div>
  <div style="background:#ffffff;padding:8px 12px;border-radius:8px;
              border:1px solid #dee2e6;box-shadow:0 1px 4px rgba(0,0,0,.06)">{logo_html}</div>
</div>""", unsafe_allow_html=True)

    sov, err = load_pipeline()
    if sov is None:
        st.error("Could not import `sov_header_mapping`. Ensure both files are in the same directory.")
        st.code(f"Error: {err}")
        return

    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Map & Analyse", "Review", "Transform", "Accuracy QA", "🧠 Column Rules", "⚙️ Row Rules"])
 
    with tab1: render_phase1(sov, system)
    with tab2: render_phase2(sov, system, auto_threshold)
    with tab3: render_phase3(sov, system)
    with tab4: render_accuracy_tab()
    with tab5: render_feedback_tab()
    with tab6: render_row_feedback_tab()


if __name__ == "__main__":
    main()

