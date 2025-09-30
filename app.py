import streamlit as st, uuid, json
from datetime import datetime
from config import N8N_WEBHOOK_URL, APP_TITLE, APP_CAPTION, DEBUG_DEFAULT
from state import ensure_state
from n8n_client import post_file
from excel_utils import extract_metrics_from_excel, merge_data
import pandas as pd

from tabs import tab_start, tab_allgemein, tab_finanzen, tab_mitarbeiter, tab_lager, tab_social, tab_erklaerungen, tab_risiken

st.set_page_config(page_title="Self-Storage Dashboard", layout="wide")
st.title(APP_TITLE); st.caption(APP_CAPTION)

ensure_state()

st.sidebar.title("🔧 Optionen")
DEBUG_MODE = st.sidebar.checkbox("Debug-Modus aktivieren", value=DEBUG_DEFAULT)

# EIN Upload-Feld (multi)
st.subheader("📥 Datenzufuhr")
uploaded_files = st.file_uploader(
    "Dateien per Drag & Drop (CSV/JSON/Excel). Eine Datei geht an n8n; Excel wird lokal gemerged.",
    type=["csv","json","xlsx"], accept_multiple_files=True, key=f"upl_{st.session_state.upload_key}"
)

main_file, excel_metrics_total = None, {}

if uploaded_files:
    csv_json = [f for f in uploaded_files if f.name.lower().endswith((".csv",".json"))]
    xlsx = [f for f in uploaded_files if f.name.lower().endswith(".xlsx")]
    main_file = csv_json[0] if csv_json else uploaded_files[0]

    for xf in xlsx:
        try:
            import openpyxl
            df = pd.read_excel(xf)
            metrics = extract_metrics_from_excel(df)
            excel_metrics_total = merge_data(excel_metrics_total, metrics)
        except Exception as e:
            st.error(f"Excel-Fehler ({xf.name}): {e}")

if st.button("📤 Datei(en) hochladen und analysieren", type="primary"):
    if not main_file:
        st.error("Bitte mindestens eine Datei wählen.")
    else:
        st.session_state.processing = True
        try:
            sid = str(uuid.uuid4())
            status, text, data_json = post_file(N8N_WEBHOOK_URL, (main_file.name, main_file.getvalue()), sid)
            if status == 200 and data_json:
                # Erwartet: {metrics, recommendations, customer_message} oder flach
                base = data_json.get("metrics", data_json)
                merged = merge_data(base, excel_metrics_total or {})
                st.session_state.prev_data = st.session_state.data.copy()
                st.session_state.data = merged
                st.session_state.processing = False
                st.session_state.history.append({"ts": datetime.now().isoformat(), "data": merged})
                st.success("✅ Daten erfolgreich verarbeitet!")
            else:
                st.error(f"n8n Fehler: {status}")
                if DEBUG_MODE: st.sidebar.error(text)
                st.session_state.processing = False
        except Exception as e:
            st.error(f"Systemfehler: {e}")
            st.session_state.processing = False

# Tabs rendern
prev, cur = st.session_state.prev_data, st.session_state.data
tab_objs = st.tabs(["🏠 Start","📚 Allgemein","💶 Finanzen","👥 Mitarbeiter","📦 Lager & Auslastung","📣 Social Media","❓ Erklärungen","⚠️ Risiken"])
with tab_objs[0]: tab_start.render(prev, cur)
with tab_objs[1]: tab_allgemein.render(prev, cur)
with tab_objs[2]: tab_finanzen.render(prev, cur)
with tab_objs[3]: tab_mitarbeiter.render(prev, cur)
with tab_objs[4]: tab_lager.render(prev, cur)
with tab_objs[5]: tab_social.render(prev, cur)
with tab_objs[6]: tab_erklaerungen.render(prev, cur)
with tab_objs[7]: tab_risiken.render(prev, cur)
