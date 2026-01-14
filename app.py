
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
import requests
import json

class N8NResponseValidator:
    """Zentrale Klasse zur Validierung von n8n-Responses"""
    
    @staticmethod
    def validate_response(response):
        """
        Validiert und normalisiert n8n-Responses auf ein einheitliches Format.
        Akzeptiert verschiedene Input-Formate:
        1. Standard-Format: {"status": "success", "data": {...}}
        2. Direktes Data-Format: {"metrics": {...}, "recommendations": [...]}
        3. Supabase-Format: [{"metrics": "json_string", ...}, ...]
        4. Legacy-Format: {"current_analysis": {...}, "previous_analysis": {...}}
        """
        if not response:
            print("Leere Response in Validator")
            return None, "Leere Response erhalten"
        
        # Fall 1: Standard-Format mit data wrapper
        if isinstance(response, dict) and "data" in response:
            print("Validator: Standard-Format erkannt")
            data = response.get("data", {})
            if isinstance(data, dict):
                return data, None
            return None, "Data-Feld ist kein Dictionary"
        
        # Fall 2: Direktes Format (ohne data wrapper)
        if isinstance(response, dict):
            print("Validator: Direktes Format erkannt")
            
            # Extrahiere Metriken aus verschiedenen möglichen Feldern
            metrics = {}
            recommendations = []
            customer_message = ""
            analysis_date = datetime.now().isoformat()
            
            # Suche nach Metriken
            if "metrics" in response:
                metrics = response["metrics"]
            elif "analysis_result" in response:
                analysis_result = response["analysis_result"]
                if isinstance(analysis_result, dict):
                    metrics = analysis_result.get("metrics", analysis_result)
            elif any(key in response for key in ["belegt", "frei", "belegungsgrad"]):
                # Direkte Business-Daten
                metrics = response
            else:
                return None, "Keine Metriken gefunden"
            
            # Extrahiere andere Felder
            recommendations = response.get("recommendations", response.get("recommendation_list", []))
            customer_message = response.get("customer_message", response.get("summary", ""))
            analysis_date = response.get("analysis_date", 
                                       response.get("timestamp", 
                                                   response.get("processed_at", 
                                                              datetime.now().isoformat())))
            
            # Stelle sicher, dass metrics ein Dict ist
            if isinstance(metrics, str):
                try:
                    metrics = json.loads(metrics)
                except json.JSONDecodeError:
                    return None, "Metrics ist ungültiger JSON-String"
            
            data = {
                "metrics": metrics if isinstance(metrics, dict) else {},
                "recommendations": recommendations if isinstance(recommendations, list) else [],
                "customer_message": customer_message or "Analyse geladen",
                "analysis_date": analysis_date
            }
            
            return data, None
        
        # Fall 3: Liste (Supabase-Format)
        if isinstance(response, list):
            print(f"Validator: Listen-Format mit {len(response)} Elementen")
            if len(response) > 0:
                # Rekursive Validierung des ersten Elements
                return N8NResponseValidator.validate_response(response[0])
            return None, "Leere Liste"
        
        # Fall 4: Unbekanntes Format
        return None, f"Unbekanntes Response-Format: {type(response)}"

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
# ====== KORRIGIERTE API-FUNKTIONEN ======
def post_to_n8n_get_last(base_url, tenant_id, uuid_str):
    """
    Erwartet jetzt Contract-Format von n8n
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
            print(f"GET-LAST JSON Typ: {type(json_response)}")
            
            # NEU: Contract-Format erkennen
            if isinstance(json_response, dict) and 'data' in json_response:
                # Contract-Format erkannt
                contract = json_response
                print(f"✅ Contract Format erkannt, Status: {contract.get('status')}")
                
                if contract.get('status') == 'success' and contract.get('count', 0) > 0:
                    # Extrahiere die Business-Daten aus data.metrics
                    data = contract['data']
                    
                    # Kombiniere metrics mit den anderen Feldern
                    business_data = data['metrics'].copy() if 'metrics' in data else {}
                    business_data['recommendations'] = data.get('recommendations', [])
                    business_data['customer_message'] = data.get('customer_message', '')
                    business_data['analysis_date'] = data.get('analysis_date', '')
                    business_data['tenant_id'] = contract.get('tenant_id', tenant_id)
                    
                    return business_data, "Success", None
                else:
                    return None, f"Keine Daten im Contract (Status: {contract.get('status')})", json_response
            else:
                # Altes Format (Fallback)
                print("⚠️ Altes Format, versuche direkte Business-Daten")
                if isinstance(json_response, dict) and any(key in json_response for key in ["belegt", "frei", "belegungsgrad"]):
                    return json_response, "Success (altes Format)", None
                else:
                    return None, "Ungültiges Format", json_response
                
        except json.JSONDecodeError:
            return None, "Kein JSON in Response", response.text[:200]
            
    except requests.exceptions.Timeout:
        return None, "Timeout nach 30s", None
    except Exception as e:
        return None, f"Exception: {str(e)}", None


def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
    """
    Erwartet jetzt Contract-Format von n8n
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
            print(f"Response Typ: {type(json_response)}")
            
            # NEU: Contract-Format erkennen
            if isinstance(json_response, dict) and 'data' in json_response:
                # Contract-Format erkannt
                contract = json_response
                print(f"✅ Contract Format erkannt, Status: {contract.get('status')}")
                
                if contract.get('status') == 'success' and contract.get('count', 0) > 0:
                    # Extrahiere die Business-Daten aus data.metrics
                    data = contract['data']
                    
                    # Kombiniere metrics mit den anderen Feldern
                    business_data = data['metrics'].copy() if 'metrics' in data else {}
                    business_data['recommendations'] = data.get('recommendations', [])
                    business_data['customer_message'] = data.get('customer_message', '')
                    business_data['analysis_date'] = data.get('analysis_date', '')
                    business_data['tenant_id'] = contract.get('tenant_id', tenant_id)
                    
                    return business_data, "Success", None
                else:
                    return None, f"Fehler im Contract (Status: {contract.get('status')})", json_response
            else:
                # Altes Format (Fallback)
                print("⚠️ Altes Format, versuche direkte Business-Daten")
                if isinstance(json_response, dict) and any(key in json_response for key in ["belegt", "frei", "belegungsgrad"]):
                    return json_response, "Success (altes Format)", None
                else:
                    return None, "Ungültiges Format", json_response
            
        except json.JSONDecodeError:
            return None, "Kein JSON in Response", response.text[:200]
            
    except Exception as e:
        return None, f"Exception: {str(e)}", None

def merge_contract_data(contract_data):
    """
    Hilfsfunktion: Kombiniert metrics mit den anderen Feldern aus einem Contract
    """
    if not contract_data or not isinstance(contract_data, dict):
        return None
    
    # Wenn es schon Business-Daten sind (direktes Format)
    if 'belegt' in contract_data:
        return contract_data
    
    # Wenn es ein Contract ist
    if 'data' in contract_data:
        data = contract_data['data']
        result = {}
        
        # Füge metrics hinzu
        if 'metrics' in data and isinstance(data['metrics'], dict):
            result.update(data['metrics'])
        
        # Füge andere Felder hinzu
        for key in ['recommendations', 'customer_message', 'analysis_date']:
            if key in data:
                result[key] = data[key]
        
        # Füge tenant_id hinzu
        if 'tenant_id' in contract_data:
            result['tenant_id'] = contract_data['tenant_id']
        
        return result
    
    return None

def standardize_get_last_response(raw_response, tenant_id):
    """
    Standardisiert die Response von /get-last-analysis-only
    Transformiert Supabase-Format in unser Standard-Format
    """
    print(f"Standardizing response of type: {type(raw_response)}")
    
    # Fall 1: Response ist bereits im Standard-Format
    if isinstance(raw_response, dict) and "data" in raw_response:
        print("Response bereits im Standard-Format")
        return raw_response
    
    # Fall 2: Supabase Row-Format (Array mit rows)
    if isinstance(raw_response, list) and len(raw_response) > 0:
        print(f"Response ist Liste mit {len(raw_response)} Elementen")
        
        # Nimm die neueste (letzte) Analyse
        latest_analysis = raw_response[-1]
        
        # Extrahiere Metriken aus verschiedenen Feldern
        metrics_data = {}
        recommendations = []
        customer_message = ""
        analysis_date = datetime.now().isoformat()
        
        # WICHTIG: Metriken könnten in verschiedenen Feldern sein
        if "metrics" in latest_analysis:
            # Metriken als String oder Dict?
            metrics_field = latest_analysis["metrics"]
            
            if isinstance(metrics_field, str):
                # JSON-String parsen
                try:
                    metrics_data = json.loads(metrics_field)
                    print("Metriken aus JSON-String geparsed")
                except json.JSONDecodeError as e:
                    print(f"Fehler beim Parsen von metrics JSON: {e}")
                    metrics_data = {}
            elif isinstance(metrics_field, dict):
                metrics_data = metrics_field
                print("Metriken als Dict erhalten")
            else:
                print(f"Unbekannter metrics Typ: {type(metrics_field)}")
        
        # Prüfe auch analysis_result Feld
        elif "analysis_result" in latest_analysis and latest_analysis["analysis_result"]:
            analysis_result = latest_analysis["analysis_result"]
            if isinstance(analysis_result, dict):
                if "metrics" in analysis_result:
                    metrics_data = analysis_result["metrics"]
                else:
                    metrics_data = analysis_result
                print("Metriken aus analysis_result extrahiert")
        
        # Extrahiere Timestamp
        if "updated_at" in latest_analysis:
            analysis_date = latest_analysis["updated_at"]
        elif "created_at" in latest_analysis:
            analysis_date = latest_analysis["created_at"]
        
        # Erstelle standardisiertes Format
        standardized = {
            "status": "success",
            "data": {
                "metrics": metrics_data,
                "recommendations": recommendations,
                "customer_message": customer_message or f"Letzte Analyse geladen für {tenant_id}",
                "analysis_date": analysis_date,
                "tenant_id": tenant_id,
                "source": "supabase",
                "row_id": latest_analysis.get("id", ""),
                "file_name": latest_analysis.get("file_name", "")
            }
        }
        
        print(f"Standardisierte Response erstellt mit {len(metrics_data)} Metriken")
        return standardized
    
    # Fall 3: Direkte Metrics im Root
    elif isinstance(raw_response, dict):
        # Prüfe ob es Business-Metriken enthält
        if any(key in raw_response for key in ["belegt", "frei", "belegungsgrad", "vertragsdauer_durchschnitt"]):
            standardized = {
                "status": "success",
                "data": {
                    "metrics": raw_response,
                    "recommendations": raw_response.get("recommendations", []),
                    "customer_message": raw_response.get("customer_message", "Letzte Analyse geladen"),
                    "analysis_date": raw_response.get("timestamp", datetime.now().isoformat()),
                    "tenant_id": tenant_id,
                    "source": "direct"
                }
            }
            return standardized
    
    # Fall 4: Leer oder unbekannt
    print(f"Unbekanntes Response-Format: {type(raw_response)}")
    return {
        "status": "success",
        "data": {
            "metrics": {},
            "recommendations": [],
            "customer_message": "Keine vorherige Analyse gefunden",
            "analysis_date": datetime.now().isoformat(),
            "tenant_id": tenant_id,
            "source": "empty"
        }
    }
        
def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
    """Vereinfachte Version - erwartet standardisiertes Format von n8n"""
    print(f"\nNEW-ANALYSIS für {tenant_id}")
    
    url = f"{base_url.rstrip('/')}/analyze-with-deepseek"
    
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
        },
        "metadata": {
            "source": "streamlit",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)  # 2 Minuten Timeout für KI
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            return {
                "status": "error",
                "code": response.status_code,
                "message": f"HTTP {response.status_code}: {response.text[:200]}",
                "data": None
            }
        
        try:
            json_response = response.json()
            print(f"Response Type: {type(json_response)}")
            
            # ====== WICHTIG: Standardisiere die Response ======
            # n8n sollte immer {"status": "success", "data": {...}} zurückgeben
            # Falls nicht, baue es selbst
            
            if isinstance(json_response, dict) and "status" in json_response:
                # Bereits standardisiert
                standardized = json_response
            else:
                # Baue Standard-Format
                validated_data, error = N8NResponseValidator.validate_response(json_response)
                
                if validated_data:
                    standardized = {
                        "status": "success",
                        "data": validated_data
                    }
                else:
                    standardized = {
                        "status": "error",
                        "data": {
                            "metrics": {},
                            "recommendations": [],
                            "customer_message": f"Validierungsfehler: {error}",
                            "analysis_date": datetime.now().isoformat()
                        }
                    }
            
            return {
                "status": "success",
                "code": 200,
                "message": "Analyse erfolgreich",
                "data": standardized.get("data", {}) if standardized.get("status") == "success" else None
            }
            
        except json.JSONDecodeError:
            return {
                "status": "error",
                "code": 500,
                "message": f"Kein JSON: {response.text[:200]}",
                "data": None
            }
            
    except Exception as e:
        return {
            "status": "error",
            "code": 500,
            "message": f"Exception: {str(e)}",
            "data": None
        }
        
            
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
    """Lädt die letzte Analyse - robust und einfach"""
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
        # Rufe n8n Endpoint auf
        status, message, response = post_to_n8n_get_last(
            n8n_base_url, tenant_id, str(uuid.uuid4())
        )
        
        # Debug-Info
        if st.session_state.debug_mode:
            with st.expander("Debug: GET-LAST Response", expanded=False):
                st.write(f"Status Code: {status}")
                st.write(f"Message: {message}")
                st.write("Raw Response:")
                st.json(response if response else {})
        
        # Fallback bei Fehlern
        if status != 200 or not response:
            st.info("⚠️ Keine vorherige Analyse gefunden oder Server-Fehler. Verwende Standarddaten.")
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.before_analysis = DEFAULT_DATA.copy()
            return True
        
        # Validiere Response
        validated_data, error_msg = N8NResponseValidator.validate_response(response)
        
        if not validated_data:
            st.warning(f"⚠️ Ungültiges Format: {error_msg}. Verwende Standarddaten.")
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.before_analysis = DEFAULT_DATA.copy()
            return True
        
        # ====== MERGE LOGIK ======
        # Starte mit DEFAULT_DATA
        loaded_data = DEFAULT_DATA.copy()
        
        # Extrahiere Metriken
        metrics = validated_data.get("metrics", {})
        
        # WICHTIG: Konvertiere alle Werte zu richtigen Typen
        def safe_convert(value):
            """Konvertiert Werte sicher zu int/float"""
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                try:
                    # Versuche Float, dann Int
                    return float(value)
                except:
                    try:
                        return int(value)
                    except:
                        return value
            return value
        
        # Übernehme alle Metriken aus der validierten Response
        for key, value in metrics.items():
            if key in loaded_data:
                loaded_data[key] = safe_convert(value)
        
        # Spezielle Felder (können in metrics oder direkt sein)
        if "kundenherkunft" in metrics:
            loaded_data["kundenherkunft"] = metrics["kundenherkunft"]
        elif "kundenherkunft" in validated_data:
            loaded_data["kundenherkunft"] = validated_data["kundenherkunft"]
        
        if "zahlungsstatus" in metrics:
            loaded_data["zahlungsstatus"] = metrics["zahlungsstatus"]
        elif "zahlungsstatus" in validated_data:
            loaded_data["zahlungsstatus"] = validated_data["zahlungsstatus"]
        
        # Empfehlungen und Message
        loaded_data["recommendations"] = validated_data.get("recommendations", [])
        loaded_data["customer_message"] = validated_data.get("customer_message", 
                                                           f"Letzte Analyse für {tenant_id} geladen")
        
        # Analysis Date
        loaded_data["analysis_date"] = validated_data.get("analysis_date", datetime.now().isoformat())
        loaded_data["tenant_id"] = tenant_id
        
        # Debug-Info
        if st.session_state.debug_mode:
            with st.expander("Debug: Geladene Daten", expanded=False):
                st.write("Validierte Daten:")
                st.json(validated_data)
                st.write("Geladene Daten (nach Merge):")
                st.json({k: v for k, v in loaded_data.items() if k in DEFAULT_DATA})
        
        # In Session State speichern
        st.session_state.current_data = loaded_data
        st.session_state.before_analysis = loaded_data.copy()
        st.session_state.last_analysis_loaded = True
        
        st.success(f"✅ Letzte Analyse vom {loaded_data['analysis_date'][:10]} geladen!")
        return True


def perform_analysis(uploaded_files):
    """Führt KI-Analyse mit robustem Error-Handling durch"""
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
    
    # ====== NEUE LOGIK: Standardisierter n8n Call ======
    with st.spinner("KI analysiert Daten... (dies kann 30-60 Sekunden dauern)"):
        result = post_to_n8n_analyze(n8n_base_url, tenant_id, str(uuid.uuid4()), file_info)
    
    # Debug-Info
    if st.session_state.debug_mode:
        with st.expander("Debug: n8n Kommunikation", expanded=False):
            st.write(f"Status: {result['status']}")
            st.write(f"Code: {result['code']}")
            st.write(f"Meldung: {result['message']}")
            if result['data']:
                st.write("Validierte Daten:")
                st.json(result['data'])
    
    # ====== ZENTRALE ERGEBNISVERARBEITUNG ======
    if result['status'] == 'success' and result['data']:
        n8n_data = result['data']
        
        # 1. Metrics mit Excel-Daten mergen (n8n hat Priorität)
        final_metrics = {}
        
        if "metrics" in n8n_data:
            # Beginne mit n8n Metrics
            final_metrics = n8n_data["metrics"].copy()
            # Füge Excel-Daten hinzu, falls n8n sie nicht geliefert hat
            for key, value in excel_data.items():
                if key not in final_metrics or final_metrics[key] == 0:
                    final_metrics[key] = value
        
        # 2. Fehlende Werte mit Defaults füllen
        final_data = DEFAULT_DATA.copy()
        for key in final_data:
            if key in final_metrics:
                final_data[key] = final_metrics[key]
        
        # 3. Empfehlungen und Message
        final_data["recommendations"] = n8n_data.get("recommendations", [])
        if not final_data["recommendations"]:
            # Fallback-Empfehlungen basierend auf Excel-Daten
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
        
        final_data["customer_message"] = n8n_data.get("customer_message", 
                                                     f"Analyse für {tenant_name} abgeschlossen.")
        
        # 4. Metadaten
        final_data["analysis_date"] = n8n_data.get("analysis_date", datetime.now().isoformat())
        final_data["tenant_id"] = tenant_id
        final_data["files"] = [f.name for f in uploaded_files]
        final_data["source"] = "n8n_ai"
        
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
            "source": "n8n"
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
        st.warning(f"⚠️ KI-Analyse fehlgeschlagen: {result['message']}")
        
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

# Hilfsfunktion für Fallback-Empfehlungen
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

# SEITENFUNKTIONEN (identisch wie vorher, aber ich kürze für Lesbarkeit)
def render_login_page():
    st.title("Self-Storage Business Intelligence")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("## Willkommen!\n**KI-gestützte Analyse für Self-Storage Unternehmen:**\n✅ Durchgängiger Workflow\n✅ Vorher/Nachher Visualisierung\n✅ Automatisches Laden\n✅ Zeitliche Entwicklung\n\n**Workflow:**\n1. Login mit Tenant-Zugang\n2. Letzte Analyse wird automatisch geladen\n3. Neue Daten hochladen und analysieren\n4. Vergleich Vorher vs. Nachher sehen\n5. History aller Analysen durchsuchen\n\n**Demo-Zugänge:**\n- E-Mail: `demo@kunde.de`\n- E-Mail: `test@firma.de`\n- Passwort: (beliebig für Demo)")
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", caption="Data-Driven Decisions for SelfStorage")
        st.info("**Beispiel-Vergleich:**\n**Bevor:**\n- Belegungsgrad: 75%\n- Ø Vertragsdauer: 7.2 Monate\n- Offene Zahlungen: 3\n**Nach KI-Analyse:**\n- Belegungsgrad: 82% (+7%)\n- Ø Vertragsdauer: 8.1 Monate (+0.9)\n- Offene Zahlungen: 1 (-2)")
    
    st.divider()
    st.subheader("Dashboard-Features")
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
    
    if st.session_state.get('show_comparison') and st.session_state.before_analysis and st.session_state.after_analysis:
        st.header("Vergleich: Vorher vs. Nachher")
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        
        st.subheader("Key Performance Indicators")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1: 
            before_val = before.get('belegungsgrad', 0)
            after_val = after.get('belegungsgrad', 0)
            delta = after_val - before_val
            st.metric("Belegungsgrad", f"{after_val}%", f"{delta:+.1f}%")
        
        with col2: 
            before_val = before.get('vertragsdauer_durchschnitt', 0)
            after_val = after.get('vertragsdauer_durchschnitt', 0)
            delta = after_val - before_val
            st.metric("Ø Vertragsdauer", f"{after_val:.1f} Monate", f"{delta:+.1f}")
        
        with col3: 
            before_val = before.get('belegt', 0)
            after_val = after.get('belegt', 0)
            delta = after_val - before_val
            st.metric("Belegte Einheiten", after_val, f"{delta:+d}")
        
        with col4: 
            # Hier wird after_social definiert, bevor es verwendet wird
            before_social = before.get('social_facebook', 0) + before.get('social_google', 0)
            after_social = after.get('social_facebook', 0) + after.get('social_google', 0)
            delta = after_social - before_social
            st.metric("Social Engagement", after_social, f"{delta:+.0f}")
        
        st.subheader("Detail-Vergleich")
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_comparison_chart(before, after, 'belegungsgrad', 'Belegungsgrad (%)')
            if fig: 
                st.plotly_chart(fig, use_container_width=True)
            
            if 'kundenherkunft' in before and 'kundenherkunft' in after:
                fig = make_subplots(
                    rows=1, 
                    cols=2, 
                    subplot_titles=('Vorher', 'Nachher'), 
                    specs=[[{'type':'domain'}, {'type':'domain'}]]
                )
                fig.add_trace(
                    go.Pie(
                        labels=list(before['kundenherkunft'].keys()), 
                        values=list(before['kundenherkunft'].values()), 
                        name="Vorher"
                    ), 
                    1, 1
                )
                fig.add_trace(
                    go.Pie(
                        labels=list(after['kundenherkunft'].keys()), 
                        values=list(after['kundenherkunft'].values()), 
                        name="Nachher"
                    ), 
                    1, 2
                )
                fig.update_layout(height=300, title_text="Kundenherkunft")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
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
        
        recommendations = after.get('recommendations', [])
        if recommendations: 
            st.subheader("KI-Empfehlungen")
            for i, rec in enumerate(recommendations[:5], 1):
                st.markdown(f"**{i}.** {rec}")
        
        if after.get('customer_message'): 
            with st.expander("Zusammenfassung"): 
                st.info(after['customer_message'])
    
    else:
        data = st.session_state.current_data
        st.subheader("Aktuelle KPIs")
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
        
        st.subheader("Aktuelle Visualisierungen")
        col1, col2 = st.columns(2)
        with col1:
            belegung = data.get('belegungsgrad', 0)
            fig = go.Figure(data=[
                go.Pie(
                    labels=["Belegt", "Frei"], 
                    values=[belegung, max(100 - belegung, 0)], 
                    hole=0.6
                )
            ])
            fig.update_layout(title="Belegungsgrad", height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if 'kundenherkunft' in data:
                df = pd.DataFrame({
                    "Kanal": list(data['kundenherkunft'].keys()), 
                    "Anzahl": list(data['kundenherkunft'].values())
                })
                fig = px.pie(df, values='Anzahl', names='Kanal')
                fig.update_layout(title="Kundenherkunft", height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                labels = data.get('neukunden_labels', ['Jan', 'Feb', 'Mär'])
                values = data.get('neukunden_monat', [5, 4, 7])
                fig = go.Figure(data=[go.Bar(x=labels, y=values)])
                fig.update_layout(title="Neukunden pro Monat", height=300)
                st.plotly_chart(fig, use_container_width=True)
    
    st.header("Analyse-History")
    tenant_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') == tenant['tenant_id']]
    
    if tenant_history:
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
        
        st.subheader("Vergangene Analysen")
        history_df = []
        for entry in reversed(tenant_history[-10:]):
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
        st.info("Noch keine Analysen durchgeführt. Starten Sie Ihre erste KI-Analyse!")
        
def render_customers():
    st.title("Kundenanalyse")
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
    st.title("Kapazitätsmanagement")
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
        col1, col2 = st.columns(2)
        with col1: 
            st.metric("Belegte Einheiten", data.get("belegt", 0))
            st.metric("Freie Einheiten", data.get("frei", 0))
            st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
        
        with col2: 
            fig = go.Figure(data=[
                go.Bar(x=["Belegt", "Frei"], y=[data.get("belegt", 0), data.get("frei", 0)])
            ])
            fig.update_layout(title="Kapazitätsverteilung", height=300)
            st.plotly_chart(fig, use_container_width=True)

def render_finance():
    st.title("Finanzübersicht")
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
        
        if 'zahlungsstatus' in before and 'zahlungsstatus' in after:
            st.subheader("Zahlungsmoral")
            before_total = sum(before['zahlungsstatus'].values())
            before_paid = before['zahlungsstatus'].get('bezahlt', 0)
            before_moral = (before_paid / before_total * 100) if before_total > 0 else 0
            
            after_total = sum(after['zahlungsstatus'].values())
            after_paid = after['zahlungsstatus'].get('bezahlt', 0)
            after_moral = (after_paid / after_total * 100) if after_total > 0 else 0
            
            delta = after_moral - before_moral
            
            col1, col2 = st.columns(2)
            with col1: 
                st.metric("Zahlungsmoral Vorher", f"{before_moral:.1f}%")
            with col2: 
                st.metric("Zahlungsmoral Nachher", f"{after_moral:.1f}%", f"{delta:+.1f}%")
    
    else:
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
                total = sum(status.values())
                paid = status.get('bezahlt', 0)
                moral = (paid / total * 100) if total > 0 else 0
                st.metric("Zahlungsmoral", f"{moral:.1f}%")
                fig = px.pie(df, values='Anzahl', names='Status')
                st.plotly_chart(fig, use_container_width=True)
        else: 
            st.info("Keine Finanzdaten verfügbar. Führen Sie eine Analyse durch.")

def render_system():
    st.title("System & Export")
    data = st.session_state.current_data
    tenant = st.session_state.current_tenant
    
    st.header("Tenant-Information")
    col1, col2 = st.columns(2)
    with col1: 
        st.info(f"Tenant-ID: `{tenant['tenant_id']}`")
        st.info(f"Firmenname: {tenant['name']}")
    with col2: 
        st.info(f"Abo-Plan: {tenant['plan'].upper()}")
        st.info(f"Analysen genutzt: {tenant.get('analyses_used', 0)}/{tenant.get('analyses_limit', '∞')}")
    
    st.header("Daten exportieren")
    col1, col2, col3 = st.columns(3)
    
    with col1: 
        csv = pd.DataFrame([data]).to_csv(index=False)
        st.download_button(
            "Aktuelle Daten (CSV)", 
            csv, 
            f"storage_current_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.csv", 
            "text/csv", 
            use_container_width=True
        )
    
    with col2:
        if st.session_state.get('show_comparison') and st.session_state.before_analysis:
            comparison_data = {
                'vorher': st.session_state.before_analysis, 
                'nachher': st.session_state.after_analysis, 
                'vergleich_datum': datetime.now().isoformat()
            }
            json_str = json.dumps(comparison_data, indent=2, ensure_ascii=False)
            st.download_button(
                "Vergleich (JSON)", 
                json_str, 
                f"storage_comparison_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json", 
                "application/json", 
                use_container_width=True
            )
        else: 
            st.button(
                "Vergleich (JSON)", 
                disabled=True, 
                use_container_width=True, 
                help="Kein Vergleich verfügbar. Führen Sie eine Analyse durch."
            )
    
    with col3:
        tenant_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') == tenant['tenant_id']]
        if tenant_history: 
            history_json = json.dumps(tenant_history, indent=2, ensure_ascii=False)
            st.download_button(
                "Gesamte History (JSON)", 
                history_json, 
                f"storage_history_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json", 
                "application/json", 
                use_container_width=True
            )
        else: 
            st.button(
                "History (JSON)", 
                disabled=True, 
                use_container_width=True, 
                help="Keine History verfügbar"
            )
    
    st.header("Analyserverlauf")
    tenant_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') == tenant['tenant_id']]
    
    if tenant_history:
        history_options = [f"{h['ts'][:16]} - {len(h.get('files', []))} Dateien" for h in reversed(tenant_history)]
        selected = st.selectbox("Analyse auswählen", history_options, key="history_select")
        
        if selected:
            idx = history_options.index(selected)
            selected_entry = list(reversed(tenant_history))[idx]
            
            with st.expander("Analyse-Details", expanded=True):
                st.write(f"Datum: {selected_entry['ts'][:19]}")
                st.write(f"Dateien: {', '.join(selected_entry.get('files', []))}")
                
                if selected_entry['data'].get('recommendations'): 
                    st.write("Empfehlungen:")
                    for rec in selected_entry['data']['recommendations'][:3]:
                        st.write(f"- {rec}")
                
                if st.button("Diese Analyse laden", key="load_selected"): 
                    st.session_state.current_data = selected_entry['data'].copy()
                    st.session_state.before_analysis = selected_entry['data'].copy()
                    st.session_state.show_comparison = False
                    st.success("Analyse geladen!")
                    time.sleep(1)
                    st.rerun()
        
        if st.button("History löschen", type="secondary"):
            st.session_state.analyses_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') != tenant['tenant_id']]
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.show_comparison = False
            st.success("History gelöscht!")
            st.rerun()
    else: 
        st.info("Noch keine Analysen für diesen Tenant")
    
    st.header("Systeminformation")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1: 
        st.metric("Analysen gesamt", len(tenant_history))
    with col2: 
        st.metric("Vergleich aktiv", "Ja" if st.session_state.get('show_comparison') else "Nein")
    with col3: 
        st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    with col4: 
        st.metric("n8n Basis-URL", "Gesetzt" if st.session_state.n8n_base_url else "Fehlt")
    
    # Neue Information über die Endpunkte
    st.subheader("n8n Endpunkte")
    if st.session_state.n8n_base_url:
        base = st.session_state.n8n_base_url.rstrip('/')
        st.code(f"GET-LAST: {base}/get-last-analysis-only")
        st.code(f"NEW-ANALYSIS: {base}/analyze-with-deepseek")
    else:
        st.info("n8n Basis-URL nicht konfiguriert")
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
        # Bitte ändere diese URL zu deiner tatsächlichen n8n Basis-URL
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
