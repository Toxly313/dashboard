import os, uuid, json, re, time
from datetime import datetime
import pandas as pd
import streamlit as st

# ===== PORT FIX FÜR RAILWAY =====
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

# ===== KONFIGURATION =====
st.set_page_config(
    page_title="Self-Storage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== HILFSFUNKTIONEN =====
def post_to_n8n(url, file_tuple, uuid_str):
    """Sendet Datei an n8n Webhook."""
    import requests
    if not url or not url.startswith("http"):
        return 400, "Ungültige URL", None
    
    try:
        response = requests.post(
            url,
            files={'file': file_tuple} if file_tuple else None,
            data={'uuid': uuid_str},
            timeout=45,
            headers={'User-Agent': 'Dashboard-KI/1.0'}
        )
        
        if response.status_code != 200:
            error_msg = f"n8n Fehler {response.status_code}"
            try:
                error_detail = response.json().get('error', response.text[:200])
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            return response.status_code, error_msg, None
        
        try:
            return response.status_code, "Success", response.json()
        except json.JSONDecodeError:
            return response.status_code, "Kein gültiges JSON", None
            
    except requests.exceptions.Timeout:
        return 408, "Timeout nach 45s", None
    except requests.exceptions.ConnectionError:
        return 503, "Verbindungsfehler", None
    except Exception as e:
        return 500, f"Fehler: {str(e)}", None

def extract_json_from_markdown(text):
    """Extrahiert JSON aus Markdown-Text."""
    if not text or not isinstance(text, str):
        return None
    
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        try:
            return json.loads(matches[0])
        except:
            pass
    
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except:
        pass
    
    return None

def extract_metrics_from_excel(df):
    """Extrahiert Metriken aus Excel-Daten."""
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
        
        for col in ['vertragsdauer_durchschnitt', 'reminder_automat', 
                   'social_facebook', 'social_google']:
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
    """Merge zwei Dictionaries."""
    result = base_dict.copy() if base_dict else {}
    if new_dict:
        for key, value in new_dict.items():
            if key not in ['kundenherkunft', 'zahlungsstatus', 'recommendations', 'customer_message']:
                result[key] = value
        
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

# ===== DEFAULT DATEN =====
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [5, 4, 7, 6, 8, 9],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ===== HAUPTAPP =====
def main():
    # Session State initialisieren
    if "data" not in st.session_state:
        st.session_state.data = DEFAULT_DATA.copy()
    if "prev" not in st.session_state:
        st.session_state.prev = DEFAULT_DATA.copy()
    if "history" not in st.session_state:
        st.session_state.history = []
    if "n8n_url" not in st.session_state:
        st.session_state.n8n_url = os.environ.get("N8N_URL", "")
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "last_raw_response" not in st.session_state:
        st.session_state.last_raw_response = None
    
    # ===== SIDEBAR =====
    with st.sidebar:
        st.title("⚙️ Einstellungen")
        
        # Debug Info
        st.caption(f"🔧 Railway Port: {os.environ.get('PORT', 'Nicht gesetzt')}")
        
        # n8n URL
        n8n_url = st.text_input(
            "n8n Webhook URL",
            value=st.session_state.n8n_url,
            placeholder="https://deine-n8n-url.com/webhook"
        )
        st.session_state.n8n_url = n8n_url
        
        # Debug Mode
        st.session_state.debug_mode = st.checkbox("🐛 Debug-Modus aktivieren")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigation",
            ["📊 Übersicht", "👥 Kunden", "📦 Kapazität", "💰 Finanzen", "⚙️ System"]
        )
        
        st.divider()
        
        # Reset Button
        if st.button("🗑️ Zurücksetzen", use_container_width=True):
            st.session_state.data = DEFAULT_DATA.copy()
            st.session_state.prev = DEFAULT_DATA.copy()
            st.session_state.history = []
            st.session_state.last_raw_response = None
            st.success("Zurückgesetzt!")
            time.sleep(1)
            st.rerun()
        
        # Debug Info anzeigen
        if st.session_state.debug_mode and st.session_state.last_raw_response:
            st.divider()
            st.subheader("🔍 Letzte Rohantwort")
            with st.expander("Anzeigen"):
                st.json(st.session_state.last_raw_response)
    
    # ===== HAUPTINHALT =====
    if page == "📊 Übersicht":
        render_overview()
    elif page == "👥 Kunden":
        render_customers()
    elif page == "📦 Kapazität":
        render_capacity()
    elif page == "💰 Finanzen":
        render_finance()
    elif page == "⚙️ System":
        render_system()

# ===== SEITENFUNKTIONEN =====
def render_overview():
    """Hauptseite mit Upload und Analyse."""
    st.title("📊 Dashboard Übersicht")
    
    # Upload Bereich
    st.header("📥 Daten analysieren")
    
    uploaded_files = st.file_uploader(
        "Dateien hochladen (Excel/CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        analyze_btn = st.button("🚀 KI-Analyse starten", type="primary", use_container_width=True)
    with col2:
        mock_btn = st.button("🧪 Mock-Daten", use_container_width=True)
    with col3:
        if st.button("📋 Datenvorschau", use_container_width=True) and uploaded_files:
            try:
                df = pd.read_excel(uploaded_files[0])
                st.dataframe(df.head(), width='stretch')
            except:
                st.warning("Konnte Datei nicht lesen")
    
    # Mock-Daten
    if mock_btn:
        mock_data = {
            "belegt": 22, "frei": 3, "belegungsgrad": 88, 
            "vertragsdauer_durchschnitt": 9.1,
            "recommendations": ["Testempfehlung 1", "Testempfehlung 2"],
            "customer_message": "Mock-Daten erfolgreich geladen."
        }
        st.session_state.prev = st.session_state.data.copy()
        st.session_state.data = {**st.session_state.data, **mock_data}
        st.success("✅ Mock-Daten geladen!")
        time.sleep(1)
        st.rerun()
    
    # Echte Analyse
    if analyze_btn and uploaded_files:
        perform_analysis(uploaded_files)
    
    # KPIs anzeigen
    st.header("📈 Key Performance Indicators")
    data = st.session_state.data
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Belegt", data.get("belegt", 0))
    with col2:
        st.metric("Frei", data.get("frei", 0))
    with col3:
        st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
    with col4:
        st.metric("Ø Vertragsdauer", f"{data.get('vertragsdauer_durchschnitt', 0)} Monate")
    
    # Charts
    st.header("📊 Visualisierungen")
    
    col1, col2 = st.columns(2)
    with col1:
        import plotly.graph_objects as go
        labels = data.get("neukunden_labels", [])
        values = data.get("neukunden_monat", [])
        fig = go.Figure(data=[go.Bar(x=labels, y=values)])
        fig.update_layout(title="Neukunden pro Monat", height=300)
        st.plotly_chart(fig, width='stretch')
    
    with col2:
        belegung = data.get("belegungsgrad", 0)
        fig = go.Figure(data=[go.Pie(
            labels=["Belegt", "Frei"],
            values=[belegung, 100 - belegung],
            hole=0.6
        )])
        fig.update_layout(title="Belegungsgrad", height=300)
        st.plotly_chart(fig, width='stretch')
    
    # KI-Empfehlungen
    recommendations = data.get("recommendations", [])
    if recommendations:
        st.header("🤖 KI-Empfehlungen")
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"**{i}.** {rec}")
        
        if data.get("customer_message"):
            with st.expander("📝 Kundennachricht"):
                st.info(data["customer_message"])

def perform_analysis(uploaded_files):
    """Führt die KI-Analyse durch - KERNLOGIK FIXED."""
    with st.spinner("🧠 KI analysiert Daten... (ca. 15-45 Sekunden)"):
        # Dateien vorbereiten
        csv_json_files = [f for f in uploaded_files if f.name.lower().endswith((".csv", ".json"))]
        excel_files = [f for f in uploaded_files if f.name.lower().endswith((".xlsx", ".xls"))]
        
        main_file = csv_json_files[0] if csv_json_files else uploaded_files[0]
        excel_merge = {}
        
        # Excel-Daten extrahieren
        for excel_file in excel_files:
            try:
                df = pd.read_excel(excel_file)
                excel_metrics = extract_metrics_from_excel(df)
                excel_merge = merge_data(excel_merge, excel_metrics)
            except Exception as e:
                st.warning(f"Excel-Fehler: {str(e)[:50]}")
        
        # Prüfe n8n URL
        n8n_url = st.session_state.n8n_url
        if not n8n_url or not n8n_url.startswith("http"):
            st.error("❌ Bitte gültige n8n URL in der Sidebar eingeben")
            return
        
        # n8n aufrufen
        status, message, response = post_to_n8n(
            n8n_url,
            (main_file.name, main_file.getvalue()),
            str(uuid.uuid4())
        )
        
        # Debug: Rohantwort speichern
        st.session_state.last_raw_response = response
        
        # Debug-Ausgabe
        if st.session_state.debug_mode:
            with st.expander("🔍 Debug: n8n Kommunikation", expanded=True):
                st.write(f"**Status:** {status}")
                st.write(f"**Meldung:** {message}")
                if response:
                    st.write("**Rohantwort von n8n:**")
                    st.json(response)
        
        if status != 200 or not response:
            st.error(f"❌ n8n-Fehler: {message}")
            return
        
        # ===== KRITISCHE DATENVERARBEITUNG =====
        # Dein n8n sendet doppelt verschachtelte Daten: {metrics: {metrics: {...}}}
        processed_data = None
        
        if isinstance(response, dict):
            # FALL A: Doppelt verschachtelt (dein aktuelles Problem!)
            if 'metrics' in response and isinstance(response['metrics'], dict):
                if 'metrics' in response['metrics']:
                    # Doppelte Verschachtelung: metrics -> metrics -> daten
                    processed_data = {
                        'metrics': response['metrics'].get('metrics', {}),
                        'recommendations': response.get('recommendations', []),
                        'customer_message': response.get('customer_message', '')
                    }
                    if st.session_state.debug_mode:
                        st.info("🔄 Doppelte Verschachtelung erkannt und korrigiert")
                else:
                    # Einfache Verschachtelung: metrics -> daten
                    processed_data = {
                        'metrics': response['metrics'],
                        'recommendations': response.get('recommendations', []),
                        'customer_message': response.get('customer_message', '')
                    }
            
            # FALL B: Flaches Format (nach Korrektur der n8n-Node)
            elif all(k in response for k in ['metrics', 'recommendations', 'customer_message']):
                processed_data = response
            
            # FALL C: Direkte Metriken
            elif any(k in response for k in ['belegt', 'belegungsgrad']):
                processed_data = {
                    'metrics': response,
                    'recommendations': response.get('recommendations', []),
                    'customer_message': response.get('customer_message', '')
                }
        
        if not processed_data:
            # Letzter Versuch: Extrahiere JSON aus String
            json_str = str(response)
            extracted = extract_json_from_markdown(json_str)
            if extracted and isinstance(extracted, dict):
                # Wiederhole die gleiche Logik mit extrahierten Daten
                if 'metrics' in extracted:
                    processed_data = {
                        'metrics': extracted.get('metrics', {}),
                        'recommendations': extracted.get('recommendations', []),
                        'customer_message': extracted.get('customer_message', '')
                    }
        
        # ===== ERGEBNIS VERARBEITEN =====
        if processed_data:
            # Metriken extrahieren
            metrics_data = processed_data.get('metrics', {})
            recommendations = processed_data.get('recommendations', [])
            customer_message = processed_data.get('customer_message', '')
            
            # Mit Excel-Daten mergen
            merged_data = merge_data(metrics_data, excel_merge)
            merged_data['recommendations'] = recommendations
            merged_data['customer_message'] = customer_message
            
            # Session State aktualisieren
            st.session_state.prev = st.session_state.data.copy()
            st.session_state.data = merged_data
            
            # History speichern
            st.session_state.history.append({
                "ts": datetime.now().isoformat(),
                "data": merged_data.copy(),
                "files": [f.name for f in uploaded_files],
                "source": "n8n"
            })
            
            st.success(f"✅ KI-Analyse erfolgreich! ({len(recommendations)} Empfehlungen)")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ n8n-Antwort hat unerwartetes Format")
            if st.session_state.debug_mode:
                with st.expander("🔍 Problem-Details"):
                    st.write("Rohdaten-Typ:", type(response))
                    st.write("Rohdaten:", response)

def render_kpi_grid():
    """Zeigt KPIs in einem Grid."""
    data = st.session_state.data
    
    metrics = [
        ("Belegt", "belegt", ""),
        ("Frei", "frei", ""),
        ("Belegungsgrad", "belegungsgrad", "%"),
        ("Ø Vertragsdauer", "vertragsdauer_durchschnitt", " Monate"),
        ("Facebook", "social_facebook", ""),
        ("Google", "social_google", "")
    ]
    
    cols = st.columns(len(metrics))
    for idx, (label, key, suffix) in enumerate(metrics):
        with cols[idx]:
            value = data.get(key, 0)
            st.metric(label, f"{value}{suffix}")

def render_customers():
    """Kundenseite."""
    st.title("👥 Kundenanalyse")
    
    data = st.session_state.data
    
    # Kundenherkunft
    st.header("Kundenherkunft")
    herkunft = data.get("kundenherkunft", {})
    
    if herkunft:
        col1, col2 = st.columns(2)
        with col1:
            import plotly.express as px
            df = pd.DataFrame({
                "Kanal": list(herkunft.keys()),
                "Anzahl": list(herkunft.values())
            })
            fig = px.pie(df, values='Anzahl', names='Kanal')
            st.plotly_chart(fig, width='stretch')
        with col2:
            st.dataframe(df, width='stretch')
    
    # Empfehlungen
    st.header("Kundenakquise")
    st.markdown("""
    - **Empfehlungsprogramm**: 25€ Guthaben pro Neukunde
    - **Google Business**: Regelmäßige Updates und Bewertungen
    - **Zielgruppen-Marketing**: Gezielte Ansprache
    """)

def render_capacity():
    """Kapazitätsseite."""
    st.title("📦 Kapazitätsmanagement")
    
    data = st.session_state.data
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Belegte Einheiten", data.get("belegt", 0))
        st.metric("Freie Einheiten", data.get("frei", 0))
        st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
    with col2:
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Bar(
            x=["Belegt", "Frei"],
            y=[data.get("belegt", 0), data.get("frei", 0)]
        )])
        fig.update_layout(title="Kapazitätsverteilung", height=300)
        st.plotly_chart(fig, width='stretch')
    
    # Optimierung
    st.header("Optimierungsvorschläge")
    belegung = data.get("belegungsgrad", 0)
    
    if belegung < 85:
        st.warning(f"Auslastung ({belegung}%) optimierbar")
        st.markdown("- Kurzzeit-Aktionen starten\n- Marketing intensivieren")
    else:
        st.success(f"Auslastung ({belegung}%) sehr gut")

def render_finance():
    """Finanzseite."""
    st.title("💰 Finanzübersicht")
    
    data = st.session_state.data
    
    # Zahlungsstatus
    st.header("Zahlungsstatus")
    status = data.get("zahlungsstatus", {})
    
    if status:
        col1, col2 = st.columns(2)
        with col1:
            df = pd.DataFrame({
                "Status": list(status.keys()),
                "Anzahl": list(status.values())
            })
            st.dataframe(df, width='stretch')
        with col2:
            import plotly.express as px
            fig = px.pie(df, values='Anzahl', names='Status')
            st.plotly_chart(fig, width='stretch')
    
    # Finanztipps
    st.header("Finanzoptimierung")
    offen = status.get("offen", 0)
    überfällig = status.get("überfällig", 0)
    
    if offen + überfällig > 0:
        st.warning(f"{offen + überfällig} offene/überfällige Zahlungen")
        st.markdown("- Automatische Erinnerungen\n- Skonto anbieten")

def render_system():
    """Systemseite."""
    st.title("⚙️ System & Export")
    
    data = st.session_state.data
    
    # Export
    st.header("Daten exportieren")
    
    col1, col2 = st.columns(2)
    with col1:
        csv = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            "⬇️ CSV Export",
            csv,
            f"storage_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
    with col2:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            "⬇️ JSON Export",
            json_str,
            f"storage_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json",
            use_container_width=True
        )
    
    # History
    st.header("Analyserverlauf")
    history = st.session_state.history
    
    if history:
        for i, entry in enumerate(reversed(history[-3:]), 1):
            with st.expander(f"Analyse {i} - {entry['ts'][11:16]}"):
                st.write(f"Dateien: {entry['files']}")
                st.write(f"Quelle: {entry.get('source', 'n8n')}")
    else:
        st.info("Noch keine Analysen")
    
    # Systeminfo
    st.header("Systeminformation")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Analysen gesamt", len(history))
        st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    with col2:
        st.metric("n8n URL", "Gesetzt" if st.session_state.n8n_url else "Fehlt")
        st.metric("Session", "Aktiv")

# ===== APP START =====
if __name__ == "__main__":
    main()
