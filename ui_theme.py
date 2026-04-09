from datetime import datetime
import streamlit as st

# ========== DARK BLUE COLOR SYSTEM ==========
PRIMARY = "#3B82F6"          # Klares Blau für Akzente
PRIMARY_LIGHT = "#1E3A8A"    # Dunkleres Blau für Hintergründe
SECONDARY = "#8B5CF6"        # Lila als Zweitfarbe
ACCENT = "#F59E0B"           # Orange für Highlights
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

BG = "#0B1120"               # Tiefer, dunkler Hintergrund
CARD_BG = "#1E293B"          # Dunkelgrau‑Blau für Karten
SIDEBAR_BG = "#0F172A"       # Noch dunkler für Sidebar
BORDER = "#334155"           # Dezente Border
TEXT = "#F1F5F9"             # Helles Grau für Text
MUTED = "#94A3B8"            # Gedimmter Text
PLOT_BG = "#1E293B"          # Hintergrund für Plotly‑Charts

def inject_css():
    st.markdown(f"""
    <style>
      /* ===== GLOBAL ===== */
      .stApp {{
        background: {BG};
      }}
      html, body, [class*="css"] {{
        font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Arial, sans-serif !important;
        color: {TEXT};
      }}

      /* ===== SIDEBAR ===== */
      section[data-testid="stSidebar"] {{
        background: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
      }}
      section[data-testid="stSidebar"] .stMarkdown {{
        color: {TEXT} !important;
      }}
      section[data-testid="stSidebar"] input {{
        background: {CARD_BG} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
      }}
      .side-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 20px;
        padding: 20px 16px;
        box-shadow: 0 4px 6px -2px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
      }}

      /* Navigation (Radio) */
      section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        display: block;
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 10px 14px;
        margin-bottom: 8px;
        background: {CARD_BG};
        transition: all 0.15s ease;
        font-weight: 500;
        color: {MUTED};
      }}
      section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
        border-color: {PRIMARY};
        background: #1E293B;
        color: {TEXT};
      }}
      section[data-testid="stSidebar"] div[role="radiogroup"] input:checked + div {{
        background: {PRIMARY_LIGHT};
        border-color: {PRIMARY};
        color: {TEXT};
      }}

      /* ===== KARTEN / KPIs ===== */
      .card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 20px;
        padding: 20px 18px;
        box-shadow: 0 8px 12px -6px rgba(0, 0, 0, 0.4);
        margin-bottom: 20px;
      }}
      .card h4 {{
        margin: 0 0 12px 0;
        font-weight: 700;
        font-size: 18px;
        color: {TEXT};
      }}

      /* Metric-Werte */
      div[data-testid="stMetricValue"] {{
        font-weight: 800;
        font-size: 32px !important;
        color: {TEXT};
      }}
      div[data-testid="stMetricDelta"] {{
        font-weight: 600;
        font-size: 16px;
      }}
      div[data-testid="stMetricLabel"] {{
        font-weight: 500;
        color: {MUTED};
        font-size: 14px;
      }}

      /* Pills */
      .pill {{
        background: {PRIMARY_LIGHT};
        color: {PRIMARY};
        border: 1px solid {PRIMARY}33;
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
      }}
      .pill-alt {{
        background: #312E81;
        color: #A78BFA;
        border: 1px solid #8B5CF633;
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
      }}

      /* KPI Status Borders */
      .kpi-good  {{ border-left: 6px solid {SUCCESS}; padding-left: 14px; }}
      .kpi-warn  {{ border-left: 6px solid {WARNING}; padding-left: 14px; }}
      .kpi-bad   {{ border-left: 6px solid {DANGER}; padding-left: 14px; }}

      /* Drag & Drop Zone */
      .dropzone {{
        border: 2px dashed {PRIMARY};
        border-radius: 24px;
        background: {PRIMARY_LIGHT}22;
        padding: 28px 20px;
        text-align: center;
        transition: all 0.2s;
      }}
      .dropzone:hover {{
        background: {PRIMARY_LIGHT}44;
        border-color: {PRIMARY};
      }}
      .dropzone h4 {{
        margin: 8px 0 4px 0;
        font-weight: 700;
        color: {TEXT};
      }}
      .dropzone p {{
        margin: 0;
        color: {MUTED};
        font-size: 14px;
      }}

      /* Buttons */
      .stButton > button {{
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 10px 18px !important;
        transition: all 0.15s;
        background: {PRIMARY} !important;
        color: white !important;
        border: none !important;
      }}
      .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 8px 12px -4px {PRIMARY}66;
        background: #2563EB !important;
      }}

      /* Expander */
      .streamlit-expanderHeader {{
        font-weight: 600;
        color: {TEXT};
        background: {CARD_BG};
        border-radius: 12px;
      }}

      /* Dataframe */
      .stDataFrame {{
        border-radius: 16px;
        border: 1px solid {BORDER};
        background: {CARD_BG};
      }}

      /* Inputs */
      .stTextInput > div > div > input {{
        background: {CARD_BG};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 12px;
      }}
      .stSelectbox > div > div {{
        background: {CARD_BG};
        color: {TEXT};
      }}
    </style>
    """, unsafe_allow_html=True)

def header_bar(title="Overview", subtitle="Self-Storage KPIs & Trends"):
    left, right = st.columns([0.72, 0.28])
    with left:
        st.markdown(f"### {title}")
        st.caption(subtitle)
    with right:
        st.markdown(f"""
        <div class="card" style="text-align:right; padding: 14px 20px;">
          <div style="font-size:13px; color:{MUTED};">Letztes Update</div>
          <div style="font-weight:800; font-size:18px; color:{TEXT};">
            {datetime.now().strftime('%d.%m.%Y %H:%M')}
          </div>
        </div>
        """, unsafe_allow_html=True)

def card_start(title=None, right_pill=None, alt=False):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if title or right_pill:
        c1, c2 = st.columns([0.78, 0.22])
        with c1:
            if title:
                st.markdown(f"#### {title}")
        with c2:
            if right_pill:
                klass = "pill-alt" if alt else "pill"
                st.markdown(f'<div style="text-align:right;"><span class="{klass}">{right_pill}</span></div>', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)

def kpi_container_start(state="neutral"):
    klass = {"good": "kpi-good", "warn": "kpi-warn", "bad": "kpi-bad"}.get(state, "")
    st.markdown(f'<div class="card {klass}">', unsafe_allow_html=True)

def kpi_container_end():
    st.markdown('</div>', unsafe_allow_html=True)

def style_fig(fig, title=None, h=320):
    """Dunkles Plotly‑Theme passend zum Dashboard."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CARD_BG,
        plot_bgcolor=PLOT_BG,
        colorway=[PRIMARY, SECONDARY, ACCENT, SUCCESS, "#0EA5E9", DANGER],
        title=dict(text=title, font=dict(size=16, color=TEXT)) if title else None,
        height=h,
        margin=dict(t=50 if title else 30, l=20, r=20, b=30),
        font=dict(family="Inter, system-ui, Segoe UI, Roboto, Ubuntu, Arial", size=13, color=TEXT),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(30,41,59,0.8)',
            bordercolor=BORDER,
            borderwidth=1
        ),
        xaxis=dict(
            gridcolor='#334155',
            linecolor='#475569',
            title_font=dict(size=13, color=MUTED)
        ),
        yaxis=dict(
            gridcolor='#334155',
            linecolor='#475569',
            title_font=dict(size=13, color=MUTED)
        )
    )
    return fig
