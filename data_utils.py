import json, re, streamlit as st

def extract_json_from_markdown_debug(text, debug_name="n8n"):
    """
    Extrahiert JSON mit ausführlichem Debugging.
    Gibt (json_data, debug_log) zurück.
    """
    debug_log = []
    
    if not text or not isinstance(text, str):
        debug_log.append("❌ Eingabe ist leer oder kein String")
        return None, debug_log
    
    debug_log.append(f"📏 Eingabelänge: {len(text)} Zeichen")
    
    # Versuch 1: Codeblock
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(pattern, text, re.DOTALL)
    debug_log.append(f"🔍 Codeblock-Matches: {len(matches)}")
    
    if matches:
        try:
            result = json.loads(matches[0])
            debug_log.append("✅ JSON aus Codeblock geparst")
            return result, debug_log
        except json.JSONDecodeError as e:
            debug_log.append(f"❌ JSON-Decode-Fehler: {e}")
    
    # Versuch 2: Erste geschweifte Klammern
    start, end = text.find('{'), text.rfind('}')+1
    debug_log.append(f"🔍 Klammern gefunden: Start {start}, End {end}")
    
    if start != -1 and end > start:
        try:
            json_str = text[start:end]
            debug_log.append(f"📄 JSON-Stringlänge: {len(json_str)}")
            result = json.loads(json_str)
            debug_log.append("✅ JSON aus Klammern geparst")
            return result, debug_log
        except Exception as e:
            debug_log.append(f"❌ Parse-Fehler: {e}")
            # Zeige Ausschnitt des Problembereichs
            snippet_start = max(0, start-100)
            snippet_end = min(len(text), end+100)
            debug_log.append(f"🔍 Ausschnitt:\n{text[snippet_start:snippet_end]}")
    
    debug_log.append("❌ Kein JSON gefunden")
    return None, debug_log

# In deiner app.py ersetze extract_json_from_markdown() durch:
# json_data, debug_info = extract_json_from_markdown_debug(response.text)
# for line in debug_info: st.sidebar.text(line)  # Debug in Sidebar
