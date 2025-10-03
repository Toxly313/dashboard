# data_utils.py
import json, uuid, requests
import pandas as pd

def delta(a, b):
    try: a=float(a); b=float(b)
    except: return 0.0, None
    abs_ = b-a
    pct_ = None if a==0 else (b-a)/a*100
    return abs_, pct_

def post_to_n8n(url: str, file_tuple, session_id: str):
    r = requests.post(url, files={"file": file_tuple}, headers={"X-Session-ID": session_id}, timeout=60)
    try: return r.status_code, r.text, r.json()
    except Exception: return r.status_code, r.text, None

def extract_metrics_from_excel(df: pd.DataFrame) -> dict:
    # gleiche Heuristik wie zuvor – mappt einfache Spaltennamen
    colmap = {
        "belegt":"belegt", "frei":"frei", "vertragsdauer_durchschnitt":"vertragsdauer_durchschnitt",
        "reminder_automat":"reminder_automat", "social_facebook":"social_facebook",
        "social_google":"social_google", "belegungsgrad":"belegungsgrad",
        "kundenherkunft_online":("kundenherkunft","Online"),
        "kundenherkunft_empfehlung":("kundenherkunft","Empfehlung"),
        "kundenherkunft_vorbeikommen":("kundenherkunft","Vorbeikommen"),
        "zahlungsstatus_bezahlt":("zahlungsstatus","bezahlt"),
        "zahlungsstatus_offen":("zahlungsstatus","offen"),
        "zahlungsstatus_überfällig":("zahlungsstatus","überfällig"),
    }
    out = {"kundenherkunft": {}, "zahlungsstatus": {}}
    if df.empty: return {}
    row = df.iloc[0]
    for c in df.columns:
        key = c.strip().lower().replace(" ","_")
        if key in colmap:
            target = colmap[key]
            try: val=float(row[c])
            except: continue
            if isinstance(target, tuple):
                p, ch = target; out[p][ch]=val
            else:
                out[target]=val
    return out

def merge_data(base: dict, addon: dict) -> dict:
    merged = json.loads(json.dumps(base))
    for k, v in (addon or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged
