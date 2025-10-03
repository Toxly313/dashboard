# app.py
import os, json, uuid
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from ui_theme import inject_base_css, header_block, apply_fig_style, card_start, card_end
from data_utils import (
    delta, badge_delta, color_for_change,
    extract_metrics_from_excel, merge_data, post_to_n8n
)

# ---------- Config ----------
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://tundtelectronics.app.n8n.cloud/webhook/process-business-data"
)

DEFAULT_DATA = {
    "belegt": 15, "frei": 5, "vertragsdauer_durchschnitt": 6.5, "reminder_automat": 12,
    "social_facebook": 250, "social_google": 45, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [3, 5, 2, 4, 6, 5],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ---------- Page Setup ----------
st.set_page_config(page_title="Self-Storage Dashboard", page_icon="📦", layout="wide", initial_sidebar_state="expanded")
inject_base_css()
header_block("Nalepastraße 162 · Lagerräume mit Business-Center · www.schimmel-automobile.de")

# Sidebar
st.sidebar.subheader("🔧 Optionen")
DEBUG = st.sidebar.checkbox("Debug-Modus", value=False)
SHOW_RAW = st.sidebar.checkbox("Rohdaten anzeigen", value=False)

# Session
for key, val in {
    "data": DEFAULT_DATA.copy(),
    "prev_data": DEFAULT_DATA.copy(),
    "last_upload": None, "processing": False, "history": [],
    "file_uploader_key": 0
}.items():
    if key not in st.session_state: st.session_state[key] = val

# ---------- Upload Section ----------
st.subheader("📥 Datenzufuhr")
left, right = st.columns([0.7, 0.3])
with left:
    uploaded_files = st.file_uploader(
        "Dateien (CSV/JSON/Excel). **Eine** Hauptdatei geht an n8n, Excel wird zusätzlich gemerged.",
        type=["csv","json","xlsx"], accept_multiple_files=True,
        key=f"upl_{st.session_state.file_uploader_key}"
    )
with right:
    st.caption("Aktiver Endpoint")
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
            try:
                import openpyxl
            except ImportError:
                st.error("Bitte `pip install openpyxl` ausführen, um Excel lesen zu können.")
                st.stop()
            df_x = pd.read_excel(xf)
            if SHOW_RAW:
                st.markdown(f"**📋 Excel-Rohdaten – {xf.name}**")
                st.dataframe(df_x, use_container_width=True)
            metrics = extract_metrics_from_excel(df_x)
            excel_metrics_total = merge_data(excel_metrics_total, metrics)
        except Exception as e:
            st.error(f"Excel konnte nicht verarbeitet werden ({xf.name}): {e}")

if st.button("📤 Hochladen & analysieren", type="primary"):
    if not main_file:
        st.error("Bitte mindestens eine Datei wählen.")
    else:
        st.session_state.processing = True
        st.session_state.prev_data = st.session_state.data.copy()
        st.session_state.last_upload = main_file
        with st.spinner("KI verarbeitet Daten …"):
            try:
                session_id = str(uuid.uuid4())
                status, text, data_json = post_to_n8n(N8N_WEBHOOK_URL, (main_file.name, main_file.getvalue()), session_id)
                if DEBUG:
                    st.sidebar.write(f"Status: {status}")
                    st.sidebar.code(text[:800], language="text")

                if status == 200 and data_json:
                    # Root oder {metrics:…}
                    if "metrics" in data_json:
                        base = data_json["metrics"]
                        merged = merge_data(base, excel_metrics_total or {})
                        data_json["metrics"] = merged
                        st.session_state.data = merged
                    else:
                        merged = merge_data(data_json, excel_metrics_total or {})
                        st.session_state.data = merged

                    st.session_state.processing = False
                    st.session_state.history.append({"ts": datetime.now().isoformat(), "data": st.session_state.data, "files": file_names})
                    st.session_state.file_uploader_key += 1
                    st.success("✅ Daten erfolgreich verarbeitet!")
                else:
                    st.error(f"Fehler von n8n: Status {status}")
                    st.session_state.data = st.session_state.prev_data.copy()
                    st.session_state.processing = False
            except Exception as e:
                st.error(f"Systemfehler: {e}")
                st.session_state.data = st.session_state.prev_data.copy()
                st.session_state.processing = False

if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet …")

data, prev = st.session_state.data, st.session_state.prev_data

# ---------- Rohdaten optional ----------
if SHOW_RAW:
    card_start()
    st.markdown("**📂 Rohdaten (aktuell & vorher)**")
    st.json({"prev": prev, "current": data})
    if st.session_state.history:
        st.markdown("**Letzte Uploads (Dateinamen)**")
        st.table(pd.DataFrame([{"Zeit": h["ts"], "Dateien": ", ".join(h.get("files", []))} for h in st.session_state.history][-5:]))
    card_end()

# ---------- KPIs ----------
card_start()
st.subheader("📊 KPIs – Δ seit letztem Upload")
kpi_keys = ["belegt","frei","vertragsdauer_durchschnitt","reminder_automat","social_facebook","social_google","belegungsgrad"]
cols = st.columns(len(kpi_keys))
for i, k in enumerate(kpi_keys):
    cur, prv = data.get(k,0), prev.get(k,0)
    abs_, pct_ = delta(prv, cur)
    cols[i].metric(k.replace("_"," ").title(), cur if isinstance(cur,(int,float)) else str(cur), delta=badge_delta(abs_, pct_))
card_end()

# ---------- Charts ----------
def chart_auslastung():
    belegt_cur, belegt_prev = data.get("belegt",0), prev.get("belegt",0)
    frei_cur, frei_prev     = data.get("frei",0), prev.get("frei",0)
    x = ["Belegt","Frei"]
    prev_vals = [belegt_prev, frei_prev]
    cur_vals  = [belegt_cur,  frei_cur]
    colors = [color_for_change("belegt", belegt_prev, belegt_cur),
              color_for_change("frei", frei_prev, frei_cur)]
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=x, y=prev_vals, marker_color="#CBD5E1")
    fig.add_bar(name="Nachher", x=x, y=cur_vals, marker_color=colors)
    for i, lbl in enumerate(x):
        abs_, pct_ = delta(prev_vals[i], cur_vals[i])
        fig.add_annotation(x=lbl, y=max(prev_vals[i], cur_vals[i]), text=badge_delta(abs_, pct_), showarrow=False, yshift=10)
    return apply_fig_style(fig, "Auslastung: Belegt vs. Frei", 320)

def chart_zahlungen():
    keys = ["bezahlt","offen","überfällig"]
    prev_vals = [prev.get("zahlungsstatus",{}).get(k,0) for k in keys]
    cur_vals  = [data.get("zahlungsstatus",{}).get(k,0) for k in keys]
    colors = [color_for_change(k, prev_vals[i], cur_vals[i]) for i,k in enumerate(keys)]
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=[k.title() for k in keys], y=prev_vals, marker_color="#CBD5E1")
    fig.add_bar(name="Nachher", x=[k.title() for k in keys], y=cur_vals, marker_color=colors, text=[badge_delta(*delta(prev_vals[i],cur_vals[i])) for i in range(len(keys))], textposition="outside")
    return apply_fig_style(fig, "Zahlungsstatus (Δ farblich)", 320)

def chart_herkunft():
    prev_h = prev.get("kundenherkunft",{}) or {}
    cur_h  = data.get("kundenherkunft",{}) or {}
    channels = sorted(set(prev_h.keys())|set(cur_h.keys()))
    p = [prev_h.get(k,0) for k in channels]; c = [cur_h.get(k,0) for k in channels]
    colors = [color_for_change("kundenherkunft", p[i], c[i]) for i in range(len(channels))]
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=channels, y=p, marker_color="#CBD5E1")
    fig.add_bar(name="Nachher", x=channels, y=c, marker_color=colors, text=[badge_delta(*delta(p[i],c[i])) for i in range(len(channels))], textposition="outside")
    return apply_fig_style(fig, "Kundenherkunft (Δ farblich)", 340)

def chart_neukunden():
    labels = data.get("neukunden_labels", [])
    after  = data.get("neukunden_monat", [])
    before = prev.get("neukunden_monat", [0]*len(labels))
    if before and len(before)!=len(after):
        before = before[:len(after)] if len(before)>len(after) else before+[0]*(len(after)-len(before))
    colors = [color_for_change("neukunden_monat", before[i] if i<len(before) else 0, v) for i, v in enumerate(after)]
    deltas = [badge_delta(*delta(before[i] if i<len(before) else 0, v)) for i, v in enumerate(after)]
    fig = go.Figure()
    fig.add_bar(x=labels, y=after, marker_color=colors, text=deltas, textposition="outside", name="Nachher")
    fig.add_scatter(x=labels, y=before, mode="lines+markers", name="Vorher", line=dict(width=2, dash="dot"))
    return apply_fig_style(fig, "Neukunden (Δ farblich, Vorher als Linie)", 340)

col1, col2 = st.columns(2)
with col1:
    card_start(); st.plotly_chart(chart_auslastung(), use_container_width=True); card_end()
    card_start(); st.plotly_chart(chart_herkunft(), use_container_width=True); card_end()
with col2:
    card_start(); st.plotly_chart(chart_zahlungen(), use_container_width=True); card_end()
    card_start(); st.plotly_chart(chart_neukunden(), use_container_width=True); card_end()

# ---------- Zusätzliche Stats ----------
card_start()
st.subheader("🧮 Zusätzliche Statistiken")
# Belegungsgrad berechnet
tot_cur = (data.get("belegt",0) or 0) + (data.get("frei",0) or 0)
occ_calc = (data.get("belegt",0)/tot_cur*100) if tot_cur else data.get("belegungsgrad",0)
tot_prev = (prev.get("belegt",0) or 0) + (prev.get("frei",0) or 0)
occ_prev = (prev.get("belegt",0)/tot_prev*100) if tot_prev else prev.get("belegungsgrad",0)
abs_occ, pct_occ = delta(occ_prev, occ_calc)
# Zahlungsquote
paid = data.get("zahlungsstatus",{}).get("bezahlt",0)
open_ = data.get("zahlungsstatus",{}).get("offen",0)
overd = data.get("zahlungsstatus",{}).get("überfällig",0)
tot_inv = paid+open_+overd
pay_ratio = (paid/tot_inv*100) if tot_inv else 0
# Wachstum Neukunden
try:
    vals = data.get("neukunden_monat",[]) or []
    growth = float(np.mean(np.diff(vals))) if len(vals)>=2 else None
except: growth = None
# Anteile Leads
her = data.get("kundenherkunft",{}) or {}
tot_leads = sum(her.values()) if her else 0
share_empf = (her.get("Empfehlung",0)/tot_leads*100) if tot_leads else 0
share_online = (her.get("Online",0)/tot_leads*100) if tot_leads else 0

c1,c2,c3,c4 = st.columns(4)
c1.metric("Belegungsgrad berechnet (%)", f"{occ_calc:.1f}", delta=badge_delta(abs_occ, pct_occ))
c2.metric("Bezahlquote (%)", f"{pay_ratio:.1f}")
c3.metric("Ø Neukunden-Wachstum/Monat", f"{growth:.1f}" if growth is not None else "–")
c4.metric("Leads: Empfehlung/Online (%)", f"{share_empf:.1f}/{share_online:.1f}")
card_end()

# ---------- KI-Tipps & Summary ----------
card_start()
st.subheader("💡 KI-Tipps & Zusammenfassung")
recs = data.get("recommendations",[]) or []
if recs:
    for r in recs[:6]: st.markdown(f"- {r}")
else:
    st.caption("Keine Empfehlungen im JSON gefunden.")
msg = data.get("customer_message") or ""
if msg: st.info(msg)
card_end()

# ---------- Footer / System ----------
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ System")
st.sidebar.write(f"Uploads in History: {len(st.session_state.history)}")
if st.button("🔄 Alles zurücksetzen"):
    st.session_state.update({
        "prev_data": DEFAULT_DATA.copy(),
        "data": DEFAULT_DATA.copy(),
        "last_upload": None, "history": [], "file_uploader_key": st.session_state.file_uploader_key+1
    })
    st.rerun()

st.caption(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} · Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}")
