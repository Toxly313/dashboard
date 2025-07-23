import streamlit as st
import json
import plotly.graph_objects as go

st.set_page_config(page_title="Self-Storage Dashboard", layout="wide")
st.title("📦 Shurgard Self‑Storage Business Dashboard")
st.caption("Nalepastraße 162 – Lagerräume mit Business-Center  \nwww.schimmel-automobile.de")

# --- Daten einlesen ---
try:
    with open('dashboard_summary.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    st.error(f"Fehler beim Laden der Dashboard-Daten: {e}")
    st.stop()

# --- KPI Kacheln ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Belegte Einheiten", data.get("belegt", 0))
col2.metric("Freie Einheiten", data.get("frei", 0))
col3.metric("Ø Vertragsdauer (Monate)", round(data.get("vertragsdauer_durchschnitt", 0), 1))
col4.metric("Auto-Reminder gesendet", data.get("reminder_automat", 0))

# --- Social Media Stats & Weitere KPIs ---
col5, col6, col7, col8 = st.columns(4)
col5.metric("Facebook-Follower", data.get("social_facebook", 0))
col6.metric("Google Reviews", data.get("social_google", 0))
col7.metric("Ø Belegungsgrad (%)", data.get("belegungsgrad", 0))
col8.metric("Empfehlungsrate (%)", round(
    100 * data.get("kundenherkunft", {}).get("Empfehlung", 0) / max((data.get("belegt", 1) + data.get("frei", 0)), 1), 1)
)

# --- Auslastung Pie ---
auslastung_fig = go.Figure(data=[
    go.Pie(
        labels=["Belegt", "Frei"],
        values=[data.get("belegt", 0), data.get("frei", 0)],
        hole=.5,
        marker_colors=["royalblue", "lightgray"]
    )
])
auslastung_fig.update_layout(
    title="Auslastung Lagerräume",
    showlegend=True
)

# --- Neukundenentwicklung ---
kunden_fig = go.Figure(data=[
    go.Bar(
        x=data.get("neukunden_labels", []),
        y=data.get("neukunden_monat", []),
        marker_color="orange"
    )
])
kunden_fig.update_layout(
    title="Neukunden pro Monat",
    xaxis_title="Monat",
    yaxis_title="Neukunden"
)

# --- Zahlungsstatus ---
zahlungsstatus = data.get("zahlungsstatus", {})
zahlung_fig = go.Figure(data=[
    go.Bar(
        x=["Bezahlt", "Offen", "Überfällig"],
        y=[zahlungsstatus.get("bezahlt", 0), zahlungsstatus.get("offen", 0), zahlungsstatus.get("überfällig", 0)],
        marker_color=["seagreen", "gold", "crimson"]
    )
])
zahlung_fig.update_layout(
    title="Zahlungsstatus",
    yaxis_title="Anzahl Rechnungen"
)

# --- Kundenherkunft ---
kundenherkunft = data.get("kundenherkunft", {})
herkunft_fig = go.Figure(data=[
    go.Pie(
        labels=list(kundenherkunft.keys()),
        values=list(kundenherkunft.values()),
        hole=.4,
        marker_colors=["deepskyblue", "orange", "lightgreen"]
    )
])
herkunft_fig.update_layout(
    title="Kundenherkunft",
    showlegend=True
)

# --- Dashboard Layout ---
col9, col10 = st.columns(2)
with col9:
    st.plotly_chart(auslastung_fig, use_container_width=True)
    st.plotly_chart(kunden_fig, use_container_width=True)
with col10:
    st.plotly_chart(zahlung_fig, use_container_width=True)
    st.plotly_chart(herkunft_fig, use_container_width=True)

st.caption("Daten werden automatisch nach jedem n8n-Workflow aktualisiert. Kontakt: info@schimmel-automobile.de")
