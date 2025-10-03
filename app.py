# app.py
import os, uuid
from datetime import datetime
import streamlit as st
import numpy as np
import pandas as pd

from ui_theme import inject_base_css, header_block, card_start, card_end
from components import sidebar_profile, kpi_grid
from charts import bar_grouped, area_soft, donut
from data_utils import (
    delta, badge_delta, color_for_change,
    extract_metrics_from_excel, merge_data, post_to_n8n
)

# ---------- Config ----------
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL","https://tundtelectronics.app.n8n.cloud/webhook/process-business-data")

DEFAULT_DATA = {
    "belegt": 15, "frei": 5, "vertragsdauer_durchschnitt": 6.5, "reminder_automat": 12,
    "social_facebook": 250, "social_google": 45, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Jan","Feb","Mär","Apr","Mai","Jun"],
    "neukunden_monat": [3,5,2,4,6,5],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ---------- Page Setup ----------
st.set_page_config(page_title="Self-Storage Dashboard", page_icon="📦", layout="wide", initial_sidebar_state="expanded")
inject_base_css()
header_block("Dashboard User", "White + Orange UI")

# Sidebar User-Card & simple nav list (wie im Mockup)
sidebar_profile(name="JOHN DON", email="johndon@company.com", avatar_emoji="🟠")

# Debug toggles
st.sidebar.markdown("### Optionen")
DEBUG = st.sidebar.toggle("Debug", value=False)
SHOW_RAW = st.sidebar.toggle("Rohdaten anzeigen", value=False)

# Session init
for key, val in {
    "data": DEFAULT_DATA.copy(),
    "prev_data": DEFAULT_DATA.copy(),
    "processing": False,
    "history": [],
    "file_uploader_key": 0
}.items():
    if key not in st.session_state: st.session_state[key] = val

# ---------- Uploads ----------
card_start("Upload", "Check now")
left, right = st.columns([0.7, 0.3])

with left:
    uploaded_files = st.file_uploader(
        "Dateien (CSV/JSON/Excel) – eine Hauptdatei geht an n8n, Excel wird gemerged.",
        type=["csv","json","xlsx"], accept_multiple_files=True,
        key=f"upl_{st.session_state.file_uploader_key}"
    )
with right:
    st.caption("Endpoint")
    st.code(N8N_WEBHOOK_URL, language="text")

main_file, excel_metrics_total = None, {}
file_names = []

if uploaded_files:
    csv_json = [f for f in uploaded_files if f.name.lower().endswith((".csv",".json"))]
    xlsx = [f for f in uploaded_files if f.name.lower().endswith(".xlsx")]
    main_file = csv_json[0] if csv_json else uploaded_files[0]
    file_names = [f.name for f in uploaded_files]

    for xf in xlsx:
        try:
            import openpyxl  # ensure installed
            df_x = pd.read_excel(xf)
            if SHOW_RAW:
                st.markdown(f"**Excel-Vorschau – {xf.name}**")
                st.dataframe(df_x, use_container_width=True)
            metrics = extract_metrics_from_excel(df_x)
            excel_metrics_total = merge_data(excel_metrics_total, metrics)
        except Exception as e:
            st.error(f"Excel-Fehler ({xf.name}): {e}")

clicked = st.button("📤 Hochladen & analysieren", type="primary")
card_end()

if clicked:
    if not main_file:
        st.error("Bitte mindestens eine Datei auswählen.")
    else:
        st.session_state.processing = True
        st.session_state.prev_data = st.session_state.data.copy()
        with st.spinner("KI verarbeitet Daten …"):
            try:
                status, text, data_json = post_to_n8n(N8N_WEBHOOK_URL, (main_file.name, main_file.getvalue()), str(uuid.uuid4()))
                if DEBUG: st.sidebar.code(text[:800], language="text")
                if status==200 and data_json:
                    # {metrics: ...} oder Root
                    base = data_json.get("metrics", data_json)
                    merged = merge_data(base, excel_metrics_total or {})
                    st.session_state.data = merged
                    st.session_state.history.append({"ts": datetime.now().isoformat(), "files": file_names, "data": merged})
                else:
                    st.error(f"n8n Fehlerstatus: {status}")
            finally:
                st.session_state.processing = False

data, prev = st.session_state.data, st.session_state.prev_data

if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet …")

# ---------- KPI Cards Row (Earning/Share/Likes/Rating Stil)
kpis = [
    {"label":"Earning", "value":"$ 628", "delta_text":"+12%"},
    {"label":"Share", "value": f"{data.get('social_google',0)+data.get('social_facebook',0)}", "delta_text":"+3%"},
    {"label":"Likes", "value": f"{data.get('social_facebook',0)}", "delta_text":"+1%"},
    {"label":"Rating", "value": "8,5", "delta_text":"+0,2"}
]
card_start()
kpi_grid(kpis)
card_end()

# ---------- Result (Bar + Callout) ----------
card_start("Result", "Check now")
# Balken (Vorher/Nachher) – Auslastung
x = ["JAN","FEB","MÄR","APR","MAI","JUN"]  # Label-Layout wie im Mockup
nv = data.get("neukunden_monat",[3,5,2,4,6,5])
pv = prev.get("neukunden_monat",[0]*len(nv))
fig_bar = bar_grouped(x, pv, nv, title="Neukunden – Vorher vs. Nachher")
st.plotly_chart(fig_bar, use_container_width=True)
card_end()

# ---------- Area Chart (Smooth Verlauf) ----------
card_start()
area = [max(v,1) for v in nv]
prev_area = [max(v,1) for v in pv]
fig_area = area_soft(x, area, prev_area, title="Trend")
st.plotly_chart(fig_area, use_container_width=True)
card_end()

# ---------- Donut (Belegungsgrad) + Mini-List rechts ----------
colA, colB = st.columns([0.55, 0.45])
with colA:
    card_start(right_badge="Check now")
    occ = float(data.get("belegungsgrad",0))
    fig_donut = donut(occ, title="Belegungsgrad")
    st.plotly_chart(fig_donut, use_container_width=True)
    card_end()

with colB:
    card_start("Notizen")
    st.write("• Lorem ipsum")  # hier könntest du Empfehlungen rendern
    for r in (data.get("recommendations") or [])[:5]:
        st.markdown(f"- {r}")
    card_end()

# ---------- Optional: Rohdaten & History -----------
if SHOW_RAW:
    card_start("Rohdaten & Upload-Historie")
    st.json({"current": data, "prev": prev})
    if st.session_state.history:
        st.table(pd.DataFrame([{"Zeit": h["ts"], "Dateien": ", ".join(h.get("files", []))} for h in st.session_state.history][-6:]))
    card_end()

# ---------- Footer ----------
st.caption(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} • Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}")
