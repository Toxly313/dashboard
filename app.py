import os, uuid, json
from datetime import datetime
import numpy as np, pandas as pd, streamlit as st

from ui_theme import inject_css, header_bar, card_start, card_end, kpi_container_start, kpi_container_end
from components import sidebar_nav, presets_ui, control_panel, kpi_deck, load_prefs, save_prefs
from charts import bar_grouped, bar_stacked, line_chart, area_chart, donut_chart, sma_forecast, heatmap
from insights import build_insights
from data_utils import post_to_n8n, extract_metrics_from_excel, merge_data, delta, kpi_state

# --------------------------------
# Konfiguration
# --------------------------------
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://tandtelectronics51.app.n8n.cloud/webhook/process-business-data"
)

DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Oct 2019","Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"],
    "neukunden_monat": [3000, 600, 4200, 700, 4500, 650],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# --------------------------------
# Init & Sidebar
# --------------------------------
st.set_page_config(page_title="Self-Storage Pro", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
inject_css()

nav = sidebar_nav()
DEFAULT_PREFS = {"layout":"Executive (empfohlen)","chart_style":"Balken (gruppiert)","kpis":["Belegt","Frei","Belegungsgrad","Ø Vertragsdauer"]}
user_prefs = load_prefs(DEFAULT_PREFS)
user_prefs.update({"layout":nav["layout"], "chart_style":nav["chart_style"], "kpis":nav["kpis"]})
loaded = presets_ui(user_prefs)
if loaded:
    user_prefs.update(loaded); save_prefs(user_prefs); st.experimental_rerun()
save_prefs(user_prefs)

# State
if "data" not in st.session_state: st.session_state["data"] = DEFAULT_DATA.copy()
if "prev" not in st.session_state: st.session_state["prev"] = DEFAULT_DATA.copy()
if "history" not in st.session_state: st.session_state["history"] = []

data, prev = st.session_state["data"], st.session_state["prev"]

# --------------------------------
# Header + DRAG & DROP Upload-Karte
# --------------------------------
header_bar("Overview")

card_start("📥 Daten hochladen & analysieren", right_pill="Drag & Drop")
# Große lila Dropzone + echtes file_uploader (Streamlit kann nativ Drag&Drop)
st.markdown("""
<div class="dropzone">
  <h4>Dateien ablegen oder hier klicken</h4>
  <p>Unterstützt: CSV, JSON, Excel (mehrere Dateien möglich). Eine Hauptdatei wird an n8n gesendet; Excel-Dateien werden zusätzlich gemerged.</p>
</div>
""", unsafe_allow_html=True)

files = st.file_uploader(" ", type=["csv","json","xlsx"], accept_multiple_files=True, label_visibility="collapsed", key="main_drop")
c1, c2, c3 = st.columns([0.25,0.25,0.5])
with c1:
    analyze = st.button("🚀 Analysieren", use_container_width=True, type="primary")
with c2:
    reset = st.button("🗑️ Zurücksetzen", use_container_width=True)

if analyze:
    main, excel_merge = None, {}
    if files:
        csv_json = [f for f in files if f.name.lower().endswith((".csv",".json"))]
        xlsx     = [f for f in files if f.name.lower().endswith(".xlsx")]
        main = csv_json[0] if csv_json else files[0]
        for xf in xlsx:
            try:
                import openpyxl
                df = pd.read_excel(xf)
                excel_merge = merge_data(excel_merge, extract_metrics_from_excel(df))
            except Exception as e:
                st.error(f"Excel-Fehler ({xf.name}): {e}")
    if not main:
        st.error("Bitte mindestens eine Hauptdatei auswählen.")
    else:
        st.session_state["prev"] = st.session_state.get("data", DEFAULT_DATA).copy()
        status, text, js = post_to_n8n(N8N_WEBHOOK_URL, (main.name, main.getvalue()), str(uuid.uuid4()))
        base = js.get("metrics", js) if (status==200 and js) else st.session_state["prev"]
        st.session_state["data"] = merge_data(base, excel_merge)
        hist = st.session_state.get("history", [])
        hist.append({"ts": datetime.now().isoformat(), "data": st.session_state["data"], "files":[f.name for f in (files or [])]})
        st.session_state["history"] = hist
        data, prev = st.session_state["data"], st.session_state["prev"]
        st.success("Upload verarbeitet.")

if reset:
    st.session_state["data"] = DEFAULT_DATA.copy()
    st.session_state["prev"] = DEFAULT_DATA.copy()
    st.session_state["history"] = []
    data, prev = st.session_state["data"], st.session_state["prev"]
    st.info("Zurückgesetzt.")
card_end()

# --------------------------------
# Control Panel (Filter)
# --------------------------------
filters = control_panel()

# --------------------------------
# KPI Deck mit Ampel
# --------------------------------
kpi_map = {
    "Belegt": ("belegt", None), "Frei": ("frei", None),
    "Ø Vertragsdauer": ("vertragsdauer_durchschnitt", " mo."),
    "Reminder": ("reminder_automat", None),
    "Belegungsgrad": ("belegungsgrad", " %"),
    "Facebook": ("social_facebook", None), "Google Reviews": ("social_google", None)
}
items=[]
for label in user_prefs["kpis"]:
    key, unit = kpi_map[label]
    cur, prv = data.get(key,0), prev.get(key,0)
    abs_, pct_ = delta(prv, cur)
    dtxt = f"{'+' if abs_>=0 else '−'}{abs(abs_):.0f}" + (f" ({'+' if (pct_ or 0)>=0 else '−'}{abs(pct_):.1f}%)" if pct_ is not None else "")
    value = f"{cur:.1f}{unit}" if (isinstance(cur,float) and unit) else (f"{cur}{unit}" if unit else cur)
    items.append({"label":label,"value":value,"delta":dtxt,"state":kpi_state(key,cur)})
kpi_container_start("good" if any(i["state"]=="good" for i in items) else "neutral")
kpi_deck([{"label":i["label"],"value":i["value"],"delta":i["delta"]} for i in items])
kpi_container_end()

# --------------------------------
# Charts – Top Grid
# --------------------------------
labels = data.get("neukunden_labels", [])
now_vals = data.get("neukunden_monat", [])
prev_vals = prev.get("neukunden_monat", [0]*len(now_vals))
if prev_vals and len(prev_vals)!=len(now_vals):
    prev_vals = prev_vals[:len(now_vals)] if len(prev_vals)>len(now_vals) else prev_vals+[0]*(len(now_vals)-len(prev_vals))

def main_chart(style):
    if style == "Balken (gestapelt)": return bar_stacked(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Linie":              return line_chart(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Fläche":             return area_chart(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Donut":              return donut_chart(data.get("belegungsgrad",0), title="Belegungsgrad")
    return bar_grouped(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))

top_left, top_mid, top_right = st.columns([0.62, 0.19, 0.19])
with top_left:
    card_start(right_pill="Show by months")
    st.plotly_chart(main_chart(user_prefs["chart_style"]), use_container_width=True)
    if labels:
        selected_month = st.selectbox("Details für Monat", options=labels)
        idx = labels.index(selected_month)
        detail_df = pd.DataFrame({"Customer":["A","B","C"], "Month":[selected_month]*3, "Source":["Online","Empfehlung","Vorbeikommen"]})
        st.markdown("**Drill-down: Kundenliste**")
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
        month_subset = dict(data); month_subset["neukunden_monat"] = [now_vals[idx]]
        st.markdown("**Monats-Insights**")
        for r in build_insights(month_subset):
            st.markdown(f"- **{r['title']}** — {r['analysis']}")
    card_end()

with top_mid:
    card_start("Belegungsgrad", alt=True)
    st.plotly_chart(donut_chart(data.get("belegungsgrad",0)), use_container_width=True)
    st.caption("Ziel ≥ 90 %")
    card_end()

with top_right:
    her = data.get("kundenherkunft",{}) or {}
    tot_leads = sum(her.values()) or 1
    online_pct = her.get("Online",0)/tot_leads*100
    card_start("Online-Lead-Anteil")
    st.plotly_chart(donut_chart(online_pct), use_container_width=True)
    st.caption("Online vs. andere Quellen")
    card_end()

# --------------------------------
# Bottom Grid
# --------------------------------
bot_left, bot_mid, bot_right = st.columns([0.45, 0.30, 0.25])
with bot_left:
    card_start("Zeitentwicklung (Neukunden)")
    st.plotly_chart(line_chart(labels, now_vals, None, labels=("Neukunden",), h=260), use_container_width=True)
    with st.expander("Forecast (SMA)"):
        steps = st.slider("Prognose Schritte", 1, 6, 3)
        window = st.selectbox("SMA Fenster", [3,4,6], index=0)
        fc = sma_forecast(now_vals, window=window, steps=steps)
        idx_fc = [f"F+{i+1}" for i in range(len(fc))]
        fc_df = pd.DataFrame({"Periode": labels + idx_fc, "Wert": now_vals + fc})
        st.line_chart(fc_df.set_index("Periode"))
        st.caption("Einfache Basis-Prognose via gleitendem Durchschnitt (SMA).")
    card_end()

with bot_mid:
    card_start("Zahlungsstatus (Tabelle)")
    tbl = pd.DataFrame({
        "Status": ["bezahlt","offen","überfällig"],
        "Anzahl": [data.get("zahlungsstatus",{}).get("bezahlt",0),
                   data.get("zahlungsstatus",{}).get("offen",0),
                   data.get("zahlungsstatus",{}).get("überfällig",0)]
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    with st.expander("Segmente & Kohorten (Demo)"):
        matrix = [[100,72,61,54],[100,70,59,47],[100,68,52,40]]
        st.plotly_chart(heatmap(matrix, ["M1","M2","M3","M4"], ["Cohort Jan","Feb","Mär"]), use_container_width=True)
    card_end()

with bot_right:
    card_start("Kurz-Zusammenfassung")
    msg = data.get("customer_message") or "Noch keine kundenspezifische Zusammenfassung vorhanden."
    st.write(msg)
    with st.expander("Preis-/Elastizitäts-Sandbox"):
        price_delta = st.slider("Preisänderung (%)", -15, 15, 5)
        elast = st.slider("Nachfrage-Elastizität (−0.2 … −1.5)", -150, -20, -60) / 100
        current_demand = np.mean(now_vals[-min(3,len(now_vals)):]) if now_vals else 0
        demand_new = current_demand * (1 + elast * (price_delta/100))
        st.metric("Erwartete Nachfrage", f"{demand_new:.0f}", f"{price_delta:+d}% Preis, Elastizität {elast:.2f}")
        st.caption("ΔNachfrage ≈ Elastizität × ΔPreis.")
    card_end()

# --------------------------------
# KI-Empfehlungen + Exporte
# --------------------------------
card_start("🔎 KI-Empfehlungen & Analysen", right_pill="Automatisch")
ins = build_insights(data)
if not ins:
    st.caption("Keine besonderen Auffälligkeiten – solide Performance.")
else:
    for i, rec in enumerate(ins, 1):
        st.markdown(f"**{i}. {rec['title']}** — _Impact: {rec['impact']}_")
        st.markdown(f"{rec['analysis']}")
        st.markdown("**Empfohlene Maßnahmen:**")
        for a in rec["actions"]:
            st.markdown(f"- {a}")
        st.markdown("---")
card_end()

with st.expander("💬 Frag dein Dashboard"):
    q = st.text_input("Beispiel: zeige kundenherkunft q2 vs q1 / belegung anzeigen")
    if q:
        ql = q.lower()
        if "kundenherkunft" in ql:
            her = data.get("kundenherkunft",{}) or {}
            tot = sum(her.values()) or 1
            pct = her.get("Online",0)/tot*100
            st.plotly_chart(donut_chart(pct, title="Online-Anteil"), use_container_width=True)
            st.info("Interpretation: Anteil Online an allen Leads.")
        elif "belegung" in ql or "auslastung" in ql:
            st.plotly_chart(donut_chart(data.get("belegungsgrad",0), title="Belegungsgrad"), use_container_width=True)
        else:
            st.write("Nicht eindeutig erkannt – Beispiele: 'belegung', 'kundenherkunft'.")

st.markdown("### Exporte")
cur_df = pd.DataFrame([data])
st.download_button("⬇️ CSV (aktueller Snapshot)", data=cur_df.to_csv(index=False).encode("utf-8"),
                   file_name=f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
st.download_button("⬇️ JSON", data=json.dumps(data, ensure_ascii=False, indent=2),
                   file_name="snapshot.json", mime="application/json")

st.caption(f"Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')} • Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}")
