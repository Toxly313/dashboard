import streamlit as st
import sys, traceback, os, uuid, json, time, pathlib, hashlib
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import base64

# ========== ALLERERSTER Streamlit-Befehl ==========
st.set_page_config(
    page_title="Self-Storage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== GLOBALER EXCEPTION-HANDLER ==========
def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        st.error("🔥 Unbehandelte Exception – bitte an Entwickler weitergeben:")
        st.code(error_msg)
    except:
        print(error_msg)

sys.excepthook = global_exception_handler

# ========== MODULE IMPORTIEREN ==========
try:
    from ui_theme import inject_css, style_fig
    from insights import build_insights
    from charts import bar_grouped, donut_chart, tips_impact_chart, tips_savings_chart
    from components import kpi_deck
except Exception as e:
    st.error(f"❌ Fehler beim Import: {e}")
    st.code(traceback.format_exc())
    st.stop()

# ========== CSS INJIZIEREN ==========
try:
    inject_css()
except Exception as e:
    st.error(f"❌ Fehler in inject_css: {e}")
    st.code(traceback.format_exc())
    st.stop()

# ========== PORT FIX ==========
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

# ========== PASSWORT-HASHES ==========
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

# ========== DEFAULT DATEN ==========
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [5, 4, 7, 6, 8, 9],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ========== SESSION-STATE ==========
def init_session_state():
    defaults = {
        "current_data": DEFAULT_DATA.copy(),
        "before_analysis": None,
        "after_analysis": None,
        "analyses_history": [],
        "n8n_base_url": os.environ.get("N8N_BASE_URL", "https://tundtelectronics.app.n8n.cloud/webhook"),
        "debug_mode": False,
        "show_comparison": False,
        "last_analysis_loaded": False,
        "logged_in": False,
        "current_tenant": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ========== N8NResponseValidator ==========
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

# ========== HILFSFUNKTIONEN ==========
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
    data = contract.get("data", {})
    result = DEFAULT_DATA.copy()
    metrics = data.get("metrics", {})
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except json.JSONDecodeError:
            metrics = {}
    if not metrics or (isinstance(metrics, dict) and len(metrics) == 0):
        for key in ["belegt", "frei", "belegungsgrad", "vertragsdauer_durchschnitt",
                     "reminder_automat", "social_facebook", "social_google"]:
            if key in data and data[key] is not None:
                metrics[key] = data[key]
        for special in ["kundenherkunft", "zahlungsstatus"]:
            if special in data and isinstance(data[special], dict):
                metrics[special] = data[special]
    def safe_num(v):
        if isinstance(v, (int, float)):
            return v
        try:
            return float(v)
        except:
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

def parse_supabase_response(response_data):
    if isinstance(response_data, list):
        if len(response_data) == 0:
            return {"status": "success", "count": 0, "data": DEFAULT_DATA.copy()}
        valid_rows = sorted(
            [r for r in response_data if isinstance(r, dict)],
            key=lambda r: r.get('created_at', r.get('updated_at', '')),
            reverse=True
        )
        valid_rows = [r for r in valid_rows if not r.get('_for_supabase')]
        best_row = None
        for row in valid_rows:
            ar = row.get('analysis_result')
            if ar and ar != 'undefined' and ar is not None:
                try:
                    parsed = json.loads(ar) if isinstance(ar, str) else ar
                    if isinstance(parsed, dict) and isinstance(parsed.get('metrics'), dict) and len(parsed.get('metrics', {})) > 0:
                        best_row = row
                        break
                except:
                    pass
        if best_row is None:
            for row in valid_rows:
                ar = row.get('analysis_result')
                if ar and ar != 'undefined' and ar is not None:
                    best_row = row
                    break
        if best_row is None:
            return {"status": "success", "count": 0, "data": DEFAULT_DATA.copy()}
        ar = best_row.get('analysis_result')
        if ar and ar not in ('undefined', None):
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
            except:
                pass
    if isinstance(response_data, dict):
        if 'data' in response_data:
            return response_data
        ar = response_data.get('analysis_result')
        if ar and ar not in ('undefined', None):
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
            except:
                pass
    return {"status": "error", "message": "Unbekanntes Format", "data": DEFAULT_DATA.copy()}

def post_to_n8n_analyze(base_url, tenant_id, uuid_str, file_info):
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
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        json_response = response.json()
        if isinstance(json_response, dict) and "status" in json_response:
            standardized = json_response
        else:
            validated_data, error = N8NResponseValidator.validate_response(json_response)
            if validated_data:
                standardized = {"status": "success", "data": validated_data}
            else:
                standardized = {"status": "error", "data": {}}
        return {
            "status": "success",
            "message": "Analyse erfolgreich",
            "data": standardized.get("data", {}) if standardized.get("status") == "success" else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
            metrics = data_field.get('metrics', {})
            has_real_metrics = isinstance(metrics, dict) and len(metrics) > 0
            has_data = (
                contract.get('count', 0) > 0 or
                bool(data_field.get('recommendations')) or
                has_real_metrics or
                bool(data_field.get('customer_message'))
            )
            if contract.get('status') == 'success' and has_data:
                business_data = extract_business_data(contract)
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
    n8n_base_url = st.session_state.n8n_base_url
    if not n8n_base_url:
        st.error("Bitte n8n Basis-URL in der Sidebar eingeben")
        return
    main_file = uploaded_files[0]
    file_info = (main_file.name, main_file.getvalue(), main_file.type)
    with st.spinner("KI analysiert Daten... (dies kann 30-60 Sekunden dauern)"):
        result = post_to_n8n_analyze(n8n_base_url, tenant_id, str(uuid.uuid4()), file_info)
    if result['status'] == 'success' and result.get('data'):
        n8n_data = result['data']
        final_data = DEFAULT_DATA.copy()
        if "metrics" in n8n_data:
            for k, v in n8n_data["metrics"].items():
                if k in final_data:
                    final_data[k] = v
        final_data["recommendations"] = n8n_data.get("recommendations", [])
        final_data["customer_message"] = n8n_data.get("customer_message", f"Analyse für {tenant_name} abgeschlossen.")
        final_data["analysis_date"] = n8n_data.get("analysis_date", datetime.now().isoformat())
        st.session_state.after_analysis = final_data
        st.session_state.current_data = final_data
        st.session_state.show_comparison = True
        st.success(f"✅ KI-Analyse erfolgreich für {tenant_name}!")
        st.balloons()
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"Analyse fehlgeschlagen: {result.get('message')}")

# ========== SEITEN RENDERING ==========
def render_login_page():
    st.title("Self-Storage Business Intelligence")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""## Willkommen!
**Demo-Zugänge:**
- E-Mail: `demo@kunde.de` | Passwort: `demo123`
- E-Mail: `test@firma.de` | Passwort: `demo123`
""")
    with col2:
        st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600", caption="Data-Driven Decisions for Self-Storage")

def render_overview():
    tenant = st.session_state.current_tenant
    st.title(f"Dashboard - {tenant['name']}")
    data = st.session_state.current_data

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Belegungsgrad", f"{data.get('belegungsgrad', 0)}%")
    col2.metric("Ø Vertragsdauer", f"{data.get('vertragsdauer_durchschnitt', 0):.1f} Mo")
    col3.metric("Belegte Einheiten", data.get('belegt', 0))
    col4.metric("Social Engagement", data.get('social_facebook', 0) + data.get('social_google', 0))

    uploaded_files = st.file_uploader("Dateien hochladen (Excel/CSV)", type=["xlsx", "xls", "csv"], accept_multiple_files=True)
    c1, c2 = st.columns(2)
    if c1.button("KI-Analyse starten", disabled=not uploaded_files):
        perform_analysis(uploaded_files)
    if c2.button("Letzte Analyse neu laden"):
        load_last_analysis()
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        fig = donut_chart(data.get('belegungsgrad', 0), "Belegungsgrad")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        if data.get('kundenherkunft'):
            df = pd.DataFrame({"Kanal": list(data['kundenherkunft'].keys()), "Anzahl": list(data['kundenherkunft'].values())})
            fig = px.pie(df, values='Anzahl', names='Kanal')
            fig = style_fig(fig, "Kundenherkunft")
            st.plotly_chart(fig, use_container_width=True)

def render_page(page_name):
    try:
        if page_name == "Übersicht":
            render_overview()
        elif page_name == "Kunden":
            st.title("Kundenanalyse")
        elif page_name == "Kapazität":
            st.title("Kapazitätsmanagement")
        elif page_name == "Finanzen":
            st.title("Finanzübersicht")
        elif page_name == "System":
            st.title("System & Export")
        else:
            st.title(page_name)
    except Exception as e:
        st.error(f"❌ Fehler beim Rendern der Seite '{page_name}': {e}")
        st.code(traceback.format_exc())

# ========== MAIN ==========
def main():
    with st.sidebar:
        st.title("Login & Einstellungen")
        if not st.session_state.logged_in:
            email = st.text_input("E-Mail")
            password = st.text_input("Passwort", type="password")
            if st.button("Anmelden"):
                entered_hash = hashlib.sha256(password.encode()).hexdigest()
                if email in TENANTS and TENANTS[email]["password_hash"] == entered_hash:
                    st.session_state.logged_in = True
                    st.session_state.current_tenant = {k: v for k, v in TENANTS[email].items() if k != "password_hash"}
                    load_last_analysis()
                    st.rerun()
                else:
                    st.error("Ungültige E-Mail oder Passwort")
        else:
            tenant = st.session_state.current_tenant
            st.success(f"Eingeloggt als: {tenant['name']}")
            if st.button("Abmelden"):
                st.session_state.logged_in = False
                st.rerun()
            st.divider()
            st.session_state.n8n_base_url = st.text_input("n8n Basis-URL", value=st.session_state.n8n_base_url)
            st.session_state.debug_mode = st.checkbox("Debug-Modus")
            st.divider()
            page = st.radio("Menü", ["Übersicht", "Kunden", "Kapazität", "Finanzen", "System"])

    if not st.session_state.logged_in:
        render_login_page()
    else:
        render_page(page)

if __name__ == "__main__":
    main()
