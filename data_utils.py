# data_utils.py
import json, uuid, requests
import pandas as pd

BETTER_RULES = {
    "belegt": True, "frei": False, "vertragsdauer_durchschnitt": True,
    "reminder_automat": None, "social_facebook": True,
    "social_google": True, "belegungsgrad": True
}

def delta(a, b):
    try:
        a = float(a); b = float(b)
    except Exception:
        return 0.0, None
    abs_ = b - a
    pct_ = None if a == 0 else (b - a) / a * 100.0
    return abs_, pct_

def badge_delta(abs_, pct_):
    if pct_ is None: return f"{abs_:+.0f}"
    sign = "+" if abs_ >= 0 else "−"
    return f"{sign}{abs(abs_):.0f} ({sign}{abs(pct_):.1f}%)"

def color_for_change(key, a, b):
    rule = BETTER_RULES.get(key, None)
    try:
        a = float(a); b = float(b)
    except Exception:
        return "#A9A9A9"
    if b == a: return "#A9A9A9"
    if rule is True:  return "#22C55E" if b > a else "#EF4444"
    if rule is False: return "#22C55E" if b < a else "#EF4444"
    return "#22C55E" if b > a else "#EF4444"

def extract_metrics_from_excel(df: pd.DataFrame) -> dict:
    colmap = {
        "belegt": "belegt", "frei": "frei",
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
    if len(df) == 0: return {}
    row = df.iloc[0]
    for c in df.columns:
        key = c.strip().lower().replace(" ", "_")
        if key in colmap:
            target = colmap[key]
            try:
                val = float(row[c])
            except Exception:
                continue
            if isinstance(target, tuple):
                parent, child = target; out[parent][child] = val
            else:
                out[target] = val
    return out

def merge_data(base: dict, addon: dict) -> dict:
    merged = json.loads(json.dumps(base))
    for k, v in (addon or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged

def post_to_n8n(url: str, file_tuple, session_id: str):
    r = requests.post(
        url, files={"file": file_tuple},
        headers={"X-Session-ID": session_id}, timeout=60
    )
    try: return r.status_code, r.text, r.json()
    except Exception: return r.status_code, r.text, None
