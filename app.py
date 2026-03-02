import os, uuid, json, time, pathlib, hashlib
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import base64

# ====== INSIGHTS ENGINE ======
from insights import build_insights

# ====== KLASSEN ======
class N8NResponseValidator:
    @staticmethod
    def validate_response(response):
        if not response:
            return None, "Leere Response erhalten"
        if isinstance(response, dict) and "data" in response:
            data = response.get("data", {})
            if isinstance(data, dict):
                return data, None
            return None, "Data-Feld ist kein Dictionary"
        if isinstance(response, dict):
            metrics = {}
            if "metrics" in response:
                metrics = response["metrics"]
            elif "analysis_result" in response:
                ar = response["analysis_result"]
                if isinstance(ar, dict):
                    metrics = ar.get("metrics", ar)
            elif any(k in response for k in ["belegt", "frei", "belegungsgrad"]):
                metrics = response
            else:
                return None, "Keine Metriken gefunden"
            recommendations = response.get("recommendations", response.get("recommendation_list", []))
            customer_message = response.get("customer_message", response.get("summary", ""))
            analysis_date = response.get("analysis_date", response.get("timestamp", response.get("processed_at", datetime.now().isoformat())))
            if isinstance(metrics, str):
                try:
                    metrics = json.loads(metrics)
                except json.JSONDecodeError:
                    return None, "Metrics ist ungültiger JSON-String"
            return {
                "metrics": metrics if isinstance(metrics, dict) else {},
                "recommendations": recommendations if isinstance(recommendations, list) else [],
                "customer_message": customer_message or "Analyse geladen",
                "analysis_date": analysis_date
            }, None
        if isinstance(response, list):
            if len(response) > 0:
                return N8NResponseValidator.validate_response(response[0])
            return None, "Leere Liste"
        return None, f"Unbekanntes Response-Format: {type(response)}"

# ====== PORT FIX ======
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

# ====== KONFIGURATION ======
st.set_page_config(page_title="Self-Storage Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# ====== PASSWORT-HASHES (sha256) ======
TENANTS = {
    "demo@kunde.de": {
        "tenant_id": "kunde_demo_123",
        "name": "Demo Kunde GmbH",
        "plan": "pro",
        "analyses_limit": 50,
        "analyses_used": 0,
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest()
    },
    "test@firma.de": {
        "tenant_id": "firma_test_456",
        "name": "Test Firma AG",
        "plan": "business",
        "analyses_limit": 200,
        "analyses_used": 0,
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest()
    }
}

# ====== DEFAULT DATEN ======
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [5, 4, 7, 6, 8, 9],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ====== PERSISTENTE HISTORY ======
def save_history_to_disk(tenant_id: str, history: list):
    try:
        path = pathlib.Path(f".history_{tenant_id}.json")
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"History speichern fehlgeschlagen: {e}")

def load_history_from_disk(tenant_id: str) -> list:
    try:
        path = pathlib.Path(f".history_{tenant_id}.json")
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        print(f"History laden fehlgeschlagen: {e}")
    return []

def extract_business_data(contract: dict) -> dict:
    """Extrahiert Business-Daten aus einem standardisierten Contract-Dict"""
    data = contract.get("data", {})
    result = DEFAULT_DATA.copy()

    metrics = data.get("metrics", {})
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except json.JSONDecodeError:
            metrics = {}

    def safe_num(v):
        if isinstance(v, (int, float)):
            return v
        try:
            return float(v)
        except Exception:
            return v

    for key in result:
        if key in metrics:
            result[key] = safe_num(metrics[key])

    for special in ["kundenherkunft", "zahlungsstatus"]:
        if special in metrics:
            result[special] = metrics[special]

    result["recommendations"] = data.get("recommendations", [])
    result["customer_message"] = data.get("customer_message", "")
    result["analysis_date"] = data.get("analysis_date", datetime.now().isoformat())
    return result

# ====== API-FUNKTIONEN ======
def post_to_n8n_get_last(base_url, tenant_id, uuid_str):
    url = f"{base_url.rstrip('/')}/get-last-analysis-only"
    payload = {"tenant_id": tenant_id, "uuid": uuid_str, "action": "get_last_analysis"}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}", None
        json_response = response.json()
        if isinstance(json_response, dict) and 'data' in json_response:
            contract = json_response
            data = contract.get('data', {})
            has_data = (
                contract.get('count', 0) > 0 or
                bool(data.get('recommendations')) or
                bool(data.get('metrics')) or
                bool(data.get('customer_message'))
            )
            if contract.get('status') == 'success' and has_data:
                business_data = data.get('metrics', {}).copy()
                business_data['recommendations'] = data.get('recommendations', [])
                business_data['customer_message'] = data.get('customer_message', '')
                business_data['analysis_date'] = data.get('analysis_date', '')
                business_data['tenant_id'] = contract.get('tenant_id', tenant_id)
                return business_data, "Success", None
            else:
                return None, f"Keine Daten im Contract", json_response
        else:
            if isinstance(json_response, dict) and any(k in json_response for k in ["belegt", "frei", "belegungsgrad"]):
                return json_response, "Success (altes Format)", None
            return None, "Ungültiges Format", json_response
    except requests.exceptions.Timeout:
        return None, "Timeout nach 30s", None
    except Exception as e:
        return None, f"Exception: {str(e)}", None


def parse_supabase_response(response_data):
    """Parst n8n-Antwort – sortiert nach created_at, nimmt die NEUESTE Analyse."""
    # --- Liste: nach Datum sortieren, neueste zuerst ---
    if isinstance(response_data, list):
        if len(response_data) == 0:
            return {"status": "success", "count": 0, "data": DEFAULT_DATA.copy()}

        # ====== FIX: Sortiere nach created_at absteigend → neueste Zeile zuerst ======
        valid_rows = sorted(
            [r for r in response_data if isinstance(r, dict)],
            key=lambda r: r.get('created_at', r.get('updated_at', r.get('converted_at', ''))),
            reverse=True  # neueste zuerst
        )

        # Suche erste (= neueste) Zeile mit analysis_result oder data.recommendations
        _invalid = ('undefined', None, 'unknown', '')
        best_row = None
        for row in valid_rows:
            # Fall A: analysis_result direkt auf der Zeile
            ar = row.get('analysis_result')
            if ar and ar not in _invalid:
                best_row = row
                break
            # Fall A2: analysis_result in data verschachtelt (n8n Contract-Format)
            data_field = row.get('data', {})
            if isinstance(data_field, dict):
                ar_nested = data_field.get('analysis_result')
                if ar_nested and ar_nested not in _invalid:
                    best_row = row
                    break
                # Fall B: data hat bereits recommendations (bereits transformiert)
                if data_field.get('recommendations'):
                    best_row = row
                    break

        if best_row is None:
            return {"status": "success", "count": 0, "data": DEFAULT_DATA.copy()}

        # analysis_result finden: erst top-level, dann in data verschachtelt
        ar = best_row.get('analysis_result')
        if not ar or ar in _invalid:
            nested_data = best_row.get('data', {})
            if isinstance(nested_data, dict):
                ar = nested_data.get('analysis_result')

        # Fall A: analysis_result als JSON-String oder Dict parsen
        if ar and ar not in _invalid:
            try:
                analysis_data = json.loads(ar) if isinstance(ar, str) else ar
                return {
                    "status": "success",
                    "tenant_id": best_row.get('tenant_id'),
                    "count": 1,
                    "data": {
                        "metrics": analysis_data.get('metrics', {}),
                        "recommendations": analysis_data.get('recommendations', []),
                        "customer_message": analysis_data.get('customer_message', ''),
                        "analysis_date": analysis_data.get('analysis_date', best_row.get('created_at', ''))
                    }
                }
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fall B: data-Feld direkt nutzen
        data_field = best_row.get('data', {})
        if isinstance(data_field, dict):
            return {
                "status": "success",
                "tenant_id": best_row.get('tenant_id'),
                "count": 1,
                "data": data_field
            }

        return {"status": "success", "count": 0, "data": DEFAULT_DATA.copy()}

    # --- Dict direkt von n8n (bereits strukturiert) ---
    if isinstance(response_data, dict):
        if 'data' in response_data:
            data = response_data.get('data', {})
            has_content = (
                data.get('recommendations') or
                data.get('metrics') or
                data.get('customer_message')
            )
            if has_content and response_data.get('count', 0) == 0:
                response_data = dict(response_data)
                response_data['count'] = 1
            return response_data
        ar = response_data.get('analysis_result')
        if ar and ar not in ('undefined', None, 'unknown', ''):
            try:
                analysis_data = json.loads(ar) if isinstance(ar, str) else ar
                return {
                    "status": "success",
                    "tenant_id": response_data.get('tenant_id'),
                    "count": 1,
                    "data": {
                        "metrics": analysis_data.get('metrics', {}),
                        "recommendations": analysis_data.get('recommendations', []),
                        "customer_message": analysis_data.get('customer_message', ''),
                        "analysis_date": analysis_data.get('analysis_date', '')
                    }
                }
            except (json.JSONDecodeError, AttributeError):
                pass

    return {"status": "error", "message": f"Unbekanntes Format: {type(response_data)}", "data": DEFAULT_DATA.copy()}


def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
    """Sendet Datei an n8n und gibt standardisiertes Ergebnis zurück"""
    url = f"{base_url.rstrip('/')}/analyze-with-deepseek"
    filename, file_content, file_type = file_info
    base64_content = base64.b64encode(file_content).decode('utf-8')
    payload = {
        "tenant_id": tenant_id,
        "uuid": uuid_str,
        "action": "analyze_with_deepseek",
        "file": {"filename": filename, "content_type": file_type, "data": base64_content},
        "metadata": {"source": "streamlit", "timestamp": datetime.now().isoformat()}
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code != 200:
            return {"status": "error", "code": response.status_code, "message": f"HTTP {response.status_code}: {response.text[:200]}", "data": None}
        try:
            json_response = response.json()
            if isinstance(json_response, dict) and "status" in json_response:
                standardized = json_response
            else:
                validated_data, error = N8NResponseValidator.validate_response(json_response)
                if validated_data:
                    standardized = {"status": "success", "data": validated_data}
                else:
                    standardized = {"status": "error", "data": {"metrics": {}, "recommendations": [], "customer_message": f"Validierungsfehler: {error}", "analysis_date": datetime.now().isoformat()}}
            return {
                "status": "success",
                "code": 200,
                "message": "Analyse erfolgreich",
                "data": standardized.get("data", {}) if standardized.get("status") == "success" else None
            }
        except json.JSONDecodeError:
            return {"status": "error", "code": 500, "message": f"Kein JSON: {response.text[:200]}", "data": None}
    except Exception as e:
        return {"status": "error", "code": 500, "message": f"Exception: {str(e)}", "data": None}


# ====== HILFSFUNKTIONEN ======
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
            counts = df[herkunft_cols[0]].value_counts().to_dict()
            metrics['kundenherkunft'] = {'Online': counts.get('Online', 0), 'Empfehlung': counts.get('Empfehlung', 0), 'Vorbeikommen': counts.get('Vorbeikommen', 0)}
        status_cols = [c for c in df.columns if 'status' in c.lower()]
        if status_cols:
            counts = df[status_cols[0]].value_counts().to_dict()
            metrics['zahlungsstatus'] = {'bezahlt': counts.get('bezahlt', 0), 'offen': counts.get('offen', 0), 'überfällig': counts.get('überfällig', 0)}
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
    fig.update_layout(title=f"{title}<br><span style='font-size:12px;color:{delta_color}'>{delta_symbol}{delta:.1f} Veränderung</span>", height=300, showlegend=True, yaxis_title=title)
    return fig

def create_timeseries_chart(history_data, metric_key, title):
    if not history_data or len(history_data) < 2:
        return None
    dates, values = [], []
    for entry in sorted(history_data, key=lambda x: x.get('ts', '')):
        if isinstance(entry, dict) and 'data' in entry and metric_key in entry['data']:
            dates.append(entry.get('ts', ''))
            values.append(entry['data'][metric_key])
    if len(dates) < 2:
        return None
    fig = go.Figure(data=[go.Scatter(x=dates, y=values, mode='lines+markers', name=title)])
    fig.update_layout(title=f"Entwicklung: {title}", height=300, xaxis_title="Datum", yaxis_title=title)
    return fig

def generate_fallback_recommendations(tenant_name, data):
    recs = []
    if data.get('belegungsgrad', 0) > 80:
        recs.append(f"Hohe Auslastung bei {tenant_name} - Erwäge Erweiterung")
    elif data.get('belegungsgrad', 0) < 50:
        recs.append(f"Geringe Auslastung bei {tenant_name} - Marketing intensivieren")
    if data.get('vertragsdauer_durchschnitt', 0) < 6:
        recs.append("Vertragsdauer erhöhen durch Rabatte für Langzeitmieten")
    if data.get('social_facebook', 0) + data.get('social_google', 0) < 100:
        recs.append("Social Media Präsenz ausbauen")
    recs.append("Regelmäßige Kundenbefragungen durchführen")
    recs.append("Automatische Zahlungserinnerungen einrichten")
    return recs


def load_last_analysis():
    if not st.session_state.logged_in:
        return False

    tenant_id = st.session_state.current_tenant["tenant_id"]
    n8n_base_url = st.session_state.n8n_base_url

    if not n8n_base_url:
        st.warning("n8n Basis-URL nicht gesetzt.")
        st.session_state.current_data = DEFAULT_DATA.copy()
        return True

    with st.spinner("Lade letzte Analyse..."):
        try:
            response = requests.post(
                f"{n8n_base_url.rstrip('/')}/get-last-analysis-only",
                json={"tenant_id": tenant_id, "uuid": str(uuid.uuid4())},
                timeout=10
            )
            if response.status_code != 200:
                st.info("Keine vorherige Analyse gefunden.")
                st.session_state.current_data = DEFAULT_DATA.copy()
                return True

            supabase_data = response.json()

            if st.session_state.debug_mode:
                with st.expander("Debug: Raw Supabase Response"):
                    st.json(supabase_data)

            contract = parse_supabase_response(supabase_data)

            data_field = contract.get('data', {})
            has_data = (
                contract.get('count', 0) > 0 or
                bool(data_field.get('recommendations')) or
                bool(data_field.get('metrics')) or
                bool(data_field.get('customer_message'))
            )
            if contract.get('status') == 'success' and has_data:
                business_data = extract_business_data(contract)
                # Wenn Metriken leer (n8n metrics: {}) → aus lokaler History ergänzen
                if not business_data.get('belegt') or business_data.get('belegt') == DEFAULT_DATA.get('belegt'):
                    local_history = load_history_from_disk(tenant_id)
                    if local_history:
                        for entry in reversed(local_history):
                            local_data = entry.get('data', {})
                            if local_data.get('belegt') and local_data.get('belegt') != DEFAULT_DATA.get('belegt'):
                                for key in ['belegt', 'frei', 'belegungsgrad', 'vertragsdauer_durchschnitt', 'reminder_automat', 'social_facebook', 'social_google', 'kundenherkunft', 'zahlungsstatus', 'neukunden_monat', 'neukunden_labels']:
                                    if key in local_data:
                                        business_data[key] = local_data[key]
                                break
                st.session_state.current_data = business_data
                st.session_state.before_analysis = business_data.copy()
                date_str = business_data.get('analysis_date', '')[:10]
                st.success(f"Letzte Analyse geladen vom {date_str}")
                return True
            else:
                st.info("Keine Analyse in der Datenbank.")
                st.session_state.current_data = DEFAULT_DATA.copy()
                return True

        except Exception as e:
            st.error(f"Fehler beim Laden: {str(e)}")
            st.session_state.current_data = DEFAULT_DATA.copy()
            return False


def perform_analysis(uploaded_files):
    if not st.session_state.logged_in:
        st.error("Kein Tenant eingeloggt")
        return

    tenant_id = st.session_state.current_tenant['tenant_id']
    tenant_name = st.session_state.current_tenant['name']
    st.session_state.before_analysis = st.session_state.current_data.copy()

    excel_data = {}
    for excel_file in [f for f in uploaded_files if f.name.lower().endswith((".xlsx", ".xls", ".csv"))]:
        try:
            df = pd.read_csv(excel_file) if excel_file.name.endswith('.csv') else pd.read_excel(excel_file)
            excel_data = merge_data(excel_data, extract_metrics_from_excel(df))
        except Exception as e:
            st.warning(f"Konnte {excel_file.name} nicht lesen: {str(e)[:50]}")

    n8n_base_url = st.session_state.n8n_base_url
    if not n8n_base_url:
        st.error("Bitte n8n Basis-URL in der Sidebar eingeben")
        return

    main_file = uploaded_files[0]
    file_info = (main_file.name, main_file.getvalue(), main_file.type)

    with st.spinner("KI analysiert Daten... (dies kann 30-60 Sekunden dauern)"):
        result = post_to_n8n_analyze(n8n_base_url, tenant_id, str(uuid.uuid4()), file_info)

    if st.session_state.debug_mode:
        with st.expander("Debug: n8n Kommunikation", expanded=False):
            st.write(f"Status: {result['status']}")
            st.write(f"Code: {result.get('code')}")
            st.write(f"Meldung: {result.get('message')}")
            if result.get('data'):
                st.json(result['data'])

    if result['status'] == 'success' and result['data']:
        n8n_data = result['data']
        final_metrics = {}
        if "metrics" in n8n_data:
            final_metrics = n8n_data["metrics"].copy() if n8n_data["metrics"] else {}
        # Excel-Daten immer einmergen (auch wenn n8n metrics leer oder fehlt)
        for key, value in excel_data.items():
            if key not in final_metrics or final_metrics[key] == 0:
                final_metrics[key] = value

        final_data = DEFAULT_DATA.copy()
        for key in final_data:
            if key in final_metrics:
                final_data[key] = final_metrics[key]

        final_data["recommendations"] = n8n_data.get("recommendations", [])
        if not final_data["recommendations"]:
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)

        final_data["customer_message"] = n8n_data.get("customer_message", f"Analyse für {tenant_name} abgeschlossen.")
        final_data["analysis_date"] = n8n_data.get("analysis_date", datetime.now().isoformat())
        final_data["tenant_id"] = tenant_id
        final_data["files"] = [f.name for f in uploaded_files]
        final_data["source"] = "n8n_ai"

        st.session_state.after_analysis = final_data.copy()
        st.session_state.current_data = final_data.copy()

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
        save_history_to_disk(tenant_id, st.session_state.analyses_history)

        if 'analyses_used' in st.session_state.current_tenant:
            st.session_state.current_tenant['analyses_used'] += 1

        st.success(f"✅ KI-Analyse erfolgreich für {tenant_name}!")
        st.session_state.show_comparison = True
        st.balloons()

    else:
        st.warning(f"⚠️ KI-Analyse fehlgeschlagen: {result.get('message', 'Unbekannter Fehler')}")
        if excel_data:
            st.info("Verwende Excel-Daten als Fallback...")
            final_data = DEFAULT_DATA.copy()
            for key in final_data:
                if key in excel_data:
                    final_data[key] = excel_data[key]
            final_data["recommendations"] = generate_fallback_recommendations(tenant_name, final_data)
            final_data["customer_message"] = f"Analyse basierend auf Excel-Daten für {tenant_name}"
            final_data["analysis_date"] = datetime.now().isoformat()
            final_data["tenant_id"] = tenant_id
            final_data["files"] = [f.name for f in uploaded_files]
            final_data["source"] = "excel_fallback"

            st.session_state.after_analysis = final_data.copy()
            st.session_state.current_data = final_data.copy()

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
            save_history_to_disk(tenant_id, st.session_state.analyses_history)

            st.success(f"✅ Excel-Analyse erfolgreich für {tenant_name}!")
            st.session_state.show_comparison = True
        else:
            st.error("Keine analysierbaren Daten gefunden.")
            return

    time.sleep(1)
    st.rerun()


# ====== SEITENFUNKTIONEN ======
def render_login_page():
    st.title("Self-Storage Business Intelligence")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""## Willkommen!
**KI-gestützte Analyse für Self-Storage Unternehmen:**
✅ Durchgängiger Workflow  
✅ Vorher/Nachher Visualisierung  
✅ Automatisches Laden  
✅ Zeitliche Entwicklung  

**Demo-Zugänge:**
- E-Mail: `demo@kunde.de` | Passwort: `demo123`
- E-Mail: `test@firma.de` | Passwort: `demo123`
""")
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", caption="Data-Driven Decisions for Self-Storage")
        st.info("**Beispiel-Vergleich:**\n\n**Vorher:** Belegungsgrad: 75%\n\n**Nachher:** Belegungsgrad: 82% (+7%)")

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Vergleichsansicht**")
        st.write("Side-by-Side Diagramme, Delta-Berechnungen")
    with col2:
        st.markdown("**History-Tracking**")
        st.write("Alle Analysen persistent gespeichert, Zeitreihen")
    with col3:
        st.markdown("**KI-Integration**")
        st.write("Automatische Empfehlungen, Datenbank-Anbindung")


def render_overview():
    tenant = st.session_state.current_tenant
    st.title(f"Dashboard - {tenant['name']}")

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.info(f"Tenant-ID: `{tenant['tenant_id']}`")
    with col2: st.info(f"Plan: {tenant['plan'].upper()}")
    with col3:
        used = tenant.get('analyses_used', 0)
        limit = tenant.get('analyses_limit', '∞')
        st.info(f"Analysen: {used}/{limit}")
    with col4:
        current_date = st.session_state.current_data.get('analysis_date', '')
        display_date = current_date[:10] if current_date else "Keine"
        st.info(f"Letzte Analyse: {display_date}")

    st.header("Neue Analyse durchführen")
    uploaded_files = st.file_uploader("Dateien hochladen (Excel/CSV)", type=["xlsx", "xls", "csv"], accept_multiple_files=True, key="file_uploader")

    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("KI-Analyse starten", type="primary", use_container_width=True, disabled=not uploaded_files)
    with col2:
        if st.button("Letzte Analyse neu laden", use_container_width=True):
            load_last_analysis()
            st.session_state.show_comparison = False
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
            delta = after.get('belegungsgrad', 0) - before.get('belegungsgrad', 0)
            st.metric("Belegungsgrad", f"{after.get('belegungsgrad', 0)}%", f"{delta:+.1f}%")
        with col2:
            delta = after.get('vertragsdauer_durchschnitt', 0) - before.get('vertragsdauer_durchschnitt', 0)
            st.metric("Ø Vertragsdauer", f"{after.get('vertragsdauer_durchschnitt', 0):.1f} Monate", f"{delta:+.1f}")
        with col3:
            delta = after.get('belegt', 0) - before.get('belegt', 0)
            st.metric("Belegte Einheiten", after.get('belegt', 0), f"{delta:+d}")
        with col4:
            before_social = before.get('social_facebook', 0) + before.get('social_google', 0)
            after_social = after.get('social_facebook', 0) + after.get('social_google', 0)
            st.metric("Social Engagement", after_social, f"{after_social - before_social:+.0f}")

        st.subheader("Detail-Vergleich")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_comparison_chart(before, after, 'belegungsgrad', 'Belegungsgrad (%)')
            if fig: st.plotly_chart(fig, use_container_width=True)
            if 'kundenherkunft' in before and 'kundenherkunft' in after:
                fig = make_subplots(rows=1, cols=2, subplot_titles=('Vorher', 'Nachher'), specs=[[{'type': 'domain'}, {'type': 'domain'}]])
                fig.add_trace(go.Pie(labels=list(before['kundenherkunft'].keys()), values=list(before['kundenherkunft'].values()), name="Vorher"), 1, 1)
                fig.add_trace(go.Pie(labels=list(after['kundenherkunft'].keys()), values=list(after['kundenherkunft'].values()), name="Nachher"), 1, 2)
                fig.update_layout(height=300, title_text="Kundenherkunft")
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'zahlungsstatus' in before and 'zahlungsstatus' in after:
                categories = list(before['zahlungsstatus'].keys())
                fig = go.Figure(data=[
                    go.Bar(name='Vorher', x=categories, y=[before['zahlungsstatus'][k] for k in categories]),
                    go.Bar(name='Nachher', x=categories, y=[after['zahlungsstatus'][k] for k in categories])
                ])
                fig.update_layout(title='Zahlungsstatus Vergleich', height=300, barmode='group')
                st.plotly_chart(fig, use_container_width=True)

        recommendations = after.get('recommendations', [])
        local_tips = build_insights(after)

        if recommendations:
            st.subheader("KI-Empfehlungen")
            for i, rec in enumerate(recommendations[:5], 1):
                st.markdown(f"**{i}.** {rec}")

        if local_tips:
            st.subheader("📊 Lokale Analyse-Empfehlungen")
            for tip in local_tips[:4]:
                with st.expander(f"💡 {tip['title']} | Impact: {tip['impact_score']}/10 | ~{tip['savings_eur']:.0f}€/Monat"):
                    st.write(tip["analysis"])
                    for action in tip["actions"]:
                        st.markdown(f"- {action}")

        if after.get('customer_message'):
            with st.expander("Zusammenfassung"):
                st.info(after['customer_message'])

    else:
        data = st.session_state.current_data
        st.subheader("Aktuelle KPIs")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
        with col2: st.metric("Ø Vertragsdauer", f"{data.get('vertragsdauer_durchschnitt', 0)} Monate")
        with col3: st.metric("Belegte Einheiten", data.get('belegt', 0))
        with col4: st.metric("Social Engagement", data.get('social_facebook', 0) + data.get('social_google', 0))

        local_tips = build_insights(data)
        if local_tips and not data.get("recommendations"):
            st.subheader("📊 Handlungsempfehlungen")
            for tip in local_tips[:3]:
                with st.expander(f"💡 {tip['title']} | Impact: {tip['impact_score']}/10 | ~{tip['savings_eur']:.0f}€/Monat"):
                    st.write(tip["analysis"])
                    for action in tip["actions"]:
                        st.markdown(f"- {action}")

        st.subheader("Aktuelle Visualisierungen")
        col1, col2 = st.columns(2)
        with col1:
            belegung = data.get('belegungsgrad', 0)
            fig = go.Figure(data=[go.Pie(labels=["Belegt", "Frei"], values=[belegung, max(100 - belegung, 0)], hole=0.6)])
            fig.update_layout(title="Belegungsgrad", height=300)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'kundenherkunft' in data:
                df = pd.DataFrame({"Kanal": list(data['kundenherkunft'].keys()), "Anzahl": list(data['kundenherkunft'].values())})
                fig = px.pie(df, values='Anzahl', names='Kanal')
                fig.update_layout(title="Kundenherkunft", height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                labels = data.get('neukunden_labels', ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun'])
                values = data.get('neukunden_monat', [5, 4, 7, 6, 8, 9])
                min_len = min(len(labels), len(values))
                fig = go.Figure(data=[go.Bar(x=labels[:min_len], y=values[:min_len])])
                fig.update_layout(title="Neukunden pro Monat", height=300)
                st.plotly_chart(fig, use_container_width=True)

    st.header("Analyse-History")
    tenant_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') == tenant['tenant_id']]
    if tenant_history:
        st.subheader("Entwicklung über Zeit")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_timeseries_chart(tenant_history, 'belegungsgrad', 'Belegungsgrad (%)')
            if fig: st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_timeseries_chart(tenant_history, 'vertragsdauer_durchschnitt', 'Vertragsdauer (Monate)')
            if fig: st.plotly_chart(fig, use_container_width=True)

        history_df = []
        for entry in reversed(tenant_history[-10:]):
            history_df.append({
                'Datum': entry.get('ts', '')[:16].replace('T', ' '),
                'Dateien': len(entry.get('files', [])),
                'Belegungsgrad': f"{entry['data'].get('belegungsgrad', 0)}%",
                'Empfehlungen': len(entry['data'].get('recommendations', []))
            })
        if history_df: st.dataframe(pd.DataFrame(history_df), use_container_width=True)
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
                st.dataframe(pd.DataFrame({"Kanal": list(before['kundenherkunft'].keys()), "Anzahl": list(before['kundenherkunft'].values())}), use_container_width=True)
        with col2:
            st.subheader("Nachher")
            if 'kundenherkunft' in after:
                st.dataframe(pd.DataFrame({"Kanal": list(after['kundenherkunft'].keys()), "Anzahl": list(after['kundenherkunft'].values())}), use_container_width=True)
        if 'kundenherkunft' in before and 'kundenherkunft' in after:
            st.subheader("Veränderungen")
            changes = []
            for key in before['kundenherkunft'].keys():
                bv = before['kundenherkunft'].get(key, 0)
                av = after['kundenherkunft'].get(key, 0)
                change = av - bv
                pct = (change / bv * 100) if bv > 0 else 0
                changes.append({'Kanal': key, 'Vorher': bv, 'Nachher': av, 'Δ Absolut': change, 'Δ %': f"{pct:+.1f}%" if bv > 0 else "Neu"})
            st.dataframe(pd.DataFrame(changes), use_container_width=True)
    else:
        herkunft = data.get("kundenherkunft", {})
        if herkunft:
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(pd.DataFrame({"Kanal": list(herkunft.keys()), "Anzahl": list(herkunft.values())}), use_container_width=True)
            with col2:
                fig = px.pie(pd.DataFrame({"Kanal": list(herkunft.keys()), "Anzahl": list(herkunft.values())}), values='Anzahl', names='Kanal')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Kundendaten verfügbar. Führen Sie eine Analyse durch.")


def render_capacity():
    st.title("Kapazitätsmanagement")
    data = st.session_state.current_data
    if st.session_state.get('show_comparison') and st.session_state.before_analysis:
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
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
        fig = go.Figure(data=[
            go.Bar(name='Vorher', x=['Belegt', 'Frei'], y=[before.get('belegt', 0), before.get('frei', 0)]),
            go.Bar(name='Nachher', x=['Belegt', 'Frei'], y=[after.get('belegt', 0), after.get('frei', 0)])
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
            fig = go.Figure(data=[go.Bar(x=["Belegt", "Frei"], y=[data.get("belegt", 0), data.get("frei", 0)])])
            fig.update_layout(title="Kapazitätsverteilung", height=300)
            st.plotly_chart(fig, use_container_width=True)


def render_finance():
    st.title("Finanzübersicht")
    data = st.session_state.current_data
    if st.session_state.get('show_comparison') and st.session_state.before_analysis:
        before = st.session_state.before_analysis
        after = st.session_state.after_analysis
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Vorher")
            if 'zahlungsstatus' in before:
                st.dataframe(pd.DataFrame({"Status": list(before['zahlungsstatus'].keys()), "Anzahl": list(before['zahlungsstatus'].values())}), use_container_width=True)
        with col2:
            st.subheader("Nachher")
            if 'zahlungsstatus' in after:
                st.dataframe(pd.DataFrame({"Status": list(after['zahlungsstatus'].keys()), "Anzahl": list(after['zahlungsstatus'].values())}), use_container_width=True)
        if 'zahlungsstatus' in before and 'zahlungsstatus' in after:
            before_total = sum(before['zahlungsstatus'].values())
            before_moral = (before['zahlungsstatus'].get('bezahlt', 0) / before_total * 100) if before_total > 0 else 0
            after_total = sum(after['zahlungsstatus'].values())
            after_moral = (after['zahlungsstatus'].get('bezahlt', 0) / after_total * 100) if after_total > 0 else 0
            col1, col2 = st.columns(2)
            with col1: st.metric("Zahlungsmoral Vorher", f"{before_moral:.1f}%")
            with col2: st.metric("Zahlungsmoral Nachher", f"{after_moral:.1f}%", f"{after_moral - before_moral:+.1f}%")
    else:
        status = data.get("zahlungsstatus", {})
        if status:
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(pd.DataFrame({"Status": list(status.keys()), "Anzahl": list(status.values())}), use_container_width=True)
            with col2:
                total = sum(status.values())
                moral = (status.get('bezahlt', 0) / total * 100) if total > 0 else 0
                st.metric("Zahlungsmoral", f"{moral:.1f}%")
                fig = px.pie(pd.DataFrame({"Status": list(status.keys()), "Anzahl": list(status.values())}), values='Anzahl', names='Status')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Keine Finanzdaten verfügbar.")


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
        st.download_button("Aktuelle Daten (CSV)", csv, f"storage_current_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    with col2:
        if st.session_state.get('show_comparison') and st.session_state.before_analysis:
            comparison_data = {'vorher': st.session_state.before_analysis, 'nachher': st.session_state.after_analysis, 'vergleich_datum': datetime.now().isoformat()}
            st.download_button("Vergleich (JSON)", json.dumps(comparison_data, indent=2, ensure_ascii=False), f"storage_comparison_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json", "application/json", use_container_width=True)
        else:
            st.button("Vergleich (JSON)", disabled=True, use_container_width=True, help="Kein Vergleich verfügbar.")
    with col3:
        tenant_history = [h for h in st.session_state.analyses_history if h.get('tenant_id') == tenant['tenant_id']]
        if tenant_history:
            st.download_button("Gesamte History (JSON)", json.dumps(tenant_history, indent=2, ensure_ascii=False), f"storage_history_{tenant['tenant_id']}_{datetime.now().strftime('%Y%m%d')}.json", "application/json", use_container_width=True)
        else:
            st.button("History (JSON)", disabled=True, use_container_width=True, help="Keine History verfügbar")

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
            save_history_to_disk(tenant['tenant_id'], [])
            st.session_state.current_data = DEFAULT_DATA.copy()
            st.session_state.show_comparison = False
            st.success("History gelöscht!")
            st.rerun()
    else:
        st.info("Noch keine Analysen für diesen Tenant")

    st.header("Systeminformation")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Analysen gesamt", len(tenant_history))
    with col2: st.metric("Vergleich aktiv", "Ja" if st.session_state.get('show_comparison') else "Nein")
    with col3: st.metric("Debug-Modus", "Aktiv" if st.session_state.debug_mode else "Inaktiv")
    with col4: st.metric("n8n Basis-URL", "Gesetzt" if st.session_state.n8n_base_url else "Fehlt")

    st.subheader("n8n Endpunkte")
    if st.session_state.n8n_base_url:
        base = st.session_state.n8n_base_url.rstrip('/')
        st.code(f"GET-LAST: {base}/get-last-analysis-only")
        st.code(f"NEW-ANALYSIS: {base}/analyze-with-deepseek")
    else:
        st.info("n8n Basis-URL nicht konfiguriert")


# ====== HAUPTAPP ======
def main():
    if "current_data" not in st.session_state: st.session_state.current_data = DEFAULT_DATA.copy()
    if "before_analysis" not in st.session_state: st.session_state.before_analysis = None
    if "after_analysis" not in st.session_state: st.session_state.after_analysis = None
    if "analyses_history" not in st.session_state: st.session_state.analyses_history = []
    if "n8n_base_url" not in st.session_state: st.session_state.n8n_base_url = os.environ.get("N8N_BASE_URL", "https://tundtelectronics.app.n8n.cloud/webhook")
    if "debug_mode" not in st.session_state: st.session_state.debug_mode = False
    if "show_comparison" not in st.session_state: st.session_state.show_comparison = False
    if "last_analysis_loaded" not in st.session_state: st.session_state.last_analysis_loaded = False
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "current_tenant" not in st.session_state: st.session_state.current_tenant = None

    with st.sidebar:
        st.title("Login & Einstellungen")

        if not st.session_state.logged_in:
            st.subheader("Anmelden")
            email = st.text_input("E-Mail", key="login_email")
            password = st.text_input("Passwort", type="password", key="login_password")

            if st.button("Anmelden", type="primary", use_container_width=True):
                entered_hash = hashlib.sha256(password.encode()).hexdigest()
                if email in TENANTS and TENANTS[email]["password_hash"] == entered_hash:
                    st.session_state.logged_in = True
                    st.session_state.current_tenant = {k: v for k, v in TENANTS[email].items() if k != "password_hash"}
                    st.session_state.analyses_history = load_history_from_disk(TENANTS[email]["tenant_id"])
                    load_success = load_last_analysis()
                    if load_success:
                        st.success(f"Willkommen, {TENANTS[email]['name']}!")
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
                st.caption(f"GET-LAST: `{n8n_base_url.rstrip('/')}/get-last-analysis-only`")
                st.caption(f"ANALYZE: `{n8n_base_url.rstrip('/')}/analyze-with-deepseek`")

            st.session_state.debug_mode = st.checkbox("Debug-Modus")
            st.divider()
            st.subheader("Navigation")
            page = st.radio(
                "Menü",
                ["Übersicht", "Kunden", "Kapazität", "Finanzen", "System"],
                key="nav_radio",
                format_func=lambda x: (
                    f"📊 {x}" if x == "Übersicht" else
                    f"👥 {x}" if x == "Kunden" else
                    f"📦 {x}" if x == "Kapazität" else
                    f"💰 {x}" if x == "Finanzen" else f"⚙️ {x}"
                )
            )
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Vergleich zurücksetzen", use_container_width=True):
                    st.session_state.show_comparison = False
                    time.sleep(0.5)
                    st.rerun()
            with col2:
                if st.button("Daten zurücksetzen", type="secondary", use_container_width=True):
                    st.session_state.current_data = DEFAULT_DATA.copy()
                    st.session_state.before_analysis = None
                    st.session_state.after_analysis = None
                    st.session_state.show_comparison = False
                    time.sleep(0.5)
                    st.rerun()
        else:
            page = "Übersicht"

    if not st.session_state.logged_in:
        render_login_page()
    else:
        if page == "Übersicht": render_overview()
        elif page == "Kunden": render_customers()
        elif page == "Kapazität": render_capacity()
        elif page == "Finanzen": render_finance()
        elif page == "System": render_system()


if __name__ == "__main__":
    main()
