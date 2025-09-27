import streamlit as st
import requests
import uuid
import time
import os
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# Konfiguration
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "https://tundtelectronics.app.n8n.cloud/webhook-test/process-business-data")
DEFAULT_DATA = {
    "belegt": 0,
    "frei": 0,
    "vertragsdauer_durchschnitt": 0,
    "reminder_automat": 0,
    "social_facebook": 0,
    "social_google": 0,
    "belegungsgrad": 0,
    "kundenherkunft": {},
    "neukunden_labels": [],
    "neukunden_monat": [],
    "zahlungsstatus": {}
}

# Dashboard Initialisierung
st.set_page_config(page_title="Self-Storage Dashboard", layout="wide")
st.title("📦 Shurgard Self‑Storage Business Dashboard")
st.caption("Nalepastraße 162 – Lagerräume mit Business-Center  \nwww.schimmel-automobile.de")

# Session State für Daten initialisieren
if 'data' not in st.session_state:
    st.session_state.data = DEFAULT_DATA

# Drag & Drop Upload mit KI-Verarbeitung
uploaded_file = st.file_uploader(
    "Geschäftsdaten hochladen (Daten werden nicht gespeichert)",
    type=["csv", "json", "xlsx"],
    help="Ziehen Sie Ihre Geschäftsdaten hierher oder klicken Sie zum Durchsuchen"
)

# Verarbeite Datei wenn hochgeladen
if uploaded_file:
    with st.spinner("KI verarbeitet Daten datenschutzkonform..."):
        try:
            session_id = str(uuid.uuid4())
            
            # Debug-Ausgabe
            st.write(f"📤 Sende Datei an n8n...")
            
            # Datei vorbereiten
            file_data = uploaded_file.getvalue()
            
            # Mehrere Versuche mit verschiedenen Content-Types
            try:
                # Versuch 1: Standard multipart/form-data
                response = requests.post(
                    N8N_WEBHOOK_URL,
                    files={"file": (uploaded_file.name, file_data)},
                    headers={"X-Session-ID": session_id},
                    timeout=30
                )
            except:
                # Versuch 2: Einfacher JSON Upload
                response = requests.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "fileName": uploaded_file.name,
                        "file": base64.b64encode(file_data).decode('utf-8')
                    },
                    timeout=30
                )

            # Response validieren
            st.write(f"📥 Antwort erhalten: Status {response.status_code}")
            
            if response.status_code == 200:
                try:
                    # Response als JSON parsen
                    response_data = response.json()
                    st.session_state.data = response_data
                    st.success("✅ Daten erfolgreich verarbeitet!")
                    
                    # Debug: Zeige empfangene Daten
                    st.write("📊 Empfangene Daten:", response_data)
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ Ungültiges JSON erhalten: {response.text}")
                    # Fallback-Daten verwenden
                    st.session_state.data = DEFAULT_DATA
            else:
                st.error(f"❌ Fehler von n8n: Status {response.status_code}")
                st.write(f"Antwort-Text: {response.text}")
                # Fallback-Daten verwenden
                st.session_state.data = DEFAULT_DATA
                
        except Exception as e:
            st.error(f"❌ Systemfehler: {str(e)}")
            # Fallback-Daten verwenden
            st.session_state.data = DEFAULT_DATA

# Verwende die aktuellen Daten (entweder aus Session oder Default)
data = st.session_state.data

# --- Dashboard Visualisierungen ---
def display_dashboard(data):
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

    # Empfehlungsrate berechnen
    kundenherkunft = data.get("kundenherkunft", {})
    empfehlungen = kundenherkunft.get("Empfehlung", 0)
    total_kunden = max(sum(kundenherkunft.values()), 1)  # Division durch Null verhindern
    col8.metric("Empfehlungsrate (%)", round(100 * empfehlungen / total_kunden, 1))

    # --- Auslastung Pie Chart ---
    auslastung_fig = go.Figure(data=[
        go.Pie(
            labels=["Belegt", "Frei"],
            values=[data.get("belegt", 0), data.get("frei", 0)],
            hole=.5,
            marker_colors=["#1f77b4", "#d3d3d3"],
            textinfo="percent+value"
        )
    ])
    auslastung_fig.update_layout(
        title="Auslastung Lagerräume",
        showlegend=True,
        margin=dict(t=40, b=20),
        height=300
    )

    # --- Neukundenentwicklung ---
    kunden_fig = go.Figure(data=[
        go.Bar(
            x=data.get("neukunden_labels", []),
            y=data.get("neukunden_monat", []),
            marker_color="#ff7f0e",
            textposition="auto"
        )
    ])
    kunden_fig.update_layout(
        title="Neukunden pro Monat",
        xaxis_title="Monat",
        yaxis_title="Neukunden",
        margin=dict(t=40, b=40),
        height=300
    )

    # --- Zahlungsstatus ---
    zahlungsstatus = data.get("zahlungsstatus", {})
    zahlung_fig = go.Figure(data=[
        go.Bar(
            x=["Bezahlt", "Offen", "Überfällig"],
            y=[
                zahlungsstatus.get("bezahlt", 0),
                zahlungsstatus.get("offen", 0),
                zahlungsstatus.get("überfällig", 0)
            ],
            marker_color=["#2ca02c", "#ffd700", "#d62728"],
            textposition="auto"
        )
    ])
    zahlung_fig.update_layout(
        title="Zahlungsstatus",
        yaxis_title="Anzahl Rechnungen",
        margin=dict(t=40, b=20),
        height=300
    )

    # --- Kundenherkunft ---
    kundenherkunft = data.get("kundenherkunft", {})
    if kundenherkunft:
        herkunft_fig = go.Figure(data=[
            go.Pie(
                labels=list(kundenherkunft.keys()),
                values=list(kundenherkunft.values()),
                hole=.4,
                textinfo="percent+label",
                marker_colors=px.colors.qualitative.Pastel
            )
        ])
    else:
        herkunft_fig = go.Figure()
        herkunft_fig.add_annotation(
            text="Keine Daten verfügbar",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
    
    herkunft_fig.update_layout(
        title="Kundenherkunft",
        showlegend=False,
        margin=dict(t=40, b=20),
        height=350
    )

    # --- Dashboard Layout ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.plotly_chart(auslastung_fig, use_container_width=True)
        st.plotly_chart(kunden_fig, use_container_width=True)
    
    with col_right:
        st.plotly_chart(zahlung_fig, use_container_width=True)
        st.plotly_chart(herkunft_fig, use_container_width=True)

# Zeige Dashboard mit aktuellen Daten
display_dashboard(data)

# --- Reset-Button für Daten ---
if st.button("Daten zurücksetzen"):
    st.session_state.data = DEFAULT_DATA
    st.rerun()

# --- Footer ---
st.caption(f"""
Daten werden datenschutzkonform verarbeitet - Keine Speicherung personenbezogener Daten | 
Kontakt: info@schimmel-automobile.de | 
Aktualisiert: {datetime.now().strftime('%B %Y')}
""")
