# ========== ALLERERSTER Streamlit-Befehl ==========
import streamlit as st

st.set_page_config(
    page_title="Self-Storage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== IMPORTS (nach set_page_config) ==========
import os
import uuid
import json
import time
import pathlib
import hashlib
import traceback
import sys
from datetime import datetime

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import base64

# ========== EIGENE MODULE ==========
from insights import build_insights
from ui_theme import inject_css, style_fig
from charts import bar_grouped, donut_chart, tips_impact_chart, tips_savings_chart
from components import kpi_deck

# ========== GLOBALER EXCEPTION-HANDLER ==========
def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        st.error("🔥 Unbehandelte Exception – bitte an Entwickler weitergeben:")
        st.code(error_msg)
    except Exception:
        print(error_msg)

sys.excepthook = global_exception_handler

# ========== CSS INJIZIEREN ==========
inject_css()

# ========== PORT FIX ==========
if 'PORT' in os.environ:
    os.environ['STREAMLIT_SERVER_PORT'] = os.environ['PORT']
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

# ========== PASSWORT-HASHES ==========
TENANTS = {
    "demo@kunde.de": {
        "tenant_id": "kunde_demo_123",
        "name": "Demo Kunde GmbH",
        "plan": "pro",
        "analyses_limit": 50,
        "analyses_used": 0,
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest()
    },
    "test@firma.de": {
        "tenant_id": "firma_test_456",
        "name": "Test Firma AG",
        "plan": "business",
        "analyses_limit": 200,
        "analyses_used": 0,
        "password_hash": hashlib.sha256("demo123".encode()).hexdigest()
    }
}

# ========== DEFAULT DATEN ==========
DEFAULT_DATA = {
    "belegt": 18, "frei": 6, "vertragsdauer_durchschnitt": 7.2, "reminder_automat": 15,
    "social_facebook": 280, "social_google": 58, "belegungsgrad": 75,
    "kundenherkunft": {"Online": 12, "Empfehlung": 6, "Vorbeikommen": 4},
    "neukunden_labels": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun"],
    "neukunden_monat": [5, 4, 7, 6, 8, 9],
    "zahlungsstatus": {"bezahlt": 21, "offen": 2, "überfällig": 1},
    "recommendations": [], "customer_message": ""
}

# ========== SESSION-STATE INITIALISIEREN ==========
def init_session_state():
    defaults = {
        "current_data": DEFAULT_DATA.copy(),
        "before_analysis": None,
        "after_analysis": None,
        "analyses_history": [],
        "n8n_base_url": os.environ.get("N8N_BASE_URL", "https://tundtelectronics.app.n8n.cloud/webhook"),
        "debug_mode": False,
        "show_comparison": False,
        "last_analysis_loaded": False,
        "logged_in": False,
        "current_tenant": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ========== HILFSFUNKTIONEN (unverändert aus deinem Code) ==========
# (Hier den gesamten restlichen Code aus deiner app.py einfügen,
#  beginnend ab "class N8NResponseValidator" bis zum Ende,
#  aber OHNE die bereits oben stehenden Teile wie set_page_config, Imports, TENANTS, DEFAULT_DATA, init_session_state)

# Ich füge den restlichen Code hier als Platzhalter ein – du kannst deinen bestehenden Code
# ab "class N8NResponseValidator" bis zum Ende kopieren und hier einfügen.
