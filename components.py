# components.py
import streamlit as st
from ui_theme import ORANGE, WHITE

def sidebar_profile(name="JOHN DON", email="johndon@company.com", avatar_emoji="👤"):
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-card" style="text-align:center;">
              <div style="font-size:46px;line-height:1.1;">{avatar_emoji}</div>
              <div style="font-weight:800;letter-spacing:.4px;margin-top:6px;">{name}</div>
              <div style="font-size:13px;opacity:.85;">{email}</div>
            </div>
            """, unsafe_allow_html=True
        )
        st.markdown("### ")
        st.markdown("**Navigation**")
        st.markdown("- home\n- file\n- messages\n- notification\n- location\n- graph")

def kpi_grid(items):
    """
    items: list of dicts {label, value, delta_text, icon (optional)}
    """
    cols = st.columns(len(items))
    for i, it in enumerate(items):
        with cols[i]:
            st.metric(
                label=(it.get("icon","") + " " + it["label"]).strip(),
                value=it["value"],
                delta=it.get("delta_text","")
            )
