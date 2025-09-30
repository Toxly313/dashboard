import json
import pandas as pd

def extract_metrics_from_excel(df: pd.DataFrame) -> dict:
    colmap = {
        "belegt": "belegt", "frei": "frei", "vertragsdauer_durchschnitt": "vertragsdauer_durchschnitt",
        "reminder_automat": "reminder_automat", "social_facebook": "social_facebook",
        "social_google": "social_google", "belegungsgrad": "belegungsgrad",
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
                parent, child = target
                out[parent][child] = val
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
