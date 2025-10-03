# ui_theme.py
from datetime import datetime
import streamlit as st

PLOTLY_TEMPLATE = "plotly_white"
COLORWAY = ["#2563EB", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#10B981", "#F97316"]

def inject_base_css():
    st.markdown("""
    <style>
    html, body, [class*="css"]  { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Arial !important; }
    .section-card { padding: 18px 18px 6px 18px; border: 1px solid #E9EEF3; border-radius: 14px;
      background: #fff; box-shadow: 0 1px 2px rgba(16,24,40,0.04); margin-bottom: 12px; }
    div[data-testid="stMetricValue"] { font-weight: 700; }
    div[data-testid="stMetricDelta"] { font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

def header_block(subtitle: str = ""):
    left, right = st.columns([0.75, 0.25])
    with left:
        st.markdown("### 📦 Self-Storage Business Dashboard")
        if subtitle:
            st.caption(subtitle)
    with right:
        st.markdown(f"""
        <div class="section-card" style="text-align:right">
          <div style="font-size:13px;color:#667085">Letztes Update</div>
          <div style="font-weight:700;font-size:16px">{datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
        </div>
        """, unsafe_allow_html=True)

def apply_fig_style(fig, title=None, height=320):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        colorway=COLORWAY,
        title=title or None,
        height=height,
        margin=dict(t=50, l=20, r=20, b=40),
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def card_start():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)
