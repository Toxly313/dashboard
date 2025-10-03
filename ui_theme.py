# ui_theme.py
from datetime import datetime
import streamlit as st

# Farbpalette (weiß + orange als Akzent)
ORANGE = "#FF8A00"
ORANGE_DARK = "#F27300"
DARK = "#0F172A"
SLATE = "#1F2937"
MUTED = "#64748B"
CARD_BORDER = "#E9EEF3"
BG = "#F6F7FB"
WHITE = "#FFFFFF"

# Plotly Defaults
PLOTLY_TEMPLATE = "plotly_white"
COLORWAY = [ORANGE, "#1F2937", "#22C55E", "#8B5CF6", "#0EA5E9", "#F97316"]

def inject_base_css():
    st.markdown(f"""
    <style>
      html, body, [class*="css"] {{
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial !important;
      }}
      /* App-Hintergrund */
      .stApp {{ background: {BG}; }}
      /* Sidebar dunkel wie im Mockup */
      section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {SLATE} 0%, #0B1220 100%);
        color: #E5E7EB;
      }}
      section[data-testid="stSidebar"] .sidebar-card {{
        background: rgba(255,255,255,0.06);
        border-radius: 14px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,0.12);
      }}
      /* Allgemeine Card */
      .card {{
        background: {WHITE};
        border: 1px solid {CARD_BORDER};
        box-shadow: 0 1px 2px rgba(16,24,40,.05);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
      }}
      /* KPI-Karten kompakter */
      div[data-testid="stMetricValue"] {{ font-weight: 800; }}
      div[data-testid="stMetricDelta"] {{ font-weight: 600; }}
      /* Kleine Pills (Buttons / Tags) */
      .pill {{
        background: {ORANGE}1A; color: {ORANGE};
        border: 1px solid {ORANGE}33; border-radius: 999px;
        padding: 2px 10px; font-size: 12px; display: inline-block;
      }}
      /* Mini-Header in Cards */
      .card h4 {{ margin: 0 0 8px 0; font-weight:700; }}
    </style>
    """, unsafe_allow_html=True)

def header_block(title="Dashboard User", subtitle=""):
    left, right = st.columns([0.7, 0.3])
    with left:
        st.markdown(f"## {title}")
        if subtitle:
            st.caption(subtitle)
    with right:
        st.markdown(
            f"""
            <div class="card" style="text-align:right;">
              <div style="font-size:13px;color:{MUTED};">Letztes Update</div>
              <div style="font-weight:800;font-size:18px;color:{DARK};">{datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
            </div>
            """, unsafe_allow_html=True
        )

def apply_fig_style(fig, title=None, height=300):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        colorway=COLORWAY,
        title=title,
        height=height,
        margin=dict(t=48, l=16, r=16, b=16),
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def card_start(title=None, right_badge=None):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if title or right_badge:
        cols = st.columns([0.8, 0.2])
        with cols[0]:
            if title: st.markdown(f"#### {title}")
        with cols[1]:
            if right_badge: st.markdown(f'<span class="pill">{right_badge}</span>', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)
