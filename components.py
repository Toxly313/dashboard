import json, pathlib, streamlit as st

PRESET_DIR = pathlib.Path("presets"); PRESET_DIR.mkdir(exist_ok=True)
PREFS_FILE = pathlib.Path(".user_prefs.json")

def load_prefs(defaults: dict) -> dict:
    if PREFS_FILE.exists():
        try: return json.loads(PREFS_FILE.read_text())
        except: return defaults
    return defaults

def save_prefs(prefs: dict):
    PREFS_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))

def save_preset(name: str, prefs: dict):
    (PRESET_DIR / f"{name}.json").write_text(json.dumps(prefs, ensure_ascii=False, indent=2))

def load_preset(name: str) -> dict | None:
    p = PRESET_DIR / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None

def sidebar_nav():
    with st.sidebar:
        st.markdown("""
        <div class="side-card" style="text-align:center;">
          <div style="font-size:40px;line-height:1">🟣</div>
          <div style="font-weight:800;margin-top:4px">Self-Storage</div>
          <div style="font-size:12px;opacity:.8">Business Suite</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("#### Navigation")
        section = st.radio(
            label="Bereich wählen",
            options=["Overview","Customers","Open Orders","Capacity","Social Media","Finance","Settings"],
            index=0, label_visibility="collapsed"
        )
        st.markdown("#### Dashboard-Builder")
        layout = st.selectbox("Layout", ["Executive (empfohlen)","Operations","Marketing"])
        chart_style = st.selectbox("Diagramm-Stil", ["Balken (gruppiert)","Balken (gestapelt)","Linie","Fläche","Donut"])
        kpis = st.multiselect("KPIs anzeigen",
            ["Belegt","Frei","Ø Vertragsdauer","Reminder","Belegungsgrad","Facebook","Google Reviews"],
            default=["Belegt","Frei","Belegungsgrad","Ø Vertragsdauer"])
        return {"section": section, "layout": layout, "chart_style": chart_style, "kpis": kpis}

def presets_ui(current_prefs: dict) -> dict | None:
    st.markdown("#### Presets")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Preset speichern als", placeholder="Executive-Board", label_visibility="collapsed")
        if st.button("💾 Speichern", use_container_width=True):
            if name.strip():
                save_preset(name.strip(), current_prefs); st.success("Preset gespeichert.")
    with c2:
        choices = ["–"] + [p.stem for p in PRESET_DIR.glob("*.json")]
        sel = st.selectbox("Preset laden", options=choices, label_visibility="collapsed")
        if st.button("📥 Laden", use_container_width=True) and sel!="–":
            return load_preset(sel)
    return None

def control_panel():
    st.markdown("#### Anzeige filtern")
    c1, c2 = st.columns(2)
    with c1: period = st.selectbox("Zeitraum", ["Letzter Upload","Letzte 3 Uploads","Letzte 6 Uploads"])
    with c2: compare = st.selectbox("Vergleichsbasis", ["Vorheriger Upload","Baseline (Start)"])
    return {"period": period, "compare": compare}

def kpi_deck(items: list[dict]):
    cols = st.columns(len(items))
    for i, it in enumerate(items):
        with cols[i]:
            st.metric(it["label"], it["value"], it.get("delta",""))
