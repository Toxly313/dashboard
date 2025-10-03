# app.py
import os, uuid
from datetime import datetime
import streamlit as st
import numpy as np
import pandas as pd

from ui_theme import inject_css, header_bar, card_start, card_end
from components import sidebar_nav, kpi_row, highlight_card
from charts import bar_compare, donut, line_trend, tiny_spark
from data_utils import post_to_n8n, extract_metrics_from_excel, merge_data, delta

# ---------- Config ----------
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL","https://tundtelectronics.app.n8n.cloud/webhook/process-business-data")

DEFAULT_DATA = {
    "belegt": 15, "frei": 5, "vertragsdauer_durchschnitt": 6.5, "reminder_automat": 12,
    "social_facebook": 250, "social_google": 45, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Oct 2019","Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"],
    "neukunden_monat": [3200, 450, 3300, 470, 3600, 420],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ---------- Page ----------
st.set_page_config(page_title="H-care layout – Self-Storage", page_icon="🟣", layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_nav()
header_bar()

# Session
for k, v in {"data":DEFAULT_DATA.copy(), "prev":DEFAULT_DATA.copy(), "processing":False, "history":[], "upl_key":0}.items():
    if k not in st.session_state: st.session_state[k]=v

# ---------- Upload Row (oben ähnlich Suchleiste/Buttons) ----------
with st.sidebar:
    st.markdown("### Upload")
    uploaded_files = st.file_uploader(
        "Dateien (CSV/JSON/Excel) – eine Hauptdatei geht an n8n, Excel wird gemerged.",
        type=["csv","json","xlsx"], accept_multiple_files=True, key=f"upl_{st.session_state['upl_key']}"
    )
    if st.button("Analysieren"):
        main_file, excel_merge = None, {}
        if uploaded_files:
            csv_json = [f for f in uploaded_files if f.name.lower().endswith((".csv",".json"))]
            xlsx = [f for f in uploaded_files if f.name.lower().endswith(".xlsx")]
            main_file = csv_json[0] if csv_json else uploaded_files[0]
            for xf in xlsx:
                try:
                    import openpyxl
                    df = pd.read_excel(xf)
                    excel_merge = merge_data(excel_merge, extract_metrics_from_excel(df))
                except Exception as e:
                    st.error(f"Excel-Fehler ({xf.name}): {e}")
        if not main_file:
            st.error("Bitte mindestens eine Datei wählen.")
        else:
            st.session_state["prev"] = st.session_state["data"].copy()
            status, text, data_json = post_to_n8n(N8N_WEBHOOK_URL, (main_file.name, main_file.getvalue()), str(uuid.uuid4()))
            base = data_json.get("metrics", data_json) if (status==200 and data_json) else st.session_state["prev"]
            st.session_state["data"] = merge_data(base, excel_merge)
            st.session_state["history"].append({"ts": datetime.now().isoformat(), "data": st.session_state["data"]})
            st.session_state["upl_key"] += 1

data, prev = st.session_state["data"], st.session_state["prev"]

# ---------- KPI Cards Row (4 kleine Kacheln wie im H-care Header) ----------
kpis = [
    {"label":"Total Units", "value": (data.get("belegt",0)+data.get("frei",0))},
    {"label":"Available Units", "value": data.get("frei",0)},
    {"label":"Ø Contract (mo.)", "value": round(data.get("vertragsdauer_durchschnitt",0),1)},
    {"label":"Reminders", "value": data.get("reminder_automat",0)},
]
card_start()
kpi_row([{**k, "value": k["value"], "delta": ""} for k in kpis])
card_end()

# ---------- Top grid: Big bar left, two donuts right ----------
top_left, top_mid, top_right = st.columns([0.6, 0.2, 0.2])

with top_left:
    card_start("Outpatients vs. Inpatients Trend", right_pill="Show by months")
    # Wir mappen: Inpatients = Neukunden_monat, Outpatients = Vorperiode (prev)
    labels = data.get("neukunden_labels", [])
    series_now = data.get("neukunden_monat", [])
    series_prev = prev.get("neukunden_monat", [0]*len(series_now))
    fig_bar = bar_compare(labels, series_prev, series_now, labels=("Outpatients","Inpatients"), title=None)
    st.plotly_chart(fig_bar, use_container_width=True)
    card_end()

with top_mid:
    card_start("Patients by Gender")  # Donut 1 – mappen wir auf Zahlungsstatus „bezahlt-Anteil“
    paid = data.get("zahlungsstatus",{}).get("bezahlt",0)
    tot = sum(data.get("zahlungsstatus",{}).values() or [0])
    pct = (paid/tot*100) if tot else 0
    st.plotly_chart(donut(pct, title=None), use_container_width=True)
    st.caption("• Paid  • Other")
    card_end()

with top_right:
    card_start("Leads Mix")
    her = data.get("kundenherkunft",{}) or {}
    online = her.get("Online",0); tot_l = sum(her.values()) or 1
    pct_o = online/tot_l*100
    st.plotly_chart(donut(pct_o, title=None), use_container_width=True)
    st.caption("• Online  • Other")
    card_end()

# ---------- Bottom grid: line left, table middle, purple highlight right ----------
bot_left, bot_mid, bot_right = st.columns([0.46, 0.28, 0.26])

with bot_left:
    card_start("Time Admitted", right_pill="Today")
    # Linien-Chart: nehmen wir die letzten 10 Punkte aus series_now (oder repeat)
    x = list(range(1, len(series_now)+1))
    st.plotly_chart(line_trend(x, series_now, title=None), use_container_width=True)
    card_end()

with bot_mid:
    card_start("Patients by Division")
    # Tabelle: mappen wir auf Kundenherkunft
    table = pd.DataFrame({
        "DIVISION": list(her.keys()) or ["Online","Empfehlung","Vorbeikommen"],
        "PT.": [her.get("Online",0), her.get("Empfehlung",0), her.get("Vorbeikommen",0)] if her else [0,0,0]
    })
    st.table(table)
    card_end()

with bot_right:
    # Highlight-Karte (violett, Sparkline)
    spark = tiny_spark(x, series_now)
    highlight_card(f"Patients this month", f"{int(series_now[-1]) if series_now else 0}", sparkline=spark)

# ---------- Optional: Foot ----------
st.caption(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} • Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}")
