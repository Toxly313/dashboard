import streamlit as st
import sys, traceback

# ---------- ALLERERSTER Streamlit-Befehl ----------
st.set_page_config(page_title="Diagnose", layout="wide")

# ---------- Exception-Handler (muss nach set_page_config stehen) ----------
def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        st.error("🔥 Unbehandelte Exception:")
        st.code(error_msg)
    except:
        print(error_msg)

sys.excepthook = global_exception_handler

# ---------- Module importieren (nur Import, kein UI) ----------
try:
    from ui_theme import inject_css, style_fig
    from components import kpi_deck
    from insights import build_insights
    from charts import bar_grouped, donut_chart
    st.success("✅ Alle Module importiert")
except Exception as e:
    st.error(f"❌ Fehler beim Import: {e}")
    st.code(traceback.format_exc())
    st.stop()

# ---------- CSS injizieren ----------
try:
    inject_css()
    st.success("✅ CSS injiziert")
except Exception as e:
    st.error(f"❌ Fehler in inject_css: {e}")
    st.code(traceback.format_exc())
    st.stop()

# ---------- Session-State initialisieren ----------
if "test_data" not in st.session_state:
    st.session_state.test_data = {"belegungsgrad": 75}

# ---------- Minimales UI rendern ----------
st.title("🔬 Diagnose-Modus")
st.write("Wenn du diesen Text siehst, sind Importe und CSS okay.")

# Teste KPI-Deck
try:
    kpi_deck([
        {"label": "Belegung", "value": f"{st.session_state.test_data['belegungsgrad']}%"}
    ])
    st.success("✅ kpi_deck funktioniert")
except Exception as e:
    st.error(f"❌ Fehler in kpi_deck: {e}")
    st.code(traceback.format_exc())

# Teste Chart
try:
    fig = donut_chart(st.session_state.test_data['belegungsgrad'], "Test Chart")
    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ Chart funktioniert")
except Exception as e:
    st.error(f"❌ Fehler im Chart: {e}")
    st.code(traceback.format_exc())

# Teste Insights
try:
    tips = build_insights(st.session_state.test_data)
    st.write("Insights:", tips)
    st.success("✅ Insights funktionieren")
except Exception as e:
    st.error(f"❌ Fehler in build_insights: {e}")
    st.code(traceback.format_exc())
