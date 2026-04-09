import streamlit as st

# ALLERERSTER Befehl
st.set_page_config(page_title="Test", layout="wide")

st.title("🔬 Minimaltest")
st.write("Wenn du diesen Text siehst, funktioniert die Basis.")
st.success("Streamlit läuft!")

# Jetzt testen wir die problematischen Importe
try:
    from ui_theme import inject_css
    inject_css()
    st.write("✅ ui_theme importiert und CSS injiziert.")
except Exception as e:
    st.error(f"❌ Fehler in ui_theme: {e}")

try:
    from components import sidebar_nav
    st.write("✅ components importiert.")
    # Nicht ausführen, nur Import testen
except Exception as e:
    st.error(f"❌ Fehler in components: {e}")

try:
    from insights import build_insights
    st.write("✅ insights importiert.")
except Exception as e:
    st.error(f"❌ Fehler in insights: {e}")
