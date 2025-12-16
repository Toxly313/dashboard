import json, re, time
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

def post_to_n8n(url, file_tuple, uuid_str):
    """
    Sendet Datei an n8n Webhook und gibt Antwort zurück.
    
    Args:
        url: n8n Webhook URL
        file_tuple: (filename, file_bytes)
        uuid_str: Eindeutige ID für diesen Request
    
    Returns:
        (status_code, message, json_response)
    """
    import requests
    
    if not url or not url.startswith("http"):
        return 400, "Ungültige URL", None
    
    # Daten vorbereiten
    files = {'file': file_tuple} if file_tuple else None
    data = {'uuid': uuid_str}
    
    try:
        # Längeren Timeout für KI-Analyse (n8n braucht ~16s)
        timeout = 45  # Sekunden
        
        # Request senden
        response = requests.post(
            url, 
            files=files, 
            data=data, 
            timeout=timeout,
            headers={'User-Agent': 'Dashboard-KI/1.0'}
        )
        
        # Status-Code prüfen
        if response.status_code != 200:
            error_msg = f"n8n Fehler {response.status_code}"
            try:
                error_detail = response.json().get('error', response.text[:200])
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            return response.status_code, error_msg, None
        
        # JSON Antwort parsen
        try:
            response_json = response.json()
            return response.status_code, "Success", response_json
        except json.JSONDecodeError as e:
            return response.status_code, f"Kein gültiges JSON: {str(e)}", None
            
    except requests.exceptions.Timeout:
        return 408, f"Timeout nach {timeout}s - n8n braucht zu lange", None
    except requests.exceptions.ConnectionError:
        return 503, "Verbindungsfehler zu n8n", None
    except requests.exceptions.RequestException as e:
        return 500, f"Request Fehler: {str(e)}", None
    except Exception as e:
        return 500, f"Unerwarteter Fehler: {str(e)}", None

def extract_metrics_from_excel(df):
    """
    Extrahiert Metriken aus Excel-Daten.
    """
    metrics = {}
    
    try:
        # Beispiel: Belegung aus Spalten erkennen
        if 'belegt' in df.columns:
            metrics['belegt'] = int(df['belegt'].sum())
        if 'frei' in df.columns:
            metrics['frei'] = int(df['frei'].sum())
        
        # Belegungsgrad berechnen
        if 'belegt' in metrics and 'frei' in metrics:
            total = metrics['belegt'] + metrics['frei']
            if total > 0:
                metrics['belegungsgrad'] = round((metrics['belegt'] / total) * 100, 1)
        
        # Weitere Spalten prüfen
        for col in ['vertragsdauer_durchschnitt', 'reminder_automat', 
                   'social_facebook', 'social_google']:
            if col in df.columns:
                metrics[col] = float(df[col].mean())
        
        # Kundenherkunft
        herkunft_cols = [c for c in df.columns if 'herkunft' in c.lower() or 'kanal' in c.lower()]
        if herkunft_cols:
            # Einfache Zählung
            herkunft_counts = df[herkunft_cols[0]].value_counts().to_dict()
            metrics['kundenherkunft'] = {
                'Online': herkunft_counts.get('Online', 0),
                'Empfehlung': herkunft_counts.get('Empfehlung', 0),
                'Vorbeikommen': herkunft_counts.get('Vorbeikommen', 0)
            }
        
        # Zahlungsstatus
        status_cols = [c for c in df.columns if 'status' in c.lower() or 'zahlung' in c.lower()]
        if status_cols:
            status_counts = df[status_cols[0]].value_counts().to_dict()
            metrics['zahlungsstatus'] = {
                'bezahlt': status_counts.get('bezahlt', 0),
                'offen': status_counts.get('offen', 0),
                'überfällig': status_counts.get('überfällig', 0)
            }
            
    except Exception as e:
        st.warning(f"Konnte nicht alle Excel-Daten verarbeiten: {str(e)[:100]}")
    
    return metrics

def merge_data(base_dict, new_dict):
    """
    Mergt zwei Dictionaries, wobei new_dict Vorrang hat.
    """
    result = base_dict.copy() if base_dict else {}
    
    if new_dict:
        # Einfache Werte mergen
        for key, value in new_dict.items():
            if key not in ['kundenherkunft', 'zahlungsstatus', 'recommendations', 'customer_message']:
                result[key] = value
        
        # Kundenherkunft mergen
        if 'kundenherkunft' in new_dict:
            if 'kundenherkunft' not in result:
                result['kundenherkunft'] = {'Online': 0, 'Empfehlung': 0, 'Vorbeikommen': 0}
            for k, v in new_dict['kundenherkunft'].items():
                if k in result['kundenherkunft']:
                    result['kundenherkunft'][k] += v
                else:
                    result['kundenherkunft'][k] = v
        
        # Zahlungsstatus mergen
        if 'zahlungsstatus' in new_dict:
            if 'zahlungsstatus' not in result:
                result['zahlungsstatus'] = {'bezahlt': 0, 'offen': 0, 'überfällig': 0}
            for k, v in new_dict['zahlungsstatus'].items():
                if k in result['zahlungsstatus']:
                    result['zahlungsstatus'][k] += v
                else:
                    result['zahlungsstatus'][k] = v
    
    return result

def delta(prev, cur):
    """
    Berechnet absolute und prozentuale Veränderung.
    """
    try:
        abs_change = float(cur) - float(prev)
        if float(prev) != 0:
            pct_change = (abs_change / float(prev)) * 100
        else:
            pct_change = None
        return round(abs_change, 2), round(pct_change, 2) if pct_change is not None else None
    except:
        return 0, 0

def kpi_state(key, value):
    """
    Bestimmt den Status einer KPI für Farbgebung.
    """
    thresholds = {
        'belegt': (0, 10, 20),
        'belegungsgrad': (70, 85, 95),
        'vertragsdauer_durchschnitt': (3, 6, 12),
        'social_google': (20, 50, 100)
    }
    
    if key in thresholds:
        low, medium, high = thresholds[key]
        if value < low:
            return 'critical'
        elif value < medium:
            return 'warning'
        elif value < high:
            return 'neutral'
        else:
            return 'good'
    
    return 'neutral'

def extract_json_from_markdown(text):
    """
    Extrahiert JSON aus Markdown-Codeblöcken.
    """
    if not text or not isinstance(text, str):
        return None
    
    # Suche nach JSON-Codeblöcken
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass
    
    # Falls kein Codeblock: versuche JSON direkt zu finden
    try:
        # Suche nach ersten { und letzten }
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
    except:
        pass
    
    return None

# Hilfsfunktion für historische Daten
def save_snapshot(data, filename_prefix="snapshot"):
    """
    Speichert einen Daten-Snapshot als JSON.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename
