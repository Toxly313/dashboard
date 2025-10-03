# components.py
import streamlit as st
from ui_theme import PURPLE, TEAL, WHITE, BORDER

def sidebar_nav():
    with st.sidebar:
        st.markdown("### ")
        st.markdown(f"""
        <div class="side-card" style="text-align:left;">
          <a style="display:inline-block;background:{PURPLE};color:white;padding:10px 12px;border-radius:10px;text-decoration:none;">Register patient</a>
          <div style="height:12px;"></div>
          <ul style="list-style:none;padding-left:0;line-height:1.9;margin:0;">
            <li>Patients</li>
            <li><b>Overview</b></li>
            <li>Map</li>
            <li>Departments</li>
            <li>Doctors</li>
            <li>History</li>
            <li>Settings</li>
          </ul>
        </div>
        """, unsafe_allow_html=True)

def kpi_row(items):
    cols = st.columns(len(items))
    for i, it in enumerate(items):
        with cols[i]:
            st.metric(it["label"], it["value"], delta=it.get("delta",""))

def highlight_card(title, big_value, sublabel="This month", sparkline=None):
    st.markdown(f"""
    <div class="card" style="background:linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%); color:white;">
      <div style="font-size:14px;opacity:.9">{sublabel}</div>
      <div style="font-weight:900;font-size:36px;line-height:1.1;margin-top:6px;">{big_value}</div>
      <div style="font-weight:700;font-size:15px;margin-top:2px;">{title}</div>
    </div>
    """, unsafe_allow_html=True)
    if sparkline is not None:
        st.plotly_chart(sparkline, use_container_width=True)
