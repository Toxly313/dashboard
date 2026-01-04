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

# ===== TENANT-KONFIGURATION (Später durch Datenbank ersetzen) =====
TENANTS = {
    "demo@kunde.de": {
        "tenant_id": "kunde_demo_123",
        "name": "Demo Kunde GmbH",
        "plan": "pro",
        "analyses_limit": 50,
        "analyses_used": 0
    },
    "test@firma.de": {
        "tenant_id": "firma_test_456", 
        "name": "Test Firma AG",
        "plan": "business",
        "analyses_limit": 200,
        "analyses_used": 0
    }
}

# ===== HILFSFUNKTIONEN =====
def post_to_n8n(url, file_tuple, tenant_id, uuid_str):
    """Sendet Daten an n8n - REINE JSON VERSION"""
    import requests
    import json
    import base64
    
    print(f"\n🚀 Sende REINES JSON an n8n")
    print(f"URL: {url}")
    print(f"Tenant-ID: {tenant_id}")
    print(f"UUID: {uuid_str}")
    
    # 1. Erstelle JSON Payload
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "metadata": {
            "source": "streamlit",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "customer_email": "demo@kunde.de"  # Beispiel
        }
    }
    
    # 2. Datei als Base64 hinzufügen (falls vorhanden)
    if file_tuple:
        file_name, file_content, file_type = file_tuple
        
        # Kodiere als Base64
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        
        payload["file"] = {
            "filename": file_name,
            "content_type": file_type,
            "data": file_b64,  # Base64 encoded
            "size": len(file_content)
        }
        
        print(f"📎 Datei: {file_name} ({len(file_content)} bytes) als Base64")
    
    # 3. Sende als PURE JSON
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print(f"📤 JSON Payload (Auszug): {json.dumps(payload)[:200]}...")
    
    try:
        response = requests.post(
            url,
            json=payload,  # WICHTIG: json= statt data=
            headers=headers,
            timeout=60
        )
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ Fehler: {response.text[:500]}")
            return response.status_code, f"HTTP {response.status_code}", None
        
        try:
            json_response = response.json()
            print("✅ JSON Response erhalten")
            return response.status_code, "Success", json_response
        except json.JSONDecodeError:
            print(f"⚠️ Kein JSON in Response: {response.text[:500]}")
            return response.status_code, "No JSON", response.text
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout nach 60s")
        return 408, "Timeout", None
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
        return 500, f"Error: {str(e)}", None
    
    # Debug-Info (wird in Streamlit-Logs angezeigt)
    print(f"[DEBUG] Sende an n8n: tenant_id={tenant_id}, uuid={uuid_str}")
    
    try:
        # 🚀 Multipart-Request: Datei + Formulardaten
        response = requests.post(
            url,
            files={'file': file_tuple} if file_tuple else None,
            data=data,  # ✅ WICHTIG: tenant_id als Form-Data-Feld
            timeout=45,
            headers={'User-Agent': 'Dashboard-KI/1.0'}
        )
        
        # Debug-Info für Response
        print(f"[DEBUG] n8n Response: Status={response.status_code}")
        
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
    
    # MULTI-TENANT: Login-Status
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "current_tenant" not in st.session_state:
        st.session_state.current_tenant = None
    
    # ===== SIDEBAR MIT LOGIN =====
    with st.sidebar:
        st.title("🔐 Login & Einstellungen")
        
        # Login/Logout Bereich
        if not st.session_state.logged_in:
            st.subheader("Anmelden")
            email = st.text_input("E-Mail", key="login_email")
            password = st.text_input("Passwort", type="password", key="login_password")
            
            if st.button("🚀 Anmelden", type="primary", use_container_width=True):
                if email in TENANTS:
                    # In Produktion: Passwort prüfen!
                    st.session_state.logged_in = True
                    st.session_state.current_tenant = TENANTS[email]
                    st.success(f"Willkommen, {TENANTS[email]['name']}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Ungültige E-Mail oder Passwort")
        else:
            # Eingeloggter Zustand
            tenant = st.session_state.current_tenant
            st.success(f"✅ Eingeloggt als: {tenant['name']}")
            st.info(f"📋 Plan: {tenant['plan'].upper()}")
            st.info(f"📊 Analysen: {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
            
            # ✅ TENANT-ID ANZEIGEN (für Debugging wichtig)
            st.info(f"🔑 Tenant-ID: `{tenant['tenant_id']}`")
            
            if st.button("🚪 Abmelden", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.current_tenant = None
                st.session_state.data = DEFAULT_DATA.copy()
                st.rerun()
        
        st.divider()
        
        # Nur wenn eingeloggt: Einstellungen anzeigen
        if st.session_state.logged_in:
            st.subheader("⚙️ n8n Konfiguration")
            
            # n8n URL
            n8n_url = st.text_input(
                "n8n Webhook URL",
                value=st.session_state.n8n_url,
                placeholder="https://tundtelectronics.app.n8n.cloud/webhook/process-business-data",
                key="n8n_url_input"
            )
            st.session_state.n8n_url = n8n_url
            
            if n8n_url:
                st.caption(f"Verwendet: `{n8n_url[:50]}...`")
            
            # Debug Mode
            st.session_state.debug_mode = st.checkbox("🐛 Debug-Modus", key="debug_checkbox")
            
            st.divider()
            
            # Navigation (nur für eingeloggte Benutzer)
            st.subheader("📱 Navigation")
            page = st.radio(
                "Menü",
                ["📊 Übersicht", "👥 Kunden", "📦 Kapazität", "💰 Finanzen", "⚙️ System"],
                key="nav_radio"
            )
            
            st.divider()
            
            # Reset Button
            if st.button("🗑️ Zurücksetzen", use_container_width=True, key="reset_btn"):
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
        else:
            # Nicht eingeloggt: Nur Info
            st.info("👆 Bitte zuerst anmelden, um das Dashboard zu nutzen.")
            page = "📊 Übersicht"  # Default-Seite
    
    # ===== HAUPTINHALT =====
    if not st.session_state.logged_in:
        # Login-Seite anzeigen
        render_login_page()
    else:
        # Eingeloggte Benutzer sehen das Dashboard
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
def render_login_page():
    """Login-Seite für nicht eingeloggte Benutzer."""
    st.title("🔐 Self-Storage Business Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ## Willkommen!
        
        **KI-gestützte Analyse für Self-Storage Unternehmen:**
        
        ✅ **Auslastung optimieren**  
        ✅ **Zahlungsmoral verbessern**  
        ✅ **Marketing-ROI steigern**  
        ✅ **Kundenbindung erhöhen**
        
        **Test-Zugänge:**
        - **E-Mail:** `demo@kunde.de` → Tenant-ID: `kunde_demo_123`
        - **E-Mail:** `test@firma.de` → Tenant-ID: `firma_test_456`
        - **Passwort:** (beliebig für Demo)
        """)
    
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", 
                caption="Data-Driven Decisions for SelfStorage")
    
    st.divider()
    
    # Demo-Dashboard Vorschau
    st.subheader("📊 Dashboard Vorschau")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Auslastung", "71%", "Verbesserungswürdig")
    with col2:
        st.metric("Ø Vertragsdauer", "8.5", "Monate")
    with col3:
        st.metric("Zahlungsmoral", "87%", "Bezugsrate")
    with col4:
        st.metric("Kunden-Zufriedenheit", "4.2/5", "Sterne")
    
    st.info("💡 **Hinweis:** Dies ist eine Demo-Version. Für vollen Zugang bitte anmelden.")

def render_overview():
    """Hauptseite mit Upload und Analyse."""
    tenant = st.session_state.current_tenant
    st.title(f"📊 Dashboard - {tenant['name']}")
    
    # Tenant-Info Box
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info(f"**Tenant-ID:** `{tenant['tenant_id']}`")
    with col2:
        st.info(f"**Plan:** {tenant['plan'].upper()}")
    with col3:
        st.info(f"**Analysen:** {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
    with col4:
        st.info(f"**Unternehmen:** {tenant['name']}")
    
    # 🎯 WICHTIGER HINWEIS ZUR TENANT-ID
    st.info("""
    **ℹ️ Wichtig für n8n-Kommunikation:** 
    Die Tenant-ID `{tenant_id}` wird automatisch mit jeder hochgeladenen Datei an n8n gesendet.
    Diese ID wird verwendet, um Ihre Daten in der Datenbank zu identifizieren.
    """.format(tenant_id=tenant['tenant_id']))
    
    # Upload Bereich
    st.header("📥 Daten analysieren")
    
    uploaded_files = st.file_uploader(
        "Dateien hochladen (Excel/CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        analyze_btn = st.button("🚀 KI-Analyse starten", type="primary", use_container_width=True, key="analyze_btn")
    with col2:
        mock_btn = st.button("🧪 Mock-Daten", use_container_width=True, key="mock_btn")
    with col3:
        if st.button("📋 Datenvorschau", use_container_width=True, key="preview_btn") and uploaded_files:
            try:
                df = pd.read_excel(uploaded_files[0])
                st.dataframe(df.head(), width='stretch')
                st.caption(f"Datei: {uploaded_files[0].name} | Größe: {len(uploaded_files[0].getvalue())} bytes")
            except:
                st.warning("Konnte Datei nicht lesen")
    
    # Mock-Daten
    if mock_btn:
        mock_data = {
            "belegt": 22, "frei": 3, "belegungsgrad": 88, 
            "vertragsdauer_durchschnitt": 9.1,
            "recommendations": [
                f"Testempfehlung für {tenant['name']}",
                "Optimieren Sie Ihre Lagerauslastung",
                "Starten Sie eine Marketing-Kampagne"
            ],
            "customer_message": f"Mock-Daten für {tenant['name']} (Tenant-ID: {tenant['tenant_id']}) geladen."
        }
        st.session_state.prev = st.session_state.data.copy()
        st.session_state.data = {**st.session_state.data, **mock_data}
        st.success("✅ Mock-Daten geladen!")
        time.sleep(1)
        st.rerun()
    
    # Echte Analyse (MIT TENANT-ID)
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

# In n8n: Function Node vor HTTP Request zu Streamlit
const metrics = {
  belegt: 142,
  frei: 58,
  vertragsdauer_durchschnitt: 8.5,
  reminder_automat: 67,
  social_facebook: 23,
  social_google: 19,
  belegungsgrad: 71.0,
  kundenherkunft: {
    Online: 45,
    Empfehlung: 32,
    Vorbeikommen: 23
  },
  neukunden_labels: ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
  neukunden_monat: [12, 10, 14, 11, 15, 13, 16, 14, 12, 15, 11, 13],
  zahlungsstatus: {
    bezahlt: 128,
    offen: 9,
    überfällig: 5
  }
};

const recommendations = [
  "Belegungsgrad von 71% kann auf 85% optimiert werden",
  "Zahlungserinnerungen automatisieren für bessere Zahlungsmoral",
  "Google-Bewertungen erhöhen für mehr Online-Sichtbarkeit"
];

const customer_message = "Ihre Lagerauslastung liegt bei 71% mit insgesamt 200 Einheiten. Optimieren Sie die Vermarktung freier Einheiten.";

return [{
  json: {
    // Streamlit-Format
    metrics: metrics,
    recommendations: recommendations,
    customer_message: customer_message,
    
    // ODER flaches Format (auch unterstützt):
    // ...metrics,
    // recommendations: recommendations,
    // customer_message: customer_message,
    
    // Metadaten
    timestamp: new Date().toISOString(),
    tenant_id: items[0].json.tenant_id || "kunde_demo_123",
    status: "success"
  }
}];

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
    tenant = st.session_state.current_tenant
    
    # Tenant Info
    st.header("Tenant-Information")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Tenant-ID:** `{tenant['tenant_id']}`")
        st.info(f"**Firmenname:** {tenant['name']}")
    with col2:
        st.info(f"**Abo-Plan:** {tenant['plan'].upper()}")
        st.info(f"**Analysen genutzt:** {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
    
    # Export
    st.header("Daten exportieren")
    
    col1, col2 = st.columns(2)
    with col1:
        csv = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            "⬇️ CSV Export",
            csv,
            f"storage_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
    with col2:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            "⬇️ JSON Export",
            json_str,
            f"storage_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json",
            use_container_width=True
        )
    
    # History (tenant-spezifisch)
    st.header("Analyserverlauf")
    history = [h for h in st.session_state.history if h.get('tenant_id') == tenant['tenant_id']]
    
    if history:
        for i, entry in enumerate(reversed(history[-3:]), 1):
            with st.expander(f"Analyse {i} - {entry['ts'][11:16]} ({len(entry.get('files', []))} Dateien)"):
                st.write(f"**Dateien:** {', '.join(entry['files'])}")
                st.write(f"**Tenant:** {entry.get('tenant_name', entry.get('tenant_id', 'N/A'))}")
                st.write(f"**Quelle:** {entry.get('source', 'n8n')}")
                if entry.get('data', {}).get('recommendations'):
                    st.write("**Empfehlungen:**")
                    for rec in entry['data']['recommendations'][:2]:
                        st.write(f"- {rec}")
    else:
        st.info("Noch keine Analysen für diesen Tenant")
    
    # Systeminfo
    st.header("Systeminformation")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Analysen gesamt", len(history))
        st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    with col2:
        st.metric("n8n URL", "Gesetzt" if st.session_state.n8n_url else "Fehlt")
        st.metric("Session", "Aktiv")
    
    # n8n Workflow Info
    st.header("n8n Integration")
    st.info("""
    **Datenfluss:** Streamlit → n8n Webhook → KI-Analyse → Datenbank → Streamlit
    
    **Wichtig:**
    1. Tenant-ID wird automatisch an n8n gesendet
    2. n8n erwartet tenant_id im `formData` Teil des Requests
    3. Die Antwort wird automatisch für Ihr Dashboard verarbeitet
    """)

# ===== APP START =====
if __name__ == "__main__":
    main()
