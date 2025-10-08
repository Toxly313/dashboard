import os, uuid, json
from datetime import datetime
import numpy as np, pandas as pd, streamlit as st

from ui_theme import inject_css, header_bar, card_start, card_end, kpi_container_start, kpi_container_end
from components import sidebar_nav, presets_panel_right, control_panel, kpi_deck, load_prefs, save_prefs
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
# Init
# --------------------------------
st.set_page_config(page_title="Self-Storage Pro", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
inject_css()

# State
if "data" not in st.session_state: st.session_state["data"] = DEFAULT_DATA.copy()
if "prev" not in st.session_state: st.session_state["prev"] = DEFAULT_DATA.copy()
if "history" not in st.session_state: st.session_state["history"] = []
if "prefs" not in st.session_state:
    st.session_state["prefs"] = {"layout":"Executive (empfohlen)","chart_style":"Balken (gruppiert)",
                                 "kpis":["Belegt","Frei","Belegungsgrad","Ø Vertragsdauer"]}

# Sidebar: Navigation + Builder (nur Auswahl)
nav = sidebar_nav(current_prefs=st.session_state["prefs"])
st.session_state["prefs"].update({"layout":nav["layout"], "chart_style":nav["chart_style"], "kpis":nav["kpis"]})
save_prefs(st.session_state["prefs"])

# Header
header_bar(nav["section"])

# Rechter Rand: Presets – ausklappbar (auf jeder Seite sichtbar)
presets_panel_right(st.session_state["prefs"])

# ----------------- gemeinsame Helfer -----------------
def render_kpis(data, prev, selected_kpis):
    kpi_map = {
        "Belegt": ("belegt", None), "Frei": ("frei", None),
        "Ø Vertragsdauer": ("vertragsdauer_durchschnitt", " mo."),
        "Reminder": ("reminder_automat", None),
        "Belegungsgrad": ("belegungsgrad", " %"),
        "Facebook": ("social_facebook", None), "Google Reviews": ("social_google", None)
    }
    items=[]
    for label in selected_kpis:
        key, unit = kpi_map[label]
        cur, prv = data.get(key,0), prev.get(key,0)
        abs_, pct_ = delta(prv, cur)
        dtxt = f"{'+' if abs_>=0 else '−'}{abs(abs_):.0f}" + (f" ({'+' if (pct_ or 0)>=0 else '−'}{abs(pct_):.1f}%)" if pct_ is not None else "")
        value = f"{cur:.1f}{unit}" if (isinstance(cur,float) and unit) else (f"{cur}{unit}" if unit else cur)
        items.append({"label":label,"value":value,"delta":dtxt,"state":kpi_state(key,cur)})
    kpi_container_start("good" if any(i["state"]=="good" for i in items) else "neutral")
    kpi_deck([{"label":i["label"],"value":i["value"],"delta":i["delta"]} for i in items])
    kpi_container_end()

def main_chart(style, labels, prev_vals, now_vals, belegungsgrad):
    if style == "Balken (gestapelt)": return bar_stacked(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Linie":              return line_chart(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Fläche":             return area_chart(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))
    if style == "Donut":              return donut_chart(belegungsgrad, title="Belegungsgrad")
    return bar_grouped(labels, prev_vals, now_vals, labels=("Vorher","Nachher"))

def money_saver_tips(data):
    tips = []
    pay = data.get("zahlungsstatus",{}) or {}
    paid, open_, over = pay.get("bezahlt",0), pay.get("offen",0), pay.get("überfällig",0)
    occ = data.get("belegungsgrad",0)
    vd = data.get("vertragsdauer_durchschnitt",0)
    if over+open_ > 0: tips.append("💳 Mahnwesen automatisieren (E-Mail+SMS am Fälligkeitstag, nach 7 Tagen Stufe 1).")
    if paid and (paid/(paid+open_+over)) < .9: tips.append("🧾 2% Skonto bei Zahlung in 7 Tagen – schneller Cashflow.")
    if occ < 85: tips.append("🎯 Kurzfristige Neukunden-Aktion −10% (Mindestlaufzeit 3 Monate).")
    if vd < 6: tips.append("🔁 Retention-Angebot 4 Wochen vor Laufzeitende (Upgrade mit Rabatt im 1. Monat).")
    if not tips: tips.append("✅ Aktuell keine offensichtlichen Einsparpotenziale.")
    return tips

# ----------------- Seiten-Renderer -----------------
def page_overview():
    data, prev = st.session_state["data"], st.session_state["prev"]
    labels = data.get("neukunden_labels", [])
    now_vals = data.get("neukunden_monat", [])
    prev_vals = prev.get("neukunden_monat", [0]*len(now_vals))
    if len(prev_vals)!=len(now_vals):
        prev_vals = prev_vals[:len(now_vals)] if len(prev_vals)>len(now_vals) else prev_vals+[0]*(len(now_vals)-len(prev_vals))

    # Upload-Karte
    card_start("📥 Daten hochladen & analysieren", right_pill="Drag & Drop")
    st.markdown("""
    <div class="dropzone">
      <h4>Dateien ablegen oder klicken</h4>
      <p>CSV, JSON, Excel • Hauptdatei → n8n • Excel wird zusätzlich gemerged</p>
    </div>
    """, unsafe_allow_html=True)
    files = st.file_uploader(" ", type=["csv","json","xlsx"], accept_multiple_files=True, label_visibility="collapsed", key="drop_overview")
    c1, c2, c3 = st.columns([0.25,0.25,0.5])
    with c1: analyze = st.button("🚀 Analysieren", use_container_width=True, type="primary", key="analyze_overview")
    with c2: reset = st.button("🗑️ Zurücksetzen", use_container_width=True, key="reset_overview")
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
            st.success("Upload verarbeitet.")
    if reset:
        st.session_state["data"] = DEFAULT_DATA.copy()
        st.session_state["prev"] = DEFAULT_DATA.copy()
        st.session_state["history"] = []
        st.info("Zurückgesetzt.")
    card_end()

    # KPIs
    render_kpis(data, prev, st.session_state["prefs"]["kpis"])

    # Charts-Grid
    top_left, top_mid, top_right = st.columns([0.62, 0.19, 0.19])
    with top_left:
        card_start(right_pill="Show by months")
        st.plotly_chart(main_chart(st.session_state["prefs"]["chart_style"], labels, prev_vals, now_vals, data.get("belegungsgrad",0)), use_container_width=True)
        card_end()
    with top_mid:
        card_start("Belegungsgrad")
        st.plotly_chart(donut_chart(data.get("belegungsgrad",0)), use_container_width=True)
        st.caption("Ziel ≥ 90 %")
        card_end()
    with top_right:
        her = data.get("kundenherkunft",{}) or {}
        tot_leads = sum(her.values()) or 1
        online_pct = her.get("Online",0)/tot_leads*100
        card_start("Online-Lead-Anteil")
        st.plotly_chart(donut_chart(online_pct), use_container_width=True)
        card_end()

    # Tipps & Sparen
    card_start("🔎 KI-Empfehlungen & Spar-Tipps", right_pill="Automatisch")
    for i, rec in enumerate(build_insights(data), 1):
        st.markdown(f"**{i}. {rec['title']}** — _Impact: {rec['impact']}_")
        st.markdown(rec["analysis"])
        st.markdown("**Maßnahmen:**")
        for a in rec["actions"]: st.markdown(f"- {a}")
        st.markdown("---")
    st.markdown("**Sparen:**")
    for t in money_saver_tips(data): st.markdown(f"- {t}")
    card_end()

def page_customers():
    data, prev = st.session_state["data"], st.session_state["prev"]
    render_kpis(data, prev, ["Belegt","Frei","Ø Vertragsdauer","Belegungsgrad"])
    labels = data.get("neukunden_labels", [])
    now_vals = data.get("neukunden_monat", [])
    prev_vals = prev.get("neukunden_monat", [0]*len(now_vals))
    card_start("Neukunden (Vorher/Nachher)")
    st.plotly_chart(bar_grouped(labels, prev_vals, now_vals, labels=("Vorher","Nachher")), use_container_width=True)
    card_end()
    card_start("Kundenherkunft")
    her = data.get("kundenherkunft",{}) or {}
    st.dataframe(pd.DataFrame({"Kanal":list(her.keys()), "Anzahl":list(her.values())}), use_container_width=True, hide_index=True)
    card_end()
    card_start("Empfehlungen")
    st.markdown("- 🤝 Referral-Programm: 25 € Guthaben / geworbenem Neukunden.")
    st.markdown("- 🌐 Google Business: 10 neue Fotos, 5 frische Bewertungen – mehr Online-Leads.")
    st.markdown("- 📩 CRM-Nurturing: 3-Stufen E-Mail bei nicht abgeschlossenen Anfragen.")
    card_end()

def page_orders():
    data, prev = st.session_state["data"], st.session_state["prev"]
    render_kpis(data, prev, ["Reminder","Belegungsgrad","Ø Vertragsdauer"])
    card_start("Zahlungsstatus")
    pay_keys = ["bezahlt","offen","überfällig"]
    cur  = [data.get("zahlungsstatus",{}).get(k,0) for k in pay_keys]
    prv  = [prev.get("zahlungsstatus",{}).get(k,0) for k in pay_keys]
    st.plotly_chart(bar_grouped([k.title() for k in pay_keys], prv, cur, labels=("Vorher","Nachher")), use_container_width=True)
    card_end()
    card_start("Prozess-Tipps")
    st.markdown("- 💳 Automatisches Mahnwesen (E-Mail+SMS) – Ziel < 5 offen/überfällig.")
    st.markdown("- 📅 Reminder-Automat feinjustieren (Zeitpunkt, Ton, Kanal).")
    st.markdown("- 🧾 Skonto 2% bei Zahlung in 7 Tagen testen.")
    card_end()

def page_capacity():
    data, prev = st.session_state["data"], st.session_state["prev"]
    render_kpis(data, prev, ["Belegt","Frei","Belegungsgrad"])
    belegt_cur, belegt_prev = data.get("belegt",0), prev.get("belegt",0)
    frei_cur, frei_prev     = data.get("frei",0), prev.get("frei",0)
    card_start("Auslastung")
    st.plotly_chart(bar_grouped(["Belegt","Frei"], [belegt_prev,frei_prev], [belegt_cur,frei_cur], labels=("Vorher","Nachher")), use_container_width=True)
    st.plotly_chart(donut_chart(data.get("belegungsgrad",0)), use_container_width=True)
    card_end()
    card_start("Steuerungs-Ideen")
    st.markdown("- < 85%: 2-Wochen-Aktion −10 % für Neukunden (LZ ≥ 3 Monate).")
    st.markdown("- ≥ 95%: Preise kleiner Einheiten +3–5 %; Warteliste.")
    st.markdown("- Bundles: Vorauszahlung + 1. Monat gratis (Auslastungsschub).")
    card_end()

def page_social():
    data, prev = st.session_state["data"], st.session_state["prev"]
    render_kpis(data, prev, ["Facebook","Google Reviews","Belegungsgrad"])
    sf, sg = data.get("social_facebook",0), data.get("social_google",0)
    card_start("Leads nach Kanal")
    st.plotly_chart(bar_grouped(["Facebook","Google"], [0,0], [sf, sg], labels=("Baseline","Aktuell")), use_container_width=True)
    card_end()
    card_start("Kanal-Tipps")
    if sg < 60: st.markdown("🔎 **Google Ads**: 2 Keywords mit Kaufabsicht testen („Selfstorage [Stadt] mieten“).")
    if sf > 200 and (data.get("belegungsgrad",0) < 90): st.markdown("🎯 **FB-Targeting** schärfen: Umzüge/Studierende, Click-to-Call.")
    st.markdown("📣 **Bewertungs-Boost**: QR-Code, Dankes-Mail, Gewinnspiel (monatlich).")
    card_end()

def page_finance():
    data, prev = st.session_state["data"], st.session_state["prev"]
    render_kpis(data, prev, ["Belegungsgrad","Ø Vertragsdauer","Reminder"])
    pay = data.get("zahlungsstatus",{}) or {}
    card_start("Rechnungen (Tabelle)")
    st.dataframe(pd.DataFrame({"Status":["bezahlt","offen","überfällig"], "Anzahl":[pay.get("bezahlt",0), pay.get("offen",0), pay.get("überfällig",0)]}),
                 use_container_width=True, hide_index=True)
    card_end()
    card_start("Sparen & Ertrag")
    for t in money_saver_tips(data): st.markdown(f"- {t}")
    st.markdown("- 📈 Dynamische Preisanpassung quartalsweise anhand Auslastung.")
    card_end()

def page_settings():
    data = st.session_state["data"]
    card_start("Export & Debug")
    cur_df = pd.DataFrame([data])
    st.download_button("⬇️ CSV (aktueller Snapshot)", data=cur_df.to_csv(index=False).encode("utf-8"),
                       file_name=f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
    st.download_button("⬇️ JSON", data=json.dumps(data, ensure_ascii=False, indent=2),
                       file_name="snapshot.json", mime="application/json")
    st.caption(f"Uploads im Verlauf: {len(st.session_state['history'])}")
    card_end()

# ----------------- Router -----------------
page_map = {
    "Overview": page_overview,
    "Customers": page_customers,
    "Open Orders": page_orders,
    "Capacity": page_capacity,
    "Social Media": page_social,
    "Finance": page_finance,
    "Settings": page_settings,
}
page_map.get(nav["section"], page_overview)()
