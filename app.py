import streamlit as st
import requests
import uuid
import os
import json
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# ---------------------------------
# Konfiguration
# ---------------------------------
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://tundtelectronics.app.n8n.cloud/webhook-test/process-business-data"
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
    "zahlungsstatus": {"bezahlt": 18, "offen": 3, "überfällig": 1}
}

# Regeln: höher = besser (True) / niedriger = besser (False) / neutral (None)
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
st.sidebar.title("🔧 Debug-Optionen")
DEBUG_MODE = st.sidebar.checkbox("Debug-Modus aktivieren", value=False)
SHOW_RAW_DATA = st.sidebar.checkbox("Rohdaten anzeigen", value=False)

# Session init
if "data" not in st.session_state:
    st.session_state.data = DEFAULT_DATA
if "prev_data" not in st.session_state:
    # Beim ersten Start nehmen wir DEFAULT_DATA als „Vorher“
    st.session_state.prev_data = DEFAULT_DATA.copy()
if "last_upload" not in st.session_state:
    st.session_state.last_upload = None
if "processing" not in st.session_state:
    st.session_state.processing = False

# ---------------------------------
# Upload & n8n-Verarbeitung
# ---------------------------------
uploaded_file = st.file_uploader(
    "Geschäftsdaten hochladen (Daten werden nicht gespeichert)",
    type=["csv", "json", "xlsx"],
    help="Ziehen Sie Ihre Geschäftsdaten hierher oder klicken Sie zum Durchsuchen"
)

if uploaded_file and uploaded_file != st.session_state.last_upload:
    st.session_state.processing = True
    # Merke aktuelle Daten als „vorher“, bevor wir neue holen
    st.session_state.prev_data = st.session_state.data.copy()
    st.session_state.last_upload = uploaded_file

    with st.spinner("🤖 KI verarbeitet Daten datenschutzkonform..."):
        try:
            session_id = str(uuid.uuid4())

            if DEBUG_MODE:
                st.sidebar.info("🔍 **Debug-Informationen:**")
                st.sidebar.write(f"📁 Dateiname: `{uploaded_file.name}`")
                st.sidebar.write(f"📊 Dateigröße: `{uploaded_file.size} bytes`")
                st.sidebar.write(f"🌐 n8n URL: `{N8N_WEBHOOK_URL}`")
                st.sidebar.write(f"🆔 Session ID: `{session_id}`")

            file_data = uploaded_file.getvalue()

            response = requests.post(
                N8N_WEBHOOK_URL,
                files={"file": (uploaded_file.name, file_data)},
                headers={"X-Session-ID": session_id},
                timeout=60
            )

            if DEBUG_MODE:
                st.sidebar.write(f"📡 Response Status: `{response.status_code}`")
                st.sidebar.write(f"⏱️ Response Zeit: `{response.elapsed.total_seconds():.2f}s`")

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    st.session_state.data = response_data
                    st.session_state.processing = False

                    if DEBUG_MODE:
                        st.sidebar.success("✅ Daten erfolgreich empfangen!")
                        st.sidebar.json(response_data, expanded=False)

                    st.success("✅ Daten erfolgreich verarbeitet!")

                    if response_data.get("ki_analyse_erfolgreich"):
                        st.info("🤖 KI-Analyse wurde erfolgreich durchgeführt")
                    elif response_data.get("fallback_used"):
                        st.warning("⚠️ Verwende Fallback-Daten (KI nicht verfügbar)")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Ungültiges JSON erhalten: {str(e)}")
                    if DEBUG_MODE:
                        st.sidebar.error(f"Raw Response: `{response.text[:500]}...`")
                    # Rückgängig: wenn Fehler, nimm „vorher“ wieder als aktuelle Daten
                    st.session_state.data = st.session_state.prev_data.copy()
                    st.session_state.processing = False
            else:
                st.error(f"❌ Fehler von n8n: Status {response.status_code}")
                if DEBUG_MODE:
                    st.sidebar.error(f"Fehlerantwort: `{response.text}`")
                # Rückgängig
                st.session_state.data = st.session_state.prev_data.copy()
                st.session_state.processing = False

        except Exception as e:
            st.error(f"❌ Systemfehler: {str(e)}")
            if DEBUG_MODE:
                st.sidebar.exception(e)
            # Rückgängig
            st.session_state.data = st.session_state.prev_data.copy()
            st.session_state.processing = False

# Verarbeitungsstatus
if st.session_state.processing:
    st.info("🔄 Daten werden verarbeitet...")

data = st.session_state.data
prev = st.session_state.prev_data

# Rohdaten
if SHOW_RAW_DATA:
    with st.expander("📋 Rohdaten anzeigen", expanded=False):
        st.json({"prev": prev, "current": data})

# ---------------------------------
# Hilfsfunktionen für Deltas & Farben
# ---------------------------------
def delta(a, b):
    """Delta b - a (absolut, prozentual)"""
    try:
        a = float(a)
        b = float(b)
    except Exception:
        return 0.0, None
    abs_ = b - a
    pct_ = None
    if a != 0:
        pct_ = (b - a) / a * 100.0
    return abs_, pct_

def color_for_change(key, a, b):
    """Farbe je nach Regel: grün bei Verbesserung, rot bei Verschlechterung, grau sonst."""
    rule = BETTER_RULES.get(key, None)
    try:
        a = float(a)
        b = float(b)
    except Exception:
        return "#A9A9A9"  # grau
    if b == a:
        return "#A9A9A9"
    if rule is True:     # mehr ist besser
        return "#2ca02c" if b > a else "#d62728"
    if rule is False:    # weniger ist besser
        return "#2ca02c" if b < a else "#d62728"
    # neutral
    return "#2ca02c" if b > a else "#d62728"

def badge_delta(abs_, pct_):
    if pct_ is None:
        return f"{abs_:+.0f}"
    sign = "+" if abs_ >= 0 else "−"
    return f"{sign}{abs(abs_):.0f}  ({sign}{abs(pct_):.1f}%)"

# ---------------------------------
# KPI-Kacheln mit Δ vs. letztem Upload
# ---------------------------------
st.subheader("📊 KPIs – Veränderungen seit letztem Upload")
kpi_keys = [
    "belegt","frei","vertragsdauer_durchschnitt","reminder_automat",
    "social_facebook","social_google","belegungsgrad"
]
cols = st.columns(7)
for i, k in enumerate(kpi_keys):
    cur = data.get(k, 0)
    prv = prev.get(k, 0)
    abs_, pct_ = delta(prv, cur)
    cols[i].metric(
        label=k.replace("_"," ").title(),
        value=cur if isinstance(cur, (int,float)) else str(cur),
        delta=badge_delta(abs_, pct_)
    )

# ---------------------------------
# Δ-Heatmap der Skalare
# ---------------------------------
with st.expander("🧭 Δ-Heatmap (Skalare)", expanded=False):
    vals = []
    labels = []
    for k in kpi_keys:
        cur = data.get(k, 0)
        prv = prev.get(k, 0)
        abs_, pct_ = delta(prv, cur)
        labels.append(k)
        vals.append(pct_ if pct_ is not None else 0.0)
    # einfache Heatmap mit 1 Reihe
    fig_hm = go.Figure(
        data=go.Heatmap(
            z=[vals],
            x=labels,
            y=["Δ %"],
            colorscale="RdYlGn",
            zmid=0
        )
    )
    fig_hm.update_layout(height=150, margin=dict(l=20, r=20, t=10, b=10))
    st.plotly_chart(fig_hm, use_container_width=True)

# ---------------------------------
# Visualisierungen mit farblicher Δ-Hervorhebung
# ---------------------------------
st.subheader("📈 Visualisierungen (Δ farblich hervorgehoben)")

# 1) Auslastung: Belegt/Frei als Vorher/Nachher mit Farben je Δ
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
# Delta-Labels
for idx, lbl in enumerate(x_labels):
    abs_, pct_ = delta(prev_vals[idx], cur_vals[idx])
    fig_occ.add_annotation(
        x=lbl, y=max(prev_vals[idx], cur_vals[idx]),
        text=badge_delta(abs_, pct_),
        showarrow=False, yshift=10
    )
fig_occ.update_layout(
    title="Auslastung: Belegt vs. Frei",
    barmode="group",
    height=320,
    margin=dict(t=40, b=40)
)

# 2) Neukunden pro Monat: Balken je Monat farblich nach Δ
labels = data.get("neukunden_labels", [])
after_vals = data.get("neukunden_monat", [])
before_vals = prev.get("neukunden_monat", [0]*len(labels))
if before_vals and len(before_vals) != len(after_vals):
    # robust vereinheitlichen
    before_vals = before_vals[:len(after_vals)] if len(before_vals) > len(after_vals) else before_vals + [0]*(len(after_vals)-len(before_vals))

colors = []
texts = []
for i, v in enumerate(after_vals):
    prv = before_vals[i] if i < len(before_vals) else 0
    c = color_for_change("neukunden_monat", prv, v)  # neutral-Regel
    colors.append(c)
    abs_, pct_ = delta(prv, v)
    texts.append(badge_delta(abs_, pct_))

fig_new = go.Figure()
fig_new.add_bar(
    x=labels, y=after_vals,
    marker_color=colors,
    text=texts, textposition="outside"
)
fig_new.add_scatter(
    x=labels, y=before_vals,
    mode="lines+markers",
    name="Vorher",
    line=dict(width=2, dash="dot"),
    marker=dict(size=6),
    opacity=0.6
)
fig_new.update_layout(
    title="Neukunden pro Monat (Δ farblich, Vorher als Linie)",
    xaxis_title="Monat",
    yaxis_title="Neukunden",
    height=340,
    margin=dict(t=40, b=50)
)

# 3) Zahlungsstatus: farbige Δ je Kategorie
pay_keys = ["bezahlt","offen","überfällig"]
pay_prev = [prev.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
pay_cur  = [data.get("zahlungsstatus", {}).get(k, 0) for k in pay_keys]
pay_colors = [color_for_change(k, pay_prev[i], pay_cur[i]) for i,k in enumerate(pay_keys)]
pay_texts  = [badge_delta(*delta(pay_prev[i], pay_cur[i])) for i in range(len(pay_keys))]

fig_pay = go.Figure()
fig_pay.add_bar(name="Vorher", x=[k.title() for k in pay_keys], y=pay_prev, marker_color="#B0B0B0", opacity=0.5)
fig_pay.add_bar(name="Nachher", x=[k.title() for k in pay_keys], y=pay_cur, marker_color=pay_colors, text=pay_texts, textposition="outside")
fig_pay.update_layout(
    title="Zahlungsstatus (Δ farblich)",
    yaxis_title="Anzahl Rechnungen",
    barmode="group",
    height=320,
    margin=dict(t=40, b=40)
)

# 4) Kundenherkunft: farbige Δ je Kanal
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
fig_src.update_layout(
    title="Kundenherkunft (Δ farblich)",
    barmode="group",
    height=340,
    margin=dict(t=40, b=40)
)

# Layout
col_l, col_r = st.columns(2)
with col_l:
    st.plotly_chart(fig_occ, use_container_width=True)
    st.plotly_chart(fig_new, use_container_width=True)
with col_r:
    st.plotly_chart(fig_pay, use_container_width=True)
    st.plotly_chart(fig_src, use_container_width=True)

# ---------------------------------
# Sidebar Infos
# ---------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ System-Information")
st.sidebar.write(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.write("Datenquelle: n8n Workflow")
st.sidebar.write(f"Workflow Status: {'Bereit' if not st.session_state.processing else 'Verarbeitung läuft'}")

# Reset
if st.button("🔄 Daten zurücksetzen"):
    st.session_state.prev_data = DEFAULT_DATA.copy()
    st.session_state.data = DEFAULT_DATA.copy()
    st.session_state.last_upload = None
    st.rerun()

st.markdown("---")
st.caption(f"""
Daten werden datenschutzkonform verarbeitet - Keine Speicherung personenbezogener Daten |
Kontakt: info@schimmel-automobile.de |
Aktualisiert: {datetime.now().strftime('%d.%m.%Y %H:%M')} |
n8n Endpoint: {N8N_WEBHOOK_URL.split('/')[-1]}
""")
