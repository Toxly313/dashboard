import streamlit as st
from ..charts import occ_chart, pay_chart, source_chart

def render(prev, cur):
    st.subheader("Start – Überblick")
    # Drei Kernplots mit eindeutigen keys
    fig_occ, k1 = occ_chart(prev, cur)
    fig_pay, k2 = pay_chart(prev, cur)
    fig_src, k3 = source_chart(prev, cur)

    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(fig_occ, use_container_width=True, key=k1)
        st.plotly_chart(fig_src, use_container_width=True, key=k3)
    with col_r:
        st.plotly_chart(fig_pay, use_container_width=True, key=k2)
