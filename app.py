import os, uuid, json, streamlit as st
from datetime import datetime
import numpy as np, pandas as pd

# ===== KONFIGURATION =====
st.set_page_config(
    page_title="Self-Storage Pro Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CSS FÜR WEISSEN HINTERGRUND =====
st.markdown("""
<style>
    .stApp {
        background-color: white !important;
    }
    .main-header {
        color: #1E3A8A;
        border-bottom: 3px solid #3B82F6;
        padding-bottom: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .dropzone {
        border: 2px dashed #3B82F6;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background-color: #F0F9FF;
        margin-bottom: 1rem;
    }
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== HILFSFUNKTIONEN =====
def post_to_n8n(url, file_tuple, uuid_str):
    """
    Sendet Datei an n8n Webhook und gibt Antwort zurück.
    """
    import requests
    
    if not url or not url.startswith("http"):
        return 400, "Ungültige URL", None
    
    files = {'file': file_tuple} if file_tuple else None
    data = {'uuid': uuid_str}
    
    try:
        timeout = 45
        response = requests.post(
            url, 
            files=files, 
            data=data, 
            timeout=timeout,
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
            response_json = response.json()
            return response.status_code, "Success", response_json
        except json.JSONDecodeError as e:
            return response.status_code, f"Kein gültiges JSON: {str(e)}", None
            
    except requests.exceptions.Timeout:
        return 408, f"Timeout nach {timeout}s", None
    except requests.exceptions.ConnectionError:
        return 503, "Verbindungsfehler", None
    except requests.exceptions.RequestException as e:
        return 500, f"Request Fehler: {str(e)}", None
    except Exception as e:
        return 500, f"Unerwarteter Fehler: {str(e)}", None

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
        st.warning(f"Konnte nicht alle Daten verarbeiten: {str(e)[:100]}")
    
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

def delta(prev, cur):
    """Berechnet Veränderung."""
    try:
        abs_change = float(cur) - float(prev)
        if float(prev) != 0:
            pct_change = (abs_change / float(prev)) * 100
        else:
            pct_change = None
        return round(abs_change, 2), round(pct_change, 2) if pct_change is not None else None
    except:
        return 0, 0

def kpi_state(key, value):
    """Bestimmt KPI-Status für Farbgebung."""
    thresholds = {
        'belegt': (0, 10, 20),
        'belegungsgrad': (70, 85, 95),
        'vertragsdauer_durchschnitt': (3, 6, 12),
        'social_google': (20, 50, 100)
    }
    
    if key in thresholds:
        low, medium, high = thresholds[key]
        if value < low:
            return 'critical'
        elif value < medium:
            return 'warning'
        elif value < high:
            return 'neutral'
        else:
            return 'good'
    
    return 'neutral'

def extract_json_from_markdown(text):
    """Extrahiert JSON aus Markdown-Codeblöcken."""
    if not text or not isinstance(text, str):
        return None
    
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass
    
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
    except:
        pass
    
    return None

# ===== DEFAULT DATEN =====
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Oct 2019","Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"],
    "neukunden_monat": [3000, 600, 4200, 700, 4500, 650],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ===== MOCK DATEN FÜR TEST =====
MOCK_DATA = {
    "belegt": 20, "frei": 4, "vertragsdauer_durchschnitt": 8.5, "reminder_automat": 18,
    "social_facebook": 320, "social_google": 65, "belegungsgrad": 83.3,
    "kundenherkunft": {"Online": 14, "Empfehlung": 7, "Vorbeikommen": 3},
    "neukunden_labels": ["Oct 2019","Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"],
    "neukunden_monat": [3500, 800, 4800, 900, 5000, 800],
    "zahlungsstatus": {"bezahlt": 22, "offen": 1, "überfällig": 1},
    "recommendations": [
        "Belegung auf 90% steigern durch gezielte Marketingaktionen",
        "Vertragsdauer auf durchschnittlich 12 Monate erhöhen",
        "Social Media Präsenz verstärken für mehr Online-Leads"
    ],
    "customer_message": "Wir freuen uns, Ihnen mitteilen zu können, dass wir unsere Belegung optimiert haben und neue attraktive Angebote für Sie bereithalten!"
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
    if "test_mode" not in st.session_state:
        st.session_state.test_mode = False
    if "n8n_url" not in st.session_state:
        st.session_state.n8n_url = os.environ.get("N8N_URL", "")
    
    # Header
    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        st.image("https://cdn-icons-png.flaticon.com/512/2103/2103655.png", width=80)
    with col_title:
        st.markdown('<h1 class="main-header">📊 Self-Storage Pro Dashboard</h1>', unsafe_allow_html=True)
        st.markdown("KI-gestützte Datenanalyse für dein Self-Storage Business")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        # Port Debug Info
        port = os.environ.get('PORT', 'Nicht gesetzt')
        st.caption(f"🔧 Debug: PORT={port}")
        
        # n8n URL
        n8n_url_input = st.text_input(
            "n8n Webhook URL",
            value=st.session_state.n8n_url,
            placeholder="https://deine-n8n-url.com/webhook",
            help="URL für die KI-Analyse"
        )
        st.session_state.n8n_url = n8n_url_input
        
        # Testmodus
        test_mode = st.checkbox("🧪 Testmodus aktivieren (ohne echte KI)")
        st.session_state.test_mode = test_mode
        
        if test_mode:
            st.info("Im Testmodus werden Mock-Daten verwendet")
        
        st.divider()
        
        # Navigation
        page_options = ["Übersicht", "Kunden", "Kapazität", "Finanzen", "Einstellungen"]
        selected_page = st.selectbox("Navigation", page_options)
        
        st.divider()
        
        # Reset Button
        if st.button("🗑️ Daten zurücksetzen", use_container_width=True):
            st.session_state.data = DEFAULT_DATA.copy()
            st.session_state.prev = DEFAULT_DATA.copy()
            st.session_state.history = []
            st.success("✅ Daten zurückgesetzt!")
    
    # Hauptinhalt basierend auf ausgewählter Seite
    if selected_page == "Übersicht":
        render_overview()
    elif selected_page == "Kunden":
        render_customers()
    elif selected_page == "Kapazität":
        render_capacity()
    elif selected_page == "Finanzen":
        render_finance()
    elif selected_page == "Einstellungen":
        render_settings()

# ===== SEITENFUNKTIONEN =====
def render_overview():
    """Hauptübersichtsseite"""
    st.header("📈 Übersicht")
    
    # Datei-Upload Card
    with st.container():
        st.subheader("📥 Daten hochladen & analysieren")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            uploaded_files = st.file_uploader(
                "Dateien hochladen",
                type=["csv", "xlsx", "xls", "json"],
                accept_multiple_files=True,
                help="CSV, Excel oder JSON Dateien"
            )
        
        with col2:
            analyze_col1, analyze_col2 = st.columns(2)
            with analyze_col1:
                analyze_btn = st.button("🚀 Analysieren", type="primary", use_container_width=True)
            with analyze_col2:
                if st.button("🧪 Mock Test", use_container_width=True):
                    st.session_state.test_mode = True
                    st.session_state.prev = st.session_state.data.copy()
                    st.session_state.data = MOCK_DATA.copy()
                    st.session_state.history.append({
                        "ts": datetime.now().isoformat(),
                        "data": MOCK_DATA.copy(),
                        "files": ["Mock-Daten"],
                        "ki_analyse": True
                    })
                    st.success("✅ Mock-Daten geladen!")
                    st.rerun()
        
        # Dateien anzeigen
        if uploaded_files:
            st.info(f"📁 {len(uploaded_files)} Datei(en) zum Upload bereit")
            for file in uploaded_files:
                st.caption(f"• {file.name} ({file.size/1024:.1f} KB)")
        
        # Analyse durchführen
        if analyze_btn and uploaded_files:
            perform_analysis(uploaded_files)
    
    # KPIs anzeigen
    render_kpis()
    
    # Charts
    st.subheader("📊 Charts")
    col1, col2 = st.columns(2)
    
    with col1:
        # Belegungs-Chart
        import plotly.graph_objects as go
        
        labels = st.session_state.data.get("neukunden_labels", [])
        values = st.session_state.data.get("neukunden_monat", [])
        
        fig = go.Figure(data=[go.Bar(x=labels, y=values)])
        fig.update_layout(
            title="Neukunden pro Monat",
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Belegungsgrad Donut
        belegungsgrad = st.session_state.data.get("belegungsgrad", 0)
        
        fig = go.Figure(data=[go.Pie(
            labels=["Belegt", "Frei"],
            values=[belegungsgrad, 100 - belegungsgrad],
            hole=.6
        )])
        fig.update_layout(
            title=f"Belegungsgrad: {belegungsgrad}%",
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # KI-Empfehlungen
    if st.session_state.data.get("recommendations"):
        st.subheader("🤖 KI-Empfehlungen")
        for i, rec in enumerate(st.session_state.data["recommendations"], 1):
            st.markdown(f"{i}. **{rec}**")
        
        if st.session_state.data.get("customer_message"):
            with st.expander("📝 Kundennachricht-Vorschlag"):
                st.info(st.session_state.data["customer_message"])

def render_kpis():
    """KPIs anzeigen"""
    data = st.session_state.data
    prev = st.session_state.prev
    
    kpis = [
        ("Belegt", "belegt", None),
        ("Frei", "frei", None),
        ("Belegungsgrad", "belegungsgrad", " %"),
        ("Ø Vertragsdauer", "vertragsdauer_durchschnitt", " Monate"),
        ("Facebook", "social_facebook", None),
        ("Google", "social_google", None)
    ]
    
    cols = st.columns(len(kpis))
    
    for idx, (label, key, suffix) in enumerate(kpis):
        with cols[idx]:
            current = data.get(key, 0)
            previous = prev.get(key, 0)
            
            # Delta berechnen
            abs_change, pct_change = delta(previous, current)
            
            # Formatierung
            display_value = f"{current}{suffix}" if suffix else current
            display_delta = f"{'+' if abs_change >= 0 else ''}{abs_change}"
            
            # Metrik anzeigen
            st.metric(
                label=label,
                value=display_value,
                delta=display_delta
            )

def perform_analysis(uploaded_files):
    """Führt die KI-Analyse durch"""
    import re
    
    with st.spinner("🧠 KI analysiert Daten... (kann bis zu 45s dauern)"):
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
                st.warning(f"Excel-Fehler ({excel_file.name}): {e}")
        
        # Testmodus oder echte KI-Analyse
        if st.session_state.test_mode:
            # Mock-Daten verwenden
            st.session_state.prev = st.session_state.data.copy()
            st.session_state.data = merge_data(MOCK_DATA, excel_merge)
            
            # History aktualisieren
            st.session_state.history.append({
                "ts": datetime.now().isoformat(),
                "data": st.session_state.data.copy(),
                "files": [f.name for f in uploaded_files],
                "ki_analyse": True
            })
            
            st.success("✅ Mock-Analyse erfolgreich!")
            
        elif st.session_state.n8n_url and st.session_state.n8n_url.startswith("http"):
            # Echte n8n-Analyse
            status, message, response = post_to_n8n(
                st.session_state.n8n_url,
                (main_file.name, main_file.getvalue()),
                str(uuid.uuid4())
            )
            
            if status == 200 and response:
                # JSON aus Antwort extrahieren
                json_data = extract_json_from_markdown(str(response))
                
                if json_data:
                    # Metriken übernehmen
                    base = json_data.get("metrics", json_data)
                    
                    # Recommendations und Message speichern
                    recommendations = json_data.get("recommendations", [])
                    customer_message = json_data.get("customer_message", "")
                    
                    # Mit Excel-Daten mergen
                    merged_data = merge_data(base, excel_merge)
                    merged_data["recommendations"] = recommendations
                    merged_data["customer_message"] = customer_message
                    
                    # Session State aktualisieren
                    st.session_state.prev = st.session_state.data.copy()
                    st.session_state.data = merged_data
                    
                    # History aktualisieren
                    st.session_state.history.append({
                        "ts": datetime.now().isoformat(),
                        "data": merged_data.copy(),
                        "files": [f.name for f in uploaded_files],
                        "ki_analyse": True
                    })
                    
                    st.success(f"✅ KI-Analyse erfolgreich! {len(recommendations)} Empfehlungen")
                else:
                    st.error("❌ KI-Antwort konnte nicht verarbeitet werden")
            else:
                st.error(f"❌ Fehler bei KI-Analyse: {message}")
        else:
            st.error("❌ Bitte n8n URL eingeben oder Testmodus aktivieren")
    
    st.rerun()

def render_customers():
    """Kundenseite"""
    st.header("👥 Kunden")
    
    data = st.session_state.data
    
    # Kundenherkunft
    st.subheader("Kundenherkunft")
    herkunft = data.get("kundenherkunft", {})
    
    if herkunft:
        col1, col2 = st.columns(2)
        
        with col1:
            df = pd.DataFrame({
                "Kanal": list(herkunft.keys()),
                "Anzahl": list(herkunft.values())
            })
            st.dataframe(df, use_container_width=True)
        
        with col2:
            import plotly.express as px
            fig = px.pie(
                values=list(herkunft.values()),
                names=list(herkunft.keys()),
                title="Kundenherkunft Verteilung"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Empfehlungen für Kunden
    st.subheader("💡 Kundenempfehlungen")
    st.markdown("""
    - **🤝 Referral-Programm**: 25€ Guthaben pro geworbenem Neukunden
    - **🌐 Google Business**: Regelmäßig neue Fotos und Bewertungen anfragen
    - **📩 CRM-Nurturing**: Automatisierte Follow-up E-Mails
    - **🎯 Zielgruppen-Marketing**: Gezielte Ansprache von Umzugsunternehmen
    """)

def render_capacity():
    """Kapazitätsseite"""
    st.header("📦 Kapazität")
    
    data = st.session_state.data
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Belegt", data.get("belegt", 0))
        st.metric("Frei", data.get("frei", 0))
        st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
    
    with col2:
        # Kapazitäts-Diagramm
        import plotly.graph_objects as go
        
        labels = ["Belegt", "Frei"]
        values = [data.get("belegt", 0), data.get("frei", 0)]
        
        fig = go.Figure(data=[go.Bar(x=labels, y=values)])
        fig.update_layout(
            title="Kapazitätsauslastung",
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Optimierungsvorschläge
    st.subheader("⚡ Optimierungsvorschläge")
    
    belegungsgrad = data.get("belegungsgrad", 0)
    
    if belegungsgrad < 85:
        st.warning(f"Belegungsgrad von {belegungsgrad}% ist optimierbar")
        st.markdown("""
        **Vorschläge:**
        - 2-Wochen-Aktion: 10% Rabatt für Neukunden (Mindestlaufzeit 3 Monate)
        - Social Media Kampagne starten
        - Kooperationen mit Umzugsunternehmen eingehen
        """)
    elif belegungsgrad >= 95:
        st.success(f"Belegungsgrad von {belegungsgrad}% ist ausgezeichnet")
        st.markdown("""
        **Vorschläge:**
        - Preise für kleine Einheiten um 3-5% erhöhen
        - Warteliste für beliebte Einheiten einführen
        - Kundenbindungsprogramm verstärken
        """)
    else:
        st.info(f"Belegungsgrad von {belegungsgrad}% ist gut")
        st.markdown("Weiter so! Regelmäßige Überwachung der Auslastung empfohlen.")

def render_finance():
    """Finanzseite"""
    st.header("💰 Finanzen")
    
    data = st.session_state.data
    
    # Zahlungsstatus
    st.subheader("Zahlungsstatus")
    status = data.get("zahlungsstatus", {})
    
    if status:
        col1, col2 = st.columns(2)
        
        with col1:
            df = pd.DataFrame({
                "Status": list(status.keys()),
                "Anzahl": list(status.values())
            })
            st.dataframe(df, use_container_width=True)
        
        with col2:
            import plotly.express as px
            fig = px.pie(
                values=list(status.values()),
                names=list(status.keys()),
                title="Zahlungsstatus Verteilung"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Vertragsdauer
    st.subheader("Vertragsdauer")
    vd = data.get("vertragsdauer_durchschnitt", 0)
    st.metric("Durchschnittliche Vertragsdauer", f"{vd} Monate")
    
    # Finanztipps
    st.subheader("💡 Finanztipps")
    
    offen = status.get("offen", 0)
    überfällig = status.get("überfällig", 0)
    
    if offen + überfällig > 0:
        st.warning(f"{offen + überfällig} offene/überfällige Zahlungen")
        st.markdown("""
        **Maßnahmen:**
        - Mahnwesen automatisieren (E-Mail + SMS)
        - Zahlungserinnerungen 3 Tage vor Fälligkeit
        - Bei Überfälligkeit: Telefonische Kontaktaufnahme
        """)
    
    st.markdown("""
    **Allgemeine Empfehlungen:**
    - Skonto von 2% bei Zahlung innerhalb 7 Tagen anbieten
    - Quartalsweise Preisanpassung basierend auf Auslastung
    - Langfristige Verträge mit Rabatt fördern
    """)

def render_settings():
    """Einstellungsseite"""
    st.header("⚙️ Einstellungen")
    
    # Export
    st.subheader("📤 Daten exportieren")
    
    data = st.session_state.data
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV Export
        csv = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            label="⬇️ CSV Export",
            data=csv,
            file_name=f"storage_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # JSON Export
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ JSON Export",
            data=json_str,
            file_name=f"storage_data_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # History
    st.subheader("📋 Verlauf")
    history = st.session_state.history
    
    if history:
        for i, entry in enumerate(reversed(history[-5:]), 1):
            with st.expander(f"Analyse {i}: {entry['ts']}"):
                st.write(f"**Dateien:** {', '.join(entry['files'])}")
                st.write(f"**KI-Analyse:** {'✅' if entry.get('ki_analyse') else '❌'}")
    else:
        st.info("Noch keine Analysen durchgeführt")
    
    # Debug Info
    st.subheader("🔧 Debug Information")
    
    st.json({
        "session_state_keys": list(st.session_state.keys()),
        "data_keys": list(st.session_state.data.keys()),
        "history_count": len(st.session_state.history),
        "test_mode": st.session_state.test_mode,
        "n8n_url_set": bool(st.session_state.n8n_url)
    })

# ===== APP START =====
if __name__ == "__main__":
    main()
