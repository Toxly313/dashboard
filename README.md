# Self-Storage Business Intelligence

Ein Dashboard, das die Kennzahlen eines Self-Storage-Betriebs vor und nach einer
Maßnahme gegenüberstellt und die Veränderung sichtbar macht.

Entstanden 2025 als Prototyp für einen realen Betrieb. Kein Produkt, kein
laufender Dienst, sondern eine Arbeitsprobe.

---

## Wozu

Die meisten Auswertungen zeigen einen Zustand. Interessant ist aber fast immer
die **Differenz**: Was hat sich verändert, seit wir etwas getan haben, und um
wie viel.

Deshalb ist der Vorher-Nachher-Vergleich hier nicht ein Bericht unter vielen,
sondern der Kern der Anwendung. Zwei Analysen, dieselben Kennzahlen, die
Veränderung dazwischen.

## Was es kann

| Bereich | Inhalt |
|---|---|
| **Analyse** | Dokumente und Zahlen einlesen, Auswertung anstoßen |
| **Vergleich** | Vorher gegen Nachher, Kennzahlen mit Differenz |
| **Kunden** | Kundenentwicklung, Veränderungen über den Zeitraum |
| **Kapazität** | Auslastung vorher und nachher |
| **Finanzen** | Umsatz- und Kostenübersicht |
| **Verlauf** | Historie aller Analysen, Entwicklung über die Zeit |
| **System** | Mandanten, Export, Konfiguration |

Dazu Handlungsempfehlungen: einmal lokal aus Regeln abgeleitet, einmal über ein
Sprachmodell im Backend.

## Wie es gebaut ist

```
Streamlit (Python)          Oberfläche, Diagramme über Plotly
        |
        v
n8n (Webhooks)              Auswertung, Dokumentenverarbeitung, LLM-Aufrufe
```

Die Oberfläche hält keine Geschäftslogik. Sie schickt Anfragen an
n8n-Workflows und stellt dar, was zurückkommt. Ohne konfiguriertes Backend
läuft die App mit lokalen Beispieldaten.

Rund 1.500 Zeilen Python, Deployment über Railway vorbereitet.

## Ausführen

```bash
pip install -r requirements.txt
streamlit run app.py
```

Für den Betrieb mit Backend:

```bash
export N8N_BASE_URL="https://ihre-instanz.example.com/webhook"
```

**Ohne diese Variable startet die App im lokalen Modus.** Es ist bewusst keine
Adresse voreingestellt.

## Ehrliche Einordnung

- **Prototyp, kein Produkt.** Letzter Stand April 2026, seitdem nicht gepflegt.
- **Keine Tests.** Die Anwendung ist gewachsen, nicht getestet aufgebaut.
- `app.py` ist mit knapp 1.000 Zeilen zu groß und gehört aufgeteilt.
- Die Auswertungslogik liegt in n8n-Workflows, die **nicht Teil dieses
  Repositories** sind. Ohne sie sieht man die Oberfläche und die
  Beispieldaten, nicht die echte Analyse.
- Die Zahlen im lokalen Modus sind Platzhalter.

## Zum Entstehen

Ich habe den Code nicht selbst getippt. Ich habe die Struktur entworfen,
KI-Werkzeuge angesteuert und geprüft, ob das Ergebnis trägt.

Mein zweites Repository liegt unter
[truth-engine](https://github.com/Toxly313/truth-engine) und beschäftigt sich
mit genau der Frage, die dabei am schwersten war: **woher weiß man, dass ein
gemeldetes Ergebnis tatsächlich eingetreten ist.**

Tobias Tischer · `Tobias.tischer@icloud.com`
