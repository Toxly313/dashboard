import streamlit as st
import requests
import uuid
import os
import json
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

# ---------------------------------
# Konfiguration
# ---------------------------------
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://tundtelectronics.app.n8n.cloud/webhook/process-business-data"
)

DEFAULT_DATA = {
    "belegt": 15,
    "frei": 5,
    "vertragsdauer_durchschnitt": 6.5,
    "reminder_automat": 12,
    "social_facebook": 250,
    "social_google": 45,
    "belegungsgrad": 75,
    "kundenherkunft": {"Online": 8, "Empfehlung": 5, "Vorbeikommen": 7},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [3, 5, 2, 4, 6, 5],
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1},
    "recommendations": [],
    "customer_message": ""
}

# Regeln: höher = besser (True) / niedriger = besser (False) / neutral (None)
BETTER_RULES = {
    "belegt": True,
    "frei": False,
    "vertragsdauer_durchschnitt": True,
    "reminder_automat": None,
    "social_facebook": True,
    "social_google": True,
    "belegungsgrad": True
}

# ---------------------------------
# Setup
# ---------------------------------
st.set_page_config(page_title="Self-Storage Dashboard", layout="wide")
st.title("📦 Shurgard Self-Storage Business Dashboard")
st.caption("Nalepastraße 162 – Lagerräume mit Business-Center  \nwww.schimmel-automobile.de")

# Sidebar / Debug
st.sidebar.title("🔧 Optionen")
DEBUG_MODE = st.sidebar.checkbox("Debug-Modus aktivieren", value=True)
SHOW_RAW_DATA = st.sidebar.checkbox("Rohdaten anzeigen (KI & Excel)", value=False)

# Session init
if "data" not in st.session_state:
    st.session_state.data = DEFAULT_DATA.copy()
if "prev_data" not in st.session_state:
    st.session_state.prev_data = DEFAULT_DATA.copy()
if "last_upload" not in st.session_state:
    st.session_state.last_upload = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "history" not in st.session_state:
    st.session_state.history = []
if "file_uploader_key" not in st.session_state:
    st.session_state.file_uploader_key = 0

# ---------------------------------
# Helper Functions
# ---------------------------------
def delta(a, b):
    """Delta b - a (absolut, prozentual)"""
    try:
        a = float(a); b = float(b)
    except Exception:
        return 0.0, None
    abs_ = b - a
    pct_ = None if a == 0 else (b - a) / a * 100.0
    return abs_, pct_

def color_for_change(key, a, b):
    """Farbe je nach Regel: grün=Verbesserung, rot=Verschlechterung, grau=gleich."""
    rule = BETTER_RULES.get(key, None)
    try:
        a = float(a); b = float(b)
    except Exception:
        return "#A9A9A9"
    if b == a: return "#A9A9A9"
    if rule is True:  # mehr ist besser
        return "#2ca02c" if b > a else "#d62728"
    if rule is False: # weniger ist besser
        return "#2ca02c" if b < a else "#d62728"
    return "#2ca02c" if b > a else "#d62728"

def badge_delta(abs_, pct_):
    if pct_ is None:
        return f"{abs_:+.0f}"
    sign = "+" if abs_ >= 0 else "−"
    return f"{sign}{abs(abs_):.0f}  ({sign}{abs(pct_):.1f}%)"

def extract_metrics_from_excel(df: pd.DataFrame) -> dict:
    """Versucht, bekannte Spaltennamen in Excel auf deine Struktur zu mappen."""
    colmap = {
        "belegt": "belegt",
        "frei": "frei",
        "vertragsdauer_durchschnitt": "vertragsdauer_durchschnitt",
        "reminder_automat": "reminder_automat",
        "social_facebook": "social_facebook",
        "social_google": "social_google",
        "belegungsgrad": "belegungsgrad",
        "kundenherkunft_online": ("kundenherkunft", "Online"),
        "kundenherkunft_empfehlung": ("kundenherkunft", "Empfehlung"),
        "kundenherkunft_vorbeikommen": ("kundenherkunft", "Vorbeikommen"),
        "zahlungsstatus_bezahlt": ("zahlungsstatus", "bezahlt"),
        "zahlungsstatus_offen": ("zahlungsstatus", "offen"),
        "zahlungsstatus_überfällig": ("zahlungsstatus", "überfällig"),
    }
    out = {"kundenherkunft": {}, "zahlungsstatus": {}}
    if len(df) == 0:
        return {}
    row = df.iloc[0]
    for c in df.columns:
        key = c.strip().lower().replace(" ", "_")
        if key in colmap:
            target = colmap[key]
            try:
                val = float(row[c])
            except Exception:
                continue
            if isinstance(target, tuple):  # nested
                parent, child = target
                out[parent][child] = val
            else:
                out[target] = val
    return out

def merge_data(base: dict, addon: dict) -> dict:
    """Mergt addon (z. B. Excel) in base (z. B. KI), ohne Pflichtfelder zu zerstören."""
    merged = json.loads(json.dumps(base))  # deep copy
    for k, v in (addon or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged

def post_to_n8n(file_tuple, session_id: str):
    """Sendet Datei an n8n (multipart) und gibt (status_code, text, json_obj|None) zurück."""
    response = requests.post(
        N8N_WEBHOOK_URL,
        files={"file": file_tuple},
        headers={"X-Session-ID": session_id},
        timeout=60
    )
    try:
        data = response.json()
    except Exception:
        data = None
    return response.status_code, response.text, data

def upload_and_process(main_file, excel_metrics):
    """Verarbeitet Datei(en) und sendet Hauptdatei an n8n, merged Excel-Metriken lokal."""
    if main_file is None:
        st.error("❌ Bitte wähle zuerst mindestens eine Datei aus.")
        return False

    st.session_state.processing = True
    st.session_state.prev_data = st.session_state.data.copy()
    st.session_state.last_upload = main_file

    with st.spinner("🤖 KI verarbeitet Daten datenschutzkonform..."):
        try:
            session_id = str(uuid.uuid4())
            file_data = main_file.getvalue()

            if DEBUG_MODE:
                st.sidebar.info("🔍 Debug-Informationen")
                st.sidebar.write(f"📁 Hauptdatei: {main_file.name}")
                st.sidebar.write(f"📊 Größe: {main_file.size} bytes")
                st.sidebar.write(f"🌐 n8n URL: {N8N_WEBHOOK_URL}")
                st.sidebar.write(f"🆔 Session ID: {session_id}")

            status, text, data_json = post_to_n8n((main_file.name, file_data))
            if DEBUG_MODE:
                st.sidebar.write(f"📡 Status: {status}")
                st.sidebar.write("📨 Rohantwort:")
                st.sidebar.code(text[:1000] if text else "LEER", language="text")

            if status == 200 and data_json:
                # Wenn dein n8n-Respond nur die finalen Felder liefert (empfohlen)
                # kann data_json bereits {metrics, recommendations, customer_message} sein
                response_data = data_json
                # Support: falls n8n direkt metrics auf Root schreibt
                if "metrics" in response_data:
                    base = response_data["metrics"]
                    merged = merge_data(base, excel_metrics or {})
                    response_data["metrics"] = merged
                    st.session_state.data = merged
                else:
                    merged = merge_data(response_data, excel_metrics or {})
                    st.session_state.data = merged

                st.session_state.processing = False
                st.session_state.history.append({"ts": datetime.now().isoformat(), "data": st.session_state.data})
                st.session_state.file_uploader_key += 1

                st.success("✅ Daten erfolgreich verarbeitet!")
                if isinstance(response_data, dict) and response_data.get("ki_analyse_erfolgreich"):
                    st.info("🤖 KI-Analyse erfolgreich")
                elif isinstance(response_data, dict) and response_data.get("fallback_used"):
                    st.warning("⚠️ Fallback-Daten verwendet")

                if DEBUG_MODE:
                    st.sidebar.success("✅ JSON erfolgreich geparst")
                    st.sidebar.json(response_data, expanded=False)

                return True
            else:
                st.error(f"❌ Fehler von n8n: Status {status}")
                if DEBUG_MODE:
                    st.sidebar.error(f"n8n Fehlerantwort: {text}")
                st.session_state.data = st.session_state.prev_data.copy()
                st.session_state.processing = False
                return False

        except requests.exceptions.Timeout:
            st.error("❌ Timeout: n8n antwortet nicht (60s)")
            if DEBUG_MODE:
                st.sidebar.error("Timeout bei n8n Anfrage")
            st.session_state.data = st.session_state.prev_data.copy()
            st.session_state.processing = False
            return False
        except requests.exceptions.ConnectionError:
            st.error("❌ Verbindungsfehler: n8n ist nicht erreichbar")
            if DEBUG_MODE:
                st.sidebar.error("n8n URL nicht erreichbar")
            st.session_state.data = st.session_state.prev_data.copy()
            st.session_state.processing = False
            return False
        except Exception as e:
            st.error(f"❌ Systemfehler: {str(e)}")
            if DEBUG_MODE:
                st.sidebar.exception(e)
            st.session_state.data = st.session_state.prev_data.copy()
            st.session_state.processing = False
            return False

# ---------------------------------
# EIN Upload-Feld (optional mehrere Dateien)
# ---------------------------------
st.subheader("📥 Datenzufuhr")
uploaded_files = st.file_uploader(
    "Dateien per Drag & Drop hinzufügen (CSV/JSON/Excel) – eine Datei wird an n8n gesendet, Excel-Dateien werden zusätzlich gemerged.",
    type=["csv", "json", "xlsx"],
    accept_multiple_files=True,
    key=f"ki_upl_{st.session_state.file_uploader_key}"
)

# Auswahl der Hauptdatei + optional Excel-Merge
main_file = None
excel_metrics_total = {}

if uploaded_files:
    # Wähle als Hauptdatei: priorisiere CSV/JSON (typisch Rohdaten für KI/n8n)
    csv_json = [f for f in uploaded_files if f.name.lower().endswith((".csv", ".json"))]
    xlsx = [f for f in uploaded_files if f.name.lower().endswith(".xlsx")]

    # Hauptdatei-Regel
    main_file = csv_json[0] if csv_json else uploaded_files[0]

    # Excel zusammenführen (alle xlsx werden gemerged)
    for xf in xlsx:
        try:
            try:
                import openpyxl  # für Excel-Parsing
            except ImportError:
                st.error("""
                **❌ Fehlende Abhängigkeit: openpyxl**
                Bitte `openpyxl` installieren:
                ```bash
                pip install openpyxl
                ```
                """)
                st.stop()
            df_x = pd.read_excel(xf)
            if SHOW_RAW_DATA:
                st.markdown(f"**📋 Excel-Rohdaten – {xf.name}**")
                st.dataframe(df_x, use_container_width=True)
            metrics = extract_metrics_from_excel(df_x)
            excel_metrics_total = merge_data(excel_metrics_total, metrics)
        except Exception as e:
            st.error(f"❌ Excel konnte nicht verarbeitet werden ({xf.name}): {str(e)}")

# Upload Button
if st.button("📤 Datei(en) hochladen und analysieren", type="primary"):
    upload_and_process(main_file, excel_metrics_total)

if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet...")

data = st.session_state.data
prev = st.session_state.prev_data

# ---------------------------------
# Tabs / Reiter
# ---------------------------------
tabs = st.tabs([
    "🏠 Start", "📚 Allgemein", "💶 Finanzen",
    "👥 Mitarbeiter", "📦 Lager & Auslastung",
    "📣 Social Media", "❓ Erklärungen",
    "⚠️ Risiken & Einsparpotenziale"
])

# ----- Gemeinsame Kennzahlen Hilfen -----
def kpi_row():
    st.subheader("📊 KPIs – Veränderungen seit letztem Upload")
    kpi_keys = [
        "belegt","frei","vertragsdauer_durchschnitt","reminder_automat",
        "social_facebook","social_google","belegungsgrad"
    ]
    cols = st.columns(len(kpi_keys))
    for i, k in enumerate(kpi_keys):
        cur = data.get(k, 0)
        prv = prev.get(k, 0)
        abs_, pct_ = delta(prv, cur)
        cols[i].metric(
            label=k.replace("_"," ").title(),
            value=cur if isinstance(cur,(int,float)) else str(cur),
            delta=badge_delta(abs_, pct_)
        )

def occupancy_numbers():
    total_cur = (data.get("belegt",0) or 0) + (data.get("frei",0) or 0)
    occ_calc = (data.get("belegt",0)/total_cur*100) if total_cur else data.get("belegungsgrad",0)
    total_prev = (prev.get("belegt",0) or 0) + (prev.get("frei",0) or 0)
    occ_prev_calc = (prev.get("belegt",0)/total_prev*100) if total_prev else prev.get("belegungsgrad",0)
    abs_occ, pct_occ = delta(occ_prev_calc, occ_calc)
    return total_cur, occ_calc, occ_prev_calc, abs_occ, pct_occ

def payment_ratio():
    paid = data.get("zahlungsstatus",{}).get("bezahlt",0)
    open_ = data.get("zahlungsstatus",{}).get("offen",0)
    overd = data.get("zahlungsstatus",{}).get("überfällig",0)
    tot_invoices = paid + open_ + overd
    pay_ratio = (paid / tot_invoices * 100) if tot_invoices else 0
    return paid, open_, overd, tot_invoices, pay_ratio

def lead_shares():
    her = data.get("kundenherkunft",{}) or {}
    total_leads = sum(her.values()) if her else 0
    share_empf = (her.get("Empfehlung",0) / total_leads * 100) if total_leads else 0
    share_online = (her.get("Online",0) / total_leads * 100) if total_leads else 0
    return total_leads, share_empf, share_online

def plot_occ_pay_sources():
    # 1) Auslastung
    belegt_cur = data.get("belegt", 0); belegt_prev = prev.get("belegt", 0)
    frei_cur   = data.get("frei", 0);   frei_prev   = prev.get("frei", 0)
    x_labels = ["Belegt","Frei"]
    cur_vals = [belegt_cur, frei_cur]
    prev_vals = [belegt_prev, frei_prev]
    bar_colors = [
        color_for_change("belegt", belegt_prev, belegt_cur),
        color_for_change("frei",   frei_prev,   frei_cur)
    ]
    fig_occ = go.Figure()
    fig_occ.add_bar(name="Vorher", x=x_labels, y=prev_vals, marker_color="#B0B0B0", opacity=0.5)
    fig_occ.add_bar(name="Nachher", x=x_labels, y=cur_vals, marker_color=bar_colors)
    for idx, lbl in enumerate(x_labels):
        abs_, pct_ = delta(prev_vals[idx], cur_vals[idx])
        fig_occ.add_annotation(x=lbl, y=max(prev_vals[idx], cur_vals[idx]), text=badge_delta(abs_, pct_), showarrow=False, yshift=10)
    fig_occ.update_layout(title="Auslastung: Belegt vs. Frei", barmode="group", height=320, margin=dict(t=40,b=40))

    # 2) Zahlungsstatus
    pay_keys = ["bezahlt","offen","überfällig"]
    pay_prev = [prev.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
    pay_cur  = [data.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
    pay_colors = [color_for_change(k, pay_prev[i], pay_cur[i]) for i,k in enumerate(pay_keys)]
    pay_texts  = [badge_delta(*delta(pay_prev[i], pay_cur[i])) for i in range(len(pay_keys))]
    fig_pay = go.Figure()
    fig_pay.add_bar(name="Vorher", x=[k.title() for k in pay_keys], y=pay_prev, marker_color="#B0B0B0", opacity=0.5)
    fig_pay.add_bar(name="Nachher", x=[k.title() for k in pay_keys], y=pay_cur, marker_color=pay_colors, text=pay_texts, textposition="outside")
    fig_pay.update_layout(title="Zahlungsstatus (Δ farblich)", yaxis_title="Anzahl Rechnungen", barmode="group", height=320, margin=dict(t=40,b=40))

    # 3) Kundenherkunft
    her_prev = prev.get("kundenherkunft", {}) or {}
    her_cur  = data.get("kundenherkunft", {}) or {}
    channels = sorted(set(her_prev.keys()) | set(her_cur.keys()))
    prev_h = [her_prev.get(k, 0) for k in channels]
    cur_h  = [her_cur.get(k, 0) for k in channels]
    her_colors = [color_for_change("kundenherkunft", prev_h[i], cur_h[i]) for i in range(len(channels))]
    her_texts  = [badge_delta(*delta(prev_h[i], cur_h[i])) for i in range(len(channels))]
    fig_src = go.Figure()
    fig_src.add_bar(name="Vorher", x=channels, y=prev_h, marker_color="#B0B0B0", opacity=0.5)
    fig_src.add_bar(name="Nachher", x=channels, y=cur_h, marker_color=her_colors, text=her_texts, textposition="outside")
    fig_src.update_layout(title="Kundenherkunft (Δ farblich)", barmode="group", height=340, margin=dict(t=40,b=40))

    return fig_occ, fig_pay, fig_src

# ----- Tab: Start -----
with tabs[0]:
    kpi_row()

    # Δ-Heatmap
    with st.expander("🧭 Δ-Heatmap (Skalare)", expanded=False):
        kpi_keys = [
            "belegt","frei","vertragsdauer_durchschnitt","reminder_automat",
            "social_facebook","social_google","belegungsgrad"
        ]
        labels = []; vals = []
        for k in kpi_keys:
            cur = data.get(k, 0); prv = prev.get(k, 0)
            _, pct_ = delta(prv, cur)
            labels.append(k); vals.append(pct_ if pct_ is not None else 0.0)
        fig_hm = go.Figure(data=go.Heatmap(z=[vals], x=labels, y=["Δ %"], colorscale="RdYlGn", zmid=0))
        fig_hm.update_layout(height=150, margin=dict(l=20,r=20,t=10,b=10))
        st.plotly_chart(fig_hm, use_container_width=True, key="hm_start")

    # Drei Kernplots
    fig_occ, fig_pay, fig_src = plot_occ_pay_sources()
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(fig_occ, use_container_width=True, key="occ_start")
        st.plotly_chart(fig_src, use_container_width=True, key="src_start")
    with col_r:
        st.plotly_chart(fig_pay, use_container_width=True, key="pay_start")

    # Kennzahlen unten
    total_cur, occ_calc, occ_prev_calc, abs_occ, pct_occ = occupancy_numbers()
    paid, open_, overd, tot_invoices, pay_ratio = payment_ratio()
    total_leads, share_empf, share_online = lead_shares()

    scol1, scol2, scol3, scol4 = st.columns(4)
    scol1.metric("Belegungsgrad (berechnet) %", f"{occ_calc:.1f}", delta=badge_delta(abs_occ, pct_occ))
    scol2.metric("Zahlungsquote (bezahlt %)", f"{pay_ratio:.1f}")
    try:
        vals = data.get("neukunden_monat", []) or []
        growth = float(np.mean(np.diff(vals))) if len(vals) >= 2 else None
    except Exception:
        growth = None
    scol3.metric("Ø Neukunden-Wachstum/Monat", f"{growth:.1f}" if growth is not None else "–")
    scol4.metric("Leads: Empfehlung vs. Online (%)", f"{share_empf:.1f} / {share_online:.1f}")

# ----- Tab: Allgemein -----
with tabs[1]:
    st.subheader("Überblick & Hinweise")
    st.markdown("""
    - **Reminder-Automat**: Zielwert anpassen, wenn offene/überfällige Rechnungen > 0.
    - **Vertragsdauer**: < 6 Monate → *Churn-Risiko hoch* → Proaktiv verlängern.
    - **Lead-Mix**: Online < Empfehlung → Google Business & Bewertungen pushen.
    """)
    # Zusammenfassung aus KI
    msg = st.session_state.get("customer_message") or data.get("customer_message") or ""
    if msg:
        st.info(msg)
    else:
        st.caption("Keine personalisierte Zusammenfassung vorhanden.")

# ----- Tab: Finanzen -----
with tabs[2]:
    st.subheader("Rechnungen, Einnahmen, Ausgaben (Schnell-Sicht)")
    paid, open_, overd, tot_invoices, pay_ratio = payment_ratio()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rechnungen – bezahlt", paid)
    c2.metric("Rechnungen – offen", open_)
    c3.metric("Rechnungen – überfällig", overd)
    c4.metric("Bezahlquote (%)", f"{pay_ratio:.1f}")

    # Spar-Tipps (regelbasiert)
    tips = []
    if overd + open_ > 0:
        tips.append("💳 **Mahnwesen automatisieren:** E-Mail+SMS am Fälligkeitstag, nach 7 Tagen Mahnstufe 1.")
    if pay_ratio < 90:
        tips.append("📈 **Skonto testen:** 2% bei Zahlung innerhalb 7 Tage, um Cashflow zu verbessern.")
    if data.get("vertragsdauer_durchschnitt", 12) < 9:
        tips.append("🔁 **Retention-Paket:** Verlängerungsangebote 4 Wochen vor Ende (Upgrade in größere Einheit mit Rabatt im 1. Monat).")
    if data.get("social_facebook", 0) > 200 and ((data.get('belegungsgrad',0) or 0) < 90):
        tips.append("📣 **Ads effizienter:** Zielgruppe enger, Landingpage mit Sofort-Preisabfrage → weniger Streuverlust.")
    if not tips:
        tips.append("✅ Aktuell keine kritischen Finanz-Leaks erkennbar.")
    st.markdown("**Einspar-/Ertrags-Tipps:**")
    for t in tips:
        st.markdown(f"- {t}")

# ----- Tab: Mitarbeiter -----
with tabs[3]:
    st.subheader("Team & Prozesse")
    st.caption("Hinweis: Konkrete Mitarbeiterdaten werden erst angezeigt, wenn sie in der Excel/JSON vorhanden sind.")
    # Platzhalter-KPIs (kannst du später aus Daten füttern)
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Tickets pro Woche", "–")
    mc2.metric("Ø Antwortzeit (Std.)", "–")
    mc3.metric("No-Shows / Monat", "–")
    st.markdown("""
    **Prozess-Tipps:**
    - 📅 Schichtplanung automatisieren (ICS/Google Calendar Export).
    - ✅ Standard-Checklisten für Ein-/Auszug reduzieren Fehlerquote.
    - 🧰 Schulungs-„Micro-Lessons“ (5 Min) für häufige Kundenfragen.
    """)

# ----- Tab: Lager & Auslastung -----
with tabs[4]:
    st.subheader("Kapazität & Belegungssteuerung")
    total_cur, occ_calc, occ_prev_calc, abs_occ, pct_occ = occupancy_numbers()
    lc1, lc2, lc3 = st.columns(3)
    lc1.metric("Gesamt-Einheiten", total_cur)
    lc2.metric("Auslastung (%)", f"{occ_calc:.1f}", delta=badge_delta(abs_occ, pct_occ))
    lc3.metric("Ziel-Auslastung (%)", "92.0")
    fig_occ, _, _ = plot_occ_pay_sources()
    st.plotly_chart(fig_occ, use_container_width=True, key="occ_lager")

    st.markdown("""
    **Steuerungs-Tipps:**
    - < 85% Auslastung → **2-Wochen-Aktion −10%** für Neukunden, Mindestmietdauer 3 Monate.
    - ≥ 95% → **Preise für kleine Einheiten +3–5%** testen.
    - Leerstand nach Größe clustern → gezielte Bundles (z. B. 1. Monat gratis bei Vorauszahlung).
    """)

# ----- Tab: Social Media -----
with tabs[5]:
    st.subheader("Kanäle & Wirkung")
    sf = data.get("social_facebook", 0)
    sg = data.get("social_google", 0)
    sc1, sc2 = st.columns(2)
    sc1.metric("Facebook Leads", sf)
    sc2.metric("Google Leads", sg)
    bars = go.Figure()
    bars.add_bar(x=["Facebook","Google"], y=[sf, sg], marker_color=["#1877F2","#34A853"])
    bars.update_layout(height=300, title="Leads nach Kanal")
    st.plotly_chart(bars, use_container_width=True, key="sm_bars")
    sm_tips = []
    if sg < 60:
        sm_tips.append("🔎 **Google Ads:** 2 Keywords mit Kaufabsicht testen ('Selfstorage [Stadt] mieten', 'Lagerraum kurzfristig').")
    if sf > 200 and (data.get("belegungsgrad", 0) < 90):
        sm_tips.append("🎯 **FB-Targeting schärfen:** Umzüge/Studierende lokalisieren, Click-to-Call testen.")
    if not sm_tips:
        sm_tips.append("✅ Kanäle wirken solide. A/B-Tests beibehalten.")
    st.markdown("**Kanal-Tipps:**")
    for t in sm_tips:
        st.markdown(f"- {t}")

# ----- Tab: Erklärungen -----
with tabs[6]:
    st.subheader("Begriffe & Logik (für Kunden verständlich erklärt)")
    st.markdown("""
    - **Belegungsgrad**: Anteil belegter Einheiten (berechnet aus belegt/(belegt+frei)).
    - **Zahlungsquote**: Anteil bezahlter Rechnungen in %.
    - **Reminder-Automat**: Automatische Erinnerungen für fällige Rechnungen (E-Mail/SMS Workflow).
    - **Lead-Kanäle**: Herkunft neuer Anfragen (Online/Empfehlung/Vorbeikommen).
    - **Δ/Delta**: Veränderung im Vergleich zum letzten Upload in absolut und %.
    """)

# ----- Tab: Risiken & Einsparpotenziale -----
with tabs[7]:
    st.subheader("Priorisierte Risiken & Spar-Chancen")
    risks = []
    if (data.get("zahlungsstatus",{}).get("überfällig",0) or 0) > 0:
        risks.append("🔴 Überfällige Rechnungen vorhanden → Mahnprozess prüfen (Ziel: < 5 offen/überfällig).")
    if (data.get("belegungsgrad",0) or 0) < 85:
        risks.append("🟠 Niedrige Auslastung → Kurzfristige Neukunden-Aktion nötig.")
    if data.get("vertragsdauer_durchschnitt", 12) < 6:
        risks.append("🟠 Hohe Kündigungsgefahr (kurze Vertragsdauer) → Retention-Angebote 4 Wochen vor Ende.")
    if not risks:
        risks.append("🟢 Aktuell keine kritischen Risiken ersichtlich.")
    st.markdown("**Risiko-Board:**")
    for r in risks:
        st.markdown(f"- {r}")

    st.markdown("**Konkrete Einsparungen:**")
    save_tips = [
        "⚙️ Automatisierte Kommunikation statt manuellem Nachfassen (Zeitersparnis, schnellere Zahlungseingänge).",
        "🧾 Skonto & Vorauszahlung anbieten → Liquidität + weniger Ausfallrisiko.",
        "📊 Kampagnen nur auf konvertierende Zielgruppen skalieren (regelmäßige A/B-Auswertung)."
    ]
    for t in save_tips:
        st.markdown(f"- {t}")

# ---------------------------------
# Debug & System
# ---------------------------------
if DEBUG_MODE:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🌐 n8n Status")
    try:
        st.sidebar.markdown("**Aktive n8n URL (genau so gesendet):**")
        st.sidebar.code(N8N_WEBHOOK_URL, language="text")
    except:
        pass

# Rohdaten-Block
if SHOW_RAW_DATA:
    with st.expander("📂 Rohdaten (Aktuell & Vorher)", expanded=False):
        st.json({"prev": prev, "current": data})

# Sidebar Infos & Actions
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ System-Information")
st.sidebar.write(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.write("Datenquelle: n8n Workflow")
st.sidebar.write(f"Workflow Status: {'Bereit' if not st.session_state.processing else 'Verarbeitung läuft'}")
st.sidebar.write(f"Uploads in History: {len(st.session_state.history)}")

# Reset
if st.button("🔄 Daten zurücksetzen"):
    st.session_state.prev_data = DEFAULT_DATA.copy()
    st.session_state.data = DEFAULT_DATA.copy()
    st.session_state.last_upload = None
    st.session_state.history = []
    st.session_state.file_uploader_key += 1
    st.rerun()

st.markdown("---")
st.caption(f"""
Daten werden datenschutzkonform verarbeitet – Keine Speicherung personenbezogener Daten |
Kontakt: info@schimmel-automobile.de |
Aktualisiert: {datetime.now().strftime('%d.%m.%Y %H:%M')} |
n8n Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}
""")
