# ui_theme.py
from datetime import datetime
import streamlit as st

# Farben (H-care Style)
PURPLE = "#7C3AED"
PURPLE_DARK = "#5B21B6"
TEAL = "#14B8A6"
SLATE = "#1F2937"
TEXT = "#0F172A"
MUTED = "#667085"
BG = "#F7F8FC"
WHITE = "#FFFFFF"
BORDER = "#E6EAF2"

PLOTLY_TEMPLATE = "plotly_white"
COLORWAY = [PURPLE, TEAL, "#F59E0B", "#EF4444", "#0EA5E9", "#22C55E"]

def inject_css():
    st.markdown(f"""
    <style>
      .stApp {{ background:{BG}; }}
      html, body, [class*="css"] {{
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial !important;
      }}
      /* Sidebar: hell, klare Buttons */
      section[data-testid="stSidebar"] {{
        background:{WHITE};
        border-right:1px solid {BORDER};
      }}
      .side-card {{
        background:{WHITE};
        border:1px solid {BORDER};
        border-radius:16px;
        padding:16px;
        box-shadow:0 1px 2px rgba(16,24,40,.05);
      }}
      /* Generic Card */
      .card {{
        background:{WHITE};
        border:1px solid {BORDER};
        border-radius:16px;
        padding:16px;
        box-shadow:0 1px 2px rgba(16,24,40,.05);
        margin-bottom:14px;
      }}
      .card h4 {{ margin:0 0 8px 0; font-weight:700; }}
      /* KPI metric weight */
      div[data-testid="stMetricValue"] {{ font-weight:800; }}
      div[data-testid="stMetricDelta"] {{ font-weight:600; }}
      /* Small pill */
      .pill {{
        background:{PURPLE}12; color:{PURPLE};
        border:1px solid {PURPLE}33; border-radius:999px;
        padding:2px 10px; font-size:12px; display:inline-block;
      }}
    </style>
    """, unsafe_allow_html=True)

def header_bar():
    left, right = st.columns([0.75, 0.25])
    with left:
        st.markdown("### Overview")
        st.caption("Self-Storage KPIs & Trends")
    with right:
        st.markdown(f"""
        <div class="card" style="text-align:right;">
          <div style="font-size:12px;color:{MUTED}">Last update</div>
          <div style="font-weight:800;font-size:16px;color:{TEXT}">{datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
        </div>
        """, unsafe_allow_html=True)

def card_start(title=None, right_pill=None):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if title or right_pill:
        cols = st.columns([0.78, 0.22])
        with cols[0]:
            if title: st.markdown(f"#### {title}")
        with cols[1]:
            if right_pill: st.markdown(f'<div style="text-align:right;"><span class="pill">{right_pill}</span></div>', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)

def style_fig(fig, title=None, h=300):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        colorway=COLORWAY,
        title=title,
        height=h,
        margin=dict(t=48,l=16,r=16,b=16),
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig
