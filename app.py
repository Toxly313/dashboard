import os, uuid, json, re, time
from datetime import datetime
import numpy as np, pandas as pd, streamlit as st

# ===== PORT FIX FÜR RAILWAY =====
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    print(f"🚨 Railway PORT gesetzt auf: {os.environ['PORT']}")

# ===== KONFIGURATION =====
st.set_page_config(
    page_title="Self-Storage Pro Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== HILFSFUNKTIONEN =====
def post_to_n8n(url, file_tuple, uuid_str):
    """Sendet Datei an n8n Webhook mit Debugging."""
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
        return 503, "Verbindungsfehler zu n8n", None
    except Exception as e:
        return 500, f"Unerwarteter Fehler: {str(e)}", None

def extract_json_from_markdown(text):
    """Extrahiert JSON aus Markdown-Codeblöcken."""
    if not text or not isinstance(text, str):
        return None
    
    # Suche nach JSON-Codeblöcken
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass
    
    # Falls kein Codeblock: versuche JSON direkt zu finden
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
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
        
        herkunft_cols = [c for c in df.columns if 'herkunft' in c.lower() or 'kanal' in c.lower()]
        if herkunft_cols:
            herkunft_counts = df[herkunft_cols[0]].value_counts().to_dict()
            metrics['kundenherkunft'] = {
                'Online': herkunft_counts.get('Online', 0),
                'Empfehlung': herkunft_counts.get('Empfehlung', 0),
                'Vorbeikommen': herkunft_counts.get('Vorbeikommen', 0)
            }
        
        status_cols = [c for c in df.columns if 'status' in c.lower() or 'zahlung' in c.lower()]
        if status_cols:
            status_counts = df[status_cols[0]].value_counts().to_dict()
            metrics['zahlungsstatus'] = {
                'bezahlt': status_counts.get('bezahlt', 0),
                'offen': status_counts.get('offen', 0),
                'überfällig': status_counts.get('überfällig', 0)
            }
    except Exception as e:
        st.warning(f"Konnte nicht alle Excel-Daten verarbeiten: {str(e)[:100]}")
    
    return metrics

def merge_data(base_dict, new_dict):
    """Merge zwei Dictionaries, wobei new_dict Vorrang hat."""
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

def delta(prev, cur):
    """Berechnet absolute und prozentuale Veränderung."""
    try:
        abs_change = float(cur) - float(prev)
        if float(prev) != 0:
            pct_change = (abs_change / float(prev)) * 100
        else:
            pct_change = None
        return round(abs_change, 2), round(pct_change, 2) if pct_change is not None else None
    except:
        return 0, 0

# ===== DEFAULT & MOCK DATEN =====
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Oct 2019","Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"],
    "neukunden_monat": [3000, 600, 4200, 700, 4500, 650],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

MOCK_DATA = {
    "belegt": 20, "frei": 4, "vertragsdauer_durchschnitt": 8.5, "reminder_automat": 18,
    "social_facebook": 320, "social_google": 65, "belegungsgrad": 83.3,
    "kundenherkunft": {"Online": 14, "Empfehlung": 7, "Vorbeikommen": 3},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [8, 7, 10, 9, 6, 5],
    "zahlungsstatus": {"bezahlt": 22, "offen": 1, "überfällig": 1},
    "recommendations": [
        "Automatische Zahlungserinnerungen für alle Kunden aktivieren",
        "Google-Marketing-Budget leicht erhöhen",
        "Empfehlungsprogramm für bestehende Kunden einführen",
        "Flexible Kurzzeit-Mietoptionen bewerben"
    ],
    "customer_message": "Ihre Lagerfläche ist zu 71% ausgelastet mit einer durchschnittlichen Vertragsdauer von über 8 Monaten."
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
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    
    # ===== DEBUG SIDEBAR =====
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # Debug Info
        st.caption(f"🔧 Port: {os.environ.get('PORT', 'Nicht gesetzt')}")
        
        # n8n URL Eingabe
        n8n_url_input = st.text_input(
            "n8n Webhook URL",
            value=st.session_state.n8n_url,
            placeholder="https://deine-n8n-url.com/webhook",
            help="URL für die KI-Analyse"
        )
        st.session_state.n8n_url = n8n_url_input
        
        # Testmodus
        test_mode = st.checkbox("🧪 Testmodus (Mock-Daten)")
        
        # Debug-Modus
        st.session_state.debug_mode = st.checkbox("🐛 Debug-Modus aktivieren")
        
        st.divider()
        
        # Navigation
        page_options = ["📊 Übersicht", "👥 Kunden", "📦 Kapazität", "💰 Finanzen", "⚙️ Einstellungen"]
        selected_page = st.selectbox("Navigation", page_options)
        
        # Reset Button
        if st.button("🗑️ Alle Daten zurücksetzen", use_container_width=True):
            st.session_state.data = DEFAULT_DATA.copy()
            st.session_state.prev = DEFAULT_DATA.copy()
            st.session_state.history = []
            st.session_state.last_response = None
            st.success("✅ Alle Daten zurückgesetzt!")
            time.sleep(1)
            st.rerun()
        
        # Debug-Info anzeigen
        if st.session_state.debug_mode:
            st.divider()
            st.subheader("🔍 Debug Info")
            if st.session_state.last_response:
                with st.expander("Letzte n8n-Antwort"):
                    st.json(st.session_state.last_response)
            
            if st.button("Session State anzeigen"):
                st.json({k: v for k, v in st.session_state.items() if k != 'last_response'})
    
    # ===== HAUPTINHALT =====
    if selected_page == "📊 Übersicht":
        render_overview(test_mode)
    elif selected_page == "👥 Kunden":
        render_customers()
    elif selected_page == "📦 Kapazität":
        render_capacity()
    elif selected_page == "💰 Finanzen":
        render_finance()
    elif selected_page == "⚙️ Einstellungen":
        render_settings()

# ===== SEITENFUNKTIONEN =====
def render_overview(test_mode=False):
    """Hauptübersichtsseite mit Datei-Upload."""
    st.title("📊 Dashboard Übersicht")
    
    # Datei-Upload Section
    st.header("📥 Daten hochladen & analysieren")
    
    uploaded_files = st.file_uploader(
        "Excel/CSV Dateien hochladen",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help="Lade deine Business-Daten für die KI-Analyse hoch"
    )
    
    col1, col2 = st.columns([1, 1])
    with col1:
        analyze_btn = st.button("🚀 KI-Analyse starten", type="primary", use_container_width=True)
    with col2:
        mock_btn = st.button("🧪 Mock-Daten laden", use_container_width=True)
    
    # Mock-Daten laden
    if mock_btn:
        st.session_state.prev = st.session_state.data.copy()
        st.session_state.data = MOCK_DATA
        st.session_state.history.append({
            "ts": datetime.now().isoformat(),
            "data": MOCK_DATA.copy(),
            "files": ["Mock-Daten"],
            "source": "mock"
        })
        st.success("✅ Mock-Daten erfolgreich geladen!")
        time.sleep(1)
        st.rerun()
    
    # Analyse durchführen
    if analyze_btn and uploaded_files:
        perform_analysis(uploaded_files, test_mode)
    
    # Datei-Info anzeigen
    if uploaded_files:
        with st.expander("📁 Hochgeladene Dateien", expanded=False):
            for file in uploaded_files:
                st.write(f"**{file.name}** ({file.size/1024:.1f} KB)")
                if file.name.lower().endswith(('.xlsx', '.xls')):
                    try:
                        df = pd.read_excel(file)
                        st.caption(f"→ {len(df)} Zeilen, {len(df.columns)} Spalten")
                    except:
                        st.caption("→ Konnte nicht gelesen werden")
    
    # KPIs anzeigen
    st.header("📈 Key Performance Indicators")
    render_kpis()
    
    # Charts Section
    st.header("📊 Visualisierungen")
    col1, col2 = st.columns(2)
    
    with col1:
        # Neukunden Chart
        import plotly.graph_objects as go
        labels = st.session_state.data.get("neukunden_labels", [])
        values = st.session_state.data.get("neukunden_monat", [])
        fig = go.Figure(data=[go.Bar(x=labels, y=values, name="Neukunden")])
        fig.update_layout(
            title="Neukunden pro Monat",
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=400
        )
        st.plotly_chart(fig, width='stretch')
    
    with col2:
        # Belegungsgrad Donut
        belegungsgrad = st.session_state.data.get("belegungsgrad", 0)
        fig = go.Figure(data=[go.Pie(
            labels=["Belegt", "Frei"],
            values=[belegungsgrad, 100 - belegungsgrad],
            hole=.6,
            marker_colors=['#3B82F6', '#E5E7EB']
        )])
        fig.update_layout(
            title=f"Belegungsgrad: {belegungsgrad}%",
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig, width='stretch')
    
    # KI-Empfehlungen anzeigen
    recommendations = st.session_state.data.get("recommendations", [])
    if recommendations:
        st.header("🤖 KI-Empfehlungen")
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. **{rec}**")
        
        customer_message = st.session_state.data.get("customer_message", "")
        if customer_message:
            with st.expander("📝 Kundennachricht-Vorschlag anzeigen"):
                st.info(customer_message)

def render_kpis():
    """Zeigt alle KPIs in einer Grid an."""
    data = st.session_state.data
    prev = st.session_state.prev
    
    kpis = [
        ("Belegt", "belegt", "", "📦"),
        ("Frei", "frei", "", "🆓"),
        ("Belegungsgrad", "belegungsgrad", " %", "📊"),
        ("Ø Vertragsdauer", "vertragsdauer_durchschnitt", " Monate", "📅"),
        ("Facebook Leads", "social_facebook", "", "👍"),
        ("Google Reviews", "social_google", "", "⭐")
    ]
    
    cols = st.columns(len(kpis))
    for idx, (label, key, suffix, icon) in enumerate(kpis):
        with cols[idx]:
            current = data.get(key, 0)
            previous = prev.get(key, 0)
            abs_change, pct_change = delta(previous, current)
            
            display_value = f"{current}{suffix}"
            display_delta = f"{abs_change:+.0f}{suffix}" if abs_change != 0 else None
            
            st.metric(
                label=f"{icon} {label}",
                value=display_value,
                delta=display_delta
            )

def perform_analysis(uploaded_files, test_mode=False):
    """Führt die KI-Analyse durch."""
    import requests
    
    with st.spinner("🧠 KI analysiert Daten... (dies kann bis zu 45 Sekunden dauern)"):
        # Dateien verarbeiten
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
                st.warning(f"Konnte {excel_file.name} nicht verarbeiten: {str(e)[:50]}")
        
        # Testmodus
        if test_mode:
            st.session_state.prev = st.session_state.data.copy()
            merged_mock = merge_data(MOCK_DATA, excel_merge)
            st.session_state.data = merged_mock
            st.session_state.history.append({
                "ts": datetime.now().isoformat(),
                "data": merged_mock.copy(),
                "files": [f.name for f in uploaded_files],
                "source": "test_mode"
            })
            st.success("✅ Test-Analyse erfolgreich!")
            time.sleep(1)
            st.rerun()
        
        # Echte n8n-Analyse
        elif st.session_state.n8n_url and st.session_state.n8n_url.startswith("http"):
            status, message, response = post_to_n8n(
                st.session_state.n8n_url,
                (main_file.name, main_file.getvalue()),
                str(uuid.uuid4())
            )
            
            # Debug-Ausgabe
            if st.session_state.debug_mode:
                with st.expander("🔍 Debug: n8n Kommunikation", expanded=True):
                    st.write(f"**Status:** {status}")
                    st.write(f"**Meldung:** {message}")
                    if response:
                        st.write("**Rohantwort:**")
                        st.json(response)
            
            st.session_state.last_response = response
            
            if status == 200 and response:
                # JSON extrahieren
                json_data = extract_json_from_markdown(str(response))
                
                # ROBUSTE DATENVERARBEITUNG für verschiedene n8n-Formate
                processed_data = None
                
                if isinstance(json_data, dict):
                    # FALL 1: Normales Format mit metrics, recommendations, customer_message
                    if all(k in json_data for k in ['metrics', 'recommendations', 'customer_message']):
                        processed_data = json_data
                    
                    # FALL 2: Doppelt verschachtelt (dein aktuelles Problem)
                    elif 'metrics' in json_data and isinstance(json_data['metrics'], dict):
                        if 'metrics' in json_data['metrics']:  # Doppelte Verschachtelung
                            processed_data = {
                                'metrics': json_data['metrics'].get('metrics', {}),
                                'recommendations': json_data.get('recommendations', []),
                                'customer_message': json_data.get('customer_message', '')
                            }
                        else:  # Einfache Verschachtelung
                            processed_data = {
                                'metrics': json_data['metrics'],
                                'recommendations': json_data.get('recommendations', []),
                                'customer_message': json_data.get('customer_message', '')
                            }
                    
                    # FALL 3: Direkte Metriken ohne Wrapper
                    elif any(k in json_data for k in ['belegt', 'belegungsgrad', 'vertragsdauer_durchschnitt']):
                        processed_data = {
                            'metrics': json_data,
                            'recommendations': json_data.get('recommendations', []),
                            'customer_message': json_data.get('customer_message', '')
                        }
                
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
                    
                    # History aktualisieren
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
                        st.json(json_data)
            else:
                st.error(f"❌ Fehler bei KI-Analyse: {message}")
        else:
            st.error("❌ Bitte gültige n8n URL eingeben oder Testmodus aktivieren")

def render_customers():
    """Kundenseite."""
    st.title("👥 Kundenanalyse")
    
    data = st.session_state.data
    
    # Kundenherkunft
    st.header("📍 Kundenherkunft")
    herkunft = data.get("kundenherkunft", {})
    
    if herkunft:
        col1, col2 = st.columns(2)
        
        with col1:
            import plotly.express as px
            df_herkunft = pd.DataFrame({
                "Kanal": list(herkunft.keys()),
                "Anzahl": list(herkunft.values())
            })
            fig = px.pie(df_herkunft, values='Anzahl', names='Kanal', 
                        title='Verteilung nach Kanal')
            st.plotly_chart(fig, width='stretch')
        
        with col2:
            st.dataframe(df_herkunft, width='stretch')
    
    # Empfehlungen für Kundenakquise
    st.header("💡 Kundenakquise-Strategien")
    st.markdown("""
    - **🤝 Referral-Programm**: 25€ Guthaben pro geworbenem Neukunden
    - **🌐 Google Business**: Regelmäßig neue Fotos und Bewertungen anfragen
    - **📩 CRM-Nurturing**: Automatisierte Follow-up E-Mails bei Interessenten
    - **🎯 Zielgruppen-Marketing**: Gezielte Ansprache von Umzugsunternehmen
    - **📱 Social Media Ads**: Facebook/Instagram Kampagnen für junge Zielgruppen
    """)

def render_capacity():
    """Kapazitätsseite."""
    st.title("📦 Kapazitätsmanagement")
    
    data = st.session_state.data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Aktuelle Auslastung")
        st.metric("Belegte Einheiten", data.get("belegt", 0))
        st.metric("Freie Einheiten", data.get("frei", 0))
        st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
    
    with col2:
        # Kapazitäts-Diagramm
        import plotly.graph_objects as go
        labels = ["Belegt", "Frei"]
        values = [data.get("belegt", 0), data.get("frei", 0)]
        
        fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=['#3B82F6', '#E5E7EB'])])
        fig.update_layout(
            title="Kapazitätsverteilung",
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=300
        )
        st.plotly_chart(fig, width='stretch')
    
    # Optimierungsvorschläge
    st.header("⚡ Optimierungsvorschläge")
    belegungsgrad = data.get("belegungsgrad", 0)
    
    if belegungsgrad < 70:
        st.warning(f"⚠️ Niedrige Auslastung ({belegungsgrad}%)")
        st.markdown("""
        **Empfehlungen:**
        - 2-Wochen-Aktion: 15% Rabatt für Neukunden
        - Kooperationen mit lokalen Umzugsunternehmen
        - Social Media Kampagne starten
        - Flexible Kurzzeitmieten bewerben
        """)
    elif belegungsgrad < 85:
        st.info(f"✅ Gute Auslastung ({belegungsgrad}%)")
        st.markdown("""
        **Weiter optimieren:**
        - Preise für Standardeinheiten stabil halten
        - Kundenbindungsprogramm ausbauen
        - Empfehlungsprogramm intensivieren
        """)
    else:
        st.success(f"🚀 Hervorragende Auslastung ({belegungsgrad}%)")
        st.markdown("""
        **Nächste Schritte:**
        - Preise für kleine Einheiten um 3-5% erhöhen
        - Warteliste für beliebte Einheitengrößen
        - Premium-Angebote entwickeln
        - Expansion prüfen
        """)

def render_finance():
    """Finanzseite."""
    st.title("💰 Finanzübersicht")
    
    data = st.session_state.data
    
    # Zahlungsstatus
    st.header("💳 Zahlungsstatus")
    status = data.get("zahlungsstatus", {})
    
    if status:
        col1, col2 = st.columns(2)
        
        with col1:
            df_status = pd.DataFrame({
                "Status": list(status.keys()),
                "Anzahl": list(status.values())
            })
            st.dataframe(df_status, width='stretch')
        
        with col2:
            import plotly.express as px
            fig = px.pie(df_status, values='Anzahl', names='Status', 
                        title='Zahlungsstatus Verteilung')
            st.plotly_chart(fig, width='stretch')
    
    # Vertragsdauer
    st.header("📅 Vertragsanalyse")
    vd = data.get("vertragsdauer_durchschnitt", 0)
    st.metric("Durchschnittliche Vertragsdauer", f"{vd} Monate")
    
    # Finanztipps
    st.header("💡 Finanzoptimierung")
    
    offen = status.get("offen", 0)
    überfällig = status.get("überfällig", 0)
    
    if offen + überfällig > 0:
        st.warning(f"⚠️ {offen + überfällig} offene/überfällige Zahlungen")
        st.markdown("""
        **Dringende Maßnahmen:**
        - Automatische Zahlungserinnerungen aktivieren
        - Bei Überfälligkeit: Telefonische Kontaktaufnahme
        - Skonto bei Vorauszahlung anbieten (2-3%)
        """)
    
    st.markdown("""
    **Allgemeine Empfehlungen:**
    - Quartalsweise Preisanpassung basierend auf Auslastung
    - Langfristige Verträge mit Rabatt fördern (6+ Monate = 5% Rabatt)
    - Kautionen optimieren (1-2 Monatsmieten)
    - Versicherungsoptionen als Zusatzleistung
    """)

def render_settings():
    """Einstellungsseite."""
    st.title("⚙️ Einstellungen & Export")
    
    data = st.session_state.data
    
    # Export Section
    st.header("📤 Daten exportieren")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # CSV Export
        csv_data = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            label="⬇️ CSV Export",
            data=csv_data,
            file_name=f"storage_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # JSON Export
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ JSON Export",
            data=json_str,
            file_name=f"storage_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        # Excel Export
        df = pd.DataFrame([data])
        excel_buffer = pd.ExcelWriter("temp_data.xlsx", engine='openpyxl')
        df.to_excel(excel_buffer, index=False)
        excel_buffer.close()
        with open("temp_data.xlsx", "rb") as f:
            excel_data = f.read()
        st.download_button(
            label="⬇️ Excel Export",
            data=excel_data,
            file_name=f"storage_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    # History
    st.header("📋 Analyseverlauf")
    history = st.session_state.history
    
    if history:
        for i, entry in enumerate(reversed(history[-5:]), 1):
            with st.expander(f"Analyse #{len(history)-i+1} - {entry['ts'][:10]} {entry['ts'][11:16]}"):
                st.write(f"**Quelle:** {entry.get('source', 'unknown')}")
                st.write(f"**Dateien:** {', '.join(entry['files'])}")
                if st.button(f"Daten anzeigen #{len(history)-i+1}", key=f"show_{i}"):
                    st.json(entry['data'])
    else:
        st.info("Noch keine Analysen durchgeführt")
    
    # System Info
    st.header("🔧 Systeminformation")
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.metric("Analysen gesamt", len(history))
        st.metric("Session aktiv", "Ja" if st.session_state.data else "Nein")
    
    with info_col2:
        st.metric("n8n URL gesetzt", "Ja" if st.session_state.n8n_url else "Nein")
        st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    
    # Reset Section
    st.header("🔄 System")
    
    if st.button("🔄 App komplett neu laden", type="secondary", use_container_width=True):
        st.rerun()

# ===== APP START =====
if __name__ == "__main__":
    main()
