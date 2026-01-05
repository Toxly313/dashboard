import os, uuid, json, re, time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import base64

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

# ===== TENANT-KONFIGURATION =====
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

# ===== HILFSFUNKTIONEN =====
def post_to_n8n_get_last(url, tenant_id, uuid_str):
    """Sendet GET-LAST Request an n8n (OHNE Datei) - für Login."""
    print(f"\n🔍 GET-LAST Request für Tenant: {tenant_id}")
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "action": "analyze",  # WICHTIG: Immer "analyze" senden!
        "metadata": {
            "source": "streamlit",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "purpose": "load_last_analysis",  # Hier unterscheiden wir
            "mode": "get_last"  # NEU: Modus-Flag hinzufügen
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30  # Kürzeres Timeout für get_last
        )
        
        print(f"📥 GET-LAST Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return response.status_code, f"HTTP {response.status_code}", None
        
        try:
            json_response = response.json()
            print(f"✅ GET-LAST JSON erhalten")
            return response.status_code, "Success", json_response
        except json.JSONDecodeError:
            print(f"⚠️ Kein JSON in GET-LAST Response: {response.text[:200]}")
            return response.status_code, "No JSON", response.text
            
    except requests.exceptions.Timeout:
        print("⏰ GET-LAST Timeout nach 30s")
        return 408, "Timeout", None
    except Exception as e:
        print(f"💥 GET-LAST Exception: {str(e)}")
        return 500, f"Error: {str(e)}", None

def post_to_n8n_analyze(url, file_tuple, tenant_id, uuid_str):
    """Sendet ANALYZE Request an n8n (MIT Datei) - für neue Analyse."""
    print(f"\n🚀 ANALYZE Request für Tenant: {tenant_id}")
    
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "action": "analyze",  # WICHTIG: Andere Action!
        "metadata": {
            "source": "streamlit",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "purpose": "new_analysis"
        }
    }
    
    # Datei hinzufügen
    if file_tuple:
        file_name, file_content, file_type = file_tuple
        file_b64 = base64.b64encode(file_content).decode('utf-8')
        payload["file"] = {
            "filename": file_name,
            "content_type": file_type,
            "data": file_b64,
            "size": len(file_content)
        }
        print(f"📎 Datei: {file_name} ({len(file_content)} bytes) als Base64")
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=60
        )
        
        print(f"📥 ANALYZE Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ ANALYZE Fehler: {response.text[:200]}")
            return response.status_code, f"HTTP {response.status_code}", None
        
        try:
            json_response = response.json()
            print("✅ ANALYZE JSON erhalten")
            return response.status_code, "Success", json_response
        except json.JSONDecodeError:
            print(f"⚠️ Kein JSON in ANALYZE Response: {response.text[:200]}")
            return response.status_code, "No JSON", response.text
            
    except requests.exceptions.Timeout:
        print("⏰ ANALYZE Timeout nach 60s")
        return 408, "Timeout", None
    except Exception as e:
        print(f"💥 ANALYZE Exception: {str(e)}")
        return 500, f"Error: {str(e)}", None

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

def create_comparison_chart(before_data, after_data, metric_key, title):
    """Erstellt Vergleichsdiagramm für eine Metrik."""
    if metric_key not in before_data or metric_key not in after_data:
        return None
    
    before_val = before_data[metric_key]
    after_val = after_data[metric_key]
    
    fig = go.Figure(data=[
        go.Bar(name='Vorher', x=['Vorher'], y=[before_val], marker_color='lightblue'),
        go.Bar(name='Nachher', x=['Nachher'], y=[after_val], marker_color='lightgreen')
    ])
    
    delta = after_val - before_val
    delta_color = 'green' if delta >= 0 else 'red'
    delta_symbol = '+' if delta >= 0 else ''
    
    fig.update_layout(
        title=f"{title}<br><span style='font-size:12px;color:{delta_color}'>{delta_symbol}{delta:.1f} Veränderung</span>",
        height=300,
        showlegend=True,
        yaxis_title=title
    )
    
    return fig

def create_timeseries_chart(history_data, metric_key, title):
    """Erstellt Zeitreihendiagramm aus History-Daten."""
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
    
    fig = go.Figure(data=[
        go.Scatter(x=dates, y=values, mode='lines+markers', name=title)
    ])
    
    fig.update_layout(
        title=f"Entwicklung: {title}",
        height=300,
        xaxis_title="Datum",
        yaxis_title=title
    )
    
    return fig

def load_last_analysis():
    """Lädt die letzte Analyse für den eingeloggten Tenant (BEIM LOGIN)."""
    if not st.session_state.logged_in:
        return False
    
    tenant_id = st.session_state.current_tenant['tenant_id']
    n8n_url = st.session_state.n8n_url
    
    if not n8n_url:
        st.warning("⚠️ n8n URL nicht gesetzt. Verwende Standarddaten.")
        st.session_state.current_data = DEFAULT_DATA.copy()
        st.session_state.before_analysis = DEFAULT_DATA.copy()
        return True
    
    with st.spinner("📊 Lade letzte Analyse..."):
        # GET-LAST an n8n senden
        status, message, response = post_to_n8n_get_last(
            n8n_url,
            tenant_id,
            str(uuid.uuid4())
        )
        
        if status == 200 and response:
            if response.get('current_analysis'):
                # Letzte Analyse gefunden
                current_analysis = response['current_analysis']
                
                # Sicherstellen, dass alle benötigten Felder vorhanden sind
                if 'metrics' in current_analysis:
                    metrics_data = current_analysis['metrics']
                else:
                    metrics_data = current_analysis
                
                # Empfehlungen und Nachricht
                recommendations = current_analysis.get('recommendations', [])
                customer_message = current_analysis.get('customer_message', 'Letzte Analyse')
                
                # Vollständige Datenstruktur erstellen
                loaded_data = {
                    **metrics_data,
                    'recommendations': recommendations,
                    'customer_message': customer_message,
                    'analysis_date': current_analysis.get('analysis_date', datetime.now().isoformat()),
                    'tenant_id': tenant_id
                }
                
                # In Session State speichern
                st.session_state.current_data = loaded_data
                st.session_state.before_analysis = loaded_data.copy()
                st.session_state.last_analysis_loaded = True
                
                print(f"✅ Letzte Analyse geladen für Tenant: {tenant_id}")
                return True
            else:
                # Keine vorherige Analyse gefunden
                st.session_state.current_data = DEFAULT_DATA.copy()
                st.session_state.before_analysis = DEFAULT_DATA.copy()
                st.info("ℹ️ Keine vorherige Analyse gefunden. Verwende Standarddaten.")
                return True
        else:
            st.error(f"❌ Fehler beim Laden: {message}")
            # Fallback: Default-Daten
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.before_analysis = DEFAULT_DATA.copy()
            return False

def perform_analysis(uploaded_files):
    """Führt die KI-Analyse durch und speichert Vergleich."""
    with st.spinner("🧠 KI analysiert Daten... (ca. 15-45 Sekunden)"):
        if not st.session_state.logged_in:
            st.error("❌ Kein Tenant eingeloggt")
            return
        
        tenant_id = st.session_state.current_tenant['tenant_id']
        tenant_name = st.session_state.current_tenant['name']
        
        # 1. Vorherige Daten als Vergleich speichern
        st.session_state.before_analysis = st.session_state.current_data.copy()
        
        # 2. Excel-Daten extrahieren (falls vorhanden)
        excel_merge = {}
        for excel_file in [f for f in uploaded_files if f.name.lower().endswith((".xlsx", ".xls"))]:
            try:
                df = pd.read_excel(excel_file)
                excel_metrics = extract_metrics_from_excel(df)
                excel_merge = merge_data(excel_merge, excel_metrics)
            except Exception as e:
                st.warning(f"Excel-Fehler: {str(e)[:50]}")
        
        # 3. n8n aufrufen (ANALYZE Action) MIT Modus-Flag
        n8n_url = st.session_state.n8n_url
        if not n8n_url:
            st.error("❌ Bitte n8n URL in der Sidebar eingeben")
            return
        
        main_file = uploaded_files[0]
        status, message, response = post_to_n8n_analyze(
            n8n_url,
            (main_file.name, main_file.getvalue(), main_file.type),
            tenant_id,
            str(uuid.uuid4()),
            mode="new_analysis"  # NEU: Modus-Parameter
        )
        # ... Rest bleibt
        
        # Debug
        if st.session_state.debug_mode:
            with st.expander("🔍 Debug: n8n Kommunikation", expanded=True):
                st.write(f"**Status:** {status}")
                st.write(f"**Meldung:** {message}")
                st.write(f"**Tenant-ID:** `{tenant_id}`")
                st.write(f"**Tenant-Name:** {tenant_name}")
                if response:
                    st.write("**Rohantwort von n8n:**")
                    st.json(response)
        
        if status != 200 or not response:
            st.error(f"❌ n8n-Fehler: {message}")
            if status == 400:
                st.info("💡 Tipp: Prüfen Sie ob die n8n URL korrekt ist und der Workflow aktiv ist.")
            return
        
        # 4. Antwort verarbeiten
        processed_data = None
        
        # Prüfe ob response current_analysis enthält (neues Format)
        if isinstance(response, dict) and 'current_analysis' in response:
            current_analysis = response['current_analysis']
            previous_analysis = response.get('previous_analysis')
            
            if 'metrics' in current_analysis:
                metrics_data = current_analysis['metrics']
            else:
                metrics_data = current_analysis
            
            recommendations = current_analysis.get('recommendations', [])
            customer_message = current_analysis.get('customer_message', 'Analyse abgeschlossen')
            
            processed_data = {
                'metrics': metrics_data,
                'recommendations': recommendations,
                'customer_message': customer_message,
                'previous_analysis': previous_analysis
            }
            
            if st.session_state.debug_mode:
                st.success("✅ n8n-Format mit current_analysis erkannt!")
        
        # Fallback: Altes Format
        elif isinstance(response, list) and len(response) > 0:
            first_item = response[0]
            if isinstance(first_item, dict):
                if 'metrics' in first_item:
                    processed_data = {
                        'metrics': first_item.get('metrics', {}),
                        'recommendations': first_item.get('recommendations', []),
                        'customer_message': first_item.get('summary', 'Analyse abgeschlossen')
                    }
        elif isinstance(response, dict):
            if 'metrics' in response:
                processed_data = {
                    'metrics': response.get('metrics', {}),
                    'recommendations': response.get('recommendations', []),
                    'customer_message': response.get('customer_message', '')
                }
        
        # 5. Daten zusammenführen und speichern
        if processed_data:
            metrics_data = processed_data.get('metrics', {})
            recommendations = processed_data.get('recommendations', [])
            customer_message = processed_data.get('customer_message', '')
            
            # Fallback-Empfehlungen
            if not recommendations:
                recommendations = [
                    f"Optimieren Sie Ihre Lagerauslastung für {tenant_name}",
                    "Automatische Zahlungserinnerungen einrichten",
                    "Google Business Profile pflegen"
                ]
            
            # Mit Excel-Daten mergen
            merged_data = merge_data(metrics_data, excel_merge)
            merged_data['recommendations'] = recommendations
            merged_data['customer_message'] = customer_message
            merged_data['tenant_id'] = tenant_id
            merged_data['analysis_date'] = datetime.now().isoformat()
            merged_data['files'] = [f.name for f in uploaded_files]
            
            # Nachher-Daten speichern
            st.session_state.after_analysis = merged_data.copy()
            st.session_state.current_data = merged_data.copy()
            
            # History aktualisieren
            history_entry = {
                "ts": datetime.now().isoformat(),
                "data": merged_data.copy(),
                "files": [f.name for f in uploaded_files],
                "tenant_id": tenant_id,
                "tenant_name": tenant_name,
                "type": "analysis"
            }
            
            st.session_state.analyses_history.append(history_entry)
            
            # Usage erhöhen
            if 'analyses_used' in st.session_state.current_tenant:
                st.session_state.current_tenant['analyses_used'] += 1
            
            st.success(f"✅ KI-Analyse erfolgreich für {tenant_name}!")
            
            # Vergleich anzeigen
            st.session_state.show_comparison = True
            
            st.balloons()
            time.sleep(2)
            st.rerun()
        else:
            st.error("❌ n8n-Antwort hat unerwartetes Format")
            
            # Zeige Debug-Info
            with st.expander("🔍 Problem-Details", expanded=True):
                st.write("**n8n sendet:**")
                st.json(response)
                
                st.write("**Streamlit erwartet EINES dieser Formate:**")
                st.code("""
OPTION 1 (NEUES FORMAT - empfohlen):
{
  "current_analysis": {
    "metrics": { ... },
    "recommendations": [...],
    "customer_message": "...",
    "analysis_date": "..."
  },
  "previous_analysis": {
    "metrics": { ... },
    "analysis_date": "..."
  }
}

OPTION 2 (ALTES FORMAT):
{
  "metrics": { ... },
  "recommendations": [...],
  "customer_message": "..."
}

OPTION 3 (ARRAY FORMAT):
[
  {
    "metrics": { ... },
    "recommendations": [...],
    "summary": "..."
  }
]
                """)

# ===== SEITENFUNKTIONEN =====
def render_login_page():
    """Login-Seite für nicht eingeloggte Benutzer."""
    st.title("🔐 Self-Storage Business Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ## Willkommen!
        
        **KI-gestützte Analyse für Self-Storage Unternehmen:**
        
        ✅ **Durchgängiger Workflow** - Vom Login bis zum Vergleich  
        ✅ **Vorher/Nachher Visualisierung** - Zeigt Veränderungen  
        ✅ **Automatisches Laden** - Letzte Analyse nach Login  
        ✅ **Zeitliche Entwicklung** - Alle Analysen im Überblick  
        
        **Workflow:**
        1. **Login** mit Tenant-Zugang
        2. **Letzte Analyse** wird automatisch geladen
        3. **Neue Daten** hochladen und analysieren
        4. **Vergleich** Vorher vs. Nachher sehen
        5. **History** aller Analysen durchsuchen
        
        **Demo-Zugänge:**
        - **E-Mail:** `demo@kunde.de`
        - **E-Mail:** `test@firma.de`
        - **Passwort:** (beliebig für Demo)
        """)
    
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", 
                caption="Data-Driven Decisions for SelfStorage")
        
        st.info("""
        **📊 Beispiel-Vergleich:**
        
        **Bevor:**
        - Belegungsgrad: 75%
        - Ø Vertragsdauer: 7.2 Monate
        - Offene Zahlungen: 3
        
        **Nach KI-Analyse:**
        - Belegungsgrad: 82% (+7%)
        - Ø Vertragsdauer: 8.1 Monate (+0.9)
        - Offene Zahlungen: 1 (-2)
        """)
    
    st.divider()
    
    # Feature-Vorschau
    st.subheader("📈 Dashboard-Features")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Vergleichsansicht**")
        st.write("Side-by-Side Diagramme")
        st.write("Delta-Berechnungen")
        st.write("Prozentuale Veränderungen")
    
    with col2:
        st.markdown("**History-Tracking**")
        st.write("Alle Analysen speichern")
        st.write("Zeitreihen-Diagramme")
        st.write("Export-Funktion")
    
    with col3:
        st.markdown("**KI-Integration**")
        st.write("Automatische Empfehlungen")
        st.write("Datenbank-Anbindung")
        st.write("Echtzeit-Updates")

def render_overview():
    """Hauptseite mit Vergleich und History."""
    tenant = st.session_state.current_tenant
    st.title(f"📊 Dashboard - {tenant['name']}")
    
    # Tenant-Info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info(f"**Tenant-ID:** `{tenant['tenant_id']}`")
    with col2:
        st.info(f"**Plan:** {tenant['plan'].upper()}")
    with col3:
        used = tenant.get('analyses_used', 0)
        limit = tenant.get('analyses_limit', '∞')
        st.info(f"**Analysen:** {used}/{limit}")
    with col4:
        current_date = st.session_state.current_data.get('analysis_date', '')
        if current_date:
            display_date = current_date[:10] if len(current_date) > 10 else current_date
            st.info(f"**Letzte Analyse:** {display_date}")
        else:
            st.info("**Letzte Analyse:** Keine")
    
    # Upload Bereich
    st.header("📥 Neue Analyse durchführen")
    
    uploaded_files = st.file_uploader(
        "Dateien hochladen (Excel/CSV)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("🚀 KI-Analyse starten", type="primary", use_container_width=True,
                               disabled=not uploaded_files)
    with col2:
        if st.button("🔄 Letzte Analyse neu laden", use_container_width=True):
            load_last_analysis()
            st.session_state.show_comparison = False
            st.success("Letzte Analyse neu geladen!")
            time.sleep(1)
            st.rerun()
    
    if analyze_btn and uploaded_files:
        perform_analysis(uploaded_files)
    
    # ===== VERGLEICHSANSICHT =====
    if st.session_state.get('show_comparison') and st.session_state.before_analysis and st.session_state.after_analysis:
        st.header("📈 Vergleich: Vorher vs. Nachher")
        
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        
        # KPIs im Vergleich
        st.subheader("📊 Key Performance Indicators")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            before_val = before.get('belegungsgrad', 0)
            after_val = after.get('belegungsgrad', 0)
            delta = after_val - before_val
            st.metric("Belegungsgrad", 
                     f"{after_val}%", 
                     f"{delta:+.1f}%")
        
        with col2:
            before_val = before.get('vertragsdauer_durchschnitt', 0)
            after_val = after.get('vertragsdauer_durchschnitt', 0)
            delta = after_val - before_val
            st.metric("Ø Vertragsdauer", 
                     f"{after_val:.1f} Monate", 
                     f"{delta:+.1f}")
        
        with col3:
            before_val = before.get('belegt', 0)
            after_val = after.get('belegt', 0)
            delta = after_val - before_val
            st.metric("Belegte Einheiten", 
                     after_val, 
                     f"{delta:+d}")
        
        with col4:
            before_social = before.get('social_facebook', 0) + before.get('social_google', 0)
            after_social = after.get('social_facebook', 0) + after.get('social_google', 0)
            delta = after_social - before_social
            st.metric("Social Engagement", 
                     after_social, 
                     f"{delta:+d}")
        
        # Vergleichsdiagramme
        st.subheader("📉 Detail-Vergleich")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Belegungsgrad Vergleich
            fig = create_comparison_chart(before, after, 'belegungsgrad', 'Belegungsgrad (%)')
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Kundenherkunft Vergleich
            if 'kundenherkunft' in before and 'kundenherkunft' in after:
                fig = make_subplots(rows=1, cols=2, 
                                  subplot_titles=('Vorher', 'Nachher'),
                                  specs=[[{'type':'domain'}, {'type':'domain'}]])
                
                fig.add_trace(go.Pie(labels=list(before['kundenherkunft'].keys()),
                                    values=list(before['kundenherkunft'].values()),
                                    name="Vorher"), 1, 1)
                
                fig.add_trace(go.Pie(labels=list(after['kundenherkunft'].keys()),
                                    values=list(after['kundenherkunft'].values()),
                                    name="Nachher"), 1, 2)
                
                fig.update_layout(height=300, title_text="Kundenherkunft")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Zahlungsstatus Vergleich
            if 'zahlungsstatus' in before and 'zahlungsstatus' in after:
                categories = list(before['zahlungsstatus'].keys())
                before_vals = [before['zahlungsstatus'][k] for k in categories]
                after_vals = [after['zahlungsstatus'][k] for k in categories]
                
                fig = go.Figure(data=[
                    go.Bar(name='Vorher', x=categories, y=before_vals),
                    go.Bar(name='Nachher', x=categories, y=after_vals)
                ])
                fig.update_layout(title='Zahlungsstatus Vergleich', height=300, barmode='group')
                st.plotly_chart(fig, use_container_width=True)
            
            # Social Media Vergleich
            social_metrics = ['social_facebook', 'social_google']
            if all(m in before and m in after for m in social_metrics):
                fig = go.Figure(data=[
                    go.Bar(name='Facebook Vorher', x=['Facebook'], y=[before['social_facebook']]),
                    go.Bar(name='Facebook Nachher', x=['Facebook'], y=[after['social_facebook']]),
                    go.Bar(name='Google Vorher', x=['Google'], y=[before['social_google']]),
                    go.Bar(name='Google Nachher', x=['Google'], y=[after['social_google']])
                ])
                fig.update_layout(title='Social Media Vergleich', height=300, barmode='group')
                st.plotly_chart(fig, use_container_width=True)
        
        # Empfehlungen
        recommendations = after.get('recommendations', [])
        if recommendations:
            st.subheader("🤖 KI-Empfehlungen")
            for i, rec in enumerate(recommendations[:5], 1):
                st.markdown(f"**{i}.** {rec}")
        
        if after.get('customer_message'):
            with st.expander("📝 Zusammenfassung"):
                st.info(after['customer_message'])
    
    # ===== AKTUELLE DATEN (wenn kein Vergleich) =====
    else:
        data = st.session_state.current_data
        
        st.subheader("📊 Aktuelle KPIs")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
        with col2:
            st.metric("Ø Vertragsdauer", f"{data.get('vertragsdauer_durchschnitt', 0)} Monate")
        with col3:
            st.metric("Belegte Einheiten", data.get('belegt', 0))
        with col4:
            facebook = data.get('social_facebook', 0)
            google = data.get('social_google', 0)
            st.metric("Social Engagement", facebook + google)
        
        # Aktuelle Diagramme
        st.subheader("📈 Aktuelle Visualisierungen")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Belegungsgrad
            belegung = data.get('belegungsgrad', 0)
            fig = go.Figure(data=[go.Pie(
                labels=["Belegt", "Frei"],
                values=[belegung, max(100 - belegung, 0)],
                hole=0.6
            )])
            fig.update_layout(title="Belegungsgrad", height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Kundenherkunft
            if 'kundenherkunft' in data:
                df = pd.DataFrame({
                    "Kanal": list(data['kundenherkunft'].keys()),
                    "Anzahl": list(data['kundenherkunft'].values())
                })
                fig = px.pie(df, values='Anzahl', names='Kanal')
                fig.update_layout(title="Kundenherkunft", height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Neukunden-Diagramm als Fallback
                labels = data.get('neukunden_labels', ['Jan', 'Feb', 'Mär'])
                values = data.get('neukunden_monat', [5, 4, 7])
                fig = go.Figure(data=[go.Bar(x=labels, y=values)])
                fig.update_layout(title="Neukunden pro Monat", height=300)
                st.plotly_chart(fig, use_container_width=True)
    
    # ===== HISTORY / ZEITVERLAUF =====
    st.header("📅 Analyse-History")
    
    tenant_history = [h for h in st.session_state.analyses_history 
                     if h.get('tenant_id') == tenant['tenant_id']]
    
    if tenant_history:
        # Zeitreihendiagramme
        st.subheader("Entwicklung über Zeit")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_timeseries_chart(tenant_history, 'belegungsgrad', 'Belegungsgrad (%)')
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = create_timeseries_chart(tenant_history, 'vertragsdauer_durchschnitt', 'Vertragsdauer (Monate)')
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        # History-Tabelle
        st.subheader("Vergangene Analysen")
        history_df = []
        for entry in reversed(tenant_history[-10:]):  # Letzte 10
            entry_date = entry.get('ts', '')[:16].replace('T', ' ')
            history_df.append({
                'Datum': entry_date,
                'Dateien': len(entry.get('files', [])),
                'Belegungsgrad': f"{entry['data'].get('belegungsgrad', 0)}%",
                'Empfehlungen': len(entry['data'].get('recommendations', []))
            })
        
        if history_df:
            st.dataframe(pd.DataFrame(history_df), use_container_width=True)
    else:
        st.info("📝 Noch keine Analysen durchgeführt. Starten Sie Ihre erste KI-Analyse!")

def render_customers():
    """Kundenseite mit Vergleich."""
    st.title("👥 Kundenanalyse")
    
    data = st.session_state.current_data
    
    if st.session_state.get('show_comparison') and st.session_state.before_analysis:
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        
        st.header("Kundenentwicklung")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Vorher")
            if 'kundenherkunft' in before:
                df_before = pd.DataFrame({
                    "Kanal": list(before['kundenherkunft'].keys()),
                    "Anzahl": list(before['kundenherkunft'].values())
                })
                st.dataframe(df_before, use_container_width=True)
        
        with col2:
            st.subheader("Nachher")
            if 'kundenherkunft' in after:
                df_after = pd.DataFrame({
                    "Kanal": list(after['kundenherkunft'].keys()),
                    "Anzahl": list(after['kundenherkunft'].values())
                })
                st.dataframe(df_after, use_container_width=True)
        
        # Veränderungen berechnen
        if 'kundenherkunft' in before and 'kundenherkunft' in after:
            st.subheader("Veränderungen")
            changes = []
            for key in before['kundenherkunft'].keys():
                before_val = before['kundenherkunft'].get(key, 0)
                after_val = after['kundenherkunft'].get(key, 0)
                change = after_val - before_val
                percent = (change / before_val * 100) if before_val > 0 else 0
                changes.append({
                    'Kanal': key,
                    'Vorher': before_val,
                    'Nachher': after_val,
                    'Δ Absolut': change,
                    'Δ %': f"{percent:+.1f}%" if before_val > 0 else "Neu"
                })
            
            st.dataframe(pd.DataFrame(changes), use_container_width=True)
    else:
        # Normale Ansicht
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
                fig = px.pie(df, values='Anzahl', names='Kanal')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Kundendaten verfügbar. Führen Sie eine Analyse durch.")

def render_capacity():
    """Kapazitätsseite mit Vergleich."""
    st.title("📦 Kapazitätsmanagement")
    
    data = st.session_state.current_data
    
    if st.session_state.get('show_comparison') and st.session_state.before_analysis:
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        
        st.header("Kapazitätsentwicklung")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Vorher")
            st.metric("Belegte Einheiten", before.get('belegt', 0))
            st.metric("Freie Einheiten", before.get('frei', 0))
            st.metric("Belegungsgrad", f"{before.get('belegungsgrad', 0)}%")
        
        with col2:
            st.subheader("Nachher")
            st.metric("Belegte Einheiten", after.get('belegt', 0))
            st.metric("Freie Einheiten", after.get('frei', 0))
            st.metric("Belegungsgrad", f"{after.get('belegungsgrad', 0)}%")
        
        # Kapazitätsdiagramm Vergleich
        st.subheader("Kapazitätsverteilung")
        
        categories = ['Belegt', 'Frei']
        before_vals = [before.get('belegt', 0), before.get('frei', 0)]
        after_vals = [after.get('belegt', 0), after.get('frei', 0)]
        
        fig = go.Figure(data=[
            go.Bar(name='Vorher', x=categories, y=before_vals),
            go.Bar(name='Nachher', x=categories, y=after_vals)
        ])
        fig.update_layout(title='Kapazitätsverteilung Vergleich', barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        # Normale Ansicht
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Belegte Einheiten", data.get("belegt", 0))
            st.metric("Freie Einheiten", data.get("frei", 0))
            st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
        
        with col2:
            fig = go.Figure(data=[go.Bar(
                x=["Belegt", "Frei"],
                y=[data.get("belegt", 0), data.get("frei", 0)]
            )])
            fig.update_layout(title="Kapazitätsverteilung", height=300)
            st.plotly_chart(fig, use_container_width=True)

def render_finance():
    """Finanzseite mit Vergleich."""
    st.title("💰 Finanzübersicht")
    
    data = st.session_state.current_data
    
    if st.session_state.get('show_comparison') and st.session_state.before_analysis:
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        
        st.header("Finanzentwicklung")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Vorher")
            if 'zahlungsstatus' in before:
                df_before = pd.DataFrame({
                    "Status": list(before['zahlungsstatus'].keys()),
                    "Anzahl": list(before['zahlungsstatus'].values())
                })
                st.dataframe(df_before, use_container_width=True)
        
        with col2:
            st.subheader("Nachher")
            if 'zahlungsstatus' in after:
                df_after = pd.DataFrame({
                    "Status": list(after['zahlungsstatus'].keys()),
                    "Anzahl": list(after['zahlungsstatus'].values())
                })
                st.dataframe(df_after, use_container_width=True)
        
        # Zahlungsmoral berechnen
        if 'zahlungsstatus' in before and 'zahlungsstatus' in after:
            st.subheader("Zahlungsmoral")
            
            before_total = sum(before['zahlungsstatus'].values())
            before_paid = before['zahlungsstatus'].get('bezahlt', 0)
            before_moral = (before_paid / before_total * 100) if before_total > 0 else 0
            
            after_total = sum(after['zahlungsstatus'].values())
            after_paid = after['zahlungsstatus'].get('bezahlt', 0)
            after_moral = (after_paid / after_total * 100) if after_total > 0 else 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Zahlungsmoral Vorher", f"{before_moral:.1f}%")
            with col2:
                delta = after_moral - before_moral
                st.metric("Zahlungsmoral Nachher", f"{after_moral:.1f}%", f"{delta:+.1f}%")
    
    else:
        # Normale Ansicht
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
                # Zahlungsmoral berechnen
                total = sum(status.values())
                paid = status.get('bezahlt', 0)
                moral = (paid / total * 100) if total > 0 else 0
                
                st.metric("Zahlungsmoral", f"{moral:.1f}%")
                
                fig = px.pie(df, values='Anzahl', names='Status')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Finanzdaten verfügbar. Führen Sie eine Analyse durch.")

def render_system():
    """Systemseite mit Export."""
    st.title("⚙️ System & Export")
    
    data = st.session_state.current_data
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Aktuelle Daten
        csv = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            "⬇️ Aktuelle Daten (CSV)",
            csv,
            f"storage_current_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        # Vergleichsdaten (wenn vorhanden)
        if st.session_state.get('show_comparison') and st.session_state.before_analysis:
            comparison_data = {
                'vorher': st.session_state.before_analysis,
                'nachher': st.session_state.after_analysis,
                'vergleich_datum': datetime.now().isoformat()
            }
            json_str = json.dumps(comparison_data, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Vergleich (JSON)",
                json_str,
                f"storage_comparison_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json",
                "application/json",
                use_container_width=True
            )
        else:
            st.button("⬇️ Vergleich (JSON)", disabled=True, use_container_width=True,
                     help="Kein Vergleich verfügbar. Führen Sie eine Analyse durch.")
    
    with col3:
        # History Export
        tenant_history = [h for h in st.session_state.analyses_history 
                         if h.get('tenant_id') == tenant['tenant_id']]
        if tenant_history:
            history_json = json.dumps(tenant_history, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Gesamte History (JSON)",
                history_json,
                f"storage_history_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json",
                "application/json",
                use_container_width=True
            )
        else:
            st.button("⬇️ History (JSON)", disabled=True, use_container_width=True,
                     help="Keine History verfügbar")
    
    # History Management
    st.header("Analyserverlauf")
    
    tenant_history = [h for h in st.session_state.analyses_history 
                     if h.get('tenant_id') == tenant['tenant_id']]
    
    if tenant_history:
        # Auswahl für Detailansicht
        history_options = [f"{h['ts'][:16]} - {len(h.get('files', []))} Dateien" 
                          for h in reversed(tenant_history)]
        
        selected = st.selectbox("Analyse auswählen", history_options, key="history_select")
        
        if selected:
            idx = history_options.index(selected)
            selected_entry = list(reversed(tenant_history))[idx]
            
            with st.expander("📋 Analyse-Details", expanded=True):
                st.write(f"**Datum:** {selected_entry['ts'][:19]}")
                st.write(f"**Dateien:** {', '.join(selected_entry.get('files', []))}")
                
                if selected_entry['data'].get('recommendations'):
                    st.write("**Empfehlungen:**")
                    for rec in selected_entry['data']['recommendations'][:3]:
                        st.write(f"- {rec}")
                
                # Diese Analyse als aktuell setzen
                if st.button("Diese Analyse laden", key="load_selected"):
                    st.session_state.current_data = selected_entry['data'].copy()
                    st.session_state.before_analysis = selected_entry['data'].copy()
                    st.session_state.show_comparison = False
                    st.success("Analyse geladen!")
                    time.sleep(1)
                    st.rerun()
        
        # Clear History Button
        if st.button("🗑️ History löschen", type="secondary"):
            # Nur History für diesen Tenant löschen
            st.session_state.analyses_history = [
                h for h in st.session_state.analyses_history 
                if h.get('tenant_id') != tenant['tenant_id']
            ]
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.show_comparison = False
            st.success("History gelöscht!")
            st.rerun()
    else:
        st.info("Noch keine Analysen für diesen Tenant")
    
    # Systeminfo
    st.header("Systeminformation")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Analysen gesamt", len(tenant_history))
    with col2:
        st.metric("Vergleich aktiv", "Ja" if st.session_state.get('show_comparison') else "Nein")
    with col3:
        st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    with col4:
        st.metric("n8n URL", "Gesetzt" if st.session_state.n8n_url else "Fehlt")

# ===== HAUPTAPP =====
def main():
    # Session State initialisieren
    if "current_data" not in st.session_state:
        st.session_state.current_data = DEFAULT_DATA.copy()
    if "before_analysis" not in st.session_state:
        st.session_state.before_analysis = None
    if "after_analysis" not in st.session_state:
        st.session_state.after_analysis = None
    if "analyses_history" not in st.session_state:
        st.session_state.analyses_history = []
    if "n8n_url" not in st.session_state:
        st.session_state.n8n_url = os.environ.get("N8N_URL", "")
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "show_comparison" not in st.session_state:
        st.session_state.show_comparison = False
    if "last_analysis_loaded" not in st.session_state:
        st.session_state.last_analysis_loaded = False
    
    # Login-Status
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "current_tenant" not in st.session_state:
        st.session_state.current_tenant = None
    
    # ===== SIDEBAR =====
    with st.sidebar:
        st.title("🔐 Login & Einstellungen")
        
        if not st.session_state.logged_in:
            # Login Form
            st.subheader("Anmelden")
            email = st.text_input("E-Mail", key="login_email")
            password = st.text_input("Passwort", type="password", key="login_password")
            
            if st.button("🚀 Anmelden", type="primary", use_container_width=True):
                if email in TENANTS:
                    st.session_state.logged_in = True
                    st.session_state.current_tenant = TENANTS[email]
                    
                    # LETZTE ANALYSE LADEN (automatisch nach Login!)
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
            # Eingeloggt
            tenant = st.session_state.current_tenant
            st.success(f"✅ Eingeloggt als: {tenant['name']}")
            
            # Tenant Info
            st.info(f"📋 Plan: {tenant['plan'].upper()}")
            st.info(f"📊 Analysen: {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
            st.info(f"🔑 Tenant-ID: `{tenant['tenant_id']}`")
            
            if st.button("🚪 Abmelden", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.current_tenant = None
                st.session_state.show_comparison = False
                st.session_state.last_analysis_loaded = False
                st.rerun()
        
        st.divider()
        
        # Einstellungen (nur wenn eingeloggt)
        if st.session_state.logged_in:
            st.subheader("⚙️ Konfiguration")
            
            # n8n URL
            n8n_url = st.text_input(
                "n8n Webhook URL",
                value=st.session_state.n8n_url,
                placeholder="https://your-n8n-instance.com/webhook/...",
                key="n8n_url_input"
            )
            st.session_state.n8n_url = n8n_url
            
            if n8n_url:
                st.caption(f"Verwendet: `{n8n_url[:50]}...`")
            
            # Debug Mode
            st.session_state.debug_mode = st.checkbox("🐛 Debug-Modus")
            
            st.divider()
            
            # Navigation
            st.subheader("📱 Navigation")
            page = st.radio(
                "Menü",
                ["📊 Übersicht", "👥 Kunden", "📦 Kapazität", "💰 Finanzen", "⚙️ System"],
                key="nav_radio"
            )
            
            st.divider()
            
            # Reset Buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Vergleich zurücksetzen", use_container_width=True):
                    st.session_state.show_comparison = False
                    st.success("Vergleich zurückgesetzt!")
                    time.sleep(1)
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Alle Daten", type="secondary", use_container_width=True):
                    st.session_state.current_data = DEFAULT_DATA.copy()
                    st.session_state.before_analysis = None
                    st.session_state.after_analysis = None
                    st.session_state.show_comparison = False
                    st.success("Daten zurückgesetzt!")
                    time.sleep(1)
                    st.rerun()
        else:
            page = "📊 Übersicht"
    
    # ===== HAUPTINHALT =====
    if not st.session_state.logged_in:
        # Login-Seite
        render_login_page()
    else:
        # Dashboard-Seiten
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

# ===== APP START =====
if __name__ == "__main__":
    main()
