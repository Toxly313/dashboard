import os, uuid, json, time
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import base64

# PORT FIX
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

# KONFIGURATION
st.set_page_config(page_title="Self-Storage Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# TENANT-KONFIGURATION
TENANTS = {
    "demo@kunde.de": {"tenant_id": "kunde_demo_123", "name": "Demo Kunde GmbH", "plan": "pro", "analyses_limit": 50, "analyses_used": 0},
    "test@firma.de": {"tenant_id": "firma_test_456", "name": "Test Firma AG", "plan": "business", "analyses_limit": 200, "analyses_used": 0}
}

# DEFAULT DATEN
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [5, 4, 7, 6, 8, 9],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# HILFSFUNKTIONEN
def post_to_n8n_get_last(base_url, tenant_id, uuid_str):
    """
    Vereinfachte Version - erwartet direktes Business-Daten Format
    """
    print(f"\nGET-LAST Request für Tenant: {tenant_id}")
    
    url = f"{base_url.rstrip('/')}/get-last-analysis-only"
    print(f"GET-LAST URL: {url}")
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "action": "get_last_analysis"
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"GET-LAST Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}", None
        
        try:
            json_response = response.json()
            print(f"GET-LAST JSON erhalten")
            
            # ERWARTETES FORMAT: Direkte Business-Daten
            # {"belegt": 142, "frei": 58, "belegungsgrad": 71, ...}
            if isinstance(json_response, dict) and any(key in json_response for key in ["belegt", "frei", "belegungsgrad"]):
                return json_response, "Success", None
            else:
                return None, "Ungültiges Format - erwarte direkte Business-Daten", json_response
                
        except json.JSONDecodeError:
            return None, "Kein JSON in Response", response.text[:200]
            
    except requests.exceptions.Timeout:
        return None, "Timeout nach 30s", None
    except Exception as e:
        return None, f"Exception: {str(e)}", None

def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
    """
    Vereinfachte Version - erwartet direktes Business-Daten Format
    """
    print(f"\nNEW-ANALYSIS für {tenant_id}")
    
    url = f"{base_url.rstrip('/')}/analyze-with-deepseek"
    print(f"NEW-ANALYSIS URL: {url}")
    
    # Datei vorbereiten
    filename, file_content, file_type = file_info
    base64_content = base64.b64encode(file_content).decode('utf-8')
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "action": "analyze_with_deepseek",
        "file": {
            "filename": filename,
            "content_type": file_type,
            "data": base64_content
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}", response.text[:200]
        
        try:
            json_response = response.json()
            print(f"Response Type: {type(json_response)}")
            
            # ERWARTETES FORMAT: Direkte Business-Daten mit recommendations und customer_message
            if isinstance(json_response, dict) and any(key in json_response for key in ["belegt", "frei", "belegungsgrad"]):
                return json_response, "Success", None
            else:
                return None, "Ungültiges Format - erwarte direkte Business-Daten", json_response
            
        except json.JSONDecodeError:
            return None, "Kein JSON in Response", response.text[:200]
            
    except Exception as e:
        return None, f"Exception: {str(e)}", None

def extract_metrics_from_excel(df):
    metrics = {}
    try:
        if 'belegt' in df.columns: 
            metrics['belegt'] = int(df['belegt'].sum())
        if 'frei' in df.columns: 
            metrics['frei'] = int(df['frei'].sum())
        if 'belegt' in metrics and 'frei' in metrics:
            total = metrics['belegt'] + metrics['frei']
            if total > 0: 
                metrics['belegungsgrad'] = round((metrics['belegt'] / total) * 100, 1)
        for col in ['vertragsdauer_durchschnitt', 'reminder_automat', 'social_facebook', 'social_google']:
            if col in df.columns: 
                metrics[col] = float(df[col].mean())
        herkunft_cols = [c for c in df.columns if 'herkunft' in c.lower()]
        if herkunft_cols:
            herkunft_counts = df[herkunft_cols[0]].value_counts().to_dict()
            metrics['kundenherkunft'] = {
                'Online': herkunft_counts.get('Online', 0), 
                'Empfehlung': herkunft_counts.get('Empfehlung', 0), 
                'Vorbeikommen': herkunft_counts.get('Vorbeikommen', 0)
            }
        status_cols = [c for c in df.columns if 'status' in c.lower()]
        if status_cols:
            status_counts = df[status_cols[0]].value_counts().to_dict()
            metrics['zahlungsstatus'] = {
                'bezahlt': status_counts.get('bezahlt', 0), 
                'offen': status_counts.get('offen', 0), 
                'überfällig': status_counts.get('überfällig', 0)
            }
    except Exception as e: 
        st.warning(f"Excel-Warnung: {str(e)[:80]}")
    return metrics

def merge_data(base_dict, new_dict):
    """Vereinfachte Merge-Funktion"""
    if not new_dict:
        return base_dict.copy() if base_dict else {}
    
    result = base_dict.copy() if base_dict else {}
    
    # Einfache Merge-Logik: Neueste Daten ersetzen ältere
    for key, value in new_dict.items():
        if value is not None:
            result[key] = value
    
    return result

def load_last_analysis():
    """Vereinfachte Version - erwartet direktes Format von n8n"""
    if not st.session_state.logged_in:
        return False

    tenant_id = st.session_state.current_tenant["tenant_id"]
    n8n_base_url = st.session_state.n8n_base_url

    if not n8n_base_url:
        st.warning("n8n Basis-URL nicht gesetzt. Verwende Standarddaten.")
        st.session_state.current_data = DEFAULT_DATA.copy()
        st.session_state.before_analysis = DEFAULT_DATA.copy()
        return True

    with st.spinner("Lade letzte Analyse..."):
        # Rufe n8n auf
        data, message, debug_info = post_to_n8n_get_last(
            n8n_base_url, tenant_id, str(uuid.uuid4())
        )
        
        # Debug-Info
        if st.session_state.debug_mode:
            with st.expander("Debug: GET-LAST Response", expanded=False):
                st.write(f"Message: {message}")
                if data:
                    st.write("Daten:")
                    st.json(data)
                if debug_info:
                    st.write("Debug Info:")
                    st.write(debug_info)
        
        # Fallback bei Fehlern
        if not data:
            st.info(f"⚠️ {message}. Verwende Standarddaten.")
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.before_analysis = DEFAULT_DATA.copy()
            return True
        
        # ====== EINFACHE VERARBEITUNG ======
        # Starte mit DEFAULT_DATA
        loaded_data = DEFAULT_DATA.copy()
        
        # Konvertiere alle Werte sicher
        def safe_convert(value):
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                try:
                    return float(value)
                except:
                    try:
                        return int(value)
                    except:
                        return value
            return value
        
        # Übernehme alle verfügbaren Felder
        for key in DEFAULT_DATA.keys():
            if key in data:
                loaded_data[key] = safe_convert(data[key])
        
        # Spezielle Felder (müssen Dictionaries sein)
        if "kundenherkunft" in data and isinstance(data["kundenherkunft"], dict):
            loaded_data["kundenherkunft"] = data["kundenherkunft"]
        
        if "zahlungsstatus" in data and isinstance(data["zahlungsstatus"], dict):
            loaded_data["zahlungsstatus"] = data["zahlungsstatus"]
        
        # Berechne belegungsgrad falls nötig
        if "belegt" in data and "frei" in data:
            belegt = safe_convert(data["belegt"])
            frei = safe_convert(data["frei"])
            if belegt + frei > 0:
                loaded_data["belegungsgrad"] = round((belegt / (belegt + frei)) * 100, 1)
        
        # Analysis Date
        if "analysis_date" in data:
            loaded_data["analysis_date"] = data["analysis_date"]
        else:
            loaded_data["analysis_date"] = datetime.now().isoformat()
        
        # In Session State speichern
        st.session_state.current_data = loaded_data
        st.session_state.before_analysis = loaded_data.copy()
        st.session_state.last_analysis_loaded = True
        
        st.success(f"✅ Letzte Analyse geladen! Belegungsgrad: {loaded_data['belegungsgrad']}%")
        return True

def perform_analysis(uploaded_files):
    """Vereinfachte Version - erwartet direktes Format von n8n"""
    if not st.session_state.logged_in: 
        st.error("Kein Tenant eingeloggt")
        return
    
    tenant_id = st.session_state.current_tenant['tenant_id']
    tenant_name = st.session_state.current_tenant['name']
    
    # Vorherige Daten speichern für Vergleich
    st.session_state.before_analysis = st.session_state.current_data.copy()
    
    # Excel-Daten extrahieren (Fallback)
    excel_data = {}
    for excel_file in [f for f in uploaded_files if f.name.lower().endswith((".xlsx", ".xls", ".csv"))]:
        try:
            if excel_file.name.endswith('.csv'):
                df = pd.read_csv(excel_file)
            else:
                df = pd.read_excel(excel_file)
            
            excel_metrics = extract_metrics_from_excel(df)
            excel_data = merge_data(excel_data, excel_metrics)
        except Exception as e:
            st.warning(f"Konnte {excel_file.name} nicht lesen: {str(e)[:50]}")
    
    # n8n URL prüfen
    n8n_base_url = st.session_state.n8n_base_url
    if not n8n_base_url:
        st.error("Bitte n8n Basis-URL in der Sidebar eingeben")
        return
    
    # Hauptdatei für n8n vorbereiten
    main_file = uploaded_files[0]
    file_info = (main_file.name, main_file.getvalue(), main_file.type)
    
    # n8n aufrufen
    with st.spinner("KI analysiert Daten..."):
        data, message, debug_info = post_to_n8n_analyze(n8n_base_url, tenant_id, str(uuid.uuid4()), file_info)
    
    # Debug-Info
    if st.session_state.debug_mode:
        with st.expander("Debug: n8n Kommunikation", expanded=False):
            st.write(f"Message: {message}")
            if data:
                st.write("Daten:")
                st.json(data)
            if debug_info:
                st.write("Debug Info:")
                st.write(debug_info)
    
    # ====== EINFACHE VERARBEITUNG ======
    if data:
        # Starte mit Excel-Daten als Basis
        final_data = DEFAULT_DATA.copy()
        
        # Excel-Daten zuerst (Fallback)
        for key, value in excel_data.items():
            if key in final_data:
                final_data[key] = value
        
        # n8n-Daten überschreiben Excel-Daten (n8n hat Priorität)
        def safe_convert(value):
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                try:
                    return float(value)
                except:
                    try:
                        return int(value)
                    except:
                        return value
            return value
        
        for key in DEFAULT_DATA.keys():
            if key in data:
                final_data[key] = safe_convert(data[key])
        
        # Spezielle Felder
        if "kundenherkunft" in data and isinstance(data["kundenherkunft"], dict):
            final_data["kundenherkunft"] = data["kundenherkunft"]
        
        if "zahlungsstatus" in data and isinstance(data["zahlungsstatus"], dict):
            final_data["zahlungsstatus"] = data["zahlungsstatus"]
        
        # Berechne belegungsgrad falls nötig
        if "belegt" in final_data and "frei" in final_data:
            belegt = final_data["belegt"]
            frei = final_data["frei"]
            if belegt + frei > 0:
                final_data["belegungsgrad"] = round((belegt / (belegt + frei)) * 100, 1)
        
        # Empfehlungen und Message
        final_data["recommendations"] = data.get("recommendations", [])
        if not final_data["recommendations"]:
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
        
        final_data["customer_message"] = data.get("customer_message", 
                                                 f"Analyse für {tenant_name} abgeschlossen")
        
        # Metadaten
        final_data["analysis_date"] = data.get("analysis_date", datetime.now().isoformat())
        final_data["tenant_id"] = tenant_id
        final_data["files"] = [f.name for f in uploaded_files]
        
        # In Session State
        st.session_state.after_analysis = final_data.copy()
        st.session_state.current_data = final_data.copy()
        
        # History
        history_entry = {
            "ts": datetime.now().isoformat(),
            "data": final_data.copy(),
            "files": [f.name for f in uploaded_files],
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "type": "ai_analysis"
        }
        st.session_state.analyses_history.append(history_entry)
        
        # Zähler erhöhen
        if 'analyses_used' in st.session_state.current_tenant:
            st.session_state.current_tenant['analyses_used'] += 1
        
        st.success(f"✅ KI-Analyse erfolgreich für {tenant_name}!")
        st.session_state.show_comparison = True
        st.balloons()
        
    else:
        # ====== FALLBACK: Nur Excel-Daten ======
        st.warning(f"⚠️ KI-Analyse fehlgeschlagen: {message}")
        
        if excel_data:
            st.info("Verwende Excel-Daten als Fallback...")
            
            # Excel-Daten mit Defaults mergen
            final_data = DEFAULT_DATA.copy()
            for key, value in excel_data.items():
                if key in final_data:
                    final_data[key] = value
            
            # Berechne belegungsgrad
            if "belegt" in final_data and "frei" in final_data:
                belegt = final_data["belegt"]
                frei = final_data["frei"]
                if belegt + frei > 0:
                    final_data["belegungsgrad"] = round((belegt / (belegt + frei)) * 100, 1)
            
            # Empfehlungen
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
            final_data["customer_message"] = f"Analyse basierend auf Excel-Daten für {tenant_name}"
            final_data["analysis_date"] = datetime.now().isoformat()
            final_data["tenant_id"] = tenant_id
            final_data["files"] = [f.name for f in uploaded_files]
            
            # In Session State
            st.session_state.after_analysis = final_data.copy()
            st.session_state.current_data = final_data.copy()
            
            # History
            history_entry = {
                "ts": datetime.now().isoformat(),
                "data": final_data.copy(),
                "files": [f.name for f in uploaded_files],
                "tenant_id": tenant_id,
                "tenant_name": tenant_name,
                "type": "excel_analysis"
            }
            st.session_state.analyses_history.append(history_entry)
            
            st.success(f"✅ Excel-Analyse erfolgreich für {tenant_name}!")
            st.session_state.show_comparison = True
        else:
            st.error("Keine analysierbaren Daten gefunden.")
            return
    
    # Neuladen
    time.sleep(1)
    st.rerun()

def generate_fallback_recommendations(tenant_name, data):
    """Generiert einfache Empfehlungen"""
    recommendations = []
    
    if data.get('belegungsgrad', 0) > 80:
        recommendations.append(f"Hohe Auslastung bei {tenant_name} - Erwäge Erweiterung")
    elif data.get('belegungsgrad', 0) < 50:
        recommendations.append(f"Geringe Auslastung bei {tenant_name} - Marketing intensivieren")
    
    if data.get('vertragsdauer_durchschnitt', 0) < 6:
        recommendations.append("Vertragsdauer erhöhen durch Rabatte für Langzeitmieten")
    
    if data.get('social_facebook', 0) + data.get('social_google', 0) < 100:
        recommendations.append("Social Media Präsenz ausbauen")
    
    recommendations.append("Regelmäßige Kundenbefragungen durchführen")
    recommendations.append("Automatische Zahlungserinnerungen einrichten")
    
    return recommendations

# ... [REST DES CODES BLEIBT IDENTISCH - render_login_page, render_overview, etc.] ...
# (Die Seitendarstellungsfunktionen bleiben unverändert)

# HAUPTAPP
def main():
    # Session State Initialisierung
    if "current_data" not in st.session_state: 
        st.session_state.current_data = DEFAULT_DATA.copy()
    if "before_analysis" not in st.session_state: 
        st.session_state.before_analysis = None
    if "after_analysis" not in st.session_state: 
        st.session_state.after_analysis = None
    if "analyses_history" not in st.session_state: 
        st.session_state.analyses_history = []
    if "n8n_base_url" not in st.session_state: 
        st.session_state.n8n_base_url = os.environ.get("N8N_BASE_URL", "https://tundtelectronics.app.n8n.cloud/webhook")
    if "debug_mode" not in st.session_state: 
        st.session_state.debug_mode = False
    if "show_comparison" not in st.session_state: 
        st.session_state.show_comparison = False
    if "last_analysis_loaded" not in st.session_state: 
        st.session_state.last_analysis_loaded = False
    if "logged_in" not in st.session_state: 
        st.session_state.logged_in = False
    if "current_tenant" not in st.session_state: 
        st.session_state.current_tenant = None
    
    with st.sidebar:
        st.title("Login & Einstellungen")
        
        if not st.session_state.logged_in:
            st.subheader("Anmelden")
            email = st.text_input("E-Mail", key="login_email")
            password = st.text_input("Passwort", type="password", key="login_password")
            
            if st.button("Anmelden", type="primary", use_container_width=True):
                if email in TENANTS:
                    st.session_state.logged_in = True
                    st.session_state.current_tenant = TENANTS[email]
                    load_success = load_last_analysis()
                    
                    if load_success: 
                        st.success(f"Willkommen, {TENANTS[email]['name']}! Letzte Analyse geladen.")
                    else: 
                        st.warning(f"Willkommen, {TENANTS[email]['name']}! Keine vorherige Analyse gefunden.")
                    
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Ungültige E-Mail oder Passwort")
        
        else:
            tenant = st.session_state.current_tenant
            st.success(f"Eingeloggt als: {tenant['name']}")
            st.info(f"Plan: {tenant['plan'].upper()}")
            st.info(f"Analysen: {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
            st.info(f"Tenant-ID: `{tenant['tenant_id']}`")
            
            if st.button("Abmelden", use_container_width=True): 
                st.session_state.logged_in = False
                st.session_state.current_tenant = None
                st.session_state.show_comparison = False
                st.session_state.last_analysis_loaded = False
                st.rerun()
        
        st.divider()
        
        if st.session_state.logged_in:
            st.subheader("Konfiguration")
            n8n_base_url = st.text_input(
                "n8n Basis-URL (ohne Endpunkt)", 
                value=st.session_state.n8n_base_url, 
                placeholder="https://tundtelectronics.app.n8n.cloud/webhook", 
                help="Basis-URL ohne '/get-last-analysis-only' oder '/analyze-with-deepseek'",
                key="n8n_base_url_input"
            )
            st.session_state.n8n_base_url = n8n_base_url
            
            if n8n_base_url: 
                st.caption(f"Endpunkte: GET-LAST: `{n8n_base_url.rstrip('/')}/get-last-analysis-only`")
                st.caption(f"NEW-ANALYSIS: `{n8n_base_url.rstrip('/')}/analyze-with-deepseek`")
            
            st.session_state.debug_mode = st.checkbox("Debug-Modus")
            st.divider()
            st.subheader("Navigation")
            
            page = st.radio(
                "Menü", 
                ["Übersicht", "Kunden", "Kapazität", "Finanzen", "System"], 
                key="nav_radio", 
                format_func=lambda x: (
                    f"📊 {x}" if x=="Übersicht" 
                    else f"👥 {x}" if x=="Kunden" 
                    else f"📦 {x}" if x=="Kapazität" 
                    else f"💰 {x}" if x=="Finanzen" 
                    else f"⚙️ {x}"
                )
            )
            
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1: 
                if st.button("Vergleich zurücksetzen", use_container_width=True): 
                    st.session_state.show_comparison = False
                    st.success("Vergleich zurückgesetzt!")
                    time.sleep(1)
                    st.rerun()
            
            with col2: 
                if st.button("Alle Daten", type="secondary", use_container_width=True): 
                    st.session_state.current_data = DEFAULT_DATA.copy()
                    st.session_state.before_analysis = None
                    st.session_state.after_analysis = None
                    st.session_state.show_comparison = False
                    st.success("Daten zurückgesetzt!")
                    time.sleep(1)
                    st.rerun()
        
        else: 
            page = "Übersicht"
    
    if not st.session_state.logged_in: 
        render_login_page()
    else:
        if page == "Übersicht": 
            render_overview()
        elif page == "Kunden": 
            render_customers()
        elif page == "Kapazität": 
            render_capacity()
        elif page == "Finanzen": 
            render_finance()
        elif page == "System": 
            render_system()

if __name__ == "__main__": 
    main()
