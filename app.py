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

# ====== NEUE PARSER-FUNKTIONEN FÜR SUPABASE-JSON ======
def parse_supabase_response(response_data):
    """
    Parst JEDE n8n-Antwort, die jetzt Supabase-kompatibel sein sollte
    """
    print(f"\n🔍 PARSE SUPABASE RESPONSE - Type: {type(response_data)}")
    
    # Default Rückgabe
    default_result = {
        "status": "error",
        "tenant_id": "unbekannt_tenant",
        "count": 0,
        "data": DEFAULT_DATA.copy()
    }
    
    # Fall 1: Response ist None
    if response_data is None:
        print("❌ Response ist None")
        return default_result
    
    # Fall 2: Es ist bereits unser neues Format
    if isinstance(response_data, dict) and 'data' in response_data:
        print("✅ Neues Contract-Format erkannt")
        return response_data
    
    # Fall 3: Es ist ein Array (direkt von Supabase)
    if isinstance(response_data, list) and len(response_data) > 0:
        print(f"✅ Supabase Array erkannt, Länge: {len(response_data)}")
        
        row = response_data[0]
        
        # Extrahiere analysis_result (ist ein JSON-String!)
        analysis_result_str = row.get('analysis_result')
        
        if not analysis_result_str:
            print("❌ Kein analysis_result Feld")
            return default_result
        
        # Parse den JSON-String
        try:
            analysis_data = json.loads(analysis_result_str)
            print(f"✅ analysis_result geparst, Type: {type(analysis_data)}")
        except json.JSONDecodeError as e:
            print(f"❌ Konnte analysis_result nicht parsen: {e}")
            return default_result
        
        # Baue das neue Format
        return {
            "status": "success",
            "tenant_id": row.get('tenant_id', 'unbekannt_tenant'),
            "document_id": row.get('document_id'),
            "count": 1,
            "data": {
                "metrics": analysis_data.get('metrics', {}),
                "recommendations": analysis_data.get('recommendations', []),
                "customer_message": analysis_data.get('customer_message', ''),
                "analysis_date": analysis_data.get('analysis_date', row.get('created_at'))
            }
        }
    
    # Fall 4: Altes Format (für Übergangsphase)
    print("⚠️ Altes Format, versuche zu konvertieren")
    if isinstance(response_data, dict):
        # Versuche als Business-Daten zu behandeln
        if 'belegt' in response_data or 'frei' in response_data:
            return {
                "status": "success",
                "tenant_id": response_data.get('tenant_id', 'unbekannt_tenant'),
                "count": 1,
                "data": {
                    "metrics": {k: v for k, v in response_data.items() 
                               if k in DEFAULT_DATA or k in ['kundenherkunft', 'zahlungsstatus', 
                                                           'neukunden_labels', 'neukunden_monat']},
                    "recommendations": response_data.get('recommendations', []),
                    "customer_message": response_data.get('customer_message', ''),
                    "analysis_date": response_data.get('analysis_date', datetime.now().isoformat())
                }
            }
    
    print(f"❌ Unbekanntes Format: {type(response_data)}")
    return default_result


def extract_business_data(contract_response):
    """
    Extrahiert Business-Daten aus dem Contract-Format
    Für Kompatibilität mit deinem existierenden Code
    """
    if not contract_response or contract_response.get('status') != 'success':
        return DEFAULT_DATA.copy()
    
    data = contract_response.get('data', {})
    metrics = data.get('metrics', {})
    
    # Kombiniere mit Defaults
    result = DEFAULT_DATA.copy()
    
    for key in result.keys():
        if key in metrics:
            result[key] = metrics[key]
    
    # Füge zusätzliche Felder hinzu
    for field in ['recommendations', 'customer_message', 'analysis_date', 'tenant_id']:
        if field in data:
            result[field] = data[field]
    
    return result

# ====== KORRIGIERTE API-FUNKTIONEN FÜR SUPABASE-KOMMUNIKATION ======
def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
    """
    Erwartet SUPABASE-FORMAT von n8n - SENDET JSON
    """
    print(f"\n📞 NEW-ANALYSIS (Supabase Format) für {tenant_id}")
    
    url = f"{base_url.rstrip('/')}/analyze-with-deepseek"
    print(f"NEW-ANALYSIS URL: {url}")
    
    # Datei vorbereiten
    filename, file_content, file_type = file_info
    base64_content = base64.b64encode(file_content).decode('utf-8')
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
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
            return None, f"HTTP {response.status_code}", None
        
        json_response = response.json()
        print(f"Response Typ: {type(json_response)}")
        
        # Parse mit unserer neuen Funktion
        contract = parse_supabase_response(json_response)
        
        # Extrahiere Business-Daten für Kompatibilität
        business_data = extract_business_data(contract)
        
        return business_data, "Success", None
        
    except Exception as e:
        print(f"❌ Fehler: {str(e)}")
        return None, f"Exception: {str(e)}", None


def post_to_n8n_get_last(base_url, tenant_id, uuid_str):
    """
    Erwartet jetzt SUPABASE-FORMAT von n8n - EMPFÄNGT JSON
    """
    print(f"\n📞 GET-LAST (Supabase Format) für {tenant_id}")
    print(f"GET-LAST URL: {base_url.rstrip('/')}/get-last-analysis-only")
    
    url = f"{base_url.rstrip('/')}/get-last-analysis-only"
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"GET-LAST Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}", None
        
        json_response = response.json()
        print(f"GET-LAST JSON Typ: {type(json_response)}")
        
        # Parse mit unserer neuen Funktion
        contract = parse_supabase_response(json_response)
        
        # Extrahiere Business-Daten für Kompatibilität
        business_data = extract_business_data(contract)
        
        return business_data, "Success", None
        
    except Exception as e:
        print(f"❌ Fehler: {str(e)}")
        return None, f"Exception: {str(e)}", None


# ====== HILFSFUNKTIONEN ======
def extract_metrics_from_excel(df):
    """Extrahiert Metriken aus Excel/CSV Dateien für Fallback"""
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
        
        # Numerische Felder
        for col in ['vertragsdauer_durchschnitt', 'reminder_automat', 'social_facebook', 'social_google']:
            if col in df.columns: 
                metrics[col] = float(df[col].mean())
        
        # Kundenherkunft
        herkunft_cols = [c for c in df.columns if 'herkunft' in c.lower()]
        if herkunft_cols:
            herkunft_counts = df[herkunft_cols[0]].value_counts().to_dict()
            metrics['kundenherkunft'] = {
                'Online': herkunft_counts.get('Online', 0), 
                'Empfehlung': herkunft_counts.get('Empfehlung', 0), 
                'Vorbeikommen': herkunft_counts.get('Vorbeikommen', 0)
            }
        
        # Zahlungsstatus
        status_cols = [c for c in df.columns if 'status' in c.lower()]
        if status_cols:
            status_counts = df[status_cols[0]].value_counts().to_dict()
            metrics['zahlungsstatus'] = {
                'bezahlt': status_counts.get('bezahlt', 0), 
                'offen': status_counts.get('offen', 0), 
                'überfällig': status_counts.get('überfällig', 0)
            }
            
    except Exception as e: 
        print(f"Excel-Warnung: {str(e)[:80]}")
    return metrics


def merge_data(base_dict, new_dict):
    """Mergt zwei Datensätze"""
    result = base_dict.copy() if base_dict else {}
    if new_dict:
        for key, value in new_dict.items():
            if key not in ['kundenherkunft', 'zahlungsstatus', 'recommendations', 'customer_message']: 
                result[key] = value
        
        # Spezielle Merge-Logik für Dictionaries
        if 'kundenherkunft' in new_dict:
            if 'kundenherkunft' not in result: 
                result['kundenherkunft'] = {'Online': 0, 'Empfehlung': 0, 'Vorbeikommen': 0}
            for k, v in new_dict['kundenherkunft'].items(): 
                result['kundenherkunft'][k] = result['kundenherkunft'].get(k, 0) + v
        
        if 'zahlungsstatus' in new_dict:
            if 'zahlungsstatus' not in result: 
                result['zahlungsstatus'] = {'bezahlt': 0, 'offen': 0, 'überfällig': 0}
            for k, v in new_dict['zahlungsstatus'].items(): 
                result['zahlungsstatus'][k] = result['zahlungsstatus'].get(k, 0) + v
    
    return result


def create_comparison_chart(before_data, after_data, metric_key, title):
    """Erstellt Vergleichsdiagramm Vorher/Nachher"""
    if metric_key not in before_data or metric_key not in after_data: 
        return None
    
    before_val = before_data[metric_key]
    after_val = after_data[metric_key]
    delta = after_val - before_val
    delta_color = 'green' if delta >= 0 else 'red'
    delta_symbol = '+' if delta >= 0 else ''
    
    fig = go.Figure(data=[
        go.Bar(name='Vorher', x=['Vorher'], y=[before_val], marker_color='lightblue'),
        go.Bar(name='Nachher', x=['Nachher'], y=[after_val], marker_color='lightgreen')
    ])
    fig.update_layout(
        title=f"{title}<br><span style='font-size:12px;color:{delta_color}'>{delta_symbol}{delta:.1f} Veränderung</span>", 
        height=300, 
        showlegend=True, 
        yaxis_title=title
    )
    return fig


def create_timeseries_chart(history_data, metric_key, title):
    """Erstellt Zeitreihendiagramm"""
    if not history_data or len(history_data) < 2: 
        return None
    
    dates = []
    values = []
    
    for entry in sorted(history_data, key=lambda x: x.get('ts', '')):
        if isinstance(entry, dict) and 'data' in entry and metric_key in entry['data']:
            dates.append(entry.get('ts', ''))
            values.append(entry['data'][metric_key])
    
    if len(dates) < 2: 
        return None
    
    fig = go.Figure(data=[go.Scatter(x=dates, y=values, mode='lines+markers', name=title)])
    fig.update_layout(title=f"Entwicklung: {title}", height=300, xaxis_title="Datum", yaxis_title=title)
    return fig


def load_last_analysis():
    """Lädt die letzte Analyse - JETZT MIT SUPABASE-JSON"""
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
        # Rufe n8n Endpoint auf (gibt direkt Business-Daten zurück)
        business_data, message, response = post_to_n8n_get_last(
            n8n_base_url, tenant_id, str(uuid.uuid4())
        )
        
        # Debug-Info
        if st.session_state.debug_mode:
            with st.expander("Debug: GET-LAST Response", expanded=False):
                st.write(f"Message: {message}")
                st.write("Business Data geladen:")
                st.json(business_data if business_data else {})
        
        # Fallback bei Fehlern
        if business_data is None:
            st.info("⚠️ Keine vorherige Analyse gefunden oder Server-Fehler. Verwende Standarddaten.")
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.before_analysis = DEFAULT_DATA.copy()
            return True
        
        # Konvertiere alle Werte zu richtigen Typen
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
        
        # Starte mit DEFAULT_DATA
        loaded_data = DEFAULT_DATA.copy()
        
        # Übernehme alle Metriken aus der Response
        for key, value in business_data.items():
            if key in loaded_data:
                loaded_data[key] = safe_convert(value)
        
        # Spezielle Felder
        if "kundenherkunft" in business_data:
            loaded_data["kundenherkunft"] = business_data.get("kundenherkunft", {})
        
        if "zahlungsstatus" in business_data:
            loaded_data["zahlungsstatus"] = business_data.get("zahlungsstatus", {})
        
        # Empfehlungen und Message
        loaded_data["recommendations"] = business_data.get("recommendations", [])
        loaded_data["customer_message"] = business_data.get("customer_message", 
                                                          f"Letzte Analyse für {tenant_id} geladen")
        
        # Analysis Date
        loaded_data["analysis_date"] = business_data.get("analysis_date", datetime.now().isoformat())
        loaded_data["tenant_id"] = tenant_id
        
        # Debug-Info
        if st.session_state.debug_mode:
            with st.expander("Debug: Geladene Daten", expanded=False):
                st.write("Business Data von API:")
                st.json(business_data)
                st.write("Finale geladene Daten:")
                st.json({k: v for k, v in loaded_data.items() if k in DEFAULT_DATA})
        
        # In Session State speichern
        st.session_state.current_data = loaded_data
        st.session_state.before_analysis = loaded_data.copy()
        st.session_state.last_analysis_loaded = True
        
        st.success(f"✅ Letzte Analyse vom {loaded_data['analysis_date'][:10]} geladen!")
        return True


def perform_analysis(uploaded_files):
    """Führt KI-Analyse mit Supabase-JSON durch"""
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
    
    # ====== SUPABASE-JSON ANALYSE ======
    with st.spinner("KI analysiert Daten... (dies kann 30-60 Sekunden dauern)"):
        business_data, message, response = post_to_n8n_analyze(
            n8n_base_url, tenant_id, str(uuid.uuid4()), file_info
        )
    
    # Debug-Info
    if st.session_state.debug_mode:
        with st.expander("Debug: n8n Kommunikation", expanded=False):
            st.write(f"Meldung: {message}")
            if business_data:
                st.write("Business Data von API:")
                st.json(business_data)
    
    # ====== ZENTRALE ERGEBNISVERARBEITUNG ======
    if business_data is not None:
        # 1. Business-Daten mit Excel-Daten mergen (n8n hat Priorität)
        final_data = DEFAULT_DATA.copy()
        
        # Übernehme alle Felder aus Business-Daten
        for key in final_data:
            if key in business_data:
                final_data[key] = business_data[key]
        
        # 2. Falls n8n Daten fehlen, verwende Excel-Daten
        for key in excel_data:
            if key not in final_data or final_data[key] == 0:
                final_data[key] = excel_data[key]
        
        # 3. Empfehlungen und Message (aus Business-Daten)
        final_data["recommendations"] = business_data.get("recommendations", [])
        if not final_data["recommendations"]:
            # Fallback-Empfehlungen basierend auf Excel-Daten
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
        
        final_data["customer_message"] = business_data.get("customer_message", 
                                                          f"Analyse für {tenant_name} abgeschlossen.")
        
        # 4. Metadaten
        final_data["analysis_date"] = business_data.get("analysis_date", datetime.now().isoformat())
        final_data["tenant_id"] = tenant_id
        final_data["files"] = [f.name for f in uploaded_files]
        final_data["source"] = "supabase_json"
        
        # 5. In Session State speichern
        st.session_state.after_analysis = final_data.copy()
        st.session_state.current_data = final_data.copy()
        
        # 6. History aktualisieren
        history_entry = {
            "ts": datetime.now().isoformat(),
            "data": final_data.copy(),
            "files": [f.name for f in uploaded_files],
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "type": "ai_analysis",
            "source": "supabase"
        }
        st.session_state.analyses_history.append(history_entry)
        
        # 7. Zähler erhöhen
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
            for key in final_data:
                if key in excel_data:
                    final_data[key] = excel_data[key]
            
            # Empfehlungen generieren
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
            final_data["customer_message"] = f"Analyse basierend auf Excel-Daten für {tenant_name}"
            final_data["analysis_date"] = datetime.now().isoformat()
            final_data["tenant_id"] = tenant_id
            final_data["files"] = [f.name for f in uploaded_files]
            final_data["source"] = "excel_fallback"
            
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
                "type": "excel_analysis",
                "source": "fallback"
            }
            st.session_state.analyses_history.append(history_entry)
            
            st.success(f"✅ Excel-Analyse erfolgreich für {tenant_name}!")
            st.session_state.show_comparison = True
        else:
            st.error("Keine analysierbaren Daten gefunden.")
            return
    
    # Neuladen der Seite
    time.sleep(1)
    st.rerun()


def generate_fallback_recommendations(tenant_name, data):
    """Generiert einfache Empfehlungen basierend auf Daten"""
    recommendations = []
    
    if data.get('belegungsgrad', 0) > 80:
        recommendations.append(f"Hohe Auslastung bei {tenant_name} - Erwäge Erweiterung")
    elif data.get('belegungsgrad', 0) < 50:
        recommendations.append(f"Geringe Auslastung bei {tenant_name} - Marketing intensivieren")
    
    if data.get('vertragsdauer_durchschnitt', 0) < 6:
        recommendations.append("Vertragsdauer erhöhen durch Rabatte für Langzeitmieten")
    
    if data.get('social_facebook', 0) + data.get('social_google', 0) < 100:
        recommendations.append("Social Media Präsenz ausbauen")
    
    # Standard-Empfehlungen
    recommendations.append("Regelmäßige Kundenbefragungen durchführen")
    recommendations.append("Automatische Zahlungserinnerungen einrichten")
    
    return recommendations


# SEITENFUNKTIONEN (identisch wie vorher, kürze für Lesbarkeit)
def render_login_page():
    st.title("Self-Storage Business Intelligence")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("## Willkommen!\n**KI-gestützte Analyse für Self-Storage Unternehmen:**\n✅ Durchgängiger Workflow\n✅ Vorher/Nachher Visualisierung\n✅ Automatisches Laden\n✅ Zeitliche Entwicklung")
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", caption="Data-Driven Decisions for SelfStorage")
    
    st.divider()
    st.subheader("Dashboard-Features")
    col1, col2, col3 = st.columns(3)
    with col1: 
        st.markdown("**Vergleichsansicht**")
        st.write("Side-by-Side Diagramme")
    with col2: 
        st.markdown("**History-Tracking**")
        st.write("Alle Analysen speichern")
    with col3: 
        st.markdown("**KI-Integration**")
        st.write("Automatische Empfehlungen")
        

def render_overview():
    tenant = st.session_state.current_tenant
    st.title(f"Dashboard - {tenant['name']}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: 
        st.info(f"Tenant-ID: `{tenant['tenant_id']}`")
    with col2: 
        st.info(f"Plan: {tenant['plan'].upper()}")
    with col3: 
        used = tenant.get('analyses_used', 0)
        limit = tenant.get('analyses_limit', '∞')
        st.info(f"Analysen: {used}/{limit}")
    with col4: 
        current_date = st.session_state.current_data.get('analysis_date', '')
        display_date = current_date[:10] if current_date else "Keine"
        st.info(f"Letzte Analyse: {display_date}")
    
    st.header("Neue Analyse durchführen")
    uploaded_files = st.file_uploader(
        "Dateien hochladen (Excel/CSV)", 
        type=["xlsx", "xls", "csv"], 
        accept_multiple_files=True, 
        key="file_uploader"
    )
    
    col1, col2 = st.columns(2)
    with col1: 
        analyze_btn = st.button(
            "KI-Analyse starten", 
            type="primary", 
            use_container_width=True, 
            disabled=not uploaded_files
        )
    with col2: 
        if st.button("Letzte Analyse neu laden", use_container_width=True): 
            load_last_analysis()
            st.session_state.show_comparison = False
            st.success("Letzte Analyse neu geladen!")
            time.sleep(1)
            st.rerun()
    
    if analyze_btn and uploaded_files: 
        perform_analysis(uploaded_files)
    
    # Rest der Visualisierungen bleiben gleich wie in Ihrer Original-app.py
    # ... (hier würden die restlichen Visualisierungen folgen)


def render_customers():
    st.title("Kundenanalyse")
    # ... (Implementierung wie in Ihrer Original-app.py)


def render_capacity():
    st.title("Kapazitätsmanagement")
    # ... (Implementierung wie in Ihrer Original-app.py)


def render_finance():
    st.title("Finanzübersicht")
    # ... (Implementierung wie in Ihrer Original-app.py)


def render_system():
    st.title("System & Export")
    # ... (Implementierung wie in Ihrer Original-app.py)


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
