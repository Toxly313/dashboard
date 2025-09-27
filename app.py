import streamlit as st
import requests
import uuid
import time
import os
import json
import base64
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# Konfiguration
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "https://tundtelectronics.app.n8n.cloud/webhook-test/process-business-data")
DEFAULT_DATA = {
    "belegt": 15,
    "frei": 5,
    "vertragsdauer_durchschnitt": 6.5,
    "reminder_automat": 12,
    "social_facebook": 250,
    "social_google": 45,
    "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [3, 5, 2, 4, 6, 5],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1}
}

# Dashboard Initialisierung
st.set_page_config(page_title="Self-Storage Dashboard", layout="wide")
st.title("📦 Shurgard Self‑Storage Business Dashboard")
st.caption("Nalepastraße 162 – Lagerräume mit Business-Center  \nwww.schimmel-automobile.de")

# Debug Mode in Sidebar
st.sidebar.title("🔧 Debug-Optionen")
DEBUG_MODE = st.sidebar.checkbox("Debug-Modus aktivieren", value=False)
SHOW_RAW_DATA = st.sidebar.checkbox("Rohdaten anzeigen", value=False)

# Session State für Daten initialisieren
if 'data' not in st.session_state:
    st.session_state.data = DEFAULT_DATA
if 'last_upload' not in st.session_state:
    st.session_state.last_upload = None
if 'processing' not in st.session_state:
    st.session_state.processing = False

# Drag & Drop Upload mit KI-Verarbeitung
uploaded_file = st.file_uploader(
    "Geschäftsdaten hochladen (Daten werden nicht gespeichert)",
    type=["csv", "json", "xlsx"],
    help="Ziehen Sie Ihre Geschäftsdaten hierher oder klicken Sie zum Durchsuchen"
)

# Verarbeite Datei wenn hochgeladen
if uploaded_file and uploaded_file != st.session_state.last_upload:
    st.session_state.processing = True
    st.session_state.last_upload = uploaded_file
    
    with st.spinner("🤖 KI verarbeitet Daten datenschutzkonform..."):
        try:
            session_id = str(uuid.uuid4())
            
            if DEBUG_MODE:
                st.sidebar.info("🔍 **Debug-Informationen:**")
                st.sidebar.write(f"📁 Dateiname: `{uploaded_file.name}`")
                st.sidebar.write(f"📊 Dateigröße: `{uploaded_file.size} bytes`")
                st.sidebar.write(f"🌐 n8n URL: `{N8N_WEBHOOK_URL}`")
                st.sidebar.write(f"🆔 Session ID: `{session_id}`")
            
            # Datei vorbereiten
            file_data = uploaded_file.getvalue()
            
            # Versuch 1: Standard multipart/form-data
            response = requests.post(
                N8N_WEBHOOK_URL,
                files={"file": (uploaded_file.name, file_data)},
                headers={"X-Session-ID": session_id},
                timeout=60
            )
            
            if DEBUG_MODE:
                st.sidebar.write(f"📡 Response Status: `{response.status_code}`")
                st.sidebar.write(f"⏱️ Response Zeit: `{response.elapsed.total_seconds():.2f}s`")
            
            if response.status_code == 200:
                try:
                    # Response als JSON parsen
                    response_data = response.json()
                    st.session_state.data = response_data
                    st.session_state.processing = False
                    
                    if DEBUG_MODE:
                        st.sidebar.success("✅ Daten erfolgreich empfangen!")
                        st.sidebar.json(response_data, expanded=False)
                    
                    st.success("✅ Daten erfolgreich verarbeitet!")
                    
                    # Zeige KI-Status an
                    if response_data.get('ki_analyse_erfolgreich'):
                        st.info("🤖 KI-Analyse wurde erfolgreich durchgeführt")
                    elif response_data.get('fallback_used'):
                        st.warning("⚠️ Verwende Fallback-Daten (KI nicht verfügbar)")
                    
                except json.JSONDecodeError as e:
                    error_msg = f"❌ Ungültiges JSON erhalten: {str(e)}"
                    st.error(error_msg)
                    if DEBUG_MODE:
                        st.sidebar.error(f"Raw Response: `{response.text[:500]}...`")
                    st.session_state.data = DEFAULT_DATA
                    st.session_state.processing = False
            else:
                error_msg = f"❌ Fehler von n8n: Status {response.status_code}"
                st.error(error_msg)
                if DEBUG_MODE:
                    st.sidebar.error(f"Fehlerantwort: `{response.text}`")
                st.session_state.data = DEFAULT_DATA
                st.session_state.processing = False
                
        except Exception as e:
            error_msg = f"❌ Systemfehler: {str(e)}"
            st.error(error_msg)
            if DEBUG_MODE:
                st.sidebar.exception(e)
            st.session_state.data = DEFAULT_DATA
            st.session_state.processing = False

# Zeige Verarbeitungsstatus an
if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet...")

# Verwende die aktuellen Daten (entweder aus Session oder Default)
data = st.session_state.data

# Zeige Rohdaten an wenn gewünscht
if SHOW_RAW_DATA:
    with st.expander("📋 Rohdaten anzeigen", expanded=False):
        st.json(data)

# --- Dashboard Visualisierungen ---
def display_dashboard(data):
    # Debug: Prüfe ob Daten vorhanden sind
    if DEBUG_MODE and not data:
        st.warning("⚠️ Keine Daten für Dashboard verfügbar")
        return
    
    # --- KPI Kacheln ---
    st.subheader("📊 Key Performance Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        value = data.get("belegt", 0)
        delta = value - DEFAULT_DATA["belegt"] if value != DEFAULT_DATA["belegt"] else None
        st.metric("Belegte Einheiten", value, delta=delta)
    
    with col2:
        value = data.get("frei", 0)
        delta = value - DEFAULT_DATA["frei"] if value != DEFAULT_DATA["frei"] else None
        st.metric("Freie Einheiten", value, delta=delta)
    
    with col3:
        value = round(data.get("vertragsdauer_durchschnitt", 0), 1)
        delta = value - DEFAULT_DATA["vertragsdauer_durchschnitt"] if value != DEFAULT_DATA["vertragsdauer_durchschnitt"] else None
        st.metric("Ø Vertragsdauer (Monate)", value, delta=delta)
    
    with col4:
        value = data.get("reminder_automat", 0)
        delta = value - DEFAULT_DATA["reminder_automat"] if value != DEFAULT_DATA["reminder_automat"] else None
        st.metric("Auto-Reminder gesendet", value, delta=delta)

    # --- Social Media Stats & Weitere KPIs ---
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        value = data.get("social_facebook", 0)
        delta = value - DEFAULT_DATA["social_facebook"] if value != DEFAULT_DATA["social_facebook"] else None
        st.metric("Facebook-Follower", value, delta=delta)
    
    with col6:
        value = data.get("social_google", 0)
        delta = value - DEFAULT_DATA["social_google"] if value != DEFAULT_DATA["social_google"] else None
        st.metric("Google Reviews", value, delta=delta)
    
    with col7:
        value = data.get("belegungsgrad", 0)
        delta = value - DEFAULT_DATA["belegungsgrad"] if value != DEFAULT_DATA["belegungsgrad"] else None
        st.metric("Ø Belegungsgrad (%)", value, delta=delta)

    with col8:
        # Empfehlungsrate berechnen
        kundenherkunft = data.get("kundenherkunft", {})
        empfehlungen = kundenherkunft.get("Empfehlung", 0)
        total_kunden = max(sum(kundenherkunft.values()), 1)
        empfehlungsrate = round(100 * empfehlungen / total_kunden, 1)
        
        # Vergleichswert aus Default-Daten
        default_herkunft = DEFAULT_DATA.get("kundenherkunft", {})
        default_empfehlungen = default_herkunft.get("Empfehlung", 0)
        default_total = max(sum(default_herkunft.values()), 1)
        default_rate = round(100 * default_empfehlungen / default_total, 1)
        
        delta = empfehlungsrate - default_rate if empfehlungsrate != default_rate else None
        st.metric("Empfehlungsrate (%)", empfehlungsrate, delta=delta)

    # --- Diagramme ---
    st.subheader("📈 Visualisierungen")
    
    # Auslastung Pie Chart
    try:
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
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"Fehler beim Erstellen des Auslastungsdiagramms: {e}")

    # Neukundenentwicklung
    try:
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
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"Fehler beim Erstellen des Neukundendiagramms: {e}")

    # Zahlungsstatus
    try:
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
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"Fehler beim Erstellen des Zahlungsstatusdiagramms: {e}")

    # Kundenherkunft
    try:
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
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"Fehler beim Erstellen des Kundenherkunftsdiagramms: {e}")

    # --- Dashboard Layout ---
    col_left, col_right = st.columns(2)
    
    with col_left:
        if 'auslastung_fig' in locals():
            st.plotly_chart(auslastung_fig, use_container_width=True)
        if 'kunden_fig' in locals():
            st.plotly_chart(kunden_fig, use_container_width=True)
    
    with col_right:
        if 'zahlung_fig' in locals():
            st.plotly_chart(zahlung_fig, use_container_width=True)
        if 'herkunft_fig' in locals():
            st.plotly_chart(herkunft_fig, use_container_width=True)

# Zeige Dashboard mit aktuellen Daten
display_dashboard(data)

# System-Info in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ System-Information")
st.sidebar.write(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.write(f"Datenquelle: n8n Workflow")
st.sidebar.write(f"Workflow Status: {'Bereit' if not st.session_state.processing else 'Verarbeitung läuft'}")

# --- Reset-Button für Daten ---
if st.button("🔄 Daten zurücksetzen"):
    st.session_state.data = DEFAULT_DATA
    st.session_state.last_upload = None
    st.rerun()

# --- Footer ---
st.markdown("---")
st.caption(f"""
Daten werden datenschutzkonform verarbeitet - Keine Speicherung personenbezogener Daten | 
Kontakt: info@schimmel-automobile.de | 
Aktualisiert: {datetime.now().strftime('%d.%m.%Y %H:%M')} | 
n8n Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}
""")
