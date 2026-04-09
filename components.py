import streamlit as st

def kpi_deck(items: list[dict]):
    """Zeigt KPIs in einer gleichmäßigen Spaltenverteilung."""
    if not items:
        return
    cols = st.columns(len(items))
    for i, it in enumerate(items):
        with cols[i]:
            st.metric(
                label=it.get("label", ""),
                value=it.get("value", ""),
                delta=it.get("delta", ""),
                delta_color=it.get("delta_color", "normal")
            )
