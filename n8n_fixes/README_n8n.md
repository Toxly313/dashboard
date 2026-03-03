# n8n Workflow Fix: Leere Metriken durch Doppel-Konvertierung

## Problem

Der bisherige Workflow hatte **zwei Code-Nodes** hintereinander:

```
[Webhook Trigger] → [Code in JavaScript12] → [Supabase Format Converter] → [Respond to Webhook2]
```

Das hat drei Fehler verursacht:

1. **Doppel-Konvertierung:** Beide Nodes haben jeweils 2 Items zurueckgegeben (`streamlitResponse` und `supabasePayload`). Der zweite Node hat die bereits konvertierte Ausgabe des ersten Nodes nochmal verarbeitet und dabei die Metriken verloren.

2. **Leeres Objekt ist truthy in JavaScript:** Ein Check wie `if (metrics) { ... }` ist auch bei `metrics = {}` wahr. Deshalb wurde `{}` nie als Fehler erkannt und stillschweigend weitergegeben.

3. **Zwei Items am Webhook:** `Respond to Webhook` hat beide Items als JSON-Array gesendet. Das Dashboard hat dann ein Array statt ein einzelnes Objekt empfangen.

## Loesung

Beide Code-Nodes durch **einen einzigen** Node ersetzen: `unified_converter.js`

### Neuer Workflow

```
[Webhook Trigger] → [Unified Converter] → [Respond to Webhook]
```

### Anleitung

1. Die Nodes **"Code in JavaScript12"** und **"Supabase Format Converter"** aus dem Workflow loeschen.
2. Einen neuen **Code-Node** erstellen und den Inhalt von `unified_converter.js` einfuegen.
3. Den neuen Node zwischen Webhook Trigger und Respond to Webhook verbinden.
4. Testen: Der Webhook sollte jetzt **ein einzelnes JSON-Objekt** mit `success`, `tenant_id`, `analysis_date` und `data.metrics` zurueckgeben — keine leeren `{}` mehr.

### Was der neue Node anders macht

- Gibt **genau 1 Item** zurueck (nur den Dashboard-Contract, kein Supabase-Payload).
- Verwendet `hasKeys(obj)` statt `if (obj)` um leere Objekte `{}` korrekt zu erkennen.
- Erkennt automatisch 6 verschiedene Eingabeformate (AI-Agent, JSON-String, Objekt, Rohdaten, vorformatiert, verschachtelt).

## Optional: Supabase-Speicherung

Falls die Daten weiterhin in Supabase gespeichert werden sollen, einen **separaten Branch** hinzufuegen:

```
                                  ┌→ [Respond to Webhook]
[Webhook Trigger] → [Unified Converter]
                                  └→ [Supabase Node]
```

Der Unified Converter gibt ein sauberes Objekt mit `data.metrics` zurueck — das kann direkt an einen Supabase-Insert-Node weitergegeben werden, ohne zusaetzliche Konvertierung.
