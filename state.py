import streamlit as st

DEFAULT_DATA = {
    "belegt": 15, "frei": 5, "vertragsdauer_durchschnitt": 6.5,
    "reminder_automat": 12, "social_facebook": 250, "social_google": 45,
    "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Jan","Feb","Mär","Apr","Mai","Jun"],
    "neukunden_monat": [3,5,2,4,6,5],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

def ensure_state():
    if "data" not in st.session_state: st.session_state.data = DEFAULT_DATA.copy()
    if "prev_data" not in st.session_state: st.session_state.prev_data = DEFAULT_DATA.copy()
    if "processing" not in st.session_state: st.session_state.processing = False
    if "history" not in st.session_state: st.session_state.history = []
    if "upload_key" not in st.session_state: st.session_state.upload_key = 0
    if "chart_key_counter" not in st.session_state: st.session_state.chart_key_counter = 0

def next_chart_key(suffix: str) -> str:
    st.session_state.chart_key_counter += 1
    return f"chart_{st.session_state.chart_key_counter}_{suffix}"
