from datetime import datetime
import streamlit as st

# ========== FARBSYSTEM ==========
PURPLE = "#7C3AED"
PURPLE_LIGHT = "#F5F3FF"
TEAL = "#14B8A6"
TEAL_LIGHT = "#ECFDF5"
ACCENT = "#F59E0B"
ACCENT_LIGHT = "#FFFBEB"

BG = "#F4F6FA"           # Hellerer, wärmerer Hintergrund
WHITE = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
MUTED = "#64748B"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

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
        background: {WHITE};
        border-right: 1px solid {BORDER};
      }}
      section[data-testid="stSidebar"] .stMarkdown {{
        color: {TEXT};
      }}
      .side-card {{
        background: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 20px;
        padding: 20px 16px;
        box-shadow: 0 4px 6px -2px rgba(0, 0, 0, 0.03), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
        margin-bottom: 16px;
      }}

      /* Navigation (Radio) */
      section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        display: block;
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 10px 14px;
        margin-bottom: 8px;
        background: {WHITE};
        transition: all 0.15s ease;
        font-weight: 500;
      }}
      section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
        border-color: {PURPLE};
        background: {PURPLE_LIGHT};
      }}
      section[data-testid="stSidebar"] div[role="radiogroup"] input:checked + div {{
        background: {PURPLE_LIGHT};
        border-color: {PURPLE};
        color: {PURPLE};
      }}

      /* ===== KARTEN / KPIs ===== */
      .card {{
        background: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 20px;
        padding: 20px 18px;
        box-shadow: 0 8px 12px -6px rgba(0, 0, 0, 0.04), 0 2px 4px -2px rgba(0, 0, 0, 0.02);
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
        background: {PURPLE_LIGHT};
        color: {PURPLE};
        border: 1px solid {PURPLE}33;
        border-radius: 999px;
        padding: 4px 12px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
      }}
      .pill-alt {{
        background: {TEAL_LIGHT};
        color: {TEAL};
        border: 1px solid {TEAL}33;
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
        border: 2px dashed {PURPLE};
        border-radius: 24px;
        background: {PURPLE_LIGHT};
        padding: 28px 20px;
        text-align: center;
        transition: all 0.2s;
      }}
      .dropzone:hover {{
        background: #EDE9FE;
        border-color: {PURPLE};
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
      }}
      .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 8px 12px -4px rgba(124, 58, 237, 0.2);
      }}

      /* Expander */
      .streamlit-expanderHeader {{
        font-weight: 600;
        color: {TEXT};
      }}

      /* Dataframe */
      .stDataFrame {{
        border-radius: 16px;
        border: 1px solid {BORDER};
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
    """Einheitliches Styling für alle Plotly-Charts."""
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=WHITE,          # Weißer Hintergrund für die gesamte Grafik
        plot_bgcolor='#FAFBFC',       # Leicht grauer Plot-Hintergrund für Kontrast
        colorway=[PURPLE, TEAL, ACCENT, "#22C55E", "#0EA5E9", "#EF4444"],
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
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor=BORDER,
            borderwidth=1
        ),
        xaxis=dict(
            gridcolor='#E6EAF2',
            linecolor='#CBD5E1',
            title_font=dict(size=13, color=MUTED)
        ),
        yaxis=dict(
            gridcolor='#E6EAF2',
            linecolor='#CBD5E1',
            title_font=dict(size=13, color=MUTED)
        )
    )
    return fig
