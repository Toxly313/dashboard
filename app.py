import os, uuid, json, re
from datetime import datetime
import numpy as np, pandas as pd, streamlit as st

# ===== PORT FIX FÜR RAILWAY =====
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# ===== HILFSFUNKTIONEN (vereinfacht) =====
def extract_json_from_markdown(text):
    if not text or not isinstance(text, str): return None
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        try: return json.loads(matches[0])
        except: pass
    try:
        start, end = text.find('{'), text.rfind('}')+1
        if start!=-1 and end>0: return json.loads(text[start:end])
    except: pass
    return None

def delta(prev, cur):
    try:
        abs_c = float(cur)-float(prev)
        pct_c = (abs_c/float(prev))*100 if float(prev)!=0 else None
        return round(abs_c,2), round(pct_c,2) if pct_c else None
    except: return 0,0

# ===== MOCK & DEFAULT DATEN =====
DEFAULT_DATA = {"belegt":18,"frei":6,"belegungsgrad":75}
MOCK_DATA = {
    "belegt":20,"frei":4,"belegungsgrad":83,
    "recommendations":["Test-Empfehlung 1","Test-Empfehlung 2"],
    "customer_message":"Testnachricht"
}

# ===== HAUPTAPP =====
def main():
    # Session State init
    if "data" not in st.session_state: st.session_state.data = DEFAULT_DATA.copy()
    if "prev" not in st.session_state: st.session_state.prev = DEFAULT_DATA.copy()
    if "history" not in st.session_state: st.session_state.history = []
    if "debug" not in st.session_state: st.session_state.debug = ""

    # UI
    st.title("📊 Debug Dashboard")
    
    # ===== DEBUG-SIDEBAR =====
    with st.sidebar:
        st.header("🐛 Debug Panel")
        if st.button("Session State anzeigen"):
            st.session_state.debug = "session"
        if st.button("Debug löschen"):
            st.session_state.debug = ""
        st.divider()
        
        # Manuelle n8n URL
        n8n_url = st.text_input("n8n URL", value=os.environ.get("N8N_URL",""))
        test_mode = st.checkbox("Testmodus (Mock-Daten)")
        
        # Debug-Ausgabe in Sidebar
        if st.session_state.debug == "session":
            st.subheader("🔍 Session State")
            st.json(st.session_state.data)
            st.write("History:", st.session_state.history)
    
    # ===== HAUPTBEREICH =====
    st.header("📁 Datei-Upload & Analyse")
    
    uploaded_file = st.file_uploader("Datei hochladen", type=["xlsx","csv"])
    col1, col2 = st.columns(2)
    with col1: analyze_btn = st.button("🚀 Analysieren", type="primary")
    with col2: reset_btn = st.button("🗑️ Zurücksetzen")
    
    # Reset
    if reset_btn:
        st.session_state.data = DEFAULT_DATA.copy()
        st.session_state.prev = DEFAULT_DATA.copy()
        st.session_state.history = []
        st.success("Daten zurückgesetzt!")
        st.rerun()
    
    # Analyse starten
    if analyze_btn and uploaded_file:
        with st.spinner("🧠 Analysiere..."):
            # DEBUG: Log
            st.session_state.debug = f"Analysiere {uploaded_file.name}"
            
            if test_mode:
                # Mock-Daten
                st.session_state.prev = st.session_state.data.copy()
                st.session_state.data = MOCK_DATA
                st.session_state.history.append({"ts":datetime.now().isoformat(), "data":MOCK_DATA})
                st.success("✅ Mock-Analyse fertig!")
                st.rerun()
            elif n8n_url and n8n_url.startswith("http"):
                # ECHTE n8n-Analyse mit Debug
                import requests
                try:
                    response = requests.post(
                        n8n_url,
                        files={'file': (uploaded_file.name, uploaded_file.getvalue())},
                        data={'uuid': str(uuid.uuid4())},
                        timeout=30
                    )
                    
                    # ===== KRITISCHER DEBUG-BEREICH =====
                    with st.expander("🔍 n8n-Antwort (ROHDATEN)", expanded=True):
                        st.write("Status Code:", response.status_code)
                        st.text_area("Rohantwort (erste 2000 Zeichen):", 
                                   str(response.text)[:2000], height=300)
                    
                    if response.status_code == 200:
                        # Versuche JSON zu extrahieren
                        json_data = extract_json_from_markdown(response.text)
                        
                        with st.expander("🔍 Extrahiertes JSON"):
                            st.write(json_data)
                        
                        if json_data:
                            # Verarbeite Daten
                            new_data = json_data.get("metrics", json_data)
                            st.session_state.prev = st.session_state.data.copy()
                            st.session_state.data = {
                                **st.session_state.data,
                                **new_data,
                                "recommendations": json_data.get("recommendations", []),
                                "customer_message": json_data.get("customer_message", "")
                            }
                            st.success(f"✅ Analyse mit {len(json_data.get('recommendations',[]))} Empfehlungen")
                        else:
                            st.error("❌ Kein JSON in Antwort gefunden")
                    else:
                        st.error(f"❌ n8n Fehler {response.status_code}")
                        
                except Exception as e:
                    st.error(f"❌ Request fehlgeschlagen: {str(e)}")
            else:
                st.error("❌ Bitte gültige n8n URL eingeben")
    
    # ===== ERGEBNISANZEIGE =====
    st.header("📊 Ergebnisse")
    
    # KPIs
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Belegt", st.session_state.data.get("belegt", 0))
    with col2: st.metric("Frei", st.session_state.data.get("frei", 0))
    with col3: st.metric("Belegungsgrad", f"{st.session_state.data.get('belegungsgrad',0)}%")
    
    # Empfehlungen
    if st.session_state.data.get("recommendations"):
        st.subheader("🤖 KI-Empfehlungen")
        for rec in st.session_state.data["recommendations"]:
            st.markdown(f"- {rec}")
    
    # Debug-Ausgabe im Hauptbereich
    if st.session_state.debug and st.session_state.debug != "session":
        st.info(f"Debug: {st.session_state.debug}")

if __name__ == "__main__":
    main()
