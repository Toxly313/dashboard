from datetime import datetime
import streamlit as st

# Farben
PURPLE="#7C3AED"; TEAL="#14B8A6"; ACCENT="#F59E0B"
BG="#F7F8FC"; WHITE="#FFFFFF"; BORDER="#E6EAF2"; TEXT="#0F172A"; MUTED="#667085"

def inject_css():
    st.markdown(f"""
    <style>
      .stApp {{ background:{BG}; }}
      html, body, [class*="css"] {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial !important; }}
      section[data-testid="stSidebar"] {{ background:{WHITE}; border-right:1px solid {BORDER}; }}
      .side-card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:16px; padding:16px; box-shadow:0 1px 2px rgba(16,24,40,.05); margin-bottom:12px; }}
      .card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:16px; padding:16px; box-shadow:0 1px 2px rgba(16,24,40,.05); margin-bottom:14px; }}
      .card h4 {{ margin:0 0 8px 0; font-weight:700; }}
      div[data-testid="stMetricValue"] {{ font-weight:800; }}
      div[data-testid="stMetricDelta"] {{ font-weight:600; }}
      .pill {{ background:{PURPLE}12; color:{PURPLE}; border:1px solid {PURPLE}33; border-radius:999px; padding:2px 10px; font-size:12px; display:inline-block; }}
      .pill-alt {{ background:{TEAL}12; color:{TEAL}; border:1px solid {TEAL}33; border-radius:999px; padding:2px 10px; font-size:12px; display:inline-block; }}
      .kpi-good  {{ border-left: 6px solid #16A34A; padding-left: 10px; }}
      .kpi-warn  {{ border-left: 6px solid #F59E0B; padding-left: 10px; }}
      .kpi-bad   {{ border-left: 6px solid #EF4444; padding-left: 10px; }}
    </style>
    """, unsafe_allow_html=True)

def header_bar(title="Overview", subtitle="Self-Storage KPIs & Trends"):
    left, right = st.columns([0.72, 0.28])
    with left:
        st.markdown(f"### {title}")
        st.caption(subtitle)
    with right:
        st.markdown(f"""
        <div class="card" style="text-align:right;">
          <div style="font-size:12px;color:{MUTED}">Last update</div>
          <div style="font-weight:800;font-size:16px;color:{TEXT}">
            {datetime.now().strftime('%d.%m.%Y %H:%M')}
          </div>
        </div>
        """, unsafe_allow_html=True)

def card_start(title=None, right_pill=None, alt=False):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if title or right_pill:
        c1, c2 = st.columns([0.78, 0.22])
        with c1:
            if title: st.markdown(f"#### {title}")
        with c2:
            if right_pill:
                klass = "pill-alt" if alt else "pill"
                st.markdown(f'<div style="text-align:right;"><span class="{klass}">{right_pill}</span></div>', unsafe_allow_html=True)

def card_end(): st.markdown('</div>', unsafe_allow_html=True)

def kpi_container_start(state="neutral"):
    klass = dict(good="kpi-good", warn="kpi-warn", bad="kpi-bad").get(state, "")
    st.markdown(f'<div class="card {klass}">', unsafe_allow_html=True)

def kpi_container_end(): st.markdown('</div>', unsafe_allow_html=True)

def style_fig(fig, title=None, h=300):
    fig.update_layout(
        template="plotly_white",
        colorway=[PURPLE, TEAL, ACCENT, "#22C55E", "#0EA5E9", "#EF4444"],
        title=title, height=h, margin=dict(t=48, l=16, r=16, b=16),
        font=dict(family="Inter, system-ui, Segoe UI, Roboto, Ubuntu, Arial", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    ); return fig
