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
DEBUG_MODE = st.sidebar.checkbox("Debug-Modus aktivieren", value=True)  # Default true für besseres Debugging
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
    # einfache Heuristik (du kannst das Mapping hier erweitern)
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
    # Wir nehmen die erste Zeile als „aktuellen Stand" (oder Mittelwert)
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

def upload_and_process(uploaded_file, excel_metrics=None):
    """Verarbeitet die Datei und sendet sie an n8n"""
    if uploaded_file is None:
        st.error("❌ Bitte wählen Sie zuerst eine Datei aus.")
        return False

    st.session_state.processing = True
    st.session_state.prev_data = st.session_state.data.copy()
    st.session_state.last_upload = uploaded_file

    with st.spinner("🤖 KI verarbeitet Daten datenschutzkonform..."):
        try:
            session_id = str(uuid.uuid4())
            file_data = uploaded_file.getvalue()

            if DEBUG_MODE:
                st.sidebar.info("🔍 Debug-Informationen")
                st.sidebar.write(f"📁 Datei: {uploaded_file.name}")
                st.sidebar.write(f"📊 Größe: {uploaded_file.size} bytes")
                st.sidebar.write(f"🌐 n8n URL: {N8N_WEBHOOK_URL}")
                st.sidebar.write(f"🆔 Session ID: {session_id}")

            # Sende Datei an n8n
            response = requests.post(
                N8N_WEBHOOK_URL,
                files={"file": (uploaded_file.name, file_data)},
                headers={"X-Session-ID": session_id},
                timeout=60
            )

            if DEBUG_MODE:
                st.sidebar.write(f"📡 Status: {response.status_code}")
                st.sidebar.write(f"⏱️ Dauer: {response.elapsed.total_seconds():.2f}s")
                st.sidebar.write("📨 Rohantwort:")
                st.sidebar.code(response.text[:1000] if response.text else "LEER", language="text")

            # Robuste Antwort-Verarbeitung
            if response.status_code == 200:
                # Prüfe ob Antwort leer ist
                if not response.text or not response.text.strip():
                    st.error("❌ n8n hat eine leere Antwort zurückgegeben")
                    if DEBUG_MODE:
                        st.sidebar.error("Leere Antwort von n8n erhalten")
                    st.session_state.data = st.session_state.prev_data.copy()
                    st.session_state.processing = False
                    return False
                
                try:
                    # Versuche JSON zu parsen
                    response_data = response.json()
                    
                    # Excel-Metriken (falls vorhanden) in KI-JSON mergen
                    merged = merge_data(response_data, excel_metrics or {})
                    st.session_state.data = merged
                    st.session_state.processing = False
                    st.session_state.history.append({"ts": datetime.now().isoformat(), "data": merged})
                    
                    # Setze den Uploader zurück, um eine neue Datei zu ermöglichen
                    st.session_state.file_uploader_key += 1

                    st.success("✅ Daten erfolgreich verarbeitet!")
                    if merged.get("ki_analyse_erfolgreich"):
                        st.info("🤖 KI-Analyse erfolgreich")
                    elif merged.get("fallback_used"):
                        st.warning("⚠️ Fallback-Daten verwendet")
                    
                    if DEBUG_MODE:
                        st.sidebar.success("✅ JSON erfolgreich geparst")
                        st.sidebar.json(merged, expanded=False)
                    
                    return True
                    
                except json.JSONDecodeError as e:
                    error_msg = f"❌ Ungültiges JSON von n8n: {str(e)}"
                    st.error(error_msg)
                    if DEBUG_MODE:
                        st.sidebar.error(f"JSON Parse Fehler: {str(e)}")
                        st.sidebar.write("💡 Mögliche Ursachen:")
                        st.sidebar.write("- n8n Workflow nicht aktiviert")
                        st.sidebar.write("- Webhook-Pfad falsch")
                        st.sidebar.write("- n8n gibt HTML-Fehlerseite zurück")
                    
                    st.session_state.data = st.session_state.prev_data.copy()
                    st.session_state.processing = False
                    return False
                    
            else:
                error_msg = f"❌ Fehler von n8n: Status {response.status_code}"
                st.error(error_msg)
                if DEBUG_MODE:
                    st.sidebar.error(f"n8n Fehlerantwort: {response.text}")
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
# Upload Section mit Button
# ---------------------------------
st.subheader("📥 Datenzufuhr")

# Excel einlesen (nur Anzeige & optionaler Merge)
excel_file = st.file_uploader(
    "Optional: Excel-Rohdaten (für Anzeige & Merge)", 
    type=["xlsx"], 
    key="excel_upl"
)

excel_metrics = {}
if excel_file:
    try:
        # Versuche openpyxl zu importieren
        try:
            import openpyxl
        except ImportError:
            st.error("""
            **❌ Fehlende Abhängigkeit: openpyxl**
            
            Um Excel-Dateien zu lesen, muss openpyxl installiert werden:
            
            **Installation:**
            ```bash
            pip install openpyxl
            ```
            
            **Für Railway/Streamlit Cloud:** Füge `openpyxl` zu deiner `requirements.txt` hinzu.
            """)
            st.stop()
        
        df_excel = pd.read_excel(excel_file)
        if SHOW_RAW_DATA:
            st.markdown("**📋 Excel-Rohdaten**")
            st.dataframe(df_excel, use_container_width=True)
        excel_metrics = extract_metrics_from_excel(df_excel)
        
        if excel_metrics:
            st.success(f"✅ Excel-Daten erfolgreich gelesen ({len(df_excel)} Zeilen)")
        else:
            st.warning("⚠️ Excel wurde gelesen, aber keine Metriken konnten extrahiert werden")
            
    except Exception as e:
        st.error(f"❌ Excel konnte nicht verarbeitet werden: {str(e)}")

# KI-Verarbeitung mit Button
uploaded_file = st.file_uploader(
    "Geschäftsdaten für KI-Analyse auswählen (CSV/JSON/Excel)",
    type=["csv", "json", "xlsx"],
    help="Wird an n8n geschickt, dort von KI verarbeitet und als JSON zurückgegeben.",
    key=f"ki_upl_{st.session_state.file_uploader_key}"
)

# Upload Button
if st.button("📤 Datei hochladen und analysieren", type="primary"):
    upload_and_process(uploaded_file, excel_metrics)

if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet...")

data = st.session_state.data
prev = st.session_state.prev_data

# Zeige n8n Verbindungsstatus
if DEBUG_MODE:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🌐 n8n Status")
    try:
        # Einfacher Verbindungstest
        test_response = requests.get(N8N_WEBHOOK_URL.replace("/webhook/", ""), timeout=5)
        st.sidebar.write(f"n8n erreichbar: {'✅' if test_response.status_code < 500 else '❌'}")
    except:
        st.sidebar.write("n8n erreichbar: ❌")

# Rohdaten-Block
if SHOW_RAW_DATA:
    with st.expander("📂 Rohdaten (KI / Merged) & Vorher", expanded=False):
        st.json({"prev": prev, "current": data})

# ---------------------------------
# KPI-Kacheln (Δ vs letztem Upload)
# ---------------------------------
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

# Δ-Heatmap (Skalare)
with st.expander("🧭 Δ-Heatmap (Skalare)", expanded=False):
    labels = []; vals = []
    for k in kpi_keys:
        cur = data.get(k, 0); prv = prev.get(k, 0)
        _, pct_ = delta(prv, cur)
        labels.append(k); vals.append(pct_ if pct_ is not None else 0.0)
    fig_hm = go.Figure(data=go.Heatmap(z=[vals], x=labels, y=["Δ %"], colorscale="RdYlGn", zmid=0))
    fig_hm.update_layout(height=150, margin=dict(l=20,r=20,t=10,b=10))
    st.plotly_chart(fig_hm, use_container_width=True)

# ---------------------------------
# Visualisierungen (Δ farblich)
# ---------------------------------
st.subheader("📈 Visualisierungen (Δ farblich hervorgehoben)")

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

# 2) Neukunden
labels = data.get("neukunden_labels", [])
after_vals = data.get("neukunden_monat", [])
before_vals = prev.get("neukunden_monat", [0]*len(labels))
if before_vals and len(before_vals)!=len(after_vals):
    before_vals = before_vals[:len(after_vals)] if len(before_vals)>len(after_vals) else before_vals+[0]*(len(after_vals)-len(before_vals))
colors = []; texts = []
for i, v in enumerate(after_vals):
    prv = before_vals[i] if i < len(before_vals) else 0
    c = color_for_change("neukunden_monat", prv, v)
    colors.append(c)
    abs_, pct_ = delta(prv, v)
    texts.append(badge_delta(abs_, pct_))
fig_new = go.Figure()
fig_new.add_bar(x=labels, y=after_vals, marker_color=colors, text=texts, textposition="outside")
fig_new.add_scatter(x=labels, y=before_vals, mode="lines+markers", name="Vorher", line=dict(width=2, dash="dot"), marker=dict(size=6), opacity=0.6)
fig_new.update_layout(title="Neukunden pro Monat (Δ farblich, Vorher als Linie)", xaxis_title="Monat", yaxis_title="Neukunden", height=340, margin=dict(t=40,b=50))

# 3) Zahlungsstatus
pay_keys = ["bezahlt","offen","überfällig"]
pay_prev = [prev.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
pay_cur  = [data.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
pay_colors = [color_for_change(k, pay_prev[i], pay_cur[i]) for i,k in enumerate(pay_keys)]
pay_texts  = [badge_delta(*delta(pay_prev[i], pay_cur[i])) for i in range(len(pay_keys))]
fig_pay = go.Figure()
fig_pay.add_bar(name="Vorher", x=[k.title() for k in pay_keys], y=pay_prev, marker_color="#B0B0B0", opacity=0.5)
fig_pay.add_bar(name="Nachher", x=[k.title() for k in pay_keys], y=pay_cur, marker_color=pay_colors, text=pay_texts, textposition="outside")
fig_pay.update_layout(title="Zahlungsstatus (Δ farblich)", yaxis_title="Anzahl Rechnungen", barmode="group", height=320, margin=dict(t=40,b=40))

# 4) Kundenherkunft
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

# Layout
col_l, col_r = st.columns(2)
with col_l:
    st.plotly_chart(fig_occ, use_container_width=True)
    st.plotly_chart(fig_new, use_container_width=True)
with col_r:
    st.plotly_chart(fig_pay, use_container_width=True)
    st.plotly_chart(fig_src, use_container_width=True)

# ---------------------------------
# Neue Statistiken & Vergleiche
# ---------------------------------
st.subheader("🧮 Neue Statistiken dieses Uploads")

# 1) Occupancy / Quoten
total_cur = (data.get("belegt",0) or 0) + (data.get("frei",0) or 0)
occ_calc = (data.get("belegt",0)/total_cur*100) if total_cur else data.get("belegungsgrad",0)
total_prev = (prev.get("belegt",0) or 0) + (prev.get("frei",0) or 0)
occ_prev_calc = (prev.get("belegt",0)/total_prev*100) if total_prev else prev.get("belegungsgrad",0)
abs_occ, pct_occ = delta(occ_prev_calc, occ_calc)

# 2) Zahlungsquote
paid = data.get("zahlungsstatus",{}).get("bezahlt",0)
open_ = data.get("zahlungsstatus",{}).get("offen",0)
overd = data.get("zahlungsstatus",{}).get("überfällig",0)
tot_invoices = paid + open_ + overd
pay_ratio = (paid / tot_invoices * 100) if tot_invoices else 0

# 3) Ø Neukunden-Wachstum
growth = None
try:
    vals = data.get("neukunden_monat", []) or []
    if len(vals) >= 2:
        growth = float(np.mean(np.diff(vals)))
except Exception:
    growth = None

# 4) Anteil Empfehlungen vs. Online
her = data.get("kundenherkunft",{}) or {}
total_leads = sum(her.values()) if her else 0
share_empf = (her.get("Empfehlung",0) / total_leads * 100) if total_leads else 0
share_online = (her.get("Online",0) / total_leads * 100) if total_leads else 0

scol1, scol2, scol3, scol4 = st.columns(4)
scol1.metric("Belegungsgrad (berechnet) %", f"{occ_calc:.1f}", delta=badge_delta(abs_occ, pct_occ))
scol2.metric("Zahlungsquote (bezahlt %)", f"{pay_ratio:.1f}")
scol3.metric("Ø Neukunden-Wachstum/Monat", f"{growth:.1f}" if growth is not None else "–")
scol4.metric("Leads: Empfehlung vs. Online (%)", f"{share_empf:.1f} / {share_online:.1f}")

# History-Preview (Trend der letzten Uploads)
if len(st.session_state.history) >= 2:
    with st.expander("📜 Verlauf (letzte Uploads) – Belegt & Belegungsgrad", expanded=False):
        times = [h["ts"] for h in st.session_state.history][-6:]
        belegt_hist = [h["data"].get("belegt",0) for h in st.session_state.history][-6:]
        occ_hist = []
        for h in st.session_state.history[-6:]:
            d = h["data"]; t = (d.get("belegt",0)+d.get("frei",0))
            occ = (d.get("belegt",0)/t*100) if t else d.get("belegungsgrad",0)
            occ_hist.append(occ)
        fig_hist = go.Figure()
        fig_hist.add_scatter(x=times, y=belegt_hist, mode="lines+markers", name="Belegt")
        fig_hist.add_scatter(x=times, y=occ_hist, mode="lines+markers", name="Belegungsgrad %")
        fig_hist.update_layout(height=260, margin=dict(t=30,b=30))
        st.plotly_chart(fig_hist, use_container_width=True)

# ---------------------------------
# KI-Empfehlungen & Zusammenfassung
# ---------------------------------
st.subheader("💡 KI-Tipps & Zusammenfassung")
recs = data.get("recommendations", []) or []
msg = data.get("customer_message") or ""
if recs:
    for r in recs[:6]:
        st.markdown(f"- {r}")
else:
    st.caption("Keine Empfehlungen im JSON gefunden.")
if msg:
    st.info(msg)

# ---------------------------------
# Sidebar Infos & Actions
# ---------------------------------
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
